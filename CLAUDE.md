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

### Package Structure

The codebase is organized as a modular Python package under `src/btc_basis/`:

```
btc-basis-trade/
├── main.py                          # Unified CLI entry point
├── setup.py                         # Package installation config
├── config/
│   └── config.json                  # User configuration
├── config_example.json
├── data/                            # Sample CSV data files
├── output/                          # Generated reports, logs, backtests
├── tests/
└── src/btc_basis/                   # Main package
    ├── __init__.py
    ├── core/                        # Core business logic
    │   ├── models.py                # Signal, TradeConfig, MarketData
    │   ├── analyzer.py              # BasisTradeAnalyzer
    │   └── calculator.py            # BasisCalculator (shared math)
    ├── data/                        # Data fetchers
    │   ├── base.py                  # BaseFetcher ABC
    │   ├── coinbase.py              # CoinbaseFetcher, FearGreedFetcher
    │   ├── binance.py               # BinanceFetcher
    │   ├── ibkr.py                  # IBKRFetcher, IBKRHistoricalFetcher
    │   └── historical.py            # RollingDataProcessor
    ├── backtest/                    # Backtesting engine
    │   ├── engine.py                # Backtester, Trade, BacktestResult
    │   └── costs.py                 # TradingCosts calculations
    ├── monitor/                     # Monitoring daemon
    │   └── daemon.py                # BasisMonitor
    └── utils/                       # Shared utilities
        ├── config.py                # ConfigLoader
        ├── logging.py               # LoggingMixin, setup_logging
        ├── expiry.py                # Futures expiry utilities
        └── io.py                    # ReportWriter
```

### Core Module (`src/btc_basis/core/`)

- **models.py**: Data classes
  - `Signal` enum: Trading signals (STRONG_ENTRY, ACCEPTABLE_ENTRY, PARTIAL_EXIT, FULL_EXIT, STOP_LOSS)
  - `TradeConfig`: Configuration parameters (account size, leverage, funding cost, thresholds)
  - `MarketData`: Encapsulates spot price, futures price, expiry date, and calculated basis metrics
- **analyzer.py**: `BasisTradeAnalyzer` - core analysis engine with methods for returns calculation, signal generation, risk assessment, and position sizing
- **calculator.py**: `BasisCalculator` - centralized basis math used across modules

### Data Module (`src/btc_basis/data/`)

- **base.py**: `BaseFetcher` abstract base class defining the interface for all data sources
- **coinbase.py**: `CoinbaseFetcher` (BTC spot), `FearGreedFetcher` (sentiment)
- **binance.py**: `BinanceFetcher` for Binance spot/futures
- **ibkr.py**: Unified `IBKRFetcher` and `IBKRHistoricalFetcher` for Interactive Brokers
- **historical.py**: `RollingDataProcessor` for historical data handling

### Backtest Module (`src/btc_basis/backtest/`)

- **engine.py**: `Backtester` class with `Trade` and `BacktestResult` dataclasses
- **costs.py**: `TradingCosts` for comprehensive cost calculations

### Monitor Module (`src/btc_basis/monitor/`)

- **daemon.py**: `BasisMonitor` for continuous monitoring with alert generation

### Utils Module (`src/btc_basis/utils/`)

- **config.py**: `ConfigLoader` with default config management
- **logging.py**: `LoggingMixin` for consistent logging across modules
- **expiry.py**: `get_last_friday_of_month`, `get_front_month_expiry`, `generate_expiry_schedule`
- **io.py**: `ReportWriter` for text and JSON output generation

### Data Flow

```
ConfigLoader → TradeConfig → BasisTradeAnalyzer
                                      ↓
DataFetchers → MarketData → Analyzer.generate_signal() → Signal
                                      ↓
                              Analyzer.assess_risk() → Risk Dict
                                      ↓
                              Analyzer.calculate_position_sizing() → Position Dict
                                      ↓
                              ReportWriter → output/*.txt, output/*.json
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

### Installation

```bash
pip install -e .
```

### Unified CLI (Recommended)

```bash
# Single analysis
python main.py analyze

# Interactive menu
python main.py cli

# Continuous monitoring (every 5 minutes)
python main.py monitor --interval 300

# Single monitoring check
python main.py monitor --once

# Backtesting with CSV data
python main.py backtest --data data/historical_basis.csv --holding-days 30

# Backtesting with synthetic data
python main.py backtest --start 2024-01-01 --end 2024-12-31
```

### Command Reference

| Command | Description |
|---------|-------------|
| `python main.py analyze` | Single-run analysis with current market data |
| `python main.py cli` | Interactive CLI menu |
| `python main.py monitor --once` | One-time monitoring check |
| `python main.py monitor --interval N` | Continuous monitoring every N seconds |
| `python main.py backtest --data FILE` | Run backtest on historical CSV data |

## Configuration

Configuration is read from `config/config.json` (copy from `config_example.json`):

```json
{
  "account_size": 200000,
  "spot_target_pct": 0.50,
  "futures_target_pct": 0.50,
  "funding_cost_annual": 0.05,
  "leverage": 1.0,
  "cme_contract_size": 5.0,
  "min_monthly_basis": 0.005,
  "alert_thresholds": { ... }
}
```

**Critical**: `spot_target_pct` + `futures_target_pct` should equal 1.0 for balanced delta-neutral exposure.

## Key Formulas (Implementation Reference)

**Basis Calculations** (in `BasisCalculator` and `MarketData` properties):
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
- **Coinbase API**: `https://api.coinbase.com/v2/prices/BTC-USD/spot` (public, no key)
- **Fear & Greed Index**: `https://api.alternative.me/fng/` (public)
- **Binance**: Spot and futures prices
- **IBKR**: CME futures via Client Portal API (requires IBKR account)

