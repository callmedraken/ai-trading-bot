"""Strict read-only authority for the fixed unattended-decision namespace."""

from __future__ import annotations

import re
import threading
import weakref
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import IdentifiedMarketCalendar
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS,
    PaperReadNativeApi,
    PinnedTradingPaperReadSession,
    WindowsPaperReadNativeApi,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObserver,
    WindowsTradingTokenObserver,
    require_trading_token,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    completed_xnys_session_at,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_intent import (
    PersonalDesktopUnattendedPaperDecisionIntent,
    PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    personal_desktop_unattended_decision_calendar,
    verify_personal_desktop_unattended_paper_decision_intent,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)

_UUID_TEXT = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_FINAL_NAME = re.compile(rf"unattended-paper-decision-({_UUID_TEXT})")
_STAGING_NAME = re.compile(rf"\.unattended-paper-decision-({_UUID_TEXT})\.staging")


class PersonalDesktopUnattendedDecisionStorageClassification(StrEnum):
    """Complete fixed-namespace read classifications."""

    ABSENT = "ABSENT"
    FINALIZED_IDENTICAL = "FINALIZED_IDENTICAL"
    STAGING_PRESENT = "STAGING_PRESENT"
    CONFLICTING = "CONFLICTING"
    BLOCKED = "BLOCKED"


class PersonalDesktopUnattendedDecisionStorageDiagnostic(StrEnum):
    VERIFIED_ABSENT = "VERIFIED_ABSENT"
    VERIFIED_FINALIZED_IDENTICAL = "VERIFIED_FINALIZED_IDENTICAL"
    STAGING_PRESENT = "STAGING_PRESENT"
    VERIFIED_CONFLICT = "VERIFIED_CONFLICT"
    VERIFICATION_BLOCKED = "VERIFICATION_BLOCKED"


class PersonalDesktopUnattendedDecisionStorageError(Exception):
    """Trusted decision-storage read provenance is unavailable."""


class FinalizedUnattendedDecisionForSessionClassification(StrEnum):
    """Complete fixed-namespace discovery classifications for one session."""

    NONE = "NONE"
    FINALIZED = "FINALIZED"
    BLOCKED = "BLOCKED"


class SingleDeferredDecisionClassification(StrEnum):
    NONE = "NONE"
    FINALIZED = "FINALIZED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True, eq=False, weakref_slot=True)
class SingleDeferredDecisionResult:
    """Bounded complete-namespace evidence, with no reusable public authority."""

    classification: SingleDeferredDecisionClassification
    current_completed_session: TradingSession | None = None
    execution_session: TradingSession | None = None
    decision_id: UUID | None = None
    binding: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding | None = None

    def __post_init__(self) -> None:
        c = SingleDeferredDecisionClassification
        finalized = self.classification is c.FINALIZED
        if (
            type(self.classification) is not c
            or any(
                value is not None and type(value) is not TradingSession
                for value in (self.current_completed_session, self.execution_session)
            )
            or (
                self.classification is c.BLOCKED
                and self.current_completed_session is not None
            )
            or (
                self.classification is c.NONE and self.current_completed_session is None
            )
            or (finalized != (self.execution_session is not None))
            or (finalized != (self.decision_id is not None))
            or (finalized != (self.binding is not None))
            or (
                finalized
                and (
                    type(self.decision_id) is not UUID
                    or type(self.binding)
                    is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
                    or self.binding.decision.decision_id != self.decision_id
                    or self.binding.decision.intended_execution_session
                    != self.execution_session
                    or self.execution_session >= self.current_completed_session
                )
            )
        ):
            raise ValueError("single deferred decision result is invalid")


@dataclass(frozen=True, slots=True, eq=False, weakref_slot=True)
class FinalizedUnattendedDecisionForSessionResult:
    """Sanitized session-indexed discovery with an immutable verified binding."""

    classification: FinalizedUnattendedDecisionForSessionClassification
    execution_session: TradingSession
    decision_id: UUID | None
    binding: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding | None

    def __post_init__(self) -> None:
        finalized = (
            self.classification
            is FinalizedUnattendedDecisionForSessionClassification.FINALIZED
        )
        if (
            type(self.classification)
            is not FinalizedUnattendedDecisionForSessionClassification
            or type(self.execution_session) is not TradingSession
            or (finalized != (self.decision_id is not None))
            or (finalized != (self.binding is not None))
            or (self.decision_id is not None and type(self.decision_id) is not UUID)
            or (
                self.binding is not None
                and (
                    type(self.binding)
                    is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
                    or self.binding.decision.decision_id != self.decision_id
                    or self.binding.decision.intended_execution_session
                    != self.execution_session
                )
            )
        ):
            raise ValueError("finalized decision session result is invalid")


