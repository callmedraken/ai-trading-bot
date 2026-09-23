"""D8-R2 source-owned, one-attempt single-deferred Paper-v2 settlement boundary."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from trading_bot.cli.paper_operation_execution import (
    PaperOperationExecutionClassification,
)
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
)
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    derive_checkpointed_verified_snapshot_application_id,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadResult,
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
    PersonalDesktopUnattendedInvocationStorageClassification as Storage,
)
from trading_bot.runtime.verified_c3_daily_bar_open import (
    C3VerifiedDailyBarOpenBinding,
    build_c3_verified_daily_bar_open_binding,
)
from trading_bot.runtime.windows_authority_validation import (
    acquire_validated_production_authority,
    require_validated_production_authority,
)

from . import personal_desktop_unattended_paper_operation_execution as pd4d
from .personal_desktop_unattended_paper_startup_qualification import (
    PersonalDesktopUnattendedPaperStartupQualificationResult,
    PersonalDesktopUnattendedPaperStartupStatus,
    qualify_personal_desktop_unattended_paper_startup_from_verified_plan,
)


class DeferredSettlementExecutionClassification(StrEnum):
    SETTLEMENT_NOT_READY = "SETTLEMENT_NOT_READY"
    SETTLEMENT_COMPLETED = "SETTLEMENT_COMPLETED"
    SETTLEMENT_ALREADY_APPLIED = "SETTLEMENT_ALREADY_APPLIED"
    RECEIPT_RECOVERY_REQUIRED = "RECEIPT_RECOVERY_REQUIRED"
    SETTLEMENT_OUTCOME_AMBIGUOUS = "SETTLEMENT_OUTCOME_AMBIGUOUS"
    BLOCKED = "BLOCKED"


Status = DeferredSettlementExecutionClassification
_CLOSED = (False,) * 8
_EXECUTION_OPEN = (False,) * 6 + (True, False)


@dataclass(frozen=True, slots=True)
class DeferredSettlementExecutionResult:
    """Bounded diagnostic evidence; D9 remains the acceptance authority."""

    classification: DeferredSettlementExecutionClassification
    current_completed_session: TradingSession | None = None
    deferred_execution_session: TradingSession | None = None
    decision_id: UUID | None = None
    final_plan_id: UUID | None = None
    invocation_id: UUID | None = None
    operation_id: UUID | None = None
    application_id: UUID | None = None
    account_predecessor_checkpoint_id: UUID | None = None
    final_checkpoint_id: UUID | None = None
    all_eight_gates_closed: bool = False
    real_effect_performed: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.classification) is not Status
            or (
                self.current_completed_session is not None
                and type(self.current_completed_session) is not TradingSession
            )
            or (
                self.deferred_execution_session is not None
                and type(self.deferred_execution_session) is not TradingSession
            )
            or any(
                value is not None and type(value) is not UUID
                for value in (
                    self.decision_id,
                    self.final_plan_id,
                    self.invocation_id,
                    self.operation_id,
                    self.application_id,
                    self.account_predecessor_checkpoint_id,
                    self.final_checkpoint_id,
                )
            )
            or type(self.all_eight_gates_closed) is not bool
            or type(self.real_effect_performed) is not bool
            or (
                self.current_completed_session is not None
                and self.deferred_execution_session is not None
                and self.deferred_execution_session >= self.current_completed_session
            )
            or (
                self.real_effect_performed
                and self.classification
                not in {
                    Status.SETTLEMENT_COMPLETED,
                    Status.SETTLEMENT_ALREADY_APPLIED,
                    Status.RECEIPT_RECOVERY_REQUIRED,
                    Status.SETTLEMENT_OUTCOME_AMBIGUOUS,
                }
            )
        ):
            raise ValueError("D8-R2 settlement result is invalid")


@dataclass(frozen=True, slots=True)
class DisposableDeferredSettlementExecutionDependencies:
    """Read-only and disposable execution seams; production has no parameters."""

    gate_state: Callable[[], tuple[bool, ...]]
    acquire_c1: Callable[[], Any]
    validate_c1: Callable[[Any], Any]
    observe_token: Callable[[], TradingTokenObservation]
    now: Callable[[], datetime]
    discover: Callable[..., SingleDeferredDecisionResult]
    require_discovery: Callable[..., Any]
    read_selected: Callable[..., SessionIndexedSelectedC3SnapshotReadResult]
    require_selected: Callable[..., None]
    build_open: Callable[..., C3VerifiedDailyBarOpenBinding]
    complete_plan: Callable[..., ManualPaperStrategyPlanArtifactBinding]
    verify_plan: Callable[..., ManualPaperStrategyPlanArtifactBinding]
    historical_configurations: Callable[[Any], tuple[bytes, ...]]
    startup: Callable[..., PersonalDesktopUnattendedPaperStartupQualificationResult]
    execute: Callable[..., pd4d.PersonalDesktopUnattendedPaperOperationResult]


@dataclass(frozen=True, slots=True)
class _Settlement:
    c1: Any
    token: TradingTokenObservation
    completed: TradingSession
    execution_session: TradingSession
    binding: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
    original: SelectedC3SnapshotReadResult
    plan: ManualPaperStrategyPlanArtifactBinding
    historical: tuple[bytes, ...]
    startup: PersonalDesktopUnattendedPaperStartupQualificationResult
    status: Status


def execute_personal_desktop_single_deferred_settlement() -> (
    DeferredSettlementExecutionResult
):
    """Freshly rederive and, only if eligible, attempt one exact settlement."""

    try:
        dependencies = _production_dependencies()
    except Exception:
        return DeferredSettlementExecutionResult(Status.BLOCKED)
    return _run(dependencies)


def execute_personal_desktop_single_deferred_settlement_for_test(
    dependencies: DisposableDeferredSettlementExecutionDependencies,
) -> DeferredSettlementExecutionResult:
    """Exercise D8-R2 with disposable evidence and a non-production executor."""

    if type(dependencies) is not DisposableDeferredSettlementExecutionDependencies:
        raise TypeError("D8-R2 disposable dependencies are invalid")
    if (
        dependencies.execute
        is pd4d.execute_personal_desktop_unattended_paper_operation_from_verified_plan
    ):
        raise TypeError("D8-R2 test seam rejects the production executor")
    return _run(dependencies)


def _require_gates(
    d: DisposableDeferredSettlementExecutionDependencies, expected: tuple[bool, ...]
) -> None:
    gates = d.gate_state()
    if (
        type(gates) is not tuple
        or gates != expected
        or any(type(v) is not bool for v in gates)
    ):
        raise ValueError("D8-R2 effect gates differ from the exact expected state")


def _token(
    d: DisposableDeferredSettlementExecutionDependencies,
) -> TradingTokenObservation:
    observation = d.observe_token()
    require_trading_token(
        PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
        observation,
    )
    return observation


def _final_authority(
    d: DisposableDeferredSettlementExecutionDependencies,
    c1: Any,
    token: TradingTokenObservation,
) -> None:
    _require_gates(d, _CLOSED)
    if d.validate_c1(d.acquire_c1()) != c1 or _token(d) != token:
        raise ValueError("D8-R2 C1 or Trading token changed")
    _require_gates(d, _CLOSED)


def _selected(
    d: DisposableDeferredSettlementExecutionDependencies,
    c1: Any,
    session: TradingSession,
) -> SessionIndexedSelectedC3SnapshotReadResult:
    result = d.read_selected(c1, session)
    if (
        type(result) is not SessionIndexedSelectedC3SnapshotReadResult
        or result.session != session
    ):
        raise ValueError("D8-R2 selected C3 session is invalid")
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
        raise ValueError("D8-R2 selected C3 differs from finalized decision")


def _require_plan(
    binding: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    execution: SessionIndexedSelectedC3SnapshotReadResult,
    opened: C3VerifiedDailyBarOpenBinding,
    plan_binding: ManualPaperStrategyPlanArtifactBinding,
    d: DisposableDeferredSettlementExecutionDependencies,
) -> None:
    if type(plan_binding) is not ManualPaperStrategyPlanArtifactBinding:
        raise TypeError("D8-R2 completed plan binding is invalid")
    replayed = d.verify_plan(
        plan_binding.artifact_bytes,
        personal_desktop_unattended_decision_calendar(),
        expected_sha256=plan_binding.artifact_sha256,
        expected_byte_length=plan_binding.artifact_byte_length,
        expected_checkpointed_request=plan_binding.checkpointed_request,
    )
    decision = binding.decision
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
        raise ValueError("D8-R2 final plan differs from verified decision/open")


def _startup_status(
    startup: PersonalDesktopUnattendedPaperStartupQualificationResult,
    binding: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    plan: ManualPaperStrategyPlanArtifactBinding,
) -> Status:
    if type(startup) is not PersonalDesktopUnattendedPaperStartupQualificationResult:
        raise TypeError("D8-R2 startup result is invalid")
    startup.__post_init__()
    decision = binding.decision
    expected_application = derive_checkpointed_verified_snapshot_application_id(
        decision.predecessor_checkpoint_id, plan.checkpointed_request.request_id
    )
    if startup.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED:
        return Status.BLOCKED
    if startup.paper_account_id != decision.paper_account_id:
        raise ValueError("D8-R2 startup account differs from decision")
    if startup.mutex_acquisition_state is not PaperAccountMutexState.OWNED:
        raise ValueError("D8-R2 startup lacks completed mutex-scoped reconciliation")
    if (
        startup.status
        is PersonalDesktopUnattendedPaperStartupStatus.RECEIPT_RECOVERY_REQUIRED
    ):
        if (
            startup.recovery_predecessor_checkpoint_id
            != decision.predecessor_checkpoint_id
            or startup.recovery_missing_application_id != expected_application
        ):
            raise ValueError("D8-R2 recovery is unrelated to exact plan")
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
        raise ValueError("D8-R2 startup identities differ from exact plan")
    if startup.status in {
        PersonalDesktopUnattendedPaperStartupStatus.HEALTHY_NO_PENDING_INVOCATION,
        PersonalDesktopUnattendedPaperStartupStatus.READY_SAME_INVOCATION,
    }:
        expected_storage = (
            Storage.ABSENT
            if startup.status
            is PersonalDesktopUnattendedPaperStartupStatus.HEALTHY_NO_PENDING_INVOCATION
            else Storage.FINALIZED_IDENTICAL
        )
        if (
            startup.storage_classification is not expected_storage
            or startup.operation_classification
            is not PaperOperationClassification.PENDING
            or startup.operation_diagnostic is not PaperOperationInspectionCode.PENDING
        ):
            raise ValueError("D8-R2 startup durable state is not execution-ready")
        return Status.SETTLEMENT_NOT_READY  # eligible for the single effect attempt
    if startup.status is PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED:
        if (
            startup.storage_classification
            not in {Storage.ABSENT, Storage.FINALIZED_IDENTICAL}
            or startup.operation_classification
            is not PaperOperationClassification.ALREADY_APPLIED
            or startup.operation_diagnostic
            is not PaperOperationInspectionCode.ALREADY_APPLIED
        ):
            raise ValueError("D8-R2 already-applied startup state is contradictory")
        return Status.SETTLEMENT_ALREADY_APPLIED
    raise ValueError("D8-R2 startup status is invalid")


def _reconstruct(
    d: DisposableDeferredSettlementExecutionDependencies,
) -> _Settlement | TradingSession:
    _require_gates(d, _CLOSED)
    token = _token(d)
    c1 = d.validate_c1(d.acquire_c1())
    completed = completed_xnys_session_at(d.now())
    discovery = d.discover(c1)
    if (
        type(discovery) is not SingleDeferredDecisionResult
        or discovery.current_completed_session != completed
        or discovery.classification is Discovery.BLOCKED
    ):
        raise ValueError("D8-R2 finalized-decision discovery is blocked")
    binding = d.require_discovery(c1, discovery)
    if discovery.classification is Discovery.NONE:
        if binding is not None or discovery.binding is not None:
            raise ValueError("D8-R2 NONE discovery carries a decision")
        _final_authority(d, c1, token)
        return completed
    if (
        binding is not discovery.binding
        or type(binding)
        is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
    ):
        raise ValueError("D8-R2 discovery lacks exact current-C1 provenance")
    replayed = verify_personal_desktop_unattended_paper_decision_intent(
        binding.artifact_bytes,
        personal_desktop_unattended_decision_calendar(),
        expected_decision_id=discovery.decision_id,
        expected_artifact_sha256=binding.artifact_sha256,
        expected_artifact_byte_length=binding.artifact_byte_length,
    )
    if (
        replayed != binding
        or discovery.execution_session is None
        or discovery.execution_session >= completed
        or binding.decision.intended_execution_session != discovery.execution_session
    ):
        raise ValueError("D8-R2 finalized decision is inconsistent")
    decision = binding.decision
    execution = _selected(d, c1, discovery.execution_session)
    original = _selected(d, c1, decision.selected_session)
    _require_c3_evidence(decision.current_c3, original)
    if not decision.history_c3:
        raise ValueError("D8-R2 selected C3 history is empty")
    cursor = decision.history_c3[0].selected_session
    for expected in decision.history_c3:
        if expected.selected_session != cursor:
            raise ValueError("D8-R2 selected C3 history order has a gap")
        _require_c3_evidence(expected, _selected(d, c1, cursor))
        cursor = next_xnys_execution_session(cursor)
    if cursor != decision.selected_session:
        raise ValueError("D8-R2 history does not end at decision session")
    opened = d.build_open(execution.selected, c1)
    if type(opened) is not C3VerifiedDailyBarOpenBinding:
        raise TypeError("D8-R2 verified C3 open binding is invalid")
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
        raise TypeError("D8-R2 historical configuration payloads are invalid")
    startup = d.startup(
        c1,
        original.selected,
        plan,
        historical_cycle_configuration_payloads=historical,
    )
    status = _startup_status(startup, binding, plan)
    _final_authority(d, c1, token)
    return _Settlement(
        c1,
        token,
        completed,
        discovery.execution_session,
        binding,
        original.selected,
        plan,
        historical,
        startup,
        status,
    )


def _result(
    status: Status,
    settlement: _Settlement,
    *,
    final_checkpoint_id: UUID | None = None,
    real_effect_performed: bool = False,
) -> DeferredSettlementExecutionResult:
    decision = settlement.binding.decision
    startup = settlement.startup
    return DeferredSettlementExecutionResult(
        status,
        current_completed_session=settlement.completed,
        deferred_execution_session=settlement.execution_session,
        decision_id=decision.decision_id,
        final_plan_id=settlement.plan.plan.plan_id,
        invocation_id=startup.invocation_id,
        operation_id=startup.operation_id,
        application_id=startup.application_id,
        account_predecessor_checkpoint_id=decision.predecessor_checkpoint_id,
        final_checkpoint_id=final_checkpoint_id,
        all_eight_gates_closed=True,
        real_effect_performed=real_effect_performed,
    )


def _require_execution_result(
    result: pd4d.PersonalDesktopUnattendedPaperOperationResult,
    settlement: _Settlement,
) -> Status:
    if type(result) is not pd4d.PersonalDesktopUnattendedPaperOperationResult:
        raise ValueError("D8-R2 PD4-D result type is invalid")
    result.__post_init__()
    startup = settlement.startup
    decision = settlement.binding.decision
    if (
        result.status
        is not pd4d.PersonalDesktopUnattendedPaperOperationStatus.COMPLETED
    ):
        raise ValueError("D8-R2 PD4-D did not complete the admitted fresh execution")
    if (
        result.paper_account_id != decision.paper_account_id
        or result.selected_snapshot_id != decision.current_c3.snapshot_id
        or result.invocation_id != startup.invocation_id
        or result.operation_id != startup.operation_id
        or result.application_id != startup.application_id
        or result.predecessor_checkpoint_id != decision.predecessor_checkpoint_id
        or result.final_checkpoint_id is None
    ):
        raise ValueError("D8-R2 PD4-D result is unrelated to reconstructed plan")
    if (
        not result.executor_called
        or result.execution_classification
        is not PaperOperationExecutionClassification.COMPLETED
        or result.final_operation_classification
        is not PaperOperationClassification.ALREADY_APPLIED
    ):
        raise ValueError("D8-R2 completed PD4-D result lacks executor crossing")
    return Status.SETTLEMENT_COMPLETED


def _run(
    d: DisposableDeferredSettlementExecutionDependencies,
) -> DeferredSettlementExecutionResult:
    effect_boundary_entered = False
    settlement: _Settlement | None = None
    try:
        reconstructed = _reconstruct(d)
        if type(reconstructed) is TradingSession:
            return DeferredSettlementExecutionResult(
                Status.SETTLEMENT_NOT_READY,
                current_completed_session=reconstructed,
                all_eight_gates_closed=True,
            )
        settlement = reconstructed
        if settlement.status is not Status.SETTLEMENT_NOT_READY:
            final = settlement.startup.terminal_checkpoint_id
            _final_authority(d, settlement.c1, settlement.token)
            return _result(settlement.status, settlement, final_checkpoint_id=final)
        _final_authority(d, settlement.c1, settlement.token)
        pd4d.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED = True
        try:
            _require_gates(d, _EXECUTION_OPEN)
            # PD4-D can publish durably before its executor is called or returns.
            effect_boundary_entered = True
            operation = d.execute(
                settlement.c1,
                settlement.original,
                settlement.plan,
                historical_cycle_configuration_payloads=settlement.historical,
            )
        finally:
            pd4d.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED = False
        _final_authority(d, settlement.c1, settlement.token)
        status = _require_execution_result(operation, settlement)
        return _result(
            status,
            settlement,
            final_checkpoint_id=operation.final_checkpoint_id,
            real_effect_performed=effect_boundary_entered,
        )
    except Exception:
        try:
            _require_gates(d, _CLOSED)
            closed = True
        except Exception:
            closed = False
        if effect_boundary_entered:
            if settlement is not None and closed:
                return _result(
                    Status.SETTLEMENT_OUTCOME_AMBIGUOUS,
                    settlement,
                    real_effect_performed=True,
                )
            return DeferredSettlementExecutionResult(
                Status.SETTLEMENT_OUTCOME_AMBIGUOUS,
                all_eight_gates_closed=closed,
                real_effect_performed=True,
            )
        return DeferredSettlementExecutionResult(
            Status.BLOCKED, all_eight_gates_closed=closed
        )


def _production_dependencies() -> DisposableDeferredSettlementExecutionDependencies:
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
            raise ValueError("D8-R2 discovery lacks exact current-C1 provenance")
        return binding

    return DisposableDeferredSettlementExecutionDependencies(
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
        execute=pd4d.execute_personal_desktop_unattended_paper_operation_from_verified_plan,
    )
