"""Pure-Python GUI-A5a paper-operation presentation contract tests."""

from uuid import UUID

import pytest

from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
)
from trading_bot.gui import (
    MAX_PAPER_RECEIPT_PATH_CHARACTERS,
    PaperInspectionClassification,
    PaperInspectionDiagnostic,
    PaperOperationInspectionView,
    PaperPageState,
    PaperPageStatus,
    unavailable_paper_state,
)
from trading_bot.gui.mock_service import (
    MockGuiApplicationService,
    ResearchReportGuiApplicationService,
)


_OPERATION_ID = UUID("00000000-0000-0000-0000-000000000001")
_CHECKPOINT_ID = UUID("00000000-0000-0000-0000-000000000002")
_APPLICATION_ID = UUID("00000000-0000-0000-0000-000000000003")


def _inspection() -> PaperOperationInspectionView:
    return PaperOperationInspectionView(
        classification=PaperInspectionClassification.PENDING,
        operation_id=_OPERATION_ID,
        terminal_checkpoint_id=_CHECKPOINT_ID,
        application_id=_APPLICATION_ID,
        diagnostic=PaperInspectionDiagnostic.PENDING,
    )


def test_presentation_vocabulary_matches_reviewed_inspection_vocabulary() -> None:
    assert {item.value for item in PaperInspectionClassification} == {
        item.value for item in PaperOperationClassification
    }
    assert {item.value for item in PaperInspectionDiagnostic} == {
        item.value for item in PaperOperationInspectionCode
    }


def test_paper_page_state_requires_exact_payload_for_status() -> None:
    inspected = _inspection()

    assert PaperPageState(
        status=PaperPageStatus.INSPECTED,
        message="One operation inspected.",
        inspection=inspected,
    ).inspection is inspected

    with pytest.raises(ValueError, match="requires one inspection"):
        PaperPageState(
            status=PaperPageStatus.INSPECTED,
            message="Missing inspection.",
            inspection=None,
        )

    with pytest.raises(ValueError, match="must not contain"):
        PaperPageState(
            status=PaperPageStatus.UNAVAILABLE,
            message="Unavailable.",
            inspection=inspected,
        )


def test_receipt_path_is_bounded() -> None:
    PaperOperationInspectionView(
        classification=PaperInspectionClassification.ALREADY_APPLIED,
        operation_id=_OPERATION_ID,
        terminal_checkpoint_id=_CHECKPOINT_ID,
        application_id=_APPLICATION_ID,
        diagnostic=PaperInspectionDiagnostic.ALREADY_APPLIED,
        receipt_path="x" * MAX_PAPER_RECEIPT_PATH_CHARACTERS,
    )

    with pytest.raises(ValueError, match="exceeds the presentation bound"):
        PaperOperationInspectionView(
            classification=PaperInspectionClassification.ALREADY_APPLIED,
            operation_id=_OPERATION_ID,
            terminal_checkpoint_id=_CHECKPOINT_ID,
            application_id=_APPLICATION_ID,
            diagnostic=PaperInspectionDiagnostic.ALREADY_APPLIED,
            receipt_path="x" * (MAX_PAPER_RECEIPT_PATH_CHARACTERS + 1),
        )


def test_mock_service_returns_deterministic_unavailable_paper_state() -> None:
    service = MockGuiApplicationService()

    assert service.get_paper_state() == unavailable_paper_state()
    assert service.get_paper_state().status is PaperPageStatus.UNAVAILABLE


def test_research_service_composition_keeps_paper_state_unavailable(tmp_path) -> None:
    service = ResearchReportGuiApplicationService(tmp_path / "missing-report.json")

    assert service.get_paper_state() == unavailable_paper_state()


def test_public_paper_contract_is_qt_free() -> None:
    assert unavailable_paper_state().status is PaperPageStatus.UNAVAILABLE
