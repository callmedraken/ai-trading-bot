"""Focused read-only paper-operation inspection and CLI coverage."""

from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
from tests.cli.test_checkpoint_transition import _snapshot_bytes, _transition_bytes
from tests.runtime.test_checkpointed_verified_snapshot_execution import (
    _checkpoint_verification,
)
from tests.runtime.test_paper_account_lineage_verification import _two_edges
from tests.runtime.test_verified_snapshot_preparation import calendar

from trading_bot.cli.checkpoint_transition import run_checkpointed_cycle
from trading_bot.cli.checkpoint_transition_config import (
    parse_checkpoint_transition_config,
)
from trading_bot.cli.paper_operation import main
from trading_bot.cli.paper_operation_config import (
    PaperOperationInputVerificationCode,
    PaperOperationInputVerificationError,
    VerifiedPaperOperationInputs,
    adapt_verified_paper_operation_execution_inputs,
    load_verified_paper_operation_inputs,
)
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    inspect_paper_operation_root,
)
from trading_bot.market_data import verify_daily_snapshot
from trading_bot.runtime import (
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactKind,
    PaperAccountLineageVerificationStatus,
    PaperOperationArtifactEvidence,
    PaperOperationDiagnosticCode,
    PaperOperationOutcome,
    PaperOperationReceipt,
    PaperOperationStatus,
    VerifiedPaperOperationExecutionInputs,
    create_paper_operation_intent,
    serialize_paper_operation_receipt,
    verify_paper_account_lineage,
)

CALLER_KEY = UUID("4cc8a4ad-f2e9-52e8-a9f8-bf6771b36830")


@dataclass(frozen=True, slots=True)
class _Fixture:
    config_path: Path
    operation_root: Path
    inputs: VerifiedPaperOperationExecutionInputs
    cli_inputs: VerifiedPaperOperationInputs
    checkpoint_path: Path
    snapshot_path: Path
    cycle_path: Path


def _entry(path: Path, artifact: PaperAccountLineageArtifact) -> dict[str, object]:
    return {
        "artifact_id": str(artifact.artifact_id),
        "path": path.name,
        "sha256": artifact.sha256,
        "byte_length": artifact.byte_length,
    }


def _write_artifact(
    root: Path,
    artifact: PaperAccountLineageArtifact,
) -> Path:
    path = root / f"{artifact.kind.value.lower()}-{artifact.artifact_id}.json"
    path.write_bytes(artifact.payload)
    return path


