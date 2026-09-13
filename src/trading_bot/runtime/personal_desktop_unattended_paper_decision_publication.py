"""Pre-open one-shot publication authority for durable G4 decisions."""

from __future__ import annotations

import threading
import weakref
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    PersonalDesktopPreOpenDecisionEligibility,
    classify_pre_open_decision_eligibility,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_intent import (
    PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    personal_desktop_unattended_decision_calendar,
    verify_personal_desktop_unattended_paper_decision_intent,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    PersonalDesktopUnattendedDecisionStorageClassification,
    PersonalDesktopUnattendedDecisionStorageReadResult,
    read_personal_desktop_unattended_decision_storage,
    require_validated_personal_desktop_unattended_decision_storage_read,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)

PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED = False

_PERMIT_ISSUER = object()
_DISPOSABLE_PERMIT_ISSUER = object()


class PersonalDesktopUnattendedDecisionPublicationError(Exception):
    """Decision publication authority failed closed."""


class PersonalDesktopUnattendedDecisionPublicationStatus(StrEnum):
    DECISION_ALREADY_FINALIZED = "DECISION_ALREADY_FINALIZED"
    DECISION_READY = "DECISION_READY"
    DECISION_READY_EFFECTS_DISABLED = "DECISION_READY_EFFECTS_DISABLED"
    MISSED_DECISION_DEADLINE = "MISSED_DECISION_DEADLINE"
    BLOCKED = "BLOCKED"


class PersonalDesktopUnattendedDecisionPublicationDiagnostic(StrEnum):
    FINALIZED_IDENTICAL = "FINALIZED_IDENTICAL"
    PRE_OPEN_READY = "PRE_OPEN_READY"
    PUBLICATION_EFFECT_DISABLED = "PUBLICATION_EFFECT_DISABLED"
    DEADLINE_REACHED = "DEADLINE_REACHED"
    STORAGE_NOT_SAFE = "STORAGE_NOT_SAFE"


