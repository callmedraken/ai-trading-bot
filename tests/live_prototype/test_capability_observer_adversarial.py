"""Adversarial pure-model tests for the effect-disabled L41 capability report."""

from datetime import date

import pytest

from trading_bot.live_prototype.capability_observer import (
    CapabilityEvidence,
    Classification,
    FactId,
    InterfaceClaims,
    OfficialRuleProvenance,
    OverallStatus,
    RuleClaim,
    classify_capabilities,
)

_OBSERVATION = "a" * 64
_ACCOUNT = "b" * 64
_RULE_FACTS = (
    FactId.QUANTITY_INCREMENT,
    FactId.MINIMUM_QUANTITY,
    FactId.MAXIMUM_QUANTITY_OR_ABSENCE,
    FactId.MINIMUM_SELL_NOTIONAL_OR_ABSENCE,
    FactId.BELOW_MINIMUM_FULL_CLOSE,
    FactId.RESIDUAL_FULL_OWNED_CLOSE,
)


def _provenance(*claim_ids: str) -> OfficialRuleProvenance:
    return OfficialRuleProvenance(
        source_identifier="caller-asserted-source",
        canonical_url_or_document_id="https://example.invalid/rules",
        retrieved_on=date(2026, 11, 5),
        accepted_on=None,
        content_sha256="c" * 64,
        semantic_claim_ids=tuple(claim_ids),
    )


def _account_claims(**overrides: object) -> CapabilityEvidence:
    values: dict[str, object] = {
        "observation_sha256": _OBSERVATION,
        "account_fingerprint": _ACCOUNT,
        "agentic_account_count": 1,
        "account_is_active": "ACTIVE",
        "account_type": "individual",
        "spy_account_type_tradability": "TRADABLE",
        "spy_fractional_tradability": "TRADABLE",
        "interface": None,
        "official_rule_claims": (),
    }
    values.update(overrides)
    return CapabilityEvidence(**values)  # type: ignore[arg-type]


def _fact(report, fact_id: FactId):
    return next(item for item in report.facts if item.fact_id is fact_id)


def test_absent_observation_digest_is_not_run_even_when_other_fields_are_forged():
    evidence = _account_claims(observation_sha256=None)

    report = classify_capabilities(evidence)

    assert report.status is OverallStatus.NOT_RUN
    assert report.account_fingerprint is None
    assert all(
        item.classification is Classification.BLOCKING_L42
        for item in report.facts
        if item.fact_id is not FactId.INSTANCE_REVIEW_REQUIRES_POSITION
    )
    assert (
        _fact(report, FactId.INSTANCE_REVIEW_REQUIRES_POSITION).classification
        is Classification.DEFER_TO_FIRST_OWNED_POSITION
    )


def test_digest_alone_does_not_clear_missing_account_or_rule_evidence():
    report = classify_capabilities(
        CapabilityEvidence(
            observation_sha256=_OBSERVATION,
            account_fingerprint=None,
            agentic_account_count=None,
            account_is_active=None,
            account_type=None,
            spy_account_type_tradability=None,
            spy_fractional_tradability=None,
            interface=None,
        )
    )

    assert report.status is OverallStatus.BLOCKED
    assert _fact(report, FactId.INTENDED_AGENTIC_ACCOUNT).classification is (
        Classification.BLOCKING_L42
    )
    assert _fact(report, FactId.FRACTIONAL_ELIGIBILITY).classification is (
        Classification.BLOCKING_L42
    )
    assert all(
        _fact(report, fact_id).classification is Classification.BLOCKING_L42
        for fact_id in _RULE_FACTS
    )


def test_interface_schema_claims_do_not_prove_account_eligibility_or_rules():
    interface = InterfaceClaims(
        review_quantity_field="quantity",
        place_quantity_field="quantity",
        decimal_places=6,
        review_semantics="SIMULATE_WITHOUT_PLACING",
        provenance=_provenance(
            FactId.SELL_QUANTITY_FIELD.value,
            FactId.DECIMAL_INTERFACE_PRECISION.value,
            FactId.REVIEW_PREVIEW_ONLY.value,
        ),
    )
    report = classify_capabilities(
        CapabilityEvidence(
            observation_sha256=_OBSERVATION,
            account_fingerprint=None,
            agentic_account_count=None,
            account_is_active=None,
            account_type=None,
            spy_account_type_tradability=None,
            spy_fractional_tradability=None,
            interface=interface,
        )
    )

    assert _fact(report, FactId.SELL_QUANTITY_FIELD).classification is (
        Classification.PROVEN
    )
    assert _fact(report, FactId.DECIMAL_INTERFACE_PRECISION).classification is (
        Classification.PROVEN
    )
    assert _fact(report, FactId.REVIEW_PREVIEW_ONLY).classification is (
        Classification.PROVEN
    )
    assert _fact(report, FactId.INTENDED_AGENTIC_ACCOUNT).classification is (
        Classification.BLOCKING_L42
    )
    assert _fact(report, FactId.FRACTIONAL_ELIGIBILITY).classification is (
        Classification.BLOCKING_L42
    )
    assert all(
        _fact(report, fact_id).classification is Classification.BLOCKING_L42
        for fact_id in _RULE_FACTS
    )
    assert report.status is OverallStatus.BLOCKED


