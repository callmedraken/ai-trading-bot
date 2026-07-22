"""Strict version-one configuration parsing for optimized simulations."""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from trading_bot.cli.exceptions import (
    ConfigJsonError,
    ConfigReadError,
    ConfigValidationError,
)
from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.execution import PaperFillPolicy
from trading_bot.market_data import Timeframe
from trading_bot.portfolio import (
    ExpectedReturn,
    ForecastHorizon,
    MeanCvarOptimizationParameters,
    MetadataEntry,
    PortfolioConstraints,
    ReturnScenario,
    ReturnScenarioSet,
    ScenarioSource,
)
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime import PaperPortfolioCyclePrice
from trading_bot.simulation import (
    OptimizedPaperSimulationFrame,
    OptimizedPaperSimulationRequest,
)

_DECIMAL_PATTERN = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")


class _InitializationMode(StrEnum):
    CASH_ONLY = "CASH_ONLY"
    BOOTSTRAP_FILLS = "BOOTSTRAP_FILLS"


@dataclass(frozen=True, slots=True)
class _InitialPositionConfig:
    symbol: Symbol
    quantity: Decimal
    average_cost: Decimal


@dataclass(frozen=True, slots=True)
class _InitialLedgerConfig:
    initialization_mode: _InitializationMode
    as_of: datetime
    available_cash: Decimal
    positions: tuple[_InitialPositionConfig, ...]


@dataclass(frozen=True, slots=True)
class _LoadedSimulationConfig:
    schema_version: int
    request: OptimizedPaperSimulationRequest
    initial_ledger: _InitialLedgerConfig


def load_config(path: Path) -> _LoadedSimulationConfig:
    """Read and strictly parse one UTF-8 configuration file."""
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
    return parse_config(raw)


def parse_config(raw: Any) -> _LoadedSimulationConfig:
    """Parse an already-decoded JSON value into existing domain contracts."""
    root = _object(raw, "$")
    _exact_keys(
        root,
        {
            "schema_version",
            "simulation_request_id",
            "initial_ledger",
            "frames",
            "metadata",
        },
        "$",
    )
    version = _integer(root["schema_version"], "$.schema_version")
    if version != 1:
        raise ConfigValidationError("$.schema_version", "unsupported schema version")
    request_id = _uuid(root["simulation_request_id"], "$.simulation_request_id")
    initial = _initial_ledger(root["initial_ledger"], "$.initial_ledger")
    frame_values = _array(root["frames"], "$.frames", nonempty=True)
    frames = tuple(
        _frame(value, f"$.frames[{ordinal}]")
        for ordinal, value in enumerate(frame_values)
    )
    if initial.as_of > frames[0].as_of:
        raise ConfigValidationError(
            "$.initial_ledger.as_of", "must be at or before the first frame as_of"
        )
    metadata = _metadata(root["metadata"], "$.metadata")
    try:
        request = OptimizedPaperSimulationRequest(request_id, frames, metadata)
    except (TypeError, ValueError) as error:
        raise ConfigValidationError("$", str(error)) from error
    return _LoadedSimulationConfig(version, request, initial)


def _initial_ledger(value: Any, path: str) -> _InitialLedgerConfig:
    item = _object(value, path)
    _exact_keys(
        item, {"initialization_mode", "as_of", "available_cash", "positions"}, path
    )
    mode = _enum(
        item["initialization_mode"], _InitializationMode, f"{path}.initialization_mode"
    )
    as_of = _datetime(item["as_of"], f"{path}.as_of")
    cash = _decimal(item["available_cash"], f"{path}.available_cash")
    if cash < 0:
        raise ConfigValidationError(f"{path}.available_cash", "must be nonnegative")
    raw_positions = _array(item["positions"], f"{path}.positions")
    positions = tuple(
        _initial_position(position, f"{path}.positions[{ordinal}]")
        for ordinal, position in enumerate(raw_positions)
    )
    symbols = tuple(position.symbol for position in positions)
    if len(set(symbols)) != len(symbols):
        raise ConfigValidationError(f"{path}.positions", "symbols must be unique")
    if mode is _InitializationMode.CASH_ONLY and positions:
        raise ConfigValidationError(
            f"{path}.positions", "must be empty for CASH_ONLY initialization"
        )
    if cash == 0 and not positions:
        raise ConfigValidationError(
            f"{path}.available_cash",
            "zero cash without positions cannot initialize PaperLedger",
        )
    return _InitialLedgerConfig(mode, as_of, cash, positions)


