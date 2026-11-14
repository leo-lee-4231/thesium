from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

ZERO = Decimal("0")


class PortfolioError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SpotState:
    quantity: Decimal = ZERO
    avg_cost: Decimal = ZERO
    realized_pnl: Decimal = ZERO
    fee_paid: Decimal = ZERO


def _require_positive(value: Decimal | None, name: str) -> Decimal:
    if value is None or value <= 0:
        raise PortfolioError("INVALID_ARGUMENT", f"{name} must be > 0")
    return value


def _require_non_negative(value: Decimal, name: str) -> None:
    if value < 0:
        raise PortfolioError("INVALID_ARGUMENT", f"{name} must be >= 0")


def spot_buy(state: SpotState, quantity: Decimal, price: Decimal, fee: Decimal = ZERO) -> SpotState:
    _require_positive(quantity, "quantity")
    _require_positive(price, "price")
    _require_non_negative(fee, "fee")
    new_quantity = state.quantity + quantity
    total_cost = state.avg_cost * state.quantity + price * quantity + fee
    return SpotState(
        quantity=new_quantity,
        avg_cost=total_cost / new_quantity,
        realized_pnl=state.realized_pnl,
        fee_paid=state.fee_paid + fee,
    )


def spot_sell(
    state: SpotState, quantity: Decimal, price: Decimal, fee: Decimal = ZERO
) -> SpotState:
    _require_positive(quantity, "quantity")
    _require_positive(price, "price")
    _require_non_negative(fee, "fee")
    if quantity > state.quantity:
        raise PortfolioError("INSUFFICIENT_POSITION", "sell quantity exceeds position")
    realized = (price - state.avg_cost) * quantity - fee
    new_quantity = state.quantity - quantity
    return SpotState(
        quantity=new_quantity,
        avg_cost=state.avg_cost if new_quantity > 0 else ZERO,
        realized_pnl=state.realized_pnl + realized,
        fee_paid=state.fee_paid + fee,
    )


def spot_opening(state: SpotState, quantity: Decimal, avg_cost: Decimal) -> SpotState:
    _require_positive(quantity, "quantity")
    _require_positive(avg_cost, "avg_cost")
    if state.quantity > 0:
        raise PortfolioError("POSITION_EXISTS", "position already exists; use BUY or CORRECTION")
    return SpotState(quantity=quantity, avg_cost=avg_cost, realized_pnl=state.realized_pnl)


def spot_correction(state: SpotState, quantity: Decimal, avg_cost: Decimal) -> SpotState:
    _require_non_negative(quantity, "quantity")
    _require_non_negative(avg_cost, "avg_cost")
    if quantity == 0:
        avg_cost = ZERO
    return SpotState(
        quantity=quantity,
        avg_cost=avg_cost,
        realized_pnl=state.realized_pnl,
        fee_paid=state.fee_paid,
    )


def spot_metrics(state: SpotState, mark_price: Decimal | None) -> dict[str, object]:
    if mark_price is None:
        return {
            "mark_price": None,
            "market_value": None,
            "unrealized_pnl": None,
            "unrealized_pnl_pct": None,
            "cost_basis": str(state.avg_cost * state.quantity),
        }
    market_value = state.quantity * mark_price
    cost_basis = state.avg_cost * state.quantity
    unrealized = (mark_price - state.avg_cost) * state.quantity
    pct = (unrealized / cost_basis * 100) if cost_basis > 0 else None
    return {
        "mark_price": str(mark_price),
        "market_value": str(market_value),
        "unrealized_pnl": str(unrealized),
        "unrealized_pnl_pct": str(pct) if pct is not None else None,
        "cost_basis": str(cost_basis),
    }


@dataclass(frozen=True)
class DerivativeState:
    side: str = "LONG"
    quantity_base: Decimal = ZERO
    entry_price: Decimal = ZERO
    leverage: Decimal = Decimal("1")
    margin: Decimal = ZERO
    liquidation_price: Decimal | None = None
    realized_pnl: Decimal = ZERO
    funding_fees: Decimal = ZERO


def _validate_side(side: str) -> None:
    if side not in {"LONG", "SHORT"}:
        raise PortfolioError("INVALID_ARGUMENT", "side must be LONG or SHORT")


def derivative_open(
    *,
    side: str,
    quantity: Decimal,
    price: Decimal,
    leverage: Decimal,
    margin: Decimal,
    fee: Decimal = ZERO,
    liquidation_price: Decimal | None = None,
) -> DerivativeState:
    _validate_side(side)
    _require_positive(quantity, "quantity")
    _require_positive(price, "price")
    _require_positive(leverage, "leverage")
    _require_positive(margin, "margin")
    _require_non_negative(fee, "fee")
    return DerivativeState(
        side=side,
        quantity_base=quantity,
        entry_price=price,
        leverage=leverage,
        margin=margin,
        liquidation_price=liquidation_price,
        realized_pnl=-fee,
    )


