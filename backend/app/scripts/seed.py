import asyncio
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.models import Asset, Instrument, User
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

LOCAL_EMAIL = "local@thesium.local"


async def seed() -> None:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == LOCAL_EMAIL))
        if user is None:
            user = User(email=LOCAL_EMAIL, display_name="Local user")
            session.add(user)
            logger.info("seeded local user")

        asset = await session.scalar(select(Asset).where(Asset.symbol == "BTC"))
        if asset is None:
            asset = Asset(symbol="BTC", name="Bitcoin", kind="CRYPTO")
            session.add(asset)
            await session.flush()
            logger.info("seeded BTC asset")

        instrument = await session.scalar(
            select(Instrument).where(
                Instrument.provider == "binance",
                Instrument.symbol == "BTCUSDT",
                Instrument.market_type == "SPOT",
            )
        )
        if instrument is None:
            instrument = Instrument(
                asset_id=asset.id,
                provider="binance",
                symbol="BTCUSDT",
                market_type="SPOT",
                quote_currency="USDT",
            )
            session.add(instrument)
            logger.info("seeded BTCUSDT instrument")

        await session.commit()


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    asyncio.run(seed())


if __name__ == "__main__":
    main()