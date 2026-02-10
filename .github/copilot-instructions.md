# Copilot Instructions for BTC Basis Trade Toolkit

## Project Overview

Bitcoin Basis Trade Analysis Toolkit - A market-neutral cash-and-carry arbitrage strategy analyzer that trades the spread between Bitcoin spot and futures prices.

**Core Strategy**: Long spot BTC (ETF) + Short CME futures = delta-neutral position capturing basis (spread convergence).

**Return Formula**: `(Futures Price - Spot Price) / Spot Price × (365 / Days) - Funding Cost`

## Architecture Pattern

The codebase uses **modular composition** with clear separation of concerns:

```
Config JSON → TradeConfig → BasisTradeAnalyzer
                                   ↓
DataFetcher (Coinbase/Binance/IBKR) → MarketData → Analyzer methods
                                                      - generate_signal()
                                                      - assess_risk()
                                                      - calculate_position_sizing()
```

**Key Files**:
- [src/btc_basis/core/models.py](src/btc_basis/core/models.py) - Data models (`Signal`, `TradeConfig`, `MarketData`)
- [src/btc_basis/core/analyzer.py](src/btc_basis/core/analyzer.py) - Business logic (`BasisTradeAnalyzer`)
- [src/btc_basis/core/calculator.py](src/btc_basis/core/calculator.py) - Mathematical calculations (`BasisCalculator`)
- [src/btc_basis/data/](src/btc_basis/data/) - Data fetchers (Coinbase, Binance, IBKR, Historical)
- [main.py](main.py) - CLI entry point with subcommands (analyze, backtest, monitor, cli)

## Critical Workflows

### Running Analysis
```bash
# Single analysis with current market data
python main.py analyze

# Backtesting with sample or custom CSV
python main.py backtest --data data/samples/realistic_basis_2024.csv

# Continuous monitoring daemon
python main.py monitor --interval 300

# Interactive menu
python main.py cli
```

### Testing
```bash
# Run tests
pytest tests/

# Test with output
pytest -v tests/test_analyzer.py
```

### Installation for Development
```bash
pip install -e ".[ibkr,dev]"  # Installs with IBKR and pytest support
```

## Code Patterns & Conventions

### 1. **Signal Thresholds** - Hardcoded in [analyzer.py](src/btc_basis/core/analyzer.py#L64-L85)
- `monthly_basis < 0%` → STOP_LOSS (backwardation)
- `0% ≤ basis < 0.2%` → STOP_LOSS
- `1.0% ≤ basis < 2.5%` → STRONG_ENTRY
- `0.5% ≤ basis < 1.0%` → ACCEPTABLE_ENTRY
- `basis ≥ 3.5%` → FULL_EXIT

These thresholds are the heart of the strategy - modify with caution and test thoroughly.

### 2. **Data Models as Dataclasses**
All configuration and market data use `@dataclass` with `.from_dict()` and `.to_dict()` methods for serialization:
```python
# Load config from JSON
config = TradeConfig.from_dict(config_loader.get_all())

# Create market snapshot
market = MarketData(spot_price=..., futures_price=..., ...)

# Access computed properties
days_to_expiry = market.days_to_expiry
basis_percent = market.basis_percent
```

### 3. **Optional Return Types for Graceful Degradation**
Data fetchers return `Optional[float]` or `Optional[dict]`. When APIs fail, the system falls back to defaults or skips enrichment:
```python
try:
    spot = coinbase.fetch_spot_price()
except Exception:
    spot = None  # Will use fallback in analyzer
```

### 4. **Mixin Pattern for Logging**
Use `LoggingMixin` from [utils/logging.py](src/btc_basis/utils/logging.py) for consistent Windows-safe logging:
```python
from btc_basis.utils.logging import LoggingMixin

class MyFetcher(BaseFetcher, LoggingMixin):
    def fetch(self):
        self.log("info", "Fetching data...")
```

## Data Flow Deep Dives