def derivative_increase(
    state: DerivativeState,
    *,
    quantity: Decimal,
    price: Decimal,
    fee: Decimal = ZERO,
    margin_delta: Decimal | None = None,
) -> DerivativeState:
    if state.quantity_base <= 0:
        raise PortfolioError("NO_POSITION", "no position to increase")
    _require_positive(quantity, "quantity")
    _require_positive(price, "price")
    _require_non_negative(fee, "fee")
    new_quantity = state.quantity_base + quantity
    entry = (state.entry_price * state.quantity_base + price * quantity) / new_quantity
    margin = state.margin + (margin_delta or ZERO)
    return replace(
        state,
        quantity_base=new_quantity,
        entry_price=entry,
        margin=margin,
        realized_pnl=state.realized_pnl - fee,
    )


def derivative_reduce(
    state: DerivativeState,
    *,
    quantity: Decimal,
    price: Decimal,
    fee: Decimal = ZERO,
    margin: Decimal | None = None,
) -> DerivativeState:
    _require_positive(quantity, "quantity")
    _require_positive(price, "price")
    _require_non_negative(fee, "fee")
    if quantity > state.quantity_base:
        raise PortfolioError("INSUFFICIENT_POSITION", "reduce quantity exceeds position")
    pnl = (
        (price - state.entry_price) * quantity
        if state.side == "LONG"
        else (state.entry_price - price) * quantity
    )
    new_quantity = state.quantity_base - quantity
    closed = new_quantity == 0
    new_margin = ZERO if closed else (margin if margin is not None else state.margin)
    return replace(
        state,
        quantity_base=new_quantity,
        margin=new_margin,
        liquidation_price=None if closed else state.liquidation_price,
        realized_pnl=state.realized_pnl + pnl - fee,
    )


def derivative_adjust_margin(state: DerivativeState, margin: Decimal) -> DerivativeState:
    if state.quantity_base <= 0:
        raise PortfolioError("NO_POSITION", "no position to adjust")
    _require_positive(margin, "margin")
    return replace(state, margin=margin)


def derivative_funding(state: DerivativeState, amount: Decimal) -> DerivativeState:
    # positive amount = paid by user; negative = received
    return replace(
        state,
        funding_fees=state.funding_fees + amount,
        realized_pnl=state.realized_pnl - amount,
    )


def derivative_correction(
    state: DerivativeState,
    *,
    side: str,
    quantity: Decimal,
    entry_price: Decimal,
    leverage: Decimal,
    margin: Decimal,
    liquidation_price: Decimal | None,
) -> DerivativeState:
    _validate_side(side)
    _require_non_negative(quantity, "quantity")
    _require_non_negative(entry_price, "entry_price")
    _require_positive(leverage, "leverage")
    _require_non_negative(margin, "margin")
    if quantity == 0:
        entry_price = ZERO
        margin = ZERO
        liquidation_price = None
    return replace(
        state,
        side=side,
        quantity_base=quantity,
        entry_price=entry_price,
        leverage=leverage,
        margin=margin,
        liquidation_price=liquidation_price,
    )


def derivative_metrics(state: DerivativeState, mark_price: Decimal | None) -> dict[str, object]:
    if state.quantity_base <= 0:
        return {
            "mark_price": str(mark_price) if mark_price is not None else None,
            "notional": "0",
            "unrealized_pnl": "0",
            "roe": None,
            "liq_distance_pct": None,
            "margin_ratio_pct": None,
            "effective_leverage": None,
        }
    if mark_price is None:
        return {
            "mark_price": None,
            "notional": None,
            "unrealized_pnl": None,
            "roe": None,
            "liq_distance_pct": None,
            "margin_ratio_pct": None,
            "effective_leverage": None,
        }
    notional = state.quantity_base * mark_price
    unrealized = (
        (mark_price - state.entry_price) * state.quantity_base
        if state.side == "LONG"
        else (state.entry_price - mark_price) * state.quantity_base
    )
    roe = (unrealized / state.margin * 100) if state.margin > 0 else None
    liq_distance = None
    if state.liquidation_price is not None and mark_price > 0:
        liq_distance = (
            (mark_price - state.liquidation_price) / mark_price * 100
            if state.side == "LONG"
            else (state.liquidation_price - mark_price) / mark_price * 100
        )
    return {
        "mark_price": str(mark_price),
        "notional": str(notional),
        "unrealized_pnl": str(unrealized),
        "roe": str(roe) if roe is not None else None,
        "liq_distance_pct": str(liq_distance) if liq_distance is not None else None,
        "margin_ratio_pct": str(state.margin / notional * 100) if notional > 0 else None,
        "effective_leverage": str(notional / state.margin) if state.margin > 0 else None,
    }


@dataclass(frozen=True)
class SpotCommand:
    kind: str
    quantity: Decimal
    price: Decimal | None
    avg_cost: Decimal | None
    fee: Decimal
    occurred_at: datetime
    note: str | None = None


@dataclass(frozen=True)
class DerivativeCommand:
    kind: str
    side: str | None
    quantity_base: Decimal | None
    price: Decimal | None
    leverage: Decimal | None
    margin_mode: str
    margin: Decimal | None
    liquidation_price: Decimal | None
    fee: Decimal
    margin_delta: Decimal | None
    funding_amount: Decimal | None
    occurred_at: datetime
    note: str | None = None
