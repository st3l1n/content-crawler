from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from src.models import Article, ArticleStatus, PipelineRun, SourceType, Theme

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash    TEXT UNIQUE NOT NULL,
    source_type     TEXT NOT NULL CHECK (source_type IN ('rss', 'telegram', 'arxiv')),
    source_name     TEXT NOT NULL,
    source_url      TEXT NOT NULL,
    title           TEXT NOT NULL,
    content_text    TEXT,
    language        TEXT DEFAULT 'en',
    collected_at    TEXT NOT NULL,
    published_at    TEXT,
    keyword_score   REAL DEFAULT 0.0,
    keyword_themes  TEXT,
    ai_score        INTEGER,
    ai_themes       TEXT,
    ai_key_points   TEXT,
    ai_angle        TEXT,
    is_cross_theme  INTEGER DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'new',
    delivered_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_collected_at ON articles(collected_at);
CREATE INDEX IF NOT EXISTS idx_articles_ai_score ON articles(ai_score);

CREATE TABLE IF NOT EXISTS delivery_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id      INTEGER NOT NULL REFERENCES articles(id),
    telegram_msg_id INTEGER,
    chat_id         TEXT NOT NULL,
    message_type    TEXT NOT NULL CHECK (message_type IN ('card', 'digest')),
    sent_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    error           TEXT
);

CREATE INDEX IF NOT EXISTS idx_delivery_article ON delivery_log(article_id);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type            TEXT NOT NULL,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    articles_collected  INTEGER DEFAULT 0,
    articles_passed     INTEGER DEFAULT 0,
    articles_delivered  INTEGER DEFAULT 0,
    errors_count        INTEGER DEFAULT 0,
    error_details       TEXT
);

