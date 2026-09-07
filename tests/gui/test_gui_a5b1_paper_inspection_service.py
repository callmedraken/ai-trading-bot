"""Focused pure-Python tests for the GUI-A5b1 inspection adapter."""

from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    PaperOperationInspectionResult,
)
from trading_bot.gui.paper_inspection_service import PaperOperationInspectionService
from trading_bot.gui.paper_models import (
    MAX_PAPER_RECEIPT_PATH_CHARACTERS,
    PaperInspectionClassification,
    PaperInspectionDiagnostic,
    PaperPageStatus,
)
from trading_bot.runtime import VerifiedPaperOperationExecutionInputs

_OPERATION_ID = UUID("00000000-0000-0000-0000-000000000001")
_CHECKPOINT_ID = UUID("00000000-0000-0000-0000-000000000002")
_APPLICATION_ID = UUID("00000000-0000-0000-0000-000000000003")


def _verified_inputs() -> VerifiedPaperOperationExecutionInputs:
    return object.__new__(VerifiedPaperOperationExecutionInputs)


def _result(
    classification: PaperOperationClassification,
    diagnostic: PaperOperationInspectionCode,
    receipt_path: Path | None = None,
) -> PaperOperationInspectionResult:
    return PaperOperationInspectionResult(
        classification=classification,
        operation_id=_OPERATION_ID,
        terminal_checkpoint_id=_CHECKPOINT_ID,
        application_id=_APPLICATION_ID,
        receipt_path=receipt_path,
        diagnostics=(diagnostic,),
    )


@pytest.mark.parametrize(
    ("classification", "diagnostic"),
    (
        (PaperOperationClassification.PENDING, PaperOperationInspectionCode.PENDING),
        (
            PaperOperationClassification.ALREADY_APPLIED,
            PaperOperationInspectionCode.ALREADY_APPLIED,
        ),
        (
            PaperOperationClassification.CONFLICTING,
            PaperOperationInspectionCode.LINEAGE_CONFLICT,
        ),
        (
            PaperOperationClassification.BLOCKED,
            PaperOperationInspectionCode.INVALID_RECEIPT,
        ),
    ),
)
def test_adapter_preserves_classification_diagnostic_and_identities(
    monkeypatch: pytest.MonkeyPatch,
    classification: PaperOperationClassification,
    diagnostic: PaperOperationInspectionCode,
) -> None:
    operation_root = Path("explicit-operation-root")
    inputs = _verified_inputs()
    expected = _result(classification, diagnostic)
    calls: list[tuple[Path, VerifiedPaperOperationExecutionInputs]] = []

    def inspect(
        received_root: Path,
        received_inputs: VerifiedPaperOperationExecutionInputs,
    ) -> PaperOperationInspectionResult:
        calls.append((received_root, received_inputs))
        return expected

    monkeypatch.setattr(
        "trading_bot.gui.paper_inspection_service.inspect_paper_operation_root",
        inspect,
    )

    state = PaperOperationInspectionService(operation_root, inputs).get_paper_state()

    assert calls == [(operation_root, inputs)]
    assert state.status is PaperPageStatus.INSPECTED
    assert state.inspection is not None
    assert state.inspection.classification is PaperInspectionClassification(
        classification.value
    )
    assert state.inspection.diagnostic is PaperInspectionDiagnostic(diagnostic.value)
    assert state.inspection.operation_id == _OPERATION_ID
    assert state.inspection.terminal_checkpoint_id == _CHECKPOINT_ID
    assert state.inspection.application_id == _APPLICATION_ID


@pytest.mark.parametrize("diagnostic", tuple(PaperOperationInspectionCode))
def test_adapter_preserves_every_closed_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    diagnostic: PaperOperationInspectionCode,
) -> None:
    monkeypatch.setattr(
        "trading_bot.gui.paper_inspection_service.inspect_paper_operation_root",
        lambda *_: _result(PaperOperationClassification.BLOCKED, diagnostic),
    )

    state = PaperOperationInspectionService(
        Path("explicit-operation-root"), _verified_inputs()
    ).get_paper_state()

    assert state.inspection is not None
    assert state.inspection.diagnostic.value == diagnostic.value


def test_adapter_presents_optional_receipt_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path = Path("paper-operation-id") / "paper-operation-receipt-id.json"
    monkeypatch.setattr(
        "trading_bot.gui.paper_inspection_service.inspect_paper_operation_root",
        lambda *_: _result(
            PaperOperationClassification.ALREADY_APPLIED,
            PaperOperationInspectionCode.ALREADY_APPLIED,
            receipt_path,
        ),
    )

    state = PaperOperationInspectionService(
        Path("explicit-operation-root"), _verified_inputs()
    ).get_paper_state()

    assert state.inspection is not None
    assert state.inspection.receipt_path == str(receipt_path)


def test_adapter_returns_unavailable_when_receipt_path_exceeds_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "trading_bot.gui.paper_inspection_service.inspect_paper_operation_root",
        lambda *_: _result(
            PaperOperationClassification.ALREADY_APPLIED,
            PaperOperationInspectionCode.ALREADY_APPLIED,
            Path("x" * (MAX_PAPER_RECEIPT_PATH_CHARACTERS + 1)),
        ),
    )

    state = PaperOperationInspectionService(
        Path("explicit-operation-root"), _verified_inputs()
    ).get_paper_state()

    assert state.status is PaperPageStatus.UNAVAILABLE
    assert state.inspection is None
    assert len(state.message) <= MAX_PAPER_RECEIPT_PATH_CHARACTERS


def test_adapter_returns_unavailable_for_unaccepted_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "trading_bot.gui.paper_inspection_service.inspect_paper_operation_root",
        lambda *_: object(),
    )

    state = PaperOperationInspectionService(
        Path("explicit-operation-root"), _verified_inputs()
    ).get_paper_state()

    assert state.status is PaperPageStatus.UNAVAILABLE
    assert state.inspection is None


def test_adapter_sanitizes_inspection_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_exception_text = "private path and provider detail"

    def fail(*_: object) -> PaperOperationInspectionResult:
        raise RuntimeError(secret_exception_text)

    monkeypatch.setattr(
        "trading_bot.gui.paper_inspection_service.inspect_paper_operation_root",
        fail,
    )

    state = PaperOperationInspectionService(
        Path("explicit-operation-root"), _verified_inputs()
    ).get_paper_state()

    assert state.status is PaperPageStatus.UNAVAILABLE
    assert state.inspection is None
    assert secret_exception_text not in state.message
