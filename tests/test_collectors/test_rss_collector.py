from pathlib import Path
from unittest.mock import patch

import feedparser
import pytest

from src.collectors.rss_collector import RSSCollector, _strip_html
from src.config import FeedConfig
from src.models import SourceType

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_strip_html():
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"
    assert _strip_html("") == ""
    assert _strip_html("plain text") == "plain text"


@pytest.mark.asyncio
async def test_rss_collector_parses_feed():
    feed_xml = (FIXTURES / "sample_rss.xml").read_text()
    parsed_feed = feedparser.parse(feed_xml)
    feed_config = FeedConfig(name="test_blog", url="https://example.com/rss", themes=["threat_intel"])

    with patch("src.collectors.rss_collector.feedparser.parse", return_value=parsed_feed):
        collector = RSSCollector([feed_config], hours_back=999999)
        articles = await collector.collect()

    assert len(articles) >= 2
    assert all(a.source_type == SourceType.RSS for a in articles)
    assert all(a.source_name == "test_blog" for a in articles)


@pytest.mark.asyncio
async def test_rss_collector_filters_old():
    feed_xml = (FIXTURES / "sample_rss.xml").read_text()
    parsed_feed = feedparser.parse(feed_xml)
    feed_config = FeedConfig(name="test_blog", url="https://example.com/rss", themes=["threat_intel"])

    with patch("src.collectors.rss_collector.feedparser.parse", return_value=parsed_feed):
        collector = RSSCollector([feed_config], hours_back=24)
        articles = await collector.collect()

    old_urls = [a.source_url for a in articles if "old-article" in a.source_url]
    assert len(old_urls) == 0


@pytest.mark.asyncio
async def test_rss_collector_strips_html():
    feed_xml = (FIXTURES / "sample_rss.xml").read_text()
    parsed_feed = feedparser.parse(feed_xml)
    feed_config = FeedConfig(name="test_blog", url="https://example.com/rss", themes=["ai_cybersec"])

    with patch("src.collectors.rss_collector.feedparser.parse", return_value=parsed_feed):
        collector = RSSCollector([feed_config], hours_back=999999)
        articles = await collector.collect()

    llm_article = next((a for a in articles if "LLM" in a.title), None)
    assert llm_article is not None
    assert "<p>" not in llm_article.content_text
    assert "<b>" not in llm_article.content_text


@pytest.mark.asyncio
async def test_rss_collector_handles_error():
    feed_config = FeedConfig(name="broken", url="https://nonexistent.example.com/rss", themes=[])

    with patch("src.collectors.rss_collector.feedparser.parse", side_effect=Exception("Network error")):
        collector = RSSCollector([feed_config])
        articles = await collector.collect()

    assert articles == []
