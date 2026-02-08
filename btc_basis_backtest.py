#!/usr/bin/env python3
"""
Bitcoin Basis Trade Backtester

Simulates basis trade strategy performance using historical data.
Tests entry/exit signals and calculates realized returns.

Usage:
    python btc_basis_backtest.py --data historical_basis.csv
    python btc_basis_backtest.py --start 2024-01-01 --end 2024-12-31
"""

import argparse
import csv
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from btc_basis_trade_analyzer import (
    BasisTradeAnalyzer,
    MarketData,
    TradeConfig,
    Signal
)


@dataclass
class Trade:
    """Represents a single basis trade"""
    entry_date: datetime
    entry_spot: float
    entry_futures: float
    entry_basis: float
    exit_date: Optional[datetime] = None
    exit_spot: Optional[float] = None
    exit_futures: Optional[float] = None
    exit_basis: Optional[float] = None
    position_size: float = 1.0
    funding_cost: float = 0.0
    realized_pnl: Optional[float] = None
    status: str = "open"  # open, closed, stopped_out

    @property
    def holding_days(self) -> int:
        if self.exit_date:
            return (self.exit_date - self.entry_date).days
        return 0

    @property
    def return_pct(self) -> Optional[float]:
        if self.realized_pnl:
            return self.realized_pnl / (self.entry_spot * self.position_size)
        return None

    @property
    def annualized_return(self) -> Optional[float]:
        if self.return_pct and self.holding_days > 0:
            return self.return_pct * (365 / self.holding_days)
        return None


@dataclass
class BacktestResult:
    """Results from backtesting"""
    trades: List[Trade] = field(default_factory=list)
    total_return: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    initial_capital: float = 200000

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    @property
    def profit_factor(self) -> float:
        if abs(self.avg_loss) < 0.0001:
            return float('inf')
        return abs(self.avg_win / self.avg_loss)

    @property
    def final_capital(self) -> float:
        return self.initial_capital * (1 + self.total_return)

    def to_dict(self) -> Dict:
        return {
            'summary': {
                'initial_capital': self.initial_capital,
                'final_capital': self.final_capital,
                'total_return': self.total_return * 100,
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
                'win_rate': self.win_rate * 100,
                'avg_win': self.avg_win * 100,
                'avg_loss': self.avg_loss * 100,
                'profit_factor': self.profit_factor,
                'max_drawdown': self.max_drawdown * 100,
                'sharpe_ratio': self.sharpe_ratio,
                'start_date': self.start_date.isoformat() if self.start_date else None,
                'end_date': self.end_date.isoformat() if self.end_date else None
            },
            'trades': [
                {
                    'entry_date': t.entry_date.isoformat(),
                    'exit_date': t.exit_date.isoformat() if t.exit_date else None,
                    'entry_basis': t.entry_basis,
                    'exit_basis': t.exit_basis,
                    'holding_days': t.holding_days,
                    'return_pct': t.return_pct * 100 if t.return_pct else None,
                    'annualized_return': t.annualized_return * 100 if t.annualized_return else None,
                    'status': t.status
                }
                for t in self.trades
            ]
        }


