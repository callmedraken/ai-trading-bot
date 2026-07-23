"""Run deterministic rolling historical simulations from local configuration."""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from trading_bot.cli._simulation_bootstrap import build_optimized_simulator
from trading_bot.cli.exceptions import (
    AuditOutputError,
    ConfigJsonError,
    ConfigReadError,
    ConfigValidationError,
    HistoricalDataCliError,
    RollingExecutionCliError,
    RollingInitializationCliError,
)
from trading_bot.cli.rolling_historical_config import (
    LoadedRollingHistoricalConfig,
    load_rolling_config,
)
from trading_bot.cli.rolling_historical_serialization import build_rolling_audit
from trading_bot.cli.serialization import serialize_audit, write_atomic
from trading_bot.domain import OrderFill
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.ledger import LedgerError, PaperLedger
from trading_bot.market_data import (
    CoordinatingHistoricalDataProvider,
    CSVHistoricalDataProvider,
    HistoricalDataError,
    MultiSymbolHistoricalDataRequest,
    MultiSymbolHistoricalDataResult,
)
from trading_bot.simulation import (
    RollingHistoricalOptimizedSimulationRunner,
    RollingHistoricalSimulationError,
    RollingHistoricalSimulationRequest,
    RollingHistoricalSimulationResult,
)

_runner_type = RollingHistoricalOptimizedSimulationRunner
_coordinator_type = CoordinatingHistoricalDataProvider
_audit_builder = build_rolling_audit


@dataclass(frozen=True, slots=True)
class RollingHistoricalCliRunResult:
    config: LoadedRollingHistoricalConfig
    historical_data: MultiSymbolHistoricalDataResult
    result: RollingHistoricalSimulationResult
    ledger: PaperLedger
    bootstrap_fills: tuple[OrderFill, ...]
    summary: str


