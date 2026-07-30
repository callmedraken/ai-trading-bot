"""Focused authoritative local lineage-head publication and verification."""

from __future__ import annotations

import json
import os
import socket
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
from tests.cli.test_checkpoint_transition import _no_action_transition_bytes
from tests.cli.test_paper_operation_inspection import _setup
from tests.runtime.test_paper_account_lineage_verification import _two_edges
from tests.runtime.test_verified_snapshot_preparation import calendar

from trading_bot.cli.local_lineage_head import (
    CURRENT_HEAD_FILENAME,
    AtomicPointerReplacementError,
    LocalLineageHeadClassification,
    LocalLineageHeadDiagnosticCode,
    advance_local_lineage_head,
    initialize_local_lineage_head,
    verify_local_lineage_head,
)
from trading_bot.cli.paper_operation_execution import execute_paper_operation_once
from trading_bot.runtime import (
    LineageHeadAdvancementCauseEvidence,
    LineageHeadAdvancementCauseKind,
    LineageHeadRecordReference,
    LineageHeadTerminalCheckpointEvidence,
    LineageManifestEvidence,
    LocalLineageHeadReference,
    PaperOperationDiagnosticCode,
    PaperOperationReceipt,
    PaperOperationStatus,
    create_paper_account_lineage_head_record,
    parse_checkpointed_paper_cycle_report,
    parse_local_lineage_head_reference,
    serialize_local_lineage_head_reference,
    serialize_paper_account_lineage_head_record,
    serialize_paper_operation_receipt,
    verify_paper_account_lineage,
)

EPOCH_ID = UUID("e1a615c4-4ca8-5e28-9362-51f081c2e167")


def _reference(artifact_id: UUID, path: Path, payload: bytes) -> dict[str, object]:
    return {
        "artifact_id": str(artifact_id),
        "path": str(path.resolve()),
        "sha256": sha256(payload).hexdigest(),
        "byte_length": len(payload),
    }


def _write_manifest(
    path: Path,
    *,
    genesis_id: UUID,
    genesis_path: Path,
    terminal_id: UUID,
    successor: tuple[UUID, Path] | None = None,
    report: tuple[UUID, Path] | None = None,
    snapshot: tuple[UUID, Path] | None = None,
) -> Path:
    genesis_payload = genesis_path.read_bytes()
    tree = {
        "schema_version": 1,
        "genesis_checkpoint": _reference(
            genesis_id,
            genesis_path,
            genesis_payload,
        ),
        "terminal_checkpoint_id": str(terminal_id),
        "successor_checkpoints": [],
        "cycle_reports": [],
        "snapshots": [],
    }
    for field, retained in (
        ("successor_checkpoints", successor),
        ("cycle_reports", report),
        ("snapshots", snapshot),
    ):
        if retained is not None:
            artifact_id, artifact_path = retained
            tree[field].append(
                _reference(
                    artifact_id,
                    artifact_path,
                    artifact_path.read_bytes(),
                )
            )
    path.write_bytes(json.dumps(tree, sort_keys=True, separators=(",", ":")).encode())
    return path


def _initialized_fixture(tmp_path: Path):
    fixture = _setup(tmp_path / "operation")
    authority_root = tmp_path / "authority"
    authority_root.mkdir()
    genesis = fixture.inputs.lineage_manifest.genesis_checkpoint
    manifest = _write_manifest(
        tmp_path / "genesis-manifest.json",
        genesis_id=genesis.artifact_id,
        genesis_path=fixture.checkpoint_path,
        terminal_id=genesis.artifact_id,
    )
    initialized = initialize_local_lineage_head(
        authority_root,
        EPOCH_ID,
        manifest,
    )
    assert initialized.classification is LocalLineageHeadClassification.INITIALIZED
    return fixture, authority_root


