"""Run one deterministic, offline, single-symbol CSV backtest."""

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

# Make the documented module command work from a source checkout without install.
_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from trading_bot.analytics import PerformanceAnalyzer, PerformanceReport  # noqa: E402
from trading_bot.backtesting import (  # noqa: E402
    BacktestConfig,
    BacktestEngine,
    BacktestResult,
)
from trading_bot.domain import Symbol  # noqa: E402
from trading_bot.market_calendar import NYSEMarketCalendar  # noqa: E402
from trading_bot.market_data import (  # noqa: E402
    AdjustmentType,
    CSVHistoricalDataProvider,
    HistoricalDataRequest,
    Timeframe,
)
from trading_bot.risk import RiskLimits, RiskOutcome  # noqa: E402
from trading_bot.strategies import (  # noqa: E402
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
)

REPORT_SCHEMA_VERSION = 2


def _decimal_argument(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError("must be a decimal number") from error
    if not parsed.is_finite():
        raise argparse.ArgumentTypeError("must be finite")
    return parsed


def _datetime_argument(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("must include a timezone offset")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build the public command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Run a deterministic offline moving-average backtest."
    )
    parser.add_argument("--csv-root", required=True, type=Path)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True, type=_datetime_argument)
    parser.add_argument("--end", required=True, type=_datetime_argument)
    parser.add_argument("--short-window", required=True, type=int)
    parser.add_argument("--long-window", required=True, type=int)
    parser.add_argument("--quantity", required=True, type=_decimal_argument)
    parser.add_argument(
        "--starting-cash", type=_decimal_argument, default=Decimal("10000")
    )
    parser.add_argument("--commission", type=_decimal_argument, default=Decimal("0"))
    parser.add_argument("--slippage-bps", type=_decimal_argument, default=Decimal("0"))
    parser.add_argument("--run-id", type=UUID)
    parser.add_argument("--allow-missing-sessions", action="store_true")
    parser.add_argument("--json-report", type=Path)
    return parser


def _canonical_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _derived_run_id(args: argparse.Namespace, symbol: Symbol) -> UUID:
    identity = "|".join(
        (
            str(args.csv_root.resolve()),
            str(symbol),
            args.start.isoformat(),
            args.end.isoformat(),
            str(args.short_window),
            str(args.long_window),
            _canonical_decimal(args.quantity),
            _canonical_decimal(args.starting_cash),
            _canonical_decimal(args.commission),
            _canonical_decimal(args.slippage_bps),
            str(args.allow_missing_sessions),
        )
    )
    return uuid5(NAMESPACE_URL, f"offline-backtest:{identity}")


def _summary(result: BacktestResult, performance: PerformanceReport) -> dict[str, Any]:
    final_snapshot = result.account_snapshots[-1]
    symbol = result.config.data_request.symbol
    position = result.final_positions.get(symbol)
    counts = {outcome: 0 for outcome in RiskOutcome}
    for decision in result.risk_decisions:
        counts[decision.outcome] += 1
    return {
        "symbol": str(symbol),
        "bars_processed": len(result.bars),
        "starting_cash": str(result.config.starting_cash),
        "final_cash": str(final_snapshot.cash),
        "final_equity": str(final_snapshot.equity),
        "realized_profit_loss": str(final_snapshot.realized_profit_loss),
        "unrealized_profit_loss": str(final_snapshot.unrealized_profit_loss),
        "proposal_count": len(result.proposals),
        "fill_count": len(result.fills),
        "approved_risk_decision_count": counts[RiskOutcome.APPROVED],
        "resized_risk_decision_count": counts[RiskOutcome.RESIZED],
        "rejected_risk_decision_count": counts[RiskOutcome.REJECTED],
        "unexecuted_end_of_data_proposal_count": len(
            result.unexecuted_final_bar_proposals
        ),
        "final_position": (
            None
            if position is None
            else {
                "symbol": str(position.symbol),
                "quantity": str(position.quantity),
                "average_cost": str(position.average_cost),
            }
        ),
        "total_return": str(performance.total_return),
        "absolute_profit_loss": str(performance.absolute_profit_loss),
        "maximum_drawdown_amount": str(performance.maximum_drawdown_amount),
        "maximum_drawdown_percentage": str(performance.maximum_drawdown_percentage),
        "closed_trade_count": performance.closed_trade_count,
        "winning_trade_count": performance.winning_trade_count,
        "losing_trade_count": performance.losing_trade_count,
        "breakeven_trade_count": performance.breakeven_trade_count,
        "win_rate": str(performance.win_rate),
        "gross_profit": str(performance.gross_profit),
        "gross_loss": str(performance.gross_loss),
        "average_winning_trade": str(performance.average_winning_trade),
        "average_losing_trade": str(performance.average_losing_trade),
        "profit_factor": (
            None
            if performance.profit_factor is None
            else str(performance.profit_factor)
        ),
        "turnover": str(performance.turnover),
        "average_gross_exposure": str(performance.average_gross_exposure),
        "maximum_gross_exposure": str(performance.maximum_gross_exposure),
        "time_in_market_percentage": str(performance.time_in_market_percentage),
    }


