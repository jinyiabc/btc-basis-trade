# IBKR Integration - Complete Summary

## 📦 What Was Created

### Documentation
- **`ibkr_setup_guide.md`** - Complete IBKR setup walkthrough

### Python Scripts
- **`fetch_futures_ibkr.py`** - Client Portal API (REST-based, easier)
- **`fetch_futures_ibkr_tws.py`** - TWS API (native, faster)

### Configuration
- **`requirements_ibkr.txt`** - Python dependencies

---

## 🎯 Two Methods to Get IBKR Futures Data

| Feature | Client Portal API | TWS API |
|---------|-------------------|---------|
| **Setup File** | `fetch_futures_ibkr.py` | `fetch_futures_ibkr_tws.py` |
| **Requires** | Web Gateway running | TWS/IB Gateway running |
| **Connection** | REST (HTTPS) | Socket (native) |
| **Speed** | Slower (HTTP overhead) | Faster (direct socket) |
| **Ease of Use** | ⭐⭐⭐⭐⭐ Very Easy | ⭐⭐⭐ Moderate |
| **Setup Time** | 10 minutes | 20 minutes |
| **Library** | `requests` (standard) | `ib_insync` (3rd party) |
| **Best For** | Quick integration | High-frequency trading |

---

## 🚀 Quick Start - Client Portal API (Recommended)

### Step 1: Download Gateway
```bash
# Download from:
https://www.interactivebrokers.com/en/trading/ibkr-desktop.php

# Extract to: C:\clientportal.gw
```

### Step 2: Start Gateway
```bash
cd C:\clientportal.gw
bin\run.bat root\conf.yaml

# Wait for: "Client portal gateway started on port 5000"
```

### Step 3: Login
```
Open browser: https://localhost:5000
Login with IBKR credentials
```

### Step 4: Run Python Script
```bash
cd C:\Users\jinyi\btc
python fetch_futures_ibkr.py
```

**Expected Output**:
```
==================================================
IBKR CME BITCOIN FUTURES FETCHER
==================================================

Checking IBKR authentication...
[OK] Authenticated

Searching for BTC futures contract...
Found contract ID: 495512508
Fetching market data...

[*] MARKET DATA
--------------------------------------------------
Spot Price (Coinbase):  $71,199.24
Futures Price (CME):    $71,825.00
Bid:                    $71,800.00
Ask:                    $71,850.00
Spread:                 $50.00

[*] BASIS ANALYSIS
--------------------------------------------------
Basis (Absolute):       $625.76
Basis (Percent):        0.88%

[OK] Success! IBKR futures data fetched
```

---

## 🚀 Quick Start - TWS API (Alternative)

### Step 1: Install TWS or IB Gateway
```bash
# Download from:
https://www.interactivebrokers.com/en/trading/tws.php

# Choose: Standalone version (Windows)
```

### Step 2: Enable API in TWS
```
1. Open TWS
2. File → Global Configuration → API → Settings
3. ✓ Enable ActiveX and Socket Clients
4. ✓ Read-Only API
5. Socket Port: 7497 (paper) or 7496 (live)
6. Trusted IP: 127.0.0.1
7. Apply & OK
```

### Step 3: Install Python Library
```bash
pip install ib-insync
```

### Step 4: Run Script
```bash
python fetch_futures_ibkr_tws.py
```

---

## 💰 Cost Breakdown

| Item | Cost | Details |
|------|------|---------|
| **IBKR Account** | $0 | No monthly fees |
| **Paper Trading** | Free | Virtual money, real data (15min delay) |
| **Delayed Data (15min)** | Free | Good for backtesting |
| **Real-Time CME Data** | $4.50/mo | Non-professional traders |
| **Real-Time CME Data** | $105/mo | Professional traders |
| **API Access** | Free | Included with account |
| **Client Portal Gateway** | Free | Download from IBKR |
| **TWS/IB Gateway** | Free | Download from IBKR |

**Total for Development**: **$0** (paper account + delayed data)
**Total for Live Trading**: **$4.50/month** (real-time CME data)

---

## 🔧 Integration with Your Basis Trade Analyzer

### Replace Estimated Futures with Real IBKR Data

**Current code** (btc_basis_trade_analyzer.py, line ~415):
```python
futures_price = spot_price * 1.02  # ESTIMATED!
```

**New code** (using IBKR):
```python
from fetch_futures_ibkr import fetch_ibkr_spot_and_futures

# Try to get real futures data
ibkr_data = fetch_ibkr_spot_and_futures()

if ibkr_data:
    # Use real CME futures price
    futures_price = ibkr_data['futures_price']
    expiry = ibkr_data.get('expiry_date', datetime.now() + timedelta(days=30))
else:
    # Fallback to estimation
    futures_price = spot_price * 1.02
    expiry = datetime.now() + timedelta(days=30)
```

