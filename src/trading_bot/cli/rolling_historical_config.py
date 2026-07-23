"""Strict version-one configuration for rolling historical simulations."""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID

from trading_bot.cli._simulation_bootstrap import (
    InitialLedgerConfig,
)
from trading_bot.cli.config import (
    _array,
    _boolean,
    _constraints,
    _datetime,
    _decimal,
    _enum,
    _exact_keys,
    _fill_policy,
    _initial_ledger,
    _integer,
    _metadata,
    _object,
    _optional_decimal,
    _proposal_policy,
    _rebalance,
    _risk_limits,
    _risk_policy,
    _string,
    _symbol,
    _uuid,
)
from trading_bot.cli.exceptions import (
    ConfigJsonError,
    ConfigReadError,
    ConfigValidationError,
)
from trading_bot.domain import Symbol
from trading_bot.execution import PaperFillPolicy
from trading_bot.market_data import AdjustmentType, MissingBarPolicy, Timeframe
from trading_bot.portfolio import (
    HistoricalScenarioGenerationPolicy,
    HistoricalScenarioPriceField,
    HistoricalScenarioReturnMethod,
    HistoricalScenarioWindowPolicy,
    MeanCvarOptimizationParameters,
    MetadataEntry,
    PortfolioConstraints,
)
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.simulation import (
    RollingHistoricalCycleTimingPolicy,
    RollingHistoricalExecutionPriceField,
    RollingHistoricalExecutionPricePolicy,
    RollingHistoricalWindowPolicy,
)


@dataclass(frozen=True, slots=True)
class RollingHistoricalSourceConfig:
    symbol: Symbol
    configured_path: str
    resolved_path: Path = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class RollingHistoricalDataConfig:
    symbols: tuple[Symbol, ...]
    sources: tuple[RollingHistoricalSourceConfig, ...]
    start: datetime
    end: datetime
    timeframe: Timeframe
    adjustment: AdjustmentType
    missing_bar_policy: MissingBarPolicy
    source_label: str
    common_parent: Path = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class LoadedRollingHistoricalConfig:
    schema_version: int
    request_id: UUID
    historical_data: RollingHistoricalDataConfig
    rebalance_schedule: tuple[datetime, ...]
    window_policy: RollingHistoricalWindowPolicy
    scenario_policy: HistoricalScenarioGenerationPolicy
    scenario_cash_return: Decimal
    scenario_source_name: str
    execution_price_policy: RollingHistoricalExecutionPricePolicy
    timing_policy: RollingHistoricalCycleTimingPolicy
    initial_state: InitialLedgerConfig
    optimization_parameters: MeanCvarOptimizationParameters
    risk_aversion: Decimal
    portfolio_constraints: PortfolioConstraints
    rebalance_assumptions: RebalanceAssumptions
    proposal_policy: RebalanceProposalPolicy
    proposal_confidence: Decimal | None
    risk_limits: RiskLimits
    risk_policy: PortfolioRiskPolicy
    fill_policy: PaperFillPolicy
    trading_enabled: bool
    metadata: tuple[MetadataEntry, ...]


def load_rolling_config(path: Path) -> LoadedRollingHistoricalConfig:
    """Read and parse one rolling configuration relative to its own directory."""
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
    return parse_rolling_config(raw, path.parent)


def parse_rolling_config(
    raw: Any, config_directory: Path
) -> LoadedRollingHistoricalConfig:
    """Parse strict JSON values and resolve local sources operationally."""
    root = _object(raw, "$")
    expected = {
        "schema_version",
        "request_id",
        "historical_data",
        "rebalance_schedule",
        "rolling_window",
        "scenario",
        "execution_prices",
        "timing",
        "initial_state",
        "optimization",
        "portfolio_constraints",
        "rebalance",
        "risk",
        "fills",
        "trading_enabled",
        "metadata",
    }
    _exact_keys(root, expected, "$")
    version = _integer(root["schema_version"], "$.schema_version")
    if version != 1:
        raise ConfigValidationError("$.schema_version", "unsupported schema version")
    historical = _historical_data(root["historical_data"], config_directory)
    schedule = tuple(
        _datetime(value, f"$.rebalance_schedule[{index}]")
        for index, value in enumerate(
            _array(root["rebalance_schedule"], "$.rebalance_schedule", nonempty=True)
        )
    )
    window = _rolling_window(root["rolling_window"], "$.rolling_window")
    scenario_policy, cash_return, source_name = _scenario(
        root["scenario"], "$.scenario"
    )
    execution = _execution_prices(root["execution_prices"], "$.execution_prices")
    timing = _timing(root["timing"], "$.timing")
    initial = _initial_ledger(root["initial_state"], "$.initial_state")
    if initial.as_of > schedule[0]:
        raise ConfigValidationError(
            "$.initial_state.as_of", "must be at or before the first rebalance"
        )
    universe = set(historical.symbols)
    if any(item.symbol not in universe for item in initial.positions):
        raise ConfigValidationError(
            "$.initial_state.positions",
            "bootstrap symbols must belong to the historical universe",
        )
    optimization, risk_aversion = _optimization(root["optimization"], "$.optimization")
    rebalance, proposal, confidence = _rebalance_section(
        root["rebalance"], "$.rebalance"
    )
    limits, risk_policy = _risk_section(root["risk"], "$.risk")
    fill_policy = _fill_policy(root["fills"], "$.fills")
    metadata = _metadata(root["metadata"], "$.metadata")
    if any(item.key.startswith("rolling_historical_simulation_") for item in metadata):
        raise ConfigValidationError(
            "$.metadata", "rolling_historical_simulation_ keys are reserved"
        )
    return LoadedRollingHistoricalConfig(
        version,
        _uuid(root["request_id"], "$.request_id"),
        historical,
        schedule,
        window,
        scenario_policy,
        cash_return,
        source_name,
        execution,
        timing,
        initial,
        optimization,
        risk_aversion,
        _constraints(root["portfolio_constraints"], "$.portfolio_constraints"),
        rebalance,
        proposal,
        confidence,
        limits,
        risk_policy,
        fill_policy,
        _boolean(root["trading_enabled"], "$.trading_enabled"),
        metadata,
    )


