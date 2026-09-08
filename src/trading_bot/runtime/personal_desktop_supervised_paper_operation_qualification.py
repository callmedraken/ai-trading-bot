"""Qualify one supervised Paper-v2 operation without mutating it.

The production boundary is valid only while the dedicated PD2C execution gate
remains disabled.  It enters the genuine PD2B3 preparation, retains the same
PD2A mutex scope, and projects one read-only Architecture-67 inspection into
non-authorizing readiness evidence.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import UUID

from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    PaperOperationInspectionResult,
    inspect_paper_operation_root,
)
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as execution_boundary,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadResult,
)
from trading_bot.runtime.paper_operation_execution_inputs import (
    VerifiedPaperOperationExecutionInputs,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
)
from trading_bot.runtime.personal_desktop_supervised_paper_operation_preparation import (  # noqa: E501
    _require_active_prepared_paper_operation_binding,
    _SupervisedPaperOperationPreparation,
    supervised_personal_desktop_paper_operation_preparation,
)
from trading_bot.runtime.strategy_history_seed import VerifiedStrategyHistorySeed
from trading_bot.runtime.verified_snapshot_preparation import (
    CallerAssertedNextSessionOpenReference,
    VerifiedSnapshotPaperCyclePolicies,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

_PERSONAL_DESKTOP_PAPER_V2_OPERATION_ROOT = r"F:\AITradingBot\Paper-v2\runtime"
_PRODUCTION_QUALIFICATION_ISSUER = object()
_DISPOSABLE_QUALIFICATION_AUTHORITY_ISSUER = object()


class SupervisedPaperOperationQualificationError(PersonalDesktopPaperAccountError):
    """A supervised read-only operation qualification failed closed."""


class SupervisedPaperOperationQualificationGateError(
    SupervisedPaperOperationQualificationError
):
    """Qualification requires the dedicated PD2C execution gate to be false."""


class SupervisedPaperOperationQualificationRootMismatchError(
    SupervisedPaperOperationQualificationError
):
    """The prepared operation root differs from the fixed production root."""


class SupervisedPaperOperationQualificationReconciliationError(
    SupervisedPaperOperationQualificationError
):
    """Inspection evidence does not match the active preparation."""


class SupervisedPaperOperationQualificationStatus(StrEnum):
    """Non-authorizing readiness classification for one inspection."""

    READY = "READY"
    NOT_READY = "NOT_READY"


class _PaperOperationInspector(Protocol):
    def __call__(
        self,
        operation_root: Path,
        inputs: VerifiedPaperOperationExecutionInputs,
    ) -> PaperOperationInspectionResult: ...


@dataclass(frozen=True, slots=True)
class SupervisedPaperOperationQualificationResult:
    """Immutable point-in-time evidence that grants no execution authority."""

    paper_account_id: str
    selected_snapshot_id: UUID
    plan_id: UUID
    operation_id: UUID
    application_id: UUID
    terminal_checkpoint_id: UUID
    inspection_classification: PaperOperationClassification
    inspection_diagnostic: PaperOperationInspectionCode
    qualification_status: SupervisedPaperOperationQualificationStatus
    inspector_called: bool

    def __post_init__(self) -> None:
        ready = (
            self.inspection_classification is PaperOperationClassification.PENDING
            and self.inspection_diagnostic is PaperOperationInspectionCode.PENDING
        )
        if (
            type(self.paper_account_id) is not str
            or not self.paper_account_id
            or type(self.selected_snapshot_id) is not UUID
            or type(self.plan_id) is not UUID
            or type(self.operation_id) is not UUID
            or type(self.application_id) is not UUID
            or type(self.terminal_checkpoint_id) is not UUID
            or type(self.inspection_classification) is not PaperOperationClassification
            or type(self.inspection_diagnostic) is not PaperOperationInspectionCode
            or type(self.qualification_status)
            is not SupervisedPaperOperationQualificationStatus
            or (
                self.qualification_status
                is SupervisedPaperOperationQualificationStatus.READY
            )
            != ready
            or self.inspector_called is not True
        ):
            raise ValueError(
                "supervised paper-operation qualification result is invalid"
            )


class _DisposableSupervisedPaperQualificationAuthorityForTest:
    """Private one-shot barrier for the injected disposable test seam."""

    __slots__ = ("_issuer", "_lock", "_used")

    def __init__(self, *, _issuer: object | None = None) -> None:
        if _issuer is not _DISPOSABLE_QUALIFICATION_AUTHORITY_ISSUER:
            raise TypeError(
                "disposable supervised qualification authority requires its test issuer"
            )
        self._issuer = _issuer
        self._lock = threading.Lock()
        self._used = False

    def _consume(self) -> None:
        with self._lock:
            if (
                self._issuer is not _DISPOSABLE_QUALIFICATION_AUTHORITY_ISSUER
                or self._used
            ):
                raise TypeError(
                    "disposable supervised qualification authority is invalid "
                    "or consumed"
                )
            self._used = True

    def __copy__(self) -> object:
        raise TypeError(
            "disposable supervised qualification authorities cannot be copied"
        )

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError(
            "disposable supervised qualification authorities cannot be deep-copied"
        )

    def __reduce__(self) -> object:
        raise TypeError(
            "disposable supervised qualification authorities cannot be serialized"
        )

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError(
            "disposable supervised qualification authorities cannot be pickled"
        )


def qualify_supervised_personal_desktop_paper_operation(
    authority: ValidatedProductionAuthority,
    selected_snapshot: SelectedC3SnapshotReadResult,
    *,
    history_seed: VerifiedStrategyHistorySeed,
    strategy_config: MovingAverageCrossoverConfig,
    caller_idempotency_key: UUID,
    open_reference: CallerAssertedNextSessionOpenReference,
    policies: VerifiedSnapshotPaperCyclePolicies,
    planning_at: datetime,
    submitted_at: datetime,
    filled_at: datetime,
    metadata: tuple[MetadataEntry, ...] = (),
    historical_cycle_configuration_payloads: tuple[bytes, ...] = (),
) -> SupervisedPaperOperationQualificationResult:
    """Inspect one genuine prepared operation while execution stays disabled."""

    _require_execution_gate_disabled()
    preparation = supervised_personal_desktop_paper_operation_preparation(
        authority,
        selected_snapshot,
        history_seed=history_seed,
        strategy_config=strategy_config,
        caller_idempotency_key=caller_idempotency_key,
        open_reference=open_reference,
        policies=policies,
        planning_at=planning_at,
        submitted_at=submitted_at,
        filled_at=filled_at,
        metadata=metadata,
        historical_cycle_configuration_payloads=(
            historical_cycle_configuration_payloads
        ),
    )
    return _qualify_prepared_supervised_paper_operation(
        preparation,
        inspector=inspect_paper_operation_root,
        _issuer=_PRODUCTION_QUALIFICATION_ISSUER,
    )


def _open_disposable_supervised_paper_qualification_authority_for_test() -> (
    _DisposableSupervisedPaperQualificationAuthorityForTest
):
    """Issue one explicit private authority for a disposable focused test."""

    return _DisposableSupervisedPaperQualificationAuthorityForTest(
        _issuer=_DISPOSABLE_QUALIFICATION_AUTHORITY_ISSUER
    )


def _qualify_prepared_supervised_paper_operation_for_test(
    preparation: _SupervisedPaperOperationPreparation,
    *,
    inspector: _PaperOperationInspector,
    authority: _DisposableSupervisedPaperQualificationAuthorityForTest,
) -> SupervisedPaperOperationQualificationResult:
    """Exercise qualification with explicit one-shot disposable authority."""

    if type(authority) is not _DisposableSupervisedPaperQualificationAuthorityForTest:
        raise TypeError("disposable supervised qualification authority is invalid")
    authority._consume()
    return _qualify_prepared_supervised_paper_operation(
        preparation,
        inspector=inspector,
        _issuer=_DISPOSABLE_QUALIFICATION_AUTHORITY_ISSUER,
    )


def _qualify_prepared_supervised_paper_operation(
    preparation: _SupervisedPaperOperationPreparation,
    *,
    inspector: _PaperOperationInspector,
    _issuer: object,
) -> SupervisedPaperOperationQualificationResult:
    if (
        _issuer is not _PRODUCTION_QUALIFICATION_ISSUER
        and _issuer is not _DISPOSABLE_QUALIFICATION_AUTHORITY_ISSUER
    ):
        raise TypeError("supervised qualification issuer is invalid")
    if type(preparation) is not _SupervisedPaperOperationPreparation:
        raise TypeError("supervised operation preparation type is invalid")
    if not callable(inspector):
        raise TypeError("paper-operation inspector is invalid")

    _require_execution_gate_disabled()
    with preparation as active:
        if active is not preparation:
            raise SupervisedPaperOperationQualificationError(
                "supervised operation preparation context identity changed"
            )
        _require_execution_gate_disabled()
        binding = _require_active_prepared_paper_operation_binding(active)
        if (
            type(binding.operation_root) is not str
            or binding.operation_root != _PERSONAL_DESKTOP_PAPER_V2_OPERATION_ROOT
        ):
            raise SupervisedPaperOperationQualificationRootMismatchError(
                "prepared operation root does not match the fixed Paper-v2 runtime"
            )
        inputs = binding.execution_inputs
        expected_operation_id = active.operation_id
        expected_application_id = active.application_id
        expected_terminal_checkpoint_id = inputs.verified_prior.checkpoint_id
        if (
            inputs.intent.operation_id != expected_operation_id
            or inputs.application_id != expected_application_id
        ):
            raise SupervisedPaperOperationQualificationReconciliationError(
                "prepared execution identities do not match the active preparation"
            )

        inspection = inspector(Path(binding.operation_root), inputs)
        _require_execution_gate_disabled()
        if type(inspection) is not PaperOperationInspectionResult:
            raise SupervisedPaperOperationQualificationReconciliationError(
                "Architecture-67 inspector returned an invalid result type"
            )
        if (
            inspection.operation_id != expected_operation_id
            or inspection.application_id != expected_application_id
            or inspection.terminal_checkpoint_id != expected_terminal_checkpoint_id
        ):
            raise SupervisedPaperOperationQualificationReconciliationError(
                "Architecture-67 inspection identities do not match the active "
                "preparation"
            )

        status = SupervisedPaperOperationQualificationStatus.NOT_READY
        if (
            inspection.classification is PaperOperationClassification.PENDING
            and inspection.diagnostics == (PaperOperationInspectionCode.PENDING,)
        ):
            status = SupervisedPaperOperationQualificationStatus.READY
        return SupervisedPaperOperationQualificationResult(
            paper_account_id=active.paper_account_id,
            selected_snapshot_id=active.selected_snapshot_id,
            plan_id=active.plan_id,
            operation_id=inspection.operation_id,
            application_id=inspection.application_id,
            terminal_checkpoint_id=inspection.terminal_checkpoint_id,
            inspection_classification=inspection.classification,
            inspection_diagnostic=inspection.diagnostics[0],
            qualification_status=status,
            inspector_called=True,
        )


def _require_execution_gate_disabled() -> None:
    if (
        execution_boundary.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is not False
    ):
        raise SupervisedPaperOperationQualificationGateError(
            "supervised Paper-v2 execution gate must remain disabled during "
            "qualification"
        )
