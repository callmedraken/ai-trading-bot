"""D8-R1 read-only qualification of one single deferred paper settlement."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
)
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    derive_checkpointed_verified_snapshot_application_id,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    require_selected_c3_snapshot_matches_authority,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperStrategyPlanArtifactBinding,
    complete_manual_paper_strategy_plan,
    verify_manual_paper_strategy_plan,
)
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
)
from trading_bot.runtime.personal_desktop_historical_cycle_configurations import (
    resolve_personal_desktop_historical_cycle_configurations,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexState,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObservation,
    WindowsTradingTokenObserver,
    require_trading_token,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    SessionIndexedSelectedC3SnapshotReadResult,
    WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    personal_desktop_unattended_effect_gate_state,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    completed_xnys_session_at,
    next_xnys_execution_session,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_intent import (
    PersonalDesktopUnattendedPaperDecisionC3Evidence,
    PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    personal_desktop_unattended_decision_calendar,
    verify_personal_desktop_unattended_paper_decision_intent,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    SingleDeferredDecisionClassification as Discovery,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    SingleDeferredDecisionResult,
    find_single_deferred_unattended_decision,
    require_single_deferred_unattended_decision,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation import (
    create_personal_desktop_unattended_paper_invocation,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageClassification,
)
from trading_bot.runtime.verified_c3_daily_bar_open import (
    C3VerifiedDailyBarOpenBinding,
    build_c3_verified_daily_bar_open_binding,
)
from trading_bot.runtime.windows_authority_validation import (
    acquire_validated_production_authority,
    require_validated_production_authority,
)

from .personal_desktop_unattended_paper_startup_qualification import (
    PersonalDesktopUnattendedPaperStartupBlockedReason,
    PersonalDesktopUnattendedPaperStartupDiagnostic,
    PersonalDesktopUnattendedPaperStartupQualificationResult,
    PersonalDesktopUnattendedPaperStartupStatus,
    qualify_personal_desktop_unattended_paper_startup_from_verified_plan,
)


class DeferredSettlementQualificationClassification(StrEnum):
    """D8-R1 diagnostic outcomes; none grants execution authority."""

    NO_DEFERRED_SETTLEMENT = "NO_DEFERRED_SETTLEMENT"
    EXECUTION_READY = "EXECUTION_READY"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    RECEIPT_RECOVERY_REQUIRED = "RECEIPT_RECOVERY_REQUIRED"
    BLOCKED = "BLOCKED"


Status = DeferredSettlementQualificationClassification


@dataclass(frozen=True, slots=True)
class DeferredSettlementQualificationResult:
    """Only bounded identifiers and classifications; no reusable authority."""

    classification: DeferredSettlementQualificationClassification
    current_completed_session: TradingSession | None = None
    deferred_execution_session: TradingSession | None = None
    decision_selected_session: TradingSession | None = None
    decision_id: UUID | None = None
    decision_selected_snapshot_id: UUID | None = None
    execution_selected_snapshot_id: UUID | None = None
    final_plan_id: UUID | None = None
    invocation_id: UUID | None = None
    operation_id: UUID | None = None
    application_id: UUID | None = None
    account_predecessor_checkpoint_id: UUID | None = None
    terminal_checkpoint_id: UUID | None = None
    startup_status: PersonalDesktopUnattendedPaperStartupStatus | None = None
    all_eight_gates_closed: bool = False
    real_effect_performed: bool = False
    startup_diagnostic: PersonalDesktopUnattendedPaperStartupDiagnostic | None = None
    startup_storage_classification: (
        PersonalDesktopUnattendedInvocationStorageClassification | None
    ) = None
    startup_operation_classification: PaperOperationClassification | None = None
    startup_operation_diagnostic: PaperOperationInspectionCode | None = None
    startup_mutex_acquisition_state: PaperAccountMutexState | None = None
    startup_blocked_reason: (
        PersonalDesktopUnattendedPaperStartupBlockedReason | None
    ) = None

    def __post_init__(self) -> None:
        startup_mapping = {
            PersonalDesktopUnattendedPaperStartupStatus.HEALTHY_NO_PENDING_INVOCATION: (
                Status.EXECUTION_READY,
                PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_ABSENT_PENDING,
            ),
            PersonalDesktopUnattendedPaperStartupStatus.READY_SAME_INVOCATION: (
                Status.EXECUTION_READY,
                PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_IDENTICAL_PENDING,
            ),
            PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED: (
                Status.ALREADY_APPLIED,
                PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_ALREADY_APPLIED,
            ),
            PersonalDesktopUnattendedPaperStartupStatus.RECEIPT_RECOVERY_REQUIRED: (
                Status.RECEIPT_RECOVERY_REQUIRED,
                PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_TERMINAL_RECEIPT_MISSING,
            ),
            PersonalDesktopUnattendedPaperStartupStatus.BLOCKED: (
                Status.BLOCKED,
                PersonalDesktopUnattendedPaperStartupDiagnostic.QUALIFICATION_BLOCKED,
            ),
        }
        startup_diagnostic_fields = (
            self.startup_diagnostic,
            self.startup_blocked_reason,
            self.startup_storage_classification,
            self.startup_operation_classification,
            self.startup_operation_diagnostic,
            self.startup_mutex_acquisition_state,
        )
        startup_contract_valid = (
            self.startup_status is None
            and all(value is None for value in startup_diagnostic_fields)
        ) or (
            type(self.startup_status) is PersonalDesktopUnattendedPaperStartupStatus
            and startup_mapping.get(self.startup_status)
            == (self.classification, self.startup_diagnostic)
            and self.all_eight_gates_closed is True
            and (
                (
                    self.startup_status
                    is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
                    and type(self.startup_blocked_reason)
                    is PersonalDesktopUnattendedPaperStartupBlockedReason
                )
                or (
                    self.startup_status
                    is not PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
                    and self.startup_blocked_reason is None
                )
            )
        )
        if (
            type(self.classification) is not Status
            or any(
                value is not None and type(value) is not TradingSession
                for value in (
                    self.current_completed_session,
                    self.deferred_execution_session,
                    self.decision_selected_session,
                )
            )
            or any(
                value is not None and type(value) is not UUID
                for value in (
                    self.decision_id,
                    self.decision_selected_snapshot_id,
                    self.execution_selected_snapshot_id,
                    self.final_plan_id,
                    self.invocation_id,
                    self.operation_id,
                    self.application_id,
                    self.account_predecessor_checkpoint_id,
                    self.terminal_checkpoint_id,
                )
            )
            or (
                self.startup_status is not None
                and type(self.startup_status)
                is not PersonalDesktopUnattendedPaperStartupStatus
            )
            or not startup_contract_valid
            or type(self.all_eight_gates_closed) is not bool
            or any(
                value is not None and type(value) is not expected_type
                for value, expected_type in (
                    (
                        self.startup_diagnostic,
                        PersonalDesktopUnattendedPaperStartupDiagnostic,
                    ),
                    (
                        self.startup_blocked_reason,
                        PersonalDesktopUnattendedPaperStartupBlockedReason,
                    ),
                    (
                        self.startup_storage_classification,
                        PersonalDesktopUnattendedInvocationStorageClassification,
                    ),
                    (
                        self.startup_operation_classification,
                        PaperOperationClassification,
                    ),
                    (self.startup_operation_diagnostic, PaperOperationInspectionCode),
                    (self.startup_mutex_acquisition_state, PaperAccountMutexState),
                )
            )
            or self.real_effect_performed is not False
            or (
                self.classification
                in {
                    Status.EXECUTION_READY,
                    Status.ALREADY_APPLIED,
                    Status.RECEIPT_RECOVERY_REQUIRED,
                }
                and (
                    self.current_completed_session is None
                    or self.deferred_execution_session is None
                    or self.deferred_execution_session >= self.current_completed_session
                )
            )
            or (
                self.classification is Status.NO_DEFERRED_SETTLEMENT
                and (
                    self.current_completed_session is None
                    or self.deferred_execution_session is not None
                    or any(
                        value is not None
                        for value in (
                            self.decision_id,
                            self.final_plan_id,
                            self.startup_status,
                        )
                    )
                )
            )
        ):
            raise ValueError("D8-R1 settlement qualification result is invalid")


@dataclass(frozen=True, slots=True)
class DisposableDeferredSettlementQualificationDependencies:
    """Disposable read-only seams; production accepts zero arguments."""

    gate_state: Callable[[], tuple[bool, ...]]
    acquire_c1: Callable[[], Any]
    validate_c1: Callable[[Any], Any]
    observe_token: Callable[[], TradingTokenObservation]
    now: Callable[[], datetime]
    discover: Callable[[Any], SingleDeferredDecisionResult]
    require_discovery: Callable[..., Any]
    read_selected: Callable[..., SessionIndexedSelectedC3SnapshotReadResult]
    require_selected: Callable[..., None]
    build_open: Callable[..., C3VerifiedDailyBarOpenBinding]
    complete_plan: Callable[..., ManualPaperStrategyPlanArtifactBinding]
    verify_plan: Callable[..., ManualPaperStrategyPlanArtifactBinding]
    historical_configurations: Callable[[Any], tuple[bytes, ...]]
    startup: Callable[..., PersonalDesktopUnattendedPaperStartupQualificationResult]


def qualify_personal_desktop_single_deferred_settlement() -> (
    DeferredSettlementQualificationResult
):
    """Independently qualify current durable settlement truth with all gates closed."""

    try:
        return _run(_production_dependencies())
    except Exception:
        return DeferredSettlementQualificationResult(Status.BLOCKED)


def qualify_personal_desktop_single_deferred_settlement_for_test(
    dependencies: DisposableDeferredSettlementQualificationDependencies,
) -> DeferredSettlementQualificationResult:
    """Exercise the full D8-R1 composition using only disposable seams."""

    if type(dependencies) is not DisposableDeferredSettlementQualificationDependencies:
        raise TypeError("D8-R1 disposable dependencies are invalid")
    return _run(dependencies)


def _require_gates(d: DisposableDeferredSettlementQualificationDependencies) -> None:
    gates = d.gate_state()
    if (
        type(gates) is not tuple
        or len(gates) != 8
        or any(v is not False for v in gates)
    ):
        raise ValueError("D8-R1 requires eight exact closed effect gates")


def _token(
    d: DisposableDeferredSettlementQualificationDependencies,
) -> TradingTokenObservation:
    observation = d.observe_token()
    require_trading_token(
        PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
        observation,
    )
    return observation


def _final_authority(
    d: DisposableDeferredSettlementQualificationDependencies, c1: Any, token: Any
) -> None:
    if d.validate_c1(d.acquire_c1()) != c1 or _token(d) != token:
        raise ValueError("D8-R1 C1 or Trading token changed")
    _require_gates(d)


def _selected(
    d: DisposableDeferredSettlementQualificationDependencies,
    c1: Any,
    session: TradingSession,
) -> SessionIndexedSelectedC3SnapshotReadResult:
    result = d.read_selected(c1, session)
    if (
        type(result) is not SessionIndexedSelectedC3SnapshotReadResult
        or result.session != session
    ):
        raise ValueError("D8-R1 session-indexed selected C3 is invalid")
    d.require_selected(c1, result)
    return result


def _require_c3_evidence(
    expected: PersonalDesktopUnattendedPaperDecisionC3Evidence,
    actual: SessionIndexedSelectedC3SnapshotReadResult,
) -> None:
    audit = actual.selected.audit
    if (
        actual.session != expected.selected_session
        or actual.selected.snapshot_bytes != expected.snapshot_artifact
        or audit.selection_id != expected.selection_id
        or audit.session_id != expected.session_id
        or audit.terminal_id != expected.terminal_id
        or audit.snapshot_id != expected.snapshot_id
        or audit.artifact_sha256 != expected.artifact_sha256
        or audit.artifact_byte_length != expected.artifact_byte_length
    ):
        raise ValueError("D8-R1 durable selected C3 differs from current C1")


def _require_plan(
    decision_binding: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    execution: SessionIndexedSelectedC3SnapshotReadResult,
    opened: C3VerifiedDailyBarOpenBinding,
    plan_binding: ManualPaperStrategyPlanArtifactBinding,
    d: DisposableDeferredSettlementQualificationDependencies,
) -> None:
    if type(plan_binding) is not ManualPaperStrategyPlanArtifactBinding:
        raise TypeError("D8-R1 completed plan binding is invalid")
    replayed = d.verify_plan(
        plan_binding.artifact_bytes,
        personal_desktop_unattended_decision_calendar(),
        expected_sha256=plan_binding.artifact_sha256,
        expected_byte_length=plan_binding.artifact_byte_length,
        expected_checkpointed_request=plan_binding.checkpointed_request,
    )
    decision = decision_binding.decision
    prepared = decision.prepared_decision
    plan = plan_binding.plan
    references = plan.request_core.open_references
    if (
        replayed != plan_binding
        or plan.paper_account_id != decision.paper_account_id
        or plan.paper_account_id
        != PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.paper_account_id
        or plan.prior_checkpoint != prepared.prior_checkpoint
        or plan.prior_checkpoint.checkpoint_id != decision.predecessor_checkpoint_id
        or plan.selected_snapshot_artifact != decision.current_c3.snapshot_artifact
        or plan.selected_c3_assertion != prepared.selected_c3_assertion
        or plan.history_seed_artifact != prepared.history_seed_artifact
        or plan.strategy_config != prepared.strategy_config
        or plan.caller_idempotency_key != prepared.caller_idempotency_key
        or plan.strategy_run_id != prepared.strategy_run_id
        or plan.strategy_step_index != prepared.strategy_step_index
        or plan.signal_status != prepared.signal_status
        or plan.strategy_proposal != prepared.strategy_proposal
        or plan.target != prepared.target
        or len(references) != 1
        or references[0].symbol != opened.symbol
        or references[0].session != opened.session
        or references[0].caller_asserted_open_reference_price != opened.open_price
        or opened.session != decision.intended_execution_session
        or execution.session != opened.session
    ):
        raise ValueError("D8-R1 final plan differs from decision and verified open")


def _startup_status(
    startup: PersonalDesktopUnattendedPaperStartupQualificationResult,
    binding: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    plan: ManualPaperStrategyPlanArtifactBinding,
) -> Status:
    if type(startup) is not PersonalDesktopUnattendedPaperStartupQualificationResult:
        raise TypeError("D8-R1 startup result is invalid")
    startup.__post_init__()
    decision = binding.decision
    expected_application = derive_checkpointed_verified_snapshot_application_id(
        decision.predecessor_checkpoint_id,
        plan.checkpointed_request.request_id,
    )
    if startup.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED:
        return Status.BLOCKED
    if startup.paper_account_id != decision.paper_account_id:
        raise ValueError("D8-R1 startup account differs from the decision")
    if (
        startup.status
        is PersonalDesktopUnattendedPaperStartupStatus.RECEIPT_RECOVERY_REQUIRED
    ):
        if (
            startup.recovery_predecessor_checkpoint_id
            != decision.predecessor_checkpoint_id
            or startup.recovery_missing_application_id != expected_application
        ):
            raise ValueError("D8-R1 recovery is unrelated to the exact plan")
        return Status.RECEIPT_RECOVERY_REQUIRED
    invocation = create_personal_desktop_unattended_paper_invocation(
        plan, personal_desktop_unattended_decision_calendar()
    )
    if (
        startup.selected_snapshot_id != decision.current_c3.snapshot_id
        or startup.invocation_id != invocation.invocation_id
        or startup.application_id != expected_application
        or startup.operation_id is None
        or startup.terminal_checkpoint_id != decision.predecessor_checkpoint_id
    ):
        raise ValueError("D8-R1 startup identities differ from the exact plan")
    if startup.status in {
        PersonalDesktopUnattendedPaperStartupStatus.HEALTHY_NO_PENDING_INVOCATION,
        PersonalDesktopUnattendedPaperStartupStatus.READY_SAME_INVOCATION,
    }:
        return Status.EXECUTION_READY
    if startup.status is PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED:
        return Status.ALREADY_APPLIED
    raise ValueError("D8-R1 startup status is invalid")


def _run(
    d: DisposableDeferredSettlementQualificationDependencies,
) -> DeferredSettlementQualificationResult:
    try:
        _require_gates(d)
        token = _token(d)
        c1 = d.validate_c1(d.acquire_c1())
        completed = completed_xnys_session_at(d.now())
        discovery = d.discover(c1)
        if (
            type(discovery) is not SingleDeferredDecisionResult
            or discovery.current_completed_session != completed
            or discovery.classification is Discovery.BLOCKED
        ):
            raise ValueError("D8-R1 complete decision discovery is blocked")
        if discovery.classification is Discovery.NONE:
            if discovery.binding is not None:
                raise ValueError("D8-R1 NONE discovery carries a decision")
            _final_authority(d, c1, token)
            return DeferredSettlementQualificationResult(
                Status.NO_DEFERRED_SETTLEMENT,
                current_completed_session=completed,
                all_eight_gates_closed=True,
            )
        binding = d.require_discovery(c1, discovery)
        if (
            binding is not discovery.binding
            or type(binding)
            is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
            or discovery.execution_session is None
            or discovery.execution_session >= completed
        ):
            raise ValueError(
                "D8-R1 discovery lacks exact deferred current-C1 provenance"
            )
        replayed = verify_personal_desktop_unattended_paper_decision_intent(
            binding.artifact_bytes,
            personal_desktop_unattended_decision_calendar(),
            expected_decision_id=discovery.decision_id,
            expected_artifact_sha256=binding.artifact_sha256,
            expected_artifact_byte_length=binding.artifact_byte_length,
        )
        if (
            replayed != binding
            or binding.decision.intended_execution_session
            != discovery.execution_session
        ):
            raise ValueError("D8-R1 finalized decision is inconsistent")
        decision = binding.decision
        execution = _selected(d, c1, discovery.execution_session)
        original = _selected(d, c1, decision.selected_session)
        _require_c3_evidence(decision.current_c3, original)
        if not decision.history_c3:
            raise ValueError("D8-R1 selected C3 history is empty")
        cursor = decision.history_c3[0].selected_session
        for expected in decision.history_c3:
            if expected.selected_session != cursor:
                raise ValueError("D8-R1 selected C3 history order has a gap")
            _require_c3_evidence(expected, _selected(d, c1, cursor))
            cursor = next_xnys_execution_session(cursor)
        if cursor != decision.selected_session:
            raise ValueError("D8-R1 history does not end at decision session")
        opened = d.build_open(execution.selected, c1)
        if type(opened) is not C3VerifiedDailyBarOpenBinding:
            raise TypeError("D8-R1 verified C3 open binding is invalid")
        plan = d.complete_plan(
            decision.prepared_decision,
            opened,
            personal_desktop_unattended_decision_calendar(),
        )
        _require_plan(binding, execution, opened, plan, d)
        historical = d.historical_configurations(c1)
        if type(historical) is not tuple or any(
            type(item) is not bytes for item in historical
        ):
            raise TypeError("D8-R1 historical configuration payloads are invalid")
        startup = d.startup(
            c1,
            original.selected,
            plan,
            historical_cycle_configuration_payloads=historical,
        )
        status = _startup_status(startup, binding, plan)
        _final_authority(d, c1, token)
        return DeferredSettlementQualificationResult(
            status,
            current_completed_session=completed,
            deferred_execution_session=discovery.execution_session,
            decision_selected_session=decision.selected_session,
            decision_id=decision.decision_id,
            decision_selected_snapshot_id=decision.current_c3.snapshot_id,
            execution_selected_snapshot_id=execution.selected.audit.snapshot_id,
            final_plan_id=plan.plan.plan_id,
            invocation_id=startup.invocation_id,
            operation_id=startup.operation_id,
            application_id=startup.application_id,
            account_predecessor_checkpoint_id=decision.predecessor_checkpoint_id,
            terminal_checkpoint_id=startup.terminal_checkpoint_id,
            startup_status=startup.status,
            all_eight_gates_closed=True,
            startup_diagnostic=startup.diagnostic,
            startup_storage_classification=startup.storage_classification,
            startup_operation_classification=startup.operation_classification,
            startup_operation_diagnostic=startup.operation_diagnostic,
            startup_mutex_acquisition_state=startup.mutex_acquisition_state,
            startup_blocked_reason=startup.blocked_reason,
        )
    except Exception:
        return DeferredSettlementQualificationResult(Status.BLOCKED)


def _production_dependencies() -> DisposableDeferredSettlementQualificationDependencies:
    retained_readers: list[WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority] = []
    observer = WindowsTradingTokenObserver()

    def read_selected(
        c1: Any, session: TradingSession
    ) -> SessionIndexedSelectedC3SnapshotReadResult:
        reader = WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority(c1)
        retained_readers.append(reader)
        return reader.read_selected_snapshot_for_session(session)

    def require_selected(
        c1: Any, selected: SessionIndexedSelectedC3SnapshotReadResult
    ) -> None:
        require_selected_c3_snapshot_matches_authority(
            selected.selected.permit,
            selected.selected.audit,
            require_validated_production_authority(c1),
        )

    def discover(c1: Any) -> SingleDeferredDecisionResult:
        return find_single_deferred_unattended_decision(c1)

    def require_discovery(c1: Any, result: SingleDeferredDecisionResult) -> Any:
        binding = require_single_deferred_unattended_decision(result, c1)
        if binding is not result.binding:
            raise ValueError("D8-R1 discovery lacks exact current-C1 provenance")
        return binding

    return DisposableDeferredSettlementQualificationDependencies(
        gate_state=personal_desktop_unattended_effect_gate_state,
        acquire_c1=acquire_validated_production_authority,
        validate_c1=require_validated_production_authority,
        observe_token=observer.observe,
        now=lambda: datetime.now(UTC),
        discover=discover,
        require_discovery=require_discovery,
        read_selected=read_selected,
        require_selected=require_selected,
        build_open=build_c3_verified_daily_bar_open_binding,
        complete_plan=complete_manual_paper_strategy_plan,
        verify_plan=verify_manual_paper_strategy_plan,
        historical_configurations=resolve_personal_desktop_historical_cycle_configurations,
        startup=qualify_personal_desktop_unattended_paper_startup_from_verified_plan,
    )
