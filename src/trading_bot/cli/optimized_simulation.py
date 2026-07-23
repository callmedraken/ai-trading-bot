"""Run optimized paper portfolio simulations from local JSON configuration."""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5

from trading_bot.cli._simulation_bootstrap import (
    build_optimized_simulator,
    initialize_ledger,
)
from trading_bot.cli.config import (
    _LoadedSimulationConfig,
    load_config,
)
from trading_bot.cli.exceptions import (
    AnalyticsCliError,
    AuditOutputError,
    ConfigJsonError,
    ConfigReadError,
    ConfigValidationError,
    OptimizerCliError,
    SimulationCliError,
)
from trading_bot.cli.serialization import (
    AUDIT_SCHEMA_VERSION,
    build_audit,
    serialize_audit,
    write_atomic,
)
from trading_bot.domain import OrderFill
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.ledger import PaperLedger
from trading_bot.portfolio import MetadataEntry, OptimizationStatus
from trading_bot.portfolio_analytics import (
    InconsistentOptimizedSimulationPerformanceResultError,
    InvalidOptimizedSimulationPerformanceRequestError,
    OptimizedSimulationPerformanceAnalyzer,
    OptimizedSimulationPerformanceReconciliationError,
    OptimizedSimulationPerformanceRequest,
    OptimizedSimulationPerformanceResult,
    OptimizedSimulationValuationBasis,
    OptimizedSimulationValuationError,
    OptimizedSimulationValuationPolicy,
)
from trading_bot.simulation import (
    OptimizedPaperPortfolioSimulator,
    OptimizedPaperSimulationCertificationError,
    OptimizedPaperSimulationOptimizationError,
    OptimizedPaperSimulationResult,
    PaperPortfolioSimulationError,
)

_ANALYTICS_NAMESPACE = UUID("a3a30d80-b64f-5d22-b546-a11ed06c1395")
_ANALYTICS_VERSION = "optimized-simulation-cli-analytics-v1"
_simulator_type = OptimizedPaperPortfolioSimulator
_analyzer_type = OptimizedSimulationPerformanceAnalyzer


@dataclass(frozen=True, slots=True)
class _CliRunResult:
    config: _LoadedSimulationConfig
    result: OptimizedPaperSimulationResult
    performance_result: OptimizedSimulationPerformanceResult
    ledger: PaperLedger
    bootstrap_fills: tuple[OrderFill, ...]
    operational_summary: str
    performance_summary: str

    @property
    def summary(self) -> str:
        """Return the complete successful terminal summary."""
        return self.operational_summary + self.performance_summary


