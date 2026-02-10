# Bitcoin Basis Trade Analysis Toolkit

A comprehensive Python toolkit for analyzing and monitoring Bitcoin cash-and-carry arbitrage (basis trade) opportunities. This market-neutral strategy captures the spread between Bitcoin spot and futures prices.

## Features

- **Real-time basis calculation** - Analyzes spot vs futures spread
- **Automated signal generation** - Entry, exit, and stop-loss signals
- **Risk assessment** - Evaluates funding, basis, liquidity, and crowding risks
- **Position sizing** - Calculates ETF shares and CME futures contracts needed
- **Backtesting engine** - Test strategy on historical data
- **Continuous monitoring** - Background daemon for alert generation
- **IBKR integration** - Real CME futures data via Interactive Brokers
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

Run a one-time analysis with current market data:

```bash
source .venv/bin/activate
python main.py analyze
```

Output:
- Console report with full analysis
- `output/analysis/btc_basis_analysis_*.txt` - Text report
- `output/analysis/btc_basis_analysis_*.json` - JSON data export

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

Run continuous monitoring with alerts:

```bash
# Check every 5 minutes (300 seconds)
python main.py monitor --interval 300

# Run once and exit
python main.py monitor --once

# Use custom config file
python main.py monitor --config config/config.json
```

### Interactive CLI

```bash
python main.py cli
```

## Configuration

Create `config/config.json` (copy from `config/config.example.json`):

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
  }
}
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `account_size` | $200,000 | Total capital allocated to strategy |
| `spot_target_pct` | 0.50 | Percentage allocated to spot ETF (50%) |
| `futures_target_pct` | 0.50 | Percentage allocated to futures (50%) |
| `funding_cost_annual` | 0.05 | Annual funding cost (SOFR + spread, 5%) |
| `leverage` | 1.0 | Leverage multiplier (1x = no leverage) |
| `cme_contract_size` | 5.0 | BTC per CME contract (5 BTC standard) |
| `min_monthly_basis` | 0.005 | Minimum monthly basis for entry (0.5%) |

## Trading Signals

The analyzer generates the following signals:

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

[*] POSITION SIZING (Account: $200,000)
----------------------------------------------------------------------
ETF Shares (IBIT):    1,869 shares
ETF Value:            $100,000.00
CME Futures Contracts: 1 contract(s)
Futures BTC Amount:   5.00 BTC
Futures Notional:     $475,000.00
Total Exposure:       $575,000.00
Delta Neutral:        [OK] Yes

[!]  RISK ASSESSMENT
----------------------------------------------------------------------
Funding              [OK] MODERATE - Normal funding environment
Basis                [OK] LOW - Positive contango
Liquidity            [OK] LOW - ETF tracking NAV closely
Crowding             [OK] LOW - Healthy OI levels
Operational          [OK] LOW - Sufficient time to expiry

Overall Risk Level:   LOW
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
│   │   ├── models.py            # Signal, TradeConfig, MarketData
│   │   ├── analyzer.py          # BasisTradeAnalyzer
│   │   └── calculator.py        # BasisCalculator
│   ├── data/                    # Data fetchers
│   │   ├── coinbase.py          # Coinbase spot prices
│   │   ├── binance.py           # Binance spot/futures
│   │   ├── ibkr.py              # IBKR unified fetcher
│   │   └── historical.py        # Historical data utils
│   ├── backtest/                # Backtesting
│   │   ├── engine.py            # Backtester
│   │   └── costs.py             # Trading costs
│   ├── monitor/                 # Monitoring
│   │   └── daemon.py            # BasisMonitor
│   └── utils/                   # Utilities
│       ├── config.py            # ConfigLoader
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
│   └── test_backtest.py
│
└── output/                      # Generated files (gitignored)
    ├── analysis/                # Analysis reports
    ├── backtests/               # Backtest results
    └── logs/                    # Log files
```

## Return Calculation

The annualized return formula:

```
Gross Annualized = (Futures - Spot) / Spot × (365 / Days to Expiry)
Net Annualized = Gross Annualized - Funding Cost
Leveraged Return = Net Annualized × Leverage
```

Example:
- Spot: $95,000
- Futures (30-day): $97,200
- Basis: $2,200 (2.32%)
- Gross Annualized: 2.32% × (365/30) = 28.18%
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
from btc_basis.core.models import MarketData, TradeConfig
from btc_basis.core.analyzer import BasisTradeAnalyzer
from datetime import datetime, timedelta

# Create custom market data
market = MarketData(
    spot_price=95000,
    futures_price=97200,
    futures_expiry_date=datetime.now() + timedelta(days=30),
    etf_price=53.50,
    fear_greed_index=0.75
)

# Analyze
config = TradeConfig(account_size=200000)
analyzer = BasisTradeAnalyzer(config)
report = analyzer.generate_report(market)
print(report)
```

### IBKR Integration

```python
from btc_basis.data.ibkr import IBKRFetcher

# Connect and fetch data
fetcher = IBKRFetcher()
if fetcher.connect():
    data = fetcher.get_complete_basis_data(expiry="202603")
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
| IBKR | CME futures + ETF prices | Integrated |
| Alternative.me | Fear & Greed Index | Integrated |

## Monitoring & Alerts

The monitor script generates alerts for:

- Stop-loss conditions (basis negative or compressed)
- Full exit signals (peak basis >3.5%)
- Partial exit signals (elevated basis >2.5%)
- Entry signals (favorable basis >1.0%)
- Risk warnings (funding spike, ETF discount, etc.)

Alerts are written to `output/logs/alerts.log`.

## Disclaimer

**This software is for educational and analytical purposes only. It is NOT financial advice.**

- Basis trades carry real risks including funding spikes, basis collapse, and liquidity crises
- Past basis levels do not guarantee future returns
- Users should consult qualified financial professionals before trading
- The authors assume no liability for trading losses

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Areas for improvement:

- [x] Backtesting engine with historical data
- [x] IBKR integration for real CME data
- [x] Multi-exchange support (Binance, IBKR)
- [ ] Web dashboard for monitoring
- [ ] Email/SMS alert notifications
- [ ] Risk analytics (VaR, CVaR, stress testing)
- [ ] Portfolio optimization across multiple basis trades

## Support

For issues, questions, or feature requests, please open a GitHub issue.

---

**Built for Bitcoin Basis Trade Analysis**
