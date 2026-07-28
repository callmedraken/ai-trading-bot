"""Focused deterministic full-lineage offline verification coverage."""

from __future__ import annotations

import builtins
import json
import socket
from dataclasses import dataclass, replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
from tests.market_data.daily_snapshot_test_support import (
    CAPTURED_AT,
    accepted_result,
    capture_request,
)
from tests.runtime.test_checkpointed_paper_cycle_successor import (
    _edge_artifacts,
    _later_cycle_request,
    _later_snapshot_verification,
)
from tests.runtime.test_checkpointed_verified_snapshot_execution import (
    _checkpoint_verification,
    _position,
    _request,
    _target,
)
from tests.runtime.test_verified_snapshot_preparation import _verification, calendar

from trading_bot.market_data import serialize_daily_snapshot, verify_daily_snapshot
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime import (
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactKind,
    PaperAccountLineageVerificationCode,
    PaperAccountLineageVerificationStatus,
    checkpointed_paper_cycle_report_from_result,
    checkpointed_paper_cycle_report_reference,
    create_successor_paper_account_checkpoint,
    execute_checkpointed_verified_snapshot_paper_cycle,
    parse_checkpointed_paper_cycle_report,
    serialize_checkpointed_paper_cycle_report,
    serialize_successor_paper_account_checkpoint,
    verified_prior_from_successor_edge,
    verify_checkpointed_paper_cycle_successor_edge,
    verify_genesis_paper_account_checkpoint,
    verify_paper_account_lineage,
)


@dataclass(frozen=True, slots=True)
class _Lineage:
    genesis: PaperAccountLineageArtifact
    terminal_id: UUID
    successors: tuple[PaperAccountLineageArtifact, ...]
    reports: tuple[PaperAccountLineageArtifact, ...]
    snapshots: tuple[PaperAccountLineageArtifact, ...]


def _artifact(kind, artifact_id, payload) -> PaperAccountLineageArtifact:
    return PaperAccountLineageArtifact(
        kind,
        artifact_id,
        payload,
        sha256(payload).hexdigest(),
        len(payload),
    )


def _next_snapshot_verification():
    accepted = accepted_result(
        request=capture_request(
            request_id=UUID("0e2eef9a-02e6-5ed5-a7dc-203e0a94b01a")
        ),
        captured_at=CAPTURED_AT + timedelta(hours=3),
    )
    assert accepted.snapshot is not None
    payload = serialize_daily_snapshot(accepted.snapshot)
    return verify_daily_snapshot(payload, calendar())


def _one_edge(*, target=None, checkpoint=None) -> _Lineage:
    _, report, report_payload, genesis_payload, snapshot_payload, successor, payload = (
        _edge_artifacts(target=target, checkpoint=checkpoint)
    )
    genesis = verify_genesis_paper_account_checkpoint(genesis_payload).checkpoint
    assert genesis is not None
    return _Lineage(
        _artifact(
            PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
            genesis.checkpoint_id,
            genesis_payload,
        ),
        successor.checkpoint_id,
        (
            _artifact(
                PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
                successor.checkpoint_id,
                payload,
            ),
        ),
        (
            _artifact(
                PaperAccountLineageArtifactKind.CYCLE_REPORT,
                report.report_id,
                report_payload,
            ),
        ),
        (
            _artifact(
                PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
                successor.snapshot_reference.snapshot_id,
                snapshot_payload,
            ),
        ),
    )


