"""D8-A read-only qualification of one finalized unattended paper settlement."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

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
    FinalizedUnattendedDecisionForSessionClassification as Discovery,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    FinalizedUnattendedDecisionForSessionResult,
    find_finalized_unattended_decision_for_execution_session,
    require_finalized_unattended_decision_for_execution_session,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation import (
    create_personal_desktop_unattended_paper_invocation,
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
    PersonalDesktopUnattendedPaperStartupQualificationResult,
    PersonalDesktopUnattendedPaperStartupStatus,
    qualify_personal_desktop_unattended_paper_startup_from_verified_plan,
)


class SettlementQualificationClassification(StrEnum):
    """D8-A diagnostic outcomes; none grants execution authority."""

    NO_SETTLEMENT_PENDING = "NO_SETTLEMENT_PENDING"
    EXECUTION_READY = "EXECUTION_READY"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    RECEIPT_RECOVERY_REQUIRED = "RECEIPT_RECOVERY_REQUIRED"
    BLOCKED = "BLOCKED"


Status = SettlementQualificationClassification


@dataclass(frozen=True, slots=True)
class SettlementQualificationResult:
    """Only bounded identifiers and classifications; no reusable authority."""

    classification: SettlementQualificationClassification
    completed_execution_session: TradingSession | None = None
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

    def __post_init__(self) -> None:
        if (
            type(self.classification) is not Status
            or any(
                value is not None and type(value) is not TradingSession
                for value in (
                    self.completed_execution_session,
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
            or type(self.all_eight_gates_closed) is not bool
            or self.real_effect_performed is not False
            or (
                self.classification is Status.NO_SETTLEMENT_PENDING
                and (
                    self.completed_execution_session is None
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
            raise ValueError("D8-A settlement qualification result is invalid")


@dataclass(frozen=True, slots=True)
class DisposableSettlementQualificationDependencies:
    """Disposable read-only seams; production accepts zero arguments."""

    gate_state: Callable[[], tuple[bool, ...]]
    acquire_c1: Callable[[], Any]
    validate_c1: Callable[[Any], Any]
    observe_token: Callable[[], TradingTokenObservation]
    now: Callable[[], datetime]
    discover: Callable[..., FinalizedUnattendedDecisionForSessionResult]
    require_discovery: Callable[..., Any]
    read_selected: Callable[..., SessionIndexedSelectedC3SnapshotReadResult]
    require_selected: Callable[..., None]
    build_open: Callable[..., C3VerifiedDailyBarOpenBinding]
    complete_plan: Callable[..., ManualPaperStrategyPlanArtifactBinding]
    verify_plan: Callable[..., ManualPaperStrategyPlanArtifactBinding]
    historical_configurations: Callable[[Any], tuple[bytes, ...]]
    startup: Callable[..., PersonalDesktopUnattendedPaperStartupQualificationResult]


def qualify_personal_desktop_unattended_settlement() -> SettlementQualificationResult:
    """Independently qualify current durable settlement truth with all gates closed."""

    try:
        return _run(_production_dependencies())
    except Exception:
        return SettlementQualificationResult(Status.BLOCKED)


def qualify_personal_desktop_unattended_settlement_for_test(
    dependencies: DisposableSettlementQualificationDependencies,
) -> SettlementQualificationResult:
    """Exercise the full D8-A composition using only disposable seams."""

    if type(dependencies) is not DisposableSettlementQualificationDependencies:
        raise TypeError("D8-A disposable dependencies are invalid")
    return _run(dependencies)


def _require_gates(d: DisposableSettlementQualificationDependencies) -> None:
    gates = d.gate_state()
    if (
        type(gates) is not tuple
        or len(gates) != 8
        or any(v is not False for v in gates)
    ):
        raise ValueError("D8-A requires eight exact closed effect gates")


def _token(d: DisposableSettlementQualificationDependencies) -> TradingTokenObservation:
    observation = d.observe_token()
    require_trading_token(
        PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
        observation,
    )
    return observation


def _final_authority(
    d: DisposableSettlementQualificationDependencies, c1: Any, token: Any
) -> None:
    if d.validate_c1(d.acquire_c1()) != c1 or _token(d) != token:
        raise ValueError("D8-A C1 or Trading token changed")
    _require_gates(d)


def _selected(
    d: DisposableSettlementQualificationDependencies,
    c1: Any,
    session: TradingSession,
) -> SessionIndexedSelectedC3SnapshotReadResult:
    result = d.read_selected(c1, session)
    if (
        type(result) is not SessionIndexedSelectedC3SnapshotReadResult
        or result.session != session
    ):
        raise ValueError("D8-A session-indexed selected C3 is invalid")
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
        raise ValueError("D8-A durable selected C3 differs from current C1")


def _require_plan(
    decision_binding: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    execution: SessionIndexedSelectedC3SnapshotReadResult,
    opened: C3VerifiedDailyBarOpenBinding,
    plan_binding: ManualPaperStrategyPlanArtifactBinding,
    d: DisposableSettlementQualificationDependencies,
) -> None:
    if type(plan_binding) is not ManualPaperStrategyPlanArtifactBinding:
        raise TypeError("D8-A completed plan binding is invalid")
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
        raise ValueError("D8-A final plan differs from decision and verified open")


def _startup_status(
    startup: PersonalDesktopUnattendedPaperStartupQualificationResult,
    binding: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    plan: ManualPaperStrategyPlanArtifactBinding,
) -> Status:
    if type(startup) is not PersonalDesktopUnattendedPaperStartupQualificationResult:
        raise TypeError("D8-A startup result is invalid")
    startup.__post_init__()
    decision = binding.decision
    expected_application = derive_checkpointed_verified_snapshot_application_id(
        decision.predecessor_checkpoint_id,
        plan.checkpointed_request.request_id,
    )
    if startup.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED:
        return Status.BLOCKED
    if startup.paper_account_id != decision.paper_account_id:
        raise ValueError("D8-A startup account differs from the decision")
    if (
        startup.status
        is PersonalDesktopUnattendedPaperStartupStatus.RECEIPT_RECOVERY_REQUIRED
    ):
        if (
            startup.recovery_predecessor_checkpoint_id
            != decision.predecessor_checkpoint_id
            or startup.recovery_missing_application_id != expected_application
        ):
            raise ValueError("D8-A recovery is unrelated to the exact plan")
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
        raise ValueError("D8-A startup identities differ from the exact plan")
    if startup.status in {
        PersonalDesktopUnattendedPaperStartupStatus.HEALTHY_NO_PENDING_INVOCATION,
        PersonalDesktopUnattendedPaperStartupStatus.READY_SAME_INVOCATION,
    }:
        return Status.EXECUTION_READY
    if startup.status is PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED:
        return Status.ALREADY_APPLIED
    raise ValueError("D8-A startup status is invalid")


def _run(
    d: DisposableSettlementQualificationDependencies,
) -> SettlementQualificationResult:
    try:
        _require_gates(d)
        token = _token(d)
        c1 = d.validate_c1(d.acquire_c1())
        completed = completed_xnys_session_at(d.now())
        discovery = d.discover(c1, completed)
        if (
            type(discovery) is not FinalizedUnattendedDecisionForSessionResult
            or discovery.execution_session != completed
            or discovery.classification is Discovery.BLOCKED
        ):
            raise ValueError("D8-A finalized-decision discovery is blocked")
        binding = d.require_discovery(c1, discovery)
        if discovery.classification is Discovery.NONE:
            if binding is not None or discovery.binding is not None:
                raise ValueError("D8-A NONE discovery carries a decision")
            _final_authority(d, c1, token)
            return SettlementQualificationResult(
                Status.NO_SETTLEMENT_PENDING,
                completed_execution_session=completed,
                all_eight_gates_closed=True,
            )
        if (
            binding is not discovery.binding
            or type(binding)
            is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
        ):
            raise ValueError("D8-A discovery lacks exact current-C1 provenance")
        replayed = verify_personal_desktop_unattended_paper_decision_intent(
            binding.artifact_bytes,
            personal_desktop_unattended_decision_calendar(),
            expected_decision_id=discovery.decision_id,
            expected_artifact_sha256=binding.artifact_sha256,
            expected_artifact_byte_length=binding.artifact_byte_length,
        )
        if (
            replayed != binding
            or binding.decision.intended_execution_session != completed
        ):
            raise ValueError("D8-A finalized decision is inconsistent")
        decision = binding.decision
        execution = _selected(d, c1, completed)
        original = _selected(d, c1, decision.selected_session)
        _require_c3_evidence(decision.current_c3, original)
        if not decision.history_c3:
            raise ValueError("D8-A selected C3 history is empty")
        cursor = decision.history_c3[0].selected_session
        for expected in decision.history_c3:
            if expected.selected_session != cursor:
                raise ValueError("D8-A selected C3 history order has a gap")
            _require_c3_evidence(expected, _selected(d, c1, cursor))
            cursor = next_xnys_execution_session(cursor)
        if cursor != decision.selected_session:
            raise ValueError("D8-A history does not end at decision session")
        opened = d.build_open(execution.selected, c1)
        if type(opened) is not C3VerifiedDailyBarOpenBinding:
            raise TypeError("D8-A verified C3 open binding is invalid")
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
            raise TypeError("D8-A historical configuration payloads are invalid")
        startup = d.startup(
            c1,
            original.selected,
            plan,
            historical_cycle_configuration_payloads=(*historical, plan.artifact_bytes),
        )
        status = _startup_status(startup, binding, plan)
        _final_authority(d, c1, token)
        return SettlementQualificationResult(
            status,
            completed_execution_session=completed,
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
        )
    except Exception:
        return SettlementQualificationResult(Status.BLOCKED)


def _production_dependencies() -> DisposableSettlementQualificationDependencies:
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

    def discover(
        c1: Any, session: TradingSession
    ) -> FinalizedUnattendedDecisionForSessionResult:
        return find_finalized_unattended_decision_for_execution_session(session, c1)

    def require_discovery(
        c1: Any, result: FinalizedUnattendedDecisionForSessionResult
    ) -> Any:
        binding = require_finalized_unattended_decision_for_execution_session(
            result, c1
        )
        if binding is not result.binding:
            raise ValueError("D8-A discovery lacks exact current-C1 provenance")
        return binding

    return DisposableSettlementQualificationDependencies(
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
