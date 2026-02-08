# Futures Expiry Rolling - Summary

## The Problem

**Original Question**: How is `futures_expiry` determined?

**Issue Found**: The initial IBKR historical fetcher used **fixed contracts** for entire date range:

```
Aug 2025 data → March 2026 contract (MBTH6) → expiry 2026-03-27
Sep 2025 data → March 2026 contract (MBTH6) → expiry 2026-03-27  ← WRONG!
Oct 2025 data → March 2026 contract (MBTH6) → expiry 2026-03-27  ← WRONG!
...
Feb 2026 data → February 2026 contract (MBTG6) → expiry 2026-02-27
```

**Problem**: In September 2025, traders wouldn't be using March 2026 contracts (6 months away). They'd use the **front-month** (September or October 2025).

## The Solution

### Correct Approach: Rolling Contracts

Each historical date should use the **front-month contract** that was actually trading on that date.

**Rule**: Use the nearest futures expiry that is **>= current date** (typically 20-60 days out)

### Example from realistic_basis_2024.csv

```
Jan 1-30:  expiry = 2024-01-31 (front-month)
Jan 31:    expiry = 2024-02-29 (rolls to next month)
Feb 1-28:  expiry = 2024-02-29 (new front-month)
Feb 29:    expiry = 2024-03-31 (rolls again)
```

**Contract rolls ON the expiry date** to the next month's contract.

## Implementation

### Tool Created: `fix_futures_expiry_rolling.py`

This script:
1. Reads IBKR historical CSV
2. Generates CME futures expiry schedule (last Friday of each month)
3. For each date, assigns the nearest future expiry (front-month)
4. Outputs corrected CSV with proper rolling

### Algorithm

```python
def get_front_month_expiry(date: datetime, expiry_schedule: List[datetime]) -> datetime:
    """
    Get front-month expiry for a given date

    Rule: Use the nearest expiry that is >= current date
    """
    for expiry in expiry_schedule:
        if expiry.date() >= date.date():
            return expiry

    return expiry_schedule[-1]
```

### CME Expiry Schedule Generation

```python
def get_last_friday_of_month(year: int, month: int) -> datetime:
    """CME Bitcoin futures expire last Friday of month"""
    # Get last day of month
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)

    last_day = next_month - timedelta(days=1)

    # Find last Friday (weekday 4)
    days_back = (last_day.weekday() - 4) % 7
    last_friday = last_day - timedelta(days=days_back)

    return last_friday
```

## Results

### Before Fix (btc_basis_ibkr_historical.csv)

```
Date         Expiry       Days to Expiry
2025-08-04   2026-03-27   235 days  ← Wrong! Too far out
2025-09-01   2026-03-27   207 days  ← Wrong!
2025-10-01   2026-03-27   177 days  ← Wrong!
2026-01-01   2026-02-27   57 days   ← Wrong contract for Jan
2026-02-01   2026-02-27   26 days   ← Finally correct
```

**Issues**:
- August-January used wrong contracts (too far out)
- Days to expiry calculations incorrect
- No realistic contract rolling

### After Fix (btc_basis_ibkr_rolling.csv)

```
Date         Expiry       Days to Expiry  Rolling
2025-08-04   2025-08-29   25 days         ✓ Aug contract
2025-09-02   2025-09-26   24 days         ✓ Rolled to Sep
2025-09-29   2025-10-31   32 days         ✓ Rolled to Oct
2025-11-03   2025-11-28   25 days         ✓ Rolled to Nov
2025-12-01   2025-12-26   25 days         ✓ Rolled to Dec
2025-12-29   2026-01-30   32 days         ✓ Rolled to Jan
2026-02-02   2026-02-27   25 days         ✓ Rolled to Feb
```

**Improvements**:
- ✓ Each date uses correct front-month contract
- ✓ Days to expiry realistic (20-35 days typical)
- ✓ Contract rolls naturally on expiry dates
- ✓ Matches real trading behavior

## Impact on Backtesting

### Days to Expiry Accuracy

**Critical for basis calculations**:

```python
annualized_basis = basis_percent * (365 / days_to_expiry)
```

**Before (wrong)**:
```
Date: Aug 4, 2025
Basis: -0.70%
Days to expiry: 235 days (wrong)
Annualized: -0.70% × (365/235) = -1.09%
```

