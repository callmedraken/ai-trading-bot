"""Qt-free adaptation of one reviewed paper-operation inspection."""

from pathlib import Path

from trading_bot.cli.paper_operation_config import VerifiedPaperOperationInputs
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationInspectionResult,
    inspect_paper_operation_root,
)
from trading_bot.gui.paper_models import (
    PaperInspectionClassification,
    PaperInspectionDiagnostic,
    PaperOperationInspectionView,
    PaperPageState,
    PaperPageStatus,
)

_INSPECTED_MESSAGE = "One paper operation was inspected read-only."
_UNAVAILABLE_MESSAGE = "Paper-operation inspection is unavailable."


class PaperOperationInspectionService:
    """Present one explicit, already-verified paper-operation inspection."""

    def __init__(
        self,
        operation_root: Path,
        inputs: VerifiedPaperOperationInputs,
    ) -> None:
        self._operation_root = operation_root
        self._inputs = inputs

    def get_paper_state(self) -> PaperPageState:
        """Return one bounded inspection state without exposing failures."""
        try:
            result = inspect_paper_operation_root(
                self._operation_root,
                self._inputs,
            )
            return _adapt_inspection(result)
        except Exception:
            return PaperPageState(
                status=PaperPageStatus.UNAVAILABLE,
                message=_UNAVAILABLE_MESSAGE,
                inspection=None,
            )


def _adapt_inspection(result: PaperOperationInspectionResult) -> PaperPageState:
    if type(result) is not PaperOperationInspectionResult:
        raise TypeError("inspection result has an unsupported type")

    classification = PaperInspectionClassification(result.classification.value)
    diagnostic = PaperInspectionDiagnostic(result.diagnostics[0].value)
    receipt_path = None if result.receipt_path is None else str(result.receipt_path)

    return PaperPageState(
        status=PaperPageStatus.INSPECTED,
        message=_INSPECTED_MESSAGE,
        inspection=PaperOperationInspectionView(
            classification=classification,
            operation_id=result.operation_id,
            terminal_checkpoint_id=result.terminal_checkpoint_id,
            application_id=result.application_id,
            diagnostic=diagnostic,
            receipt_path=receipt_path,
        ),
    )
