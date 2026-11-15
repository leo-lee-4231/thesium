from app.domain.decision import DecisionOutput, validate_decision


def base_output(**overrides):  # type: ignore[no-untyped-def]
    values = {
        "decision": "WAIT",
        "confidence": 0.6,
        "priority": "NORMAL",
        "summary": "短期动能偏弱，等待确认。",
        "thesis_alignment": {"status": "UNKNOWN", "explanation": "no thesis"},
        "data_quality": {"status": "GOOD", "staleness": "FRESH"},
    }
    values.update(overrides)
    return DecisionOutput.model_validate(values)


def test_no_thesis_requires_wait_or_review() -> None:
    output = base_output(decision="BUY")
    errors = validate_decision(
        output, has_thesis=False, has_derivative=False, derivative_side=None, allow_short=None
    )
    assert any("WAIT" in error for error in errors)


def test_insufficient_data_cannot_notify() -> None:
    output = base_output(
        decision="WAIT",
        confidence=0.8,
        data_quality={"status": "INSUFFICIENT", "staleness": "STALE"},
        notification_recommendation={"notify": True},
    )
    errors = validate_decision(
        output, has_thesis=True, has_derivative=False, derivative_side=None, allow_short=None
    )
    assert any("confidence" in error for error in errors)
    assert any("notify" in error for error in errors)


def test_derivative_action_must_match_side() -> None:
    output = base_output(
        decision="HOLD",
        thesis_alignment={"status": "ALIGNED"},
        derivative_recommendation={
            "action": "OPEN_SHORT",
            "stop_loss": {"price": "95000", "source": "USER"},
        },
    )
    errors = validate_decision(
        output, has_thesis=True, has_derivative=True, derivative_side="LONG", allow_short=True
    )
    assert any("match LONG" in error for error in errors)


def test_open_requires_stop_loss() -> None:
    output = base_output(
        decision="BUY",
        thesis_alignment={"status": "ALIGNED"},
        derivative_recommendation={"action": "OPEN_LONG"},
    )
    errors = validate_decision(
        output, has_thesis=True, has_derivative=False, derivative_side=None, allow_short=False
    )
    assert any("stop_loss" in error for error in errors)

def test_open_short_requires_stop_loss() -> None:
    output = base_output(
        decision="SELL",
        thesis_alignment={"status": "ALIGNED"},
        derivative_recommendation={"action": "OPEN_SHORT"},
    )
    errors = validate_decision(
        output, has_thesis=True, has_derivative=False, derivative_side=None, allow_short=True
    )
    assert any("OPEN_SHORT" in error for error in errors)


def test_open_short_requires_permission() -> None:
    output = base_output(
        decision="SELL",
        thesis_alignment={"status": "ALIGNED"},
        derivative_recommendation={
            "action": "OPEN_SHORT",
            "stop_loss": {"price": "95000", "source": "USER"},
        },
    )
    errors = validate_decision(
        output, has_thesis=True, has_derivative=False, derivative_side=None, allow_short=False
    )
    assert any("allow_short" in error for error in errors)


def test_open_short_with_stop_and_permission_is_valid() -> None:
    output = base_output(
        decision="SELL",
        thesis_alignment={"status": "ALIGNED"},
        derivative_recommendation={
            "action": "OPEN_SHORT",
            "stop_loss": {"price": "95000", "source": "USER"},
        },
    )
    errors = validate_decision(
        output, has_thesis=True, has_derivative=False, derivative_side=None, allow_short=True
    )
    assert errors == []
