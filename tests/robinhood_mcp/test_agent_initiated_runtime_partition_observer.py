from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import checkpoint_runner as runner
from trading_bot.live_prototype.l43_production_owner import L43SourceIdentity
from trading_bot.live_prototype.l43_provider_contracts import (
    L43AccountIdentity,
    L43ReadPage,
)
from trading_bot.robinhood_mcp import (
    agent_initiated_runtime_partition_observer as observer,
)
from trading_bot.robinhood_mcp import agent_initiated_runtime_partition_proof as proof

_HEAD = "a" * 40
_TREE = "b" * 40
_SOURCE = L43SourceIdentity(_HEAD, _TREE)
_ACCOUNT = "account-secret-147"
_FINGERPRINT = "c" * 64
_NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


class _Read:
    def get_accounts(self) -> L43AccountIdentity:
        return L43AccountIdentity(_ACCOUNT, _FINGERPRINT)

    def get_equity_orders(self, arguments: dict[str, object]) -> L43ReadPage:
        assert arguments["symbol"] == "SPY"
        return L43ReadPage(rows=(), next_cursor=None)


class _AccountFailure:
    def get_accounts(self) -> L43AccountIdentity:
        raise RuntimeError("raw provider error secret-token")

    def get_equity_orders(self, arguments: dict[str, object]) -> L43ReadPage:
        raise AssertionError("account failure must stop before order reads")


class _ToolListing:
    tools = (
        SimpleNamespace(name="get_accounts"),
        SimpleNamespace(name="get_equity_orders"),
    )
    next_cursor = None


class _Session:
    def __init__(self, calls: list[tuple[str, str, object]]) -> None:
        self._calls = calls

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def list_tools(self, *, cursor: str | None = None) -> _ToolListing:
        self._calls.append(("list", "", cursor))
        return _ToolListing()

    async def call_tool(
        self, name: str, arguments: dict[str, object]
    ) -> SimpleNamespace:
        self._calls.append(("call", name, arguments))
        if name == "get_accounts":
            payload = {
                "data": {
                    "accounts": [{"account_number": _ACCOUNT, "agentic_allowed": True}]
                }
            }
        else:
            payload = {"data": {"orders": [], "next": None}}
        return SimpleNamespace(is_error=False, structured_content=payload)


def _valid_proof() -> proof.AgentInitiatedRuntimePartitionProofResult:
    return proof.prove_agent_initiated_partition(
        _Read(),
        source_reader=lambda: _SOURCE,
        expected_source=_SOURCE,
    )


def _not_proven() -> proof.AgentInitiatedRuntimePartitionProofResult:
    return proof.prove_agent_initiated_partition(
        _AccountFailure(),
        source_reader=lambda: _SOURCE,
        expected_source=_SOURCE,
    )


def _admission(**changes: object) -> observer._SourceAdmission:
    return replace(
        observer._SourceAdmission(
            root=str(observer._CANONICAL_WORKTREE),
            branch=observer._EXPECTED_BRANCH,
            source_head=_HEAD,
            source_tree=_TREE,
            porcelain="",
            origin=observer._EXPECTED_ORIGIN,
            remote_feature_head=_HEAD,
            remote_develop_head=_HEAD,
            feature_authority="PASS",
            prospective_develop_authority="PASS",
            reason=None,
        ),
        **changes,
    )


def _install_fake_harness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    run,
    *,
    admission: observer._SourceAdmission | None = None,
    source_recheck=None,
) -> list[str]:
    events: list[str] = []
    monkeypatch.setattr(observer, "_canonical_checkout_is_unambiguous", lambda _: True)
    monkeypatch.setattr(
        observer,
        "_admit_current_source",
        lambda *, repo_root: events.append("admission") or (admission or _admission()),
    )
    monkeypatch.setattr(
        observer,
        "_module_origins_are_source_owned",
        lambda *, repo_root: events.append("module-origins") or True,
    )

    def reserve(path: Path) -> Path:
        events.append("reserve")
        path.mkdir()
        return path

    def write(path: Path, material: dict[str, object]):
        raw = (
            json.dumps(
                material, ensure_ascii=True, sort_keys=True, separators=(",", ":")
            )
            + "\n"
        ).encode("ascii")
        evidence = path / "evidence.json"
        evidence.write_bytes(raw)
        return evidence, hashlib.sha256(raw).hexdigest()

    monkeypatch.setattr(observer, "_reserve_evidence_directory", reserve)
    monkeypatch.setattr(observer, "_write_evidence", write)
    monkeypatch.setattr(observer, "_suppress_external_output", nullcontext)
    monkeypatch.setattr(
        observer,
        "_source_recheck",
        source_recheck or (lambda repo_root, expected_source: True),
    )
    monkeypatch.setattr(observer, "_run_production_session", run)
    return events


