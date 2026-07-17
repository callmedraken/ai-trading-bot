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

REPORT_SCHEMA_VERSION = 1


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


def _summary(result: BacktestResult) -> dict[str, Any]:
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
    }


def build_json_report(
    result: BacktestResult, strategy_config: MovingAverageCrossoverConfig
) -> dict[str, Any]:
    """Build the deliberate versioned public report schema."""
    summary = _summary(result)
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
    }


def _print_summary(summary: dict[str, Any]) -> None:
    for key, value in summary.items():
        if key == "final_position":
            rendered = (
                "flat"
                if value is None
                else f"{value['quantity']} @ {value['average_cost']}"
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

    summary = _summary(result)
    _print_summary(summary)
    if args.json_report is not None:
        report = build_json_report(result, strategy_config)
        args.json_report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