@dataclass(frozen=True, slots=True, eq=False, weakref_slot=True)
class PersonalDesktopUnattendedDecisionStorageReadResult:
    classification: PersonalDesktopUnattendedDecisionStorageClassification
    expected_decision_id: UUID | None
    finalized_decision_count: int
    matching_decision_id: UUID | None
    diagnostic: PersonalDesktopUnattendedDecisionStorageDiagnostic

    def __post_init__(self) -> None:
        c = PersonalDesktopUnattendedDecisionStorageClassification
        d = PersonalDesktopUnattendedDecisionStorageDiagnostic
        expected = {
            c.ABSENT: d.VERIFIED_ABSENT,
            c.FINALIZED_IDENTICAL: d.VERIFIED_FINALIZED_IDENTICAL,
            c.STAGING_PRESENT: d.STAGING_PRESENT,
            c.CONFLICTING: d.VERIFIED_CONFLICT,
            c.BLOCKED: d.VERIFICATION_BLOCKED,
        }.get(self.classification)
        identical = self.classification is c.FINALIZED_IDENTICAL
        blocked = self.classification is c.BLOCKED
        if (
            type(self.classification)
            is not PersonalDesktopUnattendedDecisionStorageClassification
            or type(self.diagnostic)
            is not PersonalDesktopUnattendedDecisionStorageDiagnostic
            or self.diagnostic is not expected
            or (
                self.expected_decision_id is not None
                and type(self.expected_decision_id) is not UUID
            )
            or (not blocked and self.expected_decision_id is None)
            or type(self.finalized_decision_count) is not int
            or self.finalized_decision_count < 0
            or (identical != (self.matching_decision_id is not None))
            or (
                self.matching_decision_id is not None
                and self.matching_decision_id != self.expected_decision_id
            )
        ):
            raise ValueError("unattended decision storage result is invalid")


@dataclass(frozen=True, slots=True)
class _VerifiedDecisionStorageRead:
    authority: ValidatedProductionAuthority | None
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
    finalized: tuple[PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding, ...]
    classification: PersonalDesktopUnattendedDecisionStorageClassification


_REGISTRY: weakref.WeakKeyDictionary[
    PersonalDesktopUnattendedDecisionStorageReadResult, _VerifiedDecisionStorageRead
] = weakref.WeakKeyDictionary()
_REGISTRY_LOCK = threading.Lock()

_SESSION_REGISTRY: weakref.WeakKeyDictionary[
    FinalizedUnattendedDecisionForSessionResult,
    tuple[
        ValidatedProductionAuthority,
        PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding | None,
    ],
] = weakref.WeakKeyDictionary()


_DEFERRED_REGISTRY: weakref.WeakKeyDictionary[
    SingleDeferredDecisionResult,
    tuple[
        ValidatedProductionAuthority,
        PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding | None,
    ],
] = weakref.WeakKeyDictionary()


def find_single_deferred_unattended_decision(
    authority: ValidatedProductionAuthority,
) -> SingleDeferredDecisionResult:
    """Read the complete fixed namespace and derive the sole prior-session decision."""

    try:
        c1 = require_validated_production_authority(authority)
        observer = WindowsTradingTokenObserver()
        first = observer.observe()
        require_trading_token(c1.approved_account_sid, first)
        completed = completed_xnys_session_at(datetime.now(UTC))
        finalized = _read_complete_fixed_namespace(
            c1.approved_account_sid,
            api=WindowsPaperReadNativeApi(),
            calendar=personal_desktop_unattended_decision_calendar(),
        )
        last = observer.observe()
        require_trading_token(c1.approved_account_sid, last)
        if last != first or completed_xnys_session_at(datetime.now(UTC)) != completed:
            raise PersonalDesktopUnattendedDecisionStorageError(
                "decision read provenance changed"
            )
        require_validated_production_authority(c1)
        result = _single_deferred_result(finalized, completed)
        if result.classification in {
            SingleDeferredDecisionClassification.NONE,
            SingleDeferredDecisionClassification.FINALIZED,
        }:
            with _REGISTRY_LOCK:
                _DEFERRED_REGISTRY[result] = (c1, result.binding)
        return result
    except Exception:
        return SingleDeferredDecisionResult(
            SingleDeferredDecisionClassification.BLOCKED
        )