def _initial_position(value: Any, path: str) -> _InitialPositionConfig:
    item = _object(value, path)
    _exact_keys(item, {"symbol", "quantity", "average_cost"}, path)
    symbol = _symbol(item["symbol"], f"{path}.symbol")
    quantity = _decimal(item["quantity"], f"{path}.quantity")
    average_cost = _decimal(item["average_cost"], f"{path}.average_cost")
    if quantity <= 0:
        raise ConfigValidationError(f"{path}.quantity", "must be positive")
    if average_cost <= 0:
        raise ConfigValidationError(f"{path}.average_cost", "must be positive")
    return _InitialPositionConfig(symbol, quantity, average_cost)


def _frame(value: Any, path: str) -> OptimizedPaperSimulationFrame:
    item = _object(value, path)
    expected = {
        "as_of",
        "submitted_at",
        "filled_at",
        "prices",
        "expected_returns",
        "scenarios",
        "optimization",
        "portfolio_constraints",
        "rebalance_assumptions",
        "proposal_policy",
        "proposal_confidence",
        "risk_limits",
        "risk_policy",
        "fill_policy",
        "trading_enabled",
        "metadata",
    }
    _exact_keys(item, expected, path)
    as_of = _datetime(item["as_of"], f"{path}.as_of")
    prices = tuple(
        _price(row, f"{path}.prices[{index}]")
        for index, row in enumerate(
            _array(item["prices"], f"{path}.prices", nonempty=True)
        )
    )
    returns = tuple(
        _expected_return(row, f"{path}.expected_returns[{index}]")
        for index, row in enumerate(
            _array(item["expected_returns"], f"{path}.expected_returns", nonempty=True)
        )
    )
    optimization = _object(item["optimization"], f"{path}.optimization")
    _exact_keys(
        optimization,
        {
            "confidence_level",
            "minimum_expected_return",
            "solver_tolerance",
            "maximum_iterations",
            "output_quantum",
            "risk_aversion",
        },
        f"{path}.optimization",
    )
    parameters = _construct(
        f"{path}.optimization",
        MeanCvarOptimizationParameters,
        _decimal(
            optimization["confidence_level"], f"{path}.optimization.confidence_level"
        ),
        _optional_decimal(
            optimization["minimum_expected_return"],
            f"{path}.optimization.minimum_expected_return",
        ),
        _decimal(
            optimization["solver_tolerance"], f"{path}.optimization.solver_tolerance"
        ),
        _optional_integer(
            optimization["maximum_iterations"],
            f"{path}.optimization.maximum_iterations",
        ),
        _decimal(optimization["output_quantum"], f"{path}.optimization.output_quantum"),
    )
    try:
        return OptimizedPaperSimulationFrame(
            as_of,
            prices,
            returns,
            _scenarios(item["scenarios"], f"{path}.scenarios", as_of),
            parameters,
            _decimal(
                optimization["risk_aversion"], f"{path}.optimization.risk_aversion"
            ),
            _constraints(
                item["portfolio_constraints"], f"{path}.portfolio_constraints"
            ),
            _rebalance(item["rebalance_assumptions"], f"{path}.rebalance_assumptions"),
            _proposal_policy(item["proposal_policy"], f"{path}.proposal_policy"),
            _optional_decimal(
                item["proposal_confidence"], f"{path}.proposal_confidence"
            ),
            _risk_limits(item["risk_limits"], f"{path}.risk_limits"),
            _risk_policy(item["risk_policy"], f"{path}.risk_policy"),
            _fill_policy(item["fill_policy"], f"{path}.fill_policy"),
            _boolean(item["trading_enabled"], f"{path}.trading_enabled"),
            _datetime(item["submitted_at"], f"{path}.submitted_at"),
            _datetime(item["filled_at"], f"{path}.filled_at"),
            _metadata(item["metadata"], f"{path}.metadata"),
        )
    except ConfigValidationError:
        raise
    except (TypeError, ValueError) as error:
        raise ConfigValidationError(path, str(error)) from error


