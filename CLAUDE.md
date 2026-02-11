# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-Asset Basis Trade Analysis Toolkit - A Python toolkit for analyzing and monitoring cash-and-carry arbitrage (basis trade) opportunities between spot ETFs and futures markets. Supports multiple asset classes (BTC, ETH, Oil, Gold, Silver) each with their own spot+futures pair. This is a market-neutral strategy that captures the spread (basis) between spot prices and futures prices.

## Core Concepts

**Basis Trade Strategy**:
- Long spot (via ETF like IBIT, ETHA, GLD, USO, SLV)
- Short equivalent futures (CME, NYMEX, COMEX)
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
│   └── execution/                   # Execution logs and position state
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
    ├── execution/                   # Trade execution via IBKR
    │   ├── models.py                # ExecutionConfig, OrderRequest, OrderResult, enums
    │   ├── position.py              # Position, PositionTracker
    │   ├── executor.py              # IBKRExecutor (order placement)
    │   └── manager.py               # ExecutionManager (signal-to-trade bridge)
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
  - `PairConfig`: Per-pair configuration (pair_id, spot_symbol, futures_symbol, futures_exchange, contract_size, tick_size, allocation_pct)
  - `make_pair_trade_config(global_config, pair)`: Clones global TradeConfig with account_size scaled by pair's allocation and pair's contract_size
  - `MarketData`: Encapsulates spot price, futures price, expiry date, calculated basis metrics, and optional `pair_id`
- **analyzer.py**: `BasisTradeAnalyzer` - core analysis engine with methods for returns calculation, signal generation, risk assessment, and position sizing
- **calculator.py**: `BasisCalculator` - centralized basis math used across modules

### Data Module (`src/btc_basis/data/`)

- **base.py**: `BaseFetcher` abstract base class defining the interface for all data sources
- **coinbase.py**: `CoinbaseFetcher` (BTC spot), `FearGreedFetcher` (sentiment)
- **binance.py**: `BinanceFetcher` for Binance spot/futures
- **ibkr.py**: Unified `IBKRFetcher` and `IBKRHistoricalFetcher` for Interactive Brokers. Pair-aware: `get_complete_basis_data(pair=PairConfig)` routes to correct exchange. `fetch_raw_etf_price()` for non-BTC ETFs. `fetch_futures_price(exchange=)` supports CME/NYMEX/COMEX
- **historical.py**: `RollingDataProcessor` for historical data handling

### Backtest Module (`src/btc_basis/backtest/`)

- **engine.py**: `Backtester` class with `Trade` and `BacktestResult` dataclasses
- **costs.py**: `TradingCosts` for comprehensive cost calculations

### Execution Module (`src/btc_basis/execution/`)

- **models.py**: Data classes and enums for the execution subsystem
  - `ExecutionConfig`: Parsed from `config.json["execution"]` — controls `enabled`, `auto_trade`, `dry_run`, symbols, order type, position limits, and `execution_client_id`
  - `OrderRequest`: Describes a proposed order (side, symbol, quantity, order type, limit price, triggering signal, `contract_type` "stock"/"futures", `futures_exchange`)
  - `OrderResult`: Result after submission (status, fill price, filled qty, commission, errors)
  - Enums: `OrderSide` (BUY/SELL), `OrderType` (MARKET/LIMIT), `OrderStatus` (PENDING/SUBMITTED/FILLED/PARTIALLY_FILLED/CANCELLED/FAILED), `TradeAction` (OPEN/CLOSE/REDUCE/NONE)
- **position.py**: Position persistence
  - `Position`: Current open position state (`pair_id`, ETF shares, futures contracts, entry prices, expiry). Properties: `is_open`, `is_balanced`
  - `PositionTracker`: Per-pair file persistence to `output/execution/position_state_{pair_id}.json`. Accepts `pair_id` parameter. Survives restarts
