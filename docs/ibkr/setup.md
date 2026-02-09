# IBKR (Interactive Brokers) Setup Guide

This guide explains how to set up Interactive Brokers for real-time CME Bitcoin futures data.

## Prerequisites

1. **IBKR Account** - Either live or paper trading account
2. **TWS or IB Gateway** - Desktop application running
3. **Market Data Subscription** - CME Bitcoin futures data

## Installation

```bash
pip install ib-insync
```

Or install with the package:
```bash
pip install -e ".[ibkr]"
```

## TWS/Gateway Configuration

### Port Configuration

| Application | Port | Description |
|-------------|------|-------------|
| TWS Paper | 7497 | Paper trading via TWS |
| TWS Live | 7496 | Live trading via TWS |
| Gateway Paper | 4002 | Paper trading via IB Gateway |
| Gateway Live | 4001 | Live trading via IB Gateway |

### API Settings in TWS

1. Open TWS → Edit → Global Configuration
2. Go to API → Settings
3. Enable "Enable ActiveX and Socket Clients"
4. Set "Socket port" (default: 7497 for paper)
5. Uncheck "Read-Only API" if you need to trade
6. Add "127.0.0.1" to Trusted IPs

### Security Warning

Keep socket ports firewalled from external access. Only localhost should connect.

## Usage

### Basic Connection

```python
from btc_basis.data.ibkr import IBKRFetcher

# Auto-detect port
fetcher = IBKRFetcher()
if fetcher.connect():
    print("Connected!")

    # Get complete basis data
    data = fetcher.get_complete_basis_data(expiry="202603")
    print(f"Spot: ${data['spot_price']:,.2f}")
    print(f"Futures: ${data['futures_price']:,.2f}")
    print(f"Basis: {data['basis_percent']:.2f}%")

    fetcher.disconnect()
```

### Specific Port

```python
fetcher = IBKRFetcher(port=7497)  # Paper trading
fetcher.connect()
```

### Historical Data

```python
from btc_basis.data.ibkr import IBKRHistoricalFetcher
from datetime import datetime, timedelta

fetcher = IBKRHistoricalFetcher(client_id=2)
if fetcher.connect():
    # Get historical spot prices
    spot_data = fetcher.get_historical_spot(
        symbol="IBIT",
        start_date=datetime.now() - timedelta(days=90),
        end_date=datetime.now(),
    )

    # Create backtest CSV
    fetcher.create_backtest_csv(
        output_file="backtest_data.csv",
        start_date=datetime(2024, 1, 1),
        end_date=datetime.now(),
        futures_contracts=["202602", "202603", "202604"],
    )

    fetcher.disconnect()
```

## Contracts

### CME Bitcoin Futures

| Symbol | Description | Contract Size |
|--------|-------------|---------------|
| BTC | Standard Bitcoin | 5 BTC |
| MBT | Micro Bitcoin | 0.1 BTC |

### Contract Months

CME Bitcoin futures trade monthly. Contract codes:
- F = January
- G = February
- H = March
- J = April
- K = May
- M = June
- N = July
- Q = August
- U = September
- V = October
- X = November
- Z = December

Example: `MBTH6` = Micro Bitcoin March 2026

### Expiry

CME Bitcoin futures expire on the last Friday of the contract month.

## ETF Proxies for Spot

Since IBKR doesn't have direct BTC spot, we use Bitcoin ETFs:

| Symbol | Name | Multiplier |
|--------|------|------------|
| IBIT | BlackRock Bitcoin ETF | ~1850 |
| FBTC | Fidelity Bitcoin ETF | ~1850 |
| GBTC | Grayscale Bitcoin Trust | ~750 |

The multiplier converts ETF price to approximate BTC price.

## Troubleshooting

### Connection Refused

- Ensure TWS/Gateway is running
- Check socket port is enabled in settings
- Verify no firewall blocking localhost

### No Market Data

- Check market data subscription includes CME BTC futures
- Ensure contract is valid and not expired
- Wait for market hours (CME hours)

### Client ID Conflict

- Each connection needs unique client ID (1-32)
- Close other IBKR connections using same ID
- Use different IDs for different scripts

### Data Delayed

- Paper accounts may have delayed data
- Live account needed for real-time
- Some data requires additional subscriptions

## Market Data Subscriptions

Required subscriptions for full data:

1. **CME Cryptocurrency Futures** - Bitcoin futures
2. **US Securities** - For ETF prices (IBIT, FBTC)

Check in TWS: Account → Account Management → Market Data Subscriptions
