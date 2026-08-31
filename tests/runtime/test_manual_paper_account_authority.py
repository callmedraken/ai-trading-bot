"""P3 account inventory/replay/provenance coverage using disposable roots only."""

from __future__ import annotations

import ast
import copy
import json
import pickle
import socket
import sqlite3
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from tests.runtime.test_checkpointed_verified_snapshot_execution import (
    _checkpoint_verification,
    _permissive_limits,
    _request,
    _target,
)
from tests.runtime.test_paper_account_lineage_verification import _one_edge, _two_edges
from tests.runtime.test_paper_operation import CONFIGURATION, _completed
from tests.runtime.test_verified_snapshot_preparation import (
    _policies,
    _verification,
    calendar,
)

import trading_bot.runtime.manual_paper_account_authority as p3
import trading_bot.runtime.paper_operation as operation_module
from trading_bot.runtime import (
    PaperOperationDiagnosticCode,
    PaperOperationReceipt,
    PaperOperationStatus,
    checkpointed_paper_cycle_report_from_result,
    checkpointed_paper_cycle_report_reference,
    create_paper_operation_intent,
    create_successor_paper_account_checkpoint,
    derive_checkpointed_verified_snapshot_application_id,
    execute_checkpointed_verified_snapshot_paper_cycle,
    parse_checkpointed_paper_cycle_report,
    parse_paper_operation_receipt,
    parse_successor_paper_account_checkpoint,
    serialize_checkpointed_paper_cycle_report,
    serialize_paper_operation_receipt,
    serialize_successor_paper_account_checkpoint,
    verify_genesis_paper_account_checkpoint,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
)
from trading_bot.runtime.windows_paper_account_mutex import (
    PaperAccountMutexAcquisition,
    PaperAccountMutexState,
    paper_account_mutex_name,
)

ACCOUNT = UUID("fd64eb7d-50c3-4ea4-9a5a-142c465f5a95")
SID = "S-1-5-21-1-2-3-1009"
MACHINE = "test-machine/v1"


class Mutex:
    def __init__(self, account, *, abandoned=False, on_enter=None):
        self.account = account
        self.abandoned = abandoned
        self.on_enter = on_enter
        self.acquisition = None
        self.active = False
        self.exits = 0

    def __enter__(self):
        assert not self.active
        self.active = True
        self.acquisition = PaperAccountMutexAcquisition(
            paper_account_mutex_name(self.account),
            PaperAccountMutexState.ABANDONED_OWNER
            if self.abandoned
            else PaperAccountMutexState.OWNED,
        )
        if self.on_enter:
            self.on_enter()
        return self

    def __exit__(self, *args):
        self.active = False
        self.exits += 1


def anchor_for(lineage):
    return p3.ManualPaperAccountAnchor(
        ACCOUNT,
        MACHINE,
        SID,
        lineage.genesis.artifact_id,
        lineage.genesis.sha256,
        lineage.genesis.byte_length,
    )


def write_transitions(root, capture, lineage):
    for successor, report in zip(lineage.successors, lineage.reports, strict=True):
        model = parse_successor_paper_account_checkpoint(successor.payload)
        parsed_report = parse_checkpointed_paper_cycle_report(report.payload)
        result_id = parsed_report.evidence.cycle_result_id
        directory = root / f"paper-account-transition-{model.application_id}"
        directory.mkdir(exist_ok=True)
        (directory / f"checkpointed-paper-cycle-report-{result_id}.json").write_bytes(
            report.payload
        )
        (
            directory / f"paper-account-checkpoint-{model.checkpoint_id}.json"
        ).write_bytes(successor.payload)
    for snapshot in lineage.snapshots:
        (
            capture / f"daily-market-data-snapshot-{snapshot.artifact_id}.json"
        ).write_bytes(snapshot.payload)


def setup(
    tmp_path,
    lineage,
    *,
    read_factory=p3.DisposablePaperAccountReadSessionForTest,
    mutex_factory=Mutex,
):
    root, capture = tmp_path / "paper", tmp_path / "capture"
    root.mkdir()
    capture.mkdir()
    anchor = anchor_for(lineage)
    (root / p3.MANUAL_PAPER_ACCOUNT_ANCHOR_FILENAME).write_bytes(
        p3.serialize_manual_paper_account_anchor(anchor)
    )
    genesis_dir = root / f"paper-account-genesis-{anchor.genesis_checkpoint_id}"
    genesis_dir.mkdir()
    (
        genesis_dir / f"paper-account-checkpoint-{anchor.genesis_checkpoint_id}.json"
    ).write_bytes(lineage.genesis.payload)
    write_transitions(root, capture, lineage)
    authority = p3.DisposableManualPaperAccountAuthorityForTest(
        paper_root=root,
        capture_root=capture,
        machine_authority_id=MACHINE,
        approved_trading_sid=SID,
        mutex_factory=mutex_factory,
        read_session_factory=read_factory,
    )
    return authority, root, capture


