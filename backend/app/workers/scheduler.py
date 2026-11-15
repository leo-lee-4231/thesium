from __future__ import annotations

import logging
from datetime import UTC, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.job_service import DAILY_DIGEST, MONITOR_ANALYSIS, enqueue
from app.application.llm_provider_service import LLMProviderError, LLMProviderService
from app.db.models import DailyDigest, InvestmentStream, Job, NotificationPreference

logger = logging.getLogger(__name__)


def monitor_due_at(stream: InvestmentStream) -> datetime | None:
    interval = max(15, stream.monitor_interval_minutes)
    base = stream.last_monitored_at or stream.created_at
    return base + timedelta(minutes=interval)


async def enqueue_due_monitors(
    session: AsyncSession, *, now: datetime | None = None
) -> int:
    """Create at most one monitor job per active product.

    The LLM is checked first: without a configured provider a scheduled run can
    only fail, so the scheduler stays quiet until Settings is complete.
    """

    now = now or datetime.now(UTC)
    try:
        config = await LLMProviderService(session).config()
    except LLMProviderError as exc:
        logger.warning("scheduler cannot read LLM config: %s", exc.code)
        return 0
    if config is None:
        return 0

    active_job_streams = set(
        (
            await session.execute(
                select(Job.stream_id).where(
                    Job.kind == MONITOR_ANALYSIS,
                    Job.status.in_(["PENDING", "RUNNING"]),
                )
            )
        )
        .scalars()
        .all()
    )
    streams = (
        (
            await session.execute(
                select(InvestmentStream)
                .where(
                    InvestmentStream.status == "ACTIVE",
                    InvestmentStream.agent_enabled.is_(True),
                )
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    created = 0
    for stream in streams:
        if stream.id in active_job_streams:
            continue
        due_at = monitor_due_at(stream)
        if due_at is not None and due_at > now:
            continue
        slot = int(now.timestamp() // 60)
        inserted = await enqueue(
            session,
            kind=MONITOR_ANALYSIS,
            stream_id=stream.id,
            payload={"stream_id": str(stream.id)},
            dedupe_key=f"monitor:{stream.id}:{slot}",
            scheduled_at=now,
            priority=100,
            max_attempts=2,
        )
        if inserted:
            created += 1
            logger.info(
                "scheduled monitor analysis",
                extra={
                    "stream_id": str(stream.id),
                    "due_at": due_at.isoformat() if due_at else None,
                },
            )
    await session.commit()
    return created


async def claim_jobs(
    session: AsyncSession, *, limit: int = 3, now: datetime | None = None
) -> list[UUID]:
    now = now or datetime.now(UTC)
    jobs = (
        (
            await session.execute(
                select(Job)
                .where(Job.status == "PENDING", Job.scheduled_at <= now)
                .order_by(Job.priority.asc(), Job.scheduled_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    ids: list[UUID] = []
    for job in jobs:
        job.status = "RUNNING"
        job.started_at = now
        job.attempts += 1
        ids.append(job.id)
    await session.commit()
    return ids


async def recover_stale_jobs(
    session: AsyncSession, *, now: datetime | None = None, stale_minutes: int = 30
) -> int:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(minutes=max(1, stale_minutes))
    jobs = (
        (
            await session.execute(
                select(Job)
                .where(Job.status == "RUNNING", Job.started_at < cutoff)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    recovered = 0
    for job in jobs:
        if job.attempts >= job.max_attempts:
            job.status = "FAILED"
            job.finished_at = now
            job.last_error = "stale running job exceeded max attempts"
        else:
            job.status = "PENDING"
            job.scheduled_at = now
            job.started_at = None
            job.last_error = "recovered stale running job"
        recovered += 1
    if recovered:
        logger.warning("recovered %s stale jobs", recovered)
    await session.commit()
    return recovered

def _daily_digest_slot(
    stream: InvestmentStream, prefs, now: datetime
) -> tuple[object, datetime] | None:
    if not prefs.daily_summary_enabled or not stream.agent_enabled:
        return None
    try:
        zone = ZoneInfo(stream.timezone)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("Asia/Shanghai")
    local_now = now.astimezone(zone)
    try:
        summary_time = time.fromisoformat(prefs.daily_summary_time or "08:00")
    except ValueError:
        summary_time = time(8, 0)
    scheduled = datetime.combine(local_now.date(), summary_time, tzinfo=zone)
    if local_now < scheduled:
        return None
    # Catch up after a worker restart, but do not send a "morning" digest at night.
    if local_now.hour >= 12:
        return None
    return local_now.date(), scheduled


async def enqueue_due_daily_digests(
    session: AsyncSession, *, now: datetime | None = None
) -> int:
    now = now or datetime.now(UTC)
    prefs = await session.scalar(
        select(NotificationPreference).limit(1)
    )
    if prefs is None or not prefs.daily_summary_enabled:
        return 0
    streams = (
        (
            await session.execute(
                select(InvestmentStream)
                .where(
                    InvestmentStream.status == "ACTIVE",
                    InvestmentStream.agent_enabled.is_(True),
                )
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    created = 0
    for stream in streams:
        slot = _daily_digest_slot(stream, prefs, now)
        if slot is None:
            continue
        local_date, _scheduled = slot
        dedupe_key = f"digest:{stream.id}:{local_date.isoformat()}"
        existing_digest = await session.scalar(
            select(DailyDigest).where(
                DailyDigest.stream_id == stream.id,
                DailyDigest.local_date == local_date,
            )
        )
        if existing_digest is not None and existing_digest.status == "SENT":
            continue
        existing_job = await session.scalar(
            select(Job).where(Job.dedupe_key == dedupe_key).limit(1)
        )
        if existing_job is not None:
            # Never auto-reset a failed digest job: it would retry every tick.
            continue
        inserted = await enqueue(
            session,
            kind=DAILY_DIGEST,
            stream_id=stream.id,
            payload={
                "stream_id": str(stream.id),
                "local_date": local_date.isoformat(),
            },
            dedupe_key=dedupe_key,
            scheduled_at=now,
            priority=10,
            max_attempts=3,
        )
        if inserted:
            created += 1
            logger.info(
                "scheduled daily digest stream_id=%s date=%s",
                stream.id,
                local_date,
            )
    await session.commit()
    return created
