#!/usr/bin/env python3
"""
Fetch Bitcoin Futures from IBKR using TWS API

Uses ib_insync library - simpler than Client Portal API.

Prerequisites:
1. IBKR account
2. TWS or IB Gateway installed and running
3. API enabled in TWS: Global Configuration → API → Settings → Enable ActiveX and Socket Clients

Install:
    pip install ib_insync

Ports:
- TWS (paper): 7497
- TWS (live): 7496
- IB Gateway (paper): 4002
- IB Gateway (live): 4001
"""

from ib_insync import IB, Future, Stock
from datetime import datetime
from typing import Dict, Optional, List
import sys


def get_ibkr_connection(port: int = 7497, client_id: int = 1) -> Optional[IB]:
    """
    Connect to IBKR TWS or IB Gateway

    Args:
        port: 7497 (TWS paper), 7496 (TWS live), 4002 (Gateway paper), 4001 (Gateway live)
        client_id: Unique client ID (1-32)

    Returns:
        Connected IB object or None
    """
    try:
        ib = IB()
        ib.connect('127.0.0.1', port, clientId=client_id, timeout=10)
        print(f"[OK] Connected to IBKR (port {port})")
        return ib

    except Exception as e:
        print(f"[X] Connection failed (port {port}): {e}")
        return None


def get_btc_futures_contracts(ib: IB) -> List[Future]:
    """
    Get all available BTC futures contracts

    Returns:
        List of qualified Future contracts
    """
    try:
        # Create futures for different expirations
        # CME BTC futures expire on last Friday of contract month
        futures = [
            Future('BTC', '20260327', 'CME'),  # Mar 2026
            Future('BTC', '20260424', 'CME'),  # Apr 2026
            Future('BTC', '20260529', 'CME'),  # May 2026
            Future('BTC', '20260626', 'CME'),  # Jun 2026
        ]

        # Qualify contracts (get full details from IBKR)
        qualified = ib.qualifyContracts(*futures)

        print(f"[OK] Found {len(qualified)} BTC futures contracts")
        return qualified

    except Exception as e:
        print(f"[X] Error getting contracts: {e}")
        return []


def get_front_month_futures(ib: IB) -> Optional[Future]:
    """
    Get the front month (nearest expiry) BTC futures contract

    Returns:
        Front month Future contract or None
    """
    contracts = get_btc_futures_contracts(ib)

    if not contracts:
        return None

    # Sort by expiry date (contracts have lastTradeDateOrContractMonth)
    contracts.sort(key=lambda c: c.lastTradeDateOrContractMonth)

    return contracts[0]


def get_market_data(ib: IB, contract: Future) -> Optional[Dict]:
    """
    Get real-time market data for contract

    Args:
        ib: Connected IB instance
        contract: Qualified contract

    Returns:
        Market data dictionary
    """
    try:
        # Request market data
        ticker = ib.reqMktData(contract)

        # Wait for data (streaming)
        ib.sleep(2)

        # Get current values
        return {
            'symbol': contract.symbol,
            'expiry': contract.lastTradeDateOrContractMonth,
            'exchange': contract.exchange,
            'last_price': ticker.last if ticker.last == ticker.last else None,  # Check for NaN
            'bid': ticker.bid if ticker.bid == ticker.bid else None,
            'ask': ticker.ask if ticker.ask == ticker.ask else None,
            'close': ticker.close if ticker.close == ticker.close else None,
            'volume': ticker.volume if ticker.volume == ticker.volume else None,
            'timestamp': datetime.now()
        }

    except Exception as e:
        print(f"[X] Market data error: {e}")
        return None


