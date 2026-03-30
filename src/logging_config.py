import logging
import sys
from pathlib import Path


def setup_logging(log_level: str = "INFO") -> None:
    log_format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"

    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(exist_ok=True)

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(data_dir / "pipeline.log", encoding="utf-8"),
    ]

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format=log_format,
        handlers=handlers,
    )

    for noisy in ("httpx", "telegram", "feedparser", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
