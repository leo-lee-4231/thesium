from datetime import UTC, datetime, timedelta

from app.db.models import InvestmentStream
from app.workers.scheduler import monitor_due_at


def stream(**overrides: object) -> InvestmentStream:
    values: dict[str, object] = {
        "name": "BTC",
        "timezone": "Asia/Shanghai",
        "monitor_interval_minutes": 60,
        "created_at": datetime(2026, 11, 15, 0, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return InvestmentStream(**values)  # type: ignore[arg-type]


def test_first_monitor_is_due_after_create() -> None:
    item = stream()
    assert monitor_due_at(item) == datetime(2026, 11, 15, 1, 0, tzinfo=UTC)


def test_uses_last_monitored_at() -> None:
    item = stream(last_monitored_at=datetime(2026, 11, 15, 10, 0, tzinfo=UTC))
    assert monitor_due_at(item) == datetime(2026, 11, 15, 11, 0, tzinfo=UTC)


def test_interval_floor_is_fifteen_minutes() -> None:
    item = stream(monitor_interval_minutes=1)
    due = monitor_due_at(item)
    assert due is not None
    assert due - item.created_at == timedelta(minutes=15)
