#!/usr/bin/env python3
"""
Basis calculation utilities.

Consolidated basis calculation logic that was duplicated across 8 files.
"""

from datetime import datetime
from typing import Dict, Any


class BasisCalculator:
    """
    Calculate basis metrics for Bitcoin spot/futures spread.

    This class consolidates basis calculation logic that was previously
    duplicated across multiple files.
    """

    @staticmethod
    def calculate(
        spot_price: float,
        futures_price: float,
        expiry_date: datetime,
        as_of_date: datetime = None,
    ) -> Dict[str, Any]:
        """
        Calculate all basis metrics.

        Args:
            spot_price: Current spot price
            futures_price: Futures contract price
            expiry_date: Futures expiry date
            as_of_date: Reference date (defaults to now)

        Returns:
            Dictionary with all basis calculations
        """
        reference = as_of_date or datetime.now()
        days_to_expiry = (expiry_date - reference).days

        basis_absolute = futures_price - spot_price
        basis_percent = basis_absolute / spot_price if spot_price > 0 else 0

        if days_to_expiry > 0:
            monthly_basis = basis_percent * (30 / days_to_expiry)
            annualized_basis = basis_percent * (365 / days_to_expiry)
        else:
            monthly_basis = 0.0
            annualized_basis = 0.0

        return {
            "basis_absolute": basis_absolute,
            "basis_percent": basis_percent,
            "basis_percent_display": basis_percent * 100,  # For display
            "monthly_basis": monthly_basis,
            "monthly_basis_display": monthly_basis * 100,
            "annualized_basis": annualized_basis,
            "annualized_basis_display": annualized_basis * 100,
            "days_to_expiry": days_to_expiry,
            "spot_price": spot_price,
            "futures_price": futures_price,
            "expiry_date": expiry_date,
        }

    @staticmethod
    def calculate_net_return(
        basis_percent: float,
        days_to_expiry: int,
        funding_cost_annual: float = 0.05,
        leverage: float = 1.0,
    ) -> Dict[str, float]:
        """
        Calculate net returns after funding costs.

        Args:
            basis_percent: Basis as decimal (e.g., 0.02 for 2%)
            days_to_expiry: Days until futures expiry
            funding_cost_annual: Annual funding cost as decimal
            leverage: Leverage multiplier

        Returns:
            Dictionary with return calculations
        """
        if days_to_expiry <= 0:
            return {
                "gross_annualized": 0.0,
                "net_annualized": 0.0,
                "leveraged_return": 0.0,
            }

        gross_annualized = basis_percent * (365 / days_to_expiry)
        net_annualized = gross_annualized - funding_cost_annual
        leveraged_return = net_annualized * leverage

        return {
            "gross_annualized": gross_annualized,
            "gross_annualized_display": gross_annualized * 100,
            "net_annualized": net_annualized,
            "net_annualized_display": net_annualized * 100,
            "leveraged_return": leveraged_return,
            "leveraged_return_display": leveraged_return * 100,
        }

    @staticmethod
    def is_contango(spot_price: float, futures_price: float) -> bool:
        """Check if market is in contango (futures > spot)."""
        return futures_price > spot_price

    @staticmethod
    def is_backwardation(spot_price: float, futures_price: float) -> bool:
        """Check if market is in backwardation (futures < spot)."""
        return futures_price < spot_price
