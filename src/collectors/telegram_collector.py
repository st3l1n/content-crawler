from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
from bs4 import BeautifulSoup, Tag

from src.collectors.base import BaseCollector
from src.config import ChannelConfig
from src.models import Article, SourceType

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
MAX_PAGES = 3
DELAY_BETWEEN_CHANNELS = 2.5


class TelegramCollector(BaseCollector):
    def __init__(
        self,
        channels: list[ChannelConfig],
        hours_back: int = 24,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.channels = channels
        self.hours_back = hours_back
        self._client = client

    async def collect(self) -> list[Article]:
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
            follow_redirects=True,
        )

        articles: list[Article] = []
        try:
            for i, channel in enumerate(self.channels):
                if i > 0:
                    await asyncio.sleep(DELAY_BETWEEN_CHANNELS)
                try:
                    result = await self._collect_channel(client, channel)
                    articles.extend(result)
                except Exception as e:
                    logger.warning("Failed to collect TG channel @%s: %s", channel.handle, e)
        finally:
            if own_client:
                await client.aclose()

        logger.info(
            "Telegram collector: %d posts from %d channels",
            len(articles),
            len(self.channels),
        )
        return articles

    async def _collect_channel(
        self, client: httpx.AsyncClient, channel: ChannelConfig
    ) -> list[Article]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.hours_back)
        articles: list[Article] = []
        before_id: int | None = None

        for _ in range(MAX_PAGES):
            url = f"https://t.me/s/{channel.handle}"
            if before_id:
                url += f"?before={before_id}"

            resp = await client.get(url)
            resp.raise_for_status()

            posts, oldest_id = self._parse_page(resp.text, channel)

            for post in posts:
                if post.published_at and post.published_at < cutoff:
                    return articles
                articles.append(post)

            if oldest_id is None or len(posts) == 0:
                break
            before_id = oldest_id

        return articles

    def _parse_page(
        self, html: str, channel: ChannelConfig
    ) -> tuple[list[Article], int | None]:
        soup = BeautifulSoup(html, "html.parser")
        messages = soup.select("div.tgme_widget_message")

        articles: list[Article] = []
        oldest_id: int | None = None

        for msg in reversed(messages):
            post_id = self._extract_post_id(msg)
            if post_id is not None:
                if oldest_id is None or post_id < oldest_id:
                    oldest_id = post_id

            text_el = msg.select_one("div.tgme_widget_message_text")
            if not text_el:
                continue

            text = text_el.get_text(separator="\n", strip=True)
            if not text or len(text) < 20:
                continue

            pub_date = self._extract_date(msg)
            post_url = f"https://t.me/{channel.handle}/{post_id}" if post_id else ""

            title = text[:100].split("\n")[0]

            articles.append(
                Article(
                    source_type=SourceType.TELEGRAM,
                    source_name=f"@{channel.handle}",
                    source_url=post_url,
                    title=title,
                    content_text=text[:5000],
                    published_at=pub_date,
                    language=channel.language,
                )
            )

        return articles, oldest_id

    @staticmethod
    def _extract_post_id(msg: Tag) -> int | None:
        data_post = msg.get("data-post", "")
        if isinstance(data_post, list):
            data_post = data_post[0] if data_post else ""
        match = re.search(r"/(\d+)$", data_post)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_date(msg: Tag) -> datetime | None:
        time_el = msg.select_one("time[datetime]")
        if time_el:
            dt_str = time_el.get("datetime", "")
            if isinstance(dt_str, list):
                dt_str = dt_str[0] if dt_str else ""
            try:
                return datetime.fromisoformat(dt_str.replace("+00:00", "+00:00"))
            except (ValueError, TypeError):
                return None
        return None
