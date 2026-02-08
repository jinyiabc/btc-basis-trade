#!/usr/bin/env python3
"""
Fetch Bitcoin Futures Prices from Deribit

Free API, no authentication required for public data.
"""

import requests
from datetime import datetime
from typing import Dict, Optional, List


def fetch_deribit_futures() -> Optional[Dict]:
    """
    Fetch BTC futures data from Deribit

    Returns:
        Dictionary with futures price, expiry, and other data
    """
    try:
        # Get available BTC futures instruments
        url = "https://www.deribit.com/api/v2/public/get_instruments"
        params = {
            'currency': 'BTC',
            'kind': 'future',
            'expired': False
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data['result']:
            instruments = data['result']

            # Find the front month (nearest expiry)
            front_month = min(instruments, key=lambda x: x['expiration_timestamp'])

            # Get current mark price for this instrument
            ticker_url = "https://www.deribit.com/api/v2/public/ticker"
            ticker_params = {'instrument_name': front_month['instrument_name']}

            ticker_response = requests.get(ticker_url, params=ticker_params, timeout=10)
            ticker_data = ticker_response.json()

            if ticker_data['result']:
                result = ticker_data['result']

                return {
                    'instrument': front_month['instrument_name'],
                    'futures_price': result['mark_price'],  # Mark price in USD
                    'spot_price': result['underlying_price'],  # Underlying BTC price
                    'expiry_timestamp': front_month['expiration_timestamp'],
                    'expiry_date': datetime.fromtimestamp(front_month['expiration_timestamp'] / 1000),
                    'basis_absolute': result['mark_price'] - result['underlying_price'],
                    'basis_percent': (result['mark_price'] - result['underlying_price']) / result['underlying_price'],
                    'open_interest': result.get('open_interest', 0),
                    'volume_24h': result.get('stats', {}).get('volume', 0),
                    'bid': result.get('best_bid_price'),
                    'ask': result.get('best_ask_price')
                }

        return None

    except Exception as e:
        print(f"Error fetching Deribit data: {e}")
        return None


def fetch_all_deribit_futures() -> List[Dict]:
    """Fetch all available BTC futures contracts"""
    try:
        url = "https://www.deribit.com/api/v2/public/get_instruments"
        params = {
            'currency': 'BTC',
            'kind': 'future',
            'expired': False
        }

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        futures_list = []

        for instrument in data['result']:
            # Get ticker for each
            ticker_url = "https://www.deribit.com/api/v2/public/ticker"
            ticker_params = {'instrument_name': instrument['instrument_name']}

            ticker_response = requests.get(ticker_url, params=ticker_params, timeout=10)
            ticker_data = ticker_response.json()

            if ticker_data['result']:
                result = ticker_data['result']

                futures_list.append({
                    'instrument': instrument['instrument_name'],
                    'expiry': datetime.fromtimestamp(instrument['expiration_timestamp'] / 1000),
                    'futures_price': result['mark_price'],
                    'spot_price': result['underlying_price'],
                    'basis_percent': (result['mark_price'] - result['underlying_price']) / result['underlying_price'] * 100,
                    'open_interest': result.get('open_interest', 0)
                })

        # Sort by expiry date
        futures_list.sort(key=lambda x: x['expiry'])
        return futures_list

    except Exception as e:
        print(f"Error: {e}")
        return []


def main():
    print("\n" + "="*70)
    print("BITCOIN FUTURES PRICES - DERIBIT")
    print("="*70)

    # Fetch front month futures
    print("\n[*] FRONT MONTH FUTURES")
    print("-"*70)

    futures = fetch_deribit_futures()

    if futures:
        print(f"Instrument:        {futures['instrument']}")
        print(f"Expiry:            {futures['expiry_date'].strftime('%Y-%m-%d')}")
        print(f"Spot Price:        ${futures['spot_price']:,.2f}")
        print(f"Futures Price:     ${futures['futures_price']:,.2f}")
        print(f"Basis:             ${futures['basis_absolute']:,.2f} ({futures['basis_percent']*100:.2f}%)")
        print(f"Open Interest:     {futures['open_interest']:,.0f} BTC")
        print(f"Volume (24h):      {futures['volume_24h']:,.0f} BTC")
        print(f"Bid/Ask:           ${futures['bid']:,.2f} / ${futures['ask']:,.2f}")

        # Calculate monthly basis
        days_to_expiry = (futures['expiry_date'] - datetime.now()).days
        if days_to_expiry > 0:
            monthly_basis = futures['basis_percent'] * (30 / days_to_expiry)
            annualized = futures['basis_percent'] * (365 / days_to_expiry)

            print(f"\nDays to Expiry:    {days_to_expiry}")
            print(f"Monthly Basis:     {monthly_basis*100:.2f}%")
            print(f"Annualized Basis:  {annualized*100:.2f}%")
    else:
        print("Failed to fetch data")

    # Fetch all futures
    print(f"\n[*] ALL AVAILABLE BTC FUTURES")
    print("-"*70)

    all_futures = fetch_all_deribit_futures()

    if all_futures:
        print(f"{'Instrument':<20} {'Expiry':<12} {'Futures':<12} {'Basis %':<10} {'OI (BTC)':<12}")
        print("-"*70)

        for f in all_futures:
            print(f"{f['instrument']:<20} {f['expiry'].strftime('%Y-%m-%d'):<12} "
                  f"${f['futures_price']:>10,.2f} {f['basis_percent']:>8.2f}% {f['open_interest']:>10,.0f}")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
