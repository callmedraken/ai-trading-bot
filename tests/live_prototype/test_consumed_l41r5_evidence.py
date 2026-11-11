"""Fake-only validation tests for the immutable consumed L41R5 interface record."""

from __future__ import annotations

import hashlib
import json

import pytest

from trading_bot.live_prototype.consumed_l41r5_evidence import (
    ACCEPTED_L41R5_HEAD,
    ACCEPTED_L41R5_TREE,
    CONSUMED_L41R5_EVIDENCE_BYTES,
    CONSUMED_L41R5_EVIDENCE_SHA256,
    L41R5FieldSemantics,
    _parse_consumed_l41r5_bytes,
    parse_consumed_l41r5_bytes,
)

_INTERFACE_DIGESTS = {
    "get_equity_tradability": (
        "7d72877df8976be629e9a508f73ef370cfdd7f62d49938456cd0d624a334f8cf"
    ),
    "place_equity_order": (
        "46176dd0342955481cfcfee9f2bc56d92b195110d2bb0168bb0a68a431dacf4a"
    ),
    "review_equity_order": (
        "5976f7dcf8936e0bb69f0ea2212be6d883654ccb56f4aa4b904c9951160a4069"
    ),
}


def _field_record(*, present: bool) -> dict[str, object]:
    if present:
        return {
            "classification": "DIRECT_TYPE",
            "default_is_null": None,
            "default_present": False,
            "direct_type": "string",
            "logical_non_null_type": "string",
            "nullable": False,
            "present": True,
            "required": False,
            "schema_keyword_inventory_sha256": (
                "c316b4070f7b6033ddab2d75bddd4d98c9a3426babbbbac257675e586adcdf65"
            ),
            "schema_keyword_names": ["description", "type"],
            "union_keyword": "none",
            "union_primitive_types": [],
        }
    return {
        "classification": "ABSENT",
        "default_is_null": None,
        "default_present": False,
        "direct_type": "MISSING",
        "logical_non_null_type": None,
        "nullable": False,
        "present": False,
        "required": False,
        "schema_keyword_inventory_sha256": None,
        "schema_keyword_names": [],
        "union_keyword": "none",
        "union_primitive_types": [],
    }


def _fingerprint(tool_name: str) -> dict[str, object]:
    is_order_tool = tool_name in {"place_equity_order", "review_equity_order"}
    precision = [] if tool_name == "get_equity_tradability" else [6]
    return {
        "additional_properties_form": "BOOLEAN_FALSE",
        "additional_properties_present": True,
        "additional_properties_schema_composition_names": [],
        "additional_properties_schema_contains_reference": False,
        "additional_properties_schema_keyword_inventory_sha256": None,
        "additional_properties_schema_keyword_names": [],
        "additional_properties_schema_sha256": None,
        "ambiguity_classes": [],
        "description_sha256": "0" * 64,
        "fields": {
            "dollar_amount": _field_record(present=is_order_tool),
            "quantity": _field_record(present=is_order_tool),
        },
        "fractional_precision_conflict": False,
        "fractional_precision_decimal_places": precision,
        "input_schema_sha256": "1" * 64,
        "interface_sha256": _INTERFACE_DIGESTS[tool_name],
        "nested_description_classification": {
            "description_count": 0,
            "description_sha256": "5" * 64,
            "explicitly_nonplacing": False,
            "explicitly_placing": False,
            "malformed": False,
            "mentions_pretrade": False,
            "mentions_simulation": False,
            "mentions_warning_or_alert": False,
        },
        "nested_fractional_precision_decimal_places": [],
        "property_count": 0,
        "property_inventory_sha256": "2" * 64,
        "property_names": [],
        "required_count": 0,
        "required_inventory_sha256": "3" * 64,
        "required_names": [],
        "required_not_in_properties": [],
        "schema_keyword_inventory_sha256": "4" * 64,
        "schema_keyword_names": [],
        "tool_description_classification": {
            "action_semantics": "UNKNOWN",
            "explicitly_nonplacing": False,
            "explicitly_placing": False,
            "malformed": False,
            "mentions_pretrade": False,
            "mentions_simulation": False,
            "mentions_warning_or_alert": False,
        },
        "tool_fractional_precision_decimal_places": precision,
        "tool_name": tool_name,
        "top_level_type": "object",
    }


