from fastapi import APIRouter, HTTPException

from app.api.v1.schemas import StopLossPreviewRequest
from app.domain.risk import RiskError, StopLossInput, derive_stop_loss

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/stop-loss/preview")
async def preview_stop_loss(payload: StopLossPreviewRequest) -> dict[str, object]:
    try:
        return derive_stop_loss(
            StopLossInput(
                side=payload.side,
                entry_price=payload.entry_price,
                quantity_base=payload.quantity_base,
                account_equity_usd=payload.account_equity_usd,
                max_drawdown_pct=payload.max_drawdown_pct,
                max_concurrent_positions=payload.max_concurrent_positions,
                max_risk_per_trade_pct=payload.max_risk_per_trade_pct,
                risk_budget_usd=payload.risk_budget_usd,
                explicit_stop=payload.explicit_stop,
                liquidation_price=payload.liquidation_price,
                fee_buffer_usd=payload.fee_buffer_usd,
            )
        )
    except RiskError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.code}: {exc.message}") from exc
