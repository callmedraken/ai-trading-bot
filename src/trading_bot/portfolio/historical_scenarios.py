"""Deterministic historical-price return-scenario generation."""

from dataclasses import dataclass
from datetime import datetime
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DecimalException,
    localcontext,
)
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.market_data import MultiSymbolHistoricalDataResult, Timeframe
from trading_bot.portfolio.exceptions import (
    HistoricalScenarioChronologyError,
    HistoricalScenarioPriceError,
    HistoricalScenarioProbabilityError,
    HistoricalScenarioReconciliationError,
    HistoricalScenarioUniverseMismatchError,
    InconsistentHistoricalScenarioResultError,
    InvalidHistoricalScenarioRequestError,
    InvalidOptimizationRequestError,
    InvalidReturnScenarioError,
    InvalidReturnScenarioSetError,
)
from trading_bot.portfolio.models import ExpectedReturn, ForecastHorizon, MetadataEntry
from trading_bot.portfolio.scenarios import (
    ReturnScenario,
    ReturnScenarioSet,
    ScenarioSource,
)

_ZERO = Decimal("0")
_ONE = Decimal("1")
_MINIMUM_RETURN = Decimal("-1")
_CONTEXT = Context(prec=28, rounding=ROUND_HALF_EVEN)
_VERSION = "historical-return-scenarios-v1"
_NAMESPACE = UUID("d5168235-043e-59d8-81a4-274e9799d9ad")
_RESERVED_PREFIX = "historical_scenario_"


class HistoricalScenarioPriceField(StrEnum):
    """Supported canonical historical price fields."""

    CLOSE = "CLOSE"


class HistoricalScenarioReturnMethod(StrEnum):
    """Supported historical return calculations."""

    SIMPLE = "SIMPLE"


class HistoricalScenarioWindowPolicy(StrEnum):
    """Supported policies for selecting from supplied observations."""

    ALL_SUPPLIED = "ALL_SUPPLIED"


@dataclass(frozen=True, slots=True)
class HistoricalScenarioGenerationPolicy:
    """Explicit version-one historical scenario calculation policy."""

    price_field: HistoricalScenarioPriceField = HistoricalScenarioPriceField.CLOSE
    return_method: HistoricalScenarioReturnMethod = (
        HistoricalScenarioReturnMethod.SIMPLE
    )
    window_policy: HistoricalScenarioWindowPolicy = (
        HistoricalScenarioWindowPolicy.ALL_SUPPLIED
    )

    def __post_init__(self) -> None:
        if self.price_field is not HistoricalScenarioPriceField.CLOSE:
            raise InvalidHistoricalScenarioRequestError(
                "only CLOSE historical prices are supported"
            )
        if self.return_method is not HistoricalScenarioReturnMethod.SIMPLE:
            raise InvalidHistoricalScenarioRequestError(
                "only SIMPLE historical returns are supported"
            )
        if self.window_policy is not HistoricalScenarioWindowPolicy.ALL_SUPPLIED:
            raise InvalidHistoricalScenarioRequestError(
                "only ALL_SUPPLIED historical windows are supported"
            )


