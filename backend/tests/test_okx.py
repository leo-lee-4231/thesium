from decimal import Decimal

import httpx
import pytest
import respx

from app.infrastructure.market.base import MarketProviderError, Timeframe
from app.infrastructure.market.okx import OKXProvider

TICKER = {
    "code": "0",
    "msg": "",
    "data": [
        {
            "instType": "SPOT",
            "instId": "BTC-USDT",
            "last": "65204.1",
            "open24h": "68648.9",
            "high24h": "69132.9",
            "low24h": "65000",
            "volCcy24h": "765481432.49",
            "ts": "1794675741573",
        }
    ],
}

CANDLES = {
    "code": "0",
    "msg": "",
    "data": [
        ["1794675600000", "65348.7", "65348.7", "65134.1", "65201", "24.6", "1", "1", "0"],
        ["1794672000000", "65746.1", "65753.9", "65000", "65348.8", "844.2", "1", "1", "1"],
    ],
}

MARK = {"code": "0", "msg": "", "data": [{"markPx": "65169", "ts": "1794675750395"}]}
FUNDING = {
    "code": "0",
    "msg": "",
    "data": [
        {
            "fundingRate": "0.00003181",
            "nextFundingTime": "1794729600000",
            "ts": "1794675750000",
        }
    ],
}
OI = {
    "code": "0",
    "msg": "",
    "data": [{"oiCcy": "33661.82", "oiUsd": "2193852004.2", "ts": "1794675749819"}],
}


@respx.mock
async def test_quote_parses_and_computes_change() -> None:
    respx.get("https://www.okx.com/api/v5/market/ticker").mock(
        return_value=httpx.Response(200, json=TICKER)
    )
    provider = OKXProvider()
    try:
        quote = await provider.get_quote("BTC-USDT")
    finally:
        await provider.close()

    assert quote.instrument == "BTC-USDT"
    assert quote.price == Decimal("65204.1")
    assert quote.change_24h_pct is not None
    assert quote.change_24h_pct < 0
    assert quote.staleness in {"FRESH", "STALE"}


@respx.mock
async def test_candles_sorted_ascending() -> None:
    respx.get("https://www.okx.com/api/v5/market/candles").mock(
        return_value=httpx.Response(200, json=CANDLES)
    )
    provider = OKXProvider()
    try:
        candles = await provider.get_candles("BTC-USDT", Timeframe.H1, 2)
    finally:
        await provider.close()

    assert len(candles) == 2
    assert candles[0].open_time < candles[1].open_time
    assert candles[0].confirmed is True
    assert candles[1].confirmed is False
    assert candles[1].close == Decimal("65201")


@respx.mock
async def test_derivatives_overview() -> None:
    respx.get("https://www.okx.com/api/v5/public/mark-price").mock(
        return_value=httpx.Response(200, json=MARK)
    )
    respx.get("https://www.okx.com/api/v5/public/funding-rate").mock(
        return_value=httpx.Response(200, json=FUNDING)
    )
    respx.get("https://www.okx.com/api/v5/public/open-interest").mock(
        return_value=httpx.Response(200, json=OI)
    )
    provider = OKXProvider()
    try:
        overview = await provider.get_derivatives_overview("BTC-USDT-SWAP")
    finally:
        await provider.close()

    assert overview.mark_price == Decimal("65169")
    assert overview.funding_rate == Decimal("0.00003181")
    assert overview.open_interest == Decimal("33661.82")
    assert overview.next_funding_time is not None


@respx.mock
async def test_provider_error_code() -> None:
    respx.get("https://www.okx.com/api/v5/market/ticker").mock(
        return_value=httpx.Response(200, json={"code": "51000", "msg": "bad request", "data": []})
    )
    provider = OKXProvider()
    with pytest.raises(MarketProviderError) as error:
        try:
            await provider.get_quote("BAD")
        finally:
            await provider.close()
    assert error.value.code == "UPSTREAM_ERROR"