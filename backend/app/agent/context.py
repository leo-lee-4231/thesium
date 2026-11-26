from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.market_service import MarketService
from app.application.portfolio_service import PortfolioService
from app.application.thesis_service import ThesisService
from app.db.models import (
    Asset,
    DerivativePositionSnapshot,
    Instrument,
    InvestmentDecision,
    InvestmentStream,
    InvestmentThesis,
    MarketSnapshot,
    PositionSnapshot,
)
from app.domain.risk import RiskError, StopLossInput, derive_stop_loss
from app.infrastructure.market.base import Timeframe


class ContextError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class MonitorContext:
    stream: InvestmentStream
    asset: Asset
    thesis: InvestmentThesis | None
    quote: Any
    indicators: dict[str, dict[str, object]]
    recent_candles: dict[str, list[dict[str, object]]]
    rsi_history: dict[str, list[dict[str, object]]]
    derivatives: Any | None
    spot_position: dict[str, Any]
    derivative_position: dict[str, Any] | None
    risk_plan: dict[str, object] | None
    recent_decisions: list[dict[str, object]]
    context: dict[str, Any]
    digest: str
    instrument: Instrument | None
    market_snapshot: MarketSnapshot | None
    position_snapshot: PositionSnapshot | None
    derivative_snapshot: DerivativePositionSnapshot | None


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _int(value: object, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def quote_dict(quote: Any) -> dict[str, object]:
    return {
        "instrument": quote.instrument,
        "price": str(quote.price),
        "change_24h_pct": str(quote.change_24h_pct)
        if quote.change_24h_pct is not None
        else None,
        "high_24h": str(quote.high_24h) if quote.high_24h is not None else None,
        "low_24h": str(quote.low_24h) if quote.low_24h is not None else None,
        "volume_24h": str(quote.volume_24h) if quote.volume_24h is not None else None,
        "market_time": quote.market_time.isoformat(),
        "fetched_at": quote.fetched_at.isoformat(),
        "staleness": quote.staleness,
        "source": quote.source,
    }


def candle_dict(candle: Any) -> dict[str, object]:
    return {
        "open_time": candle.open_time.isoformat(),
        "open": str(candle.open),
        "high": str(candle.high),
        "low": str(candle.low),
        "close": str(candle.close),
        "volume": str(candle.volume),
        "confirmed": candle.confirmed,
    }


def recent_candle_payload(candles: list[Any], limit: int) -> list[dict[str, object]]:
    if limit <= 0:
        return []
    return [candle_dict(candle) for candle in candles[-limit:]]


def derivatives_dict(overview: Any) -> dict[str, object]:
    return {
        "instrument": overview.instrument,
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
        "market_time": overview.market_time.isoformat(),
        "staleness": overview.staleness,
    }


def thesis_dict(thesis: InvestmentThesis) -> dict[str, object]:
    return {
        "id": str(thesis.id),
        "version": thesis.version,
        "original_text": thesis.original_text,
        "final_text": thesis.final_text or thesis.original_text,
        "structured_content": thesis.structured_content,
        "effective_from": thesis.effective_from.isoformat(),
    }


def risk_plan(thesis: InvestmentThesis | None, derivative: dict | None) -> dict[str, object] | None:
    if thesis is None or derivative is None:
        return None
    content = thesis.structured_content or {}
    risk = content.get("risk") or {}
    intent = content.get("derivative_intent") or {}
    state = derivative.get("state") or {}
    side = str(state.get("side", ""))
    if side not in {"LONG", "SHORT"}:
        return None

    equity = _decimal(risk.get("account_equity_usd"))
    max_drawdown = _decimal(risk.get("max_drawdown_pct"))
    if equity is None or max_drawdown is None:
        return {"error": "missing risk.account_equity_usd or max_drawdown_pct"}

    explicit = _decimal(
        intent.get("long_stop_loss_price")
        if side == "LONG"
        else intent.get("short_stop_loss_price")
    ) or _decimal(risk.get("stop_loss_price"))

    try:
        return derive_stop_loss(
            StopLossInput(
                side=side,
                entry_price=_decimal(state.get("entry_price")) or Decimal("0"),
                quantity_base=_decimal(state.get("quantity_base")) or Decimal("0"),
                account_equity_usd=equity,
                max_drawdown_pct=max_drawdown,
                max_concurrent_positions=_int(risk.get("max_concurrent_positions"), 5),
                max_risk_per_trade_pct=_decimal(risk.get("max_risk_per_trade_pct")),
                risk_budget_usd=_decimal(risk.get("risk_budget_usd")),
                explicit_stop=explicit,
                liquidation_price=_decimal(state.get("liquidation_price")),
            )
        )
    except RiskError as exc:
        return {"error": exc.message}


async def build_monitor_context(
    session: AsyncSession, market: MarketService, stream_id: UUID
) -> MonitorContext:
    stream = await session.get(InvestmentStream, stream_id)
    if stream is None:
        raise ContextError("NOT_FOUND", "investment stream not found")
    asset = await session.get(Asset, stream.asset_id)
    if asset is None:
        raise ContextError("NOT_FOUND", "asset not found")
    thesis = await ThesisService(session).active(stream_id)

    try:
        quote = await market.quote(asset.symbol, "SPOT")
    except Exception as exc:
        raise ContextError("MARKET_UNAVAILABLE", f"spot market unavailable: {exc}") from exc
    indicators = await market.indicators(
        asset.symbol, [Timeframe.H1, Timeframe.H4, Timeframe.D1], "SPOT"
    )
    recent_candles: dict[str, list[dict[str, object]]] = {}
    rsi_history: dict[str, list[dict[str, object]]] = {}
    for timeframe, limit in (
        (Timeframe.H1, 24),
        (Timeframe.H4, 18),
        (Timeframe.D1, 14),
    ):
        bars = await market.recent_candles(asset.symbol, timeframe, limit, "SPOT")
        recent_candles[timeframe.value] = recent_candle_payload(bars, limit)
        rsi_history[timeframe.value] = await market.rsi_history(
            asset.symbol, timeframe, limit, "SPOT"
        )

    derivatives = None
    try:
        derivatives = await market.derivatives(asset.symbol)
    except Exception:
        derivatives = None

    perp_mark = derivatives.mark_price if derivatives is not None else None
    portfolio = PortfolioService(session)
    spot_position = await portfolio.spot(stream_id, quote.price)
    derivative_position = await portfolio.derivative(stream_id, perp_mark)
    plan = risk_plan(thesis, derivative_position)

    recent = await session.execute(
        select(InvestmentDecision)
        .where(InvestmentDecision.stream_id == stream_id)
        .order_by(InvestmentDecision.created_at.desc())
        .limit(3)
    )
    recent_decisions = [
        {
            "decision": decision.decision,
            "summary": decision.summary,
            "priority": decision.priority,
            "alignment": (decision.thesis_alignment or {}).get("status"),
            "created_at": decision.created_at.isoformat(),
        }
        for decision in recent.scalars().all()
    ]

    context = {
        "stream": {
            "id": str(stream.id),
            "name": stream.name,
            "timezone": stream.timezone,
            "monitor_interval_minutes": stream.monitor_interval_minutes,
        },
        "asset": {"symbol": asset.symbol, "name": asset.name, "kind": asset.kind},
        "market": {
            "quote": quote_dict(quote),
            "indicators": indicators,
            "recent_candles": recent_candles,
            "rsi_history": rsi_history,
            "derivatives": derivatives_dict(derivatives) if derivatives else None,
        },
        "thesis": thesis_dict(thesis) if thesis is not None else None,
        "has_thesis": thesis is not None,
        "spot": spot_position,
        "derivative": derivative_position,
        "risk_plan": plan,
        "recent_decisions": recent_decisions,
        "data_quality": {
            "quote_staleness": quote.staleness,
            "derivatives_staleness": derivatives.staleness if derivatives else None,
        },
    }
    digest = hashlib.sha256(
        json.dumps(context, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()

    instrument = await session.get(Instrument, stream.primary_instrument_id)
    market_snapshot = (
        await session.scalar(
            select(MarketSnapshot)
            .where(MarketSnapshot.instrument_id == instrument.id)
            .order_by(MarketSnapshot.created_at.desc())
            .limit(1)
        )
        if instrument is not None
        else None
    )
    position_snapshot = await session.scalar(
        select(PositionSnapshot)
        .where(PositionSnapshot.stream_id == stream_id)
        .order_by(PositionSnapshot.created_at.desc())
        .limit(1)
    )
    derivative_snapshot = await session.scalar(
        select(DerivativePositionSnapshot)
        .where(DerivativePositionSnapshot.stream_id == stream_id)
        .order_by(DerivativePositionSnapshot.created_at.desc())
        .limit(1)
    )
    return MonitorContext(
        stream=stream,
        asset=asset,
        thesis=thesis,
        quote=quote,
        indicators=indicators,
        recent_candles=recent_candles,
        rsi_history=rsi_history,
        derivatives=derivatives,
        spot_position=spot_position,
        derivative_position=derivative_position,
        risk_plan=plan,
        recent_decisions=recent_decisions,
        context=context,
        digest=digest,
        instrument=instrument,
        market_snapshot=market_snapshot,
        position_snapshot=position_snapshot,
        derivative_snapshot=derivative_snapshot,
    )


def source_list(ctx: MonitorContext) -> list[dict[str, object]]:
    """Read-only tools/sources that actually contributed to a chat context."""

    sources: list[dict[str, object]] = [
        {
            "tool": "get_asset_overview",
            "label": "OKX 现货行情",
            "as_of": ctx.quote.market_time.isoformat(),
            "staleness": ctx.quote.staleness,
        },
        {
            "tool": "get_technical_indicators",
            "label": "1h/4h/1d 指标",
            "as_of": ctx.indicators.get("1h", {}).get("as_of"),
        },
        {
            "tool": "get_recent_candles",
            "label": "最近 1h/4h/1d K 线",
            "as_of": ctx.recent_candles.get("1h", [{}])[-1].get("open_time")
            if ctx.recent_candles.get("1h")
            else None,
        },
        {
            "tool": "get_rsi_history",
            "label": "最近 1h/4h/1d RSI 序列",
            "as_of": ctx.rsi_history.get("1h", [{}])[-1].get("open_time")
            if ctx.rsi_history.get("1h")
            else None,
        },
        {
            "tool": "get_portfolio",
            "label": "现货/永续持仓",
            "as_of": datetime.now(UTC).isoformat(),
        },
    ]
    if ctx.derivatives is not None:
        sources.append(
            {
                "tool": "get_derivatives_observation",
                "label": "OKX 合约观察",
                "as_of": ctx.derivatives.market_time.isoformat(),
                "staleness": ctx.derivatives.staleness,
            }
        )
    if ctx.thesis is not None:
        sources.append(
            {
                "tool": "get_active_thesis",
                "label": f"ACTIVE Thesis v{ctx.thesis.version}",
                "as_of": ctx.thesis.effective_from.isoformat(),
            }
        )
    if ctx.recent_decisions:
        sources.append(
            {
                "tool": "get_recent_decisions",
                "label": "最近 Decision",
                "as_of": ctx.recent_decisions[0]["created_at"],
            }
        )
    return sources