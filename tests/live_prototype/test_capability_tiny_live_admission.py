"""Fake-only tests for additive tiny-live L41R6 capability admission."""

from __future__ import annotations

import ast
import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Final

import pytest

from trading_bot.live_prototype import capability_rule_binding_l41r6 as l41r6
from trading_bot.live_prototype import tiny_live_capability_admission as admission
from trading_bot.live_prototype.capability_observer import (
    Classification,
    FactId,
    OverallStatus,
)
from trading_bot.live_prototype.consumed_l41_evidence import (
    ACCEPTED_L41_BRANCH,
    ACCEPTED_L41_HEAD,
    ACCEPTED_L41_TREE,
    CONSUMED_L41_EVIDENCE_BYTES,
    CONSUMED_L41_EVIDENCE_SHA256,
    ConsumedL41Attempts,
    ConsumedL41Fact,
    ConsumedL41Predecessor,
    ConsumedL41Source,
)
from trading_bot.live_prototype.consumed_l41r5_evidence import (
    ACCEPTED_L41R5_BRANCH,
    ACCEPTED_L41R5_HEAD,
    ACCEPTED_L41R5_TREE,
    CONSUMED_L41R5_EVIDENCE_BYTES,
    CONSUMED_L41R5_EVIDENCE_SHA256,
    ConsumedL41R5InterfaceProvenance,
    L41R5FieldSemantics,
    L41R5ToolInterface,
)

_L41_RAW: Final = b"synthetic consumed L41 bytes"
_L41R5_RAW: Final = b"synthetic consumed L41R5 bytes"
_ACCOUNT: Final = "b" * 64


def _consumed_l41() -> ConsumedL41Predecessor:
    source = ConsumedL41Source(
        branch=ACCEPTED_L41_BRANCH,
        head=ACCEPTED_L41_HEAD,
        tree=ACCEPTED_L41_TREE,
        origin_feature_head=ACCEPTED_L41_HEAD,
        origin_feature_tree=ACCEPTED_L41_TREE,
        origin_develop_head=ACCEPTED_L41_HEAD,
        origin_develop_tree=ACCEPTED_L41_TREE,
        feature_authority="PASS",
        prospective_develop_authority="PASS",
    )
    proven = {
        FactId.INTENDED_AGENTIC_ACCOUNT: (
            Classification.PROVEN,
            "ACCOUNT_IDENTITY_PROVEN",
        ),
        FactId.SPY_TRADABILITY: (
            Classification.PROVEN,
            "SPY_TRADABILITY_PROVEN",
        ),
        FactId.FRACTIONAL_ELIGIBILITY: (
            Classification.PROVEN,
            "SPY_FRACTIONAL_ELIGIBILITY_PROVEN",
        ),
        FactId.INSTANCE_REVIEW_REQUIRES_POSITION: (
            Classification.DEFER_TO_FIRST_OWNED_POSITION,
            "EXACT_OWNED_POSITION_REVIEW_DEFERRED",
        ),
    }
    facts_list: list[ConsumedL41Fact] = []
    for fact_id in FactId:
        classification, rationale = proven.get(
            fact_id,
            (Classification.BLOCKING_L42, "OFFICIAL_RULE_UNPROVEN"),
        )
        facts_list.append(
            ConsumedL41Fact(
                fact_id=fact_id,
                classification=classification,
                rationale_code=rationale,
                evidence_sha256=CONSUMED_L41_EVIDENCE_SHA256,
            )
        )
    facts = tuple(facts_list)
    attempts = ConsumedL41Attempts(
        oauth_scope_entry_attempts=1,
        native_credential_read_count=None,
        credential_store_accounting="NATIVE_READS_SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED",
        mcp_session_open_attempts=1,
        get_accounts_attempts=1,
        get_equity_tradability_attempts=1,
        collector_invocations=1,
        collector_get_accounts_attempts=1,
        collector_get_equity_tradability_attempts=1,
        other_tool_attempts=0,
        review_equity_order_attempts=0,
        place_equity_order_attempts=0,
        cancel_equity_order_attempts=0,
    )
    return ConsumedL41Predecessor(
        evidence_sha256=CONSUMED_L41_EVIDENCE_SHA256,
        byte_length=CONSUMED_L41_EVIDENCE_BYTES,
        status=OverallStatus.BLOCKED,
        reason="L41_OBSERVATION_FAILED",
        source=source,
        capability_report_status=OverallStatus.BLOCKED,
        account_fingerprint=_ACCOUNT,
        account_type="individual",
        facts=facts,
        attempts=attempts,
    )


