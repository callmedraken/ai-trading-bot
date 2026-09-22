"""Read-only PD4-C unattended startup qualification under the PD2A mutex.

The public result is sanitized point-in-time evidence only.  It is deliberately
not registered as production provenance and cannot authorize later publication,
execution, or receipt recovery.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
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
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    IdentifiedMarketCalendar,
)
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadResult,
    require_selected_c3_snapshot_matches_authority,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperStrategyPlanArtifactBinding,
    build_manual_paper_strategy_plan,
    verify_manual_paper_strategy_plan,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexAcquisition,
    PaperAccountMutexState,
    paper_receipt_recovery_admission,
    supervised_paper_cycle_admission,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    PersonalDesktopPaperAccountReadEvidence,
    read_personal_desktop_paper_account,
    require_validated_personal_desktop_paper_account,
)
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_qualification import (
    PaperReceiptRecoveryQualificationResult,
    PaperReceiptRecoveryQualificationStatus,
    qualify_personal_desktop_paper_receipt_recovery,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation import (
    PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    create_personal_desktop_unattended_paper_invocation,
    serialize_personal_desktop_unattended_paper_invocation,
    verify_personal_desktop_unattended_paper_invocation,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageClassification,
    PersonalDesktopUnattendedInvocationStorageReadResult,
    read_personal_desktop_unattended_invocation_storage,
)
from trading_bot.runtime.strategy_history_seed import (
    VerifiedStrategyHistorySeed,
    verify_strategy_history_seed,
)
from trading_bot.runtime.verified_snapshot_preparation import (
    CallerAssertedNextSessionOpenReference,
    VerifiedSnapshotPaperCyclePolicies,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

from .personal_desktop_supervised_paper_operation_preparation import (
    PreparedPaperOperationMaterial,
    prepare_verified_paper_operation_from_account,
    reconstruct_verified_paper_operation_from_plan,
)


class PersonalDesktopUnattendedPaperStartupStatus(StrEnum):
    """Exact PD4-C startup classifications."""

    HEALTHY_NO_PENDING_INVOCATION = "HEALTHY_NO_PENDING_INVOCATION"
    READY_SAME_INVOCATION = "READY_SAME_INVOCATION"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    RECEIPT_RECOVERY_REQUIRED = "RECEIPT_RECOVERY_REQUIRED"
    BLOCKED = "BLOCKED"


class PersonalDesktopUnattendedPaperStartupDiagnostic(StrEnum):
    """Bounded public explanation without filesystem or authority material."""

    VERIFIED_ABSENT_PENDING = "VERIFIED_ABSENT_PENDING"
    VERIFIED_IDENTICAL_PENDING = "VERIFIED_IDENTICAL_PENDING"
    VERIFIED_ALREADY_APPLIED = "VERIFIED_ALREADY_APPLIED"
    VERIFIED_TERMINAL_RECEIPT_MISSING = "VERIFIED_TERMINAL_RECEIPT_MISSING"
    QUALIFICATION_BLOCKED = "QUALIFICATION_BLOCKED"


class PersonalDesktopUnattendedPaperStartupBlockedReason(StrEnum):
    """Fixed, sanitized class of a PD4-C blocked startup path."""

    PRE_RECOVERY_BLOCKED = "PRE_RECOVERY_BLOCKED"
    PRE_RECOVERY_STATUS_INVALID = "PRE_RECOVERY_STATUS_INVALID"
    PRE_RECOVERY_ACCOUNT_MISMATCH = "PRE_RECOVERY_ACCOUNT_MISMATCH"
    RECOVERY_MUTEX_MISMATCH = "RECOVERY_MUTEX_MISMATCH"
    RECOVERY_HELD_REQUALIFICATION_DRIFT = "RECOVERY_HELD_REQUALIFICATION_DRIFT"
    RECOVERY_FINAL_REQUALIFICATION_DRIFT = "RECOVERY_FINAL_REQUALIFICATION_DRIFT"
    HEALTHY_MUTEX_MISMATCH = "HEALTHY_MUTEX_MISMATCH"
    POST_LOCK_RECOVERY_MISMATCH = "POST_LOCK_RECOVERY_MISMATCH"
    POST_LOCK_ACCOUNT_MISMATCH = "POST_LOCK_ACCOUNT_MISMATCH"
    INVOCATION_STORAGE_UNSAFE = "INVOCATION_STORAGE_UNSAFE"
    INITIAL_OPERATION_INSPECTION_UNSAFE = "INITIAL_OPERATION_INSPECTION_UNSAFE"
    FINAL_ACCOUNT_DRIFT = "FINAL_ACCOUNT_DRIFT"
    FINAL_OPERATION_INSPECTION_UNSAFE = "FINAL_OPERATION_INSPECTION_UNSAFE"
    EXCEPTION_COLLAPSED = "EXCEPTION_COLLAPSED"


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedPaperStartupQualificationResult:
    """Immutable, sanitized, non-authorizing point-in-time evidence."""

    status: PersonalDesktopUnattendedPaperStartupStatus
    diagnostic: PersonalDesktopUnattendedPaperStartupDiagnostic
    paper_account_id: str | None
    selected_snapshot_id: UUID | None
    invocation_id: UUID | None
    operation_id: UUID | None
    application_id: UUID | None
    terminal_checkpoint_id: UUID | None
    storage_classification: (
        PersonalDesktopUnattendedInvocationStorageClassification | None
    )
    operation_classification: PaperOperationClassification | None
    operation_diagnostic: PaperOperationInspectionCode | None
    recovery_missing_application_id: UUID | None
    recovery_predecessor_checkpoint_id: UUID | None
    mutex_acquisition_state: PaperAccountMutexState | None
    blocked_reason: PersonalDesktopUnattendedPaperStartupBlockedReason | None = None

    def __post_init__(self) -> None:
        status = self.status
        expected_diagnostic = {
            PersonalDesktopUnattendedPaperStartupStatus.HEALTHY_NO_PENDING_INVOCATION: (
                PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_ABSENT_PENDING
            ),
            PersonalDesktopUnattendedPaperStartupStatus.READY_SAME_INVOCATION: (
                PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_IDENTICAL_PENDING
            ),
            PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED: (
                PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_ALREADY_APPLIED
            ),
            PersonalDesktopUnattendedPaperStartupStatus.RECEIPT_RECOVERY_REQUIRED: (
                PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_TERMINAL_RECEIPT_MISSING
            ),
            PersonalDesktopUnattendedPaperStartupStatus.BLOCKED: (
                PersonalDesktopUnattendedPaperStartupDiagnostic.QUALIFICATION_BLOCKED
            ),
        }.get(status)
        healthy = status in {
            PersonalDesktopUnattendedPaperStartupStatus.HEALTHY_NO_PENDING_INVOCATION,
            PersonalDesktopUnattendedPaperStartupStatus.READY_SAME_INVOCATION,
            PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED,
        }
        recovery = (
            status
            is PersonalDesktopUnattendedPaperStartupStatus.RECEIPT_RECOVERY_REQUIRED
        )
        uuid_fields = (
            self.selected_snapshot_id,
            self.invocation_id,
            self.operation_id,
            self.application_id,
            self.terminal_checkpoint_id,
            self.recovery_missing_application_id,
            self.recovery_predecessor_checkpoint_id,
        )
        if (
            type(status) is not PersonalDesktopUnattendedPaperStartupStatus
            or type(self.diagnostic)
            is not PersonalDesktopUnattendedPaperStartupDiagnostic
            or self.diagnostic is not expected_diagnostic
            or (
                status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
                and type(self.blocked_reason)
                is not PersonalDesktopUnattendedPaperStartupBlockedReason
            )
            or (
                status is not PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
                and self.blocked_reason is not None
            )
            or (
                self.paper_account_id is not None
                and type(self.paper_account_id) is not str
            )
            or any(
                value is not None and type(value) is not UUID for value in uuid_fields
            )
            or (
                self.storage_classification is not None
                and type(self.storage_classification)
                is not PersonalDesktopUnattendedInvocationStorageClassification
            )
            or (
                self.operation_classification is not None
                and type(self.operation_classification)
                is not PaperOperationClassification
            )
            or (
                self.operation_diagnostic is not None
                and type(self.operation_diagnostic) is not PaperOperationInspectionCode
            )
            or (
                self.mutex_acquisition_state is not None
                and type(self.mutex_acquisition_state) is not PaperAccountMutexState
            )
            or (
                healthy
                and any(
                    value is None
                    for value in (
                        self.paper_account_id,
                        self.selected_snapshot_id,
                        self.invocation_id,
                        self.operation_id,
                        self.application_id,
                        self.terminal_checkpoint_id,
                        self.storage_classification,
                        self.operation_classification,
                        self.operation_diagnostic,
                        self.mutex_acquisition_state,
                    )
                )
            )
            or (healthy and any(value is not None for value in uuid_fields[-2:]))
            or (
                recovery
                and (
                    self.paper_account_id is None
                    or self.terminal_checkpoint_id is None
                    or self.recovery_missing_application_id is None
                    or self.recovery_predecessor_checkpoint_id is None
                    or self.mutex_acquisition_state is None
                    or any(value is not None for value in uuid_fields[:4])
                    or self.storage_classification is not None
                    or self.operation_classification is not None
                    or self.operation_diagnostic is not None
                )
            )
        ):
            raise ValueError("unattended startup qualification result is invalid")


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedPaperPlanningInputs:
    """Immutable semantic inputs shared by PD4-C and PD4-D composition."""

    history_seed: VerifiedStrategyHistorySeed
    strategy_config: MovingAverageCrossoverConfig
    caller_idempotency_key: UUID
    open_reference: CallerAssertedNextSessionOpenReference
    policies: VerifiedSnapshotPaperCyclePolicies
    planning_at: datetime
    submitted_at: datetime
    filled_at: datetime
    metadata: tuple[MetadataEntry, ...]
    historical_configurations: tuple[bytes, ...]


class _Admission(Protocol):
    acquisition: PaperAccountMutexAcquisition | None

    def __enter__(self) -> _Admission: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> object: ...


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedPaperStartupDependencies:
    """Explicit read/reconciliation seams shared by PD4-C and PD4-D."""

    validate_c1: Callable[[object], object]
    match_snapshot: Callable[[object, object, object], None]
    qualify_recovery: Callable[
        [object, tuple[bytes, ...]], PaperReceiptRecoveryQualificationResult
    ]
    read_account: Callable[[object, tuple[bytes, ...]], object]
    require_account: Callable[[object], PersonalDesktopPaperAccountReadEvidence]
    admit_healthy: Callable[[object], _Admission]
    admit_recovery: Callable[[PaperReceiptRecoveryQualificationResult], _Admission]
    build_material: Callable[
        [
            PersonalDesktopPaperAccountReadEvidence,
            SelectedC3SnapshotReadResult,
            PersonalDesktopUnattendedPaperPlanningInputs,
            IdentifiedMarketCalendar,
        ],
        PreparedPaperOperationMaterial,
    ]
    read_storage: Callable[
        [object, PersonalDesktopUnattendedPaperInvocationArtifactBinding],
        PersonalDesktopUnattendedInvocationStorageReadResult,
    ]
    inspect_operation: Callable[[Path, object], PaperOperationInspectionResult]
    gate_state: Callable[[], tuple[bool, bool, bool, bool, bool, bool]]


@dataclass(frozen=True, slots=True)
class _HeldStartupReconciliation:
    """Mutex-scoped reconciliation state; never reusable execution authority."""

    public_result: PersonalDesktopUnattendedPaperStartupQualificationResult | None
    captured_gate_state: tuple[bool, bool, bool, bool, bool, bool]
    c1: object | None = None
    paper_account_id: str | None = None
    post_lock_account: PersonalDesktopPaperAccountReadEvidence | None = None
    material: PreparedPaperOperationMaterial | None = None
    expected_invocation: (
        PersonalDesktopUnattendedPaperInvocationArtifactBinding | None
    ) = None
    storage: PersonalDesktopUnattendedInvocationStorageReadResult | None = None
    inspection: PaperOperationInspectionResult | None = None
    acquisition: PaperAccountMutexAcquisition | None = None


class PersonalDesktopUnattendedPaperStartupReconciliation(Protocol):
    """Read-only shape shared only while the PD2A scope remains active."""

    public_result: PersonalDesktopUnattendedPaperStartupQualificationResult | None
    captured_gate_state: tuple[bool, bool, bool, bool, bool, bool]
    c1: object | None
    paper_account_id: str | None
    post_lock_account: PersonalDesktopPaperAccountReadEvidence | None
    material: PreparedPaperOperationMaterial | None
    expected_invocation: PersonalDesktopUnattendedPaperInvocationArtifactBinding | None
    storage: PersonalDesktopUnattendedInvocationStorageReadResult | None
    inspection: PaperOperationInspectionResult | None
    acquisition: PaperAccountMutexAcquisition | None


class PersonalDesktopUnattendedPaperStartupReconciliationScope(Protocol):
    """Context-bound PD4-C reconciliation seam with no execution capability."""

    def __enter__(self) -> PersonalDesktopUnattendedPaperStartupReconciliation: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> object: ...


class _UnattendedPaperStartupReconciliationScope:
    """Enter PD4-C reconciliation and retain the same PD2A mutex when healthy."""

    __slots__ = (
        "_allowed_gate_states",
        "_authority",
        "_calendar",
        "_dependencies",
        "_entered",
        "_exit_stack",
        "_inputs",
        "_selected",
    )

    def __init__(
        self,
        authority: object,
        selected: SelectedC3SnapshotReadResult,
        inputs: PersonalDesktopUnattendedPaperPlanningInputs,
        calendar: IdentifiedMarketCalendar,
        dependencies: PersonalDesktopUnattendedPaperStartupDependencies,
        *,
        allowed_gate_states: frozenset[tuple[bool, bool, bool, bool, bool, bool]],
    ) -> None:
        self._authority = authority
        self._selected = selected
        self._inputs = inputs
        self._calendar = calendar
        self._dependencies = dependencies
        self._allowed_gate_states = allowed_gate_states
        self._exit_stack: ExitStack | None = None
        self._entered = False

    def __enter__(self) -> PersonalDesktopUnattendedPaperStartupReconciliation:
        if self._entered:
            raise RuntimeError("unattended startup reconciliation scope is one-shot")
        self._entered = True
        stack = ExitStack()
        self._exit_stack = stack
        try:
            dependencies = self._dependencies
            selected = self._selected
            inputs = self._inputs
            captured = _capture_gate_state(dependencies, self._allowed_gate_states)
            c1 = dependencies.validate_c1(self._authority)
            if type(selected) is not SelectedC3SnapshotReadResult:
                raise TypeError("selected snapshot must be an exact P2 result")
            dependencies.match_snapshot(selected.permit, selected.audit, c1)
            pre_recovery = dependencies.qualify_recovery(
                c1, inputs.historical_configurations
            )
            if type(pre_recovery) is not PaperReceiptRecoveryQualificationResult:
                raise TypeError("recovery qualification result type is invalid")
            if pre_recovery.status is PaperReceiptRecoveryQualificationStatus.BLOCKED:
                return _HeldStartupReconciliation(
                    _blocked_result(
                        PersonalDesktopUnattendedPaperStartupBlockedReason.PRE_RECOVERY_BLOCKED
                    ),
                    captured,
                )
            if (
                pre_recovery.status
                is PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
            ):
                return self._enter_recovery(stack, captured, c1, pre_recovery)
            if (
                pre_recovery.status
                is not PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED
            ):
                return _HeldStartupReconciliation(
                    _blocked_result(
                        PersonalDesktopUnattendedPaperStartupBlockedReason.PRE_RECOVERY_STATUS_INVALID
                    ),
                    captured,
                )
            return self._enter_healthy(stack, captured, c1, pre_recovery)
        except BaseException:
            stack.close()
            self._exit_stack = None
            raise

    def _enter_recovery(
        self,
        stack: ExitStack,
        captured: tuple[bool, bool, bool, bool, bool, bool],
        c1: object,
        pre_recovery: PaperReceiptRecoveryQualificationResult,
    ) -> PersonalDesktopUnattendedPaperStartupReconciliation:
        dependencies = self._dependencies
        admission = dependencies.admit_recovery(pre_recovery)
        held = stack.enter_context(admission)
        acquisition = _require_acquisition(held)
        if (
            acquisition.state is not PaperAccountMutexState.OWNED
            or acquisition.paper_account_id != pre_recovery.paper_account_id
        ):
            return _HeldStartupReconciliation(
                _blocked_result(
                    PersonalDesktopUnattendedPaperStartupBlockedReason.RECOVERY_MUTEX_MISMATCH,
                    mutex_state=acquisition.state,
                ),
                captured,
            )
        revalidate_personal_desktop_unattended_paper_startup_state(
            c1, self._selected, captured, dependencies
        )
        held_recovery = dependencies.qualify_recovery(
            c1, self._inputs.historical_configurations
        )
        if not _same_exact_recovery_required(pre_recovery, held_recovery):
            return _HeldStartupReconciliation(
                _blocked_result(
                    PersonalDesktopUnattendedPaperStartupBlockedReason.RECOVERY_HELD_REQUALIFICATION_DRIFT,
                    mutex_state=acquisition.state,
                ),
                captured,
            )
        revalidate_personal_desktop_unattended_paper_startup_state(
            c1, self._selected, captured, dependencies
        )
        final_recovery = dependencies.qualify_recovery(
            c1, self._inputs.historical_configurations
        )
        if not _same_exact_recovery_required(held_recovery, final_recovery):
            return _HeldStartupReconciliation(
                _blocked_result(
                    PersonalDesktopUnattendedPaperStartupBlockedReason.RECOVERY_FINAL_REQUALIFICATION_DRIFT,
                    mutex_state=acquisition.state,
                ),
                captured,
            )
        revalidate_personal_desktop_unattended_paper_startup_state(
            c1, self._selected, captured, dependencies
        )
        return _HeldStartupReconciliation(
            _recovery_result(final_recovery, acquisition.state), captured
        )

    def _enter_healthy(
        self,
        stack: ExitStack,
        captured: tuple[bool, bool, bool, bool, bool, bool],
        c1: object,
        pre_recovery: PaperReceiptRecoveryQualificationResult,
    ) -> PersonalDesktopUnattendedPaperStartupReconciliation:
        dependencies = self._dependencies
        inputs = self._inputs
        selected = self._selected
        pre_account = dependencies.read_account(c1, inputs.historical_configurations)
        pre_evidence = dependencies.require_account(pre_account)
        pre_account_id = pre_evidence.anchor.paper_account_id
        if pre_recovery.paper_account_id != pre_account_id:
            return _HeldStartupReconciliation(
                _blocked_result(
                    PersonalDesktopUnattendedPaperStartupBlockedReason.PRE_RECOVERY_ACCOUNT_MISMATCH
                ),
                captured,
            )
        admission = dependencies.admit_healthy(pre_account)
        held = stack.enter_context(admission)
        acquisition = _require_acquisition(held)
        if (
            acquisition.state is not PaperAccountMutexState.OWNED
            or acquisition.paper_account_id != pre_account_id
        ):
            return _HeldStartupReconciliation(
                _blocked_result(
                    PersonalDesktopUnattendedPaperStartupBlockedReason.HEALTHY_MUTEX_MISMATCH,
                    mutex_state=acquisition.state,
                ),
                captured,
            )
        revalidate_personal_desktop_unattended_paper_startup_state(
            c1, selected, captured, dependencies
        )
        post_recovery = dependencies.qualify_recovery(
            c1, inputs.historical_configurations
        )
        if (
            type(post_recovery) is not PaperReceiptRecoveryQualificationResult
            or post_recovery.status
            is not PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED
            or post_recovery.paper_account_id != pre_account_id
        ):
            return _HeldStartupReconciliation(
                _blocked_result(
                    PersonalDesktopUnattendedPaperStartupBlockedReason.POST_LOCK_RECOVERY_MISMATCH,
                    mutex_state=acquisition.state,
                ),
                captured,
            )
        post_account = dependencies.read_account(c1, inputs.historical_configurations)
        post_evidence = dependencies.require_account(post_account)
        if post_evidence.anchor.paper_account_id != pre_account_id:
            return _HeldStartupReconciliation(
                _blocked_result(
                    PersonalDesktopUnattendedPaperStartupBlockedReason.POST_LOCK_ACCOUNT_MISMATCH,
                    mutex_state=acquisition.state,
                ),
                captured,
            )
        material = dependencies.build_material(
            post_evidence, selected, inputs, self._calendar
        )
        expected = _expected_invocation(material, self._calendar)
        storage = dependencies.read_storage(c1, expected)
        if not is_safe_personal_desktop_unattended_invocation_storage_result(
            storage, expected.invocation.invocation_id
        ):
            return _HeldStartupReconciliation(
                _blocked_result(
                    PersonalDesktopUnattendedPaperStartupBlockedReason.INVOCATION_STORAGE_UNSAFE,
                    paper_account_id=pre_account_id,
                    selected_snapshot_id=selected.audit.snapshot_id,
                    invocation_id=expected.invocation.invocation_id,
                    storage_classification=_storage_classification(storage),
                    mutex_state=acquisition.state,
                ),
                captured,
            )
        inspection = dependencies.inspect_operation(
            Path(PERSONAL_DESKTOP_PAPER_V2_RUNTIME), material.execution_inputs
        )
        if not is_safe_prepared_paper_operation_inspection(inspection, material):
            return _HeldStartupReconciliation(
                _blocked_from_healthy(
                    PersonalDesktopUnattendedPaperStartupBlockedReason.INITIAL_OPERATION_INSPECTION_UNSAFE,
                    pre_account_id,
                    selected,
                    expected,
                    material,
                    storage,
                    inspection,
                    acquisition,
                ),
                captured,
            )
        return _HeldStartupReconciliation(
            None,
            captured,
            c1,
            pre_account_id,
            post_evidence,
            material,
            expected,
            storage,
            inspection,
            acquisition,
        )

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        stack, self._exit_stack = self._exit_stack, None
        if stack is None:
            raise RuntimeError("unattended startup reconciliation scope is not active")
        return stack.__exit__(exc_type, exc, traceback)


def personal_desktop_unattended_paper_startup_reconciliation_scope(
    authority: object,
    selected: SelectedC3SnapshotReadResult,
    inputs: PersonalDesktopUnattendedPaperPlanningInputs,
    calendar: IdentifiedMarketCalendar,
    dependencies: PersonalDesktopUnattendedPaperStartupDependencies,
    *,
    allowed_gate_states: frozenset[tuple[bool, bool, bool, bool, bool, bool]],
) -> PersonalDesktopUnattendedPaperStartupReconciliationScope:
    """Create the context-bound shared reconciliation seam without authority."""

    return _UnattendedPaperStartupReconciliationScope(
        authority,
        selected,
        inputs,
        calendar,
        dependencies,
        allowed_gate_states=allowed_gate_states,
    )


class _DisposableStartupQualificationAuthority:
    """One-shot holder for bounded injected read-only test seams."""

    __slots__ = ("dependencies", "used")

    def __init__(
        self, dependencies: PersonalDesktopUnattendedPaperStartupDependencies
    ) -> None:
        self.dependencies = dependencies
        self.used = False

    def __copy__(self) -> object:
        raise TypeError("disposable startup qualification authority cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("disposable startup qualification authority cannot be copied")

    def __reduce__(self) -> object:
        raise TypeError(
            "disposable startup qualification authority cannot be serialized"
        )


def qualify_personal_desktop_unattended_paper_startup(
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
) -> PersonalDesktopUnattendedPaperStartupQualificationResult:
    """Reconcile one production wakeup without opening any effect boundary."""

    inputs = PersonalDesktopUnattendedPaperPlanningInputs(
        history_seed,
        strategy_config,
        caller_idempotency_key,
        open_reference,
        policies,
        planning_at,
        submitted_at,
        filled_at,
        metadata,
        historical_cycle_configuration_payloads,
    )
    calendar = BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())
    return _qualify_startup(
        authority,
        selected_snapshot,
        inputs,
        calendar,
        personal_desktop_unattended_paper_startup_production_dependencies(),
    )


def qualify_personal_desktop_unattended_paper_startup_from_verified_plan(
    authority: ValidatedProductionAuthority,
    selected_snapshot: SelectedC3SnapshotReadResult,
    verified_plan: ManualPaperStrategyPlanArtifactBinding,
    *,
    historical_cycle_configuration_payloads: tuple[bytes, ...] = (),
) -> PersonalDesktopUnattendedPaperStartupQualificationResult:
    """Reconcile an exact completed G3 plan without reevaluating its strategy."""

    authority = require_validated_production_authority(authority)
    calendar = BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())
    inputs = personal_desktop_unattended_paper_planning_inputs_from_verified_plan(
        selected_snapshot,
        verified_plan,
        historical_cycle_configuration_payloads,
        calendar,
    )
    dependencies = personal_desktop_unattended_paper_startup_production_dependencies()

    def reconstruct(
        account: PersonalDesktopPaperAccountReadEvidence,
        selected: SelectedC3SnapshotReadResult,
        unused: PersonalDesktopUnattendedPaperPlanningInputs,
        current_calendar: IdentifiedMarketCalendar,
    ) -> PreparedPaperOperationMaterial:
        del unused
        return reconstruct_verified_paper_operation_from_plan(
            account, selected, verified_plan, current_calendar
        )

    dependencies = PersonalDesktopUnattendedPaperStartupDependencies(
        dependencies.validate_c1,
        dependencies.match_snapshot,
        dependencies.qualify_recovery,
        dependencies.read_account,
        dependencies.require_account,
        dependencies.admit_healthy,
        dependencies.admit_recovery,
        reconstruct,
        dependencies.read_storage,
        dependencies.inspect_operation,
        dependencies.gate_state,
    )
    return _qualify_startup(
        authority,
        selected_snapshot,
        inputs,
        calendar,
        dependencies,
    )


def personal_desktop_unattended_paper_planning_inputs_from_verified_plan(
    selected_snapshot: SelectedC3SnapshotReadResult,
    verified_plan: ManualPaperStrategyPlanArtifactBinding,
    historical_configurations: tuple[bytes, ...],
    calendar: IdentifiedMarketCalendar,
) -> PersonalDesktopUnattendedPaperPlanningInputs:
    if (
        type(selected_snapshot) is not SelectedC3SnapshotReadResult
        or type(verified_plan) is not ManualPaperStrategyPlanArtifactBinding
    ):
        raise TypeError("verified-plan startup evidence is invalid")
    replayed = verify_manual_paper_strategy_plan(
        verified_plan.artifact_bytes,
        calendar,
        expected_sha256=verified_plan.artifact_sha256,
        expected_byte_length=verified_plan.artifact_byte_length,
        expected_checkpointed_request=verified_plan.checkpointed_request,
    )
    if replayed != verified_plan:
        raise ValueError("verified plan differs from exact replay")
    plan = verified_plan.plan
    request = plan.request_core
    if len(request.open_references) != 1:
        raise ValueError("verified plan must contain one exact open reference")
    snapshot = selected_snapshot.verification.snapshot
    if snapshot is None or len(snapshot.request.symbols) != 1:
        raise ValueError("selected snapshot evidence is incomplete")
    history = verify_strategy_history_seed(
        plan.history_seed_artifact,
        expected_symbol=snapshot.request.symbols[0],
        target_session=snapshot.target_session,
        strategy_config=plan.strategy_config,
        calendar=calendar,
    )
    return PersonalDesktopUnattendedPaperPlanningInputs(
        history,
        plan.strategy_config,
        UUID(plan.caller_idempotency_key),
        request.open_references[0],
        request.policies,
        request.planning_at,
        request.submitted_at,
        request.filled_at,
        request.metadata,
        tuple(historical_configurations),
    )


# Preserve the established internal test seam while the public PD4-D verified-plan
# wrapper uses the explicit shared name above.
_planning_inputs_from_verified_plan = (
    personal_desktop_unattended_paper_planning_inputs_from_verified_plan
)


def _create_disposable_startup_qualification_authority_for_test(
    dependencies: PersonalDesktopUnattendedPaperStartupDependencies,
) -> _DisposableStartupQualificationAuthority:
    """Create one disposable read-only seam without production provenance."""

    if type(dependencies) is not PersonalDesktopUnattendedPaperStartupDependencies:
        raise TypeError("disposable startup qualification dependencies are invalid")
    return _DisposableStartupQualificationAuthority(dependencies)


def _qualify_personal_desktop_unattended_paper_startup_for_test(
    disposable: _DisposableStartupQualificationAuthority,
    authority: object,
    selected_snapshot: SelectedC3SnapshotReadResult,
    inputs: PersonalDesktopUnattendedPaperPlanningInputs,
    calendar: IdentifiedMarketCalendar,
) -> PersonalDesktopUnattendedPaperStartupQualificationResult:
    """Consume exactly one injected qualification authority for focused tests."""

    if (
        type(disposable) is not _DisposableStartupQualificationAuthority
        or disposable.used
    ):
        raise TypeError(
            "disposable startup qualification authority is invalid or spent"
        )
    disposable.used = True
    return _qualify_startup(
        authority,
        selected_snapshot,
        inputs,
        calendar,
        disposable.dependencies,
    )


def personal_desktop_unattended_paper_startup_production_dependencies() -> (
    PersonalDesktopUnattendedPaperStartupDependencies
):
    """Bind the source-owned read-only production reconciliation seams."""

    def qualify(authority: object, configurations: tuple[bytes, ...]):
        return qualify_personal_desktop_paper_receipt_recovery(
            authority,  # type: ignore[arg-type]
            historical_cycle_configuration_payloads=configurations,
        )

    def read(authority: object, configurations: tuple[bytes, ...]):
        return read_personal_desktop_paper_account(
            authority,  # type: ignore[arg-type]
            historical_cycle_configuration_payloads=configurations,
        )

    def build(
        account: PersonalDesktopPaperAccountReadEvidence,
        selected: SelectedC3SnapshotReadResult,
        inputs: PersonalDesktopUnattendedPaperPlanningInputs,
        calendar: IdentifiedMarketCalendar,
    ) -> PreparedPaperOperationMaterial:
        return prepare_verified_paper_operation_from_account(
            account,
            selected,
            history_seed=inputs.history_seed,
            strategy_config=inputs.strategy_config,
            caller_idempotency_key=inputs.caller_idempotency_key,
            open_reference=inputs.open_reference,
            policies=inputs.policies,
            planning_at=inputs.planning_at,
            submitted_at=inputs.submitted_at,
            filled_at=inputs.filled_at,
            metadata=inputs.metadata,
            build_plan=build_manual_paper_strategy_plan,
            verify_plan=verify_manual_paper_strategy_plan,
            calendar=calendar,
        )

    return PersonalDesktopUnattendedPaperStartupDependencies(
        validate_c1=require_validated_production_authority,
        match_snapshot=require_selected_c3_snapshot_matches_authority,
        qualify_recovery=qualify,
        read_account=read,
        require_account=require_validated_personal_desktop_paper_account,
        admit_healthy=supervised_paper_cycle_admission,
        admit_recovery=paper_receipt_recovery_admission,
        build_material=build,
        read_storage=read_personal_desktop_unattended_invocation_storage,
        inspect_operation=inspect_paper_operation_root,
        gate_state=_gate_state,
    )


def _qualify_startup(
    authority: object,
    selected: SelectedC3SnapshotReadResult,
    inputs: PersonalDesktopUnattendedPaperPlanningInputs,
    calendar: IdentifiedMarketCalendar,
    dependencies: PersonalDesktopUnattendedPaperStartupDependencies,
) -> PersonalDesktopUnattendedPaperStartupQualificationResult:
    try:
        scope = personal_desktop_unattended_paper_startup_reconciliation_scope(
            authority,
            selected,
            inputs,
            calendar,
            dependencies,
            allowed_gate_states=frozenset({(False, False, False, False, False, False)}),
        )
        with scope as reconciliation:
            if reconciliation.public_result is not None:
                return reconciliation.public_result
            c1 = reconciliation.c1
            post_evidence = reconciliation.post_lock_account
            material = reconciliation.material
            expected = reconciliation.expected_invocation
            storage = reconciliation.storage
            inspection = reconciliation.inspection
            acquisition = reconciliation.acquisition
            paper_account_id = reconciliation.paper_account_id
            if (
                c1 is None
                or post_evidence is None
                or material is None
                or expected is None
                or storage is None
                or inspection is None
                or acquisition is None
                or paper_account_id is None
            ):
                raise TypeError("held startup reconciliation is incomplete")
            revalidate_personal_desktop_unattended_paper_startup_state(
                c1,
                selected,
                reconciliation.captured_gate_state,
                dependencies,
            )
            final_account = dependencies.read_account(
                c1, inputs.historical_configurations
            )
            final_evidence = dependencies.require_account(final_account)
            if final_evidence != post_evidence:
                return _blocked_from_healthy(
                    PersonalDesktopUnattendedPaperStartupBlockedReason.FINAL_ACCOUNT_DRIFT,
                    paper_account_id,
                    selected,
                    expected,
                    material,
                    storage,
                    inspection,
                    acquisition,
                )
            final_inspection = dependencies.inspect_operation(
                Path(PERSONAL_DESKTOP_PAPER_V2_RUNTIME), material.execution_inputs
            )
            if (
                final_inspection != inspection
                or not is_safe_prepared_paper_operation_inspection(
                    final_inspection, material
                )
            ):
                return _blocked_from_healthy(
                    PersonalDesktopUnattendedPaperStartupBlockedReason.FINAL_OPERATION_INSPECTION_UNSAFE,
                    paper_account_id,
                    selected,
                    expected,
                    material,
                    storage,
                    final_inspection,
                    acquisition,
                )
            revalidate_personal_desktop_unattended_paper_startup_state(
                c1,
                selected,
                reconciliation.captured_gate_state,
                dependencies,
            )
            return _healthy_result(
                paper_account_id,
                selected,
                expected,
                material,
                storage,
                final_inspection,
                acquisition.state,
            )
    except Exception:
        return _blocked_result(
            PersonalDesktopUnattendedPaperStartupBlockedReason.EXCEPTION_COLLAPSED
        )


def _expected_invocation(
    material: PreparedPaperOperationMaterial,
    calendar: IdentifiedMarketCalendar,
) -> PersonalDesktopUnattendedPaperInvocationArtifactBinding:
    if type(material) is not PreparedPaperOperationMaterial:
        raise TypeError("prepared paper operation material is invalid")
    invocation = create_personal_desktop_unattended_paper_invocation(
        material.plan_binding, calendar
    )
    payload = serialize_personal_desktop_unattended_paper_invocation(invocation)
    replayed = verify_personal_desktop_unattended_paper_invocation(
        payload,
        calendar,
        expected_invocation_id=invocation.invocation_id,
    )
    if (
        replayed.invocation != invocation
        or replayed.replayed_plan != material.plan_binding
        or replayed.artifact_bytes != payload
    ):
        raise ValueError("unattended invocation detached replay differs")
    return replayed


def _capture_gate_state(
    dependencies: PersonalDesktopUnattendedPaperStartupDependencies,
    allowed_gate_states: frozenset[tuple[bool, bool, bool, bool, bool, bool]],
) -> tuple[bool, bool, bool, bool, bool, bool]:
    state = dependencies.gate_state()
    if (
        type(state) is not tuple
        or len(state) != 6
        or any(type(value) is not bool for value in state)
        or state not in allowed_gate_states
    ):
        raise RuntimeError("Paper-v2 effect-gate state is invalid")
    return state


def revalidate_personal_desktop_unattended_paper_startup_state(
    c1: object,
    selected: SelectedC3SnapshotReadResult,
    captured_gate_state: tuple[bool, bool, bool, bool, bool, bool],
    dependencies: PersonalDesktopUnattendedPaperStartupDependencies,
) -> None:
    """Revalidate exact C1/P2 and captured six-gate state under the mutex."""

    try:
        _capture_gate_state(dependencies, frozenset({captured_gate_state}))
    except RuntimeError as error:
        raise RuntimeError(
            "Paper-v2 effect-gate state changed during reconciliation"
        ) from error
    validated = dependencies.validate_c1(c1)
    dependencies.match_snapshot(selected.permit, selected.audit, validated)


def _require_acquisition(admission: _Admission) -> PaperAccountMutexAcquisition:
    acquisition = admission.acquisition
    if type(acquisition) is not PaperAccountMutexAcquisition:
        raise TypeError("paper-account mutex acquisition evidence is invalid")
    return acquisition


def _same_exact_recovery_required(
    left: PaperReceiptRecoveryQualificationResult,
    right: PaperReceiptRecoveryQualificationResult,
) -> bool:
    return (
        type(left) is PaperReceiptRecoveryQualificationResult
        and type(right) is PaperReceiptRecoveryQualificationResult
        and left.status
        is PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
        and right.status
        is PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
        and _recovery_signature(left) == _recovery_signature(right)
    )


def _recovery_signature(
    result: PaperReceiptRecoveryQualificationResult,
) -> tuple[object, ...]:
    return (
        result.status,
        result.diagnostic,
        result.paper_account_id,
        result.terminal_checkpoint_id,
        result.missing_application_id,
        result.predecessor_checkpoint_id,
    )


def is_safe_personal_desktop_unattended_invocation_storage_result(
    result: object, expected_invocation_id: UUID
) -> bool:
    """Return whether B1 storage is exact and safe for PD4 composition."""

    return (
        type(result) is PersonalDesktopUnattendedInvocationStorageReadResult
        and result.expected_invocation_id == expected_invocation_id
        and result.classification
        in {
            PersonalDesktopUnattendedInvocationStorageClassification.ABSENT,
            PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL,
        }
    )


def _storage_classification(
    result: object,
) -> PersonalDesktopUnattendedInvocationStorageClassification | None:
    if type(result) is PersonalDesktopUnattendedInvocationStorageReadResult:
        return result.classification
    return None


def is_safe_prepared_paper_operation_inspection(
    result: object, material: PreparedPaperOperationMaterial
) -> bool:
    """Return whether an A67 inspection exactly matches prepared material."""

    inputs = material.execution_inputs
    if (
        type(result) is not PaperOperationInspectionResult
        or result.operation_id != inputs.intent.operation_id
        or result.application_id != inputs.application_id
        or result.terminal_checkpoint_id
        != inputs.intent.prior_lineage_evidence.terminal_checkpoint_id
    ):
        return False
    return (
        result.classification is PaperOperationClassification.PENDING
        and result.diagnostics == (PaperOperationInspectionCode.PENDING,)
    ) or (
        result.classification is PaperOperationClassification.ALREADY_APPLIED
        and result.diagnostics == (PaperOperationInspectionCode.ALREADY_APPLIED,)
    )


def _healthy_result(
    paper_account_id: str,
    selected: SelectedC3SnapshotReadResult,
    expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    material: PreparedPaperOperationMaterial,
    storage: PersonalDesktopUnattendedInvocationStorageReadResult,
    inspection: PaperOperationInspectionResult,
    mutex_state: PaperAccountMutexState,
) -> PersonalDesktopUnattendedPaperStartupQualificationResult:
    if inspection.classification is PaperOperationClassification.ALREADY_APPLIED:
        status = PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED
        diagnostic = (
            PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_ALREADY_APPLIED
        )
    elif (
        storage.classification
        is PersonalDesktopUnattendedInvocationStorageClassification.ABSENT
    ):
        status = (
            PersonalDesktopUnattendedPaperStartupStatus.HEALTHY_NO_PENDING_INVOCATION
        )
        diagnostic = (
            PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_ABSENT_PENDING
        )
    else:
        status = PersonalDesktopUnattendedPaperStartupStatus.READY_SAME_INVOCATION
        diagnostic = (
            PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_IDENTICAL_PENDING
        )
    return PersonalDesktopUnattendedPaperStartupQualificationResult(
        status,
        diagnostic,
        paper_account_id,
        selected.audit.snapshot_id,
        expected.invocation.invocation_id,
        material.execution_inputs.intent.operation_id,
        material.execution_inputs.application_id,
        material.execution_inputs.intent.prior_lineage_evidence.terminal_checkpoint_id,
        storage.classification,
        inspection.classification,
        inspection.diagnostics[0],
        None,
        None,
        mutex_state,
    )


def _recovery_result(
    recovery: PaperReceiptRecoveryQualificationResult,
    mutex_state: PaperAccountMutexState,
) -> PersonalDesktopUnattendedPaperStartupQualificationResult:
    return PersonalDesktopUnattendedPaperStartupQualificationResult(
        PersonalDesktopUnattendedPaperStartupStatus.RECEIPT_RECOVERY_REQUIRED,
        PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_TERMINAL_RECEIPT_MISSING,
        recovery.paper_account_id,
        None,
        None,
        None,
        None,
        recovery.terminal_checkpoint_id,
        None,
        None,
        None,
        recovery.missing_application_id,
        recovery.predecessor_checkpoint_id,
        mutex_state,
    )


def _blocked_from_healthy(
    reason: PersonalDesktopUnattendedPaperStartupBlockedReason,
    paper_account_id: str,
    selected: SelectedC3SnapshotReadResult,
    expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    material: PreparedPaperOperationMaterial,
    storage: PersonalDesktopUnattendedInvocationStorageReadResult,
    inspection: object,
    acquisition: PaperAccountMutexAcquisition,
) -> PersonalDesktopUnattendedPaperStartupQualificationResult:
    classification = None
    diagnostic = None
    if type(inspection) is PaperOperationInspectionResult:
        classification = inspection.classification
        diagnostic = inspection.diagnostics[0]
    return _blocked_result(
        reason,
        paper_account_id=paper_account_id,
        selected_snapshot_id=selected.audit.snapshot_id,
        invocation_id=expected.invocation.invocation_id,
        operation_id=material.execution_inputs.intent.operation_id,
        application_id=material.execution_inputs.application_id,
        terminal_checkpoint_id=(
            material.execution_inputs.intent.prior_lineage_evidence.terminal_checkpoint_id
        ),
        storage_classification=storage.classification,
        operation_classification=classification,
        operation_diagnostic=diagnostic,
        mutex_state=acquisition.state,
    )


def _blocked_result(
    reason: PersonalDesktopUnattendedPaperStartupBlockedReason,
    *,
    paper_account_id: str | None = None,
    selected_snapshot_id: UUID | None = None,
    invocation_id: UUID | None = None,
    operation_id: UUID | None = None,
    application_id: UUID | None = None,
    terminal_checkpoint_id: UUID | None = None,
    storage_classification: PersonalDesktopUnattendedInvocationStorageClassification
    | None = None,
    operation_classification: PaperOperationClassification | None = None,
    operation_diagnostic: PaperOperationInspectionCode | None = None,
    mutex_state: PaperAccountMutexState | None = None,
) -> PersonalDesktopUnattendedPaperStartupQualificationResult:
    return PersonalDesktopUnattendedPaperStartupQualificationResult(
        PersonalDesktopUnattendedPaperStartupStatus.BLOCKED,
        PersonalDesktopUnattendedPaperStartupDiagnostic.QUALIFICATION_BLOCKED,
        paper_account_id,
        selected_snapshot_id,
        invocation_id,
        operation_id,
        application_id,
        terminal_checkpoint_id,
        storage_classification,
        operation_classification,
        operation_diagnostic,
        None,
        None,
        mutex_state,
        reason,
    )


def _gate_state() -> tuple[bool, bool, bool, bool, bool, bool]:
    from trading_bot.runtime import personal_desktop_paper_account_security as security
    from trading_bot.runtime import (
        personal_desktop_paper_receipt_recovery_execution as recovery,
    )
    from trading_bot.runtime import (
        personal_desktop_supervised_paper_operation_execution as supervised,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_operation_execution as unattended,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_storage_provisioning as provisioning,
    )

    return (
        security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED,
        supervised.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
        recovery.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
        unattended.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED,
        provisioning.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED,
    )
