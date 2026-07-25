"""Run deterministic offline walk-forward experiment evaluation."""

import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from trading_bot.cli._simulation_bootstrap import initialize_canonical_ledger
from trading_bot.cli.coordinated_output import (
    OutputArtifact,
    normalized_destinations,
    preflight_destinations,
    write_artifacts,
)
from trading_bot.cli.exceptions import (
    ConfigJsonError,
    ConfigReadError,
    ConfigValidationError,
    WalkForwardExperimentDataError,
    WalkForwardExperimentExecutionCliError,
    WalkForwardExperimentInitializationCliError,
    WalkForwardExperimentOutputError,
)
from trading_bot.cli.walk_forward_aggregate_serialization import (
    serialize_walk_forward_aggregate_csv,
    serialize_walk_forward_aggregate_json,
)
from trading_bot.cli.walk_forward_experiment_config import (
    LoadedWalkForwardExperimentConfig,
    load_walk_forward_experiment_config,
)
from trading_bot.cli.walk_forward_experiment_serialization import (
    serialize_walk_forward_csv,
    serialize_walk_forward_json,
)
from trading_bot.execution import OrderEngine
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.experiments import (
    HistoricalExperimentInitializationError,
    HistoricalExperimentWalkForwardAggregateAnalyzer,
    HistoricalExperimentWalkForwardAggregateError,
    HistoricalExperimentWalkForwardAggregateResult,
    HistoricalExperimentWalkForwardDataError,
    HistoricalExperimentWalkForwardError,
    HistoricalExperimentWalkForwardFoldError,
    HistoricalExperimentWalkForwardRequest,
    HistoricalExperimentWalkForwardResult,
    HistoricalExperimentWalkForwardRunner,
    InvalidHistoricalExperimentWalkForwardRequestError,
)
from trading_bot.ledger import LedgerError
from trading_bot.market_data import (
    CoordinatingHistoricalDataProvider,
    CSVHistoricalDataProvider,
    HistoricalDataError,
    MultiSymbolHistoricalDataRequest,
)
from trading_bot.runtime import PaperPortfolioRuntime
from trading_bot.simulation import OptimizedPaperPortfolioSimulator

_BOOTSTRAP_NAMESPACE = UUID("45bf9ca7-299d-5661-a18f-9252a995a89c")
_BOOTSTRAP_VERSION = "walk-forward-experiment-cli-bootstrap-v1"
_runner_type = HistoricalExperimentWalkForwardRunner
_coordinator_type = CoordinatingHistoricalDataProvider
_json_serializer = serialize_walk_forward_json
_csv_serializer = serialize_walk_forward_csv
_aggregate_analyzer_type = HistoricalExperimentWalkForwardAggregateAnalyzer
_aggregate_json_serializer = serialize_walk_forward_aggregate_json
_aggregate_csv_serializer = serialize_walk_forward_aggregate_csv