def _valid_document() -> dict[str, object]:
    return {
        "attempt_counts": {
            "browser_launches": 0,
            "cancel_equity_order_attempts": 0,
            "get_accounts_attempts": 0,
            "get_equity_tradability_attempts": 0,
            "get_orders_attempts": 0,
            "get_portfolio_attempts": 0,
            "get_positions_attempts": 0,
            "get_quotes_attempts": 0,
            "mcp_session_open_attempts": 1,
            "mcp_tool_invocation_attempts": 0,
            "oauth_scope_entry_attempts": 1,
            "other_tool_attempts": 0,
            "place_equity_order_attempts": 0,
            "review_equity_order_attempts": 0,
            "tools_list_attempts": 1,
        },
        "automatic_retry": "FORBIDDEN",
        "browser_launches": 0,
        "credential_store_accounting": "SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED",
        "l41r4_interface_baseline": _INTERFACE_DIGESTS.copy(),
        "l41r4_predecessor_evidence": {
            "evidence_length_bytes": 8142,
            "evidence_path": (
                r"F:\AI\temp\arch147-l41r4-schema-observation-"
                r"7cc31ac681214030b64c8a64ba8679dd\evidence.json"
            ),
            "evidence_sha256": (
                "BB8A993179A0B8AF4C5F1343B8CFE170B578E413BCE0F95CB40A6F5FB9BA2B25"
            ),
            "observation": "L41R4_SCHEMA_CLASSIFICATION_DIAGNOSTIC",
            "reason": "L41R4_TOP_LEVEL_UNSUPPORTED_CONSTRAINT",
            "source_head": "c343ad83fc86ad1635374b177b27ab52a2da1dde",
            "source_tree": "2411e867f00e11d92ad7cf208684d03518c17731",
        },
        "native_credential_read_count": None,
        "native_credential_write_count": None,
        "observation": "L41R5_SCHEMA_SEMANTIC_RECOVERY",
        "one_shot": True,
        "provider_numeric_rules_derived": False,
        "reason": "L41R5_PLACE_NONPLACEMENT_SEMANTIC_CONFLICT",
        "schema": "arch147-l41r5-schema-semantic-recovery-observation/v1",
        "schemas": [],
        "source": {
            "branch": "feature/robinhood-live-prototype-current",
            "feature_authority": "PASS",
            "head": ACCEPTED_L41R5_HEAD,
            "origin_develop_head": ACCEPTED_L41R5_HEAD,
            "origin_develop_tree": ACCEPTED_L41R5_TREE,
            "origin_feature_head": ACCEPTED_L41R5_HEAD,
            "origin_feature_tree": ACCEPTED_L41R5_TREE,
            "prospective_develop_authority": "PASS",
            "tree": ACCEPTED_L41R5_TREE,
        },
        "status": "BLOCKED",
        "structural_fingerprints": [
            _fingerprint("get_equity_tradability"),
            _fingerprint("place_equity_order"),
            _fingerprint("review_equity_order"),
        ],
        "trusted_binding": False,
    }


def _parse_synthetic(document: dict[str, object] | None = None):
    raw = json.dumps(
        _valid_document() if document is None else document,
        separators=(",", ":"),
    ).encode("utf-8")
    return _parse_consumed_l41r5_bytes(
        raw,
        expected_sha256=hashlib.sha256(raw).hexdigest(),
        expected_byte_length=len(raw),
    )


def test_consumed_l41r5_identity_pins_are_exact() -> None:
    assert CONSUMED_L41R5_EVIDENCE_SHA256 == (
        "fc95eb9fbdd2b7dbe064b7cac84e8851996669af96be1273ae46309873a650ff"
    )
    assert CONSUMED_L41R5_EVIDENCE_BYTES == 11128
    assert ACCEPTED_L41R5_HEAD == "13a97b1f4c369243737cc0ac6646b5520327651a"
    assert ACCEPTED_L41R5_TREE == "81e58dd75656593ca0f960ecdcdf21c14d00d969"