class PreOpenDecisionPublicationPermit:
    """Sealed process-local proof of one exact pre-open admission."""

    __slots__ = ("_nonce", "__weakref__")

    def __init__(self, *, _issuer: object | None = None) -> None:
        if _issuer not in {_PERMIT_ISSUER, _DISPOSABLE_PERMIT_ISSUER}:
            raise TypeError("pre-open decision permits are issued by G4 authority")
        self._nonce = object()

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("PreOpenDecisionPublicationPermit cannot be subclassed")

    def __copy__(self) -> object:
        raise TypeError("pre-open decision permits cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("pre-open decision permits cannot be deep-copied")

    def __reduce__(self) -> object:
        raise TypeError("pre-open decision permits cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("pre-open decision permits cannot be pickled")

    def __getstate__(self) -> object:
        raise TypeError("pre-open decision permits cannot be serialized")

    def __repr__(self) -> str:
        return "PreOpenDecisionPublicationPermit(<sealed>)"


@dataclass(frozen=True, slots=True)
class _PermitEvidence:
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
    storage_read: PersonalDesktopUnattendedDecisionStorageReadResult
    intended_execution_session: TradingSession
    machine_authority_id: str
    approved_trading_sid: str
    authority_epoch_id: str
    observed_at: datetime
    production: bool
    consumed: bool = False


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedDecisionPublicationQualificationResult:
    status: PersonalDesktopUnattendedDecisionPublicationStatus
    diagnostic: PersonalDesktopUnattendedDecisionPublicationDiagnostic
    decision_id: UUID
    storage_classification: PersonalDesktopUnattendedDecisionStorageClassification
    output_capability_opened: bool = False
    filesystem_mutation_performed: bool = False

    def __post_init__(self) -> None:
        statuses = PersonalDesktopUnattendedDecisionPublicationStatus
        diagnostics = PersonalDesktopUnattendedDecisionPublicationDiagnostic
        expected = {
            statuses.DECISION_ALREADY_FINALIZED: diagnostics.FINALIZED_IDENTICAL,
            statuses.DECISION_READY: diagnostics.PRE_OPEN_READY,
            statuses.DECISION_READY_EFFECTS_DISABLED: (
                diagnostics.PUBLICATION_EFFECT_DISABLED
            ),
            statuses.MISSED_DECISION_DEADLINE: diagnostics.DEADLINE_REACHED,
            statuses.BLOCKED: diagnostics.STORAGE_NOT_SAFE,
        }.get(self.status)
        if (
            type(self.status) is not PersonalDesktopUnattendedDecisionPublicationStatus
            or type(self.diagnostic)
            is not PersonalDesktopUnattendedDecisionPublicationDiagnostic
            or self.diagnostic is not expected
            or type(self.decision_id) is not UUID
            or type(self.storage_classification)
            is not PersonalDesktopUnattendedDecisionStorageClassification
            or self.output_capability_opened is not False
            or self.filesystem_mutation_performed is not False
        ):
            raise ValueError("decision publication qualification result is invalid")


_REGISTRY: weakref.WeakKeyDictionary[
    PreOpenDecisionPublicationPermit, _PermitEvidence
] = weakref.WeakKeyDictionary()
_REGISTRY_LOCK = threading.Lock()


def issue_pre_open_decision_publication_permit(
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    storage_read: PersonalDesktopUnattendedDecisionStorageReadResult,
    authority: ValidatedProductionAuthority,
    intended_execution_session: TradingSession,
    observed_at: datetime,
) -> PreOpenDecisionPublicationPermit:
    """Issue one production permit from exact C1 and safe read provenance."""

    c1 = require_validated_production_authority(authority)
    verified_storage = (
        require_validated_personal_desktop_unattended_decision_storage_read(
            storage_read
        )
    )
    if (
        verified_storage.authority != c1
        or verified_storage.expected != expected
        or verified_storage.classification
        is not PersonalDesktopUnattendedDecisionStorageClassification.ABSENT
    ):
        raise PersonalDesktopUnattendedDecisionPublicationError(
            "decision publication storage/C1 provenance is inconsistent"
        )
    replayed = verify_personal_desktop_unattended_paper_decision_intent(
        expected.artifact_bytes,
        personal_desktop_unattended_decision_calendar(),
        expected_decision_id=expected.decision.decision_id,
        expected_artifact_sha256=expected.artifact_sha256,
        expected_artifact_byte_length=expected.artifact_byte_length,
    )
    if replayed != expected or (
        type(intended_execution_session) is not TradingSession
        or intended_execution_session != expected.decision.intended_execution_session
    ):
        raise PersonalDesktopUnattendedDecisionPublicationError(
            "decision or execution-session binding is inconsistent"
        )
    observed = _eligible_observation(intended_execution_session, observed_at)
    permit = PreOpenDecisionPublicationPermit(_issuer=_PERMIT_ISSUER)
    evidence = _PermitEvidence(
        expected,
        storage_read,
        intended_execution_session,
        c1.machine_authority_id,
        c1.approved_account_sid,
        c1.authority_epoch_id,
        observed,
        True,
    )
    with _REGISTRY_LOCK:
        _REGISTRY[permit] = evidence
    return permit


def require_pre_open_decision_publication_permit(
    permit: PreOpenDecisionPublicationPermit,
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    storage_read: PersonalDesktopUnattendedDecisionStorageReadResult,
    authority: ValidatedProductionAuthority,
) -> None:
    """Revalidate an unspent production permit without consuming it."""

    c1 = require_validated_production_authority(authority)
    _require_evidence(permit, expected, storage_read, c1, production=True)


def consume_pre_open_decision_publication_permit(
    permit: PreOpenDecisionPublicationPermit,
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    storage_read: PersonalDesktopUnattendedDecisionStorageReadResult,
    authority: ValidatedProductionAuthority,
) -> None:
    """Irrevocably spend one exact production permit before finalization."""

    c1 = require_validated_production_authority(authority)
    _consume(permit, expected, storage_read, c1, production=True)


def qualify_personal_desktop_unattended_decision_publication(
    authority: ValidatedProductionAuthority,
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    observed_at: datetime,
) -> PersonalDesktopUnattendedDecisionPublicationQualificationResult:
    """Classify production state read-only; never open an output capability."""

    decision_id = expected.decision.decision_id
    storage = read_personal_desktop_unattended_decision_storage(authority, expected)
    classification = storage.classification
    c = PersonalDesktopUnattendedDecisionStorageClassification
    statuses = PersonalDesktopUnattendedDecisionPublicationStatus
    diagnostics = PersonalDesktopUnattendedDecisionPublicationDiagnostic
    if classification is c.FINALIZED_IDENTICAL:
        status = statuses.DECISION_ALREADY_FINALIZED
        diagnostic = diagnostics.FINALIZED_IDENTICAL
    elif classification is not c.ABSENT:
        status = statuses.BLOCKED
        diagnostic = diagnostics.STORAGE_NOT_SAFE
    elif (
        classify_pre_open_decision_eligibility(
            expected.decision.intended_execution_session, observed_at
        )
        is PersonalDesktopPreOpenDecisionEligibility.MISSED_DEADLINE
    ):
        status = statuses.MISSED_DECISION_DEADLINE
        diagnostic = diagnostics.DEADLINE_REACHED
    elif PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED is False:
        status = statuses.DECISION_READY_EFFECTS_DISABLED
        diagnostic = diagnostics.PUBLICATION_EFFECT_DISABLED
    else:
        status = statuses.DECISION_READY
        diagnostic = diagnostics.PRE_OPEN_READY
    return PersonalDesktopUnattendedDecisionPublicationQualificationResult(
        status, diagnostic, decision_id, classification
    )


def issue_disposable_pre_open_decision_publication_permit_for_test(
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    storage_read: PersonalDesktopUnattendedDecisionStorageReadResult,
    intended_execution_session: TradingSession,
    observed_at: datetime,
    *,
    machine_authority_id: str = "disposable-machine",
    approved_trading_sid: str = "S-1-5-21-1-2-3-1009",
    authority_epoch_id: str = "disposable-epoch",
) -> PreOpenDecisionPublicationPermit:
    """Mint only disposable provenance for fake-native effect-path tests."""

    if (
        type(expected)
        is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
        or type(storage_read) is not PersonalDesktopUnattendedDecisionStorageReadResult
        or storage_read.classification
        is not PersonalDesktopUnattendedDecisionStorageClassification.ABSENT
        or storage_read.expected_decision_id != expected.decision.decision_id
        or intended_execution_session != expected.decision.intended_execution_session
        or any(
            type(value) is not str or not value
            for value in (
                machine_authority_id,
                approved_trading_sid,
                authority_epoch_id,
            )
        )
    ):
        raise PersonalDesktopUnattendedDecisionPublicationError(
            "disposable permit evidence is inconsistent"
        )
    observed = _eligible_observation(intended_execution_session, observed_at)
    permit = PreOpenDecisionPublicationPermit(_issuer=_DISPOSABLE_PERMIT_ISSUER)
    with _REGISTRY_LOCK:
        _REGISTRY[permit] = _PermitEvidence(
            expected,
            storage_read,
            intended_execution_session,
            machine_authority_id,
            approved_trading_sid,
            authority_epoch_id,
            observed,
            False,
        )
    return permit


def consume_disposable_pre_open_decision_publication_permit_for_test(
    permit: PreOpenDecisionPublicationPermit,
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    storage_read: PersonalDesktopUnattendedDecisionStorageReadResult,
) -> None:
    _consume(permit, expected, storage_read, None, production=False)


def _require_evidence(
    permit: PreOpenDecisionPublicationPermit,
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    storage_read: PersonalDesktopUnattendedDecisionStorageReadResult,
    authority: ValidatedProductionAuthority | None,
    *,
    production: bool,
) -> _PermitEvidence:
    if type(permit) is not PreOpenDecisionPublicationPermit:
        raise PersonalDesktopUnattendedDecisionPublicationError(
            "decision publication permit type is invalid"
        )
    with _REGISTRY_LOCK:
        evidence = _REGISTRY.get(permit)
    identity = (
        None
        if authority is None
        else (
            authority.machine_authority_id,
            authority.approved_account_sid,
            authority.authority_epoch_id,
        )
    )
    if (
        evidence is None
        or evidence.consumed
        or evidence.production is not production
        or evidence.expected != expected
        or evidence.storage_read is not storage_read
        or evidence.intended_execution_session
        != expected.decision.intended_execution_session
        or (
            production
            and identity
            != (
                evidence.machine_authority_id,
                evidence.approved_trading_sid,
                evidence.authority_epoch_id,
            )
        )
    ):
        raise PersonalDesktopUnattendedDecisionPublicationError(
            "decision publication permit provenance is invalid or consumed"
        )
    return evidence


def _consume(
    permit: PreOpenDecisionPublicationPermit,
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    storage_read: PersonalDesktopUnattendedDecisionStorageReadResult,
    authority: ValidatedProductionAuthority | None,
    *,
    production: bool,
) -> None:
    with _REGISTRY_LOCK:
        evidence = _REGISTRY.get(permit)
        identity = (
            None
            if authority is None
            else (
                authority.machine_authority_id,
                authority.approved_account_sid,
                authority.authority_epoch_id,
            )
        )
        if (
            evidence is None
            or evidence.consumed
            or evidence.production is not production
            or evidence.expected != expected
            or evidence.storage_read is not storage_read
            or (
                production
                and identity
                != (
                    evidence.machine_authority_id,
                    evidence.approved_trading_sid,
                    evidence.authority_epoch_id,
                )
            )
        ):
            raise PersonalDesktopUnattendedDecisionPublicationError(
                "decision publication permit provenance is invalid or consumed"
            )
        _REGISTRY[permit] = _PermitEvidence(
            evidence.expected,
            evidence.storage_read,
            evidence.intended_execution_session,
            evidence.machine_authority_id,
            evidence.approved_trading_sid,
            evidence.authority_epoch_id,
            evidence.observed_at,
            evidence.production,
            True,
        )


def _eligible_observation(session: TradingSession, observed_at: datetime) -> datetime:
    if (
        type(observed_at) is not datetime
        or observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise PersonalDesktopUnattendedDecisionPublicationError(
            "observed_at must be an exact timezone-aware datetime"
        )
    observed = observed_at.astimezone(UTC)
    if (
        classify_pre_open_decision_eligibility(session, observed)
        is not PersonalDesktopPreOpenDecisionEligibility.ELIGIBLE
    ):
        raise PersonalDesktopUnattendedDecisionPublicationError(
            "decision publication deadline has been reached"
        )
    return observed
