"""PD4 D7-D independent read-only finalized-decision reconciliation."""

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
    FinalizedUnattendedDecisionForSessionClassification as Discovery,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    FinalizedUnattendedDecisionForSessionResult,
    PersonalDesktopUnattendedDecisionStorageReadResult,
    find_finalized_unattended_decision_for_execution_session,
    read_personal_desktop_unattended_decision_storage,
    require_finalized_unattended_decision_for_execution_session,
    require_validated_personal_desktop_unattended_decision_storage_read,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    PersonalDesktopUnattendedDecisionStorageClassification as Storage,
)
from trading_bot.runtime.windows_authority_validation import (
    acquire_validated_production_authority,
    require_validated_production_authority,
)


class UnattendedDecisionReconciliationClassification(StrEnum):
    """Bounded D7-D outcomes; only RECONCILED is successful reconciliation."""

    RECONCILED = "RECONCILED"
    WARMING_UP = "WARMING_UP"
    SESSION_GAP = "SESSION_GAP"
    NOT_FINALIZED = "NOT_FINALIZED"
    BLOCKED = "BLOCKED"


Status = UnattendedDecisionReconciliationClassification


@dataclass(frozen=True, slots=True)
class UnattendedDecisionReconciliationResult:
    """Sanitized evidence with no authority, binding, handle, path, or permit."""

    classification: UnattendedDecisionReconciliationClassification
    completed_session: TradingSession | None = None
    selected_snapshot_id: UUID | None = None
    selected_history_count: int = 0
    required_history_count: int = 6
    expected_decision_id: UUID | None = None
    finalized_decision_id: UUID | None = None
    intended_execution_session: TradingSession | None = None
    regular_open: datetime | None = None
    observed_before_open: bool = False
    account_predecessor_checkpoint_id: UUID | None = None
    namespace_classification: Namespace | None = None
    session_discovery_classification: Discovery | None = None
    storage_classification: Storage | None = None
    all_eight_gates_closed: bool = False
    real_effect_performed: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.classification) is not Status
            or any(
                value is not None and type(value) is not TradingSession
                for value in (self.completed_session, self.intended_execution_session)
            )
            or any(
                value is not None and type(value) is not UUID
                for value in (
                    self.selected_snapshot_id,
                    self.expected_decision_id,
                    self.finalized_decision_id,
                    self.account_predecessor_checkpoint_id,
                )
            )
            or type(self.selected_history_count) is not int
            or not 0 <= self.selected_history_count <= 6
            or self.required_history_count != 6
            or type(self.required_history_count) is not int
            or (
                self.regular_open is not None
                and (
                    type(self.regular_open) is not datetime
                    or self.regular_open.tzinfo is not UTC
                )
            )
            or type(self.observed_before_open) is not bool
            or (
                self.namespace_classification is not None
                and type(self.namespace_classification) is not Namespace
            )
            or (
                self.session_discovery_classification is not None
                and type(self.session_discovery_classification) is not Discovery
            )
            or (
                self.storage_classification is not None
                and type(self.storage_classification) is not Storage
            )
            or type(self.all_eight_gates_closed) is not bool
            or self.real_effect_performed is not False
        ):
            raise ValueError("D7-D reconciliation result is invalid")


@dataclass(frozen=True, slots=True)
class DisposableUnattendedDecisionReconciliationDependencies:
    """Read-only disposable seams; the production boundary accepts no arguments."""

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
    discover_finalized: Callable[..., FinalizedUnattendedDecisionForSessionResult]
    require_discovery: Callable[..., Any]
    read_storage: Callable[..., PersonalDesktopUnattendedDecisionStorageReadResult]
    require_storage: Callable[..., None]


def reconcile_personal_desktop_unattended_decision() -> (
    UnattendedDecisionReconciliationResult
):
    """D7-D: freshly reconcile durable publication with every effect closed."""

    try:
        return _run(_production_dependencies())
    except Exception:
        return UnattendedDecisionReconciliationResult(Status.BLOCKED)


def reconcile_personal_desktop_unattended_decision_for_test(
    dependencies: DisposableUnattendedDecisionReconciliationDependencies,
) -> UnattendedDecisionReconciliationResult:
    """Exercise D7-D through disposable read-only seams."""

    if type(dependencies) is not DisposableUnattendedDecisionReconciliationDependencies:
        raise TypeError("D7-D disposable dependencies are invalid")
    return _run(dependencies)


def _require_gates(d: DisposableUnattendedDecisionReconciliationDependencies) -> None:
    gates = d.gate_state()
    if (
        type(gates) is not tuple
        or len(gates) != 8
        or any(value is not False for value in gates)
    ):
        raise ValueError("D7-D requires all eight exact closed gates")


