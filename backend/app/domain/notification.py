"""Deterministic notification policy.

The model may *suggest* a notification; this module decides. Rules are pure
functions so they can be tested without a database or a clock.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MATERIAL_DECISIONS = {"BUY", "SELL", "REDUCE", "REVIEW"}
QUIET_BYPASS_PRIORITIES = {"URGENT"}
HIGH_PRIORITIES = {"HIGH", "URGENT"}


@dataclass(frozen=True)
class DecisionFacts:
    decision: str
    priority: str
    alignment: str
    data_quality: str
    position_assessment: str
    derivative_action: str | None = None
    invalidation_thresholds: tuple[str, ...] = ()
    triggered_invalidations: tuple[str, ...] = ()


@dataclass(frozen=True)
class Preferences:
    decision_alert_enabled: bool = True
    risk_alert_enabled: bool = True
    email_enabled: bool = True
    quiet_hours_enabled: bool = True
    quiet_hours_start: str = "23:00"
    quiet_hours_end: str = "08:00"
    daily_email_limit: int = 4
    cooldown_minutes: int = 240


@dataclass(frozen=True)
class NotificationHistoryItem:
    dedupe_key: str
    decision: str
    alignment: str
    priority: str
    created_at: datetime


@dataclass(frozen=True)
class PolicyResult:
    notify: bool
    reason: str
    priority: str
    dedupe_key: str
    triggered_rules: list[str] = field(default_factory=list)
    override_reasons: list[str] = field(default_factory=list)

    @property
    def channels(self) -> list[str]:
        return ["EMAIL"] if self.notify else []


def _parse_hhmm(value: str) -> time:
    try:
        hour, minute = value.split(":", 1)
        parsed = time(int(hour), int(minute))
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"invalid quiet-hours value: {value!r}") from exc
    if not 0 <= parsed.hour <= 23 or not 0 <= parsed.minute <= 59:
        raise ValueError(f"invalid quiet-hours value: {value!r}")
    return parsed


def quiet_hours_active(
    now: datetime,
    *,
    start: str = "23:00",
    end: str = "08:00",
    timezone: str = "Asia/Shanghai",
) -> bool:
    """Return True if ``now`` falls inside the user's quiet window.

    Handles overnight windows such as 23:00–08:00. A start equal to end is
    treated as *no quiet window* so users can disable it by making both equal.
    """

    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("Asia/Shanghai")
    local = now.astimezone(zone)
    start_time = _parse_hhmm(start)
    end_time = _parse_hhmm(end)
    if start_time == end_time:
        return False
    current = local.time().replace(tzinfo=None)
    if start_time < end_time:
        return start_time <= current < end_time
    return current >= start_time or current < end_time


def effective_priority(facts: DecisionFacts) -> tuple[str, list[str]]:
    reasons: list[str] = []
    priority = facts.priority
    action = facts.derivative_action
    if action and action not in {"NONE", "HOLD"}:
        reasons.append("合约动作非 HOLD/NONE，提升为 HIGH")
        priority = "HIGH" if priority not in HIGH_PRIORITIES else priority
    if facts.position_assessment == "RISK_BUDGET_EXCEEDED":
        reasons.append("风险预算被突破，提升为 HIGH")
        priority = "HIGH" if priority not in HIGH_PRIORITIES else priority
    if facts.triggered_invalidations and priority != "URGENT":
        reasons.append("失效条件触发，提升为 HIGH")
        priority = "HIGH"
    return priority, reasons


def dedupe_key(
    *,
    stream_id: object,
    facts: DecisionFacts,
    priority: str,
) -> str:
    thresholds = ",".join(sorted(facts.invalidation_thresholds))
    raw = "|".join(
        [
            str(stream_id),
            facts.decision,
            priority,
            facts.alignment,
            thresholds,
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def evaluate(
    *,
    stream_id: object,
    facts: DecisionFacts,
    previous_decision: DecisionFacts | None,
    preferences: Preferences,
    recent: list[NotificationHistoryItem],
    emails_sent_today: int,
    now: datetime,
    timezone: str = "Asia/Shanghai",
) -> PolicyResult:
    """Apply N1–N5 triggers and S1–S6 suppressions in a deterministic order."""

    priority, override_reasons = effective_priority(facts)
    key = dedupe_key(stream_id=stream_id, facts=facts, priority=priority)

    if not preferences.decision_alert_enabled:
        return PolicyResult(False, "通知已关闭（decision_alert_enabled=false）", priority, key)

    if facts.data_quality == "INSUFFICIENT":
        return PolicyResult(False, "数据不足（INSUFFICIENT），不打扰", priority, key)

    triggers: list[str] = []
    if priority in HIGH_PRIORITIES:
        triggers.append("N1")
    if (
        previous_decision is not None
        and previous_decision.decision != facts.decision
        and (
            facts.decision in MATERIAL_DECISIONS
            or previous_decision.decision in MATERIAL_DECISIONS
        )
    ):
        triggers.append("N2")
    if (
        previous_decision is not None
        and previous_decision.alignment != "CONFLICTING"
        and facts.alignment == "CONFLICTING"
    ):
        triggers.append("N3")
    if facts.triggered_invalidations:
        triggers.append("N4")
    if facts.position_assessment == "RISK_BUDGET_EXCEEDED":
        triggers.append("N5")

    if not triggers:
        return PolicyResult(
            False,
            "与上一条相比没有需要打扰的变化",
            priority,
            key,
            override_reasons=override_reasons,
        )

    risk_only = (
        facts.position_assessment == "RISK_BUDGET_EXCEEDED"
        and not (set(triggers) & {"N2", "N3"})
    )
    if risk_only and not preferences.risk_alert_enabled:
        return PolicyResult(
            False,
            "风险类通知已关闭（risk_alert_enabled=false）",
            priority,
            key,
            triggered_rules=triggers,
            override_reasons=override_reasons,
        )

    cooldown = timedelta(minutes=max(0, preferences.cooldown_minutes))
    cutoff = now - cooldown
    if any(item.dedupe_key == key and item.created_at >= cutoff for item in recent):
        return PolicyResult(
            False,
            f"{preferences.cooldown_minutes} 分钟内已发送相同通知（冷却中）",
            priority,
            key,
            triggered_rules=triggers,
            override_reasons=override_reasons,
        )

    if recent:
        latest = max(recent, key=lambda item: item.created_at)
        if (
            latest.decision == facts.decision
            and latest.alignment == facts.alignment
            and latest.priority == priority
        ):
            return PolicyResult(
                False,
                "与上一条通知的 decision/alignment/priority 完全相同",
                priority,
                key,
                triggered_rules=triggers,
                override_reasons=override_reasons,
            )

    if (
        preferences.quiet_hours_enabled
        and priority not in QUIET_BYPASS_PRIORITIES
        and quiet_hours_active(
            now,
            start=preferences.quiet_hours_start,
            end=preferences.quiet_hours_end,
            timezone=timezone,
        )
    ):
        return PolicyResult(
            False,
            "处于免打扰时段，且不是 URGENT",
            priority,
            key,
            triggered_rules=triggers,
            override_reasons=override_reasons,
        )

    if (
        preferences.email_enabled
        and priority not in QUIET_BYPASS_PRIORITIES
        and emails_sent_today >= preferences.daily_email_limit
    ):
        return PolicyResult(
            False,
            f"今日邮件已达上限（{preferences.daily_email_limit} 封）",
            priority,
            key,
            triggered_rules=triggers,
            override_reasons=override_reasons,
        )

    return PolicyResult(
        True,
        "触发通知条件：" + ", ".join(triggers),
        priority,
        key,
        triggered_rules=triggers,
        override_reasons=override_reasons,
    )


def status_for_deliveries(statuses: list[Literal["PENDING", "SENT", "FAILED", "SKIPPED"]]) -> str:
    if not statuses:
        return "SKIPPED"
    if any(status == "PENDING" for status in statuses):
        return "PENDING"
    if any(status == "SENT" for status in statuses):
        return "SENT"
    if all(status == "SKIPPED" for status in statuses):
        return "SKIPPED"
    return "FAILED"