#!/usr/bin/env python3
"""
Unified IBKR BTC Price Fetcher - Get BOTH Spot and Futures from IBKR

Gets both BTC spot price (via IBIT ETF or PAXG proxy) and futures in ONE connection.
No need for external Coinbase API!

Based on proven ibkr-gold-silver skill pattern.
"""

from ib_insync import IB, Future, Stock, Index
from datetime import datetime
import time


class UnifiedBTCFetcher:
    """Get both spot and futures from IBKR in one connection"""

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

    def get_btc_spot_price(self):
        """
        Get BTC spot price from IBKR using multiple methods

        Methods tried in order:
        1. IBIT ETF (BlackRock Bitcoin ETF) - most liquid
        2. FBTC ETF (Fidelity Bitcoin ETF)
        3. GBTC (Grayscale Bitcoin Trust)

        Returns:
            Spot price in USD or None
        """
        # Try different BTC spot proxies
        spot_symbols = [
            ('IBIT', 'BlackRock Bitcoin ETF'),
            ('FBTC', 'Fidelity Bitcoin ETF'),
            ('GBTC', 'Grayscale Bitcoin Trust'),
        ]

        for symbol, description in spot_symbols:
            try:
                self.log(f"Trying {symbol} ({description})...")

                # Create stock contract
                contract = Stock(symbol, 'SMART', 'USD')

                # Qualify contract
                self.ib.qualifyContracts(contract)

                # Request market data
                ticker = self.ib.reqMktData(contract, '', False, False)

                # Wait for data
                self.ib.sleep(2)

                # Get price
                price = ticker.marketPrice()

                if not price or price <= 0:
                    price = ticker.last

                # Cancel subscription
                self.ib.cancelMktData(contract)

                if price and price > 0:
                    # ETF price represents BTC price / shares outstanding
                    # For IBIT: approximate BTC price = IBIT price * 1850
                    # (This multiplier varies by ETF - IBIT typically trades around 1/1850th of BTC)

                    # Get approximate BTC price
                    if symbol == 'IBIT':
                        btc_price = price * 1850  # Approximate multiplier for IBIT
                    elif symbol == 'FBTC':
                        btc_price = price * 1850  # Similar to IBIT
                    elif symbol == 'GBTC':
                        btc_price = price * 750   # GBTC has different multiplier

                    self.log(f"[OK] {symbol}: ${price:.2f} -> BTC ~${btc_price:,.2f}")

                    return {
                        'source': symbol,
                        'description': description,
                        'etf_price': price,
                        'btc_price': btc_price,
                        'note': f'Estimated from {symbol} ETF price'
                    }

            except Exception as e:
                self.log(f"[X] {symbol} failed: {e}")
                continue

        self.log("[X] Could not get spot price from any source")
        return None

    def get_btc_futures_price(self, expiry='202603', symbol='MBT'):
        """
        Get CME Bitcoin Futures price

        Args:
            expiry: Contract expiry in YYYYMM format (e.g., '202603')
            symbol: 'MBT' (Micro Bitcoin 0.1 BTC) or 'BTC' (Standard 5 BTC)

        Returns:
            Dictionary with futures data or None
        """
        try:
            # Create futures contract
            btc_future = Future(symbol, expiry, 'CME')

            self.log(f"Looking for {symbol} futures expiring {expiry}...")

            # Qualify contract
            self.ib.qualifyContracts(btc_future)

            self.log(f"[OK] Contract found: {btc_future.localSymbol}")

            # Request market data
            ticker = self.ib.reqMktData(btc_future, '', False, False)

            # Wait for data
            self.ib.sleep(2)

            # Get price
            futures_price = ticker.marketPrice()

            if not futures_price or futures_price <= 0:
                futures_price = ticker.last

            # Get other fields
            bid = ticker.bid if ticker.bid and ticker.bid > 0 else None
            ask = ticker.ask if ticker.ask and ticker.ask > 0 else None
            close = ticker.close if ticker.close and ticker.close > 0 else None
            volume = ticker.volume if ticker.volume and ticker.volume >= 0 else None

            # Cancel subscription
            self.ib.cancelMktData(btc_future)

            if futures_price and futures_price > 0:
                # For MBT (Micro Bitcoin), multiply by 10 to get actual BTC price
                # MBT contract is 0.1 BTC, so price needs to be scaled
                if symbol == 'MBT':
                    actual_futures_price = futures_price * 10
                    self.log(f"[OK] MBT Futures: ${futures_price:,.2f} (0.1 BTC)")
                    self.log(f"[OK] Equivalent BTC Price: ${actual_futures_price:,.2f}")
                    futures_price = actual_futures_price
                else:
                    self.log(f"[OK] BTC Futures: ${futures_price:,.2f}")

                return {
                    'symbol': symbol,
                    'exchange': 'CME',
                    'expiry': expiry,
                    'local_symbol': btc_future.localSymbol,
                    'futures_price': futures_price,
                    'bid': bid * 10 if symbol == 'MBT' and bid else bid,
                    'ask': ask * 10 if symbol == 'MBT' and ask else ask,
                    'close': close * 10 if symbol == 'MBT' and close else close,
                    'volume': volume,
                    'timestamp': datetime.now()
                }
            else:
                self.log("[X] No valid futures price")
                return None

        except Exception as e:
            self.log(f"[X] Failed to get futures: {e}")
            return None

    def get_complete_basis_data(self, expiry='202603', futures_symbol='MBT'):
        """
        Get EVERYTHING in ONE connection: spot + futures + basis

        This is the main method - gets all data from IBKR!

        Args:
            expiry: Futures expiry (YYYYMM)
            futures_symbol: 'MBT' or 'BTC'

        Returns:
            Complete basis trade data dictionary
        """
        if not self.connected:
            self.log("[X] Not connected to IBKR")
            return None

        # Get spot price (from ETF)
        self.log("\n[*] Fetching BTC Spot Price...")
        spot_data = self.get_btc_spot_price()

        # Get futures price
        self.log("\n[*] Fetching BTC Futures Price...")
        futures_data = self.get_btc_futures_price(expiry, futures_symbol)

        if not futures_data:
            self.log("[X] Could not get futures data")
            return None

        if not spot_data:
            self.log("[!] Warning: Could not get spot price, returning futures only")
            return futures_data

        # Calculate basis
        spot_price = spot_data['btc_price']
        futures_price = futures_data['futures_price']

        basis_absolute = futures_price - spot_price
        basis_percent = (basis_absolute / spot_price) * 100

        # Calculate days to expiry
        expiry_date = datetime.strptime(expiry + '01', '%Y%m%d')  # First day of expiry month
        # Adjust to last Friday (approximate)
        days_to_expiry = (expiry_date - datetime.now()).days + 27  # Approximate last Friday

        # Calculate monthly and annualized basis
        monthly_basis = basis_percent * (30 / days_to_expiry) if days_to_expiry > 0 else 0
        annualized_basis = basis_percent * (365 / days_to_expiry) if days_to_expiry > 0 else 0

        self.log(f"\n[*] Basis Calculation:")
        self.log(f"    Spot:        ${spot_price:,.2f} (from {spot_data['source']})")
        self.log(f"    Futures:     ${futures_price:,.2f}")
        self.log(f"    Basis:       ${basis_absolute:,.2f} ({basis_percent:.2f}%)")
        self.log(f"    Monthly:     {monthly_basis:.2f}%")
        self.log(f"    Annualized:  {annualized_basis:.2f}%")

        return {
            # Spot data
            'spot_price': spot_price,
            'spot_source': spot_data['source'],
            'spot_description': spot_data['description'],
            'etf_price': spot_data['etf_price'],

            # Futures data
            'futures_price': futures_price,
            'futures_symbol': futures_data['symbol'],
            'futures_local_symbol': futures_data['local_symbol'],
            'exchange': futures_data['exchange'],
            'expiry': expiry,
            'bid': futures_data['bid'],
            'ask': futures_data['ask'],
            'volume': futures_data['volume'],

            # Basis calculations
            'basis_absolute': basis_absolute,
            'basis_percent': basis_percent,
            'days_to_expiry': days_to_expiry,
            'monthly_basis': monthly_basis,
            'annualized_basis': annualized_basis,

            # Metadata
            'timestamp': datetime.now(),
            'data_source': 'IBKR Unified (Spot + Futures)'
        }


