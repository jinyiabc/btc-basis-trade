#!/usr/bin/env python3
"""
Bitcoin Basis Trade Monitor daemon.

Continuously monitors basis spread and generates alerts.
Refactored from btc_basis_monitor.py
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from btc_basis.core.models import Signal, TradeConfig, MarketData
from btc_basis.core.analyzer import BasisTradeAnalyzer
from btc_basis.data.coinbase import CoinbaseFetcher, FearGreedFetcher
from btc_basis.utils.config import ConfigLoader
from btc_basis.utils.logging import LoggingMixin, setup_logging
from btc_basis.utils.io import ReportWriter


class BasisMonitor(LoggingMixin):
    """Monitor basis spread and generate alerts."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize monitor.

        Args:
            config_path: Path to config JSON file
        """
        self.config_loader = ConfigLoader(config_path)
        self.trade_config = TradeConfig.from_dict(self.config_loader.get_all())
        self.analyzer = BasisTradeAnalyzer(self.trade_config)
        self.coinbase = CoinbaseFetcher()
        self.fear_greed = FearGreedFetcher()
        self.history: List[Dict] = []
        self.last_signal: Optional[Signal] = None
        self.report_writer = ReportWriter()

        # Setup logging
        setup_logging(log_file="output/logs/btc_basis_monitor.log")

    def fetch_market_data(self) -> Optional[MarketData]:
        """
        Fetch current market data.

        Returns:
            MarketData or None if fetch failed
        """
        try:
            spot_price = self.coinbase.fetch_spot_price()
            if not spot_price:
                self.log_error("Failed to fetch spot price")
                return None

            fear_greed = self.fear_greed.fetch_index()

            # For futures, would need CME API or IBKR
            # For now, use estimated basis (in production, integrate real data)
            futures_price = spot_price * 1.02  # Placeholder: 2% contango
            expiry = datetime.now() + timedelta(days=30)

            market = MarketData(
                spot_price=spot_price,
                futures_price=futures_price,
                futures_expiry_date=expiry,
                etf_price=spot_price / 1800,
                fear_greed_index=fear_greed,
            )

            self.log(
                f"Market data fetched - Spot: ${spot_price:,.2f}, "
                f"Monthly Basis: {market.monthly_basis*100:.2f}%"
            )
            return market

        except Exception as e:
            self.log_error(f"Error fetching market data: {e}")
            return None

    def check_and_alert(self, market: MarketData) -> Dict:
        """
        Check market conditions and generate alerts.

        Args:
            market: Current market data

        Returns:
            Alert data dictionary
        """
        signal, reason = self.analyzer.generate_signal(market)
        returns = self.analyzer.calculate_returns(market)
        risks = self.analyzer.assess_risk(market)

        alert_data = {
            "timestamp": datetime.now().isoformat(),
            "spot_price": market.spot_price,
            "futures_price": market.futures_price,
            "monthly_basis": returns["monthly_basis"],
            "net_annualized_return": returns["net_annualized"],
            "signal": signal.value,
            "signal_reason": reason,
            "risks": risks,
        }

        # Check if signal changed
        signal_changed = self.last_signal != signal
        self.last_signal = signal

        # Alert conditions
        alert_triggered = False
        alert_messages = []

        if signal == Signal.STOP_LOSS:
            alert_triggered = True
            alert_messages.append(f"[!!] STOP LOSS ALERT: {reason}")

        elif signal == Signal.FULL_EXIT:
            alert_triggered = True
            alert_messages.append(f"[-] FULL EXIT SIGNAL: {reason}")

        elif signal == Signal.PARTIAL_EXIT:
            alert_triggered = True
            alert_messages.append(f"[~] PARTIAL EXIT SIGNAL: {reason}")

        elif signal == Signal.STRONG_ENTRY and signal_changed:
            alert_triggered = True
            alert_messages.append(f"[+] STRONG ENTRY SIGNAL: {reason}")

        elif signal == Signal.ACCEPTABLE_ENTRY and signal_changed:
            alert_triggered = True
            alert_messages.append(f"[~] ACCEPTABLE ENTRY SIGNAL: {reason}")

        # Risk-based alerts
        critical_risks = [k for k, v in risks.items() if "[X]" in v]
        if critical_risks:
            alert_triggered = True
            alert_messages.append(f"[!]  CRITICAL RISKS: {', '.join(critical_risks)}")

        if alert_triggered:
            for msg in alert_messages:
                self.log_warning(msg)
                self.send_alert(msg, alert_data)

        # Add to history
        self.history.append(alert_data)
        if len(self.history) > 1000:
            self.history = self.history[-1000:]

        return alert_data

    def send_alert(self, message: str, data: Dict):
        """
        Send alert notification.

        Args:
            message: Alert message
            data: Alert data
        """
        # Write to alert file
        alert_file = Path("output/logs/alerts.log")
        alert_file.parent.mkdir(parents=True, exist_ok=True)

        with open(alert_file, "a") as f:
            f.write(f"{datetime.now().isoformat()} - {message}\n")
            f.write(f"Data: {json.dumps(data, indent=2)}\n\n")

        # TODO: Add additional notification methods:
        # - Email via SMTP
        # - SMS via Twilio
        # - Telegram bot
        # - Discord webhook
        # - Slack webhook

    def generate_summary_report(self) -> str:
        """
        Generate summary from recent history.

        Returns:
            Summary report string
        """
        if not self.history:
            return "No data collected yet."

        recent = self.history[-10:]
        current = self.history[-1]

        # Calculate basis trend
        if len(self.history) >= 2:
            basis_change = current["monthly_basis"] - self.history[-2]["monthly_basis"]
            trend = "[UP] Rising" if basis_change > 0 else "[DOWN] Falling"
        else:
            basis_change = 0
            trend = "[=]  Stable"

        report = f"""
{'='*70}
BASIS MONITOR SUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*70}

