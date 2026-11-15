from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job

MONITOR_ANALYSIS = "MONITOR_ANALYSIS"
NOTIFICATION_SEND = "NOTIFICATION_SEND"
DAILY_DIGEST = "DAILY_DIGEST"


async def enqueue(
    session: AsyncSession,
    *,
    kind: str,
    stream_id: UUID | None = None,
    payload: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
    scheduled_at: datetime | None = None,
    priority: int = 100,
    max_attempts: int = 3,
) -> bool:
    """Insert a job once. Returns False when the dedupe key already exists."""

    values = {
        "kind": kind,
        "status": "PENDING",
        "stream_id": stream_id,
        "dedupe_key": dedupe_key,
        "priority": priority,
        "payload": payload or {},
        "attempts": 0,
        "max_attempts": max_attempts,
        "scheduled_at": scheduled_at or datetime.now(UTC),
    }
    statement = pg_insert(Job).values(**values)
    if dedupe_key is not None:
        statement = statement.on_conflict_do_nothing(index_elements=["dedupe_key"])
    result = await session.execute(statement.returning(Job.id))
    return result.scalar_one_or_none() is not None


async def reschedule(
    session: AsyncSession,
    *,
    dedupe_key: str,
    scheduled_at: datetime,
    last_error: str | None = None,
    reset_attempts: bool = True,
) -> bool:
    job = await session.scalar(select(Job).where(Job.dedupe_key == dedupe_key))
    if job is None:
        return False
    job.status = "PENDING"
    job.scheduled_at = scheduled_at
    job.last_error = last_error
    job.finished_at = None
    if reset_attempts:
        job.attempts = 0
    return True