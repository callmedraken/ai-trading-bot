"""Effect-free L41R1 Robinhood MCP schema discovery boundary.

The operator is a one-session, ``tools/list``-only observation. It records
sanitized interface facts and digests for later review; it does not establish
provider rules, capability readiness, or order authority.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
import stat
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from trading_bot.live_prototype.capability_operator import (
    L41_FEATURE_BRANCH,
    SourceAdmission,
    _create_windows_oauth_factory,
    admit_l41_source,
)
from trading_bot.live_prototype.capability_transport import (
    _production_session as _schema_production_session,
)

L41R1_EVIDENCE_SCHEMA = "arch147-l41r1-interface-observation/v1"
_CANONICAL_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-live-prototype-current")
_EVIDENCE_ROOT = Path(r"F:\AI\temp")
_REQUIRED_TOOLS = frozenset({"review_equity_order", "place_equity_order"})
_OPTIONAL_TOOLS = frozenset({"get_equity_tradability"})
_INSPECTED_TOOLS = _REQUIRED_TOOLS | _OPTIONAL_TOOLS
_MAX_DISCOVERY_PAGES = 20
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REASON_CODES = frozenset(
    {
        "L41R1_EVIDENCE_PATH_INVALID",
        "L41R1_SOURCE_ADMISSION_BLOCKED",
        "L41R1_OAUTH_FACTORY_FAILED",
        "L41R1_TRANSPORT_CREATE_FAILED",
        "L41R1_MCP_SESSION_OPEN_FAILED",
        "L41R1_TOOLS_LIST_FAILED",
        "L41R1_TOOL_INVENTORY_MALFORMED",
        "L41R1_TOOL_CURSOR_INVALID",
        "L41R1_TOOL_PAGINATION_BOUND_EXCEEDED",
        "L41R1_REQUIRED_SCHEMA_MISSING",
        "L41R1_DUPLICATE_SCHEMA",
        "L41R1_SCHEMA_CHANGED",
        "L41R1_SCHEMA_MALFORMED",
        "L41R1_SCHEMA_AMBIGUOUS",
        "L41R1_SCHEMA_BASELINE_INVALID",
        "L41R1_SESSION_CLOSE_FAILED",
        "L41R1_DISCOVERY_FAILED",
        "L41R1_ATTEMPT_COUNTS_INVALID",
        "L41R1_EVIDENCE_WRITE_FAILED",
    }
)


class SchemaDiscoveryError(RuntimeError):
    """A fixed diagnostic with no provider text or secret material."""

    def __init__(self, reason: str) -> None:
        self.reason = reason if reason in _REASON_CODES else "L41R1_DISCOVERY_FAILED"
        super().__init__(self.reason)


class _McpSchemaClient(Protocol):
    async def list_tools(self, *, cursor: str | None = None) -> object: ...


@dataclass(frozen=True, slots=True)
class SchemaDiscoveryAttemptCounts:
    """Source-owned call accounting; every tool invocation stays prohibited."""

    oauth_scope_entry_attempts: int = 0
    mcp_session_open_attempts: int = 0
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
class InterfaceSchemaFacts:
    """Sanitized facts derived from one advertised tool schema and description."""

    tool_name: str
    input_schema_sha256: str
    description_sha256: str
    interface_sha256: str
    quantity_field_present: bool | None
    quantity_field_required: bool | None
    quantity_field_type: str | None
    regular_hours_fractional_market_precision_decimal_places: int | None
    review_semantics: str | None
    placement_semantics: str | None
    review_is_placement: bool | None
    schema_baseline_checked: bool


@dataclass(frozen=True, slots=True)
class SchemaDiscoveryResult:
    """Sanitized operator result; CAPTURED_FOR_REVIEW grants no readiness."""

    status: str
    reason: str
    evidence_path: Path | None
    source: SourceAdmission | None
    attempt_counts: SchemaDiscoveryAttemptCounts
    schemas: tuple[InterfaceSchemaFacts, ...]


class _SessionFactory(Protocol):
    def __call__(
        self, oauth: object
    ) -> AbstractAsyncContextManager[_McpSchemaClient]: ...


class RobinhoodSchemaDiscoveryTransport:
    """One-use transport that has no MCP tool-call method."""

    __slots__ = (
        "_oauth_factory",
        "_session_factory",
        "_expected_schema_digests",
        "_entered",
        "_used",
        "_oauth_attempts",
        "_session_attempts",
        "_tools_list_attempts",
        "_schemas",
    )

    def __init__(
        self,
        oauth_factory: Callable[[], object],
        *,
        session_factory: _SessionFactory | None = None,
        expected_schema_digests: Mapping[str, str] | None = None,
    ) -> None:
        if not callable(oauth_factory):
            raise TypeError("oauth_factory must be callable")
        if session_factory is not None and not callable(session_factory):
            raise TypeError("session_factory must be callable")
        self._oauth_factory = oauth_factory
        self._session_factory = (
            _schema_production_session if session_factory is None else session_factory
        )
        self._expected_schema_digests = _validate_baseline(expected_schema_digests)
        self._entered = False
        self._used = False
        self._oauth_attempts = 0
        self._session_attempts = 0
        self._tools_list_attempts = 0
        self._schemas: tuple[InterfaceSchemaFacts, ...] = ()

    def __repr__(self) -> str:
        return "RobinhoodSchemaDiscoveryTransport(<redacted>)"

    @property
    def attempt_counts(self) -> SchemaDiscoveryAttemptCounts:
        return SchemaDiscoveryAttemptCounts(
            oauth_scope_entry_attempts=self._oauth_attempts,
            mcp_session_open_attempts=self._session_attempts,
            tools_list_attempts=self._tools_list_attempts,
        )

    @property
    def schemas(self) -> tuple[InterfaceSchemaFacts, ...]:
        return self._schemas

    def __enter__(self) -> RobinhoodSchemaDiscoveryTransport:
        if self._entered or self._used:
            raise SchemaDiscoveryError("L41R1_DISCOVERY_FAILED")
        self._entered = True
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False

    def discover(self) -> tuple[InterfaceSchemaFacts, ...]:
        """Open one session, list schemas, then close it; never invoke a tool."""

        if not self._entered or self._used:
            raise SchemaDiscoveryError("L41R1_DISCOVERY_FAILED")
        self._used = True
        self._oauth_attempts += 1
        try:
            oauth = self._oauth_factory()
        except Exception:
            raise SchemaDiscoveryError("L41R1_OAUTH_FACTORY_FAILED") from None

        self._session_attempts += 1
        try:
            asyncio.run(self._discover_and_close(oauth))
        except SchemaDiscoveryError:
            raise
        except Exception:
            raise SchemaDiscoveryError("L41R1_DISCOVERY_FAILED") from None
        return self._schemas

    async def _discover_and_close(self, oauth: object) -> None:
        context: AbstractAsyncContextManager[_McpSchemaClient] | None = None
        client: _McpSchemaClient | None = None
        primary_error: SchemaDiscoveryError | None = None
        try:
            try:
                context = self._session_factory(oauth)
                client = await context.__aenter__()
            except Exception:
                raise SchemaDiscoveryError("L41R1_MCP_SESSION_OPEN_FAILED") from None
            try:
                self._schemas = await _discover_tool_schemas(
                    client,
                    on_list_attempt=self._count_tools_list,
                    expected_schema_digests=self._expected_schema_digests,
                )
            except SchemaDiscoveryError as error:
                primary_error = error
        finally:
            if context is not None and client is not None:
                try:
                    await context.__aexit__(None, None, None)
                except Exception:
                    if primary_error is None:
                        primary_error = SchemaDiscoveryError(
                            "L41R1_SESSION_CLOSE_FAILED"
                        )
        if primary_error is not None:
            raise primary_error

    def _count_tools_list(self) -> None:
        self._tools_list_attempts += 1


def run_l41r1_schema_discovery(
    *,
    evidence_dir: Path,
    expected_schema_digests: Mapping[str, str] | None = None,
) -> SchemaDiscoveryResult:
    """Run the future metadata-only observation after exact L41 source admission."""

    return _run_with_dependencies(
        evidence_dir=evidence_dir,
        source_admitter=admit_l41_source,
        oauth_factory_builder=_create_windows_oauth_factory,
        transport_builder=lambda oauth_factory: RobinhoodSchemaDiscoveryTransport(
            oauth_factory,
            expected_schema_digests=expected_schema_digests,
        ),
        repository_root_resolver=_repository_root,
        expected_schema_digests=expected_schema_digests,
    )


def _run_with_dependencies(
    *,
    evidence_dir: Path,
    source_admitter: Callable[[Path], SourceAdmission],
    oauth_factory_builder: Callable[[], object],
    transport_builder: Callable[[object], object],
    repository_root_resolver: Callable[[], Path],
    expected_schema_digests: Mapping[str, str] | None = None,
) -> SchemaDiscoveryResult:
    """Injected seams are private to fake-only tests and never called by import."""

    try:
        baseline = _validate_baseline(expected_schema_digests)
    except SchemaDiscoveryError as error:
        return _result_without_file("BLOCKED", error.reason)
    try:
        output_dir = _fresh_evidence_dir(evidence_dir)
    except Exception:
        return _result_without_file("BLOCKED", "L41R1_EVIDENCE_PATH_INVALID")

    source: SourceAdmission | None = None
    empty_counts = SchemaDiscoveryAttemptCounts()
    try:
        candidate = source_admitter(repository_root_resolver())
        if type(candidate) is not SourceAdmission or not _source_is_accepted(candidate):
            raise SchemaDiscoveryError("L41R1_SOURCE_ADMISSION_BLOCKED")
        source = candidate
    except Exception:
        return _write_result(
            output_dir,
            "BLOCKED",
            "L41R1_SOURCE_ADMISSION_BLOCKED",
            source,
            empty_counts,
            (),
        )

    try:
        oauth_factory = oauth_factory_builder()
        if not callable(oauth_factory):
            raise TypeError
    except Exception:
        return _write_result(
            output_dir,
            "BLOCKED",
            "L41R1_OAUTH_FACTORY_FAILED",
            source,
            empty_counts,
            (),
        )

    try:
        transport = transport_builder(oauth_factory)
    except Exception:
        return _write_result(
            output_dir,
            "BLOCKED",
            "L41R1_TRANSPORT_CREATE_FAILED",
            source,
            empty_counts,
            (),
        )

    reason = "L41R1_DISCOVERY_FAILED"
    status = "BLOCKED"
    schemas: tuple[InterfaceSchemaFacts, ...] = ()
    try:
        with transport as boundary:
            try:
                discovered = boundary.discover()
                if type(discovered) is not tuple or any(
                    type(item) is not InterfaceSchemaFacts for item in discovered
                ):
                    raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED")
                schemas = discovered
                status = "CAPTURED_FOR_REVIEW"
                reason = "L41R1_SCHEMA_METADATA_CAPTURED"
            except SchemaDiscoveryError as error:
                reason = error.reason
                retained = getattr(boundary, "schemas", ())
                if type(retained) is tuple and all(
                    type(item) is InterfaceSchemaFacts for item in retained
                ):
                    schemas = retained
    except SchemaDiscoveryError as error:
        reason = error.reason
    except Exception:
        reason = "L41R1_DISCOVERY_FAILED"

    counts = _read_attempt_counts(transport)
    if counts is None or not _counts_valid(counts, completed=bool(schemas)):
        status = "BLOCKED"
        reason = "L41R1_ATTEMPT_COUNTS_INVALID"
        counts = empty_counts if counts is None else counts
    elif status == "CAPTURED_FOR_REVIEW":
        if not _required_schemas_present(schemas):
            status = "BLOCKED"
            reason = "L41R1_REQUIRED_SCHEMA_MISSING"
        elif baseline is None:
            reason = "L41R1_SCHEMA_METADATA_CAPTURED_UNPINNED"

    return _write_result(output_dir, status, reason, source, counts, schemas)


async def _discover_tool_schemas(
    client: _McpSchemaClient,
    *,
    on_list_attempt: Callable[[], None],
    expected_schema_digests: Mapping[str, str] | None,
) -> tuple[InterfaceSchemaFacts, ...]:
    found: dict[str, InterfaceSchemaFacts] = {}
    cursor: str | None = None
    seen_cursors: set[str] = set()
    for _ in range(_MAX_DISCOVERY_PAGES):
        on_list_attempt()
        try:
            listing = await client.list_tools(cursor=cursor)
        except SchemaDiscoveryError:
            raise
        except Exception:
            raise SchemaDiscoveryError("L41R1_TOOLS_LIST_FAILED") from None

        entries = _field(listing, "tools")
        if not isinstance(entries, Sequence) or isinstance(
            entries, (str, bytes, bytearray)
        ):
            raise SchemaDiscoveryError("L41R1_TOOL_INVENTORY_MALFORMED")
        for entry in entries:
            name = _field(entry, "name")
            if type(name) is not str or not name:
                raise SchemaDiscoveryError("L41R1_TOOL_INVENTORY_MALFORMED")
            if name not in _INSPECTED_TOOLS:
                continue
            facts = _schema_facts(name, entry, expected_schema_digests)
            previous = found.get(name)
            if previous is not None:
                if previous.interface_sha256 != facts.interface_sha256:
                    raise SchemaDiscoveryError("L41R1_SCHEMA_CHANGED")
                raise SchemaDiscoveryError("L41R1_DUPLICATE_SCHEMA")
            found[name] = facts

        next_cursor = _field(listing, "next_cursor")
        if next_cursor is None:
            break
        if (
            type(next_cursor) is not str
            or not next_cursor
            or next_cursor in seen_cursors
        ):
            raise SchemaDiscoveryError("L41R1_TOOL_CURSOR_INVALID")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    else:
        raise SchemaDiscoveryError("L41R1_TOOL_PAGINATION_BOUND_EXCEEDED")

    missing = _REQUIRED_TOOLS - found.keys()
    if missing:
        raise SchemaDiscoveryError("L41R1_REQUIRED_SCHEMA_MISSING")
    if expected_schema_digests is not None and not set(
        expected_schema_digests
    ).issubset(found):
        raise SchemaDiscoveryError("L41R1_REQUIRED_SCHEMA_MISSING")
    return tuple(found[name] for name in sorted(found))


def _schema_facts(
    name: str,
    entry: object,
    expected_schema_digests: Mapping[str, str] | None,
) -> InterfaceSchemaFacts:
    schema = _field(entry, "inputSchema")
    description = _field(entry, "description")
    if not isinstance(schema, Mapping) or (
        description is not None and type(description) is not str
    ):
        raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED")
    description_text = "" if description is None else description
    try:
        schema_bytes = _canonical_json(schema)
        interface_bytes = _canonical_json(
            {"name": name, "inputSchema": schema, "description": description_text}
        )
    except (TypeError, ValueError, RecursionError):
        raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED") from None

    schema_digest = hashlib.sha256(schema_bytes).hexdigest()
    description_digest = hashlib.sha256(description_text.encode("utf-8")).hexdigest()
    interface_digest = hashlib.sha256(interface_bytes).hexdigest()
    if expected_schema_digests is not None and name in expected_schema_digests:
        if expected_schema_digests[name] != interface_digest:
            raise SchemaDiscoveryError("L41R1_SCHEMA_CHANGED")

    schema_type = schema.get("type")
    if schema_type is not None and schema_type != "object":
        raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED")
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, Mapping) or not isinstance(required, list):
        raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED")
    if any(type(key) is not str for key in properties):
        raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED")
    if any(type(item) is not str for item in required) or len(set(required)) != len(
        required
    ):
        raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED")
    if any(item not in properties for item in required):
        raise SchemaDiscoveryError("L41R1_SCHEMA_AMBIGUOUS")
    if any(not isinstance(value, Mapping) for value in properties.values()):
        raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED")

    baseline_checked = (
        expected_schema_digests is not None and name in expected_schema_digests
    )
    if name not in _REQUIRED_TOOLS:
        return InterfaceSchemaFacts(
            tool_name=name,
            input_schema_sha256=schema_digest,
            description_sha256=description_digest,
            interface_sha256=interface_digest,
            quantity_field_present=None,
            quantity_field_required=None,
            quantity_field_type=None,
            regular_hours_fractional_market_precision_decimal_places=None,
            review_semantics=None,
            placement_semantics=None,
            review_is_placement=None,
            schema_baseline_checked=baseline_checked,
        )

    quantity_present = "quantity" in properties
    quantity_required = "quantity" in required if quantity_present else False
    quantity_type_value: str | None = None
    advertised_descriptions = " ".join(
        (description_text, *_schema_descriptions(schema))
    )
    precision: int | None = None
    if quantity_present:
        quantity_type = properties["quantity"].get("type")
        if quantity_type is None:
            raise SchemaDiscoveryError("L41R1_SCHEMA_AMBIGUOUS")
        if type(quantity_type) is str:
            quantity_type_value = quantity_type
        elif isinstance(quantity_type, list) and all(
            type(item) is str for item in quantity_type
        ):
            raise SchemaDiscoveryError("L41R1_SCHEMA_AMBIGUOUS")
        else:
            raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED")
        precision = _advertised_fractional_precision(advertised_descriptions)

    review_semantics = _review_semantics(name, advertised_descriptions)
    placement_semantics = _placement_semantics(name, advertised_descriptions)
    review_is_placement: bool | None = None
    if name == "review_equity_order":
        says_nonplacing = _explicitly_nonplacing(advertised_descriptions)
        says_placing = _explicitly_placing(advertised_descriptions)
        if says_placing:
            raise SchemaDiscoveryError("L41R1_SCHEMA_AMBIGUOUS")
        if says_nonplacing:
            review_is_placement = False
    elif name == "place_equity_order" and _explicitly_nonplacing(
        advertised_descriptions
    ):
        raise SchemaDiscoveryError("L41R1_SCHEMA_AMBIGUOUS")

    return InterfaceSchemaFacts(
        tool_name=name,
        input_schema_sha256=schema_digest,
        description_sha256=description_digest,
        interface_sha256=interface_digest,
        quantity_field_present=quantity_present,
        quantity_field_required=quantity_required,
        quantity_field_type=quantity_type_value,
        regular_hours_fractional_market_precision_decimal_places=precision,
        review_semantics=review_semantics,
        placement_semantics=placement_semantics,
        review_is_placement=review_is_placement,
        schema_baseline_checked=baseline_checked,
    )


def _advertised_fractional_precision(text: str) -> int | None:
    lowered = text.casefold()
    context_markers = ("fractional", "market", "regular", "hour")
    if not all(marker in lowered for marker in context_markers):
        return None
    matches = re.findall(
        r"\b(?:up to|maximum of|max(?:imum)?)\s+(\d{1,2})\s+decimal places\b",
        lowered,
    )
    if not matches:
        return None
    values = {int(match) for match in matches}
    if len(values) != 1 or next(iter(values)) < 1:
        raise SchemaDiscoveryError("L41R1_SCHEMA_AMBIGUOUS")
    return next(iter(values))


def _review_semantics(name: str, description: str) -> str | None:
    if name != "review_equity_order":
        return None
    lowered = description.casefold()
    has_simulation = bool(re.search(r"\b(simulat(?:e|es|ed|ion|ing))\b", lowered))
    has_pretrade = bool(re.search(r"\bpre[- ]trade\b", lowered))
    has_warning_or_alert = bool(re.search(r"\b(?:warnings?|alerts?)\b", lowered))
    if has_simulation and has_pretrade and has_warning_or_alert:
        return "SIMULATION_PRETRADE_WARNING"
    return None


def _placement_semantics(name: str, description: str) -> str | None:
    if name != "place_equity_order":
        return None
    if _explicitly_nonplacing(description):
        return None
    if _explicitly_placing(description):
        return "ORDER_SUBMISSION"
    return None


def _explicitly_nonplacing(description: str) -> bool:
    lowered = description.casefold()
    return bool(
        re.search(r"\bwithout\s+(?:placing|submitting|executing)\b", lowered)
        or re.search(
            r"\b(?:does not|do not|will not|never)\s+(?:place|submit|execute)\b",
            lowered,
        )
        or re.search(r"\bno order (?:is|was) placed\b", lowered)
        or re.search(r"\bnothing is (?:placed|submitted|executed)\b", lowered)
    )


def _explicitly_placing(description: str) -> bool:
    if _explicitly_nonplacing(description):
        return False
    lowered = description.casefold()
    return bool(
        re.search(
            r"\b(?:place|places|placing|placement|submit|submits|submitting|submission|execute|executes|executing)\b",
            lowered,
        )
        and re.search(r"\border\b", lowered)
    )


def _schema_descriptions(value: object) -> list[str]:
    descriptions: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "description":
                if type(item) is not str:
                    raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED")
                descriptions.append(item)
            else:
                descriptions.extend(_schema_descriptions(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            descriptions.extend(_schema_descriptions(item))
    return descriptions


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
        raise ValueError("schema is too large or deeply nested")
    if value is None or type(value) in {str, bool, int}:
        if type(value) is str and len(value) > 64_000:
            raise ValueError("schema string is too large")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("schema number is not finite")
        return value
    if isinstance(value, Mapping):
        if len(value) > 5_000 or any(type(key) is not str for key in value):
            raise ValueError("schema object is malformed")
        return {
            key: _json_value(item, depth=depth + 1, budget=budget)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        if len(value) > 5_000:
            raise ValueError("schema array is too large")
        return [_json_value(item, depth=depth + 1, budget=budget) for item in value]
    raise TypeError("schema contains a non-JSON value")


def _field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _validate_baseline(
    baseline: Mapping[str, str] | None,
) -> Mapping[str, str] | None:
    if baseline is None:
        return None
    if not isinstance(baseline, Mapping) or not _REQUIRED_TOOLS.issubset(baseline):
        raise SchemaDiscoveryError("L41R1_SCHEMA_BASELINE_INVALID")
    if not set(baseline).issubset(_INSPECTED_TOOLS):
        raise SchemaDiscoveryError("L41R1_SCHEMA_BASELINE_INVALID")
    if any(
        type(name) is not str
        or type(digest) is not str
        or _SHA256.fullmatch(digest) is None
        for name, digest in baseline.items()
    ):
        raise SchemaDiscoveryError("L41R1_SCHEMA_BASELINE_INVALID")
    return dict(baseline)


def _source_is_accepted(source: SourceAdmission) -> bool:
    return (
        source.branch == L41_FEATURE_BRANCH
        and source.head == source.origin_feature_head
        and source.head == source.origin_develop_head
        and source.tree == source.origin_feature_tree
        and source.tree == source.origin_develop_tree
        and source.feature_authority == "PASS"
        and source.prospective_develop_authority == "PASS"
        and len(source.head) == 40
        and len(source.tree) == 40
        and all(character in "0123456789abcdef" for character in source.head)
        and all(character in "0123456789abcdef" for character in source.tree)
    )


def _repository_root() -> Path:
    root = Path(__file__).resolve().parents[3]
    if str(root).casefold() != str(_CANONICAL_ROOT).casefold():
        raise SchemaDiscoveryError("L41R1_SOURCE_ADMISSION_BLOCKED")
    return root


def _read_attempt_counts(transport: object) -> SchemaDiscoveryAttemptCounts | None:
    try:
        counts = transport.attempt_counts
    except Exception:
        return None
    return counts if type(counts) is SchemaDiscoveryAttemptCounts else None


def _counts_valid(counts: SchemaDiscoveryAttemptCounts, *, completed: bool) -> bool:
    positive = (
        counts.oauth_scope_entry_attempts,
        counts.mcp_session_open_attempts,
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
    if not all(type(value) is int and 0 <= value <= 1 for value in positive[:2]):
        return False
    if type(positive[2]) is not int or not 0 <= positive[2] <= _MAX_DISCOVERY_PAGES:
        return False
    if any(type(value) is not int or value != 0 for value in prohibited):
        return False
    if completed:
        return positive[0] == 1 and positive[1] == 1 and positive[2] >= 1
    return True


def _required_schemas_present(schemas: Sequence[InterfaceSchemaFacts]) -> bool:
    return _REQUIRED_TOOLS.issubset({schema.tool_name for schema in schemas})


def _fresh_evidence_dir(candidate: Path) -> Path:
    path = Path(candidate)
    parent_root = _EVIDENCE_ROOT.resolve(strict=True)
    if (
        not path.is_absolute()
        or path.drive.casefold() != "f:"
        or path.exists()
        or path.is_symlink()
    ):
        raise ValueError("L41R1_EVIDENCE_PATH_INVALID")
    parent = path.parent.resolve(strict=True)
    if path.parent != parent or not parent.is_relative_to(parent_root):
        raise ValueError("L41R1_EVIDENCE_PATH_INVALID")
    current = parent
    while True:
        if current.resolve(strict=True) != current or _has_reparse_point(current):
            raise ValueError("L41R1_EVIDENCE_PATH_INVALID")
        if current == parent_root:
            break
        if current.parent == current or not current.is_relative_to(parent_root):
            raise ValueError("L41R1_EVIDENCE_PATH_INVALID")
        current = current.parent
    path.mkdir()
    return path


def _has_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(path.stat(), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _result_without_file(status: str, reason: str) -> SchemaDiscoveryResult:
    return SchemaDiscoveryResult(
        status,
        reason,
        None,
        None,
        SchemaDiscoveryAttemptCounts(),
        (),
    )


def _write_result(
    output_dir: Path,
    status: str,
    reason: str,
    source: SourceAdmission | None,
    attempt_counts: SchemaDiscoveryAttemptCounts,
    schemas: tuple[InterfaceSchemaFacts, ...],
) -> SchemaDiscoveryResult:
    if reason not in _REASON_CODES and reason not in {
        "L41R1_SCHEMA_METADATA_CAPTURED",
        "L41R1_SCHEMA_METADATA_CAPTURED_UNPINNED",
    }:
        status = "BLOCKED"
        reason = "L41R1_DISCOVERY_FAILED"
    path = output_dir / "evidence.json"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(
                json.dumps(
                    _evidence_payload(status, reason, source, attempt_counts, schemas),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                    allow_nan=False,
                )
                + "\n"
            )
    except Exception:
        return SchemaDiscoveryResult(
            "BLOCKED",
            "L41R1_EVIDENCE_WRITE_FAILED",
            None,
            source,
            attempt_counts,
            schemas,
        )
    return SchemaDiscoveryResult(status, reason, path, source, attempt_counts, schemas)


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
    attempt_counts: SchemaDiscoveryAttemptCounts,
    schemas: tuple[InterfaceSchemaFacts, ...],
) -> dict[str, object]:
    return {
        "schema": L41R1_EVIDENCE_SCHEMA,
        "status": status,
        "reason": reason,
        "source": _source_payload(source),
        "attempt_counts": {
            name: getattr(attempt_counts, name)
            for name in SchemaDiscoveryAttemptCounts.__dataclass_fields__
        },
        "schemas": [
            {
                name: getattr(schema, name)
                for name in InterfaceSchemaFacts.__dataclass_fields__
            }
            for schema in schemas
        ],
        "trusted_binding": False,
        "provider_numeric_rules_derived": False,
        "automatic_retry": "FORBIDDEN",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture sanitized Robinhood MCP interface metadata (L41R1)."
    )
    parser.add_argument("--evidence-dir", type=Path, required=True)
    arguments = parser.parse_args(argv)
    result = run_l41r1_schema_discovery(evidence_dir=arguments.evidence_dir)
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
        )
    )
    return 0 if result.status == "CAPTURED_FOR_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
