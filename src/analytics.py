from __future__ import annotations

import sqlite3


def source_effectiveness(conn: sqlite3.Connection) -> list[dict]:
    """Which sources produce the most high-scoring articles."""
    rows = conn.execute(
        """SELECT source_name, source_type,
                  COUNT(*) as total,
                  SUM(CASE WHEN ai_score >= 4 THEN 1 ELSE 0 END) as high_score,
                  SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered,
                  ROUND(AVG(CASE WHEN ai_score IS NOT NULL THEN ai_score END), 2) as avg_score
           FROM articles
           GROUP BY source_name, source_type
           ORDER BY high_score DESC, avg_score DESC"""
    ).fetchall()
    return [dict(row) for row in rows]


def theme_distribution(conn: sqlite3.Connection) -> list[dict]:
    """Count articles per theme (from keyword_themes JSON)."""
    rows = conn.execute(
        """WITH themes AS (
               SELECT value as theme
               FROM articles, json_each(articles.keyword_themes)
               WHERE keyword_themes IS NOT NULL AND keyword_themes != '[]'
           )
           SELECT theme, COUNT(*) as count
           FROM themes
           GROUP BY theme
           ORDER BY count DESC"""
    ).fetchall()
    return [dict(row) for row in rows]


def delivery_rate(conn: sqlite3.Connection) -> dict:
    """Collected vs filtered vs delivered ratio."""
    row = conn.execute(
        """SELECT
               COUNT(*) as total,
               SUM(CASE WHEN status = 'filtered_out' THEN 1 ELSE 0 END) as filtered_out,
               SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered,
               SUM(CASE WHEN status = 'scored' THEN 1 ELSE 0 END) as scored,
               SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved
           FROM articles"""
    ).fetchone()
    return dict(row)


def api_cost_report(conn: sqlite3.Connection) -> dict:
    """API spending breakdown."""
    today = conn.execute(
        """SELECT COUNT(*) as calls,
                  COALESCE(SUM(input_tokens), 0) as input_tokens,
                  COALESCE(SUM(output_tokens), 0) as output_tokens,
                  COALESCE(SUM(cost_usd), 0) as cost_usd
           FROM api_usage WHERE called_at >= date('now')"""
    ).fetchone()

    month = conn.execute(
        """SELECT COUNT(*) as calls,
                  COALESCE(SUM(input_tokens), 0) as input_tokens,
                  COALESCE(SUM(output_tokens), 0) as output_tokens,
                  COALESCE(SUM(cost_usd), 0) as cost_usd
           FROM api_usage WHERE called_at >= date('now', 'start of month')"""
    ).fetchone()

    total = conn.execute(
        """SELECT COUNT(*) as calls,
                  COALESCE(SUM(input_tokens), 0) as input_tokens,
                  COALESCE(SUM(output_tokens), 0) as output_tokens,
                  COALESCE(SUM(cost_usd), 0) as cost_usd
           FROM api_usage"""
    ).fetchone()

    return {"today": dict(today), "month": dict(month), "total": dict(total)}


def pipeline_history(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """Recent pipeline runs."""
    rows = conn.execute(
        """SELECT run_type, started_at, finished_at,
                  articles_collected, articles_passed, articles_delivered,
                  errors_count
           FROM pipeline_runs
           ORDER BY started_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def print_report(conn: sqlite3.Connection) -> str:
    """Generate a full text report."""
    lines: list[str] = []

    lines.append("=== Source Effectiveness ===")
    for s in source_effectiveness(conn):
        lines.append(
            f"  {s['source_name']:25s} | total: {s['total']:3d} | "
            f"high: {s['high_score']:2d} | delivered: {s['delivered']:2d} | "
            f"avg: {s['avg_score'] or '-':>5s}"
        )

    lines.append("\n=== Theme Distribution ===")
    for t in theme_distribution(conn):
        lines.append(f"  {t['theme']:20s} | {t['count']:3d} articles")

    lines.append("\n=== Delivery Rate ===")
    dr = delivery_rate(conn)
    lines.append(
        f"  Total: {dr['total']} | Filtered out: {dr['filtered_out']} | "
        f"Scored: {dr['scored']} | Delivered: {dr['delivered']}"
    )

    lines.append("\n=== API Cost ===")
    costs = api_cost_report(conn)
    for period, data in costs.items():
        lines.append(
            f"  {period:6s} | calls: {data['calls']:4d} | "
            f"tokens: {data['input_tokens']:7d} in / {data['output_tokens']:6d} out | "
            f"cost: ${data['cost_usd']:.4f}"
        )

    lines.append("\n=== Recent Runs ===")
    for r in pipeline_history(conn, limit=5):
        lines.append(
            f"  {r['started_at']} | {r['run_type']:7s} | "
            f"collected: {r['articles_collected']:3d} | passed: {r['articles_passed']:3d} | "
            f"delivered: {r['articles_delivered']:2d} | errors: {r['errors_count']}"
        )

    report = "\n".join(lines)
    print(report)
    return report
