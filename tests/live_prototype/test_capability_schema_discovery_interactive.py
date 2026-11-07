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

from trading_bot.live_prototype import (
    capability_schema_discovery_interactive as discovery,
)

_HEAD = "1" * 40
_TREE = "2" * 40
_OAUTH = object()


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


def _tool(
    name: str,
    description: str,
    *,
    quantity_type: object = "string",
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
        noise: bool = False,
        fail_list: bool = False,
    ) -> None:
        self.pages = pages
        self.events = events
        self.noise = noise
        self.fail_list = fail_list
        self.calls: list[tuple[str, Mapping[str, object]]] = []

    async def list_tools(self, *, cursor: str | None = None) -> object:
        self.events.append("tools_list")
        if self.noise:
            print("SECRET_PROVIDER_STDOUT")
            print("SECRET_PROVIDER_STDERR", file=sys.stderr)
            os.write(1, b"SECRET_PROVIDER_FD1")
            os.write(2, b"SECRET_PROVIDER_FD2")
            logging.getLogger("provider").critical("SECRET_PROVIDER_LOG")
            warnings.warn("SECRET_PROVIDER_WARNING", stacklevel=1)
        if self.fail_list:
            raise RuntimeError("SECRET_PROVIDER_EXCEPTION")
        index = 0 if cursor is None else int(cursor)
        entries, next_cursor = self.pages[index]
        return SimpleNamespace(tools=entries, next_cursor=next_cursor)

    async def call_tool(self, name: str, arguments: Mapping[str, object]) -> object:
        self.calls.append((name, arguments))
        raise AssertionError(
            "interactive schema discovery must never invoke an MCP tool"
        )


def _run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    pages: Sequence[tuple[Sequence[object], str | None]] | None = None,
    source: discovery.SourceAdmission | None = None,
    events: list[str] | None = None,
    noise: bool = False,
    fail_close: bool = False,
    fail_list: bool = False,
    require_browser: bool = False,
    expected_schema_digests: Mapping[str, str] | None = None,
) -> tuple[
    discovery.InteractiveSchemaDiscoveryResult,
    _FakeClient,
    list[str],
    discovery._OneShotBrowserOpener,
]:
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
        noise=noise,
        fail_list=fail_list,
    )
    opener = discovery._OneShotBrowserOpener(lambda _url: True)

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
        if require_browser:
            opener("https://auth.example/SECRET_AUTHORIZATION_URL")
        return _OAUTH

    def admit_test_source(root: Path) -> discovery.SourceAdmission:
        assert root == tmp_path
        local_events.append("source")
        return source_value

    bundle = discovery._OAuthFactoryBundle(oauth_factory, opener)
    result = discovery._run_with_dependencies(
        evidence_dir=candidate_dir,
        source_admitter=admit_test_source,
        oauth_factory_builder=lambda: (
            local_events.append("oauth_factory_builder"),
            bundle,
        )[1],
        transport_builder=lambda oauth_factory: (
            local_events.append("transport_builder"),
            make_transport(oauth_factory),
        )[1],
        repository_root_resolver=lambda: tmp_path,
        expected_schema_digests=expected_schema_digests,
    )
    return result, client, local_events, opener


def test_source_rejection_precedes_oauth_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, client, events, opener = _run(
        monkeypatch,
        tmp_path,
        source=_source(feature_authority="NOT_RUN"),
    )

    assert result.status == "BLOCKED"
    assert result.reason == "L41R2_SOURCE_ADMISSION_BLOCKED"
    assert events == ["source"]
    assert client.calls == []
    assert opener.launch_count == 0
    assert result.attempt_counts == discovery.InteractiveSchemaDiscoveryAttemptCounts()


def test_noncanonical_production_module_root_fails_before_oauth(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    candidate_dir = tmp_path / "fresh-evidence"
    events: list[str] = []

    def create_test_evidence_dir(path: Path) -> Path:
        path.mkdir()
        return path

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
            / "capability_schema_discovery_interactive.py"
        ),
    )
    monkeypatch.setattr(
        discovery,
        "admit_l41_source",
        lambda _root: events.append("source") or _source(),
    )
    monkeypatch.setattr(
        discovery,
        "_build_windows_oauth_factory",
        lambda: (_ for _ in ()).throw(AssertionError("OAuth must follow root gate")),
    )

    result = discovery.run_l41r2_interactive_schema_discovery(
        evidence_dir=candidate_dir
    )

    assert result.status == "BLOCKED"
    assert result.reason == "L41R2_SOURCE_ADMISSION_BLOCKED"
    assert events == []


