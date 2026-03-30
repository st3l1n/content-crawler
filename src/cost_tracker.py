from __future__ import annotations

import logging
import sqlite3

from src.config import CostLimits
from src.storage.db import get_cost_month, get_cost_today, log_api_usage

logger = logging.getLogger(__name__)


class BudgetExceeded(Exception):
    pass


class CostTracker:
    def __init__(self, conn: sqlite3.Connection, limits: CostLimits) -> None:
        self.conn = conn
        self.limits = limits
        self._calls_this_run = 0
        self._cost_this_run = 0.0
        self._warned_daily = False
        self._warned_monthly = False

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_cost = (input_tokens / 1_000_000) * self.limits.input_price_per_mtok
        output_cost = (output_tokens / 1_000_000) * self.limits.output_price_per_mtok
        return input_cost + output_cost

    def check_budget(self) -> None:
        """Check all limits before making an API call. Raises BudgetExceeded if any limit hit."""
        # Per-run call limit
        if self._calls_this_run >= self.limits.max_calls_per_run:
            raise BudgetExceeded(
                f"Per-run call limit reached: {self._calls_this_run}/{self.limits.max_calls_per_run}"
            )

        # Daily limit
        cost_today = get_cost_today(self.conn)
        if cost_today >= self.limits.daily_usd:
            raise BudgetExceeded(
                f"Daily budget exhausted: ${cost_today:.4f} / ${self.limits.daily_usd:.2f}"
            )

        # Monthly limit
        cost_month = get_cost_month(self.conn)
        if cost_month >= self.limits.monthly_usd:
            raise BudgetExceeded(
                f"Monthly budget exhausted: ${cost_month:.4f} / ${self.limits.monthly_usd:.2f}"
            )

        # Warnings at threshold
        self._check_warnings(cost_today, cost_month)

    def _check_warnings(self, cost_today: float, cost_month: float) -> None:
        warn_pct = self.limits.warn_at_pct

        if not self._warned_daily and cost_today >= self.limits.daily_usd * warn_pct:
            logger.warning(
                "API cost warning: daily spend at $%.4f / $%.2f (%.0f%%)",
                cost_today,
                self.limits.daily_usd,
                (cost_today / self.limits.daily_usd) * 100,
            )
            self._warned_daily = True

        if not self._warned_monthly and cost_month >= self.limits.monthly_usd * warn_pct:
            logger.warning(
                "API cost warning: monthly spend at $%.4f / $%.2f (%.0f%%)",
                cost_month,
                self.limits.monthly_usd,
                (cost_month / self.limits.monthly_usd) * 100,
            )
            self._warned_monthly = True

    def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        article_title: str = "",
        success: bool = True,
    ) -> float:
        """Record API call usage. Returns cost in USD."""
        cost = self.calculate_cost(input_tokens, output_tokens)

        log_api_usage(
            self.conn,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            article_title=article_title[:200],
            success=success,
        )

        self._calls_this_run += 1
        self._cost_this_run += cost

        logger.debug(
            "API call #%d: %d in / %d out tokens, $%.6f (run total: $%.4f)",
            self._calls_this_run,
            input_tokens,
            output_tokens,
            cost,
            self._cost_this_run,
        )

        return cost

    def get_run_summary(self) -> str:
        cost_today = get_cost_today(self.conn)
        cost_month = get_cost_month(self.conn)
        return (
            f"API usage this run: {self._calls_this_run} calls, ${self._cost_this_run:.4f} | "
            f"Today: ${cost_today:.4f}/${self.limits.daily_usd:.2f} | "
            f"Month: ${cost_month:.4f}/${self.limits.monthly_usd:.2f}"
        )
