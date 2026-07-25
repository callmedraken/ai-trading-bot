"""Deterministic JSON and CSV export for immutable walk-forward results."""

import csv
import io
import json
from datetime import datetime
from decimal import Context, Decimal, localcontext
from enum import Enum
from uuid import UUID

from trading_bot.cli.exceptions import WalkForwardExperimentOutputError
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.experiments import (
    HistoricalExperimentReport,
    HistoricalExperimentWalkForwardResult,
    HistoricalExperimentWalkForwardSelection,
)

WALK_FORWARD_REPORT_SCHEMA_VERSION = 1

_METRIC_FIELDS = (
    "initial_equity",
    "final_equity",
    "absolute_simulation_profit_loss",
    "simulation_return",
    "maximum_drawdown_amount",
    "maximum_drawdown_percentage",
    "simulation_realized_profit_loss",
    "total_commissions",
    "adverse_slippage_cost",
    "total_execution_cost",
    "aggregate_one_way_turnover",
    "aggregate_two_way_turnover",
    "maximum_allocation_drift",
    "total_orders",
    "total_fills",
    "approved_decisions",
    "resized_decisions",
    "rejected_decisions",
    "rejected_notional",
    "reduced_notional",
    "mean_expected_portfolio_return",
    "worst_cvar",
    "minimum_target_cash_weight",
    "maximum_target_cash_weight",
    "applied_cycle_count",
    "no_action_cycle_count",
)

_RANKING_METRICS = (
    (
        "INITIAL_EQUITY",
        "initial_equity",
    ),
    ("FINAL_EQUITY", "final_equity"),
    ("ABSOLUTE_SIMULATION_PROFIT_LOSS", "absolute_simulation_profit_loss"),
    ("SIMULATION_RETURN", "simulation_return"),
    ("MAXIMUM_DRAWDOWN_AMOUNT", "maximum_drawdown_amount"),
    ("MAXIMUM_DRAWDOWN_PERCENTAGE", "maximum_drawdown_percentage"),
    ("SIMULATION_REALIZED_PROFIT_LOSS", "simulation_realized_profit_loss"),
    ("TOTAL_COMMISSIONS", "total_commissions"),
    ("ADVERSE_SLIPPAGE_COST", "adverse_slippage_cost"),
    ("TOTAL_EXECUTION_COST", "total_execution_cost"),
    ("AGGREGATE_ONE_WAY_TURNOVER", "aggregate_one_way_turnover"),
    ("AGGREGATE_TWO_WAY_TURNOVER", "aggregate_two_way_turnover"),
    ("MAXIMUM_ALLOCATION_DRIFT", "maximum_allocation_drift"),
    ("TOTAL_ORDERS", "total_orders"),
    ("TOTAL_FILLS", "total_fills"),
    ("APPROVED_DECISIONS", "approved_decisions"),
    ("RESIZED_DECISIONS", "resized_decisions"),
    ("REJECTED_DECISIONS", "rejected_decisions"),
    ("REJECTED_NOTIONAL", "rejected_notional"),
    ("REDUCED_NOTIONAL", "reduced_notional"),
    ("MEAN_EXPECTED_PORTFOLIO_RETURN", "mean_expected_portfolio_return"),
    ("WORST_CVAR", "worst_cvar"),
    ("MINIMUM_TARGET_CASH_WEIGHT", "minimum_target_cash_weight"),
    ("MAXIMUM_TARGET_CASH_WEIGHT", "maximum_target_cash_weight"),
    ("APPLIED_CYCLE_COUNT", "applied_cycle_count"),
    ("NO_ACTION_CYCLE_COUNT", "no_action_cycle_count"),
)

