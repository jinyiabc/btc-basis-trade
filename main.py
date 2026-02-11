#!/usr/bin/env python3
"""
BTC Basis Trade Analyzer - Main Entry Point

Bitcoin Basis Trade Analysis Toolkit
Market-Neutral Cash & Carry Arbitrage

Usage:
    python main.py analyze           # Run single analysis
    python main.py backtest          # Run backtest with sample data
    python main.py backtest --data FILE.csv  # Run backtest with CSV
    python main.py monitor           # Start continuous monitoring
    python main.py monitor --once    # Single check
    python main.py cli               # Interactive CLI menu
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path for package imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from btc_basis.core.models import Signal, TradeConfig, MarketData
from btc_basis.core.analyzer import BasisTradeAnalyzer
from btc_basis.data.coinbase import CoinbaseFetcher, FearGreedFetcher
from btc_basis.backtest.engine import Backtester
from btc_basis.monitor.daemon import BasisMonitor
from btc_basis.utils.config import ConfigLoader
from btc_basis.utils.io import ReportWriter


def cmd_analyze(args):
    """Run single market analysis."""
    print("\n*** Bitcoin Basis Trade Analyzer ***\n")

    # Load config
    config_loader = ConfigLoader(args.config)
    config = TradeConfig.from_dict(config_loader.get_all())
    analyzer = BasisTradeAnalyzer(config)

    # Initialize fetchers
    coinbase = CoinbaseFetcher()
    fear_greed = FearGreedFetcher()

    print("Fetching market data...")

    # Try IBKR first if available
    ibkr_data = None
    try:
        from btc_basis.data.ibkr import IBKRFetcher

        print("[1/3] Trying IBKR (spot + futures)...")
        ibkr_config = config_loader.ibkr
        ibkr = IBKRFetcher.from_config(ibkr_config)
        if ibkr.connect():
            ibkr_data = ibkr.get_complete_basis_data()
            ibkr.disconnect()
    except ImportError:
        print("[1/3] IBKR not available (ib_insync not installed)")
    except Exception as e:
        print(f"[1/3] IBKR failed: {e}")

    if ibkr_data:
        print(f"[OK] IBKR: Spot ${ibkr_data['spot_price']:,.2f}")
        print(f"[OK] IBKR: Futures ${ibkr_data['futures_price']:,.2f}")

        fg_index = fear_greed.fetch_index()

        market = MarketData(
            spot_price=ibkr_data["spot_price"],
            futures_price=ibkr_data["futures_price"],
            futures_expiry_date=datetime.strptime(
                ibkr_data["expiry"] + "27", "%Y%m%d"
            ),
            etf_price=ibkr_data["etf_price"],
            fear_greed_index=fg_index,
            cme_open_interest=ibkr_data.get("volume"),
        )
    else:
        # Fallback to Coinbase + estimated futures
        print("[2/3] Trying Coinbase spot...")
        spot_price = coinbase.fetch_spot_price()
        fg_index = fear_greed.fetch_index()

        if spot_price:
            print(f"[OK] Coinbase Spot: ${spot_price:,.2f}")
            print("[!]  Using ESTIMATED futures (spot * 1.02)")

            futures_price = spot_price * 1.02
            expiry = datetime.now() + timedelta(days=30)

            market = MarketData(
                spot_price=spot_price,
                futures_price=futures_price,
                futures_expiry_date=expiry,
                etf_price=spot_price / 1800,
                fear_greed_index=fg_index,
            )
        else:
            print("[3/3] Using sample data")
            market = MarketData(
                spot_price=95000.0,
                futures_price=97200.0,
                futures_expiry_date=datetime.now() + timedelta(days=30),
                etf_price=53.50,
                etf_nav=53.45,
                fear_greed_index=0.75,
                cme_open_interest=35000,
            )

    # Generate and print report
    report = analyzer.generate_report(market)
    print(report)

    # Save outputs
    writer = ReportWriter()
    export_data = analyzer.get_export_data(market)
    files = writer.write_analysis_output(report, export_data, "btc_basis_analysis")

    print(f"[File] Report saved to: {files['text_report']}")
    print(f"[Data] JSON data exported to: {files['json_data']}\n")


def cmd_backtest(args):
    """Run backtesting."""
    print("\n*** Bitcoin Basis Trade Backtester ***\n")

    config_loader = ConfigLoader(args.config)
    config = TradeConfig.from_dict(config_loader.get_all())
    backtester = Backtester(config)

    if args.data:
        print(f"Loading historical data from {args.data}...")
        historical_data = backtester.load_historical_data(args.data)
    else:
        print("Generating sample data...")
        start = (
            datetime.fromisoformat(args.start)
            if args.start
            else datetime(2024, 1, 1)
        )
        end = (
            datetime.fromisoformat(args.end) if args.end else datetime(2024, 12, 31)
        )
        historical_data = backtester.generate_sample_data(start, end)

    print(f"Running backtest on {len(historical_data)} data points...")
    result = backtester.run_backtest(
        historical_data, max_holding_days=args.holding_days
    )

    # Print report
    report = backtester.generate_report(result)
    print(report)

    # Save results
    writer = ReportWriter()
    json_file = writer.write_backtest_result(result.to_dict())
    print(f"Results saved to {json_file}")


def cmd_monitor(args):
    """Run monitoring."""
    monitor = BasisMonitor(config_path=args.config)

    # Apply CLI execution overrides
    execute = getattr(args, "execute", False)
    auto_trade = getattr(args, "auto_trade", False)
    dry_run = getattr(args, "dry_run", False)

    if execute and not monitor.execution_manager:
        # Enable execution via CLI even if config has enabled=false
        try:
            from btc_basis.execution.models import ExecutionConfig
            from btc_basis.execution.manager import ExecutionManager

            exec_cfg = monitor.config_loader.execution or {}
            exec_cfg["enabled"] = True
            if auto_trade:
                exec_cfg["auto_trade"] = True
            if dry_run:
                exec_cfg["dry_run"] = True

            execution_config = ExecutionConfig.from_dict(exec_cfg)
            ibkr_cfg = monitor.config_loader.ibkr or {}
            monitor.execution_manager = ExecutionManager(
                exec_config=execution_config,
                analyzer=monitor.analyzer,
                ibkr_host=ibkr_cfg.get("host", "127.0.0.1"),
                ibkr_port=ibkr_cfg.get("port"),
            )
        except Exception as e:
            print(f"[X] Failed to initialize execution: {e}")

        # Init IBKR data fetcher for real ETF/futures prices
        if not monitor.ibkr_fetcher:
            try:
                from btc_basis.data.ibkr import IBKRFetcher

                ibkr_cfg = monitor.config_loader.ibkr or {}
                monitor.ibkr_fetcher = IBKRFetcher.from_config(ibkr_cfg)
            except ImportError:
                print("[X] ib_insync not installed — IBKR data unavailable")
            except Exception as e:
                print(f"[X] IBKR data fetcher init failed: {e}")
    elif monitor.execution_manager:
        # Apply overrides to existing execution manager
        if auto_trade:
            monitor.execution_manager.config.auto_trade = True
        if dry_run:
            monitor.execution_manager.config.dry_run = True

    if args.once:
        monitor.run_once()
    else:
        monitor.run_continuous(interval_seconds=args.interval)


def cmd_cli(args):
    """Run interactive CLI menu."""
    import os

    def clear_screen():
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header():
        print("""
