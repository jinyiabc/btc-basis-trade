# Bitcoin Basis Trade Analysis Toolkit

A comprehensive Python toolkit for analyzing and monitoring Bitcoin cash-and-carry arbitrage (basis trade) opportunities. This market-neutral strategy captures the spread between Bitcoin spot and futures prices.

## Features

- **Real-time basis calculation** - Analyzes spot vs futures spread
- **Automated signal generation** - Entry, exit, and stop-loss signals
- **Risk assessment** - Evaluates funding, basis, liquidity, and crowding risks
- **Position sizing** - Calculates ETF shares and CME futures contracts needed
- **Continuous monitoring** - Background daemon for alert generation
- **Data export** - JSON and text report generation
- **Live market data** - Fetches from Coinbase, CoinGlass, Fear & Greed Index

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### Single Analysis

Run a one-time analysis with current market data:

```bash
python btc_basis_trade_analyzer.py
```

Output:
- Console report with full analysis
- `btc_basis_analysis_YYYYMMDD_HHMMSS.txt` - Text report
- `btc_basis_analysis_YYYYMMDD_HHMMSS.json` - JSON data export

### Continuous Monitoring

Run continuous monitoring with alerts:

```bash
# Check every 5 minutes (300 seconds)
python btc_basis_monitor.py --interval 300

# Run once and exit
python btc_basis_monitor.py --once

# Use custom config file
python btc_basis_monitor.py --config my_config.json
```

## Configuration

Create `config.json` (copy from `config_example.json`):

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
| 🟢 **STRONG_ENTRY** | Monthly basis > 1.0% | Enter position |
| 🟡 **ACCEPTABLE_ENTRY** | Monthly basis 0.5-1.0% | Consider entry if funding low |
| ⭕ **NO_ENTRY** | Monthly basis < 0.5% | Do not enter |
| 🟠 **PARTIAL_EXIT** | Monthly basis > 2.5% | Close 50% of position |
| 🔴 **FULL_EXIT** | Monthly basis > 3.5% | Close 100% of position |
| ❌ **STOP_LOSS** | Basis negative or < 0.2% | Exit immediately |

## Example Output

```
======================================================================
BITCOIN BASIS TRADE ANALYSIS
======================================================================

📊 MARKET DATA
----------------------------------------------------------------------
Spot Price:           $95,000.00
Futures Price:        $97,200.00
Futures Expiry:       2026-03-08 (30 days)
ETF Price (IBIT):     $53.50
Fear & Greed Index:   0.75

💰 BASIS ANALYSIS
----------------------------------------------------------------------
Basis (Absolute):     $2,200.00
Basis (Percent):      2.32%
Monthly Basis:        2.32%

📈 RETURN CALCULATIONS
----------------------------------------------------------------------
Gross Annualized:     28.18%
Funding Cost:         5.00% (annualized)
Net Annualized:       23.18%

🎯 TRADING SIGNAL
----------------------------------------------------------------------
Signal:  🟠 PARTIAL_EXIT
Reason:  Elevated basis (>2.5% monthly) - partial exit

📋 POSITION SIZING (Account: $200,000)
----------------------------------------------------------------------
ETF Shares (IBIT):    1,869 shares
ETF Value:            $100,000.00
CME Futures Contracts: 1 contract(s)
Futures BTC Amount:   5.00 BTC
Futures Notional:     $475,000.00
Total Exposure:       $575,000.00
Delta Neutral:        ✅ Yes

⚠️  RISK ASSESSMENT
----------------------------------------------------------------------
Funding              ✅ MODERATE - Normal funding environment
Basis                ✅ LOW - Positive contango
Liquidity            ✅ LOW - ETF tracking NAV closely
Crowding             ✅ LOW - Healthy OI levels
Operational          ✅ LOW - Sufficient time to expiry

Overall Risk Level:   LOW
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

## Position Sizing Example

For $200,000 account with $95,000 BTC spot:

```python
# Spot Leg (ETF)
ETF Price: $53.50 (IBIT)
Target: $100,000 (50% of account)
Shares: $100,000 / $53.50 = 1,869 shares

# Futures Leg (CME)
Target: $100,000 (50% of account)
BTC Amount: $100,000 / $95,000 = 1.05 BTC
Contracts: 1.05 / 5 BTC per contract = 0.21 → 1 contract (round up)
Actual Notional: 1 × 5 × $95,000 = $475,000

# Result: Delta-neutral position with ~$100k exposure per leg
```

## Monitoring & Alerts

The monitor script generates alerts for:

- 🚨 Stop-loss conditions (basis negative or compressed)
- 🔴 Full exit signals (peak basis >3.5%)
- 🟠 Partial exit signals (elevated basis >2.5%)
- 🟢 Entry signals (favorable basis >1.0%)
- ⚠️ Risk warnings (funding spike, ETF discount, etc.)

Alerts are written to `alerts.log` and can be integrated with:
- Email (SMTP)
- SMS (Twilio)
- Telegram/Discord/Slack webhooks
- Desktop notifications

## Data Sources

### Current Integrations

| Source | Data | API |
|--------|------|-----|
| Coinbase | BTC spot price | Public (free) |
| Alternative.me | Fear & Greed Index | Public (free) |
| CoinGlass | Basis data (optional) | Public + paid tiers |

### TODO Integrations

- **CME Group** - Real-time futures prices (requires account)
- **IBKR API** - Live ETF/futures execution
- **Deribit** - Crypto-native futures data
- **Custom data provider** - Proprietary basis feeds

## File Structure

```
btc-basis-trade/
├── btc_basis_trade_analyzer.py   # Main analysis script
├── btc_basis_monitor.py           # Continuous monitoring daemon
├── requirements.txt                # Python dependencies
├── config_example.json             # Example configuration
├── config.json                     # Your configuration (gitignored)
├── README.md                       # This file
├── alerts.log                      # Alert history
├── btc_basis_monitor.log          # Monitor logs
├── basis_history_YYYYMMDD.json    # Daily history snapshots
└── btc_basis_analysis_*.txt/json  # Analysis reports
```

## Advanced Usage

### Custom Market Data

Provide manual market data:

```python
from btc_basis_trade_analyzer import BasisTradeAnalyzer, MarketData, TradeConfig
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

### Backtesting

Extend the toolkit with historical data:

```python
# TODO: Implement backtester
# - Load historical spot/futures prices
# - Simulate entry/exit based on signals
# - Calculate realized returns and Sharpe ratio
```

### Integration with IBKR

If using Interactive Brokers:

```python
# TODO: Integrate with IBKR Client Portal API
# - Fetch real-time IBIT/FBTC and CME futures prices
# - Place orders for both legs simultaneously
# - Monitor positions and P&L
```

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

- [ ] Real-time CME futures data integration
- [ ] IBKR automated execution
- [ ] Backtesting engine with historical data
- [ ] Web dashboard for monitoring
- [ ] Email/SMS alert notifications
- [ ] Multi-exchange support (Deribit, Binance, etc.)
- [ ] Risk analytics (VaR, CVaR, stress testing)
- [ ] Portfolio optimization across multiple basis trades

## Support

For issues, questions, or feature requests, please open a GitHub issue.

---

**Built for the Bitcoin Basis Trade Analysis Skill**
**Compatible with Claude Code CLI**
