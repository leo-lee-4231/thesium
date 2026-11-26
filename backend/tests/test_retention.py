from datetime import UTC, date, datetime

from app.application.retention_service import retention_cutoffs
from app.core.config import Settings
from app.workers.scheduler import _market_retention_slot


def test_retention_cutoffs_use_configured_days() -> None:
    now = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
    settings = Settings(
        market_candle_retention_days_1h=10,
        market_candle_retention_days_4h=20,
        market_candle_retention_days_1d=30,
    )
    cutoffs = retention_cutoffs(now, settings)
    assert cutoffs["1h"] == datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
    assert cutoffs["4h"] == datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
    assert cutoffs["1d"] == datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


def test_retention_slot_waits_until_0315_utc() -> None:
    assert _market_retention_slot(datetime(2026, 11, 26, 3, 14, tzinfo=UTC)) is None
    assert _market_retention_slot(datetime(2026, 11, 26, 3, 15, tzinfo=UTC)) == date(2026, 11, 26)
    assert _market_retention_slot(datetime(2026, 11, 26, 9, 0, tzinfo=UTC)) == date(2026, 11, 26)
