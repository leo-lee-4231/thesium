from decimal import Decimal

import pytest

from app.domain.risk import RiskError, StopLossInput, derive_stop_loss


def long_input(**overrides: object) -> StopLossInput:
    values: dict[str, object] = {
        "side": "LONG",
        "entry_price": Decimal("60000"),
        "quantity_base": Decimal("0.1"),
        "account_equity_usd": Decimal("10000"),
        "max_drawdown_pct": Decimal("20"),
        "max_concurrent_positions": 5,
    }
    values.update(overrides)
    return StopLossInput(**values)  # type: ignore[arg-type]


def test_long_stop_derived_from_drawdown_and_positions() -> None:
    result = derive_stop_loss(long_input())
    assert result["per_trade_risk_pct"] == "4.0000"
    assert result["risk_amount_usd"] == "400.00"
    assert result["derived_stop"] == "56000.00000000"
    assert result["stop_source"] == "DERIVED"
    assert result["within_budget"] is True


def test_short_stop_is_above_entry() -> None:
    result = derive_stop_loss(long_input(side="SHORT"))
    assert result["derived_stop"] == "64000.00000000"
    assert result["stop_source"] == "DERIVED"


def test_explicit_stop_over_budget_warns() -> None:
    result = derive_stop_loss(long_input(explicit_stop=Decimal("54000")))
    assert result["effective_stop"] == "54000.00000000"
    assert result["stop_source"] == "USER"
    assert result["within_budget"] is False
    assert result["loss_at_stop_usd"] == "600.00"


def test_wrong_side_explicit_stop_falls_back_to_derived() -> None:
    result = derive_stop_loss(long_input(explicit_stop=Decimal("62000")))
    assert result["effective_stop"] == "56000.00000000"
    assert result["stop_source"] == "DERIVED"
    assert any("方向不正确" in warning for warning in result["warnings"])


def test_short_stop_beyond_liquidation_warns() -> None:
    result = derive_stop_loss(
        long_input(side="SHORT", liquidation_price=Decimal("63000"))
    )
    assert result["liquidation_buffer_pct"] == "-1.6667"
    assert any("清算价" in warning for warning in result["warnings"])


def test_explicit_risk_override_and_absolute_cap() -> None:
    result = derive_stop_loss(
        long_input(
            max_risk_per_trade_pct=Decimal("1"),
            risk_budget_usd=Decimal("100"),
        )
    )
    assert result["per_trade_risk_pct"] == "1.0000"
    assert result["risk_amount_usd"] == "100.00"
    assert result["derived_stop"] == "59000.00000000"


def test_invalid_side() -> None:
    with pytest.raises(RiskError):
        derive_stop_loss(long_input(side="BOTH"))