"""Strict, effect-free parsing of the one consumed L41R5 artifact.

Only immutable interface facts needed by the L41R6 composite are returned.
The predecessor's lexical action classifier, retry state, and trust flags are
validated where required but are never exposed as authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Final

CONSUMED_L41R5_SCHEMA: Final = "arch147-l41r5-schema-semantic-recovery-observation/v1"
CONSUMED_L41R5_EVIDENCE_SHA256: Final = (
    "fc95eb9fbdd2b7dbe064b7cac84e8851996669af96be1273ae46309873a650ff"
)
CONSUMED_L41R5_EVIDENCE_BYTES: Final = 11128
CONSUMED_L41R5_OBSERVATION: Final = "L41R5_SCHEMA_SEMANTIC_RECOVERY"

ACCEPTED_L41R5_BRANCH: Final = "feature/robinhood-live-prototype-current"
ACCEPTED_L41R5_HEAD: Final = "13a97b1f4c369243737cc0ac6646b5520327651a"
ACCEPTED_L41R5_TREE: Final = "81e58dd75656593ca0f960ecdcdf21c14d00d969"

_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")

_ROOT_KEYS = frozenset(
    {
        "attempt_counts",
        "automatic_retry",
        "browser_launches",
        "credential_store_accounting",
        "l41r4_interface_baseline",
        "l41r4_predecessor_evidence",
        "native_credential_read_count",
        "native_credential_write_count",
        "observation",
        "one_shot",
        "provider_numeric_rules_derived",
        "reason",
        "schema",
        "schemas",
        "source",
        "status",
        "structural_fingerprints",
        "trusted_binding",
    }
)
_SOURCE_KEYS = frozenset(
    {
        "branch",
        "feature_authority",
        "head",
        "origin_develop_head",
        "origin_develop_tree",
        "origin_feature_head",
        "origin_feature_tree",
        "prospective_develop_authority",
        "tree",
    }
)
_ATTEMPT_KEYS = frozenset(
    {
        "browser_launches",
        "cancel_equity_order_attempts",
        "get_accounts_attempts",
        "get_equity_tradability_attempts",
        "get_orders_attempts",
        "get_portfolio_attempts",
        "get_positions_attempts",
        "get_quotes_attempts",
        "mcp_session_open_attempts",
        "mcp_tool_invocation_attempts",
        "oauth_scope_entry_attempts",
        "other_tool_attempts",
        "place_equity_order_attempts",
        "review_equity_order_attempts",
        "tools_list_attempts",
    }
)
_L41R4_PREDECESSOR_KEYS = frozenset(
    {
        "evidence_length_bytes",
        "evidence_path",
        "evidence_sha256",
        "observation",
        "reason",
        "source_head",
        "source_tree",
    }
)
_BASELINE_INTERFACE_DIGESTS: Final = {
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
_TOOL_ORDER: Final = tuple(_BASELINE_INTERFACE_DIGESTS)
_FINGERPRINT_KEYS = frozenset(
    {
        "additional_properties_form",
        "additional_properties_present",
        "additional_properties_schema_composition_names",
        "additional_properties_schema_contains_reference",
        "additional_properties_schema_keyword_inventory_sha256",
        "additional_properties_schema_keyword_names",
        "additional_properties_schema_sha256",
        "ambiguity_classes",
        "description_sha256",
        "fields",
        "fractional_precision_conflict",
        "fractional_precision_decimal_places",
        "input_schema_sha256",
        "interface_sha256",
        "nested_description_classification",
        "nested_fractional_precision_decimal_places",
        "property_count",
        "property_inventory_sha256",
        "property_names",
        "required_count",
        "required_inventory_sha256",
        "required_names",
        "required_not_in_properties",
        "schema_keyword_inventory_sha256",
        "schema_keyword_names",
        "tool_description_classification",
        "tool_fractional_precision_decimal_places",
        "tool_name",
        "top_level_type",
    }
)
_FIELD_KEYS = frozenset(
    {
        "classification",
        "default_is_null",
        "default_present",
        "direct_type",
        "logical_non_null_type",
        "nullable",
        "present",
        "required",
        "schema_keyword_inventory_sha256",
        "schema_keyword_names",
        "union_keyword",
        "union_primitive_types",
    }
)


@dataclass(frozen=True, slots=True)
class L41R5FieldSemantics:
    """Minimal JSON-Schema facts for one exact interface field."""

    present: bool
    direct_type: str | None
    logical_non_null_type: str | None
    required: bool
    nullable: bool


@dataclass(frozen=True, slots=True)
class L41R5ToolInterface:
    """Bound interface facts for one of the three consumed L41R4 tools."""

    tool_name: str
    interface_sha256: str
    additional_properties_present: bool
    additional_properties_form: str
    quantity: L41R5FieldSemantics | None
    dollar_amount: L41R5FieldSemantics | None
    fractional_precision_decimal_places: tuple[int, ...]
    fractional_precision_conflict: bool


@dataclass(frozen=True, slots=True)
class ConsumedL41R5InterfaceProvenance:
    """Immutable provenance and interface-only facts from consumed L41R5."""

    evidence_sha256: str
    byte_length: int
    branch: str
    source_head: str
    source_tree: str
    origin_feature_head: str
    origin_feature_tree: str
    origin_develop_head: str
    origin_develop_tree: str
    feature_authority: str
    prospective_develop_authority: str
    tool_interfaces: tuple[L41R5ToolInterface, ...]


def parse_consumed_l41r5_bytes(raw: bytes) -> ConsumedL41R5InterfaceProvenance:
    """Verify the fixed consumed artifact before decoding or exposing facts."""
    return _parse_consumed_l41r5_bytes(
        raw,
        expected_sha256=CONSUMED_L41R5_EVIDENCE_SHA256,
        expected_byte_length=CONSUMED_L41R5_EVIDENCE_BYTES,
    )


def _parse_consumed_l41r5_bytes(
    raw: bytes, *, expected_sha256: str, expected_byte_length: int
) -> ConsumedL41R5InterfaceProvenance:
    """Private digest-injection seam used only by synthetic unit tests."""
    if type(raw) is not bytes:
        raise TypeError("L41R5_CONSUMED_EVIDENCE_BYTES_INVALID")
    if (
        type(expected_sha256) is not str
        or _SHA256.fullmatch(expected_sha256) is None
        or type(expected_byte_length) is not int
        or expected_byte_length < 0
    ):
        raise ValueError("L41R5_CONSUMED_EVIDENCE_EXPECTED_IDENTITY_INVALID")

    if len(raw) != expected_byte_length:
        raise ValueError("L41R5_CONSUMED_EVIDENCE_IDENTITY_MISMATCH")
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError("L41R5_CONSUMED_EVIDENCE_IDENTITY_MISMATCH")

    try:
        document = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise ValueError("L41R5_CONSUMED_EVIDENCE_JSON_INVALID") from None

    return _validate_consumed_l41r5_document(
        document,
        evidence_sha256=actual_sha256,
        byte_length=len(raw),
    )


def _validate_consumed_l41r5_document(
    document: object, *, evidence_sha256: str, byte_length: int
) -> ConsumedL41R5InterfaceProvenance:
    root = _mapping(document, _ROOT_KEYS, "L41R5_CONSUMED_EVIDENCE_SCHEMA_INVALID")
    if root["schema"] != CONSUMED_L41R5_SCHEMA:
        raise ValueError("L41R5_CONSUMED_EVIDENCE_SCHEMA_INVALID")
    if root["status"] != "BLOCKED" or root["reason"] != (
        "L41R5_PLACE_NONPLACEMENT_SEMANTIC_CONFLICT"
    ):
        raise ValueError("L41R5_CONSUMED_EVIDENCE_OUTCOME_INVALID")

    source = _mapping(
        root["source"], _SOURCE_KEYS, "L41R5_CONSUMED_EVIDENCE_SOURCE_INVALID"
    )
    expected_source = {
        "branch": ACCEPTED_L41R5_BRANCH,
        "feature_authority": "PASS",
        "head": ACCEPTED_L41R5_HEAD,
        "origin_develop_head": ACCEPTED_L41R5_HEAD,
        "origin_develop_tree": ACCEPTED_L41R5_TREE,
        "origin_feature_head": ACCEPTED_L41R5_HEAD,
        "origin_feature_tree": ACCEPTED_L41R5_TREE,
        "prospective_develop_authority": "PASS",
        "tree": ACCEPTED_L41R5_TREE,
    }
    if not _strict_equal(source, expected_source):
        raise ValueError("L41R5_CONSUMED_EVIDENCE_SOURCE_INVALID")
    for name in ("head", "origin_develop_head", "origin_feature_head"):
        if type(source[name]) is not str or _SHA1.fullmatch(source[name]) is None:
            raise ValueError("L41R5_CONSUMED_EVIDENCE_SOURCE_INVALID")
    for name in ("tree", "origin_develop_tree", "origin_feature_tree"):
        if type(source[name]) is not str or _SHA1.fullmatch(source[name]) is None:
            raise ValueError("L41R5_CONSUMED_EVIDENCE_SOURCE_INVALID")

    if not _strict_equal(root["attempt_counts"], _EXPECTED_ATTEMPTS):
        raise ValueError("L41R5_CONSUMED_EVIDENCE_ATTEMPTS_INVALID")
    if any(type(count) is not int for count in root["attempt_counts"].values()):
        raise ValueError("L41R5_CONSUMED_EVIDENCE_ATTEMPTS_INVALID")
    _require_exact(
        root["browser_launches"], 0, "L41R5_CONSUMED_EVIDENCE_EFFECTS_INVALID"
    )
    _require_exact(
        root["native_credential_read_count"],
        None,
        "L41R5_CONSUMED_EVIDENCE_EFFECTS_INVALID",
    )
    _require_exact(
        root["native_credential_write_count"],
        None,
        "L41R5_CONSUMED_EVIDENCE_EFFECTS_INVALID",
    )
    _require_exact(
        root["credential_store_accounting"],
        "SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED",
        "L41R5_CONSUMED_EVIDENCE_EFFECTS_INVALID",
    )
    _require_exact(root["one_shot"], True, "L41R5_CONSUMED_EVIDENCE_EFFECTS_INVALID")
    _require_exact(
        root["automatic_retry"],
        "FORBIDDEN",
        "L41R5_CONSUMED_EVIDENCE_EFFECTS_INVALID",
    )
    _require_exact(
        root["trusted_binding"],
        False,
        "L41R5_CONSUMED_EVIDENCE_TRUST_FLAGS_INVALID",
    )
    _require_exact(
        root["provider_numeric_rules_derived"],
        False,
        "L41R5_CONSUMED_EVIDENCE_TRUST_FLAGS_INVALID",
    )
    _require_exact(root["schemas"], [], "L41R5_CONSUMED_EVIDENCE_SCHEMA_INVALID")
    if root["observation"] != CONSUMED_L41R5_OBSERVATION:
        raise ValueError("L41R5_CONSUMED_EVIDENCE_SCHEMA_INVALID")

    expected_baseline = _BASELINE_INTERFACE_DIGESTS
    baseline = _mapping(
        root["l41r4_interface_baseline"],
        frozenset(expected_baseline),
        "L41R5_CONSUMED_EVIDENCE_BASELINE_INVALID",
    )
    if not _strict_equal(baseline, expected_baseline):
        raise ValueError("L41R5_CONSUMED_EVIDENCE_BASELINE_INVALID")

    predecessor = _mapping(
        root["l41r4_predecessor_evidence"],
        _L41R4_PREDECESSOR_KEYS,
        "L41R5_CONSUMED_EVIDENCE_PREDECESSOR_INVALID",
    )
    expected_predecessor = {
        "evidence_length_bytes": 8142,
        "evidence_path": (
            "F:\\AI\\temp\\arch147-l41r4-schema-observation-"
            "7cc31ac681214030b64c8a64ba8679dd\\evidence.json"
        ),
        "evidence_sha256": (
            "BB8A993179A0B8AF4C5F1343B8CFE170B578E413BCE0F95CB40A6F5FB9BA2B25"
        ),
        "observation": "L41R4_SCHEMA_CLASSIFICATION_DIAGNOSTIC",
        "reason": "L41R4_TOP_LEVEL_UNSUPPORTED_CONSTRAINT",
        "source_head": "c343ad83fc86ad1635374b177b27ab52a2da1dde",
        "source_tree": "2411e867f00e11d92ad7cf208684d03518c17731",
    }
    if not _strict_equal(predecessor, expected_predecessor):
        raise ValueError("L41R5_CONSUMED_EVIDENCE_PREDECESSOR_INVALID")

    tools = _parse_interfaces(root["structural_fingerprints"])
    return ConsumedL41R5InterfaceProvenance(
        evidence_sha256=evidence_sha256,
        byte_length=byte_length,
        branch=source["branch"],
        source_head=source["head"],
        source_tree=source["tree"],
        origin_feature_head=source["origin_feature_head"],
        origin_feature_tree=source["origin_feature_tree"],
        origin_develop_head=source["origin_develop_head"],
        origin_develop_tree=source["origin_develop_tree"],
        feature_authority=source["feature_authority"],
        prospective_develop_authority=source["prospective_develop_authority"],
        tool_interfaces=tools,
    )


def _parse_interfaces(value: object) -> tuple[L41R5ToolInterface, ...]:
    if type(value) is not list or len(value) != len(_TOOL_ORDER):
        raise ValueError("L41R5_CONSUMED_EVIDENCE_INTERFACES_INVALID")
    parsed: list[L41R5ToolInterface] = []
    for expected_name, item in zip(_TOOL_ORDER, value, strict=True):
        fingerprint = _mapping(
            item,
            _FINGERPRINT_KEYS,
            "L41R5_CONSUMED_EVIDENCE_INTERFACE_INVALID",
        )
        digest = _BASELINE_INTERFACE_DIGESTS[expected_name]
        if (
            fingerprint["tool_name"] != expected_name
            or fingerprint["interface_sha256"] != digest
        ):
            raise ValueError("L41R5_CONSUMED_EVIDENCE_INTERFACE_INVALID")
        if type(fingerprint["interface_sha256"]) is not str or (
            _SHA256.fullmatch(fingerprint["interface_sha256"]) is None
        ):
            raise ValueError("L41R5_CONSUMED_EVIDENCE_INTERFACE_INVALID")
        _require_exact(
            fingerprint["additional_properties_present"],
            True,
            "L41R5_CONSUMED_EVIDENCE_INTERFACE_INVALID",
        )
        _require_exact(
            fingerprint["additional_properties_form"],
            "BOOLEAN_FALSE",
            "L41R5_CONSUMED_EVIDENCE_INTERFACE_INVALID",
        )
        expected_precision = [] if expected_name == "get_equity_tradability" else [6]
        _require_exact(
            fingerprint["fractional_precision_decimal_places"],
            expected_precision,
            "L41R5_CONSUMED_EVIDENCE_PRECISION_INVALID",
        )
        _require_exact(
            fingerprint["tool_fractional_precision_decimal_places"],
            expected_precision,
            "L41R5_CONSUMED_EVIDENCE_PRECISION_INVALID",
        )
        _require_exact(
            fingerprint["nested_fractional_precision_decimal_places"],
            [],
            "L41R5_CONSUMED_EVIDENCE_PRECISION_INVALID",
        )
        _require_exact(
            fingerprint["fractional_precision_conflict"],
            False,
            "L41R5_CONSUMED_EVIDENCE_PRECISION_INVALID",
        )

        fields = _mapping(
            fingerprint["fields"],
            frozenset({"quantity", "dollar_amount"}),
            "L41R5_CONSUMED_EVIDENCE_FIELDS_INVALID",
        )
        order_tool = expected_name in {"place_equity_order", "review_equity_order"}
        expected_field = (
            _expected_order_field() if order_tool else _expected_absent_field()
        )
        if any(
            not _strict_equal(
                _mapping(
                    fields[field_name],
                    _FIELD_KEYS,
                    "L41R5_CONSUMED_EVIDENCE_FIELD_INVALID",
                ),
                expected_field,
            )
            for field_name in ("quantity", "dollar_amount")
        ):
            raise ValueError("L41R5_CONSUMED_EVIDENCE_FIELD_INVALID")

        # These legacy classifier summaries are intentionally not read or
        # returned: they conflict and are not interface or action authority.
        if type(fingerprint["tool_description_classification"]) is not dict or (
            type(fingerprint["nested_description_classification"]) is not dict
        ):
            raise ValueError("L41R5_CONSUMED_EVIDENCE_INTERFACE_INVALID")

        parsed.append(
            L41R5ToolInterface(
                tool_name=expected_name,
                interface_sha256=digest,
                additional_properties_present=True,
                additional_properties_form="BOOLEAN_FALSE",
                quantity=(
                    L41R5FieldSemantics(True, "string", "string", False, False)
                    if order_tool
                    else None
                ),
                dollar_amount=(
                    L41R5FieldSemantics(True, "string", "string", False, False)
                    if order_tool
                    else None
                ),
                fractional_precision_decimal_places=tuple(expected_precision),
                fractional_precision_conflict=False,
            )
        )
    return tuple(parsed)


def _expected_order_field() -> dict[str, object]:
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


def _expected_absent_field() -> dict[str, object]:
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


_EXPECTED_ATTEMPTS: Final = {
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
}


def _mapping(value: object, keys: frozenset[str], error: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != keys:
        raise ValueError(error)
    if any(type(key) is not str for key in value):
        raise ValueError(error)
    return value


def _strict_equal(actual: object, expected: object) -> bool:
    """Compare JSON values without Python's bool/int equality aliasing."""
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(
            _strict_equal(actual[key], expected[key]) for key in expected
        )
    if type(expected) is list:
        return len(actual) == len(expected) and all(
            _strict_equal(left, right)
            for left, right in zip(actual, expected, strict=True)
        )
    return actual == expected


def _require_exact(actual: object, expected: object, error: str) -> None:
    if not _strict_equal(actual, expected):
        raise ValueError(error)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("L41R5_CONSUMED_EVIDENCE_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-JSON constant: {value}")
