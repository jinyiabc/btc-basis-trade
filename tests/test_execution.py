#!/usr/bin/env python3
"""
Tests for the execution subsystem.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from btc_basis.core.models import Signal, TradeConfig, MarketData
from btc_basis.core.analyzer import BasisTradeAnalyzer
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
from btc_basis.execution.manager import ExecutionManager


# ---------------------------------------------------------------------------
# ExecutionConfig
# ---------------------------------------------------------------------------


class TestExecutionConfig:
    def test_from_dict_defaults(self):
        cfg = ExecutionConfig.from_dict({})
        assert cfg.enabled is False
        assert cfg.auto_trade is False
        assert cfg.spot_symbol == "IBIT"
        assert cfg.futures_symbol == "MBT"
        assert cfg.order_type == "limit"
        assert cfg.limit_offset_pct == 0.001
        assert cfg.max_etf_shares == 10000
        assert cfg.max_futures_contracts == 50
        assert cfg.execution_client_id == 2
        assert cfg.dry_run is True

    def test_from_dict_overrides(self):
        cfg = ExecutionConfig.from_dict({
            "enabled": True,
            "auto_trade": True,
            "spot_symbol": "FBTC",
            "futures_symbol": "BTC",
            "order_type": "market",
            "limit_offset_pct": 0.002,
            "max_etf_shares": 5000,
            "max_futures_contracts": 20,
            "execution_client_id": 5,
            "dry_run": False,
        })
        assert cfg.enabled is True
        assert cfg.auto_trade is True
        assert cfg.spot_symbol == "FBTC"
        assert cfg.futures_symbol == "BTC"
        assert cfg.order_type == "market"
        assert cfg.limit_offset_pct == 0.002
        assert cfg.max_etf_shares == 5000
        assert cfg.max_futures_contracts == 20
        assert cfg.execution_client_id == 5
        assert cfg.dry_run is False

    def test_to_dict_roundtrip(self):
        original = ExecutionConfig(enabled=True, spot_symbol="FBTC")
        rebuilt = ExecutionConfig.from_dict(original.to_dict())
        assert rebuilt.enabled == original.enabled
        assert rebuilt.spot_symbol == original.spot_symbol


# ---------------------------------------------------------------------------
# OrderRequest
# ---------------------------------------------------------------------------


class TestOrderRequest:
    def test_describe_market(self):
        req = OrderRequest(
            side=OrderSide.BUY,
            symbol="IBIT",
            quantity=100,
            order_type=OrderType.MARKET,
        )
        desc = req.describe()
        assert "BUY" in desc
        assert "100" in desc
        assert "IBIT" in desc
        assert "MARKET" in desc

    def test_describe_limit(self):
        req = OrderRequest(
            side=OrderSide.SELL,
            symbol="MBT",
            quantity=3,
            order_type=OrderType.LIMIT,
            limit_price=97500.00,
        )
        desc = req.describe()
        assert "SELL" in desc
        assert "MBT" in desc
        assert "LIMIT" in desc
        assert "97,500.00" in desc


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------


class TestPosition:
    def test_empty_position(self):
        pos = Position()
        assert pos.is_open is False
        assert pos.is_balanced is False

    def test_open_position(self):
        pos = Position(etf_shares=100, futures_contracts=2)
        assert pos.is_open is True
        assert pos.is_balanced is True

    def test_unbalanced_position(self):
        pos = Position(etf_shares=100, futures_contracts=0)
        assert pos.is_open is True
        assert pos.is_balanced is False

    def test_roundtrip(self):
        pos = Position(
            etf_shares=200,
            etf_symbol="FBTC",
            etf_entry_price=55.0,
            futures_contracts=3,
            futures_symbol="BTC",
            futures_entry_price=98000.0,
            futures_expiry="202603",
            opened_at="2026-01-15T10:30:00",
        )
        rebuilt = Position.from_dict(pos.to_dict())
        assert rebuilt.etf_shares == 200
        assert rebuilt.futures_symbol == "BTC"
        assert rebuilt.opened_at == "2026-01-15T10:30:00"


# ---------------------------------------------------------------------------
# PositionTracker
# ---------------------------------------------------------------------------


class TestPositionTracker:
    def test_save_load_cycle(self, tmp_path):
        path = str(tmp_path / "pos.json")
        tracker = PositionTracker(path=path)
        assert tracker.position.is_open is False

        tracker.update_on_entry(
            etf_shares=100,
            etf_price=55.0,
            futures_contracts=2,
            futures_price=97000.0,
            futures_expiry="202603",
        )
        assert tracker.position.is_open is True

        # Reload from disk
        tracker2 = PositionTracker(path=path)
        assert tracker2.position.etf_shares == 100
        assert tracker2.position.futures_contracts == 2

    def test_clear(self, tmp_path):
        path = str(tmp_path / "pos.json")
        tracker = PositionTracker(path=path)
        tracker.update_on_entry(
            etf_shares=50, etf_price=55.0,
            futures_contracts=1, futures_price=97000.0,
        )
        assert tracker.position.is_open is True

        tracker.clear()
        assert tracker.position.is_open is False

        # Verify on disk too
        tracker3 = PositionTracker(path=path)
        assert tracker3.position.is_open is False

    def test_partial_exit(self, tmp_path):
        path = str(tmp_path / "pos.json")
        tracker = PositionTracker(path=path)
        tracker.update_on_entry(
            etf_shares=100, etf_price=55.0,
            futures_contracts=4, futures_price=97000.0,
        )

        tracker.update_on_partial_exit(etf_shares_sold=50, contracts_closed=2)
        assert tracker.position.etf_shares == 50
        assert tracker.position.futures_contracts == 2

    def test_partial_exit_to_zero_clears(self, tmp_path):
        path = str(tmp_path / "pos.json")
        tracker = PositionTracker(path=path)
        tracker.update_on_entry(
            etf_shares=100, etf_price=55.0,
            futures_contracts=2, futures_price=97000.0,
        )

        tracker.update_on_partial_exit(etf_shares_sold=100, contracts_closed=2)
        assert tracker.position.is_open is False


# ---------------------------------------------------------------------------
# ExecutionManager._determine_action
# ---------------------------------------------------------------------------


class TestDetermineAction:
    """Test signal × position-state → action mapping."""

    def _make_manager(self, tmp_path, has_position=False):
        cfg = ExecutionConfig(enabled=True, dry_run=True)
        analyzer = BasisTradeAnalyzer(TradeConfig())
        mgr = ExecutionManager(
            exec_config=cfg,
            analyzer=analyzer,
        )
        # Override tracker with temp path
        mgr.tracker = PositionTracker(path=str(tmp_path / "pos.json"))
        mgr.executor.tracker = mgr.tracker

        if has_position:
            mgr.tracker.update_on_entry(
                etf_shares=100, etf_price=55.0,
                futures_contracts=2, futures_price=97000.0,
            )
        return mgr

    def test_entry_no_position(self, tmp_path):
        mgr = self._make_manager(tmp_path, has_position=False)
        assert mgr._determine_action(Signal.STRONG_ENTRY) == TradeAction.OPEN
        assert mgr._determine_action(Signal.ACCEPTABLE_ENTRY) == TradeAction.OPEN

    def test_entry_with_position(self, tmp_path):
        mgr = self._make_manager(tmp_path, has_position=True)
        assert mgr._determine_action(Signal.STRONG_ENTRY) == TradeAction.NONE
        assert mgr._determine_action(Signal.ACCEPTABLE_ENTRY) == TradeAction.NONE

    def test_exit_with_position(self, tmp_path):
        mgr = self._make_manager(tmp_path, has_position=True)
        assert mgr._determine_action(Signal.FULL_EXIT) == TradeAction.CLOSE
        assert mgr._determine_action(Signal.STOP_LOSS) == TradeAction.CLOSE

    def test_exit_no_position(self, tmp_path):
        mgr = self._make_manager(tmp_path, has_position=False)
        assert mgr._determine_action(Signal.FULL_EXIT) == TradeAction.NONE
        assert mgr._determine_action(Signal.STOP_LOSS) == TradeAction.NONE

    def test_partial_exit_with_position(self, tmp_path):
        mgr = self._make_manager(tmp_path, has_position=True)
        assert mgr._determine_action(Signal.PARTIAL_EXIT) == TradeAction.REDUCE

    def test_partial_exit_no_position(self, tmp_path):
        mgr = self._make_manager(tmp_path, has_position=False)
        assert mgr._determine_action(Signal.PARTIAL_EXIT) == TradeAction.NONE

    def test_no_entry_always_none(self, tmp_path):
        mgr = self._make_manager(tmp_path, has_position=False)
        assert mgr._determine_action(Signal.NO_ENTRY) == TradeAction.NONE

    def test_hold_always_none(self, tmp_path):
        mgr = self._make_manager(tmp_path, has_position=True)
        assert mgr._determine_action(Signal.HOLD) == TradeAction.NONE


# ---------------------------------------------------------------------------
# ExecutionManager._safety_checks
# ---------------------------------------------------------------------------


class TestSafetyChecks:
    def _make_manager(self, tmp_path):
        cfg = ExecutionConfig(
            enabled=True, dry_run=True,
            max_etf_shares=500, max_futures_contracts=10,
        )
        analyzer = BasisTradeAnalyzer(TradeConfig())
        mgr = ExecutionManager(exec_config=cfg, analyzer=analyzer)
        mgr.tracker = PositionTracker(path=str(tmp_path / "pos.json"))
        return mgr

    def _make_market(self, monthly_basis_pct=1.0):
        """Create market data with a given monthly basis (approx)."""
        spot = 95000.0
        # monthly_basis = basis_percent * (30/days_to_expiry)
        # basis_percent = monthly_basis * days_to_expiry / 30
        days = 30
        basis_pct = monthly_basis_pct / 100 * days / 30
        futures = spot * (1 + basis_pct)
        return MarketData(
            spot_price=spot,
            futures_price=futures,
            futures_expiry_date=datetime.now() + timedelta(days=days),
            etf_price=53.50,
        )

    def test_etf_shares_limit(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        market = self._make_market()
        sizing = {"etf_shares": 600, "futures_contracts": 5}
        result = mgr._safety_checks(TradeAction.OPEN, sizing, market)
        assert result is not None
        assert "ETF shares" in result

    def test_futures_contracts_limit(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        market = self._make_market()
        sizing = {"etf_shares": 100, "futures_contracts": 15}
        result = mgr._safety_checks(TradeAction.OPEN, sizing, market)
        assert result is not None
        assert "Futures contracts" in result

    def test_backwardation_guard(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        market = self._make_market(monthly_basis_pct=-0.5)
        sizing = {"etf_shares": 100, "futures_contracts": 2}
        result = mgr._safety_checks(TradeAction.OPEN, sizing, market)
        assert result is not None
        assert "Backwardation" in result

    def test_passes_when_ok(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        market = self._make_market(monthly_basis_pct=1.0)
        sizing = {"etf_shares": 100, "futures_contracts": 2}
        result = mgr._safety_checks(TradeAction.OPEN, sizing, market)
        # Could be None (pass) or weekend error depending on day of week
        if datetime.now().weekday() < 5:
            assert result is None
        else:
            assert "Weekend" in result


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_returns_pending(self):
        from btc_basis.execution.executor import IBKRExecutor

        cfg = ExecutionConfig(enabled=True, dry_run=True)
        executor = IBKRExecutor(config=cfg)

        req = OrderRequest(
            side=OrderSide.BUY,
            symbol="IBIT",
            quantity=100,
            order_type=OrderType.MARKET,
        )
        result = executor.execute_order(req)
        assert result.status == OrderStatus.PENDING
        assert "Dry run" in result.error

    def test_dry_run_connect_skips(self):
        from btc_basis.execution.executor import IBKRExecutor

        cfg = ExecutionConfig(enabled=True, dry_run=True)
        executor = IBKRExecutor(config=cfg)
        assert executor.connect() is True
        assert executor.connected is False  # not actually connected


# ---------------------------------------------------------------------------
# OrderResult.to_dict
# ---------------------------------------------------------------------------


class TestOrderResult:
    def test_to_dict(self):
        req = OrderRequest(
            side=OrderSide.BUY,
            symbol="IBIT",
            quantity=100,
        )
        result = OrderResult(
            status=OrderStatus.FILLED,
            order_request=req,
            fill_price=55.10,
            filled_qty=100,
            commission=1.50,
        )
        d = result.to_dict()
        assert d["status"] == "FILLED"
        assert d["side"] == "BUY"
        assert d["symbol"] == "IBIT"
        assert d["fill_price"] == 55.10
        assert d["commission"] == 1.50
        assert "timestamp" in d
