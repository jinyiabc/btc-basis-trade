#!/usr/bin/env python3
"""
Basis Trade Monitor daemon.

Continuously monitors basis spread and generates alerts.
Supports multiple asset pairs (BTC, ETH, Oil, Gold, Silver, etc.)
each with their own spot ETF + futures contract.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from btc_basis.core.models import Signal, TradeConfig, MarketData, PairConfig, make_pair_trade_config
from btc_basis.core.analyzer import BasisTradeAnalyzer
from btc_basis.data.coinbase import CoinbaseFetcher, FearGreedFetcher
from btc_basis.utils.config import ConfigLoader
from btc_basis.utils.logging import LoggingMixin, setup_logging
from btc_basis.utils.io import ReportWriter


@dataclass
class PairContext:
    """Per-pair runtime state for the monitor loop."""

    pair: PairConfig
    trade_config: TradeConfig
    analyzer: BasisTradeAnalyzer
    execution_manager: Optional[object] = None  # ExecutionManager (lazy import)
    last_signal: Optional[Signal] = None
    history: List[Dict] = field(default_factory=list)


class BasisMonitor(LoggingMixin):
    """Monitor basis spread and generate alerts for multiple pairs."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize monitor.

        Args:
            config_path: Path to config JSON file
        """
        self.config_loader = ConfigLoader(config_path)
        self.global_trade_config = TradeConfig.from_dict(self.config_loader.get_all())
        self.coinbase = CoinbaseFetcher()
        self.fear_greed = FearGreedFetcher()
        self.report_writer = ReportWriter()
        self.ibkr_fetcher = None

        # Build per-pair contexts
        pairs = self.config_loader.get_pairs()
        self.pairs: Dict[str, PairContext] = {}
        for pair in pairs:
            pair_config = make_pair_trade_config(self.global_trade_config, pair)
            analyzer = BasisTradeAnalyzer(pair_config)
            ctx = PairContext(
                pair=pair,
                trade_config=pair_config,
                analyzer=analyzer,
            )
            self.pairs[pair.pair_id] = ctx

        # Conditionally init execution managers and IBKR data fetcher
        exec_cfg = self.config_loader.execution
        if exec_cfg and exec_cfg.get("enabled"):
            self._init_execution(exec_cfg)
            self._init_ibkr_fetcher()

        # Setup logging
        setup_logging(log_file="output/logs/btc_basis_monitor.log")

    def _init_execution(self, exec_cfg: Dict):
        """Initialize execution managers for all pairs."""
        try:
            from btc_basis.execution.models import ExecutionConfig
            from btc_basis.execution.manager import ExecutionManager

            execution_config = ExecutionConfig.from_dict(exec_cfg)
            ibkr_cfg = self.config_loader.ibkr or {}

            for pair_id, ctx in self.pairs.items():
                ctx.execution_manager = ExecutionManager(
                    exec_config=execution_config,
                    analyzer=ctx.analyzer,
                    ibkr_host=ibkr_cfg.get("host", "127.0.0.1"),
                    ibkr_port=ibkr_cfg.get("port"),
                    pair=ctx.pair,
                )
        except Exception as e:
            logging.warning(f"Execution manager init failed: {e}")

    def _init_ibkr_fetcher(self):
        """Initialize shared IBKR data fetcher."""
        try:
            from btc_basis.data.ibkr import IBKRFetcher

            ibkr_cfg = self.config_loader.ibkr or {}
            self.ibkr_fetcher = IBKRFetcher.from_config(ibkr_cfg)
        except ImportError:
            logging.warning("ib_insync not installed — IBKR data unavailable")
        except Exception as e:
            logging.warning(f"IBKR data fetcher init failed: {e}")

    # ------------------------------------------------------------------
    # Backward-compat properties for CLI override logic
    # ------------------------------------------------------------------

    @property
    def execution_manager(self):
        """Return first pair's execution manager (backward compat)."""
        for ctx in self.pairs.values():
            if ctx.execution_manager:
                return ctx.execution_manager
        return None

    @property
    def trade_config(self):
        return self.global_trade_config

    @property
    def analyzer(self):
        """Return first pair's analyzer (backward compat)."""
        for ctx in self.pairs.values():
            return ctx.analyzer
        return BasisTradeAnalyzer(self.global_trade_config)

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def _fetch_via_ibkr(self, pair: PairConfig) -> Optional[MarketData]:
        """Try fetching market data via IBKR for a specific pair."""
        if not self.ibkr_fetcher:
            return None

        try:
            if not self.ibkr_fetcher.connected:
                if not self.ibkr_fetcher.connect():
                    return None

            ibkr_data = self.ibkr_fetcher.get_complete_basis_data(pair=pair)
            if not ibkr_data:
                return None

            fear_greed = self.fear_greed.fetch_index()

            from btc_basis.utils.expiry import get_expiry_from_yyyymm
            expiry_date = get_expiry_from_yyyymm(ibkr_data["expiry"])

            market = MarketData(
                spot_price=ibkr_data["spot_price"],
                futures_price=ibkr_data["futures_price"],
                futures_expiry_date=expiry_date,
                etf_price=ibkr_data.get("etf_price"),
                fear_greed_index=fear_greed,
                cme_open_interest=ibkr_data.get("volume"),
                pair_id=pair.pair_id,
                spot_symbol=pair.spot_symbol,
                futures_symbol=pair.futures_symbol,
            )

            self.log(
                f"[{pair.pair_id}] IBKR data fetched - Spot: ${market.spot_price:,.2f}, "
                f"Futures: ${market.futures_price:,.2f}, "
                f"ETF: ${market.etf_price:.2f}" if market.etf_price else ""
                f", Monthly Basis: {market.monthly_basis*100:.2f}%"
            )
            return market

        except Exception as e:
            self.log_warning(f"[{pair.pair_id}] IBKR fetch failed: {e}")
            return None

    def fetch_market_data(self, pair: PairConfig) -> Optional[MarketData]:
        """
        Fetch current market data for a specific pair.

        Uses IBKR for real ETF/futures prices when available.
        Falls back to Coinbase + estimated futures for BTC only.

        Args:
            pair: PairConfig for the pair to fetch data for

        Returns:
            MarketData or None if fetch failed
        """
        # Try IBKR first for real prices
        market = self._fetch_via_ibkr(pair)
        if market:
            return market

        # Fallback: Coinbase spot + estimated futures (crypto pairs only)
        if pair.crypto_symbol:
            try:
                spot_price = self.coinbase.fetch_spot_price(currency=pair.crypto_symbol)
                if not spot_price:
                    self.log_error(f"[{pair.pair_id}] Failed to fetch {pair.crypto_symbol} spot price")
                    return None

                fear_greed = self.fear_greed.fetch_index()

                futures_price = spot_price * 1.02  # Placeholder: 2% contango
                expiry = datetime.now() + timedelta(days=30)

                market = MarketData(
                    spot_price=spot_price,
                    futures_price=futures_price,
                    futures_expiry_date=expiry,
                    fear_greed_index=fear_greed,
                    pair_id=pair.pair_id,
                    spot_symbol=pair.spot_symbol,
                futures_symbol=pair.futures_symbol,
                )

                self.log(
                    f"[{pair.pair_id}] Coinbase {pair.crypto_symbol} spot: ${spot_price:,.2f}, "
                    f"Monthly Basis: {market.monthly_basis*100:.2f}% (estimated)"
                )
                return market

            except Exception as e:
                self.log_error(f"[{pair.pair_id}] Error fetching market data: {e}")
                return None
        else:
            self.log_warning(
                f"[{pair.pair_id}] No IBKR connection — no fallback for non-crypto pairs"
            )
            return None

    # ------------------------------------------------------------------
    # Alert processing
    # ------------------------------------------------------------------

    def check_and_alert(self, ctx: PairContext, market: MarketData) -> Dict:
        """
        Check market conditions and generate alerts for a specific pair.

        Args:
            ctx: PairContext for the pair
            market: Current market data

        Returns:
            Alert data dictionary
        """
        signal, reason = ctx.analyzer.generate_signal(market)
        returns = ctx.analyzer.calculate_returns(market)
        risks = ctx.analyzer.assess_risk(market)

        alert_data = {
            "timestamp": datetime.now().isoformat(),
            "pair_id": ctx.pair.pair_id,
            "spot_price": market.spot_price,
            "futures_price": market.futures_price,
            "monthly_basis": returns["monthly_basis"],
            "net_annualized_return": returns["net_annualized"],
            "signal": signal.value,
            "signal_reason": reason,
            "risks": risks,
        }

        # Check if signal changed
        signal_changed = ctx.last_signal != signal
        ctx.last_signal = signal

        # Alert conditions
        alert_triggered = False
        alert_messages = []
        pair_tag = f"[{ctx.pair.pair_id}]"

        if signal == Signal.STOP_LOSS:
            alert_triggered = True
            alert_messages.append(f"{pair_tag} [!!] STOP LOSS ALERT: {reason}")

        elif signal == Signal.FULL_EXIT:
            alert_triggered = True
            alert_messages.append(f"{pair_tag} [-] FULL EXIT SIGNAL: {reason}")

        elif signal == Signal.PARTIAL_EXIT:
            alert_triggered = True
            alert_messages.append(f"{pair_tag} [~] PARTIAL EXIT SIGNAL: {reason}")

        elif signal == Signal.STRONG_ENTRY and signal_changed:
            alert_triggered = True
            alert_messages.append(f"{pair_tag} [+] STRONG ENTRY SIGNAL: {reason}")

        elif signal == Signal.ACCEPTABLE_ENTRY and signal_changed:
            alert_triggered = True
            alert_messages.append(f"{pair_tag} [~] ACCEPTABLE ENTRY SIGNAL: {reason}")

        # Risk-based alerts
        critical_risks = [k for k, v in risks.items() if "[X]" in v]
        if critical_risks:
            alert_triggered = True
            alert_messages.append(f"{pair_tag} [!] CRITICAL RISKS: {', '.join(critical_risks)}")

        if alert_triggered:
            for msg in alert_messages:
                self.log_warning(msg)
                self.send_alert(msg, alert_data)

            # Trigger execution if manager is available
            if ctx.execution_manager:
                try:
                    ctx.execution_manager.handle_signal(signal, reason, market)
                except Exception as e:
                    self.log_error(f"[{ctx.pair.pair_id}] Execution failed: {e}")

        # Add to history
        ctx.history.append(alert_data)
        if len(ctx.history) > 1000:
            ctx.history = ctx.history[-1000:]

        return alert_data

    def send_alert(self, message: str, data: Dict):
        """
        Send alert notification.

        Args:
            message: Alert message
            data: Alert data
        """
        alert_file = Path("output/logs/alerts.log")
        alert_file.parent.mkdir(parents=True, exist_ok=True)

        with open(alert_file, "a") as f:
            f.write(f"{datetime.now().isoformat()} - {message}\n")
            f.write(f"Data: {json.dumps(data, indent=2)}\n\n")

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def generate_summary_report(self) -> str:
        """
        Generate combined summary from recent history across all pairs.

        Returns:
            Summary report string
        """
        lines = [
            f"{'='*70}",
            f"BASIS MONITOR SUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"{'='*70}",
        ]

        for pair_id, ctx in self.pairs.items():
            if not ctx.history:
                lines.append(f"\n[{pair_id}] No data collected yet.")
                continue

            current = ctx.history[-1]
            recent = ctx.history[-10:]

            if len(ctx.history) >= 2:
                basis_change = current["monthly_basis"] - ctx.history[-2]["monthly_basis"]
                trend = "[UP] Rising" if basis_change > 0 else "[DOWN] Falling"
            else:
                basis_change = 0
                trend = "[=]  Stable"

            lines += [
                f"\n--- [{pair_id}] {ctx.pair.spot_symbol}/{ctx.pair.futures_symbol} ---",
                f"  Spot Price:         ${current['spot_price']:,.2f}",
                f"  Monthly Basis:      {current['monthly_basis']:.2f}%",
                f"  Net Annual Return:  {current['net_annualized_return']:.2f}%",
                f"  Signal:             {current['signal']}",
                f"  Trend:              {trend} ({basis_change:+.2f}% change)",
                f"  Recent ({len(recent)} samples):",
            ]

            for i, record in enumerate(recent, 1):
                ts = datetime.fromisoformat(record["timestamp"]).strftime("%H:%M:%S")
                lines.append(
                    f"    {i}. {ts} - Basis: {record['monthly_basis']:5.2f}% - {record['signal']}"
                )

            lines.append("  Risks:")
            for risk_type, risk_level in current["risks"].items():
                lines.append(f"    {risk_type.capitalize():20s} {risk_level}")

        lines.append(f"\n{'='*70}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Run modes
    # ------------------------------------------------------------------

    def run_continuous(self, interval_seconds: int = 300, pair_filter: Optional[str] = None):
        """
        Run continuous monitoring loop for all (or filtered) pairs.

        Args:
            interval_seconds: Check interval in seconds
            pair_filter: If set, only monitor this pair_id
        """
        active_pairs = self._get_active_pairs(pair_filter)
        pair_names = ", ".join(active_pairs.keys())
        self.log(f"Starting continuous monitoring for [{pair_names}] (interval: {interval_seconds}s)")

        check_count = 0
        try:
            while True:
                for pair_id, ctx in active_pairs.items():
                    market = self.fetch_market_data(ctx.pair)
                    if market:
                        self.check_and_alert(ctx, market)

                check_count += 1
                # Print summary every hour (12 x 5-min intervals)
                if check_count % 12 == 0:
                    print(self.generate_summary_report())

                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            self.log("Monitoring stopped by user")
            if self.ibkr_fetcher and self.ibkr_fetcher.connected:
                self.ibkr_fetcher.disconnect()
            for ctx in active_pairs.values():
                if ctx.execution_manager:
                    ctx.execution_manager.disconnect()
            self.save_history()

    def run_once(self, pair_filter: Optional[str] = None) -> bool:
        """
        Run single check for all (or filtered) pairs.

        Args:
            pair_filter: If set, only check this pair_id

        Returns:
            True if at least one check was successful
        """
        active_pairs = self._get_active_pairs(pair_filter)
        success = False

        for pair_id, ctx in active_pairs.items():
            market = self.fetch_market_data(ctx.pair)
            if market:
                self.check_and_alert(ctx, market)
                report = ctx.analyzer.generate_report(market)
                print(f"\n--- [{pair_id}] ---")
                print(report)
                success = True

        return success

    def _get_active_pairs(self, pair_filter: Optional[str] = None) -> Dict[str, PairContext]:
        """Get pairs to monitor, optionally filtered."""
        if pair_filter:
            pair_filter = pair_filter.upper()
            if pair_filter in self.pairs:
                return {pair_filter: self.pairs[pair_filter]}
            self.log_warning(f"Pair '{pair_filter}' not found. Available: {list(self.pairs.keys())}")
            return {}
        return self.pairs

    def save_history(self):
        """Save history to file for all pairs."""
        combined = {}
        for pair_id, ctx in self.pairs.items():
            combined[pair_id] = ctx.history

        history_file = f"output/logs/basis_history_{datetime.now().strftime('%Y%m%d')}.json"
        Path(history_file).parent.mkdir(parents=True, exist_ok=True)

        with open(history_file, "w") as f:
            json.dump(combined, f, indent=2)

        self.log(f"History saved to {history_file}")
