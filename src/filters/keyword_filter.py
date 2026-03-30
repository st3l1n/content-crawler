from __future__ import annotations

import re
from dataclasses import dataclass

from src.models import Article, ArticleStatus, Theme

FILTER_OUT_THRESHOLD = 0.2


@dataclass
class _ThemePattern:
    theme: Theme
    patterns: list[re.Pattern[str]]


class KeywordFilter:
    def __init__(self, keywords: dict[str, list[str]]) -> None:
        self._theme_patterns: list[_ThemePattern] = []
        self._total_keywords = 0

        for theme_name, kw_list in keywords.items():
            try:
                theme = Theme(theme_name)
            except ValueError:
                continue

            patterns = []
            for kw in kw_list:
                escaped = re.escape(kw)
                pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
                patterns.append(pattern)
                self._total_keywords += 1

            self._theme_patterns.append(_ThemePattern(theme=theme, patterns=patterns))

    def filter_article(self, article: Article) -> Article:
        text = f"{article.title} {article.content_text}"
        total_matches = 0
        matched_themes: list[Theme] = []

        for tp in self._theme_patterns:
            theme_matches = 0
            for pattern in tp.patterns:
                if pattern.search(text):
                    theme_matches += 1

            if theme_matches >= 2:
                matched_themes.append(tp.theme)
            total_matches += theme_matches

        article.keyword_score = (
            total_matches / self._total_keywords if self._total_keywords else 0.0
        )
        article.keyword_themes = matched_themes
        article.is_cross_theme = len(matched_themes) >= 2

        if not matched_themes and article.keyword_score < FILTER_OUT_THRESHOLD:
            article.status = ArticleStatus.FILTERED_OUT

        return article

    def filter_batch(self, articles: list[Article]) -> list[Article]:
        return [self.filter_article(a) for a in articles]