def _observe_with(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    run,
    **kwargs: object,
) -> observer.AgentInitiatedRuntimePartitionObservationResult:
    _install_fake_harness(monkeypatch, tmp_path, run, **kwargs)
    instance = observer.RobinhoodAgentInitiatedRuntimePartitionObserver()
    return asyncio.run(
        instance.observe(
            evidence_dir=tmp_path
            / ("arch147-agent-initiated-runtime-partition-" + "a" * 32)
        )
    )


def test_observer_signature_is_one_use_and_construction_is_inert() -> None:
    instance = observer.RobinhoodAgentInitiatedRuntimePartitionObserver()

    assert list(inspect.signature(instance.observe).parameters) == ["evidence_dir"]
    assert instance._used is False
    assert not hasattr(observer.RobinhoodB2ReadTransport, "get_equity_positions")
    assert not hasattr(observer.RobinhoodB2ReadTransport, "place_equity_order")


def test_b2o_checkpoint_is_explicit_manual_and_not_automatic() -> None:
    root = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[runner.ARCH147_B2O_NAME]

    assert spec.preflight is runner._arch147_b2o_preflight
    assert spec.execute is None
    assert spec.remote_branch is None
    assert runner.ARCH147_B2O_NAME not in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert runner.ARCH147_B2O_NAME not in runner.ACTIVE_CI_CHECKPOINTS
    assert runner.ARCH147_B2O_NAME not in runner.CI_CERTIFICATION_PROFILES
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), runner.ARCH147_PROTOTYPE_BRANCH, "push"
        )
        == runner.ARCH147_PROTOTYPE_NAME
    )
    assert runner._arch147_b2o_authority_check(root) == ()


@pytest.mark.parametrize(
    "admission",
    (
        _admission(reason="SOURCE_AUTHORITY_BLOCKED"),
        _admission(branch="wrong-branch", reason="SOURCE_AUTHORITY_BLOCKED"),
        _admission(porcelain=" M tracked.py", reason="SOURCE_AUTHORITY_BLOCKED"),
        _admission(root="F:\\other-checkout", reason="SOURCE_AUTHORITY_BLOCKED"),
    ),
)
def test_source_guards_block_before_provider_or_evidence_reservation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    admission: observer._SourceAdmission,
) -> None:
    calls: list[str] = []

    def run(*args: object) -> object:
        calls.append("provider")
        raise AssertionError("provider dispatch must not start")

    events = _install_fake_harness(monkeypatch, tmp_path, run, admission=admission)
    result = asyncio.run(
        observer.RobinhoodAgentInitiatedRuntimePartitionObserver().observe(
            evidence_dir=tmp_path
            / ("arch147-agent-initiated-runtime-partition-" + "a" * 32)
        )
    )

    assert result.status is (
        observer.AgentInitiatedRuntimePartitionObservationStatus.SOURCE_AUTHORITY_BLOCKED
    )
    assert result.attempt_counters["oauth_scope_entry_attempts"] == 0
    assert result.attempt_counters["mcp_session_open_attempts"] == 0
    assert events == ["admission"]
    assert calls == []


def test_evidence_destination_reparse_or_collision_failure_blocks_before_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []

    def run(*args: object) -> object:
        calls.append("provider")
        raise AssertionError("provider dispatch must not start")

    events = _install_fake_harness(monkeypatch, tmp_path, run)
    monkeypatch.setattr(
        observer,
        "_reserve_evidence_directory",
        lambda path: (_ for _ in ()).throw(ValueError("destination rejected")),
    )
    result = asyncio.run(
        observer.RobinhoodAgentInitiatedRuntimePartitionObserver().observe(
            evidence_dir=tmp_path
            / ("arch147-agent-initiated-runtime-partition-" + "a" * 32)
        )
    )

    assert result.status is (
        observer.AgentInitiatedRuntimePartitionObservationStatus.EVIDENCE_WRITE_FAILURE
    )
    assert result.reason == "EVIDENCE_DESTINATION_REJECTED"
    assert events == ["admission", "module-origins"]
    assert calls == []