- **executor.py**: `IBKRExecutor` — places orders via `ib_insync` using a separate `execution_client_id` (default 2) to avoid connection conflicts with the data fetcher
  - `connect()` / `disconnect()`: Connect with execution client_id
  - `execute_order(request)`: Single order entry point; in `dry_run` mode, logs but doesn't submit
  - `execute_entry_pair(etf_shares, futures_contracts, ..., pair=PairConfig)`: BUY ETF then SELL futures; uses pair-specific symbols/exchange/tick_size; aborts futures leg if ETF fails
  - `execute_exit_pair(pair=PairConfig)`: SELL ETF + BUY futures using current position from tracker
  - `execute_partial_exit(exit_pct=0.5, pair=PairConfig)`: Reduce both legs proportionally
- **manager.py**: `ExecutionManager` — bridges monitor signals to executor
  - Constructor accepts optional `pair: PairConfig` for per-pair position tracking and logging
  - `handle_signal(signal, reason, market)`: Main entry point called by monitor. Maps signal to `TradeAction`, gets position sizing, runs safety checks, optionally prompts for confirmation, executes, and logs
  - `_determine_action(signal)`: Signal × position-state → action mapping
  - `_safety_checks(action, sizing, market)`: Position limits, weekend guard, backwardation guard
  - All events logged to `output/execution/execution_log.jsonl` with `pair_id`

### Monitor Module (`src/btc_basis/monitor/`)

- **daemon.py**: Multi-pair monitor with `PairContext` dataclass and `BasisMonitor`
  - `PairContext`: Per-pair runtime state (pair config, trade config, analyzer, execution manager, signal history)
  - `BasisMonitor.__init__()`: Loads pairs via `ConfigLoader.get_pairs()`, creates per-pair `PairContext` with scaled `TradeConfig` and optional `ExecutionManager`
  - `fetch_market_data(pair)`: IBKR path calls `get_complete_basis_data(pair=pair)`; Coinbase fallback only for BTC
  - `check_and_alert(ctx, market)`: Per-pair signal generation and execution; alert messages prefixed with `[PAIR_ID]`
  - `run_continuous(pair_filter=)` / `run_once(pair_filter=)`: Iterates over all (or filtered) pairs
  - `generate_summary_report()`: Combined summary showing all pairs

### Utils Module (`src/btc_basis/utils/`)

- **config.py**: `ConfigLoader` with default config management and `get_pairs()` method
  - `get_pairs() -> List[PairConfig]`: Parses `pairs` array from config. If absent (legacy), synthesizes single BTC pair from `execution.spot_symbol`, `execution.futures_symbol`, `cme_contract_size`
- **logging.py**: `LoggingMixin` for consistent logging across modules
- **expiry.py**: `get_last_friday_of_month`, `get_front_month_expiry`, `generate_expiry_schedule`
- **io.py**: `ReportWriter` for text and JSON output generation

### Data Flow

```
ConfigLoader → get_pairs() → List[PairConfig]
                                      ↓
                For each pair:
                  make_pair_trade_config(global, pair) → pair TradeConfig
                  pair TradeConfig → BasisTradeAnalyzer
                                      ↓
                  DataFetchers(pair) → MarketData(pair_id=...) → Analyzer.generate_signal() → Signal
                                      ↓
                              Analyzer.assess_risk() → Risk Dict
                                      ↓
                              Analyzer.calculate_position_sizing() → Position Dict
                                      ↓
                              ReportWriter → output/*.txt, output/*.json
```

### Execution Flow (when `execution.enabled` is true)

