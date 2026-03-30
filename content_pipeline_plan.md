# Контент-конвейер «Синяя шляпа»

## Цель

Автоматизированный сбор глубоких материалов по 5 тематическим линиям → фильтрация → AI-суммаризация → доставка в приватный Telegram-чат. На выходе: 3-7 готовых карточек в день, из которых ты выбираешь темы для постов.

---

## 1. Архитектура системы

```
┌─────────────────────────────────────────────────────┐
│                    ИСТОЧНИКИ                         │
│                                                      │
│  RSS-фиды ──┐                                        │
│  arxiv API ──┼──► Сборщик (Python) ──► SQLite (дедуп)│
│  TG каналы ──┘         │                             │
│                        ▼                             │
│              Фильтр (keywords + scoring)             │
│                        │                             │
│                        ▼                             │
│              Claude API (Haiku) — суммаризация        │
│                        │                             │
│                        ▼                             │
│              Telegram Bot → приватный чат             │
└─────────────────────────────────────────────────────┘
```

**Стек:** Python 3.12+, feedparser, arxiv, httpx/aiohttp (для парсинга t.me/s/), python-telegram-bot, Claude API (Haiku), SQLite, cron/GitHub Actions.

**Расписание:**
- Ежедневно, 08:00 MSK — RSS + Telegram каналы (посты за последние 24ч)
- Воскресенье, 10:00 MSK — arxiv batch (за неделю)

---

## 2. Источники: RSS-фиды

### 2.1 AI × Cybersec

| Источник | URL блога | RSS/Feed |
|----------|-----------|----------|
| Anthropic Blog | https://www.anthropic.com/news | https://www.anthropic.com/rss.xml |
| OpenAI Blog (Security) | https://openai.com/blog | https://openai.com/blog/rss.xml |
| Simon Willison's Blog | https://simonwillison.net | https://simonwillison.net/atom/everything/ |
| AISecHub (Medium) | https://medium.com/ai-security-hub | RSS через medium feed |
| Google Threat Intel | https://cloud.google.com/blog/topics/threat-intelligence | Feed доступен |
| Microsoft Security Blog | https://www.microsoft.com/en-us/security/blog | https://www.microsoft.com/en-us/security/blog/feed/ |
| Darktrace Blog | https://www.darktrace.com/blog | RSS доступен |

### 2.2 Threat Intelligence / Malware Research

| Источник | URL блога | RSS/Feed |
|----------|-----------|----------|
| Google TAG / Mandiant | https://cloud.google.com/blog/topics/threat-intelligence | Feed доступен |
| SentinelLabs | https://www.sentinelone.com/labs/ | https://www.sentinelone.com/labs/feed/ |
| Cisco Talos | https://blog.talosintelligence.com | http://feeds.feedburner.com/feedburner/Talos |
| CrowdStrike Blog | https://www.crowdstrike.com/blog/ | https://www.crowdstrike.com/blog/feed/ |
| Recorded Future | https://www.recordedfuture.com/blog | https://www.recordedfuture.com/feed |
| Securelist (Kaspersky) | https://securelist.com | https://securelist.com/feed/ |
| Unit 42 (Palo Alto) | https://unit42.paloaltonetworks.com | https://unit42.paloaltonetworks.com/feed/ |
| Hunt.io Blog | https://hunt.io/blog | RSS доступен |
| Proofpoint Threat Insight | https://www.proofpoint.com/us/blog/threat-insight | RSS доступен |
| ESET WeLiveSecurity | https://www.welivesecurity.com | https://www.welivesecurity.com/feed/ |

### 2.3 DFIR / Incident Response

| Источник | URL блога | RSS/Feed |
|----------|-----------|----------|
| SANS DFIR Blog | https://www.sans.org/blog/?focus-area=digital-forensics | RSS доступен |
| Velociraptor Blog | https://docs.velociraptor.app/blog/ | RSS доступен |
| 13Cubed (YouTube) | https://www.youtube.com/@13Cubed | YouTube RSS feed |
| DFIR Report | https://thedfirreport.com | https://thedfirreport.com/feed/ |
| Magnet Forensics | https://www.magnetforensics.com/blog/ | RSS доступен |
| Forensafe | https://forensafe.com/blogs.html | RSS доступен |

### 2.4 Вайбкодинг / AI для Cybersec задач