def require_single_deferred_unattended_decision(
    result: SingleDeferredDecisionResult,
    authority: ValidatedProductionAuthority,
) -> PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding | None:
    """Require same-process current-C1 provenance for exact absence or candidate."""

    try:
        c1 = require_validated_production_authority(authority)
    except Exception as error:
        raise PersonalDesktopUnattendedDecisionStorageError(
            "deferred decision lacks C1 provenance"
        ) from error
    if type(result) is not SingleDeferredDecisionResult:
        raise PersonalDesktopUnattendedDecisionStorageError(
            "deferred decision lacks C1 provenance"
        )
    try:
        result.__post_init__()
    except ValueError as error:
        raise PersonalDesktopUnattendedDecisionStorageError(
            "deferred decision result is invalid"
        ) from error
    with _REGISTRY_LOCK:
        evidence = _DEFERRED_REGISTRY.get(result)
    if (
        result.classification is SingleDeferredDecisionClassification.BLOCKED
        or evidence is None
        or evidence[0] != c1
        or evidence[1] is not result.binding
    ):
        raise PersonalDesktopUnattendedDecisionStorageError(
            "deferred decision lacks C1 provenance"
        )
    return evidence[1]


def _single_deferred_result(
    finalized: tuple[PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding, ...],
    completed: TradingSession,
) -> SingleDeferredDecisionResult:
    if not finalized:
        return SingleDeferredDecisionResult(
            SingleDeferredDecisionClassification.NONE, completed
        )
    if len(finalized) != 1:
        raise PersonalDesktopUnattendedDecisionStorageError(
            "exactly one finalized decision is required"
        )
    binding = finalized[0]
    execution = binding.decision.intended_execution_session
    if execution >= completed:
        raise PersonalDesktopUnattendedDecisionStorageError("decision is not deferred")
    return SingleDeferredDecisionResult(
        SingleDeferredDecisionClassification.FINALIZED,
        completed,
        execution,
        binding.decision.decision_id,
        binding,
    )


def _find_single_deferred_unattended_decision_for_test(
    trading_sid: str,
    observed_at: datetime,
    *,
    api: PaperReadNativeApi,
    observer: TradingTokenObserver,
    calendar: IdentifiedMarketCalendar,
) -> SingleDeferredDecisionResult:
    """Disposable complete-namespace seam; never registers production C1 provenance."""

    try:
        if api is None or isinstance(api, WindowsPaperReadNativeApi):
            raise PersonalDesktopUnattendedDecisionStorageError(
                "fake native API required"
            )
        first = observer.observe()
        require_trading_token(trading_sid, first)
        try:
            finalized = _read_complete_fixed_namespace(
                trading_sid, api=api, calendar=calendar
            )
        finally:
            last = observer.observe()
            require_trading_token(trading_sid, last)
            if last != first:
                raise PersonalDesktopUnattendedDecisionStorageError(
                    "Trading token changed"
                )
        return _single_deferred_result(
            finalized, completed_xnys_session_at(observed_at)
        )
    except Exception:
        return SingleDeferredDecisionResult(
            SingleDeferredDecisionClassification.BLOCKED
        )


def unattended_paper_decision_directory_name(
    decision_id: UUID, *, staging: bool = False
) -> str:
    """Return the only canonical final or staging directory name."""

    if type(decision_id) is not UUID or type(staging) is not bool:
        raise PersonalDesktopUnattendedDecisionStorageError(
            "decision directory identity is invalid"
        )
    prefix = ".unattended-paper-decision-" if staging else "unattended-paper-decision-"
    suffix = ".staging" if staging else ""
    return f"{prefix}{decision_id}{suffix}"


