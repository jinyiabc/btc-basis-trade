#!/usr/bin/env python3
"""
Bitcoin Basis Trade Analyzer.

Core analysis engine for cash-and-carry arbitrage opportunities.
Refactored from btc_basis_trade_analyzer.py
"""

from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, Any

from btc_basis.core.models import Signal, TradeConfig, MarketData
from btc_basis.core.calculator import BasisCalculator


class BasisTradeAnalyzer:
    """Main analyzer for Bitcoin basis trades."""

    def __init__(self, config: TradeConfig = None):
        """
        Initialize analyzer with configuration.

        Args:
            config: Trade configuration (uses defaults if None)
        """
        self.config = config or TradeConfig()
        self.calculator = BasisCalculator()

    def calculate_returns(self, market: MarketData) -> Dict[str, float]:
        """
        Calculate all return metrics.

        Args:
            market: Current market data

        Returns:
            Dictionary with basis and return calculations
        """
        if market.days_to_expiry == 0:
            return {
                "basis_absolute": 0.0,
                "basis_percent": 0.0,
                "monthly_basis": 0.0,
                "gross_annualized": 0.0,
                "net_annualized": 0.0,
                "leveraged_return": 0.0,
            }

        gross_annualized = market.basis_percent * (365 / market.days_to_expiry)
        net_annualized = gross_annualized - self.config.funding_cost_annual
        leveraged_return = net_annualized * self.config.leverage

        return {
            "basis_absolute": market.basis_absolute,
            "basis_percent": market.basis_percent * 100,
            "monthly_basis": market.monthly_basis * 100,
            "gross_annualized": gross_annualized * 100,
            "net_annualized": net_annualized * 100,
            "leveraged_return": leveraged_return * 100,
        }

    def generate_signal(self, market: MarketData) -> Tuple[Signal, str]:
        """
        Generate trading signal based on current market conditions.

        Args:
            market: Current market data

        Returns:
            Tuple of (Signal, reason string)
        """
        monthly_basis = market.monthly_basis

        # Stop loss conditions
        if monthly_basis < 0:
            return Signal.STOP_LOSS, "Backwardation detected - basis negative"

        if monthly_basis < 0.002:  # 0.2%
            return Signal.STOP_LOSS, "Basis compressed below 0.2% monthly"

        # Funding cost check
        monthly_funding = self.config.funding_cost_annual / 12
        if monthly_basis < monthly_funding:
            return (
                Signal.STOP_LOSS,
                f"Basis below funding cost ({monthly_funding*100:.2f}% monthly)",
            )

        # ETF discount check
        if market.etf_discount_premium and market.etf_discount_premium < -0.01:
            return Signal.STOP_LOSS, "ETF discount > 1% - liquidity stress"

        # Take profit conditions
        if monthly_basis > 0.035:  # 3.5%
            return (
                Signal.FULL_EXIT,
                "Basis at peak levels (>3.5% monthly) - take profit",
            )

        if monthly_basis > 0.025:  # 2.5%
            return Signal.PARTIAL_EXIT, "Elevated basis (>2.5% monthly) - partial exit"

        # Entry conditions
        if monthly_basis > 0.01:  # 1.0%
            if market.fear_greed_index and market.fear_greed_index > 0.8:
                return (
                    Signal.STRONG_ENTRY,
                    "Strong basis + high Fear & Greed - optimal entry",
                )
            return Signal.STRONG_ENTRY, "Strong basis >1.0% monthly"

        if monthly_basis > self.config.min_monthly_basis:
            return Signal.ACCEPTABLE_ENTRY, f"Acceptable basis {self.config.min_monthly_basis*100:.1f}-1.0% monthly"

        return Signal.NO_ENTRY, f"Basis too low ({monthly_basis*100:.2f}% monthly, min {self.config.min_monthly_basis*100:.1f}%)"

    def assess_risk(self, market: MarketData) -> Dict[str, str]:
        """
        Assess risk factors for basis trade.

        Args:
            market: Current market data

        Returns:
            Dictionary of risk assessments
        """
        risks = {}

        # Funding risk
        if self.config.funding_cost_annual > 0.06:
            risks["funding"] = "[!]  HIGH - Funding cost elevated (>6%)"
        else:
            risks["funding"] = "[OK] MODERATE - Normal funding environment"

        # Basis risk
        if market.monthly_basis < 0:
            risks["basis"] = "[X] CRITICAL - Backwardation (negative carry)"
        elif market.monthly_basis < self.config.min_monthly_basis:
            risks["basis"] = "[!]  HIGH - Basis near zero"
        else:
            risks["basis"] = "[OK] LOW - Positive contango"

        # Liquidity risk
        etf_disc = market.etf_discount_premium
        if etf_disc and etf_disc < -0.01:
            risks["liquidity"] = "[!]  HIGH - ETF trading at discount >1%"
        elif etf_disc and abs(etf_disc) < 0.002:
            risks["liquidity"] = "[OK] LOW - ETF tracking NAV closely"
        else:
            risks["liquidity"] = "[OK] MODERATE - Normal ETF tracking"

        # Crowding risk
        if market.cme_open_interest and market.cme_open_interest > 40000:
            risks["crowding"] = "[!]  HIGH - CME OI >40k contracts (crowded)"
        elif market.cme_open_interest and market.cme_open_interest > 30000:
            risks["crowding"] = "[!]  MODERATE - CME OI rising"
        else:
            risks["crowding"] = "[OK] LOW - Healthy OI levels"

        # Operational risk (time to expiry)
        if market.days_to_expiry < 7:
            risks["operational"] = "[!]  HIGH - Near expiry (rollover soon)"
        else:
            risks["operational"] = "[OK] LOW - Sufficient time to expiry"

        return risks

    def calculate_position_sizing(self, market: MarketData) -> Dict[str, Any]:
        """
        Calculate position sizes for both legs.

        Args:
            market: Current market data

        Returns:
            Dictionary with position sizing details
        """
        futures_amount = self.config.futures_target_amount

        # 1. Futures leg first (integer rounding determines notional)
        btc_amount = futures_amount / market.spot_price
        contracts_needed = btc_amount / self.config.cme_contract_size
        contracts = max(1, round(contracts_needed))

        actual_futures_value = (
            contracts * self.config.cme_contract_size * market.spot_price
        )

        # 2. Spot leg sized to match futures notional
        etf_shares = None
        if market.etf_price:
            etf_shares = int(actual_futures_value / market.etf_price)
            actual_spot_value = etf_shares * market.etf_price
        else:
            actual_spot_value = actual_futures_value

        return {
            "etf_shares": etf_shares,
            "etf_value": actual_spot_value,
            "futures_contracts": contracts,
            "futures_btc": contracts * self.config.cme_contract_size,
            "futures_value": actual_futures_value,
            "total_exposure": actual_spot_value + actual_futures_value,
            "delta_neutral": abs(actual_spot_value - actual_futures_value) < 1000,
        }

    def generate_report(self, market: MarketData) -> str:
        """
        Generate comprehensive analysis report.

        Args:
            market: Current market data

        Returns:
            Formatted report string
        """
        returns = self.calculate_returns(market)
        signal, reason = self.generate_signal(market)
        risks = self.assess_risk(market)
        positions = self.calculate_position_sizing(market)

        # Signal symbols
        signal_symbols = {
            Signal.STRONG_ENTRY: "[+]",
            Signal.ACCEPTABLE_ENTRY: "[~]",
            Signal.NO_ENTRY: "[ ]",
            Signal.PARTIAL_EXIT: "[~]",
            Signal.FULL_EXIT: "[-]",
            Signal.STOP_LOSS: "[X]",
            Signal.HOLD: "[=]",
        }

        pair_label = f"[{market.pair_id}] " if market.pair_id else ""
        report = f"""
{'='*70}
{pair_label}BASIS TRADE ANALYSIS
{'='*70}

[*] MARKET DATA
{'-'*70}
Spot Price:           ${market.spot_price:,.2f}
Futures Price:        ${market.futures_price:,.2f}
Futures Expiry:       {market.futures_expiry_date.strftime('%Y-%m-%d')} ({market.days_to_expiry} days)
"""

        if market.etf_price:
            etf_label = market.spot_symbol or "ETF"
            report += f"ETF Price ({etf_label}):{'  ' if len(etf_label) >= 4 else '   '}  ${market.etf_price:.2f}\n"
        if market.etf_nav:
            report += f"ETF NAV:              ${market.etf_nav:.2f}\n"
        if market.fear_greed_index:
            report += f"Fear & Greed Index:   {market.fear_greed_index:.2f}\n"
        if market.cme_open_interest:
            report += f"CME Open Interest:    {market.cme_open_interest:,.0f} contracts\n"

        report += f"""
[*] BASIS ANALYSIS
{'-'*70}
Basis (Absolute):     ${returns['basis_absolute']:,.2f}
Basis (Percent):      {returns['basis_percent']:.2f}%
Monthly Basis:        {returns['monthly_basis']:.2f}%

[*] RETURN CALCULATIONS
{'-'*70}
Gross Annualized:     {returns['gross_annualized']:.2f}%
Funding Cost:         {self.config.funding_cost_annual*100:.2f}% (annualized)
Net Annualized:       {returns['net_annualized']:.2f}%
"""

        if self.config.leverage > 1.0:
            report += f"With {self.config.leverage}x Leverage: {returns['leveraged_return']:.2f}%\n"
            report += "[!]  Higher leverage = higher liquidation risk\n"

        report += f"""
[*] TRADING SIGNAL
{'-'*70}
Signal:  {signal_symbols.get(signal, '[?]')} {signal.value}
Reason:  {reason}

[*] POSITION SIZING (Account: ${self.config.account_size:,.0f})
{'-'*70}
"""

        # Unit label for futures amount
        UNIT_MAP = {"BTC": "BTC", "ETH": "ETH", "OIL": "barrels",
                    "GOLD": "oz", "SILVER": "oz"}
        unit = UNIT_MAP.get(market.pair_id, "units")
        fut_label = market.futures_symbol or "Futures"

        if positions["etf_shares"]:
            etf_label = market.spot_symbol or "ETF"
            report += f"ETF Shares ({etf_label}):{'  ' if len(etf_label) >= 4 else '   '} {positions['etf_shares']:,} shares\n"
            report += f"ETF Value:            ${positions['etf_value']:,.2f}\n"
        else:
            report += f"Spot Value:           ${positions['etf_value']:,.2f}\n"

        report += f"""Futures Contracts:    {positions['futures_contracts']} {fut_label} contract(s)
Futures Amount:       {positions['futures_btc']:,.2f} {unit}
Futures Notional:     ${positions['futures_value']:,.2f}
Total Exposure:       ${positions['total_exposure']:,.2f}
Delta Neutral:        {'[OK] Yes' if positions['delta_neutral'] else '[!]  No - rebalance needed'}

[!]  RISK ASSESSMENT
{'-'*70}
"""

        for risk_type, risk_level in risks.items():
            report += f"{risk_type.capitalize():20s} {risk_level}\n"

        # Overall risk level
        high_risks = sum(1 for r in risks.values() if "[!]" in r or "[X]" in r)
        if high_risks >= 3:
            overall_risk = "HIGH"
        elif high_risks >= 1:
            overall_risk = "MODERATE"
        else:
            overall_risk = "LOW"

        report += f"\nOverall Risk Level:   {overall_risk}\n"

        report += f"\n{'='*70}\n"
        report += "[!]  This is not financial advice. Consult a qualified professional.\n"
        report += f"{'='*70}\n"

        return report

    def get_export_data(self, market: MarketData) -> Dict[str, Any]:
        """
        Get structured data for JSON export.

        Args:
            market: Current market data

        Returns:
            Dictionary suitable for JSON serialization
        """
        signal, reason = self.generate_signal(market)

        return {
            "timestamp": datetime.now().isoformat(),
            "market_data": market.to_dict(),
            "returns": self.calculate_returns(market),
            "signal": {
                "signal": signal.value,
                "reason": reason,
            },
            "risks": self.assess_risk(market),
            "positions": self.calculate_position_sizing(market),
            "config": self.config.to_dict(),
        }
