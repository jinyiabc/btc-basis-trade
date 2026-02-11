#!/usr/bin/env python3
"""
IBKR trade executor for the execution subsystem.

Places orders via ib_insync using patterns from IBKRFetcher but with a
separate client_id to avoid connection conflicts.
"""

import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from btc_basis.execution.models import (
    ExecutionConfig,
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderType,
    OrderStatus,
)
from btc_basis.execution.position import PositionTracker
from btc_basis.utils.logging import LoggingMixin
from btc_basis.utils.expiry import get_front_month_expiry_str


class IBKRExecutor(LoggingMixin):
    """Places orders via IBKR's ib_insync API."""

    # Default ports to try (same as IBKRFetcher)
    PORTS = {
        7497: "TWS Paper Trading",
        4002: "IB Gateway Paper",
        7496: "TWS Live",
        4001: "IB Gateway Live",
    }

    def __init__(
        self,
        config: ExecutionConfig,
        position_tracker: Optional[PositionTracker] = None,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
    ):
        self.config = config
        self.tracker = position_tracker or PositionTracker()
        self.host = host
        self.port = port
        self.ib = None
        self.connected = False

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

    def connect(self) -> bool:
        """Connect to IBKR with execution client_id."""
        if self.config.dry_run:
            self.log("[DRY RUN] Skipping IBKR connection")
            return True

        ib = self._get_ib()

        if self.port:
            ports_to_try = {self.port: f"Port {self.port}"}
        else:
            ports_to_try = self.PORTS

        for p, description in ports_to_try.items():
            try:
                self.log(f"Executor connecting: {description} (port {p})...")
                ib.connect(
                    self.host, p, clientId=self.config.execution_client_id
                )
                self.connected = True
                self.port = p
                self.log(f"[OK] Executor connected ({self.host}:{p}, "
                         f"clientId={self.config.execution_client_id})")
                return True
            except Exception as e:
                self.log(f"[X] {description} failed: {e}")
                continue

        self.log("[X] Executor could not connect to IBKR on any port")
        return False

    def disconnect(self):
        """Disconnect from IBKR."""
        if self.connected and self.ib:
            self.ib.disconnect()
            self.log("[OK] Executor disconnected from IBKR")
            self.connected = False

    def _create_etf_contract(self, symbol: str):
        """Create ETF stock contract (same pattern as ibkr.py:186)."""
        from ib_insync import Stock
        contract = Stock(symbol, "SMART", "USD")
        self.ib.qualifyContracts(contract)
        return contract

    def _create_futures_contract(self, symbol: str, expiry: Optional[str] = None):
        """Create CME futures contract (same pattern as ibkr.py:239)."""
        from ib_insync import Future
        if expiry is None:
            expiry = get_front_month_expiry_str()
        contract = Future(symbol, expiry, "CME")
        self.ib.qualifyContracts(contract)
        return contract

    @staticmethod
    def _is_overnight_session() -> bool:
        """Check if current time is in IBKR overnight session (8:00 PM - 3:50 AM ET)."""
        et = timezone(timedelta(hours=-5))
        now_et = datetime.now(et)
        hour, minute = now_et.hour, now_et.minute
        # 20:00 ET to 03:50 ET next day
        return hour >= 20 or (hour < 3) or (hour == 3 and minute < 50)

    def _create_order(
        self,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        limit_price: Optional[float] = None,
    ):
        """Create an ib_insync order object."""
        from ib_insync import MarketOrder, LimitOrder

        action = "BUY" if side == OrderSide.BUY else "SELL"

        if order_type == OrderType.LIMIT and limit_price is not None:
            order = LimitOrder(action, quantity, limit_price)
            if self._is_overnight_session():
                order.outsideRth = True
                order.tif = "OVERNIGHT"
            else:
                order.outsideRth = True
            return order
        return MarketOrder(action, quantity)

    def _place_and_wait(self, contract, order, timeout: int = 30) -> OrderResult:
        """Place order and wait for fill, cancel on timeout."""
        trade = self.ib.placeOrder(contract, order)
        self.log(f"Order placed: {trade.order.action} {trade.order.totalQuantity} "
                 f"{contract.symbol}")

        start = time.time()
        while not trade.isDone() and (time.time() - start) < timeout:
            self.ib.sleep(0.5)

        if trade.isDone():
            if trade.orderStatus.status == "Filled":
                return OrderResult(
                    status=OrderStatus.FILLED,
                    order_request=OrderRequest(
                        side=OrderSide(trade.order.action),
                        symbol=contract.symbol,
                        quantity=trade.order.totalQuantity,
                    ),
                    fill_price=trade.orderStatus.avgFillPrice,
                    filled_qty=trade.orderStatus.filled,
                    commission=sum(
                        fill.commissionReport.commission
                        for fill in trade.fills
                        if fill.commissionReport
                    ) or None,
                )
            else:
                return OrderResult(
                    status=OrderStatus.FAILED,
                    order_request=OrderRequest(
                        side=OrderSide(trade.order.action),
                        symbol=contract.symbol,
                        quantity=trade.order.totalQuantity,
                    ),
                    error=f"Order ended with status: {trade.orderStatus.status}",
                )

        # Timeout — cancel
        self.log_warning(f"Order timeout after {timeout}s — cancelling")
        self.ib.cancelOrder(order)
        self.ib.sleep(1)

        filled = trade.orderStatus.filled or 0
        if filled > 0:
            return OrderResult(
                status=OrderStatus.PARTIALLY_FILLED,
                order_request=OrderRequest(
                    side=OrderSide(trade.order.action),
                    symbol=contract.symbol,
                    quantity=trade.order.totalQuantity,
                ),
                fill_price=trade.orderStatus.avgFillPrice,
                filled_qty=filled,
                error=f"Partial fill ({filled}/{trade.order.totalQuantity}) before timeout",
            )

        return OrderResult(
            status=OrderStatus.CANCELLED,
            order_request=OrderRequest(
                side=OrderSide(trade.order.action),
                symbol=contract.symbol,
                quantity=trade.order.totalQuantity,
            ),
            error="Order cancelled due to timeout",
        )

    def execute_order(self, request: OrderRequest) -> OrderResult:
        """
        Execute a single order.

        In dry_run mode, returns PENDING without submitting.
        """
        if self.config.dry_run:
            self.log(f"[DRY RUN] Would execute: {request.describe()}")
            return OrderResult(
                status=OrderStatus.PENDING,
                order_request=request,
                error="Dry run — order not submitted",
            )

        if not self.connected:
            return OrderResult(
                status=OrderStatus.FAILED,
                order_request=request,
                error="Not connected to IBKR",
            )

        try:
            # Determine contract type based on symbol
            if request.symbol in ("IBIT", "FBTC", "GBTC"):
                contract = self._create_etf_contract(request.symbol)
            else:
                contract = self._create_futures_contract(request.symbol)

            order = self._create_order(
                request.side,
                request.order_type,
                request.quantity,
                request.limit_price,
            )

            return self._place_and_wait(contract, order)

        except Exception as e:
            self.log_error(f"Order execution failed: {e}")
            return OrderResult(
                status=OrderStatus.FAILED,
                order_request=request,
                error=str(e),
            )

    def execute_entry_pair(
        self,
        etf_shares: int,
        futures_contracts: int,
        etf_price: Optional[float] = None,
        futures_price: Optional[float] = None,
        futures_expiry: Optional[str] = None,
    ) -> Tuple[OrderResult, Optional[OrderResult]]:
        """
        Execute entry: BUY ETF then SELL futures.

        Aborts futures leg if ETF leg fails.
        """
        # Calculate limit prices if using limit orders
        etf_limit = None
        futures_limit = None
        if self.config.order_type == "limit":
            if etf_price:
                etf_limit = round(etf_price * (1 + self.config.limit_offset_pct), 2)
            if futures_price:
                futures_limit = round(
                    futures_price * (1 - self.config.limit_offset_pct), 2
                )

        order_type = (
            OrderType.LIMIT if self.config.order_type == "limit" else OrderType.MARKET
        )

        # Leg 1: BUY ETF
        etf_request = OrderRequest(
            side=OrderSide.BUY,
            symbol=self.config.spot_symbol,
            quantity=etf_shares,
            order_type=order_type,
            limit_price=etf_limit,
            signal="ENTRY",
            reason="Basis trade entry — spot leg",
        )

        self.log(f"[1/2] ETF entry: {etf_request.describe()}")
        etf_result = self.execute_order(etf_request)

        if etf_result.status not in (
            OrderStatus.FILLED,
            OrderStatus.PENDING,  # dry_run
        ):
            self.log_error(f"ETF leg failed: {etf_result.error} — aborting futures leg")
            return etf_result, None

        # Leg 2: SELL futures
        futures_request = OrderRequest(
            side=OrderSide.SELL,
            symbol=self.config.futures_symbol,
            quantity=futures_contracts,
            order_type=order_type,
            limit_price=futures_limit,
            signal="ENTRY",
            reason="Basis trade entry — futures leg",
        )

        self.log(f"[2/2] Futures entry: {futures_request.describe()}")
        futures_result = self.execute_order(futures_request)

        # Update position tracker on success
        if etf_result.status == OrderStatus.FILLED and futures_result.status == OrderStatus.FILLED:
            self.tracker.update_on_entry(
                etf_shares=int(etf_result.filled_qty or etf_shares),
                etf_price=etf_result.fill_price or etf_price or 0,
                futures_contracts=int(futures_result.filled_qty or futures_contracts),
                futures_price=futures_result.fill_price or futures_price or 0,
                etf_symbol=self.config.spot_symbol,
                futures_symbol=self.config.futures_symbol,
                futures_expiry=futures_expiry,
            )

        return etf_result, futures_result

    def execute_exit_pair(self) -> Tuple[OrderResult, Optional[OrderResult]]:
        """
        Execute full exit: SELL ETF + BUY futures using current position.
        """
        pos = self.tracker.position
        if not pos.is_open:
            self.log_warning("No open position to exit")
            dummy = OrderRequest(
                side=OrderSide.SELL, symbol="NONE", quantity=0
            )
            return OrderResult(
                status=OrderStatus.FAILED,
                order_request=dummy,
                error="No open position",
            ), None

        order_type = (
            OrderType.LIMIT if self.config.order_type == "limit" else OrderType.MARKET
        )

        # Leg 1: SELL ETF
        etf_request = OrderRequest(
            side=OrderSide.SELL,
            symbol=pos.etf_symbol,
            quantity=pos.etf_shares,
            order_type=order_type,
            signal="EXIT",
            reason="Basis trade exit — spot leg",
        )

        self.log(f"[1/2] ETF exit: {etf_request.describe()}")
        etf_result = self.execute_order(etf_request)

        # Leg 2: BUY futures (close short)
        futures_request = OrderRequest(
            side=OrderSide.BUY,
            symbol=pos.futures_symbol,
            quantity=pos.futures_contracts,
            order_type=order_type,
            signal="EXIT",
            reason="Basis trade exit — futures leg",
        )

        self.log(f"[2/2] Futures exit: {futures_request.describe()}")
        futures_result = self.execute_order(futures_request)

        # Clear position on success
        if etf_result.status == OrderStatus.FILLED and futures_result.status == OrderStatus.FILLED:
            self.tracker.clear()
        elif self.config.dry_run:
            self.tracker.clear()

        return etf_result, futures_result

    def execute_partial_exit(
        self, exit_pct: float = 0.5
    ) -> Tuple[OrderResult, Optional[OrderResult]]:
        """Reduce both legs proportionally."""
        pos = self.tracker.position
        if not pos.is_open:
            self.log_warning("No open position to reduce")
            dummy = OrderRequest(
                side=OrderSide.SELL, symbol="NONE", quantity=0
            )
            return OrderResult(
                status=OrderStatus.FAILED,
                order_request=dummy,
                error="No open position",
            ), None

        etf_to_sell = max(1, int(pos.etf_shares * exit_pct))
        contracts_to_close = max(1, int(pos.futures_contracts * exit_pct))

        order_type = (
            OrderType.LIMIT if self.config.order_type == "limit" else OrderType.MARKET
        )

        # SELL portion of ETF
        etf_request = OrderRequest(
            side=OrderSide.SELL,
            symbol=pos.etf_symbol,
            quantity=etf_to_sell,
            order_type=order_type,
            signal="PARTIAL_EXIT",
            reason=f"Partial exit ({exit_pct*100:.0f}%) — spot leg",
        )

        self.log(f"[1/2] Partial ETF exit: {etf_request.describe()}")
        etf_result = self.execute_order(etf_request)

        # BUY portion of futures (close part of short)
        futures_request = OrderRequest(
            side=OrderSide.BUY,
            symbol=pos.futures_symbol,
            quantity=contracts_to_close,
            order_type=order_type,
            signal="PARTIAL_EXIT",
            reason=f"Partial exit ({exit_pct*100:.0f}%) — futures leg",
        )

        self.log(f"[2/2] Partial futures exit: {futures_request.describe()}")
        futures_result = self.execute_order(futures_request)

        # Update tracker
        if etf_result.status == OrderStatus.FILLED and futures_result.status == OrderStatus.FILLED:
            self.tracker.update_on_partial_exit(
                int(etf_result.filled_qty or etf_to_sell),
                int(futures_result.filled_qty or contracts_to_close),
            )
        elif self.config.dry_run:
            self.tracker.update_on_partial_exit(etf_to_sell, contracts_to_close)

        return etf_result, futures_result