def unattended_paper_decision_artifact_name(decision_id: UUID) -> str:
    """Return the only canonical decision-intent artifact name."""

    if type(decision_id) is not UUID:
        raise PersonalDesktopUnattendedDecisionStorageError(
            "decision artifact identity is invalid"
        )
    return f"personal-desktop-unattended-paper-decision-intent-{decision_id}.json"


def require_validated_personal_desktop_unattended_decision_storage_read(
    result: PersonalDesktopUnattendedDecisionStorageReadResult,
) -> _VerifiedDecisionStorageRead:
    """Require genuine same-process production provenance for a safe read."""

    with _REGISTRY_LOCK:
        if (
            type(result) is not PersonalDesktopUnattendedDecisionStorageReadResult
            or result.classification
            not in {
                PersonalDesktopUnattendedDecisionStorageClassification.ABSENT,
                PersonalDesktopUnattendedDecisionStorageClassification.FINALIZED_IDENTICAL,
            }
            or result not in _REGISTRY
        ):
            raise PersonalDesktopUnattendedDecisionStorageError(
                "unattended decision storage read lacks production provenance"
            )
        return _REGISTRY[result]


def read_personal_desktop_unattended_decision_storage(
    authority: ValidatedProductionAuthority,
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
) -> PersonalDesktopUnattendedDecisionStorageReadResult:
    """Read and classify only the fixed production decision namespace."""

    try:
        c1 = require_validated_production_authority(authority)
        verified = _perform_storage_read(
            expected,
            c1.approved_account_sid,
            authority=c1,
            api=None,
            observer=WindowsTradingTokenObserver(),
            calendar=personal_desktop_unattended_decision_calendar(),
        )
        require_validated_production_authority(c1)
    except Exception:
        return _blocked_result(_expected_decision_id(expected))
    result = _public_result(verified)
    if verified.classification in {
        PersonalDesktopUnattendedDecisionStorageClassification.ABSENT,
        PersonalDesktopUnattendedDecisionStorageClassification.FINALIZED_IDENTICAL,
    }:
        with _REGISTRY_LOCK:
            _REGISTRY[result] = verified
    return result


def find_finalized_unattended_decision_for_execution_session(
    execution_session: TradingSession,
    authority: ValidatedProductionAuthority,
) -> FinalizedUnattendedDecisionForSessionResult:
    """Resolve at most one finalized G4 decision targeting one exact session."""

    if type(execution_session) is not TradingSession:
        raise PersonalDesktopUnattendedDecisionStorageError(
            "execution session must be an exact TradingSession"
        )
    try:
        c1 = require_validated_production_authority(authority)
        finalized = _perform_session_discovery(
            execution_session,
            c1.approved_account_sid,
            api=WindowsPaperReadNativeApi(),
            observer=WindowsTradingTokenObserver(),
            calendar=personal_desktop_unattended_decision_calendar(),
        )
        if finalized is not None:
            _require_decision_c3_matches_current_authority(finalized, c1)
        require_validated_production_authority(c1)
        result = _session_result(execution_session, finalized)
    except Exception:
        return _blocked_session_result(execution_session)
    with _REGISTRY_LOCK:
        _SESSION_REGISTRY[result] = (c1, finalized)
    return result


def require_finalized_unattended_decision_for_execution_session(
    result: FinalizedUnattendedDecisionForSessionResult,
    authority: ValidatedProductionAuthority,
) -> PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding | None:
    """Require same-process current-C1 provenance for session discovery."""

    try:
        c1 = require_validated_production_authority(authority)
    except Exception as error:
        raise PersonalDesktopUnattendedDecisionStorageError(
            "finalized decision discovery lacks current-C1 provenance"
        ) from error
    with _REGISTRY_LOCK:
        evidence = _SESSION_REGISTRY.get(result)
    if (
        type(result) is not FinalizedUnattendedDecisionForSessionResult
        or result.classification
        is FinalizedUnattendedDecisionForSessionClassification.BLOCKED
        or evidence is None
        or evidence[0] != c1
        or evidence[1] is not result.binding
    ):
        raise PersonalDesktopUnattendedDecisionStorageError(
            "finalized decision discovery lacks current-C1 provenance"
        )
    return evidence[1]


