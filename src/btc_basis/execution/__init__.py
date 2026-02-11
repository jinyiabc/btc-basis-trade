"""
Execution subsystem for BTC Basis Trade.

Handles order execution via IBKR, position tracking, and signal-to-trade mapping.
"""

from btc_basis.execution.models import (
    ExecutionConfig,
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderType,
    OrderStatus,
    TradeAction,
)
from btc_basis.execution.position import Position, PositionTracker
from btc_basis.execution.executor import IBKRExecutor
from btc_basis.execution.manager import ExecutionManager

__all__ = [
    "ExecutionConfig",
    "OrderRequest",
    "OrderResult",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "TradeAction",
    "Position",
    "PositionTracker",
    "IBKRExecutor",
    "ExecutionManager",
]
