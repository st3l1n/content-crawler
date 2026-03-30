from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, datetime, timedelta

from src.collectors.arxiv_collector import ArxivCollector
from src.collectors.rss_collector import RSSCollector
from src.collectors.telegram_collector import TelegramCollector
from src.config import get_settings
from src.cost_tracker import CostTracker
from src.delivery.telegram_bot import TelegramDelivery
from src.filters.ai_scorer import AIScorer
from src.filters.keyword_filter import KeywordFilter
from src.logging_config import setup_logging
from src.models import Article, ArticleStatus, PipelineRun
from src.storage.db import (
    get_connection,
    init_db,
    is_duplicate,
    log_delivery,
    save_article,
    save_pipeline_run,
    update_article_status,
)

logger = logging.getLogger(__name__)

MAX_CARDS_PER_RUN = 7


async def run_daily_pipeline() -> None:
    settings = get_settings()
    conn = get_connection(settings.db_path)
    init_db(conn)

    run = PipelineRun(run_type="daily")
    logger.info("Starting daily pipeline run")

    try:
        # 1. Collect from RSS + Telegram in parallel
        rss_collector = RSSCollector(settings.feeds)
        tg_collector = TelegramCollector(settings.channels)

        rss_articles, tg_articles = await asyncio.gather(
            rss_collector.collect(),
            tg_collector.collect(),
        )

        all_articles: list[Article] = [*rss_articles, *tg_articles]
        run.articles_collected = len(all_articles)
        logger.info("Collected %d articles total", len(all_articles))

        # 2. Deduplicate
        new_articles = [a for a in all_articles if not is_duplicate(conn, a.content_hash)]
        logger.info("After dedup: %d new articles", len(new_articles))

        # 3. Keyword filter
        kw_filter = KeywordFilter(settings.keywords)
        kw_filter.filter_batch(new_articles)

        passed = [a for a in new_articles if a.status != ArticleStatus.FILTERED_OUT]
        run.articles_passed = len(passed)
        logger.info("After keyword filter: %d passed", len(passed))

        # 4. AI scoring (if API key configured)
        cost_tracker = None
        if settings.anthropic_api_key and passed:
            cost_tracker = CostTracker(conn, settings.cost_limits)
            scorer = AIScorer(settings.anthropic_api_key, cost_tracker)
            passed = await scorer.score_batch(passed)

        # 5. Save all to DB
        for article in new_articles:
            save_article(conn, article)

        # 6. Select top articles for delivery
        publishable = [a for a in passed if a.is_publishable]
        approved = sorted(publishable, key=lambda a: a.effective_score, reverse=True)[
            :MAX_CARDS_PER_RUN
        ]

        # 7. Deliver via Telegram
        run.articles_delivered = await _deliver_cards(conn, settings, approved)

        # 8. Send budget alert if needed
        if cost_tracker:
            await _send_budget_alert(settings, cost_tracker)

    except Exception as e:
        logger.error("Pipeline error: %s", e, exc_info=True)
        run.errors.append(str(e))
    finally:
        run.finished_at = datetime.utcnow()
        save_pipeline_run(conn, run)
        conn.close()

    logger.info(
        "Pipeline finished: collected=%d, passed=%d, delivered=%d, errors=%d",
        run.articles_collected,
        run.articles_passed,
        run.articles_delivered,
        len(run.errors),
    )


