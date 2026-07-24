from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest
from tests.experiments.test_historical import (
    START,
    _Factory,
    _history,
    _initial,
    _variant,
)

from trading_bot.experiments import (
    HistoricalExperimentRankingCriterion,
    HistoricalExperimentRankingDirection,
    HistoricalExperimentRankingMetric,
    HistoricalExperimentRankingPolicy,
    HistoricalExperimentTieBreaker,
    HistoricalExperimentWalkForwardDataError,
    HistoricalExperimentWalkForwardFold,
    HistoricalExperimentWalkForwardRequest,
    HistoricalExperimentWalkForwardRunner,
    HistoricalExperimentWalkForwardSelectionPolicy,
    InvalidHistoricalExperimentWalkForwardRequestError,
)
from trading_bot.portfolio import MetadataEntry


def _policy() -> HistoricalExperimentWalkForwardSelectionPolicy:
    ranking = HistoricalExperimentRankingPolicy(
        UUID(int=80),
        (
            HistoricalExperimentRankingCriterion(
                HistoricalExperimentRankingMetric.FINAL_EQUITY,
                HistoricalExperimentRankingDirection.DESCENDING,
            ),
        ),
        HistoricalExperimentTieBreaker.CALLER_ORDER,
    )
    return HistoricalExperimentWalkForwardSelectionPolicy(UUID(int=81), ranking)


def _fold(
    identifier: int,
    training_start: datetime,
    training_end: datetime,
    test_end: datetime,
    training_rebalance: datetime,
    test_rebalance: datetime,
) -> HistoricalExperimentWalkForwardFold:
    return HistoricalExperimentWalkForwardFold(
        UUID(int=identifier),
        training_start,
        training_end,
        training_end,
        test_end,
        (training_rebalance,),
        (test_rebalance,),
    )


def _request() -> HistoricalExperimentWalkForwardRequest:
    history = _history(
        tuple((str(100 + index), str(90 + index)) for index in range(12))
    )
    folds = (
        _fold(
            91,
            START,
            START + timedelta(days=4),
            START + timedelta(days=8),
            START + timedelta(days=2),
            START + timedelta(days=6),
        ),
        _fold(
            92,
            START,
            START + timedelta(days=8),
            START + timedelta(days=12),
            START + timedelta(days=6),
            START + timedelta(days=10),
        ),
    )
    return HistoricalExperimentWalkForwardRequest(
        UUID(int=90),
        history,
        folds,
        _initial(),
        (_variant(93), _variant(94, risk_aversion="2")),
        _policy(),
        (MetadataEntry("purpose", "test"),),
    )


def test_walk_forward_runs_training_selection_and_independent_test_folds() -> None:
    factory = _Factory()
    request = _request()

    result = HistoricalExperimentWalkForwardRunner(factory).run(request)

    assert len(result.folds) == 2
    assert len(factory.calls) == 6
    for fold_result in result.folds:
        assert len(fold_result.training_report.variants) == 2
        assert fold_result.selection.selected_rank == 1
        assert fold_result.training_report.ranking is not None
        assert len(fold_result.test_report.variants) == 1
        assert fold_result.test_report.ranking is None
        assert (
            fold_result.test_report.variants[0].variant_id
            == fold_result.selection.selected_variant_id
        )
        assert (
            fold_result.training_historical_fingerprint
            != fold_result.test_historical_fingerprint
        )

    repeated = HistoricalExperimentWalkForwardRunner(_Factory()).run(request)
    assert repeated == result


def test_fold_normalizes_aware_datetimes_and_rejects_naive_values() -> None:
    offset = timezone(timedelta(hours=-5))
    fold = _fold(
        1,
        START.astimezone(offset),
        (START + timedelta(days=3)).astimezone(offset),
        (START + timedelta(days=6)).astimezone(offset),
        (START + timedelta(days=2)).astimezone(offset),
        (START + timedelta(days=5)).astimezone(offset),
    )
    assert fold.training_start.tzinfo is UTC
    assert fold.training_rebalance_timestamps[0].tzinfo is UTC

    with pytest.raises(InvalidHistoricalExperimentWalkForwardRequestError):
        replace(fold, training_start=datetime(2026, 1, 1))


@pytest.mark.parametrize(
    "replacement",
    (
        {"test_start": START + timedelta(days=5)},
        {"training_rebalance_timestamps": ()},
        {"test_rebalance_timestamps": (START + timedelta(days=3),)},
    ),
)
def test_fold_rejects_nonadjacent_empty_or_out_of_interval_input(replacement) -> None:
    fold = _request().folds[0]
    with pytest.raises(InvalidHistoricalExperimentWalkForwardRequestError):
        replace(fold, **replacement)


def test_all_slices_are_prevalidated_before_any_experiment_executes() -> None:
    request = _request()
    invalid_fold = replace(
        request.folds[1],
        test_rebalance_timestamps=(START + timedelta(days=9),),
    )
    request = replace(request, folds=(request.folds[0], invalid_fold))
    factory = _Factory()

    with pytest.raises(HistoricalExperimentWalkForwardDataError):
        HistoricalExperimentWalkForwardRunner(factory).run(request)

    assert factory.calls == []


def test_request_rejects_duplicate_folds_variants_and_reserved_metadata() -> None:
    request = _request()
    with pytest.raises(InvalidHistoricalExperimentWalkForwardRequestError):
        replace(request, folds=(request.folds[0], request.folds[0]))
    with pytest.raises(InvalidHistoricalExperimentWalkForwardRequestError):
        replace(request, variants=(request.variants[0], request.variants[0]))
    with pytest.raises(InvalidHistoricalExperimentWalkForwardRequestError):
        replace(
            request,
            metadata=(MetadataEntry("historical_experiment_walk_forward_bad", "x"),),
        )
