"""Effect-free L41R5 union-aware schema classification successor.

This additive observer composes the reviewed L41R3 metadata-only transport,
retains original interface digests, and records bounded structural diagnostics
before the inherited parser can reject an ambiguous schema.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import re
import stat
import sys
import warnings
import webbrowser
from collections.abc import AsyncIterator, Callable, Iterator, Mapping, Sequence
from contextlib import (
    AbstractAsyncContextManager,
    ExitStack,
    asynccontextmanager,
    contextmanager,
    redirect_stderr,
    redirect_stdout,
)
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from trading_bot.live_prototype.capability_operator import (
    L41_FEATURE_BRANCH,
    SourceAdmission,
    admit_l41_source,
)
from trading_bot.live_prototype.capability_schema_discovery import (
    InterfaceSchemaFacts,
    SchemaDiscoveryAttemptCounts,
    SchemaDiscoveryError,
)
from trading_bot.live_prototype.capability_schema_discovery_l41r3 import (
    L41R3SchemaDiscoveryTransport as _L41R3SchemaDiscoveryTransport,
)
from trading_bot.robinhood_mcp.sdk_transport import ROBINHOOD_TRADING_MCP_URL
from trading_bot.robinhood_mcp.windows_oauth import (
    create_windows_robinhood_oauth_factory,
)

L41R5_EVIDENCE_SCHEMA = "arch147-l41r5-schema-semantic-recovery-observation/v1"
L41R5_OBSERVATION = "L41R5_SCHEMA_SEMANTIC_RECOVERY"
_CANONICAL_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-live-prototype-current")
_EVIDENCE_ROOT = Path(r"F:\AI\temp")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_DISCOVERY_PAGES = 20
_MAX_INVENTORY_NAMES = 32
_MAX_NESTED_DESCRIPTIONS = 512
_MAX_NESTED_DESCRIPTION_BYTES = 262_144
_MISSING = object()
_INSPECTED_TOOLS = frozenset(
    {"review_equity_order", "place_equity_order", "get_equity_tradability"}
)
_REQUIRED_TOOLS = frozenset({"review_equity_order", "place_equity_order"})
_L41R4_INTERFACE_BASELINE = (
    (
        "review_equity_order",
        "5976f7dcf8936e0bb69f0ea2212be6d883654ccb56f4aa4b904c9951160a4069",
    ),
    (
        "place_equity_order",
        "46176dd0342955481cfcfee9f2bc56d92b195110d2bb0168bb0a68a431dacf4a",
    ),
    (
        "get_equity_tradability",
        "7d72877df8976be629e9a508f73ef370cfdd7f62d49938456cd0d624a334f8cf",
    ),
)
_L41R4_PREDECESSOR_EVIDENCE = {
    "source_head": "c343ad83fc86ad1635374b177b27ab52a2da1dde",
    "source_tree": "2411e867f00e11d92ad7cf208684d03518c17731",
    "observation": "L41R4_SCHEMA_CLASSIFICATION_DIAGNOSTIC",
    "reason": "L41R4_TOP_LEVEL_UNSUPPORTED_CONSTRAINT",
    "evidence_path": (
        r"F:\AI\temp\arch147-l41r4-schema-observation-"
        r"7cc31ac681214030b64c8a64ba8679dd\evidence.json"
    ),
    "evidence_sha256": (
        "BB8A993179A0B8AF4C5F1343B8CFE170B578E413BCE0F95CB40A6F5FB9BA2B25"
    ),
    "evidence_length_bytes": 8142,
}
_PRIMITIVE_TYPES = frozenset(
    {"null", "boolean", "object", "array", "number", "integer", "string"}
)
_JSON_SCHEMA_KEYWORDS = frozenset(
    {
        "$comment",
        "$defs",
        "$dynamicAnchor",
        "$dynamicRef",
        "$id",
        "$ref",
        "$schema",
        "$vocabulary",
        "additionalProperties",
        "allOf",
        "anyOf",
        "const",
        "contains",
        "contentEncoding",
        "contentMediaType",
        "contentSchema",
        "default",
        "dependentRequired",
        "dependentSchemas",
        "deprecated",
        "description",
        "else",
        "enum",
        "examples",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "format",
        "if",
        "items",
        "maxContains",
        "maximum",
        "maxItems",
        "maxLength",
        "maxProperties",
        "minContains",
        "minimum",
        "minItems",
        "minLength",
        "minProperties",
        "multipleOf",
        "not",
        "oneOf",
        "pattern",
        "patternProperties",
        "prefixItems",
        "properties",
        "propertyNames",
        "readOnly",
        "required",
        "then",
        "title",
        "type",
        "uniqueItems",
        "unevaluatedItems",
        "unevaluatedProperties",
        "writeOnly",
    }
)
_ANNOTATIONS = frozenset(
    {
        "$comment",
        "default",
        "deprecated",
        "description",
        "examples",
        "readOnly",
        "title",
        "writeOnly",
    }
)
_SAFE_PROPERTY_NAMES = frozenset(
    {
        "account_number",
        "dollar_amount",
        "market_hours",
        "order_id",
        "quantity",
        "ref_id",
        "side",
        "symbol",
        "time_in_force",
        "type",
    }
)
_REASON_CODES = frozenset(
    {
        "L41R5_EVIDENCE_PATH_INVALID",
        "L41R5_SOURCE_ADMISSION_BLOCKED",
        "L41R5_OAUTH_FACTORY_FAILED",
        "L41R5_TRANSPORT_CREATE_FAILED",
        "L41R5_MCP_SESSION_OPEN_FAILED",
        "L41R5_TOOLS_LIST_FAILED",
        "L41R5_TOOL_INVENTORY_MALFORMED",
        "L41R5_TOOL_CURSOR_INVALID",
        "L41R5_TOOL_PAGINATION_BOUND_EXCEEDED",
        "L41R5_REQUIRED_SCHEMA_MISSING",
        "L41R5_DUPLICATE_SCHEMA",
        "L41R5_SCHEMA_CHANGED",
        "L41R5_SCHEMA_MALFORMED",
        "L41R5_REQUIRED_NOT_IN_PROPERTIES",
        "L41R5_QUANTITY_DIRECT_TYPE_MISSING",
        "L41R5_QUANTITY_NULL_ONLY_UNION",
        "L41R5_QUANTITY_MULTI_NON_NULL_UNION",
        "L41R5_QUANTITY_UNRESOLVED_REF",
        "L41R5_QUANTITY_UNSUPPORTED_COMPOSITION",
        "L41R5_QUANTITY_UNSUPPORTED_CONSTRAINT",
        "L41R5_QUANTITY_INVALID_TYPE",
        "L41R5_DOLLAR_AMOUNT_DIRECT_TYPE_MISSING",
        "L41R5_DOLLAR_AMOUNT_NULL_ONLY_UNION",
        "L41R5_DOLLAR_AMOUNT_MULTI_NON_NULL_UNION",
        "L41R5_DOLLAR_AMOUNT_UNRESOLVED_REF",
        "L41R5_DOLLAR_AMOUNT_UNSUPPORTED_COMPOSITION",
        "L41R5_DOLLAR_AMOUNT_UNSUPPORTED_CONSTRAINT",
        "L41R5_DOLLAR_AMOUNT_INVALID_TYPE",
        "L41R5_FRACTIONAL_PRECISION_CONFLICT",
        "L41R5_FRACTIONAL_PRECISION_PROVENANCE_CONFLICT",
        "L41R5_FRACTIONAL_PRECISION_INVALID",
        "L41R5_REVIEW_PLACEMENT_SEMANTIC_CONFLICT",
        "L41R5_PLACE_NONPLACEMENT_SEMANTIC_CONFLICT",
        "L41R5_SCHEMA_DESCRIPTION_MALFORMED",
        "L41R5_ADDITIONAL_PROPERTIES_INVALID",
        "L41R5_ADDITIONAL_PROPERTIES_SCHEMA_UNSUPPORTED",
        "L41R5_TOP_LEVEL_UNRESOLVED_REF",
        "L41R5_TOP_LEVEL_UNSUPPORTED_COMPOSITION",
        "L41R5_TOP_LEVEL_UNSUPPORTED_CONSTRAINT",
        "L41R5_SCHEMA_AMBIGUITY_UNCLASSIFIED",
        "L41R5_SCHEMA_BASELINE_INVALID",
        "L41R5_SESSION_CLOSE_FAILED",
        "L41R5_DISCOVERY_FAILED",
        "L41R5_ATTEMPT_COUNTS_INVALID",
        "L41R5_EVIDENCE_WRITE_FAILED",
        "L41R5_SCHEMA_SEMANTIC_RECOVERY_CAPTURED",
    }
)


class L41R5SchemaDiscoveryError(RuntimeError):
    """Fixed diagnostic with no provider text or secret material."""

    def __init__(self, reason: str) -> None:
        self.reason = reason if reason in _REASON_CODES else "L41R5_DISCOVERY_FAILED"
        super().__init__(self.reason)


class _McpSchemaClient(Protocol):
    async def list_tools(self, *, cursor: str | None = None) -> object: ...


@dataclass(frozen=True, slots=True)
class L41R5SchemaDiscoveryAttemptCounts:
    """Attempt accounting; all MCP tool invocations remain prohibited."""

    oauth_scope_entry_attempts: int = 0
    mcp_session_open_attempts: int = 0
    browser_launches: int = 0
    tools_list_attempts: int = 0
    mcp_tool_invocation_attempts: int = 0
    get_accounts_attempts: int = 0
    get_equity_tradability_attempts: int = 0
    get_positions_attempts: int = 0
    get_orders_attempts: int = 0
    get_portfolio_attempts: int = 0
    get_quotes_attempts: int = 0
    review_equity_order_attempts: int = 0
    place_equity_order_attempts: int = 0
    cancel_equity_order_attempts: int = 0
    other_tool_attempts: int = 0


@dataclass(frozen=True, slots=True)
class L41R5SchemaDiscoveryResult:
    """Sanitized result; CAPTURED_FOR_REVIEW grants no operational authority."""

    status: str
    reason: str
    evidence_path: Path | None
    source: SourceAdmission | None
    attempt_counts: L41R5SchemaDiscoveryAttemptCounts
    schemas: tuple[dict[str, object], ...]
    structural_fingerprints: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class _OAuthFactoryBundle:
    factory: Callable[[], object]
    browser_opener: _OneShotBrowserOpener


class _OneShotBrowserOpener:
    """Permit at most one launch and retain no authorization URL."""

    __slots__ = ("_launch_count", "_opener")

    def __init__(self, opener: Callable[[str], object]) -> None:
        if not callable(opener):
            raise TypeError("browser opener must be callable")
        self._opener = opener
        self._launch_count = 0

    @property
    def launch_count(self) -> int:
        return self._launch_count

    def __call__(self, authorization_url: str) -> object:
        if self._launch_count != 0:
            raise RuntimeError("L41R5_BROWSER_LAUNCH_ALREADY_USED")
        self._launch_count = 1
        try:
            return self._opener(authorization_url)
        finally:
            del authorization_url


def _build_windows_oauth_factory() -> _OAuthFactoryBundle:
    opener = _OneShotBrowserOpener(webbrowser.open)
    factory = create_windows_robinhood_oauth_factory(
        redirect_uri="http://127.0.0.1:8765/robinhood/callback",
        browser_opener=opener,
    )
    return _OAuthFactoryBundle(factory, opener)


@asynccontextmanager
async def _production_session(oauth: object) -> AsyncIterator[_McpSchemaClient]:
    try:
        import httpx2
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client
    except ImportError:
        raise L41R5SchemaDiscoveryError("L41R5_MCP_SESSION_OPEN_FAILED") from None

    try:
        async with httpx2.AsyncClient(auth=oauth, timeout=60) as http:
            async with Client(
                streamable_http_client(
                    ROBINHOOD_TRADING_MCP_URL,
                    http_client=http,
                )
            ) as client:
                yield client
    except SchemaDiscoveryError:
        raise
    except Exception:
        raise L41R5SchemaDiscoveryError("L41R5_MCP_SESSION_OPEN_FAILED") from None


class _ClassificationCapture:
    """Retain only safe facts and original hashes while projecting schemas."""

    __slots__ = ("expected", "fingerprints", "originals", "failure_reason")

    def __init__(self, expected: Mapping[str, str]) -> None:
        if not _valid_schema_baseline(expected):
            raise L41R5SchemaDiscoveryError("L41R5_SCHEMA_BASELINE_INVALID")
        self.expected = expected
        self.fingerprints: dict[str, dict[str, object]] = {}
        self.originals: dict[str, dict[str, object]] = {}
        self.failure_reason: str | None = None

    def inspect(self, name: str, entry: object) -> dict[str, object]:
        description = _read_field(entry, "description")
        if type(description) not in {str, type(None)}:
            self.fingerprints[name] = _empty_fingerprint(
                name, "SCHEMA_DESCRIPTION_MALFORMED"
            )
            self.failure_reason = "L41R5_SCHEMA_DESCRIPTION_MALFORMED"
            raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED")
        try:
            raw_schema = _read_input_schema(entry)
        except SchemaDiscoveryError:
            self.fingerprints[name] = _empty_fingerprint(name, "SCHEMA_MALFORMED")
            self.failure_reason = "L41R5_SCHEMA_MALFORMED"
            raise
        if raw_schema is _MISSING:
            self.fingerprints[name] = _empty_fingerprint(name, "SCHEMA_MALFORMED")
            self.failure_reason = "L41R5_SCHEMA_MALFORMED"
            raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED")
        try:
            original = _original_interface_hashes(name, raw_schema, description)
        except (TypeError, ValueError, RecursionError):
            self.fingerprints[name] = _empty_fingerprint(name, "SCHEMA_MALFORMED")
            self.failure_reason = "L41R5_SCHEMA_MALFORMED"
            raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED") from None
        self.originals[name] = original
        expected = self.expected.get(name)
        if expected is None or expected != original["interface_sha256"]:
            fingerprint = _empty_fingerprint(name, "SCHEMA_CHANGED")
            fingerprint.update(original)
            self.fingerprints[name] = fingerprint
            self.failure_reason = "L41R5_SCHEMA_CHANGED"
            raise SchemaDiscoveryError("L41R1_SCHEMA_CHANGED")
        result = _inspect_schema(name, raw_schema, description, original=original)
        self.fingerprints[name] = result["fingerprint"]
        if result["failure_reason"] is not None:
            self.failure_reason = self.failure_reason or str(result["failure_reason"])
            raise SchemaDiscoveryError("L41R1_SCHEMA_AMBIGUOUS")
        return result


class _ClassifyingMcpClient:
    """Normalize only proven union fields before inherited strict parsing."""

    __slots__ = ("_client", "_capture", "_seen_originals")

    def __init__(self, client: _McpSchemaClient, capture: _ClassificationCapture):
        self._client = client
        self._capture = capture
        self._seen_originals: dict[str, object] = {}

    async def list_tools(self, *, cursor: str | None = None) -> object:
        listing = await self._client.list_tools(cursor=cursor)
        entries = _read_field(listing, "tools")
        if not isinstance(entries, Sequence) or isinstance(
            entries, (str, bytes, bytearray)
        ):
            self._capture.failure_reason = "L41R5_TOOL_INVENTORY_MALFORMED"
            raise SchemaDiscoveryError("L41R1_TOOL_INVENTORY_MALFORMED")

        normalized: list[dict[str, object]] = []
        page_failures: list[str] = []
        for entry in entries:
            name = _read_field(entry, "name")
            if type(name) is not str or not name:
                page_failures.append("L41R5_TOOL_INVENTORY_MALFORMED")
                normalized.append({"name": name})
                continue
            if name not in _INSPECTED_TOOLS:
                normalized.append({"name": name})
                continue
            try:
                item = self._capture.inspect(name, entry)
            except SchemaDiscoveryError:
                page_failures.append(
                    self._capture.failure_reason or "L41R5_SCHEMA_MALFORMED"
                )
                normalized.append({"name": name})
                continue

            digest = item["interface_sha256"]
            if name in self._seen_originals:
                if self._seen_originals[name] != digest:
                    self._capture.failure_reason = "L41R5_SCHEMA_CHANGED"
                    page_failures.append("L41R5_SCHEMA_CHANGED")
                else:
                    self._capture.failure_reason = "L41R5_DUPLICATE_SCHEMA"
                    page_failures.append("L41R5_DUPLICATE_SCHEMA")
            else:
                self._seen_originals[name] = digest
            normalized.append(_tool_projection(entry, item["normalized_schema"]))

        if page_failures:
            reason = page_failures[0]
            self._capture.failure_reason = reason
            inherited = {
                "L41R5_TOOL_INVENTORY_MALFORMED": "L41R1_TOOL_INVENTORY_MALFORMED",
                "L41R5_SCHEMA_MALFORMED": "L41R1_SCHEMA_MALFORMED",
                "L41R5_DUPLICATE_SCHEMA": "L41R1_DUPLICATE_SCHEMA",
                "L41R5_SCHEMA_CHANGED": "L41R1_SCHEMA_CHANGED",
            }.get(reason, "L41R1_SCHEMA_AMBIGUOUS")
            raise SchemaDiscoveryError(inherited)

        return {"tools": normalized, "next_cursor": _read_cursor(listing)}


class _L41R5SchemaDiscoveryTransport:
    """One-use L41R5 transport with no MCP tool-call method."""

    __slots__ = ("_transport", "_capture", "_schemas")

    def __init__(
        self,
        oauth_factory: Callable[[], object],
        *,
        session_factory: Callable[
            [object], AbstractAsyncContextManager[_McpSchemaClient]
        ]
        | None = None,
        expected_schema_digests: Mapping[str, str],
    ) -> None:
        self._capture = _ClassificationCapture(expected_schema_digests)
        self._schemas: tuple[dict[str, object], ...] = ()
        raw_session_factory = (
            _production_session if session_factory is None else session_factory
        )

        @asynccontextmanager
        async def classifying_session(oauth: object) -> AsyncIterator[_McpSchemaClient]:
            async with raw_session_factory(oauth) as client:
                yield _ClassifyingMcpClient(client, self._capture)

        self._transport = _L41R3SchemaDiscoveryTransport(
            oauth_factory,
            session_factory=classifying_session,
            expected_schema_digests=None,
        )

    @property
    def attempt_counts(self) -> SchemaDiscoveryAttemptCounts:
        return self._transport.attempt_counts

    @property
    def schemas(self) -> tuple[dict[str, object], ...]:
        return self._schemas

    @property
    def structural_fingerprints(self) -> tuple[dict[str, object], ...]:
        return tuple(
            self._capture.fingerprints[name]
            for name in sorted(self._capture.fingerprints)
        )

    def __enter__(self) -> _L41R5SchemaDiscoveryTransport:
        self._transport.__enter__()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return self._transport.__exit__(exc_type, exc, traceback)

    def discover(self) -> tuple[dict[str, object], ...]:
        try:
            inherited = self._transport.discover()
        except SchemaDiscoveryError as error:
            if self._capture.failure_reason is not None:
                raise L41R5SchemaDiscoveryError(self._capture.failure_reason) from None
            raise L41R5SchemaDiscoveryError(
                _map_inherited_reason(error.reason)
            ) from None
        except Exception as error:
            reason = getattr(error, "reason", None)
            if self._capture.failure_reason is not None:
                mapped = self._capture.failure_reason
            elif type(reason) is str and reason == "L41R3_MCP_SESSION_OPEN_FAILED":
                mapped = "L41R5_MCP_SESSION_OPEN_FAILED"
            else:
                mapped = "L41R5_DISCOVERY_FAILED"
            raise L41R5SchemaDiscoveryError(mapped) from None

        records: list[dict[str, object]] = []
        expected = self._capture.expected
        for facts in inherited:
            original = self._capture.originals.get(facts.tool_name)
            fingerprint = self._capture.fingerprints.get(facts.tool_name)
            if original is None or fingerprint is None:
                raise L41R5SchemaDiscoveryError("L41R5_SCHEMA_AMBIGUITY_UNCLASSIFIED")
            interface_digest = original["interface_sha256"]
            if expected is not None and facts.tool_name in expected:
                if expected[facts.tool_name] != interface_digest:
                    self._capture.failure_reason = "L41R5_SCHEMA_CHANGED"
                    raise L41R5SchemaDiscoveryError("L41R5_SCHEMA_CHANGED")
            records.append(_schema_record(facts, original, fingerprint, expected))
        self._schemas = tuple(records)
        if expected is not None and not set(expected).issubset(
            {facts.tool_name for facts in inherited}
        ):
            self._capture.failure_reason = "L41R5_REQUIRED_SCHEMA_MISSING"
            raise L41R5SchemaDiscoveryError("L41R5_REQUIRED_SCHEMA_MISSING")
        return self._schemas


def _inspect_schema(
    name: str,
    schema: object,
    description: object,
    *,
    original: Mapping[str, str] | None = None,
) -> dict[str, object]:
    try:
        original_facts = (
            _original_interface_hashes(name, schema, description)
            if original is None
            else dict(original)
        )
    except (TypeError, ValueError, RecursionError):
        fingerprint = _empty_fingerprint(name, "SCHEMA_MALFORMED")
        return {
            "fingerprint": fingerprint,
            "normalized_schema": schema,
            "input_schema_sha256": None,
            "description_sha256": None,
            "interface_sha256": None,
            "failure_reason": "L41R5_SCHEMA_MALFORMED",
        }
    schema_hash = original_facts["input_schema_sha256"]
    description_hash = original_facts["description_sha256"]
    interface_hash = original_facts["interface_sha256"]
    if not isinstance(schema, Mapping) or any(type(key) is not str for key in schema):
        fingerprint = _empty_fingerprint(name, "SCHEMA_MALFORMED")
        fingerprint.update(original_facts)
        return {
            "fingerprint": fingerprint,
            "normalized_schema": schema,
            **original_facts,
            "failure_reason": "L41R5_SCHEMA_MALFORMED",
        }

    anomalies: list[str] = []
    schema_type = schema.get("type")
    top_type = _safe_type(schema_type if "type" in schema else _MISSING)
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    valid_props = isinstance(properties, Mapping) and all(
        type(key) is str for key in properties
    )
    valid_required = (
        isinstance(required, list)
        and all(type(item) is str for item in required)
        and len(set(required)) == len(required)
    )
    if "type" in schema and schema_type != "object":
        anomalies.append("L41R5_SCHEMA_MALFORMED")
    if not valid_props or not valid_required:
        anomalies.append("L41R5_SCHEMA_MALFORMED")
        properties = {} if not valid_props else properties
        required = [] if not valid_required else required
    if valid_props and any(
        not isinstance(value, Mapping) for value in properties.values()
    ):
        anomalies.append("L41R5_SCHEMA_MALFORMED")

    additional_facts, additional_failure = _additional_properties_facts(schema)
    top_level_reason: str | None = None
    if "$ref" in schema:
        top_level_reason = "L41R5_TOP_LEVEL_UNRESOLVED_REF"
    elif any(key in schema for key in ("allOf", "anyOf", "oneOf")):
        top_level_reason = "L41R5_TOP_LEVEL_UNSUPPORTED_COMPOSITION"
    elif additional_failure is not None:
        top_level_reason = additional_failure
    elif set(schema) - (
        _ANNOTATIONS | {"type", "properties", "required", "additionalProperties"}
    ):
        top_level_reason = "L41R5_TOP_LEVEL_UNSUPPORTED_CONSTRAINT"
    if top_level_reason is not None:
        anomalies.append(top_level_reason)

    property_names = sorted(properties) if valid_props else []
    required_names = sorted(required) if valid_required else []
    missing_required = (
        sorted(set(required_names) - set(property_names))
        if valid_props and valid_required
        else []
    )
    if missing_required:
        anomalies.append("L41R5_REQUIRED_NOT_IN_PROPERTIES")

    tool_description_malformed = type(description) not in {str, type(None)}
    tool_description = description if type(description) is str else ""
    nested_descriptions, malformed_nested = _schema_descriptions(schema)
    if tool_description_malformed or malformed_nested:
        anomalies.append("L41R5_SCHEMA_DESCRIPTION_MALFORMED")
        nested_descriptions = [] if malformed_nested else nested_descriptions
    tool_description_facts = _description_facts(tool_description)
    nested_description_facts = _aggregate_description_facts(nested_descriptions)
    if (
        name == "review_equity_order"
        and tool_description_facts["explicitly_placing"] is True
    ):
        anomalies.append("L41R5_REVIEW_PLACEMENT_SEMANTIC_CONFLICT")
    if (
        name == "place_equity_order"
        and tool_description_facts["explicitly_nonplacing"] is True
    ):
        anomalies.append("L41R5_PLACE_NONPLACEMENT_SEMANTIC_CONFLICT")

    tool_precision = _fractional_precision_values(tool_description)
    nested_precision_values: set[int] = set()
    for nested_description in nested_descriptions:
        nested_precision_values.update(_fractional_precision_values(nested_description))
    nested_precision = tuple(sorted(nested_precision_values))
    precision_values = tuple(sorted(set(tool_precision) | set(nested_precision)))
    precision_conflict = (
        len(tool_precision) > 1
        or len(nested_precision) > 1
        or bool(
            tool_precision
            and nested_precision
            and set(tool_precision) != set(nested_precision)
        )
    )
    if precision_conflict:
        anomalies.append("L41R5_FRACTIONAL_PRECISION_PROVENANCE_CONFLICT")
    elif precision_values and precision_values[0] < 1:
        anomalies.append("L41R5_FRACTIONAL_PRECISION_INVALID")

    field_facts: dict[str, dict[str, object]] = {}
    normalized_schema = _schema_projection_without_descriptions(
        schema,
        omit_boolean_additional_properties=additional_facts[
            "additional_properties_form"
        ]
        in {"BOOLEAN_TRUE", "BOOLEAN_FALSE"},
    )
    normalized_properties = normalized_schema.get("properties", {})
    for field_name in ("quantity", "dollar_amount"):
        fact, field_anomalies, logical_type = _field_facts(
            field_name,
            properties.get(field_name, _MISSING),
            present=field_name in properties,
            required=field_name in required,
        )
        if top_level_reason is not None:
            fact["nullable"] = None
            fact["logical_non_null_type"] = None
            fact["classification"] = top_level_reason.removeprefix("L41R5_")
            logical_type = None
        field_facts[field_name] = fact
        anomalies.extend(field_anomalies)
        if field_name == "quantity" and logical_type is not None:
            normalized_schema = _project_quantity_type(
                normalized_schema,
                normalized_properties,
                logical_type,
            )

    unique_anomalies = list(dict.fromkeys(anomalies))
    failure_reason = unique_anomalies[0] if unique_anomalies else None
    action_state = _action_state(tool_description_facts)
    fingerprint = {
        "tool_name": name,
        "input_schema_sha256": schema_hash,
        "description_sha256": description_hash,
        "interface_sha256": interface_hash,
        "schema_keyword_names": _safe_keyword_inventory(sorted(schema)),
        "schema_keyword_inventory_sha256": _name_inventory_digest(sorted(schema)),
        "top_level_type": top_type,
        "property_count": min(len(property_names), 5000),
        "property_names": _safe_name_inventory(property_names),
        "property_inventory_sha256": _name_inventory_digest(property_names),
        "required_count": min(len(required_names), 5000),
        "required_names": _safe_name_inventory(required_names),
        "required_inventory_sha256": _name_inventory_digest(required_names),
        "required_not_in_properties": _safe_name_inventory(missing_required),
        **additional_facts,
        "tool_description_classification": {
            **tool_description_facts,
            "action_semantics": action_state,
            "malformed": tool_description_malformed,
        },
        "nested_description_classification": {
            **nested_description_facts,
            "description_count": min(
                len(nested_descriptions), _MAX_NESTED_DESCRIPTIONS
            ),
            "description_sha256": _description_inventory_sha256(nested_descriptions),
            "malformed": malformed_nested,
        },
        "tool_fractional_precision_decimal_places": list(tool_precision[:8]),
        "nested_fractional_precision_decimal_places": list(nested_precision[:8]),
        "fractional_precision_decimal_places": list(precision_values[:8]),
        "fractional_precision_conflict": precision_conflict,
        "fields": field_facts,
        "ambiguity_classes": unique_anomalies,
    }
    return {
        "fingerprint": fingerprint,
        "normalized_schema": normalized_schema,
        **original_facts,
        "failure_reason": failure_reason,
    }


def _field_facts(
    field_name: str,
    raw_schema: object,
    *,
    present: bool,
    required: bool,
) -> tuple[dict[str, object], list[str], str | None]:
    prefix = "QUANTITY" if field_name == "quantity" else "DOLLAR_AMOUNT"
    fact: dict[str, object] = {
        "present": present,
        "required": required,
        "schema_keyword_names": [],
        "schema_keyword_inventory_sha256": None,
        "direct_type": "MISSING",
        "nullable": None if present else False,
        "union_keyword": "none",
        "union_primitive_types": [],
        "logical_non_null_type": None,
        "default_present": False,
        "default_is_null": None,
        "classification": "ABSENT",
    }
    if not present:
        return fact, [], None
    if not isinstance(raw_schema, Mapping):
        fact["classification"] = "FIELD_SCHEMA_MALFORMED"
        return fact, ["L41R5_SCHEMA_MALFORMED"], None

    field_keywords = sorted(key for key in raw_schema if type(key) is str)
    fact["schema_keyword_names"] = _safe_keyword_inventory(field_keywords)
    fact["schema_keyword_inventory_sha256"] = _name_inventory_digest(field_keywords)
    fact["default_present"] = "default" in raw_schema
    fact["default_is_null"] = (
        raw_schema.get("default") is None if "default" in raw_schema else None
    )
    for keyword in ("$ref", "allOf", "anyOf", "oneOf"):
        if keyword in raw_schema:
            fact["union_keyword"] = "ref" if keyword == "$ref" else keyword
            break

    if "$ref" in raw_schema:
        fact["classification"] = "UNRESOLVED_REF"
        return fact, [f"L41R5_{prefix}_UNRESOLVED_REF"], None
    composition_keys = [key for key in ("allOf", "anyOf", "oneOf") if key in raw_schema]
    if composition_keys:
        keyword = composition_keys[0]
        fact["union_keyword"] = keyword
        known_types, has_reference = _branch_type_inventory(
            [raw_schema.get(key) for key in composition_keys]
        )
        fact["union_primitive_types"] = known_types
        non_null_types = sorted(set(known_types) - {"null"})
        if has_reference:
            fact["classification"] = "UNRESOLVED_REF"
            return fact, [f"L41R5_{prefix}_UNRESOLVED_REF"], None
        if "allOf" in composition_keys or len(composition_keys) > 1:
            fact["classification"] = "UNSUPPORTED_COMPOSITION"
            return fact, [f"L41R5_{prefix}_UNSUPPORTED_COMPOSITION"], None
        if len(non_null_types) > 1:
            fact["classification"] = "MULTI_NON_NULL_UNION"
            return fact, [f"L41R5_{prefix}_MULTI_NON_NULL_UNION"], None
        logical_type = _simple_nullable_branches(raw_schema.get(keyword))
        if logical_type is None:
            fact["classification"] = "UNSUPPORTED_COMPOSITION"
            return fact, [f"L41R5_{prefix}_UNSUPPORTED_COMPOSITION"], None
        if logical_type != "string":
            fact["classification"] = "UNSUPPORTED_COMPOSITION"
            return fact, [f"L41R5_{prefix}_UNSUPPORTED_COMPOSITION"], None
        if set(raw_schema) - (_ANNOTATIONS | {keyword}):
            fact["classification"] = "UNSUPPORTED_CONSTRAINT"
            return fact, [f"L41R5_{prefix}_UNSUPPORTED_CONSTRAINT"], None
        fact["nullable"] = True
        fact["union_primitive_types"] = ["null", "string"]
        fact["logical_non_null_type"] = logical_type
        fact["classification"] = _nullable_classification(prefix, logical_type)
        return fact, [], logical_type

    raw_type = raw_schema.get("type", _MISSING)
    if raw_type is _MISSING:
        fact["classification"] = "DIRECT_TYPE_MISSING"
        return fact, [f"L41R5_{prefix}_DIRECT_TYPE_MISSING"], None
    if type(raw_type) is str:
        if raw_type not in _PRIMITIVE_TYPES:
            fact["direct_type"] = "UNRECOGNIZED"
            fact["classification"] = "INVALID_TYPE"
            return fact, [f"L41R5_{prefix}_INVALID_TYPE"], None
        fact["direct_type"] = raw_type
        if raw_type == "null":
            if set(raw_schema) - (_ANNOTATIONS | {"type"}):
                fact["classification"] = "UNSUPPORTED_CONSTRAINT"
                return fact, [f"L41R5_{prefix}_UNSUPPORTED_CONSTRAINT"], None
            fact["classification"] = "NULL_ONLY"
            fact["nullable"] = True
            fact["union_primitive_types"] = ["null"]
            return fact, [f"L41R5_{prefix}_NULL_ONLY_UNION"], None
        fact["nullable"] = False
        allowed = _ANNOTATIONS | {"type"}
        if set(raw_schema) - allowed:
            fact["classification"] = "UNSUPPORTED_CONSTRAINT"
            return fact, [f"L41R5_{prefix}_UNSUPPORTED_CONSTRAINT"], None
        fact["logical_non_null_type"] = raw_type
        fact["classification"] = "DIRECT_TYPE"
        return fact, [], raw_type
    if isinstance(raw_type, list):
        fact["direct_type"] = "TYPE_LIST"
        fact["union_keyword"] = "type_list"
        parsed = _type_list(raw_type)
        if parsed is None:
            fact["classification"] = "INVALID_TYPE"
            return fact, [f"L41R5_{prefix}_INVALID_TYPE"], None
        non_null = sorted(set(parsed) - {"null"})
        fact["union_primitive_types"] = sorted(set(parsed))
        if set(raw_schema) - (_ANNOTATIONS | {"type"}):
            fact["classification"] = "UNSUPPORTED_CONSTRAINT"
            return fact, [f"L41R5_{prefix}_UNSUPPORTED_CONSTRAINT"], None
        if not non_null:
            fact["classification"] = "NULL_ONLY"
            fact["nullable"] = True
            return fact, [f"L41R5_{prefix}_NULL_ONLY_UNION"], None
        if len(non_null) != 1:
            fact["classification"] = "MULTI_NON_NULL_UNION"
            return fact, [f"L41R5_{prefix}_MULTI_NON_NULL_UNION"], None
        logical_type = non_null[0]
        if set(parsed) != {"string", "null"}:
            fact["classification"] = "UNSUPPORTED_COMPOSITION"
            return fact, [f"L41R5_{prefix}_UNSUPPORTED_COMPOSITION"], None
        fact["nullable"] = True
        fact["logical_non_null_type"] = logical_type
        fact["classification"] = (
            _nullable_classification(prefix, logical_type)
            if "null" in parsed
            else "SINGLE_NON_NULL_TYPE_LIST"
        )
        return fact, [], logical_type
    fact["direct_type"] = "UNRECOGNIZED"
    fact["classification"] = "INVALID_TYPE"
    return fact, [f"L41R5_{prefix}_INVALID_TYPE"], None


def _nullable_classification(prefix: str, logical_type: str) -> str:
    if logical_type == "string":
        return f"{prefix}_NULLABLE_STRING"
    return "SUPPORTED_NULLABLE_UNION"


def _type_list(value: list[object]) -> list[str] | None:
    if not value or len(value) > len(_PRIMITIVE_TYPES):
        return None
    if any(type(item) is not str or item not in _PRIMITIVE_TYPES for item in value):
        return None
    if len(set(value)) != len(value):
        return None
    return list(value)


def _simple_nullable_branches(branches: object) -> str | None:
    if not isinstance(branches, list) or len(branches) != 2:
        return None
    values: list[str] = []
    for branch in branches:
        if not isinstance(branch, Mapping):
            return None
        if set(branch) - (_ANNOTATIONS | {"type"}):
            return None
        value = branch.get("type", _MISSING)
        if type(value) is not str or value not in _PRIMITIVE_TYPES:
            return None
        values.append(value)
    if len(set(values)) != 2 or "null" not in values:
        return None
    logical_type = next(value for value in values if value != "null")
    return logical_type if logical_type == "string" else None


def _branch_type_inventory(value: object) -> tuple[list[str], bool]:
    found: set[str] = set()
    has_reference = False

    def visit(node: object, depth: int) -> None:
        nonlocal has_reference
        if depth > 4:
            return
        if isinstance(node, Mapping):
            has_reference = has_reference or "$ref" in node
            raw_type = node.get("type", _MISSING)
            if type(raw_type) is str and raw_type in _PRIMITIVE_TYPES:
                found.add(raw_type)
            elif isinstance(raw_type, list):
                for item in raw_type[:8]:
                    if type(item) is str and item in _PRIMITIVE_TYPES:
                        found.add(item)
            for keyword in ("anyOf", "oneOf", "allOf"):
                children = node.get(keyword)
                if isinstance(children, list):
                    for child in children[:16]:
                        visit(child, depth + 1)
        elif isinstance(node, list):
            for child in node[:16]:
                visit(child, depth + 1)

    visit(value, 0)
    return sorted(found), has_reference


def _project_quantity_type(
    schema: object, properties: Mapping[str, object], logical_type: str
) -> object:
    if not isinstance(schema, Mapping):
        return schema
    field = properties.get("quantity")
    if not isinstance(field, Mapping):
        return schema
    normalized_field = dict(field)
    normalized_field["type"] = logical_type
    normalized_properties = dict(properties)
    normalized_properties["quantity"] = normalized_field
    normalized_schema = dict(schema)
    normalized_schema["properties"] = normalized_properties
    return normalized_schema


def _schema_record(
    facts: InterfaceSchemaFacts,
    original: Mapping[str, str],
    fingerprint: Mapping[str, object],
    expected: Mapping[str, str],
) -> dict[str, object]:
    fields = fingerprint.get("fields", {})
    assert isinstance(fields, Mapping)
    quantity = fields.get("quantity", {})
    dollars = fields.get("dollar_amount", {})
    tool_description = fingerprint.get("tool_description_classification", {})
    nested_description = fingerprint.get("nested_description_classification", {})
    assert isinstance(quantity, Mapping) and isinstance(dollars, Mapping)
    assert isinstance(tool_description, Mapping) and isinstance(
        nested_description, Mapping
    )
    digest_checked = expected.get(facts.tool_name) == original["interface_sha256"]
    return {
        "tool_name": facts.tool_name,
        "input_schema_sha256": original["input_schema_sha256"],
        "description_sha256": original["description_sha256"],
        "interface_sha256": original["interface_sha256"],
        "quantity_field_present": quantity.get("present"),
        "quantity_field_required": quantity.get("required"),
        "quantity_logical_non_null_type": quantity.get("logical_non_null_type"),
        "quantity_nullable": quantity.get("nullable"),
        "dollar_amount_field_present": dollars.get("present"),
        "dollar_amount_field_required": dollars.get("required"),
        "dollar_amount_logical_non_null_type": dollars.get("logical_non_null_type"),
        "dollar_amount_nullable": dollars.get("nullable"),
        "regular_hours_fractional_market_precision_decimal_places": (
            fingerprint["fractional_precision_decimal_places"][0]
            if len(fingerprint.get("fractional_precision_decimal_places", [])) == 1
            and fingerprint.get("fractional_precision_conflict") is False
            else None
        ),
        "fractional_precision_decimal_places": fingerprint.get(
            "fractional_precision_decimal_places", []
        ),
        "tool_fractional_precision_decimal_places": (
            fingerprint.get("tool_fractional_precision_decimal_places", [])
        ),
        "nested_fractional_precision_decimal_places": (
            fingerprint.get("nested_fractional_precision_decimal_places", [])
        ),
        "fractional_precision_conflict": fingerprint.get(
            "fractional_precision_conflict", False
        ),
        "tool_description_classification": dict(tool_description),
        "nested_description_classification": dict(nested_description),
        "review_semantics": (
            "SIMULATION_PRETRADE_WARNING"
            if facts.tool_name == "review_equity_order"
            and tool_description.get("mentions_simulation") is True
            and tool_description.get("mentions_pretrade") is True
            and tool_description.get("mentions_warning_or_alert") is True
            and tool_description.get("explicitly_nonplacing") is True
            else "UNKNOWN"
        ),
        "placement_semantics": tool_description.get("action_semantics", "UNKNOWN"),
        "review_is_placement": (
            True
            if tool_description.get("explicitly_placing") is True
            else False
            if tool_description.get("explicitly_nonplacing") is True
            else None
        ),
        "additional_properties_present": fingerprint.get(
            "additional_properties_present", False
        ),
        "additional_properties_form": fingerprint.get(
            "additional_properties_form", "MISSING"
        ),
        "additional_properties_schema_sha256": fingerprint.get(
            "additional_properties_schema_sha256"
        ),
        "additional_properties_schema_keyword_names": fingerprint.get(
            "additional_properties_schema_keyword_names", []
        ),
        "additional_properties_schema_keyword_inventory_sha256": fingerprint.get(
            "additional_properties_schema_keyword_inventory_sha256"
        ),
        "schema_baseline_checked": digest_checked,
    }


def _tool_projection(entry: object, schema: object) -> dict[str, object]:
    result: dict[str, object] = {
        "name": _read_field(entry, "name"),
        "inputSchema": schema,
    }
    description = _read_field(entry, "description")
    if description is not None:
        result["description"] = description
    return result


def _read_field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _read_input_schema(entry: object) -> object:
    if isinstance(entry, Mapping):
        if "inputSchema" in entry and "input_schema" in entry:
            raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED")
        return entry.get("inputSchema", entry.get("input_schema", _MISSING))
    v2_schema = getattr(entry, "input_schema", _MISSING)
    legacy_schema = getattr(entry, "inputSchema", _MISSING)
    if v2_schema is not _MISSING and legacy_schema is not _MISSING:
        raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED")
    return legacy_schema if v2_schema is _MISSING else v2_schema


def _read_cursor(listing: object) -> object:
    if isinstance(listing, Mapping):
        snake = listing.get("next_cursor", _MISSING)
        wire = listing.get("nextCursor", _MISSING)
    else:
        snake = getattr(listing, "next_cursor", _MISSING)
        wire = getattr(listing, "nextCursor", _MISSING)
    if snake is _MISSING:
        return None if wire is _MISSING else wire
    if wire is _MISSING:
        return snake
    if type(snake) is not str and snake is not None:
        raise SchemaDiscoveryError("L41R1_TOOL_CURSOR_INVALID")
    if type(wire) is not str and wire is not None:
        raise SchemaDiscoveryError("L41R1_TOOL_CURSOR_INVALID")
    if snake != wire:
        raise SchemaDiscoveryError("L41R1_TOOL_CURSOR_INVALID")
    return snake


def _safe_type(value: object) -> str:
    if value is _MISSING:
        return "MISSING"
    if type(value) is str and value in _PRIMITIVE_TYPES:
        return value
    if isinstance(value, list):
        return "TYPE_LIST" if _type_list(value) is not None else "UNRECOGNIZED"
    return "UNRECOGNIZED"


def _safe_name_inventory(names: Sequence[str]) -> list[str]:
    safe = sorted(
        name if name in _SAFE_PROPERTY_NAMES else "other_sha256:" + _sha256_text(name)
        for name in names
    )
    if len(safe) <= _MAX_INVENTORY_NAMES:
        return safe
    return safe[:_MAX_INVENTORY_NAMES] + [
        f"truncated:{len(safe) - _MAX_INVENTORY_NAMES}:sha256:"
        + _name_inventory_digest(names)
    ]


def _safe_keyword_inventory(names: Sequence[str]) -> list[str]:
    safe = sorted(
        name if name in _JSON_SCHEMA_KEYWORDS else "other_sha256:" + _sha256_text(name)
        for name in names
    )
    if len(safe) <= _MAX_INVENTORY_NAMES:
        return safe
    return safe[:_MAX_INVENTORY_NAMES] + [
        f"truncated:{len(safe) - _MAX_INVENTORY_NAMES}:sha256:"
        + _name_inventory_digest(names)
    ]


def _name_inventory_digest(names: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(names):
        raw = name.encode("utf-8", errors="replace")
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _empty_fingerprint(name: str, category: str) -> dict[str, object]:
    return {
        "tool_name": name,
        "input_schema_sha256": None,
        "description_sha256": None,
        "interface_sha256": None,
        "schema_keyword_names": [],
        "schema_keyword_inventory_sha256": None,
        "top_level_type": "MALFORMED",
        "property_count": 0,
        "property_names": [],
        "property_inventory_sha256": None,
        "required_count": 0,
        "required_names": [],
        "required_inventory_sha256": None,
        "required_not_in_properties": [],
        "additional_properties_present": False,
        "additional_properties_form": "MISSING",
        "additional_properties_schema_sha256": None,
        "additional_properties_schema_keyword_names": [],
        "additional_properties_schema_keyword_inventory_sha256": None,
        "additional_properties_schema_contains_reference": False,
        "additional_properties_schema_composition_names": [],
        "tool_description_classification": {
            **_description_facts(""),
            "action_semantics": "UNKNOWN",
            "malformed": False,
        },
        "nested_description_classification": {
            **_aggregate_description_facts([]),
            "action_semantics": "UNKNOWN",
            "description_count": 0,
            "description_sha256": _description_inventory_sha256([]),
            "malformed": False,
        },
        "tool_fractional_precision_decimal_places": [],
        "nested_fractional_precision_decimal_places": [],
        "fractional_precision_decimal_places": [],
        "fractional_precision_conflict": False,
        "fields": {
            "quantity": _field_facts(
                "quantity", _MISSING, present=False, required=False
            )[0],
            "dollar_amount": _field_facts(
                "dollar_amount", _MISSING, present=False, required=False
            )[0],
        },
        "ambiguity_classes": [category],
    }


def _original_interface_hashes(
    name: str, schema: object, description: object
) -> dict[str, str]:
    if type(name) is not str or not name or type(description) not in {str, type(None)}:
        raise ValueError("invalid original interface")
    description_text = "" if description is None else description
    schema_bytes = _canonical_json(schema)
    description_bytes = description_text.encode("utf-8")
    interface_bytes = _canonical_json(
        {"name": name, "inputSchema": schema, "description": description_text}
    )
    return {
        "input_schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
        "description_sha256": hashlib.sha256(description_bytes).hexdigest(),
        "interface_sha256": hashlib.sha256(interface_bytes).hexdigest(),
    }


def _additional_properties_facts(
    schema: Mapping[str, object],
) -> tuple[dict[str, object], str | None]:
    present = "additionalProperties" in schema
    empty: dict[str, object] = {
        "additional_properties_present": present,
        "additional_properties_form": "MISSING",
        "additional_properties_schema_sha256": None,
        "additional_properties_schema_keyword_names": [],
        "additional_properties_schema_keyword_inventory_sha256": None,
        "additional_properties_schema_contains_reference": False,
        "additional_properties_schema_composition_names": [],
    }
    if not present:
        return empty, None
    value = schema["additionalProperties"]
    if type(value) is bool:
        empty["additional_properties_form"] = (
            "BOOLEAN_TRUE" if value else "BOOLEAN_FALSE"
        )
        return empty, None
    if not isinstance(value, Mapping):
        empty["additional_properties_form"] = "INVALID"
        return empty, "L41R5_ADDITIONAL_PROPERTIES_INVALID"
    try:
        schema_bytes = _canonical_json(value)
        names = sorted(value)
        if any(type(name) is not str for name in names):
            raise ValueError("invalid schema keyword")
        has_reference, compositions = _schema_structure_markers(value)
    except (TypeError, ValueError, RecursionError):
        empty["additional_properties_form"] = "INVALID"
        return empty, "L41R5_ADDITIONAL_PROPERTIES_INVALID"
    empty.update(
        {
            "additional_properties_form": "SCHEMA_MAPPING",
            "additional_properties_schema_sha256": hashlib.sha256(
                schema_bytes
            ).hexdigest(),
            "additional_properties_schema_keyword_names": _safe_keyword_inventory(
                names
            ),
            "additional_properties_schema_keyword_inventory_sha256": (
                _name_inventory_digest(names)
            ),
            "additional_properties_schema_contains_reference": has_reference,
            "additional_properties_schema_composition_names": compositions,
        }
    )
    return empty, "L41R5_ADDITIONAL_PROPERTIES_SCHEMA_UNSUPPORTED"


def _schema_structure_markers(value: object) -> tuple[bool, list[str]]:
    found: set[str] = set()
    has_reference = False
    remaining = [4096]

    def visit(node: object, depth: int) -> None:
        nonlocal has_reference
        remaining[0] -= 1
        if remaining[0] < 0 or depth > 32:
            raise ValueError("schema structure bound exceeded")
        if isinstance(node, Mapping):
            for key, child in node.items():
                if type(key) is not str:
                    raise ValueError("schema keyword malformed")
                if key in {"$ref", "$dynamicRef", "$recursiveRef"}:
                    has_reference = True
                if key in {"allOf", "anyOf", "oneOf"}:
                    found.add(key)
                visit(child, depth + 1)
        elif isinstance(node, (list, tuple)):
            for child in node:
                visit(child, depth + 1)

    visit(value, 0)
    return has_reference, sorted(found)


def _schema_projection_without_descriptions(
    schema: Mapping[str, object], *, omit_boolean_additional_properties: bool
) -> dict[str, object]:
    remaining = [20_000]

    def project(value: object, depth: int) -> object:
        remaining[0] -= 1
        if remaining[0] < 0 or depth > 64:
            raise ValueError("schema projection bound exceeded")
        if isinstance(value, Mapping):
            result: dict[str, object] = {}
            for key, child in value.items():
                if type(key) is not str:
                    raise ValueError("schema key malformed")
                if key == "description":
                    continue
                result[key] = project(child, depth + 1)
            return result
        if isinstance(value, (list, tuple)):
            return [project(child, depth + 1) for child in value]
        return value

    result = project(schema, 0)
    assert isinstance(result, dict)
    if omit_boolean_additional_properties:
        result.pop("additionalProperties", None)
    return result


def _aggregate_description_facts(descriptions: Sequence[str]) -> dict[str, bool]:
    keys = (
        "mentions_simulation",
        "mentions_pretrade",
        "mentions_warning_or_alert",
        "explicitly_nonplacing",
        "explicitly_placing",
    )
    result = {key: False for key in keys}
    for description in descriptions:
        facts = _description_facts(description)
        for key in keys:
            result[key] = result[key] or facts[key]
    return result


def _description_inventory_sha256(descriptions: Sequence[str]) -> str | None:
    try:
        return hashlib.sha256(_canonical_json(list(descriptions))).hexdigest()
    except (TypeError, ValueError, RecursionError):
        return None


def _action_state(facts: Mapping[str, object]) -> str:
    places = facts.get("explicitly_placing") is True
    nonplaces = facts.get("explicitly_nonplacing") is True
    if places and nonplaces:
        return "CONFLICTING"
    if places:
        return "PLACING"
    if nonplaces:
        return "NONPLACING"
    return "UNKNOWN"


def _schema_descriptions(value: object) -> tuple[list[str], bool]:
    descriptions: list[str] = []
    malformed = False
    total_bytes = [0]

    def visit(node: object, depth: int) -> None:
        nonlocal malformed
        if malformed:
            return
        if depth > 64 or len(descriptions) > _MAX_NESTED_DESCRIPTIONS:
            malformed = True
            return
        if isinstance(node, Mapping):
            for key, item in node.items():
                if key == "description":
                    if type(item) is not str:
                        malformed = True
                        return
                    total_bytes[0] += len(item.encode("utf-8", errors="replace"))
                    if total_bytes[0] > _MAX_NESTED_DESCRIPTION_BYTES:
                        malformed = True
                        return
                    descriptions.append(item)
                    if len(descriptions) > _MAX_NESTED_DESCRIPTIONS:
                        malformed = True
                        return
                else:
                    visit(item, depth + 1)
                    if malformed:
                        return
        elif isinstance(node, (list, tuple)):
            if len(node) > 4096:
                malformed = True
                return
            for item in node:
                visit(item, depth + 1)
                if malformed:
                    return

    visit(value, 0)
    return descriptions, malformed


def _description_facts(description: str) -> dict[str, bool]:
    lowered = description.casefold()
    negative_patterns = (
        r"\bwithout\s+(?:placing|submitting|executing)\b(?:\s+(?:an?\s+)?orders?)?",
        r"\b(?:does not|doesn't|do not|don't|will not|won't|never)\s+"
        r"(?:place|submit|execute)\b(?:\s+(?:an?\s+)?orders?)?",
        r"\bno orders? (?:is|was|are|were) placed\b",
        r"\bnothing is (?:placed|submitted|executed)\b",
    )
    nonplacing = any(re.search(pattern, lowered) for pattern in negative_patterns)
    positive_source = re.sub(r"\bdecimal places\b", " ", lowered)
    for pattern in negative_patterns:
        positive_source = re.sub(pattern, " ", positive_source)
    mentions_placing = bool(
        re.search(
            r"\b(?:place|places|placing|placement|submit|submits|submitting|submission|execute|executes|executing)\b",
            positive_source,
        )
        and re.search(r"\borders?\b", positive_source)
    )
    return {
        "mentions_simulation": bool(
            re.search(r"\b(simulat(?:e|es|ed|ion|ing))\b", lowered)
        ),
        "mentions_pretrade": bool(re.search(r"\bpre[- ]trade\b", lowered)),
        "mentions_warning_or_alert": bool(
            re.search(r"\b(?:warnings?|alerts?)\b", lowered)
        ),
        "explicitly_nonplacing": nonplacing,
        "explicitly_placing": mentions_placing,
    }


def _fractional_precision_values(description: str) -> tuple[int, ...]:
    lowered = description.casefold()
    if not all(
        marker in lowered for marker in ("fractional", "market", "regular", "hour")
    ):
        return ()
    matches = re.findall(
        r"\b(?:up to|maximum of|max(?:imum)?)\s+(\d{1,2})\s+decimal places\b",
        lowered,
    )
    return tuple(sorted({int(value) for value in matches}))


def _canonical_json(value: object) -> bytes:
    budget = [20_000]
    clean = _json_value(value, depth=0, budget=budget)
    return json.dumps(
        clean,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _json_value(value: object, *, depth: int, budget: list[int]) -> object:
    budget[0] -= 1
    if budget[0] < 0 or depth > 64:
        raise ValueError("schema size bound exceeded")
    if value is None or type(value) in {str, bool, int}:
        if type(value) is str and len(value) > 64_000:
            raise ValueError("schema string bound exceeded")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("schema number invalid")
        return value
    if isinstance(value, Mapping):
        if len(value) > 5_000 or any(type(key) is not str for key in value):
            raise ValueError("schema object invalid")
        return {
            key: _json_value(item, depth=depth + 1, budget=budget)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        if len(value) > 5_000:
            raise ValueError("schema array too large")
        return [_json_value(item, depth=depth + 1, budget=budget) for item in value]
    raise TypeError("schema is not JSON")


def _map_inherited_reason(reason: str) -> str:
    mapping = {
        "L41R1_SESSION_CLOSE_FAILED": "L41R5_SESSION_CLOSE_FAILED",
        "L41R1_TOOLS_LIST_FAILED": "L41R5_TOOLS_LIST_FAILED",
        "L41R1_TOOL_INVENTORY_MALFORMED": "L41R5_TOOL_INVENTORY_MALFORMED",
        "L41R1_TOOL_CURSOR_INVALID": "L41R5_TOOL_CURSOR_INVALID",
        "L41R1_TOOL_PAGINATION_BOUND_EXCEEDED": "L41R5_TOOL_PAGINATION_BOUND_EXCEEDED",
        "L41R1_REQUIRED_SCHEMA_MISSING": "L41R5_REQUIRED_SCHEMA_MISSING",
        "L41R1_DUPLICATE_SCHEMA": "L41R5_DUPLICATE_SCHEMA",
        "L41R1_SCHEMA_CHANGED": "L41R5_SCHEMA_CHANGED",
        "L41R1_SCHEMA_MALFORMED": "L41R5_SCHEMA_MALFORMED",
    }
    if reason == "L41R1_SCHEMA_AMBIGUOUS":
        return "L41R5_SCHEMA_AMBIGUITY_UNCLASSIFIED"
    return mapping.get(reason, "L41R5_DISCOVERY_FAILED")


def run_l41r5_schema_semantic_recovery(
    *,
    evidence_dir: Path,
) -> L41R5SchemaDiscoveryResult:
    """Run the one-shot L41R5 observer against the fixed L41R4 baseline."""

    baseline = _l41r4_interface_baseline()
    return _run_with_dependencies(
        evidence_dir=evidence_dir,
        source_admitter=admit_l41_source,
        oauth_factory_builder=_build_windows_oauth_factory,
        transport_builder=lambda oauth: _L41R5SchemaDiscoveryTransport(
            oauth,
            expected_schema_digests=baseline,
        ),
        repository_root_resolver=_repository_root,
        expected_schema_digests=baseline,
    )


def _run_with_dependencies(
    *,
    evidence_dir: Path,
    source_admitter: Callable[[Path], SourceAdmission],
    oauth_factory_builder: Callable[[], _OAuthFactoryBundle],
    transport_builder: Callable[[object], object],
    repository_root_resolver: Callable[[], Path],
    expected_schema_digests: Mapping[str, str],
) -> L41R5SchemaDiscoveryResult:
    if not _valid_schema_baseline(expected_schema_digests):
        return _result_without_file("BLOCKED", "L41R5_SCHEMA_BASELINE_INVALID")
    try:
        output_dir = _fresh_evidence_dir(evidence_dir)
    except Exception:
        return _result_without_file("BLOCKED", "L41R5_EVIDENCE_PATH_INVALID")

    empty_counts = L41R5SchemaDiscoveryAttemptCounts()
    source: SourceAdmission | None = None
    try:
        candidate = source_admitter(repository_root_resolver())
        if type(candidate) is not SourceAdmission or not _source_is_accepted(candidate):
            raise L41R5SchemaDiscoveryError("L41R5_SOURCE_ADMISSION_BLOCKED")
        source = candidate
    except Exception:
        return _write_result(
            output_dir,
            "BLOCKED",
            "L41R5_SOURCE_ADMISSION_BLOCKED",
            source,
            empty_counts,
            (),
            (),
        )

    browser_opener: _OneShotBrowserOpener | None = None
    try:
        with _quiet_provider():
            bundle = oauth_factory_builder()
        if type(bundle) is not _OAuthFactoryBundle or not callable(bundle.factory):
            raise TypeError
        browser_opener = bundle.browser_opener
    except Exception:
        return _write_result(
            output_dir,
            "BLOCKED",
            "L41R5_OAUTH_FACTORY_FAILED",
            source,
            empty_counts,
            (),
            (),
        )

    try:
        with _quiet_provider():
            transport = transport_builder(bundle.factory)
    except Exception:
        return _write_result(
            output_dir,
            "BLOCKED",
            "L41R5_TRANSPORT_CREATE_FAILED",
            source,
            empty_counts,
            (),
            (),
        )

    status = "BLOCKED"
    reason = "L41R5_DISCOVERY_FAILED"
    schemas: tuple[dict[str, object], ...] = ()
    fingerprints: tuple[dict[str, object], ...] = ()
    try:
        with _quiet_provider():
            with transport as boundary:
                try:
                    discovered = boundary.discover()
                    if type(discovered) is not tuple or any(
                        type(item) is not dict for item in discovered
                    ):
                        raise L41R5SchemaDiscoveryError("L41R5_SCHEMA_MALFORMED")
                    schemas = discovered
                    status = "CAPTURED_FOR_REVIEW"
                    reason = "L41R5_SCHEMA_SEMANTIC_RECOVERY_CAPTURED"
                except L41R5SchemaDiscoveryError as error:
                    reason = error.reason
                except SchemaDiscoveryError as error:
                    reason = _map_inherited_reason(error.reason)
                except Exception:
                    reason = "L41R5_DISCOVERY_FAILED"
                try:
                    retained = getattr(boundary, "schemas", ())
                    if type(retained) is tuple and all(
                        type(item) is dict for item in retained
                    ):
                        schemas = retained
                except Exception:
                    pass
                try:
                    retained_fingerprints = getattr(
                        boundary, "structural_fingerprints", ()
                    )
                    if type(retained_fingerprints) is tuple and all(
                        type(item) is dict for item in retained_fingerprints
                    ):
                        fingerprints = retained_fingerprints
                except Exception:
                    pass
    except L41R5SchemaDiscoveryError as error:
        status = "BLOCKED"
        reason = error.reason
    except Exception as error:
        status = "BLOCKED"
        inherited_reason = getattr(error, "reason", None)
        reason = (
            "L41R5_SESSION_CLOSE_FAILED"
            if inherited_reason
            in {"L41R1_SESSION_CLOSE_FAILED", "L41R3_SESSION_CLOSE_FAILED"}
            else "L41R5_DISCOVERY_FAILED"
        )

    counts = _read_attempt_counts(transport, browser_opener)
    if counts is None or not _counts_valid(
        counts, completed=bool(counts.tools_list_attempts)
    ):
        status = "BLOCKED"
        reason = "L41R5_ATTEMPT_COUNTS_INVALID"
        counts = empty_counts if counts is None else counts
    elif status == "CAPTURED_FOR_REVIEW":
        if not _required_schemas_present(schemas):
            status = "BLOCKED"
            reason = "L41R5_REQUIRED_SCHEMA_MISSING"

    return _write_result(
        output_dir, status, reason, source, counts, schemas, fingerprints
    )


def _source_is_accepted(source: SourceAdmission) -> bool:
    return (
        source.branch == L41_FEATURE_BRANCH
        and source.head == source.origin_feature_head == source.origin_develop_head
        and source.tree == source.origin_feature_tree == source.origin_develop_tree
        and source.feature_authority == "PASS"
        and source.prospective_develop_authority == "PASS"
    )


def _valid_schema_baseline(baseline: Mapping[str, str]) -> bool:
    if not isinstance(baseline, Mapping) or set(baseline) != _INSPECTED_TOOLS:
        return False
    return all(
        type(name) is str
        and type(digest) is str
        and _SHA256.fullmatch(digest) is not None
        for name, digest in baseline.items()
    )


def _read_attempt_counts(
    transport: object, browser_opener: _OneShotBrowserOpener | None
) -> L41R5SchemaDiscoveryAttemptCounts | None:
    try:
        counts = transport.attempt_counts
        launches = 0 if browser_opener is None else browser_opener.launch_count
    except Exception:
        return None
    if type(counts) is not SchemaDiscoveryAttemptCounts or type(launches) is not int:
        return None
    return L41R5SchemaDiscoveryAttemptCounts(
        oauth_scope_entry_attempts=counts.oauth_scope_entry_attempts,
        mcp_session_open_attempts=counts.mcp_session_open_attempts,
        browser_launches=launches,
        tools_list_attempts=counts.tools_list_attempts,
        mcp_tool_invocation_attempts=counts.mcp_tool_invocation_attempts,
        get_accounts_attempts=counts.get_accounts_attempts,
        get_equity_tradability_attempts=counts.get_equity_tradability_attempts,
        get_positions_attempts=counts.get_positions_attempts,
        get_orders_attempts=counts.get_orders_attempts,
        get_portfolio_attempts=counts.get_portfolio_attempts,
        get_quotes_attempts=counts.get_quotes_attempts,
        review_equity_order_attempts=counts.review_equity_order_attempts,
        place_equity_order_attempts=counts.place_equity_order_attempts,
        cancel_equity_order_attempts=counts.cancel_equity_order_attempts,
        other_tool_attempts=counts.other_tool_attempts,
    )


def _counts_valid(
    counts: L41R5SchemaDiscoveryAttemptCounts, *, completed: bool
) -> bool:
    positive = (
        counts.oauth_scope_entry_attempts,
        counts.mcp_session_open_attempts,
        counts.browser_launches,
        counts.tools_list_attempts,
    )
    prohibited = (
        counts.mcp_tool_invocation_attempts,
        counts.get_accounts_attempts,
        counts.get_equity_tradability_attempts,
        counts.get_positions_attempts,
        counts.get_orders_attempts,
        counts.get_portfolio_attempts,
        counts.get_quotes_attempts,
        counts.review_equity_order_attempts,
        counts.place_equity_order_attempts,
        counts.cancel_equity_order_attempts,
        counts.other_tool_attempts,
    )
    if not all(type(value) is int and 0 <= value <= 1 for value in positive[:3]):
        return False
    if type(positive[3]) is not int or not 0 <= positive[3] <= _MAX_DISCOVERY_PAGES:
        return False
    if any(type(value) is not int or value != 0 for value in prohibited):
        return False
    if completed:
        return positive[0] == 1 and positive[1] == 1 and positive[3] >= 1
    return True


def _required_schemas_present(schemas: Sequence[Mapping[str, object]]) -> bool:
    return _INSPECTED_TOOLS.issubset({schema.get("tool_name") for schema in schemas})


def _l41r4_interface_baseline() -> dict[str, str]:
    return dict(_L41R4_INTERFACE_BASELINE)


def _repository_root() -> Path:
    root = Path(__file__).resolve().parents[3]
    if str(root).casefold() != str(_CANONICAL_ROOT).casefold():
        raise L41R5SchemaDiscoveryError("L41R5_SOURCE_ADMISSION_BLOCKED")
    return root


def _fresh_evidence_dir(candidate: Path) -> Path:
    path = Path(candidate)
    parent_root = _EVIDENCE_ROOT.resolve(strict=True)
    if not path.is_absolute() or path.drive.casefold() != "f:":
        raise ValueError("L41R5_EVIDENCE_PATH_INVALID")
    return _create_fresh_evidence_dir_under_root(path, parent_root)


def _create_fresh_evidence_dir_under_root(path: Path, parent_root: Path) -> Path:
    if path.exists() or path.is_symlink():
        raise ValueError("L41R5_EVIDENCE_PATH_INVALID")
    parent = path.parent.resolve(strict=True)
    if path.parent != parent or not parent.is_relative_to(parent_root):
        raise ValueError("L41R5_EVIDENCE_PATH_INVALID")
    current = parent
    while True:
        if current.resolve(strict=True) != current or _has_reparse_point(current):
            raise ValueError("L41R5_EVIDENCE_PATH_INVALID")
        if current == parent_root:
            break
        if current.parent == current or not current.is_relative_to(parent_root):
            raise ValueError("L41R5_EVIDENCE_PATH_INVALID")
        current = current.parent
    path.mkdir()
    return path


def _has_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(path.stat(), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _result_without_file(status: str, reason: str) -> L41R5SchemaDiscoveryResult:
    return L41R5SchemaDiscoveryResult(
        status,
        reason,
        None,
        None,
        L41R5SchemaDiscoveryAttemptCounts(),
        (),
        (),
    )


def _write_result(
    output_dir: Path,
    status: str,
    reason: str,
    source: SourceAdmission | None,
    attempt_counts: L41R5SchemaDiscoveryAttemptCounts,
    schemas: tuple[dict[str, object], ...],
    fingerprints: tuple[dict[str, object], ...],
) -> L41R5SchemaDiscoveryResult:
    if reason not in _REASON_CODES:
        status = "BLOCKED"
        reason = "L41R5_DISCOVERY_FAILED"
    path = output_dir / "evidence.json"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(
                json.dumps(
                    _evidence_payload(
                        status, reason, source, attempt_counts, schemas, fingerprints
                    ),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                    allow_nan=False,
                )
                + "\n"
            )
    except Exception:
        return L41R5SchemaDiscoveryResult(
            "BLOCKED",
            "L41R5_EVIDENCE_WRITE_FAILED",
            None,
            source,
            attempt_counts,
            schemas,
            fingerprints,
        )
    return L41R5SchemaDiscoveryResult(
        status, reason, path, source, attempt_counts, schemas, fingerprints
    )


def _source_payload(source: SourceAdmission | None) -> dict[str, object] | None:
    if source is None:
        return None
    return {
        "branch": source.branch,
        "head": source.head,
        "tree": source.tree,
        "origin_feature_head": source.origin_feature_head,
        "origin_feature_tree": source.origin_feature_tree,
        "origin_develop_head": source.origin_develop_head,
        "origin_develop_tree": source.origin_develop_tree,
        "feature_authority": source.feature_authority,
        "prospective_develop_authority": source.prospective_develop_authority,
    }


def _evidence_payload(
    status: str,
    reason: str,
    source: SourceAdmission | None,
    attempt_counts: L41R5SchemaDiscoveryAttemptCounts,
    schemas: tuple[dict[str, object], ...],
    fingerprints: tuple[dict[str, object], ...],
) -> dict[str, object]:
    return {
        "schema": L41R5_EVIDENCE_SCHEMA,
        "observation": L41R5_OBSERVATION,
        "one_shot": True,
        "status": status,
        "reason": reason,
        "source": _source_payload(source),
        "attempt_counts": {
            name: getattr(attempt_counts, name)
            for name in L41R5SchemaDiscoveryAttemptCounts.__dataclass_fields__
        },
        "browser_launches": attempt_counts.browser_launches,
        "schemas": list(schemas),
        "l41r4_predecessor_evidence": dict(_L41R4_PREDECESSOR_EVIDENCE),
        "l41r4_interface_baseline": dict(_L41R4_INTERFACE_BASELINE),
        "structural_fingerprints": list(fingerprints),
        "native_credential_read_count": None,
        "native_credential_write_count": None,
        "credential_store_accounting": "SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED",
        "trusted_binding": False,
        "provider_numeric_rules_derived": False,
        "automatic_retry": "FORBIDDEN",
    }


def _discard_log(*args: object, **kwargs: object) -> None:
    del args, kwargs


@contextmanager
def _quiet_provider() -> Iterator[None]:
    """Discard SDK prints/logs/warnings and native stdout/stderr descriptors."""

    streams = sys.stdout, sys.stderr
    for stream in streams:
        stream.flush()
    previous_disable = logging.root.manager.disable
    previous_handle = logging.Logger.handle
    with (
        open(os.devnull, "w", encoding="utf-8") as sink,
        redirect_stdout(sink),
        redirect_stderr(sink),
        warnings.catch_warnings(),
        ExitStack() as descriptors,
    ):
        for descriptor in (1, 2):
            saved = os.dup(descriptor)
            descriptors.callback(os.close, saved)
            descriptors.callback(os.dup2, saved, descriptor)
            os.dup2(sink.fileno(), descriptor)
        try:
            logging.disable(sys.maxsize)
            logging.Logger.handle = _discard_log
            warnings.simplefilter("ignore")
            yield
        finally:
            for stream in streams:
                stream.flush()
            logging.Logger.handle = previous_handle
            logging.disable(previous_disable)


def _run_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture sanitized Robinhood MCP schema semantic recovery (L41R5)."
    )
    parser.add_argument("--evidence-dir", type=Path, required=True)
    arguments = parser.parse_args(argv)
    result = run_l41r5_schema_semantic_recovery(evidence_dir=arguments.evidence_dir)
    print(
        json.dumps(
            {
                "status": result.status,
                "reason": result.reason,
                "evidence_path": (
                    None if result.evidence_path is None else str(result.evidence_path)
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0 if result.status == "CAPTURED_FOR_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(_run_main())
