import asyncio
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.users import LOCAL_USER_EMAIL
from app.db.models import Asset, Instrument, User
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

INSTRUMENTS = [
    {"provider": "okx", "symbol": "BTC-USDT", "market_type": "SPOT"},
    {"provider": "okx", "symbol": "BTC-USDT-SWAP", "market_type": "SWAP"},
]


async def seed() -> None:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == LOCAL_USER_EMAIL))
        if user is None:
            user = User(email=LOCAL_USER_EMAIL, display_name="Local user")
            session.add(user)
            logger.info("seeded local user")

        asset = await session.scalar(select(Asset).where(Asset.symbol == "BTC"))
        if asset is None:
            asset = Asset(symbol="BTC", name="Bitcoin", kind="CRYPTO")
            session.add(asset)
            await session.flush()
            logger.info("seeded BTC asset")

        for spec in INSTRUMENTS:
            instrument = await session.scalar(
                select(Instrument).where(
                    Instrument.provider == spec["provider"],
                    Instrument.symbol == spec["symbol"],
                    Instrument.market_type == spec["market_type"],
                )
            )
            if instrument is None:
                session.add(
                    Instrument(
                        asset_id=asset.id,
                        provider=spec["provider"],
                        symbol=spec["symbol"],
                        market_type=spec["market_type"],
                        quote_currency="USDT",
                    )
                )
                logger.info(
                    "seeded %s %s %s",
                    spec["provider"],
                    spec["symbol"],
                    spec["market_type"],
                )

        await session.commit()


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    asyncio.run(seed())


if __name__ == "__main__":
    main()