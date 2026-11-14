from decimal import Decimal

import pytest

from app.domain.portfolio import (
    DerivativeState,
    PortfolioError,
    SpotState,
    derivative_increase,
    derivative_metrics,
    derivative_open,
    derivative_reduce,
    spot_buy,
    spot_metrics,
    spot_sell,
)


def test_spot_weighted_average_and_realized_pnl() -> None:
    state = SpotState()
    state = spot_buy(state, Decimal("0.1"), Decimal("80000"), Decimal("4"))
    state = spot_buy(state, Decimal("0.1"), Decimal("90000"), Decimal("6"))
    assert state.quantity == Decimal("0.2")
    assert state.avg_cost == Decimal("85050")

    state = spot_sell(state, Decimal("0.05"), Decimal("95000"), Decimal("2"))
    assert state.quantity == Decimal("0.15")
    assert state.realized_pnl == Decimal("495.5")


def test_spot_metrics() -> None:
    state = SpotState(quantity=Decimal("0.5"), avg_cost=Decimal("82000"))
    metrics = spot_metrics(state, Decimal("90000"))
    assert Decimal(str(metrics["market_value"])) == Decimal("45000")
    assert Decimal(str(metrics["unrealized_pnl"])) == Decimal("4000")
    pct = Decimal(str(metrics["unrealized_pnl_pct"]))
    assert pct.quantize(Decimal("0.0001")) == Decimal("9.7561")


def test_spot_sell_insufficient() -> None:
    with pytest.raises(PortfolioError) as error:
        spot_sell(
            SpotState(quantity=Decimal("0.1"), avg_cost=Decimal("80000")),
            Decimal("0.2"),
            Decimal("90000"),
        )
    assert error.value.code == "INSUFFICIENT_POSITION"


def test_long_perpetual_pnl_and_liq_distance() -> None:
    state = derivative_open(
        side="LONG",
        quantity=Decimal("0.2"),
        price=Decimal("88000"),
        leverage=Decimal("3"),
        margin=Decimal("6000"),
        liquidation_price=Decimal("65000"),
    )
    state = derivative_increase(
        state, quantity=Decimal("0.1"), price=Decimal("90000"), margin_delta=Decimal("3000")
    )
    assert state.quantity_base == Decimal("0.3")
    assert state.entry_price == Decimal("88666.66666666666666666666667")
    assert state.margin == Decimal("9000")

    metrics = derivative_metrics(state, Decimal("92000"))
    assert Decimal(str(metrics["notional"])) == Decimal("27600")
    assert Decimal(str(metrics["unrealized_pnl"])).quantize(Decimal("0.01")) == Decimal("1000.00")
    assert Decimal(str(metrics["liq_distance_pct"])).quantize(Decimal("0.01")) == Decimal("29.35")

    state = derivative_reduce(state, quantity=Decimal("0.1"), price=Decimal("90000"))
    assert state.quantity_base == Decimal("0.2")


def test_short_perpetual_pnl() -> None:
    state = derivative_open(
        side="SHORT",
        quantity=Decimal("1"),
        price=Decimal("90000"),
        leverage=Decimal("2"),
        margin=Decimal("10000"),
        liquidation_price=Decimal("110000"),
    )
    metrics = derivative_metrics(state, Decimal("80000"))
    assert metrics["unrealized_pnl"] == "10000"
    assert metrics["roe"] == "100"


def test_derivative_state_default() -> None:
    assert DerivativeState().side == "LONG"