"""Strict version-one policy configuration for pairwise experiment analysis."""

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
    HistoricalExperimentPairwiseOrientation,
    HistoricalExperimentPairwisePairing,
    HistoricalExperimentPairwisePolicy,
    HistoricalExperimentRankingMetric,
    InvalidHistoricalExperimentPairwisePolicyError,
)


@dataclass(frozen=True, slots=True)
class LoadedHistoricalExperimentPairwisePolicy:
    """One canonical pairwise policy loaded from its versioned document."""

    schema_version: int
    policy: HistoricalExperimentPairwisePolicy


def load_historical_experiment_pairwise_policy(
    path: Path,
) -> LoadedHistoricalExperimentPairwisePolicy:
    """Read one strict UTF-8 pairwise-policy document."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ConfigReadError(f"cannot read pairwise policy {path}: {error}") from error
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise ConfigJsonError(
            "invalid pairwise policy JSON at "
            f"line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error
    return parse_historical_experiment_pairwise_policy(raw)


def parse_historical_experiment_pairwise_policy(
    raw: Any,
) -> LoadedHistoricalExperimentPairwisePolicy:
    """Parse one strict policy document without running an experiment."""
    root = _object(raw, "$")
    _exact_keys(root, {"schema_version", "policy"}, "$")
    version = _integer(root["schema_version"], "$.schema_version")
    if version != 1:
        raise ConfigValidationError(
            "$.schema_version", "unsupported pairwise policy schema version"
        )

    path = "$.policy"
    item = _object(root["policy"], path)
    _exact_keys(
        item,
        {
            "policy_id",
            "metrics",
            "pairing",
            "orientation",
            "baseline_variant_id",
            "metadata",
        },
        path,
    )
    metrics = tuple(
        _enum(value, HistoricalExperimentRankingMetric, f"{path}.metrics[{index}]")
        for index, value in enumerate(
            _array(item["metrics"], f"{path}.metrics", nonempty=True)
        )
    )
    baseline = item["baseline_variant_id"]
    try:
        policy = HistoricalExperimentPairwisePolicy(
            _uuid(item["policy_id"], f"{path}.policy_id"),
            metrics,
            _enum(
                item["pairing"],
                HistoricalExperimentPairwisePairing,
                f"{path}.pairing",
            ),
            _enum(
                item["orientation"],
                HistoricalExperimentPairwiseOrientation,
                f"{path}.orientation",
            ),
            (
                None
                if baseline is None
                else _uuid(baseline, f"{path}.baseline_variant_id")
            ),
            _metadata(item["metadata"], f"{path}.metadata"),
        )
    except InvalidHistoricalExperimentPairwisePolicyError as error:
        message = str(error)
        if "metrics" in message:
            error_path = f"{path}.metrics"
        elif "orientation" in message:
            error_path = f"{path}.orientation"
        elif "baseline" in message:
            error_path = f"{path}.baseline_variant_id"
        elif "metadata" in message or "reserved" in message:
            error_path = f"{path}.metadata"
        else:
            error_path = path
        raise ConfigValidationError(error_path, message) from error
    return LoadedHistoricalExperimentPairwisePolicy(version, policy)
