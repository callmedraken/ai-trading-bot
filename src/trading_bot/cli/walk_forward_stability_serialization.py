"""Deterministic projections of immutable walk-forward stability results."""

import csv
import io
import json
from datetime import timedelta
from decimal import Context, Decimal, localcontext

from trading_bot.cli.exceptions import WalkForwardExperimentOutputError
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.experiments import HistoricalExperimentWalkForwardStabilityResult

WALK_FORWARD_STABILITY_SCHEMA_VERSION = 1
WALK_FORWARD_STABILITY_CSV_HEADER = (
    "record_type",
    "stability_result_id",
    "source_walk_forward_result_id",
    "source_request_id",
    "source_historical_fingerprint",
    "source_aggregate_result_id",
    "stability_policy_id",
    "stability_policy_metadata",
    "fold_count",
    "metric_ordinal",
    "metric",
    "operations",
    "comparability_rule",
    "unique_selected_variant_count",
    "persistence_adjacency_count",
    "changed_adjacency_count",
    "persistence_ratio_numerator",
    "persistence_ratio_denominator",
    "longest_consecutive_selection_run",
    "fold_ordinal",
    "fold_id",
    "test_duration_microseconds",
    "test_schedule_count",
    "selected_variant_id",
    "selected_rank",
    "run_ordinal",
    "run_start_fold_ordinal",
    "run_end_fold_ordinal",
    "run_variant_id",
    "run_consecutive_fold_count",
    "transition_ordinal",
    "previous_fold_ordinal",
    "current_fold_ordinal",
    "previous_fold_id",
    "current_fold_id",
    "from_variant_id",
    "to_variant_id",
    "transition_changed",
    "transition_occurrence_count",
    "frequency_variant_id",
    "selected_fold_count",
    "first_selected_fold_ordinal",
    "test_report_id",
    "test_run_id",
    "observation_value",
    "observation_scalar_type",
    "previous_variant_id",
    "current_variant_id",
    "previous_value",
    "current_value",
    "absolute_change",
    "change_scalar_type",
    "value_range",
    "range_scalar_type",
    "median",
    "median_absolute_deviation",
    "sign_change_count",
)


