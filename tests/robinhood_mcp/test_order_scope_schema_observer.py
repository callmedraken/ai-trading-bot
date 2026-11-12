from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import types
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.robinhood_mcp import order_scope_schema_observer as observer
from trading_bot.robinhood_mcp.order_scope_schema_qualifier import (
    OrderScopeClassification,
)

_ROOT = Path(__file__).resolve().parents[2]
_HEAD = subprocess.run(
    ("git", "-C", str(_ROOT), "rev-parse", "--verify", "HEAD"),
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()
_TREE = subprocess.run(
    ("git", "-C", str(_ROOT), "rev-parse", "--verify", "HEAD^{tree}"),
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()
_SCOPE = (
    "When placed_agent is omitted, the result includes all orders for the "
    "authenticated account across all agents."
)


def _tool(
    description: str = _SCOPE, schema_type: object = "string"
) -> dict[str, object]:
    return {
        "name": "get_equity_orders",
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {"placed_agent": {"type": schema_type}},
            "required": [],
        },
    }


def _page(tools: list[object], cursor: object = None) -> dict[str, object]:
    return {"tools": tools, "next_cursor": cursor}


def _admission(**changes: object) -> observer._SourceAdmission:
    return replace(
        observer._SourceAdmission(
            source_head=_HEAD,
            source_tree=_TREE,
            remote_feature_head=_HEAD,
            remote_develop_head=_HEAD,
            feature_authority="PASS",
            prospective_develop_authority="PASS",
            reason=None,
        ),
        **changes,
    )


class _Session:
    def __init__(self, pages: dict[str | None, object]) -> None:
        self.pages, self.cursors = pages, []
        self.close_error: Exception | None = None
        self.list_error: Exception | None = None
        self.print_on_list = False

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_: object) -> None:
        if self.close_error:
            raise self.close_error

    async def list_tools(self, *, cursor: str | None = None) -> object:
        self.cursors.append(cursor)
        if self.print_on_list:
            print("provider token=secret")
        if self.list_error:
            raise self.list_error
        return self.pages[cursor]


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch):
    state = SimpleNamespace(
        admission=_admission(),
        session=_Session({None: _page([_tool()])}),
        calls=[],
        real_runner=observer._run_production_session,
    )

    def admit(**_: object) -> observer._SourceAdmission:
        state.calls.append("admission")
        return state.admission

    def reserve(path: Path) -> Path:
        if path.exists():
            raise FileExistsError
        path.mkdir()
        return path

    async def run(attempts: observer._AttemptCounters, root: Path):
        state.calls.append("provider")
        attempts.oauth_scope_entry_attempts += 1
        attempts.mcp_session_open_attempts += 1
        async with state.session as client:
            return await observer._qualify(client, attempts, root)

    monkeypatch.setattr(observer, "_admit_current_source", admit)
    monkeypatch.setattr(observer, "_reserve_evidence_directory", reserve)
    monkeypatch.setattr(observer, "_verify_reserved_evidence_directory", lambda _: None)
    monkeypatch.setattr(observer, "_run_production_session", run)
    state.observer = observer.RobinhoodOrderScopeSchemaObserver()
    return state


def _observe(harness: object, tmp_path: Path, name: str):
    return asyncio.run(
        harness.observer.observe(evidence_dir=tmp_path / name)  # type: ignore[attr-defined]
    )


def _evidence(result: observer.OrderScopeObservationResult) -> dict[str, object]:
    assert result.evidence_file is not None
    return json.loads(result.evidence_file.read_text(encoding="ascii"))


def test_construction_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(observer.subprocess, "run", lambda *a, **k: calls.append(a))

    observer.RobinhoodOrderScopeSchemaObserver()

    assert calls == []


def test_source_admission_precedes_provider_construction(
    harness, tmp_path: Path
) -> None:
    harness.admission = _admission(reason="SOURCE_AUTHORITY_BLOCKED")

    result = _observe(harness, tmp_path, "source-blocked")

    assert (
        result.status is observer.OrderScopeObservationStatus.SOURCE_AUTHORITY_BLOCKED
    )
    assert harness.calls == ["admission"]
    counters = _evidence(result)["attempt_counters"]
    assert (
        counters["oauth_scope_entry_attempts"]
        == counters["mcp_session_open_attempts"]
        == 0
    )