| Источник | URL блога | RSS/Feed |
|----------|-----------|----------|
| Anthropic Engineering | https://www.anthropic.com/engineering | Входит в основной feed |
| LangChain Blog | https://blog.langchain.dev | https://blog.langchain.dev/rss/ |
| Cursor Blog | https://www.cursor.com/blog | RSS если доступен |
| Risky.Biz Newsletter | https://risky.biz | https://risky.biz/feeds/risky-business/ |

### 2.5 Психология × Cybersec

| Источник | URL | Формат |
|----------|-----|--------|
| CybSafe Blog | https://www.cybsafe.com/blog | RSS доступен |
| Cori Faklaris Blog | https://blog.corifaklaris.com | RSS/blog |
| ISACA Journal | https://www.isaca.org/resources/isaca-journal | Нет RSS — парсить вручную или через скрапер |
| Computers in Human Behavior (Elsevier) | ScienceDirect | Через arxiv/Google Scholar alerts |
| J. of Risk Research — cybersec | tandfonline.com | Google Scholar alerts |

**Готовые коллекции RSS для быстрого старта:**
- `muchdogesec/awesome_threat_intel_blogs` — курируемый список с проверенными RSS-ссылками
- `ThreatIntelligenceLab/RSS-Feeds-ThreatIntelligence-Cybersecurity` — ~1400 фидов с health-статусом
- `thehappydinoa/awesome-threat-intel-rss` — компактный список с описаниями
- `EndlessFractal/Threat-Intel-Feed` — готовый агрегированный XML-фид

---

## 3. Источники: Telegram-каналы

Парсинг через `https://t.me/s/{channel_name}` — публичная веб-версия, не требует авторизации.

### 3.1 RU — Исследования, аналитика, мнения (не новостные)

| Канал | @handle | Зачем |
|-------|---------|-------|
| Пост Лукацкого | @alukatsky | Мнения, аналитика, ссылки на исследования. Один из главных агрегаторов смыслов в RU-cybersec |
| SecAtor | @true_secator | Злободневные заметки по ИБ с авторской аналитикой, разборы APT |
| BI.ZONE | @biaboratory | Исследования от BI.ZONE, отчёты по угрозам, APT-трекинг |
| PT Security | @PTsecurity | Positive Technologies — исследования, отчёты, Securelist-стиль |
| CyberSecurityTechnologies | @CyberSecurityTechnologies | Теги по DFIR, Malware Analysis, Research, BlueTeam. Хорошо структурирован |
| 3side кибербезопасности | @By3side | Практические заметки по ИБ, кейсы |
| Backconnect | @b4ckc0nn3ct | Ты уже читаешь. Дайджесты, подкасты |
| in4security | @in4security | OSINT-расследования, анализ схем |
| Утечки информации | @dataleak | Анализ утечек с разбором причин |
| poxek | @poxek | Практика ИБ, инструменты, offensive |
| Киберп****ц | @kirfreed | Технологии и кибербезопасность, авторский стиль |

### 3.2 EN — Исследования, deep technical

| Канал | @handle | Зачем |
|-------|---------|-------|
| vx-underground | @vaboratory | Коллекция семплов ВПО, разборы, исследовательское сообщество |
| The DFIR Report | @thedfirreport | Публичные IR-кейсы с таймлайнами, IOC, TTPs |
| MalwareHunterTeam | Через Twitter/TG | Оперативные находки новых семплов |
| Cyber Threat Intel | @cybaboratory | Агрегация TI-отчётов |

### 3.3 Психология / Human Factors (пересечение)

| Канал/Источник | Описание |
|----------------|----------|
| Профайлинг, нейротехнологии и детекция лжи | TG-канал Алексея Филатова — пересечение психологии и безопасности |
| @psycho_daily | Психология для широкой аудитории — фильтровать по когнитивным искажениям и decision-making |

---

## 4. Источники: arxiv

**API endpoint:** `http://export.arxiv.org/api/query`

**Запросы (раз в неделю):**

```
# AI × Security
cat:cs.CR AND (ti:"LLM" OR ti:"language model" OR ti:"AI agent" OR ti:"prompt injection")

# Human factors × Security
cat:cs.CR AND (ti:"human factor" OR ti:"cognitive" OR ti:"decision making" OR ti:"social engineering")

# DFIR / Forensics
cat:cs.CR AND (ti:"forensic" OR ti:"incident response" OR ti:"memory analysis" OR ti:"malware analysis")
```

