#!/usr/bin/env python3
"""
Bitcoin Basis Trade Analysis Tool

Analyzes cash-and-carry arbitrage opportunities between Bitcoin spot and futures.
Market-neutral strategy that captures the basis spread.

Author: Generated for Claude Code
Date: 2026-02-08
"""

import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class Signal(Enum):
    """Trading signals"""
    STRONG_ENTRY = "STRONG_ENTRY"
    ACCEPTABLE_ENTRY = "ACCEPTABLE_ENTRY"
    NO_ENTRY = "NO_ENTRY"
    PARTIAL_EXIT = "PARTIAL_EXIT"
    FULL_EXIT = "FULL_EXIT"
    STOP_LOSS = "STOP_LOSS"
    HOLD = "HOLD"


@dataclass
class TradeConfig:
    """Configuration for basis trade"""
    account_size: float = 200_000
    spot_target_pct: float = 0.50  # 50% of account
    futures_target_pct: float = 0.50
    funding_cost_annual: float = 0.05  # 5% annualized
    leverage: float = 1.0
    cme_contract_size: float = 5.0  # BTC per contract
    min_monthly_basis: float = 0.005  # 0.5% minimum

    @property
    def spot_target_amount(self) -> float:
        return self.account_size * self.spot_target_pct

    @property
    def futures_target_amount(self) -> float:
        return self.account_size * self.futures_target_pct


@dataclass
class MarketData:
    """Market data for basis trade analysis"""
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
        """Absolute basis in dollars"""
        return self.futures_price - self.spot_price

    @property
    def basis_percent(self) -> float:
        """Basis as percentage of spot"""
        return self.basis_absolute / self.spot_price

    @property
    def days_to_expiry(self) -> int:
        """Days until futures expiry"""
        reference_date = self.as_of_date if self.as_of_date else datetime.now()
        return (self.futures_expiry_date - reference_date).days

    @property
    def monthly_basis(self) -> float:
        """Normalized to 30-day basis"""
        if self.days_to_expiry == 0:
            return 0.0
        return self.basis_percent * (30 / self.days_to_expiry)

    @property
    def etf_discount_premium(self) -> Optional[float]:
        """ETF discount/premium vs NAV"""
        if self.etf_price and self.etf_nav:
            return (self.etf_price - self.etf_nav) / self.etf_nav
        return None


