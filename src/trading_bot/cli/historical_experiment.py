"""Run deterministic offline historical experiments from local configuration."""

import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from trading_bot.cli._simulation_bootstrap import initialize_canonical_ledger
from trading_bot.cli.exceptions import (
    AuditOutputError,
    ConfigJsonError,
    ConfigReadError,
    ConfigValidationError,
    HistoricalExperimentAuditError,
    HistoricalExperimentDataError,
    HistoricalExperimentExecutionCliError,
    HistoricalExperimentInitializationCliError,
)
from trading_bot.cli.historical_experiment_config import (
    LoadedHistoricalExperimentConfig,
    load_historical_experiment_config,
)
from trading_bot.cli.historical_experiment_serialization import (
    build_historical_experiment_audit,
)
from trading_bot.cli.serialization import serialize_audit, write_atomic
from trading_bot.domain import OrderFill
from trading_bot.execution import OrderEngine
from trading_bot.execution.state_fingerprints import (
    canonical_decimal,
    engine_snapshot,
    engine_state_id,
    ledger_snapshot,
    ledger_state_id,
)
from trading_bot.experiments import (
    HistoricalExperimentComparator,
    HistoricalExperimentComparisonError,
    HistoricalExperimentComparisonResult,
    HistoricalExperimentError,
    HistoricalExperimentExecutionError,
    HistoricalExperimentInitializationError,
    HistoricalExperimentInitialState,
    HistoricalExperimentIsolationError,
    HistoricalExperimentReconciliationError,
    HistoricalExperimentRequest,
    HistoricalExperimentResult,
    HistoricalExperimentRunner,
    InconsistentHistoricalExperimentResultError,
    InvalidHistoricalExperimentRequestError,
)
from trading_bot.ledger import LedgerError
from trading_bot.market_data import (
    CoordinatingHistoricalDataProvider,
    CSVHistoricalDataProvider,
    HistoricalDataError,
    MultiSymbolHistoricalDataRequest,
    MultiSymbolHistoricalDataResult,
)
from trading_bot.runtime import PaperPortfolioRuntime
from trading_bot.simulation import OptimizedPaperPortfolioSimulator

_BOOTSTRAP_NAMESPACE = UUID("8777c17e-0c37-55f8-bf91-a8cd307b73c8")
_BOOTSTRAP_VERSION = "historical-experiment-cli-bootstrap-v1"
_runner_type = HistoricalExperimentRunner
_comparator_type = HistoricalExperimentComparator
_coordinator_type = CoordinatingHistoricalDataProvider
_audit_builder = build_historical_experiment_audit


@dataclass(frozen=True, slots=True)
class _FactoryRecord:
    variant_id: UUID
    variant_ordinal: int
    simulator: OptimizedPaperPortfolioSimulator
    bootstrap_fills: tuple[OrderFill, ...]
    initial_engine_state_id: UUID
    initial_ledger_state_id: UUID


class _ExperimentSimulatorFactory:
    def __init__(self, *, collect_audit_records: bool) -> None:
        self._records: list[_FactoryRecord] = []
        self._contexts: set[tuple[UUID, int]] = set()
        self._collect_audit_records = collect_audit_records

    @property
    def records(self) -> tuple[_FactoryRecord, ...]:
        return tuple(self._records)

    def __call__(
        self,
        initial_state: HistoricalExperimentInitialState,
        *,
        experiment_request_id: UUID,
        variant_id: UUID,
        variant_ordinal: int,
    ) -> OptimizedPaperPortfolioSimulator:
        context = (variant_id, variant_ordinal)
        if context in self._contexts:
            raise ValueError("duplicate experiment factory construction context")
        self._contexts.add(context)
        ledger, fills = initialize_canonical_ledger(
            mode=initial_state.mode.value,
            as_of=initial_state.as_of,
            available_cash=initial_state.available_cash,
            positions=tuple(
                (item.symbol, item.quantity, item.unit_cost)
                for item in initial_state.bootstrap_positions
            ),
            identity_namespace=_BOOTSTRAP_NAMESPACE,
            identity_material=(
                _BOOTSTRAP_VERSION,
                str(experiment_request_id),
                str(variant_id),
                str(variant_ordinal),
                initial_state.mode.value,
            ),
        )
        engine = OrderEngine()
        simulator = OptimizedPaperPortfolioSimulator(
            PaperPortfolioRuntime(engine, ledger)
        )
        if self._collect_audit_records:
            self._records.append(
                _FactoryRecord(
                    variant_id,
                    variant_ordinal,
                    simulator,
                    fills,
                    engine_state_id(engine_snapshot(engine)),
                    ledger_state_id(ledger_snapshot(ledger)),
                )
            )
        return simulator


