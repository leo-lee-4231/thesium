import asyncio
import contextlib
import logging
import signal

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.workers.runner import JobRunner
from app.workers.scheduler import (
    claim_jobs,
    enqueue_due_daily_digests,
    enqueue_due_monitors,
    recover_stale_jobs,
)

logger = logging.getLogger(__name__)


async def _tick(runner: JobRunner, *, scheduler_enabled: bool) -> None:
    if scheduler_enabled:
        async with SessionLocal() as session:
            await enqueue_due_daily_digests(session)
            await enqueue_due_monitors(session)
    async with SessionLocal() as session:
        settings = get_settings()
        await recover_stale_jobs(session, stale_minutes=settings.stale_job_minutes)
        job_ids = await claim_jobs(session, limit=settings.worker_job_batch)
    for job_id in job_ids:
        await runner.run(job_id)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            # Windows / restricted environments: rely on KeyboardInterrupt.
            loop.add_signal_handler(sig, stop.set)

    runner = JobRunner()
    logger.info(
        "thesium worker starting",
        extra={
            "environment": settings.environment,
            "scheduler_enabled": settings.scheduler_enabled,
            "poll_seconds": settings.worker_poll_seconds,
        },
    )
    while not stop.is_set():
        try:
            await _tick(runner, scheduler_enabled=settings.scheduler_enabled)
        except Exception:  # noqa: BLE001 - keep the worker alive
            logger.exception("worker tick failed")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=5)
            continue
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(
                stop.wait(), timeout=max(5, settings.worker_poll_seconds)
            )
    logger.info("thesium worker stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()