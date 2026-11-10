from __future__ import annotations

import json
import logging
import os
import sys
import warnings
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.live_prototype import capability_schema_discovery_l41r3 as discovery

_HEAD = "1" * 40
_TREE = "2" * 40
_OAUTH = object()
_MISSING = object()


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


def _schema(quantity_type: object = "string") -> dict[str, object]:
    return {
        "type": "object",
        "properties": {"quantity": {"type": quantity_type}},
        "required": [],
    }


def _tool(
    name: str,
    *,
    style: str = "v2_object",
    description: str | None = None,
    schema: object = _schema(),
) -> object:
    actual_description = description
    if actual_description is None:
        actual_description = (
            "Simulates a pre-trade warning and does not place an order."
            if name == "review_equity_order"
            else "Places an equity order."
        )
    fields: dict[str, object] = {"name": name, "description": actual_description}
    if schema is not _MISSING:
        if style == "v2_object":
            fields["input_schema"] = schema
            return SimpleNamespace(**fields)
        if style == "legacy_object":
            fields["inputSchema"] = schema
            return SimpleNamespace(**fields)
        if style == "wire_mapping":
            fields.pop("description")
            fields["description"] = actual_description
            fields["inputSchema"] = schema
            return fields
        raise AssertionError(f"unknown tool style: {style}")
    if style == "wire_mapping":
        return fields
    return SimpleNamespace(**fields)


def _tools(
    *, style: str = "v2_object", review_schema: object = _schema()
) -> list[object]:
    return [
        _tool("review_equity_order", style=style, schema=review_schema),
        _tool("place_equity_order", style=style),
    ]


def _emit_test_noise(prefix: str) -> None:
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
        wire_cursor: bool = False,
        conflicting_cursor: bool = False,
        noise: bool = False,
    ) -> None:
        self.pages = pages
        self.events = events
        self.wire_cursor = wire_cursor
        self.conflicting_cursor = conflicting_cursor
        self.noise = noise
        self.calls: list[tuple[str, Mapping[str, object]]] = []

    async def list_tools(self, *, cursor: str | None = None) -> object:
        self.events.append("tools_list")
        if self.noise:
            _emit_test_noise("SECRET_PROVIDER")
        index = 0 if cursor is None else int(cursor)
        entries, next_cursor = self.pages[index]
        if self.conflicting_cursor:
            return {
                "tools": entries,
                "next_cursor": "1",
                "nextCursor": "2",
            }
        if self.wire_cursor:
            return {"tools": entries, "nextCursor": next_cursor}
        return SimpleNamespace(tools=entries, next_cursor=next_cursor)

    async def call_tool(self, name: str, arguments: Mapping[str, object]) -> object:
        self.calls.append((name, arguments))
        raise AssertionError("L41R3 must never invoke an MCP tool")


def _run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    pages: Sequence[tuple[Sequence[object], str | None]] | None = None,
    source: discovery.SourceAdmission | None = None,
    events: list[str] | None = None,
    style: str = "v2_object",
    wire_cursor: bool = False,
    conflicting_cursor: bool = False,
    noise: bool = False,
    construction_noise: bool = False,
    expected_schema_digests: Mapping[str, str] | None = None,
) -> tuple[discovery.L41R3SchemaDiscoveryResult, _FakeClient, list[str]]:
    local_events = [] if events is None else events
    output_dir = tmp_path / "fresh-evidence"

    def create_test_evidence_dir(path: Path) -> Path:
        path.mkdir(parents=True)
        return path

    monkeypatch.setattr(discovery, "_fresh_evidence_dir", create_test_evidence_dir)
    client = _FakeClient(
        [(_tools(style=style), None)] if pages is None else pages,
        local_events,
        wire_cursor=wire_cursor,
        conflicting_cursor=conflicting_cursor,
        noise=noise,
    )

    @asynccontextmanager
    async def session_factory(oauth: object):
        assert oauth is _OAUTH
        local_events.append("session_open")
        try:
            yield client
        finally:
            local_events.append("session_close")

    def build_oauth() -> discovery._OAuthFactoryBundle:
        local_events.append("oauth_factory_builder")
        if construction_noise:
            _emit_test_noise("SECRET_OAUTH_BUILDER")

        def oauth_factory() -> object:
            local_events.append("oauth_scope_entry")
            return _OAUTH

        return discovery._OAuthFactoryBundle(
            oauth_factory,
            discovery._OneShotBrowserOpener(lambda _url: True),
        )

    def source_admitter(root: Path) -> discovery.SourceAdmission:
        assert root == tmp_path
        local_events.append("source")
        return _source() if source is None else source

    def build_transport(
        oauth_factory: object,
    ) -> discovery.L41R3SchemaDiscoveryTransport:
        if construction_noise:
            _emit_test_noise("SECRET_TRANSPORT_BUILDER")
        return discovery.L41R3SchemaDiscoveryTransport(
            oauth_factory,  # type: ignore[arg-type]
            session_factory=session_factory,
            expected_schema_digests=expected_schema_digests,
        )

    result = discovery._run_with_dependencies(
        evidence_dir=output_dir,
        source_admitter=source_admitter,
        oauth_factory_builder=build_oauth,
        transport_builder=build_transport,
        repository_root_resolver=lambda: tmp_path,
        expected_schema_digests=expected_schema_digests,
    )
    return result, client, local_events


