#!/usr/bin/env python3
"""
Core data models for BTC Basis Trade analysis.

Extracted from btc_basis_trade_analyzer.py
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Signal(Enum):
    """Trading signals for basis trade strategy."""

    STRONG_ENTRY = "STRONG_ENTRY"
    ACCEPTABLE_ENTRY = "ACCEPTABLE_ENTRY"
    NO_ENTRY = "NO_ENTRY"
    PARTIAL_EXIT = "PARTIAL_EXIT"
    FULL_EXIT = "FULL_EXIT"
    STOP_LOSS = "STOP_LOSS"
    HOLD = "HOLD"


@dataclass
class TradeConfig:
    """Configuration for basis trade strategy."""

    account_size: float = 200_000
    spot_target_pct: float = 0.50  # 50% of account
    futures_target_pct: float = 0.50
    funding_cost_annual: float = 0.05  # 5% annualized
    leverage: float = 1.0
    cme_contract_size: float = 5.0  # BTC per standard contract
    min_monthly_basis: float = 0.005  # 0.5% minimum

    @property
    def spot_target_amount(self) -> float:
        """Target amount for spot leg."""
        return self.account_size * self.spot_target_pct

    @property
    def futures_target_amount(self) -> float:
        """Target amount for futures leg."""
        return self.account_size * self.futures_target_pct

    @classmethod
    def from_dict(cls, data: dict) -> "TradeConfig":
        """Create TradeConfig from dictionary."""
        return cls(
            account_size=data.get("account_size", 200_000),
            spot_target_pct=data.get("spot_target_pct", 0.50),
            futures_target_pct=data.get("futures_target_pct", 0.50),
            funding_cost_annual=data.get("funding_cost_annual", 0.05),
            leverage=data.get("leverage", 1.0),
            cme_contract_size=data.get("cme_contract_size", 5.0),
            min_monthly_basis=data.get("min_monthly_basis", 0.005),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "account_size": self.account_size,
            "spot_target_pct": self.spot_target_pct,
            "futures_target_pct": self.futures_target_pct,
            "funding_cost_annual": self.funding_cost_annual,
            "leverage": self.leverage,
            "cme_contract_size": self.cme_contract_size,
            "min_monthly_basis": self.min_monthly_basis,
        }


@dataclass
class MarketData:
    """Market data for basis trade analysis."""

    spot_price: float
    futures_price: float
    futures_expiry_date: datetime
    etf_price: Optional[float] = None
    etf_nav: Optional[float] = None
    fear_greed_index: Optional[float] = None
    cme_open_interest: Optional[float] = None
    as_of_date: Optional[datetime] = None  # For backtesting; defaults to now()

    @property
    def basis_absolute(self) -> float:
        """Absolute basis in dollars."""
        return self.futures_price - self.spot_price

    @property
    def basis_percent(self) -> float:
        """Basis as percentage of spot."""
        return self.basis_absolute / self.spot_price

    @property
    def days_to_expiry(self) -> int:
        """Days until futures expiry."""
        reference_date = self.as_of_date if self.as_of_date else datetime.now()
        return (self.futures_expiry_date - reference_date).days

    @property
    def monthly_basis(self) -> float:
        """Normalized to 30-day basis."""
        if self.days_to_expiry == 0:
            return 0.0
        return self.basis_percent * (30 / self.days_to_expiry)

    @property
    def annualized_basis(self) -> float:
        """Annualized basis percentage."""
        if self.days_to_expiry == 0:
            return 0.0
        return self.basis_percent * (365 / self.days_to_expiry)

    @property
    def etf_discount_premium(self) -> Optional[float]:
        """ETF discount/premium vs NAV."""
        if self.etf_price and self.etf_nav:
            return (self.etf_price - self.etf_nav) / self.etf_nav
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "spot_price": self.spot_price,
            "futures_price": self.futures_price,
            "futures_expiry": self.futures_expiry_date.isoformat(),
            "etf_price": self.etf_price,
            "etf_nav": self.etf_nav,
            "fear_greed_index": self.fear_greed_index,
            "cme_open_interest": self.cme_open_interest,
            "basis_absolute": self.basis_absolute,
            "basis_percent": self.basis_percent,
            "monthly_basis": self.monthly_basis,
            "days_to_expiry": self.days_to_expiry,
        }
