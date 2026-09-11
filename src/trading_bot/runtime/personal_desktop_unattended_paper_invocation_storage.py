"""Fixed read-only storage authority for canonical PD4 invocation artifacts.

The production boundary admits no caller-selected path, SID, native API, or
calendar.  It verifies the complete fixed namespace through pinned read-only
handles and retains successful production provenance privately for later PD4
composition.  This module contains no publication or mutation capability.
"""

from __future__ import annotations

import re
import threading
import weakref
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    IdentifiedMarketCalendar,
)
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS,
    PaperReadNativeApi,
    PinnedTradingPaperReadSession,
    WindowsPaperReadNativeApi,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObserver,
    WindowsTradingTokenObserver,
    require_trading_token,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation import (
    PersonalDesktopUnattendedPaperInvocation,
    PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    verify_personal_desktop_unattended_paper_invocation,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)

_UUID_TEXT = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_FINAL_NAME = re.compile(rf"unattended-paper-invocation-({_UUID_TEXT})")
_STAGING_NAME = re.compile(rf"\.unattended-paper-invocation-({_UUID_TEXT})\.staging")


class PersonalDesktopUnattendedInvocationStorageClassification(StrEnum):
    """Stable read-only classification of the complete fixed namespace."""

    ABSENT = "ABSENT"
    FINALIZED_IDENTICAL = "FINALIZED_IDENTICAL"
    STAGING_PRESENT = "STAGING_PRESENT"
    CONFLICTING = "CONFLICTING"
    BLOCKED = "BLOCKED"


class PersonalDesktopUnattendedInvocationStorageDiagnostic(StrEnum):
    """Sanitized diagnostic for an unattended-invocation storage read."""

    VERIFIED_ABSENT = "VERIFIED_ABSENT"
    VERIFIED_FINALIZED_IDENTICAL = "VERIFIED_FINALIZED_IDENTICAL"
    STAGING_PRESENT = "STAGING_PRESENT"
    VERIFIED_CONFLICT = "VERIFIED_CONFLICT"
    VERIFICATION_BLOCKED = "VERIFICATION_BLOCKED"


class PersonalDesktopUnattendedInvocationStorageError(Exception):
    """Raised when trusted storage-read provenance is unavailable."""


@dataclass(frozen=True, slots=True, eq=False, weakref_slot=True)
class PersonalDesktopUnattendedInvocationStorageReadResult:
    """Immutable sanitized read result with no filesystem authority."""

    classification: PersonalDesktopUnattendedInvocationStorageClassification
    expected_invocation_id: UUID | None
    finalized_invocation_count: int
    matching_invocation_id: UUID | None
    diagnostic: PersonalDesktopUnattendedInvocationStorageDiagnostic

    def __post_init__(self) -> None:
        classifications = PersonalDesktopUnattendedInvocationStorageClassification
        expected_diagnostic = {
            classifications.ABSENT: (
                PersonalDesktopUnattendedInvocationStorageDiagnostic.VERIFIED_ABSENT
            ),
            classifications.FINALIZED_IDENTICAL: (
                PersonalDesktopUnattendedInvocationStorageDiagnostic.VERIFIED_FINALIZED_IDENTICAL
            ),
            classifications.STAGING_PRESENT: (
                PersonalDesktopUnattendedInvocationStorageDiagnostic.STAGING_PRESENT
            ),
            classifications.CONFLICTING: (
                PersonalDesktopUnattendedInvocationStorageDiagnostic.VERIFIED_CONFLICT
            ),
            classifications.BLOCKED: (
                PersonalDesktopUnattendedInvocationStorageDiagnostic.VERIFICATION_BLOCKED
            ),
        }.get(self.classification)
        identical = self.classification is classifications.FINALIZED_IDENTICAL
        blocked = self.classification is classifications.BLOCKED
        if (
            type(self.classification)
            is not PersonalDesktopUnattendedInvocationStorageClassification
            or type(self.diagnostic)
            is not PersonalDesktopUnattendedInvocationStorageDiagnostic
            or self.diagnostic is not expected_diagnostic
            or (
                self.expected_invocation_id is not None
                and type(self.expected_invocation_id) is not UUID
            )
            or (not blocked and self.expected_invocation_id is None)
            or type(self.finalized_invocation_count) is not int
            or self.finalized_invocation_count < 0
            or (identical != (self.matching_invocation_id is not None))
            or (
                self.matching_invocation_id is not None
                and (
                    type(self.matching_invocation_id) is not UUID
                    or self.matching_invocation_id != self.expected_invocation_id
                )
            )
        ):
            raise ValueError("unattended invocation storage result is invalid")


@dataclass(frozen=True, slots=True)
class _VerifiedStorageRead:
    authority: ValidatedProductionAuthority | None
    expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding
    finalized: tuple[PersonalDesktopUnattendedPaperInvocationArtifactBinding, ...]
    classification: PersonalDesktopUnattendedInvocationStorageClassification