def _prohibited_counts_are_zero(
    counts: discovery.L41R3SchemaDiscoveryAttemptCounts,
) -> bool:
    return all(
        value == 0
        for name, value in asdict(counts).items()
        if name
        not in {
            "oauth_scope_entry_attempts",
            "mcp_session_open_attempts",
            "browser_launches",
            "tools_list_attempts",
        }
    )


@pytest.mark.parametrize("style", ["v2_object", "wire_mapping", "legacy_object"])
def test_normalizes_v2_wire_and_intentionally_retained_legacy_tool_shapes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, style: str
) -> None:
    result, client, _events = _run(monkeypatch, tmp_path, style=style)

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert result.reason == "L41R3_SCHEMA_METADATA_CAPTURED_UNPINNED"
    assert {item.tool_name for item in result.schemas} == {
        "review_equity_order",
        "place_equity_order",
    }
    assert result.attempt_counts.tools_list_attempts == 1
    assert client.calls == []
    assert _prohibited_counts_are_zero(result.attempt_counts)


def test_same_normalized_schema_has_identical_sanitized_facts_and_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    facts_by_style = []
    for index, style in enumerate(("v2_object", "wire_mapping", "legacy_object")):
        result, _client, _events = _run(
            monkeypatch,
            tmp_path / str(index),
            style=style,
        )
        facts_by_style.append(result.schemas)

    assert facts_by_style[0] == facts_by_style[1] == facts_by_style[2]
    assert facts_by_style[0][0].input_schema_sha256


@pytest.mark.parametrize(
    ("schema", "expected_reason"),
    [
        (_MISSING, "L41R3_SCHEMA_MALFORMED"),
        ("not-a-mapping", "L41R3_SCHEMA_MALFORMED"),
        (
            {"type": "object", "properties": "bad", "required": []},
            "L41R3_SCHEMA_MALFORMED",
        ),
        (
            {"type": "object", "properties": {}, "required": ()},
            "L41R3_SCHEMA_MALFORMED",
        ),
        ({"type": "array", "properties": {}, "required": []}, "L41R3_SCHEMA_MALFORMED"),
        (
            {"type": "object", "properties": {"quantity": "bad"}, "required": []},
            "L41R3_SCHEMA_MALFORMED",
        ),
        (
            {"type": "object", "properties": {}, "required": [1]},
            "L41R3_SCHEMA_MALFORMED",
        ),
        (
            {"type": "object", "properties": {"quantity": {}}, "required": []},
            "L41R3_SCHEMA_AMBIGUOUS",
        ),
    ],
)
def test_invalid_or_missing_schema_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    schema: object,
    expected_reason: str,
) -> None:
    result, client, _events = _run(
        monkeypatch,
        tmp_path,
        pages=[
            (
                [
                    _tool("review_equity_order", schema=schema),
                    _tool("place_equity_order"),
                ],
                None,
            )
        ],
    )

    assert result.status == "BLOCKED"
    assert result.reason == expected_reason
    assert client.calls == []
    assert _prohibited_counts_are_zero(result.attempt_counts)