@pytest.fixture(scope="module")
def one():
    return _one_edge()


@pytest.fixture(scope="module")
def two():
    return _two_edges()


def genesis_only(one):
    return replace(
        one,
        successors=(),
        reports=(),
        snapshots=(),
        terminal_id=one.genesis.artifact_id,
    )


@pytest.mark.parametrize("edges", [0, 1, 2])
def test_complete_inventory_graph_and_immutable_output(tmp_path, one, two, edges):
    lineage = [genesis_only(one), one, two][edges]
    authority, root, capture = setup(tmp_path, lineage)
    before = {
        path: path.read_bytes()
        for base in (root, capture)
        for path in base.rglob("*")
        if path.is_file()
    }
    result = authority.preflight()
    assert result.anchor == anchor_for(one)
    assert result.paper_account_id == ACCOUNT
    assert result.machine_authority_id == MACHINE
    assert result.approved_trading_sid == SID
    assert result.finalized_transition_count == result.lineage.edge_count == edges
    assert result.terminal_checkpoint_id == lineage.terminal_id
    assert result.terminal_sequence == edges
    assert result.terminal_sha256 == result.lineage.checkpoint_artifacts[-1].sha256
    assert (
        result.terminal_byte_length
        == result.lineage.checkpoint_artifacts[-1].byte_length
    )
    assert result.historical_snapshot_dependencies == result.lineage.snapshot_artifacts
    assert result.verified_prior.compact_state == result.lineage.terminal_compact_state
    assert {path: path.read_bytes() for path in before} == before
    with pytest.raises(FrozenInstanceError):
        result.finalized_transition_count = 99


def test_exact_historical_paths_no_capture_scan_and_graph_order(
    tmp_path, two, monkeypatch
):
    reads, listings = [], []

    class Reader(p3.DisposablePaperAccountReadSessionForTest):
        def inventory(self, path, role, limit):
            listings.append(path)
            return tuple(reversed(super().inventory(path, role, limit)))

        def read(self, path, role, limit):
            reads.append((path, role))
            return super().read(path, role, limit)

    authority, root, capture = setup(tmp_path, two, read_factory=Reader)
    (capture / "daily-market-data-snapshot-latest.json").write_bytes(b"not authority")
    seen = []
    verify = p3.verify_paper_account_lineage

    def capture_verification(*args):
        seen.append(args)
        return verify(*args)

    monkeypatch.setattr(p3, "verify_paper_account_lineage", capture_verification)
    first = authority.preflight()
    assert str(capture) not in listings
    assert {path for path, role in reads if role == "snapshot"} == {
        str(capture / f"daily-market-data-snapshot-{item.artifact_id}.json")
        for item in two.snapshots
    }
    assert len(seen) == 1
    assert seen[0][:5] == (
        two.genesis,
        two.terminal_id,
        two.successors,
        two.reports,
        two.snapshots,
    )
    for path in root.rglob("*.json"):
        import os

        os.utime(path, (100, 100))
    assert authority.preflight() == first