def test_live_feature_and_develop_must_equal_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(observer, "_CANONICAL_WORKTREE", tmp_path)
    monkeypatch.setattr(observer, "_loaded_checkout_root", lambda: tmp_path)
    monkeypatch.setattr(
        observer,
        "_read_git_snapshot",
        lambda _: observer._SourceAdmission(
            root=str(tmp_path),
            branch="feature/robinhood-live-prototype-current",
            source_head=_HEAD,
            source_tree=_TREE,
            origin=observer._EXPECTED_ORIGIN,
            remote_feature_head="c" * 40,
            remote_develop_head=_HEAD,
            reason=None,
        ),
    )

    result = observer._admit_current_source(repo_root=tmp_path)

    assert not result.passed
    assert result.remote_feature_head == "c" * 40 and result.remote_feature_tree is None
    assert result.remote_develop_head == _HEAD and result.remote_develop_tree == _TREE


def test_ambiguous_schema_representation_fails_closed(harness, tmp_path: Path) -> None:
    target = _tool()
    target["inputSchema"] = target["input_schema"]
    harness.session.pages = {None: _page([target])}
    ambiguous = _observe(harness, tmp_path, "ambiguous")
    assert ambiguous.status is observer.OrderScopeObservationStatus.SCHEMA_MALFORMED


def test_duplicate_target_blocks(harness, tmp_path: Path) -> None:
    harness.session.pages = {None: _page([_tool(), _tool("duplicate")])}
    duplicate = _observe(harness, tmp_path, "duplicate")
    assert duplicate.status is observer.OrderScopeObservationStatus.SCHEMA_MALFORMED


def test_unrelated_and_raw_metadata_are_not_serialized(harness, tmp_path: Path) -> None:
    marker = "provider-private-marker"
    other = {"name": "unrelated", "description": marker, "inputSchema": {"x": marker}}
    target = _tool(marker, marker)
    target["input_schema"]["private_note"] = marker  # type: ignore[index]
    normalized = observer._normalize_page(_page([other, target]))
    assert normalized["tools"][0] == {"name": "unrelated"}
    harness.session.pages = {None: _page([other, target])}

    result = _observe(harness, tmp_path, "sanitized")
    evidence = _evidence(result)
    raw = result.evidence_file.read_text(encoding="ascii")  # type: ignore[union-attr]
    assert marker not in raw
    assert evidence["placed_agent_schema"]["schema_type"] == "UNRECOGNIZED"
    assert (
        result.status
        is observer.OrderScopeObservationStatus.PROVIDER_SEMANTICS_UNPROVEN
    )


def test_provider_exception_is_sanitized_and_tool_counters_remain_zero(
    harness, tmp_path: Path
) -> None:
    harness.session.list_error = RuntimeError("token=secret https://private.invalid")

    result = _observe(harness, tmp_path, "provider-error")

    assert (
        result.status
        is observer.OrderScopeObservationStatus.OAUTH_SESSION_TOOLS_LIST_FAILURE
    )
    raw = result.evidence_file.read_text(encoding="ascii")  # type: ignore[union-attr]
    assert "secret" not in raw and "private.invalid" not in raw
    counters = _evidence(result)["attempt_counters"]
    assert counters["tools_list_attempts"] == 1
    assert counters["mcp_tool_invocation_attempts"] == 0
    assert all(
        counters[name] == 0
        for name in (
            "account_reads",
            "position_reads",
            "order_reads",
            "review_calls",
            "placement_calls",
            "cancellation_calls",
            "other_tool_calls",
        )
    )


def test_positive_classification_remains_review_only(harness, tmp_path: Path) -> None:
    result = _observe(harness, tmp_path, "positive")
    evidence = _evidence(result)

    assert result.status is observer.OrderScopeObservationStatus.SCOPE_PROVEN_FOR_REVIEW
    assert (
        evidence["classification"]
        == OrderScopeClassification.PROVEN_ACCOUNT_WIDE_ALL_AGENTS.value
    )
    assert evidence["qualifier_evidence_sha256"]
    assert "live_authority" not in evidence and "order_authority" not in evidence


def test_session_close_failure_discards_positive_result(
    harness, tmp_path: Path
) -> None:
    harness.session.close_error = RuntimeError("provider token=secret")

    result = _observe(harness, tmp_path, "close-error")

    assert (
        result.status
        is observer.OrderScopeObservationStatus.OAUTH_SESSION_TOOLS_LIST_FAILURE
    )
    assert _evidence(result)["classification"] == "NOT_CLASSIFIED"
    assert "secret" not in result.evidence_file.read_text(encoding="ascii")  # type: ignore[union-attr]


