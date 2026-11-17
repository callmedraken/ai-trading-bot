from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import sys
import threading
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, datetime
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from scripts import checkpoint_runner as runner
from trading_bot.desktop_paper.robinhood_read import resolve_account
from trading_bot.live_prototype import l43_production_owner as q62_owner
from trading_bot.live_prototype.l43_production_owner import L43SourceIdentity
from trading_bot.live_prototype.l43_provider_contracts import (
    L43AccountIdentity,
)
from trading_bot.robinhood_mcp import _current_session
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

    def get_equity_orders(self, arguments: dict[str, object]) -> proof.B2OrderReadPage:
        assert arguments["symbol"] == "SPY"
        return proof.B2OrderReadPage(rows=(), next_cursor=None)


class _AccountFailure:
    def get_accounts(self) -> L43AccountIdentity:
        raise RuntimeError("raw provider error secret-token")

    def get_equity_orders(self, arguments: dict[str, object]) -> proof.B2OrderReadPage:
        raise AssertionError("account failure must stop before order reads")


class _ToolListing:
    tools = (
        SimpleNamespace(name="get_accounts"),
        SimpleNamespace(name="get_equity_orders"),
    )
    next_cursor = None


class _Session:
    def __init__(
        self,
        calls: list[tuple[str, str, object]],
        account_number: str = _ACCOUNT,
    ) -> None:
        self._calls = calls
        self._account_number = account_number

    async def __aenter__(self) -> _Session:
        self._calls.append(("open", "", None))
        return self

    async def __aexit__(self, *args: object) -> None:
        self._calls.append(("close", "", None))
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
                    "accounts": [
                        {
                            "account_number": self._account_number,
                            "agentic_allowed": True,
                        }
                    ]
                }
            }
        else:
            payload = {"data": {"orders": [], "next": None}}
        return SimpleNamespace(is_error=False, structured_content=payload)


class _ConfiguredSession(_Session):
    def __init__(
        self,
        calls: list[tuple[str, str, object]],
        listings: tuple[object, ...],
    ) -> None:
        super().__init__(calls)
        self._listings = iter(listings)

    async def list_tools(self, *, cursor: str | None = None) -> object:
        self._calls.append(("list", "", cursor))
        return next(self._listings)


def _tool_listing(*names: str, next_cursor: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        tools=tuple(SimpleNamespace(name=name) for name in names),
        next_cursor=next_cursor,
    )


def _account_fingerprint(account_number: str) -> str:
    return resolve_account(
        {
            "data": {
                "accounts": [
                    {
                        "account_number": account_number,
                        "agentic_allowed": True,
                    }
                ]
            }
        }
    ).fingerprint


def _q62_runtime_identity(account_fingerprint: object) -> q62_owner.RuntimeIdentity:
    return q62_owner.RuntimeIdentity(
        account_fingerprint=account_fingerprint,  # type: ignore[arg-type]
        source_head="1" * 40,
        source_tree="2" * 40,
        config_digest="3" * 64,
        binding_digest="4" * 64,
        lifecycle_id="00000000-0000-4000-8000-000000000001",
    )


def _q62_origin(runtime_identity: object) -> q62_owner.Q62JournalOrigin:
    return q62_owner.Q62JournalOrigin(
        runtime_identity=runtime_identity,  # type: ignore[arg-type]
        journal_label="fake-q62-origin",
        journal_sha256="5" * 64,
        initialization_event_sha256="6" * 64,
        consumed_observation_sha256="7" * 64,
    )


