#!/usr/bin/env python3
"""
Fetch Bitcoin Futures from IBKR - Based on Working ibkr-gold-silver Skill

This is the PROVEN working method from the ibkr-gold-silver skill,
adapted for Bitcoin futures.

Prerequisites:
1. IBKR account (paper or live)
2. TWS or IB Gateway running
3. API enabled in TWS: Global Configuration → API → Settings → Enable Socket Clients
4. Install: pip install ib-insync

Ports:
- TWS Paper: 7497
- TWS Live: 7496
- IB Gateway Paper: 4002
- IB Gateway Live: 4001
"""

from ib_insync import IB, Future, Stock
from datetime import datetime
import time


class BTCFuturesFetcher:
    """Fetch CME Bitcoin Futures prices from IBKR"""

    def __init__(self, host='127.0.0.1', port=7497, client_id=1):
        """
        Initialize IBKR connection

        Args:
            host: IBKR address (default: localhost)
            port: 7497=paper, 7496=live, 4002=gateway paper, 4001=gateway live
            client_id: Unique client ID (1-32)
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()
        self.connected = False

    def log(self, message):
        """Print log message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            print(f"[{timestamp}] {message}")
        except UnicodeEncodeError:
            # Windows console encoding fallback
            safe_message = message.encode('ascii', 'replace').decode('ascii')
            print(f"[{timestamp}] {safe_message}")

    def connect(self):
        """Connect to IBKR TWS/Gateway"""
        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self.connected = True
            self.log(f"[OK] Connected to IBKR ({self.host}:{self.port})")

            # Show account info
            account_summary = self.ib.accountSummary()
            for item in account_summary:
                if item.tag == 'NetLiquidation' and item.currency == 'USD':
                    self.log(f"[*] Account Value: ${float(item.value):,.2f} USD")

            return True

        except Exception as e:
            self.log(f"[X] Connection failed: {e}")
            self.log("Tips:")
            self.log("  1. Ensure TWS or IB Gateway is running")
            self.log("  2. Enable API in TWS: File -> Global Configuration -> API -> Settings")
            self.log("  3. Check 'Enable ActiveX and Socket Clients'")
            self.log("  4. Add trusted IP: 127.0.0.1")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.connected:
            self.ib.disconnect()
            self.log("[OK] Disconnected")
            self.connected = False

    def get_btc_futures_price(self, expiry='202603', symbol='MBT'):
        """
        Get CME Bitcoin Futures price (PROVEN METHOD from gold-silver skill)

        Args:
            expiry: Contract expiry in YYYYMM format (e.g., '202603' = March 2026)
            symbol: 'MBT' (Micro Bitcoin 0.1 BTC) or 'BTC' (Standard 5 BTC)
                   Most retail accounts only have access to MBT

        Returns:
            Dictionary with futures data or None
        """
        try:
            # Create Bitcoin futures contract
            # MBT = Micro Bitcoin (0.1 BTC per contract) - most common for retail
            # BTC = Standard Bitcoin (5 BTC per contract) - institutional/large accounts
            btc_future = Future(symbol, expiry, 'CME')

            self.log(f"Looking for BTC futures expiring {expiry}...")

            # Qualify contract (confirm it exists)
            self.ib.qualifyContracts(btc_future)

            self.log(f"[OK] Contract found: {btc_future.localSymbol}")

            # Request market data (same method as gold-silver skill)
            ticker = self.ib.reqMktData(btc_future, '', False, False)

            # Wait for data to arrive
            self.ib.sleep(2)

            # Get price - try marketPrice() first, fallback to last
            futures_price = ticker.marketPrice()

            if not futures_price or futures_price <= 0:
                futures_price = ticker.last

            # Get other fields
            bid = ticker.bid if ticker.bid and ticker.bid > 0 else None
            ask = ticker.ask if ticker.ask and ticker.ask > 0 else None
            close = ticker.close if ticker.close and ticker.close > 0 else None
            volume = ticker.volume if ticker.volume and ticker.volume >= 0 else None

            # Cancel market data subscription
            self.ib.cancelMktData(btc_future)

            if futures_price and futures_price > 0:
                self.log(f"[OK] BTC Futures: ${futures_price:,.2f}")

                return {
                    'symbol': 'BTC',
                    'exchange': 'CME',
                    'expiry': expiry,
                    'local_symbol': btc_future.localSymbol,
                    'futures_price': futures_price,
                    'bid': bid,
                    'ask': ask,
                    'close': close,
                    'volume': volume,
                    'timestamp': datetime.now()
                }
            else:
                self.log("[X] No valid price data")
                return None

        except Exception as e:
            self.log(f"[X] Failed to get futures price: {e}")
            return None

    def get_btc_spot_price(self):
        """Get BTC spot price (for basis calculation)"""
        try:
            # Try to import our spot price fetcher
            import sys
            import os
            sys.path.insert(0, os.path.dirname(__file__))
            from get_btc_prices import fetch_coinbase_spot

            spot = fetch_coinbase_spot()
            if spot:
                self.log(f"[OK] BTC Spot: ${spot:,.2f}")
                return spot
        except:
            pass

        return None

    def get_btc_basis_data(self, expiry='202603', symbol='MBT'):
        """
        Get complete basis trade data (spot + futures + basis calculation)

        Args:
            expiry: Futures contract expiry (YYYYMM format, e.g., '202603')
            symbol: 'MBT' (Micro Bitcoin) or 'BTC' (Standard)

        Returns:
            Dictionary with complete basis trade data
        """
        # Get futures price
        futures_data = self.get_btc_futures_price(expiry, symbol)

        if not futures_data:
            return None

        # Get spot price
        spot_price = self.get_btc_spot_price()

        if not spot_price:
            self.log("[!] Warning: Could not fetch spot price")
            return futures_data

        # Calculate basis
        futures_price = futures_data['futures_price']
        basis_absolute = futures_price - spot_price
        basis_percent = (basis_absolute / spot_price) * 100

        # Calculate days to expiry
        expiry_date = datetime.strptime(expiry, '%Y%m%d')
        days_to_expiry = (expiry_date - datetime.now()).days

        # Calculate monthly and annualized basis
        monthly_basis = basis_percent * (30 / days_to_expiry) if days_to_expiry > 0 else 0
        annualized_basis = basis_percent * (365 / days_to_expiry) if days_to_expiry > 0 else 0

        self.log(f"[*] Basis: ${basis_absolute:,.2f} ({basis_percent:.2f}%)")
        self.log(f"[*] Monthly Basis: {monthly_basis:.2f}%")
        self.log(f"[*] Annualized: {annualized_basis:.2f}%")

        return {
            **futures_data,
            'spot_price': spot_price,
            'basis_absolute': basis_absolute,
            'basis_percent': basis_percent,
            'days_to_expiry': days_to_expiry,
            'monthly_basis': monthly_basis,
            'annualized_basis': annualized_basis,
            'expiry_date': expiry_date
        }


