"""Source-owned PD3 receipt-recovery composition with effects disabled."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import UUID

from trading_bot.cli.paper_operation_execution import (
    PaperOperationExecutionClassification,
    PaperOperationExecutionDiagnosticCode,
    recover_paper_operation_receipt_once,
)
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    inspect_paper_operation_root,
)
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as supervised_execution,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadResult,
    require_selected_c3_snapshot_matches_authority,
)
from trading_bot.runtime.paper_operation import PaperOperationStatus
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexState,
    paper_receipt_recovery_admission,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    read_personal_desktop_paper_account,
    require_validated_personal_desktop_paper_account,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_qualification import (
    PaperReceiptRecoveryQualificationResult,
    PaperReceiptRecoveryQualificationStatus,
    qualify_personal_desktop_paper_receipt_recovery,
    require_validated_paper_receipt_recovery_qualification,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_reconstruction import (
    _PaperReceiptRecoveryReconstructionBinding,
    _reconstruct_personal_desktop_paper_receipt_recovery_operation,
)
from trading_bot.runtime.personal_desktop_paper_runtime_output import (
    open_personal_desktop_paper_receipt_recovery_output_capability,
)
from trading_bot.runtime.strategy_history_seed import VerifiedStrategyHistorySeed
from trading_bot.runtime.verified_snapshot_preparation import (
    CallerAssertedNextSessionOpenReference,
    VerifiedSnapshotPaperCyclePolicies,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED = False

_PRODUCTION_COMPOSITION_ISSUER = object()
_DISPOSABLE_COMPOSITION_ISSUER = object()
_DISPOSABLE_OPERATION_ROOT = Path(r"Z:\disposable-pd3-receipt-recovery")


class PersonalDesktopPaperReceiptRecoveryExecutionError(
    PersonalDesktopPaperAccountError
):
    """A personal-desktop receipt-recovery execution failed closed."""


class PersonalDesktopPaperReceiptRecoveryEffectsDisabledError(
    PersonalDesktopPaperReceiptRecoveryExecutionError
):
    """The dedicated receipt-recovery production-effect gate is disabled."""


class PersonalDesktopPaperReceiptRecoveryBlockedError(
    PersonalDesktopPaperReceiptRecoveryExecutionError
):
    """Recovery evidence, ordering, or reconciliation was not exact."""


@dataclass(frozen=True, slots=True)
class PersonalDesktopPaperReceiptRecoveryResult:
    """Immutable sanitized audit facts carrying no reusable authority."""

    qualification_status: PaperReceiptRecoveryQualificationStatus
    paper_account_id: str
    operation_id: UUID | None
    application_id: UUID | None
    predecessor_checkpoint_id: UUID | None
    installed_terminal_checkpoint_id: UUID
    pre_recovery_classification: PaperOperationClassification | None
    recovery_classification: PaperOperationExecutionClassification | None
    recovery_diagnostic: str
    receipt_evidence_produced: bool
    post_recovery_classification: PaperOperationClassification | None

    def __post_init__(self) -> None:
        attempted = self.operation_id is not None
        paired = (
            self.application_id,
            self.predecessor_checkpoint_id,
            self.pre_recovery_classification,
            self.recovery_classification,
            self.post_recovery_classification,
        )
        if (
            type(self.qualification_status)
            is not PaperReceiptRecoveryQualificationStatus
            or type(self.paper_account_id) is not str
            or not self.paper_account_id
            or type(self.installed_terminal_checkpoint_id) is not UUID
            or type(self.recovery_diagnostic) is not str
            or not self.recovery_diagnostic
            or type(self.receipt_evidence_produced) is not bool
            or attempted != all(value is not None for value in paired)
            or any(
                value is not None and type(value) is not UUID
                for value in (
                    self.operation_id,
                    self.application_id,
                    self.predecessor_checkpoint_id,
                )
            )
            or (
                self.pre_recovery_classification is not None
                and type(self.pre_recovery_classification)
                is not PaperOperationClassification
            )
            or (
                self.recovery_classification is not None
                and type(self.recovery_classification)
                is not PaperOperationExecutionClassification
            )
            or (
                self.post_recovery_classification is not None
                and type(self.post_recovery_classification)
                is not PaperOperationClassification
            )
            or (
                not attempted
                and (
                    self.qualification_status
                    is not PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED
                    or self.receipt_evidence_produced
                )
            )
            or (
                attempted
                and (
                    self.qualification_status
                    is not (
                        PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
                    )
                    or self.pre_recovery_classification
                    is not PaperOperationClassification.BLOCKED
                    or self.post_recovery_classification
                    is not PaperOperationClassification.ALREADY_APPLIED
                    or self.recovery_classification
                    not in {
                        PaperOperationExecutionClassification.RECEIPT_RECOVERED,
                        PaperOperationExecutionClassification.ALREADY_APPLIED,
                    }
                    or self.receipt_evidence_produced
                    != (
                        self.recovery_classification
                        is PaperOperationExecutionClassification.RECEIPT_RECOVERED
                    )
                )
            )
        ):
            raise ValueError("personal-desktop receipt-recovery result is invalid")


@dataclass(frozen=True, slots=True)
class _EffectGateState:
    receipt_recovery: bool
    publication: bool
    provisioning_recovery: bool
    supervised_execution: bool


class _Qualifier(Protocol):
    def __call__(
        self,
        authority: object,
        *,
        historical_cycle_configuration_payloads: tuple[bytes, ...] = (),
    ) -> object: ...


class _DisposablePaperReceiptRecoveryExecutionAuthorityForTest:
    """Private one-shot authority for the fully injected disposable seam."""

    __slots__ = ("_issuer", "_lock", "_used")

    def __init__(self, *, _issuer: object | None = None) -> None:
        if _issuer is not _DISPOSABLE_COMPOSITION_ISSUER:
            raise TypeError("disposable recovery authority requires its test issuer")
        self._issuer = _issuer
        self._lock = threading.Lock()
        self._used = False

    def _consume(self) -> None:
        with self._lock:
            if self._issuer is not _DISPOSABLE_COMPOSITION_ISSUER or self._used:
                raise TypeError("disposable recovery authority is invalid or consumed")
            self._used = True

    def __copy__(self) -> object:
        raise TypeError("disposable recovery authorities cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("disposable recovery authorities cannot be deep-copied")

    def __reduce__(self) -> object:
        raise TypeError("disposable recovery authorities cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("disposable recovery authorities cannot be pickled")


def recover_personal_desktop_paper_receipt(
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
) -> PersonalDesktopPaperReceiptRecoveryResult:
    """Compose one source-owned recovery attempt; the committed gate is closed."""

    c1 = _require_c1_p2(authority, selected_snapshot)

    def recheck() -> None:
        _require_c1_p2(c1, selected_snapshot)

    return _compose_personal_desktop_paper_receipt_recovery(
        c1,
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
        historical_cycle_configuration_payloads=historical_cycle_configuration_payloads,
        qualifier=qualify_personal_desktop_paper_receipt_recovery,
        admission_factory=paper_receipt_recovery_admission,
        reconstructor=_reconstruct_personal_desktop_paper_receipt_recovery_operation,
        inspector=inspect_paper_operation_root,
        output_capability_factory=(
            open_personal_desktop_paper_receipt_recovery_output_capability
        ),
        recovery=recover_paper_operation_receipt_once,
        post_reader=read_personal_desktop_paper_account,
        post_read_validator=require_validated_personal_desktop_paper_account,
        operation_root=Path(security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME),
        calendar=BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()),
        gate_state=_production_gate_state,
        recheck_provenance=recheck,
        _issuer=_PRODUCTION_COMPOSITION_ISSUER,
    )


def _open_disposable_paper_receipt_recovery_execution_authority_for_test() -> (
    _DisposablePaperReceiptRecoveryExecutionAuthorityForTest
):
    return _DisposablePaperReceiptRecoveryExecutionAuthorityForTest(
        _issuer=_DISPOSABLE_COMPOSITION_ISSUER
    )


def _recover_personal_desktop_paper_receipt_for_test(
    authority: object,
    selected_snapshot: object,
    *,
    history_seed: object,
    strategy_config: object,
    caller_idempotency_key: UUID,
    open_reference: object,
    policies: object,
    planning_at: datetime,
    submitted_at: datetime,
    filled_at: datetime,
    pre_lock_qualifier: _Qualifier,
    post_lock_qualifier: _Qualifier,
    admission_factory: Callable[[object], object],
    reconstructor: Callable[..., object],
    inspector: Callable[[Path, object], object],
    output_capability_factory: Callable[[], object],
    recovery: Callable[..., object],
    post_reader: Callable[..., object],
    post_read_validator: Callable[[object], object],
    execution_authority: _DisposablePaperReceiptRecoveryExecutionAuthorityForTest,
    metadata: tuple[MetadataEntry, ...] = (),
    historical_cycle_configuration_payloads: tuple[bytes, ...] = (),
) -> PersonalDesktopPaperReceiptRecoveryResult:
    """Exercise future-enabled ordering using disposable injected boundaries."""

    if (
        type(execution_authority)
        is not _DisposablePaperReceiptRecoveryExecutionAuthorityForTest
    ):
        raise TypeError("disposable recovery execution authority is invalid")
    forbidden = (
        qualify_personal_desktop_paper_receipt_recovery,
        paper_receipt_recovery_admission,
        _reconstruct_personal_desktop_paper_receipt_recovery_operation,
        inspect_paper_operation_root,
        open_personal_desktop_paper_receipt_recovery_output_capability,
        recover_paper_operation_receipt_once,
        read_personal_desktop_paper_account,
        require_validated_personal_desktop_paper_account,
    )
    supplied = (
        pre_lock_qualifier,
        post_lock_qualifier,
        admission_factory,
        reconstructor,
        inspector,
        output_capability_factory,
        recovery,
        post_reader,
        post_read_validator,
    )
    if any(not callable(item) for item in supplied) or any(
        any(item is production_callable for production_callable in forbidden)
        for item in supplied
    ):
        raise TypeError("disposable recovery seam rejects production wiring")
    execution_authority._consume()

    qualification_calls = 0

    def qualify(
        value: object,
        *,
        historical_cycle_configuration_payloads: tuple[bytes, ...] = (),
    ) -> object:
        nonlocal qualification_calls
        qualification_calls += 1
        selected = (
            pre_lock_qualifier if qualification_calls == 1 else post_lock_qualifier
        )
        return selected(
            value,
            historical_cycle_configuration_payloads=(
                historical_cycle_configuration_payloads
            ),
        )

    return _compose_personal_desktop_paper_receipt_recovery(
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
        historical_cycle_configuration_payloads=historical_cycle_configuration_payloads,
        qualifier=qualify,
        admission_factory=admission_factory,
        reconstructor=reconstructor,
        inspector=inspector,
        output_capability_factory=output_capability_factory,
        recovery=recovery,
        post_reader=post_reader,
        post_read_validator=post_read_validator,
        operation_root=_DISPOSABLE_OPERATION_ROOT,
        calendar=object(),
        gate_state=lambda: _EffectGateState(True, False, False, False),
        recheck_provenance=lambda: None,
        _issuer=_DISPOSABLE_COMPOSITION_ISSUER,
    )


def _compose_personal_desktop_paper_receipt_recovery(
    authority: object,
    selected_snapshot: object,
    *,
    history_seed: object,
    strategy_config: object,
    caller_idempotency_key: UUID,
    open_reference: object,
    policies: object,
    planning_at: datetime,
    submitted_at: datetime,
    filled_at: datetime,
    metadata: tuple[MetadataEntry, ...],
    historical_cycle_configuration_payloads: tuple[bytes, ...],
    qualifier: _Qualifier,
    admission_factory: Callable[[object], object],
    reconstructor: Callable[..., object],
    inspector: Callable[[Path, object], object],
    output_capability_factory: Callable[[], object],
    recovery: Callable[..., object],
    post_reader: Callable[..., object],
    post_read_validator: Callable[[object], object],
    operation_root: Path,
    calendar: object,
    gate_state: Callable[[], _EffectGateState],
    recheck_provenance: Callable[[], None],
    _issuer: object,
) -> PersonalDesktopPaperReceiptRecoveryResult:
    production = _issuer is _PRODUCTION_COMPOSITION_ISSUER
    if not production and _issuer is not _DISPOSABLE_COMPOSITION_ISSUER:
        raise TypeError("receipt-recovery composition issuer is invalid")
    pre_lock = qualifier(
        authority,
        historical_cycle_configuration_payloads=(
            historical_cycle_configuration_payloads
        ),
    )
    pre_status = _qualification_status(pre_lock, production=production)
    recheck_provenance()
    if pre_status is PaperReceiptRecoveryQualificationStatus.BLOCKED:
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            "pre-lock receipt-recovery qualification blocked"
        )
    if pre_status is PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED:
        return _no_recovery_result(pre_lock)

    pre_account_id = _required_text(pre_lock, "paper_account_id")
    admission = admission_factory(pre_lock)
    with admission as held_admission:
        acquisition = getattr(held_admission, "acquisition", None)
        if (
            acquisition is None
            or getattr(acquisition, "paper_account_id", None) != pre_account_id
        ):
            raise PersonalDesktopPaperReceiptRecoveryBlockedError(
                "receipt-recovery mutex acquisition does not match the account"
            )
        if getattr(acquisition, "state", None) is not PaperAccountMutexState.OWNED:
            raise PersonalDesktopPaperReceiptRecoveryBlockedError(
                "abandoned or invalid receipt-recovery mutex ownership blocks"
            )
        recheck_provenance()
        post_lock = qualifier(
            authority,
            historical_cycle_configuration_payloads=(
                historical_cycle_configuration_payloads
            ),
        )
        post_status = _qualification_status(post_lock, production=production)
        recheck_provenance()
        if post_status is PaperReceiptRecoveryQualificationStatus.BLOCKED:
            raise PersonalDesktopPaperReceiptRecoveryBlockedError(
                "post-lock receipt-recovery qualification blocked"
            )
        post_account_id = _required_text(post_lock, "paper_account_id")
        if post_account_id != pre_account_id:
            raise PersonalDesktopPaperReceiptRecoveryBlockedError(
                "post-lock receipt-recovery account identity changed"
            )
        if post_status is PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED:
            return _no_recovery_result(post_lock)
        _require_same_recovery_target(pre_lock, post_lock)

        binding = reconstructor(
            authority,
            post_lock,
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
            operation_root=operation_root,
            calendar=calendar,
        )
        if (
            production
            and type(binding) is not _PaperReceiptRecoveryReconstructionBinding
        ):
            raise PersonalDesktopPaperReceiptRecoveryBlockedError(
                "production reconstruction binding type is invalid"
            )
        result = getattr(binding, "result", None)
        inputs = getattr(binding, "execution_inputs", None)
        _require_reconstruction_agreement(
            result,
            inputs,
            post_lock,
            acquisition.paper_account_id,
        )
        if production:
            require_validated_paper_receipt_recovery_qualification(post_lock)
        recheck_provenance()
        _require_effect_gate_state(gate_state())

        with output_capability_factory() as capability:
            before = inspector(operation_root, inputs)
            before_classification = _inspection_classification(
                before,
                result,
                allow_already_applied=True,
            )
            if before_classification is PaperOperationClassification.BLOCKED:
                recheck_provenance()
                recovery_result = recovery(
                    operation_root,
                    inputs,
                    output_capability=capability,
                )
                recovery_classification, recovery_diagnostic = _require_recovery_result(
                    recovery_result, result
                )
            else:
                recovery_classification = (
                    PaperOperationExecutionClassification.ALREADY_APPLIED
                )
                recovery_diagnostic = PaperOperationInspectionCode.ALREADY_APPLIED.value

            post_configurations = _post_read_configurations(
                historical_cycle_configuration_payloads,
                getattr(inputs, "cycle_configuration_payload", None),
            )
            post_account = post_reader(
                authority,
                historical_cycle_configuration_payloads=post_configurations,
            )
            post_evidence = post_read_validator(post_account)
            _require_post_read_agreement(post_evidence, result)
            recheck_provenance()
            after = inspector(operation_root, inputs)
            _require_final_inspection(after, result)
            recheck_provenance()
            _require_effect_gate_state(gate_state())
            return PersonalDesktopPaperReceiptRecoveryResult(
                qualification_status=(
                    PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
                ),
                paper_account_id=result.paper_account_id,
                operation_id=result.operation_id,
                application_id=result.application_id,
                predecessor_checkpoint_id=result.predecessor_checkpoint_id,
                installed_terminal_checkpoint_id=(
                    result.installed_terminal_checkpoint_id
                ),
                pre_recovery_classification=result.inspection_classification,
                recovery_classification=recovery_classification,
                recovery_diagnostic=recovery_diagnostic,
                receipt_evidence_produced=(
                    recovery_classification
                    is PaperOperationExecutionClassification.RECEIPT_RECOVERED
                ),
                post_recovery_classification=after.classification,
            )


def _require_c1_p2(
    authority: object,
    selected_snapshot: object,
) -> ValidatedProductionAuthority:
    try:
        c1 = require_validated_production_authority(authority)
        if type(selected_snapshot) is not SelectedC3SnapshotReadResult:
            raise TypeError("selected snapshot must be an exact P2 read result")
        require_selected_c3_snapshot_matches_authority(
            selected_snapshot.permit,
            selected_snapshot.audit,
            c1,
        )
        return c1
    except PersonalDesktopPaperReceiptRecoveryExecutionError:
        raise
    except Exception as error:
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            "receipt recovery lacks exact C1/P2 provenance"
        ) from error


def _qualification_status(
    value: object,
    *,
    production: bool,
) -> PaperReceiptRecoveryQualificationStatus:
    if production and type(value) is not PaperReceiptRecoveryQualificationResult:
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            "production qualification result type is invalid"
        )
    status = getattr(value, "status", None)
    if type(status) is not PaperReceiptRecoveryQualificationStatus:
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            "receipt-recovery qualification status is invalid"
        )
    return status


def _no_recovery_result(value: object) -> PersonalDesktopPaperReceiptRecoveryResult:
    account_id = _required_text(value, "paper_account_id")
    terminal = getattr(value, "terminal_checkpoint_id", None)
    diagnostic = getattr(getattr(value, "diagnostic", None), "value", None)
    if (
        type(terminal) is not UUID
        or type(diagnostic) is not str
        or getattr(value, "missing_application_id", None) is not None
        or getattr(value, "predecessor_checkpoint_id", None) is not None
    ):
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            "no-recovery qualification evidence is invalid"
        )
    return PersonalDesktopPaperReceiptRecoveryResult(
        PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED,
        account_id,
        None,
        None,
        None,
        terminal,
        None,
        None,
        diagnostic,
        False,
        None,
    )


def _required_text(value: object, name: str) -> str:
    retained = getattr(value, name, None)
    if type(retained) is not str or not retained:
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            f"receipt-recovery {name} is invalid"
        )
    return retained


def _require_same_recovery_target(before: object, after: object) -> None:
    names = (
        "paper_account_id",
        "missing_application_id",
        "predecessor_checkpoint_id",
        "terminal_checkpoint_id",
    )
    if any(getattr(before, name, None) != getattr(after, name, None) for name in names):
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            "recoverable target changed while waiting for the account mutex"
        )


def _require_reconstruction_agreement(
    result: object,
    inputs: object,
    qualification: object,
    account_id: str,
) -> None:
    intent = getattr(inputs, "intent", None)
    if (
        result is None
        or inputs is None
        or getattr(result, "paper_account_id", None) != account_id
        or getattr(result, "paper_account_id", None)
        != getattr(qualification, "paper_account_id", None)
        or getattr(result, "application_id", None)
        != getattr(qualification, "missing_application_id", None)
        or getattr(result, "predecessor_checkpoint_id", None)
        != getattr(qualification, "predecessor_checkpoint_id", None)
        or getattr(result, "installed_terminal_checkpoint_id", None)
        != getattr(qualification, "terminal_checkpoint_id", None)
        or type(getattr(result, "operation_id", None)) is not UUID
        or getattr(result, "operation_id", None)
        != getattr(intent, "operation_id", None)
        or getattr(result, "application_id", None)
        != getattr(inputs, "application_id", None)
        or getattr(result, "inspection_classification", None)
        is not PaperOperationClassification.BLOCKED
        or getattr(result, "inspection_diagnostic", None)
        is not PaperOperationInspectionCode.FINALIZED_TRANSITION_WITHOUT_RECEIPT
    ):
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            "reconstruction does not reconcile with the locked recovery target"
        )


def _production_gate_state() -> _EffectGateState:
    return _EffectGateState(
        PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED,
        supervised_execution.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
    )


def _require_effect_gate_state(state: _EffectGateState) -> None:
    if (
        type(state) is not _EffectGateState
        or state.receipt_recovery is not True
        or state.publication is not False
        or state.provisioning_recovery is not False
        or state.supervised_execution is not False
    ):
        raise PersonalDesktopPaperReceiptRecoveryEffectsDisabledError(
            "Paper-v2 receipt-recovery effect-gate state is invalid"
        )


def _inspection_classification(
    inspection: object,
    result: object,
    *,
    allow_already_applied: bool,
) -> PaperOperationClassification:
    classification = getattr(inspection, "classification", None)
    diagnostic = getattr(inspection, "diagnostics", None)
    expected = (
        (PaperOperationClassification.BLOCKED,)
        if not allow_already_applied
        else (
            PaperOperationClassification.BLOCKED,
            PaperOperationClassification.ALREADY_APPLIED,
        )
    )
    exact_diagnostic = {
        PaperOperationClassification.BLOCKED: (
            PaperOperationInspectionCode.FINALIZED_TRANSITION_WITHOUT_RECEIPT,
        ),
        PaperOperationClassification.ALREADY_APPLIED: (
            PaperOperationInspectionCode.ALREADY_APPLIED,
        ),
    }.get(classification)
    if (
        classification not in expected
        or diagnostic != exact_diagnostic
        or getattr(inspection, "operation_id", None)
        != getattr(result, "operation_id", None)
        or getattr(inspection, "application_id", None)
        != getattr(result, "application_id", None)
        or getattr(inspection, "terminal_checkpoint_id", None)
        != getattr(result, "predecessor_checkpoint_id", None)
    ):
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            "Architecture-67 inspection did not match the recovery target"
        )
    return classification


def _require_recovery_result(
    value: object,
    reconstruction: object,
) -> tuple[PaperOperationExecutionClassification, str]:
    classification = getattr(value, "classification", None)
    diagnostic = getattr(value, "diagnostic_code", None)
    expected_diagnostic = {
        PaperOperationExecutionClassification.RECEIPT_RECOVERED: (
            PaperOperationExecutionDiagnosticCode.RECEIPT_RECOVERED.value
        ),
        PaperOperationExecutionClassification.ALREADY_APPLIED: (
            PaperOperationInspectionCode.ALREADY_APPLIED.value
        ),
    }.get(classification)
    expected_pre = (
        PaperOperationClassification.BLOCKED
        if classification is PaperOperationExecutionClassification.RECEIPT_RECOVERED
        else PaperOperationClassification.ALREADY_APPLIED
    )
    if (
        classification
        not in {
            PaperOperationExecutionClassification.RECEIPT_RECOVERED,
            PaperOperationExecutionClassification.ALREADY_APPLIED,
        }
        or diagnostic != expected_diagnostic
        or getattr(value, "operation_id", None)
        != getattr(reconstruction, "operation_id", None)
        or getattr(value, "application_id", None)
        != getattr(reconstruction, "application_id", None)
        or getattr(value, "terminal_checkpoint_id", None)
        != getattr(reconstruction, "predecessor_checkpoint_id", None)
        or getattr(value, "pre_execution_classification", None) is not expected_pre
        or (
            classification is PaperOperationExecutionClassification.RECEIPT_RECOVERED
            and (
                getattr(value, "successor_checkpoint_id", None)
                != getattr(reconstruction, "installed_terminal_checkpoint_id", None)
                or getattr(value, "receipt_path", None) is None
            )
        )
    ):
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            "Architecture-67 recovery result did not reconcile"
        )
    assert type(diagnostic) is str
    return classification, diagnostic


def _post_read_configurations(
    historical: tuple[bytes, ...],
    current: object,
) -> tuple[bytes, ...]:
    if type(historical) is not tuple or type(current) is not bytes or not current:
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            "post-recovery configuration dependencies are invalid"
        )
    retained: dict[tuple[str, int], bytes] = {}
    ordered: list[bytes] = []
    for payload in (*historical, current):
        if type(payload) is not bytes or not payload:
            raise PersonalDesktopPaperReceiptRecoveryBlockedError(
                "post-recovery configuration dependency is invalid"
            )
        key = (sha256(payload).hexdigest(), len(payload))
        previous = retained.get(key)
        if previous is not None:
            if previous != payload:
                raise PersonalDesktopPaperReceiptRecoveryBlockedError(
                    "configuration digest/length collision is unsafe"
                )
            continue
        retained[key] = payload
        ordered.append(payload)
    return tuple(ordered)


def _require_post_read_agreement(evidence: object, result: object) -> None:
    anchor = getattr(evidence, "anchor", None)
    lineage = getattr(evidence, "lineage", None)
    receipts = getattr(evidence, "receipts", None)
    if (
        getattr(anchor, "paper_account_id", None)
        != getattr(result, "paper_account_id", None)
        or getattr(lineage, "terminal_checkpoint_id", None)
        != getattr(result, "installed_terminal_checkpoint_id", None)
        or not isinstance(receipts, tuple)
    ):
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            "post-recovery ordinary account evidence does not reconcile"
        )
    matching = tuple(
        receipt
        for receipt in receipts
        if getattr(receipt, "receipt_id", None) == getattr(result, "operation_id", None)
        and getattr(receipt, "application_id", None)
        == getattr(result, "application_id", None)
    )
    if len(matching) != 1:
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            "post-recovery ordinary account lacks the exact verified receipt"
        )
    receipt = matching[0]
    intent = getattr(receipt, "intent", None)
    prior = getattr(receipt, "prior_lineage_evidence", None)
    successor = getattr(receipt, "successor_lineage_evidence", None)
    if (
        getattr(receipt, "status", None) is not PaperOperationStatus.COMPLETED
        or getattr(intent, "operation_id", None)
        != getattr(result, "operation_id", None)
        or getattr(prior, "terminal_checkpoint_id", None)
        != getattr(result, "predecessor_checkpoint_id", None)
        or getattr(successor, "terminal_checkpoint_id", None)
        != getattr(result, "installed_terminal_checkpoint_id", None)
    ):
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            "post-recovery receipt lineage does not reconcile"
        )


def _require_final_inspection(inspection: object, result: object) -> None:
    if (
        _inspection_classification(
            inspection,
            result,
            allow_already_applied=True,
        )
        is not PaperOperationClassification.ALREADY_APPLIED
    ):
        raise PersonalDesktopPaperReceiptRecoveryBlockedError(
            "final Architecture-67 inspection is not exact ALREADY_APPLIED"
        )
