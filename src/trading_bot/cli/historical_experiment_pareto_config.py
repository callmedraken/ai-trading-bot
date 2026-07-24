"""Strict version-one policy configuration for Pareto experiment analysis."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trading_bot.cli.config import (
    _array,
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
from trading_bot.experiments import (
    HistoricalExperimentParetoObjective,
    HistoricalExperimentParetoPolicy,
    HistoricalExperimentRankingDirection,
    HistoricalExperimentRankingMetric,
    InvalidHistoricalExperimentParetoPolicyError,
)


@dataclass(frozen=True, slots=True)
class LoadedHistoricalExperimentParetoPolicy:
    schema_version: int
    policy: HistoricalExperimentParetoPolicy


def load_historical_experiment_pareto_policy(
    path: Path,
) -> LoadedHistoricalExperimentParetoPolicy:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ConfigReadError(f"cannot read Pareto policy {path}: {error}") from error
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise ConfigJsonError(
            f"invalid Pareto policy JSON at line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from error
    return parse_historical_experiment_pareto_policy(raw)


def parse_historical_experiment_pareto_policy(
    raw: Any,
) -> LoadedHistoricalExperimentParetoPolicy:
    root = _object(raw, "$")
    _exact_keys(root, {"schema_version", "policy"}, "$")
    version = _integer(root["schema_version"], "$.schema_version")
    if version != 1:
        raise ConfigValidationError(
            "$.schema_version", "unsupported Pareto policy schema version"
        )
    path = "$.policy"
    item = _object(root["policy"], path)
    _exact_keys(item, {"policy_id", "objectives", "metadata"}, path)
    objectives = []
    for index, raw_objective in enumerate(
        _array(item["objectives"], f"{path}.objectives", nonempty=True)
    ):
        objective_path = f"{path}.objectives[{index}]"
        objective = _object(raw_objective, objective_path)
        _exact_keys(objective, {"metric", "direction"}, objective_path)
        objectives.append(
            HistoricalExperimentParetoObjective(
                _enum(
                    objective["metric"],
                    HistoricalExperimentRankingMetric,
                    f"{objective_path}.metric",
                ),
                _enum(
                    objective["direction"],
                    HistoricalExperimentRankingDirection,
                    f"{objective_path}.direction",
                ),
            )
        )
    try:
        policy = HistoricalExperimentParetoPolicy(
            _uuid(item["policy_id"], f"{path}.policy_id"),
            tuple(objectives),
            _metadata(item["metadata"], f"{path}.metadata"),
        )
    except InvalidHistoricalExperimentParetoPolicyError as error:
        message = str(error)
        error_path = (
            f"{path}.objectives"
            if "objective" in message
            else f"{path}.metadata"
            if "metadata" in message or "reserved" in message
            else path
        )
        raise ConfigValidationError(error_path, message) from error
    return LoadedHistoricalExperimentParetoPolicy(version, policy)
