#!/usr/bin/env python3
"""
Bitcoin Basis Trade CLI

Interactive command-line interface for all basis trade tools.
Provides a simple menu system for analysis, monitoring, and backtesting.

Usage:
    python btc_basis_cli.py
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Import modules
from btc_basis_trade_analyzer import (
    BasisTradeAnalyzer,
    MarketData,
    MarketDataFetcher,
    TradeConfig
)
from btc_basis_monitor import BasisMonitor
from btc_basis_backtest import Backtester


class BasisTradeCLI:
    """Interactive CLI for basis trade tools"""

    def __init__(self):
        self.config = TradeConfig()
        self.config_file = "config.json"

    def clear_screen(self):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(self):
        """Print application header"""
        print("""
╔══════════════════════════════════════════════════════════════════╗
║         Bitcoin Basis Trade Analysis Toolkit                    ║
║         Market-Neutral Cash & Carry Arbitrage                    ║
╚══════════════════════════════════════════════════════════════════╝
""")

    def print_menu(self):
        """Print main menu"""
        print("\n[*] MAIN MENU\n")
        print("  1. [A] Run Single Analysis (current market)")
        print("  2. [M] Start Continuous Monitor (background)")
        print("  3. [B] Run Backtest (historical data)")
        print("  4. [C] Configure Settings")
        print("  5. [S] Quick Status Check")
        print("  6. [D] View Documentation")
        print("  7. [X] Exit")
        print()

    def run_single_analysis(self):
        """Run single market analysis"""
        self.clear_screen()
        print("\n[*] Running Single Analysis...\n")

        analyzer = BasisTradeAnalyzer(self.config)
        fetcher = MarketDataFetcher()

        # Fetch data
        print("Fetching market data...")
        spot_price = fetcher.fetch_coinbase_spot()
        fear_greed = fetcher.fetch_fear_greed_index()

        if spot_price:
            print(f"[OK] Live BTC Spot: ${spot_price:,.2f}")

            # Estimate futures (2% contango typical)
            futures_price = spot_price * 1.02
            expiry = datetime.now() + timedelta(days=30)

            market = MarketData(
                spot_price=spot_price,
                futures_price=futures_price,
                futures_expiry_date=expiry,
                etf_price=spot_price / 1800,
                fear_greed_index=fear_greed
            )
        else:
            print("[!]  Using sample data (live fetch failed)")
            market = fetcher.create_sample_data()

        # Generate report
        report = analyzer.generate_report(market)
        print(report)

        # Save to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"btc_basis_analysis_{timestamp}.txt"
        with open(filename, 'w') as f:
            f.write(report)
        print(f"\n[OK] Report saved to: {filename}")

        input("\nPress Enter to continue...")

    def start_monitor(self):
        """Start continuous monitoring"""
        self.clear_screen()
        print("\n👁️  Starting Continuous Monitor\n")

        print("Select monitoring interval:")
        print("  1. Every 1 minute")
        print("  2. Every 5 minutes (recommended)")
        print("  3. Every 15 minutes")
        print("  4. Every 60 minutes")
        print("  5. Back to main menu")

        choice = input("\nChoice: ").strip()

        intervals = {
            '1': 60,
            '2': 300,
            '3': 900,
            '4': 3600
        }

        if choice in intervals:
            interval = intervals[choice]
            print(f"\nStarting monitor (checking every {interval}s)")
            print("Press Ctrl+C to stop\n")

            monitor = BasisMonitor(config_path=self.config_file)
            try:
                monitor.run_continuous(interval_seconds=interval)
            except KeyboardInterrupt:
                print("\n\nMonitor stopped.")
                monitor.save_history()
                input("Press Enter to continue...")

    def run_backtest(self):
        """Run backtesting"""
        self.clear_screen()
        print("\n🔙 Running Backtest\n")

        print("Data source:")
        print("  1. Generate sample data (demo)")
        print("  2. Load from CSV file")
        print("  3. Back to main menu")

        choice = input("\nChoice: ").strip()

        if choice == '1':
            print("\nGenerating sample data for 2024...")
            backtester = Backtester(self.config)
            start = datetime(2024, 1, 1)
            end = datetime(2024, 12, 31)
            historical_data = backtester.generate_sample_data(start, end)

            print(f"Running backtest on {len(historical_data)} days...")
            result = backtester.run_backtest(historical_data)

            report = backtester.generate_report(result)
            print(report)

            # Save results
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            json_file = f"backtest_result_{timestamp}.json"
            import json
            with open(json_file, 'w') as f:
                json.dump(result.to_dict(), f, indent=2)
            print(f"Results saved to {json_file}")

        elif choice == '2':
            csv_path = input("Enter CSV file path: ").strip()
            if Path(csv_path).exists():
                print(f"\nLoading data from {csv_path}...")
                backtester = Backtester(self.config)
                try:
                    historical_data = backtester.load_historical_data(csv_path)
                    print(f"Running backtest on {len(historical_data)} records...")
                    result = backtester.run_backtest(historical_data)

                    report = backtester.generate_report(result)
                    print(report)

                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    json_file = f"backtest_result_{timestamp}.json"
                    import json
                    with open(json_file, 'w') as f:
                        json.dump(result.to_dict(), f, indent=2)
                    print(f"Results saved to {json_file}")
                except Exception as e:
                    print(f"[X] Error loading CSV: {e}")
            else:
                print(f"[X] File not found: {csv_path}")

        input("\nPress Enter to continue...")

    def configure_settings(self):
        """Configure settings"""
        self.clear_screen()
        print("\n⚙️  Configuration\n")

        print("Current Configuration:")
        print(f"  Account Size:      ${self.config.account_size:,.2f}")
        print(f"  Funding Cost:      {self.config.funding_cost_annual*100:.2f}% annual")
        print(f"  Leverage:          {self.config.leverage}x")
        print(f"  Min Monthly Basis: {self.config.min_monthly_basis*100:.2f}%")
        print()

        print("Options:")
        print("  1. Change account size")
        print("  2. Change funding cost")
        print("  3. Change leverage")
        print("  4. Load from config.json")
        print("  5. Back to main menu")

        choice = input("\nChoice: ").strip()

        if choice == '1':
            try:
                new_size = float(input("Enter new account size ($): "))
                self.config.account_size = new_size
                print(f"[OK] Account size set to ${new_size:,.2f}")
            except ValueError:
                print("[X] Invalid input")

        elif choice == '2':
            try:
                new_cost = float(input("Enter annual funding cost (e.g., 5 for 5%): ")) / 100
                self.config.funding_cost_annual = new_cost
                print(f"[OK] Funding cost set to {new_cost*100:.2f}%")
            except ValueError:
                print("[X] Invalid input")

        elif choice == '3':
            try:
                new_leverage = float(input("Enter leverage (e.g., 1.5 for 1.5x): "))
                self.config.leverage = new_leverage
                print(f"[OK] Leverage set to {new_leverage}x")
            except ValueError:
                print("[X] Invalid input")

        elif choice == '4':
            if Path(self.config_file).exists():
                import json
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                self.config = TradeConfig(
                    account_size=config_data.get('account_size', 200000),
                    funding_cost_annual=config_data.get('funding_cost_annual', 0.05),
                    leverage=config_data.get('leverage', 1.0)
                )
                print(f"[OK] Configuration loaded from {self.config_file}")
            else:
                print(f"[X] Config file not found: {self.config_file}")

        if choice in ['1', '2', '3', '4']:
            input("\nPress Enter to continue...")

    def quick_status(self):
        """Quick status check"""
        self.clear_screen()
        print("\n📈 Quick Status Check\n")

        fetcher = MarketDataFetcher()
        spot_price = fetcher.fetch_coinbase_spot()

        if spot_price:
            print(f"Current BTC Spot:     ${spot_price:,.2f}")

            # Estimate basis (simplified)
            estimated_basis = spot_price * 0.02  # 2% typical
            monthly_basis_pct = 2.0

            print(f"Estimated Basis:      ~2.0% monthly")
            print(f"Estimated Annual:     ~24.0% gross")
            print(f"Less Funding (5%):    ~19.0% net")
            print()

            if monthly_basis_pct > 1.0:
                print("Signal: [+] FAVORABLE for entry")
            elif monthly_basis_pct > 0.5:
                print("Signal: [~] ACCEPTABLE for entry")
            else:
                print("Signal: ⭕ NOT FAVORABLE")

            print("\n[i] Tip: Run full analysis (Option 1) for detailed assessment")
        else:
            print("[X] Could not fetch current market data")

        input("\nPress Enter to continue...")

    def view_docs(self):
        """View documentation"""
        self.clear_screen()
        print("\n📚 Documentation\n")

        print("Available documentation files:")
        print("  1. README.md - Full documentation")
        print("  2. QUICKSTART.md - Quick start guide")
        print("  3. config_example.json - Configuration template")
        print("  4. Back to main menu")

        choice = input("\nChoice: ").strip()

        files = {
            '1': 'README.md',
            '2': 'QUICKSTART.md',
            '3': 'config_example.json'
        }

        if choice in files:
            filepath = Path(files[choice])
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                print(f"\n{'='*70}")
                print(f" {files[choice]}")
                print(f"{'='*70}\n")
                print(content)
            else:
                print(f"[X] File not found: {files[choice]}")

        input("\nPress Enter to continue...")

    def run(self):
        """Main application loop"""
        while True:
            self.clear_screen()
            self.print_header()
            self.print_menu()

            choice = input("Select option (1-7): ").strip()

            if choice == '1':
                self.run_single_analysis()
            elif choice == '2':
                self.start_monitor()
            elif choice == '3':
                self.run_backtest()
            elif choice == '4':
                self.configure_settings()
            elif choice == '5':
                self.quick_status()
            elif choice == '6':
                self.view_docs()
            elif choice == '7':
                print("\nBye Goodbye!\n")
                sys.exit(0)
            else:
                print("\n[X] Invalid choice. Please select 1-7.")
                input("Press Enter to continue...")


def main():
    """Entry point"""
    cli = BasisTradeCLI()
    cli.run()


if __name__ == "__main__":
    main()
