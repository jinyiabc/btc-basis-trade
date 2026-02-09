"""
BTC Basis Trade Analysis Package

A Python toolkit for analyzing and monitoring cash-and-carry arbitrage
(basis trade) opportunities between Bitcoin spot and futures markets.
"""

__version__ = "1.0.0"
__author__ = "BTC Basis Trade Toolkit"

from btc_basis.core.models import Signal, TradeConfig, MarketData
from btc_basis.core.analyzer import BasisTradeAnalyzer
from btc_basis.core.calculator import BasisCalculator

__all__ = [
    "Signal",
    "TradeConfig",
    "MarketData",
    "BasisTradeAnalyzer",
    "BasisCalculator",
]