def test_evidence_collision_blocks_before_source_or_provider(
    harness, tmp_path: Path
) -> None:
    collision = tmp_path / "exists"
    collision.mkdir()

    result = asyncio.run(harness.observer.observe(evidence_dir=collision))

    assert result.status is observer.OrderScopeObservationStatus.EVIDENCE_WRITE_FAILURE
    assert harness.calls == []


def test_final_holdout_and_provider_tool_dispatch_are_absent() -> None:
    source = Path(observer.__file__).read_text(encoding="utf-8")
    assert not hasattr(observer._MetadataToolsListTransport, "call_tool")
    assert all(
        token not in source
        for token in (
            "FINAL_HOLDOUT",
            ".call_tool(",
            "get_equity_positions",
            "review_equity_order",
            "place_equity_order",
            "cancel_equity_order",
        )
    )


def test_public_sdk_oauth_session_wiring_is_fake_and_output_is_suppressed(
    harness,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    events: list[str] = []
    session = _Session(
        {
            None: SimpleNamespace(
                tools=[
                    SimpleNamespace(
                        name="get_equity_orders",
                        description=_SCOPE,
                        input_schema=_tool()["input_schema"],
                    )
                ],
                next_cursor=None,
            )
        }
    )
    expected_auth = object()

    class Context:
        def __init__(self, value: object, name: str) -> None:
            self.value, self.name = value, name

        async def __aenter__(self):
            events.append(f"{self.name}-open")
            return self.value

        async def __aexit__(self, *_: object) -> None:
            events.append(f"{self.name}-close")

    httpx = types.ModuleType("httpx2")

    def make_http(*, auth: object) -> Context:
        assert auth is expected_auth
        return Context(object(), "http")

    httpx.AsyncClient = make_http  # type: ignore[attr-defined]
    mcp = types.ModuleType("mcp")

    def make_client(stream: object) -> Context:
        assert stream == "stream"
        return Context(session, "mcp")

    mcp.Client = make_client  # type: ignore[attr-defined]
    client_pkg = types.ModuleType("mcp.client")
    streamable = types.ModuleType("mcp.client.streamable_http")

    def make_stream(*_args: object, **_kwargs: object) -> str:
        events.append("stream")
        return "stream"

    streamable.streamable_http_client = make_stream  # type: ignore[attr-defined]
    for name, module in (
        ("httpx2", httpx),
        ("mcp", mcp),
        ("mcp.client", client_pkg),
        ("mcp.client.streamable_http", streamable),
    ):
        monkeypatch.setitem(sys.modules, name, module)

    from trading_bot.robinhood_mcp import windows_oauth

    def oauth_factory(**kwargs: object):
        events.append("oauth-factory")

        def enter_oauth() -> object:
            events.append("oauth-enter")
            browser_opener = kwargs["browser_opener"]
            browser_opener("https://auth.invalid/?token=secret")  # type: ignore[operator]
            return expected_auth

        return enter_oauth

    monkeypatch.setattr(
        windows_oauth, "create_windows_robinhood_oauth_factory", oauth_factory
    )
    monkeypatch.setattr(
        observer.webbrowser, "open", lambda _: events.append("browser-open")
    )
    monkeypatch.setattr(observer, "_run_production_session", harness.real_runner)
    session.print_on_list = True
    result = _observe(harness, tmp_path, "sdk")

    assert result.status is observer.OrderScopeObservationStatus.SCOPE_PROVEN_FOR_REVIEW
    wire = observer._normalize_page(
        {
            "tools": [
                {
                    "name": "get_equity_orders",
                    "description": _SCOPE,
                    "inputSchema": {"type": "object"},
                }
            ],
            "nextCursor": "cursor",
        }
    )
    assert wire["tools"][0]["input_schema"] == {"type": "object"}
    assert wire["next_cursor"] == "cursor"
    assert capsys.readouterr().out == ""
    assert events == [
        "oauth-factory",
        "oauth-enter",
        "browser-open",
        "http-open",
        "stream",
        "mcp-open",
        "mcp-close",
        "http-close",
    ]
    counters = _evidence(result)["attempt_counters"]
    assert counters["oauth_scope_entry_attempts"] == 1
    assert counters["browser_launches"] == 1
    assert counters["mcp_session_open_attempts"] == 1
    assert counters["tools_list_attempts"] == 1
    assert counters["mcp_tool_invocation_attempts"] == 0
