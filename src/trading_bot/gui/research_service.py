"""Read-only adapter from compact research artifacts to GUI presentation state."""

from decimal import Decimal
from pathlib import Path

from trading_bot.cli.exceptions import HistoricalExperimentReportOutputError
from trading_bot.cli.historical_experiment_report_serialization import (
    deserialize_compact_report_json,
)
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.experiments import (
    HistoricalExperimentGridAssignment,
    HistoricalExperimentReport,
)
from trading_bot.gui.models import (
    ResearchPageState,
    ResearchReportStatus,
    ResearchReportView,
    ResearchResultRow,
)

MAX_RESEARCH_RESULT_ROWS = 500
MAX_RESEARCH_ARTIFACT_BYTES = 10_000_000
_UNAVAILABLE_MESSAGE = "No supported compact historical experiment report is available."


class CompactReportResearchService:
    """Load one local compact-report artifact without invoking research work."""

    def __init__(self, artifact_path: Path) -> None:
        if not isinstance(artifact_path, Path):
            raise TypeError("artifact_path must be exactly pathlib.Path")
        self._artifact_path = artifact_path

    def get_research_state(self) -> ResearchPageState:
        """Return loaded presentation state or one bounded unavailable state."""
        try:
            if self._artifact_path.stat().st_size > MAX_RESEARCH_ARTIFACT_BYTES:
                return unavailable_research_state()
            report = deserialize_compact_report_json(self._artifact_path.read_bytes())
            if len(report.variants) > MAX_RESEARCH_RESULT_ROWS:
                return unavailable_research_state()
            return ResearchPageState(
                status=ResearchReportStatus.LOADED,
                message="Compact historical experiment report loaded read-only.",
                report=_to_view(report),
            )
        except (OSError, UnicodeError, HistoricalExperimentReportOutputError):
            return unavailable_research_state()


def unavailable_research_state() -> ResearchPageState:
    """Return the deterministic empty/unavailable Research-page state."""
    return ResearchPageState(
        status=ResearchReportStatus.UNAVAILABLE,
        message=_UNAVAILABLE_MESSAGE,
        report=None,
    )


def _to_view(report: HistoricalExperimentReport) -> ResearchReportView:
    ranking = report.ranking
    if ranking is None:
        ranking_summary = "Unranked"
    else:
        criteria = ", ".join(
            f"{item.metric.value} {item.direction.value}" for item in ranking.criteria
        )
        ranking_summary = (
            f"Policy {ranking.policy_id}: {criteria}; "
            f"tie breaker {ranking.tie_breaker.value}"
        )
    metadata_summary = (
        "; ".join(f"{item.key}={item.value}" for item in report.metadata)
        or "No report metadata"
    )
    rows = tuple(
        ResearchResultRow(
            caller_ordinal=row.caller_ordinal,
            rank=row.rank,
            variant_label=row.variant_name,
            parameter_label=_parameter_label(row.grid_assignments),
            total_return=row.metrics.simulation_return,
            maximum_drawdown_percentage=(row.metrics.maximum_drawdown_percentage),
            turnover=row.metrics.aggregate_one_way_turnover,
            trade_count=row.metrics.total_fills,
            exposure=None,
            return_over_drawdown=None,
        )
        for row in report.variants
    )
    return ResearchReportView(
        report_id=str(report.report_id),
        experiment_result_id=str(report.experiment_result_id),
        variant_source=report.variant_source.value,
        ranking_summary=ranking_summary,
        metadata_summary=metadata_summary,
        rows=rows,
    )


def _parameter_label(
    assignments: tuple[HistoricalExperimentGridAssignment, ...],
) -> str:
    if not assignments:
        return "Explicit variant"
    return ", ".join(
        f"{item.parameter.value}={_scalar_label(item.value)}" for item in assignments
    )


def _scalar_label(value: Decimal | int | bool | None) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    return canonical_decimal(value)
