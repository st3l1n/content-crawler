# Синяя шляпа — Content Pipeline

Автоматизированный конвейер сбора, фильтрации и доставки материалов по кибербезопасности в приватный Telegram-чат.

**На выходе:** 3-7 готовых карточек в день по 5 тематическим линиям, из которых ты выбираешь темы для постов.

---

## Архитектура

```
┌──────────────────────────────────────────────────────────┐
│                      ИСТОЧНИКИ                           │
│                                                          │
│  RSS-фиды (13) ──┐                                       │
│  TG каналы (7)  ──┼──► Collectors (async) ──► SQLite     │
│  arxiv API (3)  ──┘         │                 (дедуп)    │
│                             ▼                            │
│                   Keyword Filter (regex)                  │
│                             │                            │
│                             ▼                            │
│                   Claude Haiku (scoring 1-5)              │
│                        + guardrails                      │
│                             │                            │
│                             ▼                            │
│                   Telegram Bot → приватный чат            │
└──────────────────────────────────────────────────────────┘
```

## 5 тематических линий

| Тема | Примеры ключевых слов |
|------|----------------------|
| **AI x Cybersec** | LLM, prompt injection, AI agent, Claude, adversarial AI |
| **Threat Intelligence** | APT, threat actor, MITRE ATT&CK, IOC, zero-day |
| **DFIR** | forensic, incident response, volatility, velociraptor, timeline |
| **Vibe Coding** | automation, Claude Code, cursor, DevSecOps, pipeline |
| **Psychology x Cybersec** | cognitive bias, human factor, security fatigue, risk perception |

---

## Быстрый старт

### 1. Установка

```bash
# Клонировать репозиторий
git clone <repo-url>
cd content_crawler

# Установить uv (если нет)
brew install uv    # macOS
# или: curl -LsSf https://astral.sh/uv/install.sh | sh

# Установить зависимости
uv sync
```

### 2. Настройка

```bash
cp .env.example .env
```

Заполнить `.env`:

```env
# Обязательно
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...    # от @BotFather
TELEGRAM_CHAT_ID=-100123456789          # ID приватного чата

# Опционально (без этого работает keyword scoring)
ANTHROPIC_API_KEY=sk-ant-...            # для Claude Haiku scoring

# Бюджетные лимиты API (дефолты)
API_DAILY_LIMIT_USD=0.50
API_MONTHLY_LIMIT_USD=5.00
API_MAX_CALLS_PER_RUN=50
```

#### Как получить Telegram Bot Token

