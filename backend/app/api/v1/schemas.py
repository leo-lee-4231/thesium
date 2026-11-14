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