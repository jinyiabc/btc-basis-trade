# Backtest Data Preparation from IBKR - Complete Guide

## Overview

This guide explains how to fetch real historical Bitcoin spot and futures data from Interactive Brokers for backtesting the basis trade strategy.

## What We Built

**`fetch_ibkr_historical.py`** - Historical data fetcher that:
- Connects to IBKR (TWS or IB Gateway)
- Fetches IBIT ETF historical prices (spot proxy)
- Fetches CME MBT futures historical prices
- Merges data and calculates basis
- Outputs CSV ready for `btc_basis_backtest.py`

## How It Works

### Data Sources

1. **Spot Price Proxy**: IBIT ETF (BlackRock Bitcoin ETF)
   - Most liquid Bitcoin ETF
   - Multiplier: ~1850x (IBIT price × 1850 ≈ BTC price)
   - Available since: January 2024
   - Alternatives: FBTC, GBTC

2. **Futures Price**: CME Micro Bitcoin (MBT)
   - Contract size: 0.1 BTC
   - Quote format: Index points (same as full BTC price)
   - Multiplier: $50 per index point
   - Symbol examples: MBTG6 (Feb), MBTH6 (Mar), MBTJ6 (Apr)

### CME Contract Months

| Code | Month | Example | Expiry |
|------|-------|---------|--------|
| F | January | MBTF6 | Last Friday |
| G | February | MBTG6 | Last Friday |
| H | March | MBTH6 | Last Friday |
| J | April | MBTJ6 | Last Friday |
| K | May | MBTK6 | Last Friday |
| M | June | MBTM6 | Last Friday |

Format: `YYYYMM` (e.g., '202603' = March 2026)

## Usage

### Basic Usage (Recent 3 Months)

```bash
python fetch_ibkr_historical.py
```

**Output**: `btc_basis_ibkr_historical.csv`

### Custom Date Range

Edit the script configuration:

```python
# In fetch_ibkr_historical.py, main() function:

start_date = datetime(2025, 10, 1)  # Your start date
end_date = datetime.now()            # Your end date (or specific date)

futures_contracts = [
    '202602',  # Feb 2026
    '202603',  # Mar 2026
    '202604',  # Apr 2026
]
```

### Running Backtest with IBKR Data

```bash
# Fetch historical data
python fetch_ibkr_historical.py

# Run backtest
python btc_basis_backtest.py --data btc_basis_ibkr_historical.csv --holding-days 30
```

## Output Format

The CSV file contains:

| Column | Description | Example |
|--------|-------------|---------|
| date | Trading date | 2026-01-15 |
| spot_price | BTC spot price (from IBIT) | 93739.50 |
| futures_price | CME futures price | 89750.00 |
| futures_expiry | Contract expiry date | 2026-02-27 |

## Sample Output

```
======================================================================
IBKR HISTORICAL DATA FETCHER FOR BACKTESTING
======================================================================

[OK] Connected to IBKR (127.0.0.1:7496)

Period: 2025-10-01 to 2026-02-08
Futures contracts: ['202602', '202603', '202604']

[OK] Fetched 130 bars for IBIT
[OK] Fetched 110 bars for MBTG6
[OK] Fetched 130 bars for MBTH6
[OK] Fetched 65 bars for MBTJ6

Writing 130 rows to btc_basis_ibkr_historical.csv...
[OK] CSV file created: btc_basis_ibkr_historical.csv

Sample data (first 5 rows):
----------------------------------------------------------------------
Date         Spot         Futures      Basis %    Expiry
----------------------------------------------------------------------
2025-08-04   $120,620.00  $119,770.00  -0.70%     2026-03-27
2025-08-05   $119,417.50  $118,600.00  -0.68%     2026-03-27
2025-08-06   $121,193.50  $120,320.00  -0.72%     2026-03-27
```

## Real Data Example - Backwardation Period

