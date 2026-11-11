"""Pure L41R6 composition of consumed account, interface, and public-rule evidence.

Callers supply the two preserved observation byte strings. Source-owned parsers
and the canonical official-rule resolver validate their identities. This module
performs no file, network, provider, OAuth, MCP, or broker operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from trading_bot.live_prototype.capability_observer import (
    CapabilityReport,
    Classification,
    FactId,
    FactResult,
    OverallStatus,
)
from trading_bot.live_prototype.consumed_l41_evidence import (
    ConsumedL41Predecessor,
    parse_consumed_l41_bytes,
)
from trading_bot.live_prototype.consumed_l41r5_evidence import (
    ConsumedL41R5InterfaceProvenance,
    L41R5ToolInterface,
    parse_consumed_l41r5_bytes,
)
from trading_bot.live_prototype.official_rule_binding import (
    AuthenticatedOfficialSourceProvenance,
    OfficialClaimId,
    TrustedOfficialClaim,
    accepted_official_rule_binding_v2,
    resolve_trusted_official_claim_v2,
)

_CLAIM_FACTS: Final[tuple[tuple[FactId, OfficialClaimId], ...]] = (
    (
        FactId.MINIMUM_SELL_NOTIONAL_OR_ABSENCE,
        OfficialClaimId.ORDINARY_FRACTIONAL_TRANSACTION_MINIMUM_USD_1,
    ),
    (
        FactId.REVIEW_PREVIEW_ONLY,
        OfficialClaimId.REVIEW_EQUITY_ORDER_SIMULATION_PRETRADE_WARNINGS,
    ),
)
_ORDER_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    {"place_equity_order", "review_equity_order"}
)
_L41R6_DECISIONS: Final[dict[FactId, tuple[Classification, str, str | None]]] = {
    FactId.SELL_QUANTITY_FIELD: (
        Classification.PROVEN,
        "L41R6_SELL_QUANTITY_INTERFACE_PROVEN",
        "INTERFACE",
    ),
    FactId.DECIMAL_INTERFACE_PRECISION: (
        Classification.PROVEN,
        "L41R6_ADVERTISED_SIX_DECIMAL_BOUND_PROVEN",
        "INTERFACE",
    ),
    FactId.QUANTITY_INCREMENT: (
        Classification.BLOCKING_L42,
        "L41R6_QUANTITY_INCREMENT_UNSUPPORTED",
        None,
    ),
    FactId.MINIMUM_QUANTITY: (
        Classification.BLOCKING_L42,
        "L41R6_MINIMUM_QUANTITY_UNSUPPORTED",
        None,
    ),
    FactId.MAXIMUM_QUANTITY_OR_ABSENCE: (
        Classification.BLOCKING_L42,
        "L41R6_MAXIMUM_QUANTITY_UNSUPPORTED",
        None,
    ),
    FactId.MINIMUM_SELL_NOTIONAL_OR_ABSENCE: (
        Classification.PROVEN,
        "L41R6_ORDINARY_MINIMUM_USD_1_PROVEN",
        None,
    ),
    FactId.BELOW_MINIMUM_FULL_CLOSE: (
        Classification.BLOCKING_L42,
        "L41R6_BELOW_MINIMUM_CLOSE_UNSUPPORTED",
        None,
    ),
    FactId.RESIDUAL_FULL_OWNED_CLOSE: (
        Classification.BLOCKING_L42,
        "L41R6_RESIDUAL_CLOSE_UNSUPPORTED",
        None,
    ),
    FactId.REVIEW_PREVIEW_ONLY: (
        Classification.PROVEN,
        "L41R6_OFFICIAL_REVIEW_PREVIEW_PROVEN",
        "INTERFACE",
    ),
}


@dataclass(frozen=True, slots=True)
class L41R6OfficialClaimScopeBinding:
    """One canonical official claim and its exact authenticated source records."""

    fact_id: FactId
    claim: TrustedOfficialClaim
    sources: tuple[AuthenticatedOfficialSourceProvenance, ...]


@dataclass(frozen=True, slots=True)
class L41R6InterfaceFactProvenance:
    """Consumed live-interface evidence, kept separate from official rules."""

    fact_id: FactId
    evidence_sha256: str
    source_head: str
    source_tree: str
    tool_interfaces: tuple[L41R5ToolInterface, ...]
    scope_code: str


@dataclass(frozen=True, slots=True)
class L41R6CompositeReport:
    """Result with distinct consumed-observation and official-source lineage."""

    capability_report: CapabilityReport
    consumed_l41: ConsumedL41Predecessor
    consumed_l41r5: ConsumedL41R5InterfaceProvenance
    interface_provenance: tuple[L41R6InterfaceFactProvenance, ...]
    official_claim_bindings: tuple[L41R6OfficialClaimScopeBinding, ...]

    @property
    def status(self) -> OverallStatus:
        return self.capability_report.status

    @property
    def facts(self) -> tuple[FactResult, ...]:
        return self.capability_report.facts


def classify_l41r6_composite(
    consumed_l41_bytes: bytes,
    consumed_l41r5_bytes: bytes,
) -> L41R6CompositeReport:
    """Validate both consumed artifacts and emit a pure 13-fact classification.

    Only immutable artifact bytes are accepted. Official claims and source
    digests come from the canonical no-argument source-owned binding. A source
    or evidence identity mismatch raises and yields no partial report.
    """
    consumed_l41 = parse_consumed_l41_bytes(consumed_l41_bytes)
    consumed_l41r5 = parse_consumed_l41r5_bytes(consumed_l41r5_bytes)
    official_bindings = _accepted_claim_bindings()
    interface_provenance = _interface_provenance(consumed_l41r5)
    facts = _classify_facts(consumed_l41, consumed_l41r5, official_bindings)
    status = (
        OverallStatus.BLOCKED
        if any(item.classification is Classification.BLOCKING_L42 for item in facts)
        else OverallStatus.READY_FOR_L42
    )
    report = CapabilityReport(
        status,
        facts,
        consumed_l41.account_fingerprint,
        consumed_l41.account_type,
    )
    return L41R6CompositeReport(
        capability_report=report,
        consumed_l41=consumed_l41,
        consumed_l41r5=consumed_l41r5,
        interface_provenance=interface_provenance,
        official_claim_bindings=official_bindings,
    )


def _accepted_claim_bindings() -> tuple[L41R6OfficialClaimScopeBinding, ...]:
    binding = accepted_official_rule_binding_v2()
    sources_by_id = {source.source_id: source for source in binding.sources}
    claims_by_id = {claim.claim_id: claim for claim in binding.claims}
    result: list[L41R6OfficialClaimScopeBinding] = []
    for fact_id, claim_id in _CLAIM_FACTS:
        try:
            claim = claims_by_id[claim_id]
            source_records = tuple(
                sources_by_id[source_id] for source_id in claim.sources
            )
            source_digests = {
                source.source_id: source.content_sha256 for source in source_records
            }
            resolved = resolve_trusted_official_claim_v2(claim_id, source_digests)
        except (KeyError, TypeError, ValueError):
            raise ValueError("L41R6_OFFICIAL_CLAIM_UNTRUSTED") from None
        if resolved is not claim:
            raise ValueError("L41R6_OFFICIAL_CLAIM_UNTRUSTED")
        result.append(
            L41R6OfficialClaimScopeBinding(
                fact_id=fact_id,
                claim=resolved,
                sources=source_records,
            )
        )
    return tuple(result)


def _interface_provenance(
    evidence: ConsumedL41R5InterfaceProvenance,
) -> tuple[L41R6InterfaceFactProvenance, ...]:
    order_interfaces = tuple(
        interface
        for interface in evidence.tool_interfaces
        if interface.tool_name in _ORDER_TOOL_NAMES
    )
    common = {
        "evidence_sha256": evidence.evidence_sha256,
        "source_head": evidence.source_head,
        "source_tree": evidence.source_tree,
        "tool_interfaces": order_interfaces,
    }
    return (
        L41R6InterfaceFactProvenance(
            fact_id=FactId.SELL_QUANTITY_FIELD,
            scope_code="EXACT_CONSUMED_L41R5_QUANTITY_FIELDS",
            **common,
        ),
        L41R6InterfaceFactProvenance(
            fact_id=FactId.DECIMAL_INTERFACE_PRECISION,
            scope_code="ADVERTISED_REGULAR_HOURS_FRACTIONAL_MARKET_BOUND_ONLY",
            **common,
        ),
        L41R6InterfaceFactProvenance(
            fact_id=FactId.REVIEW_PREVIEW_ONLY,
            scope_code="EXACT_CONSUMED_L41R5_REVIEW_AND_PLACE_IDENTITIES",
            **common,
        ),
    )


def _classify_facts(
    consumed_l41: ConsumedL41Predecessor,
    consumed_l41r5: ConsumedL41R5InterfaceProvenance,
    official_bindings: tuple[L41R6OfficialClaimScopeBinding, ...],
) -> tuple[FactResult, ...]:
    l41_facts = {item.fact_id: item for item in consumed_l41.facts}
    official_facts = {item.fact_id for item in official_bindings}
    decisions: dict[FactId, FactResult] = {}
    for fact_id, item in l41_facts.items():
        if item.classification in {
            Classification.PROVEN,
            Classification.DEFER_TO_FIRST_OWNED_POSITION,
        }:
            decisions[fact_id] = FactResult(
                fact_id,
                item.classification,
                item.rationale_code,
                consumed_l41.evidence_sha256,
            )

    for fact_id, (classification, rationale, evidence_kind) in _L41R6_DECISIONS.items():
        if fact_id in {
            FactId.MINIMUM_SELL_NOTIONAL_OR_ABSENCE,
            FactId.REVIEW_PREVIEW_ONLY,
        }:
            if fact_id not in official_facts:
                classification = Classification.BLOCKING_L42
                rationale = "L41R6_OFFICIAL_CLAIM_UNSUPPORTED"
        evidence_sha256 = (
            consumed_l41r5.evidence_sha256 if evidence_kind == "INTERFACE" else None
        )
        decisions[fact_id] = FactResult(
            fact_id,
            classification,
            rationale,
            evidence_sha256,
        )
    return tuple(decisions[fact_id] for fact_id in FactId)