def build_parser() -> argparse.ArgumentParser:
    """Build the optimized simulation command-line parser."""
    parser = argparse.ArgumentParser(
        description="Run a deterministic offline optimized paper simulation."
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def run_cli(config_path: Path) -> _CliRunResult:
    """Load, assemble, and run exactly one self-contained simulation."""
    config = load_config(config_path)
    simulator, bootstrap_fills = build_optimized_simulator(
        config.request.request_id, config.initial_ledger, _simulator_type
    )
    try:
        result = simulator.run(config.request)
    except OptimizedPaperSimulationOptimizationError as error:
        raise OptimizerCliError(
            error.frame_ordinal,
            str(error),
            status=error.status,
            diagnostic_codes=error.diagnostic_codes,
        ) from error
    except OptimizedPaperSimulationCertificationError as error:
        raise SimulationCliError(f"frame {error.frame_ordinal}: {error}") from error
    except PaperPortfolioSimulationError as error:
        ordinal = getattr(error, "frame_ordinal", None)
        prefix = "" if ordinal is None else f"frame {ordinal}: "
        raise SimulationCliError(f"{prefix}{error}") from error
    try:
        performance_request = _build_performance_request(result)
        performance_result = _analyzer_type().analyze(performance_request)
    except (
        InvalidOptimizedSimulationPerformanceRequestError,
        OptimizedSimulationValuationError,
        OptimizedSimulationPerformanceReconciliationError,
        InconsistentOptimizedSimulationPerformanceResultError,
    ) as error:
        raise AnalyticsCliError(result.result_id, str(error)) from error
    operational_summary = _format_operational_summary(config, result, simulator.ledger)
    performance_summary = _format_performance_summary(performance_result)
    return _CliRunResult(
        config,
        result,
        performance_result,
        simulator.ledger,
        bootstrap_fills,
        operational_summary,
        performance_summary,
    )


def _build_performance_request(
    result: OptimizedPaperSimulationResult,
) -> OptimizedSimulationPerformanceRequest:
    policy = OptimizedSimulationValuationPolicy(
        OptimizedSimulationValuationBasis.FRAME_RISK_PRICES
    )
    material = "|".join(
        (
            _ANALYTICS_VERSION,
            str(result.request.request_id),
            str(result.result_id),
            "analytics",
            policy.valuation_basis.value,
            str(AUDIT_SCHEMA_VERSION),
        )
    )
    metadata = (
        *result.request.metadata,
        MetadataEntry("optimized_simulation_cli_schema_version", "2"),
        MetadataEntry("optimized_simulation_cli_source", "offline-cli"),
    )
    return OptimizedSimulationPerformanceRequest(
        uuid5(_ANALYTICS_NAMESPACE, material),
        result,
        policy,
        metadata,
    )


def _initialize_ledger(
    config: _LoadedSimulationConfig,
) -> tuple[PaperLedger, tuple[OrderFill, ...]]:
    return initialize_ledger(config.request.request_id, config.initial_ledger)


def _format_operational_summary(
    config: _LoadedSimulationConfig,
    result: OptimizedPaperSimulationResult,
    ledger: PaperLedger,
) -> str:
    """Build the existing deterministic operational summary."""
    lines = [
        f"simulation result: {result.result_id}",
        f"status: {result.status.value}",
        f"frame count: {len(result.evaluations)}",
        f"applied cycles: {result.applied_cycle_count}",
        f"no-action cycles: {result.no_action_cycle_count}",
        "initialized available cash: "
        f"{canonical_decimal(config.initial_ledger.available_cash)}",
        f"final cash: {canonical_decimal(ledger.cash)}",
        f"final ledger realized P&L: {canonical_decimal(ledger.realized_profit_loss)}",
        "final positions:",
    ]
    final_symbols = tuple(item.symbol for item in result.request.frames[-1].prices)
    lines.extend(_position_lines(ledger.positions, final_symbols, "  "))
    running_positions = {
        item.symbol: (item.quantity, item.average_cost)
        for item in config.initial_ledger.positions
    }
    running_cash = config.initial_ledger.available_cash
    for evaluation in result.evaluations:
        cycle = evaluation.cycle_result
        for application in cycle.application_result.evaluations:
            position = application.ledger_position_after
            if position is None:
                running_positions.pop(application.fill.symbol, None)
            else:
                running_positions[position.symbol] = (
                    position.quantity,
                    position.average_cost,
                )
            running_cash = application.ledger_cash_after
        target = evaluation.optimized_target_result.target
        weights = ", ".join(
            f"{item.symbol}={canonical_decimal(item.weight)}"
            for item in target.allocations
        )
        lines.extend(
            (
                "",
                f"frame {evaluation.frame_ordinal}: "
                f"{evaluation.frame.as_of.isoformat()}",
                "  optimization: "
                f"{evaluation.optimization_result.optimization_result.status.value}",
                f"  target: {weights}, cash={canonical_decimal(target.cash_weight)}",
                f"  cycle: {cycle.status.value}",
                "  risk: "
                f"approved={cycle.risk_result.approved_count} "
                f"resized={cycle.risk_result.resized_count} "
                f"rejected={cycle.risk_result.rejected_count}",
                f"  orders: {len(cycle.order_result.orders)}",
                f"  fills: {len(cycle.fill_result.fills)}",
                f"  ending cash: {canonical_decimal(running_cash)}",
                "  ending positions:",
            )
        )
        symbol_order = tuple(item.symbol for item in evaluation.frame.prices)
        if running_positions:
            for symbol in symbol_order:
                if symbol in running_positions:
                    quantity, average_cost = running_positions[symbol]
                    lines.append(
                        f"    {symbol}: {canonical_decimal(quantity)} @ "
                        f"{canonical_decimal(average_cost)}"
                    )
        else:
            lines.append("    flat")
    return "\n".join(lines) + "\n"


def _format_performance_summary(
    result: OptimizedSimulationPerformanceResult,
) -> str:
    """Build a deterministic aggregate performance summary."""
    amount_source = _drawdown_source(result, result.drawdowns.maximum_amount)
    percentage_source = _drawdown_source(result, result.drawdowns.maximum_percentage)
    summary = result.optimization_summary
    lines = [
        "",
        "Performance:",
        f"  initial equity: {canonical_decimal(result.initial_equity)}",
        f"  final equity: {canonical_decimal(result.final_equity)}",
        "  absolute simulation P&L: "
        f"{canonical_decimal(result.absolute_simulation_profit_loss)}",
        f"  simulation return: {canonical_decimal(result.simulation_return)}",
        "  maximum drawdown amount: "
        f"{canonical_decimal(result.maximum_drawdown_amount)}",
        "  maximum drawdown amount source: "
        f"frame={amount_source.frame_ordinal} phase={amount_source.phase.value}",
        "  maximum drawdown percentage: "
        f"{canonical_decimal(result.maximum_drawdown_percentage)}",
        "  maximum drawdown percentage source: "
        f"frame={percentage_source.frame_ordinal} "
        f"phase={percentage_source.phase.value}",
        "  simulation realized P&L: "
        f"{canonical_decimal(result.cumulative_simulation_realized_profit_loss)}",
        "  initial unrealized P&L: "
        f"{canonical_decimal(result.initial_unrealized_profit_loss)}",
        "  final unrealized P&L: "
        f"{canonical_decimal(result.final_unrealized_profit_loss)}",
        f"  total commissions: {canonical_decimal(result.total_commissions)}",
        "  signed slippage P&L: "
        f"{canonical_decimal(result.total_signed_slippage_profit_loss)}",
        "  adverse slippage cost: "
        f"{canonical_decimal(result.total_adverse_slippage_cost)}",
        f"  total execution cost: {canonical_decimal(result.total_execution_cost)}",
        "  aggregate one-way turnover: "
        f"{canonical_decimal(result.aggregate_one_way_turnover)}",
        "  aggregate two-way turnover: "
        f"{canonical_decimal(result.aggregate_two_way_turnover)}",
        "  maximum allocation drift: "
        f"{canonical_decimal(result.maximum_absolute_allocation_drift)}",
        "  total allocation drift: "
        f"{canonical_decimal(result.total_absolute_allocation_drift)}",
        "",
        "Optimization summary:",
        "  mean expected portfolio return: "
        f"{canonical_decimal(summary.mean_expected_portfolio_return)}",
        f"  worst CVaR: {canonical_decimal(summary.worst_cvar)}",
        "  minimum target cash weight: "
        f"{canonical_decimal(summary.minimum_target_cash_weight)}",
        "  maximum target cash weight: "
        f"{canonical_decimal(summary.maximum_target_cash_weight)}",
        "",
        "Trading and risk summary:",
        f"  total orders: {result.total_order_count}",
        f"  total fills: {result.total_fill_count}",
        f"  approved: {result.total_approved_risk_count}",
        f"  resized: {result.total_resized_risk_count}",
        f"  rejected: {result.total_rejected_risk_count}",
        f"  rejected notional: {canonical_decimal(result.total_rejected_notional)}",
        f"  reduced notional: {canonical_decimal(result.total_reduced_notional)}",
    ]
    return "\n".join(lines) + "\n"


def _drawdown_source(result, record):  # type: ignore[no-untyped-def]
    matches = tuple(
        item
        for item in result.equity_observations
        if item.timestamp == record.trough_timestamp
        and item.equity == record.trough_equity
        and item.running_peak == record.peak_equity
        and item.drawdown_amount == record.amount
        and item.drawdown_percentage == record.percentage
    )
    if not matches:
        raise InconsistentOptimizedSimulationPerformanceResultError(
            "drawdown maximum has no source observation"
        )
    return matches[0]


def _position_lines(positions, symbols, prefix):  # type: ignore[no-untyped-def]
    output = [
        f"{prefix}{symbol}: {canonical_decimal(positions[symbol].quantity)} @ "
        f"{canonical_decimal(positions[symbol].average_cost)}"
        for symbol in symbols
        if symbol in positions
    ]
    return output or [f"{prefix}flat"]


def _optimizer_message(error: OptimizerCliError) -> str:
    status = "UNKNOWN" if error.status is None else error.status.value
    codes = ",".join(error.diagnostic_codes) or "none"
    message = (
        f"optimizer error: frame {error.frame_ordinal}; status={status}; "
        f"diagnostics={codes}; {error}"
    )
    if error.status is OptimizationStatus.UNAVAILABLE:
        message += (
            "; install CPU optimization support with: pip install -e "
            '".[optimization-cpu]"'
        )
    return message


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run one simulation, and return a stable exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.pretty and args.output is None:
        parser.error("--pretty requires --output")
    if args.overwrite and args.output is None:
        parser.error("--overwrite requires --output")
    if args.output is not None and args.output.exists() and not args.overwrite:
        print(f"output error: output already exists: {args.output}", file=sys.stderr)
        return 7
    try:
        cli_result = run_cli(args.config)
        audit_text = None
        if args.output is not None:
            audit = build_audit(
                cli_result.config,
                cli_result.result,
                cli_result.performance_result,
                cli_result.ledger,
                cli_result.bootstrap_fills,
            )
            audit_text = serialize_audit(audit, pretty=args.pretty)
            write_atomic(args.output, audit_text, overwrite=args.overwrite)
    except (ConfigReadError, ConfigJsonError) as error:
        print(f"configuration read error: {error}", file=sys.stderr)
        return 3
    except ConfigValidationError as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 4
    except OptimizerCliError as error:
        print(_optimizer_message(error), file=sys.stderr)
        return 5
    except SimulationCliError as error:
        print(f"simulation error: {error}", file=sys.stderr)
        return 6
    except AnalyticsCliError as error:
        print(
            "analytics error: simulation result "
            f"{error.source_simulation_result_id}; {error}",
            file=sys.stderr,
        )
        return 6
    except AuditOutputError as error:
        print(f"output error: {error}", file=sys.stderr)
        return 7
    if not args.quiet:
        print(cli_result.summary, end="")
    return 0
