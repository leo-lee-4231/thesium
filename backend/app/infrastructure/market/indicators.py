import math
import statistics
from collections.abc import Sequence

from app.infrastructure.market.base import Candle


def ema(values: Sequence[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return result
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    multiplier = 2 / (period + 1)
    for index in range(period, len(values)):
        previous = result[index - 1]
        assert previous is not None
        result[index] = values[index] * multiplier + previous * (1 - multiplier)
    return result


def rsi(values: Sequence[float], period: int = 14) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result

    gains = [max(values[i] - values[i - 1], 0.0) for i in range(1, len(values))]
    losses = [max(values[i - 1] - values[i], 0.0) for i in range(1, len(values))]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def value(gain: float, loss: float) -> float:
        if loss == 0:
            return 100.0
        return 100.0 - 100.0 / (1.0 + gain / loss)

    result[period] = value(avg_gain, avg_loss)
    for index in range(period + 1, len(values)):
        avg_gain = (avg_gain * (period - 1) + gains[index - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[index - 1]) / period
        result[index] = value(avg_gain, avg_loss)
    return result


def macd(
    values: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    fast_ema = ema(values, fast)
    slow_ema = ema(values, slow)
    macd_line: list[float | None] = [None] * len(values)
    for index in range(len(values)):
        if fast_ema[index] is not None and slow_ema[index] is not None:
            macd_line[index] = fast_ema[index] - slow_ema[index]  # type: ignore[operator]

    valid = [value for value in macd_line if value is not None]
    signal_values = ema(valid, signal)
    signal_line: list[float | None] = [None] * len(values)
    valid_index = 0
    for index, value in enumerate(macd_line):
        if value is None:
            continue
        signal_line[index] = signal_values[valid_index]
        valid_index += 1

    histogram: list[float | None] = [None] * len(values)
    for index in range(len(values)):
        if macd_line[index] is not None and signal_line[index] is not None:
            histogram[index] = macd_line[index] - signal_line[index]  # type: ignore[operator]
    return macd_line, signal_line, histogram


def volatility(values: Sequence[float], period: int = 20) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result
    returns = [0.0] * (len(values) - 1)
    for index in range(1, len(values)):
        if values[index - 1] <= 0 or values[index] <= 0:
            returns[index - 1] = 0.0
        else:
            returns[index - 1] = math.log(values[index] / values[index - 1])
    for index in range(period, len(returns) + 1):
        window = returns[index - period : index]
        result[index] = statistics.pstdev(window) * 100
    return result


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def build_rsi_history(
    candles: Sequence[Candle], limit: int = 24
) -> list[dict[str, object]]:
    """Serialize the recent RSI path, aligned by candle open_time."""
    if limit <= 0 or not candles:
        return []
    closes = [float(candle.close) for candle in candles]
    values = rsi(closes, 14)
    return [
        {
            "open_time": candle.open_time.isoformat(),
            "rsi14": _round(value),
        }
        for candle, value in zip(candles[-limit:], values[-limit:], strict=True)
    ]


def build_indicator_snapshot(candles: Sequence[Candle]) -> dict[str, object]:
    bars = len(candles)
    if bars < 20:
        return {
            "status": "INSUFFICIENT",
            "bars": bars,
            "as_of": candles[-1].open_time.isoformat() if candles else None,
            "warnings": ["K 线不足 20 根，无法计算稳定指标"],
        }

    closes = [float(candle.close) for candle in candles]
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    rsi14 = rsi(closes, 14)
    macd_line, signal_line, histogram = macd(closes)
    vol20 = volatility(closes, 20)

    last_ema20 = ema20[-1]
    last_ema50 = ema50[-1]
    close = closes[-1]
    trend = "UNKNOWN"
    if last_ema20 is not None and last_ema50 is not None:
        if close > last_ema20 > last_ema50:
            trend = "UP"
        elif close < last_ema20 < last_ema50:
            trend = "DOWN"
        else:
            trend = "SIDEWAYS"

    warnings: list[str] = []
    if bars < 50:
        warnings.append("K 线不足 50 根，EMA50/趋势仅供参考")

    return {
        "status": "OK",
        "bars": bars,
        "as_of": candles[-1].open_time.isoformat(),
        "close": _round(close),
        "ema20": _round(last_ema20),
        "ema50": _round(last_ema50),
        "rsi14": _round(rsi14[-1]),
        "macd": _round(macd_line[-1]),
        "macd_signal": _round(signal_line[-1]),
        "macd_hist": _round(histogram[-1]),
        "volatility_pct": _round(vol20[-1]),
        "trend": trend,
        "warnings": warnings,
    }