def serialize_walk_forward_stability_json(
    result: HistoricalExperimentWalkForwardStabilityResult, *, pretty: bool = False
) -> str:
    _validate(result)
    if type(pretty) is not bool:
        raise WalkForwardExperimentOutputError("pretty must be bool")
    tree = {
        "schema_version": WALK_FORWARD_STABILITY_SCHEMA_VERSION,
        "walk_forward_stability_result": _result_json(result),
    }
    try:
        rendered = json.dumps(
            tree,
            ensure_ascii=False,
            sort_keys=True,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise WalkForwardExperimentOutputError(
            f"cannot serialize walk-forward stability JSON: {error}"
        ) from error
    return rendered + "\n"


def serialize_walk_forward_stability_csv(
    result: HistoricalExperimentWalkForwardStabilityResult,
) -> str:
    _validate(result)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=WALK_FORWARD_STABILITY_CSV_HEADER,
        lineterminator="\n",
    )
    writer.writeheader()
    base = _csv_base(result)
    selection = result.selection_stability
    for item in selection.observations:
        writer.writerow(
            base
            | _selection_summary_csv(selection)
            | {
                "record_type": "SELECTION_OBSERVATION",
                "fold_ordinal": item.fold_ordinal,
                "fold_id": item.fold_id,
                "test_duration_microseconds": _duration_microseconds(
                    item.test_duration
                ),
                "test_schedule_count": item.test_schedule_count,
                "selected_variant_id": item.selected_variant_id,
                "selected_rank": item.selected_rank,
            }
        )
    for ordinal, item in enumerate(selection.runs):
        writer.writerow(
            base
            | {
                "record_type": "SELECTION_RUN",
                "run_ordinal": ordinal,
                "run_start_fold_ordinal": item.start_fold_ordinal,
                "run_end_fold_ordinal": item.end_fold_ordinal,
                "run_variant_id": item.variant_id,
                "run_consecutive_fold_count": item.consecutive_fold_count,
            }
        )
    for ordinal, item in enumerate(selection.transitions):
        writer.writerow(
            base
            | {
                "record_type": "SELECTION_TRANSITION",
                "transition_ordinal": ordinal,
                "previous_fold_ordinal": item.previous_fold_ordinal,
                "current_fold_ordinal": item.current_fold_ordinal,
                "previous_fold_id": item.previous_fold_id,
                "current_fold_id": item.current_fold_id,
                "from_variant_id": item.from_variant_id,
                "to_variant_id": item.to_variant_id,
                "transition_changed": _boolean(item.changed),
            }
        )
    for item in selection.transition_frequencies:
        writer.writerow(
            base
            | {
                "record_type": "TRANSITION_FREQUENCY",
                "from_variant_id": item.from_variant_id,
                "to_variant_id": item.to_variant_id,
                "transition_occurrence_count": item.occurrence_count,
            }
        )
    for item in selection.variant_frequencies:
        writer.writerow(
            base
            | {
                "record_type": "VARIANT_FREQUENCY",
                "frequency_variant_id": item.variant_id,
                "selected_fold_count": item.selected_fold_count,
                "first_selected_fold_ordinal": item.first_selected_fold_ordinal,
            }
        )
    for metric_ordinal, summary in enumerate(result.metric_stability):
        policy = result.policy.metrics[metric_ordinal]
        metric_base = base | _metric_policy_csv(metric_ordinal, policy)
        for item in summary.observations:
            writer.writerow(
                metric_base
                | {
                    "record_type": "METRIC_OBSERVATION",
                    "fold_ordinal": item.fold_ordinal,
                    "fold_id": item.fold_id,
                    "test_duration_microseconds": _duration_microseconds(
                        item.test_duration
                    ),
                    "test_schedule_count": item.test_schedule_count,
                    "selected_variant_id": item.selected_variant_id,
                    "test_report_id": item.test_report_id,
                    "test_run_id": item.test_run_id,
                    "observation_value": _scalar(item.value),
                    "observation_scalar_type": _scalar_type(item.value),
                }
            )
        for item in summary.adjacent_changes:
            writer.writerow(
                metric_base
                | {
                    "record_type": "ADJACENT_METRIC_CHANGE",
                    "previous_fold_ordinal": item.previous_fold_ordinal,
                    "current_fold_ordinal": item.current_fold_ordinal,
                    "previous_fold_id": item.previous_fold_id,
                    "current_fold_id": item.current_fold_id,
                    "previous_variant_id": item.previous_variant_id,
                    "current_variant_id": item.current_variant_id,
                    "previous_value": _scalar(item.previous_value),
                    "current_value": _scalar(item.current_value),
                    "absolute_change": _scalar(item.absolute_change),
                    "change_scalar_type": _scalar_type(item.absolute_change),
                }
            )
        writer.writerow(
            metric_base
            | {
                "record_type": "METRIC_SUMMARY",
                "value_range": _optional_scalar(summary.value_range),
                "range_scalar_type": (
                    ""
                    if summary.value_range is None
                    else _scalar_type(summary.value_range)
                ),
                "median": _optional_scalar(summary.median),
                "median_absolute_deviation": _optional_scalar(
                    summary.median_absolute_deviation
                ),
                "sign_change_count": (
                    ""
                    if summary.sign_change_count is None
                    else summary.sign_change_count
                ),
            }
        )
    return stream.getvalue()