class BasisTradeAnalyzer:
    """Main analyzer for Bitcoin basis trades"""

    def __init__(self, config: TradeConfig = TradeConfig()):
        self.config = config

    def calculate_returns(self, market: MarketData) -> Dict[str, float]:
        """Calculate all return metrics"""
        if market.days_to_expiry == 0:
            return {
                'basis_absolute': 0.0,
                'basis_percent': 0.0,
                'monthly_basis': 0.0,
                'gross_annualized': 0.0,
                'net_annualized': 0.0,
                'leveraged_return': 0.0
            }

        gross_annualized = market.basis_percent * (365 / market.days_to_expiry)
        net_annualized = gross_annualized - self.config.funding_cost_annual
        leveraged_return = net_annualized * self.config.leverage

        return {
            'basis_absolute': market.basis_absolute,
            'basis_percent': market.basis_percent * 100,
            'monthly_basis': market.monthly_basis * 100,
            'gross_annualized': gross_annualized * 100,
            'net_annualized': net_annualized * 100,
            'leveraged_return': leveraged_return * 100
        }

    def generate_signal(self, market: MarketData) -> Tuple[Signal, str]:
        """Generate trading signal based on current market conditions"""
        monthly_basis = market.monthly_basis

        # Stop loss conditions
        if monthly_basis < 0:
            return Signal.STOP_LOSS, "Backwardation detected - basis negative"

        if monthly_basis < 0.002:  # 0.2%
            return Signal.STOP_LOSS, "Basis compressed below 0.2% monthly"

        # Funding cost check
        monthly_funding = self.config.funding_cost_annual / 12
        if monthly_basis < monthly_funding:
            return Signal.STOP_LOSS, f"Basis below funding cost ({monthly_funding*100:.2f}% monthly)"

        # ETF discount check
        if market.etf_discount_premium and market.etf_discount_premium < -0.01:
            return Signal.STOP_LOSS, f"ETF discount > 1% - liquidity stress"

        # Take profit conditions
        if monthly_basis > 0.035:  # 3.5%
            return Signal.FULL_EXIT, "Basis at peak levels (>3.5% monthly) - take profit"

        if monthly_basis > 0.025:  # 2.5%
            return Signal.PARTIAL_EXIT, "Elevated basis (>2.5% monthly) - partial exit"

        # Entry conditions
        if monthly_basis > 0.01:  # 1.0%
            # Check Fear & Greed for optimal timing
            if market.fear_greed_index and market.fear_greed_index > 0.8:
                return Signal.STRONG_ENTRY, "Strong basis + high Fear & Greed - optimal entry"
            return Signal.STRONG_ENTRY, "Strong basis >1.0% monthly"

        if monthly_basis > 0.005:  # 0.5%
            return Signal.ACCEPTABLE_ENTRY, "Acceptable basis 0.5-1.0% monthly"

        return Signal.NO_ENTRY, f"Basis too low ({monthly_basis*100:.2f}% monthly)"

    def assess_risk(self, market: MarketData) -> Dict[str, str]:
        """Assess risk factors"""
        risks = {}

        # Funding risk
        if self.config.funding_cost_annual > 0.06:
            risks['funding'] = "[!]  HIGH - Funding cost elevated (>6%)"
        else:
            risks['funding'] = "[OK] MODERATE - Normal funding environment"

        # Basis risk
        if market.monthly_basis < 0:
            risks['basis'] = "[X] CRITICAL - Backwardation (negative carry)"
        elif market.monthly_basis < 0.005:
            risks['basis'] = "[!]  HIGH - Basis near zero"
        else:
            risks['basis'] = "[OK] LOW - Positive contango"

        # Liquidity risk
        etf_disc = market.etf_discount_premium
        if etf_disc and etf_disc < -0.01:
            risks['liquidity'] = "[!]  HIGH - ETF trading at discount >1%"
        elif etf_disc and abs(etf_disc) < 0.002:
            risks['liquidity'] = "[OK] LOW - ETF tracking NAV closely"
        else:
            risks['liquidity'] = "[OK] MODERATE - Normal ETF tracking"

        # Crowding risk
        if market.cme_open_interest and market.cme_open_interest > 40000:
            risks['crowding'] = "[!]  HIGH - CME OI >40k contracts (crowded)"
        elif market.cme_open_interest and market.cme_open_interest > 30000:
            risks['crowding'] = "[!]  MODERATE - CME OI rising"
        else:
            risks['crowding'] = "[OK] LOW - Healthy OI levels"

        # Operational risk (time to expiry)
        if market.days_to_expiry < 7:
            risks['operational'] = "[!]  HIGH - Near expiry (rollover soon)"
        else:
            risks['operational'] = "[OK] LOW - Sufficient time to expiry"

        return risks

    def calculate_position_sizing(self, market: MarketData) -> Dict[str, any]:
        """Calculate position sizes for both legs"""
        spot_amount = self.config.spot_target_amount
        futures_amount = self.config.futures_target_amount

        # ETF shares (if ETF price provided)
        etf_shares = None
        if market.etf_price:
            etf_shares = int(spot_amount / market.etf_price)
            actual_spot_value = etf_shares * market.etf_price
        else:
            actual_spot_value = spot_amount

        # CME futures contracts
        btc_amount = futures_amount / market.spot_price
        contracts_needed = btc_amount / self.config.cme_contract_size
        contracts = max(1, round(contracts_needed))  # Round to nearest, min 1

        actual_futures_value = contracts * self.config.cme_contract_size * market.spot_price

        return {
            'etf_shares': etf_shares,
            'etf_value': actual_spot_value if etf_shares else spot_amount,
            'futures_contracts': contracts,
            'futures_btc': contracts * self.config.cme_contract_size,
            'futures_value': actual_futures_value,
            'total_exposure': actual_spot_value + actual_futures_value,
            'delta_neutral': abs(actual_spot_value - actual_futures_value) < 1000
        }

    def generate_report(self, market: MarketData) -> str:
        """Generate comprehensive analysis report"""
        returns = self.calculate_returns(market)
        signal, reason = self.generate_signal(market)
        risks = self.assess_risk(market)
        positions = self.calculate_position_sizing(market)

        # Color coding for signal
        signal_symbols = {
            Signal.STRONG_ENTRY: "[+]",
            Signal.ACCEPTABLE_ENTRY: "[~]",
            Signal.NO_ENTRY: "[ ]",
            Signal.PARTIAL_EXIT: "[~]",
            Signal.FULL_EXIT: "[-]",
            Signal.STOP_LOSS: "[X]",
            Signal.HOLD: "[=]"
        }

        report = f"""
{'='*70}
BITCOIN BASIS TRADE ANALYSIS
{'='*70}

[*] MARKET DATA
{'-'*70}
Spot Price:           ${market.spot_price:,.2f}
Futures Price:        ${market.futures_price:,.2f}
Futures Expiry:       {market.futures_expiry_date.strftime('%Y-%m-%d')} ({market.days_to_expiry} days)
"""

        if market.etf_price:
            report += f"ETF Price (IBIT):     ${market.etf_price:.2f}\n"
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
            report += f"[!]  Higher leverage = higher liquidation risk\n"

        report += f"""
[*] TRADING SIGNAL
{'-'*70}
Signal:  {signal_symbols.get(signal, '[?]')} {signal.value}
Reason:  {reason}

[*] POSITION SIZING (Account: ${self.config.account_size:,.0f})
{'-'*70}
"""

        if positions['etf_shares']:
            report += f"ETF Shares (IBIT):    {positions['etf_shares']:,} shares\n"
            report += f"ETF Value:            ${positions['etf_value']:,.2f}\n"
        else:
            report += f"Spot BTC Value:       ${positions['etf_value']:,.2f}\n"

        report += f"""CME Futures Contracts: {positions['futures_contracts']} contract(s)
Futures BTC Amount:   {positions['futures_btc']:.2f} BTC
Futures Notional:     ${positions['futures_value']:,.2f}
Total Exposure:       ${positions['total_exposure']:,.2f}
Delta Neutral:        {'[OK] Yes' if positions['delta_neutral'] else '[!]  No - rebalance needed'}

[!]  RISK ASSESSMENT
{'-'*70}
"""

        for risk_type, risk_level in risks.items():
            report += f"{risk_type.capitalize():20s} {risk_level}\n"

        # Overall risk level
        high_risks = sum(1 for r in risks.values() if '[!]' in r or '[X]' in r)
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