def _find_finalized_unattended_decision_for_execution_session_for_test(
    execution_session: TradingSession,
    trading_sid: str,
    *,
    api: PaperReadNativeApi,
    observer: TradingTokenObserver,
    calendar: IdentifiedMarketCalendar,
) -> FinalizedUnattendedDecisionForSessionResult:
    """Exercise complete namespace discovery through disposable native seams."""

    try:
        if api is None or isinstance(api, WindowsPaperReadNativeApi):
            raise PersonalDesktopUnattendedDecisionStorageError(
                "disposable discovery requires an explicit fake native API"
            )
        finalized = _perform_session_discovery(
            execution_session,
            trading_sid,
            api=api,
            observer=observer,
            calendar=calendar,
        )
        return _session_result(execution_session, finalized)
    except Exception:
        return _blocked_session_result(execution_session)


def _read_personal_desktop_unattended_decision_storage_for_test(
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    trading_sid: str,
    *,
    api: PaperReadNativeApi,
    observer: TradingTokenObserver,
    calendar: IdentifiedMarketCalendar,
) -> PersonalDesktopUnattendedDecisionStorageReadResult:
    """Exercise the read path with explicit disposable, non-production seams."""

    try:
        if api is None or isinstance(api, WindowsPaperReadNativeApi):
            raise PersonalDesktopUnattendedDecisionStorageError(
                "disposable storage reads require an explicit fake native API"
            )
        verified = _perform_storage_read(
            expected,
            trading_sid,
            authority=None,
            api=api,
            observer=observer,
            calendar=calendar,
        )
    except Exception:
        return _blocked_result(_expected_decision_id(expected))
    return _public_result(verified)


def _perform_storage_read(
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    trading_sid: str,
    *,
    authority: ValidatedProductionAuthority | None,
    api: PaperReadNativeApi | None,
    observer: TradingTokenObserver,
    calendar: IdentifiedMarketCalendar,
) -> _VerifiedDecisionStorageRead:
    initial = observer.observe()
    require_trading_token(trading_sid, initial)
    try:
        replayed = _replay_expected(expected, calendar)
        result = _read_fixed_namespace(
            replayed,
            trading_sid,
            authority=authority,
            api=WindowsPaperReadNativeApi() if api is None else api,
            calendar=calendar,
        )
    finally:
        final = observer.observe()
        require_trading_token(trading_sid, final)
        if final != initial:
            raise PersonalDesktopUnattendedDecisionStorageError(
                "Trading token changed during decision storage read"
            )
    return result


def _perform_session_discovery(
    execution_session: TradingSession,
    trading_sid: str,
    *,
    api: PaperReadNativeApi,
    observer: TradingTokenObserver,
    calendar: IdentifiedMarketCalendar,
) -> PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding | None:
    if type(execution_session) is not TradingSession:
        raise PersonalDesktopUnattendedDecisionStorageError(
            "execution session must be an exact TradingSession"
        )
    initial = observer.observe()
    require_trading_token(trading_sid, initial)
    try:
        finalized = _read_complete_fixed_namespace(
            trading_sid,
            api=api,
            calendar=calendar,
        )
    finally:
        final = observer.observe()
        require_trading_token(trading_sid, final)
        if final != initial:
            raise PersonalDesktopUnattendedDecisionStorageError(
                "Trading token changed during decision session discovery"
            )
    matches = tuple(
        item
        for item in finalized
        if item.decision.intended_execution_session == execution_session
    )
    if len(matches) > 1:
        raise PersonalDesktopUnattendedDecisionStorageError(
            "multiple finalized decisions target the execution session"
        )
    return matches[0] if matches else None