def test_synthetic_exact_interface_evidence_parses_with_private_digest_seam() -> None:
    result = _parse_synthetic()

    assert result.evidence_sha256 != CONSUMED_L41R5_EVIDENCE_SHA256
    assert result.byte_length > 0
    assert result.source_head == ACCEPTED_L41R5_HEAD
    assert result.source_tree == ACCEPTED_L41R5_TREE
    assert tuple(tool.tool_name for tool in result.tool_interfaces) == (
        "get_equity_tradability",
        "place_equity_order",
        "review_equity_order",
    )
    assert tuple(tool.interface_sha256 for tool in result.tool_interfaces) == tuple(
        _INTERFACE_DIGESTS.values()
    )

    tradability, place, review = result.tool_interfaces
    assert tradability.quantity is None
    assert tradability.dollar_amount is None
    assert tradability.fractional_precision_decimal_places == ()
    assert all(
        tool.additional_properties_present
        and tool.additional_properties_form == "BOOLEAN_FALSE"
        and not tool.fractional_precision_conflict
        for tool in result.tool_interfaces
    )
    assert place.quantity == L41R5FieldSemantics(True, "string", "string", False, False)
    assert place.dollar_amount == L41R5FieldSemantics(
        True, "string", "string", False, False
    )
    assert review.quantity == place.quantity
    assert review.dollar_amount == place.dollar_amount
    assert place.fractional_precision_decimal_places == (6,)
    assert review.fractional_precision_decimal_places == (6,)


def test_public_parser_rejects_wrong_bytes_before_json_decode() -> None:
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        parse_consumed_l41r5_bytes(b"not json")


def test_private_parser_rejects_wrong_expected_byte_count() -> None:
    raw = b"{}"
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        _parse_consumed_l41r5_bytes(
            raw,
            expected_sha256=hashlib.sha256(raw).hexdigest(),
            expected_byte_length=len(raw) + 1,
        )


def test_private_parser_rejects_wrong_expected_digest() -> None:
    raw = b"{}"
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        _parse_consumed_l41r5_bytes(
            raw,
            expected_sha256="0" * 64,
            expected_byte_length=len(raw),
        )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("source", "head"), "0000000000000000000000000000000000000000"),
        (("source", "tree"), "0000000000000000000000000000000000000000"),
        (("source", "origin_feature_head"), "0000000000000000000000000000000000000000"),
        (("source", "origin_feature_tree"), "0000000000000000000000000000000000000000"),
        (("source", "origin_develop_head"), "0000000000000000000000000000000000000000"),
        (("source", "origin_develop_tree"), "0000000000000000000000000000000000000000"),
        (("source", "feature_authority"), "FAIL"),
        (("source", "prospective_develop_authority"), "FAIL"),
    ],
)
def test_source_identity_or_authority_mutation_fails_closed(
    path: tuple[str, ...], value: str
) -> None:
    document = _valid_document()
    target = document
    for key in path[:-1]:
        target = target[key]  # type: ignore[assignment]
    target[path[-1]] = value  # type: ignore[index]
    with pytest.raises(ValueError, match="SOURCE_INVALID"):
        _parse_synthetic(document)


@pytest.mark.parametrize(
    ("tool_index", "field", "value", "error"),
    [
        (0, "interface_sha256", "0" * 64, "INTERFACE_INVALID"),
        (1, "additional_properties_form", "SCHEMA", "INTERFACE_INVALID"),
        (1, "additional_properties_form", False, "INTERFACE_INVALID"),
        (1, "fractional_precision_decimal_places", [5], "PRECISION_INVALID"),
        (2, "fractional_precision_conflict", True, "PRECISION_INVALID"),
    ],
)
def test_interface_digest_shape_and_precision_mutations_fail_closed(
    tool_index: int, field: str, value: object, error: str
) -> None:
    document = _valid_document()
    document["structural_fingerprints"][tool_index][field] = value  # type: ignore[index]
    with pytest.raises(ValueError, match=error):
        _parse_synthetic(document)


@pytest.mark.parametrize(
    ("tool_index", "field_name", "field", "value"),
    [
        (1, "quantity", "present", False),
        (1, "quantity", "direct_type", "number"),
        (1, "quantity", "logical_non_null_type", "number"),
        (1, "quantity", "required", True),
        (1, "quantity", "nullable", True),
        (2, "dollar_amount", "present", False),
        (2, "dollar_amount", "direct_type", "integer"),
        (2, "dollar_amount", "logical_non_null_type", "integer"),
        (2, "dollar_amount", "required", True),
        (2, "dollar_amount", "nullable", True),
    ],
)
def test_order_field_semantic_mutations_fail_closed(
    tool_index: int, field_name: str, field: str, value: object
) -> None:
    document = _valid_document()
    fingerprints = document["structural_fingerprints"]
    fingerprints[tool_index]["fields"][field_name][field] = value  # type: ignore[index]
    with pytest.raises(ValueError, match="FIELD_INVALID"):
        _parse_synthetic(document)


