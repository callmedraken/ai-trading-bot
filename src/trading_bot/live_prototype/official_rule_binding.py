"""Source-owned bindings to narrowly supported official Robinhood claims.

These public sources do not establish the current MCP JSON schema or account-
specific execution capability. No provider maximum or derived quantity bound
is asserted here.
"""

from __future__ import annotations

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
