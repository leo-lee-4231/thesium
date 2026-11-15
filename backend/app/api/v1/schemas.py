from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class StreamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    asset_symbol: str = Field(min_length=1, max_length=32)
    provider: str = Field(default="okx", min_length=1, max_length=64)
    instrument_symbol: str = Field(min_length=1, max_length=64)
    market_type: Literal["SPOT", "SWAP"] = "SPOT"
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=64)
    monitor_interval_minutes: int = Field(default=60, ge=15, le=1440)
    agent_enabled: bool = True


class SpotEventCreate(BaseModel):
    kind: Literal["BUY", "SELL", "OPENING", "CORRECTION"]
    quantity: Decimal = Field(ge=0)
    price: Decimal | None = None
    avg_cost: Decimal | None = None
    fee: Decimal = Field(default=Decimal("0"), ge=0)
    occurred_at: datetime
    note: str | None = Field(default=None, max_length=500)


class DerivativeEventCreate(BaseModel):
    kind: Literal["OPEN", "INCREASE", "REDUCE", "CLOSE", "ADJUST_MARGIN", "FUNDING", "CORRECTION"]
    side: Literal["LONG", "SHORT"] | None = None
    quantity_base: Decimal | None = Field(default=None, ge=0)
    price: Decimal | None = Field(default=None, gt=0)
    leverage: Decimal | None = Field(default=None, gt=0, le=125)
    margin_mode: Literal["ISOLATED", "CROSS"] = "ISOLATED"
    margin: Decimal | None = Field(default=None, ge=0)
    liquidation_price: Decimal | None = Field(default=None, gt=0)
    fee: Decimal = Field(default=Decimal("0"), ge=0)
    margin_delta: Decimal | None = None
    funding_amount: Decimal | None = None
    occurred_at: datetime
    note: str | None = Field(default=None, max_length=500)


class SpotSimulate(BaseModel):
    side: Literal["BUY", "SELL"]
    quantity: Decimal = Field(gt=0)
    assumed_price: Decimal = Field(gt=0)


class DerivativeSimulate(BaseModel):
    action: Literal[
        "REDUCE_LONG",
        "REDUCE_SHORT",
        "CLOSE_LONG",
        "CLOSE_SHORT",
        "INCREASE_LONG",
        "INCREASE_SHORT",
    ]
    size_change_pct: Decimal = Field(default=Decimal("25"), ge=0, le=100)
    assumed_mark: Decimal = Field(gt=0)


class ThesisVersionCreate(BaseModel):
    original_text: str = Field(min_length=1, max_length=20000)
    final_text: str | None = Field(default=None, max_length=20000)
    structured_content: dict = Field(default_factory=dict)
    source: Literal["USER", "AGENT", "SYSTEM"] = "USER"
    source_agent_run_id: UUID | None = None
    polish_agent_run_id: UUID | None = None
    base_version_id: UUID | None = None


class ThesisTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class ThesisRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class LLMConfigUpdate(BaseModel):
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    api_key: str | None = Field(default=None, max_length=500)
    clear_api_key: bool = False


class LLMTestRequest(BaseModel):
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    api_key: str | None = Field(default=None, max_length=500)


class StopLossPreviewRequest(BaseModel):
    side: Literal["LONG", "SHORT"]
    entry_price: Decimal = Field(gt=0)
    quantity_base: Decimal = Field(gt=0)
    account_equity_usd: Decimal = Field(gt=0)
    max_drawdown_pct: Decimal = Field(ge=0, le=100)
    max_concurrent_positions: int = Field(default=5, ge=1, le=100)
    max_risk_per_trade_pct: Decimal | None = Field(default=None, gt=0, le=100)
    risk_budget_usd: Decimal | None = Field(default=None, ge=0)
    explicit_stop: Decimal | None = Field(default=None, gt=0)
    liquidation_price: Decimal | None = Field(default=None, gt=0)
    fee_buffer_usd: Decimal = Field(default=Decimal("0"), ge=0)


class EmailSettingsUpdate(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=587, ge=1, le=65535)
    from_address: str = Field(min_length=3, max_length=320)
    to_address: str | None = Field(default=None, max_length=320)
    from_name: str | None = Field(default=None, max_length=120)
    username: str | None = Field(default=None, max_length=320)
    password: str | None = Field(default=None, max_length=500)
    clear_password: bool = False
    use_tls: bool = True
    use_ssl: bool = False


class EmailTestRequest(BaseModel):
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    from_address: str | None = Field(default=None, max_length=320)
    to_address: str | None = Field(default=None, max_length=320)
    from_name: str | None = Field(default=None, max_length=120)
    username: str | None = Field(default=None, max_length=320)
    password: str | None = Field(default=None, max_length=500)
    use_tls: bool | None = None
    use_ssl: bool | None = None
    recipient: str | None = Field(default=None, max_length=320)


class NotificationPreferencesUpdate(BaseModel):
    decision_alert_enabled: bool = True
    risk_alert_enabled: bool = True
    email_enabled: bool = True
    daily_summary_enabled: bool = False
    daily_summary_time: str = Field(default="08:00", pattern=r"^\d{2}:\d{2}$")
    news_enabled: bool = True
    quiet_hours_enabled: bool = True
    quiet_hours_start: str = Field(default="23:00", pattern=r"^\d{2}:\d{2}$")
    quiet_hours_end: str = Field(default="08:00", pattern=r"^\d{2}:\d{2}$")
    daily_email_limit: int = Field(default=4, ge=1, le=50)
    cooldown_minutes: int = Field(default=240, ge=0, le=10080)
    feishu_push_enabled: bool = False


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    client_message_id: str | None = Field(default=None, max_length=120)


class NetworkSettingsUpdate(BaseModel):
    market_proxy_enabled: bool = False
    market_proxy_url: str | None = Field(default=None, max_length=500)
