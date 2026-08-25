"""Deterministic JSON and CSV serialization for compact experiment reports."""

import csv
import io
import json
from decimal import Context, Decimal, localcontext
from uuid import UUID

from trading_bot.cli.exceptions import HistoricalExperimentReportOutputError
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.experiments import (
    HistoricalExperimentGridAssignment,
    HistoricalExperimentGridParameter,
    HistoricalExperimentMetrics,
    HistoricalExperimentRankingCriterion,
    HistoricalExperimentRankingDirection,
    HistoricalExperimentRankingMetric,
    HistoricalExperimentReport,
    HistoricalExperimentReportError,
    HistoricalExperimentReportRanking,
    HistoricalExperimentReportVariant,
    HistoricalExperimentReportVariantSource,
    HistoricalExperimentTieBreaker,
)
from trading_bot.portfolio import MetadataEntry

COMPACT_EXPERIMENT_REPORT_SCHEMA_VERSION = 1
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

_INTEGER_METRIC_FIELDS = frozenset(
    {
        "total_orders",
        "total_fills",
        "approved_decisions",
        "resized_decisions",
        "rejected_decisions",
        "applied_cycle_count",
        "no_action_cycle_count",
    }
)

_RANKING_METRIC_FIELDS = (
    (HistoricalExperimentRankingMetric.INITIAL_EQUITY, "initial_equity"),
    (HistoricalExperimentRankingMetric.FINAL_EQUITY, "final_equity"),
    (
        HistoricalExperimentRankingMetric.ABSOLUTE_SIMULATION_PROFIT_LOSS,
        "absolute_simulation_profit_loss",
    ),
    (HistoricalExperimentRankingMetric.SIMULATION_RETURN, "simulation_return"),
    (
        HistoricalExperimentRankingMetric.MAXIMUM_DRAWDOWN_AMOUNT,
        "maximum_drawdown_amount",
    ),
    (
        HistoricalExperimentRankingMetric.MAXIMUM_DRAWDOWN_PERCENTAGE,
        "maximum_drawdown_percentage",
    ),
    (
        HistoricalExperimentRankingMetric.SIMULATION_REALIZED_PROFIT_LOSS,
        "simulation_realized_profit_loss",
    ),
    (HistoricalExperimentRankingMetric.TOTAL_COMMISSIONS, "total_commissions"),
    (
        HistoricalExperimentRankingMetric.ADVERSE_SLIPPAGE_COST,
        "adverse_slippage_cost",
    ),
    (
        HistoricalExperimentRankingMetric.TOTAL_EXECUTION_COST,
        "total_execution_cost",
    ),
    (
        HistoricalExperimentRankingMetric.AGGREGATE_ONE_WAY_TURNOVER,
        "aggregate_one_way_turnover",
    ),
    (
        HistoricalExperimentRankingMetric.AGGREGATE_TWO_WAY_TURNOVER,
        "aggregate_two_way_turnover",
    ),
    (
        HistoricalExperimentRankingMetric.MAXIMUM_ALLOCATION_DRIFT,
        "maximum_allocation_drift",
    ),
    (HistoricalExperimentRankingMetric.TOTAL_ORDERS, "total_orders"),
    (HistoricalExperimentRankingMetric.TOTAL_FILLS, "total_fills"),
    (HistoricalExperimentRankingMetric.APPROVED_DECISIONS, "approved_decisions"),
    (HistoricalExperimentRankingMetric.RESIZED_DECISIONS, "resized_decisions"),
    (HistoricalExperimentRankingMetric.REJECTED_DECISIONS, "rejected_decisions"),
    (HistoricalExperimentRankingMetric.REJECTED_NOTIONAL, "rejected_notional"),
    (HistoricalExperimentRankingMetric.REDUCED_NOTIONAL, "reduced_notional"),
    (
        HistoricalExperimentRankingMetric.MEAN_EXPECTED_PORTFOLIO_RETURN,
        "mean_expected_portfolio_return",
    ),
    (HistoricalExperimentRankingMetric.WORST_CVAR, "worst_cvar"),
    (
        HistoricalExperimentRankingMetric.MINIMUM_TARGET_CASH_WEIGHT,
        "minimum_target_cash_weight",
    ),
    (
        HistoricalExperimentRankingMetric.MAXIMUM_TARGET_CASH_WEIGHT,
        "maximum_target_cash_weight",
    ),
    (
        HistoricalExperimentRankingMetric.APPLIED_CYCLE_COUNT,
        "applied_cycle_count",
    ),
    (
        HistoricalExperimentRankingMetric.NO_ACTION_CYCLE_COUNT,
        "no_action_cycle_count",
    ),
)