def _completed_advancement_inputs(tmp_path: Path):
    fixture, authority_root = _initialized_fixture(tmp_path)
    expected = tmp_path / "expected-head.json"
    expected.write_bytes((authority_root / CURRENT_HEAD_FILENAME).read_bytes())
    execution = execute_paper_operation_once(
        fixture.operation_root,
        fixture.inputs,
    )
    assert execution.transition_path is not None
    assert execution.receipt_path is not None
    assert execution.cycle_result_id is not None
    assert execution.successor_checkpoint_id is not None
    report_path = (
        execution.transition_path
        / f"checkpointed-paper-cycle-report-{execution.cycle_result_id}.json"
    )
    report = parse_checkpointed_paper_cycle_report(report_path.read_bytes())
    successor_path = (
        execution.transition_path
        / f"paper-account-checkpoint-{execution.successor_checkpoint_id}.json"
    )
    genesis = fixture.inputs.lineage_manifest.genesis_checkpoint
    manifest = _write_manifest(
        tmp_path / "successor-manifest.json",
        genesis_id=genesis.artifact_id,
        genesis_path=fixture.checkpoint_path,
        terminal_id=execution.successor_checkpoint_id,
        successor=(execution.successor_checkpoint_id, successor_path),
        report=(report.report_id, report_path),
        snapshot=(
            fixture.inputs.intent.completed_snapshot_artifact.artifact_id,
            fixture.snapshot_path,
        ),
    )
    return {
        "fixture": fixture,
        "authority_root": authority_root,
        "expected": expected,
        "manifest": manifest,
        "report": report_path,
        "successor": successor_path,
        "receipt": execution.receipt_path,
    }


def _advance(values, *, replacer=None):
    fixture = values["fixture"]
    return advance_local_lineage_head(
        values["authority_root"],
        expected_head_reference_path=values["expected"],
        lineage_manifest_path=values["manifest"],
        prior_checkpoint_path=fixture.checkpoint_path,
        cycle_report_path=values["report"],
        snapshot_path=fixture.snapshot_path,
        successor_checkpoint_path=values["successor"],
        completed_receipt_path=values["receipt"],
        cycle_configuration_path=fixture.cycle_path,
        replacer=replacer,
    )


def test_genesis_initialization_and_read_only_complete_verification(
    tmp_path: Path,
) -> None:
    _, authority_root = _initialized_fixture(tmp_path)
    inventory = sorted(
        str(item.relative_to(authority_root)) for item in authority_root.rglob("*")
    )

    result = verify_local_lineage_head(authority_root)

    assert result.classification is LocalLineageHeadClassification.PASS
    assert result.authority is not None
    assert result.authority.pointer.generation == 0
    assert result.authority.current_record.terminal_checkpoint.sequence == 0
    assert inventory == sorted(
        str(item.relative_to(authority_root)) for item in authority_root.rglob("*")
    )


def test_existing_safe_root_without_pointer_reports_pointer_missing(
    tmp_path: Path,
) -> None:
    authority_root = tmp_path / "authority"
    authority_root.mkdir()

    result = verify_local_lineage_head(authority_root)

    assert result.classification is LocalLineageHeadClassification.BLOCKED
    assert result.diagnostic is LocalLineageHeadDiagnosticCode.POINTER_MISSING


def test_exact_one_edge_completed_operation_advances_head(tmp_path: Path) -> None:
    values = _completed_advancement_inputs(tmp_path)

    result = _advance(values)

    assert result.classification is LocalLineageHeadClassification.ADVANCED
    assert result.authority is not None
    assert result.authority.pointer.generation == 1
    assert len(result.authority.records) == 2
    assert (
        verify_local_lineage_head(values["authority_root"]).classification
        is LocalLineageHeadClassification.PASS
    )


def test_stale_expected_pointer_does_not_publish_another_generation(
    tmp_path: Path,
) -> None:
    values = _completed_advancement_inputs(tmp_path)
    first = _advance(values)
    assert first.classification is LocalLineageHeadClassification.ADVANCED

    repeated = _advance(values)

    assert repeated.classification is LocalLineageHeadClassification.STALE_EXPECTED_HEAD
    assert repeated.diagnostic is LocalLineageHeadDiagnosticCode.STALE_EXPECTED_HEAD
    verified = verify_local_lineage_head(values["authority_root"])
    assert verified.authority is not None
    assert verified.authority.pointer.generation == 1


def test_retained_newer_expected_pointer_detects_installed_rollback(
    tmp_path: Path,
) -> None:
    values = _completed_advancement_inputs(tmp_path)
    old_pointer = values["expected"].read_bytes()
    first = _advance(values)
    assert first.classification is LocalLineageHeadClassification.ADVANCED
    newer_expected = tmp_path / "newer-expected.json"
    newer_expected.write_bytes(
        (values["authority_root"] / CURRENT_HEAD_FILENAME).read_bytes()
    )
    (values["authority_root"] / CURRENT_HEAD_FILENAME).write_bytes(old_pointer)
    values["expected"] = newer_expected

    result = _advance(values)

    assert result.classification is LocalLineageHeadClassification.CONFLICTING
    assert result.diagnostic is LocalLineageHeadDiagnosticCode.ROLLBACK


