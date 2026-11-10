from __future__ import annotations

import hashlib
import inspect
import json
import logging
import os
import sys
import warnings
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.live_prototype import capability_schema_discovery_l41r5 as discovery

_HEAD = "1" * 40
_TREE = "2" * 40
_OAUTH = object()
_PROHIBITED_COUNTERS = {
    "mcp_tool_invocation_attempts",
    "get_accounts_attempts",
    "get_equity_tradability_attempts",
    "get_positions_attempts",
    "get_orders_attempts",
    "get_portfolio_attempts",
    "get_quotes_attempts",
    "review_equity_order_attempts",
    "place_equity_order_attempts",
    "cancel_equity_order_attempts",
    "other_tool_attempts",
}


def _source(**overrides: object) -> discovery.SourceAdmission:
    values: dict[str, object] = {
        "branch": "feature/robinhood-live-prototype-current",
        "head": _HEAD,
        "tree": _TREE,
        "origin_feature_head": _HEAD,
        "origin_feature_tree": _TREE,
        "origin_develop_head": _HEAD,
        "origin_develop_tree": _TREE,
        "feature_authority": "PASS",
        "prospective_develop_authority": "PASS",
    }
    values.update(overrides)
    return discovery.SourceAdmission(**values)  # type: ignore[arg-type]


def _schema(
    quantity: object | None = None,
    *,
    required: Sequence[str] = (),
    properties: Mapping[str, object] | None = None,
) -> dict[str, object]:
    fields = (
        {"quantity": {"type": "string"}} if properties is None else dict(properties)
    )
    if quantity is not None:
        fields["quantity"] = quantity
    return {
        "type": "object",
        "properties": fields,
        "required": list(required),
    }


def _tool(
    name: str,
    *,
    schema: object | None = None,
    description: str | None = None,
) -> object:
    if schema is None:
        schema = _schema()
    if description is None:
        description = (
            "Simulates a pre-trade warning and does not place an order."
            if name == "review_equity_order"
            else "Places an equity order."
        )
    return SimpleNamespace(
        name=name,
        description=description,
        input_schema=schema,
    )


def _tools(
    *,
    review_schema: object | None = None,
    place_schema: object | None = None,
    review_description: str | None = None,
    place_description: str | None = None,
) -> list[object]:
    return [
        _tool(
            "review_equity_order",
            schema=review_schema,
            description=review_description,
        ),
        _tool(
            "place_equity_order",
            schema=place_schema,
            description=place_description,
        ),
        _tool(
            "get_equity_tradability",
            schema=_schema(
                properties={
                    "symbol": {"type": "string"},
                    "market_hours": {"type": "string"},
                },
                required=["symbol", "market_hours"],
            ),
            description="Read the symbol trading eligibility metadata.",
        ),
    ]


def _fixture_baseline(
    pages: Sequence[tuple[Sequence[object], str | None]],
) -> dict[str, str]:
    baseline: dict[str, str] = {}
    for entry in _tools():
        name = discovery._read_field(entry, "name")
        schema = discovery._read_input_schema(entry)
        description = discovery._read_field(entry, "description")
        baseline[name] = discovery._original_interface_hashes(
            name, schema, description
        )["interface_sha256"]
    seen: set[str] = set()
    for entries, _cursor in pages:
        for entry in entries:
            name = discovery._read_field(entry, "name")
            if name not in discovery._INSPECTED_TOOLS or name in seen:
                continue
            schema = discovery._read_input_schema(entry)
            description = discovery._read_field(entry, "description")
            baseline[name] = discovery._original_interface_hashes(
                name, schema, description
            )["interface_sha256"]
            seen.add(name)
    return baseline


def _emit_noise(prefix: str) -> None:
    print(f"{prefix}_STDOUT")
    print(f"{prefix}_STDERR", file=sys.stderr)
    warnings.warn(f"{prefix}_WARNING", stacklevel=2)
    logging.getLogger("mcp").warning(f"{prefix}_LOG")
    os.write(1, f"{prefix}_NATIVE_STDOUT\n".encode())
    os.write(2, f"{prefix}_NATIVE_STDERR\n".encode())


class _FakeClient:
    def __init__(
        self,
        pages: Sequence[tuple[Sequence[object], str | None]],
        events: list[str],
        *,
        noise: bool = False,
    ) -> None:
        self.pages = pages
        self.events = events
        self.noise = noise
        self.calls: list[tuple[str, Mapping[str, object]]] = []

    async def list_tools(self, *, cursor: str | None = None) -> object:
        self.events.append("tools_list")
        if self.noise:
            _emit_noise("SECRET_PROVIDER")
        index = 0 if cursor is None else int(cursor)
        entries, next_cursor = self.pages[index]
        return SimpleNamespace(tools=entries, next_cursor=next_cursor)

    async def call_tool(self, name: str, arguments: Mapping[str, object]) -> object:
        self.calls.append((name, arguments))
        raise AssertionError("L41R5 must never invoke an MCP tool")


class _OuterSessionCloseError(RuntimeError):
    reason = "L41R3_SESSION_CLOSE_FAILED"


class _OuterExitFailure:
    def __init__(self, inner: discovery._L41R5SchemaDiscoveryTransport) -> None:
        self._inner = inner
        self.schemas: tuple[dict[str, object], ...] = ()

    @property
    def attempt_counts(self) -> discovery.SchemaDiscoveryAttemptCounts:
        return self._inner.attempt_counts

    @property
    def structural_fingerprints(self) -> tuple[dict[str, object], ...]:
        return self._inner.structural_fingerprints

    def __enter__(self) -> _OuterExitFailure:
        self._inner.__enter__()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self._inner.__exit__(exc_type, exc, traceback)
        if exc_type is None:
            raise _OuterSessionCloseError("synthetic outer teardown failure")
        return False

    def discover(self) -> tuple[dict[str, object], ...]:
        self.schemas = self._inner.discover()
        return self.schemas