def _install_rhc2_source_guards(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[ModuleType, Path]:
    from scripts import arch147_rhc2_order_scope_successor_source as rhc2

    monkeypatch.setattr(rhc2, "_expected_worktree", lambda: tmp_path)
    monkeypatch.setattr(rhc2, "_module_origin_is_canonical", lambda *a, **k: True)
    monkeypatch.setattr(runner, "_arch147_rhc2_authority_check", lambda _: ())
    q62_path = tmp_path / rhc2._Q62_READER_PATH
    q62_path.parent.mkdir(parents=True, exist_ok=True)
    q62_path.write_text("# fake source path for origin guard\n", encoding="utf-8")
    canonical_find_spec = rhc2.importlib.util.find_spec

    def find_spec(name: str, *args: object, **kwargs: object) -> object:
        if name == rhc2._Q62_READER_MODULE:
            return ModuleSpec(name, loader=None, origin=str(q62_path))
        return canonical_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(rhc2.importlib.util, "find_spec", find_spec)
    return rhc2, q62_path


def _install_fake_rhc2_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[list[tuple[str, str, object]], list[dict[str, object]], list[str | None]]:
    from trading_bot.robinhood_mcp import windows_oauth

    calls: list[tuple[str, str, object]] = []
    oauth_factories: list[dict[str, object]] = []
    proof_bindings: list[str | None] = []
    monkeypatch.setattr(
        windows_oauth,
        "create_windows_robinhood_oauth_factory",
        lambda **kwargs: oauth_factories.append(kwargs) or (lambda: object()),
    )
    real_proof = proof.prove_agent_initiated_partition

    def prove_with_binding(read, **kwargs):
        proof_bindings.append(kwargs.get("expected_account_fingerprint"))
        return real_proof(read, **kwargs)

    monkeypatch.setattr(observer, "prove_agent_initiated_partition", prove_with_binding)

    def open_fake_session(
        oauth_factory, *, before_oauth, before_mcp_session
    ) -> _Session:
        del oauth_factory
        before_oauth()
        before_mcp_session()
        return _Session(calls)

    monkeypatch.setattr(observer, "_open_robinhood_client", open_fake_session)
    monkeypatch.setattr(proof, "_read_source_identity", lambda _: _SOURCE)
    monkeypatch.setattr(observer, "_EVIDENCE_ROOT", tmp_path)
    _install_fake_harness(monkeypatch, tmp_path, observer._run_production_session)
    return calls, oauth_factories, proof_bindings


def _assert_q62_blocked_before_observer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    rhc2: ModuleType,
    reader_calls: list[str],
    expected_reader_calls: list[str],
    expected_origin_events: list[str],
) -> None:
    from trading_bot.robinhood_mcp import windows_oauth

    monkeypatch.setattr(observer, "_EVIDENCE_ROOT", tmp_path)
    oauth_calls: list[str] = []
    monkeypatch.setattr(
        windows_oauth,
        "create_windows_robinhood_oauth_factory",
        lambda **kwargs: oauth_calls.append("oauth") or (lambda: object()),
    )
    constructed: list[object] = []

    class _ObserverConstructionTrap:
        def __init__(self, **kwargs: object) -> None:
            constructed.append(kwargs)
            raise AssertionError("observer construction must follow Q62 validation")

    monkeypatch.setattr(
        observer,
        "RobinhoodAgentInitiatedRuntimePartitionObserver",
        _ObserverConstructionTrap,
    )
    provider_calls: list[str] = []

    def fake_provider(*args: object) -> object:
        provider_calls.append("dispatch")
        raise AssertionError("provider dispatch must not start")

    events = _install_fake_harness(monkeypatch, tmp_path, fake_provider)
    before = tuple(sorted(path.name for path in tmp_path.iterdir()))

    result = rhc2._run_preflight()

    assert result == {
        "status": "BLOCKED",
        "reason": "Q62_ORIGIN_REJECTED",
        "disposition": "REVIEW_ONLY",
        "production_order_scope_authority": "NOT_GRANTED",
    }
    assert reader_calls == expected_reader_calls
    assert constructed == []
    assert provider_calls == []
    assert oauth_calls == []
    assert events == expected_origin_events
    assert tuple(sorted(path.name for path in tmp_path.iterdir())) == before


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
    assert instance._expected_account_fingerprint is None
    assert not hasattr(observer.RobinhoodB2ReadTransport, "get_equity_positions")
    assert not hasattr(observer.RobinhoodB2ReadTransport, "place_equity_order")


@pytest.mark.parametrize(
    "fingerprint",
    ("", "A" * 64, "g" * 64, "a" * 63, "a" * 65, 123, object()),
)
def test_observer_rejects_noncanonical_expected_account_fingerprint(
    fingerprint: object,
) -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        observer.RobinhoodAgentInitiatedRuntimePartitionObserver(
            expected_account_fingerprint=fingerprint  # type: ignore[arg-type]
        )


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


