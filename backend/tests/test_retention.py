from datetime import UTC, date, datetime

import pytest

from app.application.market_retention_settings_service import (
    DEFAULT_RETENTION_POLICY,
    RetentionPolicy,
    RetentionSettingsError,
    validate_policy,
)
from app.application.retention_service import retention_cutoffs
from app.workers.scheduler import _market_retention_slot


def test_retention_cutoffs_use_configured_days() -> None:
    now = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
    policy = RetentionPolicy(
        enabled=True,
        candle_1h_days=10,
        candle_4h_days=20,
        candle_1d_days=30,
        snapshot_days=90,
    )
    cutoffs = retention_cutoffs(now, policy)
    assert cutoffs["1h"] == datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
    assert cutoffs["4h"] == datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
    assert cutoffs["1d"] == datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


def test_retention_slot_waits_until_0315_utc() -> None:
    assert _market_retention_slot(datetime(2026, 11, 26, 3, 14, tzinfo=UTC)) is None
    assert _market_retention_slot(datetime(2026, 11, 26, 3, 15, tzinfo=UTC)) == date(2026, 11, 26)
    assert _market_retention_slot(datetime(2026, 11, 26, 9, 0, tzinfo=UTC)) == date(2026, 11, 26)


def test_retention_policy_rejects_non_monotonic_windows() -> None:
    with pytest.raises(RetentionSettingsError):
        validate_policy(
            RetentionPolicy(
                enabled=True,
                candle_1h_days=400,
                candle_4h_days=300,
                candle_1d_days=500,
                snapshot_days=90,
            )
        )


def test_retention_policy_rejects_invalid_snapshot_window() -> None:
    with pytest.raises(RetentionSettingsError):
        validate_policy(
            RetentionPolicy(
                enabled=True,
                candle_1h_days=30,
                candle_4h_days=60,
                candle_1d_days=90,
                snapshot_days=0,
            )
        )


def test_retention_defaults_are_built_in() -> None:
    assert DEFAULT_RETENTION_POLICY.enabled is True
    assert DEFAULT_RETENTION_POLICY.candle_1h_days == 365
    assert DEFAULT_RETENTION_POLICY.candle_4h_days == 730
    assert DEFAULT_RETENTION_POLICY.candle_1d_days == 1825
    assert DEFAULT_RETENTION_POLICY.snapshot_days == 90
