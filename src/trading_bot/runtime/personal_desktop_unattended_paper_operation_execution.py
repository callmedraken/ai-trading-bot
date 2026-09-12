"""PD4-D unattended Paper-v2 composition with production effects closed."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import UUID

from trading_bot.cli.paper_operation_execution import (
    PaperOperationExecutionClassification,
    PaperOperationExecutionDiagnosticCode,
    PaperOperationExecutionResult,
    execute_paper_operation_once,
)
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    PaperOperationInspectionResult,
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
)
from trading_bot.runtime.paper_operation import PaperOperationStatus
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    PersonalDesktopPaperAccountReadEvidence,
)
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
)
from trading_bot.runtime.personal_desktop_paper_runtime_output import (
    PersonalDesktopUnattendedInvocationPublicationResult,
    open_personal_desktop_unattended_invocation_output_capability,
    open_personal_desktop_unattended_paper_runtime_output_capability,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation import (
    PersonalDesktopUnattendedPaperInvocationArtifactBinding,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageClassification,
    PersonalDesktopUnattendedInvocationStorageReadResult,
    require_validated_personal_desktop_unattended_invocation_storage_read,
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

from .personal_desktop_supervised_paper_operation_preparation import (
    _PreparedPaperOperationMaterial,
    _reconstruct_verified_paper_operation_from_plan,
)
from .personal_desktop_unattended_paper_startup_qualification import (
    PersonalDesktopUnattendedPaperStartupStatus,
    _PlanningInputs,
    _production_dependencies,
    _QualificationDependencies,
    _revalidate_c1_p2_gate_state,
    _safe_inspection,
    _safe_storage_result,
    _unattended_paper_startup_reconciliation_scope,
)

PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED = False

_READ_ONLY_DISABLED = (False, False, False, False, False, False)
_UNATTENDED_EFFECT_ENABLED = (False, False, False, False, True, False)
_ACCEPTED_GATE_STATES = frozenset({_READ_ONLY_DISABLED, _UNATTENDED_EFFECT_ENABLED})
_PRODUCTION_EXECUTION_ISSUER = object()
_DISPOSABLE_EXECUTION_ISSUER = object()


class PersonalDesktopUnattendedPaperOperationExecutionError(
    PersonalDesktopPaperAccountError
):
    """Base class for fail-closed PD4-D composition failures."""


class PersonalDesktopUnattendedPaperEffectsDisabledError(
    PersonalDesktopUnattendedPaperOperationExecutionError
):
    """Raised after safe read-only reconciliation when fresh effects are closed."""


class PersonalDesktopUnattendedPaperOperationStatus(StrEnum):
    COMPLETED = "COMPLETED"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    RECEIPT_RECOVERY_REQUIRED = "RECEIPT_RECOVERY_REQUIRED"
    BLOCKED = "BLOCKED"


class PersonalDesktopUnattendedPaperOperationDiagnostic(StrEnum):
    VERIFIED_COMPLETED = "VERIFIED_COMPLETED"
    VERIFIED_ALREADY_APPLIED = "VERIFIED_ALREADY_APPLIED"
    VERIFIED_TERMINAL_RECEIPT_MISSING = "VERIFIED_TERMINAL_RECEIPT_MISSING"
    EXECUTION_BLOCKED = "EXECUTION_BLOCKED"


_Status = PersonalDesktopUnattendedPaperOperationStatus
_Diagnostic = PersonalDesktopUnattendedPaperOperationDiagnostic
_Storage = PersonalDesktopUnattendedInvocationStorageClassification
_StartupStatus = PersonalDesktopUnattendedPaperStartupStatus


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedPaperOperationResult:
    """Immutable sanitized non-authorizing PD4-D evidence."""

    status: PersonalDesktopUnattendedPaperOperationStatus
    diagnostic: PersonalDesktopUnattendedPaperOperationDiagnostic
    paper_account_id: str | None
    selected_snapshot_id: UUID | None
    invocation_id: UUID | None
    operation_id: UUID | None
    application_id: UUID | None
    predecessor_checkpoint_id: UUID | None
    final_checkpoint_id: UUID | None
    invocation_published: bool
    executor_called: bool
    execution_classification: PaperOperationExecutionClassification | None
    final_operation_classification: PaperOperationClassification | None

    def __post_init__(self) -> None:
        expected_diagnostic = {
            _Status.COMPLETED: _Diagnostic.VERIFIED_COMPLETED,
            _Status.ALREADY_APPLIED: _Diagnostic.VERIFIED_ALREADY_APPLIED,
            _Status.RECEIPT_RECOVERY_REQUIRED: (
                _Diagnostic.VERIFIED_TERMINAL_RECEIPT_MISSING
            ),
            _Status.BLOCKED: _Diagnostic.EXECUTION_BLOCKED,
        }.get(self.status)
        uuid_values = (
            self.selected_snapshot_id,
            self.invocation_id,
            self.operation_id,
            self.application_id,
            self.predecessor_checkpoint_id,
            self.final_checkpoint_id,
        )
        if (
            type(self.status) is not PersonalDesktopUnattendedPaperOperationStatus
            or type(self.diagnostic)
            is not PersonalDesktopUnattendedPaperOperationDiagnostic
            or self.diagnostic is not expected_diagnostic
            or (
                self.paper_account_id is not None
                and type(self.paper_account_id) is not str
            )
            or any(
                value is not None and type(value) is not UUID for value in uuid_values
            )
            or type(self.invocation_published) is not bool
            or type(self.executor_called) is not bool
            or (
                self.execution_classification is not None
                and type(self.execution_classification)
                is not PaperOperationExecutionClassification
            )
            or (
                self.final_operation_classification is not None
                and type(self.final_operation_classification)
                is not PaperOperationClassification
            )
        ):
            raise ValueError("unattended paper-operation result is invalid")
        if self.status in {
            PersonalDesktopUnattendedPaperOperationStatus.COMPLETED,
            PersonalDesktopUnattendedPaperOperationStatus.ALREADY_APPLIED,
        } and any(
            value is None
            for value in (
                self.paper_account_id,
                self.selected_snapshot_id,
                self.invocation_id,
                self.operation_id,
                self.application_id,
                self.predecessor_checkpoint_id,
                self.final_checkpoint_id,
                self.final_operation_classification,
            )
        ):
            raise ValueError("successful unattended evidence is incomplete")


class _Publisher(Protocol):
    def __enter__(self) -> _Publisher: ...
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> object: ...
    def publish(self) -> PersonalDesktopUnattendedInvocationPublicationResult: ...


class _OutputCapability(Protocol):
    def __enter__(self) -> object: ...
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> object: ...


@dataclass(frozen=True, slots=True)
class _ExecutionDependencies:
    qualification: _QualificationDependencies
    resolve_storage: Callable[
        [PersonalDesktopUnattendedInvocationStorageReadResult],
        PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    ]
    open_publisher: Callable[
        [PersonalDesktopUnattendedInvocationStorageReadResult], _Publisher
    ]
    reconstruct: Callable[
        [object, SelectedC3SnapshotReadResult, object, IdentifiedMarketCalendar],
        _PreparedPaperOperationMaterial,
    ]
    open_output: Callable[[], _OutputCapability]
    execute_operation: Callable[[Path, object, object], PaperOperationExecutionResult]


class _DisposableUnattendedPaperExecutionAuthorityForTest:
    __slots__ = ("_lock", "_used", "dependencies")

    def __init__(self, dependencies: _ExecutionDependencies) -> None:
        self.dependencies = dependencies
        self._lock = threading.Lock()
        self._used = False

    def _consume(self) -> None:
        with self._lock:
            if self._used:
                raise TypeError("disposable unattended execution authority is spent")
            self._used = True

    def __copy__(self) -> object:
        raise TypeError("disposable unattended execution authorities cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError(
            "disposable unattended execution authorities cannot be deep-copied"
        )

    def __reduce__(self) -> object:
        raise TypeError(
            "disposable unattended execution authorities cannot be serialized"
        )


def execute_personal_desktop_unattended_paper_operation(
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
) -> PersonalDesktopUnattendedPaperOperationResult:
    inputs = _PlanningInputs(
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
    return _compose_personal_desktop_unattended_paper_operation(
        authority,
        selected_snapshot,
        inputs,
        calendar,
        _production_execution_dependencies(),
        _issuer=_PRODUCTION_EXECUTION_ISSUER,
    )


def _open_disposable_unattended_paper_execution_authority_for_test(
    dependencies: _ExecutionDependencies,
) -> _DisposableUnattendedPaperExecutionAuthorityForTest:
    if type(dependencies) is not _ExecutionDependencies:
        raise TypeError("disposable unattended execution dependencies are invalid")
    if (
        dependencies.open_publisher
        is open_personal_desktop_unattended_invocation_output_capability
        or dependencies.open_output
        is open_personal_desktop_unattended_paper_runtime_output_capability
        or dependencies.execute_operation is _execute_architecture_67
    ):
        raise TypeError("disposable seam rejects production mutation boundaries")
    return _DisposableUnattendedPaperExecutionAuthorityForTest(dependencies)


def _execute_personal_desktop_unattended_paper_operation_for_test(
    authority: _DisposableUnattendedPaperExecutionAuthorityForTest,
    c1: object,
    selected_snapshot: SelectedC3SnapshotReadResult,
    inputs: _PlanningInputs,
    calendar: IdentifiedMarketCalendar,
) -> PersonalDesktopUnattendedPaperOperationResult:
    if type(authority) is not _DisposableUnattendedPaperExecutionAuthorityForTest:
        raise TypeError("disposable unattended execution authority is invalid")
    authority._consume()
    return _compose_personal_desktop_unattended_paper_operation(
        c1,
        selected_snapshot,
        inputs,
        calendar,
        authority.dependencies,
        _issuer=_DISPOSABLE_EXECUTION_ISSUER,
    )


def _production_execution_dependencies() -> _ExecutionDependencies:
    return _ExecutionDependencies(
        _production_dependencies(),
        _resolve_finalized_storage_binding,
        open_personal_desktop_unattended_invocation_output_capability,
        _reconstruct_verified_paper_operation_from_plan,
        open_personal_desktop_unattended_paper_runtime_output_capability,
        _execute_architecture_67,
    )


def _compose_personal_desktop_unattended_paper_operation(
    authority: object,
    selected: SelectedC3SnapshotReadResult,
    inputs: _PlanningInputs,
    calendar: IdentifiedMarketCalendar,
    dependencies: _ExecutionDependencies,
    *,
    _issuer: object,
) -> PersonalDesktopUnattendedPaperOperationResult:
    if _issuer not in {_PRODUCTION_EXECUTION_ISSUER, _DISPOSABLE_EXECUTION_ISSUER}:
        raise TypeError("unattended execution issuer is invalid")
    if type(dependencies) is not _ExecutionDependencies:
        raise TypeError("unattended execution dependencies are invalid")
    if _issuer is _PRODUCTION_EXECUTION_ISSUER and (
        dependencies.open_publisher
        is not open_personal_desktop_unattended_invocation_output_capability
        or dependencies.open_output
        is not open_personal_desktop_unattended_paper_runtime_output_capability
        or dependencies.execute_operation is not _execute_architecture_67
        or dependencies.resolve_storage is not _resolve_finalized_storage_binding
        or dependencies.reconstruct
        is not _reconstruct_verified_paper_operation_from_plan
    ):
        raise TypeError(
            "production unattended execution dependencies are not source-owned"
        )

    known: dict[str, object] = {
        "selected_snapshot_id": selected.audit.snapshot_id
        if type(selected) is SelectedC3SnapshotReadResult
        else None,
        "invocation_published": False,
        "executor_called": False,
    }
    disabled_after_reconciliation = False
    try:
        scope = _unattended_paper_startup_reconciliation_scope(
            authority,
            selected,
            inputs,
            calendar,
            dependencies.qualification,
            allowed_gate_states=_ACCEPTED_GATE_STATES,
        )
        with scope as reconciliation:
            public = reconciliation.public_result
            if public is not None:
                if public.status is _StartupStatus.RECEIPT_RECOVERY_REQUIRED:
                    return PersonalDesktopUnattendedPaperOperationResult(
                        PersonalDesktopUnattendedPaperOperationStatus.RECEIPT_RECOVERY_REQUIRED,
                        PersonalDesktopUnattendedPaperOperationDiagnostic.VERIFIED_TERMINAL_RECEIPT_MISSING,
                        public.paper_account_id,
                        None,
                        None,
                        None,
                        None,
                        public.recovery_predecessor_checkpoint_id,
                        public.terminal_checkpoint_id,
                        False,
                        False,
                        None,
                        None,
                    )
                return _blocked_result(known)

            c1 = reconciliation.c1
            account = reconciliation.post_lock_account
            material = reconciliation.material
            expected = reconciliation.expected_invocation
            storage = reconciliation.storage
            initial_inspection = reconciliation.inspection
            account_id = reconciliation.paper_account_id
            if any(
                value is None
                for value in (
                    c1,
                    account,
                    material,
                    expected,
                    storage,
                    initial_inspection,
                    account_id,
                )
            ):
                raise TypeError("healthy mutex-held reconciliation is incomplete")
            if (
                type(material) is not _PreparedPaperOperationMaterial
                or type(expected)
                is not PersonalDesktopUnattendedPaperInvocationArtifactBinding
                or type(storage)
                is not PersonalDesktopUnattendedInvocationStorageReadResult
                or type(initial_inspection) is not PaperOperationInspectionResult
                or type(account_id) is not str
            ):
                raise TypeError("healthy mutex-held reconciliation types are invalid")
            _remember_material(
                known, account_id, expected, material, initial_inspection
            )

            captured = reconciliation.captured_gate_state
            durable = None
            durable_material = material
            if storage.classification is _Storage.FINALIZED_IDENTICAL:
                durable = dependencies.resolve_storage(storage)
                durable_material = dependencies.reconstruct(
                    account, selected, durable.replayed_plan, calendar
                )
                _require_reconstructed_identity(
                    material, durable_material, expected, durable
                )
                initial_inspection = _inspect_exact(
                    dependencies, durable_material, allow_already_applied=True
                )
                known["final_operation_classification"] = (
                    initial_inspection.classification
                )

            if (
                initial_inspection.classification
                is PaperOperationClassification.ALREADY_APPLIED
            ):
                final_account, final_inspection = _final_reconciliation(
                    c1,
                    selected,
                    inputs,
                    captured,
                    account_id,
                    durable_material,
                    expected,
                    storage,
                    durable,
                    dependencies,
                    execution_result=None,
                    require_finalized_storage=durable is not None,
                )
                return _successful_result(
                    known,
                    PersonalDesktopUnattendedPaperOperationStatus.ALREADY_APPLIED,
                    final_account,
                    final_inspection,
                )

            if captured == _READ_ONLY_DISABLED:
                _require_read_only_stability(
                    c1,
                    selected,
                    inputs,
                    captured,
                    account_id,
                    account,
                    durable_material,
                    expected,
                    storage,
                    dependencies,
                )
                disabled_after_reconciliation = True
            else:
                if (
                    storage.classification
                    is PersonalDesktopUnattendedInvocationStorageClassification.ABSENT
                ):
                    _revalidate_c1_p2_gate_state(
                        c1, selected, captured, dependencies.qualification
                    )
                    with dependencies.open_publisher(storage) as publisher:
                        publication = publisher.publish()
                    _require_publication_result(publication, expected)
                    known["invocation_published"] = True
                    storage = dependencies.qualification.read_storage(c1, expected)
                    _require_finalized_storage(storage, expected)
                    durable = dependencies.resolve_storage(storage)
                    durable_material = dependencies.reconstruct(
                        account, selected, durable.replayed_plan, calendar
                    )
                    _require_reconstructed_identity(
                        material, durable_material, expected, durable
                    )

                if durable is None:
                    raise RuntimeError(
                        "finalized durable invocation binding is unavailable"
                    )
                pre_execution = _inspect_exact(
                    dependencies, durable_material, allow_already_applied=True
                )
                known["final_operation_classification"] = pre_execution.classification
                if (
                    pre_execution.classification
                    is PaperOperationClassification.ALREADY_APPLIED
                ):
                    final_account, final_inspection = _final_reconciliation(
                        c1,
                        selected,
                        inputs,
                        captured,
                        account_id,
                        durable_material,
                        expected,
                        storage,
                        durable,
                        dependencies,
                        execution_result=None,
                        require_finalized_storage=True,
                    )
                    return _successful_result(
                        known,
                        PersonalDesktopUnattendedPaperOperationStatus.ALREADY_APPLIED,
                        final_account,
                        final_inspection,
                    )
                _revalidate_c1_p2_gate_state(
                    c1, selected, captured, dependencies.qualification
                )
                with dependencies.open_output() as output_capability:
                    known["executor_called"] = True
                    execution_result = dependencies.execute_operation(
                        Path(PERSONAL_DESKTOP_PAPER_V2_RUNTIME),
                        durable_material.execution_inputs,
                        output_capability,
                    )
                classification = _require_execution_result(
                    execution_result, durable_material
                )
                known["execution_classification"] = classification
                final_account, final_inspection = _final_reconciliation(
                    c1,
                    selected,
                    inputs,
                    captured,
                    account_id,
                    durable_material,
                    expected,
                    storage,
                    durable,
                    dependencies,
                    execution_result=execution_result,
                    require_finalized_storage=True,
                )
                status = (
                    PersonalDesktopUnattendedPaperOperationStatus.COMPLETED
                    if classification is PaperOperationExecutionClassification.COMPLETED
                    else PersonalDesktopUnattendedPaperOperationStatus.ALREADY_APPLIED
                )
                return _successful_result(
                    known, status, final_account, final_inspection
                )
    except PersonalDesktopUnattendedPaperEffectsDisabledError:
        raise
    except Exception:
        return _blocked_result(known)
    if disabled_after_reconciliation:
        raise PersonalDesktopUnattendedPaperEffectsDisabledError(
            "unattended Paper-v2 execution effects are disabled"
        )
    return _blocked_result(known)


def _resolve_finalized_storage_binding(
    result: PersonalDesktopUnattendedInvocationStorageReadResult,
) -> PersonalDesktopUnattendedPaperInvocationArtifactBinding:
    verified = require_validated_personal_desktop_unattended_invocation_storage_read(
        result
    )
    if verified.classification is not _Storage.FINALIZED_IDENTICAL:
        raise ValueError("durable invocation resolution requires FINALIZED_IDENTICAL")
    expected_id = verified.expected.invocation.invocation_id
    matching = tuple(
        binding
        for binding in verified.finalized
        if binding.invocation.invocation_id == expected_id
    )
    if matching != (verified.expected,):
        raise ValueError("durable invocation storage lacks one exact finalized binding")
    return matching[0]


def _execute_architecture_67(
    operation_root: Path, inputs: object, output_capability: object
) -> PaperOperationExecutionResult:
    return execute_paper_operation_once(
        operation_root,
        inputs,  # type: ignore[arg-type]
        output_capability=output_capability,  # type: ignore[arg-type]
    )


def _remember_material(
    known: dict[str, object],
    account_id: str,
    expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    material: _PreparedPaperOperationMaterial,
    inspection: PaperOperationInspectionResult,
) -> None:
    known.update(
        paper_account_id=account_id,
        invocation_id=expected.invocation.invocation_id,
        operation_id=material.execution_inputs.intent.operation_id,
        application_id=material.execution_inputs.application_id,
        predecessor_checkpoint_id=material.execution_inputs.intent.prior_lineage_evidence.terminal_checkpoint_id,
        final_operation_classification=inspection.classification,
    )


def _require_reconstructed_identity(
    expected_material: _PreparedPaperOperationMaterial,
    reconstructed: _PreparedPaperOperationMaterial,
    expected_invocation: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    durable_invocation: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
) -> None:
    expected_inputs = expected_material.execution_inputs
    reconstructed_inputs = reconstructed.execution_inputs
    if (
        type(reconstructed) is not _PreparedPaperOperationMaterial
        or durable_invocation.invocation.invocation_id
        != expected_invocation.invocation.invocation_id
        or durable_invocation.replayed_plan != reconstructed.plan_binding
        or reconstructed_inputs.intent.operation_id
        != expected_inputs.intent.operation_id
        or reconstructed_inputs.application_id != expected_inputs.application_id
    ):
        raise ValueError("durable invocation reconstruction identities do not agree")


def _inspect_exact(
    dependencies: _ExecutionDependencies,
    material: _PreparedPaperOperationMaterial,
    *,
    allow_already_applied: bool,
) -> PaperOperationInspectionResult:
    result = dependencies.qualification.inspect_operation(
        Path(PERSONAL_DESKTOP_PAPER_V2_RUNTIME), material.execution_inputs
    )
    if not _safe_inspection(result, material):
        raise ValueError("Architecture-67 inspection is not exact")
    if (
        not allow_already_applied
        and result.classification is not PaperOperationClassification.PENDING
    ):
        raise ValueError("Architecture-67 operation is not exact PENDING/PENDING")
    return result


def _require_publication_result(
    result: object, expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding
) -> None:
    if (
        type(result) is not PersonalDesktopUnattendedInvocationPublicationResult
        or result.invocation_id != expected.invocation.invocation_id
        or result.artifact_sha256 != expected.artifact_sha256
        or result.artifact_byte_length != expected.artifact_byte_length
        or result.staging_created is not True
        or result.finalized is not True
        or result.artifact_verified is not True
    ):
        raise ValueError("invocation publication result does not reconcile")


def _require_finalized_storage(
    storage: object, expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding
) -> None:
    if (
        not _safe_storage_result(storage, expected.invocation.invocation_id)
        or storage.classification is not _Storage.FINALIZED_IDENTICAL
    ):
        raise ValueError("invocation storage is not exact FINALIZED_IDENTICAL")


def _require_read_only_stability(
    c1: object,
    selected: SelectedC3SnapshotReadResult,
    inputs: _PlanningInputs,
    captured: tuple[bool, bool, bool, bool, bool, bool],
    account_id: str,
    post_lock_account: object,
    material: _PreparedPaperOperationMaterial,
    expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    initial_storage: PersonalDesktopUnattendedInvocationStorageReadResult,
    dependencies: _ExecutionDependencies,
) -> None:
    _revalidate_c1_p2_gate_state(c1, selected, captured, dependencies.qualification)
    configurations = _configuration_dependencies(
        inputs.historical_configurations, material.plan_binding.artifact_bytes
    )
    final_read = dependencies.qualification.read_account(c1, configurations)
    final_account = dependencies.qualification.require_account(final_read)
    if (
        final_account.anchor.paper_account_id != account_id
        or final_account != post_lock_account
    ):
        raise ValueError("read-only final account truth changed")
    _inspect_exact(dependencies, material, allow_already_applied=False)
    final_storage = dependencies.qualification.read_storage(c1, expected)
    if (
        not _safe_storage_result(final_storage, expected.invocation.invocation_id)
        or final_storage.classification is not initial_storage.classification
    ):
        raise ValueError("read-only durable invocation state changed")
    _revalidate_c1_p2_gate_state(c1, selected, captured, dependencies.qualification)


def _final_reconciliation(
    c1: object,
    selected: SelectedC3SnapshotReadResult,
    inputs: _PlanningInputs,
    captured: tuple[bool, bool, bool, bool, bool, bool],
    account_id: str,
    material: _PreparedPaperOperationMaterial,
    expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    initial_storage: PersonalDesktopUnattendedInvocationStorageReadResult,
    durable: PersonalDesktopUnattendedPaperInvocationArtifactBinding | None,
    dependencies: _ExecutionDependencies,
    *,
    execution_result: PaperOperationExecutionResult | None,
    require_finalized_storage: bool,
) -> tuple[PersonalDesktopPaperAccountReadEvidence, PaperOperationInspectionResult]:
    configurations = _configuration_dependencies(
        inputs.historical_configurations, material.plan_binding.artifact_bytes
    )
    final_read = dependencies.qualification.read_account(c1, configurations)
    final_account = dependencies.qualification.require_account(final_read)
    if final_account.anchor.paper_account_id != account_id:
        raise ValueError("post-run account identity changed")
    _require_terminal_receipt(final_account, material, execution_result)
    final_inspection = _inspect_exact(
        dependencies, material, allow_already_applied=True
    )
    if (
        final_inspection.classification
        is not PaperOperationClassification.ALREADY_APPLIED
    ):
        raise ValueError("final Architecture-67 state is not ALREADY_APPLIED")
    final_storage = dependencies.qualification.read_storage(c1, expected)
    if require_finalized_storage:
        _require_finalized_storage(final_storage, expected)
        final_durable = dependencies.resolve_storage(final_storage)
        if durable is None or final_durable != durable:
            raise ValueError("final durable invocation binding changed")
    elif (
        not _safe_storage_result(final_storage, expected.invocation.invocation_id)
        or final_storage.classification is not initial_storage.classification
    ):
        raise ValueError("final invocation storage state changed")
    _revalidate_c1_p2_gate_state(c1, selected, captured, dependencies.qualification)
    return final_account, final_inspection


def _configuration_dependencies(
    historical: tuple[bytes, ...], current: bytes
) -> tuple[bytes, ...]:
    if type(historical) is not tuple or type(current) is not bytes or not current:
        raise ValueError("post-run configuration dependencies are invalid")
    retained: dict[tuple[str, int], bytes] = {}
    ordered: list[bytes] = []
    for payload in (*historical, current):
        if type(payload) is not bytes or not payload:
            raise ValueError("post-run configuration dependency is invalid")
        key = (sha256(payload).hexdigest(), len(payload))
        previous = retained.get(key)
        if previous is not None:
            if previous != payload:
                raise ValueError("configuration digest/length collision is unsafe")
            continue
        retained[key] = payload
        ordered.append(payload)
    return tuple(ordered)


def _require_execution_result(
    result: object, material: _PreparedPaperOperationMaterial
) -> PaperOperationExecutionClassification:
    inputs = material.execution_inputs
    if type(result) is not PaperOperationExecutionResult:
        raise ValueError("Architecture-67 executor result type is invalid")
    expected_diagnostic = {
        PaperOperationExecutionClassification.COMPLETED: (
            PaperOperationExecutionDiagnosticCode.COMPLETED.value
        ),
        PaperOperationExecutionClassification.ALREADY_APPLIED: (
            PaperOperationInspectionCode.ALREADY_APPLIED.value
        ),
    }.get(result.classification)
    expected_pre = (
        PaperOperationClassification.PENDING
        if result.classification is PaperOperationExecutionClassification.COMPLETED
        else PaperOperationClassification.ALREADY_APPLIED
    )
    if (
        result.classification
        not in {
            PaperOperationExecutionClassification.COMPLETED,
            PaperOperationExecutionClassification.ALREADY_APPLIED,
        }
        or result.diagnostic_code != expected_diagnostic
        or result.operation_id != inputs.intent.operation_id
        or result.application_id != inputs.application_id
        or result.terminal_checkpoint_id
        != inputs.intent.prior_lineage_evidence.terminal_checkpoint_id
        or result.pre_execution_classification is not expected_pre
    ):
        raise ValueError("Architecture-67 executor result does not reconcile")
    return result.classification


def _require_terminal_receipt(
    evidence: PersonalDesktopPaperAccountReadEvidence,
    material: _PreparedPaperOperationMaterial,
    execution_result: PaperOperationExecutionResult | None,
) -> None:
    inputs = material.execution_inputs
    matching = tuple(
        receipt
        for receipt in evidence.receipts
        if receipt.receipt_id == inputs.intent.operation_id
        and receipt.application_id == inputs.application_id
    )
    if len(matching) != 1:
        raise ValueError("post-run account lacks the exact operation receipt")
    receipt = matching[0]
    successor = receipt.successor_lineage_evidence
    if (
        receipt.status is not PaperOperationStatus.COMPLETED
        or receipt.intent != inputs.intent
        or receipt.prior_lineage_evidence != inputs.intent.prior_lineage_evidence
        or successor != evidence.lineage
        or successor is None
        or successor.terminal_checkpoint_id != evidence.lineage.terminal_checkpoint_id
    ):
        raise ValueError("post-run receipt lineage does not reconcile")
    if (
        execution_result is not None
        and execution_result.classification
        is PaperOperationExecutionClassification.COMPLETED
        and (
            execution_result.successor_checkpoint_id != successor.terminal_checkpoint_id
            or execution_result.cycle_result_id != receipt.cycle_result_id
        )
    ):
        raise ValueError("completed executor successor does not reconcile")


def _successful_result(
    known: dict[str, object],
    status: PersonalDesktopUnattendedPaperOperationStatus,
    final_account: PersonalDesktopPaperAccountReadEvidence,
    final_inspection: PaperOperationInspectionResult,
) -> PersonalDesktopUnattendedPaperOperationResult:
    diagnostic = (
        PersonalDesktopUnattendedPaperOperationDiagnostic.VERIFIED_COMPLETED
        if status is PersonalDesktopUnattendedPaperOperationStatus.COMPLETED
        else PersonalDesktopUnattendedPaperOperationDiagnostic.VERIFIED_ALREADY_APPLIED
    )
    return PersonalDesktopUnattendedPaperOperationResult(
        status,
        diagnostic,
        _optional_text(known.get("paper_account_id")),
        _optional_uuid(known.get("selected_snapshot_id")),
        _optional_uuid(known.get("invocation_id")),
        _optional_uuid(known.get("operation_id")),
        _optional_uuid(known.get("application_id")),
        _optional_uuid(known.get("predecessor_checkpoint_id")),
        final_account.lineage.terminal_checkpoint_id,
        bool(known.get("invocation_published", False)),
        bool(known.get("executor_called", False)),
        _optional_execution_classification(known.get("execution_classification")),
        final_inspection.classification,
    )


def _blocked_result(
    known: dict[str, object],
) -> PersonalDesktopUnattendedPaperOperationResult:
    return PersonalDesktopUnattendedPaperOperationResult(
        PersonalDesktopUnattendedPaperOperationStatus.BLOCKED,
        PersonalDesktopUnattendedPaperOperationDiagnostic.EXECUTION_BLOCKED,
        _optional_text(known.get("paper_account_id")),
        _optional_uuid(known.get("selected_snapshot_id")),
        _optional_uuid(known.get("invocation_id")),
        _optional_uuid(known.get("operation_id")),
        _optional_uuid(known.get("application_id")),
        _optional_uuid(known.get("predecessor_checkpoint_id")),
        None,
        bool(known.get("invocation_published", False)),
        bool(known.get("executor_called", False)),
        _optional_execution_classification(known.get("execution_classification")),
        _optional_operation_classification(known.get("final_operation_classification")),
    )


def _optional_uuid(value: object) -> UUID | None:
    return value if type(value) is UUID else None


def _optional_text(value: object) -> str | None:
    return value if type(value) is str else None


def _optional_execution_classification(
    value: object,
) -> PaperOperationExecutionClassification | None:
    return value if type(value) is PaperOperationExecutionClassification else None


def _optional_operation_classification(
    value: object,
) -> PaperOperationClassification | None:
    return value if type(value) is PaperOperationClassification else None
