# Multi-Asset Basis Trade Analysis Toolkit

A comprehensive Python toolkit for analyzing and monitoring cash-and-carry arbitrage (basis trade) opportunities across multiple asset classes. Supports Bitcoin, Ethereum, Oil, Gold, Silver, and more — each with their own spot ETF + futures pair. This market-neutral strategy captures the spread between spot prices and futures prices.

## Features

- **Multi-asset support** - Configure multiple spot+futures pairs (BTC, ETH, Oil, Gold, Silver)
- **Real-time basis calculation** - Analyzes spot vs futures spread per pair
- **Automated signal generation** - Entry, exit, and stop-loss signals
- **Risk assessment** - Evaluates funding, basis, liquidity, and crowding risks
- **Position sizing** - Calculates ETF shares and futures contracts per pair allocation
- **Trade execution** - Execute basis trades via IBKR with 10 safety layers
- **Per-pair position tracking** - Independent position state for each pair
- **Backtesting engine** - Test strategy on historical data
- **Continuous monitoring** - Background daemon with per-pair alerts
- **IBKR integration** - Real futures data from CME, NYMEX, COMEX and trade execution
- **Multi-exchange support** - Coinbase, Binance, IBKR data sources
- **Data export** - JSON and text report generation

## Installation

```bash
# Clone the repository
git clone https://github.com/jinyiabc/btc-basis-trade.git
cd btc-basis-trade

# Install package
pip install -e .

# With IBKR support
pip install -e ".[ibkr]"

# With development tools
pip install -e ".[dev]"
```

## Quick Start

### Single Analysis

Run a one-time analysis for all configured pairs:

```bash
source .venv/bin/activate

# Analyze all pairs
python main.py analyze

# Analyze a single pair
python main.py analyze --pair BTC
python main.py analyze --pair ETH
python main.py analyze --pair OIL
python main.py analyze --pair GOLD
python main.py analyze --pair SILVER
```

Output per pair:
- Console report with full analysis
- `output/basis_analysis_{pair_id}_*.txt` - Text report
- `output/basis_analysis_{pair_id}_*.json` - JSON data export

### Backtesting

Test strategy on historical data:

```bash
# With sample data
python main.py backtest

# With custom CSV file
python main.py backtest --data data/samples/realistic_basis_2024.csv

# With date range
python main.py backtest --start 2024-01-01 --end 2024-12-31
```

### Continuous Monitoring

Run continuous monitoring with alerts for all pairs:

```bash
# Check every 5 minutes (300 seconds), all pairs
python main.py monitor --interval 300

# Monitor a single pair
python main.py monitor --pair ETH --interval 300

# Run once and exit
python main.py monitor --once

# Use custom config file
python main.py monitor --config config/config.json
```

### Trade Execution

Execute basis trades through IBKR when signals fire. Execution is disabled by default and protected by multiple safety layers.

```bash
# Dry-run mode: log proposed orders without submitting (safe to test)
python main.py monitor --execute --dry-run --once

# Dry-run with auto-trade (no confirmation prompts)
python main.py monitor --execute --dry-run --auto-trade --interval 300

# Dry-run for a single pair
python main.py monitor --execute --dry-run --pair BTC --once

# Live execution with manual confirmation (prompts before each trade)
python main.py monitor --execute --once

# Live execution with auto-trade (requires IBKR TWS/Gateway running)
python main.py monitor --execute --auto-trade --interval 300
```

**Safety layers** (all on by default):

| # | Layer | Default |
|---|-------|---------|
| 1 | Master kill switch (`enabled`) | Off |
| 2 | Dry-run mode (`dry_run`) | On |
| 3 | Manual confirmation (`auto_trade`) | Off (prompts before each trade) |
| 4 | Position limits | 10,000 ETF shares / 50 futures contracts |
| 5 | Market guards | Weekend check, backwardation guard |
| 6 | Separate IBKR client ID | Avoids connection conflicts with data fetcher |
| 7 | Execution audit log | Every event logged to JSONL with pair_id |
| 8 | Per-pair position persistence | Survives restarts |
| 9 | Sequential leg execution | Aborts futures if ETF leg fails |
| 10 | Fill timeout | Cancels unfilled orders after 30s |

### Interactive CLI

```bash
python main.py cli
```

## Configuration

Create `config/config.json` (copy from `config_example.json`):

