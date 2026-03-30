from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"


@dataclass(frozen=True)
class FeedConfig:
    name: str
    url: str
    themes: list[str]
    language: str = "en"


@dataclass(frozen=True)
class ChannelConfig:
    handle: str
    themes: list[str]
    language: str = "ru"


@dataclass(frozen=True)
class CostLimits:
    daily_usd: float = 0.50
    monthly_usd: float = 5.00
    max_calls_per_run: int = 50
    warn_at_pct: float = 0.8  # warn when 80% of budget used
    input_price_per_mtok: float = 1.00  # Haiku 4.5 input
    output_price_per_mtok: float = 5.00  # Haiku 4.5 output


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_id: str
    anthropic_api_key: str
    log_level: str
    db_path: Path
    feeds: list[FeedConfig]
    channels: list[ChannelConfig]
    keywords: dict[str, list[str]]
    cost_limits: CostLimits = CostLimits()


_settings: Settings | None = None


def _load_yaml(filename: str) -> dict:
    path = CONFIG_DIR / filename
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_settings() -> Settings:
    global _settings
    if _settings is not None:
        return _settings

    load_dotenv(ROOT_DIR / ".env")

    feeds_data = _load_yaml("feeds.yaml")
    feeds = [FeedConfig(**f) for f in feeds_data.get("feeds", [])]

    channels_data = _load_yaml("telegram_channels.yaml")
    channels = [ChannelConfig(**c) for c in channels_data.get("channels", [])]

    keywords_data = _load_yaml("keywords.yaml")
    keywords = keywords_data.get("themes", {})

    cost_limits = CostLimits(
        daily_usd=float(os.getenv("API_DAILY_LIMIT_USD", "0.50")),
        monthly_usd=float(os.getenv("API_MONTHLY_LIMIT_USD", "5.00")),
        max_calls_per_run=int(os.getenv("API_MAX_CALLS_PER_RUN", "50")),
        warn_at_pct=float(os.getenv("API_WARN_AT_PCT", "0.8")),
        input_price_per_mtok=float(os.getenv("API_INPUT_PRICE_PER_MTOK", "1.00")),
        output_price_per_mtok=float(os.getenv("API_OUTPUT_PRICE_PER_MTOK", "5.00")),
    )

    _settings = Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        db_path=ROOT_DIR / "data" / "pipeline.db",
        feeds=feeds,
        channels=channels,
        keywords=keywords,
        cost_limits=cost_limits,
    )
    return _settings