def _price(value: Any, path: str) -> PaperPortfolioCyclePrice:
    item = _object(value, path)
    _exact_keys(item, {"symbol", "risk_price", "fill_reference_price"}, path)
    return _construct(
        path,
        PaperPortfolioCyclePrice,
        _symbol(item["symbol"], f"{path}.symbol"),
        _decimal(item["risk_price"], f"{path}.risk_price"),
        _decimal(item["fill_reference_price"], f"{path}.fill_reference_price"),
    )


def _expected_return(value: Any, path: str) -> ExpectedReturn:
    item = _object(value, path)
    _exact_keys(item, {"symbol", "value"}, path)
    return _construct(
        path,
        ExpectedReturn,
        _symbol(item["symbol"], f"{path}.symbol"),
        _decimal(item["value"], f"{path}.value"),
    )


def _scenarios(value: Any, path: str, as_of: datetime) -> ReturnScenarioSet:
    item = _object(value, path)
    _exact_keys(
        item,
        {
            "scenario_set_id",
            "forecast_horizon",
            "symbols",
            "rows",
            "cash_return",
            "source",
            "source_name",
            "metadata",
        },
        path,
    )
    horizon_raw = _object(item["forecast_horizon"], f"{path}.forecast_horizon")
    _exact_keys(horizon_raw, {"periods", "timeframe"}, f"{path}.forecast_horizon")
    horizon = _construct(
        f"{path}.forecast_horizon",
        ForecastHorizon,
        _integer(horizon_raw["periods"], f"{path}.forecast_horizon.periods"),
        _enum(
            horizon_raw["timeframe"], Timeframe, f"{path}.forecast_horizon.timeframe"
        ),
    )
    symbols = tuple(
        _symbol(symbol, f"{path}.symbols[{index}]")
        for index, symbol in enumerate(
            _array(item["symbols"], f"{path}.symbols", nonempty=True)
        )
    )
    rows = tuple(
        _scenario(row, f"{path}.rows[{index}]")
        for index, row in enumerate(_array(item["rows"], f"{path}.rows", nonempty=True))
    )
    source = _enum(item["source"], ScenarioSource, f"{path}.source")
    source_name = _optional_string(item["source_name"], f"{path}.source_name")
    return _construct(
        path,
        ReturnScenarioSet,
        _uuid(item["scenario_set_id"], f"{path}.scenario_set_id"),
        as_of,
        horizon,
        symbols,
        rows,
        _decimal(item["cash_return"], f"{path}.cash_return"),
        source,
        source_name,
        _metadata(item["metadata"], f"{path}.metadata"),
    )


def _scenario(value: Any, path: str) -> ReturnScenario:
    item = _object(value, path)
    _exact_keys(item, {"scenario_id", "returns", "probability", "metadata"}, path)
    returns = tuple(
        _decimal(entry, f"{path}.returns[{index}]")
        for index, entry in enumerate(
            _array(item["returns"], f"{path}.returns", nonempty=True)
        )
    )
    return _construct(
        path,
        ReturnScenario,
        _uuid(item["scenario_id"], f"{path}.scenario_id"),
        returns,
        _decimal(item["probability"], f"{path}.probability"),
        _metadata(item["metadata"], f"{path}.metadata"),
    )


