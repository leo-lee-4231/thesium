from datetime import UTC, datetime

from app.db.models import InvestmentStream, NotificationPreference
from app.workers.scheduler import _daily_digest_slot


def stream() -> InvestmentStream:
    return InvestmentStream(
        name="BTC",
        timezone="Asia/Shanghai",
        monitor_interval_minutes=60,
        agent_enabled=True,
        created_at=datetime(2026, 11, 15, 0, 0, tzinfo=UTC),
    )


def prefs(**overrides: object) -> NotificationPreference:
    values: dict[str, object] = {
        "daily_summary_enabled": True,
        "daily_summary_time": "08:00",
        "news_enabled": True,
    }
    values.update(overrides)
    return NotificationPreference(**values)  # type: ignore[arg-type]


def test_digest_due_after_8am() -> None:
    slot = _daily_digest_slot(stream(), prefs(), datetime(2026, 11, 15, 0, 1, tzinfo=UTC))
    assert slot is not None
    assert slot[0].isoformat() == "2026-11-15"


def test_digest_not_due_before_8am() -> None:
    assert _daily_digest_slot(stream(), prefs(), datetime(2026, 11, 14, 23, 59, tzinfo=UTC)) is None


def test_digest_not_sent_late_at_night() -> None:
    assert _daily_digest_slot(stream(), prefs(), datetime(2026, 11, 15, 6, 0, tzinfo=UTC)) is None


def test_digest_disabled() -> None:
    now = datetime(2026, 11, 15, 0, 1, tzinfo=UTC)
    assert _daily_digest_slot(
        stream(), prefs(daily_summary_enabled=False), now
    ) is None
