from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import Symbol
from trading_bot.market_data import Timeframe
from trading_bot.portfolio import (
    ForecastHorizon,
    InvalidReturnScenarioError,
    InvalidReturnScenarioSetError,
    MetadataEntry,
    ReturnScenario,
    ReturnScenarioSet,
    ScenarioCompatibilityError,
    ScenarioSource,
    ScenarioUniverseMismatchError,
)

NOW = datetime(2026, 7, 21, 20, tzinfo=UTC)
HORIZON = ForecastHorizon(5, Timeframe.DAY_1)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def row(
    identifier: int,
    returns: tuple[str, ...],
    probability: str,
    metadata: tuple[MetadataEntry, ...] = (),
) -> ReturnScenario:
    return ReturnScenario(
        UUID(int=identifier),
        tuple(Decimal(value) for value in returns),
        Decimal(probability),
        metadata,
    )


def scenario_set(
    scenarios: tuple[ReturnScenario, ...] | None = None,
    *,
    symbols: tuple[Symbol, ...] = (SPY, QQQ),
    cash_return: str = "0",
    source: ScenarioSource = ScenarioSource.MANUAL,
    source_name: str | None = None,
    as_of: datetime = NOW,
    horizon: ForecastHorizon = HORIZON,
    metadata: tuple[MetadataEntry, ...] = (),
) -> ReturnScenarioSet:
    scenarios = scenarios or (row(1, ("0.1", "-0.1"), "1"),)
    return ReturnScenarioSet(
        UUID(int=100),
        as_of,
        horizon,
        symbols,
        scenarios,
        Decimal(cash_return),
        source,
        source_name,
        metadata,
    )


def test_one_scenario_preserves_columns_and_explicit_probability() -> None:
    item = scenario_set()
    assert item.symbols == (SPY, QQQ)
    assert item.scenarios[0].returns == (Decimal("0.1"), Decimal("-0.1"))
    assert item.scenarios[0].probability == Decimal("1")
    assert item.scenario_count == 1


def test_equal_and_unequal_probability_rows_preserve_producer_order() -> None:
    equal = scenario_set((row(2, ("0.1", "0"), "0.5"), row(1, ("0", "0.1"), "0.5")))
    assert tuple(item.scenario_id for item in equal.scenarios) == (
        UUID(int=2),
        UUID(int=1),
    )
    unequal = scenario_set((row(1, ("0", "0"), "0.25"), row(2, ("0", "0"), "0.75")))
    assert tuple(item.probability for item in unequal.scenarios) == (
        Decimal("0.25"),
        Decimal("0.75"),
    )


def test_probability_total_is_exact_and_near_one_is_rejected() -> None:
    with pytest.raises(InvalidReturnScenarioSetError, match="exactly"):
        scenario_set(
            (
                row(1, ("0", "0"), "0.5"),
                row(2, ("0", "0"), "0.499999"),
            )
        )


@pytest.mark.parametrize("probability", ("0", "-0.1", "1.1", "NaN", "Infinity"))
def test_probability_must_be_positive_finite_and_at_most_one(
    probability: str,
) -> None:
    with pytest.raises(InvalidReturnScenarioError, match="probability"):
        row(1, ("0",), probability)


def test_returns_accept_signed_values_and_exact_negative_one() -> None:
    item = row(1, ("0.2", "0", "-0.5", "-1"), "1")
    assert item.returns[-1] == Decimal("-1")
    with pytest.raises(InvalidReturnScenarioError, match="negative one"):
        row(2, ("-1.0001",), "1")


@pytest.mark.parametrize("value", ("NaN", "Infinity", "-Infinity"))
def test_nonfinite_returns_are_rejected(value: str) -> None:
    with pytest.raises(InvalidReturnScenarioError, match="finite"):
        row(1, (value,), "1")


def test_negative_zero_is_normalized_for_returns_probability_and_cash() -> None:
    scenario = row(1, ("-0",), "1")
    item = scenario_set((scenario,), symbols=(SPY,), cash_return="-0")
    assert scenario.returns[0] == Decimal("0")
    assert not scenario.returns[0].is_signed()
    assert item.cash_return == Decimal("0")
    assert not item.cash_return.is_signed()


def test_empty_rows_sets_and_universes_are_rejected() -> None:
    with pytest.raises(InvalidReturnScenarioError, match="empty"):
        ReturnScenario(UUID(int=1), (), Decimal("1"))
    with pytest.raises(InvalidReturnScenarioSetError, match="symbols"):
        scenario_set(symbols=())
    with pytest.raises(InvalidReturnScenarioSetError, match="scenarios"):
        ReturnScenarioSet(UUID(int=100), NOW, HORIZON, (SPY,), (), Decimal("0"))