def _run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    pages: Sequence[tuple[Sequence[object], str | None]] | None = None,
    source: discovery.SourceAdmission | None = None,
    noise: bool = False,
    construction_noise: bool = False,
    session_close_error: bool = False,
    outer_exit_error: bool = False,
    expected_schema_digests: Mapping[str, str] | None = None,
) -> tuple[discovery.L41R5SchemaDiscoveryResult, _FakeClient, list[str]]:
    events: list[str] = []
    evidence_number = len(tuple(tmp_path.glob("evidence-*")))
    evidence_dir = tmp_path / f"evidence-{evidence_number}"
    selected_pages = [(_tools(), None)] if pages is None else list(pages)
    fixture_baseline = (
        _fixture_baseline(selected_pages)
        if expected_schema_digests is None
        else dict(expected_schema_digests)
    )

    def create_evidence_dir(path: Path) -> Path:
        path.mkdir(parents=True)
        return path

    monkeypatch.setattr(discovery, "_fresh_evidence_dir", create_evidence_dir)
    client = _FakeClient(selected_pages, events, noise=noise)

    @asynccontextmanager
    async def session_factory(oauth: object):
        assert oauth is _OAUTH
        events.append("session_open")
        try:
            yield client
        finally:
            events.append("session_close")
            if session_close_error:
                raise RuntimeError("SECRET_SESSION_CLOSE_FAILURE")

    def oauth_builder() -> discovery._OAuthFactoryBundle:
        events.append("oauth_factory_builder")
        if construction_noise:
            _emit_noise("SECRET_OAUTH_BUILDER")

        def oauth_factory() -> object:
            events.append("oauth_scope_entry")
            return _OAUTH

        opener = discovery._OneShotBrowserOpener(
            lambda _url: events.append("browser") or True
        )
        return discovery._OAuthFactoryBundle(oauth_factory, opener)

    def source_admitter(root: Path) -> discovery.SourceAdmission:
        assert root == tmp_path
        events.append("source")
        return _source() if source is None else source

    def transport_builder(oauth: object) -> object:
        transport = discovery._L41R5SchemaDiscoveryTransport(
            oauth,  # type: ignore[arg-type]
            session_factory=session_factory,
            expected_schema_digests=fixture_baseline,
        )
        return _OuterExitFailure(transport) if outer_exit_error else transport

    result = discovery._run_with_dependencies(
        evidence_dir=evidence_dir,
        source_admitter=source_admitter,
        oauth_factory_builder=oauth_builder,
        transport_builder=transport_builder,
        repository_root_resolver=lambda: tmp_path,
        expected_schema_digests=fixture_baseline,
    )
    return result, client, events


def _fingerprint(
    result: discovery.L41R5SchemaDiscoveryResult, tool_name: str = "review_equity_order"
) -> dict[str, object]:
    return next(
        item
        for item in result.structural_fingerprints
        if item["tool_name"] == tool_name
    )


@pytest.mark.parametrize(
    "types",
    [
        ["string", "null"],
        ["null", "string"],
    ],
)
@pytest.mark.parametrize("required", [False, True])
def test_type_list_nullable_string_is_proven_independently_from_requiredness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    types: list[str],
    required: bool,
) -> None:
    required_names = ["quantity"] if required else []
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[
            (
                _tools(review_schema=_schema({"type": types}, required=required_names)),
                None,
            )
        ],
    )

    assert result.status == "CAPTURED_FOR_REVIEW"
    review = next(
        item for item in result.schemas if item["tool_name"] == "review_equity_order"
    )
    assert review["quantity_logical_non_null_type"] == "string"
    assert review["quantity_nullable"] is True
    assert review["quantity_field_required"] is required
    fingerprint = _fingerprint(result)
    field = fingerprint["fields"]["quantity"]
    assert field["classification"] == "QUANTITY_NULLABLE_STRING"
    assert field["required"] is required


@pytest.mark.parametrize("keyword", ["anyOf", "oneOf"])
@pytest.mark.parametrize("reverse", [False, True])
def test_disjoint_string_null_branches_are_supported(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    keyword: str,
    reverse: bool,
) -> None:
    branches = [{"type": "string"}, {"type": "null"}]
    if reverse:
        branches.reverse()
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[
            (
                _tools(
                    review_schema=_schema(
                        {"description": "quantity", keyword: branches}
                    )
                ),
                None,
            )
        ],
    )

    assert result.status == "CAPTURED_FOR_REVIEW"
    review = next(
        item for item in result.schemas if item["tool_name"] == "review_equity_order"
    )
    assert review["quantity_logical_non_null_type"] == "string"
    assert review["quantity_nullable"] is True
    assert _fingerprint(result)["fields"]["quantity"]["union_keyword"] == keyword


def test_direct_and_nullable_forms_keep_distinct_original_digests(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    direct, _, _ = _run(monkeypatch, tmp_path)
    nullable, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[
            (
                _tools(review_schema=_schema({"type": ["string", "null"]})),
                None,
            )
        ],
    )
    direct_review = next(
        item for item in direct.schemas if item["tool_name"] == "review_equity_order"
    )
    nullable_review = next(
        item for item in nullable.schemas if item["tool_name"] == "review_equity_order"
    )

    assert direct_review["quantity_logical_non_null_type"] == "string"
    assert nullable_review["quantity_logical_non_null_type"] == "string"
    assert direct_review["quantity_nullable"] is False
    assert nullable_review["quantity_nullable"] is True
    assert (
        direct_review["input_schema_sha256"] != nullable_review["input_schema_sha256"]
    )
    assert direct_review["interface_sha256"] != nullable_review["interface_sha256"]


def test_dollar_amount_nullable_facts_remain_separate_from_requiredness(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    schema = _schema(
        properties={
            "quantity": {"type": "string"},
            "dollar_amount": {"type": ["null", "string"]},
        },
        required=["dollar_amount"],
    )
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[(_tools(review_schema=schema), None)],
    )
    review = next(
        item for item in result.schemas if item["tool_name"] == "review_equity_order"
    )

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert review["dollar_amount_logical_non_null_type"] == "string"
    assert review["dollar_amount_nullable"] is True
    assert review["dollar_amount_field_required"] is True