def _two_edges(*, mixed_no_action: bool = False) -> _Lineage:
    lineage = (
        _one_edge(target=_target("10", "0", "972.50"))
        if mixed_no_action
        else _one_edge()
    )
    first_successor = lineage.successors[0]
    first_report = lineage.reports[0]
    first_snapshot = lineage.snapshots[0]
    first_edge = verify_checkpointed_paper_cycle_successor_edge(
        first_report.payload,
        lineage.genesis.payload,
        first_snapshot.payload,
        first_successor.payload,
        calendar(),
    )
    prior = verified_prior_from_successor_edge(first_edge)
    snapshot_verification = _next_snapshot_verification()
    snapshot = snapshot_verification.snapshot
    assert snapshot is not None
    request = _later_cycle_request(snapshot_verification)
    if mixed_no_action:
        request = replace(request, target=_target("0", "0", "2000"))
    result = execute_checkpointed_verified_snapshot_paper_cycle(
        request,
        prior,
        snapshot_verification,
        calendar(),
    )
    report = checkpointed_paper_cycle_report_from_result(result)
    report_payload = serialize_checkpointed_paper_cycle_report(report)
    successor = create_successor_paper_account_checkpoint(
        report.evidence.prior_checkpoint,
        report.evidence.prior_lineage_id,
        result,
        checkpointed_paper_cycle_report_reference(report_payload),
    )
    successor_payload = serialize_successor_paper_account_checkpoint(successor)
    snapshot_payload = serialize_daily_snapshot(snapshot)
    return _Lineage(
        lineage.genesis,
        successor.checkpoint_id,
        (
            *lineage.successors,
            _artifact(
                PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
                successor.checkpoint_id,
                successor_payload,
            ),
        ),
        (
            *lineage.reports,
            _artifact(
                PaperAccountLineageArtifactKind.CYCLE_REPORT,
                report.report_id,
                report_payload,
            ),
        ),
        (
            *lineage.snapshots,
            _artifact(
                PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
                snapshot.snapshot_id,
                snapshot_payload,
            ),
        ),
    )


def _verify(lineage: _Lineage):
    return verify_paper_account_lineage(
        lineage.genesis,
        lineage.terminal_id,
        lineage.successors,
        lineage.reports,
        lineage.snapshots,
        calendar(),
    )


def test_genesis_only_lineage_exposes_exact_terminal_state() -> None:
    lineage = _one_edge()
    genesis_only = replace(
        lineage,
        terminal_id=lineage.genesis.artifact_id,
        successors=(),
        reports=(),
        snapshots=(),
    )

    result = _verify(genesis_only)

    assert result.status is PaperAccountLineageVerificationStatus.PASS
    assert result.evidence is not None
    assert result.evidence.edge_count == 0
    assert result.evidence.checkpoint_ids == (lineage.genesis.artifact_id,)
    assert result.terminal_restored_ledger is not None
    assert result.terminal_restored_ledger.fills == ()


def test_one_edge_lineage_retains_ordered_artifact_evidence() -> None:
    lineage = _one_edge()

    result = _verify(lineage)

    assert result.status is PaperAccountLineageVerificationStatus.PASS
    assert result.evidence is not None
    assert result.evidence.edge_count == 1
    assert result.evidence.checkpoint_ids == (
        lineage.genesis.artifact_id,
        lineage.terminal_id,
    )
    assert (
        result.evidence.checkpoint_artifacts[1].sha256 == lineage.successors[0].sha256
    )
    assert result.terminal_checkpoint is not None
    assert result.terminal_restored_ledger is not None
    assert result.terminal_restored_ledger.is_compact_restored


def test_multi_edge_chain_is_deterministic_and_deduplicates_exact_references() -> None:
    lineage = _two_edges()
    repeated = replace(
        lineage,
        successors=(lineage.successors[1], *lineage.successors, lineage.successors[0]),
        reports=(lineage.reports[1], *lineage.reports, lineage.reports[0]),
        snapshots=(lineage.snapshots[1], *lineage.snapshots, lineage.snapshots[0]),
    )

    first = _verify(lineage)
    second = _verify(repeated)

    assert first.status is PaperAccountLineageVerificationStatus.PASS
    assert second.status is PaperAccountLineageVerificationStatus.PASS
    assert first.evidence == second.evidence
    assert first.evidence is not None
    assert first.evidence.edge_count == 2
    assert str(first.evidence.evidence_id) == "e02e9608-1300-56d6-974f-4a4376700ca1"
    assert len(first.evidence.application_ids) == 2
    assert len(first.evidence.cycle_result_ids) == 2


def test_mixed_applied_and_no_action_chain_verifies_completely() -> None:
    lineage = _two_edges(mixed_no_action=True)

    result = _verify(lineage)

    assert result.status is PaperAccountLineageVerificationStatus.PASS
    assert result.evidence is not None
    assert result.evidence.edge_count == 2
    assert result.terminal_checkpoint is not None
    assert result.terminal_checkpoint.account_state.compact_state.positions == ()


