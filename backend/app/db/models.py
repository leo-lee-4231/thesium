from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Shanghai", server_default="Asia/Shanghai"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LLMProvider(Base):
    __tablename__ = "llm_providers"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    api_key_hint: Mapped[str | None] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    extra: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNTESTED", server_default="UNTESTED"
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="CRYPTO")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint("provider", "symbol", "market_type", name="uq_instrument_identity"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    asset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    market_type: Mapped[str] = mapped_column(String(32), nullable=False, default="SPOT")
    quote_currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USDT")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    meta: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class InvestmentStream(Base):
    __tablename__ = "investment_streams"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    asset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True
    )
    primary_instrument_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Shanghai", server_default="Asia/Shanghai"
    )
    monitor_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, server_default="60"
    )
    agent_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

class MarketCandle(Base):
    __tablename__ = "market_candles"

    instrument_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("instruments.id"), primary_key=True
    )
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    change_24h_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    volume_24h: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    high_24h: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    low_24h: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    market_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    staleness: Mapped[str] = mapped_column(String(16), nullable=False)
    indicators: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    derivatives: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    raw: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    stream_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("investment_streams.id"), nullable=False, unique=True
    )
    instrument_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=0)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=0)
    cost_currency: Mapped[str] = mapped_column(
        String(16), nullable=False, default="USDT", server_default="USDT"
    )
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=0)
    fee_paid: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PositionEvent(Base):
    __tablename__ = "position_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    stream_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("investment_streams.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str | None] = mapped_column(String(8))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    fee: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=0)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="MANUAL", server_default="MANUAL"
    )
    before_state: Mapped[dict | None] = mapped_column(JSONB)
    after_state: Mapped[dict | None] = mapped_column(JSONB)
    resulting_snapshot_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    stream_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("investment_streams.id"), nullable=False, index=True
    )
    position_version: Mapped[int] = mapped_column(Integer, nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    cost_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=0)
    source_event_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("position_events.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DerivativePosition(Base):
    __tablename__ = "derivative_positions"
    __table_args__ = (
        UniqueConstraint("stream_id", "instrument_id", name="uq_derivative_position_stream"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    stream_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("investment_streams.id"), nullable=False, index=True
    )
    instrument_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=0)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=0)
    leverage: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=1)
    margin_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ISOLATED", server_default="ISOLATED"
    )
    margin: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=0)
    liquidation_price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=0)
    funding_fees: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DerivativePositionEvent(Base):
    __tablename__ = "derivative_position_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    stream_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("investment_streams.id"), nullable=False, index=True
    )
    position_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("derivative_positions.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity_base: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    fee: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=0)
    margin_delta: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    funding_amount: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))
    before_state: Mapped[dict | None] = mapped_column(JSONB)
    after_state: Mapped[dict | None] = mapped_column(JSONB)
    resulting_snapshot_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DerivativePositionSnapshot(Base):
    __tablename__ = "derivative_position_snapshots"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    stream_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("investment_streams.id"), nullable=False, index=True
    )
    position_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("derivative_positions.id"), nullable=False, index=True
    )
    position_version: Mapped[int] = mapped_column(Integer, nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    leverage: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    margin_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    margin: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    liquidation_price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    mark_price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    notional: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    roe: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    liq_distance_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    risk_budget_usage_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    source_event_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("derivative_position_events.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class InvestmentThesis(Base):
    __tablename__ = "investment_theses"
    __table_args__ = (
        UniqueConstraint("stream_id", "version", name="uq_thesis_stream_version"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    stream_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("investment_streams.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="USER")
    change_class: Mapped[str] = mapped_column(String(16), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    final_text: Mapped[str | None] = mapped_column(Text)
    structured_content: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    diff_from_previous: Mapped[list | None] = mapped_column(JSONB)
    source_agent_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    polish_agent_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
