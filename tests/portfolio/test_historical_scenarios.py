from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from types import MappingProxyType
from uuid import UUID

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.market_data import (
    AlignedMarketFrame,
    MissingBarPolicy,
    MultiSymbolHistoricalDataRequest,
    MultiSymbolHistoricalDataResult,
    Timeframe,
)
from trading_bot.portfolio import (
    ForecastHorizon,
    HistoricalReturnScenarioFactory,
    HistoricalScenarioChronologyError,
    HistoricalScenarioGenerationDiagnosticCode,
    HistoricalScenarioGenerationPolicy,
    HistoricalScenarioGenerationRequest,
    HistoricalScenarioPriceError,
    HistoricalScenarioPriceField,
    HistoricalScenarioReturnMethod,
    HistoricalScenarioUniverseMismatchError,
    HistoricalScenarioWindowPolicy,
    InconsistentHistoricalScenarioResultError,
    InvalidHistoricalScenarioRequestError,
    MetadataEntry,
    ScenarioSource,
)
from trading_bot.portfolio.historical_scenarios import _result_id, _row_id

SPY = Symbol("SPY")
QQQ = Symbol("QQQ")
SYMBOLS = (SPY, QQQ)
START = datetime(2026, 1, 5, 20, tzinfo=UTC)


def _bar(symbol: Symbol, timestamp: datetime, close: Decimal) -> Bar:
    return Bar(symbol, timestamp, close, close, close, close, 100)


def _data(
    rows: tuple[tuple[str, str], ...] = (
        ("100", "50"),
        ("110", "45"),
        ("99", "45"),
    ),
    *,
    policy: MissingBarPolicy = MissingBarPolicy.INTERSECTION,
    symbols: tuple[Symbol, ...] = SYMBOLS,
    start: datetime = START,
) -> MultiSymbolHistoricalDataResult:
    timestamps = tuple(start + timedelta(days=index) for index in range(len(rows)))
    request = MultiSymbolHistoricalDataRequest(
        symbols,
        timestamps[0] - timedelta(days=1),
        timestamps[-1] + timedelta(days=1),
        missing_bar_policy=policy,
    )
    frames = tuple(
        AlignedMarketFrame(
            timestamp,
            symbols,
            {
                symbol: _bar(symbol, timestamp, Decimal(value))
                for symbol, value in zip(symbols, values, strict=True)
            },
        )
        for timestamp, values in zip(timestamps, rows, strict=True)
    )
    return MultiSymbolHistoricalDataResult(request, frames, "fixture")


def _request(
    data: MultiSymbolHistoricalDataResult | None = None,
    **changes,
) -> HistoricalScenarioGenerationRequest:
    source = _data() if data is None else data
    values = {
        "request_id": UUID(int=1),
        "historical_data": source,
        "policy": HistoricalScenarioGenerationPolicy(),
        "as_of": source.frames[-1].timestamp,
        "forecast_horizon": ForecastHorizon(1, Timeframe.DAY_1),
        "cash_return": Decimal("0.001"),
        "source_name": "local-csv",
        "metadata": (MetadataEntry("dataset", "fixture"),),
    }
    values.update(changes)
    return HistoricalScenarioGenerationRequest(**values)


def _generate(
    data: MultiSymbolHistoricalDataResult | None = None,
    **changes,
):
    return HistoricalReturnScenarioFactory().generate(_request(data, **changes))


def test_policy_defaults_are_explicit() -> None:
    policy = HistoricalScenarioGenerationPolicy()
    assert policy.price_field is HistoricalScenarioPriceField.CLOSE
    assert policy.return_method is HistoricalScenarioReturnMethod.SIMPLE
    assert policy.window_policy is HistoricalScenarioWindowPolicy.ALL_SUPPLIED


