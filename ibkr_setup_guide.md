# Interactive Brokers (IBKR) API Setup Guide

Complete guide to get Bitcoin futures prices from IBKR (CME BTC futures).

## Why IBKR?

- ✅ **Real CME futures data** (official exchange)
- ✅ **Free with account** (no additional data fees for delayed data)
- ✅ **Can execute trades** (not just data)
- ✅ **Professional grade** (used by hedge funds)
- ✅ **Multiple APIs** (TWS API, Client Portal API, Web API)

---

## Prerequisites

### 1. IBKR Account
- Open account at: https://www.interactivebrokers.com/
- Fund with minimum: $0 (paper trading) or $10,000+ (live)
- Enable **futures trading** permissions

### 2. Market Data Subscription
- **Free delayed data** (15-minute delay) - Good for backtesting
- **Real-time CME data** - $4.50/month for non-professionals
  - Subscribe at: Account Management → Market Data Subscriptions
  - Add: CME (Chicago Mercantile Exchange)

### 3. Choose Your API

| API | Best For | Requires | Setup Time |
|-----|----------|----------|------------|
| **Client Portal API** | Python scripts, automation | Web browser | 15 min |
| **TWS API** | Advanced trading, fastest | TWS/IB Gateway running | 30 min |
| **Web API** | Simple REST calls | Just browser | 10 min |

**Recommendation**: Start with **Client Portal API** (easiest)

---

## Option 1: Client Portal API (Recommended)

### Step 1: Download Client Portal Gateway

```bash
# Download from IBKR
https://www.interactivebrokers.com/en/trading/ibkr-desktop.php

# Or direct link
https://download2.interactivebrokers.com/portal/clientportal.gw.zip
```

### Step 2: Extract and Start

```bash
# Windows
cd C:\clientportal.gw
bin\run.bat root\conf.yaml

# Wait for: "Client portal gateway started on port 5000"
```

### Step 3: Authenticate in Browser

```
1. Open browser: https://localhost:5000
2. Login with IBKR credentials
3. Accept SSL warning (self-signed cert)
4. You'll see: "Client Portal Gateway"
```

### Step 4: Test Connection

```bash
# Test authentication
curl https://localhost:5000/v1/api/iserver/auth/status -k

# Expected response:
# {"authenticated":true,"competing":false,"connected":true}
```

---

## Python Integration

Install required packages:
```bash
pip install requests urllib3
```

---

## Complete Python Implementation

See: `fetch_futures_ibkr.py`

Key features:
- Auto-connects to Client Portal Gateway
- Fetches CME Bitcoin futures (BTC, MBT symbols)
- Gets real-time or delayed prices
- Calculates basis vs spot
- Error handling and retries

---

## Option 2: TWS API (Advanced)

### Requirements
- Install TWS or IB Gateway
- Install Python library: `pip install ib_insync`

### Advantages
- Faster (native socket connection)
- More features (streaming data, order execution)
- Better for high-frequency strategies

### Setup

```python
from ib_insync import IB, Future

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)  # TWS
# or
ib.connect('127.0.0.1', 4001, clientId=1)  # IB Gateway

# Get BTC futures contract
btc = Future('BTC', '20260327', 'CME')  # March 2026 expiry
ib.qualifyContracts(btc)

# Get market data
ticker = ib.reqMktData(btc)
ib.sleep(2)  # Wait for data

print(f"Last price: {ticker.last}")
print(f"Bid: {ticker.bid}, Ask: {ticker.ask}")

ib.disconnect()
```

---

## Security Notes

⚠️ **Important Security Considerations**:

1. **SSL Certificates**: Client Portal uses self-signed certs
   - Safe for local use
   - Disable SSL verification in code: `verify=False`

2. **Firewall**: Only allow localhost (127.0.0.1)
   - Don't expose port 5000 to internet

3. **API Keys**: IBKR doesn't use API keys
   - Authentication via web login
   - Session expires after inactivity

4. **Paper Trading**: Test with paper account first
   - Account Management → Trade → Paper Trading

---

## Troubleshooting

### "Could not connect to Gateway"
- Check if Gateway is running: `netstat -an | findstr 5000`
- Restart Gateway
- Check firewall settings

### "Not authenticated"
- Login via browser: https://localhost:5000
- Check session hasn't expired
- Re-authenticate if needed

### "No market data permissions"
- Check Account Management → Settings → Market Data
- Subscribe to CME data
- Wait 24 hours for activation

### "Contract not found"
- Verify symbol: BTC (standard) or MBT (micro)
- Check expiry date format: YYYYMMDD
- Ensure futures permissions enabled

---

## Cost Summary

| Item | Cost | Notes |
|------|------|-------|
| IBKR Account | $0 | No monthly fee |
| Paper Trading | Free | Unlimited virtual money |
| Delayed Data | Free | 15-minute delay |
| Real-time CME | $4.50/mo | Non-professional |
| Real-time CME | $105/mo | Professional |
| API Access | Free | Included with account |

**Total for development**: **$0** (paper trading + delayed data)
**Total for live trading**: **$4.50/mo** (live account + real-time)

---

## Next Steps

1. Open IBKR account (if you don't have one)
2. Enable paper trading
3. Download Client Portal Gateway
4. Run `fetch_futures_ibkr.py`
5. Integrate into your basis trade analyzer

---

## Resources

- IBKR API Docs: https://www.interactivebrokers.com/api/doc.html
- Client Portal API: https://www.interactivebrokers.com/api/doc.html#tag/Market-Data
- TWS API: https://interactivebrokers.github.io/tws-api/
- ib_insync library: https://ib-insync.readthedocs.io/
- IBKR Campus (tutorials): https://www.ibkr.com/campus/

---

## Support

- IBKR Support: https://www.interactivebrokers.com/en/support/contact.php
- API Forum: https://groups.io/g/twsapi
- Discord: IBKR API community

