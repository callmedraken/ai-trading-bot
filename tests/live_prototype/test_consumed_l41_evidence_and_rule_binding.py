"""Fake-only tests for consumed L41 lineage and trusted public rule claims."""

from dataclasses import FrozenInstanceError

import pytest

from trading_bot.live_prototype.capability_observer import (
    CapabilityEvidence,
    Classification,
    FactId,
    OverallStatus,
    classify_capabilities,
)
from trading_bot.live_prototype.consumed_l41_evidence import (
    ACCEPTED_L41_BRANCH,
    ACCEPTED_L41_HEAD,
    ACCEPTED_L41_TREE,
    CONSUMED_L41_EVIDENCE_BYTES,
    CONSUMED_L41_EVIDENCE_SHA256,
    CONSUMED_L41_SCHEMA,
    validate_consumed_l41_document,
)
from trading_bot.live_prototype.official_rule_binding import (
    TRUSTED_OFFICIAL_RULE_BINDING,
    OfficialClaimId,
    OfficialSourceId,
)

_OBSERVATION_DIGEST = "a" * 64
_ACCOUNT_FINGERPRINT = "b" * 64
_FACT_CLASSIFICATIONS = {
    FactId.INTENDED_AGENTIC_ACCOUNT: "PROVEN",
    FactId.SPY_TRADABILITY: "PROVEN",
    FactId.FRACTIONAL_ELIGIBILITY: "PROVEN",
    FactId.INSTANCE_REVIEW_REQUIRES_POSITION: "DEFER_TO_FIRST_OWNED_POSITION",
}
_FACT_RATIONALES = {
    FactId.INTENDED_AGENTIC_ACCOUNT: "ACCOUNT_IDENTITY_PROVEN",
    FactId.SPY_TRADABILITY: "SPY_TRADABILITY_PROVEN",
    FactId.FRACTIONAL_ELIGIBILITY: "SPY_FRACTIONAL_ELIGIBILITY_PROVEN",
    FactId.SELL_QUANTITY_FIELD: "SELL_QUANTITY_INTERFACE_UNPROVEN",
    FactId.DECIMAL_INTERFACE_PRECISION: "SIX_DECIMAL_INTERFACE_BOUND_UNPROVEN",
    FactId.QUANTITY_INCREMENT: "OFFICIAL_RULE_UNUNPROVEN",
    FactId.MINIMUM_QUANTITY: "OFFICIAL_RULE_UNUNPROVEN",
    FactId.MAXIMUM_QUANTITY_OR_ABSENCE: "OFFICIAL_RULE_UNUNPROVEN",
    FactId.MINIMUM_SELL_NOTIONAL_OR_ABSENCE: "OFFICIAL_RULE_UNUNPROVEN",
    FactId.BELOW_MINIMUM_FULL_CLOSE: "OFFICIAL_RULE_UNUNPROVEN",
    FactId.RESIDUAL_FULL_OWNED_CLOSE: "OFFICIAL_RULE_UNUNPROVEN",
    FactId.REVIEW_PREVIEW_ONLY: "REVIEW_PREVIEW_SEMANTICS_UNPROVEN",
    FactId.INSTANCE_REVIEW_REQUIRES_POSITION: "EXACT_OWNED_POSITION_REVIEW_DEFERRED",
}


