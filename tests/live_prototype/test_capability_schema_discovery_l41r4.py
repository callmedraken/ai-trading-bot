from __future__ import annotations

import logging
import os
import sys
import warnings
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.live_prototype import capability_schema_discovery_l41r4 as discovery

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
    ]


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
        raise AssertionError("L41R4 must never invoke an MCP tool")


def _run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    pages: Sequence[tuple[Sequence[object], str | None]] | None = None,
    source: discovery.SourceAdmission | None = None,
    noise: bool = False,
    construction_noise: bool = False,
    session_close_error: bool = False,
    expected_schema_digests: Mapping[str, str] | None = None,
) -> tuple[discovery.L41R4SchemaDiscoveryResult, _FakeClient, list[str]]:
    events: list[str] = []
    evidence_number = len(tuple(tmp_path.glob("evidence-*")))
    evidence_dir = tmp_path / f"evidence-{evidence_number}"

    def create_evidence_dir(path: Path) -> Path:
        path.mkdir(parents=True)
        return path

    monkeypatch.setattr(discovery, "_fresh_evidence_dir", create_evidence_dir)
    client = _FakeClient(
        [(_tools(), None)] if pages is None else pages,
        events,
        noise=noise,
    )

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

    def transport_builder(oauth: object) -> discovery.L41R4SchemaDiscoveryTransport:
        return discovery.L41R4SchemaDiscoveryTransport(
            oauth,  # type: ignore[arg-type]
            session_factory=session_factory,
            expected_schema_digests=expected_schema_digests,
        )

    result = discovery._run_with_dependencies(
        evidence_dir=evidence_dir,
        source_admitter=source_admitter,
        oauth_factory_builder=oauth_builder,
        transport_builder=transport_builder,
        repository_root_resolver=lambda: tmp_path,
        expected_schema_digests=expected_schema_digests,
    )
    return result, client, events