### Signal Generation ([analyzer.py](src/btc_basis/core/analyzer.py#L47-L90))
1. `MarketData` is created with spot/futures prices and expiry
2. Computed properties (basis_percent, monthly_basis, days_to_expiry) are calculated
3. `generate_signal()` compares `market.monthly_basis` against hardcoded thresholds
4. Returns `(Signal enum, reason_string)` tuple

### Backtesting ([backtest/engine.py](src/btc_basis/backtest/engine.py))
1. `Backtester` iterates CSV rows of historical prices
2. For each row, creates `MarketData` and calls `analyzer.generate_signal()`
3. Tracks `Trade` objects with entry/exit prices, fees, PnL
4. Computes aggregate `BacktestResult` with metrics (Sharpe, max_drawdown, etc.)

### Monitoring ([monitor/daemon.py](src/btc_basis/monitor/daemon.py))
1. `BasisMonitor` runs in infinite loop at `--interval` seconds
2. Fetches live data, generates signal, writes to `btc_basis_monitor.log` and `alerts.log`
3. Outputs JSON snapshots to `output/logs/basis_history_YYYYMMDD.json`

## Configuration

**Single source of truth**: [config/config.json](config/config.json) (copied from [config/config.example.json](config/config.example.json))

Key parameters:
- `account_size` - Capital deployed (e.g., $200,000)
- `spot_target_pct`, `futures_target_pct` - Allocation split (typically 50/50)
- `funding_cost_annual` - Expected annual funding cost (e.g., 0.05 = 5%)
- `cme_contract_size` - BTC per CME contract (standard = 5.0)
- `min_monthly_basis` - Minimum entry threshold (e.g., 0.005 = 0.5%)

Configuration is loaded as `TradeConfig` and passed to all components via constructor injection.

## Extension Points

### Add a New Data Source
1. Create [src/btc_basis/data/new_exchange.py](src/btc_basis/data/new_exchange.py)
2. Extend `BaseFetcher` with `fetch_spot_price()`, `fetch_futures_price()` methods
3. Register in [src/btc_basis/data/__init__.py](src/btc_basis/data/__init__.py)
4. Use in [main.py](main.py#L60-L85) alongside existing fetchers

### Modify Signal Logic
Edit thresholds in [analyzer.py](src/btc_basis/core/analyzer.py#L64-L85) and add unit tests in [tests/test_analyzer.py](tests/test_analyzer.py).

### Enhance Position Sizing
Extend `calculate_position_sizing()` in [analyzer.py](src/btc_basis/core/analyzer.py#L100-L140) and test with [tests/test_analyzer.py](tests/test_analyzer.py).

## Testing Fixtures

Pytest provides shared fixtures in [conftest.py](tests/conftest.py):
- `trade_config` - Default TradeConfig instance
- `sample_market_data` - MarketData with realistic spot/futures/expiry
- `analyzer` - BasisTradeAnalyzer instance
- `backtester` - Backtester instance

Use in tests: `def test_signal(analyzer, sample_market_data):`

## Common Gotchas

1. **Expiry Calculation** - CME futures expire on the 3rd Friday of the month. See [utils/expiry.py](src/btc_basis/utils/expiry.py) for helpers.
2. **Monthly Basis** - Not the same as basis_percent; monthly_basis normalizes to 30-day holding period.
3. **Funding Cost** - Annual funding cost is deducted from gross basis in signal generation.
4. **API Failures** - All fetchers gracefully degrade; use fallback sample data or skip enrichment.
5. **Days to Expiry = 0** - Returns (0, "Expiry today") to avoid division by zero in returns calculation.

## Debugging Tips

- Check [output/logs/](output/logs/) for monitor logs
- Review [output/analysis/](output/analysis/) JSON exports for data snapshots
- Run `pytest -v` to see individual test results
- Use `python main.py analyze --once` to get single snapshot
- Enable verbose logging by modifying [utils/logging.py](src/btc_basis/utils/logging.py)