@pytest.mark.parametrize(
    ("quantity", "expected_reason", "expected_types"),
    [
        (
            {"type": ["string", "number", "null"]},
            "L41R5_QUANTITY_MULTI_NON_NULL_UNION",
            ["null", "number", "string"],
        ),
        (
            {
                "anyOf": [
                    {"type": "string"},
                    {"type": "number"},
                ]
            },
            "L41R5_QUANTITY_MULTI_NON_NULL_UNION",
            ["number", "string"],
        ),
        (
            {
                "anyOf": [
                    {"type": "string"},
                    {"$ref": "secret/callback/token"},
                ]
            },
            "L41R5_QUANTITY_UNRESOLVED_REF",
            ["string"],
        ),
        (
            {"allOf": [{"type": "string"}, {"type": "null"}]},
            "L41R5_QUANTITY_UNSUPPORTED_COMPOSITION",
            ["null", "string"],
        ),
    ],
)
def test_unsupported_union_shapes_fail_closed_with_structural_types(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    quantity: object,
    expected_reason: str,
    expected_types: list[str],
) -> None:
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[(_tools(review_schema=_schema(quantity)), None)],
    )

    assert result.status == "BLOCKED"
    assert result.reason == expected_reason
    assert _fingerprint(result)["fields"]["quantity"]["union_primitive_types"] == (
        expected_types
    )
    if "secret/callback/token" in str(quantity):
        assert "secret/callback/token" not in result.evidence_path.read_text(
            encoding="utf-8"
        )


@pytest.mark.parametrize(
    ("quantity", "expected_reason"),
    [
        ({"type": "null"}, "L41R5_QUANTITY_NULL_ONLY_UNION"),
        ({"type": ["string", 7]}, "L41R5_QUANTITY_INVALID_TYPE"),
        (
            {
                "type": "string",
                "anyOf": [{"type": "string"}, {"type": "null"}],
            },
            "L41R5_QUANTITY_UNSUPPORTED_CONSTRAINT",
        ),
    ],
)
def test_null_only_malformed_and_contradictory_field_types_fail_precisely(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    quantity: object,
    expected_reason: str,
) -> None:
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[(_tools(review_schema=_schema(quantity)), None)],
    )

    assert result.status == "BLOCKED"
    assert result.reason == expected_reason


@pytest.mark.parametrize(
    "quantity",
    [
        {"anyOf": [{"type": "string"}, {"type": "null"}], "const": "x"},
        {"type": ["string", "null"], "enum": ["x"]},
        {"anyOf": [{"type": "string", "not": {"type": "string"}}, {"type": "null"}]},
        {"type": {"token": "secret"}},
        {"type": ["string", "string"]},
    ],
)
def test_unresolved_or_malformed_constraints_do_not_claim_nullable_string(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, quantity: object
) -> None:
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[(_tools(review_schema=_schema(quantity)), None)],
    )

    field = _fingerprint(result)["fields"]["quantity"]
    assert result.status == "BLOCKED"
    assert field["nullable"] is None
    assert field["logical_non_null_type"] is None
    assert field["classification"] in {
        "UNSUPPORTED_CONSTRAINT",
        "UNSUPPORTED_COMPOSITION",
        "INVALID_TYPE",
    }
    if isinstance(quantity, Mapping):
        for keyword in ("const", "enum", "not"):
            if keyword in quantity:
                assert keyword in field["schema_keyword_names"]


@pytest.mark.parametrize(
    ("root_constraint", "expected_reason"),
    [
        (
            {"$ref": "private/root/schema"},
            "L41R5_TOP_LEVEL_UNRESOLVED_REF",
        ),
        (
            {"allOf": [{"properties": {"quantity": {"type": "null"}}}]},
            "L41R5_TOP_LEVEL_UNSUPPORTED_COMPOSITION",
        ),
        (
            {"if": {"properties": {"quantity": {"const": None}}}},
            "L41R5_TOP_LEVEL_UNSUPPORTED_CONSTRAINT",
        ),
        (
            {"$schema": "https://private.invalid/schema?token=SECRET_VALUE"},
            "L41R5_TOP_LEVEL_UNSUPPORTED_CONSTRAINT",
        ),
        (
            {"x-private-callback-token-key": True},
            "L41R5_TOP_LEVEL_UNSUPPORTED_CONSTRAINT",
        ),
    ],
)
def test_root_schema_composition_cannot_claim_nullable_field_proof(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    root_constraint: Mapping[str, object],
    expected_reason: str,
) -> None:
    schema = _schema({"type": ["string", "null"]})
    schema.update(root_constraint)
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[(_tools(review_schema=schema), None)],
    )
    field = _fingerprint(result)["fields"]["quantity"]
    evidence = result.evidence_path.read_text(encoding="utf-8")
    keyword_names = _fingerprint(result)["schema_keyword_names"]

    assert result.reason == expected_reason
    assert field["nullable"] is None
    assert field["logical_non_null_type"] is None
    assert expected_reason in _fingerprint(result)["ambiguity_classes"]
    assert "private/root/schema" not in evidence
    if "$schema" in root_constraint:
        assert "$schema" in keyword_names
        assert "SECRET_VALUE" not in evidence
    if "x-private-callback-token-key" in root_constraint:
        assert "x-private-callback-token-key" not in evidence
        assert any(name.startswith("other_sha256:") for name in keyword_names)


def test_required_not_in_properties_has_explicit_non_schema_validity_class(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[
            (
                _tools(
                    review_schema=_schema(
                        properties={"dollar_amount": {"type": "string"}},
                        required=["quantity"],
                    )
                ),
                None,
            )
        ],
    )

    assert result.status == "BLOCKED"
    assert result.reason == "L41R5_REQUIRED_NOT_IN_PROPERTIES"
    assert _fingerprint(result)["ambiguity_classes"] == [
        "L41R5_REQUIRED_NOT_IN_PROPERTIES"
    ]
    assert _fingerprint(result)["required_not_in_properties"] == ["quantity"]