def _token(
    d: DisposableUnattendedDecisionReconciliationDependencies,
) -> TradingTokenObservation:
    observation = d.observe_token()
    require_trading_token(
        PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
        observation,
    )
    return observation


def _run(
    d: DisposableUnattendedDecisionReconciliationDependencies,
) -> UnattendedDecisionReconciliationResult:
    evidence = UnattendedDecisionReconciliationResult(Status.BLOCKED)
    try:
        _require_gates(d)
        token = _token(d)
        c1 = d.validate_c1(d.acquire_c1())
        historical = d.historical_configurations(c1)
        prelock = d.require_account(d.read_account(c1, historical))
        prelock_anchor = prelock.anchor
        prelock_predecessor = prelock.prior_checkpoint.checkpoint_id
        if (
            prelock_anchor.paper_account_id
            != PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.paper_account_id
        ):
            raise ValueError("D7-D requires the exact Paper-v2 account")
        with d.admission(prelock):
            _require_gates(d)
            if d.validate_c1(c1) != c1 or _token(d) != token:
                raise ValueError("D7-D authority/token changed after locking")
            account = d.require_account(d.read_account(c1, historical))
            if (
                account.anchor != prelock_anchor
                or account.prior_checkpoint.checkpoint_id != prelock_predecessor
            ):
                raise ValueError("D7-D Paper-v2 account changed before reconciliation")

            completed = completed_xnys_session_at(d.now())
            selected = d.read_selected(c1, completed)
            if (
                type(selected) is not SessionIndexedSelectedC3SnapshotReadResult
                or selected.session != completed
            ):
                raise ValueError("D7-D selected session is invalid")
            d.require_selected(c1, selected)
            config = personal_desktop_unattended_strategy_config()
            window = d.inspect_history(c1, selected, config)
            _require_window(window, selected)
            for item in window.selected:
                d.require_selected(c1, item)

            namespace = d.qualify_namespace()
            if type(namespace) is not Namespace:
                raise ValueError("D7-D decision namespace result is invalid")
            evidence = replace(
                evidence,
                completed_session=completed,
                selected_snapshot_id=selected.selected.audit.snapshot_id,
                selected_history_count=len(window.selected),
                account_predecessor_checkpoint_id=prelock_predecessor,
                namespace_classification=namespace,
            )
            if namespace is not Namespace.PRESENT_VALID:
                raise ValueError("D7-D requires the fixed valid decision namespace")

            status = Status.BLOCKED
            expected = None
            if window.classification is Window.WARMING_UP:
                status = Status.WARMING_UP
            elif window.classification is Window.SESSION_GAP:
                status = Status.SESSION_GAP
            elif window.classification is Window.READY:
                if len(window.selected) != 6 or window.selected[-1] != selected:
                    raise ValueError("D7-D ready history is invalid")
                history = d.build_history(c1, window.selected[:-1], selected, config)
                snapshot = selected.selected.verification.snapshot
                if snapshot is None:
                    raise ValueError("D7-D selected snapshot is invalid")
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
                    expected_decision_id=expected.decision.decision_id,
                    intended_execution_session=execution,
                    regular_open=opening,
                    observed_before_open=d.now() < opening,
                )

                discovery = d.discover_finalized(c1, execution)
                if (
                    type(discovery) is not FinalizedUnattendedDecisionForSessionResult
                    or discovery.execution_session != execution
                ):
                    raise ValueError("D7-D finalized-decision discovery is invalid")
                evidence = replace(
                    evidence,
                    finalized_decision_id=discovery.decision_id,
                    session_discovery_classification=discovery.classification,
                )
                discovered = d.require_discovery(c1, discovery)
                if discovery.classification is Discovery.NONE:
                    if discovered is not None or discovery.binding is not None:
                        raise ValueError("D7-D NONE discovery carries a decision")
                    status = Status.NOT_FINALIZED
                elif discovery.classification is Discovery.FINALIZED:
                    if discovered is not discovery.binding:
                        raise ValueError("D7-D discovery provenance changed binding")
                    _require_exact_finalized(expected, discovered)
                    storage = d.read_storage(c1, expected)
                    if (
                        type(storage)
                        is not PersonalDesktopUnattendedDecisionStorageReadResult
                        or storage.expected_decision_id != expected.decision.decision_id
                    ):
                        raise ValueError(
                            "D7-D expected-decision storage read is invalid"
                        )
                    evidence = replace(
                        evidence, storage_classification=storage.classification
                    )
                    d.require_storage(c1, expected, storage)
                    if storage.classification is not Storage.FINALIZED_IDENTICAL:
                        raise ValueError("D7-D storage is not finalized-identical")
                    status = Status.RECONCILED
                else:
                    raise ValueError("D7-D finalized-decision discovery is blocked")
            else:
                raise ValueError("D7-D history classification is invalid")

            # The account remains serialized until every independent authority
            # and all eight gates have been freshly reconciled.
            final_account = d.require_account(d.read_account(c1, historical))
            if (
                final_account.anchor != account.anchor
                or final_account.prior_checkpoint.checkpoint_id
                != account.prior_checkpoint.checkpoint_id
                or (
                    expected is not None
                    and final_account.prior_checkpoint.checkpoint_id
                    != expected.decision.predecessor_checkpoint_id
                )
                or d.validate_c1(d.acquire_c1()) != c1
                or _token(d) != token
                or d.qualify_namespace() is not Namespace.PRESENT_VALID
            ):
                raise ValueError("D7-D final durable authority changed")
            _require_gates(d)
            return replace(
                evidence,
                classification=status,
                all_eight_gates_closed=True,
            )
    except Exception:
        return replace(evidence, classification=Status.BLOCKED)


