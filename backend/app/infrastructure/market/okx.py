import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.infrastructure.market.base import (
    Candle,
    DerivativesOverview,
    MarketProviderError,
    Quote,
    Timeframe,
)

_TIMEFRAME_MAP = {
    Timeframe.H1: "1H",
    Timeframe.H4: "4H",
    Timeframe.D1: "1Dutc",
}

# OKX returns HTTP 200 with these business codes when the public rate limit is hit.
_RATE_LIMIT_CODES = {"50011", "50013", "50026"}
_MAX_ATTEMPTS = 3

logger = logging.getLogger(__name__)


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _required_decimal(value: Any, field: str) -> Decimal:
    parsed = _decimal(value)
    if parsed is None:
        raise MarketProviderError("INVALID_RESPONSE", f"OKX returned invalid {field}")
    return parsed


def _ms_to_dt(value: Any) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)


class OKXProvider:
    """OKX public market data provider.

    Only public endpoints; no API key. Honors HTTP(S)_PROXY via httpx trust_env.
    """

    name = "okx"

    def __init__(
        self,
        base_url: str = "https://www.okx.com",
        timeout_seconds: float = 10.0,
        client: httpx.AsyncClient | None = None,
        proxy: str | None = None,
        trust_env: bool = True,
    ) -> None:
        if client is not None:
            self._client = client
        elif proxy:
            # A dedicated proxy for market data; socks5h keeps DNS on the proxy,
            # which matters where local DNS returns a blocked placeholder IP.
            self._client = httpx.AsyncClient(
                base_url=base_url,
                timeout=httpx.Timeout(timeout_seconds),
                headers={"User-Agent": "thesium/0.1"},
                proxy=proxy,
                trust_env=False,
            )
        else:
            self._client = httpx.AsyncClient(
                base_url=base_url,
                timeout=httpx.Timeout(timeout_seconds),
                headers={"User-Agent": "thesium/0.1"},
                trust_env=trust_env,
            )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = await self._client.get(path, params=params)
                response.raise_for_status()
                payload = response.json()
                code = str(payload.get("code"))
                if code != "0":
                    message = f"OKX error {code}: {payload.get('msg')}"
                    if code in _RATE_LIMIT_CODES and attempt < _MAX_ATTEMPTS - 1:
                        last_error = MarketProviderError("RATE_LIMITED", message)
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    if code in _RATE_LIMIT_CODES:
                        raise MarketProviderError("RATE_LIMITED", message)
                    raise MarketProviderError("UPSTREAM_ERROR", message)
                data = payload.get("data") or []
                if not data:
                    raise MarketProviderError("NO_DATA", "OKX returned no data")
                return data
            except MarketProviderError:
                raise
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 429:
                    last_error = exc
                    if attempt < _MAX_ATTEMPTS - 1:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    raise MarketProviderError(
                        "RATE_LIMITED", "OKX rate limited (HTTP 429)"
                    ) from exc
                if status in {500, 502, 503, 504} and attempt < _MAX_ATTEMPTS - 1:
                    last_error = exc
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                raise MarketProviderError(
                    "UPSTREAM_ERROR", f"OKX HTTP {status}"
                ) from exc
            except httpx.TransportError as exc:
                # Includes timeouts, proxy errors, connection resets, and protocol
                # errors. A dead local proxy commonly shows up as ReadError('').
                last_error = exc
                logger.warning(
                    "OKX request failed path=%s attempt=%s error=%s: %r",
                    path,
                    attempt + 1,
                    type(exc).__name__,
                    exc,
                )
                if attempt < _MAX_ATTEMPTS - 1:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
        detail = f"{type(last_error).__name__}: {last_error!r}" if last_error else "no response"
        raise MarketProviderError(
            "UPSTREAM_UNAVAILABLE",
            f"OKX network unavailable after {_MAX_ATTEMPTS} attempts ({detail})",
        )

    async def get_quote(self, symbol: str) -> Quote:
        data = await self._request("/api/v5/market/ticker", {"instId": symbol})
        item = data[0]
        last = _required_decimal(item.get("last"), "last")
        open_24h = _decimal(item.get("open24h"))
        change = None
        if open_24h is not None and open_24h != 0:
            change = (last - open_24h) / open_24h * Decimal(100)
        market_time = _ms_to_dt(item["ts"])
        fetched_at = datetime.now(UTC)
        return Quote(
            instrument=symbol,
            price=last,
            change_24h_pct=change,
            high_24h=_decimal(item.get("high24h")),
            low_24h=_decimal(item.get("low24h")),
            volume_24h=_decimal(item.get("volCcy24h")) or _decimal(item.get("vol24h")),
            market_time=market_time,
            fetched_at=fetched_at,
            source=self.name,
            staleness=self._staleness(market_time, fetched_at, 300),
        )

    async def get_candles(
        self, symbol: str, timeframe: Timeframe, limit: int = 200
    ) -> list[Candle]:
        bar = _TIMEFRAME_MAP[timeframe]
        data = await self._request(
            "/api/v5/market/candles",
            {"instId": symbol, "bar": bar, "limit": str(max(1, min(limit, 300)))},
        )
        candles = [
            Candle(
                open_time=_ms_to_dt(item[0]),
                open=_required_decimal(item[1], "open"),
                high=_required_decimal(item[2], "high"),
                low=_required_decimal(item[3], "low"),
                close=_required_decimal(item[4], "close"),
                volume=_required_decimal(item[5], "volume"),
                confirmed=item[8] == "1",
            )
            for item in data
        ]
        candles.sort(key=lambda candle: candle.open_time)
        return candles

    async def get_derivatives_overview(self, symbol: str) -> DerivativesOverview:
        mark_data, funding_data, oi_data = await asyncio.gather(
            self._request(
                "/api/v5/public/mark-price", {"instType": "SWAP", "instId": symbol}
            ),
            self._request("/api/v5/public/funding-rate", {"instId": symbol}),
            self._request(
                "/api/v5/public/open-interest", {"instType": "SWAP", "instId": symbol}
            ),
        )
        mark = mark_data[0]
        funding = funding_data[0]
        oi = oi_data[0]
        market_time = _ms_to_dt(mark["ts"])
        fetched_at = datetime.now(UTC)
        return DerivativesOverview(
            instrument=symbol,
            mark_price=_required_decimal(mark.get("markPx"), "markPx"),
            funding_rate=_decimal(funding.get("fundingRate")),
            next_funding_time=(
                _ms_to_dt(funding["nextFundingTime"])
                if funding.get("nextFundingTime")
                else None
            ),
            open_interest=_decimal(oi.get("oiCcy")) or _decimal(oi.get("oi")),
            open_interest_usd=_decimal(oi.get("oiUsd")),
            market_time=market_time,
            fetched_at=fetched_at,
            source=self.name,
            staleness=self._staleness(market_time, fetched_at, 600),
        )

    @staticmethod
    def _staleness(market_time: datetime, fetched_at: datetime, threshold: int) -> str:
        age = (fetched_at - market_time).total_seconds()
        if age > threshold:
            return "STALE"
        return "FRESH"