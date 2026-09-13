"""Strict read-only authority for the fixed unattended-decision namespace."""

from __future__ import annotations

import re
import threading
import weakref
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

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