def _document() -> dict[str, object]:
    facts = [
        {
            "fact_id": fact_id.value,
            "classification": _FACT_CLASSIFICATIONS.get(fact_id, "BLOCKING_L42"),
            "rationale_code": _FACT_RATIONALES[fact_id],
            "evidence_sha256": _OBSERVATION_DIGEST,
            "provenance": None,
        }
        for fact_id in FactId
    ]
    return {
        "schema": CONSUMED_L41_SCHEMA,
        "status": "BLOCKED",
        "reason": "L41_OBSERVATION_FAILED",
        "source": {
            "branch": ACCEPTED_L41_BRANCH,
            "head": ACCEPTED_L41_HEAD,
            "tree": ACCEPTED_L41_TREE,
            "origin_feature_head": ACCEPTED_L41_HEAD,
            "origin_feature_tree": ACCEPTED_L41_TREE,
            "origin_develop_head": ACCEPTED_L41_HEAD,
            "origin_develop_tree": ACCEPTED_L41_TREE,
            "feature_authority": "PASS",
            "prospective_develop_authority": "PASS",
        },
        "capability_report": {
            "status": "BLOCKED",
            "account_fingerprint": _ACCOUNT_FINGERPRINT,
            "account_type": "individual",
            "facts": facts,
        },
        "attempts": {
            "oauth_scope_entry_attempts": 1,
            "native_credential_read_count": None,
            "credential_store_accounting": (
                "NATIVE_READS_SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED"
            ),
            "mcp_session_open_attempts": 1,
            "get_accounts_attempts": 1,
            "get_equity_tradability_attempts": 1,
            "collector_invocations": 1,
            "collector_get_accounts_attempts": 1,
            "collector_get_equity_tradability_attempts": 1,
            "other_tool_attempts": 0,
            "review_equity_order_attempts": 0,
            "place_equity_order_attempts": 0,
            "cancel_equity_order_attempts": 0,
        },
    }


def _parse(document: object | None = None):
    return validate_consumed_l41_document(
        _document() if document is None else document,
        evidence_sha256=CONSUMED_L41_EVIDENCE_SHA256,
        byte_length=CONSUMED_L41_EVIDENCE_BYTES,
    )


def test_consumed_record_is_strictly_predecessor_evidence_not_authority():
    parsed = _parse()

    assert parsed.consumed is True
    assert parsed.retry_authority is False
    assert parsed.capability_authority is False
    assert parsed.status is OverallStatus.BLOCKED
    assert parsed.reason == "L41_OBSERVATION_FAILED"
    assert parsed.source.feature_authority == "PASS"
    assert parsed.source.prospective_develop_authority == "PASS"
    assert len(parsed.facts) == 13
    assert [fact.fact_id for fact in parsed.facts] == list(FactId)
    facts = {fact.fact_id: fact for fact in parsed.facts}
    assert all(
        facts[fact_id].classification is Classification.PROVEN
        for fact_id in (
            FactId.INTENDED_AGENTIC_ACCOUNT,
            FactId.SPY_TRADABILITY,
            FactId.FRACTIONAL_ELIGIBILITY,
        )
    )
    assert parsed.attempts.oauth_scope_entry_attempts == 1
    assert parsed.attempts.mcp_session_open_attempts == 1
    assert parsed.attempts.get_accounts_attempts == 1
    assert parsed.attempts.get_equity_tradability_attempts == 1
    assert parsed.attempts.collector_invocations == 1
    assert parsed.attempts.collector_get_accounts_attempts == 1
    assert parsed.attempts.collector_get_equity_tradability_attempts == 1
    assert (
        parsed.attempts.other_tool_attempts,
        parsed.attempts.review_equity_order_attempts,
        parsed.attempts.place_equity_order_attempts,
        parsed.attempts.cancel_equity_order_attempts,
    ) == (0, 0, 0, 0)
    with pytest.raises(FrozenInstanceError):
        parsed.reason = "READY"  # type: ignore[misc]


@pytest.mark.parametrize(
    "digest,length",
    [
        ("0" * 64, CONSUMED_L41_EVIDENCE_BYTES),
        (CONSUMED_L41_EVIDENCE_SHA256, CONSUMED_L41_EVIDENCE_BYTES - 1),
    ],
)
def test_artifact_digest_and_byte_length_are_fixed(digest: str, length: int):
    with pytest.raises(ValueError, match="L41_CONSUMED_EVIDENCE_IDENTITY_MISMATCH"):
        validate_consumed_l41_document(
            _document(), evidence_sha256=digest, byte_length=length
        )


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("source", "head", "0" * 40),
        ("source", "tree", "0" * 40),
        ("source", "origin_feature_head", "0" * 40),
        ("source", "origin_feature_tree", "0" * 40),
        ("source", "origin_develop_head", "0" * 40),
        ("source", "origin_develop_tree", "0" * 40),
        ("source", "feature_authority", "NOT_RUN"),
        ("source", "prospective_develop_authority", "NOT_RUN"),
    ],
)
def test_source_and_both_authority_identities_fail_closed(
    section: str, key: str, value: str
):
    document = _document()
    document[section][key] = value  # type: ignore[index]

    with pytest.raises(ValueError, match="L41_CONSUMED_EVIDENCE_SOURCE_INVALID"):
        _parse(document)


