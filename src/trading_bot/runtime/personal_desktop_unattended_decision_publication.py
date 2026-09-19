"""Architecture-113 D6 decision-only, zero-semantic-argument composition."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from trading_bot.market_calendar import TradingSession
from trading_bot.runtime import (
    personal_desktop_unattended_paper_decision_publication as publication,
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
from trading_bot.runtime.personal_desktop_paper_runtime_output import (
    open_personal_desktop_unattended_decision_output_capability,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    SessionIndexedSelectedC3SnapshotReadResult,
    WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    AuthoritativeC3HistorySessionGap,
    InsufficientAuthoritativeC3History,
    build_personal_desktop_unattended_c3_history,
    build_personal_desktop_unattended_next_decision,
    personal_desktop_unattended_effect_gate_state,
    personal_desktop_unattended_paper_policies,
    personal_desktop_unattended_strategy_config,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    completed_xnys_session_at,
    next_xnys_execution_session,
    xnys_regular_open,
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


class PersonalDesktopUnattendedDecisionPublicationClassification(StrEnum):
    """Diagnostic classifications; none grant publication or retry authority."""

    DECISION_NOT_READY = "DECISION_NOT_READY"
    DECISION_PUBLISHED = "DECISION_PUBLISHED"
    DECISION_ALREADY_FINALIZED = "DECISION_ALREADY_FINALIZED"
    MISSED_DECISION_DEADLINE = "MISSED_DECISION_DEADLINE"
    SESSION_GAP = "SESSION_GAP"
    PUBLICATION_OUTCOME_AMBIGUOUS = "PUBLICATION_OUTCOME_AMBIGUOUS"
    BLOCKED = "BLOCKED"


_Status = PersonalDesktopUnattendedDecisionPublicationClassification
_PublicationStatus = publication.PersonalDesktopUnattendedDecisionPublicationStatus
_Qualification = (
    publication.PersonalDesktopUnattendedDecisionPublicationQualificationResult
)


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedDecisionPublicationResult:
    """Bounded evidence containing no permit, path, or raw authority."""

    classification: PersonalDesktopUnattendedDecisionPublicationClassification
    decision_id: UUID | None = None
    selected_session: TradingSession | None = None
    intended_execution_session: TradingSession | None = None
    real_effect_performed: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.classification) is not _Status
            or (self.decision_id is not None and type(self.decision_id) is not UUID)
            or any(
                value is not None and type(value) is not TradingSession
                for value in (self.selected_session, self.intended_execution_session)
            )
            or type(self.real_effect_performed) is not bool
        ):
            raise ValueError("decision publication result is invalid")


@dataclass(frozen=True, slots=True)
class DisposableUnattendedDecisionPublicationDependencies:
    """Explicit disposable seams; the production entry point accepts none."""

    gate_state: Callable[[], tuple[bool, ...]]
    set_publication_gate: Callable[[bool], None]
    acquire_c1: Callable[[], Any]
    validate_c1: Callable[[Any], Any]
    now: Callable[[], datetime]
    historical_configurations: Callable[[Any], tuple[bytes, ...]]
    read_account: Callable[[Any, tuple[bytes, ...]], Any]
    require_account: Callable[[Any], Any]
    admission: Callable[[Any], AbstractContextManager[Any]]
    read_selected: Callable[
        [Any, TradingSession], SessionIndexedSelectedC3SnapshotReadResult
    ]
    build_history: Callable[..., Any]
    build_decision: Callable[
        ..., PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
    ]
    read_storage: Callable[..., PersonalDesktopUnattendedDecisionStorageReadResult]
    require_storage: Callable[..., None]
    qualify: Callable[
        ..., publication.PersonalDesktopUnattendedDecisionPublicationQualificationResult
    ]
    issue_permit: Callable[..., publication.PreOpenDecisionPublicationPermit]
    open_writer: Callable[..., Any]


@dataclass(slots=True)
class _Invocation:
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding | None = None
    writer: Any = None
    publication_failed: bool = False

    def result(
        self, status: _Status
    ) -> PersonalDesktopUnattendedDecisionPublicationResult:
        decision = None if self.expected is None else self.expected.decision
        return PersonalDesktopUnattendedDecisionPublicationResult(
            status,
            None if decision is None else decision.decision_id,
            None if decision is None else decision.selected_session,
            None if decision is None else decision.intended_execution_session,
            self.writer is not None and self.writer.real_effect_performed is True,
        )


def run_personal_desktop_unattended_decision_publication() -> (
    PersonalDesktopUnattendedDecisionPublicationResult
):
    """Run one D6 invocation using only current source-owned production truth."""

    return _run(_production_dependencies())


def run_personal_desktop_unattended_decision_publication_for_test(
    dependencies: DisposableUnattendedDecisionPublicationDependencies,
) -> PersonalDesktopUnattendedDecisionPublicationResult:
    """Exercise ordering/failures without constructing production authority."""

    if type(dependencies) is not DisposableUnattendedDecisionPublicationDependencies:
        raise TypeError("disposable decision publication dependencies are invalid")
    return _run(dependencies)


def _require_gates(
    dependencies: DisposableUnattendedDecisionPublicationDependencies,
    *,
    opened: bool = False,
) -> None:
    gates = dependencies.gate_state()
    expected = (False, opened, False, False, False, False, False, False)
    if (
        type(gates) is not tuple
        or len(gates) != 8
        or any(
            value is not target for value, target in zip(gates, expected, strict=True)
        )
    ):
        raise RuntimeError("decision publication effect gates are invalid")


def _run(
    dependencies: DisposableUnattendedDecisionPublicationDependencies,
) -> PersonalDesktopUnattendedDecisionPublicationResult:
    invocation = _Invocation()
    try:
        _require_gates(dependencies)
        c1 = dependencies.validate_c1(dependencies.acquire_c1())
        historical = dependencies.historical_configurations(c1)
        prelock = dependencies.read_account(c1, historical)
        immutable = dependencies.require_account(prelock).anchor
        with dependencies.admission(prelock):
            _require_gates(dependencies)
            dependencies.validate_c1(c1)
            account = dependencies.require_account(
                dependencies.read_account(c1, historical)
            )
            if account.anchor != immutable:
                raise ValueError("paper account identity changed under admission")
            completed = completed_xnys_session_at(dependencies.now())
            selected = dependencies.read_selected(c1, completed)
            if (
                type(selected) is not SessionIndexedSelectedC3SnapshotReadResult
                or selected.session != completed
            ):
                raise ValueError("current selected C3 session is invalid")
            config = personal_desktop_unattended_strategy_config()
            history = dependencies.build_history(c1, selected, config)
            # Wake time is admission evidence only. Deterministic planning uses
            # the durable current selected-C3 capture time, never the wake clock.
            snapshot = selected.selected.verification.snapshot
            if snapshot is None:
                raise ValueError("current selected C3 snapshot is invalid")
            expected = dependencies.build_decision(
                c1,
                selected,
                history,
                account,
                snapshot.audit.captured_at,
                config,
                personal_desktop_unattended_paper_policies(),
            )
            if (
                type(expected)
                is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
            ):
                raise TypeError("expected decision binding is invalid")
            invocation.expected = expected
            replay = verify_personal_desktop_unattended_paper_decision_intent(
                expected.artifact_bytes,
                personal_desktop_unattended_decision_calendar(),
                expected_decision_id=expected.decision.decision_id,
                expected_artifact_sha256=expected.artifact_sha256,
                expected_artifact_byte_length=expected.artifact_byte_length,
            )
            audit = selected.selected.audit
            if (
                replay != expected
                or expected.decision.current_c3.snapshot_artifact
                != selected.selected.snapshot_bytes
                or any(
                    getattr(expected.decision.current_c3, field)
                    != getattr(audit, field)
                    for field in (
                        "selection_id",
                        "session_id",
                        "terminal_id",
                        "snapshot_id",
                        "artifact_sha256",
                        "artifact_byte_length",
                    )
                )
                or expected.decision.selected_session != completed
                or expected.decision.intended_execution_session
                != next_xnys_execution_session(completed)
                or expected.decision.paper_account_id != account.anchor.paper_account_id
                or expected.decision.predecessor_checkpoint_id
                != account.prior_checkpoint.checkpoint_id
            ):
                raise ValueError(
                    "decision source/account/session binding is inconsistent"
                )
            storage = dependencies.read_storage(c1, expected)
            _require_storage(dependencies, c1, expected, storage)
            if storage.classification is Storage.FINALIZED_IDENTICAL:
                status = _Status.DECISION_ALREADY_FINALIZED
            else:
                observed = dependencies.now()
                qualification = dependencies.qualify(c1, expected, observed)
                if (
                    type(qualification) is not _Qualification
                    or qualification.decision_id != expected.decision.decision_id
                    or qualification.storage_classification is not Storage.ABSENT
                ):
                    raise ValueError("publication qualification changed storage")
                if qualification.status is _PublicationStatus.MISSED_DECISION_DEADLINE:
                    status = _Status.MISSED_DECISION_DEADLINE
                elif (
                    qualification.status
                    is _PublicationStatus.DECISION_READY_EFFECTS_DISABLED
                ):
                    status = _publish(dependencies, invocation, c1, storage)
                else:
                    raise ValueError("publication qualification is invalid")
            # Writer return values are ignored. Even exceptions get one fresh
            # all-gates-closed reread and final account/C1 reconciliation.
            _require_gates(dependencies)
            storage_error = None
            try:
                final_storage = dependencies.read_storage(c1, expected)
            except BaseException as error:
                storage_error = error
            final_account = dependencies.require_account(
                dependencies.read_account(c1, historical)
            )
            dependencies.validate_c1(c1)
            _require_gates(dependencies)
            if storage_error is not None:
                raise storage_error
            _require_storage(dependencies, c1, expected, final_storage)
            if (
                final_account.anchor != account.anchor
                or final_account.prior_checkpoint.checkpoint_id
                != expected.decision.predecessor_checkpoint_id
            ):
                raise ValueError("final account predecessor changed")
            if (
                status is not _Status.MISSED_DECISION_DEADLINE
                and final_storage.classification is not Storage.FINALIZED_IDENTICAL
            ):
                raise ValueError("publication is not durably finalized")
            if invocation.publication_failed:
                status = _Status.PUBLICATION_OUTCOME_AMBIGUOUS
        return invocation.result(status)
    except InsufficientAuthoritativeC3History:
        return invocation.result(_Status.DECISION_NOT_READY)
    except AuthoritativeC3HistorySessionGap:
        return invocation.result(_Status.SESSION_GAP)
    except BaseException:
        return invocation.result(
            _Status.PUBLICATION_OUTCOME_AMBIGUOUS
            if invocation.writer is not None or invocation.publication_failed
            else _Status.BLOCKED
        )


def _require_storage(
    dependencies: DisposableUnattendedDecisionPublicationDependencies,
    c1: Any,
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    storage: object,
) -> None:
    if (
        type(storage) is not PersonalDesktopUnattendedDecisionStorageReadResult
        or storage.classification not in (Storage.ABSENT, Storage.FINALIZED_IDENTICAL)
        or storage.expected_decision_id != expected.decision.decision_id
    ):
        raise ValueError("decision storage is unsafe")
    dependencies.require_storage(c1, expected, storage)


def _publish(
    dependencies: DisposableUnattendedDecisionPublicationDependencies,
    invocation: _Invocation,
    c1: Any,
    storage: PersonalDesktopUnattendedDecisionStorageReadResult,
) -> _Status:
    expected = invocation.expected
    assert expected is not None
    _require_gates(dependencies)
    observed = dependencies.now()
    if observed >= xnys_regular_open(expected.decision.intended_execution_session):
        return _Status.MISSED_DECISION_DEADLINE
    permit = dependencies.issue_permit(
        expected, storage, c1, expected.decision.intended_execution_session, observed
    )
    try:
        dependencies.set_publication_gate(True)
        _require_gates(dependencies, opened=True)
        invocation.writer = dependencies.open_writer(storage, permit)
        with invocation.writer as writer:
            observed = dependencies.now()
            if observed >= xnys_regular_open(
                expected.decision.intended_execution_session
            ):
                return _Status.MISSED_DECISION_DEADLINE
            _require_gates(dependencies, opened=True)
            writer.publish(observed)
    except BaseException:
        invocation.publication_failed = True
    finally:
        dependencies.set_publication_gate(False)
    return _Status.DECISION_PUBLISHED


def _production_dependencies() -> DisposableUnattendedDecisionPublicationDependencies:
    retained_readers: list[WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority] = []

    def read_selected(
        c1: Any, session: TradingSession
    ) -> SessionIndexedSelectedC3SnapshotReadResult:
        reader = WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority(c1)
        retained_readers.append(reader)
        return reader.read_selected_snapshot_for_session(session)

    def require_storage(
        c1: Any,
        expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
        storage: PersonalDesktopUnattendedDecisionStorageReadResult,
    ) -> None:
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
            raise ValueError("decision storage lacks exact current-C1 provenance")

    def set_publication_gate(value: bool) -> None:
        if type(value) is not bool:
            raise TypeError("decision publication gate must be boolean")
        publication.PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED = (
            value
        )

    return DisposableUnattendedDecisionPublicationDependencies(
        personal_desktop_unattended_effect_gate_state,
        set_publication_gate,
        acquire_validated_production_authority,
        require_validated_production_authority,
        lambda: datetime.now(UTC),
        resolve_personal_desktop_historical_cycle_configurations,
        lambda c1, historical: read_personal_desktop_paper_account(
            c1, historical_cycle_configuration_payloads=historical
        ),
        require_validated_personal_desktop_paper_account,
        supervised_paper_cycle_admission,
        read_selected,
        build_personal_desktop_unattended_c3_history,
        build_personal_desktop_unattended_next_decision,
        read_personal_desktop_unattended_decision_storage,
        require_storage,
        publication.qualify_personal_desktop_unattended_decision_publication,
        publication.issue_pre_open_decision_publication_permit,
        open_personal_desktop_unattended_decision_output_capability,
    )
