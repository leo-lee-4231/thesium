from datetime import UTC, datetime

from app.application.digest_templates import build_daily_digest
from app.db.models import Asset, InvestmentStream


def test_build_digest_contains_sections_and_news() -> None:
    stream = InvestmentStream(
        name="BTC 产品",
        timezone="Asia/Shanghai",
        monitor_interval_minutes=60,
        agent_enabled=True,
        created_at=datetime(2026, 11, 15, 0, 0, tzinfo=UTC),
    )
    asset = Asset(symbol="BTC", name="Bitcoin", kind="CRYPTO")
    context = {
        "market": {
            "quote": {
                "instrument": "BTC-USDT",
                "price": "64000",
                "change_24h_pct": "-2.5",
                "staleness": "FRESH",
            },
            "indicators": {
                "1h": {
                    "trend": "DOWN",
                    "rsi14": 41.2,
                    "ema20": 65000,
                    "macd_hist": -10.5,
                    "as_of": "2026-11-15T03:00:00Z",
                }
            },
            "derivatives": None,
        },
        "spot": {
            "state": {"quantity": "0", "avg_cost": "0"},
            "metrics": {"market_value": "0", "unrealized_pnl": "0"},
        },
        "derivative": None,
        "risk_plan": None,
    }
    ops = {
        "scheduler_enabled": True,
        "stream": {
            "last_monitored_at": "2026-11-15T00:00:00Z",
            "next_monitor_at": "2026-11-15T01:00:00Z",
        },
        "runs": {"last_24h": {"SUCCEEDED": 3}, "last_failed": None},
        "jobs": {"pending_or_running": 0, "failed_24h": 0},
        "decisions": {"last_24h": 1},
        "notifications": {"last_7d": {"SENT": 1, "SKIPPED": 4}},
        "market": {"price": "64000", "staleness": "FRESH", "last_snapshot_at": None},
    }
    news = [
        {
            "category": "CRYPTO",
            "title": "Bitcoin moves",
            "source": "CoinDesk",
            "published_at": datetime(2026, 11, 15, 2, 0, tzinfo=UTC),
            "url": "https://example.com/a",
        }
    ]
    subject, text, body_html = build_daily_digest(
        stream=stream,
        asset=asset,
        context=context,
        decision={
            "decision": "WAIT",
            "priority": "NORMAL",
            "confidence": "0.6",
        },
        decision_summary="等待确认",
        analysis_error=None,
        ops=ops,
        news=news,
        scheduled_for=datetime(2026, 11, 15, 0, 0, tzinfo=UTC),
    )
    assert "每日简报" in subject
    assert "行情与指标" in text
    assert "系统健康度" in text
    assert "https://example.com/a" in text
    assert "Bitcoin moves" in body_html