def test_valid_proof_is_called_once_validated_and_persisted_review_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    expected = _valid_proof()

    def run(*args: object) -> object:
        calls.append("proof")
        return expected

    result = _observe_with(monkeypatch, tmp_path, run)
    evidence = json.loads(result.evidence_file.read_text(encoding="ascii"))

    assert (
        result.status is observer.AgentInitiatedRuntimePartitionObservationStatus.PROVEN
    )
    assert calls == ["proof"]
    assert result.source_recheck_status == "PASS"
    assert result.production_order_scope_authority == "NOT_GRANTED"
    assert evidence["b2_result"]["status"] == "PROVEN"
    assert evidence["b2_result_status"] == "PROVEN"
    assert evidence["b2_result_reason"] == "PARTITION_EQUALITY_PROVEN"
    assert evidence["b2_evidence_sha256"] == evidence["b2_result"]["evidence_sha256"]
    assert evidence["b2_result"]["partition_equality_proof"] == "PROVEN"
    assert evidence["production_order_scope_authority"] == "NOT_GRANTED"
    serialized = result.evidence_file.read_text(encoding="ascii")
    assert _ACCOUNT not in serialized
    assert "provider-order-secret" not in serialized
    assert all(
        evidence["attempt_counters"][name] == 0
        for name in (
            "review_attempts",
            "placement_attempts",
            "cancellation_attempts",
            "other_tool_attempts",
        )
    )