def _read_complete_fixed_namespace(
    trading_sid: str,
    *,
    api: PaperReadNativeApi,
    calendar: IdentifiedMarketCalendar,
) -> tuple[PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding, ...]:
    finalized: list[PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding] = []
    with PinnedTradingPaperReadSession(api, trading_sid) as session:
        names = session.names(PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS)
        finals: list[tuple[str, UUID]] = []
        for name in names:
            final_match = _FINAL_NAME.fullmatch(name)
            if final_match is not None:
                finals.append((name, _canonical_uuid(final_match.group(1))))
                continue
            if _STAGING_NAME.fullmatch(name) is not None:
                raise PersonalDesktopUnattendedDecisionStorageError(
                    "decision namespace contains staging state"
                )
            raise PersonalDesktopUnattendedDecisionStorageError(
                "decision namespace contains an unknown entry"
            )
        for name, directory_id in finals:
            directory = PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS + "\\" + name
            artifact_name = unattended_paper_decision_artifact_name(directory_id)
            if session.names(directory) != (artifact_name,):
                raise PersonalDesktopUnattendedDecisionStorageError(
                    "finalized decision directory contents are invalid"
                )
            binding = verify_personal_desktop_unattended_paper_decision_intent(
                session.read(directory + "\\" + artifact_name), calendar
            )
            if binding.decision.decision_id != directory_id:
                raise PersonalDesktopUnattendedDecisionStorageError(
                    "decision directory and artifact identities disagree"
                )
            finalized.append(binding)
    if len({item.decision.decision_id for item in finalized}) != len(finalized):
        raise PersonalDesktopUnattendedDecisionStorageError(
            "decision namespace contains duplicate identities"
        )
    return tuple(finalized)


def _require_decision_c3_matches_current_authority(
    binding: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    authority: ValidatedProductionAuthority,
) -> None:
    reader = WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority(authority)
    for expected in (*binding.decision.history_c3, binding.decision.current_c3):
        actual = reader.read_selected_snapshot_for_session(expected.selected_session)
        audit = actual.selected.audit
        if (
            actual.selected.snapshot_bytes != expected.snapshot_artifact
            or audit.selection_id != expected.selection_id
            or audit.session_id != expected.session_id
            or audit.terminal_id != expected.terminal_id
            or audit.snapshot_id != expected.snapshot_id
            or audit.artifact_sha256 != expected.artifact_sha256
            or audit.artifact_byte_length != expected.artifact_byte_length
        ):
            raise PersonalDesktopUnattendedDecisionStorageError(
                "finalized decision C3 evidence differs from current C1 authority"
            )


def _replay_expected(
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    calendar: IdentifiedMarketCalendar,
) -> PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding:
    if (
        type(expected)
        is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
    ):
        raise PersonalDesktopUnattendedDecisionStorageError(
            "expected decision binding type is invalid"
        )
    replayed = verify_personal_desktop_unattended_paper_decision_intent(
        expected.artifact_bytes,
        calendar,
        expected_decision_id=expected.decision.decision_id,
        expected_artifact_sha256=expected.artifact_sha256,
        expected_artifact_byte_length=expected.artifact_byte_length,
    )
    if replayed != expected:
        raise PersonalDesktopUnattendedDecisionStorageError(
            "expected decision binding differs from exact replay"
        )
    return replayed


def _read_fixed_namespace(
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    trading_sid: str,
    *,
    authority: ValidatedProductionAuthority | None,
    api: PaperReadNativeApi,
    calendar: IdentifiedMarketCalendar,
) -> _VerifiedDecisionStorageRead:
    expected_id = expected.decision.decision_id
    finalized: list[PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding] = []
    conflicting = False
    with PinnedTradingPaperReadSession(api, trading_sid) as session:
        names = session.names(PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS)
        finals: list[tuple[str, UUID]] = []
        stagings: list[str] = []
        for name in names:
            final_match = _FINAL_NAME.fullmatch(name)
            staging_match = _STAGING_NAME.fullmatch(name)
            if final_match is not None:
                finals.append((name, _canonical_uuid(final_match.group(1))))
            elif staging_match is not None:
                _canonical_uuid(staging_match.group(1))
                stagings.append(name)
            else:
                raise PersonalDesktopUnattendedDecisionStorageError(
                    "decision namespace contains an unknown entry"
                )
        for name in stagings:
            session.pin(PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS + "\\" + name)
        for name, directory_id in finals:
            directory = PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS + "\\" + name
            artifact_name = unattended_paper_decision_artifact_name(directory_id)
            if session.names(directory) != (artifact_name,):
                raise PersonalDesktopUnattendedDecisionStorageError(
                    "finalized decision directory contents are invalid"
                )
            binding = verify_personal_desktop_unattended_paper_decision_intent(
                session.read(directory + "\\" + artifact_name), calendar
            )
            if binding.decision.decision_id != directory_id:
                if directory_id == expected_id:
                    conflicting = True
                else:
                    raise PersonalDesktopUnattendedDecisionStorageError(
                        "historical decision name and artifact identity disagree"
                    )
            finalized.append(binding)
    expected_matches = tuple(
        item for item in finalized if item.decision.decision_id == expected_id
    )
    expected_directory_present = any(identity == expected_id for _, identity in finals)
    if stagings:
        classification = (
            PersonalDesktopUnattendedDecisionStorageClassification.STAGING_PRESENT
        )
    elif not expected_directory_present:
        classification = PersonalDesktopUnattendedDecisionStorageClassification.ABSENT
    elif conflicting or expected_matches != (expected,):
        classification = (
            PersonalDesktopUnattendedDecisionStorageClassification.CONFLICTING
        )
    else:
        classification = (
            PersonalDesktopUnattendedDecisionStorageClassification.FINALIZED_IDENTICAL
        )
    return _VerifiedDecisionStorageRead(
        authority, expected, tuple(finalized), classification
    )