```
BasisMonitor.run_continuous() / run_once()
        ↓ (for each pair)
    fetch_market_data(ctx.pair) → MarketData
        ↓
    check_and_alert(ctx, market)
        ↓ (alert triggered)
    ctx.ExecutionManager.handle_signal(signal, reason, market)
        ↓
    _determine_action(signal) → TradeAction (OPEN/CLOSE/REDUCE/NONE)
        ↓
    _safety_checks(action, sizing, market) → pass/reject
        ↓
    [if auto_trade=false] _prompt_confirmation() → yes/no
        ↓
    IBKRExecutor.execute_entry_pair(pair=self.pair) / execute_exit_pair(pair=) / execute_partial_exit(pair=)
        ↓                                           ↓
    PositionTracker(pair_id).save()     execution_log.jsonl (append, with pair_id)
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
# Analyze all configured pairs
python main.py analyze

# Analyze single pair
python main.py analyze --pair BTC

# Interactive menu
python main.py cli

# Continuous monitoring (every 5 minutes, all pairs)
python main.py monitor --interval 300

# Monitor single pair
python main.py monitor --pair ETH --once

# Single monitoring check
python main.py monitor --once

# Monitor with execution (dry-run, manual confirmation)
python main.py monitor --execute --dry-run --once

# Monitor with execution (dry-run, auto-trade, no prompts)
python main.py monitor --execute --dry-run --auto-trade --interval 300

# Monitor with live execution (requires IBKR connection)
python main.py monitor --execute --auto-trade --interval 300

# Backtesting with CSV data
python main.py backtest --data data/historical_basis.csv --holding-days 30

# Backtesting with synthetic data
python main.py backtest --start 2024-01-01 --end 2024-12-31
```

### Command Reference