@pytest.mark.parametrize(
    ("failure_kind", "expected_reason"),
    (
        ("dispatch", proof.B2FailureReason.TRANSPORT_TOOL_DISPATCH_FAILURE),
        ("result", proof.B2FailureReason.PROVIDER_RESULT_ENVELOPE_FAILURE),
        ("normalization", proof.B2FailureReason.AGENT_INITIATED_STRICT_BOOL_FAILURE),
    ),
)
def test_closed_failure_classes_reach_sanitized_observer_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure_kind: str,
    expected_reason: proof.B2FailureReason,
) -> None:
    real_run = observer._run_production_session
    real_transport = observer.RobinhoodB2ReadTransport

    class _FailureSession:
        async def __aenter__(self) -> _FailureSession:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def list_tools(self, *, cursor: str | None = None) -> _ToolListing:
            del cursor
            return _ToolListing()

        async def call_tool(
            self, name: str, arguments: dict[str, object]
        ) -> SimpleNamespace:
            del arguments
            if name == "get_accounts":
                return SimpleNamespace(
                    is_error=False,
                    structured_content={
                        "data": {
                            "accounts": [
                                {
                                    "account_number": _ACCOUNT,
                                    "agentic_allowed": True,
                                }
                            ]
                        }
                    },
                )
            if failure_kind == "dispatch":
                raise RuntimeError("raw dispatch secret-token")
            if failure_kind == "result":
                return SimpleNamespace(
                    is_error=True,
                    structured_content={"raw": "provider-result-secret"},
                )
            return SimpleNamespace(
                is_error=False,
                structured_content={
                    "data": {
                        "orders": [
                            {
                                "id": "provider-order-secret",
                                "symbol": "SPY",
                            }
                        ],
                        "next": None,
                    }
                },
            )

    monkeypatch.setattr(
        observer,
        "RobinhoodB2ReadTransport",
        lambda _oauth, attempts, dispatch: real_transport.for_test(
            _FailureSession, attempts, dispatch
        ),
    )
    monkeypatch.setattr(
        "trading_bot.robinhood_mcp.windows_oauth.create_windows_robinhood_oauth_factory",
        lambda **_kwargs: lambda: None,
    )
    monkeypatch.setattr(proof, "_read_source_identity", lambda _root: _SOURCE)

    def run(*args: object) -> object:
        return real_run(*args)

    _install_fake_harness(monkeypatch, tmp_path, run)
    result = asyncio.run(
        observer.RobinhoodAgentInitiatedRuntimePartitionObserver().observe(
            evidence_dir=tmp_path
            / ("arch147-agent-initiated-runtime-partition-" + "c" * 32)
        )
    )
    assert result.evidence_file is not None
    evidence_text = result.evidence_file.read_text(encoding="ascii")
    evidence = json.loads(evidence_text)

    assert result.reason == expected_reason.value
    assert evidence["reason"] == expected_reason.value
    assert evidence["b2_result_reason"] == expected_reason.value
    assert evidence["b2_proof_contract_version"] == proof.B2_PROOF_CONTRACT_VERSION
    assert _ACCOUNT not in evidence_text
    assert "secret-token" not in evidence_text
    assert "provider-result-secret" not in evidence_text
    assert "provider-order-secret" not in evidence_text
    assert "raw dispatch" not in evidence_text
    assert result.provider_dispatch_started is True


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


def test_outer_cancellation_waits_for_proof_worker_cleanup_before_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started = threading.Event()
    release = threading.Event()
    closed = threading.Event()

    def run(*args: object) -> object:
        del args
        started.set()
        try:
            if not release.wait(timeout=5):
                raise TimeoutError("fake proof worker timed out")
            return _valid_proof()
        finally:
            closed.set()

    _install_fake_harness(monkeypatch, tmp_path, run)
    instance = observer.RobinhoodAgentInitiatedRuntimePartitionObserver()
    evidence_dir = tmp_path / ("arch147-agent-initiated-runtime-partition-" + "d" * 32)
    evidence_file = evidence_dir / "evidence.json"

    async def cancel_and_drain():
        task = asyncio.create_task(instance.observe(evidence_dir=evidence_dir))
        while not started.is_set():
            await asyncio.sleep(0.001)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert not evidence_file.exists()
        release.set()
        return await task

    result = asyncio.run(cancel_and_drain())

    assert closed.is_set()
    assert (
        result.status
        is observer.AgentInitiatedRuntimePartitionObservationStatus.PROVIDER_EXCEPTION
    )
    assert result.reason == "PROVIDER_EXCEPTION"
    assert result.evidence_file == evidence_file
    evidence = json.loads(evidence_file.read_text(encoding="ascii"))
    assert evidence["status"] == "PROVIDER_EXCEPTION"


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

        def __enter__(self):
            calls.append("scope-enter")
            return self

        def __exit__(self, *_args: object) -> bool:
            calls.append("scope-exit")
            return False

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
    assert [item if isinstance(item, str) else item[0] for item in calls] == [
        "transport",
        "adapter",
        "scope-enter",
        "proof",
        "scope-exit",
    ]
    assert calls[3][1] == "normalized-boundary"
    assert calls[3][2]["expected_account_fingerprint"] is None


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


def test_b2_transport_construction_is_inert() -> None:
    oauth_calls: list[str] = []
    attempts = observer._AttemptCounters()
    transport = observer.RobinhoodB2ReadTransport(
        lambda: oauth_calls.append("oauth") or object(),
        attempts,
        observer._DispatchState(),
    )

    assert oauth_calls == []
    assert attempts.material() == observer._AttemptCounters().material()
    assert transport._session.in_scope is False


def test_b2_source_origin_guard_binds_current_session_owner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo_root = Path(observer.__file__).resolve().parents[3]
    monkeypatch.setattr(observer, "_CANONICAL_WORKTREE", repo_root)

    assert observer._module_origins_are_source_owned(repo_root=repo_root)

    foreign_module = tmp_path / "foreign_current_session.py"
    foreign_module.write_text("# not the selected worktree\n", encoding="ascii")
    monkeypatch.setattr(_current_session, "__file__", str(foreign_module))

    assert not observer._module_origins_are_source_owned(repo_root=repo_root)


