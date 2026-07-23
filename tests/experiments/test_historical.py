from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import Bar, OrderFill, OrderSide, Symbol
from trading_bot.execution import OrderEngine, PaperFillPolicy
from trading_bot.experiments import (
    HistoricalExperimentBootstrapPosition,
    HistoricalExperimentInitializationError,
    HistoricalExperimentInitializationMode,
    HistoricalExperimentInitialState,
    HistoricalExperimentIsolationError,
    HistoricalExperimentRequest,
    HistoricalExperimentRunner,
    HistoricalExperimentVariant,
    HistoricalExperimentVariantError,
    InvalidHistoricalExperimentRequestError,
)
from trading_bot.ledger import PaperLedger
from trading_bot.market_data import (
    AlignedMarketFrame,
    MultiSymbolHistoricalDataRequest,
    MultiSymbolHistoricalDataResult,
)
from trading_bot.portfolio import (
    HistoricalScenarioGenerationPolicy,
    MeanCvarOptimizationParameters,
    MetadataEntry,
    PortfolioConstraints,
)
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime import PaperPortfolioRuntime
from trading_bot.simulation import (
    OptimizedPaperPortfolioSimulator,
    RollingHistoricalCycleTimingPolicy,
    RollingHistoricalExecutionPricePolicy,
    RollingHistoricalWindowPolicy,
)

SPY = Symbol("SPY")
QQQ = Symbol("QQQ")
SYMBOLS = (SPY, QQQ)
START = datetime(2026, 1, 5, 20, tzinfo=UTC)


def _history(
    rows: tuple[tuple[str, str], ...] = (
        ("100", "100"),
        ("102", "99"),
        ("104", "98"),
        ("106", "97"),
        ("108", "96"),
    ),
) -> MultiSymbolHistoricalDataResult:
    timestamps = tuple(START + timedelta(days=index) for index in range(len(rows)))
    request = MultiSymbolHistoricalDataRequest(
        SYMBOLS,
        START - timedelta(days=1),
        timestamps[-1] + timedelta(days=1),
    )
    frames = tuple(
        AlignedMarketFrame(
            timestamp,
            SYMBOLS,
            {
                symbol: Bar(
                    symbol,
                    timestamp,
                    Decimal(close),
                    Decimal(close),
                    Decimal(close),
                    Decimal(close),
                    100,
                )
                for symbol, close in zip(SYMBOLS, values, strict=True)
            },
        )
        for timestamp, values in zip(timestamps, rows, strict=True)
    )
    return MultiSymbolHistoricalDataResult(request, frames, "fixture")


def _variant(
    identifier: int,
    *,
    name: str | None = None,
    risk_aversion: str = "1",
    trading_enabled: bool = True,
) -> HistoricalExperimentVariant:
    fee = Decimal("0")
    return HistoricalExperimentVariant(
        UUID(int=identifier),
        name or f"variant-{identifier}",
        RollingHistoricalWindowPolicy(3),
        HistoricalScenarioGenerationPolicy(),
        RollingHistoricalExecutionPricePolicy(),
        RollingHistoricalCycleTimingPolicy(timedelta(minutes=1), timedelta(minutes=2)),
        Decimal("0"),
        "fixture",
        MeanCvarOptimizationParameters(Decimal("0.75")),
        Decimal(risk_aversion),
        PortfolioConstraints(maximum_position_weight=Decimal("0.6")),
        RebalanceAssumptions(fixed_commission=fee),
        RebalanceProposalPolicy(allow_partial_plans=True),
        None,
        RiskLimits(
            max_position_percent=Decimal("0.6"),
            max_total_exposure_percent=Decimal("1"),
            minimum_cash_reserve_percent=Decimal("0"),
            estimated_commission=fee,
        ),
        PortfolioRiskPolicy(),
        PaperFillPolicy(Decimal("0"), fee),
        trading_enabled,
    )


def _initial(
    *,
    bootstrap: bool = False,
) -> HistoricalExperimentInitialState:
    return HistoricalExperimentInitialState(
        (
            HistoricalExperimentInitializationMode.BOOTSTRAP_FILLS
            if bootstrap
            else HistoricalExperimentInitializationMode.CASH_ONLY
        ),
        START - timedelta(hours=1),
        Decimal("1000"),
        (
            (HistoricalExperimentBootstrapPosition(SPY, Decimal("1"), Decimal("100")),)
            if bootstrap
            else ()
        ),
    )


def _request(
    *,
    history: MultiSymbolHistoricalDataResult | None = None,
    initial: HistoricalExperimentInitialState | None = None,
    variants: tuple[HistoricalExperimentVariant, ...] | None = None,
    metadata: tuple[MetadataEntry, ...] = (),
) -> HistoricalExperimentRequest:
    data = history or _history()
    return HistoricalExperimentRequest(
        UUID(int=1),
        data,
        (data.frames[2].timestamp, data.frames[4].timestamp),
        initial or _initial(),
        variants or (_variant(10), _variant(11, risk_aversion="2")),
        metadata,
    )


