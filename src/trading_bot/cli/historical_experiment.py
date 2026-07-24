"""Run deterministic offline historical experiments from local configuration."""

import argparse
import os
import sys
import tempfile
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
    HistoricalExperimentPairwiseOutputError,
    HistoricalExperimentParetoOutputError,
    HistoricalExperimentReportOutputError,
)
from trading_bot.cli.historical_experiment_config import (
    LoadedHistoricalExperimentConfig,
    load_historical_experiment_config,
)
from trading_bot.cli.historical_experiment_pairwise_config import (
    load_historical_experiment_pairwise_policy,
)
from trading_bot.cli.historical_experiment_pairwise_serialization import (
    serialize_pairwise_csv,
    serialize_pairwise_json,
)
from trading_bot.cli.historical_experiment_pareto_config import (
    load_historical_experiment_pareto_policy,
)
from trading_bot.cli.historical_experiment_pareto_serialization import (
    serialize_pareto_csv,
    serialize_pareto_json,
)
from trading_bot.cli.historical_experiment_report_serialization import (
    serialize_compact_report_csv,
    serialize_compact_report_json,
)
from trading_bot.cli.historical_experiment_serialization import (
    build_historical_experiment_audit,
)
from trading_bot.cli.serialization import serialize_audit
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
    HistoricalExperimentGridError,
    HistoricalExperimentGridGenerator,
    HistoricalExperimentGridResult,
    HistoricalExperimentInitializationError,
    HistoricalExperimentInitialState,
    HistoricalExperimentIsolationError,
    HistoricalExperimentPairwiseComparator,
    HistoricalExperimentPairwiseError,
    HistoricalExperimentPairwiseResult,
    HistoricalExperimentParetoAnalyzer,
    HistoricalExperimentParetoError,
    HistoricalExperimentParetoResult,
    HistoricalExperimentReconciliationError,
    HistoricalExperimentReport,
    HistoricalExperimentReportBuilder,
    HistoricalExperimentReportError,
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
_pairwise_comparator_type = HistoricalExperimentPairwiseComparator
_pareto_analyzer_type = HistoricalExperimentParetoAnalyzer
_comparator_type = HistoricalExperimentComparator
_grid_generator_type = HistoricalExperimentGridGenerator
_coordinator_type = CoordinatingHistoricalDataProvider
_report_builder_type = HistoricalExperimentReportBuilder
_audit_builder = build_historical_experiment_audit
_compact_json_serializer = serialize_compact_report_json
_compact_csv_serializer = serialize_compact_report_csv


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
    grid_result: HistoricalExperimentGridResult | None
    historical_data: MultiSymbolHistoricalDataResult
    result: HistoricalExperimentResult
    comparison: HistoricalExperimentComparisonResult | None
    compact_report: HistoricalExperimentReport | None
    pairwise_result: HistoricalExperimentPairwiseResult | None
    pareto_result: HistoricalExperimentParetoResult | None
    factory: _ExperimentSimulatorFactory
    summary: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a deterministic offline historical experiment."
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--compact-json", type=Path)
    parser.add_argument("--compact-json-pretty", action="store_true")
    parser.add_argument("--compact-csv", type=Path)
    parser.add_argument("--pairwise-policy", type=Path)
    parser.add_argument("--pairwise-json", type=Path)
    parser.add_argument("--pairwise-json-pretty", action="store_true")
    parser.add_argument("--pairwise-csv", type=Path)
    parser.add_argument("--pareto-policy", type=Path)
    parser.add_argument("--pareto-json", type=Path)
    parser.add_argument("--pareto-json-pretty", action="store_true")
    parser.add_argument("--pareto-csv", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def run_cli(
    config_path: Path,
    *,
    collect_audit_records: bool = True,
    build_compact_report: bool = False,
    pairwise_policy_path: Path | None = None,
    pareto_policy_path: Path | None = None,
) -> HistoricalExperimentCliRunResult:
    """Load local history once and invoke one experiment runner once."""
    config = load_historical_experiment_config(config_path)
    loaded_pairwise_policy = (
        None
        if pairwise_policy_path is None
        else load_historical_experiment_pairwise_policy(pairwise_policy_path)
    )
    loaded_pareto_policy = (
        None
        if pareto_policy_path is None
        else load_historical_experiment_pareto_policy(pareto_policy_path)
    )
    grid_result = None
    if config.grid_specification is None:
        variants = config.explicit_variants
    else:
        try:
            grid_result = _grid_generator_type().generate(config.grid_specification)
        except HistoricalExperimentGridError as error:
            raise HistoricalExperimentExecutionCliError(
                f"variant-grid generation failed: {error}"
            ) from error
        variants = tuple(item.variant for item in grid_result.generated_variants)
    if variants is None:
        raise HistoricalExperimentExecutionCliError(
            "configuration did not resolve experiment variants"
        )
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
            variants,
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
    compact_report = None
    pairwise_result = None
    report_required = (
        build_compact_report
        or loaded_pairwise_policy is not None
        or loaded_pareto_policy is not None
    )
    if report_required:
        try:
            compact_report = _report_builder_type().build(
                result,
                grid_result=grid_result,
                comparison_result=comparison,
                metadata=(),
            )
        except HistoricalExperimentReportError as error:
            raise HistoricalExperimentExecutionCliError(
                f"compact report construction failed: {error}"
            ) from error
    if loaded_pairwise_policy is not None:
        try:
            pairwise_result = _pairwise_comparator_type().compare(
                compact_report,
                loaded_pairwise_policy.policy,
            )
        except HistoricalExperimentPairwiseError as error:
            raise HistoricalExperimentExecutionCliError(
                f"pairwise comparison failed: {error}"
            ) from error
    pareto_result = None
    if loaded_pareto_policy is not None:
        try:
            pareto_result = _pareto_analyzer_type().analyze(
                compact_report, loaded_pareto_policy.policy
            )
        except HistoricalExperimentParetoError as error:
            raise HistoricalExperimentExecutionCliError(
                f"Pareto analysis failed: {error}"
            ) from error
    summary = ""
    if grid_result is not None:
        summary += _format_grid_summary(grid_result)
    summary += _format_summary(result)
    if comparison is not None:
        summary += _format_ranked_summary(comparison)
    if pairwise_result is not None:
        summary += _format_pairwise_summary(pairwise_result)
    if pareto_result is not None:
        summary += _format_pareto_summary(pareto_result)
    return HistoricalExperimentCliRunResult(
        config,
        grid_result,
        historical,
        result,
        comparison,
        compact_report,
        pairwise_result,
        pareto_result,
        factory,
        summary,
    )


def _format_pareto_summary(result: HistoricalExperimentParetoResult) -> str:
    lines = [
        "Pareto analysis:",
        f"  result ID: {result.result_id}",
        f"  policy ID: {result.policy.policy_id}",
        "  objectives:",
        *(
            f"    {index}. {item.metric.value} | {item.direction.value}"
            for index, item in enumerate(result.policy.objectives, start=1)
        ),
        f"  variant count: {len(result.variants)}",
        f"  frontier count: {len(result.frontier_variant_ids)}",
        f"  dominance record count: {len(result.dominance_records)}",
    ]
    return "\n".join(lines) + "\n"


def _format_pairwise_summary(
    result: HistoricalExperimentPairwiseResult,
) -> str:
    policy = result.policy
    lines = [
        "Pairwise comparison:",
        f"  result ID: {result.result_id}",
        f"  policy ID: {policy.policy_id}",
        f"  pairing: {policy.pairing.value}",
        f"  orientation: {policy.orientation.value}",
        "  metrics:",
        *(
            f"    {index}. {metric.value}"
            for index, metric in enumerate(policy.metrics, start=1)
        ),
        f"  record count: {len(result.records)}",
    ]
    return "\n".join(lines) + "\n"


def _format_grid_summary(result: HistoricalExperimentGridResult) -> str:
    specification = result.specification
    lines = [
        "Variant grid:",
        f"  specification ID: {specification.specification_id}",
        f"  generated variant count: {len(result.generated_variants)}",
        f"  maximum variant count: {specification.maximum_variant_count}",
        "  axes:",
    ]
    for ordinal, axis in enumerate(specification.axes, start=1):
        values = ", ".join(_grid_value(value) for value in axis.values)
        lines.append(f"    {ordinal}. {axis.parameter.value}: {values}")
    return "\n".join(lines) + "\n"


def _grid_value(value: Decimal | int | bool | None) -> str:
    if value is None:
        return "NULL"
    if type(value) is bool:
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return canonical_decimal(value)
    return str(value)


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


@dataclass(frozen=True, slots=True)
class _OutputArtifact:
    destination: Path
    content: str


def _normalized_destinations(
    args,  # type: ignore[no-untyped-def]
) -> tuple[
    Path | None,
    Path | None,
    Path | None,
    Path | None,
    Path | None,
    Path | None,
    Path | None,
]:
    return tuple(
        None if value is None else value.resolve(strict=False)
        for value in (
            args.output,
            args.compact_json,
            args.compact_csv,
            args.pairwise_json,
            args.pairwise_csv,
            args.pareto_json,
            args.pareto_csv,
        )
    )  # type: ignore[return-value]


def _preflight_destinations(
    destinations: tuple[Path | None, ...], *, overwrite: bool
) -> None:
    for destination in destinations:
        if destination is None:
            continue
        if not destination.parent.is_dir():
            raise HistoricalExperimentReportOutputError(
                f"output parent directory does not exist: {destination.parent}"
            )
        if destination.exists() and not overwrite:
            raise HistoricalExperimentReportOutputError(
                f"output already exists: {destination}"
            )


def _write_artifacts(
    artifacts: tuple[_OutputArtifact, ...], *, overwrite: bool
) -> None:
    staged: list[tuple[Path, Path]] = []
    try:
        for artifact in artifacts:
            destination = artifact.destination
            if destination.exists() and not overwrite:
                raise HistoricalExperimentReportOutputError(
                    f"output already exists: {destination}"
                )
            descriptor, name = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
            )
            temporary = Path(name)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
                    stream.write(artifact.content)
                    stream.flush()
                    os.fsync(stream.fileno())
            except (OSError, UnicodeError):
                temporary.unlink(missing_ok=True)
                raise
            staged.append((destination, temporary))
        for destination, temporary in staged:
            if destination.exists() and not overwrite:
                raise HistoricalExperimentReportOutputError(
                    f"output already exists: {destination}"
                )
            os.replace(temporary, destination)
    except HistoricalExperimentReportOutputError:
        raise
    except (OSError, UnicodeError) as error:
        raise HistoricalExperimentReportOutputError(
            f"cannot write compact experiment output: {error}"
        ) from error
    finally:
        for _, temporary in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _compact_success(
    report: HistoricalExperimentReport,
    compact_json: Path | None,
    compact_csv: Path | None,
) -> str:
    lines = ["Compact report:", f"  report ID: {report.report_id}"]
    if compact_json is not None:
        lines.append(f"  JSON: {compact_json}")
    if compact_csv is not None:
        lines.append(f"  CSV: {compact_csv}")
    return "\n".join(lines) + "\n"


