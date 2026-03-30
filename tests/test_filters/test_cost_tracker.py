import sqlite3

import pytest

from src.config import CostLimits
from src.cost_tracker import BudgetExceeded, CostTracker
from src.storage.db import init_db, log_api_usage


@pytest.fixture
def cost_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    yield conn
    conn.close()


def test_calculate_cost():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    tracker = CostTracker(conn, CostLimits())

    # 1000 input tokens @ $1/MTok = $0.001
    # 500 output tokens @ $5/MTok = $0.0025
    cost = tracker.calculate_cost(1000, 500)
    assert cost == pytest.approx(0.0035)
    conn.close()


def test_per_run_limit(cost_db):
    limits = CostLimits(max_calls_per_run=2)
    tracker = CostTracker(cost_db, limits)

    tracker.record_usage("haiku", 1000, 200, article_title="Test 1")
    tracker.record_usage("haiku", 1000, 200, article_title="Test 2")

    with pytest.raises(BudgetExceeded, match="Per-run call limit"):
        tracker.check_budget()


def test_daily_limit(cost_db):
    limits = CostLimits(daily_usd=0.01, max_calls_per_run=100)
    tracker = CostTracker(cost_db, limits)

    # Pre-fill with enough cost to exceed daily limit
    log_api_usage(cost_db, "haiku", 50000, 5000, 0.015, "Previous")

    with pytest.raises(BudgetExceeded, match="Daily budget"):
        tracker.check_budget()


def test_monthly_limit(cost_db):
    limits = CostLimits(monthly_usd=0.02, daily_usd=10.0, max_calls_per_run=100)
    tracker = CostTracker(cost_db, limits)

    log_api_usage(cost_db, "haiku", 50000, 5000, 0.025, "Previous")

    with pytest.raises(BudgetExceeded, match="Monthly budget"):
        tracker.check_budget()


def test_record_usage_tracks_cost(cost_db):
    tracker = CostTracker(cost_db, CostLimits())

    cost1 = tracker.record_usage("haiku", 1000, 200, article_title="Test 1")
    cost2 = tracker.record_usage("haiku", 2000, 300, article_title="Test 2")

    assert cost1 > 0
    assert cost2 > cost1
    assert tracker._cost_this_run == pytest.approx(cost1 + cost2)
    assert tracker._calls_this_run == 2


def test_run_summary(cost_db):
    tracker = CostTracker(cost_db, CostLimits(daily_usd=1.0, monthly_usd=5.0))
    tracker.record_usage("haiku", 1000, 200, article_title="Test")

    summary = tracker.get_run_summary()
    assert "1 calls" in summary
    assert "Today:" in summary
    assert "Month:" in summary


def test_warning_at_threshold(cost_db, caplog):
    limits = CostLimits(daily_usd=0.01, warn_at_pct=0.8, max_calls_per_run=100)
    tracker = CostTracker(cost_db, limits)

    # Pre-fill to 85% of daily limit
    log_api_usage(cost_db, "haiku", 10000, 1000, 0.0085, "Previous")

    import logging
    with caplog.at_level(logging.WARNING):
        tracker.check_budget()

    assert "daily spend" in caplog.text


def test_budget_ok_when_under_limits(cost_db):
    limits = CostLimits(daily_usd=10.0, monthly_usd=50.0, max_calls_per_run=100)
    tracker = CostTracker(cost_db, limits)

    # Should not raise
    tracker.check_budget()
    tracker.record_usage("haiku", 1000, 200, article_title="Test")
    tracker.check_budget()
