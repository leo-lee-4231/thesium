from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.market import get_market_service
from app.api.v1.schemas import (
    DerivativeEventCreate,
    DerivativeSimulate,
    SpotEventCreate,
    SpotSimulate,
)
from app.application.market_service import MarketService
from app.application.portfolio_service import PortfolioService
from app.db.models import (
    Asset,
    DerivativePositionEvent,
    DerivativePositionSnapshot,
    InvestmentStream,
    PositionEvent,
    PositionSnapshot,
)
from app.db.session import get_session
from app.domain.portfolio import (
    DerivativeCommand,
    PortfolioError,
    SpotCommand,
)
from app.infrastructure.market.base import MarketProviderError

router = APIRouter(prefix="/streams/{stream_id}", tags=["portfolio"])


def _error(exc: PortfolioError) -> HTTPException:
    status = 400
    if exc.code == "NOT_FOUND":
        status = 404
    elif exc.code in {"POSITION_SIDE_CONFLICT", "POSITION_EXISTS", "INSUFFICIENT_POSITION"}:
        status = 409
    return HTTPException(status_code=status, detail=f"{exc.code}: {exc.message}")


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


async def _marks(
    session: AsyncSession, market: MarketService, stream_id: UUID
) -> tuple[Decimal | None, Decimal | None, list[str]]:
    stream = await session.get(InvestmentStream, stream_id)
    if stream is None:
        raise HTTPException(status_code=404, detail="investment stream not found")
    asset = await session.get(Asset, stream.asset_id)
    if asset is None:
        return None, None, ["asset not found"]
    spot_mark: Decimal | None = None
    perp_mark: Decimal | None = None
    warnings: list[str] = []
    try:
        quote = await market.quote(asset.symbol, "SPOT")
        spot_mark = quote.price
    except MarketProviderError:
        warnings.append("现货行情不可用，未计算浮盈")
    try:
        derivative = await market.derivatives(asset.symbol)
        perp_mark = derivative.mark_price
    except (MarketProviderError, Exception):
        warnings.append("合约观察数据不可用，未计算 uPnL/距清算价")
    return spot_mark, perp_mark, warnings


async def _portfolio(
    session: AsyncSession,
    stream_id: UUID,
    service: PortfolioService,
    market: MarketService,
) -> dict[str, object]:
    spot_mark, perp_mark, warnings = await _marks(session, market, stream_id)
    return {
        "spot": await service.spot(stream_id, spot_mark),
        "derivative": await service.derivative(stream_id, perp_mark),
        "warnings": warnings,
    }


def _spot_event(event: PositionEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "kind": event.kind,
        "side": event.side,
        "quantity": _decimal(event.quantity),
        "price": _decimal(event.price),
        "fee": _decimal(event.fee),
        "occurred_at": event.occurred_at,
        "note": event.note,
        "before_state": event.before_state,
        "after_state": event.after_state,
    }


def _derivative_event(event: DerivativePositionEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "kind": event.kind,
        "side": event.side,
        "quantity_base": _decimal(event.quantity_base),
        "price": _decimal(event.price),
        "fee": _decimal(event.fee),
        "margin_delta": _decimal(event.margin_delta),
        "funding_amount": _decimal(event.funding_amount),
        "occurred_at": event.occurred_at,
        "note": event.note,
        "before_state": event.before_state,
        "after_state": event.after_state,
    }