```json
{
  "account_size": 200000,
  "spot_target_pct": 0.50,
  "futures_target_pct": 0.50,
  "funding_cost_annual": 0.05,
  "leverage": 1.0,
  "cme_contract_size": 5.0,
  "min_monthly_basis": 0.005,
  "alert_thresholds": {
    "stop_loss_basis": 0.002,
    "partial_exit_basis": 0.025,
    "full_exit_basis": 0.035,
    "strong_entry_basis": 0.01,
    "min_entry_basis": 0.005
  },
  "ibkr": {
    "host": "127.0.0.1",
    "port": 7497,
    "client_id": 1,
    "timeout": 10
  },
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
    },
    {
      "pair_id": "OIL",
      "spot_symbol": "USO",
      "futures_symbol": "MCL",
      "futures_exchange": "NYMEX",
      "contract_size": 100,
      "tick_size": 0.01,
      "allocation_pct": 0.15
    },
    {
      "pair_id": "GOLD",
      "spot_symbol": "GLD",
      "futures_symbol": "MGC",
      "futures_exchange": "COMEX",
      "contract_size": 10,
      "tick_size": 0.10,
      "allocation_pct": 0.15
    },
    {
      "pair_id": "SILVER",
      "spot_symbol": "SLV",
      "futures_symbol": "SIL",
      "futures_exchange": "COMEX",
      "contract_size": 1000,
      "tick_size": 0.005,
      "allocation_pct": 0.10
    }
  ]
}
```

### Global Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `account_size` | $200,000 | Total capital allocated to strategy |
| `spot_target_pct` | 0.50 | Percentage allocated to spot ETF (50%) |
| `futures_target_pct` | 0.50 | Percentage allocated to futures (50%) |
| `funding_cost_annual` | 0.05 | Annual funding cost (SOFR + spread, 5%) |
| `leverage` | 1.0 | Leverage multiplier (1x = no leverage) |
| `min_monthly_basis` | 0.005 | Minimum monthly basis for entry (0.5%) |

### Pair Parameters

Each entry in the `pairs` array configures a spot+futures trading pair:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pair_id` | `"BTC"` | Unique identifier for the pair |
| `spot_symbol` | `"IBIT"` | ETF symbol for the spot leg |
| `futures_symbol` | `"MBT"` | Futures contract symbol |
| `futures_exchange` | `"CME"` | Futures exchange (`CME`, `NYMEX`, `COMEX`) |
| `contract_size` | `0.1` | Futures contract size in underlying units |
| `tick_size` | `5.0` | Minimum price increment for limit orders |
| `allocation_pct` | `1.0` | Fraction of `account_size` allocated to this pair |
| `enabled` | `true` | Whether this pair is active |

**Note**: `allocation_pct` across all pairs should sum to 1.0 for full capital utilization.

**Backward compatibility**: When `pairs` is absent from config, a single BTC pair is automatically synthesized from legacy `execution.spot_symbol`, `execution.futures_symbol`, and `cme_contract_size` fields.

### Execution Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | `false` | Master kill switch for execution |
| `auto_trade` | `false` | Skip manual confirmation prompts |
| `dry_run` | `true` | Log proposed orders without submitting to IBKR |
| `order_type` | `"limit"` | Order type: `"limit"` or `"market"` |
| `limit_offset_pct` | `0.001` | Limit price offset from market (0.1%) |
| `max_etf_shares` | `10000` | Safety cap on ETF shares per trade |
| `max_futures_contracts` | `50` | Safety cap on futures contracts per trade |
| `execution_client_id` | `2` | Separate IBKR client ID (avoids conflicts with data fetcher) |

## Trading Signals

The analyzer generates the following signals (shared across all pairs):

| Signal | Condition | Action |
|--------|-----------|--------|
| **STRONG_ENTRY** | Monthly basis > 1.0% | Enter position |
| **ACCEPTABLE_ENTRY** | Monthly basis 0.5-1.0% | Consider entry if funding low |
| **NO_ENTRY** | Monthly basis < 0.5% | Do not enter |
| **PARTIAL_EXIT** | Monthly basis > 2.5% | Close 50% of position |
| **FULL_EXIT** | Monthly basis > 3.5% | Close 100% of position |
| **STOP_LOSS** | Basis negative or < 0.2% | Exit immediately |

## Example Output

```
============================================================
  [BTC] IBIT / MBT
  Allocation: 40% ($80,000)
============================================================
======================================================================
BITCOIN BASIS TRADE ANALYSIS
======================================================================

[*] MARKET DATA
----------------------------------------------------------------------
Spot Price:           $95,000.00
Futures Price:        $97,200.00
Futures Expiry:       2026-03-08 (30 days)
ETF Price (IBIT):     $53.50
Fear & Greed Index:   0.75

