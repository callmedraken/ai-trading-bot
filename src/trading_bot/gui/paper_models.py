"""Immutable Qt-free presentation records for paper-operation inspection."""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

MAX_PAPER_RECEIPT_PATH_CHARACTERS = 512


class PaperPageStatus(Enum):
    """Bounded availability state for the read-only Paper page."""

    INSPECTED = "inspected"
    UNAVAILABLE = "unavailable"


class PaperInspectionClassification(Enum):
    """Presentation mirror of the reviewed paper-operation classifications."""

    PENDING = "PENDING"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    CONFLICTING = "CONFLICTING"
    BLOCKED = "BLOCKED"


class PaperInspectionDiagnostic(Enum):
    """Closed presentation mirror of reviewed paper-operation diagnostics."""

    PENDING = "PENDING"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    CALLER_IDEMPOTENCY_CONFLICT = "CALLER_IDEMPOTENCY_CONFLICT"
    LINEAGE_CONFLICT = "LINEAGE_CONFLICT"
    STALE_TERMINAL_CHECKPOINT = "STALE_TERMINAL_CHECKPOINT"
    VALID_FAILED_RECEIPT = "VALID_FAILED_RECEIPT"
    FOREIGN_RECEIPT_DEPENDENCIES_UNAVAILABLE = (
        "FOREIGN_RECEIPT_DEPENDENCIES_UNAVAILABLE"
    )
    FOREIGN_TRANSITION_DEPENDENCIES_UNAVAILABLE = (
        "FOREIGN_TRANSITION_DEPENDENCIES_UNAVAILABLE"
    )
    INVALID_RECEIPT = "INVALID_RECEIPT"
    INVALID_FOREIGN_RECEIPT = "INVALID_FOREIGN_RECEIPT"
    INVALID_OPERATION_STATE = "BLOCKED_INVALID_OPERATION_STATE"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    FINALIZED_TRANSITION_WITHOUT_RECEIPT = "FINALIZED_TRANSITION_WITHOUT_RECEIPT"
    OPERATION_STAGING_EXISTS = "OPERATION_STAGING_EXISTS"
    TRANSITION_STAGING_EXISTS = "TRANSITION_STAGING_EXISTS"
    UNSAFE_OPERATION_ROOT = "UNSAFE_OPERATION_ROOT"
    ENUMERATION_LIMIT_EXCEEDED = "ENUMERATION_LIMIT_EXCEEDED"
    CASEFOLD_COLLISION = "CASEFOLD_COLLISION"
    MALFORMED_OPERATION_LAYOUT = "MALFORMED_OPERATION_LAYOUT"
    MALFORMED_TRANSITION_LAYOUT = "MALFORMED_TRANSITION_LAYOUT"
    AMBIGUOUS_OPERATION_STATE = "AMBIGUOUS_OPERATION_STATE"


def _require_message(value: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError("paper page message must be non-empty text")


@dataclass(frozen=True, slots=True)
class PaperOperationInspectionView:
    """One exact reviewed paper-operation result prepared for presentation."""

    classification: PaperInspectionClassification
    operation_id: UUID
    terminal_checkpoint_id: UUID
    application_id: UUID
    diagnostic: PaperInspectionDiagnostic
    receipt_path: str | None = None

    def __post_init__(self) -> None:
        if type(self.classification) is not PaperInspectionClassification:
            raise TypeError("classification must be a PaperInspectionClassification")
        for name in ("operation_id", "terminal_checkpoint_id", "application_id"):
            if type(getattr(self, name)) is not UUID:
                raise TypeError(f"{name} must be a UUID")
        if type(self.diagnostic) is not PaperInspectionDiagnostic:
            raise TypeError("diagnostic must be a PaperInspectionDiagnostic")
        if self.receipt_path is not None:
            if type(self.receipt_path) is not str or not self.receipt_path.strip():
                raise ValueError("receipt_path must be non-empty text or None")
            if len(self.receipt_path) > MAX_PAPER_RECEIPT_PATH_CHARACTERS:
                raise ValueError("receipt_path exceeds the presentation bound")


@dataclass(frozen=True, slots=True)
class PaperPageState:
    """One inspected paper operation or a bounded unavailable state."""

    status: PaperPageStatus
    message: str
    inspection: PaperOperationInspectionView | None

    def __post_init__(self) -> None:
        if type(self.status) is not PaperPageStatus:
            raise TypeError("status must be a PaperPageStatus")
        _require_message(self.message)
        if self.status is PaperPageStatus.INSPECTED:
            if type(self.inspection) is not PaperOperationInspectionView:
                raise ValueError("inspected paper state requires one inspection")
        elif self.inspection is not None:
            raise ValueError("unavailable paper state must not contain an inspection")


def unavailable_paper_state() -> PaperPageState:
    """Return the deterministic default paper state with no inspection connected."""
    return PaperPageState(
        status=PaperPageStatus.UNAVAILABLE,
        message="No paper-operation inspection is connected to this read-only GUI.",
        inspection=None,
    )
