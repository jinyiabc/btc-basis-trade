#!/usr/bin/env python3
"""
Data models for the execution subsystem.

Defines configuration, order requests/results, and enums for trade execution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(Enum):
    """Order side."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(Enum):
    """Order execution status."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class TradeAction(Enum):
    """High-level trade action derived from signals."""
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    REDUCE = "REDUCE"
    NONE = "NONE"


@dataclass
class ExecutionConfig:
    """Configuration for the execution subsystem."""

    enabled: bool = False
    auto_trade: bool = False
    spot_symbol: str = "IBIT"
    futures_symbol: str = "MBT"
    order_type: str = "limit"
    limit_offset_pct: float = 0.001
    max_etf_shares: int = 10000
    max_futures_contracts: int = 50
    execution_client_id: int = 2
    dry_run: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionConfig":
        """Create ExecutionConfig from dictionary."""
        return cls(
            enabled=data.get("enabled", False),
            auto_trade=data.get("auto_trade", False),
            spot_symbol=data.get("spot_symbol", "IBIT"),
            futures_symbol=data.get("futures_symbol", "MBT"),
            order_type=data.get("order_type", "limit"),
            limit_offset_pct=data.get("limit_offset_pct", 0.001),
            max_etf_shares=data.get("max_etf_shares", 10000),
            max_futures_contracts=data.get("max_futures_contracts", 50),
            execution_client_id=data.get("execution_client_id", 2),
            dry_run=data.get("dry_run", True),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "auto_trade": self.auto_trade,
            "spot_symbol": self.spot_symbol,
            "futures_symbol": self.futures_symbol,
            "order_type": self.order_type,
            "limit_offset_pct": self.limit_offset_pct,
            "max_etf_shares": self.max_etf_shares,
            "max_futures_contracts": self.max_futures_contracts,
            "execution_client_id": self.execution_client_id,
            "dry_run": self.dry_run,
        }


@dataclass
class OrderRequest:
    """Describes a proposed order."""

    side: OrderSide
    symbol: str
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    signal: Optional[str] = None
    reason: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def describe(self) -> str:
        """Human-readable order description."""
        price_str = f" @ ${self.limit_price:,.2f}" if self.limit_price else ""
        qty_str = f"{self.quantity:,.0f}" if self.quantity == int(self.quantity) else f"{self.quantity:,.2f}"
        return (
            f"{self.side.value} {qty_str} {self.symbol} "
            f"({self.order_type.value}{price_str})"
        )


@dataclass
class OrderResult:
    """Result after order submission."""

    status: OrderStatus
    order_request: OrderRequest
    fill_price: Optional[float] = None
    filled_qty: Optional[float] = None
    commission: Optional[float] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "status": self.status.value,
            "side": self.order_request.side.value,
            "symbol": self.order_request.symbol,
            "requested_qty": self.order_request.quantity,
            "order_type": self.order_request.order_type.value,
            "limit_price": self.order_request.limit_price,
            "fill_price": self.fill_price,
            "filled_qty": self.filled_qty,
            "commission": self.commission,
            "error": self.error,
            "signal": self.order_request.signal,
            "timestamp": self.timestamp.isoformat(),
        }
