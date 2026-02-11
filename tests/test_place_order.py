#!/usr/bin/env python3
"""Standalone test: place a BUY 100 IBIT limit order via IBKR.

Detects overnight session and sets TIF accordingly.
Usage: PYTHONPATH=src python3 tests/test_place_order.py
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

from ib_insync import IB, Stock, LimitOrder


def is_overnight_session() -> bool:
    """Check if current time is in IBKR overnight session (8:00 PM - 3:50 AM ET)."""
    now_et = datetime.now(ZoneInfo("America/New_York"))
    hour, minute = now_et.hour, now_et.minute
    return hour >= 20 or (hour < 3) or (hour == 3 and minute < 50)


def main():
    ib = IB()
    ib.connect("127.0.0.1", 7497, clientId=3)

    try:
        # Current ET time
        now_et = datetime.now(ZoneInfo("America/New_York"))
        overnight = is_overnight_session()
        print(f"Current ET: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Overnight session: {overnight}")

        # Get current IBIT price — use OVERNIGHT exchange during overnight session
        if overnight:
            contract = Stock("IBIT", "OVERNIGHT", "USD")
        else:
            contract = Stock("IBIT", "SMART", "USD")
        ib.qualifyContracts(contract)
        ticker = ib.reqMktData(contract)
        ib.sleep(2)

        mid = (ticker.bid + ticker.ask) / 2 if ticker.bid and ticker.ask else ticker.last
        limit_price = round(mid * 1.001, 2)  # 0.1% above mid
        print(f"Bid: {ticker.bid}, Ask: {ticker.ask}, Mid: {mid}, Limit: {limit_price}")

        # Create limit order with session-appropriate TIF
        order = LimitOrder("BUY", 100, limit_price)
        if overnight:
            order.tif = "OVERNIGHT"
            order.outsideRth = False
        else:
            order.outsideRth = True
        print(f"Placing: BUY 100 IBIT @ {limit_price}, TIF={order.tif}, outsideRth={order.outsideRth}, exchange={contract.exchange}")

        trade = ib.placeOrder(contract, order)
        print("Order placed, waiting for fill (up to 120s)...")

        start = time.time()
        while not trade.isDone() and (time.time() - start) < 120:
            ib.sleep(1)
            s = trade.orderStatus
            elapsed = int(time.time() - start)
            print(f"  [{elapsed}s] Status: {s.status}, Filled: {s.filled}/{s.remaining}", end="\r")

        print()
        s = trade.orderStatus
        print(f"Final status: {s.status}")
        print(f"Fill price: {s.avgFillPrice}")
        print(f"Filled: {s.filled}")

        if trade.fills:
            for f in trade.fills:
                comm = f.commissionReport.commission if f.commissionReport else "N/A"
                print(f"  Fill: {f.execution.shares} @ {f.execution.price}, commission: {comm}")

        if not trade.isDone():
            print("Timeout — cancelling")
            ib.cancelOrder(order)
            ib.sleep(2)
            print(f"After cancel: {trade.orderStatus.status}")

    finally:
        ib.disconnect()


if __name__ == "__main__":
    main()