@pytest.mark.parametrize(
    ("name", "description", "expected_reason"),
    [
        (
            "review_equity_order",
            "Places an order. SECRET_CALLBACK_TOKEN_123",
            "L41R5_REVIEW_PLACEMENT_SEMANTIC_CONFLICT",
        ),
        (
            "place_equity_order",
            "Does not place an order. SECRET_CALLBACK_TOKEN_456",
            "L41R5_PLACE_NONPLACEMENT_SEMANTIC_CONFLICT",
        ),
    ],
)
def test_description_semantic_conflicts_retain_flags_without_raw_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    name: str,
    description: str,
    expected_reason: str,
) -> None:
    tools = _tools()
    target_index = 0 if name == "review_equity_order" else 1
    tools[target_index] = _tool(
        name,
        description=description,
        schema=_schema(),
    )
    result, _, _ = _run(monkeypatch, tmp_path, pages=[(tools, None)])

    evidence = result.evidence_path.read_text(encoding="utf-8")
    fingerprint = _fingerprint(result, name)
    assert result.reason == expected_reason
    assert "SECRET_CALLBACK_TOKEN" not in evidence
    assert fingerprint["tool_description_classification"]["explicitly_nonplacing"] is (
        name == "place_equity_order"
    )


@pytest.mark.parametrize(
    ("description", "expected_reason", "precision_values"),
    [
        (
            "Fractional regular market hours allow up to 6 decimal places and "
            "maximum 8 decimal places.",
            "L41R5_FRACTIONAL_PRECISION_PROVENANCE_CONFLICT",
            [6, 8],
        ),
        (
            "Fractional regular market hours allow up to 0 decimal places.",
            "L41R5_FRACTIONAL_PRECISION_INVALID",
            [0],
        ),
    ],
)
def test_fractional_precision_ambiguity_is_sanitized_and_specific(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    description: str,
    expected_reason: str,
    precision_values: list[int],
) -> None:
    tools = _tools()
    tools[0] = _tool(
        "review_equity_order",
        description=description + " PRIVATE_PROSE_CALLBACK_TOKEN",
        schema=_schema(),
    )
    result, _, _ = _run(monkeypatch, tmp_path, pages=[(tools, None)])
    fingerprint = _fingerprint(result)

    assert result.reason == expected_reason
    assert fingerprint["fractional_precision_decimal_places"] == precision_values
    assert "PRIVATE_PROSE" not in result.evidence_path.read_text(encoding="utf-8")


def test_unknown_property_names_and_defaults_are_hashed_or_boolean_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret_name = "callback=Bearer PRIVATE_TOKEN_ABC"
    quantity = {"type": "string", "default": "PRIVATE_DEFAULT_TOKEN"}
    schema = _schema(
        quantity,
        properties={
            "quantity": quantity,
            secret_name: {"type": "string"},
        },
    )
    result, _, _ = _run(
        monkeypatch, tmp_path, pages=[(_tools(review_schema=schema), None)]
    )
    evidence = result.evidence_path.read_text(encoding="utf-8")
    fingerprint = _fingerprint(result)

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert secret_name not in evidence
    assert "PRIVATE_DEFAULT_TOKEN" not in evidence
    assert "PRIVATE_TOKEN_ABC" not in evidence
    assert fingerprint["fields"]["quantity"]["default_present"] is True
    assert fingerprint["fields"]["quantity"]["default_is_null"] is False
    assert any(
        value.startswith("other_sha256:") for value in fingerprint["property_names"]
    )


@pytest.mark.parametrize(
    "schema",
    [
        "secret provider schema body",
        {"type": None, "properties": {"quantity": {"type": "string"}}},
    ],
)
def test_malformed_schema_retains_a_bounded_fingerprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, schema: object
) -> None:
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[(_tools(review_schema=schema), None)],
    )

    assert result.status == "BLOCKED"
    assert result.reason == "L41R5_SCHEMA_MALFORMED"
    assert result.structural_fingerprints
    assert "secret provider schema body" not in result.evidence_path.read_text(
        encoding="utf-8"
    )


def test_original_digest_baseline_mismatch_and_missing_optional_tool_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    accepted, _, _ = _run(monkeypatch, tmp_path)
    accepted_baseline = {
        item["tool_name"]: item["interface_sha256"] for item in accepted.schemas
    }
    baseline = {
        **accepted_baseline,
        "review_equity_order": "0" * 64,
    }
    mismatch, _, _ = _run(
        monkeypatch,
        tmp_path,
        expected_schema_digests=baseline,
    )
    assert mismatch.reason == "L41R5_SCHEMA_CHANGED"
    assert mismatch.structural_fingerprints

    missing_optional, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[(_tools()[:2], None)],
        expected_schema_digests={
            **accepted_baseline,
        },
    )
    assert missing_optional.reason == "L41R5_REQUIRED_SCHEMA_MISSING"


def test_original_schema_change_is_not_hidden_by_equal_scalar_projection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    direct = _schema({"type": "string"})
    nullable = _schema({"type": ["string", "null"]})
    pages = [
        (
            [
                _tool(
                    "review_equity_order",
                    schema=direct,
                    description=(
                        "Simulates a pre-trade warning and does not place an order."
                    ),
                ),
                _tool(
                    "place_equity_order",
                    schema=_schema(),
                    description="Places an equity order.",
                ),
            ],
            "1",
        ),
        (
            [
                _tool(
                    "review_equity_order",
                    schema=nullable,
                    description=(
                        "Simulates a pre-trade warning and does not place an order."
                    ),
                )
            ],
            None,
        ),
    ]
    result, _, _ = _run(monkeypatch, tmp_path, pages=pages)

    assert result.reason == "L41R5_SCHEMA_CHANGED"
    assert _fingerprint(result)["input_schema_sha256"]


def test_pagination_is_bounded_and_tool_invocation_surface_is_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pages = []
    for index in range(discovery._MAX_DISCOVERY_PAGES):
        tools = _tools() if index == 0 else [_tool("uninspected_tool")]
        pages.append((tools, str(index + 1)))
    result, client, events = _run(monkeypatch, tmp_path, pages=pages)

    assert result.reason == "L41R5_TOOL_PAGINATION_BOUND_EXCEEDED"
    assert result.attempt_counts.tools_list_attempts == 20
    assert client.calls == []
    assert events.count("tools_list") == 20
    assert not hasattr(discovery._L41R5SchemaDiscoveryTransport, "call_tool")
    assert all(
        getattr(result.attempt_counts, name) == 0 for name in _PROHIBITED_COUNTERS
    )


