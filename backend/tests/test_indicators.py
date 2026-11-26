from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.infrastructure.market.base import Candle
from app.infrastructure.market.indicators import (
    build_indicator_snapshot,
    build_rsi_history,
    ema,
    macd,
    rsi,
    volatility,
)


def make_candles(closes: list[float]) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Candle(
            open_time=start + timedelta(hours=index),
            open=Decimal(str(value)),
            high=Decimal(str(value + 1)),
            low=Decimal(str(value - 1)),
            close=Decimal(str(value)),
            volume=Decimal("10"),
            confirmed=True,
        )
        for index, value in enumerate(closes)
    ]


def test_ema() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = ema(values, 3)
    assert result[:2] == [None, None]
    assert result[2] == 2.0
    assert result[3] == 3.0
    assert result[4] == 4.0


def test_rsi_monotonic() -> None:
    values = [float(index) for index in range(1, 30)]
    result = rsi(values, 14)
    assert result[14] == 100.0
    assert result[-1] == 100.0


def test_macd_alignment() -> None:
    values = [float(index) for index in range(1, 60)]
    line, signal, histogram = macd(values)
    assert len(line) == len(values)
    assert len(signal) == len(values)
    assert len(histogram) == len(values)
    assert line[-1] is not None
    assert signal[-1] is not None
    assert histogram[-1] == line[-1] - signal[-1]


def test_volatility_non_negative() -> None:
    values = [100.0 + (index % 3) for index in range(40)]
    result = volatility(values, 20)
    assert result[-1] is not None
    assert result[-1] >= 0


def test_snapshot_trend_up() -> None:
    candles = make_candles([100.0 + index * 0.5 for index in range(80)])
    snapshot = build_indicator_snapshot(candles)
    assert snapshot["status"] == "OK"
    assert snapshot["trend"] == "UP"
    assert snapshot["rsi14"] == 100.0
    assert snapshot["bars"] == 80


def test_snapshot_insufficient() -> None:
    snapshot = build_indicator_snapshot(make_candles([100.0, 101.0]))
    assert snapshot["status"] == "INSUFFICIENT"

def test_build_rsi_history_is_aligned_and_limited() -> None:
    candles = make_candles([float(index) for index in range(1, 40)])
    history = build_rsi_history(candles, 3)
    assert len(history) == 3
    assert [item["open_time"] for item in history] == [
        candles[-3].open_time.isoformat(),
        candles[-2].open_time.isoformat(),
        candles[-1].open_time.isoformat(),
    ]
    assert history[-1]["rsi14"] == 100.0


def test_build_rsi_history_zero_limit() -> None:
    assert build_rsi_history(make_candles([100.0, 101.0]), 0) == []