def _setup_from_lineage(
    tmp_path: Path,
    *,
    genesis: PaperAccountLineageArtifact,
    terminal_id: UUID,
    successors: tuple[PaperAccountLineageArtifact, ...] = (),
    reports: tuple[PaperAccountLineageArtifact, ...] = (),
    lineage_snapshots: tuple[PaperAccountLineageArtifact, ...] = (),
    snapshot_payload: bytes | None = None,
    cycle_payload: bytes | None = None,
) -> _Fixture:
    tmp_path.mkdir(parents=True, exist_ok=True)
    dependencies = tmp_path / "dependencies"
    operation_root = tmp_path / "operation-root"
    dependencies.mkdir()
    operation_root.mkdir()
    paths = {
        artifact.artifact_id: _write_artifact(dependencies, artifact)
        for artifact in (
            genesis,
            *successors,
            *reports,
            *lineage_snapshots,
        )
    }
    prior = verify_paper_account_lineage(
        genesis,
        terminal_id,
        successors,
        reports,
        lineage_snapshots,
        calendar(),
    )
    assert prior.status is PaperAccountLineageVerificationStatus.PASS
    assert prior.evidence is not None
    manifest_tree = {
        "schema_version": 1,
        "genesis_checkpoint": _entry(paths[genesis.artifact_id], genesis),
        "terminal_checkpoint_id": str(terminal_id),
        "successor_checkpoints": [
            _entry(paths[item.artifact_id], item) for item in successors
        ],
        "cycle_reports": [_entry(paths[item.artifact_id], item) for item in reports],
        "snapshots": [
            _entry(paths[item.artifact_id], item) for item in lineage_snapshots
        ],
    }
    manifest_path = dependencies / "lineage-manifest.json"
    manifest_payload = json.dumps(manifest_tree, separators=(",", ":")).encode()
    manifest_path.write_bytes(manifest_payload)
    retained_snapshot = (
        _snapshot_bytes() if snapshot_payload is None else snapshot_payload
    )
    snapshot_verification = verify_daily_snapshot(retained_snapshot, calendar())
    assert snapshot_verification.snapshot is not None
    snapshot = snapshot_verification.snapshot
    snapshot_path = dependencies / "snapshot.json"
    snapshot_path.write_bytes(retained_snapshot)
    retained_cycle = _transition_bytes() if cycle_payload is None else cycle_payload
    cycle = parse_checkpoint_transition_config(retained_cycle)
    cycle_path = dependencies / "cycle.json"
    cycle_path.write_bytes(retained_cycle)
    terminal_artifact = next(
        item for item in (genesis, *successors) if item.artifact_id == terminal_id
    )
    config_tree = {
        "schema_version": 1,
        "caller_idempotency_key": str(CALLER_KEY),
        "prior_lineage_manifest": {
            "artifact_id": str(prior.evidence.evidence_id),
            "path": manifest_path.name,
            "sha256": sha256(manifest_payload).hexdigest(),
            "byte_length": len(manifest_payload),
        },
        "terminal_checkpoint": _entry(
            paths[terminal_artifact.artifact_id],
            terminal_artifact,
        ),
        "completed_snapshot": {
            "artifact_id": str(snapshot.snapshot_id),
            "path": snapshot_path.name,
            "sha256": sha256(retained_snapshot).hexdigest(),
            "byte_length": len(retained_snapshot),
        },
        "cycle_configuration": {
            "artifact_id": str(cycle.request.request_id),
            "path": cycle_path.name,
            "sha256": sha256(retained_cycle).hexdigest(),
            "byte_length": len(retained_cycle),
        },
    }
    config_path = dependencies / "operation.json"
    config_path.write_bytes(json.dumps(config_tree, separators=(",", ":")).encode())
    cli_inputs = load_verified_paper_operation_inputs(config_path, calendar())
    inputs = adapt_verified_paper_operation_execution_inputs(cli_inputs)
    return _Fixture(
        config_path,
        operation_root,
        inputs,
        cli_inputs,
        paths[terminal_artifact.artifact_id],
        snapshot_path,
        cycle_path,
    )


def _setup(tmp_path: Path, *, cycle_payload: bytes | None = None) -> _Fixture:
    verification, payload = _checkpoint_verification()
    checkpoint = verification.checkpoint
    assert checkpoint is not None
    genesis = PaperAccountLineageArtifact(
        PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
        checkpoint.checkpoint_id,
        payload,
        sha256(payload).hexdigest(),
        len(payload),
    )
    return _setup_from_lineage(
        tmp_path,
        genesis=genesis,
        terminal_id=checkpoint.checkpoint_id,
        cycle_payload=cycle_payload,
    )


def _artifact(kind, artifact_id, payload) -> PaperAccountLineageArtifact:
    return PaperAccountLineageArtifact(
        kind,
        artifact_id,
        payload,
        sha256(payload).hexdigest(),
        len(payload),
    )