def test_repeated_cursor_fails_closed_with_bounded_attempt_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[
            (_tools(), "1"),
            ([_tool("uninspected_tool")], "1"),
        ],
    )

    assert result.reason == "L41R5_TOOL_CURSOR_INVALID"
    assert result.attempt_counts.tools_list_attempts == 2
    assert result.structural_fingerprints


def test_ambiguous_fingerprint_survives_session_teardown_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[
            (
                _tools(review_schema=_schema({"type": ["string", "number", "null"]})),
                None,
            )
        ],
        session_close_error=True,
    )

    assert result.status == "BLOCKED"
    assert result.reason == "L41R5_QUANTITY_MULTI_NON_NULL_UNION"
    assert not result.schemas
    assert _fingerprint(result)["fields"]["quantity"]["union_primitive_types"] == (
        ["null", "number", "string"]
    )


def test_outer_teardown_failure_after_returned_schemas_is_blocked_but_retains_facts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, _, _ = _run(monkeypatch, tmp_path, outer_exit_error=True)

    assert result.status == "BLOCKED"
    assert result.reason == "L41R5_SESSION_CLOSE_FAILED"
    assert result.schemas
    assert result.structural_fingerprints
    assert (
        _fingerprint(result)["fields"]["quantity"]["logical_non_null_type"] == "string"
    )


def test_output_suppression_and_source_admission_precede_oauth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    result, _, events = _run(
        monkeypatch,
        tmp_path,
        noise=True,
        construction_noise=True,
    )
    output = capfd.readouterr()

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert output.out == ""
    assert output.err == ""
    assert events.index("source") < events.index("oauth_factory_builder")
    assert events.count("oauth_scope_entry") == 1
    assert events.count("session_open") == 1
    assert events.count("tools_list") == 1
    assert events.count("session_close") == 1
    assert "browser" not in events
    assert all(
        getattr(result.attempt_counts, name) == 0 for name in _PROHIBITED_COUNTERS
    )


def test_source_rejection_prevents_oauth_or_session_creation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, _, events = _run(
        monkeypatch,
        tmp_path,
        source=_source(feature_authority="NOT_RUN"),
    )

    assert result.reason == "L41R5_SOURCE_ADMISSION_BLOCKED"
    assert events == ["source"]
    assert result.attempt_counts.oauth_scope_entry_attempts == 0
    assert result.attempt_counts.mcp_session_open_attempts == 0


def test_browser_opener_is_one_shot() -> None:
    calls: list[str] = []
    opener = discovery._OneShotBrowserOpener(lambda url: calls.append(url) or True)

    assert opener("https://example.invalid/oauth") is True
    with pytest.raises(RuntimeError, match="L41R5_BROWSER_LAUNCH_ALREADY_USED"):
        opener("https://example.invalid/second")
    assert calls == ["https://example.invalid/oauth"]
    assert opener.launch_count == 1


def test_evidence_directory_creation_never_overwrites_existing_evidence(
    tmp_path: Path,
) -> None:
    parent_root = tmp_path.resolve(strict=True)
    evidence_dir = parent_root / "fresh"
    created = discovery._create_fresh_evidence_dir_under_root(evidence_dir, parent_root)
    assert created.is_dir()
    evidence_path = created / "evidence.json"
    original_evidence = b"original evidence\n"
    evidence_path.write_bytes(original_evidence)

    with pytest.raises(ValueError, match="L41R5_EVIDENCE_PATH_INVALID"):
        discovery._create_fresh_evidence_dir_under_root(evidence_dir, parent_root)

    assert evidence_path.read_bytes() == original_evidence


def test_fresh_evidence_dir_rejects_non_f_drive_with_monkeypatched_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    parent_root = Path.home().resolve(strict=True)
    monkeypatch.setattr(discovery, "_EVIDENCE_ROOT", parent_root)
    evidence_dir = parent_root / f"l41r5-non-f-drive-{tmp_path.name}"
    assert evidence_dir.drive.casefold() != "f:"
    assert not evidence_dir.exists()

    with pytest.raises(ValueError, match="L41R5_EVIDENCE_PATH_INVALID"):
        discovery._fresh_evidence_dir(evidence_dir)

    assert not evidence_dir.exists()


@pytest.mark.parametrize(
    ("additional_value", "expected_form"),
    [(False, "BOOLEAN_FALSE"), (True, "BOOLEAN_TRUE")],
)
@pytest.mark.parametrize("required_names", [[], ["quantity", "dollar_amount"]])
def test_boolean_additional_properties_preserves_named_field_facts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    additional_value: bool,
    expected_form: str,
    required_names: list[str],
) -> None:
    schema = _schema(
        properties={
            "quantity": {"type": "string"},
            "dollar_amount": {"type": "string"},
        },
        required=required_names,
    )
    schema["additionalProperties"] = additional_value
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[(_tools(review_schema=schema), None)],
    )

    assert result.status == "CAPTURED_FOR_REVIEW"
    fingerprint = _fingerprint(result)
    assert fingerprint["additional_properties_present"] is True
    assert fingerprint["additional_properties_form"] == expected_form
    assert fingerprint["ambiguity_classes"] == []
    assert fingerprint["fields"]["quantity"]["logical_non_null_type"] == "string"
    assert fingerprint["fields"]["quantity"]["nullable"] is False
    assert fingerprint["fields"]["quantity"]["required"] is (
        "quantity" in required_names
    )
    assert fingerprint["fields"]["dollar_amount"]["logical_non_null_type"] == "string"
    assert fingerprint["fields"]["dollar_amount"]["required"] is (
        "dollar_amount" in required_names
    )