class MarketDataFetcher:
    """Fetch market data from various sources"""

    @staticmethod
    def fetch_coinbase_spot() -> Optional[float]:
        """Fetch BTC spot price from Coinbase"""
        try:
            url = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            return float(data['data']['amount'])
        except Exception as e:
            print(f"Error fetching Coinbase data: {e}")
            return None

    @staticmethod
    def fetch_coinglass_basis() -> Optional[Dict]:
        """Fetch basis data from CoinGlass (requires API key for some data)"""
        try:
            # Public endpoint for basic data
            url = "https://open-api.coinglass.com/public/v2/indicator/bitcoin_basis"
            headers = {'accept': 'application/json'}
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching CoinGlass data: {e}")
            return None

    @staticmethod
    def fetch_fear_greed_index() -> Optional[float]:
        """Fetch Fear & Greed Index"""
        try:
            url = "https://api.alternative.me/fng/"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            # Returns 0-100, normalize to 0-1
            value = int(data['data'][0]['value'])
            return value / 100.0
        except Exception as e:
            print(f"Error fetching Fear & Greed Index: {e}")
            return None

    @staticmethod
    def fetch_ibkr_data(expiry='202603', futures_symbol='MBT') -> Optional[Dict]:
        """
        Fetch both spot and futures from IBKR in one connection

        Returns:
            Dictionary with complete basis data or None if failed
        """
        try:
            # Import unified fetcher (optional dependency)
            import sys
            import os
            sys.path.insert(0, os.path.dirname(__file__))
            from fetch_btc_ibkr_unified import UnifiedBTCFetcher

            # Try to connect to IBKR (try multiple ports)
            ports = [7496, 7497, 4001, 4002]  # Live, Paper, Gateway Live, Gateway Paper

            for port in ports:
                fetcher = UnifiedBTCFetcher(port=port, client_id=1)

                if fetcher.connect():
                    try:
                        # Get complete data
                        data = fetcher.get_complete_basis_data(expiry, futures_symbol)
                        return data
                    finally:
                        fetcher.disconnect()

            return None

        except Exception as e:
            # IBKR not available, will fall back to other methods
            return None

    @staticmethod
    def create_sample_data() -> MarketData:
        """Create sample market data for testing"""
        spot_price = 95000.0
        futures_price = 97200.0
        expiry = datetime.now() + timedelta(days=30)

        return MarketData(
            spot_price=spot_price,
            futures_price=futures_price,
            futures_expiry_date=expiry,
            etf_price=53.50,
            etf_nav=53.45,
            fear_greed_index=0.75,
            cme_open_interest=35000
        )


