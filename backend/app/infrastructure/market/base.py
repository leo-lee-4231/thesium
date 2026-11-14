from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol


class Timeframe(StrEnum):
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class MarketProviderError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Quote:
    instrument: str
    price: Decimal
    change_24h_pct: Decimal | None
    high_24h: Decimal | None
    low_24h: Decimal | None
    volume_24h: Decimal | None
    market_time: datetime
    fetched_at: datetime
    source: str
    staleness: str


@dataclass(frozen=True)
class Candle:
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    confirmed: bool


@dataclass(frozen=True)
class DerivativesOverview:
    instrument: str
    mark_price: Decimal
    funding_rate: Decimal | None
    next_funding_time: datetime | None
    open_interest: Decimal | None
    open_interest_usd: Decimal | None
    market_time: datetime
    fetched_at: datetime
    source: str
    staleness: str


class MarketDataProvider(Protocol):
    name: str

    async def get_quote(self, symbol: str) -> Quote: ...

    async def get_candles(
        self, symbol: str, timeframe: Timeframe, limit: int = 200
    ) -> list[Candle]: ...

    async def get_derivatives_overview(self, symbol: str) -> DerivativesOverview: ...

class InstrumentNotFound(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
