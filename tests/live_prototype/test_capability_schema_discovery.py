from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.live_prototype import capability_schema_discovery as discovery

_HEAD = "1" * 40
_TREE = "2" * 40


def _source(**overrides: object) -> discovery.SourceAdmission:
    values: dict[str, object] = {
        "branch": discovery.L41_FEATURE_BRANCH,
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


def _tool(
    name: str,
    description: str,
    *,
    quantity_type: str | None = "string",
    quantity_required: bool = False,
) -> SimpleNamespace:
    properties: dict[str, object] = {}
    required: list[str] = []
    if quantity_type is not None:
        properties["quantity"] = {"type": quantity_type}
        if quantity_required:
            required.append("quantity")
    return SimpleNamespace(
        name=name,
        description=description,
        inputSchema={"type": "object", "properties": properties, "required": required},
    )


def _tools() -> list[SimpleNamespace]:
    return [
        _tool(
            "review_equity_order",
            "Simulates a pre-trade warning and does not place an order. "
            "Fractional market orders during regular hours support "
            "up to 6 decimal places.",
        ),
        _tool("place_equity_order", "Places an equity order."),
    ]


class _FakeClient:
    def __init__(
        self,
        pages: Sequence[tuple[Sequence[object], str | None]],
        events: list[str],
        *,
        fail_list: bool = False,
    ) -> None:
        self.pages = pages
        self.events = events
        self.fail_list = fail_list
        self.calls: list[tuple[str, Mapping[str, object]]] = []

    async def list_tools(self, *, cursor: str | None = None) -> object:
        self.events.append("tools_list")
        if self.fail_list:
            raise RuntimeError("SECRET_PROVIDER_EXCEPTION")
        index = 0 if cursor is None else int(cursor)
        entries, next_cursor = self.pages[index]
        return SimpleNamespace(tools=entries, next_cursor=next_cursor)

    async def call_tool(self, name: str, arguments: Mapping[str, object]) -> object:
        self.calls.append((name, arguments))
        raise AssertionError("schema discovery must never invoke an MCP tool")


def _run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    pages: Sequence[tuple[Sequence[object], str | None]] | None = None,
    source: discovery.SourceAdmission | None = None,
    events: list[str] | None = None,
    fail_list: bool = False,
    fail_close: bool = False,
    expected_schema_digests: Mapping[str, str] | None = None,
) -> tuple[discovery.SchemaDiscoveryResult, _FakeClient, list[str]]:
    local_events = [] if events is None else events
    candidate_dir = tmp_path / "fresh-evidence"

    def create_test_evidence_dir(path: Path) -> Path:
        path.mkdir()
        return path

    monkeypatch.setattr(discovery, "_fresh_evidence_dir", create_test_evidence_dir)
    tools = _tools() if pages is None else None
    client = _FakeClient(
        [(tools or [], None)] if pages is None else pages,
        local_events,
        fail_list=fail_list,
    )

    @asynccontextmanager
    async def session_factory(oauth: object):
        assert oauth is _OAUTH
        local_events.append("session_open")
        try:
            yield client
        finally:
            local_events.append("session_close")
            if fail_close:
                raise RuntimeError("SECRET_CLOSE_EXCEPTION")

    def make_transport(
        oauth_factory: object,
    ) -> discovery.RobinhoodSchemaDiscoveryTransport:
        assert callable(oauth_factory)
        return discovery.RobinhoodSchemaDiscoveryTransport(
            oauth_factory,  # type: ignore[arg-type]
            session_factory=session_factory,
            expected_schema_digests=expected_schema_digests,
        )

    source_value = _source() if source is None else source

    def oauth_factory() -> object:
        local_events.append("oauth_scope_entry")
        return _OAUTH

    def admit_test_source(root: Path) -> discovery.SourceAdmission:
        assert root == tmp_path
        local_events.append("source")
        return source_value

    result = discovery._run_with_dependencies(
        evidence_dir=candidate_dir,
        source_admitter=admit_test_source,
        oauth_factory_builder=lambda: (
            local_events.append("oauth_factory_builder"),
            oauth_factory,
        )[1],
        transport_builder=lambda oauth_factory: (
            local_events.append("transport_builder"),
            make_transport(oauth_factory),
        )[1],
        repository_root_resolver=lambda: tmp_path,
        expected_schema_digests=expected_schema_digests,
    )
    return result, client, local_events


_OAUTH = object()


def test_schema_discovery_is_source_admitted_and_tools_list_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, client, events = _run(monkeypatch, tmp_path)

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert result.reason == "L41R1_SCHEMA_METADATA_CAPTURED_UNPINNED"
    assert [schema.tool_name for schema in result.schemas] == [
        "place_equity_order",
        "review_equity_order",
    ]
    assert events == [
        "source",
        "oauth_factory_builder",
        "transport_builder",
        "oauth_scope_entry",
        "session_open",
        "tools_list",
        "session_close",
    ]
    assert client.calls == []
    assert result.attempt_counts.oauth_scope_entry_attempts == 1
    assert result.attempt_counts.mcp_session_open_attempts == 1
    assert result.attempt_counts.tools_list_attempts == 1
    assert all(
        value == 0
        for name, value in asdict(result.attempt_counts).items()
        if name
        not in {
            "oauth_scope_entry_attempts",
            "mcp_session_open_attempts",
            "tools_list_attempts",
        }
    )


