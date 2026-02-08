#!/usr/bin/env python3
"""
Fetch Bitcoin Futures Prices from Binance

Free API, no authentication required for public data.
Binance has excellent liquidity and simple API.
"""

import requests
from datetime import datetime
from typing import Dict, Optional, List


def fetch_binance_spot() -> Optional[float]:
    """Fetch BTC spot price from Binance"""
    try:
        url = "https://api.binance.com/api/v3/ticker/price"
        params = {'symbol': 'BTCUSDT'}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        return float(data['price'])

    except Exception as e:
        print(f"Error fetching Binance spot: {e}")
        return None


def fetch_binance_futures() -> Optional[Dict]:
    """
    Fetch BTC futures data from Binance

    Binance has quarterly futures (similar to CME)
    """
    try:
        # Get futures ticker for BTCUSD quarterly contract
        url = "https://dapi.binance.com/dapi/v1/ticker/24hr"
        params = {'symbol': 'BTCUSD_PERP'}  # Perpetual futures

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list):
            data = data[0]

        # Get funding rate for perpetual
        funding_url = "https://dapi.binance.com/dapi/v1/fundingRate"
        funding_params = {'symbol': 'BTCUSD_PERP', 'limit': 1}

        funding_response = requests.get(funding_url, params=funding_params, timeout=10)
        funding_data = funding_response.json()

        funding_rate = float(funding_data[0]['fundingRate']) if funding_data else 0

        return {
            'symbol': 'BTCUSD_PERP',
            'type': 'perpetual',
            'mark_price': float(data['lastPrice']),
            'index_price': float(data['indexPrice']),  # Spot price
            'funding_rate': funding_rate,
            'funding_rate_annual': funding_rate * 3 * 365 * 100,  # 3 times daily, annualized %
            'volume_24h': float(data['volume']),
            'open_interest': float(data['openInterest']),
            'basis_absolute': float(data['lastPrice']) - float(data['indexPrice']),
            'basis_percent': (float(data['lastPrice']) - float(data['indexPrice'])) / float(data['indexPrice'])
        }

    except Exception as e:
        print(f"Error fetching Binance futures: {e}")
        return None


def fetch_binance_quarterly_futures() -> List[Dict]:
    """Fetch Binance quarterly futures (CME-style)"""
    try:
        # Get all futures symbols
        url = "https://dapi.binance.com/dapi/v1/exchangeInfo"
        response = requests.get(url, timeout=10)
        data = response.json()

        quarterly_contracts = []

        for symbol_info in data['symbols']:
            symbol = symbol_info['symbol']

            # Only quarterly contracts (e.g., BTCUSD_241227)
            if symbol.startswith('BTCUSD_') and symbol != 'BTCUSD_PERP':
                # Get ticker
                ticker_url = "https://dapi.binance.com/dapi/v1/ticker/24hr"
                ticker_params = {'symbol': symbol}

                ticker_response = requests.get(ticker_url, params=ticker_params, timeout=10)
                ticker_data = ticker_response.json()

                if isinstance(ticker_data, list):
                    ticker_data = ticker_data[0]

                # Parse expiry from symbol (YYMMDD format)
                expiry_str = symbol.split('_')[1]
                expiry_date = datetime.strptime('20' + expiry_str, '%Y%m%d')

                mark_price = float(ticker_data['lastPrice'])
                index_price = float(ticker_data['indexPrice'])

                quarterly_contracts.append({
                    'symbol': symbol,
                    'expiry': expiry_date,
                    'futures_price': mark_price,
                    'spot_price': index_price,
                    'basis_absolute': mark_price - index_price,
                    'basis_percent': (mark_price - index_price) / index_price * 100,
                    'open_interest': float(ticker_data.get('openInterest', 0)),
                    'volume_24h': float(ticker_data.get('volume', 0))
                })

        # Sort by expiry
        quarterly_contracts.sort(key=lambda x: x['expiry'])
        return quarterly_contracts

    except Exception as e:
        print(f"Error fetching quarterly futures: {e}")
        return []


def main():
    print("\n" + "="*70)
    print("BITCOIN FUTURES PRICES - BINANCE")
    print("="*70)

    # Spot price
    print("\n[*] SPOT PRICE")
    print("-"*70)
    spot = fetch_binance_spot()
    if spot:
        print(f"BTC/USDT Spot:     ${spot:,.2f}")

    # Perpetual futures
    print(f"\n[*] PERPETUAL FUTURES (Funding Rate Model)")
    print("-"*70)

    perp = fetch_binance_futures()

    if perp:
        print(f"Symbol:            {perp['symbol']}")
        print(f"Mark Price:        ${perp['mark_price']:,.2f}")
        print(f"Index Price:       ${perp['index_price']:,.2f}")
        print(f"Basis:             ${perp['basis_absolute']:,.2f} ({perp['basis_percent']*100:.4f}%)")
        print(f"Funding Rate:      {perp['funding_rate']*100:.4f}% (per 8h)")
        print(f"Funding Annual:    {perp['funding_rate_annual']:.2f}%")
        print(f"Open Interest:     {perp['open_interest']:,.0f} contracts")
        print(f"Volume (24h):      {perp['volume_24h']:,.0f} contracts")

        print(f"\nNote: Perpetual futures use funding rates, not expiry.")
        print(f"Negative funding = shorts pay longs (backwardation)")
        print(f"Positive funding = longs pay shorts (contango)")

    # Quarterly futures
    print(f"\n[*] QUARTERLY FUTURES (CME-Style, with Expiry)")
    print("-"*70)

    quarterly = fetch_binance_quarterly_futures()

    if quarterly:
        print(f"{'Symbol':<20} {'Expiry':<12} {'Futures':<12} {'Basis %':<10} {'OI':<15}")
        print("-"*70)

        for f in quarterly[:5]:  # Show first 5
            days_to_expiry = (f['expiry'] - datetime.now()).days
            print(f"{f['symbol']:<20} {f['expiry'].strftime('%Y-%m-%d'):<12} "
                  f"${f['futures_price']:>10,.2f} {f['basis_percent']:>8.2f}% "
                  f"{f['open_interest']:>13,.0f}")

            # Calculate monthly basis
            if days_to_expiry > 0:
                monthly_basis = f['basis_percent'] * (30 / days_to_expiry)
                print(f"  └─> Days to expiry: {days_to_expiry}, Monthly basis: {monthly_basis:.2f}%")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