def test_restricted_transport_counts_only_account_and_order_reads() -> None:
    calls: list[tuple[str, str, object]] = []
    attempts = observer._AttemptCounters()
    dispatch = observer._DispatchState()
    transport = observer.RobinhoodB2ReadTransport.for_test(
        lambda: _Session(calls), attempts, dispatch
    )
    assert not hasattr(transport, "call_tool")

    with transport:
        assert transport.get_accounts()["data"]["accounts"]
        assert transport.get_equity_orders({"symbol": "SPY"})["data"]["orders"] == []
    counters = attempts.material()
    assert counters["mcp_session_open_attempts"] == 1
    assert counters["tools_list_attempts"] == 1
    assert counters["tools_list_pages_received"] == 1
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
    assert [item[0] for item in calls if item[0] in {"open", "close"}] == [
        "open",
        "close",
    ]


def test_b2_missing_capability_fails_before_dispatch_and_closes_session() -> None:
    calls: list[tuple[str, str, object]] = []
    attempts = observer._AttemptCounters()
    transport = observer.RobinhoodB2ReadTransport.for_test(
        lambda: _ConfiguredSession(
            calls,
            (_tool_listing("get_accounts"),),
        ),
        attempts,
        observer._DispatchState(),
    )

    with pytest.raises(observer._B2ReadError) as error:
        with transport:
            transport.get_accounts()

    assert error.value.reason is proof.B2FailureReason.PROVIDER_RESULT_ENVELOPE_FAILURE
    assert attempts.mcp_session_open_attempts == 1
    assert attempts.tools_list_attempts == attempts.tools_list_pages_received == 1
    assert attempts.mcp_tool_invocation_attempts == 0
    assert [item[0] for item in calls if item[0] in {"open", "close"}] == [
        "open",
        "close",
    ]


def test_b2_repeated_discovery_cursor_fails_closed_and_closes_session() -> None:
    calls: list[tuple[str, str, object]] = []
    attempts = observer._AttemptCounters()
    transport = observer.RobinhoodB2ReadTransport.for_test(
        lambda: _ConfiguredSession(
            calls,
            (
                _tool_listing("get_accounts", next_cursor="repeat"),
                _tool_listing("get_equity_orders", next_cursor="repeat"),
            ),
        ),
        attempts,
        observer._DispatchState(),
    )

    with pytest.raises(observer._B2ReadError) as error:
        with transport:
            transport.get_accounts()

    assert (
        error.value.reason is proof.B2FailureReason.PAGINATION_ENVELOPE_CURSOR_FAILURE
    )
    assert attempts.mcp_session_open_attempts == 1
    assert attempts.tools_list_attempts == attempts.tools_list_pages_received == 2
    assert attempts.mcp_tool_invocation_attempts == 0
    assert [item[0] for item in calls if item[0] in {"open", "close"}] == [
        "open",
        "close",
    ]


def test_b2_discovery_state_does_not_carry_to_the_next_session() -> None:
    calls: list[tuple[str, str, object]] = []
    attempts = observer._AttemptCounters()
    sessions = iter(
        (
            (_tool_listing("get_accounts", "get_equity_orders"),),
            (_tool_listing("get_accounts"),),
        )
    )
    transport = observer.RobinhoodB2ReadTransport.for_test(
        lambda: _ConfiguredSession(calls, next(sessions)),
        attempts,
        observer._DispatchState(),
    )

    with transport:
        assert transport.get_accounts()["data"]["accounts"]

    with pytest.raises(observer._B2ReadError) as error:
        with transport:
            transport.get_accounts()

    assert error.value.reason is proof.B2FailureReason.PROVIDER_RESULT_ENVELOPE_FAILURE
    assert attempts.mcp_session_open_attempts == 2
    assert attempts.tools_list_attempts == attempts.tools_list_pages_received == 2
    assert attempts.account_read_attempts == 1
    assert attempts.mcp_tool_invocation_attempts == 1
    assert [item[0] for item in calls if item[0] in {"open", "close"}] == [
        "open",
        "close",
        "open",
        "close",
    ]


def test_b2_nested_scope_fails_without_corrupting_the_outer_scope() -> None:
    calls: list[tuple[str, str, object]] = []
    attempts = observer._AttemptCounters()
    transport = observer.RobinhoodB2ReadTransport.for_test(
        lambda: _Session(calls),
        attempts,
        observer._DispatchState(),
    )

    with transport:
        with pytest.raises(observer._B2ReadError):
            with transport:
                pytest.fail("nested scope should not enter")
        assert transport.get_accounts()["data"]["accounts"]

    assert attempts.mcp_session_open_attempts == 1
    assert attempts.account_read_attempts == 1
    assert [item[0] for item in calls if item[0] in {"open", "close"}] == [
        "open",
        "close",
    ]


