#!/usr/bin/env python3
"""
Enhanced Cost Calculation for Bitcoin Basis Trade Backtest

This module demonstrates comprehensive cost modeling for basis trades.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class TradingCosts:
    """All costs involved in a basis trade"""

    # Transaction costs (one-time)
    spot_entry_commission: float = 0.0
    spot_exit_commission: float = 0.0
    futures_entry_commission: float = 0.0
    futures_exit_commission: float = 0.0
    etf_entry_commission: float = 0.0
    etf_exit_commission: float = 0.0

    # Slippage costs (one-time)
    spot_entry_slippage: float = 0.0
    spot_exit_slippage: float = 0.0
    futures_entry_slippage: float = 0.0
    futures_exit_slippage: float = 0.0

    # Holding costs (daily/ongoing)
    funding_cost: float = 0.0
    etf_expense_ratio: float = 0.0  # Daily ETF management fee

    @property
    def total_entry_costs(self) -> float:
        """Total costs to enter position"""
        return (self.spot_entry_commission + self.futures_entry_commission +
                self.etf_entry_commission + self.spot_entry_slippage +
                self.futures_entry_slippage)

    @property
    def total_exit_costs(self) -> float:
        """Total costs to exit position"""
        return (self.spot_exit_commission + self.futures_exit_commission +
                self.etf_exit_commission + self.spot_exit_slippage +
                self.futures_exit_slippage)

    @property
    def total_holding_costs(self) -> float:
        """Total holding costs over trade duration"""
        return self.funding_cost + self.etf_expense_ratio

    @property
    def total_costs(self) -> float:
        """All costs combined"""
        return self.total_entry_costs + self.total_exit_costs + self.total_holding_costs


def calculate_comprehensive_costs(
    entry_spot: float,
    exit_spot: float,
    entry_futures: float,
    exit_futures: float,
    position_size: float,
    holding_days: int,
    use_etf: bool = True
) -> Dict[str, float]:
    """
    Calculate all costs for a basis trade

    Args:
        entry_spot: Spot price at entry
        exit_spot: Spot price at exit
        entry_futures: Futures price at entry
        exit_futures: Futures price at exit
        position_size: Position size in BTC
        holding_days: Days trade was held
        use_etf: True if using ETF (IBIT/FBTC), False if direct spot BTC

    Returns:
        Dictionary with detailed cost breakdown
    """

    costs = TradingCosts()

    # ==================================================================
    # 1. COMMISSION COSTS
    # ==================================================================

    if use_etf:
        # ETF Trading (e.g., IBIT via IBKR)
        # Typical: $0.005 per share, min $1, max 1% of trade value
        etf_shares = position_size * entry_spot / 38.5  # Approximate IBIT price
        etf_commission_rate = 0.0005  # 0.05% typical

        costs.etf_entry_commission = max(1, entry_spot * position_size * etf_commission_rate)
        costs.etf_exit_commission = max(1, exit_spot * position_size * etf_commission_rate)
    else:
        # Direct Spot BTC (e.g., Coinbase, Kraken)
        # Maker: 0.40%, Taker: 0.60% (Coinbase Pro tier)
        spot_commission_rate = 0.004  # 0.4% maker fee

        costs.spot_entry_commission = entry_spot * position_size * spot_commission_rate
        costs.spot_exit_commission = exit_spot * position_size * spot_commission_rate

    # CME Bitcoin Futures Commission
    # Typical: $1.50-$2.50 per contract per side
    # 1 contract = 5 BTC, so for 1 BTC we have 0.2 contracts
    contracts = position_size / 5.0
    futures_commission_per_contract = 2.00  # $2 per contract

    costs.futures_entry_commission = contracts * futures_commission_per_contract
    costs.futures_exit_commission = contracts * futures_commission_per_contract

    # ==================================================================
    # 2. SLIPPAGE COSTS
    # ==================================================================

    # Slippage: difference between expected price and actual execution
    # Typically 0.01-0.05% for liquid markets

    if use_etf:
        # ETF slippage (very low, tight spreads)
        etf_slippage_rate = 0.0001  # 0.01% (1 basis point)
        costs.spot_entry_slippage = entry_spot * position_size * etf_slippage_rate
        costs.spot_exit_slippage = exit_spot * position_size * etf_slippage_rate
    else:
        # Spot BTC slippage
        spot_slippage_rate = 0.0005  # 0.05%
        costs.spot_entry_slippage = entry_spot * position_size * spot_slippage_rate
        costs.spot_exit_slippage = exit_spot * position_size * spot_slippage_rate

    # Futures slippage (CME is very liquid)
    futures_slippage_rate = 0.0002  # 0.02%
    costs.futures_entry_slippage = entry_futures * position_size * futures_slippage_rate
    costs.futures_exit_slippage = exit_futures * position_size * futures_slippage_rate

    # ==================================================================
    # 3. FUNDING COST (HOLDING COST)
    # ==================================================================

    # Cost of borrowing to buy spot BTC
    # SOFR + spread: typically 4-5% annual
    funding_rate_annual = 0.05  # 5% annual
    position_value = entry_spot * position_size

    costs.funding_cost = (funding_rate_annual / 365) * holding_days * position_value

    # ==================================================================
    # 4. ETF EXPENSE RATIO (if using ETF)
    # ==================================================================

    if use_etf:
        # IBIT expense ratio: 0.25% annual
        # FBTC expense ratio: 0.25% annual
        etf_expense_ratio_annual = 0.0025  # 0.25%

        costs.etf_expense_ratio = (etf_expense_ratio_annual / 365) * holding_days * position_value

    # ==================================================================
    # SUMMARY
    # ==================================================================

    return {
        # Entry costs
        'spot_entry_commission': costs.spot_entry_commission,
        'etf_entry_commission': costs.etf_entry_commission,
        'futures_entry_commission': costs.futures_entry_commission,
        'spot_entry_slippage': costs.spot_entry_slippage,
        'futures_entry_slippage': costs.futures_entry_slippage,
        'total_entry_costs': costs.total_entry_costs,

        # Exit costs
        'spot_exit_commission': costs.spot_exit_commission,
        'etf_exit_commission': costs.etf_exit_commission,
        'futures_exit_commission': costs.futures_exit_commission,
        'spot_exit_slippage': costs.spot_exit_slippage,
        'futures_exit_slippage': costs.futures_exit_slippage,
        'total_exit_costs': costs.total_exit_costs,

        # Holding costs
        'funding_cost': costs.funding_cost,
        'etf_expense_ratio': costs.etf_expense_ratio,
        'total_holding_costs': costs.total_holding_costs,

        # Grand total
        'total_all_costs': costs.total_costs
    }


def example_cost_calculation():
    """Example: Calculate costs for a real basis trade"""

    print("=" * 70)
    print("BITCOIN BASIS TRADE - COMPREHENSIVE COST ANALYSIS")
    print("=" * 70)

    # Trade parameters
    entry_spot = 50000
    exit_spot = 50000  # Flat spot price
    entry_futures = 51000  # 2% contango
    exit_futures = 50000  # Converged at expiry
    position_size = 1.0  # 1 BTC
    holding_days = 30

    # Calculate P&L before costs
    spot_pnl = (exit_spot - entry_spot) * position_size
    futures_pnl = (entry_futures - exit_futures) * position_size
    gross_pnl = spot_pnl + futures_pnl

    print(f"\n[*] TRADE DETAILS")
    print(f"-" * 70)
    print(f"Entry:  Spot=${entry_spot:,}, Futures=${entry_futures:,}, Basis=${entry_futures-entry_spot:,} ({(entry_futures-entry_spot)/entry_spot*100:.2f}%)")
    print(f"Exit:   Spot=${exit_spot:,}, Futures=${exit_futures:,}, Basis=${exit_futures-exit_spot:,}")
    print(f"Position Size: {position_size} BTC")
    print(f"Holding Period: {holding_days} days")

    print(f"\n[*] P&L BEFORE COSTS")
    print(f"-" * 70)
    print(f"Spot P&L (long):     ${spot_pnl:+,.2f}")
    print(f"Futures P&L (short): ${futures_pnl:+,.2f}")
    print(f"Gross P&L:           ${gross_pnl:+,.2f}")

    # Calculate costs - ETF version
    print(f"\n[*] COST BREAKDOWN (Using ETF: IBIT/FBTC)")
    print(f"-" * 70)

    costs_etf = calculate_comprehensive_costs(
        entry_spot, exit_spot, entry_futures, exit_futures,
        position_size, holding_days, use_etf=True
    )

    print(f"\nEntry Costs:")
    print(f"  ETF Commission:      ${costs_etf['etf_entry_commission']:,.2f}")
    print(f"  Futures Commission:  ${costs_etf['futures_entry_commission']:,.2f}")
    print(f"  ETF Slippage:        ${costs_etf['spot_entry_slippage']:,.2f}")
    print(f"  Futures Slippage:    ${costs_etf['futures_entry_slippage']:,.2f}")
    print(f"  Total Entry:         ${costs_etf['total_entry_costs']:,.2f}")

    print(f"\nExit Costs:")
    print(f"  ETF Commission:      ${costs_etf['etf_exit_commission']:,.2f}")
    print(f"  Futures Commission:  ${costs_etf['futures_exit_commission']:,.2f}")
    print(f"  ETF Slippage:        ${costs_etf['spot_exit_slippage']:,.2f}")
    print(f"  Futures Slippage:    ${costs_etf['futures_exit_slippage']:,.2f}")
    print(f"  Total Exit:          ${costs_etf['total_exit_costs']:,.2f}")

    print(f"\nHolding Costs:")
    print(f"  Funding Cost:        ${costs_etf['funding_cost']:,.2f}")
    print(f"  ETF Expense Ratio:   ${costs_etf['etf_expense_ratio']:,.2f}")
    print(f"  Total Holding:       ${costs_etf['total_holding_costs']:,.2f}")

    print(f"\n{'-' * 70}")
    print(f"TOTAL ALL COSTS:       ${costs_etf['total_all_costs']:,.2f}")

    # Net P&L
    net_pnl_etf = gross_pnl - costs_etf['total_all_costs']
    net_return_etf = (net_pnl_etf / (entry_spot * position_size)) * 100
    annualized_return_etf = net_return_etf * (365 / holding_days)

    print(f"\n[*] FINAL RESULTS (ETF)")
    print(f"-" * 70)
    print(f"Gross P&L:            ${gross_pnl:+,.2f}")
    print(f"Total Costs:          -${costs_etf['total_all_costs']:,.2f}")
    print(f"Net P&L:              ${net_pnl_etf:+,.2f}")
    print(f"Net Return:           {net_return_etf:+.2f}%")
    print(f"Annualized Return:    {annualized_return_etf:+.2f}%")

    # Calculate costs - Direct Spot version
    print(f"\n[*] COST BREAKDOWN (Using Direct Spot BTC)")
    print(f"-" * 70)

    costs_spot = calculate_comprehensive_costs(
        entry_spot, exit_spot, entry_futures, exit_futures,
        position_size, holding_days, use_etf=False
    )

    print(f"\nEntry Costs:")
    print(f"  Spot Commission:     ${costs_spot['spot_entry_commission']:,.2f}")
    print(f"  Futures Commission:  ${costs_spot['futures_entry_commission']:,.2f}")
    print(f"  Spot Slippage:       ${costs_spot['spot_entry_slippage']:,.2f}")
    print(f"  Futures Slippage:    ${costs_spot['futures_entry_slippage']:,.2f}")
    print(f"  Total Entry:         ${costs_spot['total_entry_costs']:,.2f}")

    print(f"\nExit Costs:")
    print(f"  Spot Commission:     ${costs_spot['spot_exit_commission']:,.2f}")
    print(f"  Futures Commission:  ${costs_spot['futures_exit_commission']:,.2f}")
    print(f"  Spot Slippage:       ${costs_spot['spot_exit_slippage']:,.2f}")
    print(f"  Futures Slippage:    ${costs_spot['futures_exit_slippage']:,.2f}")
    print(f"  Total Exit:          ${costs_spot['total_exit_costs']:,.2f}")

    print(f"\nHolding Costs:")
    print(f"  Funding Cost:        ${costs_spot['funding_cost']:,.2f}")
    print(f"  Total Holding:       ${costs_spot['total_holding_costs']:,.2f}")

    print(f"\n{'-' * 70}")
    print(f"TOTAL ALL COSTS:       ${costs_spot['total_all_costs']:,.2f}")

    # Net P&L
    net_pnl_spot = gross_pnl - costs_spot['total_all_costs']
    net_return_spot = (net_pnl_spot / (entry_spot * position_size)) * 100
    annualized_return_spot = net_return_spot * (365 / holding_days)

    print(f"\n[*] FINAL RESULTS (Direct Spot)")
    print(f"-" * 70)
    print(f"Gross P&L:            ${gross_pnl:+,.2f}")
    print(f"Total Costs:          -${costs_spot['total_all_costs']:,.2f}")
    print(f"Net P&L:              ${net_pnl_spot:+,.2f}")
    print(f"Net Return:           {net_return_spot:+.2f}%")
    print(f"Annualized Return:    {annualized_return_spot:+.2f}%")

    # Comparison
    print(f"\n[*] COMPARISON")
    print(f"-" * 70)
    print(f"ETF Route:      ${net_pnl_etf:+,.2f} ({annualized_return_etf:+.2f}% annualized)")
    print(f"Direct Spot:    ${net_pnl_spot:+,.2f} ({annualized_return_spot:+.2f}% annualized)")
    print(f"Difference:     ${net_pnl_etf - net_pnl_spot:+,.2f}")

    if net_pnl_etf > net_pnl_spot:
        print(f"\nRecommendation: Use ETF (IBIT/FBTC) - Lower costs!")
    else:
        print(f"\nRecommendation: Use Direct Spot - Lower costs!")

    print(f"\n{'=' * 70}\n")


if __name__ == "__main__":
    example_cost_calculation()
