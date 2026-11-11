"""Fake-only tests for consumed L41 lineage and trusted public rule claims."""

from dataclasses import FrozenInstanceError, replace

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
    TRUSTED_OFFICIAL_RULE_BINDING_V2,
    OfficialClaimId,
    OfficialSourceId,
    accepted_official_rule_binding_v2,
    resolve_trusted_official_claim_v2,
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


def test_v2_binding_pins_raw_public_source_bodies_and_semantic_locators():
    binding = accepted_official_rule_binding_v2()

    assert binding is TRUSTED_OFFICIAL_RULE_BINDING_V2
    assert binding.binding_id == "RH_L41_OFFICIAL_RULES_2026_11_10_V2"
    assert binding.claims is TRUSTED_OFFICIAL_RULE_BINDING.claims
    assert tuple(source.source_id for source in binding.sources) == tuple(
        OfficialSourceId
    )
    sources = {source.source_id: source for source in binding.sources}
    assert len(sources) == 3
    expected_sources = {
        OfficialSourceId.TRADING_WITH_YOUR_AGENT: (
            "a7789ee596168e2605ce4fbca73346f9c75ef882995df187c303d7ae7c17d980",
            271393,
            "text/html",
            None,
        ),
        OfficialSourceId.FRACTIONAL_SHARES: (
            "6735222237350f2001da457b75872647c1d4afbe86911cd1759b55f8dc86a3a3",
            196743,
            "text/html",
            None,
        ),
        OfficialSourceId.RHF_RHS_CUSTOMER_AGREEMENT: (
            "26dae42562b1ef0d50e9afbb33fa6c5f3acdbbd9dc9a814e3a8e88a5f7e2dcf2",
            498438,
            "application/pdf",
            "Revised November 2, 2026",
        ),
    }
    for source_id, expected in expected_sources.items():
        source = sources[source_id]
        assert (
            source.content_sha256,
            source.content_byte_length,
            source.content_type,
            source.source_revision,
        ) == expected
        assert source.retrieved_on.isoformat() == "2026-11-10"
        assert source.acceptance_revision == "ARCH147_L41R6_OFFICIAL_RULE_TRUST_BINDING"
        assert source.canonical_url.startswith("https://")
        assert "?" not in source.canonical_url
        assert len(source.content_sha256) == 64
        assert source.claim_locators
        assert all(
            isinstance(claim_id, OfficialClaimId)
            and type(locator) is str
            and locator
            and len(locator) <= 256
            for claim_id, locator in source.claim_locators
        )
    agreement_locators = dict(
        sources[OfficialSourceId.RHF_RHS_CUSTOMER_AGREEMENT].claim_locators
    )
    assert (
        "Section 22"
        in agreement_locators[
            OfficialClaimId.FRACTIONAL_HOLDING_PRECISION_FIFTH_OR_SIXTH_DECIMAL_BY_VENUE
        ]
    )
    assert (
        "PDF printed page label 16"
        in agreement_locators[
            OfficialClaimId.ORDINARY_FRACTIONAL_TRANSACTION_MINIMUM_USD_1
        ]
    )
    assert all(source.content_sha256 is not None for source in binding.sources)


def _source_digests_for_claim(
    claim_id: OfficialClaimId,
) -> dict[OfficialSourceId, str]:
    binding = accepted_official_rule_binding_v2()
    claim = next(claim for claim in binding.claims if claim.claim_id is claim_id)
    sources = {source.source_id: source for source in binding.sources}
    return {source_id: sources[source_id].content_sha256 for source_id in claim.sources}


def test_v2_review_claim_requires_exact_catalogue_source_digest():
    claim_id = OfficialClaimId.REVIEW_EQUITY_ORDER_SIMULATION_PRETRADE_WARNINGS
    claim = resolve_trusted_official_claim_v2(
        claim_id, _source_digests_for_claim(claim_id)
    )

    assert claim is next(
        item
        for item in accepted_official_rule_binding_v2().claims
        if item.claim_id is claim_id
    )
    assert claim.sources == (OfficialSourceId.TRADING_WITH_YOUR_AGENT,)
    assert "place_equity_order" in claim.statement


def test_v2_ordinary_minimum_claim_requires_both_exact_source_digests():
    claim_id = OfficialClaimId.ORDINARY_FRACTIONAL_TRANSACTION_MINIMUM_USD_1
    claim = resolve_trusted_official_claim_v2(
        claim_id, _source_digests_for_claim(claim_id)
    )

    assert claim.sources == (
        OfficialSourceId.FRACTIONAL_SHARES,
        OfficialSourceId.RHF_RHS_CUSTOMER_AGREEMENT,
    )


@pytest.mark.parametrize(
    "mutation",
    ["wrong_digest", "missing_source", "extra_source", "string_source_id"],
)
def test_v2_claim_resolution_rejects_unmatched_source_provenance(mutation: str):
    claim_id = OfficialClaimId.ORDINARY_FRACTIONAL_TRANSACTION_MINIMUM_USD_1
    source_digests = _source_digests_for_claim(claim_id)
    if mutation == "wrong_digest":
        source_digests[OfficialSourceId.FRACTIONAL_SHARES] = "0" * 64
    elif mutation == "missing_source":
        del source_digests[OfficialSourceId.RHF_RHS_CUSTOMER_AGREEMENT]
    elif mutation == "extra_source":
        source_digests[OfficialSourceId.TRADING_WITH_YOUR_AGENT] = "0" * 64
    else:
        source_digests = {
            source_id.value: digest  # type: ignore[dict-item]
            for source_id, digest in source_digests.items()
        }

    with pytest.raises(ValueError, match="L41R6_OFFICIAL_CLAIM_SOURCE_BINDING_INVALID"):
        resolve_trusted_official_claim_v2(claim_id, source_digests)  # type: ignore[arg-type]


def test_v2_claim_resolution_rejects_unknown_or_caller_supplied_claims():
    with pytest.raises(ValueError, match="L41R6_OFFICIAL_CLAIM_ID_INVALID"):
        resolve_trusted_official_claim_v2("UNKNOWN", {})  # type: ignore[arg-type]

    caller_claim = TRUSTED_OFFICIAL_RULE_BINDING.claims[0]
    with pytest.raises(ValueError, match="L41R6_OFFICIAL_CLAIM_ID_INVALID"):
        resolve_trusted_official_claim_v2(caller_claim, {})  # type: ignore[arg-type]


def test_v2_source_provenance_cannot_change_bound_digest_or_locator():
    source = accepted_official_rule_binding_v2().sources[0]

    with pytest.raises(ValueError, match="L41R6_TRUSTED_SOURCE_IDENTITY_INVALID"):
        replace(source, content_sha256="0" * 64)
    with pytest.raises(ValueError, match="L41R6_TRUSTED_SOURCE_LOCATOR_INVALID"):
        replace(
            source, claim_locators=((source.claim_locators[0][0], "caller locator"),)
        )


def test_v2_binding_keeps_legacy_v1_unaccepted_source_snapshot_unchanged():
    assert all(
        source.content_sha256 is None
        and source.retrieved_on.isoformat() == "2026-11-06"
        for source in TRUSTED_OFFICIAL_RULE_BINDING.sources
    )