_GRID_COLUMNS = (
    (
        HistoricalExperimentGridParameter.WINDOW_OBSERVATION_COUNT,
        "grid_window_observation_count",
    ),
    (
        HistoricalExperimentGridParameter.SCENARIO_CASH_RETURN,
        "grid_scenario_cash_return",
    ),
    (
        HistoricalExperimentGridParameter.RISK_AVERSION,
        "grid_risk_aversion",
    ),
    (
        HistoricalExperimentGridParameter.PROPOSAL_CONFIDENCE,
        "grid_proposal_confidence",
    ),
    (
        HistoricalExperimentGridParameter.TRADING_ENABLED,
        "grid_trading_enabled",
    ),
)

COMPACT_EXPERIMENT_REPORT_CSV_HEADER = (
    "report_id",
    "experiment_request_id",
    "experiment_result_id",
    "historical_fingerprint",
    "schedule_fingerprint",
    "initial_state_fingerprint",
    "variant_source",
    "grid_specification_id",
    "grid_result_id",
    "ranking_policy_id",
    "ranking_policy_fingerprint",
    "comparison_result_id",
    "ranking_tie_breaker",
    "ranking_criteria",
    "report_metadata",
    "caller_ordinal",
    "experiment_run_id",
    "rolling_result_id",
    "variant_id",
    "variant_name",
    "grid_ordinal",
    "rank",
    "grid_assignments",
    *(column for _, column in _GRID_COLUMNS),
    "comparison_values",
    *(f"rank_value_{field}" for _, field in _RANKING_METRIC_FIELDS),
    *_METRIC_FIELDS,
)

if len(COMPACT_EXPERIMENT_REPORT_CSV_HEADER) != 81:
    raise RuntimeError("compact experiment report CSV header must contain 81 columns")


def build_compact_report_json(
    report: HistoricalExperimentReport,
) -> dict[str, object]:
    """Build the explicit version-one compact report JSON tree."""
    _validate_report(report)
    ranking = report.ranking
    criteria = () if ranking is None else ranking.criteria
    return {
        "schema_version": COMPACT_EXPERIMENT_REPORT_SCHEMA_VERSION,
        "report": {
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
            "metadata": [
                {"key": item.key, "value": item.value} for item in report.metadata
            ],
        },
    }


def deserialize_compact_report_json(
    payload: str | bytes,
) -> HistoricalExperimentReport:
    """Deserialize and validate one version-one compact JSON report."""
    if not isinstance(payload, str | bytes):
        raise HistoricalExperimentReportOutputError(
            "compact report JSON payload must be text or bytes"
        )
    try:
        tree = json.loads(payload)
        root = _object(tree, "root")
        _exact_keys(root, {"schema_version", "report"}, "root")
        if root["schema_version"] != COMPACT_EXPERIMENT_REPORT_SCHEMA_VERSION:
            raise ValueError("unsupported compact report schema version")
        section = _object(root["report"], "report")
        _exact_keys(
            section,
            {
                "report_id",
                "experiment_request_id",
                "experiment_result_id",
                "historical_fingerprint",
                "schedule_fingerprint",
                "initial_state_fingerprint",
                "variant_source",
                "grid_specification_id",
                "grid_result_id",
                "ranking",
                "variants",
                "metadata",
            },
            "report",
        )
        ranking = _parse_ranking(section["ranking"])
        variants = tuple(
            _parse_variant(item, ranking, index)
            for index, item in enumerate(_array(section["variants"], "report.variants"))
        )
        metadata = tuple(
            _parse_metadata(item, index)
            for index, item in enumerate(_array(section["metadata"], "report.metadata"))
        )
        return HistoricalExperimentReport(
            report_id=_uuid(section["report_id"], "report.report_id"),
            experiment_request_id=_uuid(
                section["experiment_request_id"], "report.experiment_request_id"
            ),
            experiment_result_id=_uuid(
                section["experiment_result_id"], "report.experiment_result_id"
            ),
            historical_fingerprint=_uuid(
                section["historical_fingerprint"], "report.historical_fingerprint"
            ),
            schedule_fingerprint=_uuid(
                section["schedule_fingerprint"], "report.schedule_fingerprint"
            ),
            initial_state_fingerprint=_uuid(
                section["initial_state_fingerprint"],
                "report.initial_state_fingerprint",
            ),
            variant_source=HistoricalExperimentReportVariantSource(
                section["variant_source"]
            ),
            grid_specification_id=_parse_optional_uuid(
                section["grid_specification_id"], "report.grid_specification_id"
            ),
            grid_result_id=_parse_optional_uuid(
                section["grid_result_id"], "report.grid_result_id"
            ),
            ranking=ranking,
            variants=variants,
            metadata=metadata,
        )
    except HistoricalExperimentReportOutputError:
        raise
    except (HistoricalExperimentReportError, TypeError, ValueError) as error:
        raise HistoricalExperimentReportOutputError(
            f"invalid compact report JSON: {error}"
        ) from error