+======================================================================+
|         Bitcoin Basis Trade Analysis Toolkit                         |
|         Market-Neutral Cash & Carry Arbitrage                        |
+======================================================================+
""")

    def print_menu():
        print("\n[*] MAIN MENU\n")
        print("  1. Run Single Analysis")
        print("  2. Run Backtest (sample data)")
        print("  3. Run Monitor (single check)")
        print("  4. Exit")
        print()

    while True:
        clear_screen()
        print_header()
        print_menu()

        choice = input("Select option (1-4): ").strip()

        if choice == '1':
            cmd_analyze(args)
            input("\nPress Enter to continue...")
        elif choice == '2':
            cmd_backtest(args)
            input("\nPress Enter to continue...")
        elif choice == '3':
            args.once = True
            cmd_monitor(args)
            input("\nPress Enter to continue...")
        elif choice == '4':
            print("\nGoodbye!\n")
            sys.exit(0)
        else:
            print("\n[X] Invalid choice. Please select 1-4.")
            input("Press Enter to continue...")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="BTC Basis Trade Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py analyze                    # Single analysis
  python main.py backtest                   # Backtest with sample data
  python main.py backtest --data data.csv   # Backtest with CSV file
  python main.py monitor                    # Continuous monitoring
  python main.py monitor --once             # Single check
        """,
    )
    parser.add_argument(
        "--config", type=str, help="Path to config JSON file", default=None
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Run single analysis")

    # Backtest command
    backtest_parser = subparsers.add_parser(
        "backtest", help="Run backtesting"
    )
    backtest_parser.add_argument(
        "--data", type=str, help="Path to historical CSV data"
    )
    backtest_parser.add_argument(
        "--start", type=str, help="Start date (YYYY-MM-DD)"
    )
    backtest_parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    backtest_parser.add_argument(
        "--holding-days",
        type=int,
        default=30,
        help="Max holding period in days (default: 30)",
    )

    # Monitor command
    monitor_parser = subparsers.add_parser(
        "monitor", help="Run continuous monitoring"
    )
    monitor_parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Check interval in seconds (default: 300)",
    )
    monitor_parser.add_argument(
        "--once", action="store_true", help="Run once and exit"
    )
    monitor_parser.add_argument(
        "--execute", action="store_true", help="Enable trade execution"
    )
    monitor_parser.add_argument(
        "--auto-trade",
        action="store_true",
        help="Auto-execute without confirmation prompts",
    )
    monitor_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log orders but do not submit to IBKR",
    )

    # CLI command
    cli_parser = subparsers.add_parser("cli", help="Interactive CLI menu")

    args = parser.parse_args()

    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "backtest":
        cmd_backtest(args)
    elif args.command == "monitor":
        cmd_monitor(args)
    elif args.command == "cli":
        cmd_cli(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