@dataclass(frozen=True, slots=True)
class HistoricalExperimentCliRunResult:
    config: LoadedHistoricalExperimentConfig
    historical_data: MultiSymbolHistoricalDataResult
    result: HistoricalExperimentResult
    comparison: HistoricalExperimentComparisonResult | None
    factory: _ExperimentSimulatorFactory
    summary: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a deterministic offline historical experiment."
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def run_cli(
    config_path: Path, *, collect_audit_records: bool = True
) -> HistoricalExperimentCliRunResult:
    """Load local history once and invoke one experiment runner once."""
    config = load_historical_experiment_config(config_path)
    historical_config = config.historical_data
    coordinator = _coordinator_type(
        CSVHistoricalDataProvider(historical_config.common_parent)
    )
    request = MultiSymbolHistoricalDataRequest(
        historical_config.symbols,
        historical_config.start,
        historical_config.end,
        historical_config.timeframe,
        historical_config.adjustment,
        historical_config.missing_bar_policy,
    )
    try:
        historical = coordinator.get_bars(request)
    except HistoricalDataError as error:
        sources = ", ".join(
            f"{item.symbol}={item.configured_path}"
            for item in historical_config.sources
        )
        raise HistoricalExperimentDataError(
            f"cannot load historical interval "
            f"[{historical_config.start.isoformat()}, "
            f"{historical_config.end.isoformat()}): {sources}: {error}"
        ) from error
    if historical.symbols != historical_config.symbols:
        raise HistoricalExperimentDataError(
            "loaded historical symbol order differs from configuration"
        )
    try:
        experiment_request = HistoricalExperimentRequest(
            config.request_id,
            historical,
            config.rebalance_schedule,
            config.initial_state,
            config.variants,
            config.metadata,
        )
    except InvalidHistoricalExperimentRequestError as error:
        raise ConfigValidationError("$", str(error)) from error
    factory = _ExperimentSimulatorFactory(collect_audit_records=collect_audit_records)
    try:
        result = _runner_type(factory).run(experiment_request)
    except InvalidHistoricalExperimentRequestError as error:
        raise ConfigValidationError("$", str(error)) from error
    except HistoricalExperimentInitializationError as error:
        raise HistoricalExperimentInitializationCliError(
            _variant_failure_message(error)
        ) from error
    except (
        HistoricalExperimentIsolationError,
        HistoricalExperimentExecutionError,
    ) as error:
        raise HistoricalExperimentExecutionCliError(
            _variant_failure_message(error)
        ) from error
    except (
        HistoricalExperimentReconciliationError,
        InconsistentHistoricalExperimentResultError,
    ) as error:
        raise HistoricalExperimentExecutionCliError(str(error)) from error
    comparison = None
    if config.ranking_policy is not None:
        try:
            comparison = _comparator_type().compare(result, config.ranking_policy)
        except HistoricalExperimentComparisonError as error:
            raise HistoricalExperimentExecutionCliError(
                f"comparison failed: {error}"
            ) from error
    summary = _format_summary(result)
    if comparison is not None:
        summary += _format_ranked_summary(comparison)
    return HistoricalExperimentCliRunResult(
        config, historical, result, comparison, factory, summary
    )


def _variant_failure_message(error: HistoricalExperimentError) -> str:
    return (
        f"variant {error.variant_ordinal} "
        f"({error.variant_id}, {error.variant_name}) "
        f"at {error.stage}: {error}"
    )