@pytest.mark.parametrize(
    "key,value",
    [
        ("get_accounts_attempts", 0),
        ("get_equity_tradability_attempts", 0),
        ("collector_invocations", 2),
        ("collector_get_accounts_attempts", 0),
        ("collector_get_equity_tradability_attempts", 0),
        ("other_tool_attempts", 1),
        ("review_equity_order_attempts", 1),
        ("place_equity_order_attempts", 1),
        ("cancel_equity_order_attempts", 1),
        ("oauth_scope_entry_attempts", True),
    ],
)
def test_attempt_counts_must_match_consumed_record_exactly(key: str, value: object):
    document = _document()
    document["attempts"][key] = value  # type: ignore[index]

    with pytest.raises(ValueError, match="L41_CONSUMED_EVIDENCE_ATTEMPTS_INVALID"):
        _parse(document)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "reorder", "provenance"])
def test_fact_inventory_and_unbound_provenance_are_strict(mutation: str):
    document = _document()
    facts = document["capability_report"]["facts"]  # type: ignore[index]
    if mutation == "missing":
        facts.pop()
    elif mutation == "duplicate":
        facts[-1] = dict(facts[0])
    elif mutation == "reorder":
        facts[0], facts[1] = facts[1], facts[0]
    else:
        facts[3]["provenance"] = {"source_identifier": "caller"}

    with pytest.raises(ValueError, match="L41_CONSUMED_EVIDENCE_FACT_"):
        _parse(document)


@pytest.mark.parametrize(
    "field,value",
    [
        ("account_fingerprint", "raw-account-12345"),
        ("account_type", "account_number_12345"),
    ],
)
def test_raw_account_identifiers_are_not_accepted(field: str, value: str):
    document = _document()
    document["capability_report"][field] = value  # type: ignore[index]

    with pytest.raises(ValueError, match="L41_CONSUMED_EVIDENCE_ACCOUNT_INVALID"):
        _parse(document)


@pytest.mark.parametrize("key", ["account_number", "secret", "oauth_token"])
def test_unknown_secret_or_account_fields_are_rejected_by_closed_schema(key: str):
    document = _document()
    document[key] = "SYNTHETIC_SENSITIVE_FIXTURE"

    with pytest.raises(ValueError, match="L41_CONSUMED_EVIDENCE_SCHEMA_INVALID"):
        _parse(document)


def test_consumed_facts_remain_blocked_where_interface_and_rule_proof_is_absent():
    parsed = _parse()
    facts = {fact.fact_id: fact for fact in parsed.facts}

    assert (
        facts[FactId.INTENDED_AGENTIC_ACCOUNT].classification is Classification.PROVEN
    )
    assert facts[FactId.SPY_TRADABILITY].classification is Classification.PROVEN
    assert facts[FactId.FRACTIONAL_ELIGIBILITY].classification is Classification.PROVEN
    assert (
        facts[FactId.INSTANCE_REVIEW_REQUIRES_POSITION].classification
        is Classification.DEFER_TO_FIRST_OWNED_POSITION
    )
    assert all(
        facts[fact_id].classification is Classification.BLOCKING_L42
        for fact_id in FactId
        if fact_id
        not in {
            FactId.INTENDED_AGENTIC_ACCOUNT,
            FactId.SPY_TRADABILITY,
            FactId.FRACTIONAL_ELIGIBILITY,
            FactId.INSTANCE_REVIEW_REQUIRES_POSITION,
        }
    )


