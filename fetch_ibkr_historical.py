#!/usr/bin/env python3
"""
Fetch Historical BTC Basis Trade Data from IBKR

Gets historical spot (via IBIT ETF) and futures (via CME MBT) prices
and formats them for backtesting.

Output: CSV file ready for btc_basis_backtest.py

Prerequisites:
- IBKR account with market data subscription
- TWS or IB Gateway running
- ib_insync installed: pip install ib-insync
"""

from ib_insync import IB, Stock, Future, util
from datetime import datetime, timedelta
import csv
import time
from typing import List, Dict, Optional


class IBKRHistoricalFetcher:
    """Fetch historical data from IBKR for backtesting"""

    def __init__(self, host='127.0.0.1', port=7497, client_id=2):
        """
        Initialize IBKR connection

        Args:
            host: IBKR address
            port: 7497=paper, 7496=live, 4002=gateway paper, 4001=gateway live
            client_id: Unique client ID
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()
        self.connected = False

    def log(self, message):
        """Print timestamped log message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            print(f"[{timestamp}] {message}")
        except UnicodeEncodeError:
            safe_message = message.encode('ascii', 'replace').decode('ascii')
            print(f"[{timestamp}] {safe_message}")

    def connect(self):
        """Connect to IBKR"""
        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self.connected = True
            self.log(f"[OK] Connected to IBKR ({self.host}:{self.port})")
            return True
        except Exception as e:
            self.log(f"[X] Connection failed: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.connected:
            self.ib.disconnect()
            self.log("[OK] Disconnected")
            self.connected = False

    def get_historical_spot(
        self,
        symbol='IBIT',
        start_date: datetime = None,
        end_date: datetime = None,
        bar_size='1 day'
    ) -> List[Dict]:
        """
        Get historical spot prices from ETF

        Args:
            symbol: ETF symbol (IBIT, FBTC, GBTC)
            start_date: Start date for historical data
            end_date: End date for historical data
            bar_size: Bar size (1 day, 1 hour, etc.)

        Returns:
            List of dicts with date, etf_price, btc_price
        """
        try:
            # Create stock contract
            stock = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(stock)

            self.log(f"Fetching historical data for {symbol}...")

            # Calculate duration
            if not end_date:
                end_date = datetime.now()

            if not start_date:
                start_date = end_date - timedelta(days=365)

            duration_days = (end_date - start_date).days
            duration_str = f"{duration_days} D"

            # Request historical data
            bars = self.ib.reqHistoricalData(
                stock,
                endDateTime=end_date,
                durationStr=duration_str,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,  # Regular trading hours only
                formatDate=1
            )

            self.log(f"[OK] Fetched {len(bars)} bars for {symbol}")

            # Convert to list of dicts
            result = []
            for bar in bars:
                # Convert ETF price to approximate BTC price
                etf_price = bar.close

                if symbol == 'IBIT':
                    btc_price = etf_price * 1850
                elif symbol == 'FBTC':
                    btc_price = etf_price * 1850
                elif symbol == 'GBTC':
                    btc_price = etf_price * 750
                else:
                    btc_price = etf_price * 1850  # Default

                # Ensure date is datetime object
                if isinstance(bar.date, datetime):
                    date_obj = bar.date
                else:
                    date_obj = datetime.combine(bar.date, datetime.min.time())

                result.append({
                    'date': date_obj,
                    'etf_price': etf_price,
                    'btc_price': btc_price
                })

            return result

        except Exception as e:
            self.log(f"[X] Failed to fetch {symbol} historical data: {e}")
            return []

    def get_historical_futures(
        self,
        expiry='202603',
        symbol='MBT',
        start_date: datetime = None,
        end_date: datetime = None,
        bar_size='1 day'
    ) -> List[Dict]:
        """
        Get historical futures prices

        Args:
            expiry: Contract expiry (YYYYMM)
            symbol: MBT or BTC
            start_date: Start date
            end_date: End date
            bar_size: Bar size

        Returns:
            List of dicts with date, futures_price
        """
        try:
            # Create futures contract
            future = Future(symbol, expiry, 'CME')
            self.ib.qualifyContracts(future)

            self.log(f"Fetching historical futures: {future.localSymbol}...")

            # Calculate duration
            if not end_date:
                end_date = datetime.now()

            if not start_date:
                start_date = end_date - timedelta(days=90)

            duration_days = (end_date - start_date).days
            duration_str = f"{duration_days} D"

            # Request historical data
            bars = self.ib.reqHistoricalData(
                future,
                endDateTime=end_date,
                durationStr=duration_str,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            self.log(f"[OK] Fetched {len(bars)} bars for {future.localSymbol}")

            # Convert to list of dicts
            result = []
            for bar in bars:
                futures_price = bar.close

                # Note: IBKR quotes MBT in index points (same as full BTC price)
                # NOT as 0.1 BTC fraction, so no multiplier needed
                # The multiplier (50) refers to contract value per point: $50/point

                # Ensure date is datetime object
                if isinstance(bar.date, datetime):
                    date_obj = bar.date
                else:
                    date_obj = datetime.combine(bar.date, datetime.min.time())

                result.append({
                    'date': date_obj,
                    'futures_price': futures_price
                })

            return result

        except Exception as e:
            self.log(f"[X] Failed to fetch futures historical data: {e}")
            return []

    def get_futures_expiry_date(self, expiry='202603') -> datetime:
        """
        Calculate approximate expiry date for futures contract

        CME Bitcoin futures expire last Friday of contract month

        Args:
            expiry: YYYYMM format

        Returns:
            Approximate expiry datetime
        """
        year = int(expiry[:4])
        month = int(expiry[4:6])

        # Last day of month
        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)

        last_day = next_month - timedelta(days=1)

        # Find last Friday
        # 4 = Friday in weekday() (Monday=0)
        days_back = (last_day.weekday() - 4) % 7
        last_friday = last_day - timedelta(days=days_back)

        return last_friday

    def create_backtest_csv(
        self,
        output_file: str,
        start_date: datetime,
        end_date: datetime,
        futures_contracts: List[str] = None
    ):
        """
        Create CSV file for backtesting

        Args:
            output_file: Output CSV filename
            start_date: Start date for historical data
            end_date: End date for historical data
            futures_contracts: List of futures contract expiries (e.g., ['202512', '202601', '202602'])
                              If None, will use current front month
        """
        if not self.connected:
            self.log("[X] Not connected to IBKR")
            return

        self.log("\n" + "="*70)
        self.log("CREATING BACKTEST DATA FROM IBKR")
        self.log("="*70 + "\n")

        # Default to front month if not specified
        if not futures_contracts:
            # Use current month + next 2 months
            current = datetime.now()
            futures_contracts = []
            for i in range(3):
                month = current.month + i
                year = current.year
                if month > 12:
                    month -= 12
                    year += 1
                futures_contracts.append(f"{year}{month:02d}")

        self.log(f"Period: {start_date.date()} to {end_date.date()}")
        self.log(f"Futures contracts: {futures_contracts}\n")

        # Fetch spot prices (IBIT ETF as proxy)
        spot_data = self.get_historical_spot(
            symbol='IBIT',
            start_date=start_date,
            end_date=end_date,
            bar_size='1 day'
        )

        if not spot_data:
            self.log("[X] Failed to get spot data")
            return

        # Fetch futures for each contract
        all_futures_data = {}
        for expiry in futures_contracts:
            futures_data = self.get_historical_futures(
                expiry=expiry,
                symbol='MBT',
                start_date=start_date,
                end_date=end_date,
                bar_size='1 day'
            )

            if futures_data:
                expiry_date = self.get_futures_expiry_date(expiry)
                for entry in futures_data:
                    date_key = entry['date'].date()
                    if date_key not in all_futures_data:
                        all_futures_data[date_key] = {
                            'futures_price': entry['futures_price'],
                            'expiry': expiry_date
                        }

            # Wait between requests to avoid rate limiting
            time.sleep(1)

        # Merge spot and futures data
        merged_data = []
        for spot_entry in spot_data:
            date_key = spot_entry['date'].date()

            if date_key in all_futures_data:
                futures_info = all_futures_data[date_key]

                merged_data.append({
                    'date': spot_entry['date'],
                    'spot_price': spot_entry['btc_price'],
                    'futures_price': futures_info['futures_price'],
                    'futures_expiry': futures_info['expiry']
                })

        if not merged_data:
            self.log("[X] No merged data available")
            return

        # Write to CSV
        self.log(f"\nWriting {len(merged_data)} rows to {output_file}...")

        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['date', 'spot_price', 'futures_price', 'futures_expiry'])
            writer.writeheader()

            for row in merged_data:
                writer.writerow({
                    'date': row['date'].strftime('%Y-%m-%d'),
                    'spot_price': f"{row['spot_price']:.2f}",
                    'futures_price': f"{row['futures_price']:.2f}",
                    'futures_expiry': row['futures_expiry'].strftime('%Y-%m-%d')
                })

        self.log(f"[OK] CSV file created: {output_file}")

        # Show sample
        self.log("\nSample data (first 5 rows):")
        self.log("-" * 70)
        self.log(f"{'Date':<12} {'Spot':<12} {'Futures':<12} {'Basis %':<10} {'Expiry':<12}")
        self.log("-" * 70)

        for i, row in enumerate(merged_data[:5]):
            basis_pct = ((row['futures_price'] - row['spot_price']) / row['spot_price']) * 100
            self.log(
                f"{row['date'].date()!s:<12} "
                f"${row['spot_price']:<11,.2f} "
                f"${row['futures_price']:<11,.2f} "
                f"{basis_pct:<9.2f}% "
                f"{row['futures_expiry'].date()!s:<12}"
            )

        self.log("-" * 70)
        self.log(f"\n[OK] Ready for backtesting with: python btc_basis_backtest.py --data {output_file}")