def _format_summary(result: HistoricalExperimentResult) -> str:
    request = result.request
    lines = [
        "Experiment:",
        f"  experiment request ID: {request.request_id}",
        f"  experiment result ID: {result.result_id}",
        f"  symbol count: {len(request.historical_data.symbols)}",
        f"  historical frame count: {len(request.historical_data.frames)}",
        f"  rebalance count: {len(request.rebalance_timestamps)}",
        f"  variant count: {len(request.variants)}",
        f"  initial-state mode: {request.initial_state.mode.value}",
        f"  initial-state fingerprint: {result.initial_state_fingerprint}",
        "Variants:",
    ]
    for run in result.runs:
        metric = run.metrics
        lines.extend(
            (
                f"  variant {run.ordinal} | {run.variant.name} | result {run.run_id}",
                f"    initial equity: {_decimal(metric.initial_equity)}",
                f"    final equity: {_decimal(metric.final_equity)}",
                "    absolute simulation P&L: "
                f"{_decimal(metric.absolute_simulation_profit_loss)}",
                f"    simulation return: {_decimal(metric.simulation_return)}",
                "    maximum drawdown amount: "
                f"{_decimal(metric.maximum_drawdown_amount)}",
                "    maximum drawdown percentage: "
                f"{_decimal(metric.maximum_drawdown_percentage)}",
                "    simulation realized P&L: "
                f"{_decimal(metric.simulation_realized_profit_loss)}",
                f"    total commissions: {_decimal(metric.total_commissions)}",
                f"    adverse slippage cost: {_decimal(metric.adverse_slippage_cost)}",
                f"    total execution cost: {_decimal(metric.total_execution_cost)}",
                f"    one-way turnover: {_decimal(metric.aggregate_one_way_turnover)}",
                f"    two-way turnover: {_decimal(metric.aggregate_two_way_turnover)}",
                "    maximum allocation drift: "
                f"{_decimal(metric.maximum_allocation_drift)}",
                f"    orders: {metric.total_orders}",
                f"    fills: {metric.total_fills}",
                f"    approved decisions: {metric.approved_decisions}",
                f"    resized decisions: {metric.resized_decisions}",
                f"    rejected decisions: {metric.rejected_decisions}",
                f"    rejected notional: {_decimal(metric.rejected_notional)}",
                f"    reduced notional: {_decimal(metric.reduced_notional)}",
                f"    applied cycles: {metric.applied_cycle_count}",
                f"    no-action cycles: {metric.no_action_cycle_count}",
                "    mean expected portfolio return: "
                f"{_decimal(metric.mean_expected_portfolio_return)}",
                f"    worst CVaR: {_decimal(metric.worst_cvar)}",
                "    minimum target cash weight: "
                f"{_decimal(metric.minimum_target_cash_weight)}",
                "    maximum target cash weight: "
                f"{_decimal(metric.maximum_target_cash_weight)}",
            )
        )
    return "\n".join(lines) + "\n"


def _format_ranked_summary(
    comparison: HistoricalExperimentComparisonResult,
) -> str:
    policy = comparison.policy
    lines = [
        "Ranking policy:",
        f"  policy ID: {policy.policy_id}",
        "  criteria:",
        *(
            f"    {index}. {criterion.metric.value} {criterion.direction.value}"
            for index, criterion in enumerate(policy.criteria, start=1)
        ),
        f"  tie breaker: {policy.tie_breaker.value}",
        "Ranked comparison:",
    ]
    for ranked in comparison.ranked_runs:
        lines.append(
            f"  rank {ranked.rank} | caller ordinal {ranked.caller_ordinal} | "
            f"{ranked.run.variant.name}"
        )
        lines.extend(
            f"    {criterion.metric.value}: {_comparison_value(value)}"
            for criterion, value in zip(
                policy.criteria, ranked.comparison_values, strict=True
            )
        )
    return "\n".join(lines) + "\n"


def _comparison_value(value: Decimal | int) -> str:
    return canonical_decimal(value) if isinstance(value, Decimal) else str(value)


def _decimal(value) -> str:  # type: ignore[no-untyped-def]
    return canonical_decimal(value)


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
        run = run_cli(args.config, collect_audit_records=args.output is not None)
        if args.output is not None:
            audit = _audit_builder(
                run.config,
                run.historical_data,
                run.result,
                run.comparison,
                run.factory.records,
            )
            content = serialize_audit(audit, pretty=args.pretty)
            write_atomic(args.output, content, overwrite=args.overwrite)
    except (ConfigReadError, ConfigJsonError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 3
    except (ConfigValidationError, HistoricalExperimentDataError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 4
    except (HistoricalExperimentInitializationCliError, LedgerError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 5
    except HistoricalExperimentExecutionCliError as error:
        print(f"error: {error}", file=sys.stderr)
        return 6
    except (HistoricalExperimentAuditError, AuditOutputError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 7
    if not args.quiet:
        print(run.summary, end="")
    return 0