def _field() -> L41R5FieldSemantics:
    return L41R5FieldSemantics(
        present=True,
        direct_type="string",
        logical_non_null_type="string",
        required=False,
        nullable=False,
    )


def _consumed_l41r5() -> ConsumedL41R5InterfaceProvenance:
    interfaces = (
        L41R5ToolInterface(
            tool_name="get_equity_tradability",
            interface_sha256=(
                "7d72877df8976be629e9a508f73ef370cfdd7f62d49938456cd0d624a334f8cf"
            ),
            additional_properties_present=True,
            additional_properties_form="BOOLEAN_FALSE",
            quantity=None,
            dollar_amount=None,
            fractional_precision_decimal_places=(),
            fractional_precision_conflict=False,
        ),
        L41R5ToolInterface(
            tool_name="place_equity_order",
            interface_sha256=(
                "46176dd0342955481cfcfee9f2bc56d92b195110d2bb0168bb0a68a431dacf4a"
            ),
            additional_properties_present=True,
            additional_properties_form="BOOLEAN_FALSE",
            quantity=_field(),
            dollar_amount=_field(),
            fractional_precision_decimal_places=(6,),
            fractional_precision_conflict=False,
        ),
        L41R5ToolInterface(
            tool_name="review_equity_order",
            interface_sha256=(
                "5976f7dcf8936e0bb69f0ea2212be6d883654ccb56f4aa4b904c9951160a4069"
            ),
            additional_properties_present=True,
            additional_properties_form="BOOLEAN_FALSE",
            quantity=_field(),
            dollar_amount=_field(),
            fractional_precision_decimal_places=(6,),
            fractional_precision_conflict=False,
        ),
    )
    return ConsumedL41R5InterfaceProvenance(
        evidence_sha256=CONSUMED_L41R5_EVIDENCE_SHA256,
        byte_length=CONSUMED_L41R5_EVIDENCE_BYTES,
        branch=ACCEPTED_L41R5_BRANCH,
        source_head=ACCEPTED_L41R5_HEAD,
        source_tree=ACCEPTED_L41R5_TREE,
        origin_feature_head=ACCEPTED_L41R5_HEAD,
        origin_feature_tree=ACCEPTED_L41R5_TREE,
        origin_develop_head=ACCEPTED_L41R5_HEAD,
        origin_develop_tree=ACCEPTED_L41R5_TREE,
        feature_authority="PASS",
        prospective_develop_authority="PASS",
        tool_interfaces=interfaces,
    )


def _install_fake_predecessors(monkeypatch: pytest.MonkeyPatch) -> None:
    consumed_l41 = _consumed_l41()
    consumed_l41r5 = _consumed_l41r5()
    monkeypatch.setattr(
        l41r6,
        "parse_consumed_l41_bytes",
        lambda raw: consumed_l41,
    )
    monkeypatch.setattr(
        l41r6,
        "parse_consumed_l41r5_bytes",
        lambda raw: consumed_l41r5,
    )


def _composite(monkeypatch: pytest.MonkeyPatch) -> l41r6.L41R6CompositeReport:
    _install_fake_predecessors(monkeypatch)
    return l41r6.classify_l41r6_composite(_L41_RAW, _L41R5_RAW)


def _admit(
    composite: l41r6.L41R6CompositeReport,
) -> admission.TinyLivePrototypeCapabilityAdmission:
    return admission.admit_tiny_live_capabilities(
        composite,
        consumed_l41_bytes=_L41_RAW,
        consumed_l41r5_bytes=_L41R5_RAW,
        account_fingerprint=_ACCOUNT,
    )