@pytest.mark.parametrize(
    ("mutation",),
    [
        ("nonzero_tool_attempt",),
        ("boolean_counter_alias",),
        ("automatic_retry",),
        ("one_shot",),
        ("trusted_binding",),
        ("provider_numeric_rules_derived",),
        ("schema_nonempty",),
        ("status",),
        ("reason",),
        ("observation",),
    ],
)
def test_effect_retry_and_outcome_mutations_fail_closed(mutation: str) -> None:
    document = _valid_document()
    if mutation == "nonzero_tool_attempt":
        document["attempt_counts"]["mcp_tool_invocation_attempts"] = 1  # type: ignore[index]
    elif mutation == "boolean_counter_alias":
        document["attempt_counts"]["tools_list_attempts"] = True  # type: ignore[index]
    elif mutation == "automatic_retry":
        document["automatic_retry"] = "ALLOWED"
    elif mutation == "one_shot":
        document["one_shot"] = 1
    elif mutation == "trusted_binding":
        document["trusted_binding"] = True
    elif mutation == "provider_numeric_rules_derived":
        document["provider_numeric_rules_derived"] = True
    elif mutation == "schema_nonempty":
        document["schemas"] = ["unexpected"]
    elif mutation == "status":
        document["status"] = "READY"
    elif mutation == "reason":
        document["reason"] = "OTHER"
    else:
        document["observation"] = "L41R5_SCHEMA_CLASSIFICATION_DIAGNOSTIC"

    with pytest.raises(ValueError):
        _parse_synthetic(document)


def test_legacy_action_classifier_is_not_returned_or_used() -> None:
    document = _valid_document()
    fingerprints = document["structural_fingerprints"]
    fingerprints[1]["tool_description_classification"] = {
        "action_semantics": "CONFLICTING",
        "explicitly_placing": True,
        "explicitly_nonplacing": True,
        "malformed": False,
        "mentions_pretrade": False,
        "mentions_simulation": False,
        "mentions_warning_or_alert": False,
    }
    fingerprints[2]["tool_description_classification"] = {
        "action_semantics": "CONFLICTING",
        "explicitly_placing": False,
        "explicitly_nonplacing": True,
        "malformed": False,
        "mentions_pretrade": False,
        "mentions_simulation": False,
        "mentions_warning_or_alert": False,
    }

    result = _parse_synthetic(document)
    assert tuple(tool.interface_sha256 for tool in result.tool_interfaces) == tuple(
        _INTERFACE_DIGESTS.values()
    )
    assert not hasattr(result, "tool_description_classification")
    assert not hasattr(result, "action_semantics")
    assert not hasattr(result, "retry_authority")
    assert not hasattr(result, "trusted_binding")


@pytest.mark.parametrize(
    "raw",
    [
        b'{"duplicate":1,"duplicate":2}',
        b'{"value":NaN}',
        b'{"value":Infinity}',
        b"\xff",
    ],
)
def test_private_parser_rejects_duplicate_non_json_and_invalid_utf8(raw: bytes) -> None:
    with pytest.raises(ValueError, match="JSON_INVALID"):
        _parse_consumed_l41r5_bytes(
            raw,
            expected_sha256=hashlib.sha256(raw).hexdigest(),
            expected_byte_length=len(raw),
        )


def test_non_bytes_input_is_rejected() -> None:
    with pytest.raises(TypeError, match="BYTES_INVALID"):
        parse_consumed_l41r5_bytes(bytearray(b"{}"))  # type: ignore[arg-type]


def test_unknown_or_missing_root_fields_fail_closed() -> None:
    missing = _valid_document()
    del missing["trusted_binding"]
    with pytest.raises(ValueError, match="SCHEMA_INVALID"):
        _parse_synthetic(missing)

    extra = _valid_document()
    extra["unreviewed"] = False
    with pytest.raises(ValueError, match="SCHEMA_INVALID"):
        _parse_synthetic(extra)


def test_duplicate_json_keys_fail_even_with_correct_test_digest() -> None:
    raw = b'{"schema":"one","schema":"two"}'
    with pytest.raises(ValueError, match="JSON_INVALID"):
        _parse_consumed_l41r5_bytes(
            raw,
            expected_sha256=hashlib.sha256(raw).hexdigest(),
            expected_byte_length=len(raw),
        )