def _parse_ranking(value: object) -> HistoricalExperimentReportRanking | None:
    if value is None:
        return None
    item = _object(value, "report.ranking")
    _exact_keys(
        item,
        {
            "policy_id",
            "policy_fingerprint",
            "comparison_result_id",
            "criteria",
            "tie_breaker",
        },
        "report.ranking",
    )
    criteria = []
    for index, criterion_value in enumerate(
        _array(item["criteria"], "report.ranking.criteria")
    ):
        path = f"report.ranking.criteria[{index}]"
        criterion = _object(criterion_value, path)
        _exact_keys(criterion, {"metric", "direction"}, path)
        criteria.append(
            HistoricalExperimentRankingCriterion(
                metric=HistoricalExperimentRankingMetric(criterion["metric"]),
                direction=HistoricalExperimentRankingDirection(criterion["direction"]),
            )
        )
    return HistoricalExperimentReportRanking(
        policy_id=_uuid(item["policy_id"], "report.ranking.policy_id"),
        policy_fingerprint=_uuid(
            item["policy_fingerprint"], "report.ranking.policy_fingerprint"
        ),
        comparison_result_id=_uuid(
            item["comparison_result_id"], "report.ranking.comparison_result_id"
        ),
        criteria=tuple(criteria),
        tie_breaker=HistoricalExperimentTieBreaker(item["tie_breaker"]),
    )


def _parse_variant(
    value: object,
    ranking: HistoricalExperimentReportRanking | None,
    index: int,
) -> HistoricalExperimentReportVariant:
    path = f"report.variants[{index}]"
    item = _object(value, path)
    _exact_keys(
        item,
        {
            "caller_ordinal",
            "experiment_run_id",
            "rolling_result_id",
            "variant_id",
            "variant_name",
            "grid_ordinal",
            "grid_assignments",
            "rank",
            "comparison_values",
            "metrics",
        },
        path,
    )
    assignments = tuple(
        _parse_assignment(assignment, f"{path}.grid_assignments[{ordinal}]")
        for ordinal, assignment in enumerate(
            _array(item["grid_assignments"], f"{path}.grid_assignments")
        )
    )
    comparison_items = _array(item["comparison_values"], f"{path}.comparison_values")
    criteria = () if ranking is None else ranking.criteria
    if len(comparison_items) != len(criteria):
        raise ValueError(f"{path}.comparison_values do not match ranking criteria")
    comparison_values = []
    ranking_fields = dict(_RANKING_METRIC_FIELDS)
    for ordinal, (comparison_value, criterion) in enumerate(
        zip(comparison_items, criteria, strict=True)
    ):
        comparison_path = f"{path}.comparison_values[{ordinal}]"
        comparison = _object(comparison_value, comparison_path)
        _exact_keys(comparison, {"metric", "value"}, comparison_path)
        if comparison["metric"] != criterion.metric.value:
            raise ValueError(f"{comparison_path}.metric does not match ranking")
        comparison_values.append(
            _metric_scalar(comparison["value"], ranking_fields[criterion.metric])
        )
    metrics_item = _object(item["metrics"], f"{path}.metrics")
    _exact_keys(metrics_item, set(_METRIC_FIELDS), f"{path}.metrics")
    metrics = HistoricalExperimentMetrics(
        **{
            field: _metric_scalar(metrics_item[field], field)
            for field in _METRIC_FIELDS
        }
    )
    return HistoricalExperimentReportVariant(
        caller_ordinal=_integer(item["caller_ordinal"], f"{path}.caller_ordinal"),
        experiment_run_id=_uuid(item["experiment_run_id"], f"{path}.experiment_run_id"),
        rolling_result_id=_uuid(item["rolling_result_id"], f"{path}.rolling_result_id"),
        variant_id=_uuid(item["variant_id"], f"{path}.variant_id"),
        variant_name=_text(item["variant_name"], f"{path}.variant_name"),
        grid_ordinal=_optional_integer(item["grid_ordinal"], f"{path}.grid_ordinal"),
        grid_assignments=assignments,
        rank=_optional_integer(item["rank"], f"{path}.rank"),
        comparison_values=tuple(comparison_values),
        metrics=metrics,
    )


