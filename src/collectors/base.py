from __future__ import annotations

import abc

from src.models import Article


class BaseCollector(abc.ABC):
    @abc.abstractmethod
    async def collect(self) -> list[Article]:
        ...
