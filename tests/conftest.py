from __future__ import annotations

import sqlite3

import pytest

from src.models import Article, SourceType
from src.storage.db import init_db


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_article() -> Article:
    return Article(
        source_type=SourceType.RSS,
        source_name="securelist",
        source_url="https://securelist.com/example-post/12345/",
        title="New APT Campaign Targets Financial Sector with AI-Generated Phishing",
        content_text=(
            "Researchers at Securelist discovered a new APT campaign leveraging LLM-generated "
            "phishing emails to target financial institutions. The threat actor used Claude API "
            "to generate convincing spear-phishing messages with zero-day exploit attachments. "
            "MITRE ATT&CK techniques include T1566.001 and T1203. IOC hashes provided."
        ),
        language="en",
    )


@pytest.fixture
def sample_article_ru() -> Article:
    return Article(
        source_type=SourceType.TELEGRAM,
        source_name="@alukatsky",
        source_url="https://t.me/alukatsky/12345",
        title="Cognitive bias in incident response decisions",
        content_text=(
            "Когнитивные искажения при принятии решений в incident response. "
            "Аналитики SOC подвержены optimism bias и security fatigue, "
            "что влияет на decision making при тriage инцидентов."
        ),
        language="ru",
    )
