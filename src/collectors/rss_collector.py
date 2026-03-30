from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import feedparser
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector
from src.config import FeedConfig
from src.models import Article, SourceType

logger = logging.getLogger(__name__)


def _strip_html(html: str) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


def _parse_date(entry: dict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None
    return None


class RSSCollector(BaseCollector):
    def __init__(self, feeds: list[FeedConfig], hours_back: int = 24) -> None:
        self.feeds = feeds
        self.hours_back = hours_back

    async def collect(self) -> list[Article]:
        tasks = [self._collect_feed(feed) for feed in self.feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        articles: list[Article] = []
        for feed, result in zip(self.feeds, results):
            if isinstance(result, Exception):
                logger.warning("Failed to collect RSS feed %s: %s", feed.name, result)
                continue
            articles.extend(result)

        logger.info("RSS collector: %d articles from %d feeds", len(articles), len(self.feeds))
        return articles

    async def _collect_feed(self, feed: FeedConfig) -> list[Article]:
        parsed = await asyncio.to_thread(feedparser.parse, feed.url)

        if parsed.bozo and not parsed.entries:
            logger.warning("RSS feed %s returned bozo: %s", feed.name, parsed.bozo_exception)
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.hours_back)
        articles: list[Article] = []

        for entry in parsed.entries:
            pub_date = _parse_date(entry)
            if pub_date and pub_date < cutoff:
                continue

            title = entry.get("title", "").strip()
            if not title:
                continue

            link = entry.get("link", "")
            summary = _strip_html(
                entry.get("summary", "") or entry.get("content", [{}])[0].get("value", "")
            )

            articles.append(
                Article(
                    source_type=SourceType.RSS,
                    source_name=feed.name,
                    source_url=link,
                    title=title,
                    content_text=summary[:5000],
                    published_at=pub_date,
                    language=feed.language,
                )
            )

        return articles