def _replace_fact(
    composite: l41r6.L41R6CompositeReport,
    fact_id: FactId,
    **changes: object,
) -> l41r6.L41R6CompositeReport:
    changed = deepcopy(composite)
    facts = list(changed.capability_report.facts)
    index = next(i for i, fact in enumerate(facts) if fact.fact_id is fact_id)
    facts[index] = replace(facts[index], **changes)
    object.__setattr__(changed.capability_report, "facts", tuple(facts))
    return changed


@pytest.fixture
def valid_composite(
    monkeypatch: pytest.MonkeyPatch,
) -> l41r6.L41R6CompositeReport:
    return _composite(monkeypatch)


def test_accepts_only_exact_reconstructed_thirteen_fact_matrix(
    valid_composite: l41r6.L41R6CompositeReport,
) -> None:
    result = _admit(valid_composite)

    assert result.status is (
        admission.TinyLivePrototypeCapabilityStatus.ELIGIBLE_FOR_TINY_LIVE_Q62
    )
    assert admission.exact_l41r6_capability_report_matches(
        result.capability_report,
        valid_composite.capability_report,
    )
    assert result.capability_report.status is OverallStatus.BLOCKED
    assert len(result.capability_report.facts) == 13
    assert (
        sum(
            fact.classification is Classification.PROVEN
            for fact in result.capability_report.facts
        )
        == 7
    )
    assert tuple(
        fact.fact_id
        for fact in result.capability_report.facts
        if fact.classification is Classification.BLOCKING_L42
    ) == (
        FactId.QUANTITY_INCREMENT,
        FactId.MINIMUM_QUANTITY,
        FactId.MAXIMUM_QUANTITY_OR_ABSENCE,
        FactId.BELOW_MINIMUM_FULL_CLOSE,
        FactId.RESIDUAL_FULL_OWNED_CLOSE,
    )
    assert result.capability_report.facts[-1].classification is (
        Classification.DEFER_TO_FIRST_OWNED_POSITION
    )
    assert tuple(
        (
            fact.fact_id,
            fact.classification,
            fact.rationale_code,
            fact.evidence_sha256,
        )
        for fact in result.capability_report.facts
    ) == (
        (
            FactId.INTENDED_AGENTIC_ACCOUNT,
            Classification.PROVEN,
            "ACCOUNT_IDENTITY_PROVEN",
            CONSUMED_L41_EVIDENCE_SHA256,
        ),
        (
            FactId.SPY_TRADABILITY,
            Classification.PROVEN,
            "SPY_TRADABILITY_PROVEN",
            CONSUMED_L41_EVIDENCE_SHA256,
        ),
        (
            FactId.FRACTIONAL_ELIGIBILITY,
            Classification.PROVEN,
            "SPY_FRACTIONAL_ELIGIBILITY_PROVEN",
            CONSUMED_L41_EVIDENCE_SHA256,
        ),
        (
            FactId.SELL_QUANTITY_FIELD,
            Classification.PROVEN,
            "L41R6_SELL_QUANTITY_INTERFACE_PROVEN",
            CONSUMED_L41R5_EVIDENCE_SHA256,
        ),
        (
            FactId.DECIMAL_INTERFACE_PRECISION,
            Classification.PROVEN,
            "L41R6_ADVERTISED_SIX_DECIMAL_BOUND_PROVEN",
            CONSUMED_L41R5_EVIDENCE_SHA256,
        ),
        (
            FactId.QUANTITY_INCREMENT,
            Classification.BLOCKING_L42,
            "L41R6_QUANTITY_INCREMENT_UNSUPPORTED",
            None,
        ),
        (
            FactId.MINIMUM_QUANTITY,
            Classification.BLOCKING_L42,
            "L41R6_MINIMUM_QUANTITY_UNSUPPORTED",
            None,
        ),
        (
            FactId.MAXIMUM_QUANTITY_OR_ABSENCE,
            Classification.BLOCKING_L42,
            "L41R6_MAXIMUM_QUANTITY_UNSUPPORTED",
            None,
        ),
        (
            FactId.MINIMUM_SELL_NOTIONAL_OR_ABSENCE,
            Classification.PROVEN,
            "L41R6_ORDINARY_MINIMUM_USD_1_PROVEN",
            None,
        ),
        (
            FactId.BELOW_MINIMUM_FULL_CLOSE,
            Classification.BLOCKING_L42,
            "L41R6_BELOW_MINIMUM_CLOSE_UNSUPPORTED",
            None,
        ),
        (
            FactId.RESIDUAL_FULL_OWNED_CLOSE,
            Classification.BLOCKING_L42,
            "L41R6_RESIDUAL_CLOSE_UNSUPPORTED",
            None,
        ),
        (
            FactId.REVIEW_PREVIEW_ONLY,
            Classification.PROVEN,
            "L41R6_OFFICIAL_REVIEW_PREVIEW_PROVEN",
            CONSUMED_L41R5_EVIDENCE_SHA256,
        ),
        (
            FactId.INSTANCE_REVIEW_REQUIRES_POSITION,
            Classification.DEFER_TO_FIRST_OWNED_POSITION,
            "EXACT_OWNED_POSITION_REVIEW_DEFERRED",
            CONSUMED_L41_EVIDENCE_SHA256,
        ),
    )
    assert result.consumed_l41_sha256 == CONSUMED_L41_EVIDENCE_SHA256
    assert result.consumed_l41r5_sha256 == CONSUMED_L41R5_EVIDENCE_SHA256
    assert result.official_binding_id == "RH_L41_OFFICIAL_RULES_2026_11_10_V2"
    assert result.policy_id == admission.TINY_LIVE_POLICY.policy_id


