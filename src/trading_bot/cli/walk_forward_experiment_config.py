"""Strict configuration for walk-forward experiment evaluation."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from trading_bot.cli.config import (
    _array,
    _datetime,
    _enum,
    _exact_keys,
    _integer,
    _metadata,
    _object,
    _uuid,
)
from trading_bot.cli.exceptions import (
    ConfigJsonError,
    ConfigReadError,
    ConfigValidationError,
)
from trading_bot.cli.historical_experiment_config import (
    parse_historical_experiment_config,
)
from trading_bot.cli.rolling_historical_config import RollingHistoricalDataConfig
from trading_bot.experiments import (
    HistoricalExperimentInitialState,
    HistoricalExperimentRankingCriterion,
    HistoricalExperimentRankingDirection,
    HistoricalExperimentRankingMetric,
    HistoricalExperimentRankingPolicy,
    HistoricalExperimentTieBreaker,
    HistoricalExperimentVariant,
    HistoricalExperimentWalkForwardAggregateMetric,
    HistoricalExperimentWalkForwardAggregateOperation,
    HistoricalExperimentWalkForwardAggregateOperationError,
    HistoricalExperimentWalkForwardAggregatePolicy,
    HistoricalExperimentWalkForwardComparabilityRule,
    HistoricalExperimentWalkForwardFold,
    HistoricalExperimentWalkForwardMetricPolicy,
    HistoricalExperimentWalkForwardSelectionPolicy,
    HistoricalExperimentWalkForwardStabilityMetric,
    HistoricalExperimentWalkForwardStabilityMetricPolicy,
    HistoricalExperimentWalkForwardStabilityOperation,
    HistoricalExperimentWalkForwardStabilityOperationError,
    HistoricalExperimentWalkForwardStabilityPolicy,
    InvalidHistoricalExperimentRankingPolicyError,
    InvalidHistoricalExperimentWalkForwardAggregatePolicyError,
    InvalidHistoricalExperimentWalkForwardRequestError,
    InvalidHistoricalExperimentWalkForwardStabilityPolicyError,
)
from trading_bot.portfolio import MetadataEntry


@dataclass(frozen=True, slots=True)
class LoadedWalkForwardExperimentConfig:
    schema_version: int
    request_id: UUID
    historical_data: RollingHistoricalDataConfig
    initial_state: HistoricalExperimentInitialState
    variants: tuple[HistoricalExperimentVariant, ...]
    folds: tuple[HistoricalExperimentWalkForwardFold, ...]
    selection_policy: HistoricalExperimentWalkForwardSelectionPolicy
    metadata: tuple[MetadataEntry, ...]
    aggregate_policy: HistoricalExperimentWalkForwardAggregatePolicy | None = None
    stability_policy: HistoricalExperimentWalkForwardStabilityPolicy | None = None


def load_walk_forward_experiment_config(
    path: Path,
) -> LoadedWalkForwardExperimentConfig:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ConfigReadError(
            f"cannot read walk-forward configuration {path}: {error}"
        ) from error
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise ConfigJsonError(
            "invalid walk-forward JSON at "
            f"line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error
    return parse_walk_forward_experiment_config(raw, path.parent)


def parse_walk_forward_experiment_config(
    raw: Any, config_directory: Path
) -> LoadedWalkForwardExperimentConfig:
    root = _object(raw, "$")
    version = _integer(root.get("schema_version"), "$.schema_version")
    if version not in (1, 2, 3):
        raise ConfigValidationError(
            "$.schema_version", "unsupported walk-forward schema version"
        )
    keys = {
        "schema_version",
        "request_id",
        "historical_data",
        "initial_state",
        "variants",
        "folds",
        "selection_policy",
        "metadata",
    }
    if version == 2:
        keys.add("aggregate_policy")
    elif version == 3:
        keys.update(("aggregate_policy", "stability_policy"))
    _exact_keys(root, keys, "$")
    raw_folds = _array(root["folds"], "$.folds", nonempty=True)
    first_fold = _object(raw_folds[0], "$.folds[0]")
    first_schedule = _array(
        first_fold.get("training_rebalance_timestamps"),
        "$.folds[0].training_rebalance_timestamps",
        nonempty=True,
    )
    shared = parse_historical_experiment_config(
        {
            "schema_version": 3,
            "request_id": root["request_id"],
            "historical_data": root["historical_data"],
            "rebalance_schedule": first_schedule,
            "initial_state": root["initial_state"],
            "variants": root["variants"],
            "variant_grid": None,
            "metadata": [],
            "ranking": None,
        },
        config_directory,
    )
    if shared.explicit_variants is None or shared.grid_specification is not None:
        raise ConfigValidationError("$.variants", "walk-forward grids are unsupported")
    folds = tuple(
        _fold(value, f"$.folds[{index}]") for index, value in enumerate(raw_folds)
    )
    _validate_fold_collection(folds)
    selection = _selection_policy(root["selection_policy"], "$.selection_policy")
    metadata = _metadata(root["metadata"], "$.metadata")
    if any(
        item.key.startswith("historical_experiment_walk_forward_") for item in metadata
    ):
        raise ConfigValidationError(
            "$.metadata",
            "historical_experiment_walk_forward_ metadata keys are reserved",
        )
    aggregate_policy = None
    if version == 2:
        aggregate_policy = _aggregate_policy(
            root["aggregate_policy"], "$.aggregate_policy"
        )
    elif version == 3 and root["aggregate_policy"] is not None:
        aggregate_policy = _aggregate_policy(
            root["aggregate_policy"], "$.aggregate_policy"
        )
    stability_policy = (
        _stability_policy(root["stability_policy"], "$.stability_policy")
        if version == 3
        else None
    )
    return LoadedWalkForwardExperimentConfig(
        version,
        _uuid(root["request_id"], "$.request_id"),
        shared.historical_data,
        shared.initial_state,
        shared.explicit_variants,
        folds,
        selection,
        metadata,
        aggregate_policy,
        stability_policy,
    )


def _stability_policy(
    value: Any, path: str
) -> HistoricalExperimentWalkForwardStabilityPolicy:
    item = _object(value, path)
    _exact_keys(item, {"policy_id", "metrics", "metadata"}, path)
    metrics = []
    for index, raw in enumerate(
        _array(item["metrics"], f"{path}.metrics", nonempty=True)
    ):
        metric_path = f"{path}.metrics[{index}]"
        metric_item = _object(raw, metric_path)
        _exact_keys(
            metric_item,
            {"metric", "operations", "comparability_rule"},
            metric_path,
        )
        operations = tuple(
            _enum(
                operation,
                HistoricalExperimentWalkForwardStabilityOperation,
                f"{metric_path}.operations[{operation_index}]",
            )
            for operation_index, operation in enumerate(
                _array(metric_item["operations"], f"{metric_path}.operations")
            )
        )
        try:
            metrics.append(
                HistoricalExperimentWalkForwardStabilityMetricPolicy(
                    _enum(
                        metric_item["metric"],
                        HistoricalExperimentWalkForwardStabilityMetric,
                        f"{metric_path}.metric",
                    ),
                    operations,
                    _enum(
                        metric_item["comparability_rule"],
                        HistoricalExperimentWalkForwardComparabilityRule,
                        f"{metric_path}.comparability_rule",
                    ),
                )
            )
        except (
            InvalidHistoricalExperimentWalkForwardStabilityPolicyError,
            HistoricalExperimentWalkForwardStabilityOperationError,
        ) as error:
            raise ConfigValidationError(metric_path, str(error)) from error
    try:
        return HistoricalExperimentWalkForwardStabilityPolicy(
            _uuid(item["policy_id"], f"{path}.policy_id"),
            tuple(metrics),
            _metadata(item["metadata"], f"{path}.metadata"),
        )
    except (
        InvalidHistoricalExperimentWalkForwardStabilityPolicyError,
        HistoricalExperimentWalkForwardStabilityOperationError,
    ) as error:
        raise ConfigValidationError(path, str(error)) from error


def _aggregate_policy(
    value: Any, path: str
) -> HistoricalExperimentWalkForwardAggregatePolicy:
    item = _object(value, path)
    _exact_keys(item, {"policy_id", "metrics", "metadata"}, path)
    metrics = []
    for index, raw in enumerate(
        _array(item["metrics"], f"{path}.metrics", nonempty=True)
    ):
        metric_path = f"{path}.metrics[{index}]"
        metric_item = _object(raw, metric_path)
        _exact_keys(metric_item, {"metric", "operations"}, metric_path)
        operations = tuple(
            _enum(
                operation,
                HistoricalExperimentWalkForwardAggregateOperation,
                f"{metric_path}.operations[{operation_index}]",
            )
            for operation_index, operation in enumerate(
                _array(metric_item["operations"], f"{metric_path}.operations")
            )
        )
        try:
            metrics.append(
                HistoricalExperimentWalkForwardMetricPolicy(
                    _enum(
                        metric_item["metric"],
                        HistoricalExperimentWalkForwardAggregateMetric,
                        f"{metric_path}.metric",
                    ),
                    operations,
                )
            )
        except (
            InvalidHistoricalExperimentWalkForwardAggregatePolicyError,
            HistoricalExperimentWalkForwardAggregateOperationError,
        ) as error:
            raise ConfigValidationError(metric_path, str(error)) from error
    try:
        return HistoricalExperimentWalkForwardAggregatePolicy(
            _uuid(item["policy_id"], f"{path}.policy_id"),
            tuple(metrics),
            _metadata(item["metadata"], f"{path}.metadata"),
        )
    except (
        InvalidHistoricalExperimentWalkForwardAggregatePolicyError,
        HistoricalExperimentWalkForwardAggregateOperationError,
    ) as error:
        raise ConfigValidationError(path, str(error)) from error


def _fold(value: Any, path: str) -> HistoricalExperimentWalkForwardFold:
    item = _object(value, path)
    _exact_keys(
        item,
        {
            "fold_id",
            "training_start",
            "training_end",
            "test_start",
            "test_end",
            "training_rebalance_timestamps",
            "test_rebalance_timestamps",
            "metadata",
        },
        path,
    )
    training = tuple(
        _datetime(raw, f"{path}.training_rebalance_timestamps[{index}]")
        for index, raw in enumerate(
            _array(
                item["training_rebalance_timestamps"],
                f"{path}.training_rebalance_timestamps",
                nonempty=True,
            )
        )
    )
    test = tuple(
        _datetime(raw, f"{path}.test_rebalance_timestamps[{index}]")
        for index, raw in enumerate(
            _array(
                item["test_rebalance_timestamps"],
                f"{path}.test_rebalance_timestamps",
                nonempty=True,
            )
        )
    )
    try:
        return HistoricalExperimentWalkForwardFold(
            _uuid(item["fold_id"], f"{path}.fold_id"),
            _datetime(item["training_start"], f"{path}.training_start"),
            _datetime(item["training_end"], f"{path}.training_end"),
            _datetime(item["test_start"], f"{path}.test_start"),
            _datetime(item["test_end"], f"{path}.test_end"),
            training,
            test,
            _metadata(item["metadata"], f"{path}.metadata"),
        )
    except InvalidHistoricalExperimentWalkForwardRequestError as error:
        raise ConfigValidationError(path, str(error)) from error


def _selection_policy(
    value: Any, path: str
) -> HistoricalExperimentWalkForwardSelectionPolicy:
    item = _object(value, path)
    _exact_keys(item, {"policy_id", "ranking_policy", "metadata"}, path)
    ranking_path = f"{path}.ranking_policy"
    ranking_item = _object(item["ranking_policy"], ranking_path)
    _exact_keys(
        ranking_item,
        {"policy_id", "criteria", "tie_breaker", "metadata"},
        ranking_path,
    )
    criteria = tuple(
        _criterion(raw, f"{ranking_path}.criteria[{index}]")
        for index, raw in enumerate(
            _array(
                ranking_item["criteria"],
                f"{ranking_path}.criteria",
                nonempty=True,
            )
        )
    )
    try:
        ranking = HistoricalExperimentRankingPolicy(
            _uuid(ranking_item["policy_id"], f"{ranking_path}.policy_id"),
            criteria,
            _enum(
                ranking_item["tie_breaker"],
                HistoricalExperimentTieBreaker,
                f"{ranking_path}.tie_breaker",
            ),
            _metadata(ranking_item["metadata"], f"{ranking_path}.metadata"),
        )
        return HistoricalExperimentWalkForwardSelectionPolicy(
            _uuid(item["policy_id"], f"{path}.policy_id"),
            ranking,
            _metadata(item["metadata"], f"{path}.metadata"),
        )
    except (
        InvalidHistoricalExperimentRankingPolicyError,
        InvalidHistoricalExperimentWalkForwardRequestError,
    ) as error:
        raise ConfigValidationError(path, str(error)) from error


def _validate_fold_collection(
    folds: tuple[HistoricalExperimentWalkForwardFold, ...],
) -> None:
    if len({item.fold_id for item in folds}) != len(folds):
        raise ConfigValidationError("$.folds", "fold IDs must be unique")
    for index, (previous, current) in enumerate(
        zip(folds, folds[1:], strict=False), start=1
    ):
        path = f"$.folds[{index}]"
        if current.training_start < previous.training_start:
            raise ConfigValidationError(path, "training_start must be nondecreasing")
        if current.training_end <= previous.training_end:
            raise ConfigValidationError(
                path, "training_end must be strictly increasing"
            )
        if (
            current.test_start <= previous.test_start
            or current.test_end <= previous.test_end
        ):
            raise ConfigValidationError(path, "test bounds must be strictly increasing")
        if previous.test_end > current.test_start:
            raise ConfigValidationError(path, "test intervals must be disjoint")


def _criterion(value: Any, path: str) -> HistoricalExperimentRankingCriterion:
    item = _object(value, path)
    _exact_keys(item, {"metric", "direction"}, path)
    try:
        return HistoricalExperimentRankingCriterion(
            _enum(item["metric"], HistoricalExperimentRankingMetric, f"{path}.metric"),
            _enum(
                item["direction"],
                HistoricalExperimentRankingDirection,
                f"{path}.direction",
            ),
        )
    except InvalidHistoricalExperimentRankingPolicyError as error:
        raise ConfigValidationError(path, str(error)) from error