def test_duplicate_and_conflicting_schema_remain_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    duplicate, duplicate_client, _events = _run(
        monkeypatch,
        tmp_path / "duplicate",
        pages=[
            (
                [
                    _tool("review_equity_order"),
                    _tool("review_equity_order"),
                    _tool("place_equity_order"),
                ],
                None,
            )
        ],
    )
    conflicting, conflict_client, _events = _run(
        monkeypatch,
        tmp_path / "conflicting",
        pages=[
            (
                [
                    _tool("review_equity_order"),
                    _tool("review_equity_order", description="Changed."),
                    _tool("place_equity_order"),
                ],
                None,
            )
        ],
    )

    assert duplicate.status == "BLOCKED"
    assert duplicate.reason == "L41R3_DUPLICATE_SCHEMA"
    assert conflicting.status == "BLOCKED"
    assert conflicting.reason == "L41R3_SCHEMA_CHANGED"
    assert duplicate_client.calls == conflict_client.calls == []


def test_wire_pagination_cursor_is_normalized_and_remains_bounded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paginated, client, _events = _run(
        monkeypatch,
        tmp_path / "paginated",
        pages=[
            ([_tool("review_equity_order")], "1"),
            ([_tool("place_equity_order")], None),
        ],
        wire_cursor=True,
    )
    too_many, bounded_client, _events = _run(
        monkeypatch,
        tmp_path / "bounded",
        pages=[([], str(index + 1)) for index in range(20)] + [([], None)],
    )

    assert paginated.status == "CAPTURED_FOR_REVIEW"
    assert paginated.attempt_counts.tools_list_attempts == 2
    assert client.calls == []
    assert too_many.status == "BLOCKED"
    assert too_many.reason == "L41R3_TOOL_PAGINATION_BOUND_EXCEEDED"
    assert too_many.attempt_counts.tools_list_attempts == 20
    assert bounded_client.calls == []


def test_duplicate_pagination_cursor_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, client, _events = _run(
        monkeypatch,
        tmp_path,
        pages=[
            ([_tool("review_equity_order")], "1"),
            ([_tool("place_equity_order")], "1"),
        ],
    )

    assert result.status == "BLOCKED"
    assert result.reason == "L41R3_TOOL_CURSOR_INVALID"
    assert result.attempt_counts.tools_list_attempts == 2
    assert client.calls == []


def test_conflicting_cursor_aliases_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    conflict, conflict_client, _events = _run(
        monkeypatch,
        tmp_path,
        pages=[([*_tools()], None)],
        conflicting_cursor=True,
    )
    assert conflict.status == "BLOCKED"
    assert conflict.reason == "L41R3_TOOL_CURSOR_INVALID"
    assert conflict_client.calls == []


def test_source_admission_precedes_oauth_and_session_creation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []
    blocked_source = _source(feature_authority="NOT_RUN")
    result, client, observed = _run(
        monkeypatch,
        tmp_path,
        source=blocked_source,
        events=events,
    )

    assert result.status == "BLOCKED"
    assert result.reason == "L41R3_SOURCE_ADMISSION_BLOCKED"
    assert observed == ["source"]
    assert client.calls == []
    assert result.attempt_counts == discovery.L41R3SchemaDiscoveryAttemptCounts()


def test_malformed_tool_name_is_rejected_as_invalid_inventory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, client, _events = _run(
        monkeypatch,
        tmp_path,
        pages=[([{"name": [], "inputSchema": _schema()}], None)],
    )

    assert result.status == "BLOCKED"
    assert result.reason == "L41R3_TOOL_INVENTORY_MALFORMED"
    assert client.calls == []


