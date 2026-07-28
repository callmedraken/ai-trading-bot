"""Focused immutable paper-operation intent and receipt coverage."""

from __future__ import annotations

import builtins
import json
import socket
from dataclasses import replace
from decimal import ROUND_DOWN, ROUND_UP, Decimal, localcontext
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
from tests.runtime.test_checkpointed_paper_cycle_successor import _edge_artifacts
from tests.runtime.test_checkpointed_verified_snapshot_execution import (
    _checkpoint_verification,
    _permissive_limits,
    _request,
    _target,
)
from tests.runtime.test_verified_snapshot_preparation import (
    _policies,
    _verification,
    calendar,
)

from trading_bot.market_data import serialize_daily_snapshot
from trading_bot.runtime import (
    MAX_PAPER_OPERATION_RECEIPT_BYTES,
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactEvidence,
    PaperAccountLineageArtifactKind,
    PaperAccountLineageVerificationError,
    PaperAccountLineageVerificationStatus,
    PaperOperationArtifactEvidence,
    PaperOperationDiagnosticCode,
    PaperOperationError,
    PaperOperationOutcome,
    PaperOperationReceipt,
    PaperOperationReceiptSchemaError,
    PaperOperationReceiptSyntaxError,
    PaperOperationReceiptVerificationCode,
    PaperOperationReceiptVerificationStatus,
    PaperOperationStatus,
    create_paper_operation_intent,
    derive_checkpointed_verified_snapshot_application_id,
    parse_checkpointed_paper_cycle_report,
    parse_paper_operation_receipt,
    parse_successor_paper_account_checkpoint,
    serialize_paper_operation_receipt,
    verified_prior_from_full_lineage,
    verify_genesis_paper_account_checkpoint,
    verify_paper_account_lineage,
    verify_paper_operation_receipt,
)

CONFIGURATION = b'{"schema_version":1,"caller_authored":"exact"}\n'
CALLER_KEY = UUID("cff0bcea-e6d9-548a-8371-a45fb95ce3b4")


def _artifact(kind, artifact_id, payload):
    return PaperAccountLineageArtifact(
        kind,
        artifact_id,
        payload,
        sha256(payload).hexdigest(),
        len(payload),
    )


def _evidence(kind, artifact_id, payload):
    return PaperAccountLineageArtifactEvidence(
        kind,
        artifact_id,
        sha256(payload).hexdigest(),
        len(payload),
    )


def _completed(*, target=None):
    (
        result,
        report,
        report_payload,
        genesis_payload,
        snapshot_payload,
        successor,
        successor_payload,
    ) = _edge_artifacts(target=target)
    genesis = verify_genesis_paper_account_checkpoint(genesis_payload).checkpoint
    assert genesis is not None
    genesis_artifact = _artifact(
        PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
        genesis.checkpoint_id,
        genesis_payload,
    )
    prior = verify_paper_account_lineage(
        genesis_artifact,
        genesis.checkpoint_id,
        (),
        (),
        (),
        calendar(),
    )
    assert prior.status is PaperAccountLineageVerificationStatus.PASS
    assert prior.evidence is not None
    report_artifact = _artifact(
        PaperAccountLineageArtifactKind.CYCLE_REPORT,
        report.report_id,
        report_payload,
    )
    successor_artifact = _artifact(
        PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
        successor.checkpoint_id,
        successor_payload,
    )
    snapshot_artifact = _artifact(
        PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
        result.snapshot_reference.snapshot_id,
        snapshot_payload,
    )
    lineage = verify_paper_account_lineage(
        genesis_artifact,
        successor.checkpoint_id,
        (successor_artifact,),
        (report_artifact,),
        (snapshot_artifact,),
        calendar(),
    )
    assert lineage.status is PaperAccountLineageVerificationStatus.PASS
    assert lineage.evidence is not None
    intent = create_paper_operation_intent(
        CALLER_KEY,
        prior.evidence,
        prior.evidence.checkpoint_artifacts[-1],
        _evidence(
            PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
            result.snapshot_reference.snapshot_id,
            snapshot_payload,
        ),
        PaperOperationArtifactEvidence(
            sha256(CONFIGURATION).hexdigest(), len(CONFIGURATION)
        ),
        report.evidence.request,
    )
    outcome = (
        PaperOperationOutcome.APPLIED
        if result.status.value == "APPLIED"
        else PaperOperationOutcome.NO_ACTION
    )
    receipt = PaperOperationReceipt(
        1,
        intent.operation_id,
        intent,
        PaperOperationStatus.COMPLETED,
        outcome,
        PaperOperationDiagnosticCode.NONE,
        prior.evidence,
        lineage.evidence,
        _evidence(
            PaperAccountLineageArtifactKind.CYCLE_REPORT,
            report.report_id,
            report_payload,
        ),
        _evidence(
            PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
            successor.checkpoint_id,
            successor_payload,
        ),
        result.application_id,
        result.result_id,
    )
    return (
        receipt,
        genesis_artifact,
        snapshot_payload,
        report_payload,
        successor_payload,
    )