def test_stale_divergent_explicit_successor_is_a_fork(tmp_path: Path) -> None:
    values = _completed_advancement_inputs(tmp_path / "first")
    first = _advance(values)
    assert first.classification is LocalLineageHeadClassification.ADVANCED

    alternate = _setup(
        tmp_path / "alternate-operation",
        cycle_payload=_no_action_transition_bytes(),
    )
    alternate_execution = execute_paper_operation_once(
        alternate.operation_root,
        alternate.inputs,
    )
    assert alternate_execution.transition_path is not None
    assert alternate_execution.cycle_result_id is not None
    assert alternate_execution.successor_checkpoint_id is not None
    alternate_report = alternate_execution.transition_path / (
        f"checkpointed-paper-cycle-report-{alternate_execution.cycle_result_id}.json"
    )
    parsed_report = parse_checkpointed_paper_cycle_report(alternate_report.read_bytes())
    alternate_successor = alternate_execution.transition_path / (
        f"paper-account-checkpoint-{alternate_execution.successor_checkpoint_id}.json"
    )
    alternate_genesis = alternate.inputs.lineage_manifest.genesis_checkpoint
    alternate_manifest = _write_manifest(
        tmp_path / "alternate-manifest.json",
        genesis_id=alternate_genesis.artifact_id,
        genesis_path=alternate.checkpoint_path,
        terminal_id=alternate_execution.successor_checkpoint_id,
        successor=(
            alternate_execution.successor_checkpoint_id,
            alternate_successor,
        ),
        report=(parsed_report.report_id, alternate_report),
        snapshot=(
            alternate.inputs.intent.completed_snapshot_artifact.artifact_id,
            alternate.snapshot_path,
        ),
    )
    values["manifest"] = alternate_manifest

    result = _advance(values)

    assert result.classification is LocalLineageHeadClassification.CONFLICTING
    assert result.diagnostic is LocalLineageHeadDiagnosticCode.FORK


class _FailingReplacer:
    def replace(self, *args, **kwargs) -> None:
        raise AtomicPointerReplacementError("injected replacement failure")


def test_replacement_failure_retains_immutables_and_old_verified_pointer(
    tmp_path: Path,
) -> None:
    values = _completed_advancement_inputs(tmp_path)
    old_pointer = (values["authority_root"] / CURRENT_HEAD_FILENAME).read_bytes()

    result = _advance(values, replacer=_FailingReplacer())

    assert (
        result.classification is LocalLineageHeadClassification.MANUAL_REVIEW_REQUIRED
    )
    assert (
        result.diagnostic is LocalLineageHeadDiagnosticCode.ATOMIC_REPLACEMENT_FAILURE
    )
    assert (
        values["authority_root"] / CURRENT_HEAD_FILENAME
    ).read_bytes() == old_pointer
    verified = verify_local_lineage_head(values["authority_root"])
    assert verified.classification is LocalLineageHeadClassification.PASS
    assert verified.authority is not None
    assert verified.authority.pointer.generation == 0
    assert len(list((values["authority_root"] / "lineage-head-records").iterdir())) == 2


def test_failed_receipt_cannot_advance(tmp_path: Path) -> None:
    values = _completed_advancement_inputs(tmp_path)
    fixture = values["fixture"]
    intent = fixture.inputs.intent
    failed = PaperOperationReceipt(
        1,
        intent.operation_id,
        intent,
        PaperOperationStatus.FAILED,
        None,
        PaperOperationDiagnosticCode.RUNTIME_EXECUTION_FAILURE,
        intent.prior_lineage_evidence,
        None,
        None,
        None,
        fixture.inputs.application_id,
        None,
    )
    failed_path = tmp_path / "failed-receipt.json"
    failed_path.write_bytes(serialize_paper_operation_receipt(failed))
    values["receipt"] = failed_path

    result = _advance(values)

    assert (
        result.classification is LocalLineageHeadClassification.MANUAL_REVIEW_REQUIRED
    )
    assert (
        result.diagnostic
        is LocalLineageHeadDiagnosticCode.FAILED_RECEIPT_CANNOT_ADVANCE
    )


