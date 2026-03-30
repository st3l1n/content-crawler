import re
from pathlib import Path

import pytest

from src.collectors.telegram_collector import TelegramCollector
from src.config import ChannelConfig
from src.models import SourceType

FIXTURES = Path(__file__).parent.parent / "fixtures"
EMPTY_PAGE = "<html><body><section class='tgme_channel_history'></section></body></html>"


def _mock_tme(httpx_mock, handle: str, html: str):
    """Register mocks for initial page + any pagination requests."""
    httpx_mock.add_response(url=f"https://t.me/s/{handle}", text=html)
    httpx_mock.add_response(
        url=re.compile(rf"https://t\.me/s/{handle}\?before=\d+"),
        text=EMPTY_PAGE,
    )


@pytest.mark.asyncio
async def test_telegram_collector_parses_page(httpx_mock):
    html = (FIXTURES / "sample_tme_page.html").read_text()
    _mock_tme(httpx_mock, "testchannel", html)

    channel = ChannelConfig(handle="testchannel", themes=["threat_intel"], language="en")
    collector = TelegramCollector([channel], hours_back=999999)
    articles = await collector.collect()

    # 3 posts in fixture, but one is too short (<20 chars) -> 2 articles
    assert len(articles) == 2
    assert all(a.source_type == SourceType.TELEGRAM for a in articles)
    assert all(a.source_name == "@testchannel" for a in articles)


@pytest.mark.asyncio
async def test_telegram_collector_extracts_dates(httpx_mock):
    html = (FIXTURES / "sample_tme_page.html").read_text()
    _mock_tme(httpx_mock, "testchannel", html)

    channel = ChannelConfig(handle="testchannel", themes=["threat_intel"], language="en")
    collector = TelegramCollector([channel], hours_back=999999)
    articles = await collector.collect()

    for a in articles:
        assert a.published_at is not None


@pytest.mark.asyncio
async def test_telegram_collector_builds_urls(httpx_mock):
    html = (FIXTURES / "sample_tme_page.html").read_text()
    _mock_tme(httpx_mock, "testchannel", html)

    channel = ChannelConfig(handle="testchannel", themes=["threat_intel"], language="en")
    collector = TelegramCollector([channel], hours_back=999999)
    articles = await collector.collect()

    urls = [a.source_url for a in articles]
    assert "https://t.me/testchannel/100" in urls
    assert "https://t.me/testchannel/99" in urls


@pytest.mark.asyncio
async def test_telegram_collector_handles_http_error(httpx_mock):
    httpx_mock.add_response(url="https://t.me/s/badchannel", status_code=403)

    channel = ChannelConfig(handle="badchannel", themes=[], language="en")
    collector = TelegramCollector([channel])
    articles = await collector.collect()

    assert articles == []
