"""Synthetic contract coverage for filtered-trend comparison v2 replay."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_FLOOR, Context, Decimal, localcontext
from functools import lru_cache
from zoneinfo import ZoneInfo

import pytest

import trading_bot.experiments.filtered_trend_comparison_campaign_v2 as campaign
from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.filtered_trend_campaign import (
    AggregateSummary,
    AtrDescription,
    CellEvidence,
    Metrics,
    _evaluate_cell,
    regime_plan,
)
from trading_bot.experiments.filtered_trend_campaign import (
    frozen_context as v1_frozen_context,
)
from trading_bot.experiments.filtered_trend_campaign import (
    semantic_identity as v1_semantic_identity,
)
from trading_bot.experiments.filtered_trend_comparison_v2 import (
    CANDIDATES,
    Candidate,
    signal_series,
)
from trading_bot.experiments.filtered_trend_data import (
    UNIVERSE,
    MultiAssetDataset,
    ProviderProvenance,
    SymbolDataset,
)
from trading_bot.experiments.filtered_trend_strategies import StrategyConfig
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
)

_NEW_YORK = ZoneInfo("America/New_York")
_SOURCE_HEAD = "a" * 40
_SOURCE_TREE = "b" * 40
_DATASET_ID = "synthetic-dataset-identity"
_PRICE_BASIS = "ALPACA_ALL_ADJUSTED_PRICE_V1"
_PROVENANCE = [
    {
        "symbol": "SPY",
        "provider": {"provider": "synthetic-only"},
        "bar_count": 1,
        "first_bar": "2016-01-04T05:00:00+00:00",
        "last_bar": "2016-01-04T05:00:00+00:00",
    }
]
_QUALIFICATION_HIGHER_FIELDS = (
    "positive_continuous_symbols",
    "minimum_continuous_return",
    "median_continuous_return",
)
_QUALIFICATION_LOWER_FIELDS = (
    "median_turnover",
    "worst_continuous_drawdown",
)
_QUALIFICATION_FIELDS = _QUALIFICATION_HIGHER_FIELDS + _QUALIFICATION_LOWER_FIELDS
_ANNUAL_FIELDS = (
    "positive_regime_cells",
    "negative_regime_cells",
    "minimum_regime_return",
    "median_regime_return",
    "worst_regime_drawdown",
    "median_regime_drawdown",
)
_QUALIFICATION_CAMPAIGN_ID = campaign.semantic_identity(
    "campaign", ("synthetic-selection-fixture", 1)
)


def _aggregate() -> AggregateSummary:
    return AggregateSummary(
        positive_regime_cells=20,
        negative_regime_cells=10,
        minimum_regime_return=Decimal("-0.25"),
        median_regime_return=Decimal("0.02"),
        worst_regime_drawdown=Decimal("0.40"),
        median_regime_drawdown=Decimal("0.15"),
        median_turnover=Decimal("1.20"),
        positive_continuous_symbols=5,
        minimum_continuous_return=Decimal("-0.20"),
        median_continuous_return=Decimal("0.05"),
        worst_continuous_drawdown=Decimal("0.42"),
    )


def _candidate_summary(
    candidate: Candidate,
    *,
    base: AggregateSummary | None = None,
    stress: AggregateSummary | None = None,
    status: campaign.CandidateEvidenceStatus = (
        campaign.CandidateEvidenceStatus.COMPLETE
    ),
    failure_code: str | None = None,
) -> campaign.ComparisonSummary:
    if status is campaign.CandidateEvidenceStatus.FAILED_INCOMPLETE:
        base = stress = None
        failure_code = failure_code or campaign.CANDIDATE_EVALUATION_INCOMPLETE
    return campaign.ComparisonSummary(
        candidate,
        campaign.candidate_identity(_QUALIFICATION_CAMPAIGN_ID, candidate),
        base
        if base is not None
        else _aggregate()
        if status is campaign.CandidateEvidenceStatus.COMPLETE
        else None,
        stress
        if stress is not None
        else _aggregate()
        if status is campaign.CandidateEvidenceStatus.COMPLETE
        else None,
        status,
        failure_code,
    )


def _summary_set(
    sma: campaign.ComparisonSummary | None = None,
    momentum: campaign.ComparisonSummary | None = None,
) -> tuple[campaign.ComparisonSummary, ...]:
    control = _candidate_summary(Candidate.BASE_MA35_50_V1)
    return (
        control,
        sma or _candidate_summary(Candidate.PRICE_SMA200_V1),
        momentum or _candidate_summary(Candidate.PRICE_MOM_252_V1),
    )


def _worse(summary: AggregateSummary, field: str) -> AggregateSummary:
    value = getattr(summary, field)
    return replace(
        summary,
        **{
            field: value - (1 if type(value) is int else Decimal("0.01"))
            if field in _QUALIFICATION_HIGHER_FIELDS
            else value + (1 if type(value) is int else Decimal("0.01"))
        },
    )


def _better(summary: AggregateSummary, field: str) -> AggregateSummary:
    value = getattr(summary, field)
    return replace(
        summary,
        **{
            field: value + (1 if type(value) is int else Decimal("0.01"))
            if field in _QUALIFICATION_HIGHER_FIELDS
            else value - (1 if type(value) is int else Decimal("0.01"))
        },
    )


def test_frozen_context_changes_only_the_v2_declared_fields() -> None:
    old = v1_frozen_context(
        _SOURCE_HEAD, _SOURCE_TREE, _DATASET_ID, _PRICE_BASIS, _PROVENANCE
    )
    current = campaign.frozen_context(
        _SOURCE_HEAD, _SOURCE_TREE, _DATASET_ID, _PRICE_BASIS, _PROVENANCE
    )
    changed = {
        "schema",
        "grid",
        "qualification_policy",
        "shortlist_policy",
        "neighbor_policy",
        "prior_configurations",
        "comparison_configurations",
        "prior_campaign_id",
        "reused_history",
    }

    assert set(current) == set(old) | (changed - set(old))
    assert current["schema"] == "filtered-trend-comparison-campaign/v2"
    assert current["grid"] == [candidate.value for candidate in CANDIDATES]
    assert current["qualification_policy"] == "comparison-v2/qualification-v1"
    assert current["shortlist_policy"] == "qualified-metric-order-v2/v1"
    assert current["neighbor_policy"] is None
    assert current["prior_configurations"] == 30
    assert current["comparison_configurations"] == 3
    assert current["prior_campaign_id"] == "48ae05d5-ede1-5461-9da9-b5d7744cefad"
    assert current["reused_history"] is True
    assert all(
        current[key] == value for key, value in old.items() if key not in changed
    )


def test_v2_identity_uses_v1_typed_framing_with_distinct_kind_prefix() -> None:
    material = ("campaign", ("same", 7, Decimal("1.25")))

    assert campaign.semantic_identity("test", material) == v1_semantic_identity(
        "comparison-v2/test", material
    )
    assert campaign.semantic_identity("test", material) != v1_semantic_identity(
        "test", material
    )
    campaign_id = campaign.semantic_identity("campaign", material)
    assert campaign.campaign_identity({"x": [1, "2"]}) == campaign.semantic_identity(
        "campaign", {"x": [1, "2"]}
    )
    assert campaign.candidate_identity(
        campaign_id, Candidate.PRICE_SMA200_V1
    ) == campaign.semantic_identity(
        "candidate", (campaign_id, Candidate.PRICE_SMA200_V1.value)
    )
    with pytest.raises(ValueError, match="canonical UUID5"):
        campaign.candidate_identity(campaign_id.upper(), Candidate.PRICE_SMA200_V1)


@pytest.mark.parametrize("field", _QUALIFICATION_FIELDS)
def test_each_metric_can_supply_a_strict_stress_improvement(field: str) -> None:
    baseline = _aggregate()
    control = _candidate_summary(Candidate.BASE_MA35_50_V1)
    challenger = _candidate_summary(
        Candidate.PRICE_SMA200_V1,
        base=baseline,
        stress=_better(baseline, field),
    )

    assert campaign.qualifies_candidate(challenger, control)
    assert (
        campaign.select_candidate(_summary_set(sma=challenger))
        == Candidate.PRICE_SMA200_V1.value
    )


@pytest.mark.parametrize("field", _QUALIFICATION_FIELDS)
@pytest.mark.parametrize("scope", ("base", "stress"))
def test_any_worse_field_blocks_qualification_in_either_context(
    field: str, scope: str
) -> None:
    baseline = _aggregate()
    other_stress_gain = next(
        name for name in _QUALIFICATION_HIGHER_FIELDS if name != field
    )
    stress = _better(baseline, other_stress_gain)
    base = baseline
    if scope == "base":
        base = _worse(base, field)
    else:
        stress = _worse(stress, field)
    challenger = _candidate_summary(
        Candidate.PRICE_SMA200_V1,
        base=base,
        stress=stress,
    )

    assert not campaign.qualifies_candidate(
        challenger, _candidate_summary(Candidate.BASE_MA35_50_V1)
    )


@pytest.mark.parametrize("field", _ANNUAL_FIELDS)
@pytest.mark.parametrize("scope", ("base", "stress"))
def test_annual_regime_metric_does_not_participate_in_qualification(
    field: str, scope: str
) -> None:
    baseline = _aggregate()
    better = _better(baseline, "median_continuous_return")
    base = better
    stress = better
    if scope == "base":
        base = _worse(base, field)
    else:
        stress = _worse(stress, field)

    challenger = _candidate_summary(
        Candidate.PRICE_SMA200_V1,
        base=base,
        stress=stress,
    )
    assert campaign.qualifies_candidate(
        challenger, _candidate_summary(Candidate.BASE_MA35_50_V1)
    )


def test_policy_requires_stress_improvement_and_uses_frozen_metric_tie_break() -> None:
    baseline = _aggregate()
    base_only = _candidate_summary(
        Candidate.PRICE_SMA200_V1,
        base=_better(baseline, "positive_continuous_symbols"),
        stress=baseline,
    )
    assert not campaign.qualifies_candidate(
        base_only, _candidate_summary(Candidate.BASE_MA35_50_V1)
    )
    assert campaign.select_candidate(_summary_set(sma=base_only)) == "NONE_QUALIFIES"

    sma = _candidate_summary(
        Candidate.PRICE_SMA200_V1,
        stress=_better(baseline, "minimum_continuous_return"),
    )
    momentum = _candidate_summary(
        Candidate.PRICE_MOM_252_V1,
        stress=_better(
            _better(baseline, "minimum_continuous_return"),
            "positive_continuous_symbols",
        ),
    )
    assert campaign.select_candidate(_summary_set(sma=sma, momentum=momentum)) == (
        Candidate.PRICE_MOM_252_V1.value
    )


def test_failed_challenger_is_visible_ineligible_and_cannot_win() -> None:
    failed = _candidate_summary(
        Candidate.PRICE_SMA200_V1,
        status=campaign.CandidateEvidenceStatus.FAILED_INCOMPLETE,
    )
    assert not campaign.qualifies_candidate(
        failed, _candidate_summary(Candidate.BASE_MA35_50_V1)
    )
    assert campaign.select_candidate(_summary_set(sma=failed)) == "NONE_QUALIFIES"


def test_equal_candidates_emit_none_qualifies_and_inputs_fail_closed() -> None:
    assert campaign.select_candidate(_summary_set()) == "NONE_QUALIFIES"
    complete = _summary_set()
    with pytest.raises(ValueError, match="order"):
        campaign.select_candidate((complete[0], complete[2], complete[1]))
    with pytest.raises(ValueError, match="three ordered"):
        campaign.select_candidate(complete[:2])
    with pytest.raises(ValueError, match="distinct"):
        duplicate = replace(complete[2], candidate_id=complete[1].candidate_id)
        campaign.select_candidate((complete[0], complete[1], duplicate))


@pytest.mark.parametrize(
    "invalid",
    (
        {"positive_regime_cells": 41},
        {"positive_regime_cells": 30, "negative_regime_cells": 20},
        {"positive_continuous_symbols": 9},
        {"worst_regime_drawdown": Decimal("1.01")},
        {"median_regime_drawdown": Decimal("-0.01")},
        {"median_turnover": Decimal("-0.01")},
        {"minimum_continuous_return": Decimal("-1.01")},
        {"median_regime_return": Decimal("NaN")},
    ),
)
def test_impossible_or_nonfinite_aggregate_metrics_are_rejected(
    invalid: dict[str, int | Decimal],
) -> None:
    malformed = replace(_aggregate(), **invalid)
    challenger = _candidate_summary(Candidate.PRICE_SMA200_V1, stress=malformed)

    with pytest.raises(ValueError):
        campaign.qualifies_candidate(
            challenger, _candidate_summary(Candidate.BASE_MA35_50_V1)
        )


@lru_cache(maxsize=1)
def _synthetic_dataset() -> MultiAssetDataset:
    """Build accepted-shape fake bars from the packaged session calendar."""

    sessions = tuple(
        item
        for item in published_historical_session_authority().sessions
        if date(2016, 1, 1) <= item < date(2024, 1, 1)
    )
    provenance = ProviderProvenance()
    datasets = []
    for symbol_index, symbol in enumerate(UNIVERSE):
        instrument = Symbol(symbol)
        bars = []
        for ordinal, session in enumerate(sessions):
            close = Decimal(100 + symbol_index) + Decimal(ordinal) / Decimal(1000)
            timestamp = datetime.combine(session, time.min, _NEW_YORK).astimezone(UTC)
            bars.append(
                Bar(
                    instrument,
                    timestamp,
                    close,
                    close + Decimal("1"),
                    close - Decimal("1"),
                    close,
                    1000 + ordinal,
                )
            )
        datasets.append(SymbolDataset(symbol, tuple(bars), provenance))
    return MultiAssetDataset(tuple(datasets))


def _fake_cell(
    bars: tuple[Bar, ...],
    config: StrategyConfig,
    regime,
    candidate_id: str,
    *,
    prepared_states: tuple[str, ...],
) -> CellEvidence:
    assert config == StrategyConfig("BASE_MA", 35, 50, "none")
    assert len(prepared_states) == len(bars)
    indices = tuple(
        index
        for index, bar in enumerate(bars)
        if regime.start <= bar.timestamp.astimezone(_NEW_YORK).date() < regime.end
    )
    assert indices
    assert all(prepared_states[index - 1] is not None for index in indices)
    metrics = Metrics(
        total_return=Decimal("0.01"),
        maximum_drawdown=Decimal("0.10"),
        final_equity=Decimal("101000"),
        realized_profit_loss=Decimal("0"),
        fill_count=0,
        closed_trades=0,
        turnover=Decimal("0.10"),
        time_invested=Decimal("0"),
        equity_trace_identity=v1_semantic_identity(
            "synthetic-equity", (candidate_id, str(bars[0].symbol), regime.label)
        ),
        fills=(),
    )
    return CellEvidence(
        candidate_id=candidate_id,
        symbol=str(bars[0].symbol),
        regime=regime.label,
        result_id=v1_semantic_identity(
            "synthetic-cell", (candidate_id, str(bars[0].symbol), regime.label)
        ),
        base=metrics,
        stress=metrics,
        buy_and_hold=metrics,
        buy_and_hold_stress=metrics,
        atr=AtrDescription(
            1,
            Decimal("1"),
            Decimal("1"),
            Decimal("1"),
            Decimal("0.01"),
        ),
        session_count=len(indices),
        first_session=bars[indices[0]].timestamp.isoformat(),
        last_session=bars[indices[-1]].timestamp.isoformat(),
    )


def test_run_campaign_emits_exact_144_cell_topology_without_real_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = _synthetic_dataset()
    calls: list[tuple[str, str, str]] = []

    def fake_evaluate(
        bars: tuple[Bar, ...],
        config: StrategyConfig,
        regime,
        candidate_id: str,
        *,
        prepared_states: tuple[str, ...],
    ) -> CellEvidence:
        cell = _fake_cell(
            bars, config, regime, candidate_id, prepared_states=prepared_states
        )
        calls.append((candidate_id, cell.symbol, cell.regime))
        return cell

    monkeypatch.setattr(campaign, "_evaluate_cell", fake_evaluate)
    with localcontext(Context(prec=3)):
        context, cells, summaries = campaign.run_campaign(
            dataset, _SOURCE_HEAD, _SOURCE_TREE
        )

    expected_pairs = tuple(
        (symbol, regime.label) for symbol in UNIVERSE for regime in regime_plan()
    )
    expected_campaign_id = campaign.campaign_identity(context)
    expected_ids = tuple(
        campaign.candidate_identity(expected_campaign_id, candidate)
        for candidate in CANDIDATES
    )

    assert context["dataset_id"] == dataset.identity
    assert context["price_basis"] == dataset.price_basis
    assert tuple(item.candidate for item in summaries) == CANDIDATES
    assert tuple(item.candidate_id for item in summaries) == expected_ids
    assert len(calls) == len(cells) == 3 * len(expected_pairs) == 144
    assert tuple((cell.symbol, cell.regime) for cell in cells[:48]) == expected_pairs
    assert tuple(cell.candidate_id for cell in cells[:48]) == (expected_ids[0],) * 48
    assert tuple(cell.candidate_id for cell in cells[48:96]) == (expected_ids[1],) * 48
    assert tuple(cell.candidate_id for cell in cells[96:]) == (expected_ids[2],) * 48
    assert campaign.select_candidate(summaries) == "NONE_QUALIFIES"


def test_run_campaign_preserves_one_failed_challenger_without_cells_or_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = _synthetic_dataset()
    original_evaluate_candidate = campaign._evaluate_candidate

    def fail_sma(
        candidate_dataset: MultiAssetDataset,
        candidate: Candidate,
        candidate_id: str,
        regimes,
    ):
        if candidate is Candidate.PRICE_SMA200_V1:
            raise campaign.CandidateEvaluationIncomplete
        return original_evaluate_candidate(
            candidate_dataset, candidate, candidate_id, regimes
        )

    monkeypatch.setattr(campaign, "_evaluate_candidate", fail_sma)
    context, cells, summaries = campaign.run_campaign(
        dataset, _SOURCE_HEAD, _SOURCE_TREE
    )

    assert context["comparison_configurations"] == 3
    assert len(cells) == 96
    assert tuple(item.candidate for item in summaries) == CANDIDATES
    failed = summaries[1]
    assert failed.status is campaign.CandidateEvidenceStatus.FAILED_INCOMPLETE
    assert failed.base is None
    assert failed.stress is None
    assert failed.failure_code == campaign.CANDIDATE_EVALUATION_INCOMPLETE
    assert all(cell.candidate_id != failed.candidate_id for cell in cells)
    assert campaign.select_candidate(summaries) == "NONE_QUALIFIES"


def test_run_campaign_rejects_execution_before_candidate_warmup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = _synthetic_dataset()
    evaluate_called = False

    monkeypatch.setattr(campaign, "_regime_indices", lambda bars, regime: (1,))

    def should_not_evaluate(*args, **kwargs):
        nonlocal evaluate_called
        evaluate_called = True
        raise AssertionError("campaign must validate warmup before cell evaluation")

    monkeypatch.setattr(campaign, "_evaluate_cell", should_not_evaluate)
    with pytest.raises(campaign.CandidateEvaluationIncomplete):
        campaign.run_campaign(dataset, _SOURCE_HEAD, _SOURCE_TREE)
    assert not evaluate_called


def _cell_bars() -> tuple[Bar, ...]:
    result = []
    start = date(2017, 1, 1)
    end = date(2021, 1, 1)
    current = start
    index = 0
    while current < end:
        close = Decimal("100") + Decimal(index) / Decimal(1000)
        timestamp = datetime.combine(current, time(16), UTC)
        result.append(
            Bar(
                Symbol("SPY"),
                timestamp,
                close,
                close + Decimal("1"),
                close - Decimal("1"),
                close,
                1000,
            )
        )
        current += timedelta(days=1)
        index += 1
    return tuple(result)


def test_v2_prepared_states_keep_next_open_costs_rounding_and_regime_reset() -> None:
    bars = _cell_bars()
    candidate = Candidate.PRICE_MOM_252_V1
    campaign_id = campaign.semantic_identity("campaign", "synthetic-cell-campaign")
    candidate_id = campaign.candidate_identity(campaign_id, candidate)
    states = signal_series(candidate, bars)
    first_regime, second_regime = regime_plan()[:2]

    first = _evaluate_cell(
        bars,
        StrategyConfig("BASE_MA", 35, 50, "none"),
        first_regime,
        candidate_id,
        prepared_states=states,
    )
    second = _evaluate_cell(
        bars,
        StrategyConfig("BASE_MA", 35, 50, "none"),
        second_regime,
        candidate_id,
        prepared_states=states,
    )
    first_fill = first.base.fills[0]
    first_index = next(
        index
        for index, bar in enumerate(bars)
        if bar.timestamp.astimezone(_NEW_YORK).date() == first_regime.start
    )
    execution_bar = bars[first_index]

    with localcontext(Context(prec=50)):
        expected_price = execution_bar.open * Decimal("1.0005")
        expected_quantity = (
            (Decimal("100000") * Decimal("0.95") - Decimal("1")) / expected_price
        ).to_integral_value(rounding=ROUND_FLOOR)
        expected_cash = (
            Decimal("100000")
            - second.buy_and_hold.fills[0].quantity * second.buy_and_hold.fills[0].price
            - second.buy_and_hold.fills[0].commission
        )

    assert first_fill.session == execution_bar.timestamp.isoformat()
    assert first_fill.information_through == bars[first_index - 1].timestamp.isoformat()
    assert first_fill.execution_open == execution_bar.open
    assert first_fill.price == expected_price
    assert first_fill.quantity == expected_quantity
    assert first_fill.commission == Decimal("1")
    assert all(
        fill.information_through < fill.session
        for fill in first.base.fills
        if fill.information_through is not None
    )
    assert first.buy_and_hold.fills[0].session.startswith("2019-")
    assert second.buy_and_hold.fills[0].session.startswith("2020-")
    assert second.buy_and_hold.fills[0].cash_after == expected_cash


def test_execution_session_high_low_close_cannot_change_that_open_fill() -> None:
    bars = _cell_bars()
    candidate = Candidate.PRICE_SMA200_V1
    campaign_id = campaign.semantic_identity("campaign", "synthetic-no-lookahead")
    candidate_id = campaign.candidate_identity(campaign_id, candidate)
    states = signal_series(candidate, bars)
    regime = regime_plan()[0]
    execution_index = next(
        index
        for index, bar in enumerate(bars)
        if bar.timestamp.astimezone(_NEW_YORK).date() == regime.start
    )
    original = _evaluate_cell(
        bars,
        StrategyConfig("BASE_MA", 35, 50, "none"),
        regime,
        candidate_id,
        prepared_states=states,
    )
    chosen = bars[execution_index]
    changed = (
        bars[:execution_index]
        + (
            replace(
                chosen,
                high=chosen.open + Decimal("5000"),
                low=chosen.open - Decimal("1"),
                close=chosen.open + Decimal("4000"),
            ),
        )
        + bars[execution_index + 1 :]
    )
    changed_states = signal_series(candidate, changed)
    modified = _evaluate_cell(
        changed,
        StrategyConfig("BASE_MA", 35, 50, "none"),
        regime,
        candidate_id,
        prepared_states=changed_states,
    )

    assert original.base.fills[0] == modified.base.fills[0]
