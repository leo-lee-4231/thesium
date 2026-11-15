from datetime import UTC, datetime

from app.domain.notification import (
    DecisionFacts,
    NotificationHistoryItem,
    Preferences,
    dedupe_key,
    evaluate,
    quiet_hours_active,
)


def facts(**overrides: object) -> DecisionFacts:
    values: dict[str, object] = {
        "decision": "WAIT",
        "priority": "NORMAL",
        "alignment": "ALIGNED",
        "data_quality": "GOOD",
        "position_assessment": "NO_POSITION",
    }
    values.update(overrides)
    return DecisionFacts(**values)  # type: ignore[arg-type]


def evaluate_facts(
    current: DecisionFacts,
    *,
    previous: DecisionFacts | None = None,
    prefs: Preferences | None = None,
    recent: list[NotificationHistoryItem] | None = None,
    emails: int = 0,
    now: datetime | None = None,
):
    return evaluate(
        stream_id="stream-1",
        facts=current,
        previous_decision=previous,
        preferences=prefs or Preferences(),
        recent=recent or [],
        emails_sent_today=emails,
        now=now or datetime(2026, 11, 15, 12, 0, tzinfo=UTC),
        timezone="Asia/Shanghai",
    )


def test_ordinary_wait_does_not_notify() -> None:
    result = evaluate_facts(facts())
    assert result.notify is False
    assert "没有需要打扰的变化" in result.reason


def test_category_jump_to_sell_notifies() -> None:
    result = evaluate_facts(
        facts(decision="SELL", priority="HIGH", alignment="PARTIALLY_ALIGNED"),
        previous=facts(decision="HOLD", priority="NORMAL"),
    )
    assert result.notify is True
    assert "N1" in result.triggered_rules
    assert "N2" in result.triggered_rules


def test_thesis_conflict_transition_notifies() -> None:
    result = evaluate_facts(
        facts(decision="REVIEW", priority="NORMAL", alignment="CONFLICTING"),
        previous=facts(decision="HOLD", priority="NORMAL", alignment="ALIGNED"),
    )
    assert result.notify is True
    assert "N3" in result.triggered_rules


def test_quiet_hours_suppresses_high_but_urgent_bypasses() -> None:
    late = datetime(2026, 11, 15, 15, 30, tzinfo=UTC)  # 23:30 Asia/Shanghai
    high = facts(decision="SELL", priority="HIGH")
    suppressed = evaluate_facts(high, previous=facts(decision="HOLD"), now=late)
    assert suppressed.notify is False
    assert "免打扰" in suppressed.reason

    urgent = evaluate_facts(
        facts(decision="SELL", priority="URGENT"),
        previous=facts(decision="HOLD"),
        now=late,
    )
    assert urgent.notify is True


def test_same_dedupe_key_is_cooled_down() -> None:
    current = facts(decision="SELL", priority="HIGH")
    key = dedupe_key(stream_id="stream-1", facts=current, priority="HIGH")
    recent = [
        NotificationHistoryItem(
            dedupe_key=key,
            decision="SELL",
            alignment="ALIGNED",
            priority="HIGH",
            created_at=datetime(2026, 11, 15, 11, 55, tzinfo=UTC),
        )
    ]
    result = evaluate_facts(
        current,
        previous=facts(decision="HOLD"),
        recent=recent,
        now=datetime(2026, 11, 15, 12, 0, tzinfo=UTC),
    )
    assert result.notify is False
    assert "冷却" in result.reason


def test_identical_notification_is_suppressed() -> None:
    current = facts(decision="SELL", priority="HIGH")
    recent = [
        NotificationHistoryItem(
            dedupe_key="different",
            decision="SELL",
            alignment="ALIGNED",
            priority="HIGH",
            created_at=datetime(2026, 11, 14, 12, 0, tzinfo=UTC),
        )
    ]
    result = evaluate_facts(current, previous=facts(decision="HOLD"), recent=recent)
    assert result.notify is False
    assert "完全相同" in result.reason


def test_daily_email_cap_suppresses_non_urgent() -> None:
    current = facts(decision="SELL", priority="HIGH")
    result = evaluate_facts(current, previous=facts(decision="HOLD"), emails=4)
    assert result.notify is False
    assert "上限" in result.reason


def test_disabled_decision_alerts_suppress_everything() -> None:
    result = evaluate_facts(
        facts(decision="SELL", priority="HIGH"),
        previous=facts(decision="HOLD"),
        prefs=Preferences(decision_alert_enabled=False, quiet_hours_enabled=False),
    )
    assert result.notify is False
    assert "decision_alert_enabled" in result.reason


def test_risk_budget_break_raises_priority() -> None:
    result = evaluate_facts(
        facts(decision="REDUCE", priority="NORMAL", position_assessment="RISK_BUDGET_EXCEEDED")
    )
    assert result.priority == "HIGH"
    assert result.notify is True


def test_risk_alert_can_be_disabled() -> None:
    result = evaluate_facts(
        facts(decision="REDUCE", priority="NORMAL", position_assessment="RISK_BUDGET_EXCEEDED"),
        prefs=Preferences(risk_alert_enabled=False, quiet_hours_enabled=False),
    )
    assert result.notify is False
    assert "risk_alert_enabled" in result.reason


def test_derivative_action_raises_priority() -> None:
    result = evaluate_facts(
        facts(decision="HOLD", priority="NORMAL", derivative_action="REDUCE_LONG")
    )
    assert result.priority == "HIGH"
    assert result.notify is True


def test_quiet_hours_window() -> None:
    assert quiet_hours_active(
        datetime(2026, 11, 15, 15, 30, tzinfo=UTC),
        start="23:00",
        end="08:00",
        timezone="Asia/Shanghai",
    )
    assert not quiet_hours_active(
        datetime(2026, 11, 15, 4, 0, tzinfo=UTC),
        start="23:00",
        end="08:00",
        timezone="Asia/Shanghai",
    )
    assert not quiet_hours_active(
        datetime(2026, 11, 15, 15, 30, tzinfo=UTC),
        start="09:00",
        end="09:00",
        timezone="Asia/Shanghai",
    )


def test_dedupe_key_stable_and_threshold_sensitive() -> None:
    first = dedupe_key(stream_id="s", facts=facts(decision="SELL"), priority="HIGH")
    second = dedupe_key(stream_id="s", facts=facts(decision="SELL"), priority="HIGH")
    third = dedupe_key(
        stream_id="s",
        facts=facts(decision="SELL", invalidation_thresholds=("95000",)),
        priority="HIGH",
    )
    assert first == second
    assert first != third