def test_tampered_pointer_and_head_fail_closed(tmp_path: Path) -> None:
    _, authority_root = _initialized_fixture(tmp_path)
    pointer_path = authority_root / CURRENT_HEAD_FILENAME
    pointer = json.loads(pointer_path.read_bytes())
    pointer["head_record_sha256"] = "0" * 64
    pointer_path.write_bytes(
        (json.dumps(pointer, sort_keys=True, separators=(",", ":")) + "\n").encode()
    )

    result = verify_local_lineage_head(authority_root)

    assert result.classification is LocalLineageHeadClassification.BLOCKED
    assert (
        result.diagnostic
        is LocalLineageHeadDiagnosticCode.HEAD_RECORD_EVIDENCE_MISMATCH
    )


def test_changed_pointer_epoch_is_conflicting(tmp_path: Path) -> None:
    _, authority_root = _initialized_fixture(tmp_path)
    pointer_path = authority_root / CURRENT_HEAD_FILENAME
    pointer = parse_local_lineage_head_reference(pointer_path.read_bytes())
    changed = LocalLineageHeadReference(
        1,
        UUID("ffffffff-ffff-5fff-8fff-ffffffffffff"),
        pointer.generation,
        pointer.head_record_id,
        pointer.head_record_sha256,
        pointer.head_record_byte_length,
    )
    pointer_path.write_bytes(serialize_local_lineage_head_reference(changed))

    result = verify_local_lineage_head(authority_root)

    assert result.classification is LocalLineageHeadClassification.CONFLICTING
    assert result.diagnostic is LocalLineageHeadDiagnosticCode.EPOCH_MISMATCH


def test_altered_predecessor_evidence_breaks_chain(tmp_path: Path) -> None:
    values = _completed_advancement_inputs(tmp_path)
    first = _advance(values)
    assert first.authority is not None
    current = first.authority.current_record
    assert current.previous_head_record is not None
    altered = create_paper_account_lineage_head_record(
        current.authority_epoch_id,
        current.generation,
        LineageHeadRecordReference(
            current.previous_head_record.head_record_id,
            "0" * 64,
            current.previous_head_record.byte_length,
        ),
        current.lineage_manifest,
        current.verified_lineage_evidence_id,
        current.terminal_checkpoint,
        current.advancement_cause_kind,
        current.advancement_cause,
    )
    payload = serialize_paper_account_lineage_head_record(altered)
    record_path = (
        values["authority_root"]
        / "lineage-head-records"
        / f"paper-account-lineage-head-record-{altered.record_id}.json"
    )
    record_path.write_bytes(payload)
    pointer = LocalLineageHeadReference(
        1,
        current.authority_epoch_id,
        current.generation,
        altered.record_id,
        sha256(payload).hexdigest(),
        len(payload),
    )
    (values["authority_root"] / CURRENT_HEAD_FILENAME).write_bytes(
        serialize_local_lineage_head_reference(pointer)
    )

    result = verify_local_lineage_head(values["authority_root"])

    assert result.classification is LocalLineageHeadClassification.BLOCKED
    assert (
        result.diagnostic
        is LocalLineageHeadDiagnosticCode.HEAD_RECORD_EVIDENCE_MISMATCH
    )


