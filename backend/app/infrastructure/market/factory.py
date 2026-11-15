import logging

from app.core.config import get_settings
from app.infrastructure.market.okx import OKXProvider

logger = logging.getLogger(__name__)
_provider: OKXProvider | None = None


def get_provider() -> OKXProvider:
    """Process-wide public OKX provider (no API key)."""

    global _provider
    if _provider is None:
        settings = get_settings()
        _provider = OKXProvider(proxy=settings.market_proxy)
        logger.info(
            "OKX provider initialized (market_proxy=%s)",
            settings.market_proxy or "env/default",
        )
    return _provider
