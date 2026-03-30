from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import yaml
from anthropic import AsyncAnthropic

from src.cost_tracker import BudgetExceeded, CostTracker
from src.models import Article, ArticleStatus, Theme

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 2000
DELAY_BETWEEN_CALLS = 0.5
MODEL = "claude-haiku-4-5-20251001"

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def _load_prompt_template() -> str:
    with open(CONFIG_DIR / "prompts.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["scoring_prompt"]


class AIScorer:
    def __init__(self, api_key: str, cost_tracker: CostTracker) -> None:
        self.client = AsyncAnthropic(api_key=api_key)
        self.prompt_template = _load_prompt_template()
        self.cost_tracker = cost_tracker

    async def score_article(self, article: Article) -> Article:
        # Check budget BEFORE making the call
        try:
            self.cost_tracker.check_budget()
        except BudgetExceeded as e:
            logger.warning("Skipping scoring for '%s': %s", article.title[:50], e)
            raise

        prompt = self.prompt_template.format(
            title=article.title,
            source_name=article.source_name,
            language=article.language,
            content_text=article.content_text[:MAX_CONTENT_LENGTH],
        )

        try:
            message = await self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            # Record token usage from the actual API response
            input_tokens = message.usage.input_tokens
            output_tokens = message.usage.output_tokens
            self.cost_tracker.record_usage(
                model=MODEL,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                article_title=article.title,
                success=True,
            )

            response_text = message.content[0].text
            data = json.loads(response_text)

            article.ai_score = int(data["score"])
            article.ai_themes = [
                Theme(t) for t in data.get("themes", []) if t in Theme._value2member_map_
            ]
            article.ai_key_points = data.get("key_points", [])[:3]
            article.ai_angle = data.get("angle", "")
            article.is_cross_theme = data.get("is_cross_theme", len(article.ai_themes) >= 2)
            article.status = ArticleStatus.SCORED

        except json.JSONDecodeError as e:
            logger.warning("AI scorer: JSON parse error for '%s': %s", article.title[:50], e)
            logger.debug("AI scorer: raw response was: %r", response_text)
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("AI scorer: API error for '%s': %s", article.title[:50], e)

        return article

    async def score_batch(self, articles: list[Article]) -> list[Article]:
        scored: list[Article] = []
        budget_skipped = 0
        budget_hit = False

        for article in articles:
            if budget_hit:
                scored.append(article)
                budget_skipped += 1
                continue

            try:
                result = await self.score_article(article)
                scored.append(result)
                await asyncio.sleep(DELAY_BETWEEN_CALLS)
            except BudgetExceeded:
                budget_hit = True
                scored.append(article)
                budget_skipped += 1

        success = sum(1 for a in scored if a.ai_score is not None)
        parse_errors = len(articles) - success - budget_skipped
        logger.info("AI scorer: scored %d/%d articles", success, len(articles))
        if parse_errors:
            logger.info("AI scorer: %d articles failed (API/parse error)", parse_errors)
        if budget_skipped:
            logger.info("AI scorer: %d articles skipped (budget guardrail)", budget_skipped)

        # Log run summary
        logger.info(self.cost_tracker.get_run_summary())

        return scored