def test_generation_skip_in_selected_chain_fails_closed(tmp_path: Path) -> None:
    lineage = _two_edges()
    dependencies = tmp_path / "dependencies"
    dependencies.mkdir()
    artifact_paths = {}
    for artifact in (
        lineage.genesis,
        *lineage.successors,
        *lineage.reports,
        *lineage.snapshots,
    ):
        path = dependencies / f"{artifact.kind.value}-{artifact.artifact_id}.json"
        path.write_bytes(artifact.payload)
        artifact_paths[artifact.artifact_id] = path
    genesis_manifest = _write_manifest(
        tmp_path / "genesis-manifest.json",
        genesis_id=lineage.genesis.artifact_id,
        genesis_path=artifact_paths[lineage.genesis.artifact_id],
        terminal_id=lineage.genesis.artifact_id,
    )
    authority_root = tmp_path / "authority"
    authority_root.mkdir()
    initialized = initialize_local_lineage_head(
        authority_root,
        EPOCH_ID,
        genesis_manifest,
    )
    assert initialized.authority is not None

    full_tree = {
        "schema_version": 1,
        "genesis_checkpoint": _reference(
            lineage.genesis.artifact_id,
            artifact_paths[lineage.genesis.artifact_id],
            lineage.genesis.payload,
        ),
        "terminal_checkpoint_id": str(lineage.terminal_id),
        "successor_checkpoints": [
            _reference(
                item.artifact_id,
                artifact_paths[item.artifact_id],
                item.payload,
            )
            for item in lineage.successors
        ],
        "cycle_reports": [
            _reference(
                item.artifact_id,
                artifact_paths[item.artifact_id],
                item.payload,
            )
            for item in lineage.reports
        ],
        "snapshots": [
            _reference(
                item.artifact_id,
                artifact_paths[item.artifact_id],
                item.payload,
            )
            for item in lineage.snapshots
        ],
    }
    full_payload = json.dumps(
        full_tree,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    verification = verify_paper_account_lineage(
        lineage.genesis,
        lineage.terminal_id,
        lineage.successors,
        lineage.reports,
        lineage.snapshots,
        calendar(),
    )
    assert verification.evidence is not None
    assert verification.terminal_checkpoint is not None
    evidence = verification.evidence
    digest = sha256(full_payload).hexdigest()
    manifest_path = (
        authority_root
        / "lineage-manifests"
        / (f"paper-account-lineage-manifest-{evidence.evidence_id}-{digest}.json")
    )
    manifest_path.write_bytes(full_payload)
    previous_payload = initialized.authority.record_payloads[-1]
    terminal_artifact = evidence.checkpoint_artifacts[-1]
    skipped = create_paper_account_lineage_head_record(
        EPOCH_ID,
        2,
        LineageHeadRecordReference(
            initialized.authority.current_record.record_id,
            sha256(previous_payload).hexdigest(),
            len(previous_payload),
        ),
        LineageManifestEvidence(
            evidence.evidence_id,
            digest,
            len(full_payload),
        ),
        evidence.evidence_id,
        LineageHeadTerminalCheckpointEvidence(
            terminal_artifact.artifact_id,
            terminal_artifact.sha256,
            terminal_artifact.byte_length,
            verification.terminal_checkpoint.sequence,
        ),
        LineageHeadAdvancementCauseKind.COMPLETED_OPERATION,
        LineageHeadAdvancementCauseEvidence(
            UUID("aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa"),
            "c" * 64,
            1,
        ),
    )
    skipped_payload = serialize_paper_account_lineage_head_record(skipped)
    (
        authority_root
        / "lineage-head-records"
        / f"paper-account-lineage-head-record-{skipped.record_id}.json"
    ).write_bytes(skipped_payload)
    (authority_root / CURRENT_HEAD_FILENAME).write_bytes(
        serialize_local_lineage_head_reference(
            LocalLineageHeadReference(
                1,
                EPOCH_ID,
                2,
                skipped.record_id,
                sha256(skipped_payload).hexdigest(),
                len(skipped_payload),
            )
        )
    )

    result = verify_local_lineage_head(authority_root)

    assert result.classification is LocalLineageHeadClassification.CONFLICTING
    assert result.diagnostic is LocalLineageHeadDiagnosticCode.GENERATION_DISCONTINUITY


def test_completed_receipt_substitution_is_rejected(tmp_path: Path) -> None:
    values = _completed_advancement_inputs(tmp_path)
    receipt_payload = bytearray(values["receipt"].read_bytes())
    receipt_payload[len(receipt_payload) // 2] ^= 1
    substituted = tmp_path / "substituted-receipt.json"
    substituted.write_bytes(bytes(receipt_payload))
    values["receipt"] = substituted

    result = _advance(values)

    assert result.classification is LocalLineageHeadClassification.BLOCKED
    assert result.diagnostic is LocalLineageHeadDiagnosticCode.RECEIPT_MISMATCH


def test_symlinked_pointer_is_unsafe_when_platform_permits(
    tmp_path: Path,
) -> None:
    _, authority_root = _initialized_fixture(tmp_path)
    pointer_path = authority_root / CURRENT_HEAD_FILENAME
    retained = authority_root / "retained-pointer.json"
    retained.write_bytes(pointer_path.read_bytes())
    pointer_path.unlink()
    try:
        os.symlink(retained, pointer_path)
    except OSError:
        pytest.skip("pointer symlink creation unavailable")

    result = verify_local_lineage_head(authority_root)

    assert result.classification is LocalLineageHeadClassification.BLOCKED
    assert result.diagnostic is LocalLineageHeadDiagnosticCode.UNSAFE_POINTER


def test_verifier_ignores_unlisted_candidate_and_performs_no_external_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, authority_root = _initialized_fixture(tmp_path)
    (authority_root / "paper-account-lineage-head-record-highest.json").write_text(
        "not authority",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: pytest.fail("network access is prohibited"),
    )

    result = verify_local_lineage_head(authority_root)

    assert result.classification is LocalLineageHeadClassification.PASS
