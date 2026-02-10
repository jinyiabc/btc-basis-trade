#!/usr/bin/env python3
"""
Tests for the backtesting engine.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from btc_basis.core.models import TradeConfig
from btc_basis.backtest.engine import Backtester, Trade, BacktestResult
from btc_basis.backtest.costs import TradingCosts, calculate_comprehensive_costs


def test_trade_dataclass():
    """Test Trade dataclass."""
    trade = Trade(
        entry_date=datetime(2024, 1, 1),
        entry_spot=50000,
        entry_futures=51000,
        entry_basis=1000,
    )

    assert trade.status == "open"
    assert trade.holding_days == 0


def test_trade_with_exit():
    """Test Trade with exit data."""
    trade = Trade(
        entry_date=datetime(2024, 1, 1),
        entry_spot=50000,
        entry_futures=51000,
        entry_basis=1000,
        exit_date=datetime(2024, 1, 31),
        exit_spot=51000,
        exit_futures=51000,
        exit_basis=0,
        realized_pnl=1000,
        status="closed",
    )

    assert trade.holding_days == 30
    assert trade.return_pct == 0.02  # 1000 / 50000


def test_backtest_result():
    """Test BacktestResult dataclass."""
    result = BacktestResult(
        initial_capital=100_000,
        total_trades=10,
        winning_trades=7,
        losing_trades=3,
    )

    assert result.win_rate == 0.7


def test_backtester_generate_sample_data():
    """Test sample data generation."""
    config = TradeConfig()
    backtester = Backtester(config)

    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 31)

    data = backtester.generate_sample_data(start, end)

    assert len(data) == 31
    assert "date" in data[0]
    assert "spot_price" in data[0]
    assert "futures_price" in data[0]


def test_backtester_run_backtest():
    """Test running a backtest."""
    config = TradeConfig()
    backtester = Backtester(config)

    start = datetime(2024, 1, 1)
    end = datetime(2024, 3, 31)

    data = backtester.generate_sample_data(start, end)
    result = backtester.run_backtest(data)

    assert result.start_date == start
    assert result.initial_capital == config.account_size


def test_trading_costs():
    """Test TradingCosts dataclass."""
    costs = TradingCosts(
        spot_entry_commission=10,
        futures_entry_commission=5,
    )

    assert costs.total_entry_costs == 15


def test_calculate_comprehensive_costs():
    """Test comprehensive cost calculation."""
    costs = calculate_comprehensive_costs(
        entry_spot=50000,
        exit_spot=50000,
        entry_futures=51000,
        exit_futures=50000,
        position_size=1.0,
        holding_days=30,
        use_etf=True,
    )

    assert "total_entry_costs" in costs
    assert "total_exit_costs" in costs
    assert "funding_cost" in costs
    assert "total_all_costs" in costs


if __name__ == "__main__":
    test_trade_dataclass()
    test_trade_with_exit()
    test_backtest_result()
    test_backtester_generate_sample_data()
    test_trading_costs()
    test_calculate_comprehensive_costs()
    print("[OK] All backtest tests passed!")
