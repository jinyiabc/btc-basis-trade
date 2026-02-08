#!/usr/bin/env python3
"""
Test IBKR contract search to find correct BTC futures specification
"""

from ib_insync import IB, Future, Stock
import time

def test_btc_contracts():
    """Try different BTC contract specifications"""

    ib = IB()

    try:
        # Connect to live TWS
        ib.connect('127.0.0.1', 7496, clientId=1)
        print("[OK] Connected to IBKR\n")

        # Try different BTC contract specifications
        test_contracts = [
            # Standard CME BTC futures (5 BTC)
            Future('BTC', '202603', 'CME'),      # Month format
            Future('BTC', '20260327', 'CME'),    # Full date
            Future('BTC', '202604', 'CME'),      # April

            # Micro BTC futures (0.1 BTC)
            Future('MBT', '202603', 'CME'),
            Future('MBT', '20260327', 'CME'),

            # Try with different exchange codes
            Future('BTC', '202603', 'COMEX'),
            Future('BTC', '202603', 'NYMEX'),

            # Try continuous contract
            # ContFuture('BTC', 'CME'),  # If you have ContFuture imported
        ]

        print("Testing contract specifications...\n")
        print("="*70)

        for i, contract in enumerate(test_contracts, 1):
            print(f"\n{i}. Testing: {contract}")

            try:
                # Try to qualify the contract
                qualified = ib.qualifyContracts(contract)

                if qualified:
                    q = qualified[0]
                    print(f"   [OK] FOUND!")
                    print(f"   Symbol: {q.symbol}")
                    print(f"   Local Symbol: {q.localSymbol}")
                    print(f"   Exchange: {q.exchange}")
                    print(f"   Expiry: {q.lastTradeDateOrContractMonth}")
                    print(f"   Contract ID: {q.conId}")
                    print(f"   Currency: {q.currency}")
                    print(f"   Multiplier: {q.multiplier}")

                    # Try to get market data
                    print(f"   Requesting market data...")
                    ticker = ib.reqMktData(q, '', False, False)
                    ib.sleep(2)

                    price = ticker.marketPrice()
                    if not price or price <= 0:
                        price = ticker.last

                    if price and price > 0:
                        print(f"   Price: ${price:,.2f}")
                    else:
                        print(f"   No price data (market may be closed)")

                    ib.cancelMktData(q)

                    # This is our winner!
                    print(f"\n   *** USE THIS CONTRACT SPECIFICATION ***")
                    break

                else:
                    print(f"   [X] Not found")

            except Exception as e:
                print(f"   [X] Error: {e}")

            time.sleep(0.5)

        print("\n" + "="*70)

    except Exception as e:
        print(f"[X] Connection error: {e}")

    finally:
        ib.disconnect()
        print("\n[OK] Disconnected")


if __name__ == "__main__":
    test_btc_contracts()
