from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.agent.context import candle_dict, recent_bar_payload
from app.infrastructure.market.base import Candle


def make_candle(index: int, close: str = "58000") -> Candle:
    return Candle(
        open_time=datetime(2026, 11, 1, tzinfo=UTC) + timedelta(days=index),
        open=Decimal(close),
        high=Decimal("59000"),
        low=Decimal("57000"),
        close=Decimal(close),
        volume=Decimal("12.5"),
        confirmed=index % 2 == 0,
    )


def make_indicator(candle: Candle, rsi: float) -> dict[str, object]:
    return {
        "open_time": candle.open_time.isoformat(),
        "close": str(candle.close),
        "ema20": "58100",
        "ema50": "57900",
        "rsi14": rsi,
        "macd": "12.5",
        "macd_signal": "10.0",
        "macd_hist": "2.5",
        "volatility_pct": "0.02",
        "trend": "UP",
    }


def test_candle_dict_serializes_ohlc() -> None:
    payload = candle_dict(make_candle(0))
    assert payload["open_time"] == "2026-11-01T00:00:00+00:00"
    assert payload["open"] == "58000"
    assert payload["high"] == "59000"
    assert payload["low"] == "57000"
    assert payload["close"] == "58000"
    assert payload["volume"] == "12.5"
    assert payload["confirmed"] is True


def test_recent_bar_payload_merges_ohlc_and_indicators() -> None:
    candles = [make_candle(index, str(57000 + index)) for index in range(20)]
    indicators = [make_indicator(candle, float(index)) for index, candle in enumerate(candles)]
    payload = recent_bar_payload(candles, indicators, 3)
    assert len(payload) == 3
    assert [item["close"] for item in payload] == ["57017", "57018", "57019"]
    assert [item["rsi14"] for item in payload] == [17.0, 18.0, 19.0]
    assert payload[-1]["trend"] == "UP"
    assert payload[-1]["ema20"] == "58100"


def test_recent_bar_payload_zero_limit() -> None:
    assert recent_bar_payload([make_candle(0)], [], 0) == []
