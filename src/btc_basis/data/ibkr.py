#!/usr/bin/env python3
"""
IBKR (Interactive Brokers) data fetcher for BTC spot and futures.

CONSOLIDATED from 5 files:
- fetch_btc_futures_ibkr.py
- fetch_btc_ibkr_unified.py
- fetch_futures_ibkr.py
- fetch_futures_ibkr_tws.py
- fetch_ibkr_historical.py
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import csv
import time

from btc_basis.data.base import BaseFetcher
from btc_basis.utils.expiry import get_last_friday_of_month, get_front_month_expiry_str


class IBKRFetcher(BaseFetcher):
    """
    Unified IBKR fetcher for BTC spot (via ETF) and CME futures.

    Requires ib_insync package and running TWS/IB Gateway.
    """

    # Default ports to try
    PORTS = {
        7497: "TWS Paper Trading",
        4002: "IB Gateway Paper",
        7496: "TWS Live",
        4001: "IB Gateway Live",
    }

    # ETF multipliers for BTC price estimation
    ETF_MULTIPLIERS = {
        "IBIT": 1850,  # BlackRock Bitcoin ETF
        "FBTC": 1850,  # Fidelity Bitcoin ETF
        "GBTC": 750,   # Grayscale Bitcoin Trust
    }

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = None,
        client_id: int = 1,
        timeout: int = 10,
    ):
        """
        Initialize IBKR fetcher.

        Args:
            host: IBKR address (default: localhost)
            port: Port (None = auto-detect)
            client_id: Unique client ID (1-32)
            timeout: Request timeout
        """
        super().__init__(timeout)
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = None
        self.connected = False

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "IBKRFetcher":
        """
        Create IBKRFetcher from config dictionary.

        Args:
            config: IBKR config dict with host, port, client_id, timeout

        Returns:
            Configured IBKRFetcher instance
        """
        return cls(
            host=config.get("host", "127.0.0.1"),
            port=config.get("port"),
            client_id=config.get("client_id", 1),
            timeout=config.get("timeout", 10),
        )

    def _get_ib(self):
        """Get ib_insync IB instance (lazy import)."""
        if self.ib is None:
            try:
                from ib_insync import IB
                self.ib = IB()
            except ImportError:
                raise ImportError(
                    "ib_insync not installed. Install with: pip install ib-insync"
                )
        return self.ib

    def connect(self, port: int = None) -> bool:
        """
        Connect to IBKR.

        Args:
            port: Specific port to use (None = try all)

        Returns:
            True if connected successfully
        """
        ib = self._get_ib()

        if port:
            ports_to_try = {port: f"Port {port}"}
        elif self.port:
            ports_to_try = {self.port: f"Port {self.port}"}
        else:
            ports_to_try = self.PORTS

        for p, description in ports_to_try.items():
            try:
                self.log(f"Trying {description} (port {p})...")
                ib.connect(self.host, p, clientId=self.client_id)
                self.connected = True
                self.port = p
                self.log(f"[OK] Connected to IBKR ({self.host}:{p})")
                return True
            except Exception as e:
                self.log(f"[X] {description} failed: {e}")
                continue

        self.log("[X] Could not connect to IBKR on any port")
        return False

    def disconnect(self):
        """Disconnect from IBKR."""
        if self.connected and self.ib:
            self.ib.disconnect()
            self.log("[OK] Disconnected from IBKR")
            self.connected = False

    def fetch_spot_price(self, etf_symbol: str = "IBIT") -> Optional[float]:
        """
        Fetch BTC spot price via ETF proxy.

        Args:
            etf_symbol: ETF to use (IBIT, FBTC, GBTC)

        Returns:
            Estimated BTC spot price or None
        """
        if not self.connected:
            if not self.connect():
                return None

        etf_data = self.get_etf_price(etf_symbol)
        if etf_data:
            return etf_data["btc_price"]
        return None

    def get_etf_price(self, symbol: str = "IBIT") -> Optional[Dict[str, Any]]:
        """
        Get ETF price and estimated BTC price.

        Args:
            symbol: ETF symbol

        Returns:
            Dictionary with ETF and estimated BTC price
        """
        if not self.connected:
            return None

        from ib_insync import Stock

        symbols_to_try = (
            [(symbol, self.ETF_MULTIPLIERS.get(symbol, 1850))]
            if symbol
            else [
                ("IBIT", 1850),
                ("FBTC", 1850),
                ("GBTC", 750),
            ]
        )

        for sym, multiplier in symbols_to_try:
            try:
                self.log(f"Trying {sym}...")

                contract = Stock(sym, "SMART", "USD")
                self.ib.qualifyContracts(contract)

                ticker = self.ib.reqMktData(contract, "", False, False)
                self.ib.sleep(2)

                price = ticker.marketPrice()
                if not price or price <= 0:
                    price = ticker.last

                self.ib.cancelMktData(contract)

                if price and price > 0:
                    btc_price = price * multiplier
                    self.log(f"[OK] {sym}: ${price:.2f} -> BTC ~${btc_price:,.2f}")

                    return {
                        "source": sym,
                        "etf_price": price,
                        "btc_price": btc_price,
                        "multiplier": multiplier,
                    }

            except Exception as e:
                self.log(f"[X] {sym} failed: {e}")
                continue

        return None

    def fetch_raw_etf_price(self, symbol: str, exchange: str = "SMART") -> Optional[float]:
        """
        Fetch raw ETF/stock price without BTC multiplier conversion.

        Useful for non-BTC pairs (e.g. GLD, USO, SLV) where ETF_MULTIPLIERS don't apply.

        Args:
            symbol: ETF/stock symbol
            exchange: Exchange (default SMART)

        Returns:
            ETF price or None
        """
        if not self.connected:
            if not self.connect():
                return None

        from ib_insync import Stock

        try:
            contract = Stock(symbol, exchange, "USD")
            self.ib.qualifyContracts(contract)

            ticker = self.ib.reqMktData(contract, "", False, False)
            self.ib.sleep(2)

            price = ticker.marketPrice()
            if not price or price <= 0:
                price = ticker.last

            self.ib.cancelMktData(contract)

            if price and price > 0:
                self.log(f"[OK] {symbol}: ${price:.2f}")
                return price

        except Exception as e:
            self.log(f"[X] {symbol} fetch failed: {e}")

        return None

    def fetch_crypto_spot_price(
        self, symbol: str = "BTC", currency: str = "USD"
    ) -> Optional[float]:
        """
        Fetch crypto spot price via IBKR Crypto contract (e.g. BTC.USD, ETH.USD).

        Args:
            symbol: Crypto symbol (BTC, ETH, etc.)
            currency: Quote currency (default USD)

        Returns:
            Spot price or None
        """
        if not self.connected:
            if not self.connect():
                return None

        from ib_insync import Crypto

        try:
            contract = Crypto(symbol, "PAXOS", currency)
            self.ib.qualifyContracts(contract)

            ticker = self.ib.reqMktData(contract, "", False, False)
            self.ib.sleep(2)

            price = ticker.marketPrice()
            if not price or price <= 0:
                price = ticker.last
            if not price or price <= 0:
                price = ticker.close

            self.ib.cancelMktData(contract)

            if price and price > 0:
                self.log(f"[OK] {symbol}.{currency}: ${price:,.2f}")
                return price

            self.log(f"[X] {symbol}.{currency}: no valid price")
            return None

        except Exception as e:
            self.log(f"[X] {symbol}.{currency} fetch failed: {e}")
            return None

    def fetch_commodity_spot_price(
        self, symbol: str = "XAUUSD", currency: str = "USD"
    ) -> Optional[float]:
        """
        Fetch commodity spot price via IBKR CMDTY contract (e.g. XAUUSD, XAGUSD).

        Args:
            symbol: Commodity symbol (XAUUSD for gold, XAGUSD for silver)
            currency: Quote currency (default USD)

        Returns:
            Spot price or None
        """
        if not self.connected:
            if not self.connect():
                return None

        from ib_insync import Contract

        try:
            contract = Contract(secType="CMDTY", symbol=symbol, exchange="SMART", currency=currency)
            self.ib.qualifyContracts(contract)

            ticker = self.ib.reqMktData(contract, "", False, False)
            self.ib.sleep(2)

            price = ticker.marketPrice()
            if not price or price <= 0:
                price = ticker.last
            if not price or price <= 0:
                price = ticker.close

            self.ib.cancelMktData(contract)

            if price and price > 0:
                self.log(f"[OK] {symbol}: ${price:,.2f}")
                return price

            self.log(f"[X] {symbol}: no valid price")
            return None

        except Exception as e:
            self.log(f"[X] {symbol} fetch failed: {e}")
            return None

    def fetch_futures_price(
        self, expiry: str = None, symbol: str = "MBT", exchange: str = "CME",
        multiplier: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch futures price.

        Args:
            expiry: Contract expiry in YYYYMM format (None = front-month)
            symbol: Futures symbol (e.g. 'MBT', 'MET', 'MCL', 'MGC', 'SI')
            exchange: Exchange (e.g. 'CME', 'NYMEX', 'COMEX')
            multiplier: Contract multiplier (e.g. 1000 for SI micro silver)

        Returns:
            Dictionary with futures data or None
        """
        if not self.connected:
            if not self.connect():
                return None

        # Use front-month if no expiry specified
        if expiry is None:
            expiry = get_front_month_expiry_str()

        from ib_insync import Future

        try:
            if multiplier:
                btc_future = Future(symbol=symbol, lastTradeDateOrContractMonth=expiry,
                                    exchange=exchange, multiplier=str(multiplier))
            else:
                btc_future = Future(symbol, expiry, exchange)
            self.log(f"Looking for {symbol} futures expiring {expiry}...")

            self.ib.qualifyContracts(btc_future)
            self.log(f"[OK] Contract found: {btc_future.localSymbol}")

            ticker = self.ib.reqMktData(btc_future, "", False, False)
            self.ib.sleep(2)

            futures_price = ticker.marketPrice()
            if not futures_price or futures_price <= 0:
                futures_price = ticker.last

            bid = ticker.bid if ticker.bid and ticker.bid > 0 else None
            ask = ticker.ask if ticker.ask and ticker.ask > 0 else None
            close = ticker.close if ticker.close and ticker.close > 0 else None
            volume = ticker.volume if ticker.volume and ticker.volume >= 0 else None

            self.ib.cancelMktData(btc_future)

            if futures_price and futures_price > 0:
                # MBT quotes are in index points (same as BTC price)
                # No multiplication needed for historical data
                # For live data, check if it's the raw quote
                if symbol == "MBT" and futures_price < 1000:
                    # Raw quote, multiply by 10
                    futures_price = futures_price * 10
                    if bid:
                        bid = bid * 10
                    if ask:
                        ask = ask * 10
                    if close:
                        close = close * 10

                self.log(f"[OK] Futures: ${futures_price:,.2f}")

                return {
                    "symbol": symbol,
                    "exchange": exchange,
                    "expiry": expiry,
                    "local_symbol": btc_future.localSymbol,
                    "futures_price": futures_price,
                    "bid": bid,
                    "ask": ask,
                    "close": close,
                    "volume": volume,
                    "timestamp": datetime.now(),
                }
            else:
                self.log("[X] No valid futures price")
                return None

        except Exception as e:
            self.log(f"[X] Failed to get futures: {e}")
            return None

    def _fetch_actual_spot_price(self, currency: str = "BTC") -> Optional[Dict[str, Any]]:
        """
        Fetch actual crypto spot price from Coinbase or Binance.

        Args:
            currency: Crypto symbol (BTC, ETH, etc.)

        Returns:
            Dictionary with spot_price and source, or None if all sources fail
        """
        # Try Coinbase first
        try:
            from btc_basis.data.coinbase import CoinbaseFetcher
            coinbase = CoinbaseFetcher()
            spot = coinbase.fetch_spot_price(currency=currency)
            if spot and spot > 0:
                self.log(f"[OK] Coinbase {currency} spot: ${spot:,.2f}")
                return {"spot_price": spot, "source": f"Coinbase ({currency})"}
        except Exception as e:
            self.log(f"[X] Coinbase failed: {e}")

        # Try Binance as fallback (BTC only)
        if currency == "BTC":
            try:
                from btc_basis.data.binance import BinanceFetcher
                binance = BinanceFetcher()
                spot = binance.fetch_spot_price()
                if spot and spot > 0:
                    self.log(f"[OK] Binance spot: ${spot:,.2f}")
                    return {"spot_price": spot, "source": "Binance"}
            except Exception as e:
                self.log(f"[X] Binance failed: {e}")

        return None

    def get_complete_basis_data(
        self, expiry: str = None, futures_symbol: str = "MBT", pair=None
    ) -> Optional[Dict[str, Any]]:
        """
        Get complete basis data: spot + futures + calculations.

        This is the main method for getting all data in one connection.
        When pair is provided, uses pair-specific symbols and exchange.
        For BTC pairs, spot price is fetched from Coinbase/Binance for accuracy.
        For non-BTC pairs, spot price is fetched via ETF from IBKR.

        Args:
            expiry: Futures expiry (YYYYMM), None = front-month
            futures_symbol: Futures symbol (used when pair is None)
            pair: Optional PairConfig for multi-pair support

        Returns:
            Complete basis trade data dictionary
        """
        if not self.connected:
            if not self.connect():
                return None

        # Resolve pair-specific settings
        if pair is not None:
            futures_symbol = pair.futures_symbol
            futures_exchange = pair.futures_exchange
            futures_multiplier = pair.futures_multiplier
            spot_symbol = pair.spot_symbol
            pair_id = pair.pair_id
        else:
            futures_exchange = "CME"
            futures_multiplier = None
            spot_symbol = "IBIT"
            pair_id = "BTC"

        # Use front-month if no expiry specified
        if expiry is None:
            expiry = get_front_month_expiry_str()
            self.log(f"[*] [{pair_id}] Using front-month contract: {expiry}")

        # Fetch spot price — strategy depends on pair type
        crypto_symbol = pair.crypto_symbol if pair is not None else "BTC"
        commodity_symbol = pair.commodity_symbol if pair is not None else None
        spot_price = None
        spot_source = None
        etf_price = None

        if crypto_symbol:
            # Crypto pair: use IBKR Crypto spot (e.g. BTC.USD, ETH.USD)
            self.log(f"\n[*] [{pair_id}] Fetching {crypto_symbol}.USD spot via IBKR Crypto...")
            spot_price = self.fetch_crypto_spot_price(crypto_symbol, "USD")
            if spot_price:
                spot_source = f"IBKR Crypto ({crypto_symbol}.USD)"
            else:
                # Fallback to Coinbase/Binance
                self.log(f"[!] [{pair_id}] IBKR Crypto failed, trying Coinbase/Binance...")
                actual_spot = self._fetch_actual_spot_price(crypto_symbol)
                if actual_spot:
                    spot_price = actual_spot["spot_price"]
                    spot_source = actual_spot["source"]

            # Also fetch ETF price for position sizing
            self.log(f"[*] [{pair_id}] Fetching ETF {spot_symbol} for position sizing...")
            if pair_id == "BTC":
                etf_data = self.get_etf_price(spot_symbol)
                etf_price = etf_data["etf_price"] if etf_data else None
            else:
                etf_price = self.fetch_raw_etf_price(spot_symbol)
        elif commodity_symbol:
            # Commodity pair: use IBKR CMDTY spot (e.g. XAUUSD, XAGUSD)
            self.log(f"\n[*] [{pair_id}] Fetching {commodity_symbol} spot via IBKR CMDTY...")
            spot_price = self.fetch_commodity_spot_price(commodity_symbol, "USD")
            if spot_price:
                spot_source = f"IBKR CMDTY ({commodity_symbol})"
            else:
                # Fallback to ETF as spot proxy
                self.log(f"[!] [{pair_id}] IBKR CMDTY failed, falling back to ETF {spot_symbol}...")
                raw_price = self.fetch_raw_etf_price(spot_symbol)
                if raw_price:
                    spot_price = raw_price
                    spot_source = f"{spot_symbol} (ETF proxy)"

            # Also fetch ETF price for position sizing
            self.log(f"[*] [{pair_id}] Fetching ETF {spot_symbol} for position sizing...")
            etf_price = self.fetch_raw_etf_price(spot_symbol)
        else:
            # Other: fetch ETF price as the spot proxy
            self.log(f"\n[*] [{pair_id}] Fetching spot via ETF {spot_symbol}...")
            raw_price = self.fetch_raw_etf_price(spot_symbol)
            if raw_price:
                spot_price = raw_price
                etf_price = raw_price
                spot_source = f"{spot_symbol} (ETF)"

        if not spot_price:
            self.log(f"[X] [{pair_id}] Could not get spot price from any source")
            return None

        self.log(f"\n[*] [{pair_id}] Fetching Futures Price...")
        futures_data = self.fetch_futures_price(expiry, futures_symbol, futures_exchange, futures_multiplier)

        if not futures_data:
            self.log(f"[X] [{pair_id}] Could not get futures data")
            return None

        futures_price = futures_data["futures_price"]

        basis_absolute = futures_price - spot_price
        basis_percent = (basis_absolute / spot_price) * 100

        # Calculate days to expiry
        expiry_date = get_last_friday_of_month(int(expiry[:4]), int(expiry[4:6]))
        days_to_expiry = (expiry_date - datetime.now()).days

        # Calculate monthly and annualized basis
        monthly_basis = basis_percent * (30 / days_to_expiry) if days_to_expiry > 0 else 0
        annualized_basis = basis_percent * (365 / days_to_expiry) if days_to_expiry > 0 else 0

        self.log(f"\n[*] [{pair_id}] Basis Calculation:")
        self.log(f"    Spot:        ${spot_price:,.2f} (from {spot_source})")
        self.log(f"    Futures:     ${futures_price:,.2f}")
        self.log(f"    Basis:       ${basis_absolute:,.2f} ({basis_percent:.2f}%)")
        self.log(f"    Monthly:     {monthly_basis:.2f}%")
        self.log(f"    Annualized:  {annualized_basis:.2f}%")

        return {
            # Spot data
            "spot_price": spot_price,
            "spot_source": spot_source,
            "etf_price": etf_price,
            # Futures data
            "futures_price": futures_price,
            "futures_symbol": futures_data["symbol"],
            "futures_local_symbol": futures_data["local_symbol"],
            "exchange": futures_data["exchange"],
            "expiry": expiry,
            "bid": futures_data["bid"],
            "ask": futures_data["ask"],
            "volume": futures_data["volume"],
            # Basis calculations
            "basis_absolute": basis_absolute,
            "basis_percent": basis_percent,
            "days_to_expiry": days_to_expiry,
            "monthly_basis": monthly_basis,
            "annualized_basis": annualized_basis,
            # Metadata
            "pair_id": pair_id,
            "timestamp": datetime.now(),
            "data_source": spot_source or "IBKR",
        }


