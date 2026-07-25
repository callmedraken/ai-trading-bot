"""Deterministic projections of immutable walk-forward aggregate results."""

import csv
import io
import json
from decimal import Context, Decimal, localcontext

from trading_bot.cli.exceptions import WalkForwardExperimentOutputError
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.experiments import HistoricalExperimentWalkForwardAggregateResult

WALK_FORWARD_AGGREGATE_SCHEMA_VERSION = 1
WALK_FORWARD_AGGREGATE_CSV_HEADER = (
    "aggregate_result_id",
    "source_walk_forward_result_id",
    "source_request_id",
    "source_historical_fingerprint",
    "aggregate_policy_id",
    "aggregate_policy_metadata",
    "fold_count",
    "successful_test_fold_count",
    "fold_ordinal",
    "fold_id",
    "test_report_id",
    "test_run_id",
    "test_rolling_result_id",
    "selected_variant_id",
    "selected_rank",
    "metric_ordinal",
    "metric",
    "operations",
    "observation_value",
    "observation_scalar_type",
    "minimum",
    "maximum",
    "median",
    "arithmetic_mean_numerator",
    "arithmetic_mean_denominator",
    "sign_positive_count",
    "sign_zero_count",
    "sign_negative_count",
    "selected_variant_fold_count",
    "selected_variant_rank_one_fold_count",
)


def serialize_walk_forward_aggregate_json(
    result: HistoricalExperimentWalkForwardAggregateResult, *, pretty: bool = False
) -> str:
    _validate(result)
    if type(pretty) is not bool:
        raise WalkForwardExperimentOutputError("pretty must be bool")
    tree = {
        "schema_version": WALK_FORWARD_AGGREGATE_SCHEMA_VERSION,
        "walk_forward_aggregate_result": _result_json(result),
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
            f"cannot serialize walk-forward aggregate JSON: {error}"
        ) from error
    return rendered + "\n"


def serialize_walk_forward_aggregate_csv(
    result: HistoricalExperimentWalkForwardAggregateResult,
) -> str:
    _validate(result)
    frequencies = {item.variant_id: item for item in result.variant_frequencies}
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(WALK_FORWARD_AGGREGATE_CSV_HEADER)
    for fold in result.fold_summaries:
        frequency = frequencies[fold.selected_variant_id]
        for metric_ordinal, observation in enumerate(fold.metrics):
            policy = result.policy.metrics[metric_ordinal]
            summary = result.metric_summaries[metric_ordinal]
            mean = summary.arithmetic_mean
            signs = summary.sign_counts
            writer.writerow(
                (
                    result.result_id,
                    result.source_walk_forward_result_id,
                    result.source_request_id,
                    result.source_historical_fingerprint,
                    result.policy.policy_id,
                    _evidence(_metadata(result.policy.metadata)),
                    result.fold_count,
                    result.successful_test_fold_count,
                    fold.fold_ordinal,
                    fold.fold_id,
                    fold.test_report_id,
                    fold.test_run_id,
                    fold.test_rolling_result_id,
                    fold.selected_variant_id,
                    fold.selected_rank,
                    metric_ordinal,
                    policy.metric.value,
                    _evidence([item.value for item in policy.operations]),
                    _scalar(observation.value),
                    "DECIMAL" if type(observation.value) is Decimal else "INTEGER",
                    _optional_scalar(summary.minimum),
                    _optional_scalar(summary.maximum),
                    _optional_scalar(summary.median),
                    "" if mean is None else mean.numerator,
                    "" if mean is None else mean.denominator,
                    "" if signs is None else signs.positive,
                    "" if signs is None else signs.zero,
                    "" if signs is None else signs.negative,
                    frequency.selected_fold_count,
                    frequency.rank_one_selected_fold_count,
                )
            )
    return stream.getvalue()


def _result_json(result):
    return {
        "result_id": str(result.result_id),
        "source_walk_forward_result_id": str(result.source_walk_forward_result_id),
        "source_request_id": str(result.source_request_id),
        "source_historical_fingerprint": str(result.source_historical_fingerprint),
        "policy": {
            "policy_id": str(result.policy.policy_id),
            "metrics": [
                {
                    "metric": item.metric.value,
                    "operations": [operation.value for operation in item.operations],
                }
                for item in result.policy.metrics
            ],
            "metadata": _metadata(result.policy.metadata),
        },
        "fold_count": result.fold_count,
        "successful_test_fold_count": result.successful_test_fold_count,
        "fold_summaries": [
            {
                "fold_ordinal": fold.fold_ordinal,
                "fold_id": str(fold.fold_id),
                "test_report_id": str(fold.test_report_id),
                "test_run_id": str(fold.test_run_id),
                "test_rolling_result_id": str(fold.test_rolling_result_id),
                "selected_variant_id": str(fold.selected_variant_id),
                "selected_rank": fold.selected_rank,
                "metrics": [
                    {
                        "metric": result.policy.metrics[index].metric.value,
                        **_observation(item),
                    }
                    for index, item in enumerate(fold.metrics)
                ],
            }
            for fold in result.fold_summaries
        ],
        "metric_summaries": [
            {
                "metric": item.metric.value,
                "observations": [_observation(value) for value in item.observations],
                "minimum": _json_scalar(item.minimum),
                "maximum": _json_scalar(item.maximum),
                "median": _json_scalar(item.median),
                "arithmetic_mean": (
                    None
                    if item.arithmetic_mean is None
                    else {
                        "numerator": item.arithmetic_mean.numerator,
                        "denominator": item.arithmetic_mean.denominator,
                    }
                ),
                "sign_counts": (
                    None
                    if item.sign_counts is None
                    else {
                        "positive": item.sign_counts.positive,
                        "zero": item.sign_counts.zero,
                        "negative": item.sign_counts.negative,
                    }
                ),
            }
            for item in result.metric_summaries
        ],
        "variant_frequencies": [
            {
                "variant_id": str(item.variant_id),
                "selected_fold_count": item.selected_fold_count,
                "rank_one_selected_fold_count": item.rank_one_selected_fold_count,
            }
            for item in result.variant_frequencies
        ],
    }


def _observation(item):
    return {
        "fold_ordinal": item.fold_ordinal,
        "fold_id": str(item.fold_id),
        "test_report_id": str(item.test_report_id),
        "test_run_id": str(item.test_run_id),
        "variant_id": str(item.variant_id),
        "value": _json_scalar(item.value),
    }


def _validate(result):
    if type(result) is not HistoricalExperimentWalkForwardAggregateResult:
        raise WalkForwardExperimentOutputError(
            "result must be exactly HistoricalExperimentWalkForwardAggregateResult"
        )


def _metadata(items):
    return [{"key": item.key, "value": item.value} for item in items]


def _json_scalar(value):
    if value is None or type(value) is int:
        return value
    if type(value) is Decimal:
        return _decimal(value)
    raise WalkForwardExperimentOutputError("unsupported aggregate scalar")


def _optional_scalar(value):
    return "" if value is None else _scalar(value)


def _scalar(value):
    if type(value) is int:
        return str(value)
    if type(value) is Decimal:
        return _decimal(value)
    raise WalkForwardExperimentOutputError("unsupported aggregate scalar")


def _evidence(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decimal(value):
    digits = len(value.as_tuple().digits)
    with localcontext(
        Context(prec=max(digits, 1), Emax=999_999_999, Emin=-999_999_999)
    ):
        return canonical_decimal(value)
