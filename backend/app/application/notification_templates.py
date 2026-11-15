from __future__ import annotations

import html
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import get_settings
from app.db.models import Asset, InvestmentDecision, InvestmentStream

DECISION_LABELS = {
    "BUY": "建议买入 / 建仓",
    "SELL": "建议卖出 / 退出",
    "REDUCE": "建议降低仓位",
    "HOLD": "维持当前仓位",
    "WAIT": "暂不行动",
    "REVIEW": "需要重新审视计划",
}


def _local_time(value: datetime | None, timezone: str) -> str:
    if value is None:
        return "—"
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("Asia/Shanghai")
    return value.astimezone(zone).strftime("%Y-%m-%d %H:%M")


def _fmt_confidence(value: object) -> str:
    try:
        return f"{float(str(value)):.2f}"
    except (TypeError, ValueError):
        return "—"


def _evidence_lines(items: list) -> list[str]:
    lines: list[str] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim") or "").strip()
        if not claim:
            continue
        as_of = item.get("as_of")
        suffix = f"（{as_of}）" if as_of else ""
        lines.append(f"- {claim}{suffix}")
    return lines


def _impact_line(decision: InvestmentDecision) -> str:
    impact = decision.position_impact or {}
    assessment = impact.get("assessment") or "UNKNOWN"
    parts = [f"仓位评估：{assessment}"]
    if impact.get("exposure_usd") is not None:
        parts.append(f"敞口 {impact['exposure_usd']} USD")
    if impact.get("unrealized_pnl_usd") is not None:
        parts.append(f"浮盈亏 {impact['unrealized_pnl_usd']} USD")
    if impact.get("risk_budget_usage_pct") is not None:
        parts.append(f"风险预算占用 {impact['risk_budget_usage_pct']}%")
    if impact.get("notes"):
        parts.append(str(impact["notes"]))
    return "；".join(parts)


def _derivative_lines(decision: InvestmentDecision) -> list[str]:
    recommendation = decision.derivative_recommendation or {}
    action = recommendation.get("action")
    if not action or action == "NONE":
        return []
    lines = [f"合约建议：{action}"]
    if recommendation.get("size_change_pct") is not None:
        lines.append(f"调整比例：{recommendation['size_change_pct']}%")
    if recommendation.get("rationale"):
        lines.append(f"理由：{recommendation['rationale']}")
    stop = recommendation.get("stop_loss") or {}
    if stop.get("price"):
        lines.append(
            "止损：{price}（{source}；风险 {risk} USD / {pct}% 权益）".format(
                price=stop.get("price"),
                source=stop.get("source", "—"),
                risk=stop.get("risk_amount_usd", "—"),
                pct=stop.get("risk_pct_equity", "—"),
            )
        )
        for warning in stop.get("warnings") or []:
            lines.append(f"止损提醒：{warning}")
    return lines


def _invalidation_lines(decision: InvestmentDecision) -> list[str]:
    lines: list[str] = []
    for item in decision.invalidation_conditions or []:
        if isinstance(item, dict):
            condition = item.get("condition") or item.get("threshold")
        else:
            condition = item
        if condition:
            lines.append(f"- {condition}")
    return lines


def build_notification(
    *,
    stream: InvestmentStream,
    asset: Asset,
    decision: InvestmentDecision,
    priority: str,
    triggered_rules: list[str],
) -> tuple[str, str, str]:
    settings = get_settings()
    time_label = _local_time(decision.created_at, stream.timezone)
    label = DECISION_LABELS.get(decision.decision, decision.decision)
    title = f"[Thesium] {asset.symbol} · {priority} · {label}（{time_label}）"
    quality = decision.data_quality or {}
    alignment = decision.thesis_alignment or {}

    text_lines = [
        f"{label}：{decision.summary}",
        "",
        f"Decision：{decision.decision} · 优先级 {priority} · 置信度 "
        f"{_fmt_confidence(decision.confidence)}（模型自评，非胜率）",
        f"与 Thesis 的关系：{alignment.get('status', 'UNKNOWN')}",
    ]
    if alignment.get("explanation"):
        text_lines.append(str(alignment["explanation"]))
    text_lines.extend(["", "支持证据：", *(_evidence_lines(decision.evidence_for) or ["- 无"]),
                       "", "反面证据：", *(_evidence_lines(decision.evidence_against) or ["- 无"]),
                       "", _impact_line(decision)])
    derivative = _derivative_lines(decision)
    if derivative:
        text_lines.extend(["", *derivative])
    invalidations = _invalidation_lines(decision)
    if invalidations:
        text_lines.extend(["", "失效条件：", *invalidations])
    text_lines.extend(
        [
            "",
            f"数据质量：{quality.get('status', 'UNKNOWN')} / {quality.get('staleness', 'UNKNOWN')}"
            f" · 数据时间 {quality.get('as_of') or time_label}",
            f"通知规则：{', '.join(triggered_rules) or '—'}",
            f"查看详情：{settings.web_base_url.rstrip('/')}/products/{asset.symbol.lower()}",
            "",
            "仅供个人参考，不构成投资建议；Thesium 不执行任何交易。",
        ]
    )
    text = "\n".join(text_lines)

    def esc(value: object) -> str:
        return html.escape(str(value)) if value is not None else "—"

    evidence_html = "".join(
        f"<li>{esc(line[2:])}</li>"
        for line in (_evidence_lines(decision.evidence_for) or ["- 无"])
    )
    against_html = "".join(
        f"<li>{esc(line[2:])}</li>"
        for line in (_evidence_lines(decision.evidence_against) or ["- 无"])
    )
    derivative_html = "".join(f"<li>{esc(line)}</li>" for line in derivative)
    invalidation_html = "".join(f"<li>{esc(line[2:])}</li>" for line in invalidations)
    detail_url = settings.web_base_url.rstrip("/") + "/products/" + asset.symbol.lower()
    body_html = f"""<!doctype html>
<html lang="zh-CN"><body style="font-family:system-ui,sans-serif;line-height:1.7;color:#1f2937">
<h2 style="margin:0 0 8px">{esc(label)}</h2>
<p style="font-size:16px">{esc(decision.summary)}</p>
<p style="color:#6b7280">Decision：{esc(decision.decision)} · 优先级 {esc(priority)} ·
置信度 {esc(_fmt_confidence(decision.confidence))}（模型自评，非胜率）</p>
<h3>Thesis 关系：{esc(alignment.get('status', 'UNKNOWN'))}</h3>
<p>{esc(alignment.get('explanation', ''))}</p>
<h3>支持证据</h3><ul>{evidence_html}</ul>
<h3>反面证据</h3><ul>{against_html}</ul>
<h3>持仓影响</h3><p>{esc(_impact_line(decision))}</p>
{('<h3>合约建议</h3><ul>' + derivative_html + '</ul>') if derivative else ''}
{('<h3>失效条件</h3><ul>' + invalidation_html + '</ul>') if invalidations else ''}
<p style="color:#6b7280">数据质量：{esc(quality.get('status', 'UNKNOWN'))} /
{esc(quality.get('staleness', 'UNKNOWN'))} · 数据时间 {esc(quality.get('as_of') or time_label)}</p>
<p><a href="{esc(detail_url)}">查看详情</a></p>
<p style="color:#9ca3af;font-size:12px">仅供个人参考，不构成投资建议；Thesium 不执行任何交易。</p>
</body></html>"""
    return title, text, body_html