@dataclass(frozen=True, slots=True)
class HistoricalScenarioGenerationRequest:
    """One traceable request over an immutable aligned historical result."""

    request_id: UUID
    historical_data: MultiSymbolHistoricalDataResult
    policy: HistoricalScenarioGenerationPolicy
    as_of: datetime
    forecast_horizon: ForecastHorizon
    cash_return: Decimal
    source_name: str
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidHistoricalScenarioRequestError
        if not isinstance(self.request_id, UUID):
            raise error("request_id must be a UUID")
        if type(self.historical_data) is not MultiSymbolHistoricalDataResult:
            raise error(
                "historical_data must be exactly MultiSymbolHistoricalDataResult"
            )
        if not isinstance(self.policy, HistoricalScenarioGenerationPolicy):
            raise error("policy must be HistoricalScenarioGenerationPolicy")
        self.policy.__post_init__()
        try:
            as_of = normalize_utc(self.as_of, "as_of")
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        if not isinstance(self.forecast_horizon, ForecastHorizon):
            raise error("forecast_horizon must be a ForecastHorizon")
        if (
            self.forecast_horizon.periods != 1
            or self.forecast_horizon.timeframe is not Timeframe.DAY_1
        ):
            raise error("forecast_horizon must be exactly one DAY_1 period")
        cash_return = self.cash_return
        if not isinstance(cash_return, Decimal) or not cash_return.is_finite():
            raise error("cash_return must be a finite Decimal")
        if cash_return < _MINIMUM_RETURN:
            raise error("cash_return cannot be below negative one")
        if not isinstance(self.source_name, str) or not self.source_name.strip():
            raise error("source_name must be nonblank")
        try:
            metadata = tuple(self.metadata)
        except TypeError as caught:
            raise error("metadata must be iterable") from caught
        if not all(isinstance(item, MetadataEntry) for item in metadata):
            raise error("metadata must contain MetadataEntry values")
        if len({item.key for item in metadata}) != len(metadata):
            raise error("metadata keys must be unique")
        if any(item.key.startswith(_RESERVED_PREFIX) for item in metadata):
            raise error(f"{_RESERVED_PREFIX} metadata keys are reserved")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(
            self, "cash_return", _ZERO if cash_return == _ZERO else cash_return
        )
        object.__setattr__(self, "metadata", metadata)


class HistoricalScenarioGenerationDiagnosticCode(StrEnum):
    """Stable valid-output qualifications."""

    MINIMUM_HISTORY_ONLY = "MINIMUM_HISTORY_ONLY"
    UNEQUAL_FINAL_RESIDUAL_PROBABILITY = "UNEQUAL_FINAL_RESIDUAL_PROBABILITY"
    CONSTANT_PRICE_SERIES = "CONSTANT_PRICE_SERIES"


@dataclass(frozen=True, slots=True)
class HistoricalScenarioGenerationDiagnostic:
    """One deterministic qualification of a valid generated result."""

    code: HistoricalScenarioGenerationDiagnosticCode
    message: str
    symbol: Symbol | None = None

    def __post_init__(self) -> None:
        error = InconsistentHistoricalScenarioResultError
        if not isinstance(self.code, HistoricalScenarioGenerationDiagnosticCode):
            raise error("diagnostic code has an invalid type")
        if not isinstance(self.message, str) or not self.message.strip():
            raise error("diagnostic message must be nonblank")
        if (
            self.code
            is HistoricalScenarioGenerationDiagnosticCode.CONSTANT_PRICE_SERIES
        ):
            if not isinstance(self.symbol, Symbol):
                raise error("constant-price diagnostics require a symbol")
        elif self.symbol is not None:
            raise error("only constant-price diagnostics may contain a symbol")


