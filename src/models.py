from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SourceType(str, Enum):
    RSS = "rss"
    TELEGRAM = "telegram"
    ARXIV = "arxiv"


class ArticleStatus(str, Enum):
    NEW = "new"
    FILTERED_OUT = "filtered_out"
    SCORED = "scored"
    APPROVED = "approved"
    DELIVERED = "delivered"
    SKIPPED = "skipped"


class Theme(str, Enum):
    AI_CYBERSEC = "ai_cybersec"
    THREAT_INTEL = "threat_intel"
    DFIR = "dfir"
    VIBE_CODING = "vibe_coding"
    PSYCH_CYBERSEC = "psych_cybersec"


@dataclass
class Article:
    source_type: SourceType
    source_name: str
    source_url: str
    title: str
    content_text: str
    published_at: datetime | None = None
    language: str = "en"

    content_hash: str = field(init=False)
    collected_at: datetime = field(default_factory=datetime.utcnow)

    keyword_score: float = 0.0
    keyword_themes: list[Theme] = field(default_factory=list)

    ai_score: int | None = None
    ai_themes: list[Theme] = field(default_factory=list)
    ai_key_points: list[str] = field(default_factory=list)
    ai_angle: str = ""
    is_cross_theme: bool = False

    status: ArticleStatus = ArticleStatus.NEW
    db_id: int | None = None

    def __post_init__(self) -> None:
        raw = f"{self.source_type.value}:{self.source_url}"
        self.content_hash = hashlib.sha256(raw.encode()).hexdigest()

    @property
    def effective_themes(self) -> list[Theme]:
        return self.ai_themes if self.ai_themes else self.keyword_themes

    @property
    def effective_score(self) -> float:
        return float(self.ai_score) if self.ai_score is not None else self.keyword_score

    @property
    def is_publishable(self) -> bool:
        if self.ai_score is not None:
            return self.ai_score >= 3
        return self.keyword_score >= 0.5

    @property
    def is_priority(self) -> bool:
        if self.ai_score is not None:
            return self.ai_score >= 4 or self.is_cross_theme
        return self.keyword_score >= 0.8


@dataclass
class PipelineRun:
    run_type: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    articles_collected: int = 0
    articles_passed: int = 0
    articles_delivered: int = 0
    errors: list[str] = field(default_factory=list)
    db_id: int | None = None