def test_admission_digest_is_deterministic_and_repr_hides_account_fingerprint(
    valid_composite: l41r6.L41R6CompositeReport,
) -> None:
    first = _admit(valid_composite)
    second = _admit(deepcopy(valid_composite))

    assert first.admission_digest == second.admission_digest
    assert len(first.admission_digest) == 64
    assert first.admission_digest == first.admission_digest.lower()
    assert _ACCOUNT not in repr(first)


def test_result_is_prototype_only_and_grants_no_authority(
    valid_composite: l41r6.L41R6CompositeReport,
) -> None:
    result = _admit(valid_composite)

    assert result.provider_mutation_count == 0
    assert result.live_readiness_granted is False
    assert result.trade_authority_granted is False


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda c: _replace_fact(
                c,
                FactId.QUANTITY_INCREMENT,
                classification=Classification.PROVEN,
            ),
            id="blocker-promoted",
        ),
        pytest.param(
            lambda c: _replace_fact(
                c,
                FactId.SPY_TRADABILITY,
                classification=Classification.BLOCKING_L42,
            ),
            id="proven-fact-downgraded",
        ),
        pytest.param(
            lambda c: _replace_fact(
                c,
                FactId.QUANTITY_INCREMENT,
                rationale_code="OTHER_ACCEPTED_LOOKING_CODE",
            ),
            id="rationale-drift",
        ),
        pytest.param(
            lambda c: _replace_fact(
                c,
                FactId.QUANTITY_INCREMENT,
                evidence_sha256="a" * 64,
            ),
            id="unexpected-fact-digest",
        ),
        pytest.param(
            lambda c: _replace_fact(
                c,
                FactId.INSTANCE_REVIEW_REQUIRES_POSITION,
                classification=Classification.PROVEN,
            ),
            id="deferred-fact-reclassified",
        ),
    ],
)
def test_rejects_classification_rationale_and_fact_digest_drift(
    valid_composite: l41r6.L41R6CompositeReport,
    mutate,
) -> None:
    with pytest.raises(ValueError, match="TINY_LIVE_CAPABILITY_ADMISSION_INVALID"):
        _admit(mutate(valid_composite))


