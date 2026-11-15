from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime import AgentError, AgentRuntime
from app.application.digest_templates import build_daily_digest
from app.application.email_service import EmailSettingsError, EmailSettingsService
from app.application.market_service import MarketService
from app.application.news_service import NewsService
from app.application.ops_service import OpsService
from app.core.users import LOCAL_USER_EMAIL
from app.db.models import (
    AgentRun,
    Asset,
    DailyDigest,
    InvestmentDecision,
    InvestmentStream,
    NotificationPreference,
    User,
)
from app.infrastructure.email.sender import EmailError, OutboundEmail, send_email

logger = logging.getLogger(__name__)


class DigestError(Exception):
    pass


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Asia/Shanghai")


def _decision_payload(decision: InvestmentDecision | None) -> dict[str, object] | None:
    if decision is None:
        return None
    return {
        "id": decision.id,
        "decision": decision.decision,
        "priority": decision.priority,
        "confidence": str(decision.confidence),
        "summary": decision.summary,
    }


class DigestService:
    def __init__(self, session: AsyncSession, market: MarketService) -> None:
        self._session = session
        self._market = market

    async def _user(self) -> User:
        user = await self._session.scalar(select(User).where(User.email == LOCAL_USER_EMAIL))
        if user is None:
            raise DigestError("local user not found; run seed")
        return user

    async def _prefs(self) -> NotificationPreference | None:
        return await self._session.scalar(select(NotificationPreference).limit(1))

    async def ensure_and_send(
        self, *, stream_id: UUID, local_date: date
    ) -> DailyDigest:
        stream = await self._session.get(InvestmentStream, stream_id)
        if stream is None:
            raise DigestError("investment stream not found")
        asset = await self._session.get(Asset, stream.asset_id)
        if asset is None:
            raise DigestError("asset not found")
        user = await self._user()
        prefs = await self._prefs()

        existing = await self._session.scalar(
            select(DailyDigest).where(
                DailyDigest.stream_id == stream.id,
                DailyDigest.local_date == local_date,
            )
        )
        if existing is not None:
            if existing.status == "SENT":
                return existing
            await self._send(existing)
            await self._session.refresh(existing)
            return existing

        zone = _zone(stream.timezone)
        summary_time = time.fromisoformat(prefs.daily_summary_time if prefs else "08:00")
        scheduled_for = datetime.combine(local_date, summary_time, tzinfo=zone)

        analysis_error: str | None = None
        context: dict[str, object] | None = None
        decision_row: InvestmentDecision | None = None
        run_id: UUID | None = None
        recent_cutoff = datetime.now(UTC) - timedelta(minutes=15)
        recent_run = await self._session.scalar(
            select(AgentRun)
            .where(
                AgentRun.stream_id == stream.id,
                AgentRun.task_type == "MONITOR_ANALYSIS",
                AgentRun.status == "SUCCEEDED",
                AgentRun.started_at >= recent_cutoff,
            )
            .order_by(AgentRun.started_at.desc())
            .limit(1)
        )
        if recent_run is not None:
            run_id = recent_run.id
            context = recent_run.input_context
            decision_row = await self._session.scalar(
                select(InvestmentDecision).where(
                    InvestmentDecision.agent_run_id == recent_run.id
                )
            )
        else:
            try:
                result = await AgentRuntime(self._session, self._market).run_monitor(stream.id)
                run_id = result["run"].id
                decision_row = result["decision"]
                context = result.get("context")  # type: ignore[assignment]
            except AgentError as exc:
                analysis_error = f"{exc.code}: {exc.message}"
                run_id = exc.run_id
                logger.warning("daily digest analysis failed: %s", analysis_error)
            except Exception as exc:  # noqa: BLE001 - digest must still be sent
                analysis_error = f"{type(exc).__name__}: {exc}"
                logger.exception("daily digest analysis failed")

        ops = await OpsService(self._session).summary(stream_id=stream.id)
        news: list[dict[str, object]] = []
        if prefs is None or prefs.news_enabled:
            try:
                news = await NewsService(self._session).refresh_and_latest(limit=10)
            except Exception as exc:  # noqa: BLE001 - news is optional
                logger.warning("daily digest news unavailable: %s", exc)

        decision = _decision_payload(decision_row)
        subject, body_text, body_html = build_daily_digest(
            stream=stream,
            asset=asset,
            context=context,  # type: ignore[arg-type]
            decision=decision,
            decision_summary=(decision_row.summary if decision_row is not None else None),
            analysis_error=analysis_error,
            ops=ops,
            news=news,
            scheduled_for=scheduled_for,
        )
        digest = DailyDigest(
            user_id=user.id,
            stream_id=stream.id,
            local_date=local_date,
            status="PENDING",
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            agent_run_id=run_id,
            attempts=0,
        )
        self._session.add(digest)
        await self._session.commit()
        await self._session.refresh(digest)
        await self._send(digest)
        await self._session.refresh(digest)
        return digest

    async def _send(self, digest: DailyDigest) -> None:
        digest.attempts += 1
        try:
            config = await EmailSettingsService(self._session).config()
        except EmailSettingsError as exc:
            await self._mark_failed(digest, f"{exc.code}: {exc.message}")
            raise DigestError(f"email config unavailable: {exc.code}") from exc
        if config is None:
            await self._mark_failed(digest, "SMTP_NOT_CONFIGURED")
            raise DigestError("SMTP is not configured")
        try:
            await send_email(
                config,
                OutboundEmail(
                    to=config.to_address or config.from_address,
                    subject=digest.subject,
                    text=digest.body_text,
                    html=digest.body_html,
                ),
            )
        except EmailError as exc:
            await self._mark_failed(digest, f"{exc.code}: {exc.message}")
            raise DigestError(f"{exc.code}: {exc.message}") from exc
        digest.status = "SENT"
        digest.error = None
        digest.sent_at = datetime.now(UTC)
        await self._session.commit()

    async def _mark_failed(self, digest: DailyDigest, error: str) -> None:
        digest.status = "FAILED"
        digest.error = error[:2000]
        await self._session.commit()