WALK_FORWARD_CSV_HEADER = (
    "walk_forward_result_id",
    "walk_forward_request_id",
    "source_historical_fingerprint",
    "selection_policy_id",
    "ranking_policy_id",
    "ranking_policy_fingerprint",
    "ranking_tie_breaker",
    "ranking_criteria",
    "selection_policy_metadata",
    "walk_forward_metadata",
    "fold_ordinal",
    "fold_id",
    "training_start",
    "training_end",
    "test_start",
    "test_end",
    "training_rebalance_timestamps",
    "test_rebalance_timestamps",
    "fold_metadata",
    "selection_training_report_id",
    "selection_training_experiment_result_id",
    "selection_training_comparison_result_id",
    "selection_ranking_policy_id",
    "selected_rank",
    "selected_caller_ordinal",
    "selected_variant_id",
    "selected_training_run_id",
    "row_kind",
    "report_id",
    "experiment_request_id",
    "experiment_result_id",
    "historical_fingerprint",
    "schedule_fingerprint",
    "initial_state_fingerprint",
    "variant_source",
    "report_metadata",
    "caller_ordinal",
    "experiment_run_id",
    "rolling_result_id",
    "variant_id",
    "variant_name",
    "rank",
    "comparison_values",
    *(f"rank_value_{field}" for _, field in _RANKING_METRICS),
    *_METRIC_FIELDS,
)


def build_walk_forward_json(
    result: HistoricalExperimentWalkForwardResult,
) -> dict[str, object]:
    _validate_result(result)
    policy = result.selection_policy
    return {
        "schema_version": WALK_FORWARD_REPORT_SCHEMA_VERSION,
        "walk_forward_result": {
            "result_id": str(result.result_id),
            "request_id": str(result.request_id),
            "source_historical_fingerprint": str(result.source_historical_fingerprint),
            "selection_policy": {
                "policy_id": str(policy.policy_id),
                "ranking_policy": {
                    "policy_id": str(policy.ranking_policy.policy_id),
                    "criteria": [
                        {
                            "metric": item.metric.value,
                            "direction": item.direction.value,
                        }
                        for item in policy.ranking_policy.criteria
                    ],
                    "tie_breaker": policy.ranking_policy.tie_breaker.value,
                    "metadata": _metadata_json(policy.ranking_policy.metadata),
                },
                "metadata": _metadata_json(policy.metadata),
            },
            "folds": [
                {
                    "ordinal": item.ordinal,
                    "fold": {
                        "fold_id": str(item.fold.fold_id),
                        "training_start": item.fold.training_start.isoformat(),
                        "training_end": item.fold.training_end.isoformat(),
                        "test_start": item.fold.test_start.isoformat(),
                        "test_end": item.fold.test_end.isoformat(),
                        "training_rebalance_timestamps": [
                            value.isoformat()
                            for value in item.fold.training_rebalance_timestamps
                        ],
                        "test_rebalance_timestamps": [
                            value.isoformat()
                            for value in item.fold.test_rebalance_timestamps
                        ],
                        "metadata": _metadata_json(item.fold.metadata),
                    },
                    "training": {
                        "request_id": str(item.training_request_id),
                        "historical_fingerprint": str(
                            item.training_historical_fingerprint
                        ),
                        "report": _report_json(item.training_report),
                    },
                    "selection": _selection_json(item.selection),
                    "test": {
                        "request_id": str(item.test_request_id),
                        "historical_fingerprint": str(item.test_historical_fingerprint),
                        "report": _report_json(item.test_report),
                        "run_id": str(item.test_run_id),
                        "rolling_result_id": str(item.test_rolling_result_id),
                    },
                }
                for item in result.folds
            ],
            "metadata": _metadata_json(result.metadata),
        },
    }