def test_persisted_oauth_sufficient_does_not_open_browser(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, _client, events, opener = _run(monkeypatch, tmp_path)

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert opener.launch_count == 0
    assert events[-3:] == ["session_open", "tools_list", "session_close"]


def test_sdk_authorization_opens_browser_exactly_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, _client, _events, opener = _run(monkeypatch, tmp_path, require_browser=True)

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert opener.launch_count == 1
    assert result.attempt_counts.browser_launches == 1


def test_second_browser_open_is_blocked_before_real_opener_invocation() -> None:
    calls: list[str] = []
    opener = discovery._OneShotBrowserOpener(calls.append)

    assert opener("SECRET_FIRST_URL") is None
    with pytest.raises(RuntimeError, match="L41R2_BROWSER_LAUNCH_ALREADY_USED"):
        opener("SECRET_SECOND_URL")
    assert calls == ["SECRET_FIRST_URL"]


def test_authorization_url_and_callback_material_never_persist_or_print(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    tools = _tools()
    tools[0].description = (
        "Simulation pre-trade warning; no order was placed. "
        "SECRET_CALLBACK_CODE SECRET_CALLBACK_STATE SECRET_ACCESS_TOKEN"
    )
    result, _client, _events, _opener = _run(
        monkeypatch,
        tmp_path,
        pages=[(tools, None)],
        require_browser=True,
    )

    output = capfd.readouterr()
    persisted = result.evidence_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
    for secret in (
        "SECRET_AUTHORIZATION_URL",
        "SECRET_CALLBACK_CODE",
        "SECRET_CALLBACK_STATE",
        "SECRET_ACCESS_TOKEN",
    ):
        assert secret not in output.out + output.err
        assert secret not in persisted


def test_provider_stdout_stderr_logging_warnings_and_native_fds_are_discarded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    result, _client, _events, _opener = _run(monkeypatch, tmp_path, noise=True)

    assert result.status == "CAPTURED_FOR_REVIEW"
    captured = capfd.readouterr()
    assert captured == ("", "")


def test_tools_list_occurs_only_after_session_establishment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, client, events, _opener = _run(monkeypatch, tmp_path)

    assert result.status == "CAPTURED_FOR_REVIEW"
    assert events.index("session_open") < events.index("tools_list")
    assert client.calls == []


def test_discovery_boundary_exposes_no_call_tool_and_counters_remain_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, client, _events, _opener = _run(monkeypatch, tmp_path)

    assert not hasattr(discovery.RobinhoodSchemaDiscoveryTransport, "call_tool")
    assert client.calls == []
    counts = asdict(result.attempt_counts)
    assert counts["mcp_tool_invocation_attempts"] == 0
    assert all(
        value == 0
        for name, value in counts.items()
        if name
        not in {
            "oauth_scope_entry_attempts",
            "mcp_session_open_attempts",
            "tools_list_attempts",
            "browser_launches",
        }
    )


def test_decimal_string_quantity_representation_survives(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, _client, _events, _opener = _run(monkeypatch, tmp_path)

    review = next(
        item for item in result.schemas if item.tool_name == "review_equity_order"
    )
    assert review.quantity_field_type == "string"
    assert review.quantity_field_present is True
    assert review.quantity_field_required is False


@pytest.mark.parametrize(
    ("pages", "reason"),
    [
        (
            lambda: [([_tools()[0]], None)],
            "L41R2_REQUIRED_SCHEMA_MISSING",
        ),
        (
            lambda: [([_tools()[0], _tools()[0]], None)],
            "L41R2_DUPLICATE_SCHEMA",
        ),
        (
            lambda: [
                ([_tools()[0]], "1"),
                (
                    [_tool("review_equity_order", "Changed description."), _tools()[1]],
                    None,
                ),
            ],
            "L41R2_SCHEMA_CHANGED",
        ),
        (
            lambda: [([_tool("review_equity_order", "bad", quantity_type={})], None)],
            "L41R2_SCHEMA_MALFORMED",
        ),
    ],
)
def test_malformed_duplicate_conflicting_schema_blocks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pages: object,
    reason: str,
) -> None:
    page = pages()
    result, _client, _events, _opener = _run(
        monkeypatch,
        tmp_path,
        pages=page,  # type: ignore[arg-type]
    )

    assert result.status == "BLOCKED"
    assert result.reason == reason


def test_session_close_failure_is_truthful_and_retains_schemas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, _client, _events, _opener = _run(monkeypatch, tmp_path, fail_close=True)

    assert result.status == "BLOCKED"
    assert result.reason == "L41R2_SESSION_CLOSE_FAILED"
    assert {item.tool_name for item in result.schemas} == {
        "review_equity_order",
        "place_equity_order",
    }
    assert result.attempt_counts.tools_list_attempts == 1


def test_session_open_failure_never_reaches_tools_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []
    candidate_dir = tmp_path / "fresh-evidence"

    def create_test_evidence_dir(path: Path) -> Path:
        path.mkdir()
        return path

    monkeypatch.setattr(discovery, "_fresh_evidence_dir", create_test_evidence_dir)

    class FailingContext:
        async def __aenter__(self) -> object:
            events.append("session_open")
            raise RuntimeError("SECRET_SESSION_FAILURE")

        async def __aexit__(self, *args: object) -> None:
            events.append("session_close")

    def session_factory(_oauth: object) -> FailingContext:
        return FailingContext()

    opener = discovery._OneShotBrowserOpener(lambda _url: True)
    bundle = discovery._OAuthFactoryBundle(lambda: _OAUTH, opener)

    def transport(oauth: object) -> discovery.RobinhoodSchemaDiscoveryTransport:
        return discovery.RobinhoodSchemaDiscoveryTransport(
            oauth, session_factory=session_factory
        )

    result = discovery._run_with_dependencies(
        evidence_dir=candidate_dir,
        source_admitter=lambda _root: _source(),
        oauth_factory_builder=lambda: bundle,
        transport_builder=transport,
        repository_root_resolver=lambda: tmp_path,
    )

    assert result.status == "BLOCKED"
    assert result.reason == "L41R2_MCP_SESSION_OPEN_FAILED"
    assert result.attempt_counts.tools_list_attempts == 0
    assert events == ["session_open"]


def test_evidence_schema_and_one_shot_marker_are_exactly_sanitized(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, _client, _events, _opener = _run(monkeypatch, tmp_path)

    payload = json.loads(result.evidence_path.read_text(encoding="utf-8"))  # type: ignore[union-attr]
    assert payload["schema"] == discovery.L41R2_EVIDENCE_SCHEMA
    assert payload["observation"] == "L41R2_INTERACTIVE_SCHEMA_DISCOVERY"
    assert payload["one_shot"] is True
    assert payload["native_credential_read_count"] is None
    assert payload["native_credential_write_count"] is None
    assert payload["credential_store_accounting"] == (
        "SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED"
    )
    assert payload["trusted_binding"] is False
    assert payload["provider_numeric_rules_derived"] is False
    assert payload["automatic_retry"] == "FORBIDDEN"
    assert payload["attempt_counts"]["browser_launches"] == 0
    assert all(
        payload["attempt_counts"][name] == 0
        for name in (
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
        )
    )


def test_cli_emits_only_fixed_final_json_envelope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    evidence = tmp_path / "evidence.json"
    result = discovery.InteractiveSchemaDiscoveryResult(
        "BLOCKED",
        "L41R2_TOOLS_LIST_FAILED",
        evidence,
        None,
        discovery.InteractiveSchemaDiscoveryAttemptCounts(),
        (),
    )
    monkeypatch.setattr(
        discovery,
        "run_l41r2_interactive_schema_discovery",
        lambda evidence_dir: result,
    )

    assert discovery.main(["--evidence-dir", str(tmp_path / "fresh")]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "evidence_path": str(evidence),
        "reason": "L41R2_TOOLS_LIST_FAILED",
        "status": "BLOCKED",
    }