def build_parser() -> argparse.ArgumentParser:
    """Build the rolling historical simulation parser."""
    parser = argparse.ArgumentParser(
        description="Run a deterministic offline rolling historical simulation."
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def run_cli(config_path: Path) -> RollingHistoricalCliRunResult:
    """Load local data and execute exactly one rolling runner."""
    config = load_rolling_config(config_path)
    historical_config = config.historical_data
    provider = CSVHistoricalDataProvider(historical_config.common_parent)
    coordinator = _coordinator_type(provider)
    historical_request = MultiSymbolHistoricalDataRequest(
        historical_config.symbols,
        historical_config.start,
        historical_config.end,
        historical_config.timeframe,
        historical_config.adjustment,
        historical_config.missing_bar_policy,
    )
    try:
        historical = coordinator.get_bars(historical_request)
    except HistoricalDataError as error:
        sources = ", ".join(
            f"{item.symbol}={item.configured_path}"
            for item in historical_config.sources
        )
        raise HistoricalDataCliError(
            f"cannot load historical interval "
            f"[{historical_config.start.isoformat()}, "
            f"{historical_config.end.isoformat()}): {sources}: {error}"
        ) from error
    if historical.symbols != historical_config.symbols:
        raise HistoricalDataCliError(
            "loaded historical symbol order differs from configuration"
        )
    try:
        simulator, bootstrap_fills = build_optimized_simulator(
            config.request_id, config.initial_state
        )
    except LedgerError as error:
        raise RollingInitializationCliError(str(error)) from error
    try:
        request = RollingHistoricalSimulationRequest(
            config.request_id,
            historical,
            config.rebalance_schedule,
            config.window_policy,
            config.scenario_policy,
            config.execution_price_policy,
            config.timing_policy,
            config.scenario_cash_return,
            config.scenario_source_name,
            config.optimization_parameters,
            config.risk_aversion,
            config.portfolio_constraints,
            config.rebalance_assumptions,
            config.proposal_policy,
            config.proposal_confidence,
            config.risk_limits,
            config.risk_policy,
            config.fill_policy,
            config.trading_enabled,
            config.metadata,
        )
        result = _runner_type(simulator).run(request)
    except RollingHistoricalSimulationError as error:
        ordinal = getattr(error, "frame_ordinal", None)
        prefix = "" if ordinal is None else f"frame {ordinal}: "
        raise RollingExecutionCliError(f"{prefix}{error}") from error
    summary = _format_summary(config, historical, result, simulator.ledger)
    return RollingHistoricalCliRunResult(
        config,
        historical,
        result,
        simulator.ledger,
        bootstrap_fills,
        summary,
    )


def _format_summary(
    config: LoadedRollingHistoricalConfig,
    historical: MultiSymbolHistoricalDataResult,
    result: RollingHistoricalSimulationResult,
    ledger: PaperLedger,
) -> str:
    performance = result.performance_result
    optimization = performance.optimization_summary
    lines = [
        "Run:",
        f"  rolling request ID: {result.request.request_id}",
        f"  rolling result ID: {result.result_id}",
        f"  status: {result.optimized_result.status.value}",
        f"  symbol count: {len(historical.symbols)}",
        f"  historical frame count: {len(historical.frames)}",
        f"  rebalance count: {len(result.frame_generations)}",
        f"  observation count: {config.window_policy.observation_count}",
        f"  initial cash: {canonical_decimal(config.initial_state.available_cash)}",
        f"  final cash: {canonical_decimal(ledger.cash)}",
        f"  initial equity: {canonical_decimal(performance.initial_equity)}",
        f"  final equity: {canonical_decimal(performance.final_equity)}",
        "  absolute simulation P&L: "
        f"{canonical_decimal(performance.absolute_simulation_profit_loss)}",
        f"  simulation return: {canonical_decimal(performance.simulation_return)}",
        "  maximum drawdown amount: "
        f"{canonical_decimal(performance.drawdowns.maximum_amount.amount)}",
        "  maximum drawdown percentage: "
        f"{canonical_decimal(performance.drawdowns.maximum_percentage.percentage)}",
        f"  commissions: {canonical_decimal(performance.total_commissions)}",
        "  adverse slippage cost: "
        f"{canonical_decimal(performance.total_adverse_slippage_cost)}",
        "  total execution cost: "
        f"{canonical_decimal(performance.total_execution_cost)}",
        "  one-way turnover: "
        f"{canonical_decimal(performance.aggregate_one_way_turnover)}",
        "  two-way turnover: "
        f"{canonical_decimal(performance.aggregate_two_way_turnover)}",
        "  maximum allocation drift: "
        f"{canonical_decimal(performance.maximum_absolute_allocation_drift)}",
        "  final ledger realized P&L: "
        f"{canonical_decimal(ledger.realized_profit_loss)}",
        "Trading:",
        f"  applied cycles: {performance.applied_cycle_count}",
        f"  no-action cycles: {performance.no_action_cycle_count}",
        f"  orders: {performance.total_order_count}",
        f"  fills: {performance.total_fill_count}",
        f"  approved decisions: {performance.total_approved_risk_count}",
        f"  resized decisions: {performance.total_resized_risk_count}",
        f"  rejected decisions: {performance.total_rejected_risk_count}",
        "  rejected notional: "
        f"{canonical_decimal(performance.total_rejected_notional)}",
        f"  reduced notional: {canonical_decimal(performance.total_reduced_notional)}",
        "Optimization:",
        "  mean expected return: "
        f"{canonical_decimal(optimization.mean_expected_portfolio_return)}",
        f"  worst CVaR: {canonical_decimal(optimization.worst_cvar)}",
        "  minimum target cash: "
        f"{canonical_decimal(optimization.minimum_target_cash_weight)}",
        "  maximum target cash: "
        f"{canonical_decimal(optimization.maximum_target_cash_weight)}",
        "Frames:",
    ]
    for generation, evaluation, frame_performance in zip(
        result.frame_generations,
        result.optimized_result.evaluations,
        performance.frames,
        strict=True,
    ):
        cycle = evaluation.cycle_result
        lines.append(
            f"  frame {generation.frame_ordinal} | "
            f"{generation.rebalance_timestamp.isoformat()} | "
            f"window {generation.window_start_index}.."
            f"{generation.window_end_index_inclusive} | "
            f"scenarios {generation.scenario_result.scenario_set.scenario_count} | "
            f"cycle {cycle.status.value} | "
            f"orders {len(cycle.order_result.orders)} | "
            f"fills {len(cycle.fill_result.fills)} | "
            f"equity {canonical_decimal(frame_performance.post_cycle_equity)}"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.pretty and args.output is None:
        parser.error("--pretty requires --output")
    if args.overwrite and args.output is None:
        parser.error("--overwrite requires --output")
    if args.output is not None:
        if not args.output.parent.is_dir():
            print(
                f"error: output parent directory does not exist: {args.output.parent}",
                file=sys.stderr,
            )
            return 7
        if args.output.exists() and not args.overwrite:
            print(f"error: output already exists: {args.output}", file=sys.stderr)
            return 7
    try:
        run = run_cli(args.config)
        if args.output is not None:
            audit = _audit_builder(
                run.config,
                run.historical_data,
                run.result,
                run.ledger,
                run.bootstrap_fills,
            )
            content = serialize_audit(audit, pretty=args.pretty)
            write_atomic(args.output, content, overwrite=args.overwrite)
    except (ConfigReadError, ConfigJsonError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 3
    except (ConfigValidationError, HistoricalDataCliError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 4
    except RollingInitializationCliError as error:
        print(f"error: {error}", file=sys.stderr)
        return 5
    except RollingExecutionCliError as error:
        print(f"error: {error}", file=sys.stderr)
        return 6
    except AuditOutputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 7
    if not args.quiet:
        print(run.summary, end="")
    return 0