def _constraints(value: Any, path: str) -> PortfolioConstraints:
    item = _object(value, path)
    _exact_keys(
        item,
        {
            "minimum_cash_weight",
            "maximum_cash_weight",
            "maximum_position_weight",
            "maximum_one_way_rebalance_turnover",
            "minimum_position_weight",
            "long_only",
            "allow_leverage",
        },
        path,
    )
    return _construct(
        path,
        PortfolioConstraints,
        _decimal(item["minimum_cash_weight"], f"{path}.minimum_cash_weight"),
        _decimal(item["maximum_cash_weight"], f"{path}.maximum_cash_weight"),
        _decimal(item["maximum_position_weight"], f"{path}.maximum_position_weight"),
        _optional_decimal(
            item["maximum_one_way_rebalance_turnover"],
            f"{path}.maximum_one_way_rebalance_turnover",
        ),
        _optional_decimal(
            item["minimum_position_weight"], f"{path}.minimum_position_weight"
        ),
        _boolean(item["long_only"], f"{path}.long_only"),
        _boolean(item["allow_leverage"], f"{path}.allow_leverage"),
    )


def _rebalance(value: Any, path: str) -> RebalanceAssumptions:
    item = _object(value, path)
    _exact_keys(
        item,
        {
            "fixed_commission",
            "allow_fractional_quantities",
            "quantity_increment",
            "minimum_trade_notional",
            "minimum_trade_quantity",
            "target_weight_tolerance",
            "additional_execution_cash_buffer",
            "use_planned_sell_proceeds",
        },
        path,
    )
    return _construct(
        path,
        RebalanceAssumptions,
        _decimal(item["fixed_commission"], f"{path}.fixed_commission"),
        _boolean(
            item["allow_fractional_quantities"], f"{path}.allow_fractional_quantities"
        ),
        _decimal(item["quantity_increment"], f"{path}.quantity_increment"),
        _decimal(item["minimum_trade_notional"], f"{path}.minimum_trade_notional"),
        _decimal(item["minimum_trade_quantity"], f"{path}.minimum_trade_quantity"),
        _decimal(item["target_weight_tolerance"], f"{path}.target_weight_tolerance"),
        _decimal(
            item["additional_execution_cash_buffer"],
            f"{path}.additional_execution_cash_buffer",
        ),
        _boolean(
            item["use_planned_sell_proceeds"], f"{path}.use_planned_sell_proceeds"
        ),
    )


def _proposal_policy(value: Any, path: str) -> RebalanceProposalPolicy:
    item = _object(value, path)
    _exact_keys(item, {"allow_partial_plans"}, path)
    return _construct(
        path,
        RebalanceProposalPolicy,
        _boolean(item["allow_partial_plans"], f"{path}.allow_partial_plans"),
    )


def _risk_limits(value: Any, path: str) -> RiskLimits:
    item = _object(value, path)
    _exact_keys(
        item,
        {
            "max_position_percent",
            "max_total_exposure_percent",
            "max_order_notional",
            "max_new_position_percent",
            "minimum_cash_reserve_percent",
            "allow_fractional_shares",
            "fractional_increment",
            "allow_buying",
            "allow_selling",
            "estimated_commission",
        },
        path,
    )
    return _construct(
        path,
        RiskLimits,
        _decimal(item["max_position_percent"], f"{path}.max_position_percent"),
        _decimal(
            item["max_total_exposure_percent"], f"{path}.max_total_exposure_percent"
        ),
        _optional_decimal(item["max_order_notional"], f"{path}.max_order_notional"),
        _optional_decimal(
            item["max_new_position_percent"], f"{path}.max_new_position_percent"
        ),
        _decimal(
            item["minimum_cash_reserve_percent"], f"{path}.minimum_cash_reserve_percent"
        ),
        _boolean(item["allow_fractional_shares"], f"{path}.allow_fractional_shares"),
        _decimal(item["fractional_increment"], f"{path}.fractional_increment"),
        _boolean(item["allow_buying"], f"{path}.allow_buying"),
        _boolean(item["allow_selling"], f"{path}.allow_selling"),
        _decimal(item["estimated_commission"], f"{path}.estimated_commission"),
    )


def _risk_policy(value: Any, path: str) -> PortfolioRiskPolicy:
    item = _object(value, path)
    _exact_keys(item, {"allow_sell_proceeds_for_later_buys"}, path)
    return _construct(
        path,
        PortfolioRiskPolicy,
        _boolean(
            item["allow_sell_proceeds_for_later_buys"],
            f"{path}.allow_sell_proceeds_for_later_buys",
        ),
    )


