"""Effect-disabled Architecture 147 L43 ownership and continuity contracts.

This module is deliberately additive.  It does not open, create, append to, or
repair the consumed Q62 journal and it has no broker, provider, transport, or
credential dependency.  The contracts describe the facts a future protected
invocation must freshly establish; this source checkpoint can only produce a
readiness-for-review or a fail-closed/no-action result.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from trading_bot.live_prototype.alpaca_signal_inputs import SignalDecision
from trading_bot.live_prototype.durable_state import RuntimeIdentity

L43_SCHEMA = "arch147-l43-source-owner/v1"
L43_REVIEW_LABEL = "READY_FOR_L43_PROTECTED_EFFECT_REVIEW"
L43_ENTRY_LIMIT = Decimal("10.00")
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_LABEL = re.compile(r"[A-Za-z0-9_.-]{1,96}\Z")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


def _sha256(value: object, label: str) -> None:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _git_sha(value: object, label: str) -> None:
    if not isinstance(value, str) or _HEX40.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase Git SHA-1")


def _label(value: object, label: str) -> None:
    if not isinstance(value, str) or _LABEL.fullmatch(value) is None:
        raise ValueError(f"{label} must be a portable non-secret label")


def _code(value: object, label: str) -> None:
    if not isinstance(value, str) or _CODE.fullmatch(value) is None:
        raise ValueError(f"{label} must be a sanitized reason code")


def _decimal(value: object, label: str, *, positive: bool = False) -> None:
    if type(value) is not Decimal or not value.is_finite():
        raise TypeError(f"{label} must be a finite Decimal")
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{label} must be {'positive' if positive else 'nonnegative'}")


def _decimal_text(value: Decimal) -> str:
    _decimal(value, "decimal")
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class ContinuityStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    BLOCKED = "BLOCKED"


class L43Outcome(StrEnum):
    READY_FOR_L43_PROTECTED_EFFECT_REVIEW = L43_REVIEW_LABEL
    NO_ACTION_SIGNAL = "NO_ACTION_SIGNAL"
    MANUAL_CLOSE_REQUIRED = "MANUAL_CLOSE_REQUIRED"
    BLOCKED = "BLOCKED"


class L43Blocker(StrEnum):
    SOURCE_AUTHORITY_MISSING = "SOURCE_AUTHORITY_MISSING"
    SOURCE_LINEAGE_MISMATCH = "SOURCE_LINEAGE_MISMATCH"
    SOURCE_NOT_STRICT_DESCENDANT = "SOURCE_NOT_STRICT_DESCENDANT"
    FEATURE_AUTHORITY_FAILED = "FEATURE_AUTHORITY_FAILED"
    PROSPECTIVE_DEVELOP_AUTHORITY_FAILED = "PROSPECTIVE_DEVELOP_AUTHORITY_FAILED"
    PROVENANCE_MISMATCH = "PROVENANCE_MISMATCH"
    JOURNAL_READ_FAILED = "JOURNAL_READ_FAILED"
    JOURNAL_MUTATED = "JOURNAL_MUTATED"
    JOURNAL_IDENTITY_MISMATCH = "JOURNAL_IDENTITY_MISMATCH"
    JOURNAL_REINITIALIZED = "JOURNAL_REINITIALIZED"
    FRESH_FACTS_MISSING = "FRESH_FACTS_MISSING"
    ACCOUNT_MISMATCH = "ACCOUNT_MISMATCH"
    UNRESOLVED_EFFECT = "UNRESOLVED_EFFECT"
    RECOVERY_NOT_ACCEPTED = "RECOVERY_NOT_ACCEPTED"
    SESSION_NOT_PROVEN = "SESSION_NOT_PROVEN"
    SIGNAL_INPUTS_NOT_PROVEN = "SIGNAL_INPUTS_NOT_PROVEN"
    ENTRY_RISK_EXCEEDS_LIMIT = "ENTRY_RISK_EXCEEDS_LIMIT"
    ENTRY_ALREADY_CONSUMED = "ENTRY_ALREADY_CONSUMED"
    UNSANITIZED_EVIDENCE = "UNSANITIZED_EVIDENCE"


class ReviewOutcome(StrEnum):
    AFFIRMATIVE = "AFFIRMATIVE"
    REJECTED = "REJECTED"
    MALFORMED = "MALFORMED"
    UNKNOWN = "UNKNOWN"


class ReviewSemantics(StrEnum):
    NONPLACING_PREVIEW = "NONPLACING_PREVIEW"
    UNKNOWN = "UNKNOWN"


class SellOutcome(StrEnum):
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class EntryConsumptionFacts:
    """Pure one-entry invariant, including partial-fill consumption."""

    requested_dollars: Decimal
    confirmed_fill_quantity: Decimal
    reservation_consumed_dollars: Decimal
    entry_attempts: int
    restart_or_date_changed: bool = False

    def __post_init__(self) -> None:
        _decimal(self.requested_dollars, "requested entry dollars", positive=True)
        _decimal(self.confirmed_fill_quantity, "confirmed entry quantity")
        _decimal(
            self.reservation_consumed_dollars,
            "consumed entry dollars",
            positive=True,
        )
        if self.entry_attempts < 0:
            raise ValueError("entry attempts cannot be negative")


def entry_consumption_valid(facts: EntryConsumptionFacts) -> bool:
    """A partial fill owns only confirmed shares but consumes the full reservation."""

    return (
        facts.requested_dollars <= L43_ENTRY_LIMIT
        and facts.reservation_consumed_dollars == facts.requested_dollars
        and facts.entry_attempts == 1
        and facts.confirmed_fill_quantity >= 0
    )


@dataclass(frozen=True, slots=True)
class L43Provenance:
    """Immutable configuration/binding/account/strategy provenance."""

    config_digest: str
    binding_digest: str
    account_fingerprint: str
    strategy: str = "BASE_MA35_50_V1"
    symbol: str = "SPY"

    def __post_init__(self) -> None:
        _sha256(self.config_digest, "configuration digest")
        _sha256(self.binding_digest, "binding digest")
        _sha256(self.account_fingerprint, "account fingerprint")
        if self.strategy != "BASE_MA35_50_V1" or self.symbol != "SPY":
            raise ValueError("provenance is outside the bounded L43 product")

    def matches(self, identity: RuntimeIdentity) -> bool:
        return (
            self.config_digest == identity.config_digest
            and self.binding_digest == identity.binding_digest
            and self.account_fingerprint == identity.account_fingerprint
            and self.strategy == identity.strategy
            and self.symbol == identity.symbol
        )


@dataclass(frozen=True, slots=True)
class Q62JournalOrigin:
    """Immutable facts describing the consumed Q62 origin, not a new identity."""

    runtime_identity: RuntimeIdentity
    journal_label: str
    journal_sha256: str
    initialization_event_sha256: str
    consumed_observation_sha256: str
    initialization_sequence: int = 0
    lifecycle_state: str = "INITIALIZED"

    def __post_init__(self) -> None:
        _label(self.journal_label, "journal label")
        _sha256(self.journal_sha256, "journal digest")
        _sha256(self.initialization_event_sha256, "initialization event digest")
        _sha256(self.consumed_observation_sha256, "consumed observation digest")
        if self.initialization_sequence != 0 or self.lifecycle_state != "INITIALIZED":
            raise ValueError("Q62 origin must be the pristine initialized lifecycle")


@dataclass(frozen=True, slots=True)
class L43SourceIdentity:
    """The later executable source identity; never substituted into Q62 state."""

    source_head: str
    source_tree: str
    source_label: str = "L43"

    def __post_init__(self) -> None:
        _git_sha(self.source_head, "L43 source HEAD")
        _git_sha(self.source_tree, "L43 source tree")
        _label(self.source_label, "source label")


@dataclass(frozen=True, slots=True)
class SourceAuthorityEvidence:
    """Output of the current source-owned authority evaluator.

    The owner never accepts a caller-supplied ``accepted`` flag.  This record is
    obtained only by calling the injected evaluator seam below.
    """

    origin_head: str
    origin_tree: str
    candidate_head: str
    candidate_tree: str
    strict_descendant: bool
    feature_passed: bool
    prospective_develop_passed: bool
    evidence_sha256: str

    def __post_init__(self) -> None:
        _git_sha(self.origin_head, "authority origin HEAD")
        _git_sha(self.origin_tree, "authority origin tree")
        _git_sha(self.candidate_head, "authority candidate HEAD")
        _git_sha(self.candidate_tree, "authority candidate tree")
        _sha256(self.evidence_sha256, "authority evidence digest")

    @property
    def accepted(self) -> bool:
        return (
            self.strict_descendant
            and self.feature_passed
            and self.prospective_develop_passed
        )


@dataclass(frozen=True, slots=True)
class JournalReplayFacts:
    """Read/replay result for the original journal, with no write capability."""

    runtime_identity: RuntimeIdentity
    journal_sha256: str
    initialization_event_sha256: str
    consumed_observation_sha256: str
    initialization_sequence: int
    tail_sequence: int
    tail_sha256: str

    def __post_init__(self) -> None:
        _sha256(self.journal_sha256, "replayed journal digest")
        _sha256(self.initialization_event_sha256, "replayed initialization digest")
        _sha256(self.consumed_observation_sha256, "replayed observation digest")
        _sha256(self.tail_sha256, "replayed journal tail digest")
        if self.initialization_sequence != 0 or self.tail_sequence < 0:
            raise ValueError("journal sequence is invalid")


class SourceAuthorityVerifier(Protocol):
    """Source-owned current authority/evaluator seam; no provider capability."""

    def verify(
        self, origin: Q62JournalOrigin, current: L43SourceIdentity
    ) -> SourceAuthorityEvidence: ...


class JournalReplayReader(Protocol):
    """Read-only journal replay seam; it has no create or append operation."""

    def replay(self, origin: Q62JournalOrigin) -> JournalReplayFacts: ...


@dataclass(frozen=True, slots=True)
class L43ContinuityResult:
    status: ContinuityStatus
    origin: Q62JournalOrigin
    current: L43SourceIdentity
    provenance: L43Provenance
    blockers: tuple[L43Blocker, ...] = ()
    authority: SourceAuthorityEvidence | None = None
    journal: JournalReplayFacts | None = None

    @property
    def accepted(self) -> bool:
        return self.status is ContinuityStatus.ACCEPTED and not self.blockers

    def __post_init__(self) -> None:
        if not isinstance(self.status, ContinuityStatus):
            raise TypeError("continuity status must be typed")
        if self.status is ContinuityStatus.ACCEPTED and self.blockers:
            raise ValueError("accepted continuity cannot contain blockers")
        if self.status is ContinuityStatus.BLOCKED and not self.blockers:
            raise ValueError("blocked continuity requires a blocker")


def verify_l43_continuity(
    *,
    origin: Q62JournalOrigin,
    current: L43SourceIdentity,
    provenance: L43Provenance,
    authority_verifier: SourceAuthorityVerifier,
    journal_reader: JournalReplayReader,
) -> L43ContinuityResult:
    """Prove additive source continuity without opening the journal as L43 state."""

    blockers: list[L43Blocker] = []
    authority: SourceAuthorityEvidence | None = None
    journal: JournalReplayFacts | None = None
    if (
        current.source_head == origin.runtime_identity.source_head
        and current.source_tree == origin.runtime_identity.source_tree
    ):
        blockers.append(L43Blocker.SOURCE_LINEAGE_MISMATCH)
    if not provenance.matches(origin.runtime_identity):
        blockers.append(L43Blocker.PROVENANCE_MISMATCH)
    try:
        authority = authority_verifier.verify(origin, current)
    except Exception:
        blockers.append(L43Blocker.SOURCE_AUTHORITY_MISSING)
    if authority is None:
        blockers.append(L43Blocker.SOURCE_AUTHORITY_MISSING)
    else:
        if (
            authority.origin_head != origin.runtime_identity.source_head
            or authority.origin_tree != origin.runtime_identity.source_tree
            or authority.candidate_head != current.source_head
            or authority.candidate_tree != current.source_tree
        ):
            blockers.append(L43Blocker.SOURCE_LINEAGE_MISMATCH)
        if not authority.strict_descendant:
            blockers.append(L43Blocker.SOURCE_NOT_STRICT_DESCENDANT)
        if not authority.feature_passed:
            blockers.append(L43Blocker.FEATURE_AUTHORITY_FAILED)
        if not authority.prospective_develop_passed:
            blockers.append(L43Blocker.PROSPECTIVE_DEVELOP_AUTHORITY_FAILED)
    try:
        journal = journal_reader.replay(origin)
    except Exception:
        blockers.append(L43Blocker.JOURNAL_READ_FAILED)
    if journal is None:
        blockers.append(L43Blocker.JOURNAL_READ_FAILED)
    else:
        if journal.runtime_identity != origin.runtime_identity:
            blockers.append(L43Blocker.JOURNAL_IDENTITY_MISMATCH)
        if (
            journal.journal_sha256 != origin.journal_sha256
            or journal.initialization_event_sha256 != origin.initialization_event_sha256
            or journal.consumed_observation_sha256 != origin.consumed_observation_sha256
            or journal.initialization_sequence != origin.initialization_sequence
            or journal.tail_sequence != origin.initialization_sequence
            or journal.tail_sha256 != origin.initialization_event_sha256
        ):
            blockers.append(L43Blocker.JOURNAL_MUTATED)
    unique = tuple(dict.fromkeys(blockers))
    return L43ContinuityResult(
        status=ContinuityStatus.BLOCKED if unique else ContinuityStatus.ACCEPTED,
        origin=origin,
        current=current,
        provenance=provenance,
        blockers=unique,
        authority=authority,
        journal=journal,
    )


@dataclass(frozen=True, slots=True)
class XnysSessionFacts:
    target_session: str
    regular_hours: bool
    session_open: bool
    authority_digest: str

    def __post_init__(self) -> None:
        if _DATE.fullmatch(self.target_session) is None:
            raise ValueError("target session must be an ISO date")
        _sha256(self.authority_digest, "session authority digest")

    @property
    def proven(self) -> bool:
        return self.regular_hours and self.session_open


@dataclass(frozen=True, slots=True)
class D34SignalFacts:
    decision: SignalDecision
    inputs_digest: str
    completed_sessions: int = 60
    price_basis: str = "ALPACA_ALL_ADJUSTED_PRICE_V1"

    def __post_init__(self) -> None:
        if not isinstance(self.decision, SignalDecision):
            raise TypeError("signal decision must be SignalDecision")
        _sha256(self.inputs_digest, "signal inputs digest")
        if self.completed_sessions != 60:
            raise ValueError("L43 requires exactly 60 completed D34 sessions")
        if self.price_basis != "ALPACA_ALL_ADJUSTED_PRICE_V1":
            raise ValueError("unsupported D34 price basis")


@dataclass(frozen=True, slots=True)
class RecoveryFacts:
    reconciled: bool
    unresolved_effects: bool
    terminal_entry: bool
    exact_owned_remainder: Decimal
    evidence_digest: str

    def __post_init__(self) -> None:
        _decimal(self.exact_owned_remainder, "exact owned remainder")
        _sha256(self.evidence_digest, "recovery evidence digest")


@dataclass(frozen=True, slots=True)
class L43FreshEffectFacts:
    """Typed future facts; this checkpoint never obtains them from a provider."""

    provenance: L43Provenance
    retained_account_fingerprint: str
    current_account_fingerprint: str
    positions_digest: str
    relevant_orders_digest: str
    entry_consumed: bool
    session: XnysSessionFacts
    signal: D34SignalFacts
    recovery: RecoveryFacts
    requested_entry_risk: Decimal
    continuity: L43ContinuityResult
    fresh: bool = True

    def __post_init__(self) -> None:
        _sha256(self.retained_account_fingerprint, "retained account fingerprint")
        _sha256(self.current_account_fingerprint, "current account fingerprint")
        _sha256(self.positions_digest, "positions digest")
        _sha256(self.relevant_orders_digest, "relevant orders digest")
        _decimal(self.requested_entry_risk, "requested entry risk")


@dataclass(frozen=True, slots=True)
class L43Assessment:
    outcome: L43Outcome
    blockers: tuple[L43Blocker, ...] = ()
    evidence: tuple[tuple[str, str], ...] = ()
    entry_intent_count: int = 0
    review_count: int = 0
    placement_count: int = 0
    cancellation_count: int = 0
    provider_mutation_count: int = 0
    placement_authority: bool = False
    trade_authority: bool = False
    live_ready: bool = False

    def __post_init__(self) -> None:
        if any(
            value != 0
            for value in (
                self.entry_intent_count,
                self.review_count,
                self.placement_count,
                self.cancellation_count,
                self.provider_mutation_count,
            )
        ):
            raise ValueError("L43 source owner cannot report provider activity")
        if self.placement_authority or self.trade_authority or self.live_ready:
            raise ValueError("L43 source owner cannot grant effect authority")


_EVIDENCE_KEYS = frozenset(
    {
        "label",
        "outcome",
        "source_head",
        "source_tree",
        "config_digest",
        "binding_digest",
        "account_fingerprint_digest",
        "journal_digest",
        "signal_inputs_digest",
        "positions_digest",
        "orders_digest",
        "reason",
    }
)


def sanitize_evidence(values: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    """Return only canonical safe evidence fields; reject raw provider material."""

    if not isinstance(values, Mapping):
        raise TypeError("evidence must be a mapping")
    clean: list[tuple[str, str]] = []
    for key, value in values.items():
        if key not in _EVIDENCE_KEYS or not isinstance(value, str):
            raise ValueError("evidence contains an unsupported or non-text field")
        if any(
            token in key.casefold()
            for token in (
                "token",
                "secret",
                "url",
                "path",
                "order_id",
                "account_number",
                "exception",
            )
        ):
            raise ValueError("evidence contains a sensitive field")
        if "://" in value or "\\" in value or "\n" in value or "\r" in value:
            raise ValueError("evidence contains a raw path, URL, or multiline value")
        if key.endswith("_digest") or key in {"source_head", "source_tree"}:
            (_sha256(value, key) if key.endswith("_digest") else _git_sha(value, key))
        elif key == "reason":
            _code(value, key)
        else:
            _label(value, key)
        clean.append((key, value))
    return tuple(sorted(clean))


@dataclass(frozen=True, slots=True)
class ExactOwnedSellFacts:
    bot_owned_remainder: Decimal
    proposed_quantity: Decimal
    broker_position: Decimal
    sellable_quantity: Decimal
    entry_terminal: bool
    review_arguments_digest: str
    placement_arguments_digest: str

    def __post_init__(self) -> None:
        for label, value in (
            ("bot-owned remainder", self.bot_owned_remainder),
            ("proposed quantity", self.proposed_quantity),
            ("broker position", self.broker_position),
            ("sellable quantity", self.sellable_quantity),
        ):
            _decimal(value, label)
        _sha256(self.review_arguments_digest, "review arguments digest")
        _sha256(self.placement_arguments_digest, "placement arguments digest")


def exact_owned_sell_qualified(facts: ExactOwnedSellFacts) -> bool:
    """Pure exact-owned guard with no rounding or manual-share adoption."""

    return (
        facts.entry_terminal
        and facts.bot_owned_remainder > 0
        and facts.proposed_quantity == facts.bot_owned_remainder
        and facts.proposed_quantity <= facts.broker_position
        and facts.proposed_quantity <= facts.sellable_quantity
        and facts.review_arguments_digest == facts.placement_arguments_digest
    )


@dataclass(frozen=True, slots=True)
class NormalizedReviewFacts:
    outcome: ReviewOutcome
    semantics: ReviewSemantics
    review_arguments_digest: str
    placement_arguments_digest: str
    warnings: tuple[str, ...] = ()
    unknown_fields: tuple[str, ...] = ()
    provider_order_id_present: bool = False

    def __post_init__(self) -> None:
        _sha256(self.review_arguments_digest, "review arguments digest")
        _sha256(self.placement_arguments_digest, "placement arguments digest")
        for value in self.warnings + self.unknown_fields:
            _code(value, "review warning/unknown field")


@dataclass(frozen=True, slots=True)
class ReviewValidation:
    accepted_for_prospective_contract: bool
    manual_close_required: bool
    blockers: tuple[str, ...] = ()
    placement_authority: bool = False


def validate_l43_sell_review(facts: NormalizedReviewFacts) -> ReviewValidation:
    blockers: list[str] = []
    if facts.outcome is not ReviewOutcome.AFFIRMATIVE:
        blockers.append("NON_AFFIRMATIVE_OUTCOME")
    if facts.semantics is not ReviewSemantics.NONPLACING_PREVIEW:
        blockers.append("NOT_NONPLACING_PREVIEW")
    if facts.review_arguments_digest != facts.placement_arguments_digest:
        blockers.append("REVIEW_ARGUMENTS_MISMATCH")
    if facts.warnings:
        blockers.append("WARNINGS_PRESENT")
    if facts.unknown_fields:
        blockers.append("UNKNOWN_FIELDS_PRESENT")
    if facts.provider_order_id_present:
        blockers.append("PROVIDER_ORDER_ID_PRESENT")
    unique = tuple(dict.fromkeys(blockers))
    return ReviewValidation(
        accepted_for_prospective_contract=not unique,
        manual_close_required=bool(unique),
        blockers=unique,
    )


def sell_outcome_requires_manual_close(outcome: SellOutcome) -> bool:
    if not isinstance(outcome, SellOutcome):
        raise TypeError("sell outcome must be typed")
    return outcome is not SellOutcome.FILLED


@dataclass(frozen=True, slots=True)
class FutureInvocationOrdering:
    """Source-only proof shape for MAY_HAVE_OCCURRED-before-provider ordering."""

    durable_transition: str
    provider_call_requested: bool = False

    def __post_init__(self) -> None:
        _code(self.durable_transition, "durable transition")
        if self.provider_call_requested:
            raise ValueError("effect-disabled L43 cannot request a provider call")

    @property
    def provider_call_allowed(self) -> bool:
        return False


class L43ProductionOwner:
    """Dedicated source owner with no provider, transport, or mutation surface."""

    __slots__ = ("_authority_verifier", "_journal_reader")

    def __init__(
        self,
        *,
        authority_verifier: SourceAuthorityVerifier,
        journal_reader: JournalReplayReader,
    ) -> None:
        self._authority_verifier = authority_verifier
        self._journal_reader = journal_reader

    def prove_continuity(
        self,
        *,
        origin: Q62JournalOrigin,
        current: L43SourceIdentity,
        provenance: L43Provenance,
    ) -> L43ContinuityResult:
        return verify_l43_continuity(
            origin=origin,
            current=current,
            provenance=provenance,
            authority_verifier=self._authority_verifier,
            journal_reader=self._journal_reader,
        )

    def assess(
        self,
        *,
        origin: Q62JournalOrigin,
        current: L43SourceIdentity,
        facts: L43FreshEffectFacts,
    ) -> L43Assessment:
        continuity = self.prove_continuity(
            origin=origin,
            current=current,
            provenance=facts.provenance,
        )
        if not continuity.accepted:
            return self._assessment(
                L43Outcome.BLOCKED,
                continuity.blockers,
                continuity,
            )
        blockers: list[L43Blocker] = []
        if facts.continuity != continuity:
            blockers.append(L43Blocker.FRESH_FACTS_MISSING)
        if not facts.fresh:
            blockers.append(L43Blocker.FRESH_FACTS_MISSING)
        if (
            facts.retained_account_fingerprint != facts.provenance.account_fingerprint
            or facts.current_account_fingerprint != facts.provenance.account_fingerprint
        ):
            blockers.append(L43Blocker.ACCOUNT_MISMATCH)
        if not facts.session.proven:
            blockers.append(L43Blocker.SESSION_NOT_PROVEN)
        if facts.signal.completed_sessions != 60:
            blockers.append(L43Blocker.SIGNAL_INPUTS_NOT_PROVEN)
        if facts.recovery.unresolved_effects:
            blockers.append(L43Blocker.UNRESOLVED_EFFECT)
        if not facts.recovery.reconciled:
            blockers.append(L43Blocker.RECOVERY_NOT_ACCEPTED)
        if blockers:
            return self._assessment(
                L43Outcome.BLOCKED, tuple(dict.fromkeys(blockers)), continuity
            )
        if facts.signal.decision is not SignalDecision.BUY:
            return self._assessment(L43Outcome.NO_ACTION_SIGNAL, (), continuity)
        if (
            facts.requested_entry_risk <= 0
            or facts.requested_entry_risk > L43_ENTRY_LIMIT
        ):
            return self._assessment(
                L43Outcome.BLOCKED, (L43Blocker.ENTRY_RISK_EXCEEDS_LIMIT,), continuity
            )
        if facts.entry_consumed:
            return self._assessment(
                L43Outcome.BLOCKED, (L43Blocker.ENTRY_ALREADY_CONSUMED,), continuity
            )
        return self._assessment(
            L43Outcome.READY_FOR_L43_PROTECTED_EFFECT_REVIEW,
            (),
            continuity,
        )

    @staticmethod
    def _assessment(
        outcome: L43Outcome,
        blockers: tuple[L43Blocker, ...],
        continuity: L43ContinuityResult,
    ) -> L43Assessment:
        evidence = sanitize_evidence(
            {
                "label": L43_REVIEW_LABEL,
                "outcome": outcome.value,
                "source_head": continuity.current.source_head,
                "source_tree": continuity.current.source_tree,
                "config_digest": continuity.provenance.config_digest,
                "binding_digest": continuity.provenance.binding_digest,
                "account_fingerprint_digest": continuity.provenance.account_fingerprint,
                "journal_digest": continuity.origin.journal_sha256,
                "reason": (blockers[0].value if blockers else "SOURCE_ONLY"),
            }
        )
        return L43Assessment(outcome=outcome, blockers=blockers, evidence=evidence)


__all__ = [
    "D34SignalFacts",
    "ContinuityStatus",
    "EntryConsumptionFacts",
    "ExactOwnedSellFacts",
    "FutureInvocationOrdering",
    "JournalReplayFacts",
    "JournalReplayReader",
    "L43Assessment",
    "L43Blocker",
    "L43ContinuityResult",
    "L43FreshEffectFacts",
    "L43Outcome",
    "L43ProductionOwner",
    "L43Provenance",
    "L43SourceIdentity",
    "L43_REVIEW_LABEL",
    "NormalizedReviewFacts",
    "Q62JournalOrigin",
    "RecoveryFacts",
    "ReviewOutcome",
    "ReviewSemantics",
    "ReviewValidation",
    "SellOutcome",
    "SourceAuthorityEvidence",
    "SourceAuthorityVerifier",
    "XnysSessionFacts",
    "exact_owned_sell_qualified",
    "entry_consumption_valid",
    "sanitize_evidence",
    "sell_outcome_requires_manual_close",
    "validate_l43_sell_review",
    "verify_l43_continuity",
]