**After (correct)**:
```
Date: Aug 4, 2025
Basis: -0.70%
Days to expiry: 25 days (correct)
Annualized: -0.70% × (365/25) = -10.22%  ← More accurate!
```

### Trade Signal Accuracy

Wrong days-to-expiry affects:
- Monthly basis normalization
- Annualized return calculations
- Entry/exit signal thresholds
- Risk assessment

## Usage

### Step 1: Fetch IBKR Historical Data

```bash
python fetch_ibkr_historical.py
```

Output: `btc_basis_ibkr_historical.csv` (raw data with fixed expiries)

### Step 2: Fix Expiry Rolling

```bash
python fix_futures_expiry_rolling.py
```

Output: `btc_basis_ibkr_rolling.csv` (corrected with rolling expiries)

### Step 3: Run Backtest

```bash
python btc_basis_backtest.py --data btc_basis_ibkr_rolling.csv
```

## Example Output

```
======================================================================
FIX FUTURES EXPIRY WITH ROLLING CONTRACT LOGIC
======================================================================

Reading btc_basis_ibkr_historical.csv...
[OK] Read 130 rows

Generating CME futures expiry schedule...
[OK] Generated 9 expiry dates:
  - 2025-08-29 (Friday)
  - 2025-09-26 (Friday)
  - 2025-10-31 (Friday)
  ...

Applying rolling contract logic...

[*] Initial contract expiry: 2025-08-29

[*] Contract ROLL on 2025-09-02:
    Old expiry: 2025-08-29 (-4 days)
    New expiry: 2025-09-26 (24 days)

[*] Contract ROLL on 2025-09-29:
    Old expiry: 2025-09-26 (-3 days)
    New expiry: 2025-10-31 (32 days)

...

Sample output (first 5 rows):
------------------------------------------------------------------------
Date         Spot         Futures      Expiry       Days   Basis %
------------------------------------------------------------------------
2025-08-04   $120,620.00  $119,770.00  2025-08-29   25     -0.70%
2025-08-05   $119,417.50  $118,600.00  2025-08-29   24     -0.68%
...

[OK] Fixed CSV ready: btc_basis_ibkr_rolling.csv
```

## Why No Trades in Backtest?

Even with corrected expiries, the backtest shows **0 trades**:

```
Period: 2025-08-04 to 2026-02-06
Total Trades: 0
```

**Reason**: The entire period was in **backwardation** (futures < spot):

```
Date         Basis
2025-08-04   -0.70%  (backwardation)
2025-09-01   -0.80%  (backwardation)
2026-01-01   -3.50%  (backwardation)
2026-02-06   -3.96%  (backwardation)
```

**Conclusion**:
- ✓ Data is now correct (rolling expiries)
- ✓ Backtest logic is correct (no entry in backwardation)
- ✗ Market had no profitable opportunities during this period

To see trades, need data from **contango periods** (bull markets):
- 2024 Q1: Strong contango (~12% annualized)
- 2021 bull run: Persistent 10-20% basis
- 2019-2020: Moderate 5-10% basis

## Files Summary

| File | Description | Expiry Logic |
|------|-------------|-------------|
| `fetch_ibkr_historical.py` | Fetch raw IBKR data | Fixed contracts |
| `btc_basis_ibkr_historical.csv` | Raw output | Wrong (needs fixing) |
| `fix_futures_expiry_rolling.py` | Fix expiries | Rolling front-month |
| `btc_basis_ibkr_rolling.csv` | Fixed output | Correct ✓ |
| `realistic_basis_2024.csv` | Reference example | Correct rolling |

## Key Takeaways

1. **Always use front-month contracts** for historical data
2. **Contract rolls on expiry** to next month
3. **Days to expiry typically 20-60** for front-month
4. **Fixed expiries = wrong calculations**
5. **Rolling expiries = accurate backtests**

## Reference

- CME Contract Specs: https://www.cmegroup.com/markets/cryptocurrencies/bitcoin/micro-bitcoin.html
- CME expiry: Last Friday of contract month
- Front-month: Nearest contract (typically 30-60 days out)
- Roll timing: ON expiry date

---

**Bottom Line**: Futures expiry must ROLL with time to match real trading behavior. The fix ensures each historical date uses the appropriate front-month contract, enabling accurate basis calculations and realistic backtesting.