def _install_completed_receipt(
    fixture: _Fixture,
    *,
    transition_cycle_path: Path | None = None,
    configuration_evidence: PaperOperationArtifactEvidence | None = None,
) -> tuple[PaperOperationReceipt, Path]:
    cycle_path = (
        fixture.cycle_path if transition_cycle_path is None else transition_cycle_path
    )
    transition = run_checkpointed_cycle(
        checkpoint_path=fixture.checkpoint_path,
        snapshot_path=fixture.snapshot_path,
        config_path=cycle_path,
        output_directory=fixture.operation_root,
    )
    report_payload = transition.report_path.read_bytes()
    checkpoint_payload = transition.checkpoint_path.read_bytes()
    snapshot_payload = fixture.snapshot_path.read_bytes()
    report_artifact = _artifact(
        PaperAccountLineageArtifactKind.CYCLE_REPORT,
        transition.report.report_id,
        report_payload,
    )
    successor_artifact = _artifact(
        PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
        transition.successor.checkpoint_id,
        checkpoint_payload,
    )
    snapshot_artifact = _artifact(
        PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
        transition.result.snapshot_reference.snapshot_id,
        snapshot_payload,
    )
    successor_lineage = verify_paper_account_lineage(
        fixture.inputs.prior_genesis_checkpoint,
        transition.successor.checkpoint_id,
        (*fixture.inputs.prior_successor_checkpoints, successor_artifact),
        (*fixture.inputs.prior_cycle_reports, report_artifact),
        (*fixture.inputs.prior_snapshots, snapshot_artifact),
        calendar(),
    )
    assert successor_lineage.evidence is not None
    retained_configuration = (
        fixture.inputs.intent.cycle_configuration_artifact
        if configuration_evidence is None
        else configuration_evidence
    )
    intent = create_paper_operation_intent(
        fixture.inputs.intent.caller_idempotency_key,
        fixture.inputs.intent.prior_lineage_evidence,
        fixture.inputs.intent.terminal_checkpoint_artifact,
        fixture.inputs.intent.completed_snapshot_artifact,
        retained_configuration,
        transition.report.evidence.request,
    )
    receipt = PaperOperationReceipt(
        1,
        intent.operation_id,
        intent,
        PaperOperationStatus.COMPLETED,
        PaperOperationOutcome(transition.result.status.value),
        PaperOperationDiagnosticCode.NONE,
        intent.prior_lineage_evidence,
        successor_lineage.evidence,
        successor_lineage.evidence.report_artifacts[-1],
        successor_lineage.evidence.checkpoint_artifacts[-1],
        transition.result.application_id,
        transition.result.result_id,
    )
    receipt_directory = (
        fixture.operation_root
        / "paper-operations"
        / f"paper-operation-{receipt.receipt_id}"
    )
    receipt_directory.mkdir(parents=True)
    receipt_path = (
        receipt_directory / f"paper-operation-receipt-{receipt.receipt_id}.json"
    )
    receipt_path.write_bytes(serialize_paper_operation_receipt(receipt))
    return receipt, receipt_path


def _changed_request_cycle(fixture: _Fixture) -> Path:
    tree = json.loads(fixture.cycle_path.read_bytes())
    tree["request_id"] = "f58efbca-996d-5547-a10a-df9fbf620712"
    path = fixture.cycle_path.parent / "changed-cycle.json"
    path.write_bytes(json.dumps(tree, separators=(",", ":")).encode())
    return path


def _failed_fixture(tmp_path: Path) -> _Fixture:
    checkpoint_verification, checkpoint_payload = _checkpoint_verification(
        cash="2000",
        positions=(),
    )
    checkpoint = checkpoint_verification.checkpoint
    assert checkpoint is not None
    genesis = _artifact(
        PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
        checkpoint.checkpoint_id,
        checkpoint_payload,
    )
    snapshot_payload = _snapshot_bytes()
    cycle_tree = json.loads(_transition_bytes())
    cycle_tree["target"]["quantities"][1]["quantity"] = "9"
    cycle_tree["target"]["target_cash"] = "173"
    cycle_tree["open_references"][1]["caller_asserted_open_reference_price"] = "300"
    limits = cycle_tree["policies"]["risk_limits"]
    limits["max_position_percent"] = "1"
    limits["max_total_exposure_percent"] = "1"
    limits["minimum_cash_reserve_percent"] = "0"
    cycle_payload = json.dumps(cycle_tree, separators=(",", ":")).encode()
    return _setup_from_lineage(
        tmp_path,
        genesis=genesis,
        terminal_id=checkpoint.checkpoint_id,
        snapshot_payload=snapshot_payload,
        cycle_payload=cycle_payload,
    )