def test_provider_and_native_output_are_suppressed_and_evidence_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    tools = _tools()
    tools[0] = _tool(
        "review_equity_order",
        style="v2_object",
        description="Simulates a pre-trade warning. SECRET_PROVIDER_DESCRIPTION",
    )
    result, client, _events = _run(
        monkeypatch,
        tmp_path,
        pages=[(tools, None)],
        noise=True,
        construction_noise=True,
    )
    captured = capfd.readouterr()

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert captured.out == captured.err == ""
    assert client.calls == []
    payload = json.loads(result.evidence_path.read_text(encoding="utf-8"))  # type: ignore[union-attr]
    serialized = json.dumps(payload)
    for secret in (
        "SECRET_PROVIDER_STDOUT",
        "SECRET_PROVIDER_STDERR",
        "SECRET_PROVIDER_WARNING",
        "SECRET_PROVIDER_LOG",
        "SECRET_NATIVE_STDOUT",
        "SECRET_NATIVE_STDERR",
        "SECRET_PROVIDER_DESCRIPTION",
        "SECRET_OAUTH_BUILDER",
        "SECRET_TRANSPORT_BUILDER",
    ):
        assert secret not in serialized
    assert payload["schema"] == discovery.L41R3_EVIDENCE_SCHEMA
    assert payload["observation"] == discovery.L41R3_OBSERVATION
    assert payload["automatic_retry"] == "FORBIDDEN"
    assert payload["trusted_binding"] is False
    assert payload["provider_numeric_rules_derived"] is False
    assert payload["native_credential_read_count"] is None
    assert payload["native_credential_write_count"] is None
    assert payload["credential_store_accounting"] == (
        "SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED"
    )
    assert _prohibited_counts_are_zero(result.attempt_counts)


def test_browser_opener_is_one_shot_and_transport_exposes_no_tool_call_surface() -> (
    None
):
    urls: list[str] = []
    opener = discovery._OneShotBrowserOpener(lambda url: urls.append(url))
    assert opener("https://example.invalid/first") is None
    with pytest.raises(RuntimeError, match="L41R3_BROWSER_LAUNCH_ALREADY_USED"):
        opener("https://example.invalid/second")

    assert urls == ["https://example.invalid/first"]
    assert not hasattr(discovery.L41R3SchemaDiscoveryTransport, "call_tool")
    assert discovery.L41R3_OBSERVATION == "L41R3_MCP_V2_SCHEMA_DISCOVERY"
    assert discovery.L41R3_EVIDENCE_SCHEMA == (
        "arch147-l41r3-mcp-v2-interface-observation/v1"
    )


def test_consumed_predecessor_identity_is_not_reused_or_replayable() -> None:
    assert not hasattr(discovery, "run_l41r2_interactive_schema_discovery")
    assert discovery.L41R3_OBSERVATION != "L41R2_INTERACTIVE_SCHEMA_DISCOVERY"
    assert discovery.L41R3_EVIDENCE_SCHEMA != (
        "arch147-l41r2-interactive-interface-observation/v1"
    )


def test_cli_emits_only_fixed_result_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = discovery.L41R3SchemaDiscoveryResult(
        "BLOCKED",
        "L41R3_TOOLS_LIST_FAILED",
        tmp_path / "evidence.json",
        None,
        discovery.L41R3SchemaDiscoveryAttemptCounts(),
        (),
    )
    monkeypatch.setattr(
        discovery, "run_l41r3_mcp_v2_schema_discovery", lambda evidence_dir: result
    )

    assert discovery.main(["--evidence-dir", str(tmp_path / "fresh")]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "evidence_path": str(result.evidence_path),
        "reason": "L41R3_TOOLS_LIST_FAILED",
        "status": "BLOCKED",
    }


def test_changed_schema_does_not_match_a_pinned_interface_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    baseline_result, _client, _events = _run(monkeypatch, tmp_path / "baseline")
    baseline = {
        item.tool_name: item.interface_sha256 for item in baseline_result.schemas
    }
    changed, client, _events = _run(
        monkeypatch,
        tmp_path / "changed",
        pages=[
            (
                [
                    _tool("review_equity_order", schema=_schema("integer")),
                    _tool("place_equity_order"),
                ],
                None,
            )
        ],
        expected_schema_digests=baseline,
    )

    assert changed.status == "BLOCKED"
    assert changed.reason == "L41R3_SCHEMA_CHANGED"
    assert client.calls == []
