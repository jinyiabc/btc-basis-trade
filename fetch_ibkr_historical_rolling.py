#!/usr/bin/env python3
"""
Fetch Historical BTC Basis Trade Data with ROLLING FUTURES

This version correctly pairs each historical spot price with the
front-month futures contract that was actually trading at that time.

Key improvement: Dynamic contract selection based on date
"""

from ib_insync import IB, Stock, Future
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import csv
import time


class IBKRHistoricalRollingFetcher:
    """Fetch historical data with proper futures rolling"""

    def __init__(self, host='127.0.0.1', port=7497, client_id=2):
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
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.connected:
            self.ib.disconnect()
            self.log("[OK] Disconnected")
            self.connected = False

    def get_front_month_contract(self, date: datetime) -> str:
        """
        Determine front-month futures contract for a given date

        Rule: Use the contract that expires 30-90 days out from the date

        Args:
            date: Historical date

        Returns:
            Contract expiry in YYYYMM format
        """
        # Target: 60 days out (middle of typical 30-90 day range)
        target_date = date + timedelta(days=60)

        year = target_date.year
        month = target_date.month

        return f"{year}{month:02d}"

    def get_all_contracts_for_period(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[str]:
        """
        Get all futures contracts needed for a date range

        Args:
            start_date: Start of historical period
            end_date: End of historical period

        Returns:
            List of contract expiries (YYYYMM)
        """
        contracts = set()

        # Check front-month for start, middle, and end dates
        dates_to_check = [
            start_date,
            start_date + (end_date - start_date) / 3,
            start_date + 2 * (end_date - start_date) / 3,
            end_date
        ]

        for date in dates_to_check:
            contract = self.get_front_month_contract(date)
            contracts.add(contract)

            # Also add adjacent months for safety
            date_plus = date + timedelta(days=30)
            date_minus = date - timedelta(days=30)
            contracts.add(self.get_front_month_contract(date_plus))
            contracts.add(self.get_front_month_contract(date_minus))

        return sorted(list(contracts))

    def get_contract_expiry_date(self, expiry_yyyymm: str) -> Optional[datetime]:
        """
        Get actual expiry date from IBKR for a contract

        Args:
            expiry_yyyymm: YYYYMM format

        Returns:
            Expiry datetime or None
        """
        try:
            future = Future('MBT', expiry_yyyymm, 'CME')
            self.ib.qualifyContracts(future)

            if future.lastTradeDateOrContractMonth:
                expiry_str = future.lastTradeDateOrContractMonth
                if len(expiry_str) == 8:
                    return datetime.strptime(expiry_str, '%Y%m%d')

            return None

        except Exception as e:
            return None

    def fetch_all_futures_data(
        self,
        contracts: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Dict]:
        """
        Fetch historical futures data for all contracts

        Args:
            contracts: List of contract expiries (YYYYMM)
            start_date: Start date
            end_date: End date

        Returns:
            Dict mapping contract expiry -> {date -> {price, expiry_date}}
        """
        all_data = {}

        for contract in contracts:
            self.log(f"Fetching contract {contract}...")

            try:
                future = Future('MBT', contract, 'CME')
                self.ib.qualifyContracts(future)

                # Get actual expiry
                expiry_date = None
                if future.lastTradeDateOrContractMonth:
                    expiry_str = future.lastTradeDateOrContractMonth
                    if len(expiry_str) == 8:
                        expiry_date = datetime.strptime(expiry_str, '%Y%m%d')
                        self.log(f"  Expiry: {expiry_date.strftime('%Y-%m-%d')}")

                # Fetch historical bars
                duration_days = (end_date - start_date).days + 30
                bars = self.ib.reqHistoricalData(
                    future,
                    endDateTime=end_date,
                    durationStr=f"{duration_days} D",
                    barSizeSetting='1 day',
                    whatToShow='TRADES',
                    useRTH=True,
                    formatDate=1
                )

                self.log(f"  [OK] Fetched {len(bars)} bars")

                # Store by date
                contract_data = {}
                for bar in bars:
                    bar_date = bar.date if isinstance(bar.date, datetime) else datetime.combine(bar.date, datetime.min.time())
                    date_key = bar_date.date()

                    contract_data[date_key] = {
                        'futures_price': bar.close,
                        'expiry_date': expiry_date
                    }

                all_data[contract] = contract_data

                time.sleep(1)  # Rate limiting

            except Exception as e:
                self.log(f"  [X] Failed: {e}")
                continue

        return all_data

    def select_appropriate_contract(
        self,
        date: datetime,
        all_futures_data: Dict[str, Dict]
    ) -> Optional[Dict]:
        """
        Select the most appropriate futures contract for a given date

        Rule: Use front-month contract (30-90 days to expiry)

        Args:
            date: Historical date
            all_futures_data: All available futures data

        Returns:
            Dict with futures_price and expiry_date, or None
        """
        date_key = date.date()
        best_contract = None
        best_days_to_expiry = None

        for contract_expiry, contract_data in all_futures_data.items():
            if date_key not in contract_data:
                continue

            data = contract_data[date_key]
            if not data['expiry_date']:
                continue

            days_to_expiry = (data['expiry_date'] - date).days

            # Front-month: 30-90 days out (prefer 60)
            if 30 <= days_to_expiry <= 90:
                # Prefer closest to 60 days
                if best_days_to_expiry is None:
                    best_contract = data
                    best_days_to_expiry = days_to_expiry
                elif abs(days_to_expiry - 60) < abs(best_days_to_expiry - 60):
                    best_contract = data
                    best_days_to_expiry = days_to_expiry

        # If no contract in ideal range, use closest available
        if not best_contract:
            for contract_expiry, contract_data in all_futures_data.items():
                if date_key not in contract_data:
                    continue

                data = contract_data[date_key]
                if not data['expiry_date']:
                    continue

                days_to_expiry = (data['expiry_date'] - date).days

                if days_to_expiry > 0:  # Must be future expiry
                    if best_days_to_expiry is None or days_to_expiry < best_days_to_expiry:
                        best_contract = data
                        best_days_to_expiry = days_to_expiry

        return best_contract

    def create_rolling_backtest_csv(
        self,
        output_file: str,
        start_date: datetime,
        end_date: datetime
    ):
        """
        Create CSV with properly rolled futures contracts

        Each historical date is paired with the appropriate front-month contract

        Args:
            output_file: Output CSV filename
            start_date: Start date
            end_date: End date
        """
        self.log("\n" + "="*70)
        self.log("CREATING ROLLING FUTURES BACKTEST DATA")
        self.log("="*70 + "\n")

        self.log(f"Period: {start_date.date()} to {end_date.date()}")

        # Step 1: Determine all needed contracts
        self.log("\nStep 1: Determining contracts needed...")
        contracts = self.get_all_contracts_for_period(start_date, end_date)
        self.log(f"Contracts: {contracts}\n")

        # Step 2: Fetch spot prices
        self.log("Step 2: Fetching spot prices (IBIT)...")
        stock = Stock('IBIT', 'SMART', 'USD')
        self.ib.qualifyContracts(stock)

        duration_days = (end_date - start_date).days
        spot_bars = self.ib.reqHistoricalData(
            stock,
            endDateTime=end_date,
            durationStr=f"{duration_days} D",
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )

        self.log(f"[OK] Fetched {len(spot_bars)} spot bars\n")

        # Step 3: Fetch all futures contracts
        self.log("Step 3: Fetching futures contracts...")
        all_futures_data = self.fetch_all_futures_data(contracts, start_date, end_date)

        # Step 4: Merge with appropriate contract selection
        self.log("\nStep 4: Pairing spot with appropriate futures...")

        merged_data = []
        for bar in spot_bars:
            bar_date = bar.date if isinstance(bar.date, datetime) else datetime.combine(bar.date, datetime.min.time())

            # Get spot price
            spot_price = bar.close * 1850  # IBIT to BTC conversion

            # Select appropriate futures contract
            futures_data = self.select_appropriate_contract(bar_date, all_futures_data)

            if futures_data:
                merged_data.append({
                    'date': bar_date,
                    'spot_price': spot_price,
                    'futures_price': futures_data['futures_price'],
                    'futures_expiry': futures_data['expiry_date']
                })

        self.log(f"[OK] Merged {len(merged_data)} data points\n")

        # Step 5: Write CSV
        self.log(f"Step 5: Writing to {output_file}...")

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

        self.log(f"[OK] CSV created\n")

        # Step 6: Show sample with basis
        self.log("Sample data (first 5 rows):")
        self.log("-" * 70)
        self.log(f"{'Date':<12} {'Spot':<12} {'Futures':<12} {'Basis %':<10} {'Days':<6} {'Expiry':<12}")
        self.log("-" * 70)

        for i, row in enumerate(merged_data[:5]):
            basis_pct = ((row['futures_price'] - row['spot_price']) / row['spot_price']) * 100
            days_to_expiry = (row['futures_expiry'] - row['date']).days

            self.log(
                f"{row['date'].date()!s:<12} "
                f"${row['spot_price']:<11,.2f} "
                f"${row['futures_price']:<11,.2f} "
                f"{basis_pct:<9.2f}% "
                f"{days_to_expiry:<6} "
                f"{row['futures_expiry'].date()!s:<12}"
            )

        self.log("-" * 70)
        self.log(f"\n[OK] Ready for: python btc_basis_backtest.py --data {output_file}")


def main():
    """Main entry point"""
    print("\n" + "="*70)
    print("IBKR ROLLING FUTURES HISTORICAL DATA FETCHER")
    print("="*70 + "\n")

    # Configuration
    start_date = datetime(2025, 10, 1)
    end_date = datetime.now()
    output_file = "btc_basis_ibkr_rolling.csv"

    # Connect to IBKR
    ports = {
        7497: "TWS Paper",
        4002: "Gateway Paper",
        7496: "TWS Live",
        4001: "Gateway Live"
    }

    fetcher = None

    for port, description in ports.items():
        print(f"Trying {description} (port {port})...")
        fetcher = IBKRHistoricalRollingFetcher(port=port, client_id=5)

        if fetcher.connect():
            break

    if not fetcher or not fetcher.connected:
        print("\n[X] FAILED - Could not connect to IBKR\n")
        return

    try:
        fetcher.create_rolling_backtest_csv(
            output_file=output_file,
            start_date=start_date,
            end_date=end_date
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
        print("\nInstall with: pip install ib-insync\n")
        exit(1)

    main()