def _parse_assignment(value: object, path: str) -> HistoricalExperimentGridAssignment:
    item = _object(value, path)
    _exact_keys(item, {"parameter", "value"}, path)
    parameter = HistoricalExperimentGridParameter(item["parameter"])
    raw = item["value"]
    if parameter is HistoricalExperimentGridParameter.WINDOW_OBSERVATION_COUNT:
        parsed = _integer(raw, f"{path}.value")
    elif parameter is HistoricalExperimentGridParameter.TRADING_ENABLED:
        if type(raw) is not bool:
            raise ValueError(f"{path}.value must be a boolean")
        parsed = raw
    elif raw is None:
        parsed = None
    else:
        parsed = _decimal_value(raw, f"{path}.value")
    return HistoricalExperimentGridAssignment(parameter=parameter, value=parsed)


def _parse_metadata(value: object, index: int) -> MetadataEntry:
    path = f"report.metadata[{index}]"
    item = _object(value, path)
    _exact_keys(item, {"key", "value"}, path)
    return MetadataEntry(
        key=_text(item["key"], f"{path}.key"),
        value=_text(item["value"], f"{path}.value"),
    )


def _metric_scalar(value: object, name: str) -> Decimal | int:
    if name in _INTEGER_METRIC_FIELDS:
        return _integer(value, name)
    return _decimal_value(value, name)


def _object(value: object, path: str) -> dict[str, object]:
    if type(value) is not dict or not all(type(key) is str for key in value):
        raise ValueError(f"{path} must be an object with string keys")
    return value


def _array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        raise ValueError(f"{path} must be an array")
    return value