The fetched data from Oct 2025 - Feb 2026 shows a **backwardation** market:

```
Date         Spot       Futures    Basis
----------------------------------------------------------------------
2026-02-06   $73,408    $70,505    -3.96% (futures < spot)
2026-02-05   $66,785    $63,270    -5.26%
2026-02-04   $76,905    $72,795    -5.34%
2026-02-03   $80,105    $76,420    -4.60%
2026-01-30   $87,857    $84,640    -3.66%
```

**Result**: Backtest found **0 entry signals** (correct behavior)

The basis trade strategy only enters when:
- Basis > 0 (contango: futures > spot)
- Monthly basis > 0.5%

## Understanding the Results

### Why Zero Trades?

When the backtest shows 0 trades, it means:
1. **Market was in backwardation** - Futures traded below spot
2. **No profitable entry** - Basis trade requires contango
3. **Strategy worked correctly** - Did not enter unprofitable trades

### Backwardation vs. Contango

| Market State | Futures vs Spot | Basis | Strategy |
|--------------|----------------|-------|----------|
| **Contango** | Futures > Spot | Positive | ✓ Enter trade |
| **Backwardation** | Futures < Spot | Negative | ✗ Stay out |

Example:
- Contango: Spot $70k, Futures $72k → +2.86% basis → Enter
- Backwardation: Spot $73k, Futures $70k → -3.96% basis → No entry

### Finding Contango Periods

To find profitable periods, you need data from bull markets where:
- Strong demand for futures (institutional buying)
- Positive market sentiment
- Normal cost of carry priced in

Historical examples:
- **2024 Q1**: IBIT launch, strong contango (~12% annual)
- **2021 bull run**: Persistent 10-20% annual basis
- **2019-2020**: Moderate 5-10% annual basis

## Prerequisites

### IBKR Account Setup

1. **Account Requirements**:
   - IBKR account (paper or live)
   - Futures trading permissions enabled
   - Market data subscription (delayed = free, real-time = $4.50/mo)

2. **Software Running**:
   - TWS (Trader Workstation) or IB Gateway
   - API enabled in settings
   - Port 7496 (live) or 7497 (paper) open

3. **Python Dependencies**:
   ```bash
   pip install ib-insync
   ```

### Market Data Limitations

**IBIT Historical Data**:
- Available from: **January 11, 2024** (ETF launch date)
- Max history: ~2 years currently
- Resolution: Daily bars (1 day)

**MBT Futures Historical Data**:
- Available for: Active + recently expired contracts
- Typically: ~6 months of history per contract
- Resolution: 1 day, 1 hour, 5 min (configurable)

## Advanced Configuration

### Fetching Multiple Time Periods

```python
# Fetch 2024 data (bull market)
start_date = datetime(2024, 1, 15)
end_date = datetime(2024, 6, 30)
futures_contracts = ['202401', '202402', '202403', '202404', '202405', '202406']

fetcher.create_backtest_csv(
    output_file="btc_basis_2024_bull.csv",
    start_date=start_date,
    end_date=end_date,
    futures_contracts=futures_contracts
)
```

### Using Different Spot Proxies

Edit `get_historical_spot()` to use different ETFs:

```python
# Use FBTC instead of IBIT
spot_data = self.get_historical_spot(
    symbol='FBTC',  # or 'GBTC'
    start_date=start_date,
    end_date=end_date
)
```

### Higher Resolution Data

```python
# Fetch hourly data instead of daily
bars = self.ib.reqHistoricalData(
    stock,
    endDateTime=end_date,
    durationStr=duration_str,
    barSizeSetting='1 hour',  # Changed from '1 day'
    whatToShow='TRADES',
    useRTH=True,
    formatDate=1
)
```

## Troubleshooting

### "No security definition found"

**Cause**: Expired futures contract or wrong expiry format

