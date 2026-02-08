#!/usr/bin/env python3
"""
Fetch Bitcoin Futures Prices from Interactive Brokers (IBKR)

Uses IBKR Client Portal API to get real CME Bitcoin futures prices.

Prerequisites:
1. IBKR account (paper or live)
2. Client Portal Gateway running (localhost:5000)
3. Authenticated via browser: https://localhost:5000

Setup:
- Download: https://www.interactivebrokers.com/en/trading/ibkr-desktop.php
- Extract and run: bin/run.bat root/conf.yaml
- Login via browser: https://localhost:5000
"""

import requests
import urllib3
import time
from datetime import datetime
from typing import Dict, List, Optional

# Disable SSL warnings (Client Portal uses self-signed cert)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class IBKRClient:
    """IBKR Client Portal API client"""

    def __init__(self, base_url: str = "https://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.verify = False  # Self-signed cert

    def check_auth(self) -> bool:
        """Check if authenticated"""
        try:
            url = f"{self.base_url}/v1/api/iserver/auth/status"
            response = self.session.get(url, timeout=5)
            data = response.json()

            return data.get('authenticated', False) and data.get('connected', False)

        except Exception as e:
            print(f"Auth check failed: {e}")
            return False

    def search_contract(self, symbol: str) -> Optional[int]:
        """
        Search for contract ID (conid) by symbol

        Args:
            symbol: Contract symbol (e.g., 'BTC', 'MBT')

        Returns:
            Contract ID (conid) or None
        """
        try:
            url = f"{self.base_url}/v1/api/iserver/secdef/search"
            params = {'symbol': symbol, 'secType': 'FUT'}

            response = self.session.get(url, params=params, timeout=10)
            data = response.json()

            if data and len(data) > 0:
                # Return first match (usually front month)
                return data[0].get('conid')

            return None

        except Exception as e:
            print(f"Contract search failed: {e}")
            return None

    def get_futures_contracts(self, symbol: str = "BTC") -> List[Dict]:
        """
        Get all available futures contracts for symbol

        Args:
            symbol: 'BTC' (standard 5 BTC) or 'MBT' (micro 0.1 BTC)

        Returns:
            List of contract details
        """
        try:
            # Search for symbol
            url = f"{self.base_url}/v1/api/iserver/secdef/search"
            params = {'symbol': symbol}

            response = self.session.get(url, params=params, timeout=10)
            data = response.json()

            contracts = []

            for contract in data:
                if contract.get('sections', {}).get('secType') == 'FUT':
                    contracts.append({
                        'conid': contract.get('conid'),
                        'symbol': contract.get('symbol'),
                        'description': contract.get('description'),
                        'expiry': contract.get('expiry'),
                        'exchange': contract.get('exchange', 'CME')
                    })

            return contracts

        except Exception as e:
            print(f"Error fetching contracts: {e}")
            return []

    def get_market_data(self, conid: int) -> Optional[Dict]:
        """
        Get market data for contract

        Args:
            conid: Contract ID

        Returns:
            Market data dictionary
        """
        try:
            # Request market data snapshot
            url = f"{self.base_url}/v1/api/iserver/marketdata/snapshot"
            params = {
                'conids': str(conid),
                'fields': '31,84,86,88,85,87'  # Last, Bid, Ask, Volume, Close, etc.
            }

            response = self.session.get(url, params=params, timeout=10)
            data = response.json()

            if data and len(data) > 0:
                snapshot = data[0]

                return {
                    'conid': conid,
                    'last_price': snapshot.get('31'),  # Last traded price
                    'bid': snapshot.get('84'),  # Bid price
                    'ask': snapshot.get('86'),  # Ask price
                    'close': snapshot.get('88'),  # Previous close
                    'volume': snapshot.get('87'),  # Volume
                    'timestamp': datetime.now()
                }

            return None

        except Exception as e:
            print(f"Market data fetch failed: {e}")
            return None

    def get_btc_futures(self) -> Optional[Dict]:
        """
        Get CME Bitcoin futures data (front month)

        Returns:
            Dictionary with futures price and details
        """
        try:
            # Search for BTC futures
            print("Searching for BTC futures contract...")
            conid = self.search_contract('BTC')

            if not conid:
                print("BTC futures contract not found")
                return None

            print(f"Found contract ID: {conid}")

            # Get market data
            print("Fetching market data...")
            market_data = self.get_market_data(conid)

            if not market_data:
                print("Failed to get market data")
                return None

            return {
                'exchange': 'CME',
                'symbol': 'BTC',
                'contract_id': conid,
                'futures_price': market_data.get('last_price'),
                'bid': market_data.get('bid'),
                'ask': market_data.get('ask'),
                'close': market_data.get('close'),
                'volume': market_data.get('volume'),
                'timestamp': market_data.get('timestamp')
            }

        except Exception as e:
            print(f"Error getting BTC futures: {e}")
            return None


def fetch_ibkr_spot_and_futures() -> Optional[Dict]:
    """
    Get both spot and futures prices from IBKR

    Returns:
        Dictionary with spot, futures, and basis
    """
    client = IBKRClient()

    # Check authentication
    print("Checking IBKR authentication...")
    if not client.check_auth():
        print("[X] Not authenticated!")
        print("\nPlease:")
        print("1. Start Client Portal Gateway: bin/run.bat root/conf.yaml")
        print("2. Login via browser: https://localhost:5000")
        print("3. Try again")
        return None

    print("[OK] Authenticated\n")

    # Get futures data
    futures_data = client.get_btc_futures()

    if not futures_data:
        return None

    # Get spot price (use Coinbase as reference)
    from get_btc_prices import fetch_coinbase_spot

    spot_price = fetch_coinbase_spot()

    if not spot_price:
        print("Warning: Could not fetch spot price from Coinbase")
        return futures_data

    # Calculate basis
    futures_price = futures_data['futures_price']
    basis_absolute = futures_price - spot_price
    basis_percent = (basis_absolute / spot_price) * 100

    return {
        'spot_price': spot_price,
        'futures_price': futures_price,
        'basis_absolute': basis_absolute,
        'basis_percent': basis_percent,
        'bid': futures_data['bid'],
        'ask': futures_data['ask'],
        'spread': futures_data['ask'] - futures_data['bid'],
        'volume': futures_data['volume'],
        'exchange': 'CME (via IBKR)',
        'contract_id': futures_data['contract_id'],
        'timestamp': futures_data['timestamp']
    }


def main():
    print("\n" + "="*70)
    print("IBKR CME BITCOIN FUTURES FETCHER")
    print("="*70)

    result = fetch_ibkr_spot_and_futures()

    if result:
        print("\n[*] MARKET DATA")
        print("-"*70)
        print(f"Spot Price (Coinbase):  ${result['spot_price']:,.2f}")
        print(f"Futures Price (CME):    ${result['futures_price']:,.2f}")
        print(f"Bid:                    ${result['bid']:,.2f}")
        print(f"Ask:                    ${result['ask']:,.2f}")
        print(f"Spread:                 ${result['spread']:,.2f}")

        print(f"\n[*] BASIS ANALYSIS")
        print("-"*70)
        print(f"Basis (Absolute):       ${result['basis_absolute']:,.2f}")
        print(f"Basis (Percent):        {result['basis_percent']:.2f}%")

        print(f"\n[*] CONTRACT INFO")
        print("-"*70)
        print(f"Exchange:               {result['exchange']}")
        print(f"Contract ID:            {result['contract_id']}")
        print(f"Volume:                 {result.get('volume', 'N/A')}")
        print(f"Timestamp:              {result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")

        print("\n" + "="*70)
        print("[OK] Success! IBKR futures data fetched")
        print("="*70 + "\n")

    else:
        print("\n" + "="*70)
        print("[X] FAILED TO FETCH DATA")
        print("="*70)
        print("\nTroubleshooting:")
        print("1. Ensure Client Portal Gateway is running")
        print("2. Check authentication: https://localhost:5000")
        print("3. Verify CME futures permissions in IBKR account")
        print("4. Check market data subscription (delayed data is free)")
        print("\nSee: ibkr_setup_guide.md for detailed setup")
        print("="*70 + "\n")


if __name__ == "__main__":
    main()
