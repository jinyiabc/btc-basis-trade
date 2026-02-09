#!/usr/bin/env python3
"""
Pytest configuration and fixtures for BTC Basis Trade tests.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def trade_config():
    """Default trade configuration."""
    from btc_basis.core.models import TradeConfig
    return TradeConfig()


@pytest.fixture
def sample_market_data():
    """Sample market data for testing."""
    from btc_basis.core.models import MarketData
    return MarketData(
        spot_price=95000.0,
        futures_price=97200.0,
        futures_expiry_date=datetime.now() + timedelta(days=30),
        etf_price=53.50,
        etf_nav=53.45,
        fear_greed_index=0.75,
        cme_open_interest=35000,
    )


@pytest.fixture
def analyzer(trade_config):
    """BasisTradeAnalyzer instance."""
    from btc_basis.core.analyzer import BasisTradeAnalyzer
    return BasisTradeAnalyzer(trade_config)


@pytest.fixture
def backtester(trade_config):
    """Backtester instance."""
    from btc_basis.backtest.engine import Backtester
    return Backtester(trade_config)