def test_b2_dispatch_rejects_an_already_running_event_loop() -> None:
    calls: list[tuple[str, str, object]] = []
    attempts = observer._AttemptCounters()
    transport = observer.RobinhoodB2ReadTransport.for_test(
        lambda: _Session(calls),
        attempts,
        observer._DispatchState(),
    )

    async def inside_loop() -> None:
        with pytest.raises(observer._B2ReadError):
            transport.get_accounts()

    asyncio.run(inside_loop())

    assert attempts.mcp_session_open_attempts == 0
    assert attempts.tools_list_attempts == 0
    assert attempts.mcp_tool_invocation_attempts == 0
    assert calls == []


def test_b2_cleanup_failure_is_sanitized_after_successful_read() -> None:
    calls: list[tuple[str, str, object]] = []
    attempts = observer._AttemptCounters()

    class _CleanupFailureSession(_Session):
        async def __aexit__(self, *args: object) -> None:
            self._calls.append(("close", "", None))
            raise RuntimeError("raw cleanup secret-token")

    transport = observer.RobinhoodB2ReadTransport.for_test(
        lambda: _CleanupFailureSession(calls),
        attempts,
        observer._DispatchState(),
    )

    with pytest.raises(observer._B2ReadError) as error:
        with transport:
            assert transport.get_accounts()["data"]["accounts"]

    assert error.value.reason is proof.B2FailureReason.TRANSPORT_TOOL_DISPATCH_FAILURE
    assert "secret-token" not in str(error.value)
    assert attempts.account_read_attempts == attempts.mcp_tool_invocation_attempts == 1
    assert calls[-1][0] == "close"


@pytest.mark.parametrize("paginate_orders", (False, True))
def test_b2_proof_uses_one_fake_sdk_session_and_complete_discovery(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    paginate_orders: bool,
) -> None:
    events: list[tuple[str, object]] = []
    rows = (
        {"id": "order-true", "symbol": "SPY", "agent_initiated": True},
        {"id": "order-false", "symbol": "SPY", "agent_initiated": False},
    )
    all_order_reads = 0

    class _ProviderClient:
        async def list_tools(self, *, cursor: str | None = None) -> object:
            events.append(("tools-list", cursor))
            if cursor is None:
                return _tool_listing(
                    "get_accounts",
                    "place_equity_order",
                    next_cursor="tools-page-2",
                )
            return _tool_listing("get_equity_orders", "cancel_equity_order")

        async def call_tool(
            self, name: str, arguments: dict[str, object]
        ) -> SimpleNamespace:
            nonlocal all_order_reads
            events.append(("tool-call", (id(self), name, dict(arguments))))
            if name == "get_accounts":
                payload = {
                    "data": {
                        "accounts": [
                            {
                                "account_number": _ACCOUNT,
                                "agentic_allowed": True,
                            }
                        ]
                    }
                }
            else:
                partition = arguments.get("agent_initiated")
                next_cursor = None
                if partition is None:
                    if arguments.get("cursor") is None:
                        all_order_reads += 1
                    if paginate_orders and all_order_reads == 1:
                        if arguments.get("cursor") is None:
                            selected = list(rows[:1])
                            next_cursor = "orders-page-2"
                        else:
                            selected = list(rows[1:])
                    else:
                        selected = list(rows)
                else:
                    selected = list(
                        row for row in rows if row["agent_initiated"] is partition
                    )
                payload = {"data": {"orders": selected, "next": next_cursor}}
            return SimpleNamespace(is_error=False, structured_content=payload)

    client = _ProviderClient()

    class _HttpClient:
        def __init__(self, *, auth: object, timeout: int) -> None:
            assert timeout == 60
            events.append(("http-client-init", auth))

        async def __aenter__(self) -> _HttpClient:
            events.append(("http-client-open", None))
            return self

        async def __aexit__(self, *_args: object) -> None:
            events.append(("http-client-close", None))

    class _StreamContext:
        async def __aenter__(self) -> _ProviderClient:
            events.append(("mcp-stream-open", None))
            return client

        async def __aexit__(self, *_args: object) -> None:
            events.append(("mcp-stream-close", None))

    class _MCPClientContext:
        def __init__(self, stream: _StreamContext) -> None:
            self._stream = stream

        async def __aenter__(self) -> _ProviderClient:
            result = await self._stream.__aenter__()
            events.append(("mcp-client-open", None))
            return result

        async def __aexit__(self, *args: object) -> None:
            events.append(("mcp-client-close", None))
            await self._stream.__aexit__(*args)

    httpx2_module = ModuleType("httpx2")
    httpx2_module.AsyncClient = _HttpClient
    mcp_module = ModuleType("mcp")
    mcp_module.Client = _MCPClientContext
    mcp_client_module = ModuleType("mcp.client")
    mcp_client_module.__path__ = []
    mcp_stream_module = ModuleType("mcp.client.streamable_http")
    mcp_stream_module.streamable_http_client = lambda url, *, http_client: (
        events.append(("stream-url", url)) or _StreamContext()
    )
    monkeypatch.setitem(sys.modules, "httpx2", httpx2_module)
    monkeypatch.setitem(sys.modules, "mcp", mcp_module)
    monkeypatch.setitem(sys.modules, "mcp.client", mcp_client_module)
    monkeypatch.setitem(sys.modules, "mcp.client.streamable_http", mcp_stream_module)
    oauth_builds: list[dict[str, object]] = []
    oauth_entries: list[str] = []
    from trading_bot.robinhood_mcp import windows_oauth

    monkeypatch.setattr(
        windows_oauth,
        "create_windows_robinhood_oauth_factory",
        lambda **kwargs: (
            oauth_builds.append(kwargs)
            or (lambda: oauth_entries.append("entered") or object())
        ),
    )
    monkeypatch.setattr(proof, "_read_source_identity", lambda _root: _SOURCE)
    attempts = observer._AttemptCounters()
    dispatch = observer._DispatchState()

    result = observer._run_production_session(
        attempts,
        dispatch,
        tmp_path,
        _SOURCE,
    )

    assert result.status is proof.AgentInitiatedRuntimePartitionProofStatus.PROVEN, (
        result.reason
    )
    assert len(oauth_builds) == 1
    assert oauth_builds[0]["redirect_uri"] == observer._REDIRECT_URI
    assert callable(oauth_builds[0]["browser_opener"])
    assert len(oauth_entries) == 1
    counters = attempts.material()
    assert counters["oauth_scope_entry_attempts"] == 1
    assert counters["mcp_session_open_attempts"] == 1
    assert counters["tools_list_attempts"] == counters["tools_list_pages_received"] == 2
    assert counters["account_read_attempts"] == 1
    assert counters["order_read_attempts"] == 4 + int(paginate_orders)
    assert counters["mcp_tool_invocation_attempts"] == 5 + int(paginate_orders)
    assert counters["review_attempts"] == 0
    assert counters["placement_attempts"] == 0
    assert counters["cancellation_attempts"] == 0
    assert counters["other_tool_attempts"] == 0
    assert dispatch.started is True
    assert [name for name, _ in events].count("http-client-open") == 1
    assert [name for name, _ in events].count("mcp-client-open") == 1
    assert [name for name, _ in events].count("mcp-client-close") == 1
    assert [name for name, _ in events].count("http-client-close") == 1
    calls = [value for name, value in events if name == "tool-call"]
    assert [item[1] for item in calls] == [
        "get_accounts",
        "get_equity_orders",
        *(["get_equity_orders"] if paginate_orders else []),
        "get_equity_orders",
        "get_equity_orders",
        "get_equity_orders",
    ]
    assert len({item[0] for item in calls}) == 1
    if paginate_orders:
        assert calls[2][2]["cursor"] == "orders-page-2"


