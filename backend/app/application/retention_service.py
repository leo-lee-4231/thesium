from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.market_retention_settings_service import (
    MarketRetentionSettingsService,
    RetentionPolicy,
)
from app.db.models import MarketCandle, MarketSnapshot
from app.infrastructure.market.base import Timeframe

logger = logging.getLogger(__name__)


def retention_cutoffs(now: datetime, policy: RetentionPolicy) -> dict[str, datetime]:
    return {
        Timeframe.H1.value: now - timedelta(days=max(1, policy.candle_1h_days)),
        Timeframe.H4.value: now - timedelta(days=max(1, policy.candle_4h_days)),
        Timeframe.D1.value: now - timedelta(days=max(1, policy.candle_1d_days)),
    }


class RetentionService:
    def __init__(self, session: AsyncSession, policy: RetentionPolicy | None = None) -> None:
        self._session = session
        self._policy = policy

    async def run(self, *, now: datetime | None = None) -> dict[str, int]:
        policy = self._policy or await MarketRetentionSettingsService(self._session).policy()
        if not policy.enabled:
            return {}

        now = now or datetime.now(UTC)
        cutoffs = retention_cutoffs(now, policy)
        deleted: dict[str, int] = {}

        for timeframe, cutoff in cutoffs.items():
            result = await self._session.execute(
                delete(MarketCandle).where(
                    MarketCandle.timeframe == timeframe,
                    MarketCandle.open_time < cutoff,
                )
            )
            deleted[f"candles_{timeframe}"] = max(0, result.rowcount or 0)

        snapshot_cutoff = now - timedelta(days=max(1, policy.snapshot_days))
        result = await self._session.execute(
            delete(MarketSnapshot).where(MarketSnapshot.created_at < snapshot_cutoff)
        )
        deleted["market_snapshots"] = max(0, result.rowcount or 0)

        await self._session.commit()
        logger.info("market retention completed", extra={"deleted": deleted})
        return deleted
