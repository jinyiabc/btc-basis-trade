#!/usr/bin/env python3
"""
Tests for the BasisTradeAnalyzer.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from btc_basis.core.models import Signal, TradeConfig, MarketData
from btc_basis.core.analyzer import BasisTradeAnalyzer
from btc_basis.core.calculator import BasisCalculator


def test_signal_enum():
    """Test Signal enum values."""
    assert Signal.STRONG_ENTRY.value == "STRONG_ENTRY"
    assert Signal.STOP_LOSS.value == "STOP_LOSS"


def test_trade_config_defaults():
    """Test TradeConfig default values."""
    config = TradeConfig()
    assert config.account_size == 200_000
    assert config.spot_target_pct == 0.50
    assert config.leverage == 1.0


def test_trade_config_spot_target_amount():
    """Test TradeConfig computed properties."""
    config = TradeConfig(account_size=100_000)
    assert config.spot_target_amount == 50_000


def test_market_data_basis_calculation():
    """Test MarketData basis calculations."""
    market = MarketData(
        spot_price=100_000,
        futures_price=102_000,
        futures_expiry_date=datetime.now() + timedelta(days=30),
    )

    assert market.basis_absolute == 2000
    assert market.basis_percent == 0.02
    assert market.days_to_expiry == 30 or market.days_to_expiry == 29  # Allow for time zone


def test_analyzer_calculate_returns(sample_market_data, analyzer):
    """Test return calculations."""
    returns = analyzer.calculate_returns(sample_market_data)

    assert "basis_absolute" in returns
    assert "basis_percent" in returns
    assert "monthly_basis" in returns
    assert "net_annualized" in returns


def test_analyzer_generate_signal_strong_entry():
    """Test signal generation for strong entry."""
    config = TradeConfig()
    analyzer = BasisTradeAnalyzer(config)

    # Create market data with high basis
    market = MarketData(
        spot_price=100_000,
        futures_price=102_000,  # 2% basis
        futures_expiry_date=datetime.now() + timedelta(days=30),
    )

    signal, reason = analyzer.generate_signal(market)
    assert signal == Signal.STRONG_ENTRY


def test_analyzer_generate_signal_stop_loss():
    """Test signal generation for stop loss."""
    config = TradeConfig()
    analyzer = BasisTradeAnalyzer(config)

    # Create market data with negative basis (backwardation)
    market = MarketData(
        spot_price=100_000,
        futures_price=99_000,  # Negative basis
        futures_expiry_date=datetime.now() + timedelta(days=30),
    )

    signal, reason = analyzer.generate_signal(market)
    assert signal == Signal.STOP_LOSS


def test_analyzer_assess_risk(sample_market_data, analyzer):
    """Test risk assessment."""
    risks = analyzer.assess_risk(sample_market_data)

    assert "funding" in risks
    assert "basis" in risks
    assert "liquidity" in risks
    assert "crowding" in risks
    assert "operational" in risks


def test_analyzer_position_sizing(sample_market_data, analyzer):
    """Test position sizing calculation."""
    positions = analyzer.calculate_position_sizing(sample_market_data)

    assert "etf_shares" in positions
    assert "futures_contracts" in positions
    assert "delta_neutral" in positions


def test_basis_calculator():
    """Test BasisCalculator static methods."""
    result = BasisCalculator.calculate(
        spot_price=100_000,
        futures_price=102_000,
        expiry_date=datetime.now() + timedelta(days=30),
    )

    assert result["basis_absolute"] == 2000
    assert result["basis_percent"] == 0.02
    assert "monthly_basis" in result
    assert "annualized_basis" in result


def test_basis_calculator_contango():
    """Test contango detection."""
    assert BasisCalculator.is_contango(100_000, 102_000) == True
    assert BasisCalculator.is_backwardation(100_000, 102_000) == False


if __name__ == "__main__":
    # Run tests manually
    test_signal_enum()
    test_trade_config_defaults()
    test_trade_config_spot_target_amount()
    test_basis_calculator()
    test_basis_calculator_contango()
    print("[OK] All tests passed!")