async def run_weekly_pipeline() -> None:
    settings = get_settings()
    conn = get_connection(settings.db_path)
    init_db(conn)

    run = PipelineRun(run_type="weekly")
    logger.info("Starting weekly pipeline run")

    try:
        # 1. Collect from all sources including arxiv
        rss_collector = RSSCollector(settings.feeds, hours_back=24)
        tg_collector = TelegramCollector(settings.channels, hours_back=24)
        arxiv_collector = ArxivCollector(days_back=7)

        rss_articles, tg_articles, arxiv_articles = await asyncio.gather(
            rss_collector.collect(),
            tg_collector.collect(),
            arxiv_collector.collect(),
        )

        all_articles: list[Article] = [*rss_articles, *tg_articles, *arxiv_articles]
        run.articles_collected = len(all_articles)
        logger.info("Collected %d articles total (incl. %d arxiv)", len(all_articles), len(arxiv_articles))

        # 2. Deduplicate
        new_articles = [a for a in all_articles if not is_duplicate(conn, a.content_hash)]
        logger.info("After dedup: %d new articles", len(new_articles))

        # 3. Keyword filter
        kw_filter = KeywordFilter(settings.keywords)
        kw_filter.filter_batch(new_articles)

        passed = [a for a in new_articles if a.status != ArticleStatus.FILTERED_OUT]
        run.articles_passed = len(passed)

        # 4. AI scoring
        cost_tracker = None
        if settings.anthropic_api_key and passed:
            cost_tracker = CostTracker(conn, settings.cost_limits)
            scorer = AIScorer(settings.anthropic_api_key, cost_tracker)
            passed = await scorer.score_batch(passed)

        # 5. Save all to DB
        for article in new_articles:
            save_article(conn, article)

        # 6. Deliver daily cards
        publishable = [a for a in passed if a.is_publishable]
        approved = sorted(publishable, key=lambda a: a.effective_score, reverse=True)[
            :MAX_CARDS_PER_RUN
        ]
        run.articles_delivered = await _deliver_cards(conn, settings, approved)

        # 7. Send weekly digest
        if settings.telegram_bot_token and settings.telegram_chat_id:
            delivery = TelegramDelivery(settings.telegram_bot_token, settings.telegram_chat_id)
            today = date.today()
            week_ago = today - timedelta(days=7)
            # Digest covers all articles that passed filter this week (not just today's)
            digest_articles = publishable if publishable else passed
            msg_id = await delivery.send_weekly_digest(digest_articles, week_ago, today)
            if msg_id:
                logger.info("Weekly digest sent")

        # 8. Send budget alert if needed
        if cost_tracker:
            await _send_budget_alert(settings, cost_tracker)

    except Exception as e:
        logger.error("Pipeline error: %s", e, exc_info=True)
        run.errors.append(str(e))
    finally:
        run.finished_at = datetime.utcnow()
        save_pipeline_run(conn, run)
        conn.close()

    logger.info(
        "Weekly pipeline finished: collected=%d, passed=%d, delivered=%d, errors=%d",
        run.articles_collected,
        run.articles_passed,
        run.articles_delivered,
        len(run.errors),
    )


async def _send_budget_alert(settings, cost_tracker: CostTracker) -> None:
    """Send Telegram alert if budget is above warning threshold."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return

    from src.storage.db import get_cost_today, get_cost_month

    cost_today = get_cost_today(cost_tracker.conn)
    cost_month = get_cost_month(cost_tracker.conn)
    limits = settings.cost_limits

    alerts: list[str] = []
    if cost_today >= limits.daily_usd:
        alerts.append(f"Daily limit reached: ${cost_today:.4f} / ${limits.daily_usd:.2f}")
    elif cost_today >= limits.daily_usd * limits.warn_at_pct:
        alerts.append(f"Daily budget at {cost_today / limits.daily_usd:.0%}: ${cost_today:.4f} / ${limits.daily_usd:.2f}")

    if cost_month >= limits.monthly_usd:
        alerts.append(f"Monthly limit reached: ${cost_month:.4f} / ${limits.monthly_usd:.2f}")
    elif cost_month >= limits.monthly_usd * limits.warn_at_pct:
        alerts.append(f"Monthly budget at {cost_month / limits.monthly_usd:.0%}: ${cost_month:.4f} / ${limits.monthly_usd:.2f}")

    if alerts:
        text = "[Budget Alert]\n" + "\n".join(alerts)
        delivery = TelegramDelivery(settings.telegram_bot_token, settings.telegram_chat_id)
        await delivery.send_digest(text)
        logger.info("Budget alert sent: %s", "; ".join(alerts))


async def _deliver_cards(conn, settings, approved: list[Article]) -> int:
    delivered = 0

    if not approved:
        logger.info("No articles passed filters — nothing to deliver")
        return 0

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram credentials not configured, skipping delivery")
        return 0

    delivery = TelegramDelivery(settings.telegram_bot_token, settings.telegram_chat_id)

    for article in approved:
        msg_id = await delivery.send_card(article)

        if msg_id and article.db_id:
            update_article_status(conn, article.db_id, ArticleStatus.DELIVERED)
            log_delivery(conn, article.db_id, msg_id, settings.telegram_chat_id)
            delivered += 1
        elif article.db_id:
            update_article_status(conn, article.db_id, ArticleStatus.APPROVED)

        await asyncio.sleep(1)

    logger.info("Delivered %d cards", delivered)
    return delivered


def main() -> None:
    parser = argparse.ArgumentParser(description="Content Pipeline — Синяя шляпа")
    parser.add_argument(
        "--mode",
        choices=["daily", "weekly", "manual"],
        default="daily",
        help="Pipeline run mode",
    )
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.log_level)

    if args.mode in ("daily", "manual"):
        asyncio.run(run_daily_pipeline())
    elif args.mode == "weekly":
        asyncio.run(run_weekly_pipeline())


if __name__ == "__main__":
    main()
