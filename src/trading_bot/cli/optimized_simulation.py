"""Run optimized paper portfolio simulations from local JSON configuration."""

import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

from trading_bot.cli.config import (
    _InitializationMode,
    _LoadedSimulationConfig,
    load_config,
)
from trading_bot.cli.exceptions import (
    AuditOutputError,
    ConfigJsonError,
    ConfigReadError,
    ConfigValidationError,
    OptimizerCliError,
    SimulationCliError,
)
from trading_bot.cli.serialization import (
    build_audit,
    serialize_audit,
    write_atomic,
)
from trading_bot.domain import OrderFill, OrderSide
from trading_bot.execution import OrderEngine
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.ledger import PaperLedger
from trading_bot.portfolio import OptimizationStatus
from trading_bot.runtime import PaperPortfolioRuntime
from trading_bot.simulation import (
    OptimizedPaperPortfolioSimulator,
    OptimizedPaperSimulationCertificationError,
    OptimizedPaperSimulationOptimizationError,
    OptimizedPaperSimulationResult,
    PaperPortfolioSimulationError,
)

_BOOTSTRAP_NAMESPACE = UUID("20e175f9-81ad-5985-b460-15a79acbb41e")
_BOOTSTRAP_VERSION = "optimized-simulation-cli-bootstrap-v1"
_simulator_type = OptimizedPaperPortfolioSimulator


@dataclass(frozen=True, slots=True)
class _CliRunResult:
    config: _LoadedSimulationConfig
    result: OptimizedPaperSimulationResult
    ledger: PaperLedger
    bootstrap_fills: tuple[OrderFill, ...]
    summary: str


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
    ledger, bootstrap_fills = _initialize_ledger(config)
    runtime = PaperPortfolioRuntime(OrderEngine(), ledger)
    simulator = _simulator_type(runtime)
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
    summary = build_summary(config, result, simulator.ledger)
    return _CliRunResult(config, result, simulator.ledger, bootstrap_fills, summary)


def _initialize_ledger(
    config: _LoadedSimulationConfig,
) -> tuple[PaperLedger, tuple[OrderFill, ...]]:
    initial = config.initial_ledger
    if initial.initialization_mode is _InitializationMode.CASH_ONLY:
        return PaperLedger(initial.available_cash), ()
    basis = sum(
        (item.quantity * item.average_cost for item in initial.positions),
        start=Decimal("0"),
    )
    ledger = PaperLedger(initial.available_cash + basis)
    fills = []
    for ordinal, position in enumerate(initial.positions):
        material = "|".join(
            (
                _BOOTSTRAP_VERSION,
                str(config.request.request_id),
                initial.initialization_mode.value,
                str(ordinal),
                str(position.symbol),
                canonical_decimal(position.quantity),
                canonical_decimal(position.average_cost),
                initial.as_of.isoformat(),
            )
        )
        order_id = uuid5(_BOOTSTRAP_NAMESPACE, f"{material}|order")
        fill = OrderFill(
            uuid5(_BOOTSTRAP_NAMESPACE, f"{material}|fill"),
            order_id,
            position.symbol,
            OrderSide.BUY,
            position.quantity,
            position.average_cost,
            Decimal("0"),
            initial.as_of,
        )
        ledger.apply_fill(fill)
        fills.append(fill)
    return ledger, tuple(fills)


def build_summary(
    config: _LoadedSimulationConfig,
    result: OptimizedPaperSimulationResult,
    ledger: PaperLedger,
) -> str:
    """Build deterministic human-readable output without scenario matrices."""
    lines = [
        f"simulation result: {result.result_id}",
        f"status: {result.status.value}",
        f"frame count: {len(result.evaluations)}",
        f"applied cycles: {result.applied_cycle_count}",
        f"no-action cycles: {result.no_action_cycle_count}",
        "initialized available cash: "
        f"{canonical_decimal(config.initial_ledger.available_cash)}",
        f"final cash: {canonical_decimal(ledger.cash)}",
        f"final realized P&L: {canonical_decimal(ledger.realized_profit_loss)}",
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
    except AuditOutputError as error:
        print(f"output error: {error}", file=sys.stderr)
        return 7
    if not args.quiet:
        print(cli_result.summary, end="")
    return 0
