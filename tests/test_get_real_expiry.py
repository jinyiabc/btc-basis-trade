#!/usr/bin/env python3
"""
Test: Get actual expiry date from IBKR contract details
"""

from ib_insync import IB, Future
from datetime import datetime, timedelta

def get_real_expiry():
    """Get actual expiry from IBKR"""
    ib = IB()

    try:
        # Connect
        ib.connect('127.0.0.1', 7496, clientId=4)
        print("[OK] Connected\n")

        # Test multiple contracts
        contracts = [
            ('202602', 'MBTG6'),  # Feb 2026
            ('202603', 'MBTH6'),  # Mar 2026
            ('202604', 'MBTJ6'),  # Apr 2026
        ]

        print("Contract Expiry Dates from IBKR:")
        print("=" * 70)

        for expiry, local_symbol in contracts:
            mbt = Future('MBT', expiry, 'CME')
            ib.qualifyContracts(mbt)

            print(f"\n{local_symbol} (Expiry input: {expiry})")
            print(f"  Local Symbol:        {mbt.localSymbol}")
            print(f"  Last Trade Date:     {mbt.lastTradeDateOrContractMonth}")

            # Parse the actual expiry date
            if mbt.lastTradeDateOrContractMonth:
                # Format is YYYYMMDD
                expiry_str = mbt.lastTradeDateOrContractMonth
                if len(expiry_str) == 8:
                    expiry_date = datetime.strptime(expiry_str, '%Y%m%d')
                    day_name = expiry_date.strftime('%A')
                    print(f"  Actual Expiry:       {expiry_date.strftime('%Y-%m-%d')} ({day_name})")

                    # Verify it's a Friday
                    if day_name == 'Friday':
                        print(f"  [OK] Confirmed Friday")
                    else:
                        print(f"  [!] NOT a Friday! ({day_name})")
                elif len(expiry_str) == 6:
                    # Sometimes just YYYYMM
                    print(f"  Month Only:          {expiry_str} (calculating last Friday...)")
                    year = int(expiry_str[:4])
                    month = int(expiry_str[4:6])
                    # Calculate last Friday
                    if month == 12:
                        next_month = datetime(year + 1, 1, 1)
                    else:
                        next_month = datetime(year, month + 1, 1)
                    last_day = next_month - timedelta(days=1)
                    days_back = (last_day.weekday() - 4) % 7
                    last_friday = last_day - timedelta(days=days_back)
                    print(f"  Calculated Expiry:   {last_friday.strftime('%Y-%m-%d (%A)')}")

        print("\n" + "=" * 70)

        ib.disconnect()

    except Exception as e:
        print(f"Error: {e}")
        ib.disconnect()


if __name__ == "__main__":
    get_real_expiry()