**Data Fetcher Hierarchy**:
```
BaseFetcher (ABC)
├── CoinbaseFetcher
├── FearGreedFetcher
├── BinanceFetcher
├── IBKRFetcher
└── IBKRHistoricalFetcher
```

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

Create a new fetcher by extending `BaseFetcher` in `src/btc_basis/data/`:

```python
from btc_basis.data.base import BaseFetcher

class MyExchangeFetcher(BaseFetcher):
    def fetch_spot_price(self) -> float:
        # Implement API call
        pass

    def fetch_futures_data(self) -> dict:
        # Return: {'futures_price': float, 'expiry': datetime, 'open_interest': int}
        pass
```

### Custom Alert Notifications

Extend `BasisMonitor.send_alert()` in `src/btc_basis/monitor/daemon.py`:

```python
def send_alert(self, message: str, data: Dict):
    # Currently writes to output/alerts.log
    # Add: email (smtplib), SMS (Twilio), webhooks (requests.post)
```

### Additional Signal Logic

Extend `BasisTradeAnalyzer.generate_signal()` in `src/btc_basis/core/analyzer.py`:
- Always check `monthly_basis` first (primary signal)
- Return `(Signal, reason: str)` tuple
- Update `Signal` enum in `models.py` if adding new signal types

### Adding New Backtest Metrics

Extend `BacktestResult` dataclass in `src/btc_basis/backtest/engine.py`:

```python
@dataclass
class BacktestResult:
    # Add new fields
    sortino_ratio: float = 0.0
    max_consecutive_losses: int = 0

    @property
    def calmar_ratio(self) -> float:
        return self.total_return / self.max_drawdown if self.max_drawdown > 0 else 0.0
```

## Common Development Tasks

### Testing with Custom Market Data

```python
from btc_basis.core.models import Signal, TradeConfig, MarketData
from btc_basis.core.analyzer import BasisTradeAnalyzer
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

### Using the Package Programmatically

```python
from btc_basis import Signal, TradeConfig, MarketData, BasisTradeAnalyzer
from btc_basis.data.coinbase import CoinbaseFetcher
from btc_basis.utils.config import ConfigLoader

# Load config
config = ConfigLoader.load("config/config.json")
trade_config = TradeConfig(**config)

# Fetch live data
fetcher = CoinbaseFetcher()
spot_price = fetcher.fetch_spot_price()

# Analyze
analyzer = BasisTradeAnalyzer(trade_config)
# ...
```

## Important Constraints

**CME Contract Rounding**: Futures contracts must be integers. The analyzer rounds to nearest (min 1), which can create small delta imbalances for small accounts. For accounts < $100k, this is a known limitation.

**Time Normalization**: All basis metrics are normalized to 30-day monthly equivalents for comparison across different expiries. The annualized calculations use actual `days_to_expiry`.

**Funding Cost Timing**: Applied linearly over holding period in backtester: `(funding_rate / 365) × holding_days × position_value`

**Live Data Fallback**: If data fetchers fail (network issue, API down), scripts use sample data. Check for "Using sample data" in output.

**Futures Expiry**: Uses rolling front-month contracts with automatic expiry detection via `utils/expiry.py`.

## Output Files Reference

All output files are written to the `output/` directory:

| File Pattern | Generated By | Contains |
|--------------|--------------|----------|
| `output/btc_basis_analysis_*.txt` | analyze | Human-readable report |
| `output/btc_basis_analysis_*.json` | analyze | Structured market data, returns, signals, risks, positions |
| `output/btc_basis_monitor.log` | monitor | Timestamped monitoring activity |
| `output/alerts.log` | monitor | Trading alerts only (entry/exit/stop signals) |
| `output/basis_history_*.json` | monitor | Time-series of basis data points |
| `output/backtest_result_*.json` | backtest | Trade list, metrics (Sharpe, drawdown, win rate) |

All JSON files use ISO-8601 timestamps and can be imported to Excel/pandas.

## Dependencies

From `requirements.txt`:
- `requests>=2.31.0`: HTTP client for API calls (Coinbase, Binance, Fear & Greed)
- `python-dateutil>=2.8.2`: Date parsing utilities

Standard library only otherwise (json, dataclasses, enum, datetime, argparse, logging, csv).

## Financial Domain Notes

**This is educational software, not financial advice.** When modifying:
- Preserve risk warnings in output
- Never auto-execute trades without explicit user confirmation
- Maintain transparency in return calculations (show gross vs net, before/after funding)
- Log all signal changes for audit trail (see `BasisMonitor.check_and_alert()`)

**Regulatory Context**: Basis trades may have tax implications (short-term capital gains, wash sales). The software does not provide tax guidance.