def test_missing_additional_properties_uses_json_schema_default_for_named_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, _, _ = _run(monkeypatch, tmp_path)
    fingerprint = _fingerprint(result)

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert fingerprint["additional_properties_present"] is False
    assert fingerprint["additional_properties_form"] == "MISSING"
    assert fingerprint["fields"]["quantity"]["logical_non_null_type"] == "string"


@pytest.mark.parametrize(
    ("additional_value", "expected_reference", "expected_compositions"),
    [
        (
            {
                "type": "object",
                "$ref": "private/callback/Bearer_TOKEN_123",
                "description": "NESTED_SCHEMA_SECRET_123",
            },
            True,
            [],
        ),
        (
            {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "examples": ["PRIVATE_EXAMPLE_TOKEN"],
            },
            False,
            ["anyOf"],
        ),
    ],
)
def test_schema_valued_additional_properties_is_sanitized_and_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    additional_value: Mapping[str, object],
    expected_reference: bool,
    expected_compositions: list[str],
) -> None:
    schema = _schema()
    schema["additionalProperties"] = additional_value
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[(_tools(review_schema=schema), None)],
    )
    fingerprint = _fingerprint(result)
    evidence = result.evidence_path.read_text(encoding="utf-8")

    assert result.status == "BLOCKED"
    assert result.reason == "L41R5_ADDITIONAL_PROPERTIES_SCHEMA_UNSUPPORTED"
    assert fingerprint["additional_properties_form"] == "SCHEMA_MAPPING"
    assert fingerprint["additional_properties_schema_sha256"]
    assert fingerprint["additional_properties_schema_keyword_inventory_sha256"]
    assert (
        fingerprint["additional_properties_schema_contains_reference"]
        is expected_reference
    )
    assert (
        fingerprint["additional_properties_schema_composition_names"]
        == expected_compositions
    )
    assert "private/callback/Bearer_TOKEN_123" not in evidence
    assert "NESTED_SCHEMA_SECRET_123" not in evidence
    assert "PRIVATE_EXAMPLE_TOKEN" not in evidence


@pytest.mark.parametrize("additional_value", [None, 0, "false", []])
def test_invalid_additional_properties_forms_block_distinctly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    additional_value: object,
) -> None:
    schema = _schema()
    schema["additionalProperties"] = additional_value
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[(_tools(review_schema=schema), None)],
    )

    assert result.status == "BLOCKED"
    assert result.reason == "L41R5_ADDITIONAL_PROPERTIES_INVALID"
    assert _fingerprint(result)["additional_properties_form"] == "INVALID"


def test_boolean_additional_properties_does_not_whitelist_other_root_keywords(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    schema = _schema({"type": ["string", "null"]})
    schema["additionalProperties"] = False
    schema["patternProperties"] = {"secret-pattern": {"type": "string"}}
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[(_tools(review_schema=schema), None)],
    )
    field = _fingerprint(result)["fields"]["quantity"]

    assert result.reason == "L41R5_TOP_LEVEL_UNSUPPORTED_CONSTRAINT"
    assert field["nullable"] is None
    assert field["logical_non_null_type"] is None
    assert "secret-pattern" not in result.evidence_path.read_text(encoding="utf-8")


def test_baseline_hashes_bind_original_schema_not_projected_schema(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    schema = _schema(
        properties={
            "quantity": {"type": "string", "description": "NESTED_PRIVATE_TEXT"},
            "dollar_amount": {"type": "string"},
        }
    )
    schema["additionalProperties"] = False
    description = "Simulates a pre-trade warning and does not place an order."
    original = discovery._original_interface_hashes(
        "review_equity_order", schema, description
    )
    inspected = discovery._inspect_schema(
        "review_equity_order", schema, description, original=original
    )
    projected = inspected["normalized_schema"]
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[(_tools(review_schema=schema, review_description=description), None)],
    )
    record = next(
        item for item in result.schemas if item["tool_name"] == "review_equity_order"
    )

    assert record["input_schema_sha256"] == original["input_schema_sha256"]
    assert record["description_sha256"] == original["description_sha256"]
    assert record["interface_sha256"] == original["interface_sha256"]
    assert (
        record["input_schema_sha256"]
        != hashlib.sha256(discovery._canonical_json(projected)).hexdigest()
    )
    assert "additionalProperties" not in projected
    assert "description" not in projected["properties"]["quantity"]
    assert record["schema_baseline_checked"] is True


def test_action_semantics_use_only_tool_description_and_keep_nested_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tools = _tools(
        place_schema=_schema(
            properties={
                "quantity": {
                    "type": "string",
                    "description": "Does not place an order. NESTED_SECRET_TOKEN_17",
                }
            }
        ),
        place_description="Places an equity order. TOOL_SECRET_TOKEN_18",
    )
    review_schema = _schema(
        properties={
            "quantity": {
                "type": "string",
                "description": "Places an order. NESTED_REVIEW_SECRET_19",
            }
        }
    )
    tools[0] = _tool("review_equity_order", schema=review_schema)
    result, _, _ = _run(monkeypatch, tmp_path, pages=[(tools, None)])
    place = _fingerprint(result, "place_equity_order")
    review = _fingerprint(result, "review_equity_order")
    evidence = result.evidence_path.read_text(encoding="utf-8")

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert place["tool_description_classification"]["explicitly_placing"] is True
    assert place["tool_description_classification"]["explicitly_nonplacing"] is False
    assert place["nested_description_classification"]["explicitly_nonplacing"] is True
    assert review["tool_description_classification"]["mentions_simulation"] is True
    assert review["tool_description_classification"]["mentions_pretrade"] is True
    assert (
        review["tool_description_classification"]["mentions_warning_or_alert"] is True
    )
    assert review["tool_description_classification"]["explicitly_nonplacing"] is True
    assert review["tool_description_classification"]["explicitly_placing"] is False
    assert review["nested_description_classification"]["explicitly_placing"] is True
    review_record = next(
        item for item in result.schemas if item["tool_name"] == "review_equity_order"
    )
    assert review_record["review_semantics"] == "SIMULATION_PRETRADE_WARNING"
    assert "TOOL_SECRET_TOKEN_18" not in evidence
    assert "NESTED_SECRET_TOKEN_17" not in evidence
    assert "NESTED_REVIEW_SECRET_19" not in evidence


