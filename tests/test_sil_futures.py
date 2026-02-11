#!/usr/bin/env python3
"""Test script to fetch SIL (Micro Silver) futures price from IBKR."""

from ib_insync import IB, Future

HOST = "127.0.0.1"
PORT = 7496
CLIENT_ID = 10


def main():
    ib = IB()
    print(f"Connecting to IBKR ({HOST}:{PORT})...")
    ib.connect(HOST, PORT, clientId=CLIENT_ID)
    print("[OK] Connected\n")

    # Try different symbol/exchange combos for micro silver
    attempts = [
        {"symbol": "SIL", "exchange": "COMEX"},
        {"symbol": "SIL", "exchange": "NYMEX"},
        {"symbol": "SIL", "exchange": "SMART"},
        {"symbol": "SI", "exchange": "NYMEX", "multiplier": "1000"},
        {"symbol": "SI", "exchange": "COMEX", "multiplier": "1000"},
    ]

    from btc_basis.utils.expiry import get_front_month_expiry_str
    expiry = get_front_month_expiry_str()
    print(f"Front-month expiry: {expiry}\n")

    for attempt in attempts:
        symbol = attempt["symbol"]
        exchange = attempt["exchange"]
        mult = attempt.get("multiplier")

        label = f"{symbol} @ {exchange}"
        if mult:
            label += f" (multiplier={mult})"

        print(f"--- Trying {label} ---")
        try:
            if mult:
                contract = Future(symbol=symbol, lastTradeDateOrContractMonth=expiry,
                                  exchange=exchange, multiplier=mult)
            else:
                contract = Future(symbol=symbol, lastTradeDateOrContractMonth=expiry,
                                  exchange=exchange)

            qualified = ib.qualifyContracts(contract)
            if not qualified:
                print(f"  [X] No contract found\n")
                continue

            print(f"  [OK] Qualified: {contract.localSymbol} "
                  f"(conId={contract.conId}, multiplier={contract.multiplier})")

            ticker = ib.reqMktData(contract, "", False, False)
            ib.sleep(3)

            price = ticker.marketPrice()
            last = ticker.last
            close = ticker.close
            bid = ticker.bid
            ask = ticker.ask

            ib.cancelMktData(contract)

            print(f"  Price:  {price}")
            print(f"  Last:   {last}")
            print(f"  Close:  {close}")
            print(f"  Bid:    {bid}")
            print(f"  Ask:    {ask}")
            print()

        except Exception as e:
            print(f"  [X] Error: {e}\n")

    ib.disconnect()
    print("[OK] Disconnected")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "src")
    main()
