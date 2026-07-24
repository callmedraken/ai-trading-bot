"""Deterministic JSON and CSV serialization for pairwise experiment results."""

import csv
import io
import json
from decimal import Context, Decimal, localcontext

from trading_bot.cli.exceptions import HistoricalExperimentPairwiseOutputError
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.experiments import (
    HistoricalExperimentPairwiseResult,
    InconsistentHistoricalExperimentPairwiseResultError,
)

PAIRWISE_EXPERIMENT_SCHEMA_VERSION = 1
PAIRWISE_CSV_HEADER = (
    "pairwise_result_id",
    "source_report_id",
    "policy_id",
    "pairing",
    "orientation",
    "baseline_variant_id",
    "policy_metadata",
    "record_ordinal",
    "left_caller_ordinal",
    "right_caller_ordinal",
    "left_variant_id",
    "right_variant_id",
    "metric",
    "left_value",
    "right_value",
    "difference",
)


def build_pairwise_json(
    result: HistoricalExperimentPairwiseResult,
) -> dict[str, object]:
    """Build the explicit version-one pairwise JSON tree."""
    _validate_result(result)
    policy = result.policy
    return {
        "schema_version": PAIRWISE_EXPERIMENT_SCHEMA_VERSION,
        "pairwise_result": {
            "result_id": str(result.result_id),
            "source_report_id": str(result.source_report_id),
            "policy": {
                "policy_id": str(policy.policy_id),
                "metrics": [metric.value for metric in policy.metrics],
                "pairing": policy.pairing.value,
                "orientation": policy.orientation.value,
                "baseline_variant_id": (
                    None
                    if policy.baseline_variant_id is None
                    else str(policy.baseline_variant_id)
                ),
                "metadata": [
                    {"key": item.key, "value": item.value} for item in policy.metadata
                ],
            },
            "records": [
                {
                    "ordinal": record.ordinal,
                    "left_caller_ordinal": record.left_caller_ordinal,
                    "right_caller_ordinal": record.right_caller_ordinal,
                    "left_variant_id": str(record.left_variant_id),
                    "right_variant_id": str(record.right_variant_id),
                    "differences": [
                        {
                            "metric": difference.metric.value,
                            "left_value": _json_scalar(difference.left_value),
                            "right_value": _json_scalar(difference.right_value),
                            "difference": _json_scalar(difference.difference),
                        }
                        for difference in record.differences
                    ],
                }
                for record in result.records
            ],
        },
    }


def serialize_pairwise_json(
    result: HistoricalExperimentPairwiseResult,
    *,
    pretty: bool = False,
) -> str:
    """Serialize one pairwise result with stable JSON bytes."""
    if type(pretty) is not bool:
        raise HistoricalExperimentPairwiseOutputError("pretty must be bool")
    tree = build_pairwise_json(result)
    try:
        if pretty:
            return json.dumps(tree, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        return (
            json.dumps(
                tree,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            + "\n"
        )
    except (TypeError, ValueError) as error:
        raise HistoricalExperimentPairwiseOutputError(
            f"cannot serialize pairwise JSON: {error}"
        ) from error


def serialize_pairwise_csv(result: HistoricalExperimentPairwiseResult) -> str:
    """Serialize one long-format row per pair and selected metric."""
    _validate_result(result)
    policy = result.policy
    metadata = json.dumps(
        [{"key": item.key, "value": item.value} for item in policy.metadata],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    stream = io.StringIO(newline="")
    writer = csv.writer(
        stream,
        delimiter=",",
        quoting=csv.QUOTE_MINIMAL,
        doublequote=True,
        lineterminator="\n",
    )
    writer.writerow(PAIRWISE_CSV_HEADER)
    baseline = (
        "" if policy.baseline_variant_id is None else str(policy.baseline_variant_id)
    )
    for record in result.records:
        for difference in record.differences:
            writer.writerow(
                (
                    result.result_id,
                    result.source_report_id,
                    policy.policy_id,
                    policy.pairing.value,
                    policy.orientation.value,
                    baseline,
                    metadata,
                    record.ordinal,
                    record.left_caller_ordinal,
                    record.right_caller_ordinal,
                    record.left_variant_id,
                    record.right_variant_id,
                    difference.metric.value,
                    _csv_scalar(difference.left_value),
                    _csv_scalar(difference.right_value),
                    _csv_scalar(difference.difference),
                )
            )
    return stream.getvalue()


def _validate_result(result: HistoricalExperimentPairwiseResult) -> None:
    if type(result) is not HistoricalExperimentPairwiseResult:
        raise HistoricalExperimentPairwiseOutputError(
            "result must be exactly HistoricalExperimentPairwiseResult"
        )
    try:
        result.__post_init__()
    except InconsistentHistoricalExperimentPairwiseResultError as error:
        raise HistoricalExperimentPairwiseOutputError(
            f"invalid pairwise result: {error}"
        ) from error


def _json_scalar(value: Decimal | int) -> str | int:
    return _canonical(value) if type(value) is Decimal else value


def _csv_scalar(value: Decimal | int) -> str:
    return _canonical(value) if type(value) is Decimal else str(value)


def _canonical(value: Decimal) -> str:
    with localcontext(Context(prec=max(28, len(value.as_tuple().digits) + 8))):
        return canonical_decimal(value)