def _verify_completed(receipt, genesis, snapshot, report, successor):
    payload = serialize_paper_operation_receipt(receipt)
    return verify_paper_operation_receipt(
        payload,
        cycle_configuration_payload=CONFIGURATION,
        prior_genesis_checkpoint=genesis,
        prior_successor_checkpoints=(),
        prior_cycle_reports=(),
        prior_snapshots=(),
        completed_snapshot_payload=snapshot,
        transition_report_payload=report,
        successor_checkpoint_payload=successor,
        calendar=calendar(),
    )


def test_applied_receipt_round_trip_and_offline_verification() -> None:
    receipt, genesis, snapshot, report, successor = _completed()
    payload = serialize_paper_operation_receipt(receipt)

    assert parse_paper_operation_receipt(payload) == receipt
    verified = _verify_completed(receipt, genesis, snapshot, report, successor)

    assert verified.status is PaperOperationReceiptVerificationStatus.PASS
    assert verified.receipt == receipt
    assert receipt.outcome is PaperOperationOutcome.APPLIED
    assert str(receipt.receipt_id) == "338ecb1c-e770-5995-8a4b-2e4084828d7e"
    assert len(payload) == 6241
    assert sha256(payload).hexdigest() == (
        "9f7e62f2da362353dd4e35afa6f8e38ee26dc4ddc318bcfb70aa2d67fe5772e5"
    )


def test_no_action_receipt_verifies_as_successful_successor() -> None:
    receipt, genesis, snapshot, report, successor = _completed(
        target=_target("10", "0", "972.50")
    )

    verified = _verify_completed(receipt, genesis, snapshot, report, successor)

    assert verified.status is PaperOperationReceiptVerificationStatus.PASS
    assert receipt.outcome is PaperOperationOutcome.NO_ACTION


def test_verified_successor_lineage_exposes_later_cycle_prior_authority() -> None:
    receipt, genesis, snapshot, report_payload, successor_payload = _completed()
    report = parse_checkpointed_paper_cycle_report(report_payload)
    successor = parse_successor_paper_account_checkpoint(successor_payload)
    lineage = verify_paper_account_lineage(
        genesis,
        successor.checkpoint_id,
        (
            _artifact(
                PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
                successor.checkpoint_id,
                successor_payload,
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
                receipt.intent.completed_snapshot_artifact.artifact_id,
                snapshot,
            ),
        ),
        calendar(),
    )

    prior = verified_prior_from_full_lineage(lineage)

    assert prior.checkpoint_id == successor.checkpoint_id
    assert prior.lineage_id == receipt.successor_lineage_evidence.lineage_id
    assert (
        prior.compact_state == receipt.successor_lineage_evidence.terminal_compact_state
    )


def test_identity_is_path_independent_and_decimal_context_independent() -> None:
    receipt, *_ = _completed()
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_DOWN
        low = replace(receipt.intent)
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_UP
        high = replace(receipt.intent)

    roots = (Path("C:/one"), Path("D:/completely/different"))
    assert roots[0] != roots[1]
    assert low == high
    assert low.operation_id == high.operation_id