def _require_window(
    window: object, current: SessionIndexedSelectedC3SnapshotReadResult
) -> None:
    if type(window) is not SelectedC3StrategyHistoryWindowResult:
        raise TypeError("D7-D history window is invalid")
    calendar = personal_desktop_unattended_decision_calendar()
    cursor = current.session
    preceding = []
    for _ in range(5):
        cursor = calendar.previous_session(xnys_regular_open(cursor))
        preceding.append(cursor)
    required = (*reversed(preceding), current.session)
    present = tuple(
        session in tuple(i.session for i in window.selected) for session in required
    )
    if not present[-1]:
        raise ValueError("D7-D current history selection is missing")
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
        != tuple(
            session
            for session, is_present in zip(required, present, strict=True)
            if is_present
        )
        or window.classification is not classification
    ):
        raise ValueError("D7-D history source/session/classification differs")


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
        raise TypeError("D7-D candidate binding is invalid")
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
        raise ValueError("D7-D candidate source bindings differ")
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
            raise ValueError("D7-D candidate C3 bindings differ")


def _require_exact_finalized(
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    discovered: object,
) -> None:
    if (
        type(discovered)
        is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
    ):
        raise TypeError("D7-D discovered decision binding is invalid")
    replay = verify_personal_desktop_unattended_paper_decision_intent(
        discovered.artifact_bytes,
        personal_desktop_unattended_decision_calendar(),
        expected_decision_id=discovered.decision.decision_id,
        expected_artifact_sha256=discovered.artifact_sha256,
        expected_artifact_byte_length=discovered.artifact_byte_length,
    )
    expected_decision = expected.decision
    actual = discovered.decision
    if (
        replay != discovered
        or discovered != expected
        or discovered.artifact_bytes != expected.artifact_bytes
        or discovered.artifact_sha256 != expected.artifact_sha256
        or discovered.artifact_byte_length != expected.artifact_byte_length
        or actual.decision_id != expected_decision.decision_id
        or actual.selected_session != expected_decision.selected_session
        or actual.intended_execution_session
        != expected_decision.intended_execution_session
        or actual.paper_account_id != expected_decision.paper_account_id
        or actual.predecessor_checkpoint_id
        != expected_decision.predecessor_checkpoint_id
        or actual.history_c3 != expected_decision.history_c3
        or actual.current_c3 != expected_decision.current_c3
    ):
        raise ValueError("D7-D finalized decision differs from reconstructed candidate")


def _production_dependencies() -> (
    DisposableUnattendedDecisionReconciliationDependencies
):
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

    def discover_finalized(
        c1: Any, session: TradingSession
    ) -> FinalizedUnattendedDecisionForSessionResult:
        return find_finalized_unattended_decision_for_execution_session(session, c1)

    def require_discovery(
        c1: Any, result: FinalizedUnattendedDecisionForSessionResult
    ) -> PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding | None:
        binding = require_finalized_unattended_decision_for_execution_session(
            result, c1
        )
        if binding is not result.binding:
            raise ValueError("D7-D discovery lacks exact current-C1 provenance")
        return binding

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
            raise ValueError("D7-D storage lacks exact current-C1 provenance")

    return DisposableUnattendedDecisionReconciliationDependencies(
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
        discover_finalized=discover_finalized,
        require_discovery=require_discovery,
        read_storage=read_personal_desktop_unattended_decision_storage,
        require_storage=require_storage,
    )