---

## 📊 Data Quality Comparison

| Source | Exchange | Quality | Latency | Cost |
|--------|----------|---------|---------|------|
| **IBKR Real-Time** | CME | ⭐⭐⭐⭐⭐ Best | <1s | $4.50/mo |
| **IBKR Delayed** | CME | ⭐⭐⭐⭐ Excellent | 15min | Free |
| **Binance Perpetual** | Binance | ⭐⭐⭐ Good | <1s | Free |
| **Estimation (2%)** | None | ⭐ Poor | N/A | Free |

**Recommendation**:
- **Development**: Use IBKR delayed (free, official CME data)
- **Production**: Use IBKR real-time ($4.50/mo)

---

## ⚙️ Account Setup Checklist

### 1. Open IBKR Account
- [ ] Go to https://www.interactivebrokers.com/
- [ ] Click "Open Account"
- [ ] Choose account type (Individual recommended)
- [ ] Complete application (10-20 minutes)
- [ ] Wait for approval (1-2 days)

### 2. Enable Trading Permissions
- [ ] Login to Account Management
- [ ] Settings → Account Settings → Trading Permissions
- [ ] Enable: Futures ✓
- [ ] Enable: US Futures ✓
- [ ] Enable: CME Group ✓
- [ ] Submit and wait for approval

### 3. Market Data Subscription
- [ ] Account Management → Market Data
- [ ] Subscribe to "US Equity and Options Add-On Streaming Bundle" (includes CME)
- [ ] Or just "CME (Chicago Mercantile Exchange)"
- [ ] Choose: Real-time ($4.50/mo) or Delayed (free)

### 4. Enable API
- [ ] For Client Portal: Already enabled
- [ ] For TWS: Global Configuration → API → Enable Socket Clients

### 5. Paper Trading (Optional but Recommended)
- [ ] Account Management → Settings → Paper Trading Account
- [ ] Request paper trading account
- [ ] Use for testing without risking real money

---

## 🐛 Troubleshooting

### "Not authenticated"
**Solution**:
1. Open browser: https://localhost:5000
2. Login with IBKR credentials
3. Leave browser tab open

### "Contract not found"
**Solution**:
1. Check futures permissions enabled
2. Verify CME data subscription active
3. Wait 24 hours after enabling permissions

### "Connection refused"
**Solution**:
1. Check Gateway/TWS is running
2. Verify port number (5000 for Gateway, 7497 for TWS)
3. Check firewall allows localhost connections

### "No market data"
**Solution**:
1. Market may be closed (CME hours: Sun 6PM - Fri 5PM ET)
2. Subscribe to market data (delayed is free)
3. Wait for data subscription to activate (24 hours)

---

## 📚 Resources

### Official IBKR Documentation
- API Overview: https://www.interactivebrokers.com/api/doc.html
- Client Portal: https://www.interactivebrokers.com/api/doc.html#tag/Market-Data
- TWS API: https://interactivebrokers.github.io/tws-api/

### Python Libraries
- ib_insync docs: https://ib-insync.readthedocs.io/
- ib_insync GitHub: https://github.com/erdewit/ib_insync

### Community Support
- IBKR API Forum: https://groups.io/g/twsapi
- Reddit: r/interactivebrokers
- Stack Overflow: [ibkr-api] tag

### Trading Hours
- CME Bitcoin Futures: Sun 6PM - Fri 5PM ET (23 hours/day)
- Maintenance: Daily 5PM-6PM ET

---

## 🎯 Next Steps

1. **Setup IBKR Account** (if you don't have one)
   - Open account
   - Enable futures permissions
   - Subscribe to market data (delayed = free)

2. **Choose Your Method**
   - Client Portal API: Easier, good for most uses
   - TWS API: Faster, better for high-frequency

3. **Test Connection**
   ```bash
   python fetch_futures_ibkr.py
   # or
   python fetch_futures_ibkr_tws.py
   ```

4. **Integrate into Analyzer**
   - Replace estimated futures with real IBKR data
   - Test with paper account first
   - Deploy to production

---

## ✅ Success Criteria

You'll know it's working when you see:

```
[OK] Authenticated
[OK] Found contract ID: 495512508
[OK] Futures Price: $71,825.00
[OK] Basis: 0.88%
```

Then you'll have **real CME Bitcoin futures prices** in your basis trade analyzer! 🎉