@pytest.mark.parametrize(
    "mutation",
    ["missing", "extra", "reordered", "duplicate"],
)
def test_rejects_missing_extra_reordered_or_duplicate_fact_inventory(
    valid_composite: l41r6.L41R6CompositeReport,
    mutation: str,
) -> None:
    changed = deepcopy(valid_composite)
    facts = changed.capability_report.facts
    if mutation == "missing":
        replacement = facts[:-1]
    elif mutation == "extra":
        replacement = facts + (facts[-1],)
    elif mutation == "reordered":
        replacement = (facts[1], facts[0], *facts[2:])
    else:
        replacement = (facts[0], facts[0], *facts[2:])
    object.__setattr__(changed.capability_report, "facts", replacement)

    with pytest.raises(ValueError, match="TINY_LIVE_CAPABILITY_ADMISSION_INVALID"):
        _admit(changed)


@pytest.mark.parametrize(
    "drift",
    [
        "l41_digest",
        "l41r5_digest",
        "official_source_digest",
        "official_claim",
        "interface_scope",
        "interface_boolean_as_int",
        "classification_enum_as_string",
    ],
)
def test_rejects_consumed_and_official_provenance_drift(
    valid_composite: l41r6.L41R6CompositeReport,
    drift: str,
) -> None:
    changed = deepcopy(valid_composite)
    if drift == "l41_digest":
        object.__setattr__(changed.consumed_l41, "evidence_sha256", "a" * 64)
    elif drift == "l41r5_digest":
        object.__setattr__(changed.consumed_l41r5, "evidence_sha256", "a" * 64)
    elif drift == "official_source_digest":
        source = changed.official_claim_bindings[0].sources[0]
        object.__setattr__(source, "content_sha256", "a" * 64)
    elif drift == "official_claim":
        claim = changed.official_claim_bindings[0].claim
        object.__setattr__(
            claim,
            "claim_id",
            type(claim.claim_id).FRACTIONAL_SELL_BY_SHARE_AMOUNT,
        )
    elif drift == "interface_scope":
        object.__setattr__(
            changed.interface_provenance[0],
            "scope_code",
            "DIFFERENT_SCOPE",
        )
    elif drift == "interface_boolean_as_int":
        interface = changed.interface_provenance[0].tool_interfaces[0]
        object.__setattr__(interface, "additional_properties_present", 1)
    else:
        fact = changed.capability_report.facts[0]
        object.__setattr__(fact, "classification", "PROVEN")

    with pytest.raises(ValueError, match="TINY_LIVE_CAPABILITY_ADMISSION_INVALID"):
        _admit(changed)


