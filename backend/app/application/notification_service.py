from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.email_service import EmailSettingsError, EmailSettingsService
from app.application.job_service import NOTIFICATION_SEND, enqueue, reschedule
from app.application.notification_templates import build_notification
from app.core.users import LOCAL_USER_EMAIL
from app.db.models import (
    Asset,
    InvestmentDecision,
    InvestmentStream,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    User,
)
from app.domain.notification import (
    DecisionFacts,
    NotificationHistoryItem,
    Preferences,
    evaluate,
)
from app.infrastructure.email.sender import EmailError, OutboundEmail, send_email

logger = logging.getLogger(__name__)

RETRY_BACKOFF_MINUTES = (1, 5, 30)
RETRYABLE_EMAIL_CODES = {"EMAIL_CONNECT", "EMAIL_SMTP"}


def _preferences_from_row(row: NotificationPreference | None) -> Preferences:
    if row is None:
        return Preferences()
    return Preferences(
        decision_alert_enabled=row.decision_alert_enabled,
        risk_alert_enabled=row.risk_alert_enabled,
        email_enabled=row.email_enabled,
        quiet_hours_enabled=row.quiet_hours_enabled,
        quiet_hours_start=row.quiet_hours_start,
        quiet_hours_end=row.quiet_hours_end,
        daily_email_limit=row.daily_email_limit,
        cooldown_minutes=row.cooldown_minutes,
    )


def _facts(decision: InvestmentDecision) -> DecisionFacts:
    thresholds: list[str] = []
    triggered: list[str] = []
    for item in decision.invalidation_conditions or []:
        if not isinstance(item, dict):
            continue
        threshold = item.get("threshold")
        if threshold is not None:
            thresholds.append(str(threshold))
        if item.get("triggered") is True:
            triggered.append(str(threshold or item.get("condition") or "triggered"))
    return DecisionFacts(
        decision=decision.decision,
        priority=decision.priority,
        alignment=(decision.thesis_alignment or {}).get("status", "UNKNOWN"),
        data_quality=(decision.data_quality or {}).get("status", "GOOD"),
        position_assessment=(decision.position_impact or {}).get(
            "assessment", "NO_POSITION"
        ),
        derivative_action=(decision.derivative_recommendation or {}).get("action"),
        invalidation_thresholds=tuple(thresholds),
        triggered_invalidations=tuple(triggered),
    )


