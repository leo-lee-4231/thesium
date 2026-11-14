from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


class RiskError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class StopLossInput:
    side: str
    entry_price: Decimal
    quantity_base: Decimal
    account_equity_usd: Decimal
    max_drawdown_pct: Decimal
    max_concurrent_positions: int = 5
    max_risk_per_trade_pct: Decimal | None = None
    risk_budget_usd: Decimal | None = None
    explicit_stop: Decimal | None = None
    liquidation_price: Decimal | None = None
    fee_buffer_usd: Decimal = Decimal("0")


def _q(value: Decimal, digits: int) -> str:
    quant = Decimal(1).scaleb(-digits)
    return format(value.quantize(quant, rounding=ROUND_HALF_UP), "f")


def _positive(value: Decimal | None, name: str) -> Decimal:
    if value is None or value <= 0:
        raise RiskError("INVALID_ARGUMENT", f"{name} must be > 0")
    return value


def derive_stop_loss(params: StopLossInput) -> dict[str, object]:
    """Derive a per-trade stop from equity / max drawdown / position size.

    The max drawdown is a portfolio guardrail. A per-trade risk is either an
    explicit override or max_drawdown / max_concurrent_positions. This is a
    deterministic calculation; the LLM must not do this arithmetic itself.
    """
    side = params.side.upper()
    if side not in {"LONG", "SHORT"}:
        raise RiskError("INVALID_ARGUMENT", "side must be LONG or SHORT")
    entry = _positive(params.entry_price, "entry_price")
    quantity = _positive(params.quantity_base, "quantity_base")
    equity = _positive(params.account_equity_usd, "account_equity_usd")
    if params.max_drawdown_pct < 0 or params.max_drawdown_pct > 100:
        raise RiskError("INVALID_ARGUMENT", "max_drawdown_pct must be between 0 and 100")
    if params.max_concurrent_positions < 1:
        raise RiskError("INVALID_ARGUMENT", "max_concurrent_positions must be >= 1")
    fee_buffer = max(params.fee_buffer_usd, Decimal("0"))

    warnings: list[str] = []
    assumptions: list[str] = []

    if params.max_risk_per_trade_pct is not None:
        per_trade_pct = params.max_risk_per_trade_pct
        pct_source = "USER_OVERRIDE"
        if per_trade_pct > params.max_drawdown_pct:
            warnings.append("单笔风险比例高于最大资金回撤率，单笔亏损就可能触达组合上限")
    else:
        per_trade_pct = params.max_drawdown_pct / Decimal(params.max_concurrent_positions)
        pct_source = "MAX_DRAWDOWN_DIVIDED_BY_POSITIONS"
        assumptions.append(
            f"未单独设置单笔风险，按最大回撤 {params.max_drawdown_pct}% / "
            f"最多 {params.max_concurrent_positions} 笔并行推导"
        )
    if per_trade_pct <= 0:
        raise RiskError("INVALID_ARGUMENT", "derived per-trade risk must be > 0")

    gross_risk = equity * per_trade_pct / Decimal("100")
    if params.risk_budget_usd is not None and params.risk_budget_usd < gross_risk:
        assumptions.append(
            f"绝对风险预算 {params.risk_budget_usd} USDT 低于比例风险，取绝对值"
        )
        gross_risk = params.risk_budget_usd
    if gross_risk <= fee_buffer:
        raise RiskError("INVALID_ARGUMENT", "fee buffer consumes the entire risk budget")

    distance = (gross_risk - fee_buffer) / quantity
    derived_stop = entry - distance if side == "LONG" else entry + distance
    if derived_stop <= 0:
        raise RiskError("INVALID_ARGUMENT", "derived stop is <= 0")

    explicit = params.explicit_stop
    explicit_valid = explicit is not None and (
        (side == "LONG" and explicit < entry) or (side == "SHORT" and explicit > entry)
    )
    if explicit is not None and not explicit_valid:
        warnings.append("用户止损价方向不正确：多头止损应低于开仓价，空头止损应高于开仓价")

    if explicit_valid and explicit is not None:
        effective_stop = explicit
        stop_source = "USER"
        loss_at_stop = abs(entry - explicit) * quantity + fee_buffer
    else:
        effective_stop = derived_stop
        stop_source = "DERIVED"
        loss_at_stop = gross_risk
    risk_pct = loss_at_stop / equity * Decimal("100")
    within_budget = loss_at_stop <= gross_risk + Decimal("0.00000001")
    if not within_budget:
        warnings.append(
            f"该止损对应亏损 {_q(loss_at_stop, 2)} USDT，"
            f"超过单笔风险预算 {_q(gross_risk, 2)} USDT"
        )

    liquidation = params.liquidation_price
    liq_buffer_pct: Decimal | None = None
    if liquidation is not None:
        if liquidation <= 0:
            raise RiskError("INVALID_ARGUMENT", "liquidation_price must be > 0")
        if side == "LONG":
            liq_buffer_pct = (effective_stop - liquidation) / entry * Decimal("100")
            if effective_stop <= liquidation:
                warnings.append("止损价已低于/等于清算价，可能先被清算；需要降低仓位或增加保证金")
        else:
            liq_buffer_pct = (liquidation - effective_stop) / entry * Decimal("100")
            if effective_stop >= liquidation:
                warnings.append("止损价已高于/等于清算价，可能先被清算；需要降低仓位或增加保证金")

    return {
        "side": side,
        "entry_price": _q(entry, 8),
        "quantity_base": _q(quantity, 8),
        "account_equity_usd": _q(equity, 2),
        "max_drawdown_pct": _q(params.max_drawdown_pct, 4),
        "per_trade_risk_pct": _q(per_trade_pct, 4),
        "risk_pct_source": pct_source,
        "risk_amount_usd": _q(gross_risk, 2),
        "derived_stop": _q(derived_stop, 8),
        "explicit_stop": _q(explicit, 8) if explicit is not None else None,
        "effective_stop": _q(effective_stop, 8),
        "stop_source": stop_source,
        "stop_distance_pct": _q(
            abs(entry - effective_stop) / entry * Decimal("100"), 4
        ),
        "derived_stop_distance_pct": _q(distance / entry * Decimal("100"), 4),
        "loss_at_stop_usd": _q(loss_at_stop, 2),
        "risk_pct_equity": _q(risk_pct, 4),
        "within_budget": within_budget,
        "liquidation_price": _q(liquidation, 8) if liquidation is not None else None,
        "liquidation_buffer_pct": _q(liq_buffer_pct, 4) if liq_buffer_pct is not None else None,
        "warnings": warnings,
        "assumptions": assumptions,
    }