@dataclass(frozen=True, slots=True)
class HistoricalScenarioGenerationResult:
    """Complete deterministic scenario generation audit."""

    result_id: UUID
    request: HistoricalScenarioGenerationRequest
    scenario_set: ReturnScenarioSet
    expected_returns: tuple[ExpectedReturn, ...]
    diagnostics: tuple[HistoricalScenarioGenerationDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        error = InconsistentHistoricalScenarioResultError
        if not isinstance(self.result_id, UUID):
            raise error("result_id must be a UUID")
        if not isinstance(self.request, HistoricalScenarioGenerationRequest):
            raise error("request must be HistoricalScenarioGenerationRequest")
        if not isinstance(self.scenario_set, ReturnScenarioSet):
            raise error("scenario_set must be ReturnScenarioSet")
        try:
            expected_returns = tuple(self.expected_returns)
            diagnostics = tuple(self.diagnostics)
        except TypeError as caught:
            raise error("result collections must be iterable") from caught
        if not all(isinstance(item, ExpectedReturn) for item in expected_returns):
            raise error("expected_returns must contain ExpectedReturn values")
        if not all(
            isinstance(item, HistoricalScenarioGenerationDiagnostic)
            for item in diagnostics
        ):
            raise error("diagnostics contain invalid values")
        if tuple(item.symbol for item in expected_returns) != self.scenario_set.symbols:
            raise error("expected-return order must equal scenario symbol order")
        if (
            self.scenario_set.as_of != self.request.as_of
            or self.scenario_set.forecast_horizon != self.request.forecast_horizon
            or self.scenario_set.cash_return != self.request.cash_return
            or self.scenario_set.source is not ScenarioSource.HISTORICAL
            or self.scenario_set.source_name != self.request.source_name
        ):
            raise error("scenario set does not match its generation request")
        with localcontext(_CONTEXT):
            implied = self.scenario_set.implied_expected_returns()
        if expected_returns != implied:
            raise error("expected returns do not match the scenario distribution")
        _validate_diagnostic_order(diagnostics, self.scenario_set.symbols)
        expected_id = _result_id(
            self.request, self.scenario_set, expected_returns, diagnostics
        )
        if self.result_id != expected_id:
            raise error("result_id does not match deterministic identity")
        object.__setattr__(self, "expected_returns", expected_returns)
        object.__setattr__(self, "diagnostics", diagnostics)


class HistoricalReturnScenarioFactory:
    """Generate empirical scenarios without I/O or source mutation."""

    def generate(
        self, request: HistoricalScenarioGenerationRequest
    ) -> HistoricalScenarioGenerationResult:
        if not isinstance(request, HistoricalScenarioGenerationRequest):
            raise InvalidHistoricalScenarioRequestError(
                "request must be HistoricalScenarioGenerationRequest"
            )
        symbols, timestamps, prices = _validate_historical(request)
        with localcontext(_CONTEXT):
            returns = _calculate_returns(prices)
            probabilities = _calculate_probabilities(len(returns))
            rows = _construct_rows(request, symbols, timestamps, returns, probabilities)
            set_metadata = _scenario_metadata(request, timestamps, len(rows))
            set_id = _scenario_set_id(request, rows, probabilities, set_metadata)
            try:
                scenario_set = ReturnScenarioSet(
                    set_id,
                    request.as_of,
                    request.forecast_horizon,
                    symbols,
                    rows,
                    request.cash_return,
                    ScenarioSource.HISTORICAL,
                    request.source_name,
                    set_metadata,
                )
                expected_returns = scenario_set.implied_expected_returns()
            except (
                InvalidReturnScenarioSetError,
                InvalidOptimizationRequestError,
            ) as caught:
                raise HistoricalScenarioReconciliationError(str(caught)) from caught
            _reconcile_generated(
                request,
                symbols,
                timestamps,
                returns,
                probabilities,
                scenario_set,
                expected_returns,
                set_metadata,
            )
        diagnostics = _diagnostics(symbols, prices, probabilities)
        result_id = _result_id(request, scenario_set, expected_returns, diagnostics)
        return HistoricalScenarioGenerationResult(
            result_id, request, scenario_set, expected_returns, diagnostics
        )


def _validate_historical(
    request: HistoricalScenarioGenerationRequest,
) -> tuple[tuple[Symbol, ...], tuple[datetime, ...], tuple[tuple[Decimal, ...], ...]]:
    data = request.historical_data
    symbols = tuple(data.symbols)
    if not symbols or len(set(symbols)) != len(symbols):
        raise HistoricalScenarioUniverseMismatchError(
            "historical symbols must be nonempty and unique"
        )
    if not all(isinstance(item, Symbol) for item in symbols):
        raise HistoricalScenarioUniverseMismatchError(
            "historical symbols must contain Symbol values"
        )
    if data.request.timeframe is not Timeframe.DAY_1:
        raise InvalidHistoricalScenarioRequestError(
            "historical data must use Timeframe.DAY_1"
        )
    frames = tuple(data.frames)
    if len(frames) < 2:
        raise HistoricalScenarioChronologyError(
            "at least two historical observations are required"
        )
    if not data.is_complete:
        raise HistoricalScenarioUniverseMismatchError(
            "historical data must contain complete frames"
        )
    timestamps: list[datetime] = []
    prices: list[tuple[Decimal, ...]] = []
    previous = None
    for ordinal, frame in enumerate(frames):
        timestamp = frame.timestamp
        if previous is not None and timestamp <= previous:
            raise HistoricalScenarioChronologyError(
                "historical frame timestamps must be strictly increasing"
            )
        if frame.symbols != symbols or tuple(frame.bars_by_symbol) != symbols:
            raise HistoricalScenarioUniverseMismatchError(
                f"frame {ordinal} does not match the exact ordered universe"
            )
        if frame.missing_symbols or len(frame.bars_by_symbol) != len(symbols):
            raise HistoricalScenarioUniverseMismatchError(
                f"frame {ordinal} is incomplete"
            )
        frame_prices = []
        for symbol in symbols:
            bar = frame.bars_by_symbol.get(symbol)
            if bar is None or bar.symbol != symbol or bar.timestamp != timestamp:
                raise HistoricalScenarioUniverseMismatchError(
                    f"frame {ordinal} bar identity is inconsistent"
                )
            close = bar.close
            if (
                not isinstance(close, Decimal)
                or not close.is_finite()
                or close <= _ZERO
            ):
                raise HistoricalScenarioPriceError(
                    f"frame {ordinal} close for {symbol} must be a finite "
                    "positive Decimal"
                )
            frame_prices.append(close)
        timestamps.append(timestamp)
        prices.append(tuple(frame_prices))
        previous = timestamp
    if timestamps[-1] != request.as_of:
        raise HistoricalScenarioChronologyError(
            "scenario as_of must equal the final historical frame timestamp"
        )
    if any(timestamp >= request.as_of for timestamp in timestamps[:-1]):
        raise HistoricalScenarioChronologyError(
            "every earlier historical frame must precede scenario as_of"
        )
    return symbols, tuple(timestamps), tuple(prices)


def _calculate_returns(
    prices: tuple[tuple[Decimal, ...], ...],
) -> tuple[tuple[Decimal, ...], ...]:
    try:
        return tuple(
            tuple(
                next_price / previous_price - _ONE
                for previous_price, next_price in zip(previous, current, strict=True)
            )
            for previous, current in zip(prices[:-1], prices[1:], strict=True)
        )
    except DecimalException as caught:
        raise HistoricalScenarioPriceError(
            "historical price arithmetic failed"
        ) from caught


def _calculate_probabilities(count: int) -> tuple[Decimal, ...]:
    try:
        base = _ONE / Decimal(count)
        values = [base] * (count - 1)
        values.append(_ONE - sum(values, start=_ZERO))
    except DecimalException as caught:
        raise HistoricalScenarioProbabilityError(
            "scenario probability arithmetic failed"
        ) from caught
    probabilities = tuple(values)
    if any(value <= _ZERO for value in probabilities):
        raise HistoricalScenarioProbabilityError(
            "every generated probability must be positive"
        )
    if sum(probabilities, start=_ZERO) != _ONE:
        raise HistoricalScenarioProbabilityError(
            "generated probabilities must sum exactly to one"
        )
    return probabilities


def _construct_rows(
    request: HistoricalScenarioGenerationRequest,
    symbols: tuple[Symbol, ...],
    timestamps: tuple[datetime, ...],
    returns: tuple[tuple[Decimal, ...], ...],
    probabilities: tuple[Decimal, ...],
) -> tuple[ReturnScenario, ...]:
    rows = []
    try:
        for ordinal, (values, probability) in enumerate(
            zip(returns, probabilities, strict=True)
        ):
            rows.append(
                ReturnScenario(
                    _row_id(
                        request.request_id,
                        ordinal,
                        timestamps[ordinal],
                        timestamps[ordinal + 1],
                        symbols,
                        values,
                    ),
                    values,
                    probability,
                    (),
                )
            )
    except InvalidReturnScenarioError as caught:
        raise HistoricalScenarioReconciliationError(str(caught)) from caught
    return tuple(rows)


def _scenario_metadata(
    request: HistoricalScenarioGenerationRequest,
    timestamps: tuple[datetime, ...],
    row_count: int,
) -> tuple[MetadataEntry, ...]:
    return (
        *request.metadata,
        MetadataEntry(
            "historical_scenario_observation_start", timestamps[0].isoformat()
        ),
        MetadataEntry(
            "historical_scenario_observation_end", timestamps[-1].isoformat()
        ),
        MetadataEntry("historical_scenario_observation_count", str(len(timestamps))),
        MetadataEntry("historical_scenario_return_row_count", str(row_count)),
        MetadataEntry(
            "historical_scenario_price_field", request.policy.price_field.value
        ),
        MetadataEntry(
            "historical_scenario_return_method",
            request.policy.return_method.value,
        ),
        MetadataEntry(
            "historical_scenario_window_policy",
            request.policy.window_policy.value,
        ),
    )


def _diagnostics(
    symbols: tuple[Symbol, ...],
    prices: tuple[tuple[Decimal, ...], ...],
    probabilities: tuple[Decimal, ...],
) -> tuple[HistoricalScenarioGenerationDiagnostic, ...]:
    with localcontext(_CONTEXT):
        output = []
        if len(prices) == 2:
            output.append(
                HistoricalScenarioGenerationDiagnostic(
                    HistoricalScenarioGenerationDiagnosticCode.MINIMUM_HISTORY_ONLY,
                    "Only the minimum two historical observations were supplied.",
                )
            )
        base = _ONE / Decimal(len(probabilities))
        if probabilities[-1] != base:
            output.append(
                HistoricalScenarioGenerationDiagnostic(
                    HistoricalScenarioGenerationDiagnosticCode.UNEQUAL_FINAL_RESIDUAL_PROBABILITY,
                    "The final probability contains the deterministic residual.",
                )
            )
        for column, symbol in enumerate(symbols):
            first = prices[0][column]
            if all(row[column] == first for row in prices[1:]):
                output.append(
                    HistoricalScenarioGenerationDiagnostic(
                        HistoricalScenarioGenerationDiagnosticCode.CONSTANT_PRICE_SERIES,
                        f"{symbol} has a constant close-price series.",
                        symbol,
                    )
                )
        return tuple(output)


def _reconcile_generated(
    request: HistoricalScenarioGenerationRequest,
    symbols: tuple[Symbol, ...],
    timestamps: tuple[datetime, ...],
    returns: tuple[tuple[Decimal, ...], ...],
    probabilities: tuple[Decimal, ...],
    scenario_set: ReturnScenarioSet,
    expected_returns: tuple[ExpectedReturn, ...],
    metadata: tuple[MetadataEntry, ...],
) -> None:
    error = HistoricalScenarioReconciliationError
    if (
        scenario_set.symbols != symbols
        or tuple(item.returns for item in scenario_set.scenarios) != returns
        or tuple(item.probability for item in scenario_set.scenarios) != probabilities
        or scenario_set.metadata != metadata
    ):
        raise error("generated scenario set does not preserve calculated values")
    expected_row_ids = tuple(
        _row_id(
            request.request_id,
            ordinal,
            timestamps[ordinal],
            timestamps[ordinal + 1],
            symbols,
            values,
        )
        for ordinal, values in enumerate(returns)
    )
    if tuple(item.scenario_id for item in scenario_set.scenarios) != expected_row_ids:
        raise error("generated scenario row identities do not reconcile")
    expected_set_id = _scenario_set_id(
        request, scenario_set.scenarios, probabilities, metadata
    )
    if scenario_set.scenario_set_id != expected_set_id:
        raise error("generated scenario-set identity does not reconcile")
    if tuple(item.symbol for item in expected_returns) != symbols:
        raise error("implied expected-return order does not reconcile")
    if any(
        not isinstance(item.value, Decimal) or not item.value.is_finite()
        for item in expected_returns
    ):
        raise error("implied expected returns must be finite Decimals")
    try:
        implied = scenario_set.implied_expected_returns()
    except InvalidOptimizationRequestError as caught:
        raise error(str(caught)) from caught
    if expected_returns != implied:
        raise error("implied expected-return values do not reconcile")


def _validate_diagnostic_order(
    diagnostics: tuple[HistoricalScenarioGenerationDiagnostic, ...],
    symbols: tuple[Symbol, ...],
) -> None:
    error = InconsistentHistoricalScenarioResultError
    rank = {
        HistoricalScenarioGenerationDiagnosticCode.MINIMUM_HISTORY_ONLY: 0,
        (
            HistoricalScenarioGenerationDiagnosticCode.UNEQUAL_FINAL_RESIDUAL_PROBABILITY
        ): 1,
        HistoricalScenarioGenerationDiagnosticCode.CONSTANT_PRICE_SERIES: 2,
    }
    try:
        keys = tuple(
            (
                rank[item.code],
                -1 if item.symbol is None else symbols.index(item.symbol),
            )
            for item in diagnostics
        )
    except ValueError as caught:
        raise error("diagnostic symbol is outside the scenario universe") from caught
    if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
        raise error("diagnostics must be unique and in deterministic order")


def _row_id(
    request_id: UUID,
    ordinal: int,
    start: datetime,
    end: datetime,
    symbols: tuple[Symbol, ...],
    returns: tuple[Decimal, ...],
) -> UUID:
    material = (
        _VERSION,
        "row",
        str(request_id),
        str(ordinal),
        start.isoformat(),
        end.isoformat(),
        *(str(symbol) for symbol in symbols),
        *(_canonical(value) for value in returns),
    )
    return uuid5(_NAMESPACE, "|".join(material))


def _scenario_set_id(
    request: HistoricalScenarioGenerationRequest,
    rows: tuple[ReturnScenario, ...],
    probabilities: tuple[Decimal, ...],
    metadata: tuple[MetadataEntry, ...],
) -> UUID:
    material = (
        _VERSION,
        "scenario-set",
        str(request.request_id),
        *(str(item.scenario_id) for item in rows),
        *(_canonical(item) for item in probabilities),
        request.as_of.isoformat(),
        str(request.forecast_horizon.periods),
        request.forecast_horizon.timeframe.value,
        _canonical(request.cash_return),
        ScenarioSource.HISTORICAL.value,
        request.source_name,
        *(f"{item.key}={item.value}" for item in metadata),
    )
    return uuid5(_NAMESPACE, "|".join(material))


def _request_fingerprint(request: HistoricalScenarioGenerationRequest) -> str:
    data = request.historical_data
    source_request = data.request
    material = [
        str(request.request_id),
        source_request.start.isoformat(),
        source_request.end.isoformat(),
        data.provider_name,
        source_request.timeframe.value,
        source_request.adjustment.value,
        source_request.missing_bar_policy.value,
        *(str(symbol) for symbol in source_request.symbols),
    ]
    for frame in data.frames:
        material.append(frame.timestamp.isoformat())
        for symbol in source_request.symbols:
            bar = frame.bars_by_symbol.get(symbol)
            if bar is None:
                material.append(f"{symbol}=missing")
            else:
                material.extend(
                    (
                        str(bar.symbol),
                        bar.timestamp.isoformat(),
                        _canonical(bar.close),
                    )
                )
    material.extend(
        (
            request.policy.price_field.value,
            request.policy.return_method.value,
            request.policy.window_policy.value,
            request.as_of.isoformat(),
            str(request.forecast_horizon.periods),
            request.forecast_horizon.timeframe.value,
            _canonical(request.cash_return),
            request.source_name,
            *(f"{item.key}={item.value}" for item in request.metadata),
        )
    )
    return "|".join(material)


def _result_id(
    request: HistoricalScenarioGenerationRequest,
    scenario_set: ReturnScenarioSet,
    expected_returns: tuple[ExpectedReturn, ...],
    diagnostics: tuple[HistoricalScenarioGenerationDiagnostic, ...],
) -> UUID:
    material = (
        _VERSION,
        "result",
        _request_fingerprint(request),
        str(scenario_set.scenario_set_id),
        *(f"{item.symbol}={_canonical(item.value)}" for item in expected_returns),
        *(
            f"{item.code.value}={item.symbol if item.symbol is not None else 'none'}"
            for item in diagnostics
        ),
    )
    return uuid5(_NAMESPACE, "|".join(material))


def _canonical(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("identity values must be finite Decimals")
    if value == _ZERO:
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered
