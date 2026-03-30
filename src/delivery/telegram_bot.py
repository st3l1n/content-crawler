from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import date

from telegram import Bot
from telegram.error import BadRequest, RetryAfter

from src.models import Article, Theme

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096

THEME_LABELS: dict[Theme, str] = {
    Theme.AI_CYBERSEC: "AI x Cybersec",
    Theme.THREAT_INTEL: "Threat Intel",
    Theme.DFIR: "DFIR",
    Theme.VIBE_CODING: "Vibe Coding",
    Theme.PSYCH_CYBERSEC: "Psych x Cybersec",
}


def _theme_tag(themes: list[Theme]) -> str:
    labels = [THEME_LABELS.get(t, t.value) for t in themes]
    return " x ".join(labels) if labels else "General"


def format_card(article: Article) -> str:
    themes = article.effective_themes
    score = article.effective_score
    theme_tag = _theme_tag(themes)

    lines = [
        f"[{theme_tag}] Relevance: {score:.0f}/5" if article.ai_score is not None
        else f"[{theme_tag}] KW Score: {score:.2f}",
        f"<b>{_escape_html(article.title)}</b>",
        f"<a href=\"{article.source_url}\">Source: {_escape_html(article.source_name)}</a>",
    ]

    if article.ai_key_points:
        lines.append("")
        for point in article.ai_key_points[:3]:
            lines.append(f"• {_escape_html(point)}")

    if article.ai_angle:
        lines.append(f"\nAngle: {_escape_html(article.ai_angle)}")

    text = "\n".join(lines)
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[: MAX_MESSAGE_LENGTH - 3] + "..."
    return text


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_weekly_digest(
    articles: list[Article],
    date_from: date,
    date_to: date,
) -> str:
    date_range = f"{date_from.strftime('%d.%m')} - {date_to.strftime('%d.%m.%Y')}"

    top = sorted(articles, key=lambda a: a.effective_score, reverse=True)[:3]
    top_lines = []
    for i, a in enumerate(top, 1):
        tag = _theme_tag(a.effective_themes)
        score = a.effective_score
        top_lines.append(f"{i}. [{tag}] {_escape_html(a.title[:80])} (score: {score:.0f})")

    theme_counter: Counter[str] = Counter()
    for a in articles:
        for t in a.effective_themes:
            theme_counter[THEME_LABELS.get(t, t.value)] += 1

    trend_lines = []
    for theme_label, count in theme_counter.most_common(5):
        trend_lines.append(f"  {theme_label} — {count}")

    arxiv_count = sum(1 for a in articles if a.source_type.value == "arxiv")
    arxiv_passed = sum(
        1 for a in articles if a.source_type.value == "arxiv" and a.is_publishable
    )

    lines = [
        f"<b>Weekly digest | {date_range}</b>",
        "",
        "<b>Top-3:</b>",
        *top_lines,
        "",
        "<b>Trends:</b>",
        *trend_lines,
    ]

    if arxiv_count:
        lines.append(f"\narxiv: {arxiv_count} papers, {arxiv_passed} passed threshold")

    lines.append(f"\nTotal collected: {len(articles)}")

    text = "\n".join(lines)
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[: MAX_MESSAGE_LENGTH - 3] + "..."
    return text


class TelegramDelivery:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id

    async def send_card(self, article: Article) -> int | None:
        text = format_card(article)
        return await self._send(text)

    async def send_digest(self, text: str) -> int | None:
        return await self._send(text)

    async def send_weekly_digest(
        self,
        articles: list[Article],
        date_from: date,
        date_to: date,
    ) -> int | None:
        text = format_weekly_digest(articles, date_from, date_to)
        return await self._send(text)

    async def _send(self, text: str, retry: int = 0) -> int | None:
        try:
            msg = await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return msg.message_id
        except RetryAfter as e:
            if retry < 2:
                logger.warning("Telegram rate limit, sleeping %ds", e.retry_after)
                await asyncio.sleep(e.retry_after)
                return await self._send(text, retry + 1)
            logger.error("Telegram rate limit exceeded after retries")
            return None
        except BadRequest as e:
            logger.warning("Telegram BadRequest with HTML, falling back to plain: %s", e)
            try:
                msg = await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    disable_web_page_preview=True,
                )
                return msg.message_id
            except Exception as e2:
                logger.error("Telegram delivery failed: %s", e2)
                return None
        except Exception as e:
            logger.error("Telegram delivery failed: %s", e)
            return None