class Backtester:
    """Backtesting engine for basis trade strategy"""

    def __init__(self, config: TradeConfig = TradeConfig()):
        self.config = config
        self.analyzer = BasisTradeAnalyzer(config)

    def load_historical_data(self, csv_path: str) -> List[Dict]:
        """Load historical basis data from CSV"""
        data = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append({
                    'date': datetime.fromisoformat(row['date']),
                    'spot_price': float(row['spot_price']),
                    'futures_price': float(row['futures_price']),
                    'futures_expiry': datetime.fromisoformat(row['futures_expiry'])
                })
        return data

    def generate_sample_data(self, start_date: datetime, end_date: datetime,
                            base_price: float = 50000) -> List[Dict]:
        """Generate synthetic data for testing"""
        data = []
        current_date = start_date
        price = base_price

        while current_date <= end_date:
            # Simulate price movement (random walk)
            import random
            price_change = random.gauss(0, 0.02) * price
            price = max(10000, price + price_change)

            # Simulate basis (typically positive, occasionally negative)
            basis_pct = max(-0.01, random.gauss(0.015, 0.01))  # ~1.5% avg
            futures_price = price * (1 + basis_pct)

            # Futures expiry (30 days out, roll monthly)
            expiry_date = current_date + timedelta(days=30)

            data.append({
                'date': current_date,
                'spot_price': price,
                'futures_price': futures_price,
                'futures_expiry': expiry_date
            })

            current_date += timedelta(days=1)

        return data

    def run_backtest(self, historical_data: List[Dict],
                    max_holding_days: int = 30) -> BacktestResult:
        """Run backtest on historical data"""
        result = BacktestResult(initial_capital=self.config.account_size)
        current_trade: Optional[Trade] = None
        equity_curve = [result.initial_capital]
        daily_returns = []

        result.start_date = historical_data[0]['date']
        result.end_date = historical_data[-1]['date']

        for i, data_point in enumerate(historical_data):
            market = MarketData(
                spot_price=data_point['spot_price'],
                futures_price=data_point['futures_price'],
                futures_expiry_date=data_point['futures_expiry'],
                as_of_date=data_point['date']  # Use historical date for backtest
            )

            signal, reason = self.analyzer.generate_signal(market)

            # Check if we have an open trade
            if current_trade:
                # Check holding period
                holding_days = (data_point['date'] - current_trade.entry_date).days

                # Exit conditions
                should_exit = False
                exit_reason = ""

                if signal in [Signal.STOP_LOSS, Signal.FULL_EXIT]:
                    should_exit = True
                    exit_reason = "Signal: " + signal.value
                    current_trade.status = "stopped_out" if signal == Signal.STOP_LOSS else "closed"
                elif holding_days >= max_holding_days:
                    should_exit = True
                    exit_reason = f"Max holding period ({max_holding_days} days)"
                    current_trade.status = "closed"

                if should_exit:
                    # Close trade
                    current_trade.exit_date = data_point['date']
                    current_trade.exit_spot = market.spot_price
                    current_trade.exit_futures = market.futures_price
                    current_trade.exit_basis = market.basis_absolute

                    # Calculate P&L
                    # Long spot, short futures
                    spot_pnl = (current_trade.exit_spot - current_trade.entry_spot) * current_trade.position_size
                    futures_pnl = (current_trade.entry_futures - current_trade.exit_futures) * current_trade.position_size

                    # Funding cost
                    holding_days_actual = (current_trade.exit_date - current_trade.entry_date).days
                    funding_cost = (self.config.funding_cost_annual / 365) * holding_days_actual * \
                                  (current_trade.entry_spot * current_trade.position_size)

                    current_trade.realized_pnl = spot_pnl + futures_pnl - funding_cost

                    # Update equity
                    equity_curve.append(equity_curve[-1] + current_trade.realized_pnl)

                    # Track daily return
                    if len(equity_curve) > 1:
                        daily_return = (equity_curve[-1] - equity_curve[-2]) / equity_curve[-2]
                        daily_returns.append(daily_return)

                    # Add to results
                    result.trades.append(current_trade)
                    current_trade = None

            # Entry conditions (no open trade)
            if current_trade is None:
                if signal in [Signal.STRONG_ENTRY, Signal.ACCEPTABLE_ENTRY]:
                    # Open new trade
                    position_size = 1.0  # 1 BTC equivalent
                    current_trade = Trade(
                        entry_date=data_point['date'],
                        entry_spot=market.spot_price,
                        entry_futures=market.futures_price,
                        entry_basis=market.basis_absolute,
                        position_size=position_size
                    )

        # Close any remaining open trade at end of backtest
        if current_trade:
            last_data = historical_data[-1]
            current_trade.exit_date = last_data['date']
            current_trade.exit_spot = last_data['spot_price']
            current_trade.exit_futures = last_data['futures_price']
            current_trade.status = "forced_close"

            spot_pnl = (current_trade.exit_spot - current_trade.entry_spot) * current_trade.position_size
            futures_pnl = (current_trade.entry_futures - current_trade.exit_futures) * current_trade.position_size
            holding_days_actual = (current_trade.exit_date - current_trade.entry_date).days
            funding_cost = (self.config.funding_cost_annual / 365) * holding_days_actual * \
                          (current_trade.entry_spot * current_trade.position_size)
            current_trade.realized_pnl = spot_pnl + futures_pnl - funding_cost

            result.trades.append(current_trade)

        # Calculate statistics
        result.total_trades = len(result.trades)

        if result.total_trades > 0:
            wins = [t for t in result.trades if t.realized_pnl and t.realized_pnl > 0]
            losses = [t for t in result.trades if t.realized_pnl and t.realized_pnl < 0]

            result.winning_trades = len(wins)
            result.losing_trades = len(losses)

            if wins:
                result.avg_win = sum(t.return_pct for t in wins if t.return_pct) / len(wins)
            if losses:
                result.avg_loss = sum(t.return_pct for t in losses if t.return_pct) / len(losses)

            # Total return
            result.total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]

            # Max drawdown
            peak = equity_curve[0]
            max_dd = 0
            for equity in equity_curve:
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd
            result.max_drawdown = max_dd

            # Sharpe ratio (annualized)
            if daily_returns:
                import statistics
                avg_return = statistics.mean(daily_returns)
                std_return = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0
                if std_return > 0:
                    result.sharpe_ratio = (avg_return / std_return) * (365 ** 0.5)

        return result

    def generate_report(self, result: BacktestResult) -> str:
        """Generate backtest report"""
        report = f"""
{'='*70}
BITCOIN BASIS TRADE BACKTEST RESULTS
{'='*70}

[*] Period: {result.start_date.strftime('%Y-%m-%d') if result.start_date else 'N/A'} to {result.end_date.strftime('%Y-%m-%d') if result.end_date else 'N/A'}

[*] PERFORMANCE SUMMARY
{'-'*70}
Initial Capital:      ${result.initial_capital:,.2f}
Final Capital:        ${result.final_capital:,.2f}
Total Return:         {result.total_return*100:,.2f}%
Max Drawdown:         {result.max_drawdown*100:.2f}%
Sharpe Ratio:         {result.sharpe_ratio:.2f}

[*] TRADE STATISTICS
{'-'*70}
Total Trades:         {result.total_trades}
Winning Trades:       {result.winning_trades} ({result.win_rate*100:.1f}%)
Losing Trades:        {result.losing_trades}
Average Win:          {result.avg_win*100:.2f}%
Average Loss:         {result.avg_loss*100:.2f}%
Profit Factor:        {result.profit_factor:.2f}

[*] TRADE DETAILS
{'-'*70}
"""
        for i, trade in enumerate(result.trades, 1):
            status_symbol = "[+]" if trade.realized_pnl and trade.realized_pnl > 0 else "[-]"
            report += f"{i}. {status_symbol} {trade.entry_date.strftime('%Y-%m-%d')}"
            if trade.exit_date:
                report += f" → {trade.exit_date.strftime('%Y-%m-%d')} ({trade.holding_days}d)"
            report += f" | Basis: {trade.entry_basis/trade.entry_spot*100:.2f}%"
            if trade.return_pct:
                report += f" | Return: {trade.return_pct*100:+.2f}%"
            report += f" | {trade.status}\n"

        report += f"\n{'='*70}\n"
        return report


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Bitcoin Basis Trade Backtester')
    parser.add_argument('--data', type=str, help='Path to historical CSV data')
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--holding-days', type=int, default=30,
                       help='Max holding period in days (default: 30)')
    parser.add_argument('--output', type=str, help='Output JSON file path')
    args = parser.parse_args()

    config = TradeConfig()
    backtester = Backtester(config)

    # Load or generate data
    if args.data:
        print(f"Loading historical data from {args.data}...")
        historical_data = backtester.load_historical_data(args.data)
    else:
        print("Generating sample data...")
        start = datetime.fromisoformat(args.start) if args.start else datetime(2024, 1, 1)
        end = datetime.fromisoformat(args.end) if args.end else datetime(2024, 12, 31)
        historical_data = backtester.generate_sample_data(start, end)

    print(f"Running backtest on {len(historical_data)} data points...")
    result = backtester.run_backtest(historical_data, max_holding_days=args.holding_days)

    # Print report
    report = backtester.generate_report(result)
    print(report)

    # Save to file
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"Results saved to {args.output}")
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_file = f"backtest_result_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"Results saved to {json_file}")


if __name__ == "__main__":
    main()
