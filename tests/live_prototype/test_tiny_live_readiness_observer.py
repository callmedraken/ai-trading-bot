"""Fake-only tests for the source-owned Architecture 147 Q62 observer."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.desktop_paper.robinhood_read import AgenticAccountIdentity
from trading_bot.live_prototype import tiny_live_readiness_observer as observer
from trading_bot.live_prototype.alpaca_runtime_signal_provider import (
    RuntimeSignalReason,
    RuntimeSignalSnapshot,
)
from trading_bot.live_prototype.capability_observer import (
    CapabilityReport,
    classify_capabilities,
)
from trading_bot.live_prototype.configuration import CompletedSignalInputs
from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle
from trading_bot.live_prototype.durable_state import (
    DurableState,
    DurableStateStore,
    IntentKind,
    IntentStatus,
    OrderState,
    RuntimeIdentity,
)
from trading_bot.live_prototype.readiness_contracts import (
    ProofKind,
    ProofStatus,
    Q62Blocker,
    ReadinessIdentity,
)
from trading_bot.live_prototype.readiness_operator import Q62Status
from trading_bot.live_prototype.recovery_operator import (
    RecoveryObservation,
    RecoveryStatus,
    reconcile_read_only,
)
from trading_bot.live_prototype.tiny_live_readiness_operator import (
    TinyLiveReadinessStatus,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)

_NOW = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
_ACCOUNT_NUMBER = "912345678901"
_ACCOUNT = AgenticAccountIdentity(_ACCOUNT_NUMBER, 1)
_ACCOUNT_REPORT = replace(
    classify_capabilities(None), account_fingerprint=_ACCOUNT.fingerprint
)
_SOURCE = observer._SourceAdmission(
    observer.FEATURE_BRANCH,
    "a" * 40,
    "b" * 40,
    "a" * 40,
    "b" * 40,
    "a" * 40,
    "b" * 40,
    "PASS",
    "PASS",
)


@dataclass(frozen=True)
class _Composite:
    capability_report: CapabilityReport


@dataclass(frozen=True)
class _Admission:
    capability_report: CapabilityReport
    admission_digest: str = "d" * 64
    consumed_l41_sha256: str = "c" * 64
    consumed_l41r5_sha256: str = "e" * 64


class _FakeReadBoundary:
    def __init__(
        self,
        *,
        positions: list[object] | None = None,
        orders: list[object] | None = None,
    ) -> None:
        self.positions = [] if positions is None else positions
        self.orders = [] if orders is None else orders
        self.calls: list[str] = []
        self.arguments: list[tuple[str, dict[str, object]]] = []

    def get_accounts(self):
        self.calls.append("get_accounts")
        return {"data": {"accounts": []}}

    def get_equity_positions(self, arguments):
        self.calls.append("get_equity_positions")
        self.arguments.append(("get_equity_positions", dict(arguments)))
        return {"data": {"positions": self.positions, "next": None}}

    def get_equity_orders(self, arguments):
        self.calls.append("get_equity_orders")
        self.arguments.append(("get_equity_orders", dict(arguments)))
        return {"data": {"orders": self.orders, "next": None}}


class _FakeSignalProvider:
    def __init__(self, snapshot: RuntimeSignalSnapshot) -> None:
        self.value = snapshot
        self.calls = 0

    def snapshot(self, _as_of: datetime) -> RuntimeSignalSnapshot:
        self.calls += 1
        return self.value


def _weekday_sessions() -> tuple[date, ...]:
    values = []
    current = date(2026, 11, 9)
    while len(values) < 60:
        if current.weekday() < 5:
            values.append(current)
        current -= timedelta(days=1)
    return tuple(reversed(values))


def _signal_inputs() -> CompletedSignalInputs:
    sessions = _weekday_sessions()
    return CompletedSignalInputs(
        symbol="SPY",
        selected_sessions=sessions,
        sessions=sessions,
        closes=tuple(Decimal("100") for _ in sessions),
        price_basis="ALPACA_ALL_ADJUSTED_PRICE_V1",
        source_digest="f" * 64,
        as_of=_NOW,
        cutoff=datetime(2026, 11, 9, 21, 0, tzinfo=UTC),
    )


def _runtime_identity(
    account_fingerprint: str = _ACCOUNT.fingerprint,
    source: observer._SourceAdmission = _SOURCE,
) -> RuntimeIdentity:
    return observer._runtime_identity(
        account_fingerprint=account_fingerprint, source=source
    )


def _make_initial_state(path: Path) -> None:
    DurableStateStore.create(path, _runtime_identity(), initial_position=Decimal("0"))


def _make_evidence_destination(root: Path) -> Path:
    destination = root / "attempt"
    destination.mkdir()
    return destination


def _install_observation_fakes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    account: AgenticAccountIdentity = _ACCOUNT,
    positions: list[object] | None = None,
    orders: list[object] | None = None,
    signal_failure: bool = False,
    write_failure: bool = False,
) -> tuple[observer._Dependencies, _FakeReadBoundary, _FakeSignalProvider | None]:
    state_file = tmp_path / "durable-state.jsonl"
    _make_initial_state(state_file)
    evidence_root = tmp_path / "evidence-root"
    evidence_root.mkdir()
    monkeypatch.setattr(observer, "EVIDENCE_ROOT", evidence_root)
    monkeypatch.setattr(
        observer,
        "_validate_state_root",
        lambda _root, *, require_absent: state_file,
    )
    monkeypatch.setattr(observer, "resolve_account", lambda _payload: account)

    fake_l41 = b"fake accepted L41"
    fake_l41r5 = b"fake accepted L41R5"
    monkeypatch.setattr(observer, "CONSUMED_L41_EVIDENCE_BYTES", len(fake_l41))
    monkeypatch.setattr(
        observer, "CONSUMED_L41_EVIDENCE_SHA256", hashlib.sha256(fake_l41).hexdigest()
    )
    monkeypatch.setattr(observer, "CONSUMED_L41R5_EVIDENCE_BYTES", len(fake_l41r5))
    monkeypatch.setattr(
        observer,
        "CONSUMED_L41R5_EVIDENCE_SHA256",
        hashlib.sha256(fake_l41r5).hexdigest(),
    )
    composite_type = _Composite
    admission_type = _Admission
    retained = replace(_ACCOUNT_REPORT, account_fingerprint=_ACCOUNT.fingerprint)
    composite = composite_type(retained)
    monkeypatch.setattr(observer, "L41R6CompositeReport", composite_type)
    monkeypatch.setattr(
        observer, "TinyLivePrototypeCapabilityAdmission", admission_type
    )
    monkeypatch.setattr(
        observer,
        "admit_tiny_live_capabilities",
        lambda _composite, **_kwargs: admission_type(retained),
    )

    boundary = _FakeReadBoundary(positions=positions, orders=orders)
    signal_inputs = _signal_inputs()
    signal_snapshot = RuntimeSignalSnapshot(
        status="READY",
        reason=RuntimeSignalReason.READY,
        observation_as_of=_NOW,
        selected_sessions=signal_inputs.selected_sessions,
        display_inputs=signal_inputs,
        stale=False,
        refreshed=True,
        credential_read_count=1,
        provider_call_count=1,
    )
    signal_provider = _FakeSignalProvider(signal_snapshot)
    provider_builds: list[str] = []
    failed_providers: list[object] = []

    def robinhood_builder(_ledger):
        return boundary

    def alpaca_builder(_ledger):
        provider_builds.append("constructed")
        if signal_failure:

            class FailedProvider:
                calls = 0

                def snapshot(self, _as_of):
                    self.calls += 1
                    raise RuntimeError("provider text containing secret")

            failed = FailedProvider()
            failed_providers.append(failed)
            return failed
        return signal_provider

    monkeypatch.setattr(
        observer, "_provider_builds_for_test", provider_builds, raising=False
    )
    monkeypatch.setattr(
        observer, "_failed_providers_for_test", failed_providers, raising=False
    )
    monkeypatch.setattr(
        observer, "Q62EvidenceBundle", lambda **kwargs: SimpleNamespace(**kwargs)
    )

    def historical(bundle, *, as_of):
        del as_of
        blockers = [Q62Blocker.CAPABILITY_UNPROVEN]
        if bundle.recovery.status is not RecoveryStatus.CLEAN:
            blockers.append(Q62Blocker.RECOVERY_UNPROVEN)
        return SimpleNamespace(status=Q62Status.BLOCKED, blockers=tuple(blockers))

    def prototype(bundle, *, as_of, **_kwargs):
        del as_of
        history = historical(bundle, as_of=_NOW)
        status = (
            TinyLiveReadinessStatus.READY_FOR_L43_PROTOTYPE_READ_ONLY
            if history.blockers == (Q62Blocker.CAPABILITY_UNPROVEN,)
            and bundle.recovery.status is RecoveryStatus.CLEAN
            else TinyLiveReadinessStatus.BLOCKED
        )
        blockers = (
            ()
            if status is TinyLiveReadinessStatus.READY_FOR_L43_PROTOTYPE_READ_ONLY
            else history.blockers
        )
        return SimpleNamespace(
            status=status,
            blockers=blockers,
            provider_mutation_count=0,
            live_readiness_granted=False,
            trade_authority_granted=False,
        )

    monkeypatch.setattr(observer, "evaluate_q62_readiness", historical)
    monkeypatch.setattr(observer, "evaluate_q62_tiny_live_readiness", prototype)
    if write_failure:
        monkeypatch.setattr(
            observer,
            "_write_evidence_once",
            lambda *_args: (_ for _ in ()).throw(
                observer._ObserverBlocked("Q62_EVIDENCE_WRITE_FAILED")
            ),
        )

    source_calls = 0

    def source_admitter():
        nonlocal source_calls
        source_calls += 1
        return _SOURCE

    def evidence_destination():
        path = evidence_root / f"attempt-{source_calls}"
        path.mkdir()
        return path

    dependencies = observer._Dependencies(
        source_admitter=source_admitter,
        evidence_destination=evidence_destination,
        state_root=observer.LIVE_STATE_ROOT,
        artifact_loader=lambda: (fake_l41, fake_l41r5, composite),
        robinhood_builder=robinhood_builder,
        signal_provider_builder=alpaca_builder,
        clock=lambda: _NOW,
        session_authority=NYSEPublishedRegularSessionAuthority(),
    )
    return dependencies, boundary, signal_provider


def test_import_help_and_cli_shape_construct_no_provider(monkeypatch):
    constructed = []
    monkeypatch.setattr(
        observer,
        "AlpacaRuntimeSignalProvider",
        lambda: constructed.append("alpaca"),
    )
    with pytest.raises(SystemExit) as help_exit:
        observer.main(["--help"])
    assert help_exit.value.code == 0
    with pytest.raises(SystemExit) as invalid_exit:
        observer.main(["observe", "--capability-digest", "a" * 64])
    assert invalid_exit.value.code == 2
    assert constructed == []


def test_dirty_source_blocks_before_evidence_or_provider(monkeypatch):
    calls = []

    def denied_source():
        calls.append("source")
        raise observer._ObserverBlocked("Q62_SOURCE_DIRTY")

    dependencies = observer._Dependencies(
        denied_source,
        lambda: calls.append("evidence") or Path("F:/never-created"),
        observer.LIVE_STATE_ROOT,
        lambda: calls.append("artifacts"),
        lambda _ledger: calls.append("robinhood"),
        lambda _ledger: calls.append("alpaca"),
        lambda: _NOW,
        NYSEPublishedRegularSessionAuthority(),
    )
    result = observer._observe_once(dependencies)
    assert result.reason == "Q62_SOURCE_DIRTY"
    assert calls == ["source"]


def test_dirty_git_state_fails_before_remote_or_authority(monkeypatch):
    calls = []

    def fake_run(arguments, **_kwargs):
        calls.append(tuple(arguments[3:]))
        if arguments[-2:] == ["branch", "--show-current"]:
            return subprocess.CompletedProcess(
                arguments, 0, "feature/robinhood-live-prototype-current\n", ""
            )
        return subprocess.CompletedProcess(arguments, 0, "?? stray.txt\n", "")

    monkeypatch.setattr(observer.subprocess, "run", fake_run)
    with pytest.raises(observer._ObserverBlocked, match="Q62_SOURCE_DIRTY"):
        observer._local_git_identity(Path("F:/repo"), require_live_refs=True)
    assert len(calls) == 2


def test_consumed_artifact_loader_hashes_and_classifies_exact_source_bytes(
    monkeypatch, tmp_path
):
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    l41_path = evidence_root / "l41" / "evidence.json"
    l41r5_path = evidence_root / "l41r5" / "evidence.json"
    l41_path.parent.mkdir()
    l41r5_path.parent.mkdir()
    l41_bytes = b"retained L41 evidence"
    l41r5_bytes = b"retained L41R5 evidence"
    l41_path.write_bytes(l41_bytes)
    l41r5_path.write_bytes(l41r5_bytes)
    composite = _Composite(_ACCOUNT_REPORT)
    classified = []

    monkeypatch.setattr(observer, "EVIDENCE_ROOT", evidence_root)
    monkeypatch.setattr(observer, "_CONSUMED_L41_PATH", l41_path)
    monkeypatch.setattr(observer, "_CONSUMED_L41R5_PATH", l41r5_path)
    monkeypatch.setattr(observer, "CONSUMED_L41_EVIDENCE_BYTES", len(l41_bytes))
    monkeypatch.setattr(observer, "CONSUMED_L41R5_EVIDENCE_BYTES", len(l41r5_bytes))
    monkeypatch.setattr(
        observer,
        "CONSUMED_L41_EVIDENCE_SHA256",
        hashlib.sha256(l41_bytes).hexdigest(),
    )
    monkeypatch.setattr(
        observer,
        "CONSUMED_L41R5_EVIDENCE_SHA256",
        hashlib.sha256(l41r5_bytes).hexdigest(),
    )
    monkeypatch.setattr(observer, "L41R6CompositeReport", _Composite)

    def classify(first, second):
        classified.append((first, second))
        return composite

    monkeypatch.setattr(observer, "classify_l41r6_composite", classify)
    loaded_l41, loaded_l41r5, loaded_composite = observer._load_consumed_artifacts()

    assert (loaded_l41, loaded_l41r5) == (l41_bytes, l41r5_bytes)
    assert loaded_composite is composite
    assert classified == [(l41_bytes, l41r5_bytes)]


@pytest.mark.parametrize("remote_name", [observer.FEATURE_BRANCH, "develop"])
def test_live_remote_identity_mismatch_blocks(monkeypatch, remote_name):
    calls = []

    def fake_run(arguments, **_kwargs):
        command = tuple(arguments[3:])
        calls.append(command)
        if command == ("branch", "--show-current"):
            output = observer.FEATURE_BRANCH
        elif command[:2] == ("status", "--porcelain=v1"):
            output = ""
        elif command[:2] == ("rev-parse", "--verify"):
            output = "a" * 40
        elif command[:2] == ("rev-parse", "HEAD^{tree}"):
            output = "b" * 40
        elif command[:3] == ("remote", "get-url", "origin"):
            output = observer._EXPECTED_ORIGIN
        elif command[0] == "ls-remote":
            branch = command[-1].removeprefix("refs/heads/")
            sha = "c" * 40 if branch == remote_name else "a" * 40
            output = f"{sha}\trefs/heads/{branch}"
        else:
            raise AssertionError(command)
        return subprocess.CompletedProcess(arguments, 0, output, "")

    monkeypatch.setattr(observer.subprocess, "run", fake_run)
    with pytest.raises(observer._ObserverBlocked, match="Q62_SOURCE_REMOTE_MISMATCH"):
        observer._local_git_identity(Path("F:/repo"), require_live_refs=True)
    assert any(call[0] == "ls-remote" for call in calls)


def test_source_authority_identity_must_remain_stable(monkeypatch):
    first = {
        "branch": observer.FEATURE_BRANCH,
        "head": "a" * 40,
        "tree": "b" * 40,
        "origin_feature_head": "a" * 40,
        "origin_feature_tree": "b" * 40,
        "origin_develop_head": "a" * 40,
        "origin_develop_tree": "b" * 40,
    }
    second = {**first, "head": "c" * 40}
    reads = iter((first, second))
    monkeypatch.setattr(observer, "_local_git_identity", lambda *_a, **_k: next(reads))
    monkeypatch.setattr(
        observer,
        "evaluate_source_authority",
        lambda _root, *, publication_context: SimpleNamespace(
            passed=True,
            head=first["head"],
            tree=first["tree"],
            checkpoints=(observer.CHECKPOINT_NAME,),
        ),
    )
    with pytest.raises(observer._ObserverBlocked, match="Q62_SOURCE_IDENTITY_UNSTABLE"):
        observer._source_admission(observer.CANONICAL_ROOT)


def test_evidence_destination_rejects_non_f_existing_and_reparse_paths(
    tmp_path, monkeypatch
):
    with pytest.raises(observer._ObserverBlocked):
        observer._validate_evidence_destination(
            Path("C:/outside/evidence"), root=tmp_path
        )
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(observer._ObserverBlocked):
        observer._validate_evidence_destination(existing, root=tmp_path)
    monkeypatch.setattr(observer, "_is_reparse_point", lambda _path: True)
    with pytest.raises(observer._ObserverBlocked, match="Q62_EVIDENCE_PATH_INVALID"):
        observer._validate_evidence_destination(tmp_path / "new", root=tmp_path)


def test_pre_provider_state_and_consumed_evidence_gates(monkeypatch, tmp_path):
    calls = []
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    monkeypatch.setattr(observer, "EVIDENCE_ROOT", evidence_root)
    monkeypatch.setattr(
        observer,
        "_validate_state_root",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            observer._ObserverBlocked("Q62_STATE_MISSING")
        ),
    )
    deps = observer._Dependencies(
        lambda: _SOURCE,
        lambda: _make_evidence_destination(evidence_root),
        observer.LIVE_STATE_ROOT,
        lambda: calls.append("artifact") or (b"a", b"b", object()),
        lambda _ledger: calls.append("robinhood"),
        lambda _ledger: calls.append("alpaca"),
        lambda: _NOW,
        NYSEPublishedRegularSessionAuthority(),
    )
    result = observer._observe_once(deps)
    assert result.reason == "Q62_STATE_MISSING"
    assert calls == []


def test_completed_fake_observation_authenticates_all_nine_proofs(
    monkeypatch, tmp_path
):
    dependencies, boundary, provider = _install_observation_fakes(monkeypatch, tmp_path)
    result = observer._observe_once(dependencies)
    assert (
        result.status == TinyLiveReadinessStatus.READY_FOR_L43_PROTOTYPE_READ_ONLY.value
    )
    assert boundary.calls == [
        "get_accounts",
        "get_equity_positions",
        "get_equity_orders",
    ]
    assert boundary.arguments == [
        ("get_equity_positions", {"account_number": _ACCOUNT_NUMBER}),
        (
            "get_equity_orders",
            {
                "account_number": _ACCOUNT_NUMBER,
                "placed_agent": "agentic",
                "symbol": "SPY",
            },
        ),
    ]
    assert provider is not None and provider.calls == 1
    assert observer._provider_builds_for_test == ["constructed"]
    evidence = json.loads((result.evidence_path / "evidence.json").read_text("ascii"))
    proofs = evidence["proofs"]
    assert tuple(item["kind"] for item in proofs) == tuple(
        kind.value for kind in ProofKind
    )
    assert all(item["status"] == ProofStatus.PROVEN.value for item in proofs)
    assert all(item["identity"] == evidence["identity"] for item in proofs)
    assert (
        next(item for item in proofs if item["kind"] == "CAPABILITY")["evidence_sha256"]
        == evidence["capability"]["admission_sha256"]
    )
    assert evidence["historical_q62"]["blockers"] == ["CAPABILITY_UNPROVEN"]
    assert (
        evidence["prototype_q62"]["status"]
        == TinyLiveReadinessStatus.READY_FOR_L43_PROTOTYPE_READ_ONLY.value
    )
    assert evidence["provider_mutation_count"] == 0
    assert evidence["live_readiness_granted"] is False
    assert evidence["trade_authority_granted"] is False
    assert evidence["read_bounds"]["robinhood_sessions"] == 7
    assert evidence["read_bounds"]["robinhood_tools_list_pages_total"] == 140
    assert evidence["attempts"]["evidence_write_attempts"] == 1
    assert _ACCOUNT_NUMBER not in json.dumps(evidence)
    assert _ACCOUNT_NUMBER not in repr(_ACCOUNT)


def test_account_drift_blocks_before_positions_or_alpaca(monkeypatch, tmp_path):
    changed_account = AgenticAccountIdentity("998877665544", 1)
    dependencies, boundary, provider = _install_observation_fakes(
        monkeypatch, tmp_path, account=changed_account
    )
    result = observer._observe_once(dependencies)
    assert result.status == "BLOCKED"
    assert result.reason == "Q62_ACCOUNT_IDENTITY_MISMATCH"
    assert boundary.calls == ["get_accounts"]
    assert provider is None or provider.calls == 0
    assert observer._provider_builds_for_test == []
    serialized = json.dumps(result.evidence)
    assert "998877665544" not in serialized
    assert "account_number" not in serialized


@pytest.mark.parametrize(
    ("positions", "orders", "expected_reason"),
    [
        (
            [
                {
                    "symbol": "SPY",
                    "quantity": "1",
                    "shares_available_for_sells": "1",
                    "average_buy_price": "100",
                    "type": "long",
                }
            ],
            [],
            "Q62_READ_ONLY_PREREQUISITES_BLOCKED",
        ),
        (
            [],
            [
                {
                    "id": "order-1",
                    "symbol": "SPY",
                    "side": "buy",
                    "state": "future_unknown_state",
                    "quantity": "1",
                    "cumulative_quantity": "0",
                    "created_at": "2026-11-10T14:00:00+00:00",
                    "placed_agent": "agentic",
                }
            ],
            "Q62_READ_ONLY_PREREQUISITES_BLOCKED",
        ),
    ],
)
def test_nonflat_position_or_unresolved_order_blocks(
    monkeypatch, tmp_path, positions, orders, expected_reason
):
    dependencies, _boundary, _provider = _install_observation_fakes(
        monkeypatch, tmp_path, positions=positions, orders=orders
    )
    result = observer._observe_once(dependencies)
    assert result.status == "BLOCKED"
    assert result.reason == expected_reason
    assert result.evidence["recovery"]["status"] == RecoveryStatus.BLOCKED.value
    assert result.evidence["prototype_q62"]["live_readiness_granted"] is False


def test_malformed_unrelated_row_fails_closed_without_signal_provider(
    monkeypatch, tmp_path
):
    dependencies, boundary, provider = _install_observation_fakes(
        monkeypatch, tmp_path, positions=[{"symbol": "QQQ"}]
    )
    result = observer._observe_once(dependencies)
    assert result.status == "BLOCKED"
    assert result.reason == "Q62_ROBINHOOD_RESPONSE_INVALID"
    assert boundary.calls == ["get_accounts", "get_equity_positions"]
    assert provider is not None and provider.calls == 0
    assert observer._provider_builds_for_test == []


def test_page_limit_and_provider_failure_are_one_shot():
    ledger = observer._AttemptLedger()
    calls = []

    def endless(_arguments):
        calls.append(1)
        return {"data": {"positions": [], "next": f"cursor-{len(calls)}"}}

    with pytest.raises(
        observer._ObserverBlocked, match="Q62_ROBINHOOD_PAGE_BOUND_EXCEEDED"
    ):
        observer._read_pages(
            endless,
            {},
            "positions",
            max_pages=3,
            max_rows=1000,
            page_counter="robinhood_position_page_attempts",
            ledger=ledger,
        )
    assert len(calls) == 3
    assert ledger.robinhood_position_page_attempts == 3


def test_alpaca_exception_is_sanitized_and_not_retried(monkeypatch, tmp_path):
    dependencies, boundary, provider = _install_observation_fakes(
        monkeypatch, tmp_path, signal_failure=True
    )
    result = observer._observe_once(dependencies)
    assert result.status == "BLOCKED"
    assert result.reason == "Q62_ALPACA_OBSERVATION_BLOCKED"
    assert boundary.calls == [
        "get_accounts",
        "get_equity_positions",
        "get_equity_orders",
    ]
    assert "secret" not in json.dumps(result.evidence)
    assert observer._provider_builds_for_test == ["constructed"]
    assert observer._failed_providers_for_test[0].calls == 1
    assert result.evidence["attempts"]["alpaca_snapshot_attempts"] == 1
    assert result.evidence["attempts"]["alpaca_provider_call_attempts"] is None


def test_evidence_write_failure_never_retries_or_grants_readiness(
    monkeypatch, tmp_path
):
    dependencies, _boundary, _provider = _install_observation_fakes(
        monkeypatch, tmp_path, write_failure=True
    )
    writes = []
    monkeypatch.setattr(
        observer,
        "_write_evidence_once",
        lambda *_args: (
            writes.append(1)
            or (_ for _ in ()).throw(
                observer._ObserverBlocked("Q62_EVIDENCE_WRITE_FAILED")
            )
        ),
    )
    result = observer._observe_once(dependencies)
    assert writes == [1]
    assert result.status == "BLOCKED"
    assert result.reason == "Q62_EVIDENCE_WRITE_FAILED"
    assert result.evidence["live_readiness_granted"] is False


def test_pristine_and_uncertain_durable_state_conversion():
    identity = _runtime_identity()
    pristine = DurableState(identity, Decimal("0"), last_sequence=0)
    snapshot = observer._ownership_from_durable_state(
        pristine, target_session="2026-11-10"
    )
    assert observer._is_pristine_initial_state(pristine)
    assert snapshot.lifecycle is Lifecycle.DISARMED
    assert snapshot.effect_disposition is EffectDisposition.NO_EFFECT
    assert snapshot.budget_remaining == Decimal("10.00")
    assert snapshot.entries_used == snapshot.exits_used == 0
    assert snapshot.pending_intent_id is None

    uncertain = DurableState(
        identity,
        Decimal("0"),
        entry=OrderState(
            IntentKind.ENTRY,
            "12345678-1234-1234-1234-123456789012",
            requested_dollars=Decimal("10.00"),
            status=IntentStatus.MAY_HAVE_OCCURRED,
        ),
        last_sequence=1,
    )
    changed = observer._ownership_from_durable_state(
        uncertain, target_session="2026-11-10"
    )
    assert not observer._is_pristine_initial_state(uncertain)
    assert changed.lifecycle is Lifecycle.UNKNOWN
    assert changed.effect_disposition is EffectDisposition.MAY_HAVE_OCCURRED
    assert changed.entries_used == 1
    assert changed.pending_intent_id is not None
    assert changed.entry_reserved_dollars == Decimal("10.00")


def test_recovery_rejects_manual_position_and_local_unknown_state():
    runtime = _runtime_identity()
    identity = ReadinessIdentity(
        runtime.source_head,
        runtime.source_tree,
        runtime.config_digest,
        runtime.account_fingerprint,
        "2026-11-10",
    )
    local_state = DurableState(
        runtime,
        Decimal("0"),
        entry=OrderState(
            IntentKind.ENTRY,
            "12345678-1234-1234-1234-123456789012",
            requested_dollars=Decimal("10.00"),
            status=IntentStatus.UNKNOWN,
        ),
        last_sequence=1,
    )
    snapshot = observer._ownership_from_durable_state(
        local_state, target_session=identity.target_session
    )
    observation = RecoveryObservation(
        identity,
        "f" * 64,
        _NOW,
        _NOW + timedelta(minutes=10),
        Decimal("1"),
        1,
        True,
    )
    report = reconcile_read_only(identity, snapshot, observation, as_of=_NOW)
    assert report.status is RecoveryStatus.BLOCKED
    assert report.observed_position == Decimal("1")
    assert report.working_order_count == 1


def test_all_nine_proofs_are_source_derived_and_have_bounded_freshness():
    account = _ACCOUNT
    runtime = _runtime_identity()
    state = DurableState(runtime, Decimal("0"), last_sequence=0)
    authority = NYSEPublishedRegularSessionAuthority()
    schedule = authority.schedule_for(date(2026, 11, 10))
    assert schedule is not None
    identity = ReadinessIdentity(
        runtime.source_head,
        runtime.source_tree,
        runtime.config_digest,
        runtime.account_fingerprint,
        "2026-11-10",
    )
    ownership = observer._ownership_from_durable_state(
        state, target_session=identity.target_session
    )
    recovery = RecoveryObservation(
        identity,
        "a" * 64,
        _NOW,
        _NOW + timedelta(minutes=10),
        Decimal("0"),
        0,
        False,
    )
    proofs = observer._derive_proofs(
        identity=identity,
        source=_SOURCE,
        account=account,
        capability_admission=_Admission(_ACCOUNT_REPORT),
        ownership=ownership,
        durable_state=state,
        schedule=schedule,
        inputs=_signal_inputs(),
        recovery_observation=recovery,
        source_observed_at=_NOW + timedelta(seconds=4),
        account_observed_at=_NOW,
        capability_observed_at=_NOW + timedelta(seconds=1),
        state_observed_at=_NOW + timedelta(seconds=2),
        signal_observed_at=_NOW,
    )
    assert tuple(proof.kind for proof in proofs) == tuple(ProofKind)
    assert all(proof.identity == identity for proof in proofs)
    assert all(proof.status is ProofStatus.PROVEN for proof in proofs)
    assert next(p for p in proofs if p.kind is ProofKind.SOURCE).observed_at == (
        _NOW + timedelta(seconds=4)
    )
    assert next(p for p in proofs if p.kind is ProofKind.ACCOUNT).observed_at == _NOW
    assert next(p for p in proofs if p.kind is ProofKind.CAPABILITY).observed_at == (
        _NOW + timedelta(seconds=1)
    )
    assert next(p for p in proofs if p.kind is ProofKind.OWNERSHIP).observed_at == (
        _NOW + timedelta(seconds=2)
    )
    for proof in proofs:
        if proof.kind in {
            ProofKind.OWNERSHIP,
            ProofKind.BUDGET,
        }:
            assert proof.valid_until == _NOW + timedelta(minutes=10, seconds=2)
        elif proof.kind is ProofKind.ACCOUNT:
            assert proof.valid_until == _NOW + timedelta(minutes=10)
        elif proof.kind is ProofKind.RECOVERY:
            assert proof.valid_until == _NOW + timedelta(minutes=10)
        else:
            assert proof.valid_until == schedule.closes_at
    capability = next(proof for proof in proofs if proof.kind is ProofKind.CAPABILITY)
    assert capability.evidence_sha256 == _Admission(_ACCOUNT_REPORT).admission_digest


def test_transport_wrapper_exposes_only_three_q62_reads():
    boundary = observer._TrackedReadBoundary(
        _FakeReadBoundary(), observer._AttemptLedger()
    )
    assert callable(boundary.get_accounts)
    assert callable(boundary.get_equity_positions)
    assert callable(boundary.get_equity_orders)
    assert not hasattr(boundary, "call_tool")
    assert not hasattr(boundary, "get_portfolio")
    assert not hasattr(boundary, "get_equity_quotes")
    assert not hasattr(boundary, "review_equity_order")
    assert not hasattr(boundary, "place_equity_order")
    assert not hasattr(boundary, "cancel_equity_order")


def test_source_ownership_and_safety_contract_are_registered_once():
    from scripts import checkpoint_runner as runner

    source = "src/trading_bot/live_prototype/tiny_live_readiness_observer.py"
    test = "tests/live_prototype/test_tiny_live_readiness_observer.py"
    assert runner.ARCH147_PROTOTYPE_TESTS.count(test) == 1
    assert "src/trading_bot/live_prototype" in runner.ARCH147_PROTOTYPE_RUFF
    text = Path(observer.__file__).read_text(encoding="utf-8")
    tree = ast.parse(text)
    assert "l41r7" not in text.casefold()
    assert "final_holdout" not in text.casefold()
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"eval", "exec", "__import__"}
        for node in ast.walk(tree)
    )
    assert source.endswith("tiny_live_readiness_observer.py")
    assert "unlink(" not in text and "rmtree(" not in text