def _day_start_utc(timezone: str, now: datetime) -> datetime:
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("Asia/Shanghai")
    local = now.astimezone(zone)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC)


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _user(self) -> User:
        user = await self._session.scalar(select(User).where(User.email == LOCAL_USER_EMAIL))
        if user is None:
            raise RuntimeError("local user not found; run seed")
        return user

    async def preferences_row(self) -> NotificationPreference | None:
        return await self._session.scalar(select(NotificationPreference).limit(1))

    async def preferences(self) -> dict[str, object]:
        row = await self.preferences_row()
        prefs = _preferences_from_row(row)
        return {
            "decision_alert_enabled": prefs.decision_alert_enabled,
            "risk_alert_enabled": prefs.risk_alert_enabled,
            "email_enabled": prefs.email_enabled,
            "daily_summary_enabled": bool(row.daily_summary_enabled) if row else False,
            "quiet_hours_enabled": prefs.quiet_hours_enabled,
            "quiet_hours_start": prefs.quiet_hours_start,
            "quiet_hours_end": prefs.quiet_hours_end,
            "daily_email_limit": prefs.daily_email_limit,
            "cooldown_minutes": prefs.cooldown_minutes,
            "feishu_push_enabled": bool(row.feishu_push_enabled) if row else False,
        }

    async def save_preferences(
        self,
        *,
        decision_alert_enabled: bool,
        risk_alert_enabled: bool,
        email_enabled: bool,
        daily_summary_enabled: bool,
        quiet_hours_enabled: bool,
        quiet_hours_start: str,
        quiet_hours_end: str,
        daily_email_limit: int,
        cooldown_minutes: int,
        feishu_push_enabled: bool = False,
    ) -> dict[str, object]:
        for value in (quiet_hours_start, quiet_hours_end):
            try:
                hour, minute = value.split(":", 1)
                if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
                    raise ValueError
            except (ValueError, AttributeError) as exc:
                raise ValueError(f"invalid quiet-hours value: {value!r}") from exc
        user = await self._user()
        row = await self.preferences_row()
        if row is None:
            row = NotificationPreference(user_id=user.id)
            self._session.add(row)
        row.decision_alert_enabled = decision_alert_enabled
        row.risk_alert_enabled = risk_alert_enabled
        row.email_enabled = email_enabled
        row.daily_summary_enabled = daily_summary_enabled
        row.quiet_hours_enabled = quiet_hours_enabled
        row.quiet_hours_start = quiet_hours_start
        row.quiet_hours_end = quiet_hours_end
        row.daily_email_limit = daily_email_limit
        row.cooldown_minutes = cooldown_minutes
        row.feishu_push_enabled = feishu_push_enabled
        await self._session.commit()
        return await self.preferences()

    async def evaluate_and_create(
        self,
        *,
        stream: InvestmentStream,
        asset: Asset,
        decision: InvestmentDecision,
        now: datetime | None = None,
    ) -> Notification | None:
        existing = await self._session.scalar(
            select(Notification).where(Notification.decision_id == decision.id)
        )
        if existing is not None:
            return existing

        now = now or datetime.now(UTC)
        user = await self._user()
        prefs = _preferences_from_row(await self.preferences_row())
        previous = await self._session.scalar(
            select(InvestmentDecision)
            .where(
                InvestmentDecision.stream_id == stream.id,
                InvestmentDecision.id != decision.id,
                InvestmentDecision.created_at <= decision.created_at,
            )
            .order_by(InvestmentDecision.created_at.desc())
            .limit(1)
        )
        recent_rows = (
            await self._session.execute(
                select(Notification)
                .where(
                    Notification.stream_id == stream.id,
                    Notification.status.in_(["SENT", "PENDING", "RETRYING"]),
                )
                .order_by(Notification.created_at.desc())
                .limit(12)
            )
        ).scalars()
        recent = [
            NotificationHistoryItem(
                dedupe_key=row.dedupe_key,
                decision=row.decision,
                alignment=row.alignment,
                priority=row.priority,
                created_at=row.created_at,
            )
            for row in recent_rows
        ]

        start = _day_start_utc(stream.timezone, now)
        emails_sent = (
            await self._session.scalar(
                select(func.count(NotificationDelivery.id))
                .join(
                    Notification,
                    NotificationDelivery.notification_id == Notification.id,
                )
                .where(
                    Notification.user_id == user.id,
                    NotificationDelivery.channel == "EMAIL",
                    NotificationDelivery.status == "SENT",
                    NotificationDelivery.sent_at >= start,
                )
            )
            or 0
        )

        facts = _facts(decision)
        result = evaluate(
            stream_id=stream.id,
            facts=facts,
            previous_decision=_facts(previous) if previous is not None else None,
            preferences=prefs,
            recent=recent,
            emails_sent_today=int(emails_sent),
            now=now,
            timezone=stream.timezone,
        )
        if not result.notify and not result.triggered_rules:
            logger.info(
                "notification skipped without trigger",
                extra={"stream_id": str(stream.id), "reason": result.reason},
            )
            return None

        title, body_text, body_html = build_notification(
            stream=stream,
            asset=asset,
            decision=decision,
            priority=result.priority,
            triggered_rules=result.triggered_rules,
        )

        notification = Notification(
            user_id=user.id,
            stream_id=stream.id,
            decision_id=decision.id,
            status="SKIPPED",
            decision=decision.decision,
            alignment=facts.alignment,
            priority=result.priority,
            title=title,
            body_text=body_text,
            body_html=body_html,
            dedupe_key=result.dedupe_key,
            triggered_rules=result.triggered_rules,
            reason=result.reason,
        )
        self._session.add(notification)
        await self._session.flush()

        if not result.notify:
            await self._session.commit()
            await self._session.refresh(notification)
            return notification

        web = NotificationDelivery(
            notification_id=notification.id,
            channel="WEB",
            status="SENT",
            attempts=1,
            sent_at=now,
        )
        self._session.add(web)

        email_config = None
        try:
            email_config = await EmailSettingsService(self._session).config()
        except EmailSettingsError as exc:
            logger.warning("email config unreadable: %s", exc.code)
        email_delivery: NotificationDelivery | None = None
        if prefs.email_enabled:
            email_delivery = NotificationDelivery(
                notification_id=notification.id,
                channel="EMAIL",
                status="PENDING" if email_config is not None else "SKIPPED",
                attempts=0,
                last_error=None if email_config is not None else "SMTP_NOT_CONFIGURED",
            )
            self._session.add(email_delivery)

        if email_delivery is not None and email_delivery.status == "PENDING":
            notification.status = "PENDING"
            await enqueue(
                self._session,
                kind=NOTIFICATION_SEND,
                stream_id=stream.id,
                payload={"notification_id": str(notification.id)},
                dedupe_key=f"notification:{notification.id}",
                scheduled_at=now,
                priority=50,
                max_attempts=3,
            )
        else:
            notification.status = "SENT"
        await self._session.commit()
        await self._session.refresh(notification)
        return notification

    async def send(self, notification_id: UUID) -> datetime | None:
        notification = await self._session.get(Notification, notification_id)
        if notification is None:
            return None
        if notification.status not in {"PENDING", "RETRYING"}:
            return None
        now = datetime.now(UTC)
        deliveries = (
            await self._session.execute(
                select(NotificationDelivery).where(
                    NotificationDelivery.notification_id == notification.id
                )
            )
        ).scalars().all()
        email_config = None
        email_config_error: str | None = None
        try:
            email_config = await EmailSettingsService(self._session).config()
        except EmailSettingsError as exc:
            email_config_error = exc.code

        retry_at: datetime | None = None
        for delivery in deliveries:
            if delivery.channel != "EMAIL":
                if delivery.status == "PENDING":
                    delivery.status = "SENT"
                    delivery.sent_at = now
                continue
            if delivery.status not in {"PENDING"}:
                continue
            if delivery.next_attempt_at is not None and delivery.next_attempt_at > now:
                retry_at = min(
                    retry_at or delivery.next_attempt_at, delivery.next_attempt_at
                )
                continue
            if email_config is None:
                delivery.status = "FAILED"
                delivery.attempts += 1
                delivery.last_error = email_config_error or "SMTP_NOT_CONFIGURED"
                continue

            delivery.attempts += 1
            try:
                await send_email(
                    email_config,
                    OutboundEmail(
                        to=email_config.to_address or email_config.from_address,
                        subject=notification.title,
                        text=notification.body_text,
                        html=notification.body_html,
                    ),
                )
            except EmailError as exc:
                delivery.last_error = f"{exc.code}: {exc.message}"
                if (
                    exc.code in RETRYABLE_EMAIL_CODES
                    and delivery.attempts < len(RETRY_BACKOFF_MINUTES)
                ):
                    delay = RETRY_BACKOFF_MINUTES[delivery.attempts - 1]
                    delivery.status = "PENDING"
                    delivery.next_attempt_at = now + timedelta(minutes=delay)
                    retry_at = min(
                        retry_at or delivery.next_attempt_at, delivery.next_attempt_at
                    )
                else:
                    delivery.status = "FAILED"
            else:
                delivery.status = "SENT"
                delivery.sent_at = now
                delivery.last_error = None
                delivery.next_attempt_at = None

        statuses = [delivery.status for delivery in deliveries]
        if any(status == "PENDING" for status in statuses):
            notification.status = "RETRYING" if retry_at else "PENDING"
        elif any(status == "SENT" for status in statuses):
            notification.status = "SENT"
        elif statuses and all(status == "SKIPPED" for status in statuses):
            notification.status = "SKIPPED"
        else:
            notification.status = "FAILED"
        await self._session.commit()
        return retry_at

    async def retry(self, notification_id: UUID) -> Notification | None:
        notification = await self._session.get(Notification, notification_id)
        if notification is None:
            return None
        deliveries = (
            await self._session.execute(
                select(NotificationDelivery).where(
                    NotificationDelivery.notification_id == notification.id
                )
            )
        ).scalars().all()
        changed = False
        for delivery in deliveries:
            if delivery.status in {"FAILED", "SKIPPED"} and delivery.channel == "EMAIL":
                delivery.status = "PENDING"
                delivery.attempts = 0
                delivery.next_attempt_at = None
                delivery.last_error = None
                changed = True
        if not changed:
            return notification
        notification.status = "PENDING"
        await enqueue(
            self._session,
            kind=NOTIFICATION_SEND,
            stream_id=notification.stream_id,
            payload={"notification_id": str(notification.id)},
            dedupe_key=f"notification:{notification.id}",
            scheduled_at=datetime.now(UTC),
            priority=50,
            max_attempts=3,
        )
        await reschedule(
            self._session,
            dedupe_key=f"notification:{notification.id}",
            scheduled_at=datetime.now(UTC),
        )
        await self._session.commit()
        await self._session.refresh(notification)
        return notification

    async def list_notifications(
        self, *, stream_id: UUID | None = None, limit: int = 30
    ) -> list[dict[str, Any]]:
        statement = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
        if stream_id is not None:
            statement = statement.where(Notification.stream_id == stream_id)
        rows = (await self._session.execute(statement)).scalars().all()
        deliveries = {}
        if rows:
            delivery_rows = (
                await self._session.execute(
                    select(NotificationDelivery).where(
                        NotificationDelivery.notification_id.in_([row.id for row in rows])
                    )
                )
            ).scalars().all()
            for delivery in delivery_rows:
                deliveries.setdefault(delivery.notification_id, []).append(
                    {
                        "channel": delivery.channel,
                        "status": delivery.status,
                        "attempts": delivery.attempts,
                        "sent_at": delivery.sent_at,
                        "next_attempt_at": delivery.next_attempt_at,
                        "last_error": delivery.last_error,
                    }
                )
        return [
            {
                "id": row.id,
                "stream_id": row.stream_id,
                "decision_id": row.decision_id,
                "status": row.status,
                "decision": row.decision,
                "alignment": row.alignment,
                "priority": row.priority,
                "title": row.title,
                "body_text": row.body_text,
                "reason": row.reason,
                "triggered_rules": row.triggered_rules,
                "created_at": row.created_at,
                "deliveries": deliveries.get(row.id, []),
            }
            for row in rows
        ]