| Command | Description |
|---------|-------------|
| `python main.py analyze` | Analyze all configured pairs |
| `python main.py analyze --pair BTC` | Analyze single pair |
| `python main.py cli` | Interactive CLI menu |
| `python main.py monitor --once` | One-time monitoring check (all pairs) |
| `python main.py monitor --pair ETH --once` | One-time check for single pair |
| `python main.py monitor --interval N` | Continuous monitoring every N seconds |
| `python main.py monitor --execute` | Enable trade execution (uses config or defaults) |
| `python main.py monitor --dry-run` | Log proposed orders without submitting to IBKR |
| `python main.py monitor --auto-trade` | Skip manual confirmation prompts |
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
  "alert_thresholds": { ... },
  "ibkr": { ... },
  "execution": {
    "enabled": false,
    "auto_trade": false,
    "order_type": "limit",
    "limit_offset_pct": 0.001,
    "max_etf_shares": 10000,
    "max_futures_contracts": 50,
    "execution_client_id": 2,
    "dry_run": true
  },
  "pairs": [
    {
      "pair_id": "BTC",
      "spot_symbol": "IBIT",
      "futures_symbol": "MBT",
      "futures_exchange": "CME",
      "contract_size": 0.1,
      "tick_size": 5.0,
      "allocation_pct": 0.40
    },
    {
      "pair_id": "ETH",
      "spot_symbol": "ETHA",
      "futures_symbol": "MET",
      "futures_exchange": "CME",
      "contract_size": 0.1,
      "tick_size": 0.25,
      "allocation_pct": 0.20
    }
  ]
}
```

**Critical**: `spot_target_pct` + `futures_target_pct` should equal 1.0 for balanced delta-neutral exposure.

**Critical**: `allocation_pct` across all pairs should sum to 1.0 for full capital utilization.

### Pair Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `pair_id` | `"BTC"` | Unique identifier for the pair |
| `spot_symbol` | `"IBIT"` | ETF symbol for the spot leg |
| `futures_symbol` | `"MBT"` | Futures symbol |
| `futures_exchange` | `"CME"` | Exchange for futures (`CME`, `NYMEX`, `COMEX`) |
| `contract_size` | `0.1` | Futures contract size in underlying units |
| `tick_size` | `5.0` | Minimum price increment for limit orders |
| `spot_exchange` | `"SMART"` | Exchange for spot ETF orders |
| `currency` | `"USD"` | Currency |
| `enabled` | `true` | Whether this pair is active |
| `allocation_pct` | `1.0` | Fraction of `account_size` allocated to this pair |

When `pairs` is absent from config (legacy), a single BTC pair is synthesized from `execution.spot_symbol`, `execution.futures_symbol`, and `cme_contract_size`.

### Execution Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `false` | Master kill switch — must be `true` (or use `--execute` CLI flag) to activate |
| `auto_trade` | `false` | When `false`, prompts `Execute? (yes/no)` before each trade |
| `dry_run` | `true` | When `true`, logs proposed orders without submitting to IBKR |
| `order_type` | `"limit"` | `"limit"` or `"market"` |
| `limit_offset_pct` | `0.001` | Limit price offset from market (0.1%) — buy above, sell below |
| `max_etf_shares` | `10000` | Safety cap on ETF shares per trade |
| `max_futures_contracts` | `50` | Safety cap on futures contracts per trade |
| `execution_client_id` | `2` | Separate IBKR client ID to avoid conflicts with data fetcher (client_id 1) |

### Execution Safety Layers

| # | Layer | Description |
|---|-------|-------------|
| 1 | `enabled: false` | Master kill switch (default off) |
| 2 | `dry_run: true` | Log orders but don't submit (default on) |
| 3 | `auto_trade: false` | Require interactive confirmation (default) |
| 4 | Position limits | `max_etf_shares` / `max_futures_contracts` caps |
| 5 | Market guards | Weekend check, backwardation guard |
| 6 | Separate client_id | `execution_client_id: 2` avoids IBKR connection conflicts |
| 7 | Execution log | Every event logged to `output/execution/execution_log.jsonl` |
| 8 | Position persistence | `output/execution/position_state_{pair_id}.json` per-pair files survive restarts |
| 9 | Sequential legs | ETF leg first, futures second; abort if ETF fails |
| 10 | Fill timeout | Cancel unfilled orders after 30 seconds |

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
| `output/basis_analysis_{pair_id}_*.txt` | analyze | Per-pair human-readable report |
| `output/basis_analysis_{pair_id}_*.json` | analyze | Per-pair structured market data, returns, signals, risks, positions |
| `output/btc_basis_monitor.log` | monitor | Timestamped monitoring activity |
| `output/alerts.log` | monitor | Trading alerts only (entry/exit/stop signals) |
| `output/basis_history_*.json` | monitor | Time-series of basis data points |
| `output/backtest_result_*.json` | backtest | Trade list, metrics (Sharpe, drawdown, win rate) |
| `output/execution/execution_log.jsonl` | execution | Append-only log of all execution events with `pair_id` (proposed/executed/rejected) |
| `output/execution/position_state_{pair_id}.json` | execution | Per-pair persisted open position state (survives restarts) |

All JSON files use ISO-8601 timestamps and can be imported to Excel/pandas.

## Dependencies

From `requirements.txt`:
- `requests>=2.31.0`: HTTP client for API calls (Coinbase, Binance, Fear & Greed)
- `python-dateutil>=2.8.2`: Date parsing utilities

Optional (for IBKR data fetching and trade execution):
- `ib_insync`: IBKR TWS/Gateway API client. Required only when using `IBKRFetcher`, `IBKRExecutor`, or `execution.enabled`. Lazy-imported so the rest of the toolkit works without it.

Standard library only otherwise (json, dataclasses, enum, datetime, argparse, logging, csv).

## Financial Domain Notes

**This is educational software, not financial advice.** When modifying:
- Preserve risk warnings in output
- Execution is gated behind 10 safety layers (see Execution Safety Layers above). Defaults are: `enabled=false`, `dry_run=true`, `auto_trade=false`
- Maintain transparency in return calculations (show gross vs net, before/after funding)
- Log all signal changes for audit trail (see `BasisMonitor.check_and_alert()`)
- Log all execution events for audit trail (see `output/execution/execution_log.jsonl`)

**Regulatory Context**: Basis trades may have tax implications (short-term capital gains, wash sales). The software does not provide tax guidance.