def build_json_report(
    result: BacktestResult,
    strategy_config: MovingAverageCrossoverConfig,
    performance: PerformanceReport | None = None,
) -> dict[str, Any]:
    """Build the deliberate versioned public report schema."""
    performance = performance or PerformanceAnalyzer().analyze(result)
    summary = _summary(result, performance)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "configuration": {
            "run_id": str(result.config.run_id),
            "provider_name": result.provider_name,
            "symbol": str(result.config.data_request.symbol),
            "start": result.config.data_request.start.isoformat(),
            "end": result.config.data_request.end.isoformat(),
            "timeframe": result.config.data_request.timeframe.value,
            "adjustment": result.config.data_request.adjustment.value,
            "short_window": strategy_config.short_window,
            "long_window": strategy_config.long_window,
            "desired_quantity": str(strategy_config.desired_quantity),
            "starting_cash": str(result.config.starting_cash),
            "fixed_commission": str(result.config.fixed_commission),
            "slippage_basis_points": str(result.config.slippage_basis_points),
            "allow_missing_sessions": result.config.allow_missing_sessions,
        },
        "summary": summary,
        "final_positions": [
            {
                "symbol": str(position.symbol),
                "quantity": str(position.quantity),
                "average_cost": str(position.average_cost),
            }
            for position in result.final_positions.values()
        ],
        "proposals": [
            {
                "proposal_id": str(proposal.proposal_id),
                "symbol": str(proposal.symbol),
                "side": proposal.side.value,
                "desired_quantity": str(proposal.desired_quantity),
                "created_at": proposal.created_at.isoformat(),
                "reason": proposal.reason,
            }
            for proposal in result.proposals
        ],
        "risk_decisions": [
            {
                "proposal_id": str(decision.proposal.proposal_id),
                "outcome": decision.outcome.value,
                "approved_quantity": str(decision.approved_quantity),
                "evaluated_at": decision.evaluated_at.isoformat(),
                "reasons": [
                    {
                        "code": reason.code.value,
                        "message": reason.message,
                        "observed": None
                        if reason.observed is None
                        else str(reason.observed),
                        "limit": None if reason.limit is None else str(reason.limit),
                    }
                    for reason in decision.reasons
                ],
            }
            for decision in result.risk_decisions
        ],
        "fills": [
            {
                "fill_id": str(fill.fill_id),
                "order_id": str(fill.order_id),
                "symbol": str(fill.symbol),
                "side": fill.side.value,
                "quantity": str(fill.quantity),
                "price": str(fill.price),
                "commission": str(fill.commission),
                "filled_at": fill.filled_at.isoformat(),
            }
            for fill in result.fills
        ],
        "equity_history": [
            {
                "timestamp": snapshot.timestamp.isoformat(),
                "cash": str(snapshot.cash),
                "positions_market_value": str(snapshot.positions_market_value),
                "equity": str(snapshot.equity),
                "realized_profit_loss": str(snapshot.realized_profit_loss),
                "unrealized_profit_loss": str(snapshot.unrealized_profit_loss),
            }
            for snapshot in result.account_snapshots
        ],
        "performance": _performance_json(performance),
    }


def _drawdown_json(record: Any) -> dict[str, str]:
    return {
        "peak_timestamp": record.peak_timestamp.isoformat(),
        "trough_timestamp": record.trough_timestamp.isoformat(),
        "peak_equity": str(record.peak_equity),
        "trough_equity": str(record.trough_equity),
        "amount": str(record.amount),
        "percentage": str(record.percentage),
    }


