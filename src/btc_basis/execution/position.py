#!/usr/bin/env python3
"""
Position tracking for the execution subsystem.

Persists open position state to disk so it survives restarts.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from btc_basis.utils.logging import LoggingMixin


@dataclass
class Position:
    """Current open position state."""

    etf_shares: int = 0
    etf_symbol: str = "IBIT"
    etf_entry_price: float = 0.0
    futures_contracts: int = 0
    futures_symbol: str = "MBT"
    futures_entry_price: float = 0.0
    futures_expiry: Optional[str] = None
    opened_at: Optional[str] = None

    @property
    def is_open(self) -> bool:
        """Whether any position is open."""
        return self.etf_shares > 0 or self.futures_contracts > 0

    @property
    def is_balanced(self) -> bool:
        """Whether both legs are open (roughly balanced)."""
        return self.etf_shares > 0 and self.futures_contracts > 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "etf_shares": self.etf_shares,
            "etf_symbol": self.etf_symbol,
            "etf_entry_price": self.etf_entry_price,
            "futures_contracts": self.futures_contracts,
            "futures_symbol": self.futures_symbol,
            "futures_entry_price": self.futures_entry_price,
            "futures_expiry": self.futures_expiry,
            "opened_at": self.opened_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        """Create Position from dictionary."""
        return cls(
            etf_shares=data.get("etf_shares", 0),
            etf_symbol=data.get("etf_symbol", "IBIT"),
            etf_entry_price=data.get("etf_entry_price", 0.0),
            futures_contracts=data.get("futures_contracts", 0),
            futures_symbol=data.get("futures_symbol", "MBT"),
            futures_entry_price=data.get("futures_entry_price", 0.0),
            futures_expiry=data.get("futures_expiry"),
            opened_at=data.get("opened_at"),
        )


class PositionTracker(LoggingMixin):
    """Load, save, and manage persisted position state."""

    DEFAULT_PATH = "output/execution/position_state.json"

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or self.DEFAULT_PATH)
        self.position = self.load()

    def load(self) -> Position:
        """Load position from disk, or return empty position."""
        if self.path.exists():
            try:
                with open(self.path, "r") as f:
                    data = json.load(f)
                pos = Position.from_dict(data)
                if pos.is_open:
                    self.log(
                        f"Loaded open position: {pos.etf_shares} {pos.etf_symbol} shares, "
                        f"{pos.futures_contracts} {pos.futures_symbol} contracts"
                    )
                return pos
            except (json.JSONDecodeError, KeyError) as e:
                self.log_warning(f"Failed to load position state: {e}")
        return Position()

    def save(self) -> None:
        """Persist current position to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.position.to_dict(), f, indent=2)
        self.log_debug(f"Position saved to {self.path}")

    def update_on_entry(
        self,
        etf_shares: int,
        etf_price: float,
        futures_contracts: int,
        futures_price: float,
        etf_symbol: str = "IBIT",
        futures_symbol: str = "MBT",
        futures_expiry: Optional[str] = None,
    ) -> None:
        """Update position after an entry fill."""
        self.position = Position(
            etf_shares=etf_shares,
            etf_symbol=etf_symbol,
            etf_entry_price=etf_price,
            futures_contracts=futures_contracts,
            futures_symbol=futures_symbol,
            futures_entry_price=futures_price,
            futures_expiry=futures_expiry,
            opened_at=datetime.now().isoformat(),
        )
        self.save()

    def update_on_partial_exit(self, etf_shares_sold: int, contracts_closed: int) -> None:
        """Reduce position after partial exit."""
        self.position.etf_shares = max(0, self.position.etf_shares - etf_shares_sold)
        self.position.futures_contracts = max(
            0, self.position.futures_contracts - contracts_closed
        )
        if not self.position.is_open:
            self.clear()
        else:
            self.save()

    def clear(self) -> None:
        """Clear position (full exit)."""
        self.position = Position()
        self.save()
        self.log("Position cleared")