def _historical_data(value: Any, directory: Path) -> RollingHistoricalDataConfig:
    path = "$.historical_data"
    item = _object(value, path)
    _exact_keys(
        item,
        {
            "symbols",
            "sources",
            "start",
            "end",
            "timeframe",
            "adjustment",
            "missing_bar_policy",
            "source_label",
        },
        path,
    )
    symbols = tuple(
        _symbol(raw, f"{path}.symbols[{index}]")
        for index, raw in enumerate(
            _array(item["symbols"], f"{path}.symbols", nonempty=True)
        )
    )
    if len(set(symbols)) != len(symbols):
        raise ConfigValidationError(f"{path}.symbols", "symbols must be unique")
    raw_sources = _array(item["sources"], f"{path}.sources", nonempty=True)
    if len(raw_sources) != len(symbols):
        raise ConfigValidationError(
            f"{path}.sources", "must contain exactly one source per symbol"
        )
    sources = tuple(
        _source(raw, f"{path}.sources[{index}]", directory)
        for index, raw in enumerate(raw_sources)
    )
    for index, (symbol, source) in enumerate(zip(symbols, sources, strict=True)):
        if source.symbol != symbol:
            raise ConfigValidationError(
                f"{path}.sources[{index}].symbol",
                "must match the symbol at the same ordered index",
            )
    resolved = tuple(source.resolved_path for source in sources)
    if len(set(resolved)) != len(resolved):
        raise ConfigValidationError(f"{path}.sources", "resolved paths must be unique")
    parents = {source.parent for source in resolved}
    if len(parents) != 1:
        raise ConfigValidationError(
            f"{path}.sources", "all CSV sources must share one parent directory"
        )
    for index, source in enumerate(sources):
        if source.resolved_path.name != f"{source.symbol}.csv":
            raise ConfigValidationError(
                f"{path}.sources[{index}].path",
                f"filename must be exactly {source.symbol}.csv",
            )
        if not source.resolved_path.is_file():
            raise ConfigValidationError(
                f"{path}.sources[{index}].path", "must identify a regular file"
            )
    label = _string(item["source_label"], f"{path}.source_label")
    if not label.strip():
        raise ConfigValidationError(f"{path}.source_label", "must be nonblank")
    return RollingHistoricalDataConfig(
        symbols,
        sources,
        _datetime(item["start"], f"{path}.start"),
        _datetime(item["end"], f"{path}.end"),
        _enum(item["timeframe"], Timeframe, f"{path}.timeframe"),
        _enum(item["adjustment"], AdjustmentType, f"{path}.adjustment"),
        _enum(
            item["missing_bar_policy"],
            MissingBarPolicy,
            f"{path}.missing_bar_policy",
        ),
        label,
        next(iter(parents)),
    )


def _source(value: Any, path: str, directory: Path) -> RollingHistoricalSourceConfig:
    item = _object(value, path)
    _exact_keys(item, {"symbol", "path"}, path)
    configured = _string(item["path"], f"{path}.path")
    candidate = Path(configured)
    if candidate.is_absolute() or candidate.drive:
        raise ConfigValidationError(
            f"{path}.path", "must be relative to the configuration file"
        )
    normalized = PurePosixPath(
        os.path.normpath(configured).replace("\\", "/")
    ).as_posix()
    resolved = (directory / Path(normalized)).resolve()
    return RollingHistoricalSourceConfig(
        _symbol(item["symbol"], f"{path}.symbol"), normalized, resolved
    )