1. Открыть [@BotFather](https://t.me/BotFather) в Telegram
2. Отправить `/newbot`, задать имя
3. Скопировать токен

#### Как узнать Chat ID

1. Добавить бота в приватную группу (или написать боту в ЛС)
2. Отправить любое сообщение
3. Открыть `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Найти `"chat":{"id": ...}` — это `TELEGRAM_CHAT_ID`

### 3. Запуск

```bash
# Ежедневный сбор (RSS + Telegram каналы)
uv run python -m src --mode daily

# Еженедельный сбор (+ arxiv + дайджест)
uv run python -m src --mode weekly

# Ручной запуск (то же что daily, для тестирования)
uv run python -m src --mode manual
```

---

## Расписание

| Когда | Режим | Что делает |
|-------|-------|-----------|
| Ежедневно, 08:00 MSK | `daily` | RSS + TG каналы → фильтрация → scoring → карточки |
| Воскресенье, 10:00 MSK | `weekly` | Всё то же + arxiv за неделю + недельный дайджест |

### Настройка cron (локально)

```cron
# Ежедневно в 08:00 MSK (05:00 UTC)
0 5 * * * cd /path/to/content_crawler && uv run python -m src --mode daily >> data/cron.log 2>&1

# Воскресенье в 10:00 MSK (07:00 UTC)
0 7 * * 0 cd /path/to/content_crawler && uv run python -m src --mode weekly >> data/cron.log 2>&1
```

### GitHub Actions

Готовые workflows лежат в `.github/workflows/`:
- `daily.yml` — запуск каждый день в 05:00 UTC
- `weekly.yml` — запуск каждое воскресенье в 07:00 UTC

Нужно добавить secrets в настройках репозитория:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `ANTHROPIC_API_KEY`

---

## Формат карточек

### Обычная карточка (ежедневно)

```
[AI x Cybersec x Threat Intel] Relevance: 4/5
Claude + IDA Pro: автоматический реверс обфусцированного семпла
Source: SentinelLabs

• Предлагают MCP-интеграцию для автоматизации статического анализа
• Время анализа сократилось с дней до 30 минут
• Ограничение: контекст модели переполняется на сложных бинарниках

Angle: сравнить с твоим кейсом Claude + IDA, дополнить наблюдением про automation bias
```

### Недельный дайджест (воскресенье)

```
Weekly digest | 24.03 - 30.03.2026

Top-3:
1. [AI x Cybersec] ClawKeeper: Safety for OpenClaw Agents (score: 5)
2. [DFIR] Memory forensics meets LLM (score: 4)
3. [Psych x Cybersec] Cybersecurity Anxiety Scale (score: 4)

Trends:
  AI x Cybersec — 12
  Threat Intel — 8
  DFIR — 5

arxiv: 12 papers, 3 passed threshold
Total collected: 47
```

---

## Фильтрация

Двухступенчатая:

### 1. Keyword Filter (всегда)
- Regex-поиск по 5 наборам ключевых слов
- Word boundaries (`\b`) для точного совпадения
- Статья проходит, если 2+ ключевых слова из хотя бы одной темы
- Бонус за пересечение 2+ тем (`is_cross_theme`)

### 2. AI Scoring (если настроен `ANTHROPIC_API_KEY`)
- Claude Haiku оценивает каждую статью по шкале 1-5
- Определяет темы, ключевые тезисы, угол для поста
- Порог публикации: `score >= 3`
- Приоритет: `score >= 4` или пересечение 2+ тем

**Рубрика оценки:**

| Score | Значение |
|-------|---------|
| 1 | Пересказ новости без глубины |
| 2 | Новость с минимальным анализом |
| 3 | Обзорная статья с некоторой глубиной |
| 4 | Оригинальное исследование / глубокий анализ |
| 5 | Прорывное исследование / уникальный опыт |

---

## Контроль расходов API

Каждый вызов Claude API логируется в SQLite таблицу `api_usage` с реальным количеством токенов.

### 3 уровня гардрейлов

| Гардрейл | Дефолт | Поведение |
|----------|--------|-----------|
| Per-run limit | 50 вызовов | Стоп после N вызовов в одном запуске |
| Daily budget | $0.50/день | Стоп при превышении дневного лимита |
| Monthly budget | $5.00/мес | Стоп при превышении месячного лимита |

- Предупреждение в лог при достижении 80% бюджета
- Telegram-алерт при срабатывании гардрейла
- Статьи, не прошедшие scoring из-за бюджета, остаются с keyword score

### Настройка через `.env`

```env
API_DAILY_LIMIT_USD=0.50          # дневной лимит в $
API_MONTHLY_LIMIT_USD=5.00        # месячный лимит в $
API_MAX_CALLS_PER_RUN=50          # макс. вызовов за один запуск
API_WARN_AT_PCT=0.8               # предупреждение при 80% бюджета
API_INPUT_PRICE_PER_MTOK=1.00     # цена input-токенов Haiku ($/MTok)
API_OUTPUT_PRICE_PER_MTOK=5.00    # цена output-токенов Haiku ($/MTok)
```

### Оценка затрат

При ~30 статьях/день, ~1500 input + ~200 output токенов на статью:
- **~$0.05/день** (~$1.50/мес)
- Дефолтных лимитов хватает с 3x запасом

---

## Источники

### RSS-фиды (13 штук)

**AI x Cybersec:** Anthropic Blog, Simon Willison, Google Threat Intel, Microsoft Security

**Threat Intelligence:** SentinelLabs, Cisco Talos, CrowdStrike, Securelist (Kaspersky), Unit 42, WeLiveSecurity

**DFIR:** The DFIR Report

**Vibe Coding:** LangChain Blog, Risky.Biz

Полный список в `config/feeds.yaml`.

### Telegram каналы (7 штук)

**RU:** @alukatsky, @true_secator, @biaboratory, @By3side, @in4security

**EN:** @vaboratory, @thedfirreport

Полный список в `config/telegram_channels.yaml`.

### arxiv (еженедельно)

3 поисковых запроса к категории `cs.CR`:
- AI x Security (LLM, prompt injection, AI agent)
- Human factors (cognitive, social engineering)
- DFIR (forensic, incident response, malware analysis)

---

## Структура проекта

```
content_crawler/
├── CLAUDE.md                          # инструкции для AI-ассистента
├── README.md                          # этот файл
├── pyproject.toml                     # зависимости (uv)
├── .env.example                       # шаблон переменных окружения
├── .gitignore
│
├── config/
│   ├── feeds.yaml                     # RSS-фиды с метаданными
│   ├── telegram_channels.yaml         # TG-каналы
│   ├── keywords.yaml                  # ключевые слова по 5 темам
│   └── prompts.yaml                   # промпты для Claude API
│
├── src/
│   ├── __init__.py
│   ├── __main__.py                    # точка входа: python -m src
│   ├── main.py                        # оркестратор (daily/weekly pipeline)
│   ├── config.py                      # загрузка YAML + .env → Settings
│   ├── models.py                      # Article, Theme, SourceType, ArticleStatus
│   ├── logging_config.py              # stdout + file logging
│   ├── cost_tracker.py                # учёт расходов API + гардрейлы
│   ├── analytics.py                   # отчёты по эффективности
│   │
│   ├── collectors/
│   │   ├── base.py                    # BaseCollector ABC
│   │   ├── rss_collector.py           # feedparser + async
│   │   ├── telegram_collector.py      # httpx + BeautifulSoup
│   │   └── arxiv_collector.py         # arxiv API
│   │
│   ├── filters/
│   │   ├── keyword_filter.py          # regex word boundaries
│   │   └── ai_scorer.py              # Claude Haiku scoring
│   │
│   ├── storage/
│   │   └── db.py                      # SQLite: 4 таблицы
│   │
│   └── delivery/
│       └── telegram_bot.py            # карточки + дайджест
│
├── data/
│   ├── pipeline.db                    # SQLite база (создаётся автоматически)
│   └── pipeline.log                   # лог-файл
│
├── tests/                             # 43 unit-теста
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── sample_rss.xml
│   │   └── sample_tme_page.html
│   ├── test_models.py
│   ├── test_storage/
│   ├── test_collectors/
│   ├── test_filters/
│   └── test_delivery/
│
└── .github/workflows/
    ├── daily.yml                      # GitHub Actions: ежедневно 08:00 MSK
    └── weekly.yml                     # GitHub Actions: воскресенье 10:00 MSK
```

---

## SQLite схема

4 таблицы:

| Таблица | Назначение |
|---------|-----------|
| `articles` | Все собранные статьи, дедупликация через `content_hash UNIQUE` |
| `delivery_log` | Что и когда отправлено в Telegram |
| `pipeline_runs` | История запусков (collected/passed/delivered/errors) |
| `api_usage` | Каждый вызов Claude API (токены, стоимость, статья) |

---

## Аналитика

```bash
uv run python -c "
from src.storage.db import get_connection, init_db
from src.analytics import print_report
conn = get_connection('data/pipeline.db')
print_report(conn)
"
```

Выводит:
- **Source Effectiveness** — какие источники дают больше всего качественных статей
- **Theme Distribution** — распределение по тематическим линиям
- **Delivery Rate** — воронка: collected → filtered → scored → delivered
- **API Cost** — расходы за сегодня / месяц / всё время
- **Recent Runs** — последние 5 запусков пайплайна

---

## Разработка

```bash
# Установить dev-зависимости
uv sync

# Запустить тесты
uv run pytest tests/ -v

# Линтинг
uv run ruff check src/ tests/

# Автофикс линтинга
uv run ruff check src/ tests/ --fix
```

### Стек

| Компонент | Технология |
|-----------|-----------|
| Язык | Python 3.12+ |
| Пакетный менеджер | uv |
| HTTP клиент | httpx (async) |
| RSS парсинг | feedparser |
| HTML парсинг | BeautifulSoup4 |
| AI scoring | anthropic SDK (Claude Haiku) |
| Telegram | python-telegram-bot v22 |
| БД | SQLite (sync) |
| Тесты | pytest + pytest-httpx |
| Линтер | ruff |

---

## Добавление источников

### Новый RSS-фид

Добавить в `config/feeds.yaml`:

```yaml
  - name: new_blog
    url: https://example.com/feed/
    themes: [threat_intel, dfir]
    language: en
```

### Новый Telegram-канал

Добавить в `config/telegram_channels.yaml`:

```yaml
  - handle: channel_name     # без @
    themes: [ai_cybersec]
    language: ru
```

### Новые ключевые слова

Добавить в `config/keywords.yaml` в соответствующую тему:

```yaml
  threat_intel:
    - existing keyword
    - new keyword
```

---

## Лицензия

Private project.