class _Factory:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, int]] = []

    def __call__(
        self,
        initial_state,
        *,
        experiment_request_id,
        variant_id,
        variant_ordinal,
    ):  # noqa: ANN001, ANN204
        self.calls.append((variant_id, variant_ordinal))
        basis = sum(
            (
                item.quantity * item.unit_cost
                for item in initial_state.bootstrap_positions
            ),
            start=Decimal("0"),
        )
        ledger = PaperLedger(initial_state.available_cash + basis)
        for index, item in enumerate(initial_state.bootstrap_positions):
            ledger.apply_fill(
                OrderFill(
                    UUID(int=10_000 + variant_ordinal * 10 + index),
                    UUID(int=20_000 + variant_ordinal * 10 + index),
                    item.symbol,
                    OrderSide.BUY,
                    item.quantity,
                    item.unit_cost,
                    Decimal("0"),
                    initial_state.as_of,
                )
            )
        return OptimizedPaperPortfolioSimulator(
            PaperPortfolioRuntime(OrderEngine(), ledger)
        )


def test_initial_state_validation_and_defensive_copying() -> None:
    positions = [
        HistoricalExperimentBootstrapPosition(SPY, Decimal("1"), Decimal("100"))
    ]
    state = HistoricalExperimentInitialState(
        HistoricalExperimentInitializationMode.BOOTSTRAP_FILLS,
        START.astimezone(tz=timedelta_timezone(-5)),
        Decimal("1000"),
        positions,
    )
    positions.clear()
    assert state.as_of == START
    assert len(state.bootstrap_positions) == 1
    with pytest.raises(InvalidHistoricalExperimentRequestError, match="CASH_ONLY"):
        replace(state, mode=HistoricalExperimentInitializationMode.CASH_ONLY)
    with pytest.raises(InvalidHistoricalExperimentRequestError, match="exactly zero"):
        replace(state, bootstrap_commission=Decimal("1"))


def timedelta_timezone(hours: int):  # type: ignore[no-untyped-def]
    from datetime import timezone

    return timezone(timedelta(hours=hours))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("name", " "),
        ("trading_enabled", 1),
        ("risk_aversion", Decimal("-1")),
        (
            "metadata",
            (MetadataEntry("historical_experiment_forbidden", "x"),),
        ),
    ),
)
def test_variant_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(HistoricalExperimentVariantError):
        replace(_variant(10), **{field: value})


def test_request_copies_schedule_variants_and_rejects_duplicates() -> None:
    data = _history()
    schedule = [data.frames[2].timestamp, data.frames[4].timestamp]
    variants = [_variant(10), _variant(11)]
    request = HistoricalExperimentRequest(
        UUID(int=1), data, schedule, _initial(), variants
    )
    schedule.clear()
    variants.clear()
    assert len(request.rebalance_timestamps) == 2
    assert len(request.variants) == 2
    with pytest.raises(InvalidHistoricalExperimentRequestError, match="IDs"):
        replace(request, variants=(_variant(10), _variant(10, name="other")))
    with pytest.raises(InvalidHistoricalExperimentRequestError, match="names"):
        replace(
            request,
            variants=(_variant(10, name=" Alpha "), _variant(11, name="alpha")),
        )


def test_two_variants_run_in_order_with_exact_shared_inputs_and_metrics() -> None:
    factory = _Factory()
    request = _request()
    result = HistoricalExperimentRunner(factory).run(request)
    assert factory.calls == [(UUID(int=10), 0), (UUID(int=11), 1)]
    assert tuple(item.variant for item in result.runs) == request.variants
    assert all(
        item.rolling_result.request.historical_data is request.historical_data
        and item.rolling_result.request.rebalance_timestamps
        == request.rebalance_timestamps
        for item in result.runs
    )
    first = result.runs[0]
    performance = first.rolling_result.performance_result
    assert first.metrics.final_equity == performance.final_equity
    assert first.metrics.simulation_realized_profit_loss == (
        performance.cumulative_simulation_realized_profit_loss
    )
    assert first.metrics.total_orders == performance.total_order_count
    assert tuple(item.ordinal for item in result.runs) == (0, 1)


def test_generated_metadata_is_only_experiment_provenance() -> None:
    variant = replace(
        _variant(10), metadata=(MetadataEntry("variant_note", "private"),)
    )
    request = _request(
        variants=(variant,),
        metadata=(MetadataEntry("experiment_note", "private"),),
    )
    result = HistoricalExperimentRunner(_Factory()).run(request)
    metadata = result.runs[0].rolling_result.request.metadata
    assert tuple(item.key for item in metadata) == (
        "historical_experiment_id",
        "historical_experiment_variant_id",
        "historical_experiment_variant_ordinal",
        "historical_experiment_variant_name",
    )


