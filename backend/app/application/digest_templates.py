from __future__ import annotations

import html
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import get_settings
from app.db.models import Asset, InvestmentStream

DECISION_LABELS = {
    "BUY": "建议买入 / 建仓",
    "SELL": "建议卖出 / 退出",
    "REDUCE": "建议降低仓位",
    "HOLD": "维持当前仓位",
    "WAIT": "暂不行动",
    "REVIEW": "需要重新审视计划",
}


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def _local(value: datetime | None, timezone: str) -> str:
    if value is None:
        return "—"
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("Asia/Shanghai")
    return value.astimezone(zone).strftime("%m-%d %H:%M")


def _fmt(value: object, digits: int = 2) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"{float(str(value)):,.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _funding(value: object) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"{float(str(value)) * 100:+.4f}%"
    except (TypeError, ValueError):
        return str(value)


def _pct(value: object) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = float(str(value))
        return f"{number:+.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _market_lines(context: dict[str, Any] | None, ops: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    market = (context or {}).get("market") or {}
    quote = market.get("quote") or {}
    if quote:
        lines.append(
            f"- 现货 {quote.get('instrument', '—')}：{_fmt(quote.get('price'))} USDT，"
            f"24h {_pct(quote.get('change_24h_pct'))} · {quote.get('staleness', 'UNKNOWN')}"
        )
        indicators = market.get("indicators") or {}
        for timeframe in ("1h", "4h", "1d"):
            snapshot = indicators.get(timeframe) or {}
            if not snapshot:
                continue
            lines.append(
                f"- {timeframe.upper()}：趋势 {snapshot.get('trend', '—')}，"
                f"RSI14 {_fmt(snapshot.get('rsi14'), 2)}，EMA20 {_fmt(snapshot.get('ema20'))}，"
                f"MACD hist {_fmt(snapshot.get('macd_hist'), 2)}"
                f"（as_of {snapshot.get('as_of') or '—'}）"
            )
        derivatives = market.get("derivatives") or {}
        if derivatives:
            lines.append(
                f"- 永续观察：标记价 {_fmt(derivatives.get('mark_price'))}，"
                f"资金费率 {_funding(derivatives.get('funding_rate'))}，"
                f"{derivatives.get('staleness', 'UNKNOWN')}"
            )
    else:
        market_ops = ops.get("market") or {}
        lines.append(
            f"- 最近行情快照：{_fmt(market_ops.get('price'))} USDT，"
            f"{market_ops.get('staleness', 'UNKNOWN')}，"
            f"时间 {market_ops.get('last_snapshot_at') or '—'}"
        )
    return lines


def _position_lines(context: dict[str, Any] | None) -> list[str]:
    context = context or {}
    spot = context.get("spot") or {}
    spot_state = spot.get("state") or {}
    spot_metrics = spot.get("metrics") or {}
    derivative = context.get("derivative") or None
    lines = [
        f"- 现货：数量 {_fmt(spot_state.get('quantity'), 6)}，"
        f"均价 {_fmt(spot_state.get('avg_cost'))}，"
        f"市值 {_fmt(spot_metrics.get('market_value'))}，"
        f"浮盈亏 {_fmt(spot_metrics.get('unrealized_pnl'))}"
    ]
    if derivative:
        state = derivative.get("state") or {}
        metrics = derivative.get("metrics") or {}
        lines.append(
            f"- 永续：{state.get('side', '—')} {_fmt(state.get('quantity_base'), 6)}，"
            f"入场 {_fmt(state.get('entry_price'))}，"
            f"uPnL {_fmt(metrics.get('unrealized_pnl'))}，"
            f"ROE {_pct(metrics.get('roe'))}，"
            f"距清算价 {_pct(metrics.get('liq_distance_pct'))}"
        )
    else:
        lines.append("- 永续：无持仓")
    plan = context.get("risk_plan")
    if isinstance(plan, dict):
        if plan.get("error"):
            lines.append(f"- 风险计划：{plan['error']}")
        else:
            stop_price = (
                plan.get("effective_stop") or plan.get("derived_stop") or "—"
            )
            lines.append(
                f"- 风险计划：止损 {stop_price}，"
                f"单笔风险 {_pct(plan.get('risk_pct_equity'))}，"
                f"预算内 {plan.get('within_budget')}"
            )
    return lines


def _health_lines(ops: dict[str, Any]) -> list[str]:
    runs = ops.get("runs") or {}
    jobs = ops.get("jobs") or {}
    decisions = ops.get("decisions") or {}
    notifications = ops.get("notifications") or {}
    stream = ops.get("stream") or {}
    lines = [
        f"- 调度器：{'开启' if ops.get('scheduler_enabled') else '关闭'}；"
        f"上次分析 {_local_text(stream.get('last_monitored_at'))}；"
        f"下次计划 {_local_text(stream.get('next_monitor_at'))}"
    ]
    lines.append(
        f"- 过去 24h Run：{_status_text(runs.get('last_24h'))}；"
        f"Decision {decisions.get('last_24h', 0)} 条"
    )
    last_failed = runs.get("last_failed") or {}
    if last_failed:
        lines.append(
            f"- 最近失败：{last_failed.get('started_at')} · "
            f"{last_failed.get('error_code') or last_failed.get('status')} · "
            f"{last_failed.get('error_message') or '—'}"
        )
    lines.append(
        f"- 任务队列：待处理/运行中 {jobs.get('pending_or_running', 0)}；"
        f"24h 失败 {jobs.get('failed_24h', 0)}"
    )
    lines.append(
        f"- 通知（7 天）：{_status_text(notifications.get('last_7d'))}"
    )
    return lines


