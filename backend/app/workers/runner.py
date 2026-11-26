from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.agent.runtime import AgentError, AgentRuntime
from app.application.digest_service import DigestService
from app.application.job_service import (
    DAILY_DIGEST,
    MARKET_RETENTION,
    MONITOR_ANALYSIS,
    NOTIFICATION_SEND,
)
from app.application.market_service import MarketService
from app.application.notification_service import NotificationService
from app.application.retention_service import RetentionService
from app.db.models import Asset, InvestmentStream, Job
from app.db.session import SessionLocal
from app.infrastructure.market.factory import create_provider

logger = logging.getLogger(__name__)

RETRY_BACKOFF_MINUTES = (1, 5, 30)


class JobRunner:
    async def run(self, job_id: UUID) -> None:
        async with SessionLocal() as session:
            job = await session.get(Job, job_id)
            if job is None or job.status != "RUNNING":
                return
            try:
                retry_at: datetime | None = None
                if job.kind == MONITOR_ANALYSIS:
                    await self._run_monitor(session, job)
                elif job.kind == DAILY_DIGEST:
                    await self._run_daily_digest(session, job)
                elif job.kind == NOTIFICATION_SEND:
                    retry_at = await self._run_notification(session, job)
                elif job.kind == MARKET_RETENTION:
                    await self._run_market_retention(session)
                else:
                    raise RuntimeError(f"unknown job kind: {job.kind}")
            except Exception as exc:  # noqa: BLE001 - jobs must record every failure
                await self._fail(session, job, exc)
            else:
                if retry_at is not None:
                    job.status = "PENDING"
                    job.scheduled_at = retry_at
                    job.started_at = None
                    job.last_error = "delivery retry scheduled"
                    await session.commit()
                    logger.info(
                        "notification delivery retry scheduled",
                        extra={"job_id": str(job.id), "retry_at": retry_at.isoformat()},
                    )
                    return
                job.status = "SUCCEEDED"
                job.finished_at = datetime.now(UTC)
                job.last_error = None
                await session.commit()
                logger.info("job succeeded", extra={"job_id": str(job.id), "kind": job.kind})

    async def _run_monitor(self, session, job: Job) -> None:
        if job.stream_id is None:
            raise RuntimeError("monitor job has no stream_id")
        stream = await session.get(InvestmentStream, job.stream_id)
        if stream is None:
            raise RuntimeError("investment stream not found")
        stream.last_monitored_at = datetime.now(UTC)
        await session.commit()

        provider = await create_provider(session)
        try:
            runtime = AgentRuntime(session, MarketService(session, provider))
            result = await runtime.run_monitor(stream.id)
            asset = await session.get(Asset, stream.asset_id)
            if asset is None:
                raise RuntimeError("asset not found")
            await NotificationService(session).evaluate_and_create(
                stream=stream,
                asset=asset,
                decision=result["decision"],
            )
        finally:
            await provider.close()

    async def _run_daily_digest(self, session, job: Job) -> None:
        from datetime import date

        payload = job.payload or {}
        stream_id = payload.get("stream_id")
        local_date = payload.get("local_date")
        if not stream_id or not local_date:
            raise RuntimeError("daily digest job is missing stream_id/local_date")
        provider = await create_provider(session)
        try:
            service = DigestService(session, MarketService(session, provider))
            await service.ensure_and_send(
                stream_id=UUID(str(stream_id)),
                local_date=date.fromisoformat(str(local_date)),
            )
        finally:
            await provider.close()

    async def _run_market_retention(self, session) -> None:
        deleted = await RetentionService(session).run()
        logger.info("market retention deleted", extra={"deleted": deleted})

    async def _run_notification(self, session, job: Job) -> datetime | None:
        notification_id = (job.payload or {}).get("notification_id")
        if not notification_id:
            raise RuntimeError("notification job has no notification_id")
        return await NotificationService(session).send(UUID(str(notification_id)))

    async def _fail(self, session, job: Job, exc: Exception) -> None:
        message = f"{type(exc).__name__}: {exc}"
        job.last_error = message[:2000]
        retryable = True
        if isinstance(exc, AgentError):
            retryable = exc.code in {
                "LLM_TIMEOUT",
                "LLM_UPSTREAM_ERROR",
                "AGENT_ERROR",
                "MARKET_UNAVAILABLE",
            }
        if retryable and job.attempts < job.max_attempts:
            delay = RETRY_BACKOFF_MINUTES[min(job.attempts - 1, len(RETRY_BACKOFF_MINUTES) - 1)]
            job.status = "PENDING"
            job.scheduled_at = datetime.now(UTC) + timedelta(minutes=delay)
            job.started_at = None
            logger.warning(
                "job failed; retry scheduled",
                extra={"job_id": str(job.id), "kind": job.kind, "error": message},
            )
        else:
            job.status = "FAILED"
            job.finished_at = datetime.now(UTC)
            logger.error(
                "job failed permanently",
                extra={"job_id": str(job.id), "kind": job.kind, "error": message},
            )
        await session.commit()
