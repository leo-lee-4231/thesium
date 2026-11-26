from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.email_service import EmailSettingsError, EmailSettingsService
from app.application.job_service import MARKET_RETENTION
from app.application.llm_provider_service import LLMProviderError, LLMProviderService
from app.core.config import get_settings
from app.db.models import (
    AgentRun,
    DailyDigest,
    InvestmentDecision,
    InvestmentStream,
    Job,
    MarketSnapshot,
    Notification,
    NotificationPreference,
)

_RUN_WINDOW_DAYS = 7


def _monitor_due_at(stream: InvestmentStream) -> datetime | None:
    if not stream.agent_enabled:
        return None
    interval = max(15, stream.monitor_interval_minutes)
    base = stream.last_monitored_at or stream.created_at
    return base + timedelta(minutes=interval)


async def _counts_by_status(
    session: AsyncSession, model, *, stream_id: UUID, since: datetime, time_column=None
) -> dict[str, int]:
    time_column = time_column or model.created_at
    rows = (
        await session.execute(
            select(model.status, func.count(model.id))
            .where(model.stream_id == stream_id, time_column >= since)
            .group_by(model.status)
        )
    ).all()
    return {str(status): int(count) for status, count in rows}


class OpsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _stream(self, stream_id: UUID | None) -> InvestmentStream | None:
        if stream_id is not None:
            return await self._session.get(InvestmentStream, stream_id)
        return await self._session.scalar(
            select(InvestmentStream)
            .where(InvestmentStream.status == "ACTIVE")
            .order_by(InvestmentStream.created_at.desc())
            .limit(1)
        )

    async def summary(
        self, *, stream_id: UUID | None = None, now: datetime | None = None
    ) -> dict[str, object]:
        now = now or datetime.now(UTC)
        stream = await self._stream(stream_id)
        latest_retention = await self._session.scalar(
            select(Job).where(Job.kind == MARKET_RETENTION).order_by(Job.created_at.desc()).limit(1)
        )
        maintenance = {
            "market_retention": {
                "enabled": get_settings().market_retention_enabled,
                "last": _retention_dict(latest_retention),
            }
        }
        if stream is None:
            return {
                "scheduler_enabled": get_settings().scheduler_enabled,
                "stream": None,
                "message": "没有 ACTIVE 投资产品",
                "maintenance": maintenance,
            }

        since_24h = now - timedelta(hours=24)
        since_7d = now - timedelta(days=_RUN_WINDOW_DAYS)
        runs_24h = await _counts_by_status(
            self._session,
            AgentRun,
            stream_id=stream.id,
            since=since_24h,
            time_column=AgentRun.started_at,
        )
        runs_7d = await _counts_by_status(
            self._session,
            AgentRun,
            stream_id=stream.id,
            since=since_7d,
            time_column=AgentRun.started_at,
        )
        jobs_24h = await _counts_by_status(self._session, Job, stream_id=stream.id, since=since_24h)
        notifications_7d = await _counts_by_status(
            self._session, Notification, stream_id=stream.id, since=since_7d
        )

        latest_run = await self._session.scalar(
            select(AgentRun)
            .where(AgentRun.stream_id == stream.id)
            .order_by(AgentRun.started_at.desc())
            .limit(1)
        )
        last_failed_run = await self._session.scalar(
            select(AgentRun)
            .where(AgentRun.stream_id == stream.id, AgentRun.status == "FAILED")
            .order_by(AgentRun.started_at.desc())
            .limit(1)
        )
        latest_decision = await self._session.scalar(
            select(InvestmentDecision)
            .where(InvestmentDecision.stream_id == stream.id)
            .order_by(InvestmentDecision.created_at.desc())
            .limit(1)
        )
        decision_count_24h = (
            await self._session.scalar(
                select(func.count(InvestmentDecision.id)).where(
                    InvestmentDecision.stream_id == stream.id,
                    InvestmentDecision.created_at >= since_24h,
                )
            )
            or 0
        )
        decision_count_7d = (
            await self._session.scalar(
                select(func.count(InvestmentDecision.id)).where(
                    InvestmentDecision.stream_id == stream.id,
                    InvestmentDecision.created_at >= since_7d,
                )
            )
            or 0
        )
        failed_jobs_24h = int(jobs_24h.get("FAILED", 0))
        pending_jobs = (
            await self._session.scalar(
                select(func.count(Job.id)).where(
                    Job.status.in_(["PENDING", "RUNNING"]),
                    Job.stream_id == stream.id,
                )
            )
            or 0
        )
        latest_market = await self._session.scalar(
            select(MarketSnapshot)
            .where(MarketSnapshot.instrument_id == stream.primary_instrument_id)
            .order_by(MarketSnapshot.created_at.desc())
            .limit(1)
        )
        latest_digest = await self._session.scalar(
            select(DailyDigest)
            .where(DailyDigest.stream_id == stream.id)
            .order_by(DailyDigest.local_date.desc())
            .limit(1)
        )
        recent_jobs = (
            (
                await self._session.execute(
                    select(Job)
                    .where(Job.stream_id == stream.id)
                    .order_by(Job.created_at.desc())
                    .limit(12)
                )
            )
            .scalars()
            .all()
        )
        recent_runs = (
            (
                await self._session.execute(
                    select(AgentRun)
                    .where(AgentRun.stream_id == stream.id)
                    .order_by(AgentRun.started_at.desc())
                    .limit(12)
                )
            )
            .scalars()
            .all()
        )
        prefs = await self._session.scalar(select(NotificationPreference).limit(1))

        email_configured = False
        try:
            email_status = await EmailSettingsService(self._session).status()
            email_configured = bool(email_status["configured"])
        except EmailSettingsError:
            email_configured = False
        llm_configured = False
        try:
            llm_configured = bool((await LLMProviderService(self._session).status())["configured"])
        except LLMProviderError:
            llm_configured = False

        return {
            "scheduler_enabled": get_settings().scheduler_enabled,
            "stream": {
                "id": stream.id,
                "name": stream.name,
                "status": stream.status,
                "timezone": stream.timezone,
                "agent_enabled": stream.agent_enabled,
                "monitor_interval_minutes": stream.monitor_interval_minutes,
                "last_monitored_at": stream.last_monitored_at,
                "next_monitor_at": _monitor_due_at(stream),
            },
            "runs": {
                "last_24h": runs_24h,
                "last_7d": runs_7d,
                "latest": _run_dict(latest_run),
                "last_failed": _run_dict(last_failed_run),
            },
            "jobs": {
                "last_24h": jobs_24h,
                "pending_or_running": int(pending_jobs),
                "failed_24h": failed_jobs_24h,
                "recent": [_job_dict(job) for job in recent_jobs],
            },
            "decisions": {
                "last_24h": int(decision_count_24h),
                "last_7d": int(decision_count_7d),
                "latest": _decision_dict(latest_decision),
            },
            "notifications": {"last_7d": notifications_7d},
            "market": {
                "last_snapshot_at": latest_market.created_at if latest_market else None,
                "price": str(latest_market.price) if latest_market else None,
                "staleness": latest_market.staleness if latest_market else "UNKNOWN",
            },
            "daily_digest": {
                "enabled": bool(prefs.daily_summary_enabled) if prefs else False,
                "time": prefs.daily_summary_time if prefs else "08:00",
                "last": _digest_dict(latest_digest),
                "news_enabled": bool(prefs.news_enabled) if prefs else True,
            },
            "config": {
                "email_configured": email_configured,
                "llm_configured": llm_configured,
            },
            "maintenance": maintenance,
            "recent_runs": [_run_dict(run) for run in recent_runs],
        }


def _run_dict(run: AgentRun | None) -> dict[str, object] | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "task_type": run.task_type,
        "status": run.status,
        "model": run.model,
        "latency_ms": run.latency_ms,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


def _retention_dict(job: Job | None) -> dict[str, object] | None:
    if job is None:
        return None
    return {
        **_job_dict(job),
        "deleted": (job.payload or {}).get("deleted", {}),
    }


def _job_dict(job: Job) -> dict[str, object]:
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "attempts": job.attempts,
        "last_error": job.last_error,
        "scheduled_at": job.scheduled_at,
        "finished_at": job.finished_at,
    }


def _decision_dict(decision: InvestmentDecision | None) -> dict[str, object] | None:
    if decision is None:
        return None
    return {
        "id": decision.id,
        "decision": decision.decision,
        "priority": decision.priority,
        "summary": decision.summary,
        "created_at": decision.created_at,
    }


def _digest_dict(digest: DailyDigest | None) -> dict[str, object] | None:
    if digest is None:
        return None
    return {
        "id": digest.id,
        "local_date": digest.local_date,
        "status": digest.status,
        "sent_at": digest.sent_at,
        "error": digest.error,
    }
