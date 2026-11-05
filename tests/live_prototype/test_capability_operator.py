"""Fake-only tests for the source-admitted L41 command boundary."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.live_prototype import capability_operator as operator
from trading_bot.live_prototype.capability_collector import (
    CapabilityCallCounts,
    CapabilityCollection,
    collect_capabilities,
)
from trading_bot.live_prototype.capability_observer import (
    CapabilityReport,
    Classification,
    FactId,
    FactResult,
    OverallStatus,
)
from trading_bot.live_prototype.capability_transport import (
    CapabilityTransportCounts,
    RobinhoodCapabilityTransport,
)

_ACCOUNT = "SECRET_ACCOUNT_NUMBER_4831"
_HEAD = "1" * 40
_TREE = "2" * 40


def _source() -> operator.SourceAdmission:
    return operator.SourceAdmission(
        branch=operator.L41_FEATURE_BRANCH,
        head=_HEAD,
        tree=_TREE,
        origin_feature_head=_HEAD,
        origin_feature_tree=_TREE,
        origin_develop_head=_HEAD,
        origin_develop_tree=_TREE,
        feature_authority="PASS",
        prospective_develop_authority="PASS",
    )


def _accounts() -> dict[str, object]:
    return {
        "data": {
            "accounts": [
                {
                    "account_number": _ACCOUNT,
                    "agentic_allowed": True,
                    "brokerage_account_type": "individual",
                    "state": "active",
                    "deactivated": False,
                    "permanently_deactivated": False,
                }
            ]
        }
    }


def _tradability() -> dict[str, object]:
    return {
        "data": {
            "results": [
                {
                    "symbol": "SPY",
                    "tradeable": True,
                    "state": "active",
                    "fractional_tradability": "tradable",
                    "account_type_tradabilities": [
                        {
                            "account_type": "individual",
                            "account_type_tradability": "tradable",
                        }
                    ],
                }
            ]
        }
    }


class _FakeClient:
    def __init__(self, failure: Exception | None = None) -> None:
        self.calls: list[tuple[str, Mapping[str, object]]] = []
        self.failure = failure

    async def list_tools(self, *, cursor: str | None = None) -> object:
        assert cursor is None
        return SimpleNamespace(
            tools=[
                SimpleNamespace(name="get_accounts"),
                SimpleNamespace(name="get_equity_tradability"),
            ],
            next_cursor=None,
        )

    async def call_tool(self, name: str, arguments: Mapping[str, object]) -> object:
        self.calls.append((name, dict(arguments)))
        if self.failure is not None:
            raise self.failure
        payload = _accounts() if name == "get_accounts" else _tradability()
        return SimpleNamespace(is_error=False, structured_content=payload)


def _dependencies(
    client: _FakeClient,
    events: list[str],
    *,
    admitter=None,
):
    def source_admitter(_root: Path) -> operator.SourceAdmission:
        events.append("admission")
        if admitter is not None:
            return admitter()
        return _source()

    def oauth_builder():
        events.append("oauth_factory_build")

        def oauth_factory():
            events.append("oauth_scope_entry")
            return object()

        return oauth_factory

    @asynccontextmanager
    async def session_factory(_oauth: object) -> AsyncIterator[_FakeClient]:
        events.append("session_open")
        try:
            yield client
        finally:
            events.append("session_close")

    def transport_builder(oauth_factory):
        events.append("transport_construct")
        return RobinhoodCapabilityTransport(
            oauth_factory, session_factory=session_factory
        )

    return source_admitter, oauth_builder, transport_builder


def _run(
    evidence_dir: Path,
    client: _FakeClient,
    events: list[str],
    *,
    admitter=None,
    collector=collect_capabilities,
):
    source_admitter, oauth_builder, transport_builder = _dependencies(
        client, events, admitter=admitter
    )
    return operator._run_with_dependencies(
        evidence_dir,
        source_admitter=source_admitter,
        oauth_factory_builder=oauth_builder,
        transport_builder=transport_builder,
        collector=collector,
    )


def _otherwise_ready_collection() -> CapabilityCollection:
    facts = tuple(
        FactResult(
            fact_id,
            Classification.DEFER_TO_FIRST_OWNED_POSITION
            if fact_id is FactId.INSTANCE_REVIEW_REQUIRES_POSITION
            else Classification.PROVEN,
            "TEST_FACT_CLASSIFICATION",
        )
        for fact_id in FactId
    )
    report = CapabilityReport(
        OverallStatus.READY_FOR_L42,
        facts,
        "a" * 64,
        "individual",
    )
    return CapabilityCollection(
        report,
        "L41_TEST_READY",
        CapabilityCallCounts(1, 1),
    )


class _ReadyTransport:
    def __init__(self, counts: object) -> None:
        self._counts = counts

    @property
    def call_counts(self):
        if isinstance(self._counts, Exception):
            raise self._counts
        return self._counts

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False


def _run_ready_collection(tmp_path: Path, counts: object):
    return operator._run_with_dependencies(
        tmp_path / "ready-result",
        source_admitter=lambda _root: _source(),
        oauth_factory_builder=lambda: object(),
        transport_builder=lambda _oauth: _ReadyTransport(counts),
        collector=lambda _boundary: _otherwise_ready_collection(),
    )


def _counts_with_prohibited_attempt(field_name: str) -> CapabilityTransportCounts:
    counts = CapabilityTransportCounts(1, 1, 1, 1)
    object.__setattr__(counts, field_name, 1)
    return counts


def test_ready_requires_proven_exact_scope_session_reads_and_zero_other_calls(
    tmp_path: Path,
) -> None:
    result = _run_ready_collection(tmp_path, CapabilityTransportCounts(1, 1, 1, 1))

    assert result.status is OverallStatus.READY_FOR_L42
    assert result.reason == "L41_TEST_READY"
    assert result.evidence.transport_counts.oauth_scope_entry_attempts == 1
    assert result.evidence.transport_counts.mcp_session_open_attempts == 1
    assert result.evidence.transport_counts.get_accounts_attempts == 1
    assert result.evidence.transport_counts.get_equity_tradability_attempts == 1
    assert result.evidence.transport_counts.other_tool_attempts == 0
    assert result.evidence.transport_counts.review_equity_order_attempts == 0
    assert result.evidence.transport_counts.place_equity_order_attempts == 0
    assert result.evidence.transport_counts.cancel_equity_order_attempts == 0
    assert result.evidence.collector_counts == CapabilityCallCounts(1, 1)
    assert result.evidence.collector_invocations == 1


@pytest.mark.parametrize(
    "counts",
    [
        CapabilityTransportCounts(1, 1, 1, 0),
        None,
        RuntimeError("SECRET_COUNT_ERROR"),
    ],
)
def test_ready_is_blocked_by_mismatched_unknown_or_prohibited_attempt_counts(
    tmp_path: Path,
    counts: object,
) -> None:
    result = _run_ready_collection(tmp_path, counts)

    assert result.status is OverallStatus.BLOCKED
    assert result.evidence.report.status is OverallStatus.READY_FOR_L42
    assert result.reason != "L41_TEST_READY"
    if counts is None or isinstance(counts, Exception):
        assert result.evidence.transport_counts is None


@pytest.mark.parametrize(
    "field_name",
    (
        "other_tool_attempts",
        "review_equity_order_attempts",
        "place_equity_order_attempts",
        "cancel_equity_order_attempts",
    ),
)
def test_ready_is_blocked_by_each_prohibited_transport_attempt(
    tmp_path: Path,
    field_name: str,
) -> None:
    result = _run_ready_collection(
        tmp_path, _counts_with_prohibited_attempt(field_name)
    )

    assert result.status is OverallStatus.BLOCKED
    assert result.evidence.transport_counts is None
    assert result.reason == "L41_ATTEMPT_COUNTS_UNAVAILABLE"


def test_source_rejection_happens_before_oauth_or_transport(tmp_path: Path) -> None:
    events: list[str] = []

    def reject_source():
        raise operator._SourceAdmissionBlocked(_source())

    result = _run(
        tmp_path / "rejected",
        _FakeClient(),
        events,
        admitter=reject_source,
    )

    assert result.status is OverallStatus.BLOCKED
    assert result.reason == "L41_SOURCE_ADMISSION_BLOCKED"
    assert events == ["admission"]
    assert result.evidence.transport_counts == CapabilityTransportCounts(0, 0, 0, 0)
    assert result.evidence.native_credential_read_count is None
    evidence = json.loads(result.evidence_path.read_text(encoding="utf-8"))
    assert evidence["source"]["head"] == _HEAD
    assert evidence["attempts"]["oauth_scope_entry_attempts"] == 0


def test_success_collects_two_reads_once_in_one_scope_and_sanitizes_evidence(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    client = _FakeClient()
    collection_calls = 0

    def counted_collector(boundary):
        nonlocal collection_calls
        collection_calls += 1
        events.append("collect")
        return collect_capabilities(boundary)

    result = _run(
        tmp_path / "success",
        client,
        events,
        collector=counted_collector,
    )

    assert result.status is OverallStatus.BLOCKED
    assert collection_calls == 1
    assert events == [
        "admission",
        "oauth_factory_build",
        "transport_construct",
        "oauth_scope_entry",
        "session_open",
        "collect",
        "session_close",
    ]
    assert client.calls == [
        ("get_accounts", {}),
        (
            "get_equity_tradability",
            {"account_number": _ACCOUNT, "symbols": ["SPY"]},
        ),
    ]
    counts = result.evidence.transport_counts
    assert counts.oauth_scope_entry_attempts == 1
    assert counts.mcp_session_open_attempts == 1
    assert counts.get_accounts_attempts == 1
    assert counts.get_equity_tradability_attempts == 1
    assert counts.other_tool_attempts == 0
    assert counts.review_equity_order_attempts == 0
    assert counts.place_equity_order_attempts == 0
    assert counts.cancel_equity_order_attempts == 0
    assert result.evidence.native_credential_read_count is None

    evidence_text = result.evidence_path.read_text(encoding="utf-8")
    evidence = json.loads(evidence_text)
    assert _ACCOUNT not in evidence_text
    assert "SECRET_PROVIDER_TEXT" not in evidence_text
    assert len(evidence["capability_report"]["facts"]) == 13
    facts = {
        item["fact_id"]: item["classification"]
        for item in evidence["capability_report"]["facts"]
    }
    assert facts[FactId.MINIMUM_QUANTITY.value] == Classification.BLOCKING_L42.value
    assert evidence["attempts"]["native_credential_read_count"] is None
    assert evidence["attempts"]["collector_invocations"] == 1


def test_failed_account_read_keeps_attempt_count_and_sanitizes_provider_text(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    client = _FakeClient(RuntimeError(f"SECRET_PROVIDER_TEXT {_ACCOUNT}"))

    result = _run(tmp_path / "failed-read", client, events)

    assert result.status is OverallStatus.BLOCKED
    assert result.reason == "L41_ACCOUNTS_READ_FAILED"
    assert result.evidence.transport_counts.oauth_scope_entry_attempts == 1
    assert result.evidence.transport_counts.mcp_session_open_attempts == 1
    assert result.evidence.transport_counts.get_accounts_attempts == 1
    assert result.evidence.transport_counts.get_equity_tradability_attempts == 0
    assert len(client.calls) == 1
    body = result.evidence_path.read_text(encoding="utf-8")
    assert "SECRET_PROVIDER_TEXT" not in body
    assert _ACCOUNT not in body


def test_invalid_evidence_path_is_rejected_before_source_admission() -> None:
    events: list[str] = []
    source_admitter, oauth_builder, transport_builder = _dependencies(
        _FakeClient(), events
    )

    result = operator._run_with_dependencies(
        Path("C:/not-allowed/arch147-l41-evidence"),
        source_admitter=source_admitter,
        oauth_factory_builder=oauth_builder,
        transport_builder=transport_builder,
        collector=collect_capabilities,
    )

    assert result.status is OverallStatus.BLOCKED
    assert result.reason == "L41_EVIDENCE_PATH_INVALID"
    assert result.evidence_path is None
    assert events == []


def test_malformed_source_identity_is_rejected_before_oauth(tmp_path: Path) -> None:
    events: list[str] = []

    def oauth_builder():
        events.append("oauth_factory_build")
        return object()

    def transport_builder(_oauth):
        events.append("transport_construct")
        return object()

    result = operator._run_with_dependencies(
        tmp_path / "bad-source",
        source_admitter=lambda _root: SimpleNamespace(
            head=f"SECRET_PROVIDER_TEXT {_HEAD}"
        ),
        oauth_factory_builder=oauth_builder,
        transport_builder=transport_builder,
        collector=collect_capabilities,
    )

    assert result.status is OverallStatus.BLOCKED
    assert result.reason == "L41_SOURCE_ADMISSION_BLOCKED"
    assert events == []
    body = result.evidence_path.read_text(encoding="utf-8")
    assert "SECRET_PROVIDER_TEXT" not in body


class _UnknownCountsTransport:
    @property
    def call_counts(self):
        raise RuntimeError("SECRET_PROVIDER_TEXT")

    def __enter__(self):
        return object()

    def __exit__(self, _exc_type, _exc, _traceback):
        return False


def _raise_collector_failure(_boundary):
    raise RuntimeError("SECRET_PROVIDER_TEXT")


def test_unavailable_counters_after_collector_failure_are_null_not_zero(
    tmp_path: Path,
) -> None:
    result = operator._run_with_dependencies(
        tmp_path / "unknown-counts",
        source_admitter=lambda _root: _source(),
        oauth_factory_builder=lambda: object(),
        transport_builder=lambda _oauth: _UnknownCountsTransport(),
        collector=_raise_collector_failure,
    )

    assert result.status is OverallStatus.BLOCKED
    assert result.reason == "L41_ATTEMPT_COUNTS_UNAVAILABLE"
    assert result.evidence.transport_counts is None
    assert result.evidence.collector_counts is None
    assert result.evidence.collector_invocations == 1
    body_text = result.evidence_path.read_text(encoding="utf-8")
    body = json.loads(body_text)
    assert "SECRET_PROVIDER_TEXT" not in body_text
    assert body["attempts"]["get_accounts_attempts"] is None
    assert body["attempts"]["collector_get_accounts_attempts"] is None
    assert body["attempts"]["oauth_scope_entry_attempts"] is None


def test_help_exits_without_admission_oauth_or_evidence_effects(
    monkeypatch, capsys
) -> None:
    def forbidden(_path: Path):
        raise AssertionError("operator invoked during --help")

    monkeypatch.setattr(operator, "run_l41_read_only_observation", forbidden)

    with pytest.raises(SystemExit) as exit_info:
        operator.main(["--help"])

    assert exit_info.value.code == 0
    assert "--evidence-dir" in capsys.readouterr().out


def test_oauth_composition_reuses_accepted_redirect_uri(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_factory(**kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(
        "trading_bot.robinhood_mcp.windows_oauth.create_windows_robinhood_oauth_factory",
        fake_factory,
    )

    result = operator._create_windows_oauth_factory()

    assert result is not None
    assert calls[0]["redirect_uri"] == "http://127.0.0.1:8765/robinhood/callback"
    assert calls[0]["browser_opener"] is operator._forbid_interactive_oauth


def test_live_source_admission_rejects_develop_mismatch_before_authority(
    monkeypatch,
) -> None:
    root = Path(__file__).resolve().parents[2]
    calls: list[tuple[str, ...]] = []

    def fake_git(_root: Path, *args: str) -> str:
        calls.append(args)
        if args == ("branch", "--show-current"):
            return operator.L41_FEATURE_BRANCH
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return ""
        if args == ("rev-parse", "--verify", "HEAD"):
            return _HEAD
        if args == ("rev-parse", "HEAD^{tree}"):
            return _TREE
        if args == ("remote", "get-url", "origin"):
            return operator._EXPECTED_ORIGIN
        if args[0] == "ls-remote":
            reference = args[-1]
            remote_head = "3" * 40
            if reference.endswith(operator.L41_FEATURE_BRANCH):
                remote_head = _HEAD
            return f"{remote_head}\t{reference}"
        raise AssertionError(args)

    authority_calls: list[object] = []

    def forbidden_authority(_root: Path, *, publication_context: object):
        authority_calls.append(publication_context)
        raise AssertionError("authority must not run after identity mismatch")

    monkeypatch.setattr(operator, "_git_output", fake_git)
    monkeypatch.setattr(operator, "evaluate_source_authority", forbidden_authority)

    with pytest.raises(operator._SourceAdmissionBlocked) as error:
        operator.admit_l41_source(root)

    assert error.value.source.origin_feature_head == _HEAD
    assert error.value.source.origin_develop_head == "3" * 40
    assert error.value.source.origin_develop_tree is None
    assert authority_calls == []


def test_live_source_admission_requires_both_authority_contexts(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[2]

    def fake_git(_root: Path, *args: str) -> str:
        if args == ("branch", "--show-current"):
            return operator.L41_FEATURE_BRANCH
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return ""
        if args == ("rev-parse", "--verify", "HEAD"):
            return _HEAD
        if args == ("rev-parse", "HEAD^{tree}"):
            return _TREE
        if args == ("remote", "get-url", "origin"):
            return operator._EXPECTED_ORIGIN
        if args[0] == "ls-remote":
            reference = args[-1]
            return f"{_HEAD}\t{reference}"
        raise AssertionError(args)

    authorities: list[object] = []

    def authority(_root: Path, *, publication_context: object):
        authorities.append(publication_context)
        return SimpleNamespace(
            passed=True,
            head=_HEAD,
            tree=_TREE,
            checkpoints=(operator.L41_CHECKPOINT_OWNER,),
        )

    monkeypatch.setattr(operator, "_git_output", fake_git)
    monkeypatch.setattr(operator, "evaluate_source_authority", authority)

    admission = operator.admit_l41_source(root)

    assert admission.origin_feature_head == _HEAD
    assert admission.origin_develop_head == _HEAD
    assert admission.origin_feature_tree == _TREE
    assert admission.origin_develop_tree == _TREE
    assert admission.feature_authority == "PASS"
    assert admission.prospective_develop_authority == "PASS"
    assert len(authorities) == 2
