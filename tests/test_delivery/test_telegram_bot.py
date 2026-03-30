from datetime import date

from src.delivery.telegram_bot import format_card, format_weekly_digest
from src.models import Article, SourceType, Theme


def _make_scored_article(title: str, score: int, themes: list[Theme]) -> Article:
    a = Article(
        source_type=SourceType.RSS,
        source_name="securelist",
        source_url="https://securelist.com/test",
        title=title,
        content_text="body",
    )
    a.ai_score = score
    a.ai_themes = themes
    a.ai_key_points = ["First key point", "Second key point"]
    a.ai_angle = "Compare with your own experience"
    return a


def test_format_card_with_ai_score():
    a = _make_scored_article("Test Article", 4, [Theme.AI_CYBERSEC, Theme.THREAT_INTEL])
    text = format_card(a)

    assert "AI x Cybersec" in text
    assert "Threat Intel" in text
    assert "4/5" in text
    assert "<b>" in text  # HTML formatting
    assert "First key point" in text
    assert "Compare with your own experience" in text


def test_format_card_keyword_only():
    a = Article(
        source_type=SourceType.RSS,
        source_name="test",
        source_url="https://example.com/1",
        title="Keyword Only Article",
        content_text="body",
    )
    a.keyword_score = 0.65
    a.keyword_themes = [Theme.DFIR]
    text = format_card(a)

    assert "KW Score: 0.65" in text
    assert "DFIR" in text


def test_format_card_escapes_html():
    a = _make_scored_article("Title with <script> & \"quotes\"", 3, [Theme.DFIR])
    text = format_card(a)

    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "&amp;" in text


def test_format_card_truncates_long():
    long_title = "A" * 5000
    a = _make_scored_article(long_title, 3, [Theme.DFIR])
    text = format_card(a)

    assert len(text) <= 4096
    assert text.endswith("...")


def test_format_weekly_digest():
    articles = [
        _make_scored_article("Top Article", 5, [Theme.AI_CYBERSEC]),
        _make_scored_article("Second Article", 4, [Theme.THREAT_INTEL]),
        _make_scored_article("Third Article", 3, [Theme.DFIR]),
    ]

    text = format_weekly_digest(articles, date(2026, 3, 24), date(2026, 3, 30))

    assert "24.03 - 30.03.2026" in text
    assert "Top Article" in text
    assert "Total collected: 3" in text
