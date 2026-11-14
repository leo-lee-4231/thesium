from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InstrumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    symbol: str
    market_type: str
    quote_currency: str


class AssetOut(BaseModel):
    id: UUID
    symbol: str
    name: str
    kind: str
    instruments: list[InstrumentOut]


class StreamOut(BaseModel):
    id: UUID
    name: str
    status: str
    timezone: str
    monitor_interval_minutes: int
    agent_enabled: bool
    created_at: datetime
    asset_symbol: str
    asset_name: str
    provider: str
    instrument_symbol: str
    market_type: str


class MetaOut(BaseModel):
    name: str
    version: str
    environment: str
    phase: str
    capabilities: list[str]

class QuoteOut(BaseModel):
    instrument: str
    price: str
    change_24h_pct: str | None
    high_24h: str | None
    low_24h: str | None
    volume_24h: str | None
    market_time: datetime
    fetched_at: datetime
    source: str
    staleness: str


class CandleOut(BaseModel):
    open_time: datetime
    open: str
    high: str
    low: str
    close: str
    volume: str
    confirmed: bool


class CandlesOut(BaseModel):
    instrument: str
    timeframe: str
    candles: list[CandleOut]


class IndicatorsOut(BaseModel):
    as_of: str | None
    timeframes: dict[str, dict[str, object]]
    warnings: list[str]


class DerivativesOut(BaseModel):
    instrument: str
    mark_price: str
    funding_rate: str | None
    next_funding_time: datetime | None
    open_interest: str | None
    open_interest_usd: str | None
    market_time: datetime
    fetched_at: datetime
    source: str
    staleness: str


class MarketOverviewOut(BaseModel):
    quote: QuoteOut
    indicators: IndicatorsOut
    derivatives: DerivativesOut | None
    warnings: list[str]