def main():
    """Main entry point"""
    print("\n" + "="*70)
    print("CME BITCOIN FUTURES FETCHER (IBKR)")
    print("Based on proven ibkr-gold-silver skill pattern")
    print("="*70 + "\n")

    # Try different ports (paper trading first)
    ports = {
        7497: "TWS Paper Trading",
        4002: "IB Gateway Paper",
        7496: "TWS Live",
        4001: "IB Gateway Live"
    }

    fetcher = None

    # Try to connect
    for port, description in ports.items():
        print(f"Trying {description} (port {port})...")
        fetcher = BTCFuturesFetcher(port=port)

        if fetcher.connect():
            break
        else:
            print()

    if not fetcher or not fetcher.connected:
        print("\n" + "="*70)
        print("[X] FAILED - Could not connect to any IBKR instance")
        print("="*70)
        print("\nMake sure TWS or IB Gateway is running and API is enabled")
        print("="*70 + "\n")
        return

    try:
        # Get front month futures (March 2026)
        # CME BTC futures expire last Friday of month
        # Format: YYYYMM (e.g., '202603' = March 2026)
        expiry = '202603'  # March 2026
        symbol = 'MBT'     # Micro Bitcoin (0.1 BTC per contract)
                          # Use 'BTC' for standard 5 BTC contract (if you have permissions)

        print(f"\nFetching {symbol} futures data (expiry: {expiry})...\n")

        data = fetcher.get_btc_basis_data(expiry, symbol)

        if data:
            print("\n" + "="*70)
            print("[*] SUCCESS - CME BITCOIN FUTURES DATA")
            print("="*70)
            print(f"\nContract: {data['local_symbol']}")
            print(f"Exchange: {data['exchange']}")
            print(f"Expiry:   {data['expiry']}")
            print(f"\nSpot Price:      ${data['spot_price']:,.2f}")
            print(f"Futures Price:   ${data['futures_price']:,.2f}")
            print(f"Bid/Ask:         ${data.get('bid', 0):,.2f} / ${data.get('ask', 0):,.2f}")

            print(f"\nBasis (Abs):     ${data['basis_absolute']:,.2f}")
            print(f"Basis (%):       {data['basis_percent']:.2f}%")
            print(f"Days to Expiry:  {data['days_to_expiry']}")
            print(f"Monthly Basis:   {data['monthly_basis']:.2f}%")
            print(f"Annualized:      {data['annualized_basis']:.2f}%")

            print("\n" + "="*70)
            print("[OK] Ready to integrate into your basis trade analyzer!")
            print("="*70 + "\n")
        else:
            print("\n[X] Failed to fetch futures data")
            print("Check that:")
            print("  - Market is open (CME hours: Sun 6PM - Fri 5PM ET)")
            print("  - You have futures permissions enabled")
            print("  - Market data subscription is active\n")

    finally:
        fetcher.disconnect()


if __name__ == "__main__":
    # Check if ib_insync is installed
    try:
        import ib_insync
    except ImportError:
        print("\n[X] ERROR: ib_insync not installed")
        print("\nInstall with: pip install ib-insync")
        print("Then run this script again\n")
        exit(1)

    main()