def _canonical_uuid(value: str) -> UUID:
    try:
        result = UUID(value)
    except ValueError:
        raise PersonalDesktopUnattendedDecisionStorageError(
            "decision identity name is malformed"
        ) from None
    if str(result) != value:
        raise PersonalDesktopUnattendedDecisionStorageError(
            "decision identity name is noncanonical"
        )
    return result


def _expected_decision_id(expected: object) -> UUID | None:
    if (
        type(expected)
        is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
    ):
        return None
    decision = expected.decision
    if type(decision) is not PersonalDesktopUnattendedPaperDecisionIntent:
        return None
    return decision.decision_id if type(decision.decision_id) is UUID else None


def _public_result(
    verified: _VerifiedDecisionStorageRead,
) -> PersonalDesktopUnattendedDecisionStorageReadResult:
    c = PersonalDesktopUnattendedDecisionStorageClassification
    d = PersonalDesktopUnattendedDecisionStorageDiagnostic
    diagnostic = {
        c.ABSENT: d.VERIFIED_ABSENT,
        c.FINALIZED_IDENTICAL: d.VERIFIED_FINALIZED_IDENTICAL,
        c.STAGING_PRESENT: d.STAGING_PRESENT,
        c.CONFLICTING: d.VERIFIED_CONFLICT,
    }[verified.classification]
    expected_id = verified.expected.decision.decision_id
    return PersonalDesktopUnattendedDecisionStorageReadResult(
        verified.classification,
        expected_id,
        len(verified.finalized),
        expected_id if verified.classification is c.FINALIZED_IDENTICAL else None,
        diagnostic,
    )


def _blocked_result(
    expected_id: UUID | None,
) -> PersonalDesktopUnattendedDecisionStorageReadResult:
    return PersonalDesktopUnattendedDecisionStorageReadResult(
        PersonalDesktopUnattendedDecisionStorageClassification.BLOCKED,
        expected_id,
        0,
        None,
        PersonalDesktopUnattendedDecisionStorageDiagnostic.VERIFICATION_BLOCKED,
    )


def _session_result(
    execution_session: TradingSession,
    binding: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding | None,
) -> FinalizedUnattendedDecisionForSessionResult:
    if binding is None:
        return FinalizedUnattendedDecisionForSessionResult(
            FinalizedUnattendedDecisionForSessionClassification.NONE,
            execution_session,
            None,
            None,
        )
    return FinalizedUnattendedDecisionForSessionResult(
        FinalizedUnattendedDecisionForSessionClassification.FINALIZED,
        execution_session,
        binding.decision.decision_id,
        binding,
    )


def _blocked_session_result(
    execution_session: TradingSession,
) -> FinalizedUnattendedDecisionForSessionResult:
    return FinalizedUnattendedDecisionForSessionResult(
        FinalizedUnattendedDecisionForSessionClassification.BLOCKED,
        execution_session,
        None,
        None,
    )