@pytest.mark.parametrize(
    "change",
    [
        "unknown",
        "missing",
        "duplicate",
        "uppercase_uuid",
        "schema",
        "float",
        "bool",
        "negative",
        "sha",
        "bom",
        "newline",
        "trailing",
        "epoch",
        "provider",
        "credential",
        "path",
    ],
)
def test_strict_anchor_rejects_every_noncanonical_shape(one, change):
    payload = p3.serialize_manual_paper_account_anchor(anchor_for(one))
    tree = json.loads(payload)
    if change in {"unknown", "epoch", "provider", "credential", "path"}:
        tree[change] = "unapproved"
    elif change == "missing":
        del tree["genesis_sha256"]
    elif change == "uppercase_uuid":
        tree["paper_account_id"] = tree["paper_account_id"].upper()
    elif change == "schema":
        tree["schema"] = "manual-paper-account-authority/v2"
    elif change in {"float", "bool", "negative"}:
        tree["genesis_byte_length"] = {"float": 1.0, "bool": True, "negative": -1}[
            change
        ]
    elif change == "sha":
        tree["genesis_sha256"] = "A" * 64
    modified = json.dumps(tree, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    modified = {
        "duplicate": b'{"schema":"duplicate",' + payload[1:],
        "bom": b"\xef\xbb\xbf" + payload,
        "newline": payload[:-1],
        "trailing": payload + b" ",
    }.get(change, modified)
    with pytest.raises(p3.ManualPaperAccountAuthorityError):
        p3.parse_manual_paper_account_anchor(modified)


def test_anchor_has_only_frozen_fields(one):
    payload = p3.serialize_manual_paper_account_anchor(anchor_for(one))
    assert set(json.loads(payload)) == {
        "schema",
        "paper_account_id",
        "machine_authority_id",
        "approved_trading_sid",
        "genesis_checkpoint_id",
        "genesis_sha256",
        "genesis_byte_length",
    }
    assert p3.parse_manual_paper_account_anchor(payload) == anchor_for(one)


@pytest.mark.parametrize(
    "field,value",
    [
        ("machine_authority_id", "other-machine"),
        ("approved_trading_sid", "S-1-5-21-1-2-3-1010"),
        ("genesis_checkpoint_id", UUID(int=123)),
        ("genesis_sha256", "0" * 64),
        ("genesis_byte_length", 1),
    ],
)
def test_anchor_identity_and_genesis_bindings_block(tmp_path, one, field, value):
    authority, root, _ = setup(tmp_path, genesis_only(one))
    changed = replace(anchor_for(one), **{field: value})
    (root / p3.MANUAL_PAPER_ACCOUNT_ANCHOR_FILENAME).write_bytes(
        p3.serialize_manual_paper_account_anchor(changed)
    )
    with pytest.raises(p3.ManualPaperAccountAuthorityError):
        authority.preflight()


@pytest.mark.parametrize(
    "state",
    [
        "missing_anchor",
        "alternate_genesis",
        "root_unknown",
        "latest",
        "staging",
        "receipt_staging",
        "bad_report",
        "extra_transition_file",
        "wrong_report_name",
        "wrong_successor_name",
        "device_file",
    ],
)
def test_unknown_malformed_staging_and_unsafe_inventory_blocks(tmp_path, one, state):
    authority, root, _ = setup(tmp_path, one)
    transition = next(root.glob("paper-account-transition-*"))
    if state == "missing_anchor":
        (root / p3.MANUAL_PAPER_ACCOUNT_ANCHOR_FILENAME).unlink()
    elif state == "alternate_genesis":
        (root / f"paper-account-genesis-{UUID(int=123)}").mkdir()
    elif state in {"root_unknown", "latest"}:
        (root / state).write_bytes(b"unknown")
    elif state == "staging":
        (root / f".{transition.name}.staging").mkdir()
    elif state == "receipt_staging":
        (root / "paper-operations").mkdir()
        (
            root / "paper-operations" / f".paper-operation-{UUID(int=123)}.staging"
        ).mkdir()
    elif state == "bad_report":
        next(transition.glob("checkpointed-*.json")).write_bytes(b"{}\n")
    elif state == "extra_transition_file":
        (transition / "extra.json").write_bytes(b"{}")
    elif state == "wrong_report_name":
        next(transition.glob("checkpointed-*.json")).rename(
            transition / f"checkpointed-paper-cycle-report-{UUID(int=123)}.json"
        )
    elif state == "wrong_successor_name":
        next(transition.glob("paper-account-checkpoint-*.json")).rename(
            transition / f"paper-account-checkpoint-{UUID(int=123)}.json"
        )
    else:
        path = next(transition.glob("paper-account-checkpoint-*.json"))
        path.unlink()
        path.mkdir()
    with pytest.raises(p3.ManualPaperAccountAuthorityError):
        authority.preflight()


@pytest.mark.parametrize(
    "mode", ["missing", "wrong", "invalid_snapshot", "id_mismatch", "unstable"]
)
def test_historical_snapshot_failure_blocks(tmp_path, one, monkeypatch, mode):
    authority, _, capture = setup(tmp_path, one)
    path = next(capture.iterdir())
    if mode == "missing":
        path.unlink()
    elif mode == "wrong":
        path.write_bytes(b"wrong")
    elif mode == "unstable":
        original = p3.DisposablePaperAccountReadSessionForTest.read

        def read(self, path, role, limit):
            result = original(self, path, role, limit)
            if role == "snapshot":
                Path(path).write_bytes(b"changed after read")
            return result

        monkeypatch.setattr(p3.DisposablePaperAccountReadSessionForTest, "read", read)
    else:
        monkeypatch.setattr(
            p3,
            "verify_daily_snapshot",
            lambda *a, **kw: SimpleNamespace(
                passed=mode != "invalid_snapshot",
                diagnostics=(),
                snapshot=SimpleNamespace(snapshot_id=UUID(int=3)),
            ),
        )
    with pytest.raises(p3.ManualPaperAccountAuthorityError):
        authority.preflight()


@pytest.mark.parametrize(
    "field,value",
    [
        ("snapshot_id", str(UUID(int=3))),
        ("artifact_sha256", "0" * 64),
        ("artifact_byte_length", 1),
    ],
)
def test_report_snapshot_reference_tampering_blocks(tmp_path, one, field, value):
    authority, root, _ = setup(tmp_path, one)
    path = next(root.glob("paper-account-transition-*/checkpointed-*.json"))
    tree = json.loads(path.read_bytes())
    tree["report"]["evidence"]["request"]["snapshot_reference"][field] = value
    path.write_bytes(
        json.dumps(tree, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    )
    with pytest.raises(p3.ManualPaperAccountAuthorityError):
        authority.preflight()


def test_valid_chain_plus_disconnected_transition_is_not_ignored(tmp_path, one):
    authority, root, capture = setup(tmp_path, one)
    disconnected = _one_edge(checkpoint=_checkpoint_verification(realized="1"))
    write_transitions(root, capture, disconnected)
    with pytest.raises(p3.ManualPaperAccountAuthorityError, match="DISCONNECTED"):
        authority.preflight()


def test_fork_blocks(tmp_path, one):
    authority, root, capture = setup(tmp_path, one)
    snapshot = _verification()
    request = replace(
        _request(snapshot, target=_target("10", "0", "972.50")),
        request_id=UUID(int=999),
    )
    result = execute_checkpointed_verified_snapshot_paper_cycle(
        request,
        verify_genesis_paper_account_checkpoint(one.genesis.payload),
        snapshot,
        calendar(),
    )
    report = checkpointed_paper_cycle_report_from_result(result)
    report_bytes = serialize_checkpointed_paper_cycle_report(report)
    successor = create_successor_paper_account_checkpoint(
        report.evidence.prior_checkpoint,
        report.evidence.prior_lineage_id,
        result,
        checkpointed_paper_cycle_report_reference(report_bytes),
    )
    fork = replace(
        one,
        reports=(p3._artifact(one.reports[0].kind, report.report_id, report_bytes),),
        successors=(
            p3._artifact(
                one.successors[0].kind,
                successor.checkpoint_id,
                serialize_successor_paper_account_checkpoint(successor),
            ),
        ),
    )
    write_transitions(root, capture, fork)
    with pytest.raises(p3.ManualPaperAccountAuthorityError, match="FORK"):
        authority.preflight()


@pytest.mark.parametrize(
    "mode",
    [
        "collision",
        "overflow",
        "byte_budget",
        "lineage_partial",
        "lineage_fail",
        "changed_inventory",
    ],
)
def test_bounds_and_explicit_lineage_reconciliation(
    tmp_path, one, two, monkeypatch, mode
):
    authority, root, _ = setup(tmp_path, two)
    if mode == "collision":
        original = p3.DisposablePaperAccountReadSessionForTest.inventory

        def names(self, path, role, limit):
            result = original(self, path, role, limit)
            return (*result, result[0].upper()) if path == str(root) else result

        monkeypatch.setattr(
            p3.DisposablePaperAccountReadSessionForTest, "inventory", names
        )
    elif mode == "overflow":
        monkeypatch.setattr(p3, "MAX_MANUAL_PAPER_ROOT_ENTRIES", 2)
    elif mode == "byte_budget":
        monkeypatch.setattr(p3, "MAX_MANUAL_PAPER_INVENTORY_BYTES", 1)
    elif mode == "lineage_partial":
        verify = p3.verify_paper_account_lineage
        partial = verify(
            one.genesis,
            one.terminal_id,
            one.successors,
            one.reports,
            one.snapshots,
            p3._calendar(),
        )
        monkeypatch.setattr(p3, "verify_paper_account_lineage", lambda *a: partial)
    elif mode == "lineage_fail":
        monkeypatch.setattr(
            p3,
            "verify_paper_account_lineage",
            lambda *a: SimpleNamespace(status="FAIL", evidence=None, diagnostics=()),
        )
    else:
        original = p3.DisposablePaperAccountReadSessionForTest.finish

        def finish(self):
            (root / "late-state").write_bytes(b"unrecognized")
            original(self)

        monkeypatch.setattr(
            p3.DisposablePaperAccountReadSessionForTest, "finish", finish
        )
    with pytest.raises(p3.ManualPaperAccountAuthorityError):
        authority.preflight()


@pytest.mark.parametrize("abandoned", [False, True])
def test_lock_scoped_fresh_proof_is_revoked_before_release(tmp_path, one, abandoned):
    locks, sessions = [], []

    def mutex(account):
        lock = Mutex(account, abandoned=abandoned)
        locks.append(lock)
        return lock

    def reader():
        sessions.append(bool(locks and locks[-1].active))
        return p3.DisposablePaperAccountReadSessionForTest()

    authority, _, _ = setup(tmp_path, one, read_factory=reader, mutex_factory=mutex)
    with authority.locked_revalidate() as scope:
        assert sessions == [False, True]
        assert scope.acquisition.was_abandoned == abandoned
        assert scope.evidence.terminal_checkpoint_id == one.terminal_id
        with pytest.raises(p3.ManualPaperAccountAuthorityError, match="PROVENANCE"):
            p3.require_locked_manual_paper_account(scope, scope.evidence)
    assert locks[0].exits == 1
    with pytest.raises(p3.ManualPaperAccountAuthorityError, match="INACTIVE"):
        _ = scope.evidence


@pytest.mark.parametrize("change", ["anchor", "tip", "staging"])
def test_changes_between_preflight_and_lock_are_revalidated(tmp_path, one, two, change):
    locks = []

    def mutate():
        if change == "anchor":
            anchor = replace(anchor_for(one), paper_account_id=UUID(int=50))
            (root / p3.MANUAL_PAPER_ACCOUNT_ANCHOR_FILENAME).write_bytes(
                p3.serialize_manual_paper_account_anchor(anchor)
            )
        elif change == "tip":
            write_transitions(root, capture, two)
        else:
            (root / ".interrupted.staging").mkdir()

    def mutex(account):
        lock = Mutex(account, abandoned=True, on_enter=mutate)
        locks.append(lock)
        return lock

    authority, root, capture = setup(tmp_path, one, mutex_factory=mutex)
    expected = authority.preflight()
    with pytest.raises(p3.ManualPaperAccountAuthorityError):
        with authority.locked_revalidate(expected=expected):
            pytest.fail("stale lock admission")
    assert locks[0].exits == 1


@pytest.mark.parametrize("abandoned", [False, True])
def test_default_locked_revalidation_blocks_valid_tip_drift(
    tmp_path, one, two, abandoned
):
    locks, sessions = [], []

    def mutex(account):
        lock = Mutex(
            account,
            abandoned=abandoned,
            on_enter=lambda: write_transitions(root, capture, two),
        )
        locks.append(lock)
        return lock

    def reader():
        sessions.append(bool(locks and locks[-1].active))
        return p3.DisposablePaperAccountReadSessionForTest()

    authority, root, capture = setup(
        tmp_path, one, read_factory=reader, mutex_factory=mutex
    )
    with pytest.raises(
        p3.ManualPaperAccountAuthorityError, match="P3_ACCOUNT_CHANGED_BEFORE_LOCK"
    ):
        with authority.locked_revalidate():
            pytest.fail("a live scope was issued after valid account-tip drift")

    assert sessions == [False, True]
    assert locks[0].account == ACCOUNT
    assert locks[0].acquisition.was_abandoned == abandoned
    assert locks[0].exits == 1
    assert not locks[0].active
    # The successor itself is valid: admission failed because the proof changed.
    fresh = authority.preflight()
    assert fresh.anchor == anchor_for(one)
    assert fresh.terminal_checkpoint_id == two.terminal_id != one.terminal_id
    assert fresh.finalized_transition_count == 2


@pytest.mark.parametrize("transform", [copy.copy, copy.deepcopy, pickle.dumps])
def test_authority_and_scope_cannot_be_copied(tmp_path, one, transform):
    authority, _, _ = setup(tmp_path, genesis_only(one))
    with pytest.raises(TypeError):
        transform(authority)
    with authority.locked_revalidate() as scope:
        with pytest.raises(TypeError):
            transform(scope)


def test_forged_authority_scope_and_caller_roots_rejected(tmp_path):
    for value in (
        None,
        object(),
        SimpleNamespace(machine_authority_id=MACHINE),
        object.__new__(ValidatedProductionAuthority),
    ):
        with pytest.raises(p3.ManualPaperAccountAuthorityError):
            p3.WindowsManualPaperAccountAuthority(value)
    forged = object.__new__(p3.WindowsManualPaperAccountAuthority)
    with pytest.raises(p3.ManualPaperAccountAuthorityError):
        forged.preflight()
    with pytest.raises(TypeError):
        p3.WindowsManualPaperAccountAuthority(object(), paper_root=tmp_path)
    forged_scope = object.__new__(p3.LockedManualPaperAccount)
    with pytest.raises(p3.ManualPaperAccountAuthorityError):
        _ = forged_scope.evidence
    with pytest.raises(p3.ManualPaperAccountAuthorityError):
        p3.DisposableManualPaperAccountAuthorityForTest(
            paper_root=Path(r"F:\AITradingBot\Paper"),
            capture_root=tmp_path,
            machine_authority_id=MACHINE,
            approved_trading_sid=SID,
            mutex_factory=Mutex,
        )


def test_production_constructor_attenuates_without_retaining_c1(monkeypatch):
    c1 = SimpleNamespace(machine_authority_id=MACHINE, approved_account_sid=SID)
    calls = []

    def require(value):
        assert value is c1
        calls.append(value)
        return c1

    monkeypatch.setattr(p3, "require_validated_production_authority", require)
    authority = p3.WindowsManualPaperAccountAuthority(c1)
    assert calls == [c1]
    binding = p3._binding(authority)
    assert binding.paper_root == r"F:\AITradingBot\Paper"
    assert binding.capture_root == r"F:\AITradingBot\Authority\capture-output"
    assert binding.machine_id == MACHINE and binding.sid == SID
    assert not hasattr(authority, "__dict__")
    assert all(
        getattr(binding, field) is not c1 for field in binding.__dataclass_fields__
    )
    assert {cell.cell_contents for cell in binding.read_session.__closure__} == {SID}
    assert {cell.cell_contents for cell in binding.mutex.__closure__} == {SID}
    assert set(name for name in dir(authority) if not name.startswith("_")) == {
        "preflight",
        "locked_revalidate",
    }


def test_p3_has_no_direct_effect_or_private_cross_module_imports(
    tmp_path, one, monkeypatch
):
    authority, _, _ = setup(tmp_path, one)

    def forbidden(*args, **kwargs):
        raise AssertionError("external effect")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    authority.preflight()
    tree = ast.parse(Path(p3.__file__).read_text())
    imported = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert all(
        not name.name.startswith("_") for node in imported for name in node.names
    )
    assert not any(
        token in (node.module or "")
        for node in imported
        for token in (
            "paper_operation_execution",
            "windows_transactional_authority",
            "manual_paper_selected_c3_snapshot",
            "windows_effectful_capture",
            "credential",
            "strategy",
        )
    )
    assert not any(
        name.name.startswith("execute_") or name.name.startswith("recover_")
        for node in imported
        for name in node.names
    )


@pytest.fixture(scope="module")
def audit_receipts():
    # These receipts are independently valid fixture data. Neither exact cycle
    # configuration nor this completed edge is published into the P3 account.
    completed, genesis, snapshot, report, successor = _completed(
        target=_target("10", "0", "972.50")
    )
    base = completed.intent
    request = replace(
        base.request,
        request_id=UUID(int=501),
        target=_target("0", "9", "173"),
        policies=_policies(risk_limits=_permissive_limits()),
        open_references=tuple(
            replace(item, caller_asserted_open_reference_price=Decimal("300"))
            if str(item.symbol) == "QQQ"
            else item
            for item in base.request.open_references
        ),
    )
    intent = create_paper_operation_intent(
        base.caller_idempotency_key,
        base.prior_lineage_evidence,
        base.terminal_checkpoint_artifact,
        base.completed_snapshot_artifact,
        base.cycle_configuration_artifact,
        request,
    )
    failed = PaperOperationReceipt(
        1,
        intent.operation_id,
        intent,
        PaperOperationStatus.FAILED,
        None,
        PaperOperationDiagnosticCode.INSUFFICIENT_CASH,
        base.prior_lineage_evidence,
        None,
        None,
        None,
        derive_checkpointed_verified_snapshot_application_id(
            genesis.artifact_id, request.request_id
        ),
        None,
    )
    # Verify fixture validity before tests forbid P3 from invoking this verifier.
    for receipt, report_bytes, successor_bytes in (
        (completed, report, successor),
        (failed, None, None),
    ):
        verification = operation_module.verify_paper_operation_receipt(
            serialize_paper_operation_receipt(receipt),
            cycle_configuration_payload=CONFIGURATION,
            prior_genesis_checkpoint=genesis,
            prior_successor_checkpoints=(),
            prior_cycle_reports=(),
            prior_snapshots=(),
            completed_snapshot_payload=snapshot,
            transition_report_payload=report_bytes,
            successor_checkpoint_payload=successor_bytes,
            calendar=calendar(),
        )
        assert verification.status.value == "PASS"
    return completed, failed


def write_audit_receipt(root, receipt):
    directory = root / "paper-operations" / f"paper-operation-{receipt.receipt_id}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"paper-operation-receipt-{receipt.receipt_id}.json"
    path.write_bytes(serialize_paper_operation_receipt(receipt))
    return path


def test_genesis_with_empty_operations_namespace_passes(tmp_path, one):
    authority, root, _ = setup(tmp_path, genesis_only(one))
    before = authority.preflight()
    (root / "paper-operations").mkdir()
    assert authority.preflight() == before


@pytest.mark.parametrize("receipt_index", [0, 1])
@pytest.mark.parametrize("edges", [0, 2])
def test_finalized_receipts_do_not_authorize_or_change_account_tip(
    tmp_path, one, two, audit_receipts, monkeypatch, receipt_index, edges
):
    authority, root, _ = setup(tmp_path, two if edges else genesis_only(one))
    before = authority.preflight()
    artifact_sets = []
    verifier = p3.verify_paper_account_lineage

    def record_lineage(*args):
        artifact_sets.append(args[:5])
        return verifier(*args)

    def forbidden(*args, **kwargs):
        pytest.fail(
            "P3 must not verify operation receipts or resolve their dependencies"
        )

    monkeypatch.setattr(p3, "verify_paper_account_lineage", record_lineage)
    monkeypatch.setattr(operation_module, "verify_paper_operation_receipt", forbidden)
    monkeypatch.setattr("trading_bot.runtime.verify_paper_operation_receipt", forbidden)
    monkeypatch.setattr(p3, "verify_paper_operation_receipt", forbidden, raising=False)
    receipt = audit_receipts[receipt_index]
    path = write_audit_receipt(root, receipt)
    assert parse_paper_operation_receipt(path.read_bytes()) == receipt
    assert not any(item.read_bytes() == CONFIGURATION for item in root.rglob("*.json"))
    if receipt.status is PaperOperationStatus.COMPLETED:
        assert not list(
            root.glob(
                f"paper-account-transition-*/paper-account-checkpoint-"
                f"{receipt.successor_checkpoint_artifact.artifact_id}.json"
            )
        )
    after = authority.preflight()
    with authority.locked_revalidate(expected=before) as scope:
        assert scope.evidence == before
    assert after.lineage == before.lineage
    assert after.verified_prior == before.verified_prior
    assert after.terminal_checkpoint_id == before.terminal_checkpoint_id
    assert after == before
    path.unlink()
    path.parent.rmdir()
    assert authority.preflight() == before
    assert all(artifacts == artifact_sets[0] for artifacts in artifact_sets)


def test_receipts_with_same_caller_key_do_not_create_p3_conflicts(
    tmp_path, two, audit_receipts
):
    authority, root, _ = setup(tmp_path, two)
    before = authority.preflight()
    completed, failed = audit_receipts
    assert (
        completed.intent.caller_idempotency_key == failed.intent.caller_idempotency_key
    )
    assert completed.intent.operation_id != failed.intent.operation_id
    for receipt in audit_receipts:
        write_audit_receipt(root, receipt)
    assert authority.preflight() == before


@pytest.mark.parametrize(
    "state",
    [
        "staging",
        "malformed",
        "noncanonical",
        "directory_id",
        "file_id",
        "parsed_id",
        "intent_id",
        "extra_file",
        "unknown_namespace_entry",
        "namespace_overflow",
        "receipt_overflow",
    ],
)
def test_invalid_receipt_audit_layout_remains_fail_closed(
    tmp_path, one, audit_receipts, monkeypatch, state
):
    authority, root, _ = setup(tmp_path, one)
    receipt = audit_receipts[0]
    path = write_audit_receipt(root, receipt)
    operations = path.parent.parent
    other = UUID(int=602)
    if state == "staging":
        (operations / f".paper-operation-{other}.staging").mkdir()
    elif state == "malformed":
        path.write_bytes(b"{}\n")
    elif state == "noncanonical":
        path.write_bytes(path.read_bytes() + b" ")
    elif state == "directory_id":
        path.parent.rename(operations / f"paper-operation-{other}")
    elif state == "file_id":
        path.rename(path.parent / f"paper-operation-receipt-{other}.json")
    elif state == "parsed_id":
        path.rename(path.parent / f"paper-operation-receipt-{other}.json")
        path.parent.rename(operations / f"paper-operation-{other}")
    elif state == "intent_id":
        tree = json.loads(path.read_bytes())
        tree["receipt"]["intent"]["operation_id"] = str(other)
        path.write_bytes(
            json.dumps(tree, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        )
    elif state == "extra_file":
        (path.parent / "extra.json").write_bytes(b"{}")
    elif state == "unknown_namespace_entry":
        (operations / "current.json").write_bytes(b"{}")
    elif state == "namespace_overflow":
        monkeypatch.setattr(p3, "MAX_MANUAL_PAPER_ROOT_ENTRIES", 4)
        for index in range(4):
            (operations / f"paper-operation-{UUID(int=700 + index)}").mkdir()
    else:
        monkeypatch.setattr(p3, "MAX_PAPER_OPERATION_RECEIPT_BYTES", 2)
    with pytest.raises(p3.ManualPaperAccountAuthorityError):
        authority.preflight()


@pytest.mark.parametrize("target", ["namespace", "directory", "file"])
@pytest.mark.parametrize("attribute", [0x400, 0x40])
def test_unsafe_receipt_namespace_objects_block(
    tmp_path, one, audit_receipts, monkeypatch, target, attribute
):
    authority, root, _ = setup(tmp_path, one)
    path = write_audit_receipt(root, audit_receipts[0])
    selected = {
        "namespace": path.parent.parent,
        "directory": path.parent,
        "file": path,
    }[target]
    original = Path.lstat

    def lstat(candidate, *args, **kwargs):
        info = original(candidate, *args, **kwargs)
        if candidate == selected:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=attribute)
        return info

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(p3.ManualPaperAccountAuthorityError, match="UNSAFE"):
        authority.preflight()


def test_receipt_casefold_collision_blocks(tmp_path, one, audit_receipts, monkeypatch):
    authority, root, _ = setup(tmp_path, one)
    path = write_audit_receipt(root, audit_receipts[0])
    original = p3.DisposablePaperAccountReadSessionForTest.inventory

    def inventory(self, directory, role, limit):
        names = original(self, directory, role, limit)
        if directory == str(path.parent.parent):
            return (*names, names[0].upper())
        return names

    monkeypatch.setattr(
        p3.DisposablePaperAccountReadSessionForTest, "inventory", inventory
    )
    with pytest.raises(p3.ManualPaperAccountAuthorityError, match="CASEFOLD"):
        authority.preflight()


def test_receipt_identity_change_after_read_blocks(
    tmp_path, one, audit_receipts, monkeypatch
):
    authority, root, _ = setup(tmp_path, one)
    path = write_audit_receipt(root, audit_receipts[0])
    original = p3.DisposablePaperAccountReadSessionForTest.read

    def read(self, candidate, role, limit):
        payload = original(self, candidate, role, limit)
        if candidate == str(path):
            path.write_bytes(b"changed after canonical read")
        return payload

    monkeypatch.setattr(p3.DisposablePaperAccountReadSessionForTest, "read", read)
    with pytest.raises(p3.ManualPaperAccountAuthorityError, match="CHANGED"):
        authority.preflight()


@pytest.mark.parametrize(
    "mode",
    [
        "self_cycle",
        "detached_cycle",
        "report_reuse",
        "application_reuse",
        "competing_successor",
    ],
)
def test_complete_graph_rejects_cycles_and_reuse_even_before_replay(mode):
    def edge(parent, child, report, application):
        return SimpleNamespace(
            successor=SimpleNamespace(
                prior_checkpoint=SimpleNamespace(checkpoint_id=UUID(int=parent)),
                checkpoint_id=UUID(int=child),
                application_id=UUID(int=application),
            ),
            report=SimpleNamespace(artifact_id=UUID(int=report)),
        )

    chain = [edge(1, 2, 10, 20)]
    if mode == "self_cycle":
        chain.append(edge(2, 2, 11, 21))
    elif mode == "detached_cycle":
        chain.extend((edge(3, 4, 11, 21), edge(4, 3, 12, 22)))
    elif mode == "report_reuse":
        chain.append(edge(2, 3, 10, 21))
    elif mode == "application_reuse":
        chain.append(edge(2, 3, 11, 20))
    else:
        chain.append(edge(1, 3, 11, 21))
    with pytest.raises(p3.ManualPaperAccountAuthorityError):
        p3._ordered_chain(UUID(int=1), tuple(chain))


@pytest.mark.parametrize("target", ["root", "anchor", "genesis", "snapshot"])
def test_reparse_objects_are_rejected_at_every_read_boundary(
    tmp_path, one, monkeypatch, target
):
    authority, root, capture = setup(tmp_path, one)
    selected = {
        "root": root,
        "anchor": root / p3.MANUAL_PAPER_ACCOUNT_ANCHOR_FILENAME,
        "genesis": next(root.glob("paper-account-genesis-*/*.json")),
        "snapshot": next(capture.iterdir()),
    }[target]
    original = Path.lstat

    def lstat(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == selected:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
        return info

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(p3.ManualPaperAccountAuthorityError, match="UNSAFE"):
        authority.preflight()


def test_lock_scope_is_thread_bound_and_invalidated_on_exception(tmp_path, one):
    import threading

    authority, _, _ = setup(tmp_path, one)
    failures = []
    with pytest.raises(RuntimeError, match="caller failure"):
        with authority.locked_revalidate() as scope:

            def other_thread():
                try:
                    _ = scope.evidence
                except p3.ManualPaperAccountAuthorityError as error:
                    failures.append(str(error))

            thread = threading.Thread(target=other_thread)
            thread.start()
            thread.join(2)
            assert not thread.is_alive()
            assert failures == ["P3_LOCK_SCOPE_INVALID"]
            raise RuntimeError("caller failure")
    with pytest.raises(p3.ManualPaperAccountAuthorityError, match="INACTIVE"):
        _ = scope.acquisition


def test_real_test_only_c1_capability_is_not_production_authority():
    from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
    from trading_bot.runtime.windows_authority import WindowsAuthorityBootstrap
    from trading_bot.runtime.windows_authority_schema import (
        PRODUCTION_SCHEMA_ARTIFACT_SHA256,
        PRODUCTION_SCHEMA_ID,
        PRODUCTION_SCHEMA_VERSION,
        ProductionAuthorityEvidence,
    )
    from trading_bot.runtime.windows_authority_validation import (
        acquire_validated_production_authority_for_test,
    )

    bootstrap = WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=1,
        machine_authority_id=str(ACCOUNT),
        authority_epoch_id=str(UUID(int=2)),
        signing_key_id="test-key/v1",
        approved_account_sid=SID,
        database_path=r"F:\AITradingBot\Authority\authority.sqlite3",
        output_root=r"F:\AITradingBot\Authority\capture-output",
        provider_id=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        permitted_provider_operation=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
        authority_policy_version="authority-policy/v1",
        claim_policy_version="claim-policy/v1",
        database_identity_digest="11" * 32,
    )
    capability = acquire_validated_production_authority_for_test(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        production_evidence=ProductionAuthorityEvidence(
            database_path=bootstrap.database_path,
            schema_id=PRODUCTION_SCHEMA_ID,
            schema_version=PRODUCTION_SCHEMA_VERSION,
            schema_digest=PRODUCTION_SCHEMA_ARTIFACT_SHA256,
            metadata_digest="33" * 32,
            migration_id="migration/v1",
            release_manifest_digest="44" * 32,
            sqlite_build_manifest_digest="55" * 32,
        ),
    )
    with pytest.raises(p3.ManualPaperAccountAuthorityError, match="GENUINE_C1"):
        p3.WindowsManualPaperAccountAuthority(capability)
