from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.agent.context import candle_dict, recent_candle_payload
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


def test_candle_dict_serializes_ohlc() -> None:
    payload = candle_dict(make_candle(0))
    assert payload["open_time"] == "2026-11-01T00:00:00+00:00"
    assert payload["open"] == "58000"
    assert payload["high"] == "59000"
    assert payload["low"] == "57000"
    assert payload["close"] == "58000"
    assert payload["volume"] == "12.5"
    assert payload["confirmed"] is True


def test_recent_candle_payload_keeps_latest_bars() -> None:
    candles = [make_candle(index, str(57000 + index)) for index in range(20)]
    payload = recent_candle_payload(candles, 3)
    assert len(payload) == 3
    assert [item["close"] for item in payload] == ["57017", "57018", "57019"]


def test_recent_candle_payload_zero_limit() -> None:
    assert recent_candle_payload([make_candle(0)], 0) == []