class IBKRHistoricalFetcher(IBKRFetcher):
    """
    Fetch historical data from IBKR for backtesting.

    Extends IBKRFetcher with historical data capabilities.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = None, client_id: int = 2):
        super().__init__(host, port, client_id)

    def get_historical_spot(
        self,
        symbol: str = "IBIT",
        start_date: datetime = None,
        end_date: datetime = None,
        bar_size: str = "1 day",
    ) -> List[Dict[str, Any]]:
        """
        Get historical spot prices from ETF.

        Args:
            symbol: ETF symbol (IBIT, FBTC, GBTC)
            start_date: Start date for historical data
            end_date: End date for historical data
            bar_size: Bar size (1 day, 1 hour, etc.)

        Returns:
            List of dicts with date, etf_price, btc_price
        """
        if not self.connected:
            if not self.connect():
                return []

        from ib_insync import Stock

        try:
            stock = Stock(symbol, "SMART", "USD")
            self.ib.qualifyContracts(stock)

            self.log(f"Fetching historical data for {symbol}...")

            if not end_date:
                end_date = datetime.now()
            if not start_date:
                start_date = end_date - timedelta(days=365)

            duration_days = (end_date - start_date).days
            duration_str = f"{duration_days} D"

            bars = self.ib.reqHistoricalData(
                stock,
                endDateTime=end_date,
                durationStr=duration_str,
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
            )

            self.log(f"[OK] Fetched {len(bars)} bars for {symbol}")

            multiplier = self.ETF_MULTIPLIERS.get(symbol, 1850)
            result = []

            for bar in bars:
                etf_price = bar.close
                btc_price = etf_price * multiplier

                if isinstance(bar.date, datetime):
                    date_obj = bar.date
                else:
                    date_obj = datetime.combine(bar.date, datetime.min.time())

                result.append(
                    {
                        "date": date_obj,
                        "etf_price": etf_price,
                        "btc_price": btc_price,
                    }
                )

            return result

        except Exception as e:
            self.log(f"[X] Failed to fetch {symbol} historical data: {e}")
            return []

    def get_historical_futures(
        self,
        expiry: str = None,
        symbol: str = "MBT",
        exchange: str = "CME",
        start_date: datetime = None,
        end_date: datetime = None,
        bar_size: str = "1 day",
    ) -> List[Dict[str, Any]]:
        """
        Get historical futures prices.

        Args:
            expiry: Contract expiry (YYYYMM), None = front-month
            symbol: Futures symbol (e.g. MBT, MCL, MGC)
            exchange: Exchange (e.g. CME, NYMEX, COMEX)
            start_date: Start date
            end_date: End date
            bar_size: Bar size

        Returns:
            List of dicts with date, futures_price
        """
        if not self.connected:
            if not self.connect():
                return []

        # Use front-month if no expiry specified
        if expiry is None:
            expiry = get_front_month_expiry_str()

        from ib_insync import Future

        try:
            future = Future(symbol, expiry, exchange)
            self.ib.qualifyContracts(future)

            self.log(f"Fetching historical futures: {future.localSymbol}...")

            actual_expiry = None
            if future.lastTradeDateOrContractMonth:
                expiry_str = future.lastTradeDateOrContractMonth
                if len(expiry_str) == 8:
                    actual_expiry = datetime.strptime(expiry_str, "%Y%m%d")
                    self.log(
                        f"[*] Contract expiry: {actual_expiry.strftime('%Y-%m-%d (%A)')}"
                    )

            if not end_date:
                end_date = datetime.now()
            if not start_date:
                start_date = end_date - timedelta(days=90)

            duration_days = (end_date - start_date).days
            duration_str = f"{duration_days} D"

            bars = self.ib.reqHistoricalData(
                future,
                endDateTime=end_date,
                durationStr=duration_str,
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
            )

            self.log(f"[OK] Fetched {len(bars)} bars for {future.localSymbol}")

            result = []
            for bar in bars:
                futures_price = bar.close

                if isinstance(bar.date, datetime):
                    date_obj = bar.date
                else:
                    date_obj = datetime.combine(bar.date, datetime.min.time())

                result.append(
                    {
                        "date": date_obj,
                        "futures_price": futures_price,
                        "expiry": actual_expiry,
                    }
                )

            return result

        except Exception as e:
            self.log(f"[X] Failed to fetch futures historical data: {e}")
            return []

    def create_backtest_csv(
        self,
        output_file: str,
        start_date: datetime,
        end_date: datetime,
        futures_contracts: List[str] = None,
    ):
        """
        Create CSV file for backtesting.

        Args:
            output_file: Output CSV filename
            start_date: Start date for historical data
            end_date: End date for historical data
            futures_contracts: List of futures contract expiries
        """
        if not self.connected:
            if not self.connect():
                return

        self.log("\n" + "=" * 70)
        self.log("CREATING BACKTEST DATA FROM IBKR")
        self.log("=" * 70 + "\n")

        if not futures_contracts:
            current = datetime.now()
            futures_contracts = []
            for i in range(3):
                month = current.month + i
                year = current.year
                if month > 12:
                    month -= 12
                    year += 1
                futures_contracts.append(f"{year}{month:02d}")

        self.log(f"Period: {start_date.date()} to {end_date.date()}")
        self.log(f"Futures contracts: {futures_contracts}\n")

        # Fetch spot prices
        spot_data = self.get_historical_spot(
            symbol="IBIT",
            start_date=start_date,
            end_date=end_date,
            bar_size="1 day",
        )

        if not spot_data:
            self.log("[X] Failed to get spot data")
            return

        # Fetch futures for each contract
        all_futures_data = {}
        for expiry in futures_contracts:
            futures_data = self.get_historical_futures(
                expiry=expiry,
                symbol="MBT",
                start_date=start_date,
                end_date=end_date,
                bar_size="1 day",
            )

            if futures_data:
                for entry in futures_data:
                    date_key = entry["date"].date()
                    if date_key not in all_futures_data:
                        expiry_date = entry.get("expiry") or get_last_friday_of_month(
                            int(expiry[:4]), int(expiry[4:6])
                        )
                        all_futures_data[date_key] = {
                            "futures_price": entry["futures_price"],
                            "expiry": expiry_date,
                        }

            time.sleep(1)  # Rate limiting

        # Merge spot and futures data
        merged_data = []
        for spot_entry in spot_data:
            date_key = spot_entry["date"].date()

            if date_key in all_futures_data:
                futures_info = all_futures_data[date_key]
                merged_data.append(
                    {
                        "date": spot_entry["date"],
                        "spot_price": spot_entry["btc_price"],
                        "futures_price": futures_info["futures_price"],
                        "futures_expiry": futures_info["expiry"],
                    }
                )

        if not merged_data:
            self.log("[X] No merged data available")
            return

        # Write to CSV
        self.log(f"\nWriting {len(merged_data)} rows to {output_file}...")

        with open(output_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["date", "spot_price", "futures_price", "futures_expiry"]
            )
            writer.writeheader()

            for row in merged_data:
                writer.writerow(
                    {
                        "date": row["date"].strftime("%Y-%m-%d"),
                        "spot_price": f"{row['spot_price']:.2f}",
                        "futures_price": f"{row['futures_price']:.2f}",
                        "futures_expiry": row["futures_expiry"].strftime("%Y-%m-%d"),
                    }
                )

        self.log(f"[OK] CSV file created: {output_file}")
