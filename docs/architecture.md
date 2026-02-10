# BTC Basis Trade Toolkit - Architecture

This document describes the architecture and module structure of the BTC Basis Trade Toolkit.

## Overview

The toolkit is organized as a Python package (`btc_basis`) with clear separation of concerns:

```
btc/
├── main.py                    # Main CLI entry point
├── setup.py                   # Package installation
├── src/
│   └── btc_basis/
│       ├── core/              # Core business logic
│       ├── data/              # Data fetching
│       ├── backtest/          # Backtesting module
│       ├── monitor/           # Monitoring daemon
│       └── utils/             # Shared utilities
├── config/                    # Configuration files
├── data/                      # Data files
├── docs/                      # Documentation
├── output/                    # Generated outputs
└── tests/                     # Test suite
```

## Module Structure

### Core (`btc_basis.core`)

**models.py** - Data models:
- `Signal` - Trading signal enum (STRONG_ENTRY, STOP_LOSS, etc.)
- `TradeConfig` - Configuration dataclass
- `MarketData` - Market snapshot with computed properties

**analyzer.py** - Main analysis engine:
- `BasisTradeAnalyzer` - Signal generation, risk assessment, position sizing

**calculator.py** - Basis calculations:
- `BasisCalculator` - Static methods for basis metrics

### Data (`btc_basis.data`)

**base.py** - Base fetcher class:
- `BaseFetcher` - Abstract base with logging mixin

**coinbase.py** - Coinbase API:
- `CoinbaseFetcher` - BTC spot prices
- `FearGreedFetcher` - Fear & Greed Index

**binance.py** - Binance API:
- `BinanceFetcher` - Spot and futures prices

**ibkr.py** - Interactive Brokers (consolidated from 5 files):
- `IBKRFetcher` - Unified spot + futures
- `IBKRHistoricalFetcher` - Historical data

**historical.py** - Historical data utilities:
- `RollingDataProcessor` - Contract rolling logic

### Backtest (`btc_basis.backtest`)

**engine.py** - Backtesting engine:
- `Trade` - Single trade representation
- `BacktestResult` - Results with metrics
- `Backtester` - Simulation engine

**costs.py** - Cost calculations:
- `TradingCosts` - Cost breakdown
- `calculate_comprehensive_costs()` - Full cost analysis

### Monitor (`btc_basis.monitor`)

**daemon.py** - Monitoring daemon:
- `BasisMonitor` - Continuous monitoring with alerts

### Utils (`btc_basis.utils`)

**config.py** - Configuration:
- `ConfigLoader` - JSON config loading

**logging.py** - Logging utilities:
- `LoggingMixin` - Windows-safe logging
- `setup_logging()` - Logger setup

**expiry.py** - Futures expiry:
- `get_last_friday_of_month()` - CME expiry calculation
- `generate_expiry_schedule()` - Expiry schedule
- `get_front_month_expiry()` - Front month lookup

**io.py** - Report writing:
- `ReportWriter` - Text and JSON output

## Key Design Patterns

1. **Dataclass-based Configuration** - TradeConfig passed to components
2. **Enum for Signals** - Strongly-typed trading signals
3. **Optional Return Types** - Graceful degradation for API failures
4. **Composition over Inheritance** - Fetcher → MarketData → Analyzer
5. **Mixin Pattern** - LoggingMixin for consistent logging

## Data Flow

```
Config (JSON) → TradeConfig → BasisTradeAnalyzer
                                      ↓
MarketDataFetcher → MarketData → Analyzer.generate_signal() → Signal
                                      ↓
                              Analyzer.assess_risk() → Risk Dict
                                      ↓
                              Analyzer.calculate_position_sizing() → Position Dict
```

## Installation

```bash
# Install package
pip install -e .

# With IBKR support
pip install -e ".[ibkr]"

# With development tools
pip install -e ".[dev]"
```

## Usage

```bash
# Single analysis
python main.py analyze

# Backtest
python main.py backtest --data data/samples/realistic_basis_2024.csv

# Monitor
python main.py monitor --once
python main.py monitor --interval 300
```

## Extending the Toolkit

### Adding a New Exchange

1. Create `btc_basis/data/new_exchange.py`
2. Extend `BaseFetcher`
3. Implement `fetch_spot_price()` and `fetch_futures_price()`
4. Add to `btc_basis/data/__init__.py`

### Adding New Signal Logic

1. Modify `BasisTradeAnalyzer.generate_signal()` in `core/analyzer.py`
2. Add new `Signal` enum values if needed
3. Update tests in `tests/test_analyzer.py`

### Adding New Cost Categories

1. Add fields to `TradingCosts` in `backtest/costs.py`
2. Update `calculate_comprehensive_costs()`
3. Update `Backtester.run_backtest()` if needed