@pytest.mark.parametrize(
    ("tool_name", "description", "expected_reason", "expected_action_state"),
    [
        (
            "place_equity_order",
            "Does not place an order. PRIVATE_TOP_LEVEL_TEXT",
            "L41R5_PLACE_NONPLACEMENT_SEMANTIC_CONFLICT",
            "NONPLACING",
        ),
        (
            "review_equity_order",
            "Places an order. PRIVATE_TOP_LEVEL_TEXT",
            "L41R5_REVIEW_PLACEMENT_SEMANTIC_CONFLICT",
            "PLACING",
        ),
        (
            "review_equity_order",
            "Does not place a preview order, but places an order at finalization.",
            "L41R5_REVIEW_PLACEMENT_SEMANTIC_CONFLICT",
            "CONFLICTING",
        ),
    ],
)
def test_tool_level_action_conflicts_block_on_top_level_description_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    tool_name: str,
    description: str,
    expected_reason: str,
    expected_action_state: str,
) -> None:
    tools = _tools()
    index = 0 if tool_name == "review_equity_order" else 1
    tools[index] = _tool(tool_name, schema=_schema(), description=description)
    result, _, _ = _run(monkeypatch, tmp_path, pages=[(tools, None)])
    fingerprint = _fingerprint(result, tool_name)

    assert result.status == "BLOCKED"
    assert result.reason == expected_reason
    assert fingerprint["tool_description_classification"]["action_semantics"] == (
        expected_action_state
    )
    assert "PRIVATE_TOP_LEVEL_TEXT" not in result.evidence_path.read_text(
        encoding="utf-8"
    )


_NUMERIC_DESCRIPTION_6 = (
    "Supports fractional market orders during regular hours up to 6 decimal places."
)
_NUMERIC_DESCRIPTION_5 = (
    "Supports fractional market orders during regular hours up to 5 decimal places."
)


def test_nested_action_text_cannot_fill_unknown_tool_action_semantics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tools = _tools(
        place_schema=_schema(
            properties={
                "quantity": {
                    "type": "string",
                    "description": (
                        "Does not place an order, but places an order during execution."
                    ),
                }
            }
        ),
        place_description="Additional details are available in named properties.",
    )
    result, _, _ = _run(monkeypatch, tmp_path, pages=[(tools, None)])
    fingerprint = _fingerprint(result, "place_equity_order")

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert fingerprint["tool_description_classification"]["action_semantics"] == (
        "UNKNOWN"
    )
    assert (
        fingerprint["nested_description_classification"]["explicitly_nonplacing"]
        is True
    )
    assert (
        fingerprint["nested_description_classification"]["explicitly_placing"] is True
    )
    assert "PLACE_NONPLACEMENT_SEMANTIC_CONFLICT" not in result.reason


def test_nested_only_numeric_precision_has_nested_provenance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    schema = _schema(
        properties={
            "quantity": {"type": "string", "description": _NUMERIC_DESCRIPTION_6},
        }
    )
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[(_tools(place_schema=schema), None)],
    )
    fingerprint = _fingerprint(result, "place_equity_order")

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert fingerprint["tool_fractional_precision_decimal_places"] == []
    assert fingerprint["nested_fractional_precision_decimal_places"] == [6]
    assert fingerprint["fractional_precision_decimal_places"] == [6]
    assert fingerprint["fractional_precision_conflict"] is False
    assert fingerprint["tool_description_classification"]["explicitly_placing"] is True


def test_tool_only_numeric_precision_has_tool_provenance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tools = _tools(
        place_description="Places an equity order. " + _NUMERIC_DESCRIPTION_6
    )
    result, _, _ = _run(monkeypatch, tmp_path, pages=[(tools, None)])
    fingerprint = _fingerprint(result, "place_equity_order")

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert fingerprint["tool_fractional_precision_decimal_places"] == [6]
    assert fingerprint["nested_fractional_precision_decimal_places"] == []
    assert fingerprint["fractional_precision_decimal_places"] == [6]
    assert fingerprint["fractional_precision_conflict"] is False


def test_equal_tool_and_nested_precision_is_non_conflicting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    schema = _schema(
        properties={
            "quantity": {"type": "string", "description": _NUMERIC_DESCRIPTION_6},
        }
    )
    tools = _tools(
        place_schema=schema,
        place_description="Places an equity order. " + _NUMERIC_DESCRIPTION_6,
    )
    result, _, _ = _run(monkeypatch, tmp_path, pages=[(tools, None)])
    fingerprint = _fingerprint(result, "place_equity_order")

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert fingerprint["tool_fractional_precision_decimal_places"] == [6]
    assert fingerprint["nested_fractional_precision_decimal_places"] == [6]
    assert fingerprint["fractional_precision_decimal_places"] == [6]
    assert fingerprint["fractional_precision_conflict"] is False


def test_different_tool_and_nested_precision_blocks_with_precise_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    schema = _schema(
        properties={
            "quantity": {"type": "string", "description": _NUMERIC_DESCRIPTION_5},
        }
    )
    tools = _tools(
        place_schema=schema,
        place_description="Places an equity order. " + _NUMERIC_DESCRIPTION_6,
    )
    result, _, _ = _run(monkeypatch, tmp_path, pages=[(tools, None)])
    fingerprint = _fingerprint(result, "place_equity_order")

    assert result.status == "BLOCKED"
    assert result.reason == "L41R5_FRACTIONAL_PRECISION_PROVENANCE_CONFLICT"
    assert fingerprint["tool_fractional_precision_decimal_places"] == [6]
    assert fingerprint["nested_fractional_precision_decimal_places"] == [5]
    assert fingerprint["fractional_precision_decimal_places"] == [5, 6]
    assert fingerprint["fractional_precision_conflict"] is True