def _exact_keys(value: dict[str, object], expected: set[str], path: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{path} has unsupported fields")


def _text(value: object, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{path} must be nonblank text")
    return value


def _integer(value: object, path: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{path} must be an integer")
    return value


def _optional_integer(value: object, path: str) -> int | None:
    return None if value is None else _integer(value, path)


def _decimal_value(value: object, path: str) -> Decimal:
    if type(value) is not str:
        raise ValueError(f"{path} must be canonical decimal text")
    parsed = Decimal(value)
    if not parsed.is_finite() or _decimal(parsed) != value:
        raise ValueError(f"{path} must be canonical finite decimal text")
    return parsed


def _uuid(value: object, path: str) -> UUID:
    if type(value) is not str:
        raise ValueError(f"{path} must be a UUID string")
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError(f"{path} must be a canonical UUID string")
    return parsed


def _parse_optional_uuid(value: object, path: str) -> UUID | None:
    return None if value is None else _uuid(value, path)


def serialize_compact_report_json(
    report: HistoricalExperimentReport,
    *,
    pretty: bool = False,
) -> str:
    """Serialize compact report JSON with stable byte-level settings."""
    if type(pretty) is not bool:
        raise HistoricalExperimentReportOutputError("pretty must be bool")
    tree = build_compact_report_json(report)
    try:
        if pretty:
            rendered = json.dumps(tree, ensure_ascii=False, sort_keys=True, indent=2)
        else:
            rendered = json.dumps(
                tree,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
    except (TypeError, ValueError) as error:
        raise HistoricalExperimentReportOutputError(
            f"cannot serialize compact report JSON: {error}"
        ) from error
    return rendered + "\n"


def serialize_compact_report_csv(report: HistoricalExperimentReport) -> str:
    """Serialize one caller-order CSV row per compact report variant."""
    _validate_report(report)
    ranking = report.ranking
    criteria = () if ranking is None else ranking.criteria
    ranking_criteria = [
        {"metric": item.metric.value, "direction": item.direction.value}
        for item in criteria
    ]
    report_metadata = [
        {"key": item.key, "value": item.value} for item in report.metadata
    ]
    stream = io.StringIO(newline="")
    writer = csv.writer(
        stream,
        delimiter=",",
        quoting=csv.QUOTE_MINIMAL,
        doublequote=True,
        lineterminator="\n",
    )
    writer.writerow(COMPACT_EXPERIMENT_REPORT_CSV_HEADER)
    for row in report.variants:
        assignments = [
            {
                "parameter": item.parameter.value,
                "value": _json_scalar(item.value),
            }
            for item in row.grid_assignments
        ]
        assignment_lookup = {
            item.parameter: item.value for item in row.grid_assignments
        }
        comparison = [
            {
                "metric": criterion.metric.value,
                "value": _json_scalar(value),
            }
            for criterion, value in zip(criteria, row.comparison_values, strict=True)
        ]
        comparison_lookup = {
            criterion.metric: value
            for criterion, value in zip(criteria, row.comparison_values, strict=True)
        }
        writer.writerow(
            (
                str(report.report_id),
                str(report.experiment_request_id),
                str(report.experiment_result_id),
                str(report.historical_fingerprint),
                str(report.schedule_fingerprint),
                str(report.initial_state_fingerprint),
                report.variant_source.value,
                _csv_optional(report.grid_specification_id),
                _csv_optional(report.grid_result_id),
                "" if ranking is None else str(ranking.policy_id),
                "" if ranking is None else str(ranking.policy_fingerprint),
                "" if ranking is None else str(ranking.comparison_result_id),
                "" if ranking is None else ranking.tie_breaker.value,
                _evidence_json(ranking_criteria),
                _evidence_json(report_metadata),
                str(row.caller_ordinal),
                str(row.experiment_run_id),
                str(row.rolling_result_id),
                str(row.variant_id),
                row.variant_name,
                _csv_optional(row.grid_ordinal),
                _csv_optional(row.rank),
                _evidence_json(assignments),
                *(
                    _csv_scalar(assignment_lookup.get(parameter))
                    if parameter in assignment_lookup
                    else ""
                    for parameter, _ in _GRID_COLUMNS
                ),
                _evidence_json(comparison),
                *(
                    _csv_scalar(comparison_lookup[metric])
                    if metric in comparison_lookup
                    else ""
                    for metric, _ in _RANKING_METRIC_FIELDS
                ),
                *(_csv_scalar(getattr(row.metrics, field)) for field in _METRIC_FIELDS),
            )
        )
    return stream.getvalue()


def _validate_report(report: HistoricalExperimentReport) -> None:
    if type(report) is not HistoricalExperimentReport:
        raise HistoricalExperimentReportOutputError(
            "report must be exactly HistoricalExperimentReport"
        )
    try:
        report.__post_init__()
    except HistoricalExperimentReportError as error:
        raise HistoricalExperimentReportOutputError(
            f"compact report is inconsistent: {error}"
        ) from error


def _json_scalar(value: Decimal | int | bool | None) -> str | int | bool | None:
    if value is None:
        return None
    if type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is Decimal:
        return _decimal(value)
    raise HistoricalExperimentReportOutputError(
        "compact report contains an unsupported scalar"
    )


def _csv_scalar(value: Decimal | int | bool | None) -> str:
    if value is None:
        return ""
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if type(value) is Decimal:
        return _decimal(value)
    raise HistoricalExperimentReportOutputError(
        "compact report contains an unsupported CSV scalar"
    )


def _evidence_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise HistoricalExperimentReportOutputError(
            f"cannot serialize compact report CSV evidence: {error}"
        ) from error


def _optional_uuid(value) -> str | None:  # type: ignore[no-untyped-def]
    return None if value is None else str(value)


def _csv_optional(value) -> str:  # type: ignore[no-untyped-def]
    return "" if value is None else str(value)


def _decimal(value: Decimal) -> str:
    digits = len(value.as_tuple().digits)
    with localcontext(
        Context(prec=max(digits, 1), Emax=999_999_999, Emin=-999_999_999)
    ):
        return canonical_decimal(value)
