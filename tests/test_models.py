from src.models import Article, SourceType, Theme


def test_content_hash_deterministic():
    a1 = Article(
        source_type=SourceType.RSS,
        source_name="test",
        source_url="https://example.com/1",
        title="Test",
        content_text="body",
    )
    a2 = Article(
        source_type=SourceType.RSS,
        source_name="test",
        source_url="https://example.com/1",
        title="Different Title",
        content_text="different body",
    )
    assert a1.content_hash == a2.content_hash


def test_content_hash_differs_by_url():
    a1 = Article(
        source_type=SourceType.RSS,
        source_name="test",
        source_url="https://example.com/1",
        title="Test",
        content_text="body",
    )
    a2 = Article(
        source_type=SourceType.RSS,
        source_name="test",
        source_url="https://example.com/2",
        title="Test",
        content_text="body",
    )
    assert a1.content_hash != a2.content_hash


def test_content_hash_differs_by_source_type():
    a1 = Article(
        source_type=SourceType.RSS,
        source_name="test",
        source_url="https://example.com/1",
        title="Test",
        content_text="body",
    )
    a2 = Article(
        source_type=SourceType.TELEGRAM,
        source_name="test",
        source_url="https://example.com/1",
        title="Test",
        content_text="body",
    )
    assert a1.content_hash != a2.content_hash


def test_is_publishable_ai_score():
    a = Article(
        source_type=SourceType.RSS,
        source_name="test",
        source_url="https://example.com/1",
        title="Test",
        content_text="body",
    )
    a.ai_score = 3
    assert a.is_publishable is True

    a.ai_score = 2
    assert a.is_publishable is False


def test_is_publishable_keyword_fallback():
    a = Article(
        source_type=SourceType.RSS,
        source_name="test",
        source_url="https://example.com/1",
        title="Test",
        content_text="body",
    )
    a.keyword_score = 0.5
    assert a.is_publishable is True

    a.keyword_score = 0.3
    assert a.is_publishable is False


def test_is_priority():
    a = Article(
        source_type=SourceType.RSS,
        source_name="test",
        source_url="https://example.com/1",
        title="Test",
        content_text="body",
    )
    a.ai_score = 4
    assert a.is_priority is True

    a.ai_score = 3
    a.is_cross_theme = True
    assert a.is_priority is True

    a.ai_score = 3
    a.is_cross_theme = False
    assert a.is_priority is False


def test_effective_themes_prefers_ai():
    a = Article(
        source_type=SourceType.RSS,
        source_name="test",
        source_url="https://example.com/1",
        title="Test",
        content_text="body",
    )
    a.keyword_themes = [Theme.DFIR]
    a.ai_themes = [Theme.AI_CYBERSEC, Theme.THREAT_INTEL]
    assert a.effective_themes == [Theme.AI_CYBERSEC, Theme.THREAT_INTEL]


def test_effective_themes_falls_back_to_keyword():
    a = Article(
        source_type=SourceType.RSS,
        source_name="test",
        source_url="https://example.com/1",
        title="Test",
        content_text="body",
    )
    a.keyword_themes = [Theme.DFIR]
    assert a.effective_themes == [Theme.DFIR]
