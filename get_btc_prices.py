#!/usr/bin/env python3
"""
Simple Bitcoin Spot & Futures Price Fetcher

Works with multiple exchanges - tries each until one succeeds.
"""

import requests
from datetime import datetime
from typing import Dict, Optional


def fetch_coinbase_spot() -> Optional[float]:
    """Coinbase - Most reliable for spot"""
    try:
        url = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return float(response.json()['data']['amount'])
    except:
        return None


def fetch_binance_spot() -> Optional[float]:
    """Binance - Fast and reliable"""
    try:
        url = "https://api.binance.com/api/v3/ticker/price"
        response = requests.get(url, params={'symbol': 'BTCUSDT'}, timeout=5)
        response.raise_for_status()
        return float(response.json()['price'])
    except:
        return None


def fetch_kraken_spot() -> Optional[float]:
    """Kraken - Another reliable source"""
    try:
        url = "https://api.kraken.com/0/public/Ticker"
        response = requests.get(url, params={'pair': 'XBTUSD'}, timeout=5)
        response.raise_for_status()
        data = response.json()
        return float(data['result']['XXBTZUSD']['c'][0])
    except:
        return None


def fetch_binance_futures_simple() -> Optional[Dict]:
    """
    Binance Perpetual Futures - Simple version

    Perpetual futures don't have expiry, they use funding rates instead.
    But we can still calculate basis.
    """
    try:
        # Spot price
        spot_url = "https://api.binance.com/api/v3/ticker/price"
        spot_response = requests.get(spot_url, params={'symbol': 'BTCUSDT'}, timeout=5)
        spot_price = float(spot_response.json()['price'])

        # Futures price (perpetual)
        futures_url = "https://fapi.binance.com/fapi/v1/ticker/price"
        futures_response = requests.get(futures_url, params={'symbol': 'BTCUSDT'}, timeout=5)
        futures_price = float(futures_response.json()['price'])

        # Funding rate
        funding_url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        funding_response = requests.get(funding_url, params={'symbol': 'BTCUSDT'}, timeout=5)
        funding_data = funding_response.json()

        funding_rate = float(funding_data['lastFundingRate'])

        return {
            'exchange': 'Binance',
            'type': 'Perpetual',
            'spot_price': spot_price,
            'futures_price': futures_price,
            'basis_absolute': futures_price - spot_price,
            'basis_percent': (futures_price - spot_price) / spot_price * 100,
            'funding_rate_8h': funding_rate * 100,  # % per 8 hours
            'funding_rate_annual': funding_rate * 3 * 365 * 100,  # Annualized
            'note': 'Perpetual - no expiry, uses funding rate'
        }

    except Exception as e:
        print(f"Binance futures error: {e}")
        return None


def fetch_cme_futures_estimate() -> Dict:
    """
    Estimate CME futures price

    Real CME data requires paid subscription.
    This estimates based on typical contango of 5-15% annualized.
    """
    spot = fetch_coinbase_spot() or fetch_binance_spot()

    if not spot:
        return None

    # Estimate 10% annualized contango (typical)
    annualized_contango = 0.10  # 10%
    days_to_expiry = 30

    # Calculate futures price
    daily_contango = annualized_contango / 365
    futures_price = spot * (1 + daily_contango * days_to_expiry)

    return {
        'exchange': 'CME (Estimated)',
        'type': 'Futures',
        'spot_price': spot,
        'futures_price': futures_price,
        'basis_absolute': futures_price - spot,
        'basis_percent': (futures_price - spot) / spot * 100,
        'days_to_expiry': days_to_expiry,
        'expiry_date': (datetime.now().replace(day=28)).strftime('%Y-%m-%d'),  # Approximate
        'note': 'ESTIMATED - Real CME data requires subscription'
    }


def get_best_spot_price() -> Optional[float]:
    """Try multiple exchanges for spot price"""
    # Try Coinbase first (most reliable for USD)
    price = fetch_coinbase_spot()
    if price:
        print(f"  [OK] Coinbase: ${price:,.2f}")
        return price

    # Try Binance
    price = fetch_binance_spot()
    if price:
        print(f"  [OK] Binance: ${price:,.2f}")
        return price

    # Try Kraken
    price = fetch_kraken_spot()
    if price:
        print(f"  [OK] Kraken: ${price:,.2f}")
        return price

    print("  [X] All exchanges failed")
    return None


def main():
    print("\n" + "="*70)
    print("BITCOIN PRICE FETCHER")
    print("="*70)

    # Get spot price
    print("\n[*] SPOT PRICE")
    print("-"*70)
    spot = get_best_spot_price()

    if not spot:
        print("Failed to fetch spot price")
        return

    # Get futures data
    print(f"\n[*] FUTURES PRICES")
    print("-"*70)

    # Try Binance Perpetual
    print("\n1. Binance Perpetual Futures")
    binance_perp = fetch_binance_futures_simple()

    if binance_perp:
        print(f"   Spot:             ${binance_perp['spot_price']:,.2f}")
        print(f"   Futures:          ${binance_perp['futures_price']:,.2f}")
        print(f"   Basis:            ${binance_perp['basis_absolute']:,.2f} ({binance_perp['basis_percent']:.3f}%)")
        print(f"   Funding Rate:     {binance_perp['funding_rate_8h']:.4f}% per 8h")
        print(f"   Funding Annual:   {binance_perp['funding_rate_annual']:.2f}%")
        print(f"   Note:             {binance_perp['note']}")
    else:
        print("   [X] Failed")

    # CME Estimate
    print("\n2. CME Futures (Estimated)")
    cme_est = fetch_cme_futures_estimate()

    if cme_est:
        print(f"   Spot:             ${cme_est['spot_price']:,.2f}")
        print(f"   Futures:          ${cme_est['futures_price']:,.2f}")
        print(f"   Basis:            ${cme_est['basis_absolute']:,.2f} ({cme_est['basis_percent']:.2f}%)")
        print(f"   Days to Expiry:   {cme_est['days_to_expiry']}")
        print(f"   Expiry (approx):  {cme_est['expiry_date']}")
        print(f"   Note:             {cme_est['note']}")

    # Summary
    print(f"\n" + "="*70)
    print("[!] RECOMMENDATIONS FOR REAL CME DATA:")
    print("-"*70)
    print("1. CME DataMine API - https://www.cmegroup.com/market-data/datamine-api.html")
    print("   Cost: ~$50-500/month")
    print("")
    print("2. Interactive Brokers (IBKR) API - Free with account")
    print("   - Real-time CME futures prices")
    print("   - Can also execute trades")
    print("")
    print("3. Bloomberg Terminal - $2000/month (institutional)")
    print("")
    print("4. Use Binance/Deribit as proxy (good approximation)")
    print("   - Basis is usually within 0.1-0.2% of CME")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