[*] BASIS ANALYSIS
----------------------------------------------------------------------
Basis (Absolute):     $2,200.00
Basis (Percent):      2.32%
Monthly Basis:        2.32%

[*] RETURN CALCULATIONS
----------------------------------------------------------------------
Gross Annualized:     28.18%
Funding Cost:         5.00% (annualized)
Net Annualized:       23.18%

[*] TRADING SIGNAL
----------------------------------------------------------------------
Signal:  [~] PARTIAL_EXIT
Reason:  Elevated basis (>2.5% monthly) - partial exit
```

## Project Structure

```
btc-basis-trade/
├── main.py                      # Main CLI entry point
├── setup.py                     # Package installation
├── requirements.txt             # Python dependencies
│
├── config/
│   ├── config.json              # Your configuration (gitignored)
│   └── config.example.json      # Example configuration
│
├── src/btc_basis/               # Main package
│   ├── core/                    # Core business logic
│   │   ├── models.py            # Signal, TradeConfig, PairConfig, MarketData
│   │   ├── analyzer.py          # BasisTradeAnalyzer
│   │   └── calculator.py        # BasisCalculator
│   ├── data/                    # Data fetchers
│   │   ├── coinbase.py          # Coinbase spot prices
│   │   ├── binance.py           # Binance spot/futures
│   │   ├── ibkr.py              # IBKR unified fetcher (CME/NYMEX/COMEX)
│   │   └── historical.py        # Historical data utils
│   ├── execution/               # Trade execution via IBKR
│   │   ├── models.py            # ExecutionConfig, OrderRequest, OrderResult
│   │   ├── position.py          # Per-pair position tracking (persisted to disk)
│   │   ├── executor.py          # IBKRExecutor (order placement)
│   │   └── manager.py           # ExecutionManager (signal-to-trade bridge, per-pair)
│   ├── backtest/                # Backtesting
│   │   ├── engine.py            # Backtester
│   │   └── costs.py             # Trading costs
│   ├── monitor/                 # Monitoring
│   │   └── daemon.py            # BasisMonitor (multi-pair loop, triggers execution)
│   └── utils/                   # Utilities
│       ├── config.py            # ConfigLoader (with get_pairs())
│       ├── logging.py           # LoggingMixin
│       ├── expiry.py            # Futures expiry utils
│       └── io.py                # ReportWriter
│
├── data/
│   └── samples/                 # Sample CSV files for backtesting
│
├── docs/
│   ├── quickstart.md
│   ├── architecture.md
│   └── ibkr/setup.md            # IBKR setup guide
│
├── tests/                       # Test suite
│   ├── test_analyzer.py
│   ├── test_backtest.py
│   └── test_execution.py
│
└── output/                      # Generated files (gitignored)
    ├── analysis/                # Per-pair analysis reports
    ├── backtests/               # Backtest results
    ├── execution/               # Execution logs and per-pair position state
    └── logs/                    # Log files
```

## Return Calculation

The annualized return formula:

```
Gross Annualized = (Futures - Spot) / Spot x (365 / Days to Expiry)
Net Annualized = Gross Annualized - Funding Cost
Leveraged Return = Net Annualized x Leverage
```

Example:
- Spot: $95,000
- Futures (30-day): $97,200
- Basis: $2,200 (2.32%)
- Gross Annualized: 2.32% x (365/30) = 28.18%
- Funding: 5.00%
- **Net Annualized: 23.18%**

## Risk Factors

### 1. Funding Risk
Borrowing costs (repo rates) can spike during market stress, turning positive carry negative.

**Mitigation**: Monitor SOFR rates; exit if funding > basis.

### 2. Basis Risk
Market can flip to backwardation (futures < spot), causing losses.

**Mitigation**: Stop-loss at basis < 0.2% monthly; exit on backwardation.

### 3. Liquidity Risk
ETF discount, futures slippage, or forced liquidation during volatility spikes.

**Mitigation**: Monitor ETF NAV tracking; avoid entry near high-volatility events.

### 4. Crowding Risk
Over-crowded trades compress basis; CME open interest is a proxy.

**Mitigation**: Avoid entry when CME OI > 40k contracts.

### 5. Operational Risk
Rollover periods may compress basis; futures settlement logistics.

**Mitigation**: Plan rollovers in advance; monitor basis curve.

## Advanced Usage

### Custom Market Data

```python
from btc_basis.core.models import MarketData, TradeConfig, PairConfig, make_pair_trade_config
from btc_basis.core.analyzer import BasisTradeAnalyzer
from datetime import datetime, timedelta