@pytest.mark.parametrize(
    "change",
    (
        "caller",
        "lineage",
        "checkpoint",
        "snapshot",
        "request",
        "configuration",
    ),
)
def test_identity_binds_every_required_material(change: str) -> None:
    receipt, *_ = _completed()
    intent = receipt.intent
    caller = intent.caller_idempotency_key
    lineage = intent.prior_lineage_evidence
    checkpoint = intent.terminal_checkpoint_artifact
    snapshot = intent.completed_snapshot_artifact
    configuration = intent.cycle_configuration_artifact
    request = intent.request
    if change == "caller":
        caller = UUID(int=caller.int + 1)
    elif change == "lineage":
        with pytest.raises(PaperAccountLineageVerificationError):
            replace(
                lineage,
                evidence_id=UUID(int=lineage.evidence_id.int + 1),
            )
        return
    elif change == "checkpoint":
        checkpoint = replace(checkpoint, byte_length=checkpoint.byte_length + 1)
    elif change == "snapshot":
        snapshot = replace(snapshot, byte_length=snapshot.byte_length + 1)
        request = replace(
            request,
            snapshot_reference=replace(
                request.snapshot_reference,
                artifact_byte_length=request.snapshot_reference.artifact_byte_length
                + 1,
            ),
        )
    elif change == "request":
        request = replace(request, request_id=UUID(int=request.request_id.int + 1))
    else:
        configuration = replace(
            configuration, byte_length=configuration.byte_length + 1
        )
    if change == "checkpoint":
        with pytest.raises(PaperOperationError):
            create_paper_operation_intent(
                caller, lineage, checkpoint, snapshot, configuration, request
            )
        return
    changed = create_paper_operation_intent(
        caller, lineage, checkpoint, snapshot, configuration, request
    )
    assert changed.operation_id != intent.operation_id


@pytest.mark.parametrize(
    "mutation",
    (
        lambda tree: tree.update(extra=True),
        lambda tree: tree.pop("schema_version"),
        lambda tree: tree["receipt"].update(receipt_id="NOT-A-UUID"),
        lambda tree: tree["receipt"]["intent"]["cycle_configuration_artifact"].update(
            sha256="A" * 64
        ),
        lambda tree: tree["receipt"]["intent"]["request"].update(planning_at=1.5),
    ),
)
def test_strict_receipt_schema_rejects_noncanonical_values(mutation) -> None:
    receipt, *_ = _completed()
    tree = json.loads(serialize_paper_operation_receipt(receipt))
    mutation(tree)
    payload = json.dumps(tree, sort_keys=True, separators=(",", ":")).encode() + b"\n"

    with pytest.raises(
        (PaperOperationReceiptSchemaError, PaperOperationReceiptSyntaxError)
    ):
        parse_paper_operation_receipt(payload)


def test_duplicate_keys_constants_and_noncanonical_bytes_are_rejected() -> None:
    receipt, *_ = _completed()
    payload = serialize_paper_operation_receipt(receipt)
    duplicate = payload.replace(b'{"receipt":', b'{"schema_version":1,"receipt":', 1)

    with pytest.raises(PaperOperationReceiptSyntaxError):
        parse_paper_operation_receipt(duplicate)
    with pytest.raises(PaperOperationReceiptSyntaxError):
        parse_paper_operation_receipt(b'{"schema_version":NaN}\n')
    with pytest.raises(PaperOperationReceiptSchemaError):
        parse_paper_operation_receipt(payload + b" ")
    with pytest.raises(PaperOperationReceiptSyntaxError):
        parse_paper_operation_receipt(b"x" * (MAX_PAPER_OPERATION_RECEIPT_BYTES + 1))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("planning_at", "2025-01-08T00:00:00.000000Z"),
        ("target_cash", "972.500"),
    ),
)
def test_noncanonical_timestamp_and_decimal_are_rejected(field, value) -> None:
    receipt, *_ = _completed()
    tree = json.loads(serialize_paper_operation_receipt(receipt))
    request = tree["receipt"]["intent"]["request"]
    if field == "target_cash":
        request["target"]["target_cash"] = value
    else:
        request[field] = value
    payload = json.dumps(tree, sort_keys=True, separators=(",", ":")).encode() + b"\n"

    with pytest.raises(PaperOperationReceiptSchemaError):
        parse_paper_operation_receipt(payload)


def test_mismatched_transition_and_lineage_evidence_fail_closed() -> None:
    receipt, genesis, snapshot, report, successor = _completed()
    changed = report + b" "

    result = _verify_completed(receipt, genesis, snapshot, changed, successor)

    assert result.status is PaperOperationReceiptVerificationStatus.FAIL
    assert result.diagnostics[0].code is (
        PaperOperationReceiptVerificationCode.TRANSITION_EVIDENCE_MISMATCH
    )


