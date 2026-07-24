"""Deterministic JSON and CSV serialization for Pareto experiment results."""

import csv
import io
import json
from decimal import Context, Decimal, localcontext

from trading_bot.cli.exceptions import HistoricalExperimentParetoOutputError
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.experiments import (
    HistoricalExperimentParetoResult,
    InconsistentHistoricalExperimentParetoResultError,
)

PARETO_EXPERIMENT_SCHEMA_VERSION = 1
PARETO_CSV_HEADER = (
    "row_type",
    "pareto_result_id",
    "source_report_id",
    "policy_id",
    "policy_objectives",
    "frontier_variant_ids",
    "policy_metadata",
    "caller_ordinal",
    "variant_id",
    "is_nondominated",
    "dominated_by_variant_ids",
    "dominates_variant_ids",
    "dominator_caller_ordinal",
    "dominated_caller_ordinal",
    "dominator_variant_id",
    "dominated_variant_id",
    "objective_metric",
    "objective_direction",
    "dominator_value",
    "dominated_value",
    "strictly_better",
)


def build_pareto_json(result: HistoricalExperimentParetoResult) -> dict[str, object]:
    _validate(result)
    policy = result.policy
    return {
        "schema_version": PARETO_EXPERIMENT_SCHEMA_VERSION,
        "pareto_result": {
            "result_id": str(result.result_id),
            "source_report_id": str(result.source_report_id),
            "policy": {
                "policy_id": str(policy.policy_id),
                "objectives": [_objective(item) for item in policy.objectives],
                "metadata": [_metadata(item) for item in policy.metadata],
            },
            "frontier_variant_ids": [str(item) for item in result.frontier_variant_ids],
            "variants": [
                {
                    "caller_ordinal": item.caller_ordinal,
                    "variant_id": str(item.variant_id),
                    "is_nondominated": item.is_nondominated,
                    "dominated_by_variant_ids": [
                        str(value) for value in item.dominated_by_variant_ids
                    ],
                    "dominates_variant_ids": [
                        str(value) for value in item.dominates_variant_ids
                    ],
                }
                for item in result.variants
            ],
            "dominance_records": [
                {
                    "dominator_caller_ordinal": item.dominator_caller_ordinal,
                    "dominated_caller_ordinal": item.dominated_caller_ordinal,
                    "dominator_variant_id": str(item.dominator_variant_id),
                    "dominated_variant_id": str(item.dominated_variant_id),
                    "objective_values": [
                        {
                            **_objective(value.objective),
                            "dominator_value": _json_scalar(value.dominator_value),
                            "dominated_value": _json_scalar(value.dominated_value),
                            "strictly_better": value.strictly_better,
                        }
                        for value in item.objective_values
                    ],
                }
                for item in result.dominance_records
            ],
        },
    }


def serialize_pareto_json(
    result: HistoricalExperimentParetoResult, *, pretty: bool = False
) -> str:
    if type(pretty) is not bool:
        raise HistoricalExperimentParetoOutputError("pretty must be bool")
    tree = build_pareto_json(result)
    kwargs = {"sort_keys": True, "ensure_ascii": False}
    if pretty:
        return json.dumps(tree, indent=2, **kwargs) + "\n"
    return json.dumps(tree, separators=(",", ":"), **kwargs) + "\n"


def serialize_pareto_csv(result: HistoricalExperimentParetoResult) -> str:
    _validate(result)
    policy = result.policy
    objectives = _compact([_objective(item) for item in policy.objectives])
    frontier = _compact([str(item) for item in result.frontier_variant_ids])
    metadata = _compact([_metadata(item) for item in policy.metadata])
    prefix = (
        result.result_id,
        result.source_report_id,
        policy.policy_id,
        objectives,
        frontier,
        metadata,
    )
    stream = io.StringIO(newline="")
    writer = csv.writer(
        stream, quoting=csv.QUOTE_MINIMAL, doublequote=True, lineterminator="\n"
    )
    writer.writerow(PARETO_CSV_HEADER)
    for item in result.variants:
        writer.writerow(
            (
                "VARIANT",
                *prefix,
                item.caller_ordinal,
                item.variant_id,
                _bool(item.is_nondominated),
                _compact([str(v) for v in item.dominated_by_variant_ids]),
                _compact([str(v) for v in item.dominates_variant_ids]),
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            )
        )
    for record in result.dominance_records:
        for value in record.objective_values:
            writer.writerow(
                (
                    "DOMINANCE",
                    *prefix,
                    "",
                    "",
                    "",
                    "",
                    "",
                    record.dominator_caller_ordinal,
                    record.dominated_caller_ordinal,
                    record.dominator_variant_id,
                    record.dominated_variant_id,
                    value.objective.metric.value,
                    value.objective.direction.value,
                    _csv_scalar(value.dominator_value),
                    _csv_scalar(value.dominated_value),
                    _bool(value.strictly_better),
                )
            )
    return stream.getvalue()


def _validate(result: HistoricalExperimentParetoResult) -> None:
    if type(result) is not HistoricalExperimentParetoResult:
        raise HistoricalExperimentParetoOutputError(
            "result must be exactly HistoricalExperimentParetoResult"
        )
    try:
        result.__post_init__()
    except InconsistentHistoricalExperimentParetoResultError as error:
        raise HistoricalExperimentParetoOutputError(
            f"invalid Pareto result: {error}"
        ) from error


def _objective(value):  # type: ignore[no-untyped-def]
    return {"metric": value.metric.value, "direction": value.direction.value}


def _metadata(value):  # type: ignore[no-untyped-def]
    return {"key": value.key, "value": value.value}


def _compact(value) -> str:  # type: ignore[no-untyped-def]
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _json_scalar(value: Decimal | int) -> str | int:
    return _canonical(value) if type(value) is Decimal else value


def _csv_scalar(value: Decimal | int) -> str:
    return _canonical(value) if type(value) is Decimal else str(value)


def _canonical(value: Decimal) -> str:
    with localcontext(Context(prec=max(28, len(value.as_tuple().digits) + 8))):
        return canonical_decimal(value)


def _bool(value: bool) -> str:
    return "true" if value else "false"
