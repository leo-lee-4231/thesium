from __future__ import annotations

import asyncio
import html
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import NewsArticle

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_MAX_ITEMS_PER_FEED = 25
_MAX_TOTAL = 10
_LOOKBACK_HOURS = 48


@dataclass(frozen=True)
class NewsFeed:
    name: str
    category: str
    url: str


# Public RSS feeds only; headlines and links are stored, never full text.
DEFAULT_FEEDS: tuple[NewsFeed, ...] = (
    NewsFeed(
        "CoinDesk",
        "CRYPTO",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
    ),
    NewsFeed("Cointelegraph", "CRYPTO", "https://cointelegraph.com/rss"),
    NewsFeed(
        "CNBC Finance",
        "FINANCE",
        "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    ),
    NewsFeed(
        "CNBC Markets",
        "FINANCE",
        "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    ),
    NewsFeed(
        "Yahoo Finance",
        "FINANCE",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BTC-USD&region=US&lang=en-US",
    ),
)


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return html.unescape(_TAG_RE.sub("", value)).strip()


def _parse_date(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
    if parsed is None:
        return fallback
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_feed(
    payload: bytes | str,
    *,
    source: str,
    category: str,
    fetched_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Parse RSS 2.0 or Atom and return headline rows.

    Only title/link/date/source are retained. Full article text is never stored.
    """

    fetched_at = fetched_at or datetime.now(UTC)
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise ValueError(f"invalid feed XML: {exc}") from exc

    items: list[ElementTree.Element] = []
    if _local_name(root.tag).lower() == "feed":
        items = [element for element in root if _local_name(element.tag) == "entry"]
    else:
        for channel in root.iter():
            if _local_name(channel.tag) == "channel":
                items = [element for element in channel if _local_name(element.tag) == "item"]
                break

    rows: list[dict[str, Any]] = []
    for item in items[:_MAX_ITEMS_PER_FEED]:
        fields = {_local_name(child.tag): child for child in item}
        title = _clean_text(fields.get("title").text if fields.get("title") is not None else None)
        if not title:
            continue

        links = [
            child for child in item if _local_name(child.tag).lower() == "link"
        ]
        link_node = next(
            (
                node
                for node in links
                if node.attrib.get("rel") in {None, "alternate"}
                and node.attrib.get("href")
            ),
            links[0] if links else None,
        )
        link = ""
        if link_node is not None:
            link = (link_node.text or "").strip() or link_node.attrib.get("href", "").strip()
        if not link:
            guid = fields.get("guid")
            candidate = (guid.text or "").strip() if guid is not None else ""
            if candidate.startswith(("http://", "https://")):
                link = candidate
        parsed = urlparse(link)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue

        date_node = fields.get("pubDate")
        if date_node is None:
            date_node = fields.get("published")
        if date_node is None:
            date_node = fields.get("updated")
        if date_node is None:
            date_node = fields.get("date")
        published_at = _parse_date(
            date_node.text if date_node is not None else None, fetched_at
        )
        rows.append(
            {
                "source": source,
                "category": category,
                "title": title[:500],
                "url": link[:1000],
                "published_at": published_at,
                "fetched_at": fetched_at,
            }
        )
    return rows


def select_headlines(rows: list[dict[str, Any]], limit: int = _MAX_TOTAL) -> list[dict[str, Any]]:
    """Newest unique headlines, balanced by category and source."""

    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: item["published_at"], reverse=True):
        url = str(row["url"])
        title_key = re.sub(r"\W+", "", str(row["title"]).lower())[:120]
        if url in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url)
        seen_titles.add(title_key)
        unique.append(row)

    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    source_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {"CRYPTO": 0, "FINANCE": 0}
    max_per_source = 2
    max_per_category = 5

    def add(row: dict[str, Any]) -> None:
        selected.append(row)
        selected_ids.add(id(row))
        source_counts[str(row["source"])] = source_counts.get(str(row["source"]), 0) + 1
        category_counts[str(row["category"])] = (
            category_counts.get(str(row["category"]), 0) + 1
        )

    for row in unique:
        if len(selected) >= limit:
            break
        source = str(row["source"])
        category = str(row["category"])
        if source_counts.get(source, 0) >= max_per_source:
            continue
        if category_counts.get(category, 0) >= max_per_category:
            continue
        add(row)

    for row in unique:
        if len(selected) >= limit:
            break
        if id(row) in selected_ids:
            continue
        category = str(row["category"])
        if category_counts.get(category, 0) >= max_per_category:
            continue
        add(row)

    for row in unique:
        if len(selected) >= limit:
            break
        if id(row) not in selected_ids:
            add(row)
    return selected[:limit]

class NewsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _fetch_feed(
        self, client: httpx.AsyncClient, feed: NewsFeed, now: datetime
    ) -> list[dict[str, Any]]:
        response = await client.get(feed.url)
        response.raise_for_status()
        return parse_feed(
            response.content,
            source=feed.name,
            category=feed.category,
            fetched_at=now,
        )

    async def refresh(self, feeds: tuple[NewsFeed, ...] = DEFAULT_FEEDS) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        rows: list[dict[str, Any]] = []
        timeout = httpx.Timeout(20.0, connect=8.0)
        headers = {"User-Agent": "thesium/0.1 (headline reader)"}
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, trust_env=True, headers=headers
        ) as client:
            results = await asyncio.gather(
                *(
                    asyncio.wait_for(
                        self._fetch_feed(client, feed, now), timeout=25
                    )
                    for feed in feeds
                ),
                return_exceptions=True,
            )
        for feed, result in zip(feeds, results, strict=True):
            if isinstance(result, Exception):
                logger.warning("news feed failed source=%s error=%s", feed.name, result)
                continue
            rows.extend(result)
            logger.info("news feed fetched source=%s items=%s", feed.name, len(result))

        for row in rows:
            statement = (
                pg_insert(NewsArticle)
                .values(**row)
                .on_conflict_do_nothing(index_elements=["url"])
            )
            await self._session.execute(statement)
        await self._session.commit()
        return select_headlines(rows)

    async def latest(self, limit: int = _MAX_TOTAL) -> list[dict[str, Any]]:
        cutoff = datetime.now(UTC) - timedelta(hours=_LOOKBACK_HOURS)
        rows = (
            (
                await self._session.execute(
                    select(NewsArticle)
                    .where(NewsArticle.published_at >= cutoff)
                    .order_by(NewsArticle.published_at.desc())
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        return select_headlines(
            [
                {
                    "source": row.source,
                    "category": row.category,
                    "title": row.title,
                    "url": row.url,
                    "published_at": row.published_at,
                }
                for row in rows
            ],
            limit=limit,
        )

    async def refresh_and_latest(self, limit: int = _MAX_TOTAL) -> list[dict[str, Any]]:
        try:
            rows = await self.refresh()
        except Exception as exc:  # noqa: BLE001 - digest must still send
            logger.warning("news refresh failed; using cache: %s", exc)
            rows = []
        if not rows:
            rows = await self.latest(limit=limit)
        return rows[:limit]