def test_verified_inputs_support_multi_edge_terminal_predecessor(
    tmp_path: Path,
) -> None:
    lineage = _two_edges()
    fixture = _setup_from_lineage(
        tmp_path,
        genesis=lineage.genesis,
        terminal_id=lineage.terminal_id,
        successors=lineage.successors,
        reports=lineage.reports,
        lineage_snapshots=lineage.snapshots,
    )

    assert fixture.inputs.intent.prior_lineage_evidence.edge_count == 2
    assert fixture.inputs.verified_prior.sequence == 2


@pytest.mark.parametrize(
    ("reference", "replacement", "code"),
    (
        (
            "terminal_checkpoint",
            {"sha256": "0" * 64},
            PaperOperationInputVerificationCode.TERMINAL_CHECKPOINT_MISMATCH,
        ),
        (
            "completed_snapshot",
            {"artifact_id": "00000000-0000-0000-0000-000000000001"},
            PaperOperationInputVerificationCode.SNAPSHOT_EVIDENCE_MISMATCH,
        ),
        (
            "cycle_configuration",
            {"artifact_id": "00000000-0000-0000-0000-000000000001"},
            PaperOperationInputVerificationCode.CYCLE_CONFIGURATION_ID_MISMATCH,
        ),
    ),
)
def test_explicit_dependency_evidence_must_match(
    tmp_path: Path,
    reference: str,
    replacement: dict[str, object],
    code: PaperOperationInputVerificationCode,
) -> None:
    fixture = _setup(tmp_path)
    tree = json.loads(fixture.config_path.read_bytes())
    tree[reference].update(replacement)
    fixture.config_path.write_bytes(json.dumps(tree, separators=(",", ":")).encode())

    with pytest.raises(PaperOperationInputVerificationError) as raised:
        load_verified_paper_operation_inputs(fixture.config_path, calendar())

    assert raised.value.code is code


def test_pending_state_is_path_independent_across_filesystem_roots(
    tmp_path: Path,
) -> None:
    first = _setup(tmp_path / "first")
    second = _setup(tmp_path / "second")

    first_result = inspect_paper_operation_root(
        first.operation_root,
        first.inputs,
    )
    second_result = inspect_paper_operation_root(
        second.operation_root,
        second.inputs,
    )

    assert first_result.classification is PaperOperationClassification.PENDING
    assert second_result.classification is PaperOperationClassification.PENDING
    assert first_result.operation_id == second_result.operation_id
    assert first_result.diagnostics == (PaperOperationInspectionCode.PENDING,)


def test_matching_fully_verified_receipt_is_already_applied(tmp_path: Path) -> None:
    fixture = _setup(tmp_path)
    receipt, receipt_path = _install_completed_receipt(fixture)

    result = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationClassification.ALREADY_APPLIED
    assert result.operation_id == receipt.receipt_id
    assert result.receipt_path == receipt_path


def test_fully_verified_same_key_changed_intent_is_conflicting(
    tmp_path: Path,
) -> None:
    fixture = _setup(tmp_path)
    changed_cycle = _changed_request_cycle(fixture)
    receipt, _ = _install_completed_receipt(
        fixture,
        transition_cycle_path=changed_cycle,
        configuration_evidence=fixture.inputs.intent.cycle_configuration_artifact,
    )
    assert receipt.receipt_id != fixture.inputs.intent.operation_id

    result = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationClassification.CONFLICTING
    assert result.diagnostics == (
        PaperOperationInspectionCode.CALLER_IDEMPOTENCY_CONFLICT,
    )