# Create custom market data
market = MarketData(
    spot_price=95000,
    futures_price=97200,
    futures_expiry_date=datetime.now() + timedelta(days=30),
    etf_price=53.50,
    fear_greed_index=0.75,
    pair_id="BTC"
)

# Analyze with pair-specific config
pair = PairConfig(pair_id="BTC", allocation_pct=0.4, contract_size=0.1)
global_config = TradeConfig(account_size=200000)
pair_config = make_pair_trade_config(global_config, pair)
analyzer = BasisTradeAnalyzer(pair_config)
report = analyzer.generate_report(market)
print(report)
```

### IBKR Integration

```python
from btc_basis.data.ibkr import IBKRFetcher
from btc_basis.core.models import PairConfig

# Connect and fetch data for a specific pair
pair = PairConfig(pair_id="GOLD", spot_symbol="GLD", futures_symbol="MGC",
                  futures_exchange="COMEX", contract_size=10, tick_size=0.10)

fetcher = IBKRFetcher()
if fetcher.connect():
    data = fetcher.get_complete_basis_data(pair=pair)
    if data:
        print(f"Spot: ${data['spot_price']:,.2f}")
        print(f"Futures: ${data['futures_price']:,.2f}")
        print(f"Basis: {data['basis_percent']:.2f}%")
    fetcher.disconnect()
```

### Backtesting with Costs

```python
from btc_basis.backtest.engine import Backtester
from btc_basis.backtest.costs import calculate_comprehensive_costs
from btc_basis.core.models import TradeConfig

config = TradeConfig(account_size=200000)
backtester = Backtester(config)

# Load data and run backtest
data = backtester.load_historical_data("data/samples/realistic_basis_2024.csv")
result = backtester.run_backtest(data, max_holding_days=30)

print(f"Total Return: {result.total_return*100:.2f}%")
print(f"Win Rate: {result.win_rate*100:.1f}%")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
```

## Data Sources

| Source | Data | Status |
|--------|------|--------|
| Coinbase | BTC spot price | Integrated |
| Binance | Spot + Perpetual futures | Integrated |
| IBKR | CME/NYMEX/COMEX futures + ETF prices | Integrated |
| Alternative.me | Fear & Greed Index | Integrated |

## Monitoring & Alerts

The monitor iterates over all configured pairs and generates alerts for:

- Stop-loss conditions (basis negative or compressed)
- Full exit signals (peak basis >3.5%)
- Partial exit signals (elevated basis >2.5%)
- Entry signals (favorable basis >1.0%)
- Risk warnings (funding spike, ETF discount, etc.)

All alerts are prefixed with the pair ID (e.g. `[BTC]`, `[GOLD]`) and written to `output/logs/alerts.log`.

When execution is enabled (`--execute`), alerts also trigger the execution pipeline:

1. Signal is mapped to a trade action (OPEN/CLOSE/REDUCE) based on current per-pair position state
2. Position sizing is calculated from the pair's analyzer (using pair-specific account allocation)
3. Safety checks run (position limits, weekend guard, backwardation guard)
4. If `auto_trade=false`, user is prompted for confirmation
5. Orders are placed sequentially (ETF first, then futures) using pair-specific symbols and exchange
6. All events are logged to `output/execution/execution_log.jsonl` with `pair_id`
7. Position state is persisted per pair to `output/execution/position_state_{pair_id}.json`

## Disclaimer

**This software is for educational and analytical purposes only. It is NOT financial advice.**

- Basis trades carry real risks including funding spikes, basis collapse, and liquidity crises
- Past basis levels do not guarantee future returns
- Trade execution is disabled by default and gated behind multiple safety layers — review all settings carefully before enabling live trading
- Users should consult qualified financial professionals before trading
- The authors assume no liability for trading losses

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Areas for improvement:

- [x] Backtesting engine with historical data
- [x] IBKR integration for real CME data
- [x] Multi-exchange support (Binance, IBKR)
- [x] Trade execution via IBKR with safety layers
- [x] Multi-asset pair support (BTC, ETH, Oil, Gold, Silver)
- [x] Per-pair position tracking and execution
- [ ] Web dashboard for monitoring
- [ ] Email/SMS alert notifications
- [ ] Risk analytics (VaR, CVaR, stress testing)
- [ ] Per-pair backtesting

## Support

For issues, questions, or feature requests, please open a GitHub issue.

---

**Built for Multi-Asset Basis Trade Analysis**