def test_rhc2_wrapper_dispatches_the_b2_proof_through_one_fake_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_rhc2_source_guards(monkeypatch, tmp_path)
    expected_fingerprint = _account_fingerprint(_ACCOUNT)
    monkeypatch.setattr(
        q62_owner,
        "read_canonical_q62_origin",
        lambda: _q62_origin(_q62_runtime_identity(expected_fingerprint)),
    )
    calls, oauth_factories, proof_bindings = _install_fake_rhc2_session(
        monkeypatch, tmp_path
    )
    result = runner._arch147_rhc2_preflight()

    assert result["status"] == "PASS"
    assert result["disposition"] == "REVIEW_ONLY"
    assert result["production_order_scope_authority"] == "NOT_GRANTED"
    assert result["provider_dispatch_started"] is True
    assert len(oauth_factories) == 1
    assert result["attempt_counters"]["oauth_scope_entry_attempts"] == 1
    assert result["attempt_counters"]["mcp_session_open_attempts"] == 1
    assert result["attempt_counters"]["tools_list_attempts"] == 1
    assert result["attempt_counters"]["account_read_attempts"] == 1
    assert result["attempt_counters"]["order_read_attempts"] == 4
    assert result["attempt_counters"]["review_attempts"] == 0
    assert result["attempt_counters"]["placement_attempts"] == 0
    assert result["attempt_counters"]["cancellation_attempts"] == 0
    assert proof_bindings == [expected_fingerprint]
    assert "provider_effects" not in result
    assert [item[0] for item in calls if item[0] in {"open", "close"}] == [
        "open",
        "close",
    ]
    assert [item[0] for item in calls if item[0] == "list"] == ["list"]
    assert [item[1] for item in calls if item[0] == "call"] == [
        "get_accounts",
        "get_equity_orders",
        "get_equity_orders",
        "get_equity_orders",
        "get_equity_orders",
    ]