def _performance_json(performance: PerformanceReport) -> dict[str, Any]:
    return {
        "total_return": str(performance.total_return),
        "absolute_profit_loss": str(performance.absolute_profit_loss),
        "drawdowns": {
            "maximum_amount": _drawdown_json(performance.drawdowns.maximum_amount),
            "maximum_percentage": _drawdown_json(
                performance.drawdowns.maximum_percentage
            ),
        },
        "trade_statistics": {
            "closed_trade_count": performance.closed_trade_count,
            "winning_trade_count": performance.winning_trade_count,
            "losing_trade_count": performance.losing_trade_count,
            "breakeven_trade_count": performance.breakeven_trade_count,
            "win_rate": str(performance.win_rate),
            "gross_profit": str(performance.gross_profit),
            "gross_loss": str(performance.gross_loss),
            "average_winning_trade": str(performance.average_winning_trade),
            "average_losing_trade": str(performance.average_losing_trade),
            "profit_factor": (
                None
                if performance.profit_factor is None
                else str(performance.profit_factor)
            ),
        },
        "turnover": str(performance.turnover),
        "average_gross_exposure": str(performance.average_gross_exposure),
        "maximum_gross_exposure": str(performance.maximum_gross_exposure),
        "time_in_market_percentage": str(performance.time_in_market_percentage),
        "trade_realizations": [
            {
                "symbol": str(item.symbol),
                "quantity": str(item.quantity),
                "average_entry_cost": str(item.average_entry_cost),
                "entry_cost_basis": str(item.entry_cost_basis),
                "exit_price": str(item.exit_price),
                "gross_proceeds": str(item.gross_proceeds),
                "exit_commission": str(item.exit_commission),
                "net_profit_loss": str(item.net_profit_loss),
                "entry_started_at": item.entry_started_at.isoformat(),
                "closed_at": item.closed_at.isoformat(),
                "exit_fill_id": str(item.exit_fill_id),
            }
            for item in performance.trade_realizations
        ],
    }


def _print_summary(summary: dict[str, Any]) -> None:
    for key, value in summary.items():
        if key == "final_position":
            rendered = (
                "flat"
                if value is None
                else f"{value['quantity']} @ {value['average_cost']}"
            )
        elif key == "profit_factor" and value is None:
            rendered = (
                "undefined (no profit-or-loss activity)"
                if summary["gross_profit"] == "0" and summary["gross_loss"] == "0"
                else "undefined (no gross loss)"
            )
        else:
            rendered = value
        print(f"{key.replace('_', ' ')}: {rendered}")


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the offline backtest, and report the result."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        symbol = Symbol(args.symbol)
        strategy_config = MovingAverageCrossoverConfig(
            args.short_window, args.long_window, args.quantity
        )
        request = HistoricalDataRequest(
            symbol,
            args.start,
            args.end,
            Timeframe.DAY_1,
            AdjustmentType.RAW,
        )
        limits = RiskLimits(
            max_position_percent=Decimal("0.20"),
            max_total_exposure_percent=Decimal("0.80"),
            max_order_notional=None,
            max_new_position_percent=Decimal("0.10"),
            minimum_cash_reserve_percent=Decimal("0.10"),
            allow_fractional_shares=True,
            fractional_increment=Decimal("0.001"),
            allow_buying=True,
            allow_selling=True,
            estimated_commission=args.commission,
        )
        config = BacktestConfig(
            run_id=args.run_id or _derived_run_id(args, symbol),
            data_request=request,
            starting_cash=args.starting_cash,
            risk_limits=limits,
            fixed_commission=args.commission,
            slippage_basis_points=args.slippage_bps,
            allow_missing_sessions=args.allow_missing_sessions,
        )
        result = BacktestEngine(
            CSVHistoricalDataProvider(args.csv_root), NYSEMarketCalendar()
        ).run(config, MovingAverageCrossoverStrategy(strategy_config))
    except (TypeError, ValueError) as error:
        parser.error(str(error))

    performance = PerformanceAnalyzer().analyze(result)
    summary = _summary(result, performance)
    _print_summary(summary)
    if args.json_report is not None:
        report = build_json_report(result, strategy_config, performance)
        args.json_report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
