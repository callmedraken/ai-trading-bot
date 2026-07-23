"""Strict version-two configuration for offline historical experiments."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from trading_bot.cli.config import (
    _array,
    _boolean,
    _constraints,
    _datetime,
    _decimal,
    _enum,
    _exact_keys,
    _fill_policy,
    _integer,
    _metadata,
    _object,
    _string,
    _symbol,
    _uuid,
)
from trading_bot.cli.exceptions import (
    ConfigJsonError,
    ConfigReadError,
    ConfigValidationError,
)
from trading_bot.cli.rolling_historical_config import (
    RollingHistoricalDataConfig,
    _execution_prices,
    _historical_data,
    _optimization,
    _rebalance_section,
    _risk_section,
    _rolling_window,
    _scenario,
    _timing,
)
from trading_bot.experiments import (
    HistoricalExperimentBootstrapPosition,
    HistoricalExperimentInitializationMode,
    HistoricalExperimentInitialState,
    HistoricalExperimentRankingCriterion,
    HistoricalExperimentRankingDirection,
    HistoricalExperimentRankingMetric,
    HistoricalExperimentRankingPolicy,
    HistoricalExperimentTieBreaker,
    HistoricalExperimentVariant,
    InvalidHistoricalExperimentRankingPolicyError,
)
from trading_bot.portfolio import MetadataEntry


@dataclass(frozen=True, slots=True)
class LoadedHistoricalExperimentConfig:
    """Canonical experiment configuration with operational paths excluded."""

    schema_version: int
    request_id: UUID
    historical_data: RollingHistoricalDataConfig
    rebalance_schedule: tuple[datetime, ...]
    initial_state: HistoricalExperimentInitialState
    variants: tuple[HistoricalExperimentVariant, ...]
    metadata: tuple[MetadataEntry, ...]
    ranking_policy: HistoricalExperimentRankingPolicy | None


def load_historical_experiment_config(
    path: Path,
) -> LoadedHistoricalExperimentConfig:
    """Read strict UTF-8 JSON relative to its own directory."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ConfigReadError(f"cannot read configuration {path}: {error}") from error
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise ConfigJsonError(
            f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error
    return parse_historical_experiment_config(raw, path.parent)


def parse_historical_experiment_config(
    raw: Any, config_directory: Path
) -> LoadedHistoricalExperimentConfig:
    """Parse one strict experiment document without constructing rolling work."""
    root = dict(_object(raw, "$"))
    root.setdefault("ranking", None)
    _exact_keys(
        root,
        {
            "schema_version",
            "request_id",
            "historical_data",
            "rebalance_schedule",
            "initial_state",
            "variants",
            "metadata",
            "ranking",
        },
        "$",
    )
    version = _integer(root["schema_version"], "$.schema_version")
    if version != 2:
        raise ConfigValidationError(
            "$.schema_version",
            "unsupported schema version; historical experiment CLI requires version 2",
        )
    historical = _historical_data(root["historical_data"], config_directory)
    schedule = tuple(
        _datetime(value, f"$.rebalance_schedule[{index}]")
        for index, value in enumerate(
            _array(root["rebalance_schedule"], "$.rebalance_schedule", nonempty=True)
        )
    )
    for index in range(1, len(schedule)):
        if schedule[index] <= schedule[index - 1]:
            raise ConfigValidationError(
                f"$.rebalance_schedule[{index}]",
                "timestamps must be strictly increasing and unique",
            )
    initial = _initial_state(root["initial_state"], historical, schedule)
    variants = tuple(
        _variant(value, f"$.variants[{index}]")
        for index, value in enumerate(
            _array(root["variants"], "$.variants", nonempty=True)
        )
    )
    if len({item.variant_id for item in variants}) != len(variants):
        raise ConfigValidationError("$.variants", "variant IDs must be unique")
    names = tuple(item.name.strip().casefold() for item in variants)
    if len(set(names)) != len(names):
        raise ConfigValidationError(
            "$.variants", "variant names must be unique after normalization"
        )
    metadata = _metadata(root["metadata"], "$.metadata")
    _reject_reserved_metadata(metadata, "$.metadata")
    ranking = _ranking(root["ranking"], "$.ranking")
    return LoadedHistoricalExperimentConfig(
        version,
        _uuid(root["request_id"], "$.request_id"),
        historical,
        schedule,
        initial,
        variants,
        metadata,
        ranking,
    )


def _ranking(value: Any, path: str) -> HistoricalExperimentRankingPolicy | None:
    if value is None:
        return None
    item = _object(value, path)
    _exact_keys(item, {"policy_id", "criteria", "tie_breaker", "metadata"}, path)
    criteria = tuple(
        _ranking_criterion(raw, f"{path}.criteria[{index}]")
        for index, raw in enumerate(
            _array(item["criteria"], f"{path}.criteria", nonempty=True)
        )
    )
    metadata = _metadata(item["metadata"], f"{path}.metadata")
    try:
        return HistoricalExperimentRankingPolicy(
            _uuid(item["policy_id"], f"{path}.policy_id"),
            criteria,
            _enum(
                item["tie_breaker"],
                HistoricalExperimentTieBreaker,
                f"{path}.tie_breaker",
            ),
            metadata,
        )
    except ConfigValidationError:
        raise
    except InvalidHistoricalExperimentRankingPolicyError as error:
        raise ConfigValidationError(path, str(error)) from error


def _ranking_criterion(value: Any, path: str) -> HistoricalExperimentRankingCriterion:
    item = _object(value, path)
    _exact_keys(item, {"metric", "direction"}, path)
    try:
        return HistoricalExperimentRankingCriterion(
            _enum(
                item["metric"],
                HistoricalExperimentRankingMetric,
                f"{path}.metric",
            ),
            _enum(
                item["direction"],
                HistoricalExperimentRankingDirection,
                f"{path}.direction",
            ),
        )
    except ConfigValidationError:
        raise
    except InvalidHistoricalExperimentRankingPolicyError as error:
        raise ConfigValidationError(path, str(error)) from error


def _initial_state(
    value: Any,
    historical: RollingHistoricalDataConfig,
    schedule: tuple[datetime, ...],
) -> HistoricalExperimentInitialState:
    path = "$.initial_state"
    item = _object(value, path)
    _exact_keys(
        item,
        {
            "mode",
            "as_of",
            "available_cash",
            "bootstrap_commission",
            "bootstrap_positions",
        },
        path,
    )
    positions = tuple(
        _bootstrap_position(raw, f"{path}.bootstrap_positions[{index}]")
        for index, raw in enumerate(
            _array(item["bootstrap_positions"], f"{path}.bootstrap_positions")
        )
    )
    if len({position.symbol for position in positions}) != len(positions):
        raise ConfigValidationError(
            f"{path}.bootstrap_positions", "symbols must be unique"
        )
    if any(position.symbol not in historical.symbols for position in positions):
        raise ConfigValidationError(
            f"{path}.bootstrap_positions",
            "bootstrap symbols must belong to the historical universe",
        )
    as_of = _datetime(item["as_of"], f"{path}.as_of")
    if as_of > schedule[0]:
        raise ConfigValidationError(
            f"{path}.as_of", "must be at or before the first rebalance"
        )
    try:
        return HistoricalExperimentInitialState(
            HistoricalExperimentInitializationMode(
                _string(item["mode"], f"{path}.mode")
            ),
            as_of,
            _decimal(item["available_cash"], f"{path}.available_cash"),
            positions,
            _decimal(item["bootstrap_commission"], f"{path}.bootstrap_commission"),
        )
    except ConfigValidationError:
        raise
    except (TypeError, ValueError) as error:
        raise ConfigValidationError(path, str(error)) from error


def _bootstrap_position(value: Any, path: str) -> HistoricalExperimentBootstrapPosition:
    item = _object(value, path)
    _exact_keys(item, {"symbol", "quantity", "unit_cost"}, path)
    try:
        return HistoricalExperimentBootstrapPosition(
            _symbol(item["symbol"], f"{path}.symbol"),
            _decimal(item["quantity"], f"{path}.quantity"),
            _decimal(item["unit_cost"], f"{path}.unit_cost"),
        )
    except ConfigValidationError:
        raise
    except (TypeError, ValueError) as error:
        raise ConfigValidationError(path, str(error)) from error


def _variant(value: Any, path: str) -> HistoricalExperimentVariant:
    item = _object(value, path)
    _exact_keys(
        item,
        {
            "variant_id",
            "name",
            "rolling_window",
            "scenario",
            "execution_prices",
            "timing",
            "optimization",
            "portfolio_constraints",
            "rebalance",
            "risk",
            "fills",
            "trading_enabled",
            "metadata",
        },
        path,
    )
    scenario, cash_return, source_name = _scenario(item["scenario"], f"{path}.scenario")
    optimization, risk_aversion = _optimization(
        item["optimization"], f"{path}.optimization"
    )
    assumptions, proposal_policy, confidence = _rebalance_section(
        item["rebalance"], f"{path}.rebalance"
    )
    risk_limits, risk_policy = _risk_section(item["risk"], f"{path}.risk")
    metadata = _metadata(item["metadata"], f"{path}.metadata")
    _reject_reserved_metadata(metadata, f"{path}.metadata")
    try:
        return HistoricalExperimentVariant(
            _uuid(item["variant_id"], f"{path}.variant_id"),
            _string(item["name"], f"{path}.name"),
            _rolling_window(item["rolling_window"], f"{path}.rolling_window"),
            scenario,
            _execution_prices(item["execution_prices"], f"{path}.execution_prices"),
            _timing(item["timing"], f"{path}.timing"),
            cash_return,
            source_name,
            optimization,
            risk_aversion,
            _constraints(
                item["portfolio_constraints"], f"{path}.portfolio_constraints"
            ),
            assumptions,
            proposal_policy,
            confidence,
            risk_limits,
            risk_policy,
            _fill_policy(item["fills"], f"{path}.fills"),
            _boolean(item["trading_enabled"], f"{path}.trading_enabled"),
            metadata,
        )
    except ConfigValidationError:
        raise
    except (TypeError, ValueError) as error:
        raise ConfigValidationError(path, str(error)) from error


def _reject_reserved_metadata(metadata: tuple[MetadataEntry, ...], path: str) -> None:
    if any(item.key.startswith("historical_experiment_") for item in metadata):
        raise ConfigValidationError(
            path, "historical_experiment_ metadata keys are reserved"
        )
