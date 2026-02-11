#!/usr/bin/env python3
"""Standalone test: place a SELL 1 MBT futures limit order via IBKR.

CME futures trade nearly 24h (Sun 5 PM - Fri 5 PM ET), so no OVERNIGHT
exchange routing needed — just use CME directly.

Usage: PYTHONPATH=src python3 tests/test_place_futures_order.py
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

from ib_insync import IB, Future, LimitOrder

from btc_basis.utils.expiry import get_front_month_expiry_str


def main():
    ib = IB()
    ib.connect("127.0.0.1", 7497, clientId=4)

    try:
        now_et = datetime.now(ZoneInfo("America/New_York"))
        print(f"Current ET: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        # Front-month MBT contract
        expiry = get_front_month_expiry_str()
        print(f"Front-month expiry: {expiry}")

        contract = Future("MBT", expiry, "CME")
        ib.qualifyContracts(contract)
        print(f"Contract: {contract.localSymbol}, multiplier={contract.multiplier}")

        # Get current price
        ticker = ib.reqMktData(contract)
        ib.sleep(2)

        bid, ask = ticker.bid, ticker.ask
        mid = (bid + ask) / 2 if bid and ask else ticker.last
        # MBT tick size is $5 — round limit to nearest valid tick
        tick_size = 5
        limit_price = round(mid / tick_size) * tick_size
        print(f"Bid: {bid}, Ask: {ask}, Mid: {mid}, Limit: {limit_price}")

        # Create order — CME futures don't need OVERNIGHT TIF
        order = LimitOrder("SELL", 1, limit_price)
        #order.outsideRth = True
        print(f"Placing: SELL 1 MBT @ {limit_price}")

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
