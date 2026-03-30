import pytest

from src.models import Article, ArticleStatus, PipelineRun, SourceType
from src.storage.db import (
    get_articles_by_status,
    get_cost_today,
    get_cost_month,
    get_usage_stats,
    is_duplicate,
    log_api_usage,
    log_delivery,
    save_article,
    save_pipeline_run,
    update_article_status,
)


def test_save_and_deduplicate(db_conn, sample_article):
    db_id = save_article(db_conn, sample_article)
    assert db_id is not None
    assert sample_article.db_id == db_id

    # Same article again -> None (duplicate)
    dup = save_article(db_conn, sample_article)
    assert dup is None


def test_is_duplicate(db_conn, sample_article):
    assert is_duplicate(db_conn, sample_article.content_hash) is False
    save_article(db_conn, sample_article)
    assert is_duplicate(db_conn, sample_article.content_hash) is True


def test_update_status(db_conn, sample_article):
    save_article(db_conn, sample_article)
    update_article_status(db_conn, sample_article.db_id, ArticleStatus.DELIVERED)

    articles = get_articles_by_status(db_conn, ArticleStatus.DELIVERED)
    assert len(articles) == 1
    assert articles[0].status == ArticleStatus.DELIVERED


def test_get_articles_by_status(db_conn):
    for i in range(5):
        a = Article(
            source_type=SourceType.RSS,
            source_name="test",
            source_url=f"https://example.com/{i}",
            title=f"Article {i}",
            content_text="body",
        )
        save_article(db_conn, a)

    articles = get_articles_by_status(db_conn, ArticleStatus.NEW)
    assert len(articles) == 5


def test_log_delivery(db_conn, sample_article):
    save_article(db_conn, sample_article)
    log_delivery(db_conn, sample_article.db_id, 999, "-100123")

    row = db_conn.execute("SELECT * FROM delivery_log WHERE article_id = ?", (sample_article.db_id,)).fetchone()
    assert row["telegram_msg_id"] == 999
    assert row["chat_id"] == "-100123"


def test_save_pipeline_run(db_conn):
    run = PipelineRun(run_type="daily")
    run.articles_collected = 10
    run.articles_passed = 5
    run.articles_delivered = 3

    db_id = save_pipeline_run(db_conn, run)
    assert db_id is not None

    row = db_conn.execute("SELECT * FROM pipeline_runs WHERE id = ?", (db_id,)).fetchone()
    assert row["articles_collected"] == 10
    assert row["articles_delivered"] == 3


def test_api_usage_tracking(db_conn):
    log_api_usage(db_conn, "haiku", 1500, 200, 0.0025, "Test article")
    log_api_usage(db_conn, "haiku", 1200, 180, 0.0021, "Another article")

    assert get_cost_today(db_conn) == pytest.approx(0.0046)
    assert get_cost_month(db_conn) == pytest.approx(0.0046)

    stats = get_usage_stats(db_conn)
    assert stats["today"]["calls"] == 2
    assert stats["today"]["input_tokens"] == 2700
    assert stats["month"]["cost_usd"] == pytest.approx(0.0046)
