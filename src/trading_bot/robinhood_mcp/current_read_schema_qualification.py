"""Bounded, metadata-only qualification of the current read-tool schemas.

The module has no provider/session constructor and no tool dispatcher. Calling
``qualify_current_read_schemas`` requires an explicit ``tools/list`` callback;
the callback is never used to invoke a provider tool. Only names in the existing
current read allowlist are inspected. Schema presence is evidence about the
advertised shape, not proof of runtime account binding or order completeness.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from trading_bot.robinhood_mcp._current_session import _open_robinhood_client
from trading_bot.robinhood_mcp.current_read_transport import (
    MAX_DISCOVERY_PAGES,
    READ_TOOLS,
)

_MAX_CURSOR_LENGTH: Final = 4096
_MAX_SCHEMA_BYTES: Final = 262_144
_MAX_SCHEMA_NODES: Final = 10_000
_MAX_SCHEMA_DEPTH: Final = 32
_MAX_ARGUMENTS: Final = 256
_FIELD_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")
_JSON_TYPES = frozenset(
    {"array", "boolean", "integer", "null", "number", "object", "string"}
)
_PAGINATION_FIELDS = frozenset(
    {
        "cursor",
        "next",
        "next_cursor",
        "nextCursor",
        "page",
        "page_size",
        "page_token",
        "limit",
        "offset",
    }
)
_ACCOUNT_FIELDS = frozenset({"account_number", "account_id"})
_ORDER_FILTER_FIELDS = frozenset(
    {"placed_agent", "created_at_gte", "created_at_lte", "status", "state", "side"}
)


class SchemaQualificationStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    MALFORMED = "MALFORMED"


class SchemaFieldStatus(StrEnum):
    PRESENT_REQUIRED = "PRESENT_REQUIRED"
    PRESENT_OPTIONAL = "PRESENT_OPTIONAL"
    ABSENT = "ABSENT"
    SCHEMA_UNAVAILABLE = "SCHEMA_UNAVAILABLE"


class OrderScopeQualification(StrEnum):
    SCHEMA_ONLY_UNPROVEN = "SCHEMA_ONLY_UNPROVEN"


@dataclass(frozen=True, slots=True)
class ArgumentSchemaFact:
    name: str
    required: bool
    types: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class ReadToolSchemaFact:
    name: str
    advertised: bool
    input_schema_sha256: str | None
    output_schema_sha256: str | None
    input_arguments_complete: bool
    arguments: tuple[ArgumentSchemaFact, ...]
    account_argument_status: SchemaFieldStatus
    pagination_arguments: tuple[str, ...]
    order_filter_arguments: tuple[str, ...]
    result_schema_shape_complete: bool
    # None means outputSchema was absent or its shape was not closed/inspectable;
    # an empty tuple means a closed schema had no recognizable matching field.
    result_account_binding_paths: tuple[str, ...] | None
    result_pagination_paths: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class CurrentReadSchemaQualification:
    status: SchemaQualificationStatus
    read_tools: tuple[ReadToolSchemaFact, ...]
    tools_list_pages: int
    pagination_complete: bool
    quarantined_tool_count: int
    order_scope: OrderScopeQualification


class _QualificationFailure(Exception):
    def __init__(self, status: SchemaQualificationStatus) -> None:
        super().__init__(status.value)
        self.status = status


_ListTools = Callable[..., object | Awaitable[object]]


async def qualify_current_read_schemas(
    list_tools: _ListTools,
) -> CurrentReadSchemaQualification:
    """Inspect allowlisted tool metadata using only an injected ``tools/list``.

    Provider errors, malformed schemas, missing allowlisted tools, repeated or
    invalid cursors, and page-limit exhaustion yield a sanitized incomplete
    result. No raw descriptions, schema values, provider errors, or unallowlisted
    tool names are returned. This function does not establish the semantics of
    account binding, result completeness, or order scope.
    """
    if not callable(list_tools):
        raise TypeError("list_tools must be an explicit callable")

    seen_cursors: set[str] = set()
    collected: dict[str, ReadToolSchemaFact] = {}
    cursor: str | None = None
    quarantined = 0
    pages = 0
    try:
        for _ in range(MAX_DISCOVERY_PAGES):
            try:
                page = list_tools(cursor=cursor)
                if isinstance(page, Awaitable):
                    page = await page
            except (Exception, asyncio.CancelledError):
                return _result(
                    SchemaQualificationStatus.INCOMPLETE,
                    {},
                    pages,
                    False,
                    quarantined,
                )
            pages += 1
            entries, next_cursor = _page_parts(page)
            for entry in entries:
                name = _field(entry, ("name",))
                if not isinstance(name, str) or not name:
                    raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
                if name not in READ_TOOLS:
                    quarantined += 1
                    continue
                if name in collected:
                    raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
                collected[name] = _tool_facts(entry, name)
            if next_cursor is None:
                missing = set(READ_TOOLS).difference(collected)
                return _result(
                    (
                        SchemaQualificationStatus.INCOMPLETE
                        if missing
                        or any(
                            fact.input_schema_sha256 is None
                            or not fact.input_arguments_complete
                            or any(
                                argument.types is None for argument in fact.arguments
                            )
                            or fact.output_schema_sha256 is None
                            or not fact.result_schema_shape_complete
                            for fact in collected.values()
                        )
                        else SchemaQualificationStatus.COMPLETE
                    ),
                    collected,
                    pages,
                    True,
                    quarantined,
                )
            if (
                not isinstance(next_cursor, str)
                or not next_cursor
                or len(next_cursor) > _MAX_CURSOR_LENGTH
                or next_cursor in seen_cursors
            ):
                raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
            seen_cursors.add(next_cursor)
            cursor = next_cursor
    except _QualificationFailure as exc:
        return _result(exc.status, {}, pages, False, quarantined)
    except (Exception, asyncio.CancelledError):
        return _result(
            SchemaQualificationStatus.MALFORMED, {}, pages, False, quarantined
        )

    return _result(
        SchemaQualificationStatus.INCOMPLETE,
        collected,
        pages,
        False,
        quarantined,
    )


async def qualify_current_read_provider(
    oauth_factory: Callable[[], object],
    *,
    on_attempt: Callable[[str], None] | None = None,
) -> CurrentReadSchemaQualification:
    """Explicitly open the existing lazy provider session for ``tools/list`` only.

    Importing or constructing this module does not call this operation. When
    explicitly invoked, the operation opens the existing read transport session
    and calls only ``list_tools`` through :func:`qualify_current_read_schemas`;
    there is no ``call_tool`` path in this module. Real use requires separate
    review and authorization and is intentionally absent from tests.
    """
    if not callable(oauth_factory):
        raise TypeError("oauth_factory must be callable")

    def notify(name: str) -> None:
        if on_attempt is not None:
            on_attempt(name)

    try:
        async with _open_robinhood_client(
            oauth_factory,
            before_oauth=lambda: notify("oauth_factory"),
            before_mcp_session=lambda: notify("mcp_session"),
        ) as client:
            list_tools = getattr(client, "list_tools", None)
            if not callable(list_tools):
                return _result(
                    SchemaQualificationStatus.INCOMPLETE,
                    {},
                    0,
                    False,
                    0,
                )

            async def count_list_tools(**arguments: object) -> object:
                notify("tools_list_call")
                listing = list_tools(**arguments)
                if isinstance(listing, Awaitable):
                    listing = await listing
                notify("tools_list_page")
                return listing

            return await qualify_current_read_schemas(count_list_tools)
    except asyncio.CancelledError:
        raise
    except Exception:
        return _result(
            SchemaQualificationStatus.INCOMPLETE,
            {},
            0,
            False,
            0,
        )


def _result(
    status: SchemaQualificationStatus,
    collected: Mapping[str, ReadToolSchemaFact],
    pages: int,
    pagination_complete: bool,
    quarantined: int,
) -> CurrentReadSchemaQualification:
    return CurrentReadSchemaQualification(
        status=status,
        read_tools=tuple(
            collected.get(name, _unavailable_fact(name)) for name in READ_TOOLS
        ),
        tools_list_pages=pages,
        pagination_complete=pagination_complete,
        quarantined_tool_count=quarantined,
        order_scope=OrderScopeQualification.SCHEMA_ONLY_UNPROVEN,
    )


def _page_parts(page: object) -> tuple[Sequence[object], str | None]:
    entries = _field(page, ("tools",))
    cursor = _field(page, ("next_cursor", "nextCursor"), required=False)
    if cursor is _MISSING:
        cursor = None
    if (
        not isinstance(entries, Sequence)
        or isinstance(entries, (str, bytes))
        or (cursor is not None and not isinstance(cursor, str))
    ):
        raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
    return entries, cursor


_MISSING = object()


def _unavailable_fact(name: str) -> ReadToolSchemaFact:
    return ReadToolSchemaFact(
        name=name,
        advertised=False,
        input_schema_sha256=None,
        output_schema_sha256=None,
        input_arguments_complete=False,
        arguments=(),
        account_argument_status=SchemaFieldStatus.SCHEMA_UNAVAILABLE,
        pagination_arguments=(),
        order_filter_arguments=(),
        result_schema_shape_complete=False,
        result_account_binding_paths=None,
        result_pagination_paths=None,
    )


def _field(
    source: object,
    aliases: tuple[str, ...],
    *,
    required: bool = True,
) -> object:
    present: list[tuple[str, object]] = []
    for name in aliases:
        if isinstance(source, Mapping) and name in source:
            present.append((name, source[name]))
        elif not isinstance(source, Mapping) and hasattr(source, name):
            present.append((name, getattr(source, name)))
    if len(present) > 1:
        raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
    if not present:
        if required:
            raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
        return _MISSING
    return present[0][1]


def _schema_alias(
    tool: object, aliases: tuple[str, ...]
) -> Mapping[str, object] | None:
    value = _field(tool, aliases, required=False)
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, Mapping):
        raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
    _validate_schema(value)
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _QualificationFailure(SchemaQualificationStatus.MALFORMED) from None
    if len(encoded) > _MAX_SCHEMA_BYTES:
        raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
    return value


def _validate_schema(schema: Mapping[str, object]) -> None:
    stack: list[tuple[object, int]] = [(schema, 0)]
    visited = 0
    while stack:
        value, depth = stack.pop()
        visited += 1
        if visited > _MAX_SCHEMA_NODES or depth > _MAX_SCHEMA_DEPTH:
            raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
        if value is None or isinstance(value, (str, bool, int)):
            continue
        if isinstance(value, float):
            if value != value or value in {float("inf"), float("-inf")}:
                raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
            continue
        if isinstance(value, Mapping):
            if any(not isinstance(key, str) for key in value):
                raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
            stack.extend((item, depth + 1) for item in value.values())
            continue
        if isinstance(value, (list, tuple)):
            stack.extend((item, depth + 1) for item in value)
            continue
        raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)


def _tool_facts(tool: object, name: str) -> ReadToolSchemaFact:
    input_schema = _schema_alias(tool, ("inputSchema", "input_schema"))
    output_schema = _schema_alias(tool, ("outputSchema", "output_schema"))
    if input_schema is None:
        arguments: tuple[ArgumentSchemaFact, ...] = ()
        arguments_complete = False
        account_status = SchemaFieldStatus.SCHEMA_UNAVAILABLE
        pagination_arguments: tuple[str, ...] = ()
        order_filters: tuple[str, ...] = ()
        input_digest = None
    else:
        arguments, arguments_complete = _input_arguments(input_schema)
        account_field = next(
            (item for item in arguments if item.name == "account_number"), None
        )
        account_status = (
            SchemaFieldStatus.ABSENT
            if account_field is None and arguments_complete
            else SchemaFieldStatus.SCHEMA_UNAVAILABLE
            if account_field is None
            else SchemaFieldStatus.PRESENT_REQUIRED
            if account_field.required
            else SchemaFieldStatus.PRESENT_OPTIONAL
        )
        pagination_arguments = tuple(
            item.name for item in arguments if item.name in _PAGINATION_FIELDS
        )
        order_filters = tuple(
            item.name for item in arguments if item.name in _ORDER_FILTER_FIELDS
        )
        input_digest = _digest(input_schema)
    if output_schema is None:
        output_paths = None
        output_shape_complete = False
    else:
        output_paths, output_shape_complete = _schema_paths(output_schema)
    account_paths = (
        None
        if output_paths is None or not output_shape_complete
        else tuple(
            path for path in output_paths if path.rsplit(".", 1)[-1] in _ACCOUNT_FIELDS
        )
    )
    pagination_paths = (
        None
        if output_paths is None or not output_shape_complete
        else tuple(
            path
            for path in output_paths
            if path.rsplit(".", 1)[-1] in _PAGINATION_FIELDS
        )
    )
    return ReadToolSchemaFact(
        name=name,
        advertised=True,
        input_schema_sha256=input_digest,
        output_schema_sha256=(
            None if output_schema is None else _digest(output_schema)
        ),
        input_arguments_complete=arguments_complete,
        arguments=arguments,
        account_argument_status=account_status,
        pagination_arguments=pagination_arguments,
        order_filter_arguments=order_filters,
        result_schema_shape_complete=output_shape_complete,
        result_account_binding_paths=account_paths,
        result_pagination_paths=pagination_paths,
    )


def _input_arguments(
    schema: Mapping[str, object],
) -> tuple[tuple[ArgumentSchemaFact, ...], bool]:
    properties = schema.get("properties", {})
    required_value = schema.get("required", [])
    if (
        schema.get("type") != "object"
        or not isinstance(properties, Mapping)
        or not isinstance(required_value, list)
        or len(properties) > _MAX_ARGUMENTS
        or any(
            not isinstance(name, str) or _FIELD_NAME.fullmatch(name) is None
            for name in properties
        )
        or any(not isinstance(name, str) for name in required_value)
        or len(set(required_value)) != len(required_value)
        or not set(required_value).issubset(properties)
    ):
        raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
    required = frozenset(required_value)
    facts: list[ArgumentSchemaFact] = []
    for name in sorted(properties):
        property_schema = properties[name]
        if not isinstance(property_schema, Mapping):
            raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
        raw_types = property_schema.get("type")
        if raw_types is None:
            types = None
        elif isinstance(raw_types, str):
            types = (raw_types,) if raw_types in _JSON_TYPES else None
            if types is None:
                raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
        elif (
            isinstance(raw_types, list)
            and raw_types
            and all(isinstance(item, str) and item in _JSON_TYPES for item in raw_types)
            and len(set(raw_types)) == len(raw_types)
        ):
            types = tuple(sorted(raw_types))
        else:
            raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
        facts.append(ArgumentSchemaFact(name, name in required, types))
    return tuple(facts), schema.get("additionalProperties") is False


def _schema_paths(schema: Mapping[str, object]) -> tuple[tuple[str, ...], bool]:
    paths: set[str] = set()
    stack: list[tuple[Mapping[str, object], str, int]] = [(schema, "", 0)]
    visited = 0
    shape_complete = True
    while stack:
        node, prefix, depth = stack.pop()
        visited += 1
        if visited > _MAX_SCHEMA_NODES or depth > _MAX_SCHEMA_DEPTH:
            raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
        if any(
            key in node
            for key in (
                "$ref",
                "$dynamicRef",
                "allOf",
                "anyOf",
                "oneOf",
                "not",
                "patternProperties",
            )
        ):
            shape_complete = False
        properties = node.get("properties", {})
        if not isinstance(properties, Mapping):
            raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
        required = node.get("required", [])
        if (
            not isinstance(required, list)
            or any(not isinstance(name, str) for name in required)
            or len(set(required)) != len(required)
            or not set(required).issubset(properties or {})
        ):
            raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
        object_shape_present = node.get("type") == "object" or "properties" in node
        if object_shape_present and node.get("additionalProperties") is not False:
            shape_complete = False
        if node.get("type") is None and "properties" not in node:
            shape_complete = False
        for key, child in (properties or {}).items():
            if (
                not isinstance(key, str)
                or _FIELD_NAME.fullmatch(key) is None
                or not isinstance(child, Mapping)
            ):
                raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
            path = f"{prefix}.{key}" if prefix else key
            if key in _ACCOUNT_FIELDS or key in _PAGINATION_FIELDS:
                paths.add(path)
            stack.append((child, path, depth + 1))
        items = node.get("items")
        if items is not None:
            if not isinstance(items, Mapping):
                raise _QualificationFailure(SchemaQualificationStatus.MALFORMED)
            stack.append((items, f"{prefix}[]", depth + 1))
    return tuple(sorted(paths)), shape_complete


def _digest(schema: Mapping[str, object]) -> str:
    material = json.dumps(
        schema,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(material).hexdigest()