def _fingerprint(
    result: discovery.L41R4SchemaDiscoveryResult, tool_name: str = "review_equity_order"
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
            "L41R4_QUANTITY_MULTI_NON_NULL_UNION",
            ["null", "number", "string"],
        ),
        (
            {
                "anyOf": [
                    {"type": "string"},
                    {"type": "number"},
                ]
            },
            "L41R4_QUANTITY_MULTI_NON_NULL_UNION",
            ["number", "string"],
        ),
        (
            {
                "anyOf": [
                    {"type": "string"},
                    {"$ref": "secret/callback/token"},
                ]
            },
            "L41R4_QUANTITY_UNRESOLVED_REF",
            ["string"],
        ),
        (
            {"allOf": [{"type": "string"}, {"type": "null"}]},
            "L41R4_QUANTITY_UNSUPPORTED_COMPOSITION",
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
            "L41R4_TOP_LEVEL_UNRESOLVED_REF",
        ),
        (
            {"allOf": [{"properties": {"quantity": {"type": "null"}}}]},
            "L41R4_TOP_LEVEL_UNSUPPORTED_COMPOSITION",
        ),
        (
            {"if": {"properties": {"quantity": {"const": None}}}},
            "L41R4_TOP_LEVEL_UNSUPPORTED_CONSTRAINT",
        ),
        (
            {"$schema": "https://private.invalid/schema?token=SECRET_VALUE"},
            "L41R4_TOP_LEVEL_UNSUPPORTED_CONSTRAINT",
        ),
        (
            {"x-private-callback-token-key": True},
            "L41R4_TOP_LEVEL_UNSUPPORTED_CONSTRAINT",
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
    assert result.reason == "L41R4_REQUIRED_NOT_IN_PROPERTIES"
    assert _fingerprint(result)["ambiguity_classes"] == [
        "L41R4_REQUIRED_NOT_IN_PROPERTIES"
    ]
    assert _fingerprint(result)["required_not_in_properties"] == ["quantity"]


@pytest.mark.parametrize(
    ("name", "description", "expected_reason"),
    [
        (
            "review_equity_order",
            "Places an order. SECRET_CALLBACK_TOKEN_123",
            "L41R4_REVIEW_PLACEMENT_SEMANTIC_CONFLICT",
        ),
        (
            "place_equity_order",
            "Does not place an order. SECRET_CALLBACK_TOKEN_456",
            "L41R4_PLACE_NONPLACEMENT_SEMANTIC_CONFLICT",
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
    assert fingerprint["description_classification"]["explicitly_nonplacing"] is (
        name == "place_equity_order"
    )


@pytest.mark.parametrize(
    ("description", "expected_reason", "precision_values"),
    [
        (
            "Fractional regular market hours allow up to 6 decimal places and "
            "maximum 8 decimal places.",
            "L41R4_FRACTIONAL_PRECISION_CONFLICT",
            [6, 8],
        ),
        (
            "Fractional regular market hours allow up to 0 decimal places.",
            "L41R4_FRACTIONAL_PRECISION_INVALID",
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
    assert result.reason == "L41R4_SCHEMA_MALFORMED"
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
        "review_equity_order": "0" * 64,
        "place_equity_order": accepted_baseline["place_equity_order"],
    }
    mismatch, _, _ = _run(
        monkeypatch,
        tmp_path,
        expected_schema_digests=baseline,
    )
    assert mismatch.reason == "L41R4_SCHEMA_CHANGED"
    assert mismatch.structural_fingerprints

    missing_optional, _, _ = _run(
        monkeypatch,
        tmp_path,
        expected_schema_digests={
            "review_equity_order": accepted_baseline["review_equity_order"],
            "place_equity_order": accepted_baseline["place_equity_order"],
            "get_equity_tradability": "1" * 64,
        },
    )
    assert missing_optional.reason == "L41R4_REQUIRED_SCHEMA_MISSING"


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

    assert result.reason == "L41R4_SCHEMA_CHANGED"
    assert _fingerprint(result)["input_schema_sha256"]


def test_pagination_is_bounded_and_tool_invocation_surface_is_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pages = []
    for index in range(discovery._MAX_DISCOVERY_PAGES):
        tools = _tools() if index == 0 else [_tool("uninspected_tool")]
        pages.append((tools, str(index + 1)))
    result, client, events = _run(monkeypatch, tmp_path, pages=pages)

    assert result.reason == "L41R4_TOOL_PAGINATION_BOUND_EXCEEDED"
    assert result.attempt_counts.tools_list_attempts == 20
    assert client.calls == []
    assert events.count("tools_list") == 20
    assert not hasattr(discovery.L41R4SchemaDiscoveryTransport, "call_tool")
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

    assert result.reason == "L41R4_TOOL_CURSOR_INVALID"
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

    assert result.reason == "L41R4_QUANTITY_MULTI_NON_NULL_UNION"
    assert _fingerprint(result)["fields"]["quantity"]["union_primitive_types"] == (
        ["null", "number", "string"]
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

    assert result.reason == "L41R4_SOURCE_ADMISSION_BLOCKED"
    assert events == ["source"]
    assert result.attempt_counts.oauth_scope_entry_attempts == 0
    assert result.attempt_counts.mcp_session_open_attempts == 0


def test_browser_opener_is_one_shot() -> None:
    calls: list[str] = []
    opener = discovery._OneShotBrowserOpener(lambda url: calls.append(url) or True)

    assert opener("https://example.invalid/oauth") is True
    with pytest.raises(RuntimeError, match="L41R4_BROWSER_LAUNCH_ALREADY_USED"):
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

    with pytest.raises(ValueError, match="L41R4_EVIDENCE_PATH_INVALID"):
        discovery._create_fresh_evidence_dir_under_root(evidence_dir, parent_root)

    assert evidence_path.read_bytes() == original_evidence


def test_fresh_evidence_dir_rejects_non_f_drive_with_monkeypatched_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    parent_root = tmp_path.resolve(strict=True)
    monkeypatch.setattr(discovery, "_EVIDENCE_ROOT", parent_root)
    evidence_dir = parent_root / "non-f-drive"
    assert evidence_dir.drive.casefold() != "f:"

    with pytest.raises(ValueError, match="L41R4_EVIDENCE_PATH_INVALID"):
        discovery._fresh_evidence_dir(evidence_dir)

    assert not evidence_dir.exists()


def test_l41r4_identity_is_distinct_and_does_not_expose_r3_entrypoint() -> None:
    assert discovery.L41R4_OBSERVATION == "L41R4_SCHEMA_CLASSIFICATION_DIAGNOSTIC"
    assert discovery.L41R4_EVIDENCE_SCHEMA == (
        "arch147-l41r4-schema-classification-observation/v1"
    )
    assert not hasattr(discovery, "run_l41r3_mcp_v2_schema_discovery")
    assert not hasattr(discovery, "L41R3SchemaDiscoveryTransport")
    assert discovery.run_l41r4_schema_classification_diagnostic.__name__ == (
        "run_l41r4_schema_classification_diagnostic"
    )
