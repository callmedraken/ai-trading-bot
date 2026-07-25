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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a deterministic offline walk-forward experiment."
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--json-pretty", action="store_true")
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def run_cli(config_path: Path) -> WalkForwardExperimentCliRunResult:
    config = load_walk_forward_experiment_config(config_path)
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
    return WalkForwardExperimentCliRunResult(config, result, _format_summary(result))


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
) -> str:
    lines = ["Walk-forward artifacts:", f"  result ID: {result.result_id}"]
    if json_path is not None:
        lines.append(f"  JSON: {json_path}")
    if csv_path is not None:
        lines.append(f"  CSV: {csv_path}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.json_pretty and args.json is None:
        parser.error("--json-pretty requires --json")
    if args.overwrite and args.json is None and args.csv is None:
        parser.error("--overwrite requires an output destination")
    json_path, csv_path = normalized_destinations((args.json, args.csv))
    destinations = tuple(item for item in (json_path, csv_path) if item is not None)
    if len(set(destinations)) != len(destinations):
        parser.error("output destinations must be pairwise distinct")
    try:
        preflight_destinations(
            destinations,
            overwrite=args.overwrite,
            error_factory=WalkForwardExperimentOutputError,
        )
        run = run_cli(args.config)
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
            print(_success(run.result, json_path, csv_path), end="")
    return 0