CREATE TABLE IF NOT EXISTS api_usage (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    called_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    model           TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL,
    output_tokens   INTEGER NOT NULL,
    cost_usd        REAL NOT NULL,
    article_title   TEXT,
    success         INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_api_usage_called_at ON api_usage(called_at);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def _iso(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%dT%H:%M:%S") if dt else None


def _themes_json(themes: list[Theme]) -> str:
    return json.dumps([t.value for t in themes])


def is_duplicate(conn: sqlite3.Connection, content_hash: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM articles WHERE content_hash = ?", (content_hash,)
    ).fetchone()
    return row is not None


def save_article(conn: sqlite3.Connection, article: Article) -> int | None:
    try:
        cursor = conn.execute(
            """INSERT INTO articles
               (content_hash, source_type, source_name, source_url, title, content_text,
                language, collected_at, published_at, keyword_score, keyword_themes,
                ai_score, ai_themes, ai_key_points, ai_angle, is_cross_theme, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                article.content_hash,
                article.source_type.value,
                article.source_name,
                article.source_url,
                article.title,
                article.content_text,
                article.language,
                _iso(article.collected_at),
                _iso(article.published_at),
                article.keyword_score,
                _themes_json(article.keyword_themes),
                article.ai_score,
                _themes_json(article.ai_themes),
                json.dumps(article.ai_key_points),
                article.ai_angle,
                int(article.is_cross_theme),
                article.status.value,
            ),
        )
        conn.commit()
        article.db_id = cursor.lastrowid
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def update_article_status(
    conn: sqlite3.Connection,
    db_id: int,
    status: ArticleStatus,
    **kwargs: str | int | float | None,
) -> None:
    sets = ["status = ?"]
    values: list[str | int | float | None] = [status.value]

    for key, val in kwargs.items():
        sets.append(f"{key} = ?")
        values.append(val)

    values.append(db_id)
    conn.execute(f"UPDATE articles SET {', '.join(sets)} WHERE id = ?", values)
    conn.commit()


def _row_to_article(row: sqlite3.Row) -> Article:
    article = Article(
        source_type=SourceType(row["source_type"]),
        source_name=row["source_name"],
        source_url=row["source_url"],
        title=row["title"],
        content_text=row["content_text"] or "",
        published_at=(
            datetime.fromisoformat(row["published_at"]) if row["published_at"] else None
        ),
        language=row["language"] or "en",
    )
    article.db_id = row["id"]
    article.keyword_score = row["keyword_score"] or 0.0
    article.keyword_themes = [Theme(t) for t in json.loads(row["keyword_themes"] or "[]")]
    article.ai_score = row["ai_score"]
    article.ai_themes = [Theme(t) for t in json.loads(row["ai_themes"] or "[]")]
    article.ai_key_points = json.loads(row["ai_key_points"] or "[]")
    article.ai_angle = row["ai_angle"] or ""
    article.is_cross_theme = bool(row["is_cross_theme"])
    article.status = ArticleStatus(row["status"])
    return article


def get_articles_by_status(
    conn: sqlite3.Connection, status: ArticleStatus
) -> list[Article]:
    rows = conn.execute(
        "SELECT * FROM articles WHERE status = ? ORDER BY keyword_score DESC",
        (status.value,),
    ).fetchall()
    return [_row_to_article(row) for row in rows]


def log_delivery(
    conn: sqlite3.Connection,
    article_id: int,
    telegram_msg_id: int | None,
    chat_id: str,
    message_type: str = "card",
    error: str | None = None,
) -> None:
    conn.execute(
        """INSERT INTO delivery_log (article_id, telegram_msg_id, chat_id, message_type, error)
           VALUES (?, ?, ?, ?, ?)""",
        (article_id, telegram_msg_id, chat_id, message_type, error),
    )
    conn.commit()


def log_api_usage(
    conn: sqlite3.Connection,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    article_title: str = "",
    success: bool = True,
) -> None:
    conn.execute(
        """INSERT INTO api_usage (model, input_tokens, output_tokens, cost_usd, article_title, success)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (model, input_tokens, output_tokens, cost_usd, article_title, int(success)),
    )
    conn.commit()


def get_cost_today(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM api_usage WHERE called_at >= date('now')"
    ).fetchone()
    return row[0]


def get_cost_month(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM api_usage WHERE called_at >= date('now', 'start of month')"
    ).fetchone()
    return row[0]


def get_usage_stats(conn: sqlite3.Connection) -> dict:
    today = conn.execute(
        """SELECT COUNT(*) as calls, COALESCE(SUM(input_tokens), 0) as inp,
                  COALESCE(SUM(output_tokens), 0) as out, COALESCE(SUM(cost_usd), 0) as cost
           FROM api_usage WHERE called_at >= date('now')"""
    ).fetchone()
    month = conn.execute(
        """SELECT COUNT(*) as calls, COALESCE(SUM(input_tokens), 0) as inp,
                  COALESCE(SUM(output_tokens), 0) as out, COALESCE(SUM(cost_usd), 0) as cost
           FROM api_usage WHERE called_at >= date('now', 'start of month')"""
    ).fetchone()
    return {
        "today": {"calls": today[0], "input_tokens": today[1], "output_tokens": today[2], "cost_usd": today[3]},
        "month": {"calls": month[0], "input_tokens": month[1], "output_tokens": month[2], "cost_usd": month[3]},
    }


def save_pipeline_run(conn: sqlite3.Connection, run: PipelineRun) -> int:
    cursor = conn.execute(
        """INSERT INTO pipeline_runs
           (run_type, started_at, finished_at, articles_collected,
            articles_passed, articles_delivered, errors_count, error_details)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run.run_type,
            _iso(run.started_at),
            _iso(run.finished_at),
            run.articles_collected,
            run.articles_passed,
            run.articles_delivered,
            len(run.errors),
            json.dumps(run.errors) if run.errors else None,
        ),
    )
    conn.commit()
    run.db_id = cursor.lastrowid
    return cursor.lastrowid