def main():
    """Main execution"""
    print("\n*** Bitcoin Basis Trade Analyzer ***\n")

    # Initialize configuration
    config = TradeConfig()
    analyzer = BasisTradeAnalyzer(config)
    fetcher = MarketDataFetcher()

    # Try to fetch live data
    print("Fetching market data...")

    # Method 1: Try IBKR for BOTH spot and futures (best - real CME data)
    print("[1/3] Trying IBKR (spot + futures)...")
    ibkr_data = fetcher.fetch_ibkr_data()

    if ibkr_data:
        print(f"[OK] IBKR: Spot ${ibkr_data['spot_price']:,.2f} (from {ibkr_data['spot_source']})")
        print(f"[OK] IBKR: Futures ${ibkr_data['futures_price']:,.2f} ({ibkr_data['futures_local_symbol']})")

        fear_greed = fetcher.fetch_fear_greed_index()

        market = MarketData(
            spot_price=ibkr_data['spot_price'],
            futures_price=ibkr_data['futures_price'],
            futures_expiry_date=datetime.strptime(ibkr_data['expiry'] + '27', '%Y%m%d'),  # Last Friday approx
            etf_price=ibkr_data['etf_price'],
            fear_greed_index=fear_greed,
            cme_open_interest=ibkr_data.get('volume')
        )

    else:
        # Method 2: Try Coinbase spot + estimated futures (fallback)
        print("[2/3] IBKR unavailable, trying Coinbase spot...")
        spot_price = fetcher.fetch_coinbase_spot()
        fear_greed = fetcher.fetch_fear_greed_index()

        if spot_price:
            print(f"[OK] Coinbase Spot: ${spot_price:,.2f}")
            print("[!]  Using ESTIMATED futures (spot * 1.02)")

            # For demonstration, assume 2% monthly basis (typical)
            futures_price = spot_price * 1.02
            expiry = datetime.now() + timedelta(days=30)

            market = MarketData(
                spot_price=spot_price,
                futures_price=futures_price,
                futures_expiry_date=expiry,
                etf_price=spot_price / 1800,  # Approximate IBIT price
                fear_greed_index=fear_greed
            )
        else:
            # Method 3: Use sample data (last resort)
            print("[3/3] All live sources failed")
            print("[!]  Using sample data")
            market = fetcher.create_sample_data()

    # Generate and print report
    report = analyzer.generate_report(market)
    print(report)

    # Save to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"btc_basis_analysis_{timestamp}.txt"
    with open(filename, 'w') as f:
        f.write(report)
    print(f"[File] Report saved to: {filename}")

    # Export as JSON
    json_filename = f"btc_basis_analysis_{timestamp}.json"
    export_data = {
        'timestamp': datetime.now().isoformat(),
        'market_data': {
            'spot_price': market.spot_price,
            'futures_price': market.futures_price,
            'futures_expiry': market.futures_expiry_date.isoformat(),
            'basis_absolute': market.basis_absolute,
            'basis_percent': market.basis_percent,
            'monthly_basis': market.monthly_basis,
            'days_to_expiry': market.days_to_expiry
        },
        'returns': analyzer.calculate_returns(market),
        'signal': {
            'signal': analyzer.generate_signal(market)[0].value,
            'reason': analyzer.generate_signal(market)[1]
        },
        'risks': analyzer.assess_risk(market),
        'positions': analyzer.calculate_position_sizing(market),
        'config': {
            'account_size': config.account_size,
            'funding_cost_annual': config.funding_cost_annual,
            'leverage': config.leverage
        }
    }

    with open(json_filename, 'w') as f:
        json.dump(export_data, f, indent=2, default=str)
    print(f"[Data] JSON data exported to: {json_filename}\n")


if __name__ == "__main__":
    main()
