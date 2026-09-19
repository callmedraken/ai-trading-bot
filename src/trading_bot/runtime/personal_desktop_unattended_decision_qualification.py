"""PD4 D7-A zero-argument read-only decision-publication qualification."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    require_selected_c3_snapshot_matches_authority,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperPriorCheckpointEvidence,
)
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
)
from trading_bot.runtime.personal_desktop_historical_cycle_configurations import (
    resolve_personal_desktop_historical_cycle_configurations,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    supervised_paper_cycle_admission,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    read_personal_desktop_paper_account,
    require_validated_personal_desktop_paper_account,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObservation,
    WindowsTradingTokenObserver,
    require_trading_token,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    SelectedC3StrategyHistoryWindowClassification as Window,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    SelectedC3StrategyHistoryWindowResult,
    SessionIndexedSelectedC3SnapshotReadResult,
    WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority,
    build_selected_c3_strategy_history_binding,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    build_personal_desktop_unattended_next_decision,
    derive_personal_desktop_unattended_daily_cycle_idempotency_key,
    personal_desktop_unattended_effect_gate_state,
    personal_desktop_unattended_paper_policies,
    personal_desktop_unattended_strategy_config,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    completed_xnys_session_at,
    next_xnys_execution_session,
    xnys_regular_open,
)
from trading_bot.runtime.personal_desktop_unattended_decision_namespace import (
    TradingDecisionNamespaceClassification as Namespace,
)
from trading_bot.runtime.personal_desktop_unattended_decision_namespace import (
    qualify_trading_unattended_decision_namespace,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_intent import (
    PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    personal_desktop_unattended_decision_calendar,
    verify_personal_desktop_unattended_paper_decision_intent,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    PersonalDesktopUnattendedDecisionStorageClassification as Storage,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    PersonalDesktopUnattendedDecisionStorageReadResult,
    read_personal_desktop_unattended_decision_storage,
    require_validated_personal_desktop_unattended_decision_storage_read,
)
from trading_bot.runtime.windows_authority_validation import (
    acquire_validated_production_authority,
    require_validated_production_authority,
)


class UnattendedDecisionQualificationClassification(StrEnum):
    """Non-authorizing D7-A observations; D7-C must rederive authority."""

    WARMING_UP = "WARMING_UP"
    SESSION_GAP = "SESSION_GAP"
    NAMESPACE_MISSING = "NAMESPACE_MISSING"
    READY = "READY"
    ALREADY_FINALIZED = "ALREADY_FINALIZED"
    MISSED_DECISION_DEADLINE = "MISSED_DECISION_DEADLINE"
    BLOCKED = "BLOCKED"


Status = UnattendedDecisionQualificationClassification


@dataclass(frozen=True, slots=True)
class UnattendedDecisionQualificationResult:
    """Bounded diagnostic data; no authority or mutation capability."""

    classification: UnattendedDecisionQualificationClassification
    completed_session: TradingSession | None = None
    selected_snapshot_id: UUID | None = None
    selected_history_count: int = 0
    required_history_count: int = 6
    candidate_decision_id: UUID | None = None
    intended_execution_session: TradingSession | None = None
    regular_open: datetime | None = None
    account_predecessor_checkpoint_id: UUID | None = None
    namespace_classification: Namespace | None = None
    storage_classification: Storage | None = None
    deadline_open: bool = False
    all_eight_gates_closed: bool = False
    real_effect_performed: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.classification) is not Status
            or any(
                v is not None and type(v) is not TradingSession
                for v in (self.completed_session, self.intended_execution_session)
            )
            or any(
                v is not None and type(v) is not UUID
                for v in (
                    self.selected_snapshot_id,
                    self.candidate_decision_id,
                    self.account_predecessor_checkpoint_id,
                )
            )
            or type(self.selected_history_count) is not int
            or not 0 <= self.selected_history_count <= 6
            or type(self.required_history_count) is not int
            or self.required_history_count != 6
            or (
                self.namespace_classification is not None
                and type(self.namespace_classification) is not Namespace
            )
            or (
                self.storage_classification is not None
                and type(self.storage_classification) is not Storage
            )
            or (
                self.regular_open is not None
                and (
                    type(self.regular_open) is not datetime
                    or self.regular_open.tzinfo is not UTC
                )
            )
            or type(self.deadline_open) is not bool
            or type(self.all_eight_gates_closed) is not bool
            or self.real_effect_performed is not False
        ):
            raise ValueError("D7-A diagnostic result is invalid")


@dataclass(frozen=True, slots=True)
class DisposableUnattendedDecisionQualificationDependencies:
    """Read-only disposable seams; production accepts zero arguments."""

    gate_state: Callable[[], tuple[bool, ...]]
    acquire_c1: Callable[[], Any]
    validate_c1: Callable[[Any], Any]
    observe_token: Callable[[], TradingTokenObservation]
    now: Callable[[], datetime]
    historical_configurations: Callable[[Any], tuple[bytes, ...]]
    read_account: Callable[[Any, tuple[bytes, ...]], Any]
    require_account: Callable[[Any], Any]
    admission: Callable[[Any], AbstractContextManager[Any]]
    read_selected: Callable[..., SessionIndexedSelectedC3SnapshotReadResult]
    require_selected: Callable[..., None]
    inspect_history: Callable[..., SelectedC3StrategyHistoryWindowResult]
    build_history: Callable[..., Any]
    build_decision: Callable[
        ..., PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
    ]
    qualify_namespace: Callable[[], Namespace]
    read_storage: Callable[..., PersonalDesktopUnattendedDecisionStorageReadResult]
    require_storage: Callable[..., None]


def qualify_personal_desktop_unattended_decision() -> (
    UnattendedDecisionQualificationResult
):
    """D7-A: independently observe production truth, never issue authority."""
    try:
        return _run(_production_dependencies())
    except Exception:
        return UnattendedDecisionQualificationResult(Status.BLOCKED)


def qualify_personal_desktop_unattended_decision_for_test(
    dependencies: DisposableUnattendedDecisionQualificationDependencies,
) -> UnattendedDecisionQualificationResult:
    """Use disposable read-only seams without touching production state."""
    if type(dependencies) is not DisposableUnattendedDecisionQualificationDependencies:
        raise TypeError("D7-A disposable dependencies are invalid")
    return _run(dependencies)


def _require_gates(d: DisposableUnattendedDecisionQualificationDependencies) -> None:
    gates = d.gate_state()
    if (
        type(gates) is not tuple
        or len(gates) != 8
        or any(g is not False for g in gates)
    ):
        raise ValueError("D7-A requires all eight exact closed gates")


def _token(
    d: DisposableUnattendedDecisionQualificationDependencies,
) -> TradingTokenObservation:
    observation = d.observe_token()
    require_trading_token(
        PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid, observation
    )
    return observation


def _run(
    d: DisposableUnattendedDecisionQualificationDependencies,
) -> UnattendedDecisionQualificationResult:
    evidence = UnattendedDecisionQualificationResult(Status.BLOCKED)
    try:
        _require_gates(d)
        token = _token(d)
        c1 = d.validate_c1(d.acquire_c1())
        historical = d.historical_configurations(c1)
        prelock = d.read_account(c1, historical)
        anchor = d.require_account(prelock).anchor
        if (
            anchor.paper_account_id
            != PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.paper_account_id
        ):
            raise ValueError("D7-A requires the exact Paper-v2 account")
        with d.admission(prelock):
            _require_gates(d)
            if d.validate_c1(c1) != c1 or _token(d) != token:
                raise ValueError("D7-A authority/token changed")
            account = d.require_account(d.read_account(c1, historical))
            if account.anchor != anchor:
                raise ValueError("D7-A account identity changed")
            completed = completed_xnys_session_at(d.now())
            selected = d.read_selected(c1, completed)
            if (
                type(selected) is not SessionIndexedSelectedC3SnapshotReadResult
                or selected.session != completed
            ):
                raise ValueError("D7-A selected session is invalid")
            d.require_selected(c1, selected)
            config = personal_desktop_unattended_strategy_config()
            window = d.inspect_history(c1, selected, config)
            _require_window(window, selected)
            for item in window.selected:
                d.require_selected(c1, item)
            namespace = d.qualify_namespace()
            if type(namespace) is not Namespace or namespace is Namespace.BLOCKED:
                raise ValueError("D7-A namespace is unsafe")
            evidence = replace(
                evidence,
                completed_session=completed,
                selected_snapshot_id=selected.selected.audit.snapshot_id,
                selected_history_count=len(window.selected),
                account_predecessor_checkpoint_id=account.prior_checkpoint.checkpoint_id,
                namespace_classification=namespace,
            )
            if window.classification is Window.WARMING_UP:
                status = Status.WARMING_UP
            elif window.classification is Window.SESSION_GAP:
                status = Status.SESSION_GAP
            elif window.classification is Window.READY:
                if len(window.selected) != 6 or window.selected[-1] != selected:
                    raise ValueError("D7-A ready history is invalid")
                history = d.build_history(c1, window.selected[:-1], selected, config)
                snapshot = selected.selected.verification.snapshot
                if snapshot is None:
                    raise ValueError("D7-A snapshot is invalid")
                expected = d.build_decision(
                    c1,
                    selected,
                    history,
                    account,
                    snapshot.audit.captured_at,
                    config,
                    personal_desktop_unattended_paper_policies(),
                )
                _require_candidate(expected, selected, window, account, config)
                execution = next_xnys_execution_session(completed)
                opening = xnys_regular_open(execution)
                evidence = replace(
                    evidence,
                    candidate_decision_id=expected.decision.decision_id,
                    intended_execution_session=execution,
                    regular_open=opening,
                )
                if namespace is Namespace.MISSING:
                    status = Status.NAMESPACE_MISSING
                else:
                    storage = d.read_storage(c1, expected)
                    if (
                        type(storage)
                        is not PersonalDesktopUnattendedDecisionStorageReadResult
                    ):
                        raise ValueError("D7-A storage result is invalid")
                    evidence = replace(
                        evidence, storage_classification=storage.classification
                    )
                    if storage.expected_decision_id != expected.decision.decision_id:
                        raise ValueError("D7-A storage candidate changed")
                    d.require_storage(c1, expected, storage)
                    if storage.classification is Storage.FINALIZED_IDENTICAL:
                        status = Status.ALREADY_FINALIZED
                    elif storage.classification is Storage.ABSENT:
                        status = Status.READY
                    else:
                        status = Status.BLOCKED
            else:
                raise ValueError("D7-A history is blocked")
            # Every accepted observation, including warm-up and missing storage,
            # gets a final predecessor/C1/token/namespace/gate check under PD2A.
            final = d.require_account(d.read_account(c1, historical))
            if (
                final.anchor != account.anchor
                or final.prior_checkpoint.checkpoint_id
                != account.prior_checkpoint.checkpoint_id
                or d.validate_c1(d.acquire_c1()) != c1
                or _token(d) != token
                or d.qualify_namespace() is not namespace
            ):
                raise ValueError("D7-A final reconciliation drift")
            _require_gates(d)
            if evidence.regular_open is not None:
                deadline_open = d.now() < evidence.regular_open
                evidence = replace(evidence, deadline_open=deadline_open)
                if not deadline_open and status in (
                    Status.READY,
                    Status.NAMESPACE_MISSING,
                ):
                    status = Status.MISSED_DECISION_DEADLINE
            _require_gates(d)
            return replace(evidence, classification=status, all_eight_gates_closed=True)
    except Exception:
        return replace(evidence, classification=Status.BLOCKED)


def _require_window(
    window: object, current: SessionIndexedSelectedC3SnapshotReadResult
) -> None:
    if type(window) is not SelectedC3StrategyHistoryWindowResult:
        raise TypeError("D7-A history window is invalid")
    calendar = personal_desktop_unattended_decision_calendar()
    cursor = current.session
    preceding = []
    for _ in range(5):
        cursor = calendar.previous_session(xnys_regular_open(cursor))
        preceding.append(cursor)
    required = (*reversed(preceding), current.session)
    present = tuple(s in tuple(i.session for i in window.selected) for s in required)
    if not present[-1]:
        raise ValueError("D7-A current history selection is missing")
    first = present.index(True)
    classification = (
        Window.READY
        if all(present)
        else Window.WARMING_UP
        if all(present[first:])
        else Window.SESSION_GAP
    )
    if (
        window.required_sessions != required
        or window.selected[-1] != current
        or tuple(i.session for i in window.selected)
        != tuple(s for s, p in zip(required, present, strict=True) if p)
        or window.classification is not classification
    ):
        raise ValueError("D7-A history source/session/classification differs")


def _require_candidate(
    expected: object,
    selected: SessionIndexedSelectedC3SnapshotReadResult,
    window: SelectedC3StrategyHistoryWindowResult,
    account: Any,
    config: Any,
) -> None:
    if (
        type(expected)
        is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
    ):
        raise TypeError("D7-A candidate binding is invalid")
    replay = verify_personal_desktop_unattended_paper_decision_intent(
        expected.artifact_bytes,
        personal_desktop_unattended_decision_calendar(),
        expected_decision_id=expected.decision.decision_id,
        expected_artifact_sha256=expected.artifact_sha256,
        expected_artifact_byte_length=expected.artifact_byte_length,
    )
    decision = expected.decision
    prepared = decision.prepared_decision
    bindings = (*decision.history_c3, decision.current_c3)
    if (
        replay != expected
        or len(bindings) != 6
        or decision.selected_session != selected.session
        or decision.intended_execution_session
        != next_xnys_execution_session(selected.session)
        or decision.paper_account_id != account.anchor.paper_account_id
        or decision.predecessor_checkpoint_id != account.prior_checkpoint.checkpoint_id
        or prepared.prior_checkpoint
        != ManualPaperPriorCheckpointEvidence.from_verified(account.prior_checkpoint)
        or prepared.strategy_config != config
        or prepared.caller_idempotency_key
        != str(
            derive_personal_desktop_unattended_daily_cycle_idempotency_key(
                account.anchor.paper_account_id,
                account.prior_checkpoint.checkpoint_id,
                selected,
            )
        )
        or prepared.submitted_at
        != xnys_regular_open(decision.intended_execution_session)
        or prepared.filled_at != xnys_regular_open(decision.intended_execution_session)
        or prepared.metadata != ()
        or prepared.policies != personal_desktop_unattended_paper_policies()
        or prepared.planning_at
        != selected.selected.verification.snapshot.audit.captured_at
    ):
        raise ValueError("D7-A candidate source bindings differ")
    for binding, item in zip(bindings, window.selected, strict=True):
        if (
            binding.selected_session != item.session
            or binding.snapshot_artifact != item.selected.snapshot_bytes
            or any(
                getattr(binding, field) != getattr(item.selected.audit, field)
                for field in (
                    "selection_id",
                    "session_id",
                    "terminal_id",
                    "snapshot_id",
                    "artifact_sha256",
                    "artifact_byte_length",
                )
            )
        ):
            raise ValueError("D7-A candidate C3 bindings differ")


def _production_dependencies() -> DisposableUnattendedDecisionQualificationDependencies:
    retained_readers: list[WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority] = []
    observer = WindowsTradingTokenObserver()

    def read_selected(
        c1: Any, session: TradingSession
    ) -> SessionIndexedSelectedC3SnapshotReadResult:
        reader = WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority(c1)
        retained_readers.append(reader)
        return reader.read_selected_snapshot_for_session(session)

    def inspect_history(
        c1: Any, selected: Any, config: Any
    ) -> SelectedC3StrategyHistoryWindowResult:
        reader = WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority(c1)
        retained_readers.append(reader)
        return reader.inspect_strategy_history_window(selected, config)

    def require_selected(
        c1: Any, selected: SessionIndexedSelectedC3SnapshotReadResult
    ) -> None:
        require_selected_c3_snapshot_matches_authority(
            selected.selected.permit,
            selected.selected.audit,
            require_validated_production_authority(c1),
        )

    def require_storage(c1: Any, expected: Any, storage: Any) -> None:
        verified = require_validated_personal_desktop_unattended_decision_storage_read(
            storage
        )
        if (
            verified.authority != require_validated_production_authority(c1)
            or verified.expected != expected
            or verified.classification is not storage.classification
            or any(
                item.decision.intended_execution_session
                == expected.decision.intended_execution_session
                and item != expected
                for item in verified.finalized
            )
        ):
            raise ValueError("D7-A storage lacks exact current-C1 provenance")

    return DisposableUnattendedDecisionQualificationDependencies(
        gate_state=personal_desktop_unattended_effect_gate_state,
        acquire_c1=acquire_validated_production_authority,
        validate_c1=require_validated_production_authority,
        observe_token=observer.observe,
        now=lambda: datetime.now(UTC),
        historical_configurations=resolve_personal_desktop_historical_cycle_configurations,
        read_account=lambda c1, historical: read_personal_desktop_paper_account(
            c1, historical_cycle_configuration_payloads=historical
        ),
        require_account=require_validated_personal_desktop_paper_account,
        admission=supervised_paper_cycle_admission,
        read_selected=read_selected,
        require_selected=require_selected,
        inspect_history=inspect_history,
        build_history=build_selected_c3_strategy_history_binding,
        build_decision=build_personal_desktop_unattended_next_decision,
        qualify_namespace=qualify_trading_unattended_decision_namespace,
        read_storage=read_personal_desktop_unattended_decision_storage,
        require_storage=require_storage,
    )