def test_valid_generation_preserves_order_and_uses_historical_source() -> None:
    result = _generate()
    assert result.scenario_set.symbols == SYMBOLS
    assert result.scenario_set.source is ScenarioSource.HISTORICAL
    assert result.scenario_set.source_name == "local-csv"
    assert all(not row.metadata for row in result.scenario_set.scenarios)
    assert tuple(row.returns for row in result.scenario_set.scenarios) == (
        (Decimal("0.1"), Decimal("-0.1")),
        (Decimal("-0.1"), Decimal("0")),
    )
    assert tuple(item.symbol for item in result.expected_returns) == SYMBOLS
    assert result.expected_returns == result.scenario_set.implied_expected_returns()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("request_id", "bad", "UUID"),
        ("historical_data", object(), "exactly"),
        ("policy", object(), "policy"),
        ("as_of", datetime(2026, 1, 1), "timezone"),
        ("cash_return", Decimal("NaN"), "finite"),
        ("cash_return", Decimal("-1.01"), "negative one"),
        ("source_name", " ", "nonblank"),
        (
            "forecast_horizon",
            ForecastHorizon(2, Timeframe.DAY_1),
            "exactly one",
        ),
    ],
)
def test_request_rejects_invalid_fields(field: str, value, message: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(InvalidHistoricalScenarioRequestError, match=message):
        _request(**{field: value})


def test_request_defensively_copies_metadata_and_rejects_bad_keys() -> None:
    metadata = [MetadataEntry("source", "test")]
    request = _request(metadata=metadata)
    metadata.clear()
    assert request.metadata == (MetadataEntry("source", "test"),)
    with pytest.raises(InvalidHistoricalScenarioRequestError, match="unique"):
        _request(metadata=(MetadataEntry("x", "1"), MetadataEntry("x", "2")))
    with pytest.raises(InvalidHistoricalScenarioRequestError, match="reserved"):
        _request(metadata=(MetadataEntry("historical_scenario_x", "1"),))


def test_corrupted_policy_is_rejected() -> None:
    policy = HistoricalScenarioGenerationPolicy()
    object.__setattr__(policy, "price_field", "CLOSE")
    with pytest.raises(InvalidHistoricalScenarioRequestError, match="CLOSE"):
        _request(policy=policy)


def test_at_least_two_frames_are_required() -> None:
    data = _data()
    object.__setattr__(data, "frames", data.frames[:1])
    with pytest.raises(HistoricalScenarioChronologyError, match="at least two"):
        _generate(data)


def test_incomplete_union_is_rejected_and_complete_union_is_accepted() -> None:
    complete = _data(policy=MissingBarPolicy.UNION)
    assert _generate(complete).scenario_set.scenario_count == 2
    first = complete.frames[0]
    incomplete = AlignedMarketFrame(
        first.timestamp, SYMBOLS, {SPY: first.bars_by_symbol[SPY]}
    )
    object.__setattr__(complete, "frames", (incomplete, *complete.frames[1:]))
    with pytest.raises(HistoricalScenarioUniverseMismatchError, match="complete"):
        _generate(complete)


def test_duplicate_and_nonincreasing_timestamps_are_rejected() -> None:
    data = _data()
    object.__setattr__(data.frames[1], "timestamp", data.frames[0].timestamp)
    with pytest.raises(HistoricalScenarioChronologyError, match="strictly increasing"):
        _generate(data)


@pytest.mark.parametrize("offset", [-1, 1])
def test_as_of_must_equal_final_observation(offset: int) -> None:
    data = _data()
    with pytest.raises(HistoricalScenarioChronologyError, match="must equal"):
        _generate(data, as_of=data.frames[-1].timestamp + timedelta(days=offset))


def test_reordered_universe_and_bar_identity_are_rejected() -> None:
    data = _data()
    object.__setattr__(data.frames[0], "symbols", tuple(reversed(SYMBOLS)))
    with pytest.raises(HistoricalScenarioUniverseMismatchError, match="universe"):
        _generate(data)

    data = _data()
    frame = data.frames[0]
    wrong = _bar(QQQ, frame.timestamp, Decimal("100"))
    object.__setattr__(
        frame,
        "bars_by_symbol",
        MappingProxyType({SPY: wrong, QQQ: frame.bars_by_symbol[QQQ]}),
    )
    with pytest.raises(HistoricalScenarioUniverseMismatchError, match="identity"):
        _generate(data)


@pytest.mark.parametrize("price", [Decimal("0"), Decimal("-1"), Decimal("NaN")])
def test_invalid_close_prices_are_rejected(price: Decimal) -> None:
    data = _data()
    object.__setattr__(data.frames[0].bars_by_symbol[SPY], "close", price)
    with pytest.raises(HistoricalScenarioPriceError, match="positive Decimal"):
        _generate(data)


def test_positive_negative_zero_and_multiple_period_returns() -> None:
    result = _generate(_data((("10", "10"), ("12", "10"), ("6", "15"), ("6", "12"))))
    assert tuple(item.returns for item in result.scenario_set.scenarios) == (
        (Decimal("0.2"), Decimal("0")),
        (Decimal("-0.5"), Decimal("0.5")),
        (Decimal("0"), Decimal("-0.2")),
    )


def test_repeating_division_and_ambient_context_are_deterministic() -> None:
    data = _data((("3", "7"), ("4", "8"), ("5", "9"), ("6", "10")))
    with localcontext() as context:
        context.prec = 6
        first = _generate(data)
    with localcontext() as context:
        context.prec = 50
        second = _generate(data)
    assert first == second
    assert first.scenario_set.scenarios[0].returns[0] == Decimal(
        "0.333333333333333333333333333"
    )


def test_source_objects_are_not_mutated() -> None:
    data = _data()
    frames = data.frames
    bars = tuple(tuple(frame.bars_by_symbol.values()) for frame in frames)
    _generate(data)
    assert data.frames is frames
    assert tuple(tuple(frame.bars_by_symbol.values()) for frame in frames) == bars


def test_probability_rules_and_residual_diagnostic() -> None:
    one = _generate(_data((("1", "2"), ("2", "3"))))
    assert tuple(item.probability for item in one.scenario_set.scenarios) == (
        Decimal("1"),
    )
    assert one.diagnostics[0].code is (
        HistoricalScenarioGenerationDiagnosticCode.MINIMUM_HISTORY_ONLY
    )

    two = _generate(_data((("1", "2"), ("2", "3"), ("3", "4"))))
    assert tuple(item.probability for item in two.scenario_set.scenarios) == (
        Decimal("0.5"),
        Decimal("0.5"),
    )

    three = _generate(_data((("1", "2"), ("2", "3"), ("3", "4"), ("4", "5"))))
    probabilities = tuple(item.probability for item in three.scenario_set.scenarios)
    assert all(item > 0 for item in probabilities)
    assert sum(probabilities, start=Decimal("0")) == Decimal("1")
    assert probabilities[-1] != probabilities[0]
    assert three.diagnostics[0].code is (
        HistoricalScenarioGenerationDiagnosticCode.UNEQUAL_FINAL_RESIDUAL_PROBABILITY
    )


def test_expected_returns_are_exact_weighted_means() -> None:
    result = _generate(_data((("10", "10"), ("12", "8"), ("6", "12"), ("9", "12"))))
    with localcontext() as context:
        context.prec = 28
        assert result.expected_returns == result.scenario_set.implied_expected_returns()
    assert tuple(item.symbol for item in result.expected_returns) == SYMBOLS


def test_constant_price_diagnostics_follow_symbol_order() -> None:
    result = _generate(_data((("10", "20"), ("10", "20"), ("10", "20"))))
    constants = tuple(
        item
        for item in result.diagnostics
        if item.code is HistoricalScenarioGenerationDiagnosticCode.CONSTANT_PRICE_SERIES
    )
    assert tuple(item.symbol for item in constants) == SYMBOLS


def test_ordinary_two_row_case_has_no_diagnostics() -> None:
    result = _generate(_data((("1", "2"), ("2", "3"), ("4", "6"))))
    assert result.diagnostics == ()


def test_metadata_contains_caller_entries_then_generated_provenance() -> None:
    result = _generate()
    keys = tuple(item.key for item in result.scenario_set.metadata)
    assert keys == (
        "dataset",
        "historical_scenario_observation_start",
        "historical_scenario_observation_end",
        "historical_scenario_observation_count",
        "historical_scenario_return_row_count",
        "historical_scenario_price_field",
        "historical_scenario_return_method",
        "historical_scenario_window_policy",
    )


def test_identity_is_deterministic_and_changes_with_material_inputs() -> None:
    first = _generate()
    assert first == _generate()
    assert first.result_id != _generate(cash_return=Decimal("0.002")).result_id
    assert first.result_id != _generate(source_name="other").result_id
    assert (
        first.result_id
        != _generate(metadata=(MetadataEntry("dataset", "other"),)).result_id
    )
    assert (
        first.result_id != _generate(_data(start=START + timedelta(days=1))).result_id
    )
    assert first.result_id != _generate(_data(symbols=(QQQ, SPY))).result_id
    changed = _data()
    object.__setattr__(changed.frames[0].bars_by_symbol[SPY], "close", Decimal("101"))
    assert first.result_id != _generate(changed).result_id


def test_row_identity_and_result_identity_exclusions() -> None:
    result = _generate()
    row = result.scenario_set.scenarios[0]
    row_id = _row_id(
        result.request.request_id,
        0,
        result.request.historical_data.frames[0].timestamp,
        result.request.historical_data.frames[1].timestamp,
        result.scenario_set.symbols,
        row.returns,
    )
    assert row_id == row.scenario_id
    changed_messages = tuple(
        replace(item, message="Different human-readable text.")
        for item in result.diagnostics
    )
    assert (
        _result_id(
            result.request,
            result.scenario_set,
            result.expected_returns,
            changed_messages,
        )
        == result.result_id
    )


def test_result_rejects_inconsistent_identity_and_expected_order() -> None:
    result = _generate()
    with pytest.raises(InconsistentHistoricalScenarioResultError, match="result_id"):
        replace(result, result_id=UUID(int=99))
    with pytest.raises(
        InconsistentHistoricalScenarioResultError, match="expected-return order"
    ):
        replace(result, expected_returns=tuple(reversed(result.expected_returns)))
