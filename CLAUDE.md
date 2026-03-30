# Content Pipeline — Синяя шляпа

Automated cybersecurity content pipeline: RSS + Telegram + arxiv -> keyword filter -> Claude Haiku scoring -> Telegram delivery.

## Quick start

```bash
uv sync                                    # install deps
cp .env.example .env                       # fill in tokens
uv run python -m src --mode daily           # run daily pipeline
uv run python -m src --mode weekly          # run weekly (incl. arxiv + digest)
```

## Commands

```bash
uv run pytest tests/ -v                     # run tests (43 tests)
uv run ruff check src/ tests/              # lint
uv run python -c "from src.storage.db import get_connection, init_db; from src.analytics import print_report; conn = get_connection('data/pipeline.db'); print_report(conn)"  # analytics report
```

## Architecture

- `src/collectors/` — RSS (feedparser), Telegram (httpx+BS4), arxiv (arxiv lib)
- `src/filters/` — keyword_filter (regex), ai_scorer (Claude Haiku via anthropic SDK)
- `src/delivery/` — Telegram Bot API (python-telegram-bot)
- `src/storage/` — SQLite (articles, delivery_log, pipeline_runs, api_usage)
- `src/cost_tracker.py` — API budget guardrails (daily/monthly limits, per-run cap)
- `src/main.py` — orchestrator with daily/weekly pipelines

## Config

- `config/feeds.yaml` — RSS feed URLs and themes
- `config/telegram_channels.yaml` — TG channel handles
- `config/keywords.yaml` — keyword sets for 5 themes
- `config/prompts.yaml` — Claude API prompt templates
- `.env` — secrets and budget limits (see `.env.example`)

## API cost guardrails

Budget limits are enforced before each Claude API call. Configurable via `.env`:
- `API_DAILY_LIMIT_USD` (default: $0.50)
- `API_MONTHLY_LIMIT_USD` (default: $5.00)
- `API_MAX_CALLS_PER_RUN` (default: 50)
- Telegram alert sent when budget thresholds are hit