def main():
    """Main entry point"""
    print("\n" + "="*70)
    print("UNIFIED IBKR BTC FETCHER - Spot + Futures in ONE Connection")
    print("="*70 + "\n")

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
        fetcher = UnifiedBTCFetcher(port=port)

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
        # Get complete data in ONE connection
        expiry = '202603'  # March 2026
        futures_symbol = 'MBT'  # Micro Bitcoin

        print(f"\nFetching complete basis trade data...")
        print(f"Futures Contract: {futures_symbol} {expiry}\n")

        data = fetcher.get_complete_basis_data(expiry, futures_symbol)

        if data:
            print("\n" + "="*70)
            print("[*] SUCCESS - COMPLETE BASIS TRADE DATA FROM IBKR")
            print("="*70)

            print(f"\n[*] SPOT PRICE")
            print(f"    Source:       {data['spot_source']} ({data['spot_description']})")
            print(f"    ETF Price:    ${data['etf_price']:.2f}")
            print(f"    BTC Price:    ${data['spot_price']:,.2f}")

            print(f"\n[*] FUTURES PRICE")
            print(f"    Contract:     {data['futures_local_symbol']}")
            print(f"    Exchange:     {data['exchange']}")
            print(f"    Expiry:       {data['expiry']}")
            print(f"    Price:        ${data['futures_price']:,.2f}")
            print(f"    Bid/Ask:      ${data.get('bid', 0):,.2f} / ${data.get('ask', 0):,.2f}")

            print(f"\n[*] BASIS ANALYSIS")
            print(f"    Basis (Abs):  ${data['basis_absolute']:,.2f}")
            print(f"    Basis (%):    {data['basis_percent']:.2f}%")
            print(f"    Days to Exp:  {data['days_to_expiry']}")
            print(f"    Monthly:      {data['monthly_basis']:.2f}%")
            print(f"    Annualized:   {data['annualized_basis']:.2f}%")

            print(f"\n[*] DATA SOURCE")
            print(f"    {data['data_source']}")
            print(f"    Timestamp:    {data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")

            print("\n" + "="*70)
            print("[OK] All data fetched from IBKR in ONE connection!")
            print("="*70 + "\n")

        else:
            print("\n[X] Failed to fetch complete data")

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