@pytest.mark.parametrize(
    ("field", "code"),
    (
        ("reports", PaperAccountLineageVerificationCode.MISSING_REPORT),
        ("snapshots", PaperAccountLineageVerificationCode.MISSING_SNAPSHOT),
    ),
)
def test_required_edge_dependency_must_be_supplied(field, code) -> None:
    lineage = _one_edge()

    result = _verify(replace(lineage, **{field: ()}))

    assert result.status is PaperAccountLineageVerificationStatus.FAIL
    assert result.diagnostics[0].code is code
    assert result.evidence is None
    assert result.terminal_checkpoint is None
    assert result.terminal_restored_ledger is None


def test_missing_terminal_checkpoint_fails_before_graph_walk() -> None:
    lineage = _one_edge()
    result = _verify(replace(lineage, terminal_id=UUID(int=7)))

    assert result.diagnostics[0].code is (
        PaperAccountLineageVerificationCode.MISSING_CHECKPOINT
    )


def test_duplicate_id_with_different_bytes_is_rejected() -> None:
    lineage = _one_edge()
    original = lineage.successors[0]
    changed_payload = original.payload + b" "
    conflict = replace(
        original,
        payload=changed_payload,
        sha256=sha256(changed_payload).hexdigest(),
        byte_length=len(changed_payload),
    )

    result = _verify(replace(lineage, successors=(original, conflict)))

    assert result.diagnostics[0].code is (
        PaperAccountLineageVerificationCode.DUPLICATE_ID_CONFLICT
    )


def test_duplicate_bytes_under_different_claimed_identity_is_rejected() -> None:
    lineage = _one_edge()
    original = lineage.reports[0]
    conflict = replace(original, artifact_id=UUID(int=8))

    result = _verify(replace(lineage, reports=(original, conflict)))

    assert result.diagnostics[0].code is (
        PaperAccountLineageVerificationCode.DUPLICATE_BYTES_IDENTITY_CONFLICT
    )


def test_report_reuse_and_application_conflict_use_fixed_report_precedence() -> None:
    lineage = _one_edge()
    report = parse_checkpointed_paper_cycle_report(lineage.reports[0].payload)
    edge = verify_checkpointed_paper_cycle_successor_edge(
        lineage.reports[0].payload,
        lineage.genesis.payload,
        lineage.snapshots[0].payload,
        lineage.successors[0].payload,
        calendar(),
    )
    assert edge.cycle_result is not None
    second = create_successor_paper_account_checkpoint(
        report.evidence.prior_checkpoint,
        report.evidence.prior_lineage_id,
        edge.cycle_result,
        checkpointed_paper_cycle_report_reference(lineage.reports[0].payload),
        (MetadataEntry("branch", "conflict"),),
    )
    payload = serialize_successor_paper_account_checkpoint(second)
    second_artifact = _artifact(
        PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
        second.checkpoint_id,
        payload,
    )

    result = _verify(
        replace(lineage, successors=(*lineage.successors, second_artifact))
    )

    assert result.diagnostics[0].code is (
        PaperAccountLineageVerificationCode.REPORT_REUSE
    )


@pytest.mark.parametrize("field", ("sequence", "prior_checkpoint"))
def test_malformed_sequence_gap_or_cycle_material_never_becomes_graph_authority(
    field,
) -> None:
    lineage = _one_edge()
    tree = json.loads(lineage.successors[0].payload)
    checkpoint = tree["checkpoint"]
    if field == "sequence":
        checkpoint["sequence"] += 1
    else:
        checkpoint["prior_checkpoint"]["checkpoint_id"] = checkpoint["checkpoint_id"]
    payload = json.dumps(tree, separators=(",", ":"), sort_keys=True).encode() + b"\n"
    malformed = _artifact(
        PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
        lineage.successors[0].artifact_id,
        payload,
    )

    result = _verify(replace(lineage, successors=(malformed,)))

    assert result.diagnostics[0].code is (
        PaperAccountLineageVerificationCode.SUCCESSOR_PARSE_FAILURE
    )