def test_valid_deterministic_failed_receipt_replays_exact_failure() -> None:
    checkpoint, checkpoint_payload = _checkpoint_verification(cash="2000", positions=())
    genesis = checkpoint.checkpoint
    assert genesis is not None
    genesis_artifact = _artifact(
        PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
        genesis.checkpoint_id,
        checkpoint_payload,
    )
    prior = verify_paper_account_lineage(
        genesis_artifact, genesis.checkpoint_id, (), (), (), calendar()
    )
    assert prior.evidence is not None
    verification = _verification()
    snapshot = verification.snapshot
    assert snapshot is not None
    snapshot_payload = serialize_daily_snapshot(snapshot)
    references = tuple(
        replace(
            item,
            caller_asserted_open_reference_price=(
                Decimal("103") if str(item.symbol) == "SPY" else Decimal("300")
            ),
        )
        for item in _request(verification).open_references
    )
    request = _request(
        verification,
        target=_target("0", "9", "173"),
        policies=_policies(risk_limits=_permissive_limits()),
        open_references=references,
    )
    snapshot_evidence = _evidence(
        PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
        snapshot.snapshot_id,
        snapshot_payload,
    )
    intent = create_paper_operation_intent(
        CALLER_KEY,
        prior.evidence,
        prior.evidence.checkpoint_artifacts[-1],
        snapshot_evidence,
        PaperOperationArtifactEvidence(
            sha256(CONFIGURATION).hexdigest(), len(CONFIGURATION)
        ),
        request,
    )
    receipt = PaperOperationReceipt(
        1,
        intent.operation_id,
        intent,
        PaperOperationStatus.FAILED,
        None,
        PaperOperationDiagnosticCode.INSUFFICIENT_CASH,
        prior.evidence,
        None,
        None,
        None,
        derive_checkpointed_verified_snapshot_application_id(
            genesis.checkpoint_id, request.request_id
        ),
        None,
    )
    result = verify_paper_operation_receipt(
        serialize_paper_operation_receipt(receipt),
        cycle_configuration_payload=CONFIGURATION,
        prior_genesis_checkpoint=genesis_artifact,
        prior_successor_checkpoints=(),
        prior_cycle_reports=(),
        prior_snapshots=(),
        completed_snapshot_payload=snapshot_payload,
        calendar=calendar(),
    )

    assert result.status is PaperOperationReceiptVerificationStatus.PASS

    wrong_classification = replace(
        receipt,
        diagnostic_code=PaperOperationDiagnosticCode.APPLICATION_FAILURE,
    )
    rejected = verify_paper_operation_receipt(
        serialize_paper_operation_receipt(wrong_classification),
        cycle_configuration_payload=CONFIGURATION,
        prior_genesis_checkpoint=genesis_artifact,
        prior_successor_checkpoints=(),
        prior_cycle_reports=(),
        prior_snapshots=(),
        completed_snapshot_payload=snapshot_payload,
        calendar=calendar(),
    )
    assert rejected.status is PaperOperationReceiptVerificationStatus.FAIL
    assert rejected.diagnostics[0].code is (
        PaperOperationReceiptVerificationCode.FAILED_REPLAY_MISMATCH
    )


def test_failed_receipt_cannot_classify_filesystem_or_incomplete_state() -> None:
    with pytest.raises(ValueError):
        PaperOperationDiagnosticCode("DISK_FAILURE")


def test_receipt_rejects_mismatched_application_result_and_lineage_evidence() -> None:
    receipt, *_ = _completed()

    with pytest.raises(PaperOperationError):
        replace(receipt, application_id=UUID(int=receipt.application_id.int + 1))
    with pytest.raises(PaperOperationError):
        replace(receipt, cycle_result_id=UUID(int=receipt.cycle_result_id.int + 1))
    with pytest.raises(PaperOperationError):
        replace(
            receipt,
            successor_checkpoint_artifact=replace(
                receipt.successor_checkpoint_artifact,
                byte_length=receipt.successor_checkpoint_artifact.byte_length + 1,
            ),
        )


def test_offline_verifier_has_no_external_output_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt, genesis, snapshot, report, successor = _completed()

    def forbidden(*args, **kwargs):
        raise AssertionError("forbidden external dependency")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(
        "trading_bot.market_data.AlpacaDailySnapshotProvider.fetch", forbidden
    )

    result = _verify_completed(receipt, genesis, snapshot, report, successor)

    assert result.status is PaperOperationReceiptVerificationStatus.PASS
