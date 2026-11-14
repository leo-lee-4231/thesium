from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DerivativePosition,
    DerivativePositionEvent,
    DerivativePositionSnapshot,
    Instrument,
    InvestmentStream,
    Position,
    PositionEvent,
    PositionSnapshot,
)
from app.domain.portfolio import (
    DerivativeCommand,
    DerivativeState,
    PortfolioError,
    SpotCommand,
    SpotState,
    derivative_adjust_margin,
    derivative_correction,
    derivative_funding,
    derivative_increase,
    derivative_metrics,
    derivative_open,
    derivative_reduce,
    spot_buy,
    spot_correction,
    spot_metrics,
    spot_opening,
    spot_sell,
)


def _spot_state(position: Position | None) -> SpotState:
    if position is None:
        return SpotState()
    return SpotState(
        quantity=position.quantity,
        avg_cost=position.avg_cost,
        realized_pnl=position.realized_pnl,
        fee_paid=position.fee_paid,
    )


def _derivative_state(position: DerivativePosition | None) -> DerivativeState | None:
    if position is None:
        return None
    return DerivativeState(
        side=position.side,
        quantity_base=position.quantity_base,
        entry_price=position.entry_price,
        leverage=position.leverage,
        margin=position.margin,
        liquidation_price=position.liquidation_price,
        realized_pnl=position.realized_pnl,
        funding_fees=position.funding_fees,
    )


def _spot_dict(state: SpotState) -> dict[str, str]:
    return {
        "quantity": str(state.quantity),
        "avg_cost": str(state.avg_cost),
        "realized_pnl": str(state.realized_pnl),
        "fee_paid": str(state.fee_paid),
    }


def _derivative_dict(state: DerivativeState) -> dict[str, str | None]:
    return {
        "side": state.side,
        "quantity_base": str(state.quantity_base),
        "entry_price": str(state.entry_price),
        "leverage": str(state.leverage),
        "margin": str(state.margin),
        "liquidation_price": str(state.liquidation_price)
        if state.liquidation_price is not None
        else None,
        "realized_pnl": str(state.realized_pnl),
        "funding_fees": str(state.funding_fees),
    }


def _as_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


