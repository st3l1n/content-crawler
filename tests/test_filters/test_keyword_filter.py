from src.filters.keyword_filter import KeywordFilter
from src.models import Article, ArticleStatus, SourceType, Theme


KEYWORDS = {
    "ai_cybersec": ["LLM", "Claude", "prompt injection", "AI agent"],
    "threat_intel": ["APT", "threat actor", "MITRE ATT&CK", "IOC", "zero-day"],
    "dfir": ["forensic", "incident response", "volatility", "timeline"],
    "psych_cybersec": ["cognitive bias", "human factor", "security fatigue"],
}


def _make_article(title: str, text: str) -> Article:
    return Article(
        source_type=SourceType.RSS,
        source_name="test",
        source_url=f"https://example.com/{hash(title)}",
        title=title,
        content_text=text,
    )


def test_matches_single_theme():
    f = KeywordFilter(KEYWORDS)
    a = _make_article(
        "New APT Campaign Found",
        "Threat actor deploys zero-day exploit with IOC indicators and MITRE ATT&CK mapping",
    )
    f.filter_article(a)
    assert Theme.THREAT_INTEL in a.keyword_themes
    assert a.status != ArticleStatus.FILTERED_OUT


def test_cross_theme_detection():
    f = KeywordFilter(KEYWORDS)
    a = _make_article(
        "LLM for APT Analysis",
        "Using Claude to analyze APT threat actor TTPs with MITRE ATT&CK framework. "
        "Prompt injection risks when processing IOC data with AI agent.",
    )
    f.filter_article(a)
    assert Theme.AI_CYBERSEC in a.keyword_themes
    assert Theme.THREAT_INTEL in a.keyword_themes
    assert a.is_cross_theme is True


def test_filtered_out_no_matches():
    f = KeywordFilter(KEYWORDS)
    a = _make_article(
        "Company Quarterly Earnings Report",
        "Revenue increased 15% year over year. New office opened in London.",
    )
    f.filter_article(a)
    assert a.status == ArticleStatus.FILTERED_OUT
    assert a.keyword_themes == []


def test_word_boundary():
    f = KeywordFilter(KEYWORDS)
    # "AI" inside "WAIT" should not match
    a = _make_article(
        "WAITING for updates",
        "The WAITING room was full. CLAIMED responsibilities.",
    )
    f.filter_article(a)
    assert a.keyword_score == 0.0


def test_case_insensitive():
    f = KeywordFilter(KEYWORDS)
    a = _make_article(
        "llm security research",
        "claude and prompt injection vulnerabilities in ai agent systems",
    )
    f.filter_article(a)
    assert Theme.AI_CYBERSEC in a.keyword_themes


def test_batch_filter():
    f = KeywordFilter(KEYWORDS)
    articles = [
        _make_article("APT Analysis with Claude", "LLM threat actor APT zero-day IOC analysis"),
        _make_article("Cooking Recipe", "How to cook pasta with tomato sauce"),
    ]
    result = f.filter_batch(articles)
    assert len(result) == 2
    assert result[0].status != ArticleStatus.FILTERED_OUT
    assert result[1].status == ArticleStatus.FILTERED_OUT