def test_foreign_same_key_without_dependencies_is_blocked(tmp_path: Path) -> None:
    fixture = _setup(tmp_path)
    changed_evidence = PaperOperationArtifactEvidence("f" * 64, 17)
    foreign_intent = create_paper_operation_intent(
        fixture.inputs.intent.caller_idempotency_key,
        fixture.inputs.intent.prior_lineage_evidence,
        fixture.inputs.intent.terminal_checkpoint_artifact,
        fixture.inputs.intent.completed_snapshot_artifact,
        changed_evidence,
        fixture.inputs.request,
    )
    foreign = PaperOperationReceipt(
        1,
        foreign_intent.operation_id,
        foreign_intent,
        PaperOperationStatus.FAILED,
        None,
        PaperOperationDiagnosticCode.RECONCILIATION_FAILURE,
        foreign_intent.prior_lineage_evidence,
        None,
        None,
        None,
        fixture.inputs.application_id,
        None,
    )
    directory = (
        fixture.operation_root
        / "paper-operations"
        / f"paper-operation-{foreign.receipt_id}"
    )
    directory.mkdir(parents=True)
    (directory / f"paper-operation-receipt-{foreign.receipt_id}.json").write_bytes(
        serialize_paper_operation_receipt(foreign)
    )

    result = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationClassification.BLOCKED
    assert result.diagnostics == (
        PaperOperationInspectionCode.FOREIGN_RECEIPT_DEPENDENCIES_UNAVAILABLE,
    )


def test_valid_failed_receipt_is_verified_and_blocked(tmp_path: Path) -> None:
    fixture = _failed_fixture(tmp_path)
    intent = fixture.inputs.intent
    receipt = PaperOperationReceipt(
        1,
        intent.operation_id,
        intent,
        PaperOperationStatus.FAILED,
        None,
        PaperOperationDiagnosticCode.INSUFFICIENT_CASH,
        intent.prior_lineage_evidence,
        None,
        None,
        None,
        fixture.inputs.application_id,
        None,
    )
    directory = (
        fixture.operation_root
        / "paper-operations"
        / f"paper-operation-{receipt.receipt_id}"
    )
    directory.mkdir(parents=True)
    receipt_path = directory / f"paper-operation-receipt-{receipt.receipt_id}.json"
    receipt_path.write_bytes(serialize_paper_operation_receipt(receipt))

    result = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationClassification.BLOCKED
    assert result.receipt_path == receipt_path
    assert result.diagnostics == (PaperOperationInspectionCode.VALID_FAILED_RECEIPT,)


def test_verified_other_successor_makes_requested_terminal_stale(
    tmp_path: Path,
) -> None:
    fixture = _setup(tmp_path)
    changed_cycle = _changed_request_cycle(fixture)
    run_checkpointed_cycle(
        checkpoint_path=fixture.checkpoint_path,
        snapshot_path=fixture.snapshot_path,
        config_path=changed_cycle,
        output_directory=fixture.operation_root,
    )

    result = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationClassification.BLOCKED
    assert result.diagnostics == (
        PaperOperationInspectionCode.STALE_TERMINAL_CHECKPOINT,
    )


def test_verified_requested_transition_without_receipt_is_crash_left(
    tmp_path: Path,
) -> None:
    fixture = _setup(tmp_path)
    run_checkpointed_cycle(
        checkpoint_path=fixture.checkpoint_path,
        snapshot_path=fixture.snapshot_path,
        config_path=fixture.cycle_path,
        output_directory=fixture.operation_root,
    )

    result = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationClassification.BLOCKED
    assert result.diagnostics == (
        PaperOperationInspectionCode.FINALIZED_TRANSITION_WITHOUT_RECEIPT,
    )


def test_unverifiable_requested_transition_is_invalid(tmp_path: Path) -> None:
    fixture = _setup(tmp_path)
    transition = run_checkpointed_cycle(
        checkpoint_path=fixture.checkpoint_path,
        snapshot_path=fixture.snapshot_path,
        config_path=fixture.cycle_path,
        output_directory=fixture.operation_root,
    )
    transition.report_path.write_bytes(transition.report_path.read_bytes() + b" ")

    result = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationClassification.BLOCKED
    assert result.diagnostics == (PaperOperationInspectionCode.INVALID_TRANSITION,)