_REGISTRY: weakref.WeakKeyDictionary[
    PersonalDesktopUnattendedInvocationStorageReadResult, _VerifiedStorageRead
] = weakref.WeakKeyDictionary()
_REGISTRY_LOCK = threading.Lock()


def unattended_paper_invocation_directory_name(
    invocation_id: UUID, *, staging: bool = False
) -> str:
    """Return the one canonical final or staging directory name."""

    if type(invocation_id) is not UUID or type(staging) is not bool:
        raise PersonalDesktopUnattendedInvocationStorageError(
            "invocation directory identity is invalid"
        )
    prefix = (
        ".unattended-paper-invocation-" if staging else "unattended-paper-invocation-"
    )
    suffix = ".staging" if staging else ""
    return f"{prefix}{invocation_id}{suffix}"


def unattended_paper_invocation_artifact_name(invocation_id: UUID) -> str:
    """Return the one canonical JSON artifact name for an invocation."""

    if type(invocation_id) is not UUID:
        raise PersonalDesktopUnattendedInvocationStorageError(
            "invocation artifact identity is invalid"
        )
    return f"personal-desktop-unattended-paper-invocation-{invocation_id}.json"


def require_validated_personal_desktop_unattended_invocation_storage_read(
    result: PersonalDesktopUnattendedInvocationStorageReadResult,
) -> _VerifiedStorageRead:
    """Require genuine same-process production provenance for a safe read."""

    with _REGISTRY_LOCK:
        if (
            type(result) is not PersonalDesktopUnattendedInvocationStorageReadResult
            or result.classification
            not in {
                PersonalDesktopUnattendedInvocationStorageClassification.ABSENT,
                PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL,
            }
            or result not in _REGISTRY
        ):
            raise PersonalDesktopUnattendedInvocationStorageError(
                "unattended invocation storage read lacks production provenance"
            )
        return _REGISTRY[result]


def read_personal_desktop_unattended_invocation_storage(
    authority: ValidatedProductionAuthority,
    expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
) -> PersonalDesktopUnattendedInvocationStorageReadResult:
    """Read and classify only the fixed production invocation namespace."""

    try:
        c1 = require_validated_production_authority(authority)
        verified = _perform_storage_read(
            expected,
            c1.approved_account_sid,
            authority=c1,
            api=None,
            observer=WindowsTradingTokenObserver(),
            calendar=BoundMarketCalendar(
                XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()
            ),
        )
        require_validated_production_authority(c1)
    except Exception:
        return _blocked_result(_expected_invocation_id(expected))
    result = _public_result(verified)
    if verified.classification in {
        PersonalDesktopUnattendedInvocationStorageClassification.ABSENT,
        PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL,
    }:
        with _REGISTRY_LOCK:
            _REGISTRY[result] = verified
    return result