@pytest.mark.parametrize(
    "fact_id,value",
    [
        (FactId.QUANTITY_INCREMENT, "0.000001"),
        (FactId.MINIMUM_QUANTITY, "0"),
        (FactId.MAXIMUM_QUANTITY_OR_ABSENCE, "UNSUPPORTED"),
        (FactId.MINIMUM_SELL_NOTIONAL_OR_ABSENCE, "-0.01"),
        (FactId.BELOW_MINIMUM_FULL_CLOSE, "true"),
        (FactId.RESIDUAL_FULL_OWNED_CLOSE, "UNSUPPORTED"),
    ],
)
def test_typed_caller_rule_claim_and_digest_remain_unaccepted(
    fact_id: FactId, value: str
):
    claim = RuleClaim(fact_id, value, _provenance(fact_id.value))
    report = classify_capabilities(_account_claims(official_rule_claims=(claim,)))
    result = _fact(report, fact_id)

    assert result.classification is Classification.BLOCKING_L42
    assert result.rationale_code == "OFFICIAL_RULE_SUBMITTED_UNACCEPTED"
    assert result.evidence_sha256 == _OBSERVATION
    assert result.provenance == claim.provenance
    assert result.submitted_rule_value == value
    assert report.status is OverallStatus.BLOCKED


def test_conflicting_duplicate_rule_claims_are_rejected_not_resolved_by_order():
    provenance = _provenance(FactId.QUANTITY_INCREMENT.value)
    claims = (
        RuleClaim(FactId.QUANTITY_INCREMENT, "0.001", provenance),
        RuleClaim(FactId.QUANTITY_INCREMENT, "0.000001", provenance),
    )

    with pytest.raises(ValueError, match="L41_RULE_CLAIM_DUPLICATE"):
        _account_claims(official_rule_claims=claims)


@pytest.mark.parametrize(
    "overrides,account_status,spy_status,fractional_status",
    [
        (
            {"agentic_account_count": None},
            Classification.BLOCKING_L42,
            Classification.BLOCKING_L42,
            Classification.BLOCKING_L42,
        ),
        (
            {"agentic_account_count": 0},
            Classification.BLOCKING_L42,
            Classification.BLOCKING_L42,
            Classification.BLOCKING_L42,
        ),
        (
            {"account_is_active": "INACTIVE"},
            Classification.BLOCKING_L42,
            Classification.BLOCKING_L42,
            Classification.BLOCKING_L42,
        ),
        (
            {"spy_account_type_tradability": "UNTRADABLE"},
            Classification.PROVEN,
            Classification.BLOCKING_L42,
            Classification.PROVEN,
        ),
        (
            {"spy_fractional_tradability": "UNTRADABLE"},
            Classification.PROVEN,
            Classification.PROVEN,
            Classification.BLOCKING_L42,
        ),
        (
            {"spy_fractional_tradability": "UNKNOWN"},
            Classification.PROVEN,
            Classification.PROVEN,
            Classification.BLOCKING_L42,
        ),
    ],
)
def test_missing_or_negative_account_eligibility_facts_remain_blocked(
    overrides, account_status, spy_status, fractional_status
):
    report = classify_capabilities(_account_claims(**overrides))

    assert report.status is OverallStatus.BLOCKED
    assert (
        _fact(report, FactId.INTENDED_AGENTIC_ACCOUNT).classification is account_status
    )
    assert _fact(report, FactId.SPY_TRADABILITY).classification is spy_status
    assert _fact(report, FactId.FRACTIONAL_ELIGIBILITY).classification is (
        fractional_status
    )


def test_raw_account_identifier_is_rejected_from_fingerprint_field():
    with pytest.raises(ValueError, match="L41_EVIDENCE_DIGEST_INVALID"):
        _account_claims(account_fingerprint="raw-account-12345")


def test_report_cannot_be_constructed_ready_while_required_facts_block():
    report = classify_capabilities(_account_claims())
    assert report.status is OverallStatus.BLOCKED
    with pytest.raises(ValueError, match="L41_READY_WITH_BLOCKER"):
        type(report)(
            status=OverallStatus.READY_FOR_L42,
            facts=report.facts,
            account_fingerprint=report.account_fingerprint,
            account_type=report.account_type,
        )