def test_metadata_is_sanitized_and_only_explicit_schema_facts_are_recorded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tools = _tools()
    tools[0].description += " SECRET_ACCOUNT_NUMBER_4831"
    result, _client, _events = _run(monkeypatch, tmp_path, pages=[(tools, None)])

    review = next(
        item for item in result.schemas if item.tool_name == "review_equity_order"
    )
    assert review.quantity_field_present is True
    assert review.quantity_field_required is False
    assert review.quantity_field_type == "string"
    assert review.regular_hours_fractional_market_precision_decimal_places == 6
    assert review.review_semantics == "SIMULATION_PRETRADE_WARNING"
    assert review.review_is_placement is False
    place = next(
        item for item in result.schemas if item.tool_name == "place_equity_order"
    )
    assert place.placement_semantics == "ORDER_SUBMISSION"
    assert result.evidence_path is not None
    persisted = result.evidence_path.read_text(encoding="utf-8")
    assert "SECRET_ACCOUNT_NUMBER_4831" not in persisted
    assert "Simulates a pre-trade warning" not in persisted
    payload = json.loads(persisted)
    assert payload["trusted_binding"] is False
    assert payload["provider_numeric_rules_derived"] is False
    assert payload["automatic_retry"] == "FORBIDDEN"


def test_decimal_string_quantity_representation_is_recorded_verbatim(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, _client, _events = _run(monkeypatch, tmp_path)

    review = next(
        item for item in result.schemas if item.tool_name == "review_equity_order"
    )
    assert review.quantity_field_type == "string"


@pytest.mark.parametrize(
    "description",
    [
        "Simulation pre-trade warning without placing an order.",
        "Simulation pre-trade alert; it does not place an order.",
        "Simulation pre-trade warning; no order was placed.",
        "Simulation pre-trade alert; nothing is placed.",
    ],
)
def test_review_description_accepts_explicit_nonplacement_wording(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, description: str
) -> None:
    tools = _tools()
    tools[0].description = description
    result, _client, _events = _run(monkeypatch, tmp_path, pages=[(tools, None)])

    review = next(
        item for item in result.schemas if item.tool_name == "review_equity_order"
    )
    assert review.review_semantics == "SIMULATION_PRETRADE_WARNING"
    assert review.review_is_placement is False


def test_noncanonical_production_module_root_blocks_before_oauth_or_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    candidate_dir = tmp_path / "fresh-evidence"
    events: list[str] = []

    def create_test_evidence_dir(path: Path) -> Path:
        path.mkdir()
        return path

    def forbidden_source(_root: Path) -> discovery.SourceAdmission:
        events.append("source")
        raise AssertionError("source admission must follow the production root gate")

    def forbidden_oauth() -> object:
        events.append("oauth")
        raise AssertionError("OAuth must follow source admission")

    monkeypatch.setattr(discovery, "_fresh_evidence_dir", create_test_evidence_dir)
    monkeypatch.setattr(
        discovery,
        "__file__",
        str(
            tmp_path
            / "noncanonical"
            / "src"
            / "trading_bot"
            / "live_prototype"
            / "capability_schema_discovery.py"
        ),
    )
    monkeypatch.setattr(discovery, "admit_l41_source", forbidden_source)
    monkeypatch.setattr(discovery, "_create_windows_oauth_factory", forbidden_oauth)

    result = discovery.run_l41r1_schema_discovery(evidence_dir=candidate_dir)

    assert result.status == "BLOCKED"
    assert result.reason == "L41R1_SOURCE_ADMISSION_BLOCKED"
    assert events == []


@pytest.mark.parametrize(
    "source",
    [
        _source(feature_authority="NOT_RUN"),
        _source(origin_feature_tree="3" * 40),
        _source(origin_develop_head="3" * 40),
    ],
)
def test_source_rejection_precedes_oauth_and_session_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    source: discovery.SourceAdmission,
) -> None:
    events: list[str] = []
    result, client, observed = _run(
        monkeypatch,
        tmp_path,
        source=source,
        events=events,
    )

    assert result.status == "BLOCKED"
    assert result.reason == "L41R1_SOURCE_ADMISSION_BLOCKED"
    assert observed == ["source"]
    assert client.calls == []
    assert result.attempt_counts == discovery.SchemaDiscoveryAttemptCounts()


def test_pagination_lists_schemas_once_per_page_without_tool_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tools = _tools()
    result, client, events = _run(
        monkeypatch,
        tmp_path,
        pages=[([tools[0]], "1"), ([tools[1]], None)],
    )

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert result.attempt_counts.tools_list_attempts == 2
    assert len(events) == 8
    assert client.calls == []