**Альтернатива:** Google Scholar Alerts по ключевым фразам — приходит на почту, можно парсить IMAP.

---

## 5. Фильтрация

### 5.1 Keyword Sets (по тематическим линиям)

```python
THEMES = {
    "ai_cybersec": [
        "LLM", "language model", "AI agent", "agentic", "prompt injection",
        "Claude", "GPT", "copilot", "MCP", "RAG", "security AI",
        "adversarial AI", "AI red team", "automated analysis",
        "vibe coding", "AI malware", "AI forensics"
    ],
    "threat_intel": [
        "APT", "campaign", "threat actor", "malware family", "C2",
        "infrastructure", "TTPs", "MITRE ATT&CK", "IOC", "attribution",
        "supply chain", "zero-day", "exploit"
    ],
    "dfir": [
        "forensic", "incident response", "memory dump", "artifact",
        "timeline", "triage", "evidence", "disk image", "volatility",
        "velociraptor", "hayabusa", "plaso", "KAPE"
    ],
    "vibe_coding": [
        "automation", "script", "tool", "pipeline", "integration",
        "Claude Code", "cursor", "aider", "vibe coding",
        "Python security", "DevSecOps"
    ],
    "psych_cybersec": [
        "cognitive bias", "human factor", "decision making",
        "social engineering psychology", "awareness behavior gap",
        "optimism bias", "security fatigue", "burnout",
        "risk perception", "behavioral security"
    ]
}
```

### 5.2 AI Scoring (Claude Haiku)

Промпт для оценки:

```
Оцени статью по шкале 1-5, где:
1 = пересказ новости без глубины
2 = новость с минимальным анализом
3 = обзорная статья с некоторой глубиной
4 = оригинальное исследование / глубокий анализ / авторский кейс
5 = прорывное исследование / уникальный практический опыт

Также определи:
- Тематические линии (из 5): ai_cybersec, threat_intel, dfir, vibe_coding, psych_cybersec
- Пересекает ли 2+ линии (да/нет)
- 2-3 ключевых тезиса (по 1 предложению каждый)
- Потенциальный угол для поста в канале (1 предложение)

Порог публикации: score >= 3
Приоритет: score >= 4 ИЛИ пересечение 2+ линий
```

---

## 6. Формат доставки (Telegram Bot)

### Карточка обычного поста:

```
🔬 [AI × DFIR] Relevance: 4/5
📌 Claude + IDA Pro: автоматический реверс обфусцированного семпла
🔗 https://example.com/article
📡 Источник: SentinelLabs

Ключевое:
• Предлагают MCP-интеграцию для автоматизации статического анализа
• Время анализа сократилось с дней до 30 минут
• Ограничение: контекст модели переполняется на сложных бинарниках

💡 Угол: сравнить с твоим кейсом Claude + IDA, дополнить наблюдением про automation bias
```

### Недельный дайджест (воскресенье):

```
📊 Недельный обзор | 24-30 марта 2026

🔥 Топ-3 по релевантности:
1. [AI×Cybersec] ClawKeeper: Safety for OpenClaw Agents — arxiv (score: 5)
2. [DFIR] Memory forensics meets LLM — SANS Blog (score: 4)
3. [Psych×Cybersec] Cybersecurity Anxiety Scale — CHI 2026 (score: 4)

📈 Тренды недели:
• AI agent security — 7 публикаций (рост)
• MCP/A2A безопасность — новая тема
• Психология + IR — 2 статьи (редкое пересечение)

📚 arxiv за неделю: 12 статей в cs.CR∩cs.AI, 3 прошли порог
```

---

## 7. Техническая реализация

### 7.1 Структура проекта

```
content-pipeline/
├── config/
│   ├── feeds.yaml          # RSS-фиды с метаданными
│   ├── telegram_channels.yaml  # TG-каналы
│   ├── keywords.yaml       # Keyword sets по линиям
│   └── prompts.yaml        # Промпты для Claude API
├── src/
│   ├── collectors/
│   │   ├── rss_collector.py
│   │   ├── telegram_collector.py  # Парсинг t.me/s/
│   │   └── arxiv_collector.py
│   ├── filters/
│   │   ├── keyword_filter.py
│   │   └── ai_scorer.py     # Claude Haiku scoring
│   ├── delivery/
│   │   └── telegram_bot.py
│   ├── storage/
│   │   └── db.py            # SQLite: дедупликация, история
│   └── main.py              # Оркестратор
├── data/
│   └── pipeline.db          # SQLite база
├── .env                     # API keys
└── README.md
```

