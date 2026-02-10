# Quick Start Guide

## Installation (5 minutes)

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Copy and edit configuration
copy config_example.json config.json
# Edit config.json with your parameters

# 3. Test the analyzer
python btc_basis_trade_analyzer.py
```

## Basic Usage

### Run One-Time Analysis

```bash
python btc_basis_trade_analyzer.py
```

**Output:**
- Console report with current market conditions
- Text file: `btc_basis_analysis_YYYYMMDD_HHMMSS.txt`
- JSON file: `btc_basis_analysis_YYYYMMDD_HHMMSS.json`

### Start Continuous Monitoring

```bash
# Check every 5 minutes
python btc_basis_monitor.py --interval 300
```

**Alerts generated for:**
- Strong entry signals (basis > 1%)
- Stop-loss triggers (basis < 0.2% or negative)
- Take-profit levels (basis > 2.5%)
- Risk warnings (funding spikes, ETF discounts)

**Logs saved to:**
- `btc_basis_monitor.log` - Monitor activity log
- `alerts.log` - Trading alerts only

### Run Backtest

```bash
# Using sample data (2024 full year)
python btc_basis_backtest.py --start 2024-01-01 --end 2024-12-31

# Using your own CSV data
python btc_basis_backtest.py --data your_data.csv
```

**CSV Format:**
```csv
date,spot_price,futures_price,futures_expiry
2024-01-01,42000.00,42850.00,2024-01-31
2024-01-02,42500.00,43360.00,2024-01-31
```

## Configuration Options

Edit `config.json`:

```json
{
  "account_size": 200000,        // Your capital ($)
  "funding_cost_annual": 0.05,   // 5% annual funding cost
  "leverage": 1.0,               // 1x = no leverage
  "min_monthly_basis": 0.005     // 0.5% minimum entry threshold
}
```

## Understanding the Output

### Signal Meanings

| Symbol | Signal | Action |
|--------|--------|--------|
| 🟢 | STRONG_ENTRY | Open position (basis > 1%) |
| 🟡 | ACCEPTABLE_ENTRY | Consider entry (0.5-1%) |
| 🟠 | PARTIAL_EXIT | Take profits (basis > 2.5%) |
| 🔴 | FULL_EXIT | Exit all (basis > 3.5%) |
| ❌ | STOP_LOSS | Exit immediately (basis < 0.2%) |

### Risk Levels

- ✅ **LOW** - Normal conditions
- ⚠️  **MODERATE** - Watch closely
- ❌ **CRITICAL** - Take action

### Example Entry Signal

```
🎯 TRADING SIGNAL
Signal:  🟢 STRONG_ENTRY
Reason:  Strong basis >1.0% monthly

Monthly Basis:        2.32%
Net Annualized:       23.18%
Overall Risk Level:   LOW
```

**What to do:** Consider opening position via:
1. Buy IBIT or FBTC ETF (spot leg)
2. Sell CME BTC futures (short leg)
3. Monitor basis daily

### Example Stop-Loss Signal

```
🎯 TRADING SIGNAL
Signal:  ❌ STOP_LOSS
Reason:  Backwardation detected - basis negative

Monthly Basis:        -0.15%
Overall Risk Level:   HIGH
```

**What to do:** Close position immediately:
1. Sell ETF shares
2. Buy back futures contracts
3. Exit with minimal loss

## Scheduled Monitoring (Windows)

Create a Windows Task Scheduler job:

1. Open Task Scheduler
2. Create Basic Task: "BTC Basis Monitor"
3. Trigger: Daily at startup
4. Action: Start a program
   - Program: `python`
   - Arguments: `C:\Users\jinyi\btc_basis_monitor.py --interval 300`
   - Start in: `C:\Users\jinyi`

## Scheduled Monitoring (Linux/Mac)

Add to crontab:

```bash
# Run monitor continuously (starts at boot)
@reboot cd /path/to/scripts && python btc_basis_monitor.py --interval 300

# Or run once per hour
0 * * * * cd /path/to/scripts && python btc_basis_monitor.py --once
```

## Integrating with Your Workflow

### Export to Excel

The JSON output can be imported into Excel:

1. Open Excel
2. Data > Get Data > From JSON
3. Select `btc_basis_analysis_*.json`
4. Load and analyze

### Alert Notifications

Modify `btc_basis_monitor.py` `send_alert()` function:

**Email alerts:**
```python
import smtplib
from email.message import EmailMessage

def send_alert(self, message: str, data: Dict):
    msg = EmailMessage()
    msg['Subject'] = f'BTC Basis Alert: {data["signal"]}'
    msg['From'] = 'your@email.com'
    msg['To'] = 'recipient@email.com'
    msg.set_content(message)

    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.starttls()
        smtp.login('your@email.com', 'your_password')
        smtp.send_message(msg)
```

**SMS via Twilio:**
```python
from twilio.rest import Client

def send_alert(self, message: str, data: Dict):
    client = Client('ACCOUNT_SID', 'AUTH_TOKEN')
    client.messages.create(
        body=message,
        from_='+1234567890',
        to='+0987654321'
    )
```

## Troubleshooting

### "Failed to fetch spot price"

**Cause:** Network issue or API down

**Fix:** Check internet connection; script will use sample data

### "Module not found: requests"

**Cause:** Dependencies not installed

**Fix:** Run `pip install -r requirements.txt`

### Position sizing seems wrong

**Cause:** Configuration mismatch

**Fix:** Check `config.json`:
- `account_size` should match your capital
- `spot_target_pct` + `futures_target_pct` should equal 1.0

## Next Steps

1. **Customize configuration** - Edit `config.json` for your account
2. **Set up monitoring** - Run continuous monitor in background
3. **Backtest your strategy** - Validate with historical data
4. **Integrate with broker** - Connect to IBKR or your broker API
5. **Enable alerts** - Configure email/SMS notifications

## Support

- Read full README.md for detailed documentation
- Check example outputs in repository
- Review skill documentation in `~/.claude/skills/btc-basis-trade-analysis/`

---

**Happy trading! Remember: This is for educational purposes only.**
