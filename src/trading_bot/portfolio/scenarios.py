"""Immutable deterministic portfolio return-scenario contracts."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.portfolio.exceptions import (
    InvalidReturnScenarioError,
    InvalidReturnScenarioSetError,
    ScenarioCompatibilityError,
    ScenarioUniverseMismatchError,
)
from trading_bot.portfolio.models import ExpectedReturn, ForecastHorizon, MetadataEntry

_ZERO = Decimal("0")
_ONE = Decimal("1")
_MINIMUM_RETURN = Decimal("-1")


def _decimal(value: Decimal, name: str, error_type: type[ValueError]) -> Decimal:
    if not isinstance(value, Decimal):
        raise error_type(f"{name} must be a Decimal")
    if not value.is_finite():
        raise error_type(f"{name} must be finite")
    return _ZERO if value == _ZERO else value


def _metadata(
    source: tuple[MetadataEntry, ...], error_type: type[ValueError]
) -> tuple[MetadataEntry, ...]:
    try:
        metadata = tuple(source)
    except TypeError as error:
        raise error_type("metadata must be iterable") from error
    if not all(isinstance(item, MetadataEntry) for item in metadata):
        raise error_type("metadata must contain MetadataEntry values")
    keys = tuple(item.key for item in metadata)
    if len(set(keys)) != len(keys):
        raise error_type("metadata keys must be unique")
    return metadata


@dataclass(frozen=True, slots=True)
class ReturnScenario:
    """One probability-weighted row in enclosing symbol-column order."""

    scenario_id: UUID
    returns: tuple[Decimal, ...]
    probability: Decimal
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, UUID):
            raise InvalidReturnScenarioError("scenario_id must be a UUID")
        try:
            supplied_returns = tuple(self.returns)
        except TypeError as error:
            raise InvalidReturnScenarioError("returns must be iterable") from error
        if not supplied_returns:
            raise InvalidReturnScenarioError("returns must not be empty")
        normalized = []
        for index, value in enumerate(supplied_returns):
            item = _decimal(value, f"returns[{index}]", InvalidReturnScenarioError)
            if item < _MINIMUM_RETURN:
                raise InvalidReturnScenarioError(
                    "scenario returns cannot be below negative one"
                )
            normalized.append(item)
        probability = _decimal(
            self.probability, "probability", InvalidReturnScenarioError
        )
        if not _ZERO < probability <= _ONE:
            raise InvalidReturnScenarioError(
                "probability must be greater than zero and at most one"
            )
        object.__setattr__(self, "returns", tuple(normalized))
        object.__setattr__(self, "probability", probability)
        object.__setattr__(
            self,
            "metadata",
            _metadata(self.metadata, InvalidReturnScenarioError),
        )


class ScenarioSource(StrEnum):
    MANUAL = "MANUAL"
    HISTORICAL = "HISTORICAL"
    BOOTSTRAP = "BOOTSTRAP"
    MONTE_CARLO = "MONTE_CARLO"
    IMPORTED = "IMPORTED"


@dataclass(frozen=True, slots=True)
class ReturnScenarioSet:
    """A complete ordered probability distribution over portfolio returns."""

    scenario_set_id: UUID
    as_of: datetime
    forecast_horizon: ForecastHorizon
    symbols: tuple[Symbol, ...]
    scenarios: tuple[ReturnScenario, ...]
    cash_return: Decimal = _ZERO
    source: ScenarioSource = ScenarioSource.MANUAL
    source_name: str | None = None
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_set_id, UUID):
            raise InvalidReturnScenarioSetError("scenario_set_id must be a UUID")
        try:
            as_of = normalize_utc(self.as_of, "as_of")
        except (TypeError, ValueError) as error:
            raise InvalidReturnScenarioSetError(str(error)) from error
        if not isinstance(self.forecast_horizon, ForecastHorizon):
            raise InvalidReturnScenarioSetError(
                "forecast_horizon must be a ForecastHorizon"
            )
        try:
            symbols = tuple(self.symbols)
        except TypeError as error:
            raise InvalidReturnScenarioSetError("symbols must be iterable") from error
        if not symbols:
            raise InvalidReturnScenarioSetError("symbols must not be empty")
        if not all(isinstance(symbol, Symbol) for symbol in symbols):
            raise InvalidReturnScenarioSetError(
                "symbols must contain only Symbol values"
            )
        if len(set(symbols)) != len(symbols):
            raise InvalidReturnScenarioSetError("symbols must be unique")
        try:
            scenarios = tuple(self.scenarios)
        except TypeError as error:
            raise InvalidReturnScenarioSetError("scenarios must be iterable") from error
        if not scenarios:
            raise InvalidReturnScenarioSetError("scenarios must not be empty")
        if not all(isinstance(item, ReturnScenario) for item in scenarios):
            raise InvalidReturnScenarioSetError(
                "scenarios must contain ReturnScenario values"
            )
        ids = tuple(item.scenario_id for item in scenarios)
        if len(set(ids)) != len(ids):
            raise InvalidReturnScenarioSetError("scenario IDs must be unique")
        if any(len(item.returns) != len(symbols) for item in scenarios):
            raise InvalidReturnScenarioSetError(
                "every scenario row width must equal the symbol count"
            )
        probability_total = sum((item.probability for item in scenarios), start=_ZERO)
        if probability_total != _ONE:
            raise InvalidReturnScenarioSetError(
                "scenario probabilities must sum exactly to one"
            )
        cash_return = _decimal(
            self.cash_return, "cash_return", InvalidReturnScenarioSetError
        )
        if cash_return < _MINIMUM_RETURN:
            raise InvalidReturnScenarioSetError(
                "cash_return cannot be below negative one"
            )
        if not isinstance(self.source, ScenarioSource):
            raise InvalidReturnScenarioSetError("source must be a ScenarioSource")
        if self.source_name is not None and (
            not isinstance(self.source_name, str) or not self.source_name.strip()
        ):
            raise InvalidReturnScenarioSetError(
                "source_name must be nonblank when supplied"
            )
        if self.source is not ScenarioSource.MANUAL and self.source_name is None:
            raise InvalidReturnScenarioSetError(
                "non-manual scenario sources require source_name"
            )
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "symbols", symbols)
        object.__setattr__(self, "scenarios", scenarios)
        object.__setattr__(self, "cash_return", cash_return)
        object.__setattr__(
            self,
            "metadata",
            _metadata(self.metadata, InvalidReturnScenarioSetError),
        )

    @property
    def scenario_count(self) -> int:
        return len(self.scenarios)

    def implied_expected_returns(self) -> tuple[ExpectedReturn, ...]:
        return tuple(
            ExpectedReturn(
                symbol,
                sum(
                    (
                        scenario.probability * scenario.returns[column]
                        for scenario in self.scenarios
                    ),
                    start=_ZERO,
                ),
            )
            for column, symbol in enumerate(self.symbols)
        )

    def validate_compatibility(
        self,
        *,
        as_of: datetime,
        forecast_horizon: ForecastHorizon,
        symbols: tuple[Symbol, ...],
    ) -> None:
        try:
            normalized_as_of = normalize_utc(as_of, "as_of")
        except (TypeError, ValueError) as error:
            raise ScenarioCompatibilityError(str(error)) from error
        if not isinstance(forecast_horizon, ForecastHorizon):
            raise ScenarioCompatibilityError(
                "forecast_horizon must be a ForecastHorizon"
            )
        try:
            supplied_symbols = tuple(symbols)
        except TypeError as error:
            raise ScenarioUniverseMismatchError("symbols must be iterable") from error
        if not all(isinstance(symbol, Symbol) for symbol in supplied_symbols):
            raise ScenarioUniverseMismatchError(
                "symbols must contain only Symbol values"
            )
        if supplied_symbols != self.symbols:
            raise ScenarioUniverseMismatchError(
                "scenario ordered universe does not match"
            )
        if normalized_as_of != self.as_of:
            raise ScenarioCompatibilityError("scenario as_of does not match")
        if forecast_horizon != self.forecast_horizon:
            raise ScenarioCompatibilityError("scenario forecast horizon does not match")