def test_row_width_duplicate_symbols_and_scenario_ids_are_rejected() -> None:
    with pytest.raises(InvalidReturnScenarioSetError, match="width"):
        scenario_set((row(1, ("0",), "1"),))
    with pytest.raises(InvalidReturnScenarioSetError, match="symbols"):
        scenario_set(symbols=(SPY, SPY))
    duplicate = row(1, ("0", "0"), "0.5")
    with pytest.raises(InvalidReturnScenarioSetError, match="IDs"):
        scenario_set((duplicate, duplicate))


def test_tuple_inputs_are_copied_without_mutating_callers() -> None:
    returns = [Decimal("0"), Decimal("0.1")]
    row_metadata = [MetadataEntry("row", "first")]
    scenario = ReturnScenario(UUID(int=1), returns, Decimal("1"), row_metadata)  # type: ignore[arg-type]
    symbols = [SPY, QQQ]
    scenarios = [scenario]
    set_metadata = [MetadataEntry("set", "fixture")]
    item = ReturnScenarioSet(  # type: ignore[arg-type]
        UUID(int=100),
        NOW,
        HORIZON,
        symbols,
        scenarios,
        metadata=set_metadata,
    )
    returns[0] = Decimal("1")
    symbols.reverse()
    scenarios.clear()
    assert scenario.returns == (Decimal("0"), Decimal("0.1"))
    assert item.symbols == (SPY, QQQ)
    assert item.scenario_count == 1


def test_duplicate_metadata_keys_are_rejected_at_both_levels() -> None:
    metadata = (MetadataEntry("a", "1"), MetadataEntry("a", "2"))
    with pytest.raises(InvalidReturnScenarioError, match="unique"):
        row(1, ("0",), "1", metadata)
    with pytest.raises(InvalidReturnScenarioSetError, match="unique"):
        scenario_set(metadata=metadata)


@pytest.mark.parametrize(
    "source",
    (
        ScenarioSource.HISTORICAL,
        ScenarioSource.BOOTSTRAP,
        ScenarioSource.MONTE_CARLO,
        ScenarioSource.IMPORTED,
    ),
)
def test_nonmanual_sources_require_nonblank_source_name(
    source: ScenarioSource,
) -> None:
    with pytest.raises(InvalidReturnScenarioSetError, match="source_name"):
        scenario_set(source=source)
    item = scenario_set(source=source, source_name="fixture-generator")
    assert item.source_name == "fixture-generator"


def test_manual_source_name_is_optional_but_nonblank_when_supplied() -> None:
    assert scenario_set().source_name is None
    with pytest.raises(InvalidReturnScenarioSetError, match="source_name"):
        scenario_set(source_name=" ")


def test_timestamp_normalization_and_naive_rejection() -> None:
    offset = timezone(timedelta(hours=-4))
    item = scenario_set(as_of=NOW.astimezone(offset))
    assert item.as_of == NOW
    with pytest.raises(InvalidReturnScenarioSetError, match="aware"):
        scenario_set(as_of=NOW.replace(tzinfo=None))


def test_explicit_cash_return_boundary_and_validation() -> None:
    assert scenario_set(cash_return="0.01").cash_return == Decimal("0.01")
    assert scenario_set(cash_return="-1").cash_return == Decimal("-1")
    with pytest.raises(InvalidReturnScenarioSetError, match="negative one"):
        scenario_set(cash_return="-1.01")
    with pytest.raises(InvalidReturnScenarioSetError, match="finite"):
        scenario_set(cash_return="NaN")


def test_implied_expected_returns_are_exact_ordered_and_exclude_cash() -> None:
    item = scenario_set(
        (
            row(1, ("0.1", "-0.2"), "0.25"),
            row(2, ("0.3", "0.2"), "0.75"),
        ),
        cash_return="0.05",
    )
    implied = item.implied_expected_returns()
    assert tuple(value.symbol for value in implied) == (SPY, QQQ)
    assert tuple(value.value for value in implied) == (
        Decimal("0.250"),
        Decimal("0.100"),
    )
    assert all(value.value != item.cash_return for value in implied)


def test_exact_compatibility_and_each_mismatch_category() -> None:
    item = scenario_set()
    item.validate_compatibility(as_of=NOW, forecast_horizon=HORIZON, symbols=(SPY, QQQ))
    with pytest.raises(ScenarioUniverseMismatchError):
        item.validate_compatibility(
            as_of=NOW, forecast_horizon=HORIZON, symbols=(QQQ, SPY)
        )
    with pytest.raises(ScenarioCompatibilityError, match="as_of"):
        item.validate_compatibility(
            as_of=NOW + timedelta(days=1),
            forecast_horizon=HORIZON,
            symbols=(SPY, QQQ),
        )
    with pytest.raises(ScenarioCompatibilityError, match="horizon"):
        item.validate_compatibility(
            as_of=NOW,
            forecast_horizon=ForecastHorizon(6, Timeframe.DAY_1),
            symbols=(SPY, QQQ),
        )


def test_repeated_equal_construction_is_equal() -> None:
    assert scenario_set() == scenario_set()