def _result_json(result):  # type: ignore[no-untyped-def]
    selection = result.selection_stability
    return {
        "result_id": str(result.result_id),
        "source_walk_forward_result_id": str(result.source_walk_forward_result_id),
        "source_request_id": str(result.source_request_id),
        "source_historical_fingerprint": str(result.source_historical_fingerprint),
        "source_aggregate_result_id": (
            None
            if result.source_aggregate_result_id is None
            else str(result.source_aggregate_result_id)
        ),
        "policy": {
            "policy_id": str(result.policy.policy_id),
            "metrics": [
                {
                    "metric": item.metric.value,
                    "operations": [operation.value for operation in item.operations],
                    "comparability_rule": item.comparability_rule.value,
                }
                for item in result.policy.metrics
            ],
            "metadata": _metadata(result.policy.metadata),
        },
        "fold_count": result.fold_count,
        "selection_stability": {
            "observations": [
                {
                    "fold_ordinal": item.fold_ordinal,
                    "fold_id": str(item.fold_id),
                    "test_duration_microseconds": _duration_microseconds(
                        item.test_duration
                    ),
                    "test_schedule_count": item.test_schedule_count,
                    "selected_variant_id": str(item.selected_variant_id),
                    "selected_rank": item.selected_rank,
                }
                for item in selection.observations
            ],
            "unique_selected_variant_count": selection.unique_selected_variant_count,
            "persistence_adjacency_count": selection.persistence_adjacency_count,
            "changed_adjacency_count": selection.changed_adjacency_count,
            "persistence_ratio": (
                None
                if selection.persistence_ratio is None
                else {
                    "numerator": selection.persistence_ratio.numerator,
                    "denominator": selection.persistence_ratio.denominator,
                }
            ),
            "runs": [
                {
                    "start_fold_ordinal": item.start_fold_ordinal,
                    "end_fold_ordinal": item.end_fold_ordinal,
                    "variant_id": str(item.variant_id),
                    "consecutive_fold_count": item.consecutive_fold_count,
                }
                for item in selection.runs
            ],
            "longest_consecutive_selection_run": (
                selection.longest_consecutive_selection_run
            ),
            "transitions": [
                {
                    "previous_fold_ordinal": item.previous_fold_ordinal,
                    "current_fold_ordinal": item.current_fold_ordinal,
                    "previous_fold_id": str(item.previous_fold_id),
                    "current_fold_id": str(item.current_fold_id),
                    "from_variant_id": str(item.from_variant_id),
                    "to_variant_id": str(item.to_variant_id),
                    "changed": item.changed,
                }
                for item in selection.transitions
            ],
            "transition_frequencies": [
                {
                    "from_variant_id": str(item.from_variant_id),
                    "to_variant_id": str(item.to_variant_id),
                    "occurrence_count": item.occurrence_count,
                }
                for item in selection.transition_frequencies
            ],
            "variant_frequencies": [
                {
                    "variant_id": str(item.variant_id),
                    "selected_fold_count": item.selected_fold_count,
                    "first_selected_fold_ordinal": item.first_selected_fold_ordinal,
                }
                for item in selection.variant_frequencies
            ],
        },
        "metric_stability": [
            {
                "metric": item.metric.value,
                "observations": [_observation(value) for value in item.observations],
                "adjacent_changes": [
                    _adjacent_change(value) for value in item.adjacent_changes
                ],
                "value_range": _json_scalar(item.value_range),
                "median": _json_scalar(item.median),
                "median_absolute_deviation": _json_scalar(
                    item.median_absolute_deviation
                ),
                "sign_change_count": item.sign_change_count,
            }
            for item in result.metric_stability
        ],
    }


def _observation(item):  # type: ignore[no-untyped-def]
    return {
        "fold_ordinal": item.fold_ordinal,
        "fold_id": str(item.fold_id),
        "test_report_id": str(item.test_report_id),
        "test_run_id": str(item.test_run_id),
        "selected_variant_id": str(item.selected_variant_id),
        "test_duration_microseconds": _duration_microseconds(item.test_duration),
        "test_schedule_count": item.test_schedule_count,
        "value": _json_scalar(item.value),
        "value_scalar_type": _scalar_type(item.value),
    }


