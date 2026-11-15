from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    CandleOut,
    CandlesOut,
    DerivativesOut,
    IndicatorsOut,
    MarketOverviewOut,
    QuoteOut,
)
from app.application.market_service import MarketService
from app.db.session import get_session
from app.infrastructure.market.base import (
    DerivativesOverview,
    InstrumentNotFound,
    MarketProviderError,
    Quote,
    Timeframe,
)
from app.infrastructure.market.factory import get_provider
from app.infrastructure.market.okx import OKXProvider

router = APIRouter(prefix="/assets/{symbol}", tags=["market"])


def get_market_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    provider: Annotated[OKXProvider, Depends(get_provider)],
) -> MarketService:
    return MarketService(session, provider)


def _decimal_str(value: Decimal | None, digits: int | None = None) -> str | None:
    if value is None:
        return None
    if digits is not None:
        value = value.quantize(Decimal(1).scaleb(-digits))
    return format(value, "f")


def _quote_out(quote: Quote) -> QuoteOut:
    return QuoteOut(
        instrument=quote.instrument,
        price=_decimal_str(quote.price, 8),
        change_24h_pct=_decimal_str(quote.change_24h_pct, 4),
        high_24h=_decimal_str(quote.high_24h, 8),
        low_24h=_decimal_str(quote.low_24h, 8),
        volume_24h=_decimal_str(quote.volume_24h, 2),
        market_time=quote.market_time,
        fetched_at=quote.fetched_at,
        source=quote.source,
        staleness=quote.staleness,
    )


def _derivatives_out(overview: DerivativesOverview) -> DerivativesOut:
    return DerivativesOut(
        instrument=overview.instrument,
        mark_price=_decimal_str(overview.mark_price, 8),
        funding_rate=_decimal_str(overview.funding_rate, 8),
        next_funding_time=overview.next_funding_time,
        open_interest=_decimal_str(overview.open_interest, 4),
        open_interest_usd=_decimal_str(overview.open_interest_usd, 2),
        market_time=overview.market_time,
        fetched_at=overview.fetched_at,
        source=overview.source,
        staleness=overview.staleness,
    )


def _market_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InstrumentNotFound):
        return HTTPException(status_code=404, detail=exc.message)
    assert isinstance(exc, MarketProviderError)
    return HTTPException(status_code=503, detail=f"{exc.code}: {exc.message}")


@router.get("/market", response_model=QuoteOut)
async def get_market(
    symbol: str,
    market_type: Literal["SPOT", "SWAP"] = "SPOT",
    service: MarketService = Depends(get_market_service),
) -> QuoteOut:
    try:
        quote = await service.quote(symbol, market_type)
    except (InstrumentNotFound, MarketProviderError) as exc:
        raise _market_error(exc) from exc
    return _quote_out(quote)


@router.get("/candles", response_model=CandlesOut)
async def get_candles(
    symbol: str,
    timeframe: Literal["1h", "4h", "1d"] = "1h",
    limit: int = Query(default=200, ge=1, le=300),
    market_type: Literal["SPOT", "SWAP"] = "SPOT",
    service: MarketService = Depends(get_market_service),
) -> CandlesOut:
    try:
        candles = await service.candles(symbol, Timeframe(timeframe), limit, market_type)
    except (InstrumentNotFound, MarketProviderError) as exc:
        raise _market_error(exc) from exc
    return CandlesOut(
        instrument=symbol.upper(),
        timeframe=timeframe,
        candles=[
            CandleOut(
                open_time=candle.open_time,
                open=_decimal_str(candle.open, 8),
                high=_decimal_str(candle.high, 8),
                low=_decimal_str(candle.low, 8),
                close=_decimal_str(candle.close, 8),
                volume=_decimal_str(candle.volume, 8),
                confirmed=candle.confirmed,
            )
            for candle in candles
        ],
    )


@router.get("/indicators", response_model=IndicatorsOut)
async def get_indicators(
    symbol: str,
    timeframes: str = "1h,4h,1d",
    market_type: Literal["SPOT", "SWAP"] = "SPOT",
    service: MarketService = Depends(get_market_service),
) -> IndicatorsOut:
    requested = [item.strip() for item in timeframes.split(",") if item.strip()]
    try:
        parsed = [Timeframe(item) for item in requested]
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"Unsupported timeframe; use 1h,4h,1d: {timeframes}"
        ) from exc
    try:
        snapshots = await service.indicators(symbol, parsed, market_type)
    except (InstrumentNotFound, MarketProviderError) as exc:
        raise _market_error(exc) from exc

    warnings: list[str] = []
    for timeframe, snapshot in snapshots.items():
        for warning in snapshot.get("warnings", []):  # type: ignore[union-attr]
            warnings.append(f"{timeframe}: {warning}")
    as_of = next(
        (
            snapshot.get("as_of")  # type: ignore[union-attr]
            for snapshot in snapshots.values()
            if snapshot.get("as_of")  # type: ignore[union-attr]
        ),
        None,
    )
    return IndicatorsOut(
        as_of=as_of,  # type: ignore[arg-type]
        timeframes=snapshots,
        warnings=warnings,
    )


@router.get("/derivatives", response_model=DerivativesOut)
async def get_derivatives(
    symbol: str,
    service: MarketService = Depends(get_market_service),
) -> DerivativesOut:
    try:
        overview = await service.derivatives(symbol)
    except (InstrumentNotFound, MarketProviderError) as exc:
        raise _market_error(exc) from exc
    return _derivatives_out(overview)


@router.get("/market/overview", response_model=MarketOverviewOut)
async def get_market_overview(
    symbol: str,
    market_type: Literal["SPOT", "SWAP"] = "SPOT",
    service: MarketService = Depends(get_market_service),
) -> MarketOverviewOut:
    try:
        overview = await service.market_overview(symbol, market_type)
    except (InstrumentNotFound, MarketProviderError) as exc:
        raise _market_error(exc) from exc

    derivatives = overview["derivatives"]
    return MarketOverviewOut(
        quote=_quote_out(overview["quote"]),
        indicators=IndicatorsOut(
            as_of=next(
                (
                    snapshot.get("as_of")  # type: ignore[union-attr]
                    for snapshot in overview["indicators"].values()  # type: ignore[union-attr]
                    if snapshot.get("as_of")  # type: ignore[union-attr]
                ),
                None,
            ),
            timeframes=overview["indicators"],  # type: ignore[arg-type]
            warnings=overview["warnings"],  # type: ignore[arg-type]
        ),
        derivatives=_derivatives_out(derivatives) if derivatives is not None else None,
        warnings=overview["warnings"],  # type: ignore[arg-type]
    )