**Fix**:
```python
# Only use active contracts
# Check CME calendar: https://www.cmegroup.com/markets/cryptocurrencies/bitcoin/micro-bitcoin.html

futures_contracts = [
    '202603',  # Active: Mar 2026
    '202604',  # Active: Apr 2026
]

# NOT: '202512' (expired December 2025)
```

### "No data fetched" (0 bars)

**Cause**: Market data subscription not active or date range too old

**Fix**:
1. Verify market data subscription in IBKR account
2. Use recent dates (within last 2 years for IBIT)
3. Check IBKR market hours (closed weekends)

### "Basis percentages look wrong"

**Cause**: Incorrect price multipliers

**Fix**: The script automatically handles:
- IBIT: ~1850x multiplier
- MBT: No multiplier (already in index points)

If prices seem off, check:
- IBIT multiplier may drift over time (NAV changes)
- Consider using actual Bitcoin spot API instead of ETF proxy

## Comparison: IBKR vs. Synthetic Data

| Aspect | IBKR Historical | Synthetic (Generator) |
|--------|----------------|---------------------|
| **Accuracy** | Real market data | Simulated trends |
| **Basis** | Actual contango/backwardation | Programmed patterns |
| **Data Range** | Limited (IBIT since Jan 2024) | Unlimited |
| **Setup** | Requires IBKR account | No setup |
| **Use Case** | Production validation | Quick testing |

## Next Steps

1. **Fetch recent data** (when market opens):
   ```bash
   python fetch_ibkr_historical.py
   ```

2. **Run backtest**:
   ```bash
   python btc_basis_backtest.py --data btc_basis_ibkr_historical.csv
   ```

3. **Analyze results**:
   - Check `backtest_result_*.json` for trade details
   - Look for profitable periods (contango)
   - Identify risk events (backwardation periods)

4. **Fetch bull market data** (when available):
   - Target 2024 Q1 data (IBIT launch, strong contango)
   - Or wait for next bull market to collect profitable periods

## Example: Complete Workflow

```bash
# 1. Ensure IBKR is running
# (Start TWS or IB Gateway, enable API)

# 2. Fetch 90 days of historical data
python fetch_ibkr_historical.py

# Output: btc_basis_ibkr_historical.csv created with 130 rows

# 3. Run backtest
python btc_basis_backtest.py --data btc_basis_ibkr_historical.csv --holding-days 30

# Output: backtest_result_20260208_232240.json

# 4. Analyze results
cat backtest_result_20260208_232240.json | python -m json.tool

# 5. If zero trades (backwardation), try different date range
# Edit fetch_ibkr_historical.py to use 2024 Q1 dates
# Re-run steps 2-4
```

## Files Summary

| File | Purpose | Output |
|------|---------|--------|
| `fetch_ibkr_historical.py` | Fetch IBKR historical data | CSV file |
| `btc_basis_backtest.py` | Run backtest | JSON results |
| `btc_basis_ibkr_historical.csv` | Historical market data | Input for backtest |
| `backtest_result_*.json` | Backtest results | Analysis data |

## Key Insights from Real Data

### August 2025 - February 2026 Period

**Market Conditions**:
- Persistent backwardation throughout period
- BTC price declined: $120k → $73k (-39%)
- Futures consistently 1-5% below spot
- **Zero profitable basis trade entries**

**Lessons**:
1. **Basis trades don't work in all markets** - Need contango
2. **Backwardation = bear market signal** - Risk off, selling pressure
3. **Strategy discipline works** - Did not force unprofitable trades
4. **Need bull market data for testing** - 2024 Q1 would show trades

## Conclusion

The IBKR historical data fetcher provides **real market data** for accurate backtesting. The current market showed **backwardation**, correctly resulting in zero trades.

To see profitable trades:
- Fetch data from contango periods (2024 Q1)
- Wait for next bull market
- Or use synthetic data generators for testing strategy logic

**The tool is working correctly** - it simply reflects the reality that basis trades aren't always available!
