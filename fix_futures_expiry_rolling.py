#!/usr/bin/env python3
"""
Fix futures_expiry dates to use proper rolling contract logic

Reads IBKR historical CSV and reassigns futures_expiry to match
the front-month contract that would have been trading on each date.

Rule: Use the nearest futures expiry that is >= current date
(typically current or next month's last Friday)
"""

import csv
from datetime import datetime, timedelta
from typing import List, Dict


def get_last_friday_of_month(year: int, month: int) -> datetime:
    """Get last Friday of a given month"""
    # Last day of month
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)

    last_day = next_month - timedelta(days=1)

    # Find last Friday (weekday 4)
    days_back = (last_day.weekday() - 4) % 7
    last_friday = last_day - timedelta(days=days_back)

    return last_friday


def generate_expiry_schedule(start_date: datetime, end_date: datetime) -> List[datetime]:
    """
    Generate all CME Bitcoin futures expiry dates in a date range

    Returns:
        List of expiry dates (last Friday of each month)
    """
    expiries = []

    current = start_date.replace(day=1)  # Start of month
    end = end_date + timedelta(days=60)  # Include future expiries

    while current <= end:
        expiry = get_last_friday_of_month(current.year, current.month)
        expiries.append(expiry)

        # Next month
        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)

    return sorted(list(set(expiries)))


def get_front_month_expiry(date: datetime, expiry_schedule: List[datetime]) -> datetime:
    """
    Get front-month expiry for a given date

    Rule: Use the nearest expiry that is >= current date

    Args:
        date: Historical date
        expiry_schedule: List of all available expiry dates

    Returns:
        Front-month expiry date
    """
    for expiry in expiry_schedule:
        if expiry.date() >= date.date():
            return expiry

    # If no future expiry found, return the last one
    return expiry_schedule[-1]


def fix_rolling_expiry(input_file: str, output_file: str):
    """
    Fix futures_expiry to use proper rolling logic

    Args:
        input_file: Input CSV (from IBKR historical fetcher)
        output_file: Output CSV with corrected expiries
    """
    print(f"\nReading {input_file}...")

    # Read input CSV
    rows = []
    with open(input_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    print(f"[OK] Read {len(rows)} rows")

    # Determine date range
    start_date = datetime.strptime(rows[0]['date'], '%Y-%m-%d')
    end_date = datetime.strptime(rows[-1]['date'], '%Y-%m-%d')

    # Generate expiry schedule
    print(f"\nGenerating CME futures expiry schedule...")
    expiry_schedule = generate_expiry_schedule(start_date, end_date)
    print(f"[OK] Generated {len(expiry_schedule)} expiry dates:")
    for exp in expiry_schedule[:5]:
        print(f"  - {exp.strftime('%Y-%m-%d (%A)')}")
    if len(expiry_schedule) > 5:
        print(f"  ... and {len(expiry_schedule) - 5} more")

    # Fix each row
    print(f"\nApplying rolling contract logic...")
    fixed_rows = []
    current_expiry = None

    for row in rows:
        date = datetime.strptime(row['date'], '%Y-%m-%d')

        # Get front-month expiry for this date
        front_month_expiry = get_front_month_expiry(date, expiry_schedule)

        # Track when contract rolls
        if current_expiry is None:
            current_expiry = front_month_expiry
            print(f"\n[*] Initial contract expiry: {current_expiry.strftime('%Y-%m-%d')}")

        if front_month_expiry != current_expiry:
            days_to_old = (current_expiry - date).days
            days_to_new = (front_month_expiry - date).days
            print(f"\n[*] Contract ROLL on {date.strftime('%Y-%m-%d')}:")
            print(f"    Old expiry: {current_expiry.strftime('%Y-%m-%d')} ({days_to_old} days)")
            print(f"    New expiry: {front_month_expiry.strftime('%Y-%m-%d')} ({days_to_new} days)")
            current_expiry = front_month_expiry

        # Update expiry
        fixed_rows.append({
            'date': row['date'],
            'spot_price': row['spot_price'],
            'futures_price': row['futures_price'],
            'futures_expiry': front_month_expiry.strftime('%Y-%m-%d')
        })

    # Write output CSV
    print(f"\nWriting to {output_file}...")
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['date', 'spot_price', 'futures_price', 'futures_expiry'])
        writer.writeheader()
        writer.writerows(fixed_rows)

    print(f"[OK] Written {len(fixed_rows)} rows")

    # Show sample with days to expiry
    print("\nSample output (first 5 rows):")
    print("-" * 80)
    print(f"{'Date':<12} {'Spot':<12} {'Futures':<12} {'Expiry':<12} {'Days':<6} {'Basis %':<10}")
    print("-" * 80)

    for i, row in enumerate(fixed_rows[:5]):
        date = datetime.strptime(row['date'], '%Y-%m-%d')
        expiry = datetime.strptime(row['futures_expiry'], '%Y-%m-%d')
        days_to_expiry = (expiry - date).days

        spot = float(row['spot_price'])
        futures = float(row['futures_price'])
        basis_pct = ((futures - spot) / spot) * 100

        print(
            f"{row['date']:<12} "
            f"${spot:<11,.2f} "
            f"${futures:<11,.2f} "
            f"{row['futures_expiry']:<12} "
            f"{days_to_expiry:<6} "
            f"{basis_pct:<9.2f}%"
        )

    print("-" * 80)
    print(f"\n[OK] Fixed CSV ready: {output_file}")
    print(f"\nRun backtest with: python btc_basis_backtest.py --data {output_file}")


def main():
    """Main entry point"""
    print("\n" + "="*70)
    print("FIX FUTURES EXPIRY WITH ROLLING CONTRACT LOGIC")
    print("="*70)

    input_file = "btc_basis_ibkr_historical.csv"
    output_file = "btc_basis_ibkr_rolling.csv"

    try:
        fix_rolling_expiry(input_file, output_file)
        print("\n" + "="*70)
        print("[OK] SUCCESS")
        print("="*70 + "\n")

    except FileNotFoundError:
        print(f"\n[X] ERROR: {input_file} not found")
        print(f"\nRun this first: python fetch_ibkr_historical.py\n")

    except Exception as e:
        print(f"\n[X] ERROR: {e}\n")


if __name__ == "__main__":
    main()
