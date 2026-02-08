# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bitcoin Basis Trade Analysis Toolkit - A Python toolkit for analyzing and monitoring cash-and-carry arbitrage (basis trade) opportunities between Bitcoin spot and futures markets. This is a market-neutral strategy that captures the spread (basis) between spot prices and futures prices.

## Core Concepts

**Basis Trade Strategy**:
- Long spot BTC (via ETF like IBIT/FBTC)
- Short equivalent BTC futures (CME)
- Delta-neutral position that profits from basis convergence
- Return = (Futures Price - Spot Price) / Spot Price × (365 / Days) - Funding Cost

**Key Metrics**:
- **Monthly Basis**: Normalized 30-day basis percentage (primary entry/exit signal)
- **Net Annualized Return**: Gross annualized basis return minus funding costs
- **Delta Neutral**: Long spot + short futures = zero directional exposure

## Architecture

### Module Structure

The codebase has 4 main executable scripts that share common core classes:

**Core Data Classes** (defined in `btc_basis_trade_analyzer.py`):
- `MarketData`: Encapsulates spot price, futures price, expiry date, and calculated basis metrics
- `TradeConfig`: Configuration parameters (account size, leverage, funding cost, thresholds)
- `Signal` enum: Trading signals (STRONG_ENTRY, ACCEPTABLE_ENTRY, PARTIAL_EXIT, FULL_EXIT, STOP_LOSS)
- `BasisTradeAnalyzer`: Core analysis engine with methods for returns calculation, signal generation, risk assessment, and position sizing
- `MarketDataFetcher`: Fetches live data from Coinbase (spot), Alternative.me (Fear & Greed)

**Executable Scripts**:
1. `btc_basis_trade_analyzer.py`: Single-run analysis with current market data
2. `btc_basis_monitor.py`: Continuous monitoring daemon that imports analyzer classes
3. `btc_basis_backtest.py`: Backtesting engine that imports analyzer and extends with `Trade`, `BacktestResult` classes
4. `btc_basis_cli.py`: Interactive CLI menu that orchestrates all three above scripts

### Data Flow

```
Config (JSON) → TradeConfig → BasisTradeAnalyzer
                                      ↓
MarketDataFetcher → MarketData → Analyzer.generate_signal() → Signal
                                      ↓
                              Analyzer.assess_risk() → Risk Dict
                                      ↓
                              Analyzer.calculate_position_sizing() → Position Dict
```

### Signal Generation Logic

Signal thresholds (from `BasisTradeAnalyzer.generate_signal()`):
- Monthly basis < 0% → STOP_LOSS (backwardation)
- Monthly basis < 0.2% → STOP_LOSS (compressed)
- Monthly basis > 3.5% → FULL_EXIT (take profit peak)
- Monthly basis > 2.5% → PARTIAL_EXIT (elevated)
- Monthly basis > 1.0% → STRONG_ENTRY
- Monthly basis 0.5-1.0% → ACCEPTABLE_ENTRY
- Otherwise → NO_ENTRY

Additional stop conditions: ETF discount > 1%, funding cost > basis

## Running the Tools

### Quick Analysis
```bash
python btc_basis_trade_analyzer.py
```
Generates `btc_basis_analysis_YYYYMMDD_HHMMSS.txt` and `.json` in current directory.

### Interactive Menu (Recommended for Users)
```bash
python btc_basis_cli.py
```

### Continuous Monitoring
```bash
# Every 5 minutes (recommended)
python btc_basis_monitor.py --interval 300

# Single check
python btc_basis_monitor.py --once

# Custom config
python btc_basis_monitor.py --config my_config.json
```
Outputs: `btc_basis_monitor.log`, `alerts.log`, `basis_history_YYYYMMDD.json`

### Backtesting
```bash
# Generate synthetic data for 2024
python btc_basis_backtest.py --start 2024-01-01 --end 2024-12-31

# Use CSV data (format: date,spot_price,futures_price,futures_expiry)
python btc_basis_backtest.py --data historical_basis.csv --holding-days 30

# Output to specific file
python btc_basis_backtest.py --data data.csv --output results.json
```
Generates `backtest_result_YYYYMMDD_HHMMSS.json` with trade-by-trade details.

## Configuration

All scripts read from `config.json` (copy from `config_example.json`):

```json
{
  "account_size": 200000,           // Total capital ($)
  "spot_target_pct": 0.50,          // 50% to spot leg
  "futures_target_pct": 0.50,       // 50% to futures leg
  "funding_cost_annual": 0.05,      // 5% annual funding (SOFR + spread)
  "leverage": 1.0,                  // 1x = no leverage
  "cme_contract_size": 5.0,         // BTC per CME contract
  "min_monthly_basis": 0.005,       // 0.5% minimum entry threshold
  "alert_thresholds": { ... }
}
```

**Critical**: `spot_target_pct` + `futures_target_pct` should equal 1.0 for balanced delta-neutral exposure.

## Key Formulas (Implementation Reference)

**Basis Calculations** (in `MarketData` properties):
```python
basis_absolute = futures_price - spot_price
basis_percent = basis_absolute / spot_price
monthly_basis = basis_percent * (30 / days_to_expiry)  # Normalized to 30 days
```

**Returns** (in `BasisTradeAnalyzer.calculate_returns()`):
```python
gross_annualized = basis_percent * (365 / days_to_expiry)
net_annualized = gross_annualized - funding_cost_annual
leveraged_return = net_annualized * leverage
```

