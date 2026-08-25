"""Focused pure-Python contracts for the GUI-A2 research browser."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.cli.exceptions import HistoricalExperimentReportOutputError
from trading_bot.cli.historical_experiment_report_serialization import (
    deserialize_compact_report_json,
    serialize_compact_report_json,
)
from trading_bot.gui import (
    CompactReportResearchService,
    ResearchPageState,
    ResearchReportStatus,
    ResearchReportView,
    ResearchResultRow,
)
from trading_bot.gui.research_service import MAX_RESEARCH_ARTIFACT_BYTES

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "cli"
    / "historical-experiment-compact-report-v1-compact.json"
)


def test_gui_a2_compact_fixture_converts_deterministically() -> None:
    service = CompactReportResearchService(FIXTURE)

    first = service.get_research_state()
    second = service.get_research_state()

    assert first == second
    assert first.status is ResearchReportStatus.LOADED
    assert first.report is not None
    assert first.report.report_id == "9140ef57-0777-5434-9005-1fa20b2c681f"
    assert first.report.row_count == 4
    assert first.report.variant_source == "GRID"
    assert "SIMULATION_RETURN DESCENDING" in first.report.ranking_summary
    assert [row.rank for row in first.report.rows] == [1, 2, 3, 4]
    assert first.report.rows[0].parameter_label == (
        "WINDOW_OBSERVATION_COUNT=3, RISK_AVERSION=1"
    )
    assert first.report.rows[0].total_return == Decimal("0")
    assert first.report.rows[0].maximum_drawdown_percentage == Decimal("0")
    assert first.report.rows[0].turnover == Decimal("0.599994")
    assert first.report.rows[0].trade_count == 1
    assert first.report.rows[0].exposure is None
    assert first.report.rows[0].return_over_drawdown is None


def test_gui_a2_public_deserializer_round_trips_existing_fixture() -> None:
    payload = FIXTURE.read_text(encoding="utf-8")
    report = deserialize_compact_report_json(payload)

    assert serialize_compact_report_json(report) == payload


def test_gui_a2_malformed_and_unsupported_inputs_have_one_bounded_state(
    tmp_path: Path,
) -> None:
    malformed = tmp_path / "gui-a2-malformed-compact.json"
    malformed.write_text('{"private_parser_detail":', encoding="utf-8")
    unsupported = tmp_path / "gui-a2-unsupported-compact.json"
    tree = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tree["schema_version"] = 99
    unsupported.write_text(json.dumps(tree), encoding="utf-8")

    states = tuple(
        CompactReportResearchService(path).get_research_state()
        for path in (malformed, unsupported, tmp_path / "missing.json")
    )

    assert states[0] == states[1] == states[2]
    assert states[0].status is ResearchReportStatus.UNAVAILABLE
    assert states[0].report is None
    assert states[0].message == (
        "No supported compact historical experiment report is available."
    )
    assert "parser" not in states[0].message.casefold()


def test_gui_a2_presentation_models_reject_invalid_relationships() -> None:
    row = ResearchResultRow(
        caller_ordinal=0,
        rank=1,
        variant_label="Variant",
        parameter_label="Explicit variant",
        total_return=Decimal("0.1"),
        maximum_drawdown_percentage=Decimal("0.02"),
        turnover=Decimal("0.4"),
        trade_count=2,
        exposure=None,
        return_over_drawdown=None,
    )
    view = ResearchReportView(
        report_id="report-id",
        experiment_result_id="experiment-id",
        variant_source="EXPLICIT",
        ranking_summary="Unranked",
        metadata_summary="No report metadata",
        rows=(row,),
    )

    with pytest.raises(ValueError, match="loaded research state requires a report"):
        ResearchPageState(
            status=ResearchReportStatus.LOADED,
            message="Loaded",
            report=None,
        )
    with pytest.raises(ValueError, match="unavailable research state"):
        ResearchPageState(
            status=ResearchReportStatus.UNAVAILABLE,
            message="Unavailable",
            report=view,
        )
    with pytest.raises(TypeError, match="finite Decimal"):
        ResearchResultRow(
            caller_ordinal=0,
            rank=None,
            variant_label="Variant",
            parameter_label="Explicit variant",
            total_return=Decimal("NaN"),
            maximum_drawdown_percentage=Decimal("0"),
            turnover=Decimal("0"),
            trade_count=0,
            exposure=None,
            return_over_drawdown=None,
        )


def test_gui_a2_malformed_decimal_is_bounded_without_detail(tmp_path: Path) -> None:
    tree = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tree["report"]["variants"][0]["metrics"]["simulation_return"] = "not-a-decimal"
    payload = json.dumps(tree)
    artifact = tmp_path / "gui-a2-malformed-decimal.json"
    artifact.write_text(payload, encoding="utf-8")

    with pytest.raises(HistoricalExperimentReportOutputError):
        deserialize_compact_report_json(payload)

    state = CompactReportResearchService(artifact).get_research_state()

    assert state.status is ResearchReportStatus.UNAVAILABLE
    assert state.report is None
    assert state.message == (
        "No supported compact historical experiment report is available."
    )
    assert "decimal" not in state.message.casefold()
    assert "parser" not in state.message.casefold()


def test_gui_a2_schema_version_bool_is_rejected_and_bounded(tmp_path: Path) -> None:
    tree = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tree["schema_version"] = True
    payload = json.dumps(tree)
    artifact = tmp_path / "gui-a2-bool-schema-version.json"
    artifact.write_text(payload, encoding="utf-8")

    with pytest.raises(HistoricalExperimentReportOutputError):
        deserialize_compact_report_json(payload)

    state = CompactReportResearchService(artifact).get_research_state()
    assert state.status is ResearchReportStatus.UNAVAILABLE
    assert state.report is None
    assert state.message == (
        "No supported compact historical experiment report is available."
    )


def test_gui_a2_artifact_reader_requests_only_bound_plus_one_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_sizes: list[int] = []

    class _OversizedStream:
        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *args):  # type: ignore[no-untyped-def]
            return None

        def read(self, size: int) -> bytes:
            requested_sizes.append(size)
            return b"x" * size

    def _open(path: Path, mode: str):  # type: ignore[no-untyped-def]
        assert path == FIXTURE
        assert mode == "rb"
        return _OversizedStream()

    monkeypatch.setattr(Path, "open", _open)

    state = CompactReportResearchService(FIXTURE).get_research_state()

    assert requested_sizes == [MAX_RESEARCH_ARTIFACT_BYTES + 1]
    assert state.status is ResearchReportStatus.UNAVAILABLE
    assert state.report is None
