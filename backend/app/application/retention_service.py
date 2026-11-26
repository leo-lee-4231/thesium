from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import MarketCandle, MarketSnapshot
from app.infrastructure.market.base import Timeframe

logger = logging.getLogger(__name__)


def retention_cutoffs(now: datetime, settings: Settings) -> dict[str, datetime]:
    return {
        Timeframe.H1.value: now - timedelta(days=max(1, settings.market_candle_retention_days_1h)),
        Timeframe.H4.value: now - timedelta(days=max(1, settings.market_candle_retention_days_4h)),
        Timeframe.D1.value: now - timedelta(days=max(1, settings.market_candle_retention_days_1d)),
    }


class RetentionService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()

    async def run(self, *, now: datetime | None = None) -> dict[str, int]:
        if not self._settings.market_retention_enabled:
            return {}

        now = now or datetime.now(UTC)
        cutoffs = retention_cutoffs(now, self._settings)
        deleted: dict[str, int] = {}

        for timeframe, cutoff in cutoffs.items():
            result = await self._session.execute(
                delete(MarketCandle).where(
                    MarketCandle.timeframe == timeframe,
                    MarketCandle.open_time < cutoff,
                )
            )
            deleted[f"candles_{timeframe}"] = max(0, result.rowcount or 0)

        snapshot_cutoff = now - timedelta(
            days=max(1, self._settings.market_snapshot_retention_days)
        )
        result = await self._session.execute(
            delete(MarketSnapshot).where(MarketSnapshot.created_at < snapshot_cutoff)
        )
        deleted["market_snapshots"] = max(0, result.rowcount or 0)

        await self._session.commit()
        logger.info("market retention completed", extra={"deleted": deleted})
        return deleted