class PortfolioService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _stream(self, stream_id: UUID) -> InvestmentStream:
        stream = await self._session.get(InvestmentStream, stream_id)
        if stream is None:
            raise PortfolioError("NOT_FOUND", "investment stream not found")
        return stream

    async def _swap_instrument(self, stream: InvestmentStream) -> Instrument:
        instrument = await self._session.scalar(
            select(Instrument).where(
                Instrument.asset_id == stream.asset_id,
                Instrument.provider == "okx",
                Instrument.market_type == "SWAP",
                Instrument.status == "ACTIVE",
            )
        )
        if instrument is None:
            raise PortfolioError("NOT_FOUND", "SWAP instrument not found for this asset")
        return instrument

    async def spot(self, stream_id: UUID, mark_price: Decimal | None = None) -> dict[str, object]:
        await self._stream(stream_id)
        position = await self._session.scalar(
            select(Position).where(Position.stream_id == stream_id)
        )
        state = _spot_state(position)
        return {
            "state": _spot_dict(state),
            "metrics": spot_metrics(state, mark_price),
            "version": position.version if position else 0,
        }

    async def derivative(
        self, stream_id: UUID, mark_price: Decimal | None = None
    ) -> dict[str, object] | None:
        await self._stream(stream_id)
        position = await self._session.scalar(
            select(DerivativePosition).where(DerivativePosition.stream_id == stream_id)
        )
        state = _derivative_state(position)
        if state is None:
            return None
        return {
            "state": _derivative_dict(state),
            "metrics": derivative_metrics(state, mark_price),
            "version": position.version if position else 0,
        }

    async def record_spot(self, stream_id: UUID, command: SpotCommand) -> dict[str, object]:
        stream = await self._stream(stream_id)
        position = await self._session.scalar(
            select(Position).where(Position.stream_id == stream_id)
        )
        if position is None:
            position = Position(
                stream_id=stream_id,
                instrument_id=stream.primary_instrument_id,
                quantity=Decimal("0"),
                avg_cost=Decimal("0"),
                cost_currency="USDT",
                realized_pnl=Decimal("0"),
                fee_paid=Decimal("0"),
                version=1,
            )
            self._session.add(position)
            await self._session.flush()

        before = _spot_state(position)
        kind = command.kind.upper()
        if kind == "BUY":
            if command.price is None:
                raise PortfolioError("INVALID_ARGUMENT", "BUY requires price")
            after = spot_buy(before, command.quantity, command.price, command.fee)
        elif kind == "SELL":
            if command.price is None:
                raise PortfolioError("INVALID_ARGUMENT", "SELL requires price")
            after = spot_sell(before, command.quantity, command.price, command.fee)
        elif kind == "OPENING":
            avg_cost = command.avg_cost if command.avg_cost is not None else command.price
            if avg_cost is None:
                raise PortfolioError("INVALID_ARGUMENT", "OPENING requires avg_cost")
            after = spot_opening(before, command.quantity, avg_cost)
        elif kind == "CORRECTION":
            avg_cost = command.avg_cost if command.avg_cost is not None else command.price
            if avg_cost is None and command.quantity > 0:
                raise PortfolioError("INVALID_ARGUMENT", "CORRECTION requires avg_cost")
            after = spot_correction(before, command.quantity, avg_cost or Decimal("0"))
        else:
            raise PortfolioError("INVALID_ARGUMENT", f"unsupported spot kind: {kind}")

        position.quantity = after.quantity
        position.avg_cost = after.avg_cost
        position.realized_pnl = after.realized_pnl
        position.fee_paid = after.fee_paid
        position.version += 1

        event = PositionEvent(
            stream_id=stream_id,
            kind=kind,
            side=kind if kind in {"BUY", "SELL"} else None,
            quantity=command.quantity,
            price=command.price if command.price is not None else command.avg_cost,
            fee=command.fee,
            occurred_at=command.occurred_at,
            note=command.note,
            source="MANUAL",
            before_state=_spot_dict(before),
            after_state=_spot_dict(after),
        )
        self._session.add(event)
        await self._session.flush()

        snapshot = PositionSnapshot(
            stream_id=stream_id,
            position_version=position.version,
            as_of=command.occurred_at,
            quantity=after.quantity,
            avg_cost=after.avg_cost,
            cost_currency="USDT",
            realized_pnl=after.realized_pnl,
            source_event_id=event.id,
        )
        self._session.add(snapshot)
        await self._session.flush()
        event.resulting_snapshot_id = snapshot.id
        await self._session.commit()

        return {
            "event_id": event.id,
            "snapshot_id": snapshot.id,
            "state": _spot_dict(after),
        }

    async def record_derivative(
        self,
        stream_id: UUID,
        command: DerivativeCommand,
        mark_price: Decimal | None = None,
    ) -> dict[str, object]:
        stream = await self._stream(stream_id)
        instrument = await self._swap_instrument(stream)
        position = await self._session.scalar(
            select(DerivativePosition).where(DerivativePosition.stream_id == stream_id)
        )
        state = _derivative_state(position)
        kind = command.kind.upper()

        if kind == "OPEN":
            if state is not None and state.quantity_base > 0:
                raise PortfolioError("POSITION_EXISTS", "close the current position before opening")
            if not command.side or command.price is None or command.leverage is None:
                raise PortfolioError("INVALID_ARGUMENT", "OPEN requires side/price/leverage")
            if command.quantity_base is None or command.margin is None:
                raise PortfolioError("INVALID_ARGUMENT", "OPEN requires quantity_base/margin")
            after = derivative_open(
                side=command.side,
                quantity=command.quantity_base,
                price=command.price,
                leverage=command.leverage,
                margin=command.margin,
                fee=command.fee,
                liquidation_price=command.liquidation_price,
            )
            if position is None:
                position = DerivativePosition(
                    stream_id=stream_id,
                    instrument_id=instrument.id,
                    side=after.side,
                    quantity_base=after.quantity_base,
                    entry_price=after.entry_price,
                    leverage=after.leverage,
                    margin_mode=command.margin_mode,
                    margin=after.margin,
                    liquidation_price=after.liquidation_price,
                    realized_pnl=after.realized_pnl,
                    funding_fees=after.funding_fees,
                    version=1,
                )
                self._session.add(position)
                await self._session.flush()
        else:
            if state is None:
                raise PortfolioError("NO_POSITION", "no derivative position")
            if command.side and command.side != state.side:
                raise PortfolioError("POSITION_SIDE_CONFLICT", "side does not match position")
            if kind == "INCREASE":
                if command.quantity_base is None or command.price is None:
                    raise PortfolioError(
                        "INVALID_ARGUMENT", "INCREASE requires quantity_base/price"
                    )
                after = derivative_increase(
                    state,
                    quantity=command.quantity_base,
                    price=command.price,
                    fee=command.fee,
                    margin_delta=command.margin_delta,
                )
            elif kind == "REDUCE":
                if command.quantity_base is None or command.price is None:
                    raise PortfolioError("INVALID_ARGUMENT", "REDUCE requires quantity_base/price")
                after = derivative_reduce(
                    state,
                    quantity=command.quantity_base,
                    price=command.price,
                    fee=command.fee,
                    margin=command.margin,
                )
            elif kind == "CLOSE":
                if command.price is None:
                    raise PortfolioError("INVALID_ARGUMENT", "CLOSE requires price")
                after = derivative_reduce(
                    state,
                    quantity=state.quantity_base,
                    price=command.price,
                    fee=command.fee,
                )
            elif kind == "ADJUST_MARGIN":
                if command.margin is None:
                    raise PortfolioError("INVALID_ARGUMENT", "ADJUST_MARGIN requires margin")
                after = derivative_adjust_margin(state, command.margin)
            elif kind == "FUNDING":
                if command.funding_amount is None:
                    raise PortfolioError("INVALID_ARGUMENT", "FUNDING requires funding_amount")
                after = derivative_funding(state, command.funding_amount)
            elif kind == "CORRECTION":
                if (
                    not command.side
                    or command.quantity_base is None
                    or command.price is None
                    or command.leverage is None
                    or command.margin is None
                ):
                    raise PortfolioError(
                        "INVALID_ARGUMENT",
                        "CORRECTION requires side/quantity_base/price/leverage/margin",
                    )
                after = derivative_correction(
                    state,
                    side=command.side,
                    quantity=command.quantity_base,
                    entry_price=command.price,
                    leverage=command.leverage,
                    margin=command.margin,
                    liquidation_price=command.liquidation_price,
                )
            else:
                raise PortfolioError("INVALID_ARGUMENT", f"unsupported derivative kind: {kind}")

        assert position is not None
        before = state if state is not None else DerivativeState()
        position.side = after.side
        position.quantity_base = after.quantity_base
        position.entry_price = after.entry_price
        position.leverage = after.leverage
        position.margin_mode = command.margin_mode
        position.margin = after.margin
        position.liquidation_price = after.liquidation_price
        position.realized_pnl = after.realized_pnl
        position.funding_fees = after.funding_fees
        position.version += 1

        event = DerivativePositionEvent(
            stream_id=stream_id,
            position_id=position.id,
            kind=kind,
            side=after.side,
            quantity_base=command.quantity_base,
            price=command.price,
            fee=command.fee,
            margin_delta=command.margin_delta,
            funding_amount=command.funding_amount,
            occurred_at=command.occurred_at,
            note=command.note,
            before_state=_derivative_dict(before),
            after_state=_derivative_dict(after),
        )
        self._session.add(event)
        await self._session.flush()

        mark = mark_price or command.price or after.entry_price
        metrics = derivative_metrics(after, mark)
        snapshot = DerivativePositionSnapshot(
            stream_id=stream_id,
            position_id=position.id,
            position_version=position.version,
            as_of=command.occurred_at,
            side=after.side,
            quantity_base=after.quantity_base,
            entry_price=after.entry_price,
            leverage=after.leverage,
            margin_mode=command.margin_mode,
            margin=after.margin,
            liquidation_price=after.liquidation_price,
            mark_price=_as_decimal(metrics["mark_price"]),
            notional=_as_decimal(metrics["notional"]),
            unrealized_pnl=_as_decimal(metrics["unrealized_pnl"]),
            roe=_as_decimal(metrics["roe"]),
            liq_distance_pct=_as_decimal(metrics["liq_distance_pct"]),
            risk_budget_usage_pct=None,
            source_event_id=event.id,
        )
        self._session.add(snapshot)
        await self._session.flush()
        event.resulting_snapshot_id = snapshot.id
        await self._session.commit()

        return {
            "event_id": event.id,
            "snapshot_id": snapshot.id,
            "state": _derivative_dict(after),
            "metrics": metrics,
        }

    async def simulate_spot(
        self, stream_id: UUID, side: str, quantity: Decimal, assumed_price: Decimal
    ) -> dict[str, object]:
        await self._stream(stream_id)
        position = await self._session.scalar(
            select(Position).where(Position.stream_id == stream_id)
        )
        before = _spot_state(position)
        after = (
            spot_buy(before, quantity, assumed_price)
            if side.upper() == "BUY"
            else spot_sell(before, quantity, assumed_price)
        )
        return {
            "before": {"state": _spot_dict(before), "metrics": spot_metrics(before, assumed_price)},
            "after": {"state": _spot_dict(after), "metrics": spot_metrics(after, assumed_price)},
        }

    async def simulate_derivative(
        self, stream_id: UUID, action: str, size_change_pct: Decimal, assumed_mark: Decimal
    ) -> dict[str, object]:
        await self._stream(stream_id)
        position = await self._session.scalar(
            select(DerivativePosition).where(DerivativePosition.stream_id == stream_id)
        )
        state = _derivative_state(position)
        if state is None or state.quantity_base <= 0:
            raise PortfolioError("NO_POSITION", "no derivative position")
        action = action.upper()
        quantity = state.quantity_base * size_change_pct / Decimal("100")
        if action in {"REDUCE_LONG", "REDUCE_SHORT"}:
            after = derivative_reduce(state, quantity=quantity, price=assumed_mark)
        elif action in {"CLOSE_LONG", "CLOSE_SHORT"}:
            after = derivative_reduce(
                state, quantity=state.quantity_base, price=assumed_mark
            )
        elif action in {"INCREASE_LONG", "INCREASE_SHORT"}:
            after = derivative_increase(state, quantity=quantity, price=assumed_mark)
        else:
            raise PortfolioError("INVALID_ARGUMENT", f"unsupported action: {action}")
        return {
            "before": {
                "state": _derivative_dict(state),
                "metrics": derivative_metrics(state, assumed_mark),
            },
            "after": {
                "state": _derivative_dict(after),
                "metrics": derivative_metrics(after, assumed_mark),
            },
        }

    @staticmethod
    def now() -> datetime:
        return datetime.now(UTC)