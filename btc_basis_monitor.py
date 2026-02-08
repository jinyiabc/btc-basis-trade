#!/usr/bin/env python3
"""
Bitcoin Basis Trade Monitor

Continuously monitors basis spread and generates alerts for entry/exit signals.
Can be run as a background daemon or scheduled task.

Usage:
    python btc_basis_monitor.py --interval 300  # Check every 5 minutes
    python btc_basis_monitor.py --once          # Single check
"""

import argparse
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import sys

# Import from main analyzer
from btc_basis_trade_analyzer import (
    BasisTradeAnalyzer,
    MarketData,
    MarketDataFetcher,
    TradeConfig,
    Signal
)


class BasisMonitor:
    """Monitor basis spread and generate alerts"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config.json"
        self.load_config()
        self.analyzer = BasisTradeAnalyzer(self.trade_config)
        self.fetcher = MarketDataFetcher()
        self.history: List[Dict] = []
        self.last_signal: Optional[Signal] = None

        # Setup logging
        self.setup_logging()

    def load_config(self):
        """Load configuration from JSON file"""
        if Path(self.config_path).exists():
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)
        else:
            logging.warning(f"Config file not found: {self.config_path}, using defaults")
            config_data = {}

        self.trade_config = TradeConfig(
            account_size=config_data.get('account_size', 200000),
            spot_target_pct=config_data.get('spot_target_pct', 0.50),
            futures_target_pct=config_data.get('futures_target_pct', 0.50),
            funding_cost_annual=config_data.get('funding_cost_annual', 0.05),
            leverage=config_data.get('leverage', 1.0),
            cme_contract_size=config_data.get('cme_contract_size', 5.0),
            min_monthly_basis=config_data.get('min_monthly_basis', 0.005)
        )

        self.alert_thresholds = config_data.get('alert_thresholds', {
            'stop_loss_basis': 0.002,
            'partial_exit_basis': 0.025,
            'full_exit_basis': 0.035,
            'strong_entry_basis': 0.01,
            'min_entry_basis': 0.005
        })

    def setup_logging(self):
        """Setup logging to file and console"""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler('btc_basis_monitor.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def fetch_market_data(self) -> Optional[MarketData]:
        """Fetch current market data"""
        try:
            spot_price = self.fetcher.fetch_coinbase_spot()
            if not spot_price:
                logging.error("Failed to fetch spot price")
                return None

            # Fetch fear & greed
            fear_greed = self.fetcher.fetch_fear_greed_index()

            # For futures, would need CME API or manual input
            # For now, use estimated basis (in production, fetch real futures data)
            # TODO: Integrate with CME or futures data provider
            futures_price = spot_price * 1.02  # Placeholder: 2% contango
            expiry = datetime.now() + timedelta(days=30)

            market = MarketData(
                spot_price=spot_price,
                futures_price=futures_price,
                futures_expiry_date=expiry,
                etf_price=spot_price / 1800,
                fear_greed_index=fear_greed
            )

            logging.info(f"Market data fetched - Spot: ${spot_price:,.2f}, "
                        f"Monthly Basis: {market.monthly_basis*100:.2f}%")
            return market

        except Exception as e:
            logging.error(f"Error fetching market data: {e}")
            return None

    def check_and_alert(self, market: MarketData) -> Dict:
        """Check market conditions and generate alerts"""
        signal, reason = self.analyzer.generate_signal(market)
        returns = self.analyzer.calculate_returns(market)
        risks = self.analyzer.assess_risk(market)

        alert_data = {
            'timestamp': datetime.now().isoformat(),
            'spot_price': market.spot_price,
            'futures_price': market.futures_price,
            'monthly_basis': returns['monthly_basis'],
            'net_annualized_return': returns['net_annualized'],
            'signal': signal.value,
            'signal_reason': reason,
            'risks': risks
        }

        # Check if signal changed
        signal_changed = self.last_signal != signal
        self.last_signal = signal

        # Alert conditions
        alert_triggered = False
        alert_message = []

        if signal == Signal.STOP_LOSS:
            alert_triggered = True
            alert_message.append(f"[!!] STOP LOSS ALERT: {reason}")

        elif signal == Signal.FULL_EXIT:
            alert_triggered = True
            alert_message.append(f"[-] FULL EXIT SIGNAL: {reason}")

        elif signal == Signal.PARTIAL_EXIT:
            alert_triggered = True
            alert_message.append(f"[~] PARTIAL EXIT SIGNAL: {reason}")

        elif signal == Signal.STRONG_ENTRY and signal_changed:
            alert_triggered = True
            alert_message.append(f"[+] STRONG ENTRY SIGNAL: {reason}")

        elif signal == Signal.ACCEPTABLE_ENTRY and signal_changed:
            alert_triggered = True
            alert_message.append(f"[~] ACCEPTABLE ENTRY SIGNAL: {reason}")

        # Risk-based alerts
        critical_risks = [k for k, v in risks.items() if '[X]' in v]
        if critical_risks:
            alert_triggered = True
            alert_message.append(f"[!]  CRITICAL RISKS: {', '.join(critical_risks)}")

        if alert_triggered:
            for msg in alert_message:
                logging.warning(msg)
                self.send_alert(msg, alert_data)

        # Add to history
        self.history.append(alert_data)
        if len(self.history) > 1000:  # Keep last 1000 records
            self.history = self.history[-1000:]

        return alert_data

    def send_alert(self, message: str, data: Dict):
        """Send alert (implement your notification method)"""
        # TODO: Implement notification system
        # Options:
        # - Email via SMTP
        # - SMS via Twilio
        # - Telegram bot
        # - Discord webhook
        # - Slack webhook
        # - Desktop notification

        # For now, just write to alert file
        alert_file = Path('alerts.log')
        with open(alert_file, 'a') as f:
            f.write(f"{datetime.now().isoformat()} - {message}\n")
            f.write(f"Data: {json.dumps(data, indent=2)}\n\n")

    def generate_summary_report(self) -> str:
        """Generate summary from recent history"""
        if not self.history:
            return "No data collected yet."

        recent = self.history[-10:]  # Last 10 records
        current = self.history[-1]

        # Calculate basis trend
        if len(self.history) >= 2:
            basis_change = current['monthly_basis'] - self.history[-2]['monthly_basis']
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
            ts = datetime.fromisoformat(record['timestamp']).strftime('%H:%M:%S')
            report += f"  {i}. {ts} - Basis: {record['monthly_basis']:5.2f}% - {record['signal']}\n"

        # Risk summary
        report += f"\nCurrent Risks:\n"
        for risk_type, risk_level in current['risks'].items():
            report += f"  {risk_type.capitalize():20s} {risk_level}\n"

        report += f"\n{'='*70}\n"
        return report

    def run_continuous(self, interval_seconds: int = 300):
        """Run continuous monitoring loop"""
        logging.info(f"Starting continuous monitoring (interval: {interval_seconds}s)")

        try:
            while True:
                market = self.fetch_market_data()
                if market:
                    self.check_and_alert(market)

                    # Print summary every hour
                    if len(self.history) % 12 == 0:  # Assuming 5-min intervals
                        print(self.generate_summary_report())

                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            logging.info("Monitoring stopped by user")
            self.save_history()

    def run_once(self):
        """Run single check"""
        market = self.fetch_market_data()
        if market:
            self.check_and_alert(market)
            report = self.analyzer.generate_report(market)
            print(report)
            return True
        return False

    def save_history(self):
        """Save history to file"""
        history_file = f"basis_history_{datetime.now().strftime('%Y%m%d')}.json"
        with open(history_file, 'w') as f:
            json.dump(self.history, f, indent=2)
        logging.info(f"History saved to {history_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Bitcoin Basis Trade Monitor')
    parser.add_argument('--config', type=str, help='Path to config JSON file')
    parser.add_argument('--interval', type=int, default=300,
                       help='Check interval in seconds (default: 300)')
    parser.add_argument('--once', action='store_true',
                       help='Run once and exit')
    args = parser.parse_args()

    monitor = BasisMonitor(config_path=args.config)

    if args.once:
        monitor.run_once()
    else:
        monitor.run_continuous(interval_seconds=args.interval)


if __name__ == "__main__":
    main()