def main():
    """Main entry point"""
    print("\n" + "="*70)
    print("IBKR HISTORICAL DATA FETCHER FOR BACKTESTING")
    print("="*70 + "\n")

    # Configuration
    start_date = datetime(2025, 10, 1)  # Start date (Oct 2025 for recent data)
    end_date = datetime.now()            # End date (today)
    output_file = "btc_basis_ibkr_historical.csv"

    # Futures contracts to include (currently active contracts only)
    # Format: YYYYMM (e.g., 202602 = February 2026)
    # Note: Expired contracts (202512, 202601) won't have data
    futures_contracts = [
        '202602',  # Feb 2026 (MBTG6)
        '202603',  # Mar 2026 (MBTH6)
        '202604',  # Apr 2026 (MBTJ6)
    ]

    # Try to connect to IBKR
    ports = {
        7497: "TWS Paper Trading",
        4002: "IB Gateway Paper",
        7496: "TWS Live",
        4001: "IB Gateway Live"
    }

    fetcher = None

    for port, description in ports.items():
        print(f"Trying {description} (port {port})...")
        fetcher = IBKRHistoricalFetcher(port=port, client_id=2)

        if fetcher.connect():
            break
        else:
            print()

    if not fetcher or not fetcher.connected:
        print("\n" + "="*70)
        print("[X] FAILED - Could not connect to IBKR")
        print("="*70 + "\n")
        return

    try:
        # Create backtest CSV
        fetcher.create_backtest_csv(
            output_file=output_file,
            start_date=start_date,
            end_date=end_date,
            futures_contracts=futures_contracts
        )

    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user")

    finally:
        fetcher.disconnect()


if __name__ == "__main__":
    try:
        import ib_insync
    except ImportError:
        print("\n[X] ERROR: ib_insync not installed")
        print("\nInstall with: pip install ib-insync")
        print("Then run this script again\n")
        exit(1)

    main()