def serialize_walk_forward_json(
    result: HistoricalExperimentWalkForwardResult, *, pretty: bool = False
) -> str:
    if type(pretty) is not bool:
        raise WalkForwardExperimentOutputError("pretty must be bool")
    tree = build_walk_forward_json(result)
    try:
        rendered = (
            json.dumps(tree, ensure_ascii=False, sort_keys=True, indent=2)
            if pretty
            else json.dumps(
                tree,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except (TypeError, ValueError) as error:
        raise WalkForwardExperimentOutputError(
            f"cannot serialize walk-forward JSON: {error}"
        ) from error
    return rendered + "\n"


def serialize_walk_forward_csv(
    result: HistoricalExperimentWalkForwardResult,
) -> str:
    _validate_result(result)
    policy = result.selection_policy
    ranking = policy.ranking_policy
    criteria = [
        {"metric": item.metric.value, "direction": item.direction.value}
        for item in ranking.criteria
    ]
    stream = io.StringIO(newline="")
    writer = csv.writer(
        stream,
        delimiter=",",
        quoting=csv.QUOTE_MINIMAL,
        doublequote=True,
        lineterminator="\n",
    )
    writer.writerow(WALK_FORWARD_CSV_HEADER)
    for fold_result in result.folds:
        for report, row_kind in (
            (fold_result.training_report, "TRAINING_VARIANT"),
            (fold_result.test_report, "TEST_VARIANT"),
        ):
            for row in report.variants:
                writer.writerow(
                    _csv_row(
                        result,
                        fold_result,
                        report,
                        row,
                        row_kind,
                        criteria,
                    )
                )
    return stream.getvalue()


def _report_json(report: HistoricalExperimentReport) -> dict[str, object]:
    ranking = report.ranking
    criteria = () if ranking is None else ranking.criteria
    return {
        "report_id": str(report.report_id),
        "experiment_request_id": str(report.experiment_request_id),
        "experiment_result_id": str(report.experiment_result_id),
        "historical_fingerprint": str(report.historical_fingerprint),
        "schedule_fingerprint": str(report.schedule_fingerprint),
        "initial_state_fingerprint": str(report.initial_state_fingerprint),
        "variant_source": report.variant_source.value,
        "grid_specification_id": _optional_uuid(report.grid_specification_id),
        "grid_result_id": _optional_uuid(report.grid_result_id),
        "ranking": (
            None
            if ranking is None
            else {
                "policy_id": str(ranking.policy_id),
                "policy_fingerprint": str(ranking.policy_fingerprint),
                "comparison_result_id": str(ranking.comparison_result_id),
                "criteria": [
                    {
                        "metric": item.metric.value,
                        "direction": item.direction.value,
                    }
                    for item in criteria
                ],
                "tie_breaker": ranking.tie_breaker.value,
            }
        ),
        "variants": [
            {
                "caller_ordinal": row.caller_ordinal,
                "experiment_run_id": str(row.experiment_run_id),
                "rolling_result_id": str(row.rolling_result_id),
                "variant_id": str(row.variant_id),
                "variant_name": row.variant_name,
                "grid_ordinal": row.grid_ordinal,
                "grid_assignments": [
                    {
                        "parameter": item.parameter.value,
                        "value": _json_scalar(item.value),
                    }
                    for item in row.grid_assignments
                ],
                "rank": row.rank,
                "comparison_values": [
                    {
                        "metric": criterion.metric.value,
                        "value": _json_scalar(value),
                    }
                    for criterion, value in zip(
                        criteria, row.comparison_values, strict=True
                    )
                ],
                "metrics": {
                    field: _json_scalar(getattr(row.metrics, field))
                    for field in _METRIC_FIELDS
                },
            }
            for row in report.variants
        ],
        "metadata": _metadata_json(report.metadata),
    }


def _selection_json(
    selection: HistoricalExperimentWalkForwardSelection,
) -> dict[str, object]:
    return {
        "training_report_id": str(selection.training_report_id),
        "training_experiment_result_id": str(selection.training_experiment_result_id),
        "training_comparison_result_id": str(selection.training_comparison_result_id),
        "ranking_policy_id": str(selection.ranking_policy_id),
        "selected_rank": selection.selected_rank,
        "selected_caller_ordinal": selection.selected_caller_ordinal,
        "selected_variant_id": str(selection.selected_variant_id),
        "selected_training_run_id": str(selection.selected_training_run_id),
    }


def _csv_row(
    result,
    fold_result,
    report,
    row,
    row_kind,
    criteria,
):  # type: ignore[no-untyped-def]
    policy = result.selection_policy
    ranking_policy = policy.ranking_policy
    report_ranking = report.ranking
    report_criteria = () if report_ranking is None else report_ranking.criteria
    comparison = [
        {
            "metric": criterion.metric.value,
            "value": _json_scalar(value),
        }
        for criterion, value in zip(report_criteria, row.comparison_values, strict=True)
    ]
    comparison_lookup = {
        criterion.metric.value: value
        for criterion, value in zip(report_criteria, row.comparison_values, strict=True)
    }
    fold = fold_result.fold
    selection = fold_result.selection
    return (
        str(result.result_id),
        str(result.request_id),
        str(result.source_historical_fingerprint),
        str(policy.policy_id),
        str(ranking_policy.policy_id),
        (
            ""
            if fold_result.training_report.ranking is None
            else str(fold_result.training_report.ranking.policy_fingerprint)
        ),
        ranking_policy.tie_breaker.value,
        _evidence_json(criteria),
        _evidence_json(_metadata_json(policy.metadata)),
        _evidence_json(_metadata_json(result.metadata)),
        str(fold_result.ordinal),
        str(fold.fold_id),
        fold.training_start.isoformat(),
        fold.training_end.isoformat(),
        fold.test_start.isoformat(),
        fold.test_end.isoformat(),
        _evidence_json(
            [item.isoformat() for item in fold.training_rebalance_timestamps]
        ),
        _evidence_json([item.isoformat() for item in fold.test_rebalance_timestamps]),
        _evidence_json(_metadata_json(fold.metadata)),
        str(selection.training_report_id),
        str(selection.training_experiment_result_id),
        str(selection.training_comparison_result_id),
        str(selection.ranking_policy_id),
        str(selection.selected_rank),
        str(selection.selected_caller_ordinal),
        str(selection.selected_variant_id),
        str(selection.selected_training_run_id),
        row_kind,
        str(report.report_id),
        str(report.experiment_request_id),
        str(report.experiment_result_id),
        str(report.historical_fingerprint),
        str(report.schedule_fingerprint),
        str(report.initial_state_fingerprint),
        report.variant_source.value,
        _evidence_json(_metadata_json(report.metadata)),
        str(row.caller_ordinal),
        str(row.experiment_run_id),
        str(row.rolling_result_id),
        str(row.variant_id),
        row.variant_name,
        "" if row.rank is None else str(row.rank),
        _evidence_json(comparison),
        *(
            _csv_scalar(comparison_lookup[metric])
            if metric in comparison_lookup
            else ""
            for metric, _ in _RANKING_METRICS
        ),
        *(_csv_scalar(getattr(row.metrics, field)) for field in _METRIC_FIELDS),
    )


def _validate_result(result: HistoricalExperimentWalkForwardResult) -> None:
    if type(result) is not HistoricalExperimentWalkForwardResult:
        raise WalkForwardExperimentOutputError(
            "result must be exactly HistoricalExperimentWalkForwardResult"
        )
    try:
        result.__post_init__()
    except ValueError as error:
        raise WalkForwardExperimentOutputError(
            f"walk-forward result is inconsistent: {error}"
        ) from error


def _metadata_json(metadata) -> list[dict[str, str]]:  # type: ignore[no-untyped-def]
    return [{"key": item.key, "value": item.value} for item in metadata]


def _json_scalar(value):  # type: ignore[no-untyped-def]
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is Decimal:
        return _decimal(value)
    if type(value) is UUID:
        return str(value)
    if type(value) is datetime:
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise WalkForwardExperimentOutputError("unsupported walk-forward scalar")


def _csv_scalar(value) -> str:  # type: ignore[no-untyped-def]
    if value is None:
        return ""
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) in (int, str, UUID):
        return str(value)
    if type(value) is Decimal:
        return _decimal(value)
    raise WalkForwardExperimentOutputError("unsupported walk-forward CSV scalar")


def _evidence_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise WalkForwardExperimentOutputError(
            f"cannot serialize walk-forward CSV evidence: {error}"
        ) from error


def _optional_uuid(value: UUID | None) -> str | None:
    return None if value is None else str(value)


def _decimal(value: Decimal) -> str:
    digits = len(value.as_tuple().digits)
    with localcontext(
        Context(prec=max(digits, 1), Emax=999_999_999, Emin=-999_999_999)
    ):
        return canonical_decimal(value)