def _local_text(value: object) -> str:
    if not value:
        return "—"
    return str(value).replace("T", " ")[:16]


def _status_text(counts: dict[str, int] | None) -> str:
    if not counts:
        return "无记录"
    return " / ".join(f"{key} {value}" for key, value in sorted(counts.items()))


def _news_lines(news: list[dict[str, Any]], timezone: str) -> list[str]:
    if not news:
        return ["- 今日无可用新闻"]
    return [
        f"- [{item.get('category', 'NEWS')}] {item.get('title')} "
        f"（{item.get('source')} · {_local(item.get('published_at'), timezone)}）"
        f" {item.get('url')}"
        for item in news
    ]


def build_daily_digest(
    *,
    stream: InvestmentStream,
    asset: Asset,
    context: dict[str, Any] | None,
    decision: dict[str, Any] | None,
    decision_summary: str | None,
    analysis_error: str | None,
    ops: dict[str, Any],
    news: list[dict[str, Any]],
    scheduled_for: datetime,
) -> tuple[str, str, str]:
    timezone = stream.timezone
    time_label = _local(scheduled_for, timezone)
    date_label = scheduled_for.astimezone(ZoneInfo(timezone)).strftime("%Y-%m-%d")
    settings = get_settings()
    label = DECISION_LABELS.get(
        str(decision.get("decision")) if decision else "", "暂无新建议"
    )
    subject = f"[Thesium] {asset.symbol} 每日简报 · {date_label} {time_label[-5:]}"

    market_lines = _market_lines(context, ops)
    position_lines = _position_lines(context)
    health_lines = _health_lines(ops)
    news_lines = _news_lines(news, timezone)

    text_lines: list[str] = [
        f"{asset.name}（{asset.symbol}）每日简报 · {date_label} {time_label[-5:]}",
        "",
        "一、执行结果",
    ]
    if analysis_error:
        text_lines.append(f"- 08:00 分析失败：{analysis_error}")
    elif decision:
        text_lines.append(f"- 08:00 分析完成：{label}")
        text_lines.append(
            f"- Decision {decision.get('decision')} · "
            f"优先 {decision.get('priority')} · "
            f"置信度 {_fmt(decision.get('confidence'))}（模型自评，非胜率）"
        )
        if decision_summary:
            text_lines.append(f"- {decision_summary}")
    else:
        text_lines.append("- 08:00 没有生成新的 Decision")

    text_lines.extend(["", "二、行情与指标", *market_lines])
    text_lines.extend(["", "三、持仓与风险", *position_lines])
    text_lines.extend(["", "四、系统健康度", *health_lines])
    text_lines.extend(
        [
            "",
            "五、新闻标题（外部内容，仅标题/链接，不参与 Decision）",
            *news_lines,
        ]
    )
    text_lines.extend(
        [
            "",
            f"产品页：{settings.web_base_url.rstrip('/')}/products/{asset.symbol.lower()}",
            f"系统状态：{settings.web_base_url.rstrip('/')}/system",
            "",
            "仅供个人参考，不构成投资建议；Thesium 不执行任何交易。",
        ]
    )
    text = "\n".join(text_lines)

    def li(items: list[str]) -> str:
        parts: list[str] = []
        for item in items:
            text = item[2:] if item.startswith("- ") else item
            parts.append(f"<li>{_esc(text)}</li>")
        return "".join(parts)

    decision_html = (
        f"<p><strong>{_esc(label)}</strong> · {_esc(decision.get('priority'))} · "
        f"置信度 {_esc(decision.get('confidence'))}（模型自评，非胜率）</p>"
        f"<p>{_esc(decision_summary or '')}</p>"
        if decision and not analysis_error
        else f"<p class='error'>08:00 分析失败：{_esc(analysis_error or '未生成 Decision')}</p>"
    )
    news_html = "".join(
        f"<li><a href='{_esc(item.get('url'))}'>{_esc(item.get('title'))}</a> "
        f"<span style='color:#6b7280'>（{_esc(item.get('source'))} · "
        f"{_esc(_local(item.get('published_at'), timezone))}）</span></li>"
        for item in news
    ) or "<li>今日无可用新闻</li>"
    product_url = settings.web_base_url.rstrip("/") + "/products/" + asset.symbol.lower()
    system_url = settings.web_base_url.rstrip("/") + "/system"
    body_html = f"""<!doctype html>
<html lang="zh-CN"><body style="font-family:system-ui,sans-serif;line-height:1.7;color:#1f2937">
<h2>{_esc(asset.name)}（{_esc(asset.symbol)}）每日简报 · {_esc(date_label)}</h2>
<h3>一、执行结果</h3>{decision_html}
<h3>二、行情与指标</h3><ul>{li(market_lines)}</ul>
<h3>三、持仓与风险</h3><ul>{li(position_lines)}</ul>
<h3>四、系统健康度</h3><ul>{li(health_lines)}</ul>
<h3>五、新闻标题</h3><ul>{news_html}</ul>
<p style="color:#9ca3af;font-size:12px">外部新闻仅提供标题与链接，不参与 Decision 或投资判断。</p>
<p><a href="{_esc(product_url)}">产品页</a> ·
<a href="{_esc(system_url)}">系统状态</a></p>
<p style="color:#9ca3af;font-size:12px">仅供个人参考，不构成投资建议；Thesium 不执行任何交易。</p>
</body></html>"""
    return subject, text, body_html