def test_current_rationale_formatter_does_not_duplicate_unproven_prefix():
    report = classify_capabilities(
        CapabilityEvidence(
            observation_sha256=_OBSERVATION_DIGEST,
            account_fingerprint=_ACCOUNT_FINGERPRINT,
            agentic_account_count=1,
            account_is_active="ACTIVE",
            account_type="individual",
            spy_account_type_tradability="TRADABLE",
            spy_fractional_tradability="TRADABLE",
            interface=None,
        )
    )
    results = {item.fact_id: item for item in report.facts}

    assert report.status is OverallStatus.BLOCKED
    assert results[FactId.MINIMUM_QUANTITY].rationale_code == "OFFICIAL_RULE_UNPROVEN"
    assert "UNUNPROVEN" not in {item.rationale_code for item in report.facts}


def test_source_owned_official_binding_contains_only_supported_claims():
    binding = TRUSTED_OFFICIAL_RULE_BINDING
    claims = {claim.claim_id: claim for claim in binding.claims}

    assert tuple(claim.claim_id for claim in binding.claims) == tuple(OfficialClaimId)
    assert tuple(source.source_id for source in binding.sources) == tuple(
        OfficialSourceId
    )
    assert all(claim.is_derived is False for claim in binding.claims)
    assert all(
        claim.derivation is None and not claim.prerequisites for claim in binding.claims
    )
    assert all(source.content_sha256 is None for source in binding.sources)
    assert all(
        source.retrieved_on.isoformat() == "2026-11-06" for source in binding.sources
    )
    assert all(
        source.canonical_url.startswith("https://") and "?" not in source.canonical_url
        for source in binding.sources
    )
    assert all(
        "MCP JSON schema" in claim.scope_limit
        for claim in binding.claims
        if claim.claim_id
        in {
            OfficialClaimId.REVIEW_EQUITY_ORDER_SIMULATION_PRETRADE_WARNINGS,
            OfficialClaimId.FRACTIONAL_SELL_BY_SHARE_AMOUNT,
        }
    )
    assert (
        "simulating"
        in claims[
            OfficialClaimId.REVIEW_EQUITY_ORDER_SIMULATION_PRETRADE_WARNINGS
        ].statement
    )
    assert (
        "pre-trade warnings"
        in claims[
            OfficialClaimId.REVIEW_EQUITY_ORDER_SIMULATION_PRETRADE_WARNINGS
        ].statement
    )
    assert claims[
        OfficialClaimId.REVIEW_EQUITY_ORDER_SIMULATION_PRETRADE_WARNINGS
    ].sources == (OfficialSourceId.TRADING_WITH_YOUR_AGENT,)
    assert (
        "share amounts"
        in claims[OfficialClaimId.FRACTIONAL_SELL_BY_SHARE_AMOUNT].statement
    )
    assert (
        "$1"
        in claims[
            OfficialClaimId.ORDINARY_FRACTIONAL_TRANSACTION_MINIMUM_USD_1
        ].statement
    )
    assert (
        "below $1"
        in claims[
            OfficialClaimId.APP_SELL_ALL_PATH_FOR_SUB_USD_1_FRACTIONAL_HOLDING
        ].statement
    )
    assert (
        "fifth or sixth decimal"
        in claims[
            OfficialClaimId.FRACTIONAL_HOLDING_PRECISION_FIFTH_OR_SIXTH_DECIMAL_BY_VENUE
        ].statement
    )
    assert not any(
        "maximum quantity" in (claim.statement + claim.scope_limit).lower()
        or "unlimited" in (claim.statement + claim.scope_limit).lower()
        for claim in binding.claims
    )
    assert all(
        "residual" in claim.scope_limit.lower()
        or "exact-quantity" in claim.scope_limit.lower()
        for claim in binding.claims
        if claim.claim_id
        in {
            OfficialClaimId.APP_SELL_ALL_PATH_FOR_SUB_USD_1_FRACTIONAL_HOLDING,
            OfficialClaimId.FRACTIONAL_HOLDING_PRECISION_FIFTH_OR_SIXTH_DECIMAL_BY_VENUE,
        }
    )
