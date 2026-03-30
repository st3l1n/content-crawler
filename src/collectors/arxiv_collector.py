from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import arxiv

from src.collectors.base import BaseCollector
from src.models import Article, SourceType

logger = logging.getLogger(__name__)

DEFAULT_QUERIES = [
    'cat:cs.CR AND (ti:"LLM" OR ti:"language model" OR ti:"AI agent" OR ti:"prompt injection")',
    'cat:cs.CR AND (ti:"human factor" OR ti:"cognitive" OR ti:"decision making" OR ti:"social engineering")',
    'cat:cs.CR AND (ti:"forensic" OR ti:"incident response" OR ti:"memory analysis" OR ti:"malware analysis")',
]

MAX_RESULTS_PER_QUERY = 50


class ArxivCollector(BaseCollector):
    def __init__(
        self,
        queries: list[str] | None = None,
        days_back: int = 7,
    ) -> None:
        self.queries = queries or DEFAULT_QUERIES
        self.days_back = days_back

    async def collect(self) -> list[Article]:
        results = await asyncio.to_thread(self._collect_sync)
        logger.info("arxiv collector: %d papers from %d queries", len(results), len(self.queries))
        return results

    def _collect_sync(self) -> list[Article]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.days_back)
        seen_ids: set[str] = set()
        articles: list[Article] = []

        client = arxiv.Client()

        for query in self.queries:
            try:
                search = arxiv.Search(
                    query=query,
                    max_results=MAX_RESULTS_PER_QUERY,
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                )

                for result in client.results(search):
                    pub_date = result.published.replace(tzinfo=timezone.utc)
                    if pub_date < cutoff:
                        continue

                    paper_id = result.entry_id.split("/")[-1]
                    if paper_id in seen_ids:
                        continue
                    seen_ids.add(paper_id)

                    articles.append(
                        Article(
                            source_type=SourceType.ARXIV,
                            source_name="arxiv",
                            source_url=result.entry_id,
                            title=result.title.replace("\n", " "),
                            content_text=result.summary.replace("\n", " ")[:5000],
                            published_at=pub_date,
                            language="en",
                        )
                    )
            except Exception as e:
                logger.warning("arxiv query failed: %s — %s", query[:60], e)

        return articles
