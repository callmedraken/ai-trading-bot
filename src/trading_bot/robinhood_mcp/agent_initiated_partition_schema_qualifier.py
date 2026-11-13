"""Unauthenticated semantic matching for the explicit agent partition schema.

The matcher checks bounded ``tools/list`` metadata and deliberately cannot
produce an authenticated qualification or an L43 order-scope proof. Production
qualification is owned by the separate source-guarded metadata observer.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import subprocess
from collections.abc import Awaitable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

_TOOL_NAME = "get_equity_orders"
_CONTRACT_VERSION = "EXHAUSTIVE_AGENT_INITIATED_PARTITION/v1"
_MAX_PAGES = 25
_MAX_TOOLS = 2000
_MAX_CURSOR_LENGTH = 4096
_MAX_SCHEMA_BYTES = 262_144
_MAX_SCHEMA_NODES = 20_000
_MAX_SCHEMA_DEPTH = 40
_GIT_OBJECT_ID = re.compile(r"[0-9a-f]{40}\Z")
_ARRAY_NARROWING_KEYS = frozenset(
    {
        "contains",
        "prefixItems",
        "unevaluatedItems",
        "additionalItems",
        "minItems",
        "maxItems",
    }
)
_INPUT_ROOT_KEYS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "description",
        "title",
        "$schema",
    }
)
_INPUT_FIELD_KEYS = frozenset({"type", "description", "default", "nullable", "title"})
_OUTPUT_ROOT_KEYS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "description",
        "title",
        "$schema",
    }
)
_OUTPUT_DATA_KEYS = _OUTPUT_ROOT_KEYS
_OUTPUT_ORDERS_KEYS = frozenset({"type", "items", "description", "title"})
_OUTPUT_ROW_KEYS = frozenset(
    {"type", "properties", "required", "additionalProperties", "description", "title"}
)


class AgentInitiatedPartitionSchemaClassification(StrEnum):
    UNAUTHENTICATED_SEMANTIC_MATCH = "UNAUTHENTICATED_SEMANTIC_MATCH"
    UNPROVEN_PROVIDER_SEMANTICS = "UNPROVEN_PROVIDER_SEMANTICS"
    SCHEMA_MALFORMED = "SCHEMA_MALFORMED"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    SOURCE_AUTHORITY_FAILED = "SOURCE_AUTHORITY_FAILED"


_UNAUTHENTICATED_MATCH = (
    AgentInitiatedPartitionSchemaClassification.UNAUTHENTICATED_SEMANTIC_MATCH
)
_UNPROVEN = AgentInitiatedPartitionSchemaClassification.UNPROVEN_PROVIDER_SEMANTICS


@dataclass(frozen=True, slots=True)
class AgentInitiatedPartitionSchemaMatch:
    """A semantic match over supplied pages, never authenticated authority."""

    classification: AgentInitiatedPartitionSchemaClassification
    contract_version: str
    tool_name: str
    description_sha256: str | None
    input_schema_sha256: str | None
    output_schema_sha256: str | None
    agent_initiated_schema_sha256: str | None
    source_head: str | None
    source_tree: str | None
    tools_list_pages: int
    pagination_exhaustive: bool
    evidence_sha256: str

    @property
    def semantic_match(self) -> bool:
        return self.classification is _UNAUTHENTICATED_MATCH

    @property
    def authenticated(self) -> bool:
        """This public parser can never authenticate its supplied metadata."""
        return False


class _ToolsListSeam(Protocol):
    def __call__(self, *, cursor: str | None) -> object | Awaitable[object]: ...


class AgentInitiatedPartitionSchemaMatcher:
    """Match schema semantics from an explicit tools/list seam.

    The seam exists for deterministic tests and for the guarded observer's
    internal transport only. A returned match is never authenticated.
    """

    __slots__ = ("_repo_root",)

    def __init__(self, *, repo_root: Path) -> None:
        if not isinstance(repo_root, Path):
            raise TypeError("repo_root must be a Path")
        self._repo_root = repo_root

    async def match(
        self, *, tools_list: _ToolsListSeam
    ) -> AgentInitiatedPartitionSchemaMatch:
        if not callable(tools_list):
            raise TypeError("an explicit tools/list seam is required")
        source_head, source_tree = _source_identity(self._repo_root)
        if source_head is None or source_tree is None:
            return _result(
                AgentInitiatedPartitionSchemaClassification.SOURCE_AUTHORITY_FAILED,
                source_head=None,
                source_tree=None,
                pages=0,
                exhaustive=False,
            )

        cursor: str | None = None
        seen_cursors: set[str] = set()
        seen_names: set[str] = set()
        target: (
            tuple[str | None, Mapping[str, object], Mapping[str, object] | None] | None
        ) = None
        pages = 0
        tool_count = 0
        try:
            for _ in range(_MAX_PAGES):
                page = tools_list(cursor=cursor)
                if isinstance(page, Awaitable):
                    page = await page
                pages += 1
                tools, next_cursor = _page_material(page)
                for entry in tools:
                    tool_count += 1
                    if tool_count > _MAX_TOOLS:
                        raise ValueError("tool inventory exceeds bounds")
                    name, description, input_schema, output_schema = _tool_material(
                        entry
                    )
                    if name in seen_names:
                        raise ValueError("duplicate tool name")
                    seen_names.add(name)
                    if name == _TOOL_NAME:
                        if description is None:
                            raise ValueError("target description is missing")
                        target = (description, input_schema, output_schema)
                if next_cursor is None:
                    break
                if next_cursor in seen_cursors:
                    raise ValueError("tools/list cursor repeated")
                seen_cursors.add(next_cursor)
                cursor = next_cursor
            else:
                raise ValueError("tools/list page limit reached")
        except (Exception, asyncio.CancelledError):
            return _result(
                AgentInitiatedPartitionSchemaClassification.SCHEMA_MALFORMED,
                source_head=source_head,
                source_tree=source_tree,
                pages=pages,
                exhaustive=False,
            )

        if target is None:
            return _result(
                AgentInitiatedPartitionSchemaClassification.TOOL_UNAVAILABLE,
                source_head=source_head,
                source_tree=source_tree,
                pages=pages,
                exhaustive=True,
            )

        description, input_schema, output_schema = target
        facts = _schema_facts(input_schema, output_schema)
        return _result(
            _UNAUTHENTICATED_MATCH if facts is not None else _UNPROVEN,
            source_head=source_head,
            source_tree=source_tree,
            pages=pages,
            exhaustive=True,
            description_sha256=(
                None
                if description is None
                else hashlib.sha256(description.encode("utf-8")).hexdigest()
            ),
            input_schema_sha256=hashlib.sha256(
                _canonical_json(input_schema)
            ).hexdigest(),
            output_schema_sha256=(
                None
                if output_schema is None
                else hashlib.sha256(_canonical_json(output_schema)).hexdigest()
            ),
            agent_initiated_schema_sha256=(
                None
                if facts is None
                else hashlib.sha256(_canonical_json(facts)).hexdigest()
            ),
        )


def _page_material(page: object) -> tuple[list[object], str | None]:
    result_type = _read_alias(page, ("result_type", "resultType"))
    if result_type != "complete":
        raise ValueError("tools/list result is not complete")
    tools = _read_field(page, "tools")
    if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes, bytearray)):
        raise ValueError("tools/list inventory is malformed")
    next_cursor = _read_alias(page, ("next_cursor", "nextCursor"))
    if next_cursor is _MISSING:
        raise ValueError("tools/list cursor state is missing")
    if next_cursor is not None and (
        type(next_cursor) is not str
        or not next_cursor
        or len(next_cursor) > _MAX_CURSOR_LENGTH
    ):
        raise ValueError("tools/list cursor is malformed")
    return list(tools), next_cursor


def _tool_material(
    entry: object,
) -> tuple[str, str | None, Mapping[str, object], Mapping[str, object] | None]:
    name = _read_field(entry, "name")
    if type(name) is not str or not name:
        raise ValueError("tool name is malformed")
    description = _read_field(entry, "description")
    if (
        description is not _MISSING
        and description is not None
        and type(description) is not str
    ):
        raise ValueError("tool description is malformed")
    input_schema = _read_alias(entry, ("input_schema", "inputSchema"))
    output_schema = _read_alias(entry, ("output_schema", "outputSchema"))
    if not isinstance(input_schema, Mapping):
        raise ValueError("tool input schema is malformed")
    _bounded_schema(input_schema)
    if output_schema is not _MISSING and output_schema is not None:
        if not isinstance(output_schema, Mapping):
            raise ValueError("tool output schema is malformed")
        _bounded_schema(output_schema)
    return (
        name,
        description if type(description) is str else None,
        input_schema,
        output_schema if isinstance(output_schema, Mapping) else None,
    )


def _schema_facts(
    input_schema: Mapping[str, object],
    output_schema: Mapping[str, object] | None,
) -> dict[str, object] | None:
    input_properties = input_schema.get("properties")
    input_required = input_schema.get("required", [])
    if (
        input_schema.get("type") != "object"
        or not isinstance(input_properties, Mapping)
        or type(input_required) is not list
        or any(type(item) is not str for item in input_required)
        or len(set(input_required)) != len(input_required)
        or not set(input_required).issubset(input_properties)
        or set(input_required) != {"account_number"}
        or not set(input_schema).issubset(_INPUT_ROOT_KEYS)
    ):
        return None
    if any(
        type(name) is not str
        or not isinstance(prop, Mapping)
        or (name != "agent_initiated" and "default" in prop)
        for name, prop in input_properties.items()
    ):
        return None
    field = input_properties.get("agent_initiated")
    if not isinstance(field, Mapping) or "agent_initiated" in input_required:
        return None
    field_type = field.get("type")
    if type(field_type) is str:
        allowed_types = {field_type}
    elif (
        type(field_type) is list
        and field_type
        and all(type(item) is str for item in field_type)
        and len(set(field_type)) == len(field_type)
    ):
        allowed_types = set(field_type)
    else:
        return None
    if allowed_types not in ({"boolean"}, {"boolean", "null"}):
        return None
    if not set(field).issubset(_INPUT_FIELD_KEYS):
        return None
    if "default" in field and (
        field["default"] is not None or "null" not in allowed_types
    ):
        return None
    property_description = field.get("description")
    if property_description is not None and type(property_description) is not str:
        return None
    if output_schema is None:
        return None

    placed_agent = input_properties.get("placed_agent")
    if placed_agent is not None:
        if not isinstance(placed_agent, Mapping) or "placed_agent" in input_required:
            return None
        if "default" in placed_agent and placed_agent["default"] is not None:
            return None
    if "nullable" in field and field["nullable"] is not True:
        return None
    row = _order_row_schema(output_schema)
    if row is None:
        return None
    row_properties, row_required = row
    output_field = row_properties.get("agent_initiated")
    if (
        not isinstance(output_field, Mapping)
        or output_field.get("type") != "boolean"
        or "agent_initiated" not in row_required
        or not set(output_field).issubset({"type", "description", "title"})
    ):
        return None

    # Use one field-owned description as the semantic contract. Tool-level
    # prose cannot fill gaps or compose with text about another behavior.
    if type(property_description) is not str or not _has_exhaustive_partition_semantics(
        property_description
    ):
        return None
    return {
        "contract_version": _CONTRACT_VERSION,
        "input_type": "+".join(sorted(allowed_types)),
        "input_optional": True,
        "input_default": "null" if "default" in field else "absent",
        "output_type": "boolean",
        "output_required": True,
    }


def _order_row_schema(
    schema: Mapping[str, object],
) -> tuple[Mapping[str, object], list[str]] | None:
    root_properties = schema.get("properties")
    if (
        schema.get("type") != "object"
        or not isinstance(root_properties, Mapping)
        or not set(schema).issubset(_OUTPUT_ROOT_KEYS)
    ):
        return None
    root_required = schema.get("required")
    if (
        type(root_required) is not list
        or any(type(name) is not str for name in root_required)
        or len(set(root_required)) != len(root_required)
        or not set(root_required).issubset(root_properties)
        or "data" not in root_required
    ):
        return None
    data = root_properties.get("data")
    if not isinstance(data, Mapping):
        return None
    data_properties = data.get("properties")
    data_required = data.get("required")
    if (
        data.get("type") != "object"
        or not isinstance(data_properties, Mapping)
        or type(data_required) is not list
        or any(type(name) is not str for name in data_required)
        or len(set(data_required)) != len(data_required)
        or not set(data_required).issubset(data_properties)
        or "orders" not in data_required
        or not set(data).issubset(_OUTPUT_DATA_KEYS)
    ):
        return None
    orders = data_properties.get("orders")
    if not isinstance(orders, Mapping) or not set(orders).issubset(_OUTPUT_ORDERS_KEYS):
        return None
    order_types = orders.get("type")
    if order_types not in ("array", ["array"], ["null", "array"], ["array", "null"]):
        return None
    item = orders.get("items")
    if not isinstance(item, Mapping) or not set(item).issubset(_OUTPUT_ROW_KEYS):
        return None
    item_types = item.get("type")
    if item_types not in ("object", ["object"], ["null", "object"], ["object", "null"]):
        return None
    row_properties = item.get("properties")
    row_required = item.get("required")
    if (
        _ARRAY_NARROWING_KEYS.intersection(orders)
        or _ARRAY_NARROWING_KEYS.intersection(item)
        or not isinstance(row_properties, Mapping)
        or type(row_required) is not list
        or any(type(name) is not str for name in row_required)
        or len(set(row_required)) != len(row_required)
        or not set(row_required).issubset(row_properties)
    ):
        return None
    return row_properties, row_required


def _has_exhaustive_partition_semantics(description: str) -> bool:
    text = " ".join(description.lower().split())
    clauses = [part.strip() for part in re.split(r"[.;]+", text) if part.strip()]
    if len(clauses) != 3:
        return False
    by_kind: dict[str, list[str]] = {"true": [], "false": [], "omit": []}
    for clause in clauses:
        if (
            clause.startswith("true ")
            or clause.startswith("true:")
            or clause.startswith("true=>")
        ):
            by_kind["true"].append(clause)
        elif (
            clause.startswith("false ")
            or clause.startswith("false:")
            or clause.startswith("false=>")
        ):
            by_kind["false"].append(clause)
        elif (
            clause.startswith("omit ")
            or clause.startswith("omitting ")
            or clause.startswith("omitted ")
        ):
            by_kind["omit"].append(clause)
        else:
            return False
    if any(len(parts) != 1 for parts in by_kind.values()):
        return False
    true_clause = by_kind["true"][0]
    false_clause = by_kind["false"][0]
    omit_clause = by_kind["omit"][0]
    true_is_exhaustive = bool(
        re.fullmatch(
            r"true\s*(?::|=>|means|returns?|includes?)\s*"
            r"(?:only\s+)?(?:all|every)\s+agent[- ]initiated\s+orders?\s+"
            r"(?:from|by)\s+(?:any|all|every)\s+agents?",
            true_clause,
        )
        or re.fullmatch(
            r"true\s*(?::|=>|means|returns?|includes?)\s*"
            r"(?:only\s+)?(?:all|every)\s+orders?\s+initiated\s+by\s+"
            r"(?:any|all|every)\s+agents?",
            true_clause,
        )
    )
    false_is_exhaustive = bool(
        re.fullmatch(
            r"false\s*(?::|=>|means|returns?|includes?)\s*"
            r"(?:only\s+)?(?:all|every)\s+(?:equity\s+)?orders?\s+"
            r"(?:with\s+no\s+agent\s+(?:being\s+)?involved|"
            r"without\s+agent\s+involvement)",
            false_clause,
        )
    )
    omission_is_exhaustive = bool(
        re.fullmatch(
            r"omit(?:ting|ted)?\s+(?:(?:the\s+)?(?:agent_initiated\s+)?"
            r"(?:parameter|filter|argument)\s+)?"
            r"(?:(?:to\s+)?(?:return|include)\s+)?all\s+(?:equity\s+)?orders?",
            omit_clause,
        )
    )
    return true_is_exhaustive and false_is_exhaustive and omission_is_exhaustive


def _read_field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value.get(name, _MISSING)
    try:
        return getattr(value, name)
    except AttributeError:
        return _MISSING


def _read_alias(value: object, aliases: tuple[str, ...]) -> object:
    present = [(name, _read_field(value, name)) for name in aliases]
    present = [(name, item) for name, item in present if item is not _MISSING]
    if len(present) > 1:
        raise ValueError("ambiguous metadata aliases")
    return _MISSING if not present else present[0][1]


def _bounded_schema(schema: Mapping[str, object]) -> None:
    raw = _canonical_json(schema)
    if len(raw) > _MAX_SCHEMA_BYTES:
        raise ValueError("schema exceeds byte bound")
    nodes = 0

    def visit(value: object, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > _MAX_SCHEMA_NODES or depth > _MAX_SCHEMA_DEPTH:
            raise ValueError("schema exceeds structural bounds")
        if value is None or type(value) in {bool, int, str}:
            if type(value) is str:
                value.encode("utf-8", errors="strict")
            return
        if type(value) is float:
            if not math.isfinite(value):
                raise ValueError("schema has a non-finite number")
            return
        if type(value) is list:
            for child in value:
                visit(child, depth + 1)
            return
        if isinstance(value, Mapping):
            for key, child in value.items():
                if type(key) is not str:
                    raise ValueError("schema keys must be strings")
                key.encode("utf-8", errors="strict")
                visit(child, depth + 1)
            return
        raise ValueError("schema contains a non-JSON value")

    visit(schema, 0)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")


def _source_identity(repo_root: Path) -> tuple[str | None, str | None]:
    try:
        head = (
            subprocess.run(
                ["git", "-C", str(repo_root), "rev-parse", "--verify", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            .stdout.strip()
            .lower()
        )
        tree = (
            subprocess.run(
                ["git", "-C", str(repo_root), "rev-parse", "--verify", "HEAD^{tree}"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            .stdout.strip()
            .lower()
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    if not _GIT_OBJECT_ID.fullmatch(head) or not _GIT_OBJECT_ID.fullmatch(tree):
        return None, None
    return head, tree


def _result(
    classification: AgentInitiatedPartitionSchemaClassification,
    *,
    source_head: str | None,
    source_tree: str | None,
    pages: int,
    exhaustive: bool,
    description_sha256: str | None = None,
    input_schema_sha256: str | None = None,
    output_schema_sha256: str | None = None,
    agent_initiated_schema_sha256: str | None = None,
) -> AgentInitiatedPartitionSchemaMatch:
    material = {
        "classification": classification.value,
        "contract_version": _CONTRACT_VERSION,
        "tool_name": _TOOL_NAME,
        "description_sha256": description_sha256,
        "input_schema_sha256": input_schema_sha256,
        "output_schema_sha256": output_schema_sha256,
        "agent_initiated_schema_sha256": agent_initiated_schema_sha256,
        "source_head": source_head,
        "source_tree": source_tree,
        "tools_list_pages": pages,
        "pagination_exhaustive": exhaustive,
        "authenticated": False,
    }
    return AgentInitiatedPartitionSchemaMatch(
        classification=classification,
        contract_version=_CONTRACT_VERSION,
        tool_name=_TOOL_NAME,
        description_sha256=description_sha256,
        input_schema_sha256=input_schema_sha256,
        output_schema_sha256=output_schema_sha256,
        agent_initiated_schema_sha256=agent_initiated_schema_sha256,
        source_head=source_head,
        source_tree=source_tree,
        tools_list_pages=pages,
        pagination_exhaustive=exhaustive,
        evidence_sha256=hashlib.sha256(_canonical_json(material)).hexdigest(),
    )


_MISSING = object()


__all__ = [
    "AgentInitiatedPartitionSchemaClassification",
    "AgentInitiatedPartitionSchemaMatch",
    "AgentInitiatedPartitionSchemaMatcher",
]