@pytest.mark.parametrize(
    ("name", "code"),
    (
        (
            ".paper-account-transition-00000000-0000-0000-0000-000000000001.staging",
            PaperOperationInspectionCode.TRANSITION_STAGING_EXISTS,
        ),
        (
            ".paper-operation-00000000-0000-0000-0000-000000000001.staging",
            PaperOperationInspectionCode.OPERATION_STAGING_EXISTS,
        ),
    ),
)
def test_incomplete_staging_is_blocked(
    tmp_path: Path,
    name: str,
    code: PaperOperationInspectionCode,
) -> None:
    fixture = _setup(tmp_path)
    parent = (
        fixture.operation_root
        if name.startswith(".paper-account")
        else fixture.operation_root / "paper-operations"
    )
    parent.mkdir(exist_ok=True)
    (parent / name).mkdir()

    result = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationClassification.BLOCKED
    assert result.diagnostics == (code,)


def test_invalid_receipt_is_never_authority(tmp_path: Path) -> None:
    fixture = _setup(tmp_path)
    directory = (
        fixture.operation_root
        / "paper-operations"
        / f"paper-operation-{fixture.inputs.intent.operation_id}"
    )
    directory.mkdir(parents=True)
    (
        directory / f"paper-operation-receipt-{fixture.inputs.intent.operation_id}.json"
    ).write_bytes(b"{}\n")

    result = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationClassification.BLOCKED
    assert result.diagnostics == (PaperOperationInspectionCode.INVALID_RECEIPT,)


def test_malformed_foreign_receipt_is_not_skipped(tmp_path: Path) -> None:
    fixture = _setup(tmp_path)
    foreign_id = UUID("00000000-0000-0000-0000-000000000009")
    directory = (
        fixture.operation_root / "paper-operations" / f"paper-operation-{foreign_id}"
    )
    directory.mkdir(parents=True)
    (directory / f"paper-operation-receipt-{foreign_id}.json").write_bytes(
        b'{"schema_version":1}\n'
    )

    result = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationClassification.BLOCKED
    assert result.diagnostics == (PaperOperationInspectionCode.INVALID_RECEIPT,)


def test_unexpected_operation_layout_and_bounded_enumeration_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    operations = fixture.operation_root / "paper-operations"
    operations.mkdir()
    (operations / "unexpected.txt").write_bytes(b"x")
    malformed = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)
    assert malformed.diagnostics == (
        PaperOperationInspectionCode.MALFORMED_OPERATION_LAYOUT,
    )

    operations.rename(fixture.operation_root / "ignored")
    (fixture.operation_root / "one").write_bytes(b"1")
    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_inspection.MAX_PAPER_OPERATION_ROOT_ENTRIES",
        0,
    )
    bounded = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)
    assert bounded.diagnostics == (
        PaperOperationInspectionCode.ENUMERATION_LIMIT_EXCEEDED,
    )


def test_casefold_collision_and_linked_root_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_inspection._enumerate",
        lambda path, maximum: ("paper-operations", "PAPER-OPERATIONS"),
    )
    collision = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)
    assert collision.diagnostics == (PaperOperationInspectionCode.CASEFOLD_COLLISION,)
    monkeypatch.undo()

    real = tmp_path / "real-root"
    linked = tmp_path / "linked-root"
    real.mkdir()
    try:
        os.symlink(real, linked, target_is_directory=True)
    except OSError:
        return
    linked_result = inspect_paper_operation_root(linked, fixture.inputs)
    assert linked_result.diagnostics == (
        PaperOperationInspectionCode.UNSAFE_OPERATION_ROOT,
    )


def test_reparse_point_and_parent_identity_change_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_inspection._reparse",
        lambda value: True,
    )
    reparse = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)
    assert reparse.diagnostics == (PaperOperationInspectionCode.UNSAFE_OPERATION_ROOT,)
    monkeypatch.undo()

    calls = 0

    def changing_parent(parent) -> None:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise ValueError("changed")

    monkeypatch.setattr(
        "trading_bot.cli.paper_operation_inspection._require_parent_identity",
        changing_parent,
    )
    changed = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)
    assert changed.diagnostics == (PaperOperationInspectionCode.UNSAFE_OPERATION_ROOT,)


