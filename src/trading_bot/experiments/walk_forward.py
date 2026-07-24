"""Deterministic, explicit walk-forward historical experiment evaluation."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid5

from trading_bot.domain._validation import normalize_utc
from trading_bot.experiments.comparison import (
    HistoricalExperimentComparator,
    HistoricalExperimentRankingPolicy,
)
from trading_bot.experiments.exceptions import (
    HistoricalExperimentComparisonError,
    HistoricalExperimentError,
    HistoricalExperimentReportError,
    HistoricalExperimentWalkForwardDataError,
    HistoricalExperimentWalkForwardFoldError,
    HistoricalExperimentWalkForwardReconciliationError,
    HistoricalExperimentWalkForwardSelectionError,
    InconsistentHistoricalExperimentWalkForwardResultError,
    InvalidHistoricalExperimentWalkForwardRequestError,
)
from trading_bot.experiments.historical import (
    HistoricalExperimentInitialState,
    HistoricalExperimentRequest,
    HistoricalExperimentRunner,
    HistoricalExperimentSimulatorFactory,
    HistoricalExperimentVariant,
)
from trading_bot.experiments.report import (
    HistoricalExperimentReport,
    HistoricalExperimentReportBuilder,
)
from trading_bot.market_data import (
    MultiSymbolHistoricalDataRequest,
    MultiSymbolHistoricalDataResult,
    canonical_multi_symbol_historical_material,
)
from trading_bot.portfolio import MetadataEntry

_VERSION = "historical-experiment-walk-forward-v1"
_NAMESPACE = UUID("f519e0e6-2920-5a74-b004-c4898a7d08f3")
_RESERVED_PREFIX = "historical_experiment_walk_forward_"


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardFold:
    fold_id: UUID
    training_start: datetime
    training_end: datetime
    test_start: datetime
    test_end: datetime
    training_rebalance_timestamps: tuple[datetime, ...]
    test_rebalance_timestamps: tuple[datetime, ...]
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentWalkForwardRequestError
        if type(self.fold_id) is not UUID:
            raise error("fold_id must be a UUID")
        try:
            bounds = tuple(
                normalize_utc(getattr(self, name), name)
                for name in ("training_start", "training_end", "test_start", "test_end")
            )
            training = tuple(
                normalize_utc(value, f"training_rebalance_timestamps[{index}]")
                for index, value in enumerate(self.training_rebalance_timestamps)
            )
            test = tuple(
                normalize_utc(value, f"test_rebalance_timestamps[{index}]")
                for index, value in enumerate(self.test_rebalance_timestamps)
            )
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        training_start, training_end, test_start, test_end = bounds
        if not training_start < training_end:
            raise error("training_start must be earlier than training_end")
        if training_end != test_start:
            raise error("training_end must equal test_start")
        if not test_start < test_end:
            raise error("test_start must be earlier than test_end")
        _validate_schedule(training, training_start, training_end, "training", error)
        _validate_schedule(test, test_start, test_end, "test", error)
        metadata = _metadata(self.metadata, error)
        for name, value in zip(
            ("training_start", "training_end", "test_start", "test_end"),
            bounds,
            strict=True,
        ):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "training_rebalance_timestamps", training)
        object.__setattr__(self, "test_rebalance_timestamps", test)
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardSelectionPolicy:
    policy_id: UUID
    ranking_policy: HistoricalExperimentRankingPolicy
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentWalkForwardRequestError
        if type(self.policy_id) is not UUID:
            raise error("selection policy_id must be a UUID")
        if type(self.ranking_policy) is not HistoricalExperimentRankingPolicy:
            raise error(
                "ranking_policy must be exactly HistoricalExperimentRankingPolicy"
            )
        try:
            self.ranking_policy.__post_init__()
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        object.__setattr__(self, "metadata", _metadata(self.metadata, error))


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardRequest:
    request_id: UUID
    historical_data: MultiSymbolHistoricalDataResult
    folds: tuple[HistoricalExperimentWalkForwardFold, ...]
    initial_state: HistoricalExperimentInitialState
    variants: tuple[HistoricalExperimentVariant, ...]
    selection_policy: HistoricalExperimentWalkForwardSelectionPolicy
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentWalkForwardRequestError
        if type(self.request_id) is not UUID:
            raise error("request_id must be a UUID")
        if type(self.historical_data) is not MultiSymbolHistoricalDataResult:
            raise error(
                "historical_data must be exactly MultiSymbolHistoricalDataResult"
            )
        if type(self.initial_state) is not HistoricalExperimentInitialState:
            raise error("initial_state has an invalid type")
        if (
            type(self.selection_policy)
            is not HistoricalExperimentWalkForwardSelectionPolicy
        ):
            raise error("selection_policy has an invalid type")
        try:
            folds = tuple(self.folds)
            variants = tuple(self.variants)
            self.initial_state.__post_init__()
            self.selection_policy.__post_init__()
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        if not folds or not all(
            type(item) is HistoricalExperimentWalkForwardFold for item in folds
        ):
            raise error("folds must contain at least one exact walk-forward fold")
        if not variants or not all(
            type(item) is HistoricalExperimentVariant for item in variants
        ):
            raise error("variants must contain at least one experiment variant")
        for fold in folds:
            fold.__post_init__()
        for variant in variants:
            variant.__post_init__()
        if len({item.fold_id for item in folds}) != len(folds):
            raise error("fold IDs must be unique")
        if len({item.variant_id for item in variants}) != len(variants):
            raise error("variant IDs must be unique")
        if len({item.name.casefold() for item in variants}) != len(variants):
            raise error("variant names must be unique after normalization")
        _validate_fold_order(folds, error)
        object.__setattr__(self, "folds", folds)
        object.__setattr__(self, "variants", variants)
        object.__setattr__(self, "metadata", _metadata(self.metadata, error))


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardSelection:
    training_report_id: UUID
    training_experiment_result_id: UUID
    training_comparison_result_id: UUID
    ranking_policy_id: UUID
    selected_rank: int
    selected_caller_ordinal: int
    selected_variant_id: UUID
    selected_training_run_id: UUID

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardResultError
        for name in (
            "training_report_id",
            "training_experiment_result_id",
            "training_comparison_result_id",
            "ranking_policy_id",
            "selected_variant_id",
            "selected_training_run_id",
        ):
            if type(getattr(self, name)) is not UUID:
                raise error(f"{name} must be a UUID")
        if self.selected_rank != 1:
            raise error("selected_rank must be exactly one")
        if (
            type(self.selected_caller_ordinal) is not int
            or self.selected_caller_ordinal < 0
        ):
            raise error("selected_caller_ordinal must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardFoldResult:
    ordinal: int
    fold: HistoricalExperimentWalkForwardFold
    training_request_id: UUID
    training_historical_fingerprint: UUID
    training_report: HistoricalExperimentReport
    selection: HistoricalExperimentWalkForwardSelection
    test_request_id: UUID
    test_historical_fingerprint: UUID
    test_report: HistoricalExperimentReport
    test_run_id: UUID
    test_rolling_result_id: UUID

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardResultError
        if type(self.ordinal) is not int or self.ordinal < 0:
            raise error("fold result ordinal must be nonnegative")
        if type(self.fold) is not HistoricalExperimentWalkForwardFold:
            raise error("fold has an invalid type")
        for name in (
            "training_request_id",
            "training_historical_fingerprint",
            "test_request_id",
            "test_historical_fingerprint",
            "test_run_id",
            "test_rolling_result_id",
        ):
            if type(getattr(self, name)) is not UUID:
                raise error(f"{name} must be a UUID")
        if (
            type(self.training_report) is not HistoricalExperimentReport
            or type(self.test_report) is not HistoricalExperimentReport
        ):
            raise error("fold reports have invalid types")
        if type(self.selection) is not HistoricalExperimentWalkForwardSelection:
            raise error("selection has an invalid type")
        self.selection.__post_init__()
        if self.training_report.experiment_request_id != self.training_request_id:
            raise error("training report request linkage is inconsistent")
        if (
            self.training_report.historical_fingerprint
            != self.training_historical_fingerprint
        ):
            raise error("training historical linkage is inconsistent")
        if self.selection.training_report_id != self.training_report.report_id:
            raise error("selection training report linkage is inconsistent")
        if (
            self.selection.training_experiment_result_id
            != self.training_report.experiment_result_id
        ):
            raise error("selection training result linkage is inconsistent")
        ranking = self.training_report.ranking
        if (
            ranking is None
            or ranking.comparison_result_id
            != self.selection.training_comparison_result_id
        ):
            raise error("selection comparison linkage is inconsistent")
        if ranking.policy_id != self.selection.ranking_policy_id:
            raise error("selection ranking policy linkage is inconsistent")
        selected = tuple(row for row in self.training_report.variants if row.rank == 1)
        if len(selected) != 1:
            raise error("training report must contain exactly one rank-one row")
        row = selected[0]
        if (
            row.caller_ordinal != self.selection.selected_caller_ordinal
            or row.variant_id != self.selection.selected_variant_id
            or row.experiment_run_id != self.selection.selected_training_run_id
        ):
            raise error("selection does not match the rank-one training row")
        if self.test_report.experiment_request_id != self.test_request_id:
            raise error("test report request linkage is inconsistent")
        if self.test_report.historical_fingerprint != self.test_historical_fingerprint:
            raise error("test historical linkage is inconsistent")
        if self.test_report.ranking is not None or len(self.test_report.variants) != 1:
            raise error("test report must be unranked and contain one row")
        test_row = self.test_report.variants[0]
        if (
            test_row.variant_id != self.selection.selected_variant_id
            or test_row.experiment_run_id != self.test_run_id
            or test_row.rolling_result_id != self.test_rolling_result_id
        ):
            raise error("test report provenance is inconsistent")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardResult:
    result_id: UUID
    request_id: UUID
    source_historical_fingerprint: UUID
    selection_policy: HistoricalExperimentWalkForwardSelectionPolicy
    folds: tuple[HistoricalExperimentWalkForwardFoldResult, ...]
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardResultError
        if (
            type(self.result_id) is not UUID
            or type(self.request_id) is not UUID
            or type(self.source_historical_fingerprint) is not UUID
        ):
            raise error("walk-forward result identities must be UUIDs")
        if (
            type(self.selection_policy)
            is not HistoricalExperimentWalkForwardSelectionPolicy
        ):
            raise error("selection_policy has an invalid type")
        try:
            folds = tuple(self.folds)
        except TypeError as caught:
            raise error("folds must be iterable") from caught
        if not folds or not all(
            type(item) is HistoricalExperimentWalkForwardFoldResult for item in folds
        ):
            raise error("folds must contain fold results")
        if tuple(item.ordinal for item in folds) != tuple(range(len(folds))):
            raise error("fold result ordinals must be sequential")
        if len({item.fold.fold_id for item in folds}) != len(folds):
            raise error("fold result IDs must be unique")
        if len({item.training_request_id for item in folds}) != len(folds) or len(
            {item.test_request_id for item in folds}
        ) != len(folds):
            raise error("child request IDs must be unique")
        metadata = _metadata(self.metadata, error)
        expected = _result_id(
            self.request_id,
            self.source_historical_fingerprint,
            self.selection_policy,
            folds,
            metadata,
        )
        if self.result_id != expected:
            raise error("result_id is inconsistent")
        object.__setattr__(self, "folds", folds)
        object.__setattr__(self, "metadata", metadata)


class HistoricalExperimentWalkForwardRunner:
    def __init__(self, simulator_factory: HistoricalExperimentSimulatorFactory) -> None:
        if not callable(simulator_factory):
            raise TypeError("simulator_factory must be callable")
        self._simulator_factory = simulator_factory

    def run(
        self, request: HistoricalExperimentWalkForwardRequest
    ) -> HistoricalExperimentWalkForwardResult:
        if type(request) is not HistoricalExperimentWalkForwardRequest:
            raise InvalidHistoricalExperimentWalkForwardRequestError(
                "request must be exactly HistoricalExperimentWalkForwardRequest"
            )
        request.__post_init__()
        source_fingerprint = _historical_fingerprint(request.historical_data)
        before = _request_invariant(request)
        prepared = tuple(_prepare_fold(request, fold) for fold in request.folds)
        results = []
        for ordinal, (
            fold,
            training_data,
            test_data,
            training_id,
            test_id,
        ) in enumerate(prepared):
            training_request = HistoricalExperimentRequest(
                training_id,
                training_data,
                fold.training_rebalance_timestamps,
                request.initial_state,
                request.variants,
                (MetadataEntry("walk_forward_stage", "training"),),
            )
            training_result = self._stage(
                ordinal,
                fold,
                "TRAINING_EXPERIMENT",
                lambda training_request=training_request: HistoricalExperimentRunner(
                    self._simulator_factory
                ).run(training_request),
                (HistoricalExperimentError,),
            )
            comparison = self._stage(
                ordinal,
                fold,
                "TRAINING_RANKING",
                lambda training_result=training_result: (
                    HistoricalExperimentComparator().compare(
                        training_result, request.selection_policy.ranking_policy
                    )
                ),
                (HistoricalExperimentComparisonError,),
            )
            training_report = self._stage(
                ordinal,
                fold,
                "TRAINING_REPORT",
                lambda training_result=training_result, comparison=comparison: (
                    HistoricalExperimentReportBuilder().build(
                        training_result, comparison_result=comparison
                    )
                ),
                (HistoricalExperimentReportError,),
            )
            ranked = tuple(item for item in comparison.ranked_runs if item.rank == 1)
            if len(ranked) != 1:
                raise HistoricalExperimentWalkForwardFoldError(
                    ordinal,
                    fold.fold_id,
                    "SELECTION",
                    "training comparison did not produce exactly one rank-one run",
                    cause=HistoricalExperimentWalkForwardSelectionError(
                        "invalid rank-one selection"
                    ),
                )
            selected = ranked[0]
            test_id = _child_request_id(
                request,
                fold,
                ordinal,
                "test",
                source_fingerprint,
                selected.run.run_id,
                selected.run.variant.variant_id,
            )
            test_request = HistoricalExperimentRequest(
                test_id,
                test_data,
                fold.test_rebalance_timestamps,
                request.initial_state,
                (selected.run.variant,),
                (MetadataEntry("walk_forward_stage", "test"),),
            )
            if test_request.variants[0] is not selected.run.variant:
                raise HistoricalExperimentWalkForwardReconciliationError(
                    "selected variant object was not retained by the test request"
                )
            test_result = self._stage(
                ordinal,
                fold,
                "TEST_EXPERIMENT",
                lambda test_request=test_request: HistoricalExperimentRunner(
                    self._simulator_factory
                ).run(test_request),
                (HistoricalExperimentError,),
            )
            test_report = self._stage(
                ordinal,
                fold,
                "TEST_REPORT",
                lambda test_result=test_result: (
                    HistoricalExperimentReportBuilder().build(test_result)
                ),
                (HistoricalExperimentReportError,),
            )
            selection = HistoricalExperimentWalkForwardSelection(
                training_report.report_id,
                training_result.result_id,
                comparison.result_id,
                comparison.policy.policy_id,
                1,
                selected.caller_ordinal,
                selected.run.variant.variant_id,
                selected.run.run_id,
            )
            test_run = test_result.runs[0]
            results.append(
                HistoricalExperimentWalkForwardFoldResult(
                    ordinal,
                    fold,
                    training_id,
                    training_result.historical_fingerprint,
                    training_report,
                    selection,
                    test_id,
                    test_result.historical_fingerprint,
                    test_report,
                    test_run.run_id,
                    test_run.rolling_result.result_id,
                )
            )
        if before != _request_invariant(request):
            raise HistoricalExperimentWalkForwardReconciliationError(
                "walk-forward inputs changed during execution"
            )
        completed = tuple(results)
        result_id = _result_id(
            request.request_id,
            source_fingerprint,
            request.selection_policy,
            completed,
            request.metadata,
        )
        return HistoricalExperimentWalkForwardResult(
            result_id,
            request.request_id,
            source_fingerprint,
            request.selection_policy,
            completed,
            request.metadata,
        )

    @staticmethod
    def _stage(ordinal, fold, stage, operation, known):  # type: ignore[no-untyped-def]
        try:
            return operation()
        except known as caught:
            raise HistoricalExperimentWalkForwardFoldError(
                ordinal, fold.fold_id, stage, str(caught), cause=caught
            ) from caught


def _prepare_fold(request, fold):  # type: ignore[no-untyped-def]
    training = _slice(request.historical_data, fold.training_start, fold.training_end)
    test = _slice(request.historical_data, fold.test_start, fold.test_end)
    training_ids = {id(frame) for frame in training.frames}
    if any(id(frame) in training_ids for frame in test.frames):
        raise HistoricalExperimentWalkForwardDataError(
            "training and test slices share frames"
        )
    _validate_slice(
        training, fold.training_rebalance_timestamps, request.variants, "training"
    )
    _validate_slice(test, fold.test_rebalance_timestamps, request.variants, "test")
    source = _historical_fingerprint(request.historical_data)
    training_id = _child_request_id(
        request, fold, request.folds.index(fold), "training", source
    )
    return fold, training, test, training_id, UUID(int=0)


def _slice(source, start, end):  # type: ignore[no-untyped-def]
    frames = tuple(frame for frame in source.frames if start <= frame.timestamp < end)
    if not frames:
        raise HistoricalExperimentWalkForwardDataError("historical slice is empty")
    source_request = source.request
    sliced_request = MultiSymbolHistoricalDataRequest(
        source_request.symbols,
        start,
        end,
        source_request.timeframe,
        source_request.adjustment,
        source_request.missing_bar_policy,
    )
    try:
        return MultiSymbolHistoricalDataResult(
            sliced_request, frames, source.provider_name
        )
    except ValueError as caught:
        raise HistoricalExperimentWalkForwardDataError(str(caught)) from caught


def _validate_slice(data, schedule, variants, label):  # type: ignore[no-untyped-def]
    if not data.is_complete:
        raise HistoricalExperimentWalkForwardDataError(
            f"{label} historical data must be complete"
        )
    indices = {timestamp: index for index, timestamp in enumerate(data.timestamps)}
    for timestamp in schedule:
        if timestamp not in indices:
            raise HistoricalExperimentWalkForwardDataError(
                f"{label} rebalance timestamp is absent from its historical slice"
            )
    for variant in variants:
        for timestamp in schedule:
            if indices[timestamp] + 1 < variant.window_policy.observation_count:
                raise HistoricalExperimentWalkForwardDataError(
                    f"{label} slice has insufficient observations for "
                    f"variant {variant.name}"
                )


def _validate_schedule(schedule, start, end, label, error):  # type: ignore[no-untyped-def]
    if not schedule:
        raise error(f"{label} rebalance timestamps must not be empty")
    if any(not start <= item < end for item in schedule):
        raise error(f"{label} rebalance timestamp is outside its interval")
    if any(right <= left for left, right in zip(schedule, schedule[1:], strict=False)):
        raise error(f"{label} rebalance timestamps must be strictly increasing")


def _validate_fold_order(folds, error):  # type: ignore[no-untyped-def]
    for previous, current in zip(folds, folds[1:], strict=False):
        if current.training_start < previous.training_start:
            raise error("training_start must be nondecreasing")
        if current.training_end <= previous.training_end:
            raise error("training_end must be strictly increasing")
        if (
            current.test_start <= previous.test_start
            or current.test_end <= previous.test_end
        ):
            raise error("test bounds must be strictly increasing")
        if previous.test_end > current.test_start:
            raise error("test intervals must be disjoint")


def _metadata(values, error):  # type: ignore[no-untyped-def]
    try:
        copied = tuple(values)
    except TypeError as caught:
        raise error("metadata must be iterable") from caught
    if not all(type(item) is MetadataEntry for item in copied):
        raise error("metadata must contain exact MetadataEntry values")
    if len({item.key for item in copied}) != len(copied):
        raise error("metadata keys must be unique")
    if any(item.key.startswith(_RESERVED_PREFIX) for item in copied):
        raise error(f"{_RESERVED_PREFIX} metadata keys are reserved")
    return copied


def _historical_fingerprint(data):  # type: ignore[no-untyped-def]
    return _id("historical-data", *canonical_multi_symbol_historical_material(data))


def _child_request_id(
    request,
    fold,
    ordinal,
    stage,
    source_fingerprint,
    selected_run=None,
    selected_variant=None,
):  # type: ignore[no-untyped-def]
    schedule = (
        fold.training_rebalance_timestamps
        if stage == "training"
        else fold.test_rebalance_timestamps
    )
    bounds = (
        (fold.training_start, fold.training_end)
        if stage == "training"
        else (fold.test_start, fold.test_end)
    )
    return _id(
        "child-request",
        stage,
        str(request.request_id),
        str(ordinal),
        str(fold.fold_id),
        _typed(bounds[0]),
        _typed(bounds[1]),
        *(_typed(item) for item in schedule),
        str(source_fingerprint),
        str(request.selection_policy.policy_id),
        _typed(selected_run),
        _typed(selected_variant),
    )


def _result_id(request_id, source_fingerprint, policy, folds, metadata):  # type: ignore[no-untyped-def]
    material = [
        _typed(request_id),
        _typed(source_fingerprint),
        _typed(policy.policy_id),
        _typed(policy.ranking_policy.policy_id),
        *(_typed(item.metric) for item in policy.ranking_policy.criteria),
        *(_typed(item.direction) for item in policy.ranking_policy.criteria),
        _typed(policy.ranking_policy.tie_breaker),
    ]
    material.extend(
        _typed(value)
        for item in policy.ranking_policy.metadata
        for value in (item.key, item.value)
    )
    material.extend(
        _typed(value) for item in policy.metadata for value in (item.key, item.value)
    )
    material.extend(
        _typed(value) for item in metadata for value in (item.key, item.value)
    )
    for item in folds:
        fold = item.fold
        material.extend(
            (
                _typed(item.ordinal),
                _typed(fold.fold_id),
                _typed(fold.training_start),
                _typed(fold.training_end),
                _typed(fold.test_start),
                _typed(fold.test_end),
                *(_typed(value) for value in fold.training_rebalance_timestamps),
                *(_typed(value) for value in fold.test_rebalance_timestamps),
                *(
                    _typed(value)
                    for entry in fold.metadata
                    for value in (entry.key, entry.value)
                ),
                _typed(item.training_report.report_id),
                *(
                    _typed(getattr(item.selection, name))
                    for name in item.selection.__dataclass_fields__
                ),
                _typed(item.test_report.report_id),
                _typed(item.training_historical_fingerprint),
                _typed(item.test_historical_fingerprint),
                _typed(item.test_run_id),
                _typed(item.test_rolling_result_id),
            )
        )
    return _id("result", *material)


def _request_invariant(request):  # type: ignore[no-untyped-def]
    return (
        request.request_id,
        _historical_fingerprint(request.historical_data),
        request.folds,
        request.initial_state,
        request.variants,
        request.selection_policy,
        request.metadata,
    )


def _typed(value):  # type: ignore[no-untyped-def]
    if value is None:
        return "NULL|"
    if type(value) is UUID:
        return f"UUID|{value}"
    if type(value) is int:
        return f"INTEGER|{value}"
    if type(value) is bool:
        return f"BOOLEAN|{'true' if value else 'false'}"
    if type(value) is datetime:
        return f"DATETIME|{value.astimezone(UTC).isoformat()}"
    if isinstance(value, Enum):
        return f"ENUM|{value.value}"
    if type(value) is str:
        return f"STRING|{value}"
    raise HistoricalExperimentWalkForwardReconciliationError(
        "identity value has an unsupported type"
    )


def _id(stage, *material):  # type: ignore[no-untyped-def]
    return uuid5(_NAMESPACE, "|".join((_VERSION, stage, *material)))
