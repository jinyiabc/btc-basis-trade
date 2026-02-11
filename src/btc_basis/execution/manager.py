#!/usr/bin/env python3
"""
Execution manager — bridges monitor signals to the IBKR executor.

Handles signal-to-action mapping, safety checks, confirmation prompts,
and execution logging.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from btc_basis.core.models import Signal, MarketData
from btc_basis.core.analyzer import BasisTradeAnalyzer
from btc_basis.execution.models import (
    ExecutionConfig,
    TradeAction,
    OrderStatus,
)
from btc_basis.execution.position import PositionTracker
from btc_basis.execution.executor import IBKRExecutor
from btc_basis.utils.logging import LoggingMixin


class ExecutionManager(LoggingMixin):
    """Bridges monitor signals to the IBKR executor."""

    EXECUTION_LOG = "output/execution/execution_log.jsonl"

    def __init__(
        self,
        exec_config: ExecutionConfig,
        analyzer: BasisTradeAnalyzer,
        ibkr_host: str = "127.0.0.1",
        ibkr_port: Optional[int] = None,
        pair=None,
    ):
        self.config = exec_config
        self.analyzer = analyzer
        self.pair = pair  # PairConfig or None

        pair_id = pair.pair_id if pair else "BTC"
        self.tracker = PositionTracker(pair_id=pair_id)
        self.executor = IBKRExecutor(
            config=exec_config,
            position_tracker=self.tracker,
            host=ibkr_host,
            port=ibkr_port,
        )

    def connect(self) -> bool:
        """Connect the executor to IBKR."""
        return self.executor.connect()

    def disconnect(self):
        """Disconnect the executor from IBKR."""
        self.executor.disconnect()

    # ------------------------------------------------------------------
    # Signal → Action mapping
    # ------------------------------------------------------------------

    def _determine_action(self, signal: Signal) -> TradeAction:
        """
        Map a signal to a trade action given current position state.

        Rules:
        - STRONG_ENTRY / ACCEPTABLE_ENTRY with no open position → OPEN
        - FULL_EXIT / STOP_LOSS with open position → CLOSE
        - PARTIAL_EXIT with open position → REDUCE
        - Otherwise → NONE
        """
        has_position = self.tracker.position.is_open

        if signal in (Signal.STRONG_ENTRY, Signal.ACCEPTABLE_ENTRY):
            if not has_position:
                return TradeAction.OPEN
            return TradeAction.NONE  # already in a position

        if signal in (Signal.FULL_EXIT, Signal.STOP_LOSS):
            if has_position:
                return TradeAction.CLOSE
            return TradeAction.NONE

        if signal == Signal.PARTIAL_EXIT:
            if has_position:
                return TradeAction.REDUCE
            return TradeAction.NONE

        return TradeAction.NONE

    # ------------------------------------------------------------------
    # Safety checks
    # ------------------------------------------------------------------

    def _safety_checks(
        self, action: TradeAction, sizing: Dict, market: MarketData
    ) -> Optional[str]:
        """
        Run safety checks before execution.

        Returns an error message string if a check fails, or None if all pass.
        """
        # Position limits
        etf_shares = sizing.get("etf_shares") or 0
        futures_contracts = sizing.get("futures_contracts") or 0

        if action == TradeAction.OPEN:
            if etf_shares > self.config.max_etf_shares:
                return (
                    f"ETF shares ({etf_shares}) exceeds limit "
                    f"({self.config.max_etf_shares})"
                )
            if futures_contracts > self.config.max_futures_contracts:
                return (
                    f"Futures contracts ({futures_contracts}) exceeds limit "
                    f"({self.config.max_futures_contracts})"
                )

        # Weekend guard (Saturday=5, Sunday=6)
        now = datetime.now()
        if now.weekday() >= 5:
            return f"Weekend detected (day={now.weekday()}) — markets closed"

        # Backwardation guard
        if market.monthly_basis < 0 and action == TradeAction.OPEN:
            return "Backwardation — refusing to open new position"

        return None

    # ------------------------------------------------------------------
    # Confirmation prompt
    # ------------------------------------------------------------------

    def _prompt_confirmation(self, summary: str) -> bool:
        """Print order summary and prompt for confirmation."""
        print("\n" + "=" * 60)
        print("TRADE EXECUTION CONFIRMATION")
        print("=" * 60)
        print(summary)
        print("=" * 60)

        response = input("Execute? (yes/no): ").strip().lower()
        return response in ("yes", "y")

    # ------------------------------------------------------------------
    # Execution logging
    # ------------------------------------------------------------------

    def _log_event(self, event: Dict) -> None:
        """Append event to execution log (JSONL)."""
        log_path = Path(self.EXECUTION_LOG)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        event["pair_id"] = self.pair.pair_id if self.pair else "BTC"
        event["logged_at"] = datetime.now().isoformat()
        with open(log_path, "a") as f:
            f.write(json.dumps(event) + "\n")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def handle_signal(
        self, signal: Signal, reason: str, market: MarketData
    ) -> None:
        """
        Handle a trading signal from the monitor.

        1. Determine action from signal + position state
        2. Get position sizing from analyzer
        3. Run safety checks
        4. Optionally prompt for confirmation
        5. Execute via IBKR executor
        6. Log everything
        """
        action = self._determine_action(signal)

        if action == TradeAction.NONE:
            self.log_debug(
                f"Signal {signal.value} → no action "
                f"(position_open={self.tracker.position.is_open})"
            )
            return

        self.log(f"Signal {signal.value} → action {action.value}: {reason}")

        # Get sizing from analyzer
        sizing = self.analyzer.calculate_position_sizing(market)

        # Safety checks
        safety_error = self._safety_checks(action, sizing, market)
        if safety_error:
            self.log_warning(f"Safety check failed: {safety_error}")
            self._log_event({
                "event": "REJECTED",
                "signal": signal.value,
                "action": action.value,
                "reason": safety_error,
            })
            return

        # Build order summary
        summary = self._build_summary(action, signal, reason, sizing, market)

        # Confirmation (unless auto_trade)
        if not self.config.auto_trade:
            if not self._prompt_confirmation(summary):
                self.log("Trade rejected by user")
                self._log_event({
                    "event": "USER_REJECTED",
                    "signal": signal.value,
                    "action": action.value,
                })
                return

        # Connect if needed
        if not self.executor.connected and not self.config.dry_run:
            if not self.connect():
                self._log_event({
                    "event": "CONNECTION_FAILED",
                    "signal": signal.value,
                    "action": action.value,
                })
                return

        # Execute
        self._log_event({
            "event": "EXECUTING",
            "signal": signal.value,
            "action": action.value,
            "sizing": sizing,
            "dry_run": self.config.dry_run,
        })

        if action == TradeAction.OPEN:
            self._execute_open(sizing, market)
        elif action == TradeAction.CLOSE:
            self._execute_close()
        elif action == TradeAction.REDUCE:
            self._execute_reduce()

    def _build_summary(
        self,
        action: TradeAction,
        signal: Signal,
        reason: str,
        sizing: Dict,
        market: MarketData,
    ) -> str:
        """Build human-readable trade summary for confirmation."""
        spot_sym = self.pair.spot_symbol if self.pair else self.config.spot_symbol
        fut_sym = self.pair.futures_symbol if self.pair else self.config.futures_symbol
        pair_id = self.pair.pair_id if self.pair else "BTC"

        lines = [
            f"Pair:         {pair_id}",
            f"Signal:       {signal.value}",
            f"Reason:       {reason}",
            f"Action:       {action.value}",
            f"Dry Run:      {'YES' if self.config.dry_run else 'NO — LIVE'}",
            f"",
            f"Spot:         ${market.spot_price:,.2f}",
            f"Futures:      ${market.futures_price:,.2f}",
            f"Monthly Basis:{market.monthly_basis*100:6.2f}%",
            f"",
        ]

        if action == TradeAction.OPEN:
            lines += [
                f"ETF ({spot_sym}):",
                f"  BUY {sizing.get('etf_shares', 'N/A')} shares "
                f"(~${sizing.get('etf_value', 0):,.2f})",
                f"Futures ({fut_sym}):",
                f"  SELL {sizing.get('futures_contracts', 'N/A')} contracts "
                f"(~${sizing.get('futures_value', 0):,.2f})",
            ]
        elif action == TradeAction.CLOSE:
            pos = self.tracker.position
            lines += [
                f"Closing position:",
                f"  SELL {pos.etf_shares} {pos.etf_symbol} shares",
                f"  BUY  {pos.futures_contracts} {pos.futures_symbol} contracts",
            ]
        elif action == TradeAction.REDUCE:
            pos = self.tracker.position
            lines += [
                f"Reducing position by 50%:",
                f"  SELL {max(1, pos.etf_shares // 2)} {pos.etf_symbol} shares",
                f"  BUY  {max(1, pos.futures_contracts // 2)} {pos.futures_symbol} contracts",
            ]

        return "\n".join(lines)

    def _execute_open(self, sizing: Dict, market: MarketData) -> None:
        """Execute an OPEN action."""
        etf_shares = sizing.get("etf_shares") or 0
        futures_contracts = sizing.get("futures_contracts") or 0

        etf_result, futures_result = self.executor.execute_entry_pair(
            etf_shares=etf_shares,
            futures_contracts=futures_contracts,
            etf_price=market.etf_price,
            futures_price=market.futures_price,
            pair=self.pair,
        )

        self._log_event({
            "event": "ENTRY_RESULT",
            "etf": etf_result.to_dict(),
            "futures": futures_result.to_dict() if futures_result else None,
        })

        self.log(f"Entry ETF: {etf_result.status.value}")
        if futures_result:
            self.log(f"Entry Futures: {futures_result.status.value}")

    def _execute_close(self) -> None:
        """Execute a CLOSE action."""
        etf_result, futures_result = self.executor.execute_exit_pair(pair=self.pair)

        self._log_event({
            "event": "EXIT_RESULT",
            "etf": etf_result.to_dict(),
            "futures": futures_result.to_dict() if futures_result else None,
        })

        self.log(f"Exit ETF: {etf_result.status.value}")
        if futures_result:
            self.log(f"Exit Futures: {futures_result.status.value}")

    def _execute_reduce(self) -> None:
        """Execute a REDUCE action (50% partial exit)."""
        etf_result, futures_result = self.executor.execute_partial_exit(
            exit_pct=0.5, pair=self.pair
        )

        self._log_event({
            "event": "REDUCE_RESULT",
            "etf": etf_result.to_dict(),
            "futures": futures_result.to_dict() if futures_result else None,
        })

        self.log(f"Partial exit ETF: {etf_result.status.value}")
        if futures_result:
            self.log(f"Partial exit Futures: {futures_result.status.value}")