def _rolling_window(value: Any, path: str) -> RollingHistoricalWindowPolicy:
    item = _object(value, path)
    _exact_keys(item, {"observation_count"}, path)
    try:
        return RollingHistoricalWindowPolicy(
            _integer(item["observation_count"], f"{path}.observation_count")
        )
    except ConfigValidationError:
        raise
    except (TypeError, ValueError) as error:
        raise ConfigValidationError(path, str(error)) from error


def _scenario(
    value: Any, path: str
) -> tuple[HistoricalScenarioGenerationPolicy, Decimal, str]:
    item = _object(value, path)
    _exact_keys(
        item,
        {
            "price_field",
            "return_method",
            "window_policy",
            "cash_return",
            "source_name",
        },
        path,
    )
    try:
        policy = HistoricalScenarioGenerationPolicy(
            _enum(
                item["price_field"],
                HistoricalScenarioPriceField,
                f"{path}.price_field",
            ),
            _enum(
                item["return_method"],
                HistoricalScenarioReturnMethod,
                f"{path}.return_method",
            ),
            _enum(
                item["window_policy"],
                HistoricalScenarioWindowPolicy,
                f"{path}.window_policy",
            ),
        )
    except ConfigValidationError:
        raise
    except (TypeError, ValueError) as error:
        raise ConfigValidationError(path, str(error)) from error
    source_name = _string(item["source_name"], f"{path}.source_name")
    if not source_name.strip():
        raise ConfigValidationError(f"{path}.source_name", "must be nonblank")
    return policy, _decimal(item["cash_return"], f"{path}.cash_return"), source_name


def _execution_prices(value: Any, path: str) -> RollingHistoricalExecutionPricePolicy:
    item = _object(value, path)
    _exact_keys(item, {"risk_price_field", "fill_reference_price_field"}, path)
    try:
        return RollingHistoricalExecutionPricePolicy(
            _enum(
                item["risk_price_field"],
                RollingHistoricalExecutionPriceField,
                f"{path}.risk_price_field",
            ),
            _enum(
                item["fill_reference_price_field"],
                RollingHistoricalExecutionPriceField,
                f"{path}.fill_reference_price_field",
            ),
        )
    except (TypeError, ValueError) as error:
        raise ConfigValidationError(path, str(error)) from error


def _timing(value: Any, path: str) -> RollingHistoricalCycleTimingPolicy:
    item = _object(value, path)
    _exact_keys(
        item, {"submission_offset_microseconds", "fill_offset_microseconds"}, path
    )
    try:
        return RollingHistoricalCycleTimingPolicy(
            timedelta(
                microseconds=_integer(
                    item["submission_offset_microseconds"],
                    f"{path}.submission_offset_microseconds",
                )
            ),
            timedelta(
                microseconds=_integer(
                    item["fill_offset_microseconds"],
                    f"{path}.fill_offset_microseconds",
                )
            ),
        )
    except ConfigValidationError:
        raise
    except (TypeError, ValueError, OverflowError) as error:
        raise ConfigValidationError(path, str(error)) from error


def _optimization(
    value: Any, path: str
) -> tuple[MeanCvarOptimizationParameters, Decimal]:
    item = _object(value, path)
    _exact_keys(
        item,
        {
            "confidence_level",
            "minimum_expected_return",
            "solver_tolerance",
            "maximum_iterations",
            "output_quantum",
            "risk_aversion",
        },
        path,
    )
    try:
        parameters = MeanCvarOptimizationParameters(
            _decimal(item["confidence_level"], f"{path}.confidence_level"),
            _optional_decimal(
                item["minimum_expected_return"],
                f"{path}.minimum_expected_return",
            ),
            _decimal(item["solver_tolerance"], f"{path}.solver_tolerance"),
            (
                None
                if item["maximum_iterations"] is None
                else _integer(item["maximum_iterations"], f"{path}.maximum_iterations")
            ),
            _decimal(item["output_quantum"], f"{path}.output_quantum"),
        )
    except ConfigValidationError:
        raise
    except (TypeError, ValueError) as error:
        raise ConfigValidationError(path, str(error)) from error
    return parameters, _decimal(item["risk_aversion"], f"{path}.risk_aversion")


def _rebalance_section(
    value: Any, path: str
) -> tuple[RebalanceAssumptions, RebalanceProposalPolicy, Decimal | None]:
    item = _object(value, path)
    _exact_keys(item, {"assumptions", "proposal_policy", "proposal_confidence"}, path)
    return (
        _rebalance(item["assumptions"], f"{path}.assumptions"),
        _proposal_policy(item["proposal_policy"], f"{path}.proposal_policy"),
        _optional_decimal(item["proposal_confidence"], f"{path}.proposal_confidence"),
    )


def _risk_section(value: Any, path: str) -> tuple[RiskLimits, PortfolioRiskPolicy]:
    item = _object(value, path)
    _exact_keys(item, {"limits", "policy"}, path)
    return (
        _risk_limits(item["limits"], f"{path}.limits"),
        _risk_policy(item["policy"], f"{path}.policy"),
    )