def _fill_policy(value: Any, path: str) -> PaperFillPolicy:
    item = _object(value, path)
    _exact_keys(item, {"slippage_basis_points", "fixed_commission"}, path)
    return _construct(
        path,
        PaperFillPolicy,
        _decimal(item["slippage_basis_points"], f"{path}.slippage_basis_points"),
        _decimal(item["fixed_commission"], f"{path}.fixed_commission"),
    )


def _metadata(value: Any, path: str) -> tuple[MetadataEntry, ...]:
    output = []
    for index, raw in enumerate(_array(value, path)):
        item_path = f"{path}[{index}]"
        item = _object(raw, item_path)
        _exact_keys(item, {"key", "value"}, item_path)
        output.append(
            _construct(
                item_path,
                MetadataEntry,
                _string(item["key"], f"{item_path}.key"),
                _string(item["value"], f"{item_path}.value"),
            )
        )
    return tuple(output)


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigValidationError(path, "must be an object")
    if not all(isinstance(key, str) for key in value):
        raise ConfigValidationError(path, "object keys must be strings")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    missing = sorted(expected - value.keys())
    if missing:
        raise ConfigValidationError(f"{path}.{missing[0]}", "required field is missing")
    unknown = sorted(value.keys() - expected)
    if unknown:
        raise ConfigValidationError(f"{path}.{unknown[0]}", "unknown field")


def _array(value: Any, path: str, *, nonempty: bool = False) -> list[Any]:
    if not isinstance(value, list):
        raise ConfigValidationError(path, "must be an array")
    if nonempty and not value:
        raise ConfigValidationError(path, "must not be empty")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise ConfigValidationError(path, "must be a string")
    return value


def _optional_string(value: Any, path: str) -> str | None:
    return None if value is None else _string(value, path)


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigValidationError(path, "must be a boolean")
    return value


def _integer(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigValidationError(path, "must be an integer")
    return value


def _optional_integer(value: Any, path: str) -> int | None:
    return None if value is None else _integer(value, path)


def _decimal(value: Any, path: str) -> Decimal:
    if not isinstance(value, str) or _DECIMAL_PATTERN.fullmatch(value) is None:
        raise ConfigValidationError(path, "must be a plain Decimal string")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ConfigValidationError(path, "must be a valid Decimal string") from error
    if not result.is_finite():
        raise ConfigValidationError(path, "must be finite")
    return result


def _optional_decimal(value: Any, path: str) -> Decimal | None:
    return None if value is None else _decimal(value, path)


def _uuid(value: Any, path: str) -> UUID:
    if not isinstance(value, str):
        raise ConfigValidationError(path, "must be a UUID string")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as error:
        raise ConfigValidationError(path, "must be a valid UUID string") from error
    if str(parsed) != value:
        raise ConfigValidationError(path, "must use canonical UUID text")
    return parsed


def _datetime(value: Any, path: str) -> datetime:
    if not isinstance(value, str):
        raise ConfigValidationError(path, "must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ConfigValidationError(
            path, "must be a valid ISO-8601 timestamp"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ConfigValidationError(path, "must include a timezone offset")
    return normalize_utc(parsed, path)


def _enum(value: Any, enum_type, path: str):  # type: ignore[no-untyped-def]
    if not isinstance(value, str):
        raise ConfigValidationError(path, "must be an enum string")
    try:
        return enum_type(value)
    except ValueError as error:
        allowed = ", ".join(member.value for member in enum_type)
        raise ConfigValidationError(
            path, f"unknown value; expected one of: {allowed}"
        ) from error


def _symbol(value: Any, path: str) -> Symbol:
    try:
        return Symbol(_string(value, path))
    except (TypeError, ValueError) as error:
        raise ConfigValidationError(path, str(error)) from error


def _construct(path: str, constructor, *args):  # type: ignore[no-untyped-def]
    try:
        return constructor(*args)
    except (TypeError, ValueError) as error:
        raise ConfigValidationError(path, str(error)) from error