def test_snapshot_reference_mismatch_is_rejected() -> None:
    lineage = _one_edge()
    later = _later_snapshot_verification()
    snapshot = later.snapshot
    assert snapshot is not None
    assert snapshot.snapshot_id == lineage.snapshots[0].artifact_id
    payload = serialize_daily_snapshot(snapshot)
    replacement = _artifact(
        PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
        snapshot.snapshot_id,
        payload,
    )

    result = _verify(replace(lineage, snapshots=(replacement,)))

    assert result.diagnostics[0].code is (
        PaperAccountLineageVerificationCode.SNAPSHOT_MISMATCH
    )


def test_no_action_negative_pnl_and_exact_basis_are_retained() -> None:
    checkpoint = _checkpoint_verification(
        cash="0",
        positions=(_position(quantity="3", basis="0.6"),),
        realized="-7.25",
    )
    lineage = _one_edge(
        checkpoint=checkpoint,
        target=_target("3", "0", "0"),
    )

    result = _verify(lineage)

    assert result.status is PaperAccountLineageVerificationStatus.PASS
    assert result.evidence is not None
    compact = result.evidence.terminal_compact_state
    assert str(compact.realized_profit_loss) == "-7.25"
    assert str(compact.positions[0].total_cost_basis) == "0.6"


def test_full_sale_can_carry_cumulative_pnl_from_negative_to_positive() -> None:
    checkpoint = _checkpoint_verification(
        cash="0",
        positions=(_position(quantity="3", basis="0.6"),),
        realized="-7.25",
    )
    lineage = _one_edge(
        checkpoint=checkpoint,
        target=_target("0", "0", "308.25"),
    )

    result = _verify(lineage)

    assert result.status is PaperAccountLineageVerificationStatus.PASS
    assert result.evidence is not None
    assert result.evidence.terminal_compact_state.realized_profit_loss > 0
    assert result.evidence.terminal_compact_state.positions == ()


def test_fork_is_rejected_deterministically() -> None:
    lineage = _one_edge()
    genesis_verification = verify_genesis_paper_account_checkpoint(
        lineage.genesis.payload
    )
    snapshot_verification = _verification()
    request = replace(
        _request(snapshot_verification, target=_target("10", "0", "972.50")),
        request_id=UUID("95f0ffeb-ec29-5fba-a243-45c3d35d6ad0"),
    )
    result = execute_checkpointed_verified_snapshot_paper_cycle(
        request,
        genesis_verification,
        snapshot_verification,
        calendar(),
    )
    report = checkpointed_paper_cycle_report_from_result(result)
    report_payload = serialize_checkpointed_paper_cycle_report(report)
    successor = create_successor_paper_account_checkpoint(
        report.evidence.prior_checkpoint,
        report.evidence.prior_lineage_id,
        result,
        checkpointed_paper_cycle_report_reference(report_payload),
    )
    successor_payload = serialize_successor_paper_account_checkpoint(successor)
    branch_successor = _artifact(
        PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
        successor.checkpoint_id,
        successor_payload,
    )
    branch_report = _artifact(
        PaperAccountLineageArtifactKind.CYCLE_REPORT,
        report.report_id,
        report_payload,
    )

    verification = _verify(
        replace(
            lineage,
            successors=(*lineage.successors, branch_successor),
            reports=(*lineage.reports, branch_report),
        )
    )

    assert verification.diagnostics[0].code is PaperAccountLineageVerificationCode.FORK


def test_terminal_supplied_on_unrelated_lineage_is_not_reachable() -> None:
    lineage = _one_edge()
    other = _one_edge(
        checkpoint=_checkpoint_verification(cash="1000", positions=()),
        target=_target("0", "0", "1000"),
    )

    result = _verify(
        replace(
            lineage,
            terminal_id=other.terminal_id,
            successors=other.successors,
            reports=other.reports,
            snapshots=other.snapshots,
        )
    )

    assert result.diagnostics[0].code is (
        PaperAccountLineageVerificationCode.TERMINAL_NOT_REACHABLE
    )


def test_verification_has_no_network_broker_provider_or_output_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lineage = _two_edges()

    def forbidden(*args, **kwargs):
        raise AssertionError("forbidden external or output dependency")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(
        "trading_bot.market_data.AlpacaDailySnapshotProvider.fetch",
        forbidden,
    )

    result = _verify(lineage)

    assert result.status is PaperAccountLineageVerificationStatus.PASS