def _adjacent_change(item):  # type: ignore[no-untyped-def]
    return {
        "previous_fold_ordinal": item.previous_fold_ordinal,
        "current_fold_ordinal": item.current_fold_ordinal,
        "previous_fold_id": str(item.previous_fold_id),
        "current_fold_id": str(item.current_fold_id),
        "previous_variant_id": str(item.previous_variant_id),
        "current_variant_id": str(item.current_variant_id),
        "previous_value": _json_scalar(item.previous_value),
        "current_value": _json_scalar(item.current_value),
        "absolute_change": _json_scalar(item.absolute_change),
        "scalar_type": _scalar_type(item.absolute_change),
        "comparability_rule": item.comparability_rule.value,
    }


def _csv_base(result):  # type: ignore[no-untyped-def]
    return {
        "stability_result_id": result.result_id,
        "source_walk_forward_result_id": result.source_walk_forward_result_id,
        "source_request_id": result.source_request_id,
        "source_historical_fingerprint": result.source_historical_fingerprint,
        "source_aggregate_result_id": result.source_aggregate_result_id or "",
        "stability_policy_id": result.policy.policy_id,
        "stability_policy_metadata": _evidence(_metadata(result.policy.metadata)),
        "fold_count": result.fold_count,
    }


def _selection_summary_csv(selection):  # type: ignore[no-untyped-def]
    ratio = selection.persistence_ratio
    return {
        "unique_selected_variant_count": selection.unique_selected_variant_count,
        "persistence_adjacency_count": selection.persistence_adjacency_count,
        "changed_adjacency_count": selection.changed_adjacency_count,
        "persistence_ratio_numerator": "" if ratio is None else ratio.numerator,
        "persistence_ratio_denominator": "" if ratio is None else ratio.denominator,
        "longest_consecutive_selection_run": (
            selection.longest_consecutive_selection_run
        ),
    }


def _metric_policy_csv(ordinal, policy):  # type: ignore[no-untyped-def]
    return {
        "metric_ordinal": ordinal,
        "metric": policy.metric.value,
        "operations": _evidence([item.value for item in policy.operations]),
        "comparability_rule": policy.comparability_rule.value,
    }


def _validate(result):  # type: ignore[no-untyped-def]
    if type(result) is not HistoricalExperimentWalkForwardStabilityResult:
        raise WalkForwardExperimentOutputError(
            "result must be exactly HistoricalExperimentWalkForwardStabilityResult"
        )


def _duration_microseconds(value: timedelta) -> int:
    if type(value) is not timedelta:
        raise WalkForwardExperimentOutputError("duration must be an exact timedelta")
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds


def _json_scalar(value):  # type: ignore[no-untyped-def]
    if value is None or type(value) is int:
        return value
    if type(value) is Decimal:
        return _decimal(value)
    raise WalkForwardExperimentOutputError("unsupported stability scalar")


def _optional_scalar(value):  # type: ignore[no-untyped-def]
    return "" if value is None else _scalar(value)


def _scalar(value):  # type: ignore[no-untyped-def]
    if type(value) is int:
        return str(value)
    if type(value) is Decimal:
        return _decimal(value)
    raise WalkForwardExperimentOutputError("unsupported stability scalar")


def _scalar_type(value):  # type: ignore[no-untyped-def]
    if type(value) is Decimal:
        return "DECIMAL"
    if type(value) is int:
        return "INTEGER"
    raise WalkForwardExperimentOutputError("unsupported stability scalar type")


def _boolean(value: bool) -> str:
    if type(value) is not bool:
        raise WalkForwardExperimentOutputError("value must be an exact bool")
    return "true" if value else "false"


def _metadata(items):  # type: ignore[no-untyped-def]
    return [{"key": item.key, "value": item.value} for item in items]


def _evidence(value):  # type: ignore[no-untyped-def]
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decimal(value: Decimal) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise WalkForwardExperimentOutputError(
            "stability Decimal values must be exact and finite"
        )
    digits = len(value.as_tuple().digits)
    with localcontext(
        Context(prec=max(digits, 1), Emax=999_999_999, Emin=-999_999_999)
    ):
        return canonical_decimal(value)