def test_rhc2_q62_account_mismatch_stops_after_one_account_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_rhc2_source_guards(monkeypatch, tmp_path)
    expected_fingerprint = _account_fingerprint("different-fake-account")
    monkeypatch.setattr(
        q62_owner,
        "read_canonical_q62_origin",
        lambda: _q62_origin(_q62_runtime_identity(expected_fingerprint)),
    )
    calls, oauth_factories, proof_bindings = _install_fake_rhc2_session(
        monkeypatch, tmp_path
    )

    result = runner._arch147_rhc2_preflight()

    assert result["status"] == "BLOCKED"
    assert result["observer_status"] == "NOT_PROVEN"
    assert result["reason"] == proof.B2FailureReason.ACCOUNT_MISMATCH.value
    assert result["disposition"] == "REVIEW_ONLY"
    assert result["production_order_scope_authority"] == "NOT_GRANTED"
    assert result["observer_evidence_path"] is not None
    assert result["observer_evidence_sha256"] is not None
    evidence_text = Path(result["observer_evidence_path"]).read_text(encoding="ascii")
    evidence = json.loads(evidence_text)
    assert evidence["b2_result_reason"] == proof.B2FailureReason.ACCOUNT_MISMATCH.value
    assert _ACCOUNT not in evidence_text
    assert proof_bindings == [expected_fingerprint]
    assert len(oauth_factories) == 1
    assert result["attempt_counters"]["oauth_scope_entry_attempts"] == 1
    assert result["attempt_counters"]["mcp_session_open_attempts"] == 1
    assert result["attempt_counters"]["account_read_attempts"] == 1
    assert result["attempt_counters"]["order_read_attempts"] == 0
    assert result["attempt_counters"]["review_attempts"] == 0
    assert result["attempt_counters"]["placement_attempts"] == 0
    assert result["attempt_counters"]["cancellation_attempts"] == 0
    assert [item[1] for item in calls if item[0] == "call"] == ["get_accounts"]


@pytest.mark.parametrize(
    "invalid_origin",
    ("reader_exception", "origin_type", "identity_type", "fingerprint"),
)
def test_rhc2_rejects_q62_origin_before_observer_or_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    invalid_origin: str,
) -> None:
    rhc2, _ = _install_rhc2_source_guards(monkeypatch, tmp_path)

    def reader_exception():
        raise RuntimeError("private Q62 journal details")

    def wrong_origin_type():
        return object()

    def wrong_identity_type():
        return _q62_origin(object())

    def wrong_fingerprint():
        identity = _q62_runtime_identity("8" * 64)
        object.__setattr__(identity, "account_fingerprint", "not-a-fingerprint")
        return _q62_origin(identity)

    read_origin = {
        "reader_exception": reader_exception,
        "origin_type": wrong_origin_type,
        "identity_type": wrong_identity_type,
        "fingerprint": wrong_fingerprint,
    }[invalid_origin]
    reader_calls: list[str] = []

    def record_read():
        reader_calls.append("read")
        return read_origin()

    monkeypatch.setattr(q62_owner, "read_canonical_q62_origin", record_read)
    _assert_q62_blocked_before_observer(
        monkeypatch,
        tmp_path,
        rhc2,
        reader_calls,
        ["read"],
        ["module-origins"],
    )


@pytest.mark.parametrize(
    "foreign_stage", ("module_spec", "invalid_spec", "loaded_module")
)
def test_rhc2_rejects_foreign_q62_reader_origin_before_read_or_observer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    foreign_stage: str,
) -> None:
    rhc2, _ = _install_rhc2_source_guards(monkeypatch, tmp_path)
    foreign_path = tmp_path / "foreign_q62_reader.py"
    foreign_path.write_text("# foreign fake source\n", encoding="utf-8")
    if foreign_stage == "module_spec":
        monkeypatch.setattr(
            rhc2.importlib.util,
            "find_spec",
            lambda name, *args, **kwargs: (
                ModuleSpec(name, loader=None, origin=str(foreign_path))
                if name == rhc2._Q62_READER_MODULE
                else None
            ),
        )
    elif foreign_stage == "invalid_spec":
        monkeypatch.setattr(
            rhc2.importlib.util,
            "find_spec",
            lambda name, *args, **kwargs: (
                SimpleNamespace() if name == rhc2._Q62_READER_MODULE else None
            ),
        )
    else:

        def origin_check(module, *, repo_root: Path, relative_path: str) -> bool:
            del repo_root, relative_path
            return module is not q62_owner

        monkeypatch.setattr(rhc2, "_module_origin_is_canonical", origin_check)
    reader_calls: list[str] = []
    monkeypatch.setattr(
        q62_owner,
        "read_canonical_q62_origin",
        lambda: (
            reader_calls.append("read") or _q62_origin(_q62_runtime_identity("8" * 64))
        ),
    )
    _assert_q62_blocked_before_observer(
        monkeypatch,
        tmp_path,
        rhc2,
        reader_calls,
        [],
        [] if foreign_stage in {"module_spec", "invalid_spec"} else ["module-origins"],
    )


