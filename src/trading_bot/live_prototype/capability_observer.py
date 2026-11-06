"""Typed, effect-disabled L41 capability evidence and classification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Z][A-Z0-9_]{1,63}\Z")


class FactId(StrEnum):
    INTENDED_AGENTIC_ACCOUNT = "INTENDED_AGENTIC_ACCOUNT"
    SPY_TRADABILITY = "SPY_TRADABILITY"
    FRACTIONAL_ELIGIBILITY = "FRACTIONAL_ELIGIBILITY"
    SELL_QUANTITY_FIELD = "SELL_QUANTITY_FIELD"
    DECIMAL_INTERFACE_PRECISION = "DECIMAL_INTERFACE_PRECISION"
    QUANTITY_INCREMENT = "QUANTITY_INCREMENT"
    MINIMUM_QUANTITY = "MINIMUM_QUANTITY"
    MAXIMUM_QUANTITY_OR_ABSENCE = "MAXIMUM_QUANTITY_OR_ABSENCE"
    MINIMUM_SELL_NOTIONAL_OR_ABSENCE = "MINIMUM_SELL_NOTIONAL_OR_ABSENCE"
    BELOW_MINIMUM_FULL_CLOSE = "BELOW_MINIMUM_FULL_CLOSE"
    RESIDUAL_FULL_OWNED_CLOSE = "RESIDUAL_FULL_OWNED_CLOSE"
    REVIEW_PREVIEW_ONLY = "REVIEW_PREVIEW_ONLY"
    INSTANCE_REVIEW_REQUIRES_POSITION = "INSTANCE_REVIEW_REQUIRES_POSITION"


class Classification(StrEnum):
    PROVEN = "PROVEN"
    BLOCKING_L42 = "BLOCKING_L42"
    DEFER_TO_FIRST_OWNED_POSITION = "DEFER_TO_FIRST_OWNED_POSITION"


class OverallStatus(StrEnum):
    READY_FOR_L42 = "READY_FOR_L42"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"


_RULE_FACTS = frozenset(
    {
        FactId.QUANTITY_INCREMENT,
        FactId.MINIMUM_QUANTITY,
        FactId.MAXIMUM_QUANTITY_OR_ABSENCE,
        FactId.MINIMUM_SELL_NOTIONAL_OR_ABSENCE,
        FactId.BELOW_MINIMUM_FULL_CLOSE,
        FactId.RESIDUAL_FULL_OWNED_CLOSE,
    }
)


@dataclass(frozen=True, slots=True)
class OfficialRuleProvenance:
    """Descriptive metadata; dates and digests do not independently accept a rule."""

    source_identifier: str
    canonical_url_or_document_id: str
    retrieved_on: date | None
    accepted_on: date | None
    content_sha256: str
    semantic_claim_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_identifier or len(self.source_identifier) > 128:
            raise ValueError("L41_RULE_SOURCE_INVALID")
        if (
            not self.canonical_url_or_document_id
            or len(self.canonical_url_or_document_id) > 256
        ):
            raise ValueError("L41_RULE_DOCUMENT_INVALID")
        if self.retrieved_on is None and self.accepted_on is None:
            raise ValueError("L41_RULE_DATE_REQUIRED")
        if any(
            value is not None and type(value) is not date
            for value in (self.retrieved_on, self.accepted_on)
        ):
            raise TypeError("L41_RULE_DATE_INVALID")
        if _SHA256.fullmatch(self.content_sha256) is None:
            raise ValueError("L41_RULE_DIGEST_INVALID")
        if (
            type(self.semantic_claim_ids) is not tuple
            or not self.semantic_claim_ids
            or any(_ID.fullmatch(value) is None for value in self.semantic_claim_ids)
            or len(set(self.semantic_claim_ids)) != len(self.semantic_claim_ids)
        ):
            raise ValueError("L41_RULE_CLAIMS_INVALID")


@dataclass(frozen=True, slots=True)
class RuleClaim:
    """A non-boolean value tied to the exact official claim provenance."""

    fact_id: FactId
    value: str
    provenance: OfficialRuleProvenance

    def __post_init__(self) -> None:
        if not isinstance(self.fact_id, FactId) or self.fact_id not in _RULE_FACTS:
            raise ValueError("L41_RULE_FACT_INVALID")
        if type(self.value) is not str or not self.value or len(self.value) > 128:
            raise ValueError("L41_RULE_VALUE_INVALID")
        if type(self.provenance) is not OfficialRuleProvenance:
            raise TypeError("L41_RULE_PROVENANCE_INVALID")
        if self.fact_id.value not in self.provenance.semantic_claim_ids:
            raise ValueError("L41_RULE_CLAIM_NOT_IN_PROVENANCE")


@dataclass(frozen=True, slots=True)
class InterfaceClaims:
    """Interface-only metadata; it cannot prove account or order capability."""

    review_quantity_field: str | None
    place_quantity_field: str | None
    decimal_places: int | None
    review_semantics: str | None
    provenance: OfficialRuleProvenance | None

    def __post_init__(self) -> None:
        for value in (
            self.review_quantity_field,
            self.place_quantity_field,
            self.review_semantics,
        ):
            if value is not None and type(value) is not str:
                raise TypeError("L41_INTERFACE_CLAIM_INVALID")
        if self.decimal_places is not None and type(self.decimal_places) is not int:
            raise TypeError("L41_INTERFACE_PRECISION_INVALID")
        if (
            self.provenance is not None
            and type(self.provenance) is not OfficialRuleProvenance
        ):
            raise TypeError("L41_INTERFACE_PROVENANCE_INVALID")


@dataclass(frozen=True, slots=True)
class CapabilityEvidence:
    """Sanitized, typed observations emitted by the separately guarded collector."""

    observation_sha256: str | None
    account_fingerprint: str | None
    agentic_account_count: int | None
    account_is_active: str | None
    account_type: str | None
    spy_account_type_tradability: str | None
    spy_fractional_tradability: str | None
    interface: InterfaceClaims | None
    official_rule_claims: tuple[RuleClaim, ...] = ()

    def __post_init__(self) -> None:
        for value in (self.observation_sha256, self.account_fingerprint):
            if value is not None and _SHA256.fullmatch(value) is None:
                raise ValueError("L41_EVIDENCE_DIGEST_INVALID")
        if self.agentic_account_count is not None and (
            type(self.agentic_account_count) is not int
            or self.agentic_account_count < 0
        ):
            raise ValueError("L41_ACCOUNT_COUNT_INVALID")
        if self.account_is_active not in {None, "ACTIVE", "INACTIVE", "UNKNOWN"}:
            raise ValueError("L41_ACCOUNT_STATE_INVALID")
        if self.account_type is not None and (
            type(self.account_type) is not str
            or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", self.account_type) is None
        ):
            raise ValueError("L41_ACCOUNT_TYPE_INVALID")
        if self.spy_account_type_tradability not in {
            None,
            "TRADABLE",
            "UNTRADABLE",
            "POSITION_CLOSING_ONLY",
            "UNKNOWN",
        }:
            raise ValueError("L41_SPY_TRADABILITY_INVALID")
        if self.spy_fractional_tradability not in {
            None,
            "TRADABLE",
            "UNTRADABLE",
            "UNKNOWN",
        }:
            raise ValueError("L41_FRACTIONAL_TRADABILITY_INVALID")
        if self.interface is not None and type(self.interface) is not InterfaceClaims:
            raise TypeError("L41_INTERFACE_CLAIMS_INVALID")
        if type(self.official_rule_claims) is not tuple or any(
            type(claim) is not RuleClaim for claim in self.official_rule_claims
        ):
            raise TypeError("L41_RULE_CLAIMS_INVALID")
        if len({claim.fact_id for claim in self.official_rule_claims}) != len(
            self.official_rule_claims
        ):
            raise ValueError("L41_RULE_CLAIM_DUPLICATE")


@dataclass(frozen=True, slots=True)
class FactResult:
    fact_id: FactId
    classification: Classification
    rationale_code: str
    evidence_sha256: str | None = None
    provenance: OfficialRuleProvenance | None = None
    submitted_rule_value: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.fact_id, FactId) or not isinstance(
            self.classification, Classification
        ):
            raise TypeError("L41_FACT_RESULT_INVALID")
        if _ID.fullmatch(self.rationale_code) is None:
            raise ValueError("L41_FACT_RATIONALE_INVALID")
        if (
            self.evidence_sha256 is not None
            and _SHA256.fullmatch(self.evidence_sha256) is None
        ):
            raise ValueError("L41_FACT_DIGEST_INVALID")
        if (
            self.provenance is not None
            and type(self.provenance) is not OfficialRuleProvenance
        ):
            raise TypeError("L41_FACT_PROVENANCE_INVALID")
        if self.submitted_rule_value is not None and (
            type(self.submitted_rule_value) is not str
            or len(self.submitted_rule_value) > 128
        ):
            raise ValueError("L41_RULE_VALUE_INVALID")


@dataclass(frozen=True, slots=True)
class CapabilityReport:
    status: OverallStatus
    facts: tuple[FactResult, ...]
    account_fingerprint: str | None
    account_type: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, OverallStatus):
            raise TypeError("L41_REPORT_STATUS_INVALID")
        if type(self.facts) is not tuple or any(
            type(item) is not FactResult for item in self.facts
        ):
            raise TypeError("L41_REPORT_FACTS_INVALID")
        if tuple(item.fact_id for item in self.facts) != tuple(FactId):
            raise ValueError("L41_FACT_INVENTORY_MISMATCH")
        if (
            self.account_fingerprint is not None
            and _SHA256.fullmatch(self.account_fingerprint) is None
        ):
            raise ValueError("L41_ACCOUNT_FINGERPRINT_INVALID")
        if self.status is OverallStatus.READY_FOR_L42 and any(
            item.classification is Classification.BLOCKING_L42 for item in self.facts
        ):
            raise ValueError("L41_READY_WITH_BLOCKER")


def classify_capabilities(evidence: CapabilityEvidence | None) -> CapabilityReport:
    """Classify observations; submitted official rules remain unaccepted blockers."""
    if evidence is None or evidence.observation_sha256 is None:
        return _report(OverallStatus.NOT_RUN, _blocking_inventory(), None, None)

    rule_claims = {claim.fact_id: claim for claim in evidence.official_rule_claims}
    results: dict[FactId, FactResult] = {}
    account_proven = (
        evidence.account_fingerprint is not None
        and evidence.agentic_account_count == 1
        and evidence.account_is_active == "ACTIVE"
        and evidence.account_type is not None
    )
    _put(
        results,
        FactId.INTENDED_AGENTIC_ACCOUNT,
        account_proven,
        "ACCOUNT_IDENTITY_PROVEN",
        evidence,
    )
    _put(
        results,
        FactId.SPY_TRADABILITY,
        account_proven and evidence.spy_account_type_tradability == "TRADABLE",
        "SPY_TRADABILITY_PROVEN",
        evidence,
    )
    _put(
        results,
        FactId.FRACTIONAL_ELIGIBILITY,
        account_proven and evidence.spy_fractional_tradability == "TRADABLE",
        "SPY_FRACTIONAL_ELIGIBILITY_PROVEN",
        evidence,
    )

    interface = evidence.interface
    provenance = None if interface is None else interface.provenance
    schema_claims = () if provenance is None else provenance.semantic_claim_ids
    _put(
        results,
        FactId.SELL_QUANTITY_FIELD,
        interface is not None
        and interface.review_quantity_field == "quantity"
        and interface.place_quantity_field == "quantity"
        and provenance is not None
        and FactId.SELL_QUANTITY_FIELD.value in schema_claims,
        "SELL_QUANTITY_INTERFACE_PROVEN",
        evidence,
        provenance,
    )
    _put(
        results,
        FactId.DECIMAL_INTERFACE_PRECISION,
        interface is not None
        and type(interface.decimal_places) is int
        and interface.decimal_places == 6
        and provenance is not None
        and FactId.DECIMAL_INTERFACE_PRECISION.value in schema_claims,
        "SIX_DECIMAL_INTERFACE_BOUND_PROVEN",
        evidence,
        provenance,
    )

    for fact_id in _RULE_FACTS:
        claim = rule_claims.get(fact_id)
        _put(
            results,
            fact_id,
            False,
            "OFFICIAL_RULE_SUBMITTED_UNACCEPTED"
            if claim is not None
            else "OFFICIAL_RULE_UNPROVEN",
            evidence,
            None if claim is None else claim.provenance,
            None if claim is None else claim.value,
        )

    _put(
        results,
        FactId.REVIEW_PREVIEW_ONLY,
        interface is not None
        and interface.review_semantics == "SIMULATE_WITHOUT_PLACING"
        and provenance is not None
        and FactId.REVIEW_PREVIEW_ONLY.value in schema_claims,
        "REVIEW_PREVIEW_SEMANTICS_PROVEN",
        evidence,
        provenance,
    )
    results[FactId.INSTANCE_REVIEW_REQUIRES_POSITION] = FactResult(
        FactId.INSTANCE_REVIEW_REQUIRES_POSITION,
        Classification.DEFER_TO_FIRST_OWNED_POSITION,
        "EXACT_OWNED_POSITION_REVIEW_DEFERRED",
        evidence.observation_sha256,
    )
    facts = tuple(results[fact_id] for fact_id in FactId)
    status = (
        OverallStatus.BLOCKED
        if any(item.classification is Classification.BLOCKING_L42 for item in facts)
        else OverallStatus.READY_FOR_L42
    )
    return _report(status, facts, evidence.account_fingerprint, evidence.account_type)


def _put(
    results: dict[FactId, FactResult],
    fact_id: FactId,
    proven: bool,
    rationale: str,
    evidence: CapabilityEvidence,
    provenance: OfficialRuleProvenance | None = None,
    submitted_rule_value: str | None = None,
) -> None:
    results[fact_id] = FactResult(
        fact_id,
        Classification.PROVEN if proven else Classification.BLOCKING_L42,
        rationale
        if proven or not rationale.endswith("_PROVEN")
        else f"{rationale[:-7]}_UNPROVEN",
        evidence.observation_sha256,
        provenance,
        submitted_rule_value,
    )


def _blocking_inventory() -> tuple[FactResult, ...]:
    return tuple(
        FactResult(
            fact_id,
            Classification.DEFER_TO_FIRST_OWNED_POSITION
            if fact_id is FactId.INSTANCE_REVIEW_REQUIRES_POSITION
            else Classification.BLOCKING_L42,
            "NOT_OBSERVED",
        )
        for fact_id in FactId
    )


def _report(
    status: OverallStatus,
    facts: tuple[FactResult, ...],
    fingerprint: str | None,
    account_type: str | None,
) -> CapabilityReport:
    return CapabilityReport(status, facts, fingerprint, account_type)
