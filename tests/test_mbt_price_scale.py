#!/usr/bin/env python3
"""
Test MBT price scaling to understand IBKR's price format
"""

from ib_insync import IB, Future
from datetime import datetime

def test_mbt_pricing():
    """Test MBT contract price format"""
    ib = IB()

    try:
        # Connect
        ib.connect('127.0.0.1', 7496, clientId=3)
        print("[OK] Connected to IBKR\n")

        # Get MBT contract
        mbt = Future('MBT', '202603', 'CME')
        ib.qualifyContracts(mbt)

        print(f"Contract: {mbt.localSymbol}")
        print(f"Multiplier: {mbt.multiplier}")
        print(f"Min Tick: {mbt.minTick}\n")

        # Get current price
        ticker = ib.reqMktData(mbt, '', False, False)
        ib.sleep(2)

        raw_price = ticker.marketPrice() or ticker.last
        print(f"Raw MBT price from IBKR: ${raw_price:,.2f}")
        print(f"MBT * 10:                ${raw_price * 10:,.2f}")
        print(f"MBT / 10:                ${raw_price / 10:,.2f}")
        print(f"MBT * 100:               ${raw_price * 100:,.2f}")

        print(f"\nExpected BTC spot range: $70,000 - $75,000")
        print(f"\nWhich multiplier makes sense?")

        ib.cancelMktData(mbt)
        ib.disconnect()

    except Exception as e:
        print(f"Error: {e}")
        ib.disconnect()


if __name__ == "__main__":
    test_mbt_pricing()