def test_rejects_unexpected_official_binding_identity(
    valid_composite: l41r6.L41R6CompositeReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = deepcopy(admission.accepted_official_rule_binding_v2())
    object.__setattr__(canonical, "binding_id", "DRIFTED_BINDING")
    monkeypatch.setattr(
        admission,
        "accepted_official_rule_binding_v2",
        lambda: canonical,
    )

    with pytest.raises(ValueError, match="TINY_LIVE_CAPABILITY_ADMISSION_INVALID"):
        _admit(valid_composite)


def test_requires_exact_composite_type_and_account_fingerprint(
    valid_composite: l41r6.L41R6CompositeReport,
) -> None:
    lookalike = SimpleNamespace(
        capability_report=valid_composite.capability_report,
        consumed_l41=valid_composite.consumed_l41,
        consumed_l41r5=valid_composite.consumed_l41r5,
        interface_provenance=valid_composite.interface_provenance,
        official_claim_bindings=valid_composite.official_claim_bindings,
    )
    with pytest.raises(ValueError, match="TINY_LIVE_CAPABILITY_ADMISSION_INVALID"):
        admission.admit_tiny_live_capabilities(
            lookalike,
            consumed_l41_bytes=_L41_RAW,
            consumed_l41r5_bytes=_L41R5_RAW,
            account_fingerprint=_ACCOUNT,
        )

    with pytest.raises(ValueError, match="TINY_LIVE_CAPABILITY_ADMISSION_INVALID"):
        admission.admit_tiny_live_capabilities(
            valid_composite,
            consumed_l41_bytes=_L41_RAW,
            consumed_l41r5_bytes=_L41R5_RAW,
            account_fingerprint="c" * 64,
        )


def test_uses_reconstructed_normalized_account_type_and_rejects_report_drift(
    valid_composite: l41r6.L41R6CompositeReport,
) -> None:
    assert valid_composite.capability_report.account_type == "individual"
    assert _admit(valid_composite).capability_report.account_type == "individual"

    changed = deepcopy(valid_composite)
    object.__setattr__(changed.capability_report, "account_type", "individual_cash")
    with pytest.raises(ValueError, match="TINY_LIVE_CAPABILITY_ADMISSION_INVALID"):
        _admit(changed)


def test_classifier_reconstructs_from_both_exact_raw_arguments(
    valid_composite: l41r6.L41R6CompositeReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = admission.classify_l41r6_composite
    calls: list[tuple[bytes, bytes]] = []

    def capture(l41_bytes: bytes, l41r5_bytes: bytes) -> l41r6.L41R6CompositeReport:
        calls.append((l41_bytes, l41r5_bytes))
        return original(l41_bytes, l41r5_bytes)

    monkeypatch.setattr(admission, "classify_l41r6_composite", capture)
    _admit(valid_composite)

    assert calls == [(_L41_RAW, _L41R5_RAW)]


def test_rejects_wrong_raw_bytes_through_canonical_consumed_validators(
    valid_composite: l41r6.L41R6CompositeReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.undo()

    with pytest.raises(ValueError, match="TINY_LIVE_CAPABILITY_ADMISSION_INVALID"):
        admission.admit_tiny_live_capabilities(
            valid_composite,
            consumed_l41_bytes=b"not the preserved L41 evidence",
            consumed_l41r5_bytes=b"not the preserved L41R5 evidence",
            account_fingerprint=_ACCOUNT,
        )


def test_report_matcher_is_type_sensitive_and_fails_closed(
    valid_composite: l41r6.L41R6CompositeReport,
) -> None:
    report = deepcopy(valid_composite.capability_report)
    assert admission.exact_l41r6_capability_report_matches(
        valid_composite.capability_report, report
    )
    lookalike = SimpleNamespace(
        status=report.status,
        facts=report.facts,
        account_fingerprint=report.account_fingerprint,
        account_type=report.account_type,
    )
    assert not admission.exact_l41r6_capability_report_matches(lookalike, report)

    object.__setattr__(report.facts[0], "classification", "PROVEN")
    assert not admission.exact_l41r6_capability_report_matches(
        valid_composite.capability_report, report
    )

    uninitialized = object.__new__(type(report))
    assert not admission.exact_l41r6_capability_report_matches(
        uninitialized, valid_composite.capability_report
    )


def test_digest_changes_when_canonical_policy_material_changes(
    valid_composite: l41r6.L41R6CompositeReport,
) -> None:
    policy = admission.TINY_LIVE_POLICY
    policy_material = policy.canonical_material()
    changed_items = list(policy_material)
    first_key, first_value = changed_items[0]
    changed_items[0] = (first_key, f"{first_value}_CHANGED")
    changed_policy_material = tuple(changed_items)
    changed_policy_payload = json.dumps(
        changed_policy_material,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    changed_policy_sha256 = hashlib.sha256(changed_policy_payload).hexdigest()

    original_material = admission._admission_digest_material(
        valid_composite,
        account_fingerprint=_ACCOUNT,
        policy_id=policy.policy_id,
        policy_sha256=policy.canonical_sha256(),
        policy_material=policy_material,
    )
    changed_material = admission._admission_digest_material(
        valid_composite,
        account_fingerprint=_ACCOUNT,
        policy_id=policy.policy_id,
        policy_sha256=changed_policy_sha256,
        policy_material=changed_policy_material,
    )

    assert policy.canonical_sha256() != changed_policy_sha256
    assert admission._canonical_json_digest(original_material) != (
        admission._canonical_json_digest(changed_material)
    )


def test_new_adapter_has_no_provider_network_holdout_or_retired_path() -> None:
    source_path = Path(admission.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert not imported_roots.intersection(
        {"requests", "httpx", "urllib", "websockets", "mcp", "robinhood"}
    )
    assert "FINAL_HOLDOUT" not in source
    assert "L41R7" not in source
