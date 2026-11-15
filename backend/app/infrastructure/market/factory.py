import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.network_settings_service import NetworkSettingsService
from app.infrastructure.market.okx import OKXProvider

logger = logging.getLogger(__name__)


async def create_provider(session: AsyncSession) -> OKXProvider:
    """Build an OKX provider using the saved network setting.

    - database setting: enabled -> explicit proxy; disabled -> no proxy at all
    - no database row: fall back to THESIUM_MARKET_PROXY, then env proxy
    """

    status = await NetworkSettingsService(session).status()
    proxy = status["effective_proxy"]
    source = str(status["source"])
    trust_env = source == "none" and not bool(status["market_proxy_enabled"])
    logger.info(
        "OKX provider initialized (source=%s market_proxy=%s trust_env=%s)",
        source,
        proxy or "none",
        trust_env,
    )
    return OKXProvider(
        proxy=str(proxy) if proxy else None,
        trust_env=trust_env,
    )