Current Status:
  Spot Price:         ${current['spot_price']:,.2f}
  Monthly Basis:      {current['monthly_basis']:.2f}%
  Net Annual Return:  {current['net_annualized_return']:.2f}%
  Signal:             {current['signal']}
  Trend:              {trend} ({basis_change:+.2f}% change)

Recent History ({len(recent)} samples):
"""
        for i, record in enumerate(recent, 1):
            ts = datetime.fromisoformat(record["timestamp"]).strftime("%H:%M:%S")
            report += (
                f"  {i}. {ts} - Basis: {record['monthly_basis']:5.2f}% - {record['signal']}\n"
            )

        report += "\nCurrent Risks:\n"
        for risk_type, risk_level in current["risks"].items():
            report += f"  {risk_type.capitalize():20s} {risk_level}\n"

        report += f"\n{'='*70}\n"
        return report

    def run_continuous(self, interval_seconds: int = 300):
        """
        Run continuous monitoring loop.

        Args:
            interval_seconds: Check interval in seconds
        """
        self.log(f"Starting continuous monitoring (interval: {interval_seconds}s)")

        try:
            while True:
                market = self.fetch_market_data()
                if market:
                    self.check_and_alert(market)

                    # Print summary every hour (12 x 5-min intervals)
                    if len(self.history) % 12 == 0:
                        print(self.generate_summary_report())

                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            self.log("Monitoring stopped by user")
            self.save_history()

    def run_once(self) -> bool:
        """
        Run single check.

        Returns:
            True if check was successful
        """
        market = self.fetch_market_data()
        if market:
            self.check_and_alert(market)
            report = self.analyzer.generate_report(market)
            print(report)
            return True
        return False

    def save_history(self):
        """Save history to file."""
        history_file = f"output/logs/basis_history_{datetime.now().strftime('%Y%m%d')}.json"
        Path(history_file).parent.mkdir(parents=True, exist_ok=True)

        with open(history_file, "w") as f:
            json.dump(self.history, f, indent=2)

        self.log(f"History saved to {history_file}")