### 7.2 Парсинг Telegram (t.me/s/)

```python
# Принцип: GET https://t.me/s/{channel} возвращает HTML с последними ~20 постами
# Парсить через BeautifulSoup / selectolax
# Каждый пост имеет div.tgme_widget_message
# Текст в div.tgme_widget_message_text
# Дата в time.datetime (атрибут datetime)
# Ссылка: https://t.me/{channel}/{post_id}

# Ограничения:
# - Только последние ~20 постов за один запрос
# - Для пагинации: ?before={post_id}
# - Rate limiting: пауза 2-3 сек между запросами
# - Не работает для закрытых каналов
```

### 7.3 Оценка затрат

| Компонент | Стоимость |
|-----------|-----------|
| Claude API (Haiku) | ~$1-3/мес при 20-50 статей/день |
| Хостинг (VPS) | $0 (использовать существующий для vpn8) |
| GitHub Actions (альтернатива) | $0 (бесплатный tier) |
| Telegram Bot API | $0 |
| **Итого** | **$1-3/мес** |

### 7.4 Оценка времени на разработку (MVP)

| Задача | Часы |
|--------|------|
| RSS collector + feedparser | 1 |
| Telegram collector (t.me/s/ парсер) | 1.5 |
| arxiv API интеграция | 0.5 |
| Keyword filter | 0.5 |
| Claude API scorer/summarizer | 1 |
| Telegram bot доставка | 1 |
| SQLite дедупликация | 0.5 |
| Тестирование + настройка промптов | 1.5 |
| **Итого MVP** | **~7.5 часов** |

---

## 8. Матрица «Стоит ли поста»

Перед написанием поста в канал проверяй по 3 критериям (нужно 2 из 3):

| Критерий | Вопрос |
|----------|--------|
| **Свой угол** | Могу добавить опыт, мнение или контекст, которого нет в материале? |
| **Актуальность** | Тема горячая или набирает обороты прямо сейчас? |
| **Пересечение** | Материал лежит на стыке 2+ моих тем? |

Если набирает только 1 из 3 — не пиши, отложи или сделай репост.

---

## 9. Каденция публикаций

| День | Формат | Описание | Время |
|------|--------|----------|-------|
| Пн-Вт | Заметка | Короткое наблюдение, мысль, связка. 200-500 символов | 20-30 мин |
| Чт-Пт | Разбор | Проработанный пост с логической структурой. 1000-2500 символов | 1-1.5 часа |

**Бюджет времени:** 3-5 часов/неделю (включая потребление дайджестов из пайплайна).

---

## 10. Порядок запуска

### Фаза 1: Минимальный пайплайн (неделя 1)
- [ ] Настроить RSS collector с 10-15 ключевыми фидами
- [ ] Telegram парсер для 5-7 основных каналов
- [ ] Keyword filter (без AI scoring)
- [ ] Telegram bot для доставки
- [ ] Запуск на cron (ежедневно)

### Фаза 2: AI-слой (неделя 2)
- [ ] Подключить Claude API (Haiku) для scoring
- [ ] Настроить промпты и порог фильтрации
- [ ] Добавить формат карточек с «углом для поста»
- [ ] Добавить arxiv collector (еженедельно)

### Фаза 3: Оптимизация (неделя 3+)
- [ ] Тюнинг keyword sets по результатам первых 2 недель
- [ ] Добавить Google Scholar Alerts для психологии
- [ ] Недельный дайджест (воскресенье)
- [ ] Аналитика: какие источники дают больше всего «постабельных» тем

---

## 11. Антипаттерны (чего не делать)

1. **Не собирать 100+ фидов сразу.** Начни с 15-20. Добавляй по мере появления шума или пробелов.
2. **Не писать пост из каждой карточки.** Карточки — сырьё. Пост — переработанный продукт.
3. **Не путать потребление с производством.** Чтение дайджеста ≠ написание поста.
4. **Не делать перфектный пайплайн до первого поста.** MVP → пиши → улучшай.
5. **Не забывать свой опыт.** Лучшие посты в канале — те, где есть «я попробовал и вот что вышло».
