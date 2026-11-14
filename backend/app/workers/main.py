import asyncio
import contextlib
import logging
import signal

from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            # Windows / restricted environments: rely on KeyboardInterrupt.
            loop.add_signal_handler(sig, stop.set)

    logger.info("thesium worker starting", extra={"environment": settings.environment})
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=30)
        except TimeoutError:
            logger.debug("worker idle")
    logger.info("thesium worker stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()