def test_rhc2_wrapper_rejects_origin_or_registration_before_observer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts import arch147_rhc2_order_scope_successor_source as rhc2

    monkeypatch.setattr(rhc2, "_expected_worktree", lambda: tmp_path)
    monkeypatch.setattr(rhc2, "_module_origin_is_canonical", lambda *a, **k: False)
    authority_calls: list[Path] = []
    monkeypatch.setattr(
        runner,
        "_arch147_rhc2_authority_check",
        lambda root: authority_calls.append(root) or (),
    )
    result = rhc2._run_preflight()
    assert result["reason"] == "SOURCE_MODULE_ORIGIN_REJECTED"
    assert result["production_order_scope_authority"] == "NOT_GRANTED"
    assert authority_calls == []

    monkeypatch.setattr(rhc2, "_module_origin_is_canonical", lambda *a, **k: True)
    monkeypatch.setattr(
        runner,
        "_arch147_rhc2_authority_check",
        lambda root: authority_calls.append(root) or ("registration drift",),
    )
    observer_origin_calls: list[Path] = []
    monkeypatch.setattr(
        observer,
        "_module_origins_are_source_owned",
        lambda *, repo_root: observer_origin_calls.append(repo_root) or True,
    )
    result = rhc2._run_preflight()
    assert result["reason"] == "CHECKPOINT_REGISTRATION_REJECTED"
    assert result["production_order_scope_authority"] == "NOT_GRANTED"
    assert authority_calls == [tmp_path]
    assert observer_origin_calls == []


def test_rhc2_wrapper_keeps_negative_evidence_review_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rhc2, _ = _install_rhc2_source_guards(monkeypatch, tmp_path)

    monkeypatch.setattr(
        q62_owner,
        "read_canonical_q62_origin",
        lambda: _q62_origin(_q62_runtime_identity("8" * 64)),
    )
    monkeypatch.setattr(observer, "_EVIDENCE_ROOT", tmp_path)
    _install_fake_harness(monkeypatch, tmp_path, lambda *_: _not_proven())

    result = rhc2._run_preflight()

    assert result["status"] == "BLOCKED"
    assert result["observer_status"] == "NOT_PROVEN"
    assert result["disposition"] == "REVIEW_ONLY"
    assert result["observer_evidence_path"] is not None
    assert result["observer_evidence_sha256"] is not None
    assert result["source_recheck_status"] == "PASS"
    assert result["production_order_scope_authority"] == "NOT_GRANTED"


def test_rhc2_wrapper_sanitizes_observer_failure_without_effect_claims(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rhc2, _ = _install_rhc2_source_guards(monkeypatch, tmp_path)

    monkeypatch.setattr(observer, "_module_origins_are_source_owned", lambda **_: True)
    monkeypatch.setattr(
        q62_owner,
        "read_canonical_q62_origin",
        lambda: _q62_origin(_q62_runtime_identity("8" * 64)),
    )

    class _FailingObserver:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        async def observe(self, *, evidence_dir: Path) -> object:
            del evidence_dir
            raise RuntimeError("private-token must not escape")

    monkeypatch.setattr(
        observer, "RobinhoodAgentInitiatedRuntimePartitionObserver", _FailingObserver
    )
    result = rhc2._run_preflight()

    assert result == {
        "status": "BLOCKED",
        "reason": "OBSERVER_EXCEPTION",
        "disposition": "REVIEW_ONLY",
        "production_order_scope_authority": "NOT_GRANTED",
    }
    assert "private-token" not in repr(result)
    assert "provider_effects" not in result


def test_rhc2_wrapper_preserves_existing_evidence_on_uuid_collision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rhc2, _ = _install_rhc2_source_guards(monkeypatch, tmp_path)

    token = "d" * 32
    evidence_dir = tmp_path / ("arch147-agent-initiated-runtime-partition-" + token)
    evidence_dir.mkdir()
    sentinel = evidence_dir / "evidence.json"
    sentinel.write_bytes(b"old-path-sentinel\n")
    monkeypatch.setattr(rhc2, "uuid4", lambda: SimpleNamespace(hex=token))
    monkeypatch.setattr(
        q62_owner,
        "read_canonical_q62_origin",
        lambda: _q62_origin(_q62_runtime_identity("8" * 64)),
    )
    monkeypatch.setattr(observer, "_EVIDENCE_ROOT", tmp_path)
    provider_calls: list[str] = []
    _install_fake_harness(
        monkeypatch,
        tmp_path,
        lambda *_: provider_calls.append("dispatched"),
    )

    result = rhc2._run_preflight()

    assert result["status"] == "BLOCKED"
    assert result["observer_status"] == "EVIDENCE_WRITE_FAILURE"
    assert result["observer_evidence_path"] is None
    assert result["production_order_scope_authority"] == "NOT_GRANTED"
    assert sentinel.read_bytes() == b"old-path-sentinel\n"
    assert provider_calls == []
