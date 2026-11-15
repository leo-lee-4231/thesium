from datetime import UTC, datetime

from app.application.news_service import parse_feed, select_headlines

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Bitcoin &amp; ETH move</title>
    <link>https://example.com/crypto/1</link>
    <pubDate>Sun, 15 Nov 2026 02:00:00 +0000</pubDate>
  </item>
  <item>
    <title><![CDATA[<b>Fed</b> decision]]></title>
    <link>https://example.com/finance/1</link>
    <pubDate>Sun, 15 Nov 2026 01:00:00 +0000</pubDate>
  </item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Atom headline</title>
    <link rel="self" href="https://example.com/self"/>
    <link rel="alternate" href="https://example.com/article"/>
    <published>2026-11-15T03:00:00Z</published>
  </entry>
</feed>"""


def test_parses_rss_cleans_html_and_dates() -> None:
    rows = parse_feed(RSS, source="Example", category="CRYPTO")
    assert len(rows) == 2
    assert rows[0]["title"] == "Bitcoin & ETH move"
    assert rows[1]["title"] == "Fed decision"
    assert rows[0]["published_at"].tzinfo is not None


def test_parses_atom_and_prefers_alternate_link() -> None:
    rows = parse_feed(ATOM, source="Atom", category="FINANCE")
    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.com/article"
    assert rows[0]["published_at"] == datetime(2026, 11, 15, 3, 0, tzinfo=UTC)


def test_selection_dedupes_and_balances() -> None:
    now = datetime(2026, 11, 15, 4, 0, tzinfo=UTC)
    rows = [
        {
            "source": "A",
            "category": "CRYPTO",
            "title": "Same",
            "url": "https://a/1",
            "published_at": now,
        },
        {
            "source": "B",
            "category": "CRYPTO",
            "title": "Same",
            "url": "https://a/2",
            "published_at": now,
        },
        {
            "source": "C",
            "category": "FINANCE",
            "title": "Fed",
            "url": "https://c/1",
            "published_at": now,
        },
    ]
    selected = select_headlines(rows, limit=10)
    assert len(selected) == 2
    assert {row["category"] for row in selected} == {"CRYPTO", "FINANCE"}
