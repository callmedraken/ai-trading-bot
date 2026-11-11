"""Source-owned bindings to narrowly supported official Robinhood claims.

These public sources do not establish the current MCP JSON schema or account-
specific execution capability. No provider maximum or derived quantity bound
is asserted here.

The v2 source digest is SHA-256 over the exact anonymous HTTPS response body
bytes, after HTTP transfer framing, requested with ``Accept-Encoding: identity``
and received without a ``Content-Encoding`` transformation. HTML is not
normalized before hashing. Only digests, byte lengths, and bounded semantic
locators are retained; source bodies are not checked into the repository.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from urllib.parse import urlparse

_RETRIEVED_ON = date(2026, 11, 6)


class OfficialClaimId(StrEnum):
    REVIEW_EQUITY_ORDER_SIMULATION_PRETRADE_WARNINGS = (
        "REVIEW_EQUITY_ORDER_SIMULATION_PRETRADE_WARNINGS"
    )
    FRACTIONAL_SELL_BY_SHARE_AMOUNT = "FRACTIONAL_SELL_BY_SHARE_AMOUNT"
    ORDINARY_FRACTIONAL_TRANSACTION_MINIMUM_USD_1 = (
        "ORDINARY_FRACTIONAL_TRANSACTION_MINIMUM_USD_1"
    )
    APP_SELL_ALL_PATH_FOR_SUB_USD_1_FRACTIONAL_HOLDING = (
        "APP_SELL_ALL_PATH_FOR_SUB_USD_1_FRACTIONAL_HOLDING"
    )
    FRACTIONAL_HOLDING_PRECISION_FIFTH_OR_SIXTH_DECIMAL_BY_VENUE = (
        "FRACTIONAL_HOLDING_PRECISION_FIFTH_OR_SIXTH_DECIMAL_BY_VENUE"
    )


class OfficialSourceId(StrEnum):
    TRADING_WITH_YOUR_AGENT = "TRADING_WITH_YOUR_AGENT"
    FRACTIONAL_SHARES = "FRACTIONAL_SHARES"
    RHF_RHS_CUSTOMER_AGREEMENT = "RHF_RHS_CUSTOMER_AGREEMENT"


@dataclass(frozen=True, slots=True)
class OfficialSourceProvenance:
    source_id: OfficialSourceId
    title: str
    canonical_url: str
    section: str
    retrieved_on: date
    content_sha256: None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, OfficialSourceId):
            raise TypeError("L41_TRUSTED_SOURCE_ID_INVALID")
        if any(
            type(value) is not str or not value or len(value) > 256
            for value in (self.title, self.canonical_url, self.section)
        ):
            raise ValueError("L41_TRUSTED_SOURCE_PROVENANCE_INVALID")
        parsed = urlparse(self.canonical_url)
        if parsed.scheme != "https" or parsed.netloc not in {
            "robinhood.com",
            "cdn.robinhood.com",
        }:
            raise ValueError("L41_TRUSTED_SOURCE_PROVENANCE_INVALID")
        if self.retrieved_on != _RETRIEVED_ON or self.content_sha256 is not None:
            raise ValueError("L41_TRUSTED_SOURCE_PROVENANCE_INVALID")


@dataclass(frozen=True, slots=True)
class TrustedOfficialClaim:
    claim_id: OfficialClaimId
    statement: str
    scope_limit: str
    sources: tuple[OfficialSourceId, ...]
    is_derived: bool = False
    derivation: str | None = None
    prerequisites: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.claim_id, OfficialClaimId):
            raise TypeError("L41_TRUSTED_CLAIM_ID_INVALID")
        if any(
            type(value) is not str or not value or len(value) > 512
            for value in (self.statement, self.scope_limit)
        ):
            raise ValueError("L41_TRUSTED_CLAIM_INVALID")
        if (
            type(self.sources) is not tuple
            or not self.sources
            or any(not isinstance(source, OfficialSourceId) for source in self.sources)
            or len(set(self.sources)) != len(self.sources)
        ):
            raise ValueError("L41_TRUSTED_CLAIM_PROVENANCE_INVALID")
        if type(self.is_derived) is not bool:
            raise TypeError("L41_TRUSTED_CLAIM_DERIVATION_INVALID")
        if self.is_derived:
            if (
                type(self.derivation) is not str
                or not self.derivation
                or type(self.prerequisites) is not tuple
                or not self.prerequisites
                or any(type(item) is not str or not item for item in self.prerequisites)
            ):
                raise ValueError("L41_TRUSTED_CLAIM_DERIVATION_INVALID")
        elif self.derivation is not None or self.prerequisites:
            raise ValueError("L41_TRUSTED_CLAIM_DERIVATION_INVALID")


@dataclass(frozen=True, slots=True)
class TrustedOfficialRuleBinding:
    binding_id: str
    sources: tuple[OfficialSourceProvenance, ...]
    claims: tuple[TrustedOfficialClaim, ...]

    def __post_init__(self) -> None:
        if self.binding_id != "RH_L41_OFFICIAL_RULES_2026_11_06_V1":
            raise ValueError("L41_TRUSTED_BINDING_ID_INVALID")
        if (
            type(self.sources) is not tuple
            or any(
                type(source) is not OfficialSourceProvenance for source in self.sources
            )
            or tuple(source.source_id for source in self.sources)
            != tuple(OfficialSourceId)
        ):
            raise ValueError("L41_TRUSTED_SOURCE_INVENTORY_INVALID")
        if (
            type(self.claims) is not tuple
            or any(type(claim) is not TrustedOfficialClaim for claim in self.claims)
            or tuple(claim.claim_id for claim in self.claims) != tuple(OfficialClaimId)
        ):
            raise ValueError("L41_TRUSTED_CLAIM_INVENTORY_INVALID")
        known_sources = {source.source_id for source in self.sources}
        if any(not set(claim.sources) <= known_sources for claim in self.claims):
            raise ValueError("L41_TRUSTED_CLAIM_PROVENANCE_INVALID")


@dataclass(frozen=True, slots=True)
class _OfficialSourceSnapshot:
    content_type: str
    content_sha256: str
    content_byte_length: int
    source_revision: str | None
    claim_locators: tuple[tuple[OfficialClaimId, str], ...]


@dataclass(frozen=True, slots=True)
class AuthenticatedOfficialSourceProvenance:
    """Immutable provenance for one anonymously retrieved public source body."""

    source_id: OfficialSourceId
    title: str
    canonical_url: str
    content_type: str
    retrieved_on: date
    acceptance_revision: str
    source_revision: str | None
    content_sha256: str
    content_byte_length: int
    claim_locators: tuple[tuple[OfficialClaimId, str], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, OfficialSourceId):
            raise TypeError("L41R6_TRUSTED_SOURCE_ID_INVALID")
        if type(self.content_type) is not str or self.content_type not in {
            "text/html",
            "application/pdf",
        }:
            raise ValueError("L41R6_TRUSTED_SOURCE_PROVENANCE_INVALID")
        if any(
            type(value) is not str or not value or len(value) > 512
            for value in (self.title, self.canonical_url, self.acceptance_revision)
        ):
            raise ValueError("L41R6_TRUSTED_SOURCE_PROVENANCE_INVALID")
        if self.source_revision is not None and (
            type(self.source_revision) is not str
            or not self.source_revision
            or len(self.source_revision) > 128
        ):
            raise ValueError("L41R6_TRUSTED_SOURCE_PROVENANCE_INVALID")
        parsed = urlparse(self.canonical_url)
        if (
            parsed.scheme != "https"
            or parsed.netloc not in {"robinhood.com", "cdn.robinhood.com"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("L41R6_TRUSTED_SOURCE_PROVENANCE_INVALID")
        if (
            type(self.retrieved_on) is not date
            or type(self.content_sha256) is not str
            or len(self.content_sha256) != 64
            or any(
                character not in "0123456789abcdef" for character in self.content_sha256
            )
            or type(self.content_byte_length) is not int
            or self.content_byte_length <= 0
            or type(self.acceptance_revision) is not str
            or self.retrieved_on != _V2_RETRIEVED_ON
            or self.acceptance_revision != _V2_ACCEPTANCE_REVISION
        ):
            raise ValueError("L41R6_TRUSTED_SOURCE_IDENTITY_INVALID")
        snapshot = _V2_SOURCE_SNAPSHOTS.get(self.source_id)
        if (
            snapshot is None
            or self.content_sha256 != snapshot.content_sha256
            or self.content_byte_length != snapshot.content_byte_length
            or self.content_type != snapshot.content_type
            or self.source_revision != snapshot.source_revision
        ):
            raise ValueError("L41R6_TRUSTED_SOURCE_IDENTITY_INVALID")
        legacy_source = next(
            source for source in OFFICIAL_SOURCES if source.source_id is self.source_id
        )
        if (self.title, self.canonical_url) != (
            legacy_source.title,
            legacy_source.canonical_url,
        ):
            raise ValueError("L41R6_TRUSTED_SOURCE_IDENTITY_INVALID")
        if (
            type(self.claim_locators) is not tuple
            or self.claim_locators != snapshot.claim_locators
            or any(
                type(item) is not tuple
                or len(item) != 2
                or not isinstance(item[0], OfficialClaimId)
                or type(item[1]) is not str
                or not item[1]
                or len(item[1]) > 256
                for item in self.claim_locators
            )
        ):
            raise ValueError("L41R6_TRUSTED_SOURCE_LOCATOR_INVALID")


@dataclass(frozen=True, slots=True)
class TrustedOfficialRuleBindingV2:
    binding_id: str
    sources: tuple[AuthenticatedOfficialSourceProvenance, ...]
    claims: tuple[TrustedOfficialClaim, ...]

    def __post_init__(self) -> None:
        if type(self.binding_id) is not str or self.binding_id != _V2_BINDING_ID:
            raise ValueError("L41R6_TRUSTED_BINDING_ID_INVALID")
        if (
            type(self.sources) is not tuple
            or any(
                type(source) is not AuthenticatedOfficialSourceProvenance
                for source in self.sources
            )
            or tuple(source.source_id for source in self.sources)
            != tuple(OfficialSourceId)
        ):
            raise ValueError("L41R6_TRUSTED_SOURCE_INVENTORY_INVALID")
        if (
            type(self.claims) is not tuple
            or any(type(claim) is not TrustedOfficialClaim for claim in self.claims)
            or self.claims != TRUSTED_OFFICIAL_RULE_BINDING.claims
        ):
            raise ValueError("L41R6_TRUSTED_CLAIM_INVENTORY_INVALID")
        source_claims = {
            source.source_id: tuple(claim_id for claim_id, _ in source.claim_locators)
            for source in self.sources
        }
        for claim in self.claims:
            for source_id in claim.sources:
                if claim.claim_id not in source_claims[source_id]:
                    raise ValueError("L41R6_TRUSTED_CLAIM_LOCATOR_INVALID")
        for source_id, claim_ids in source_claims.items():
            if claim_ids != tuple(
                claim.claim_id for claim in self.claims if source_id in claim.sources
            ):
                raise ValueError("L41R6_TRUSTED_CLAIM_LOCATOR_INVALID")


OFFICIAL_SOURCES = (
    OfficialSourceProvenance(
        source_id=OfficialSourceId.TRADING_WITH_YOUR_AGENT,
        title="Trading with your agent",
        canonical_url=(
            "https://robinhood.com/us/en/support/articles/trading-with-your-agent/"
        ),
        section="Agent tools; Equities tools",
        retrieved_on=_RETRIEVED_ON,
    ),
    OfficialSourceProvenance(
        source_id=OfficialSourceId.FRACTIONAL_SHARES,
        title="Fractional shares",
        canonical_url="https://robinhood.com/us/en/support/articles/fractional-shares/",
        section="Trading fractional shares; Trade in shares; Trade in dollars",
        retrieved_on=_RETRIEVED_ON,
    ),
    OfficialSourceProvenance(
        source_id=OfficialSourceId.RHF_RHS_CUSTOMER_AGREEMENT,
        title="RHF-RHS Customer Agreement",
        canonical_url=(
            "https://cdn.robinhood.com/assets/robinhood/legal/"
            "Robinhood-Customer-Agreement.pdf"
        ),
        section="Section 22: Fractional Shares; Not Held Orders",
        retrieved_on=_RETRIEVED_ON,
    ),
)

TRUSTED_OFFICIAL_RULE_BINDING = TrustedOfficialRuleBinding(
    binding_id="RH_L41_OFFICIAL_RULES_2026_11_06_V1",
    sources=OFFICIAL_SOURCES,
    claims=(
        TrustedOfficialClaim(
            claim_id=OfficialClaimId.REVIEW_EQUITY_ORDER_SIMULATION_PRETRADE_WARNINGS,
            statement=(
                "Robinhood describes review_equity_order as simulating an equity "
                "order and returning pre-trade warnings; place_equity_order is "
                "described separately as placing an equity order."
            ),
            scope_limit=(
                "Public tool descriptions only; this does not prove the MCP JSON "
                "schema, account-specific behavior, or a submitted order result."
            ),
            sources=(OfficialSourceId.TRADING_WITH_YOUR_AGENT,),
        ),
        TrustedOfficialClaim(
            claim_id=OfficialClaimId.FRACTIONAL_SELL_BY_SHARE_AMOUNT,
            statement=(
                "Robinhood documents fractional share orders in share amounts, "
                "including Sell in Shares."
            ),
            scope_limit=(
                "Help-page product behavior; it does not establish the MCP JSON "
                "schema quantity field or its accepted precision."
            ),
            sources=(OfficialSourceId.FRACTIONAL_SHARES,),
        ),
        TrustedOfficialClaim(
            claim_id=OfficialClaimId.ORDINARY_FRACTIONAL_TRANSACTION_MINIMUM_USD_1,
            statement=(
                "Ordinary fractional share purchases and sales have a $1 value "
                "minimum; the documented sub-$1 Sell All path is a distinct exception."
            ),
            scope_limit=(
                "This records the published ordinary-order minimum and does not "
                "prove exact residual closure through the MCP interface."
            ),
            sources=(
                OfficialSourceId.FRACTIONAL_SHARES,
                OfficialSourceId.RHF_RHS_CUSTOMER_AGREEMENT,
            ),
        ),
        TrustedOfficialClaim(
            claim_id=OfficialClaimId.APP_SELL_ALL_PATH_FOR_SUB_USD_1_FRACTIONAL_HOLDING,
            statement=(
                "Robinhood documents a Sell All option for a fractional holding "
                "valued below $1."
            ),
            scope_limit=(
                "This is a documented app path; it does not prove a corresponding "
                "MCP operation or automated exact-quantity close."
            ),
            sources=(OfficialSourceId.FRACTIONAL_SHARES,),
        ),
        TrustedOfficialClaim(
            claim_id=(
                OfficialClaimId.FRACTIONAL_HOLDING_PRECISION_FIFTH_OR_SIXTH_DECIMAL_BY_VENUE
            ),
            statement=(
                "The customer agreement describes fractional holdings as rounded "
                "to the fifth or sixth decimal place depending on execution venue."
            ),
            scope_limit=(
                "Holding precision only; this does not establish MCP quantity "
                "precision or prove that all residual quantities can be closed."
            ),
            sources=(OfficialSourceId.RHF_RHS_CUSTOMER_AGREEMENT,),
        ),
    ),
)


_V2_RETRIEVED_ON = date(2026, 11, 10)
_V2_ACCEPTANCE_REVISION = "ARCH147_L41R6_OFFICIAL_RULE_TRUST_BINDING"
_V2_BINDING_ID = "RH_L41_OFFICIAL_RULES_2026_11_10_V2"
_V2_SOURCE_SNAPSHOTS = {
    OfficialSourceId.TRADING_WITH_YOUR_AGENT: _OfficialSourceSnapshot(
        content_type="text/html",
        content_sha256=(
            "a7789ee596168e2605ce4fbca73346f9c75ef882995df187c303d7ae7c17d980"
        ),
        content_byte_length=271393,
        source_revision=None,
        claim_locators=(
            (
                OfficialClaimId.REVIEW_EQUITY_ORDER_SIMULATION_PRETRADE_WARNINGS,
                "Agent tools > Equities tools table > review_equity_order and "
                "place_equity_order rows",
            ),
        ),
    ),
    OfficialSourceId.FRACTIONAL_SHARES: _OfficialSourceSnapshot(
        content_type="text/html",
        content_sha256=(
            "6735222237350f2001da457b75872647c1d4afbe86911cd1759b55f8dc86a3a3"
        ),
        content_byte_length=196743,
        source_revision=None,
        claim_locators=(
            (
                OfficialClaimId.FRACTIONAL_SELL_BY_SHARE_AMOUNT,
                "Trading fractional shares? > Trade in shares > "
                "Sell in Shares workflow",
            ),
            (
                OfficialClaimId.ORDINARY_FRACTIONAL_TRANSACTION_MINIMUM_USD_1,
                "Trading fractional shares? > Trade in dollars and Trade in shares > "
                "$1 ordinary fractional order minimum",
            ),
            (
                OfficialClaimId.APP_SELL_ALL_PATH_FOR_SUB_USD_1_FRACTIONAL_HOLDING,
                "Trading fractional shares? > Trade in dollars > sub-$1 fractional "
                "holding Sell All option",
            ),
        ),
    ),
    OfficialSourceId.RHF_RHS_CUSTOMER_AGREEMENT: _OfficialSourceSnapshot(
        content_type="application/pdf",
        content_sha256=(
            "26dae42562b1ef0d50e9afbb33fa6c5f3acdbbd9dc9a814e3a8e88a5f7e2dcf2"
        ),
        content_byte_length=498438,
        source_revision="Revised November 2, 2026",
        claim_locators=(
            (
                OfficialClaimId.ORDINARY_FRACTIONAL_TRANSACTION_MINIMUM_USD_1,
                "Section 22: Fractional Shares; Not Held Orders > paragraph 2 "
                "(PDF printed page label 16)",
            ),
            (
                OfficialClaimId.FRACTIONAL_HOLDING_PRECISION_FIFTH_OR_SIXTH_DECIMAL_BY_VENUE,
                "Section 22: Fractional Shares; Not Held Orders > paragraph 2 "
                "(PDF printed page label 16)",
            ),
        ),
    ),
}

TRUSTED_OFFICIAL_RULE_BINDING_V2 = TrustedOfficialRuleBindingV2(
    binding_id=_V2_BINDING_ID,
    sources=tuple(
        AuthenticatedOfficialSourceProvenance(
            source_id=source.source_id,
            title=source.title,
            canonical_url=source.canonical_url,
            content_type=_V2_SOURCE_SNAPSHOTS[source.source_id].content_type,
            retrieved_on=_V2_RETRIEVED_ON,
            acceptance_revision=_V2_ACCEPTANCE_REVISION,
            source_revision=_V2_SOURCE_SNAPSHOTS[source.source_id].source_revision,
            content_sha256=_V2_SOURCE_SNAPSHOTS[source.source_id].content_sha256,
            content_byte_length=(
                _V2_SOURCE_SNAPSHOTS[source.source_id].content_byte_length
            ),
            claim_locators=_V2_SOURCE_SNAPSHOTS[source.source_id].claim_locators,
        )
        for source in OFFICIAL_SOURCES
    ),
    claims=TRUSTED_OFFICIAL_RULE_BINDING.claims,
)


def accepted_official_rule_binding_v2() -> TrustedOfficialRuleBindingV2:
    """Return the immutable source-owned v2 official source and claim inventory."""

    return TRUSTED_OFFICIAL_RULE_BINDING_V2


def resolve_trusted_official_claim_v2(
    claim_id: OfficialClaimId,
    source_digests: Mapping[OfficialSourceId, str],
) -> TrustedOfficialClaim:
    """Resolve a claim only when every required source digest matches v2."""

    if not isinstance(claim_id, OfficialClaimId):
        raise ValueError("L41R6_OFFICIAL_CLAIM_ID_INVALID")
    binding = accepted_official_rule_binding_v2()
    claim = next((item for item in binding.claims if item.claim_id is claim_id), None)
    if claim is None:
        raise ValueError("L41R6_OFFICIAL_CLAIM_ID_INVALID")
    if (
        type(source_digests) is not dict
        or any(type(source_id) is not OfficialSourceId for source_id in source_digests)
        or set(source_digests) != set(claim.sources)
        or len(source_digests) != len(claim.sources)
    ):
        raise ValueError("L41R6_OFFICIAL_CLAIM_SOURCE_BINDING_INVALID")
    provenance = {source.source_id: source for source in binding.sources}
    for source_id in claim.sources:
        supplied_digest = source_digests[source_id]
        if (
            type(supplied_digest) is not str
            or supplied_digest != provenance[source_id].content_sha256
        ):
            raise ValueError("L41R6_OFFICIAL_CLAIM_SOURCE_BINDING_INVALID")
    return claim