def _pairwise_success(
    pairwise_json: Path | None,
    pairwise_csv: Path | None,
) -> str:
    lines = ["Pairwise artifacts:"]
    if pairwise_json is not None:
        lines.append(f"  JSON: {pairwise_json}")
    if pairwise_csv is not None:
        lines.append(f"  CSV: {pairwise_csv}")
    return "\n".join(lines) + "\n"


def _pareto_success(pareto_json: Path | None, pareto_csv: Path | None) -> str:
    lines = ["Pareto artifacts:"]
    if pareto_json is not None:
        lines.append(f"  JSON: {pareto_json}")
    if pareto_csv is not None:
        lines.append(f"  CSV: {pareto_csv}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.pretty and args.output is None:
        parser.error("--pretty requires --output")
    if args.compact_json_pretty and args.compact_json is None:
        parser.error("--compact-json-pretty requires --compact-json")
    if args.pairwise_json is not None and args.pairwise_policy is None:
        parser.error("--pairwise-json requires --pairwise-policy")
    if args.pairwise_csv is not None and args.pairwise_policy is None:
        parser.error("--pairwise-csv requires --pairwise-policy")
    if args.pairwise_json_pretty and args.pairwise_json is None:
        parser.error("--pairwise-json-pretty requires --pairwise-json")
    if args.pareto_json is not None and args.pareto_policy is None:
        parser.error("--pareto-json requires --pareto-policy")
    if args.pareto_csv is not None and args.pareto_policy is None:
        parser.error("--pareto-csv requires --pareto-policy")
    if args.pareto_json_pretty and args.pareto_json is None:
        parser.error("--pareto-json-pretty requires --pareto-json")
    requested = (
        args.output,
        args.compact_json,
        args.compact_csv,
        args.pairwise_json,
        args.pairwise_csv,
        args.pareto_json,
        args.pareto_csv,
    )
    if args.overwrite and not any(value is not None for value in requested):
        parser.error("--overwrite requires an output destination")
    (
        output,
        compact_json,
        compact_csv,
        pairwise_json,
        pairwise_csv,
        pareto_json,
        pareto_csv,
    ) = _normalized_destinations(args)
    destinations = tuple(
        value
        for value in (
            output,
            compact_json,
            compact_csv,
            pairwise_json,
            pairwise_csv,
            pareto_json,
            pareto_csv,
        )
        if value is not None
    )
    if len(set(destinations)) != len(destinations):
        parser.error("output destinations must be pairwise distinct")
    try:
        _preflight_destinations(destinations, overwrite=args.overwrite)
        compact_requested = compact_json is not None or compact_csv is not None
        run = run_cli(
            args.config,
            collect_audit_records=output is not None,
            build_compact_report=compact_requested,
            pairwise_policy_path=args.pairwise_policy,
            pareto_policy_path=args.pareto_policy,
        )
        artifacts = []
        if output is not None:
            audit = _audit_builder(
                run.config,
                run.grid_result,
                run.historical_data,
                run.result,
                run.comparison,
                run.factory.records,
            )
            content = serialize_audit(audit, pretty=args.pretty)
            artifacts.append(_OutputArtifact(output, content))
        if compact_requested and run.compact_report is None:
            raise HistoricalExperimentReportOutputError(
                "requested compact report was not built"
            )
        if compact_json is not None:
            artifacts.append(
                _OutputArtifact(
                    compact_json,
                    _compact_json_serializer(
                        run.compact_report,
                        pretty=args.compact_json_pretty,
                    ),
                )
            )
        if compact_csv is not None:
            artifacts.append(
                _OutputArtifact(
                    compact_csv,
                    _compact_csv_serializer(run.compact_report),
                )
            )
        if args.pairwise_policy is not None and run.pairwise_result is None:
            raise HistoricalExperimentPairwiseOutputError(
                "requested pairwise result was not built"
            )
        if pairwise_json is not None:
            artifacts.append(
                _OutputArtifact(
                    pairwise_json,
                    serialize_pairwise_json(
                        run.pairwise_result,
                        pretty=args.pairwise_json_pretty,
                    ),
                )
            )
        if pairwise_csv is not None:
            artifacts.append(
                _OutputArtifact(
                    pairwise_csv,
                    serialize_pairwise_csv(run.pairwise_result),
                )
            )
        if args.pareto_policy is not None and run.pareto_result is None:
            raise HistoricalExperimentParetoOutputError(
                "requested Pareto result was not built"
            )
        if pareto_json is not None:
            artifacts.append(
                _OutputArtifact(
                    pareto_json,
                    serialize_pareto_json(
                        run.pareto_result, pretty=args.pareto_json_pretty
                    ),
                )
            )
        if pareto_csv is not None:
            artifacts.append(
                _OutputArtifact(pareto_csv, serialize_pareto_csv(run.pareto_result))
            )
        _write_artifacts(tuple(artifacts), overwrite=args.overwrite)
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
    except (
        HistoricalExperimentAuditError,
        HistoricalExperimentPairwiseOutputError,
        HistoricalExperimentParetoOutputError,
        HistoricalExperimentReportOutputError,
        AuditOutputError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 7
    if not args.quiet:
        print(run.summary, end="")
        if compact_requested:
            print(
                _compact_success(run.compact_report, compact_json, compact_csv),
                end="",
            )
        if pairwise_json is not None or pairwise_csv is not None:
            print(_pairwise_success(pairwise_json, pairwise_csv), end="")
        if pareto_json is not None or pareto_csv is not None:
            print(_pareto_success(pareto_json, pareto_csv), end="")
    return 0