def test_not_proven_is_consumed_and_preserved_without_authority(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result = _observe_with(monkeypatch, tmp_path, lambda *args: _not_proven())
    evidence = json.loads(result.evidence_file.read_text(encoding="ascii"))

    assert (
        result.status
        is observer.AgentInitiatedRuntimePartitionObservationStatus.NOT_PROVEN
    )
    assert result.reason == "ACCOUNT_READ_EXCEPTION"
    assert evidence["b2_result"]["status"] == "NOT_PROVEN"
    assert evidence["partition_equality_proof"] == "NOT_PROVEN"
    assert result.production_order_scope_authority == "NOT_GRANTED"


def test_one_use_no_retry_after_success_or_provider_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []

    def run(*args: object) -> object:
        calls.append("provider")
        raise RuntimeError("provider exception raw secret")

    _install_fake_harness(monkeypatch, tmp_path, run)
    instance = observer.RobinhoodAgentInitiatedRuntimePartitionObserver()
    first = asyncio.run(
        instance.observe(
            evidence_dir=tmp_path
            / ("arch147-agent-initiated-runtime-partition-" + "a" * 32)
        )
    )
    second = asyncio.run(
        instance.observe(
            evidence_dir=tmp_path
            / ("arch147-agent-initiated-runtime-partition-" + "b" * 32)
        )
    )

    assert (
        first.status
        is observer.AgentInitiatedRuntimePartitionObservationStatus.PROVIDER_EXCEPTION
    )
    assert first.evidence_file is not None
    assert "provider exception raw secret" not in first.evidence_file.read_text(
        encoding="ascii"
    )
    assert second.status is (
        observer.AgentInitiatedRuntimePartitionObservationStatus.OBSERVER_ATTEMPT_ALREADY_USED
    )
    assert calls == ["provider"]


def test_source_recheck_change_blocks_and_keeps_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result = _observe_with(
        monkeypatch,
        tmp_path,
        lambda *args: _valid_proof(),
        source_recheck=lambda repo_root, expected_source: False,
    )

    assert (
        result.status
        is observer.AgentInitiatedRuntimePartitionObservationStatus.BLOCKED
    )
    assert result.reason == "SOURCE_RECHECK_BLOCKED"
    assert result.evidence_file is not None
    assert (
        result.evidence_sha256
        == hashlib.sha256(result.evidence_file.read_bytes()).hexdigest()
    )


def test_malformed_result_or_evidence_hash_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    valid = _valid_proof()
    malformed = replace(
        valid,
        evidence_json=b"{}",
        evidence_sha256=hashlib.sha256(b"{}").hexdigest(),
    )
    result = _observe_with(monkeypatch, tmp_path, lambda *args: malformed)

    assert (
        result.status
        is observer.AgentInitiatedRuntimePartitionObservationStatus.MALFORMED_RESULT
    )
    assert result.reason == "PROOF_EVIDENCE_SHAPE_INVALID"


def test_wrong_logical_read_order_is_rejected_even_for_typed_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    valid = _valid_proof()
    bad_first = replace(valid.logical_reads[0], label="TRUE", agent_initiated=True)
    bad_reads = (bad_first, *valid.logical_reads[1:])
    payload = json.loads(valid.evidence_json.decode("ascii"))
    payload["logical_reads"] = [item.material() for item in bad_reads]
    raw = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    malformed = replace(
        valid,
        logical_reads=bad_reads,
        evidence_json=raw,
        evidence_sha256=hashlib.sha256(raw).hexdigest(),
    )
    result = _observe_with(monkeypatch, tmp_path, lambda *args: malformed)

    assert (
        result.status
        is observer.AgentInitiatedRuntimePartitionObservationStatus.MALFORMED_RESULT
    )
    assert result.reason == "PROOF_LOGICAL_READ_ORDER_INVALID"


def test_exact_proof_engine_is_the_only_partition_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    class _Transport:
        def __init__(self, *args: object) -> None:
            calls.append("transport")

    monkeypatch.setattr(observer, "RobinhoodB2ReadTransport", _Transport)
    monkeypatch.setattr(
        observer,
        "RobinhoodL43B2PreEffectReadAdapter",
        lambda value: calls.append(("adapter", value)) or "normalized-boundary",
    )
    monkeypatch.setattr(
        "trading_bot.robinhood_mcp.windows_oauth.create_windows_robinhood_oauth_factory",
        lambda **kwargs: lambda: object(),
    )
    monkeypatch.setattr(
        observer,
        "prove_agent_initiated_partition",
        lambda boundary, **kwargs: (
            calls.append(("proof", boundary, kwargs)) or _valid_proof()
        ),
    )

    observer._run_production_session(
        observer._AttemptCounters(),
        observer._DispatchState(),
        Path("F:/repo"),
        _SOURCE,
    )

    assert [item for item in calls if isinstance(item, tuple) and item[0] == "proof"]
    assert calls[0] == "transport"
    assert calls[1][0] == "adapter"
    assert calls[2][0] == "proof"


def test_public_observer_cannot_accept_a_caller_supplied_proof() -> None:
    assert list(
        inspect.signature(
            observer.RobinhoodAgentInitiatedRuntimePartitionObserver.observe
        ).parameters
    ) == [
        "self",
        "evidence_dir",
    ]


def test_transport_counter_contract_keeps_effects_zero() -> None:
    counters = observer._AttemptCounters().material()

    assert counters["review_attempts"] == 0
    assert counters["placement_attempts"] == 0
    assert counters["cancellation_attempts"] == 0
    assert counters["other_tool_attempts"] == 0


def test_restricted_transport_counts_only_account_and_order_reads() -> None:
    calls: list[tuple[str, str, object]] = []
    attempts = observer._AttemptCounters()
    dispatch = observer._DispatchState()
    transport = observer.RobinhoodB2ReadTransport.for_test(
        lambda: _Session(calls), attempts, dispatch
    )

    assert transport.get_accounts()["data"]["accounts"]
    assert transport.get_equity_orders({"symbol": "SPY"})["data"]["orders"] == []
    counters = attempts.material()
    assert counters["mcp_session_open_attempts"] == 2
    assert counters["tools_list_attempts"] == 2
    assert counters["tools_list_pages_received"] == 2
    assert counters["account_read_attempts"] == 1
    assert counters["order_read_attempts"] == 1
    assert counters["mcp_tool_invocation_attempts"] == 2
    assert counters["review_attempts"] == 0
    assert counters["placement_attempts"] == 0
    assert counters["cancellation_attempts"] == 0
    assert counters["other_tool_attempts"] == 0
    assert dispatch.started is True
    assert [item[1] for item in calls if item[0] == "call"] == [
        "get_accounts",
        "get_equity_orders",
    ]
