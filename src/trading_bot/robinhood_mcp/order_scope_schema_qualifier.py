"""Inert, schema-only qualification of Robinhood order-query scope.

This module deliberately has no production transport constructor. A caller must
explicitly inject the bounded ``tools/list`` test seam when observing schemas.
The returned classification is source-preparation evidence, not authenticated
production authority. It never invokes a provider tool or connects to OAuth, a
browser, or a network.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import subprocess
from collections.abc import Awaitable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

_TOOL_NAME = "get_equity_orders"
_MAX_PAGES = 25
_MAX_CURSOR_LENGTH = 4096
_MAX_SCHEMA_BYTES = 262_144
_MAX_SCHEMA_NODES = 10_000
_MAX_SCHEMA_DEPTH = 32
_GIT_OBJECT_ID = re.compile(r"[0-9a-f]{40}\Z")
_ALL_AGENT_SCOPE = re.compile(
    r"\bwhen\s+(?:the\s+)?placed_agent(?:\s+parameter)?\s+is\s+omitted,"
    r"\s+(?:the\s+)?(?:result|response|query|call)\s+"
    r"(?:includes|returns|contains)\s+all\s+(?:equity\s+)?orders\s+"
    r"(?:for|in)\s+(?:the\s+)?(?:authenticated\s+)?account\s+"
    r"(?:from|across)\s+all\s+agents[.!]?",
    re.IGNORECASE,
)
_NEGATED_SCOPE = re.compile(
    r"\b(?:not|never|unless|except|excluding|cannot|can't)\b", re.IGNORECASE
)


class OrderScopeClassification(StrEnum):
    PROVEN_ACCOUNT_WIDE_ALL_AGENTS = "PROVEN_ACCOUNT_WIDE_ALL_AGENTS"
    UNPROVEN_PROVIDER_SEMANTICS = "UNPROVEN_PROVIDER_SEMANTICS"
    SCHEMA_MALFORMED = "SCHEMA_MALFORMED"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    SOURCE_AUTHORITY_FAILED = "SOURCE_AUTHORITY_FAILED"


@dataclass(frozen=True, slots=True)
class PlacedAgentSchemaMaterial:
    present: bool
    required: bool
    schema_type: str | None
    description_sha256: str | None
    schema_sha256: str | None


@dataclass(frozen=True, slots=True)
class OrderScopeQualification:
    classification: OrderScopeClassification
    tool_name: str
    description_sha256: str | None
    input_schema_sha256: str | None
    placed_agent: PlacedAgentSchemaMaterial | None
    source_head: str | None
    source_tree: str | None
    tools_list_pages: int
    pagination_exhaustive: bool
    evidence_sha256: str


class _ToolsListTestSeam(Protocol):
    def __call__(self, *, cursor: str | None) -> object | Awaitable[object]: ...


class RobinhoodOrderScopeSchemaQualifier:
    """Collect sanitized schema facts; construction performs no external work."""

    __slots__ = ("_repo_root",)

    def __init__(self, *, repo_root: Path) -> None:
        if not isinstance(repo_root, Path):
            raise TypeError("repo_root must be a Path")
        self._repo_root = repo_root

    async def observe(
        self, *, test_tools_list: _ToolsListTestSeam
    ) -> OrderScopeQualification:
        """Classify test supplied pages; this grants no production authority."""
        if not callable(test_tools_list):
            raise TypeError("an explicit tools/list test seam is required")
        source_head, source_tree = _source_identity(self._repo_root)
        if source_head is None or source_tree is None:
            return _result(
                OrderScopeClassification.SOURCE_AUTHORITY_FAILED,
                source_head=source_head,
                source_tree=source_tree,
                pages=0,
                exhaustive=False,
            )

        cursor: str | None = None
        seen_cursors: set[str] = set()
        seen_target = False
        target_facts: tuple[str, str, PlacedAgentSchemaMaterial, bool] | None = None
        pages = 0
        try:
            for _ in range(_MAX_PAGES):
                page = test_tools_list(cursor=cursor)
                if isinstance(page, Awaitable):
                    page = await page
                pages += 1
                if type(page) is not dict or set(page) != {"tools", "next_cursor"}:
                    return _result(
                        OrderScopeClassification.SCHEMA_MALFORMED,
                        source_head=source_head,
                        source_tree=source_tree,
                        pages=pages,
                        exhaustive=False,
                    )
                tools = page["tools"]
                next_cursor = page["next_cursor"]
                if type(tools) is not list or (
                    next_cursor is not None
                    and (
                        type(next_cursor) is not str
                        or not next_cursor
                        or len(next_cursor) > _MAX_CURSOR_LENGTH
                    )
                ):
                    return _result(
                        OrderScopeClassification.SCHEMA_MALFORMED,
                        source_head=source_head,
                        source_tree=source_tree,
                        pages=pages,
                        exhaustive=False,
                    )
                for tool in tools:
                    if type(tool) is not dict or type(tool.get("name")) is not str:
                        return _result(
                            OrderScopeClassification.SCHEMA_MALFORMED,
                            source_head=source_head,
                            source_tree=source_tree,
                            pages=pages,
                            exhaustive=False,
                        )
                    if tool["name"] != _TOOL_NAME:
                        continue
                    if seen_target:
                        return _result(
                            OrderScopeClassification.SCHEMA_MALFORMED,
                            source_head=source_head,
                            source_tree=source_tree,
                            pages=pages,
                            exhaustive=False,
                        )
                    seen_target = True
                    target_facts = _target_facts(tool)
                if next_cursor is None:
                    break
                if next_cursor in seen_cursors:
                    return _result(
                        OrderScopeClassification.SCHEMA_MALFORMED,
                        source_head=source_head,
                        source_tree=source_tree,
                        pages=pages,
                        exhaustive=False,
                    )
                seen_cursors.add(next_cursor)
                cursor = next_cursor
            else:
                return _result(
                    OrderScopeClassification.SCHEMA_MALFORMED,
                    source_head=source_head,
                    source_tree=source_tree,
                    pages=pages,
                    exhaustive=False,
                )
        except (Exception, asyncio.CancelledError):
            return _result(
                OrderScopeClassification.SCHEMA_MALFORMED,
                source_head=source_head,
                source_tree=source_tree,
                pages=pages,
                exhaustive=False,
            )

        if not seen_target:
            return _result(
                OrderScopeClassification.TOOL_UNAVAILABLE,
                source_head=source_head,
                source_tree=source_tree,
                pages=pages,
                exhaustive=True,
            )
        assert target_facts is not None
        description_sha256, schema_sha256, placed_agent, explicit_scope = target_facts
        return _result(
            (
                OrderScopeClassification.PROVEN_ACCOUNT_WIDE_ALL_AGENTS
                if explicit_scope
                else OrderScopeClassification.UNPROVEN_PROVIDER_SEMANTICS
            ),
            source_head=source_head,
            source_tree=source_tree,
            pages=pages,
            exhaustive=True,
            description_sha256=description_sha256,
            input_schema_sha256=schema_sha256,
            placed_agent=placed_agent,
        )


def _target_facts(
    tool: dict[str, object],
) -> tuple[str, str, PlacedAgentSchemaMaterial, bool]:
    description = tool.get("description")
    schema = tool.get("input_schema")
    if type(description) is not str or not isinstance(schema, Mapping):
        raise ValueError("schema metadata is malformed")
    description_bytes = description.encode("utf-8", errors="strict")
    schema_bytes = _canonical_json(schema)
    if (
        len(description_bytes) > _MAX_SCHEMA_BYTES
        or len(schema_bytes) > _MAX_SCHEMA_BYTES
    ):
        raise ValueError("schema metadata exceeds bounds")
    _validate_json(schema)
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if (
        schema.get("type") != "object"
        or not isinstance(properties, Mapping)
        or type(required) is not list
    ):
        raise ValueError("schema shape is malformed")
    if any(type(item) is not str for item in required) or len(set(required)) != len(
        required
    ):
        raise ValueError("required fields are malformed")
    if any(
        type(key) is not str or not isinstance(value, Mapping)
        for key, value in properties.items()
    ):
        raise ValueError("property schema is malformed")
    if not set(required).issubset(properties):
        raise ValueError("required fields do not resolve to properties")
    property_schema = properties.get("placed_agent")
    if property_schema is None:
        placed = PlacedAgentSchemaMaterial(False, False, None, None, None)
    else:
        type_value = property_schema.get("type")
        if type_value is not None and type(type_value) is not str:
            if (
                type(type_value) is not list
                or not type_value
                or any(type(item) is not str for item in type_value)
                or len(set(type_value)) != len(type_value)
            ):
                raise ValueError("placed_agent type is malformed")
            schema_type = "|".join(sorted(type_value))
        else:
            schema_type = type_value
        property_description = property_schema.get("description")
        if property_description is not None and type(property_description) is not str:
            raise ValueError("placed_agent description is malformed")
        property_digest = (
            None
            if property_description is None
            else hashlib.sha256(property_description.encode("utf-8")).hexdigest()
        )
        placed = PlacedAgentSchemaMaterial(
            True,
            "placed_agent" in required,
            schema_type,
            property_digest,
            hashlib.sha256(_canonical_json(property_schema)).hexdigest(),
        )
    explicit_scope = _explicit_scope(description) or (
        property_schema is not None
        and type(property_schema.get("description")) is str
        and _explicit_scope(property_schema["description"])
    )
    return (
        hashlib.sha256(description_bytes).hexdigest(),
        hashlib.sha256(schema_bytes).hexdigest(),
        placed,
        explicit_scope,
    )


def _explicit_scope(text: str) -> bool:
    if _NEGATED_SCOPE.search(text):
        return False
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return any(_ALL_AGENT_SCOPE.fullmatch(sentence.strip()) for sentence in sentences)


def _validate_json(value: object) -> None:
    nodes = 0

    def visit(item: object, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > _MAX_SCHEMA_NODES or depth > _MAX_SCHEMA_DEPTH:
            raise ValueError("schema exceeds structural bounds")
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is str:
            item.encode("utf-8", errors="strict")
            return
        if type(item) is list:
            for child in item:
                visit(child, depth + 1)
            return
        if isinstance(item, Mapping):
            for key, child in item.items():
                if type(key) is not str:
                    raise ValueError("schema keys must be strings")
                key.encode("utf-8", errors="strict")
                visit(child, depth + 1)
            return
        raise ValueError("schema contains a non-JSON value")

    visit(value, 0)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
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
    if _GIT_OBJECT_ID.fullmatch(head) is None or _GIT_OBJECT_ID.fullmatch(tree) is None:
        return None, None
    return head, tree


def _result(
    classification: OrderScopeClassification,
    *,
    source_head: str | None,
    source_tree: str | None,
    pages: int,
    exhaustive: bool,
    description_sha256: str | None = None,
    input_schema_sha256: str | None = None,
    placed_agent: PlacedAgentSchemaMaterial | None = None,
) -> OrderScopeQualification:
    material = {
        "classification": classification.value,
        "tool_name": _TOOL_NAME,
        "description_sha256": description_sha256,
        "input_schema_sha256": input_schema_sha256,
        "placed_agent": (
            None
            if placed_agent is None
            else {
                "present": placed_agent.present,
                "required": placed_agent.required,
                "schema_type": placed_agent.schema_type,
                "description_sha256": placed_agent.description_sha256,
                "schema_sha256": placed_agent.schema_sha256,
            }
        ),
        "source_head": source_head,
        "source_tree": source_tree,
        "tools_list_pages": pages,
        "pagination_exhaustive": exhaustive,
    }
    digest = hashlib.sha256(_canonical_json(material)).hexdigest()
    return OrderScopeQualification(
        classification,
        _TOOL_NAME,
        description_sha256,
        input_schema_sha256,
        placed_agent,
        source_head,
        source_tree,
        pages,
        exhaustive,
        digest,
    )


__all__ = [
    "OrderScopeClassification",
    "OrderScopeQualification",
    "PlacedAgentSchemaMaterial",
    "RobinhoodOrderScopeSchemaQualifier",
]
