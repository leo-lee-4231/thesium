import logging
import time
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Asset, Instrument, MarketCandle, MarketSnapshot
from app.infrastructure.market.base import (
    Candle,
    DerivativesOverview,
    InstrumentNotFound,
    MarketDataProvider,
    Quote,
    Timeframe,
)
from app.infrastructure.market.indicators import build_indicator_snapshot, build_rsi_history

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 20.0
_cache: dict[str, tuple[float, Any]] = {}


class MarketService:
    def __init__(self, session: AsyncSession, provider: MarketDataProvider) -> None:
        self._session = session
        self._provider = provider

    async def _instrument(self, symbol: str, market_type: str) -> Instrument:
        statement = (
            select(Instrument)
            .join(Asset, Instrument.asset_id == Asset.id)
            .where(
                Asset.symbol == symbol.upper(),
                Instrument.provider == "okx",
                Instrument.market_type == market_type.upper(),
                Instrument.status == "ACTIVE",
            )
        )
        instrument = await self._session.scalar(statement)
        if instrument is None:
            raise InstrumentNotFound(
                f"No {market_type.upper()} instrument found for {symbol.upper()}"
            )
        return instrument

    async def quote(self, symbol: str, market_type: str = "SPOT") -> Quote:
        instrument = await self._instrument(symbol, market_type)
        cached = _cache_get(f"quote:{instrument.symbol}")
        if cached is not None:
            return cast(Quote, cached)
        quote = await self._provider.get_quote(instrument.symbol)
        await self._persist_quote(instrument, quote)
        _cache_set(f"quote:{instrument.symbol}", quote)
        return quote

    async def candles(
        self, symbol: str, timeframe: Timeframe, limit: int = 200, market_type: str = "SPOT"
    ) -> list[Candle]:
        instrument = await self._instrument(symbol, market_type)
        cache_key = f"candles:{instrument.symbol}:{timeframe}:{limit}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cast(list[Candle], cached)
        candles = await self._provider.get_candles(instrument.symbol, timeframe, limit)
        await self._upsert_candles(instrument, timeframe, candles)
        _cache_set(cache_key, candles)
        return candles

    async def indicators(
        self, symbol: str, timeframes: list[Timeframe], market_type: str = "SPOT"
    ) -> dict[str, dict[str, object]]:
        result: dict[str, dict[str, object]] = {}
        for timeframe in timeframes:
            candles = await self.candles(symbol, timeframe, 220, market_type)
            result[timeframe.value] = build_indicator_snapshot(candles)
        return result

    async def recent_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 24,
        market_type: str = "SPOT",
    ) -> list[Candle]:
        """Return the latest bars from the same 220-bar fetch used by indicators."""
        if limit <= 0:
            return []
        candles = await self.candles(symbol, timeframe, 220, market_type)
        return candles[-limit:]

    async def rsi_history(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 24,
        market_type: str = "SPOT",
    ) -> list[dict[str, object]]:
        """Return recent RSI values computed from the full 220-bar window."""
        candles = await self.candles(symbol, timeframe, 220, market_type)
        return build_rsi_history(candles, limit)

    async def derivatives(self, symbol: str) -> DerivativesOverview:
        instrument = await self._instrument(symbol, "SWAP")
        cached = _cache_get(f"derivatives:{instrument.symbol}")
        if cached is not None:
            return cast(DerivativesOverview, cached)
        overview = await self._provider.get_derivatives_overview(instrument.symbol)
        await self._persist_derivatives(instrument, overview)
        _cache_set(f"derivatives:{instrument.symbol}", overview)
        return overview

    async def market_overview(
        self, symbol: str, market_type: str = "SPOT"
    ) -> dict[str, object]:
        quote = await self.quote(symbol, market_type)
        indicators = await self.indicators(
            symbol, [Timeframe.H1, Timeframe.H4, Timeframe.D1], market_type
        )
        derivatives: DerivativesOverview | None
        try:
            derivatives = await self.derivatives(symbol)
        except InstrumentNotFound:
            derivatives = None

        warnings: list[str] = []
        if quote.staleness != "FRESH":
            warnings.append(f"现货行情数据状态为 {quote.staleness}")
        if derivatives is not None and derivatives.staleness != "FRESH":
            warnings.append(f"合约观察数据状态为 {derivatives.staleness}")

        return {
            "quote": quote,
            "indicators": indicators,
            "derivatives": derivatives,
            "warnings": warnings,
        }

    async def _persist_quote(self, instrument: Instrument, quote: Quote) -> None:
        snapshot = MarketSnapshot(
            instrument_id=instrument.id,
            source=quote.source,
            price=quote.price,
            change_24h_pct=quote.change_24h_pct,
            volume_24h=quote.volume_24h,
            high_24h=quote.high_24h,
            low_24h=quote.low_24h,
            market_time=quote.market_time,
            fetched_at=quote.fetched_at,
            staleness=quote.staleness,
        )
        self._session.add(snapshot)
        await self._commit_quietly()

    async def _persist_derivatives(
        self, instrument: Instrument, overview: DerivativesOverview
    ) -> None:
        snapshot = MarketSnapshot(
            instrument_id=instrument.id,
            source=overview.source,
            price=overview.mark_price,
            market_time=overview.market_time,
            fetched_at=overview.fetched_at,
            staleness=overview.staleness,
            derivatives={
                "mark_price": str(overview.mark_price),
                "funding_rate": str(overview.funding_rate)
                if overview.funding_rate is not None
                else None,
                "next_funding_time": overview.next_funding_time.isoformat()
                if overview.next_funding_time
                else None,
                "open_interest": str(overview.open_interest)
                if overview.open_interest is not None
                else None,
                "open_interest_usd": str(overview.open_interest_usd)
                if overview.open_interest_usd is not None
                else None,
            },
        )
        self._session.add(snapshot)
        await self._commit_quietly()

    async def _upsert_candles(
        self, instrument: Instrument, timeframe: Timeframe, candles: list[Candle]
    ) -> None:
        if not candles:
            return
        rows = [
            {
                "instrument_id": instrument.id,
                "timeframe": timeframe.value,
                "open_time": candle.open_time,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "source": self._provider.name,
            }
            for candle in candles
        ]
        statement = insert(MarketCandle).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=["instrument_id", "timeframe", "open_time"],
            set_={
                "open": statement.excluded.open,
                "high": statement.excluded.high,
                "low": statement.excluded.low,
                "close": statement.excluded.close,
                "volume": statement.excluded.volume,
                "source": statement.excluded.source,
            },
        )
        await self._session.execute(statement)
        await self._commit_quietly()

    async def _commit_quietly(self) -> None:
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            logger.warning("failed to persist market data", exc_info=True)


def _cache_get(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    timestamp, value = entry
    if time.monotonic() - timestamp > _CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (time.monotonic(), value)
