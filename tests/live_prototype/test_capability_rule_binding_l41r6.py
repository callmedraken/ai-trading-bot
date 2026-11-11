"""Fake-only tests for pure L41R6 source/interface composition."""

from __future__ import annotations

import ast
import inspect
from dataclasses import fields
from pathlib import Path
from typing import Final

import pytest

from trading_bot.live_prototype import capability_rule_binding_l41r6 as l41r6
from trading_bot.live_prototype.capability_observer import (
    Classification,
    FactId,
    OverallStatus,
)
from trading_bot.live_prototype.consumed_l41_evidence import (
    ACCEPTED_L41_BRANCH,
    ACCEPTED_L41_HEAD,
    ACCEPTED_L41_TREE,
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
from trading_bot.live_prototype.official_rule_binding import (
    OfficialClaimId,
    OfficialSourceId,
)

_L41_SHA256: Final = "a" * 64


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
    classifications = {
        FactId.INTENDED_AGENTIC_ACCOUNT: Classification.PROVEN,
        FactId.SPY_TRADABILITY: Classification.PROVEN,
        FactId.FRACTIONAL_ELIGIBILITY: Classification.PROVEN,
        FactId.INSTANCE_REVIEW_REQUIRES_POSITION: (
            Classification.DEFER_TO_FIRST_OWNED_POSITION
        ),
    }
    rationales = {
        FactId.INTENDED_AGENTIC_ACCOUNT: "ACCOUNT_IDENTITY_PROVEN",
        FactId.SPY_TRADABILITY: "SPY_TRADABILITY_PROVEN",
        FactId.FRACTIONAL_ELIGIBILITY: "SPY_FRACTIONAL_ELIGIBILITY_PROVEN",
        FactId.INSTANCE_REVIEW_REQUIRES_POSITION: (
            "EXACT_OWNED_POSITION_REVIEW_DEFERRED"
        ),
    }
    facts = tuple(
        ConsumedL41Fact(
            fact_id=fact_id,
            classification=classifications.get(fact_id, Classification.BLOCKING_L42),
            rationale_code=rationales.get(fact_id, "OFFICIAL_RULE_UNPROVEN"),
            evidence_sha256=_L41_SHA256,
        )
        for fact_id in FactId
    )
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
        evidence_sha256=_L41_SHA256,
        byte_length=4114,
        status=OverallStatus.BLOCKED,
        reason="L41_OBSERVATION_FAILED",
        source=source,
        capability_report_status=OverallStatus.BLOCKED,
        account_fingerprint="b" * 64,
        account_type="agentic",
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
    digest_by_name = {
        "get_equity_tradability": "c" * 64,
        "place_equity_order": "d" * 64,
        "review_equity_order": "e" * 64,
    }
    interfaces = (
        L41R5ToolInterface(
            tool_name="get_equity_tradability",
            interface_sha256=digest_by_name["get_equity_tradability"],
            additional_properties_present=True,
            additional_properties_form="BOOLEAN_FALSE",
            quantity=None,
            dollar_amount=None,
            fractional_precision_decimal_places=(),
            fractional_precision_conflict=False,
        ),
        L41R5ToolInterface(
            tool_name="place_equity_order",
            interface_sha256=digest_by_name["place_equity_order"],
            additional_properties_present=True,
            additional_properties_form="BOOLEAN_FALSE",
            quantity=_field(),
            dollar_amount=_field(),
            fractional_precision_decimal_places=(6,),
            fractional_precision_conflict=False,
        ),
        L41R5ToolInterface(
            tool_name="review_equity_order",
            interface_sha256=digest_by_name["review_equity_order"],
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


def _patch_consumed_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_composite_emits_exact_thirteen_fact_matrix_and_typed_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_consumed_evidence(monkeypatch)

    result = l41r6.classify_l41r6_composite(
        b"fake L41 artifact", b"fake L41R5 artifact"
    )

    assert result.status is OverallStatus.BLOCKED
    assert tuple(item.fact_id for item in result.facts) == tuple(FactId)
    assert (
        sum(item.classification is Classification.PROVEN for item in result.facts) == 7
    )
    assert tuple(
        item.fact_id
        for item in result.facts
        if item.classification is Classification.BLOCKING_L42
    ) == (
        FactId.QUANTITY_INCREMENT,
        FactId.MINIMUM_QUANTITY,
        FactId.MAXIMUM_QUANTITY_OR_ABSENCE,
        FactId.BELOW_MINIMUM_FULL_CLOSE,
        FactId.RESIDUAL_FULL_OWNED_CLOSE,
    )
    assert (
        result.facts[-1].classification is Classification.DEFER_TO_FIRST_OWNED_POSITION
    )
    assert all(item.provenance is None for item in result.facts)
    assert all(item.submitted_rule_value is None for item in result.facts)
    assert tuple(item.fact_id for item in result.official_claim_bindings) == (
        FactId.MINIMUM_SELL_NOTIONAL_OR_ABSENCE,
        FactId.REVIEW_PREVIEW_ONLY,
    )
    assert tuple(item.fact_id for item in result.interface_provenance) == (
        FactId.SELL_QUANTITY_FIELD,
        FactId.DECIMAL_INTERFACE_PRECISION,
        FactId.REVIEW_PREVIEW_ONLY,
    )
    claims = {item.fact_id: item for item in result.official_claim_bindings}
    assert FactId.SELL_QUANTITY_FIELD not in claims
    assert claims[FactId.REVIEW_PREVIEW_ONLY].claim.claim_id is (
        OfficialClaimId.REVIEW_EQUITY_ORDER_SIMULATION_PRETRADE_WARNINGS
    )
    minimum_sources = claims[FactId.MINIMUM_SELL_NOTIONAL_OR_ABSENCE].sources
    assert tuple(item.source_id for item in minimum_sources) == (
        OfficialSourceId.FRACTIONAL_SHARES,
        OfficialSourceId.RHF_RHS_CUSTOMER_AGREEMENT,
    )
    assert all(item.content_sha256 for item in minimum_sources)
    assert result.facts[4].evidence_sha256 == CONSUMED_L41R5_EVIDENCE_SHA256
    sell_quantity_interface = result.interface_provenance[0]
    assert sell_quantity_interface.fact_id is FactId.SELL_QUANTITY_FIELD
    assert sell_quantity_interface.evidence_sha256 == CONSUMED_L41R5_EVIDENCE_SHA256
    assert tuple(
        item.tool_name for item in sell_quantity_interface.tool_interfaces
    ) == (
        "place_equity_order",
        "review_equity_order",
    )
    assert all(
        item.quantity is not None
        and item.quantity.present
        and item.quantity.direct_type == "string"
        for item in sell_quantity_interface.tool_interfaces
    )


def test_consumed_l41_parse_failure_returns_no_partial_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bytes] = []

    def reject_l41(raw: bytes) -> ConsumedL41Predecessor:
        calls.append(raw)
        raise ValueError("L41_CONSUMED_EVIDENCE_IDENTITY_MISMATCH")

    monkeypatch.setattr(l41r6, "parse_consumed_l41_bytes", reject_l41)
    with pytest.raises(ValueError, match="L41_CONSUMED_EVIDENCE_IDENTITY_MISMATCH"):
        l41r6.classify_l41r6_composite(b"wrong", b"unused")
    assert calls == [b"wrong"]


def test_public_composite_passes_exact_bytes_to_canonical_parsers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_l41: list[bytes] = []
    seen_l41r5: list[bytes] = []
    consumed_l41 = _consumed_l41()
    consumed_l41r5 = _consumed_l41r5()

    def parse_l41(raw: bytes) -> ConsumedL41Predecessor:
        seen_l41.append(raw)
        if raw != b"accepted L41 bytes":
            raise ValueError("L41_CONSUMED_EVIDENCE_IDENTITY_MISMATCH")
        return consumed_l41

    def parse_l41r5(raw: bytes) -> ConsumedL41R5InterfaceProvenance:
        seen_l41r5.append(raw)
        if raw != b"accepted L41R5 bytes":
            raise ValueError("L41R5_CONSUMED_EVIDENCE_IDENTITY_MISMATCH")
        return consumed_l41r5

    monkeypatch.setattr(l41r6, "parse_consumed_l41_bytes", parse_l41)
    monkeypatch.setattr(l41r6, "parse_consumed_l41r5_bytes", parse_l41r5)

    with pytest.raises(ValueError, match="L41R5_CONSUMED_EVIDENCE_IDENTITY_MISMATCH"):
        l41r6.classify_l41r6_composite(b"accepted L41 bytes", b"changed bytes")
    assert seen_l41 == [b"accepted L41 bytes"]
    assert seen_l41r5 == [b"changed bytes"]


def test_wrong_official_digest_resolution_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_consumed_evidence(monkeypatch)

    def reject_claim(*args: object, **kwargs: object) -> None:
        raise ValueError("L41R6_OFFICIAL_CLAIM_SOURCE_BINDING_INVALID")

    monkeypatch.setattr(l41r6, "resolve_trusted_official_claim_v2", reject_claim)
    with pytest.raises(ValueError, match="L41R6_OFFICIAL_CLAIM_UNTRUSTED"):
        l41r6.classify_l41r6_composite(b"fake L41", b"fake L41R5")


def test_public_composite_accepts_only_the_two_preserved_byte_artifacts() -> None:
    from typing import get_type_hints

    signature = inspect.signature(l41r6.classify_l41r6_composite)
    assert tuple(signature.parameters) == ("consumed_l41_bytes", "consumed_l41r5_bytes")
    hints = get_type_hints(l41r6.classify_l41r6_composite)
    assert all(hints[name] is bytes for name in signature.parameters)


def test_pure_classifier_has_no_provider_network_or_legacy_rule_imports() -> None:
    source_path = Path(inspect.getsourcefile(l41r6) or "")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
            imported.extend(alias.name for alias in node.names)
    assert not any(
        module.startswith("trading_bot.robinhood_mcp")
        or module.startswith("trading_bot.live_prototype.capability_collector")
        or module
        in {
            "webbrowser",
            "requests",
            "urllib.request",
            "socket",
            "httpx",
            "httpx2",
            "httpcore",
            "aiohttp",
            "subprocess",
            "mcp",
            "OfficialRuleProvenance",
        }
        for module in imported
    )


def test_r5_interface_model_excludes_untrusted_action_classifier_fields() -> None:
    field_names = {item.name for item in fields(L41R5ToolInterface)}
    assert (
        not {
            "action_semantics",
            "explicitly_placing",
            "explicitly_nonplacing",
            "simulation",
            "pre_trade",
            "warning",
            "tool_description_classification",
        }
        & field_names
    )