class _WalkForwardSimulatorFactory:
    def __init__(self) -> None:
        self._contexts: set[tuple[UUID, UUID, int]] = set()

    def __call__(
        self,
        initial_state,
        *,
        experiment_request_id,
        variant_id,
        variant_ordinal,
    ) -> OptimizedPaperPortfolioSimulator:  # type: ignore[no-untyped-def]
        context = (experiment_request_id, variant_id, variant_ordinal)
        if context in self._contexts:
            raise ValueError("duplicate walk-forward factory construction context")
        self._contexts.add(context)
        ledger, _ = initialize_canonical_ledger(
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
        return OptimizedPaperPortfolioSimulator(
            PaperPortfolioRuntime(OrderEngine(), ledger)
        )


@dataclass(frozen=True, slots=True)
class WalkForwardExperimentCliRunResult:
    config: LoadedWalkForwardExperimentConfig
    result: HistoricalExperimentWalkForwardResult
    summary: str
    aggregate_result: HistoricalExperimentWalkForwardAggregateResult | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a deterministic offline walk-forward experiment."
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--json-pretty", action="store_true")
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--aggregate-json", type=Path)
    parser.add_argument("--aggregate-json-pretty", action="store_true")
    parser.add_argument("--aggregate-csv", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def run_cli(
    config_path: Path,
    *,
    loaded_config: LoadedWalkForwardExperimentConfig | None = None,
) -> WalkForwardExperimentCliRunResult:
    config = (
        load_walk_forward_experiment_config(config_path)
        if loaded_config is None
        else loaded_config
    )
    historical_config = config.historical_data
    coordinator = _coordinator_type(
        CSVHistoricalDataProvider(historical_config.common_parent)
    )
    history_request = MultiSymbolHistoricalDataRequest(
        historical_config.symbols,
        historical_config.start,
        historical_config.end,
        historical_config.timeframe,
        historical_config.adjustment,
        historical_config.missing_bar_policy,
    )
    try:
        historical = coordinator.get_bars(history_request)
    except HistoricalDataError as error:
        sources = ", ".join(
            f"{item.symbol}={item.configured_path}"
            for item in historical_config.sources
        )
        raise WalkForwardExperimentDataError(
            "cannot load walk-forward historical interval "
            f"[{historical_config.start.isoformat()}, "
            f"{historical_config.end.isoformat()}): {sources}: {error}"
        ) from error
    if historical.symbols != historical_config.symbols:
        raise WalkForwardExperimentDataError(
            "loaded historical symbol order differs from configuration"
        )
    try:
        request = HistoricalExperimentWalkForwardRequest(
            config.request_id,
            historical,
            config.folds,
            config.initial_state,
            config.variants,
            config.selection_policy,
            config.metadata,
        )
    except InvalidHistoricalExperimentWalkForwardRequestError as error:
        raise ConfigValidationError("$", str(error)) from error
    factory = _WalkForwardSimulatorFactory()
    try:
        runner = _runner_type(factory)
        result = runner.run(request)
    except InvalidHistoricalExperimentWalkForwardRequestError as error:
        raise ConfigValidationError("$", str(error)) from error
    except HistoricalExperimentWalkForwardDataError as error:
        raise ConfigValidationError("$", str(error)) from error
    except HistoricalExperimentWalkForwardFoldError as error:
        message = _fold_failure_message(error)
        if isinstance(error.cause, HistoricalExperimentInitializationError):
            raise WalkForwardExperimentInitializationCliError(message) from error
        raise WalkForwardExperimentExecutionCliError(message) from error
    except HistoricalExperimentWalkForwardError as error:
        raise WalkForwardExperimentExecutionCliError(str(error)) from error
    aggregate_result = None
    if config.aggregate_policy is not None:
        try:
            aggregate_result = _aggregate_analyzer_type().analyze(
                result, config.aggregate_policy
            )
        except HistoricalExperimentWalkForwardAggregateError as error:
            raise WalkForwardExperimentExecutionCliError(
                f"walk-forward aggregate analysis failed: {error}"
            ) from error
    summary = _format_summary(result)
    if aggregate_result is not None:
        summary += _format_aggregate_summary(aggregate_result)
    return WalkForwardExperimentCliRunResult(config, result, summary, aggregate_result)


def _format_aggregate_summary(
    result: HistoricalExperimentWalkForwardAggregateResult,
) -> str:
    lines = [
        "Walk-forward aggregate distribution:",
        "  IMPORTANT: Every test fold is an independent simulation with "
        "independently initialized capital.",
        "  These statistics describe a distribution of fold observations; they "
        "do not describe a continuous portfolio or equity curve.",
        "  Values are not summed, compounded, annualized, weighted, ranked, or "
        "recommendations.",
        f"  aggregate result ID: {result.result_id}",
        f"  source walk-forward result ID: {result.source_walk_forward_result_id}",
        f"  aggregate policy ID: {result.policy.policy_id}",
        f"  fold count: {result.fold_count}",
        f"  successful test fold count: {result.successful_test_fold_count}",
        "  metric distributions:",
    ]
    for summary in result.metric_summaries:
        lines.append(f"    {summary.metric.value}:")
        lines.append(
            "      observations: "
            + ", ".join(_scalar(item.value) for item in summary.observations)
        )
        for label, value in (
            ("minimum", summary.minimum),
            ("maximum", summary.maximum),
            ("median", summary.median),
        ):
            if value is not None:
                lines.append(f"      {label}: {_scalar(value)}")
        if summary.arithmetic_mean is not None:
            lines.append(
                "      equal-fold arithmetic mean: "
                f"{summary.arithmetic_mean.numerator}/"
                f"{summary.arithmetic_mean.denominator}"
            )
        if summary.sign_counts is not None:
            signs = summary.sign_counts
            lines.append(
                "      sign counts: "
                f"positive={signs.positive}, zero={signs.zero}, "
                f"negative={signs.negative}"
            )
    lines.append(
        "  selection frequencies (descriptive only; they imply no quality ordering):"
    )
    lines.extend(
        f"    variant {item.variant_id}: selected folds "
        f"{item.selected_fold_count}, rank-one selected folds "
        f"{item.rank_one_selected_fold_count}"
        for item in result.variant_frequencies
    )
    return "\n".join(lines) + "\n"


def _format_summary(result: HistoricalExperimentWalkForwardResult) -> str:
    policy = result.selection_policy.ranking_policy
    lines = [
        "Walk-forward experiment:",
        f"  request ID: {result.request_id}",
        f"  result ID: {result.result_id}",
        f"  source historical fingerprint: {result.source_historical_fingerprint}",
        f"  fold count: {len(result.folds)}",
        "Selection policy:",
        f"  policy ID: {result.selection_policy.policy_id}",
        f"  ranking policy ID: {policy.policy_id}",
        "  criteria:",
        *(
            f"    {index}. {item.metric.value} {item.direction.value}"
            for index, item in enumerate(policy.criteria, start=1)
        ),
        f"  tie breaker: {policy.tie_breaker.value}",
    ]
    for item in result.folds:
        fold = item.fold
        lines.extend(
            (
                f"Fold {item.ordinal}:",
                f"  fold ID: {fold.fold_id}",
                "  training interval: "
                f"[{fold.training_start.isoformat()}, {fold.training_end.isoformat()})",
                f"  training request ID: {item.training_request_id}",
                f"  training report ID: {item.training_report.report_id}",
                "  training candidates:",
            )
        )
        lines.extend(
            "    caller ordinal "
            f"{row.caller_ordinal} | rank {row.rank} | variant {row.variant_id} | "
            f"training run {row.experiment_run_id}"
            for row in item.training_report.variants
        )
        selection = item.selection
        test_row = item.test_report.variants[0]
        lines.extend(
            (
                f"  selected rank: {selection.selected_rank}",
                f"  selected caller ordinal: {selection.selected_caller_ordinal}",
                f"  selected variant ID: {selection.selected_variant_id}",
                f"  selected training run ID: {selection.selected_training_run_id}",
                "  test interval: "
                f"[{fold.test_start.isoformat()}, {fold.test_end.isoformat()})",
                f"  test request ID: {item.test_request_id}",
                f"  test report ID: {item.test_report.report_id}",
                f"  test run ID: {item.test_run_id}",
                f"  test rolling result ID: {item.test_rolling_result_id}",
                "  test metrics:",
            )
        )
        lines.extend(
            f"    {name}: {_scalar(getattr(test_row.metrics, name))}"
            for name in test_row.metrics.__dataclass_fields__
        )
    lines.append(
        "Fold evaluations are independent; no aggregate out-of-sample metrics "
        "or continuous equity curve are defined."
    )
    return "\n".join(lines) + "\n"


def _scalar(value: Decimal | int) -> str:
    return canonical_decimal(value) if isinstance(value, Decimal) else str(value)


def _fold_failure_message(error: HistoricalExperimentWalkForwardFoldError) -> str:
    return f"fold {error.fold_ordinal} ({error.fold_id}) at {error.stage}: {error}"


def _success(
    result: HistoricalExperimentWalkForwardResult,
    json_path: Path | None,
    csv_path: Path | None,
    aggregate_result: HistoricalExperimentWalkForwardAggregateResult | None = None,
    aggregate_json_path: Path | None = None,
    aggregate_csv_path: Path | None = None,
) -> str:
    lines = ["Walk-forward artifacts:", f"  result ID: {result.result_id}"]
    if json_path is not None:
        lines.append(f"  JSON: {json_path}")
    if csv_path is not None:
        lines.append(f"  CSV: {csv_path}")
    if aggregate_result is not None and (
        aggregate_json_path is not None or aggregate_csv_path is not None
    ):
        lines.extend(
            (
                "Walk-forward aggregate artifacts:",
                f"  result ID: {aggregate_result.result_id}",
            )
        )
    if aggregate_json_path is not None:
        lines.append(f"  aggregate JSON: {aggregate_json_path}")
    if aggregate_csv_path is not None:
        lines.append(f"  aggregate CSV: {aggregate_csv_path}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.json_pretty and args.json is None:
        parser.error("--json-pretty requires --json")
    if args.aggregate_json_pretty and args.aggregate_json is None:
        parser.error("--aggregate-json-pretty requires --aggregate-json")
    raw_destinations = (
        args.json,
        args.csv,
        args.aggregate_json,
        args.aggregate_csv,
    )
    if args.overwrite and not any(item is not None for item in raw_destinations):
        parser.error("--overwrite requires an output destination")
    json_path, csv_path, aggregate_json_path, aggregate_csv_path = (
        normalized_destinations(raw_destinations)
    )
    destinations = tuple(
        item
        for item in (json_path, csv_path, aggregate_json_path, aggregate_csv_path)
        if item is not None
    )
    if len(set(destinations)) != len(destinations):
        parser.error("output destinations must be pairwise distinct")
    try:
        preflight_destinations(
            destinations,
            overwrite=args.overwrite,
            error_factory=WalkForwardExperimentOutputError,
        )
        config = load_walk_forward_experiment_config(args.config)
        if config.schema_version == 1 and (
            aggregate_json_path is not None or aggregate_csv_path is not None
        ):
            raise ConfigValidationError(
                "$.schema_version",
                "aggregate destinations require walk-forward schema version 2",
            )
        run = run_cli(args.config, loaded_config=config)
        artifacts = []
        if json_path is not None:
            artifacts.append(
                OutputArtifact(
                    json_path,
                    _json_serializer(run.result, pretty=args.json_pretty),
                )
            )
        if csv_path is not None:
            artifacts.append(OutputArtifact(csv_path, _csv_serializer(run.result)))
        if aggregate_json_path is not None:
            if run.aggregate_result is None:
                raise WalkForwardExperimentOutputError(
                    "aggregate result is unavailable"
                )
            artifacts.append(
                OutputArtifact(
                    aggregate_json_path,
                    _aggregate_json_serializer(
                        run.aggregate_result, pretty=args.aggregate_json_pretty
                    ),
                )
            )
        if aggregate_csv_path is not None:
            if run.aggregate_result is None:
                raise WalkForwardExperimentOutputError(
                    "aggregate result is unavailable"
                )
            artifacts.append(
                OutputArtifact(
                    aggregate_csv_path,
                    _aggregate_csv_serializer(run.aggregate_result),
                )
            )
        write_artifacts(
            tuple(artifacts),
            overwrite=args.overwrite,
            error_factory=WalkForwardExperimentOutputError,
            write_error_prefix="cannot write walk-forward output",
        )
    except (ConfigReadError, ConfigJsonError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 3
    except (ConfigValidationError, WalkForwardExperimentDataError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 4
    except (WalkForwardExperimentInitializationCliError, LedgerError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 5
    except WalkForwardExperimentExecutionCliError as error:
        print(f"error: {error}", file=sys.stderr)
        return 6
    except WalkForwardExperimentOutputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 7
    if not args.quiet:
        print(run.summary, end="")
        if destinations:
            print(
                _success(
                    run.result,
                    json_path,
                    csv_path,
                    run.aggregate_result,
                    aggregate_json_path,
                    aggregate_csv_path,
                ),
                end="",
            )
    return 0