**Position Sizing** (in `BasisTradeAnalyzer.calculate_position_sizing()`):
```python
# ETF leg
etf_shares = floor(spot_target_amount / etf_price)
actual_spot_value = etf_shares * etf_price

# Futures leg
btc_amount = futures_target_amount / spot_price
contracts = round(btc_amount / cme_contract_size)  # Min 1
actual_futures_value = contracts * cme_contract_size * spot_price
```

## Data Sources

**Currently Integrated**:
- Coinbase API: `https://api.coinbase.com/v2/prices/BTC-USD/spot` (public, no key)
- Fear & Greed Index: `https://api.alternative.me/fng/` (public)
- CoinGlass: `https://open-api.coinglass.com/public/v2/indicator/bitcoin_basis` (public endpoint, API key for premium)

**Futures Data Limitation**: Currently uses estimated futures prices (spot × 1.02 for 2% basis). For production, integrate:
- CME Group API (requires account)
- IBKR Client Portal API
- Deribit API

## Risk Assessment Categories

The `BasisTradeAnalyzer.assess_risk()` method evaluates 5 risk dimensions:

1. **Funding Risk**: Checks if `funding_cost_annual > 0.06` (6%)
2. **Basis Risk**: Monitors for negative basis (backwardation) or < 0.5% monthly
3. **Liquidity Risk**: ETF discount/premium vs NAV (alert if > 1% discount)
4. **Crowding Risk**: CME open interest (warning if > 30k contracts, high if > 40k)
5. **Operational Risk**: Days to expiry (warning if < 7 days, rollover imminent)

Returns dict with emoji indicators: ✅ (low/moderate), ⚠️ (high), ❌ (critical)

## Extending the Codebase

### Adding New Data Sources

Extend `MarketDataFetcher` class in `btc_basis_trade_analyzer.py`:
```python
@staticmethod
def fetch_cme_futures() -> Optional[Dict]:
    # Implement CME API call
    # Return: {'futures_price': float, 'expiry': datetime, 'open_interest': int}
```

### Custom Alert Notifications

Modify `BasisMonitor.send_alert()` in `btc_basis_monitor.py`:
```python
def send_alert(self, message: str, data: Dict):
    # Currently writes to alerts.log
    # Add: email (smtplib), SMS (Twilio), webhooks (requests.post)
```

### Additional Signal Logic

Extend `BasisTradeAnalyzer.generate_signal()` with new conditions:
- Always check `monthly_basis` first (primary signal)
- Return `(Signal, reason: str)` tuple
- Update `Signal` enum if adding new signal types

## Common Development Tasks

### Testing with Custom Market Data
```python
from btc_basis_trade_analyzer import BasisTradeAnalyzer, MarketData, TradeConfig
from datetime import datetime, timedelta

market = MarketData(
    spot_price=95000,
    futures_price=97200,
    futures_expiry_date=datetime.now() + timedelta(days=30),
    etf_price=53.50,
    fear_greed_index=0.75
)

config = TradeConfig(account_size=200000)
analyzer = BasisTradeAnalyzer(config)
signal, reason = analyzer.generate_signal(market)
print(f"{signal}: {reason}")
```

### Adding New Backtest Metrics

Extend `BacktestResult` dataclass in `btc_basis_backtest.py`:
```python
@dataclass
class BacktestResult:
    # Add new fields
    sortino_ratio: float = 0.0
    max_consecutive_losses: int = 0

    # Add computed properties
    @property
    def calmar_ratio(self) -> float:
        return self.total_return / self.max_drawdown if self.max_drawdown > 0 else 0.0
```

Calculate in `Backtester.run_backtest()` after main loop.

## Important Constraints

**CME Contract Rounding**: Futures contracts must be integers. The analyzer rounds to nearest (min 1), which can create small delta imbalances for small accounts. For accounts < $100k, this is a known limitation.

**Time Normalization**: All basis metrics are normalized to 30-day monthly equivalents for comparison across different expiries. The annualized calculations use actual `days_to_expiry`.

**Funding Cost Timing**: Applied linearly over holding period in backtester: `(funding_rate / 365) × holding_days × position_value`

**Live Data Fallback**: If `MarketDataFetcher` fails (network issue, API down), scripts use sample data. Check for "⚠️ Using sample data" in output.

## Output Files Reference

| File Pattern | Generated By | Contains |
|--------------|--------------|----------|
| `btc_basis_analysis_*.txt` | analyzer.py | Human-readable report |
| `btc_basis_analysis_*.json` | analyzer.py | Structured market data, returns, signals, risks, positions |
| `btc_basis_monitor.log` | monitor.py | Timestamped monitoring activity |
| `alerts.log` | monitor.py | Trading alerts only (entry/exit/stop signals) |
| `basis_history_*.json` | monitor.py | Time-series of basis data points |
| `backtest_result_*.json` | backtest.py | Trade list, metrics (Sharpe, drawdown, win rate) |

All JSON files use ISO-8601 timestamps and can be imported to Excel/pandas.

## Dependencies

From `requirements.txt`:
- `requests>=2.31.0`: HTTP client for API calls (Coinbase, CoinGlass, Fear & Greed)
- `python-dateutil>=2.8.2`: Date parsing utilities

Standard library only otherwise (json, dataclasses, enum, datetime, argparse, logging, csv).

## Financial Domain Notes

**This is educational software, not financial advice.** When modifying:
- Preserve risk warnings in output
- Never auto-execute trades without explicit user confirmation
- Maintain transparency in return calculations (show gross vs net, before/after funding)
- Log all signal changes for audit trail (see `BasisMonitor.check_and_alert()`)

**Regulatory Context**: Basis trades may have tax implications (short-term capital gains, wash sales). The software does not provide tax guidance.
