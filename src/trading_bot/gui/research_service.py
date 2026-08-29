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
    MAX_RESEARCH_METADATA_SUMMARY_CHARACTERS,
    MAX_RESEARCH_PARAMETER_LABEL_CHARACTERS,
    MAX_RESEARCH_RANKING_SUMMARY_CHARACTERS,
    MAX_RESEARCH_SOURCE_PATH_CHARACTERS,
    MAX_RESEARCH_VARIANT_LABEL_CHARACTERS,
    ResearchPageState,
    ResearchReportStatus,
    ResearchReportView,
    ResearchResultRow,
)

MAX_RESEARCH_RESULT_ROWS = 500
MAX_RESEARCH_ARTIFACT_BYTES = 10_000_000
MAX_RESEARCH_FILTER_CHARACTERS = 200
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
            if not _is_supported_local_json_path(self._artifact_path):
                return unavailable_research_state()
            payload = _read_bounded_payload(self._artifact_path)
            if len(payload) > MAX_RESEARCH_ARTIFACT_BYTES:
                return unavailable_research_state()
            report = deserialize_compact_report_json(payload)
            if len(report.variants) > MAX_RESEARCH_RESULT_ROWS:
                return unavailable_research_state()
            return ResearchPageState(
                status=ResearchReportStatus.LOADED,
                message="Compact historical experiment report loaded read-only.",
                report=_to_view(report, self._artifact_path),
            )
        except (OSError, UnicodeError, HistoricalExperimentReportOutputError):
            return unavailable_research_state()


def _is_supported_local_json_path(artifact_path: Path) -> bool:
    return (
        artifact_path.suffix.casefold() == ".json"
        and not artifact_path.anchor.startswith("\\\\")
    )


def _read_bounded_payload(artifact_path: Path) -> bytes:
    with artifact_path.open("rb") as artifact:
        return artifact.read(MAX_RESEARCH_ARTIFACT_BYTES + 1)


def unavailable_research_state() -> ResearchPageState:
    """Return the deterministic empty/unavailable Research-page state."""
    return ResearchPageState(
        status=ResearchReportStatus.UNAVAILABLE,
        message=_UNAVAILABLE_MESSAGE,
        report=None,
    )


def _to_view(
    report: HistoricalExperimentReport,
    artifact_path: Path,
) -> ResearchReportView:
    ranking = report.ranking
    if ranking is None:
        ranking_summary = "Unranked"
    else:
        criteria = ", ".join(
            f"{item.metric.value} {item.direction.value}" for item in ranking.criteria
        )
        ranking_summary = _bounded_text(
            f"Policy {ranking.policy_id}: {criteria}; "
            f"tie breaker {ranking.tie_breaker.value}",
            MAX_RESEARCH_RANKING_SUMMARY_CHARACTERS,
        )
    metadata_summary = _bounded_text(
        "; ".join(f"{item.key}={item.value}" for item in report.metadata)
        or "No report metadata",
        MAX_RESEARCH_METADATA_SUMMARY_CHARACTERS,
    )
    rows = tuple(
        ResearchResultRow(
            caller_ordinal=row.caller_ordinal,
            rank=row.rank,
            variant_label=_bounded_text(
                row.variant_name, MAX_RESEARCH_VARIANT_LABEL_CHARACTERS
            ),
            parameter_label=_bounded_text(
                _parameter_label(row.grid_assignments),
                MAX_RESEARCH_PARAMETER_LABEL_CHARACTERS,
            ),
            total_return=row.metrics.simulation_return,
            maximum_drawdown_percentage=(row.metrics.maximum_drawdown_percentage),
            aggregate_one_way_turnover=row.metrics.aggregate_one_way_turnover,
            total_fills=row.metrics.total_fills,
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
        source_path=_bounded_source_path(artifact_path),
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


def filter_research_rows(
    rows: tuple[ResearchResultRow, ...],
    query: str,
) -> tuple[ResearchResultRow, ...]:
    """Filter bounded presentation rows by variant or parameter label."""
    if type(query) is not str:
        raise TypeError("query must be a string")
    bounded_query = query[:MAX_RESEARCH_FILTER_CHARACTERS].strip().casefold()
    if not bounded_query:
        return rows
    return tuple(
        row
        for row in rows
        if bounded_query in row.variant_label.casefold()
        or bounded_query in row.parameter_label.casefold()
    )


def _bounded_source_path(artifact_path: Path) -> str:
    display = str(artifact_path.resolve(strict=False))
    if len(display) <= MAX_RESEARCH_SOURCE_PATH_CHARACTERS:
        return display
    return "…" + display[-(MAX_RESEARCH_SOURCE_PATH_CHARACTERS - 1) :]


def _bounded_text(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"