def test_optional_tradability_schema_is_digest_only_correlation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tools = _tools()
    tools.append(
        _tool(
            "get_equity_tradability", "Schema correlation only.", quantity_type="number"
        )
    )
    result, client, _events = _run(monkeypatch, tmp_path, pages=[(tools, None)])

    tradability = next(
        item for item in result.schemas if item.tool_name == "get_equity_tradability"
    )
    assert tradability.input_schema_sha256
    assert tradability.quantity_field_present is None
    assert tradability.regular_hours_fractional_market_precision_decimal_places is None
    assert client.calls == []


def test_missing_schema_blocks_and_persists_zero_effect_counters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, client, _events = _run(
        monkeypatch,
        tmp_path,
        pages=[([_tools()[0]], None)],
    )

    assert result.status == "BLOCKED"
    assert result.reason == "L41R1_REQUIRED_SCHEMA_MISSING"
    assert result.attempt_counts.review_equity_order_attempts == 0
    assert result.attempt_counts.place_equity_order_attempts == 0
    assert client.calls == []


@pytest.mark.parametrize(
    ("second", "reason"),
    [
        (_tools()[0], "L41R1_DUPLICATE_SCHEMA"),
        (
            _tool("review_equity_order", "Changed description."),
            "L41R1_SCHEMA_CHANGED",
        ),
    ],
)
def test_duplicate_or_conflicting_schema_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    second: SimpleNamespace,
    reason: str,
) -> None:
    tools = _tools()
    result, client, _events = _run(
        monkeypatch,
        tmp_path,
        pages=[([tools[0], second, tools[1]], None)],
    )

    assert result.status == "BLOCKED"
    assert result.reason == reason
    assert client.calls == []


def test_changed_schema_does_not_match_a_pinned_interface_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original = _tools()
    baseline = {
        item.name: discovery._schema_facts(item.name, item, None).interface_sha256
        for item in original
    }
    changed = _tools()
    changed[1].inputSchema["properties"]["quantity"]["type"] = "integer"
    result, client, _events = _run(
        monkeypatch,
        tmp_path,
        pages=[(changed, None)],
        expected_schema_digests=baseline,
    )

    assert result.status == "BLOCKED"
    assert result.reason == "L41R1_SCHEMA_CHANGED"
    assert client.calls == []


def test_ambiguous_quantity_schema_is_rejected_without_persisting_schema_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tools = _tools()
    tools[0].inputSchema["properties"]["quantity"].pop("type")
    result, client, _events = _run(monkeypatch, tmp_path, pages=[(tools, None)])

    assert result.status == "BLOCKED"
    assert result.reason == "L41R1_SCHEMA_AMBIGUOUS"
    assert client.calls == []
    assert result.evidence_path is not None
    assert "inputSchema" not in result.evidence_path.read_text(encoding="utf-8")


def test_malformed_schema_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tools = _tools()
    tools[0].inputSchema["properties"] = "malformed"
    result, client, _events = _run(monkeypatch, tmp_path, pages=[(tools, None)])

    assert result.status == "BLOCKED"
    assert result.reason == "L41R1_SCHEMA_MALFORMED"
    assert client.calls == []


@pytest.mark.parametrize(
    "tool_name,description",
    [
        ("review_equity_order", "Reviews and places an order."),
        ("place_equity_order", "Does not place an order."),
    ],
)
def test_conflicting_review_or_placement_semantics_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    tool_name: str,
    description: str,
) -> None:
    tools = _tools()
    target = next(item for item in tools if item.name == tool_name)
    target.description = description
    result, client, _events = _run(monkeypatch, tmp_path, pages=[(tools, None)])

    assert result.status == "BLOCKED"
    assert result.reason == "L41R1_SCHEMA_AMBIGUOUS"
    assert client.calls == []


def test_session_close_failure_blocks_but_retains_completed_schema_facts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, client, _events = _run(monkeypatch, tmp_path, fail_close=True)

    assert result.status == "BLOCKED"
    assert result.reason == "L41R1_SESSION_CLOSE_FAILED"
    assert {item.tool_name for item in result.schemas} == {
        "review_equity_order",
        "place_equity_order",
    }
    assert result.attempt_counts.tools_list_attempts == 1
    assert client.calls == []


def test_tools_list_failure_is_sanitized_and_closes_the_single_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, client, _events = _run(monkeypatch, tmp_path, fail_list=True)

    assert result.status == "BLOCKED"
    assert result.reason == "L41R1_TOOLS_LIST_FAILED"
    assert result.attempt_counts.tools_list_attempts == 1
    assert client.calls == []
    assert result.evidence_path is not None
    persisted = result.evidence_path.read_text(encoding="utf-8")
    assert "SECRET_PROVIDER_EXCEPTION" not in persisted