def _read_personal_desktop_unattended_invocation_storage_for_test(
    expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    trading_sid: str,
    *,
    api: PaperReadNativeApi,
    observer: TradingTokenObserver,
    calendar: IdentifiedMarketCalendar,
) -> PersonalDesktopUnattendedInvocationStorageReadResult:
    """Exercise explicit disposable seams without production provenance."""

    try:
        if api is None:
            raise PersonalDesktopUnattendedInvocationStorageError(
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
        return _blocked_result(_expected_invocation_id(expected))
    return _public_result(verified)


def _perform_storage_read(
    expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    trading_sid: str,
    *,
    authority: ValidatedProductionAuthority | None,
    api: PaperReadNativeApi | None,
    observer: TradingTokenObserver,
    calendar: IdentifiedMarketCalendar,
) -> _VerifiedStorageRead:
    initial_token = observer.observe()
    require_trading_token(trading_sid, initial_token)
    try:
        replayed_expected = _replay_expected(expected, calendar)
        read_api = WindowsPaperReadNativeApi() if api is None else api
        verified = _read_fixed_namespace(
            replayed_expected,
            trading_sid,
            authority=authority,
            api=read_api,
            calendar=calendar,
        )
    finally:
        final_token = observer.observe()
        require_trading_token(trading_sid, final_token)
        if final_token != initial_token:
            raise PersonalDesktopUnattendedInvocationStorageError(
                "Trading token changed during unattended invocation storage read"
            )
    return verified


def _replay_expected(
    expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    calendar: IdentifiedMarketCalendar,
) -> PersonalDesktopUnattendedPaperInvocationArtifactBinding:
    if type(expected) is not PersonalDesktopUnattendedPaperInvocationArtifactBinding:
        raise PersonalDesktopUnattendedInvocationStorageError(
            "expected invocation binding type is invalid"
        )
    replayed = verify_personal_desktop_unattended_paper_invocation(
        expected.artifact_bytes,
        calendar,
        expected_invocation_id=expected.invocation.invocation_id,
        expected_artifact_sha256=expected.artifact_sha256,
        expected_artifact_byte_length=expected.artifact_byte_length,
    )
    if replayed != expected:
        raise PersonalDesktopUnattendedInvocationStorageError(
            "expected invocation binding differs from exact replay"
        )
    return replayed


def _read_fixed_namespace(
    expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    trading_sid: str,
    *,
    authority: ValidatedProductionAuthority | None,
    api: PaperReadNativeApi,
    calendar: IdentifiedMarketCalendar,
) -> _VerifiedStorageRead:
    expected_id = expected.invocation.invocation_id
    finalized: list[PersonalDesktopUnattendedPaperInvocationArtifactBinding] = []
    conflicting = False
    with PinnedTradingPaperReadSession(api, trading_sid) as session:
        names = session.names(PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS)
        final_entries: list[tuple[str, UUID]] = []
        staging_entries: list[str] = []
        for name in names:
            final_match = _FINAL_NAME.fullmatch(name)
            staging_match = _STAGING_NAME.fullmatch(name)
            if final_match is not None:
                final_entries.append((name, _canonical_uuid(final_match.group(1))))
            elif staging_match is not None:
                _canonical_uuid(staging_match.group(1))
                staging_entries.append(name)
            else:
                raise PersonalDesktopUnattendedInvocationStorageError(
                    "unattended invocation namespace contains an unknown entry"
                )
        if staging_entries:
            for name in staging_entries:
                session.pin(
                    PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS + "\\" + name
                )
        for name, directory_id in final_entries:
            directory = PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS + "\\" + name
            artifact_name = unattended_paper_invocation_artifact_name(directory_id)
            if session.names(directory) != (artifact_name,):
                raise PersonalDesktopUnattendedInvocationStorageError(
                    "finalized invocation directory contents are invalid"
                )
            binding = verify_personal_desktop_unattended_paper_invocation(
                session.read(directory + "\\" + artifact_name), calendar
            )
            if binding.invocation.invocation_id != directory_id:
                if directory_id == expected_id:
                    conflicting = True
                else:
                    raise PersonalDesktopUnattendedInvocationStorageError(
                        "historical invocation name and artifact identity disagree"
                    )
            finalized.append(binding)
    expected_matches = tuple(
        binding
        for binding in finalized
        if binding.invocation.invocation_id == expected_id
    )
    expected_directory_present = any(
        identity == expected_id for _, identity in final_entries
    )
    if staging_entries:
        classification = (
            PersonalDesktopUnattendedInvocationStorageClassification.STAGING_PRESENT
        )
    elif not expected_directory_present:
        classification = PersonalDesktopUnattendedInvocationStorageClassification.ABSENT
    elif conflicting or expected_matches != (expected,):
        classification = (
            PersonalDesktopUnattendedInvocationStorageClassification.CONFLICTING
        )
    else:
        classification = (
            PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL
        )
    return _VerifiedStorageRead(authority, expected, tuple(finalized), classification)


def _canonical_uuid(value: str) -> UUID:
    try:
        identity = UUID(value)
    except ValueError:
        raise PersonalDesktopUnattendedInvocationStorageError(
            "unattended invocation identity name is malformed"
        ) from None
    if str(identity) != value:
        raise PersonalDesktopUnattendedInvocationStorageError(
            "unattended invocation identity name is noncanonical"
        )
    return identity


def _expected_invocation_id(expected: object) -> UUID | None:
    if type(expected) is not PersonalDesktopUnattendedPaperInvocationArtifactBinding:
        return None
    invocation = expected.invocation
    if type(invocation) is not PersonalDesktopUnattendedPaperInvocation:
        return None
    return invocation.invocation_id if type(invocation.invocation_id) is UUID else None


def _public_result(
    verified: _VerifiedStorageRead,
) -> PersonalDesktopUnattendedInvocationStorageReadResult:
    classifications = PersonalDesktopUnattendedInvocationStorageClassification
    diagnostics = PersonalDesktopUnattendedInvocationStorageDiagnostic
    diagnostic = {
        classifications.ABSENT: diagnostics.VERIFIED_ABSENT,
        classifications.FINALIZED_IDENTICAL: diagnostics.VERIFIED_FINALIZED_IDENTICAL,
        classifications.STAGING_PRESENT: diagnostics.STAGING_PRESENT,
        classifications.CONFLICTING: diagnostics.VERIFIED_CONFLICT,
    }[verified.classification]
    expected_id = verified.expected.invocation.invocation_id
    return PersonalDesktopUnattendedInvocationStorageReadResult(
        classification=verified.classification,
        expected_invocation_id=expected_id,
        finalized_invocation_count=len(verified.finalized),
        matching_invocation_id=(
            expected_id
            if verified.classification is classifications.FINALIZED_IDENTICAL
            else None
        ),
        diagnostic=diagnostic,
    )


def _blocked_result(
    expected_invocation_id: UUID | None,
) -> PersonalDesktopUnattendedInvocationStorageReadResult:
    return PersonalDesktopUnattendedInvocationStorageReadResult(
        classification=PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED,
        expected_invocation_id=expected_invocation_id,
        finalized_invocation_count=0,
        matching_invocation_id=None,
        diagnostic=PersonalDesktopUnattendedInvocationStorageDiagnostic.VERIFICATION_BLOCKED,
    )