def test_public_entrypoint_cannot_disable_or_replace_l41r4_baseline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    baseline = discovery._l41r4_interface_baseline()
    assert baseline == {
        "review_equity_order": (
            "5976f7dcf8936e0bb69f0ea2212be6d883654ccb56f4aa4b904c9951160a4069"
        ),
        "place_equity_order": (
            "46176dd0342955481cfcfee9f2bc56d92b195110d2bb0168bb0a68a431dacf4a"
        ),
        "get_equity_tradability": (
            "7d72877df8976be629e9a508f73ef370cfdd7f62d49938456cd0d624a334f8cf"
        ),
    }
    assert (
        "expected_schema_digests"
        not in inspect.signature(
            discovery.run_l41r5_schema_semantic_recovery
        ).parameters
    )
    assert discovery._valid_schema_baseline(baseline)
    assert not discovery._valid_schema_baseline(
        {"review_equity_order": baseline["review_equity_order"]}
    )

    observed: list[Mapping[str, object]] = []

    def run_with_dependencies(**kwargs: object) -> discovery.L41R5SchemaDiscoveryResult:
        observed.append(kwargs)
        assert kwargs["expected_schema_digests"] == baseline
        transport_builder = kwargs["transport_builder"]
        assert callable(transport_builder)
        transport = transport_builder(lambda: _OAUTH)
        assert transport._capture.expected == baseline
        return discovery._result_without_file("BLOCKED", "L41R5_DISCOVERY_FAILED")

    monkeypatch.setattr(discovery, "_run_with_dependencies", run_with_dependencies)
    result = discovery.run_l41r5_schema_semantic_recovery(
        evidence_dir=tmp_path / "unused"
    )
    assert result.reason == "L41R5_DISCOVERY_FAILED"
    assert len(observed) == 1


def test_baseline_change_precedes_schema_semantic_recovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    schema = _schema()
    schema["additionalProperties"] = {
        "$ref": "RAW_REFERENCE_MUST_NOT_LEAK",
        "description": "RAW_DESCRIPTION_MUST_NOT_LEAK",
    }
    tools = _tools(review_schema=schema, review_description="Places an order.")
    baseline = _fixture_baseline([(tools, None)])
    baseline["review_equity_order"] = "0" * 64

    original_inspect = discovery._inspect_schema
    inspected_names: list[str] = []

    def guarded_interpretation(name: str, *args: object, **kwargs: object) -> object:
        inspected_names.append(name)
        if name == "review_equity_order":
            pytest.fail("baseline mismatch must precede schema interpretation")
        return original_inspect(name, *args, **kwargs)

    monkeypatch.setattr(discovery, "_inspect_schema", guarded_interpretation)
    result, _, _ = _run(
        monkeypatch,
        tmp_path,
        pages=[(tools, None)],
        expected_schema_digests=baseline,
    )
    fingerprint = _fingerprint(result)
    evidence = result.evidence_path.read_text(encoding="utf-8")

    assert result.status == "BLOCKED"
    assert result.reason == "L41R5_SCHEMA_CHANGED"
    assert "review_equity_order" not in inspected_names
    assert fingerprint["input_schema_sha256"]
    assert fingerprint["description_sha256"]
    assert fingerprint["interface_sha256"]
    assert fingerprint["additional_properties_form"] == "MISSING"
    assert "RAW_REFERENCE_MUST_NOT_LEAK" not in evidence
    assert "RAW_DESCRIPTION_MUST_NOT_LEAK" not in evidence


def test_predecessor_identity_is_bound_without_granting_q62_or_numeric_authority(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, _, _ = _run(monkeypatch, tmp_path)
    payload = json.loads(result.evidence_path.read_text(encoding="utf-8"))

    assert (
        payload["l41r4_predecessor_evidence"] == discovery._L41R4_PREDECESSOR_EVIDENCE
    )
    assert payload["l41r4_interface_baseline"] == discovery._l41r4_interface_baseline()
    assert payload["trusted_binding"] is False
    assert payload["provider_numeric_rules_derived"] is False
    assert payload["automatic_retry"] == "FORBIDDEN"
    assert payload["native_credential_read_count"] is None
    assert payload["native_credential_write_count"] is None
    assert payload["credential_store_accounting"] == (
        "SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED"
    )
    assert "RAW_REFERENCE" not in result.evidence_path.read_text(encoding="utf-8")


def test_cli_forwards_only_to_r5_entrypoint_and_emits_fixed_envelope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    calls: list[Path] = []

    def run_r5(*, evidence_dir: Path) -> discovery.L41R5SchemaDiscoveryResult:
        calls.append(evidence_dir)
        return discovery._result_without_file("BLOCKED", "L41R5_DISCOVERY_FAILED")

    monkeypatch.setattr(discovery, "run_l41r5_schema_semantic_recovery", run_r5)
    evidence_dir = tmp_path / "never-created"
    exit_code = discovery._run_main(["--evidence-dir", str(evidence_dir)])
    output = capfd.readouterr()
    envelope = json.loads(output.out)

    assert exit_code == 2
    assert output.err == ""
    assert calls == [evidence_dir]
    assert not evidence_dir.exists()
    assert envelope == {
        "evidence_path": None,
        "reason": "L41R5_DISCOVERY_FAILED",
        "status": "BLOCKED",
    }


def test_l41r5_identity_is_distinct_and_does_not_expose_predecessor_entrypoints() -> (
    None
):
    assert discovery.L41R5_OBSERVATION == "L41R5_SCHEMA_SEMANTIC_RECOVERY"
    assert discovery.L41R5_EVIDENCE_SCHEMA == (
        "arch147-l41r5-schema-semantic-recovery-observation/v1"
    )
    assert not hasattr(discovery, "run_l41r3_mcp_v2_schema_discovery")
    assert not hasattr(discovery, "run_l41r4_schema_classification_diagnostic")
    assert not hasattr(discovery, "L41R3SchemaDiscoveryTransport")
    assert discovery.run_l41r5_schema_semantic_recovery.__name__ == (
        "run_l41r5_schema_semantic_recovery"
    )
    assert discovery._valid_schema_baseline(discovery._l41r4_interface_baseline())
    assert discovery._L41R4_PREDECESSOR_EVIDENCE == {
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