def fetch_ibkr_tws_futures(port: int = 7497) -> Optional[Dict]:
    """
    Complete flow: Connect, fetch futures, get market data

    Args:
        port: TWS/Gateway port (see docstring)

    Returns:
        Dictionary with spot, futures, and basis
    """
    # Connect to IBKR
    ib = get_ibkr_connection(port)

    if not ib:
        return None

    try:
        # Get front month futures
        print("Fetching front month BTC futures...")
        contract = get_front_month_futures(ib)

        if not contract:
            print("[X] No futures contract found")
            return None

        print(f"[OK] Contract: {contract.symbol} {contract.lastTradeDateOrContractMonth}")

        # Get market data
        print("Requesting market data...")
        data = get_market_data(ib, contract)

        if not data or not data['last_price']:
            print("[X] No market data available")
            print("Note: Market may be closed or you need real-time data subscription")
            return None

        # Get spot price for basis calculation
        # Option 1: Use Coinbase
        try:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(__file__))
            from get_btc_prices import fetch_coinbase_spot

            spot_price = fetch_coinbase_spot()
        except:
            spot_price = None

        # Calculate basis
        result = {
            'exchange': 'CME',
            'symbol': data['symbol'],
            'expiry': data['expiry'],
            'futures_price': data['last_price'],
            'bid': data['bid'],
            'ask': data['ask'],
            'close': data['close'],
            'volume': data['volume'],
            'timestamp': data['timestamp']
        }

        if spot_price:
            result['spot_price'] = spot_price
            result['basis_absolute'] = data['last_price'] - spot_price
            result['basis_percent'] = (result['basis_absolute'] / spot_price) * 100

            # Calculate days to expiry
            expiry_date = datetime.strptime(data['expiry'], '%Y%m%d')
            days_to_expiry = (expiry_date - datetime.now()).days

            result['days_to_expiry'] = days_to_expiry

            if days_to_expiry > 0:
                result['monthly_basis'] = result['basis_percent'] * (30 / days_to_expiry)
                result['annualized_basis'] = result['basis_percent'] * (365 / days_to_expiry)

        return result

    except Exception as e:
        print(f"[X] Error: {e}")
        return None

    finally:
        # Disconnect
        ib.disconnect()
        print("[OK] Disconnected from IBKR")


def main():
    print("\n" + "="*70)
    print("IBKR TWS API - CME BITCOIN FUTURES")
    print("="*70)

    # Try different ports
    ports = {
        7497: "TWS Paper Trading",
        7496: "TWS Live",
        4002: "IB Gateway Paper",
        4001: "IB Gateway Live"
    }

    print("\n[*] Available connections:")
    for port, desc in ports.items():
        print(f"  {port}: {desc}")

    print("\n[*] Attempting to connect...")

    result = None

    # Try each port
    for port in [7497, 4002, 7496, 4001]:  # Try paper first
        print(f"\nTrying port {port} ({ports[port]})...")
        result = fetch_ibkr_tws_futures(port)

        if result:
            break

    if result:
        print("\n" + "="*70)
        print("[*] MARKET DATA - CME BITCOIN FUTURES")
        print("="*70)
        print(f"Symbol:                {result['symbol']}")
        print(f"Expiry:                {result['expiry']}")
        print(f"Exchange:              {result['exchange']}")
        print(f"Futures Price:         ${result['futures_price']:,.2f}")
        print(f"Bid/Ask:               ${result.get('bid', 0):,.2f} / ${result.get('ask', 0):,.2f}")
        print(f"Previous Close:        ${result.get('close', 0):,.2f}")
        print(f"Volume:                {result.get('volume', 'N/A')}")

        if 'spot_price' in result:
            print(f"\n[*] BASIS ANALYSIS")
            print("-"*70)
            print(f"Spot Price:            ${result['spot_price']:,.2f}")
            print(f"Basis (Absolute):      ${result['basis_absolute']:,.2f}")
            print(f"Basis (Percent):       {result['basis_percent']:.2f}%")
            print(f"Days to Expiry:        {result.get('days_to_expiry', 'N/A')}")
            print(f"Monthly Basis:         {result.get('monthly_basis', 0):.2f}%")
            print(f"Annualized Basis:      {result.get('annualized_basis', 0):.2f}%")

        print("\n" + "="*70)
        print("[OK] SUCCESS!")
        print("="*70 + "\n")

    else:
        print("\n" + "="*70)
        print("[X] FAILED - Could not connect to any IBKR instance")
        print("="*70)
        print("\nTroubleshooting:")
        print("1. Install TWS or IB Gateway")
        print("2. Start TWS/Gateway and login")
        print("3. Enable API:")
        print("   - TWS: Global Configuration → API → Settings")
        print("   - Check 'Enable ActiveX and Socket Clients'")
        print("   - Socket port: 7497 (paper) or 7496 (live)")
        print("4. Install ib_insync: pip install ib_insync")
        print("\nSee: ibkr_setup_guide.md for detailed instructions")
        print("="*70 + "\n")


if __name__ == "__main__":
    # Check if ib_insync is installed
    try:
        import ib_insync
    except ImportError:
        print("\n[X] ERROR: ib_insync not installed")
        print("\nInstall with: pip install ib_insync")
        print("Then run this script again\n")
        sys.exit(1)

    main()