def test_pending_inspection_has_no_write_runtime_or_external_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(tmp_path)
    original_open = Path.open

    def guarded_open(self, mode="r", *args, **kwargs):
        assert not any(flag in mode for flag in ("w", "a", "x", "+"))
        return original_open(self, mode, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("forbidden dependency")

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(Path, "unlink", forbidden)
    monkeypatch.setattr(Path, "rename", forbidden)
    monkeypatch.setattr(os, "mkdir", forbidden)
    monkeypatch.setattr(os, "makedirs", forbidden)
    monkeypatch.setattr(os, "rename", forbidden)
    monkeypatch.setattr(os, "replace", forbidden)
    monkeypatch.setattr(os, "remove", forbidden)
    monkeypatch.setattr(os, "rmdir", forbidden)
    monkeypatch.setattr(os, "unlink", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(
        "trading_bot.runtime.checkpointed_paper_cycle_report."
        "execute_checkpointed_verified_snapshot_paper_cycle",
        forbidden,
    )
    monkeypatch.setattr(
        "trading_bot.market_data.AlpacaDailySnapshotProvider.fetch",
        forbidden,
    )
    result = inspect_paper_operation_root(fixture.operation_root, fixture.inputs)

    assert result.classification is PaperOperationClassification.PENDING


def test_cli_requires_inspect_only_and_reports_pending(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _setup(tmp_path)
    unsupported = main(
        [
            "--config",
            str(fixture.config_path),
            "--operation-root",
            str(fixture.operation_root),
        ]
    )
    assert unsupported == 2
    capsys.readouterr()

    exit_code = main(
        [
            "--config",
            str(fixture.config_path),
            "--operation-root",
            str(fixture.operation_root),
            "--inspect-only",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "classification: PENDING" in captured.out
    assert str(fixture.inputs.intent.operation_id) in captured.out
    assert "receipt path:" not in captured.out


def test_cli_exit_codes_cover_configuration_verification_conflict_and_incomplete(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = main(
        [
            "--config",
            str(tmp_path / "missing.json"),
            "--operation-root",
            str(tmp_path),
            "--inspect-only",
        ]
    )
    assert missing == 3
    capsys.readouterr()

    invalid = _setup(tmp_path / "invalid")
    operation = invalid.inputs.intent.operation_id
    receipt_directory = (
        invalid.operation_root / "paper-operations" / f"paper-operation-{operation}"
    )
    receipt_directory.mkdir(parents=True)
    (receipt_directory / f"paper-operation-receipt-{operation}.json").write_bytes(
        b"{}\n"
    )
    invalid_exit = main(
        [
            "--config",
            str(invalid.config_path),
            "--operation-root",
            str(invalid.operation_root),
            "--inspect-only",
        ]
    )
    assert invalid_exit == 4
    capsys.readouterr()

    stale = _setup(tmp_path / "stale")
    changed_cycle = _changed_request_cycle(stale)
    run_checkpointed_cycle(
        checkpoint_path=stale.checkpoint_path,
        snapshot_path=stale.snapshot_path,
        config_path=changed_cycle,
        output_directory=stale.operation_root,
    )
    stale_exit = main(
        [
            "--config",
            str(stale.config_path),
            "--operation-root",
            str(stale.operation_root),
            "--inspect-only",
        ]
    )
    assert stale_exit == 5
    capsys.readouterr()

    incomplete = _setup(tmp_path / "incomplete")
    (
        incomplete.operation_root
        / ".paper-account-transition-00000000-0000-0000-0000-000000000001.staging"
    ).mkdir()
    incomplete_exit = main(
        [
            "--config",
            str(incomplete.config_path),
            "--operation-root",
            str(incomplete.operation_root),
            "--inspect-only",
        ]
    )
    assert incomplete_exit == 8