@router.get("/portfolio")
async def get_portfolio(
    stream_id: UUID,
    market: Annotated[MarketService, Depends(get_market_service)],
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    return await _portfolio(session, stream_id, PortfolioService(session), market)


@router.get("/positions")
async def get_spot_position(
    stream_id: UUID,
    market: Annotated[MarketService, Depends(get_market_service)],
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    spot_mark, _, _ = await _marks(session, market, stream_id)
    return await PortfolioService(session).spot(stream_id, spot_mark)


@router.post("/position-events", status_code=201)
async def record_spot_event(
    stream_id: UUID,
    payload: SpotEventCreate,
    market: Annotated[MarketService, Depends(get_market_service)],
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    command = SpotCommand(
        kind=payload.kind,
        quantity=payload.quantity,
        price=payload.price,
        avg_cost=payload.avg_cost,
        fee=payload.fee,
        occurred_at=payload.occurred_at,
        note=payload.note,
    )
    service = PortfolioService(session)
    try:
        await service.record_spot(stream_id, command)
    except PortfolioError as exc:
        raise _error(exc) from exc
    return await _portfolio(session, stream_id, service, market)


@router.get("/position-events")
async def list_spot_events(
    stream_id: UUID,
    limit: int = Query(default=30, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    rows = await session.execute(
        select(PositionEvent)
        .where(PositionEvent.stream_id == stream_id)
        .order_by(PositionEvent.occurred_at.desc())
        .limit(limit)
    )
    return [_spot_event(event) for event in rows.scalars().all()]


@router.get("/position-snapshots")
async def list_spot_snapshots(
    stream_id: UUID,
    limit: int = Query(default=30, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    rows = await session.execute(
        select(PositionSnapshot)
        .where(PositionSnapshot.stream_id == stream_id)
        .order_by(PositionSnapshot.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": snapshot.id,
            "version": snapshot.position_version,
            "as_of": snapshot.as_of,
            "quantity": str(snapshot.quantity),
            "avg_cost": str(snapshot.avg_cost),
            "realized_pnl": str(snapshot.realized_pnl),
        }
        for snapshot in rows.scalars().all()
    ]


@router.post("/positions/simulate")
async def simulate_spot(
    stream_id: UUID,
    payload: SpotSimulate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    try:
        result = await PortfolioService(session).simulate_spot(
            stream_id, payload.side, payload.quantity, payload.assumed_price
        )
    except PortfolioError as exc:
        raise _error(exc) from exc
    return result


@router.get("/derivative-positions")
async def get_derivative_position(
    stream_id: UUID,
    market: Annotated[MarketService, Depends(get_market_service)],
    session: AsyncSession = Depends(get_session),
) -> dict[str, object] | None:
    _, perp_mark, _ = await _marks(session, market, stream_id)
    return await PortfolioService(session).derivative(stream_id, perp_mark)


@router.post("/derivative-position-events", status_code=201)
async def record_derivative_event(
    stream_id: UUID,
    payload: DerivativeEventCreate,
    market: Annotated[MarketService, Depends(get_market_service)],
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    _, perp_mark, _ = await _marks(session, market, stream_id)
    command = DerivativeCommand(
        kind=payload.kind,
        side=payload.side,
        quantity_base=payload.quantity_base,
        price=payload.price,
        leverage=payload.leverage,
        margin_mode=payload.margin_mode,
        margin=payload.margin,
        liquidation_price=payload.liquidation_price,
        fee=payload.fee,
        margin_delta=payload.margin_delta,
        funding_amount=payload.funding_amount,
        occurred_at=payload.occurred_at,
        note=payload.note,
    )
    service = PortfolioService(session)
    try:
        await service.record_derivative(stream_id, command, perp_mark)
    except PortfolioError as exc:
        raise _error(exc) from exc
    return await _portfolio(session, stream_id, service, market)


@router.get("/derivative-position-events")
async def list_derivative_events(
    stream_id: UUID,
    limit: int = Query(default=30, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    rows = await session.execute(
        select(DerivativePositionEvent)
        .where(DerivativePositionEvent.stream_id == stream_id)
        .order_by(DerivativePositionEvent.occurred_at.desc())
        .limit(limit)
    )
    return [_derivative_event(event) for event in rows.scalars().all()]


@router.get("/derivative-position-snapshots")
async def list_derivative_snapshots(
    stream_id: UUID,
    limit: int = Query(default=30, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    rows = await session.execute(
        select(DerivativePositionSnapshot)
        .where(DerivativePositionSnapshot.stream_id == stream_id)
        .order_by(DerivativePositionSnapshot.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": snapshot.id,
            "version": snapshot.position_version,
            "as_of": snapshot.as_of,
            "side": snapshot.side,
            "quantity_base": str(snapshot.quantity_base),
            "entry_price": str(snapshot.entry_price),
            "mark_price": _decimal(snapshot.mark_price),
            "unrealized_pnl": _decimal(snapshot.unrealized_pnl),
            "liq_distance_pct": _decimal(snapshot.liq_distance_pct),
        }
        for snapshot in rows.scalars().all()
    ]


@router.post("/derivative-positions/simulate")
async def simulate_derivative(
    stream_id: UUID,
    payload: DerivativeSimulate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    try:
        result = await PortfolioService(session).simulate_derivative(
            stream_id, payload.action, payload.size_change_pct, payload.assumed_mark
        )
    except PortfolioError as exc:
        raise _error(exc) from exc
    return result