def test_bootstrap_ids_may_differ_while_content_fingerprint_is_equal() -> None:
    result = HistoricalExperimentRunner(_Factory()).run(
        _request(
            history=_history((("100", "100"),) * 5),
            initial=_initial(bootstrap=True),
            variants=(
                _variant(10, trading_enabled=False),
                _variant(11, risk_aversion="2", trading_enabled=False),
            ),
        )
    )
    assert result.runs[0].rolling_result.initial_ledger_state_id != (
        result.runs[1].rolling_result.initial_ledger_state_id
    )
    assert result.runs[0].initial_state_content_fingerprint == (
        result.runs[1].initial_state_content_fingerprint
    )


def test_equal_inputs_and_equivalent_factories_produce_equal_result() -> None:
    request = _request()
    first = HistoricalExperimentRunner(_Factory()).run(request)
    second = HistoricalExperimentRunner(_Factory()).run(request)
    assert first == second
    changed = HistoricalExperimentRunner(_Factory()).run(
        replace(request, metadata=(MetadataEntry("changed", "yes"),))
    )
    assert changed.result_id != first.result_id


def test_reordered_variants_preserve_metrics_by_id_but_change_result_order() -> None:
    request = _request()
    first = HistoricalExperimentRunner(_Factory()).run(request)
    reordered = HistoricalExperimentRunner(_Factory()).run(
        replace(request, variants=tuple(reversed(request.variants)))
    )
    assert tuple(item.variant.variant_id for item in reordered.runs) == (
        UUID(int=11),
        UUID(int=10),
    )
    first_metrics = {item.variant.variant_id: item.metrics for item in first.runs}
    reordered_metrics = {
        item.variant.variant_id: item.metrics for item in reordered.runs
    }
    assert first_metrics == reordered_metrics
    assert first.result_id != reordered.result_id


def test_invalid_factory_return_is_rejected_with_variant_context() -> None:
    def factory(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return object()

    with pytest.raises(HistoricalExperimentInitializationError) as caught:
        HistoricalExperimentRunner(factory).run(_request())
    assert caught.value.variant_ordinal == 0
    assert caught.value.variant_id == UUID(int=10)
    assert caught.value.stage == "factory-return"


def test_incorrect_initialized_cash_is_rejected() -> None:
    def factory(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return OptimizedPaperPortfolioSimulator(
            PaperPortfolioRuntime(OrderEngine(), PaperLedger(Decimal("999")))
        )

    with pytest.raises(HistoricalExperimentInitializationError, match="cash"):
        HistoricalExperimentRunner(factory).run(_request())


@pytest.mark.parametrize("component", ("simulator", "runtime", "engine", "ledger"))
def test_reused_mutable_component_is_rejected(component: str) -> None:
    base = _Factory()
    first = base(
        _initial(),
        experiment_request_id=UUID(int=1),
        variant_id=UUID(int=10),
        variant_ordinal=0,
    )
    calls = 0

    def factory(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        nonlocal calls
        calls += 1
        if calls == 1:
            return first
        if component == "simulator":
            return first
        if component == "runtime":
            return OptimizedPaperPortfolioSimulator(first.runtime)
        if component == "engine":
            return OptimizedPaperPortfolioSimulator(
                PaperPortfolioRuntime(first.engine, PaperLedger(Decimal("1000")))
            )
        return OptimizedPaperPortfolioSimulator(
            PaperPortfolioRuntime(OrderEngine(), first.ledger)
        )

    with pytest.raises(HistoricalExperimentIsolationError) as caught:
        HistoricalExperimentRunner(factory).run(_request())
    assert caught.value.variant_ordinal == 1
    assert caught.value.stage == f"{component}-isolation"


def test_fail_fast_stops_later_variant_and_does_not_retry() -> None:
    calls: list[int] = []

    def factory(
        initial_state,
        *,
        experiment_request_id,
        variant_id,
        variant_ordinal,
    ):  # noqa: ANN001, ANN202
        calls.append(variant_ordinal)
        if variant_ordinal == 1:
            return object()
        return _Factory()(
            initial_state,
            experiment_request_id=experiment_request_id,
            variant_id=variant_id,
            variant_ordinal=variant_ordinal,
        )

    request = _request(variants=(_variant(10), _variant(11), _variant(12)))
    with pytest.raises(HistoricalExperimentInitializationError):
        HistoricalExperimentRunner(factory).run(request)
    assert calls == [0, 1]


def test_factory_is_not_called_for_invalid_request() -> None:
    calls = 0

    def factory(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        nonlocal calls
        calls += 1

    runner = HistoricalExperimentRunner(factory)
    with pytest.raises(InvalidHistoricalExperimentRequestError):
        runner.run(object())  # type: ignore[arg-type]
    assert calls == 0


def test_static_schedule_validation_precedes_factory_invocation() -> None:
    calls = 0

    def factory(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        nonlocal calls
        calls += 1

    request = _request()
    invalid = replace(
        request,
        rebalance_timestamps=(
            request.rebalance_timestamps[0],
            request.rebalance_timestamps[0],
        ),
    )
    with pytest.raises(
        InvalidHistoricalExperimentRequestError, match="strictly increasing"
    ):
        HistoricalExperimentRunner(factory).run(invalid)
    assert calls == 0
