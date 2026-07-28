"""Focused immutable successor-checkpoint and one-edge verification coverage."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

import pytest
from tests.market_data.daily_snapshot_test_support import CAPTURED_AT, accepted_result
from tests.runtime.test_checkpointed_verified_snapshot_execution import (
    _checkpoint_verification,
    _execute,
    _position,
    _request,
    _target,
)
from tests.runtime.test_verified_snapshot_preparation import (
    _policies,
    _verification,
    calendar,
)

from trading_bot.execution import PaperFillPolicy
from trading_bot.market_data import serialize_daily_snapshot, verify_daily_snapshot
from trading_bot.rebalancing import RebalanceAssumptions
from trading_bot.risk import RiskLimits
from trading_bot.runtime import (
    CheckpointedPaperCycleReportVerificationCode,
    CheckpointedPaperCycleReportVerificationStatus,
    PaperAccountCheckpointEdgeVerificationCode,
    PaperAccountCheckpointEdgeVerificationStatus,
    checkpointed_paper_cycle_report_from_result,
    checkpointed_paper_cycle_report_reference,
    create_successor_paper_account_checkpoint,
    execute_checkpointed_verified_snapshot_paper_cycle,
    parse_checkpointed_paper_cycle_report,
    parse_successor_paper_account_checkpoint,
    serialize_checkpointed_paper_cycle_report,
    serialize_successor_paper_account_checkpoint,
    verified_prior_from_successor_edge,
    verify_checkpointed_paper_cycle_report,
    verify_checkpointed_paper_cycle_successor_edge,
)


def _edge_artifacts(*, target=None, checkpoint=None, policies=None):
    checkpoint_verification, checkpoint_payload = (
        checkpoint or _checkpoint_verification()
    )
    snapshot_verification = _verification()
    snapshot = snapshot_verification.snapshot
    assert snapshot is not None
    snapshot_payload = serialize_daily_snapshot(snapshot)
    result = _execute(
        checkpoint=(checkpoint_verification, checkpoint_payload),
        target=target,
        policies=policies,
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
    return (
        result,
        report,
        report_payload,
        checkpoint_payload,
        snapshot_payload,
        successor,
        successor_payload,
    )


def _later_snapshot_verification():
    snapshot = accepted_result(captured_at=CAPTURED_AT + timedelta(hours=3)).snapshot
    assert snapshot is not None
    return verify_daily_snapshot(serialize_daily_snapshot(snapshot), calendar())


def _later_cycle_request(snapshot_verification):
    return replace(
        _request(snapshot_verification, target=_target("0", "0", "1997.50")),
        request_id=UUID("01a3fceb-4e75-581f-bbeb-6d405e51cc0a"),
        planning_at=CAPTURED_AT + timedelta(hours=3, minutes=1),
        submitted_at=CAPTURED_AT + timedelta(hours=3, minutes=2),
        filled_at=CAPTURED_AT + timedelta(hours=5),
    )


def test_applied_edge_round_trips_and_restores_exact_successor_state() -> None:
    (
        result,
        report,
        report_payload,
        checkpoint_payload,
        snapshot_payload,
        successor,
        successor_payload,
    ) = _edge_artifacts()

    assert parse_checkpointed_paper_cycle_report(report_payload) == report
    assert parse_successor_paper_account_checkpoint(successor_payload) == successor
    verified = verify_checkpointed_paper_cycle_successor_edge(
        report_payload,
        checkpoint_payload,
        snapshot_payload,
        successor_payload,
        calendar(),
        expected_successor_sha256=sha256(successor_payload).hexdigest(),
        expected_successor_byte_length=len(successor_payload),
    )

    assert verified.status is PaperAccountCheckpointEdgeVerificationStatus.PASS
    assert verified.cycle_result == result
    assert verified.successor_checkpoint == successor
    assert verified.restored_successor_ledger is not None
    assert verified.restored_successor_ledger.is_compact_restored
    assert verified.restored_successor_ledger.fills == ()


def test_golden_report_and_successor_artifact_vectors() -> None:
    _, report, report_payload, _, _, successor, successor_payload = _edge_artifacts()

    assert str(report.report_id) == "fef0b781-925c-55de-b2b7-d75060ad9f91"
    assert len(report_payload) == 3781
    assert sha256(report_payload).hexdigest() == (
        "b6f55780fb9c86d24773a2f6ca7b768ea62b9eafadebf8f6bcec8b7da549663f"
    )
    assert str(successor.checkpoint_id) == "5bc5282e-8505-5be6-88bb-4e54b686e67f"
    assert len(successor_payload) == 1344
    assert sha256(successor_payload).hexdigest() == (
        "46147ca747450380c3e3ed591f9072fc26b9d5c93a30496e3abec753606209cd"
    )


@pytest.mark.parametrize(
    "target",
    (
        _target("10", "0", "972.50"),
        _target("5", "0", "1486.25"),
        _target("0", "0", "2000"),
    ),
)
def test_successors_cover_no_action_partial_and_full_sale(target) -> None:
    (
        result,
        _,
        report_payload,
        checkpoint_payload,
        snapshot_payload,
        successor,
        payload,
    ) = _edge_artifacts(target=target)

    verified = verify_checkpointed_paper_cycle_successor_edge(
        report_payload,
        checkpoint_payload,
        snapshot_payload,
        payload,
        calendar(),
    )

    assert verified.status is PaperAccountCheckpointEdgeVerificationStatus.PASS
    assert successor.account_state.compact_state == result.final_compact_state
    assert successor.account_state.realized_profit_loss_before == (
        result.opening_realized_profit_loss
    )
    assert successor.account_state.realized_profit_loss_after == (
        result.final_realized_profit_loss
    )


def test_report_verifier_replays_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, report_payload, checkpoint_payload, snapshot_payload, _, successor_payload = (
        _edge_artifacts()
    )
    import trading_bot.runtime.checkpointed_paper_cycle_report as report_module

    original = report_module.execute_checkpointed_verified_snapshot_paper_cycle
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        report_module, "execute_checkpointed_verified_snapshot_paper_cycle", counted
    )
    verified = verify_checkpointed_paper_cycle_successor_edge(
        report_payload,
        checkpoint_payload,
        snapshot_payload,
        successor_payload,
        calendar(),
    )

    assert verified.status is PaperAccountCheckpointEdgeVerificationStatus.PASS
    assert calls == 1


def test_report_and_successor_tampering_fail_closed_without_replay() -> None:
    _, _, report_payload, checkpoint_payload, snapshot_payload, _, successor_payload = (
        _edge_artifacts()
    )
    tampered_report = report_payload.replace(
        b'"runtime_result_id":"', b'"runtime_result_id":"f', 1
    )
    report_result = verify_checkpointed_paper_cycle_report(
        tampered_report,
        checkpoint_payload,
        snapshot_payload,
        calendar(),
    )
    tampered_successor = successor_payload + b" "
    edge_result = verify_checkpointed_paper_cycle_successor_edge(
        report_payload,
        checkpoint_payload,
        snapshot_payload,
        tampered_successor,
        calendar(),
    )

    assert report_result.status is CheckpointedPaperCycleReportVerificationStatus.FAIL
    assert report_result.diagnostics[0].code is (
        CheckpointedPaperCycleReportVerificationCode.STRICT_SCHEMA_CANONICALIZATION_FAILURE
    )
    assert edge_result.status is PaperAccountCheckpointEdgeVerificationStatus.FAIL
    assert edge_result.diagnostics[0].code is (
        PaperAccountCheckpointEdgeVerificationCode.SUCCESSOR_SCHEMA_FAILURE
    )


def test_report_reconciliation_detects_canonical_identity_preserving_tampering() -> (
    None
):
    _, _, report_payload, checkpoint_payload, snapshot_payload, _, _ = _edge_artifacts()
    report = parse_checkpointed_paper_cycle_report(report_payload)
    runtime_result_id = str(report.evidence.runtime_result_id)
    replacement = ("f" if runtime_result_id[0] != "f" else "e") + runtime_result_id[1:]
    tampered = report_payload.replace(
        runtime_result_id.encode("utf-8"), replacement.encode("utf-8"), 1
    )

    result = verify_checkpointed_paper_cycle_report(
        tampered,
        checkpoint_payload,
        snapshot_payload,
        calendar(),
    )

    assert result.status is CheckpointedPaperCycleReportVerificationStatus.FAIL
    assert result.diagnostics[0].code is (
        CheckpointedPaperCycleReportVerificationCode.RESULT_RECONCILIATION_FAILURE
    )


def test_successor_identity_is_deterministic_and_binds_accounting_state() -> None:
    result, _, report_payload, _, _, successor, payload = _edge_artifacts()
    repeated = create_successor_paper_account_checkpoint(
        successor.prior_checkpoint,
        successor.prior_lineage_id,
        result,
        checkpointed_paper_cycle_report_reference(report_payload),
    )

    assert repeated == successor
    assert serialize_successor_paper_account_checkpoint(repeated) == payload
    with pytest.raises(ValueError):
        replace(
            successor.account_state,
            realized_profit_loss_before=Decimal("999"),
        )


def test_successor_preserves_negative_pnl_and_commissioned_fill_evidence() -> None:
    checkpoint = _checkpoint_verification(
        cash="0",
        positions=(_position(quantity="3", basis="0.6"),),
        realized="-7.25",
    )
    no_action = _edge_artifacts(
        checkpoint=checkpoint,
        target=_target("3", "0", "0"),
    )
    commissioned_policies = _policies(
        assumptions=RebalanceAssumptions(fixed_commission=Decimal("1")),
        risk_limits=RiskLimits(
            max_position_percent=Decimal("1"),
            max_total_exposure_percent=Decimal("1"),
            minimum_cash_reserve_percent=Decimal("0"),
            estimated_commission=Decimal("1"),
        ),
        fill_policy=PaperFillPolicy(fixed_commission=Decimal("1")),
    )
    commissioned = _edge_artifacts(policies=commissioned_policies)

    no_action_successor = no_action[5]
    commission_result = commissioned[0]
    commission_successor = commissioned[5]

    assert no_action_successor.account_state.realized_profit_loss_before == Decimal(
        "-7.25"
    )
    assert no_action_successor.account_state.realized_profit_loss_after == Decimal(
        "-7.25"
    )
    assert all(
        fill.commission == Decimal("1") for fill in commission_result.cycle_fills
    )
    assert commission_successor.account_state.realized_profit_loss_after == (
        commission_result.final_realized_profit_loss
    )


def test_verified_successor_edge_can_authorize_one_later_cycle() -> None:
    (
        _,
        _,
        first_report_payload,
        genesis_payload,
        snapshot_payload,
        _,
        first_successor,
    ) = _edge_artifacts()
    first_edge = verify_checkpointed_paper_cycle_successor_edge(
        first_report_payload,
        genesis_payload,
        snapshot_payload,
        first_successor,
        calendar(),
    )
    prior = verified_prior_from_successor_edge(first_edge)
    snapshot_verification = _later_snapshot_verification()
    later_request = _later_cycle_request(snapshot_verification)

    later = execute_checkpointed_verified_snapshot_paper_cycle(
        later_request,
        prior,
        snapshot_verification,
        calendar(),
    )

    assert later.prior_checkpoint_id == prior.checkpoint_id
    assert later.prior_sequence == 1
    assert later.prior_lineage_id == prior.lineage_id
    assert later.opening_compact_state == prior.compact_state
    assert later.application_id != first_edge.successor_checkpoint.application_id


def test_successor_prior_replays_and_verifies_a_second_complete_edge() -> None:
    _, _, first_report_payload, genesis_payload, snapshot_payload, _, first_payload = (
        _edge_artifacts()
    )
    first_edge = verify_checkpointed_paper_cycle_successor_edge(
        first_report_payload,
        genesis_payload,
        snapshot_payload,
        first_payload,
        calendar(),
    )
    prior = verified_prior_from_successor_edge(first_edge)
    snapshot_verification = _later_snapshot_verification()
    later_request = _later_cycle_request(snapshot_verification)
    later = execute_checkpointed_verified_snapshot_paper_cycle(
        later_request,
        prior,
        snapshot_verification,
        calendar(),
    )
    later_report = checkpointed_paper_cycle_report_from_result(later)
    later_report_payload = serialize_checkpointed_paper_cycle_report(later_report)
    later_successor = create_successor_paper_account_checkpoint(
        later_report.evidence.prior_checkpoint,
        later_report.evidence.prior_lineage_id,
        later,
        checkpointed_paper_cycle_report_reference(later_report_payload),
    )
    later_successor_payload = serialize_successor_paper_account_checkpoint(
        later_successor
    )

    report_verification = verify_checkpointed_paper_cycle_report(
        later_report_payload,
        first_payload,
        serialize_daily_snapshot(snapshot_verification.snapshot),
        calendar(),
        verified_prior=prior,
    )
    second_edge = verify_checkpointed_paper_cycle_successor_edge(
        later_report_payload,
        first_payload,
        serialize_daily_snapshot(snapshot_verification.snapshot),
        later_successor_payload,
        calendar(),
        verified_prior=prior,
    )

    assert (
        report_verification.status
        is CheckpointedPaperCycleReportVerificationStatus.PASS
    )
    assert report_verification.cycle_result == later
    assert second_edge.status is PaperAccountCheckpointEdgeVerificationStatus.PASS
    assert second_edge.successor_checkpoint == later_successor
    assert verified_prior_from_successor_edge(second_edge).sequence == 2


def test_successor_prior_rejects_bytes_not_bound_to_its_verified_edge() -> None:
    _, _, first_report_payload, genesis_payload, snapshot_payload, _, first_payload = (
        _edge_artifacts()
    )
    first_edge = verify_checkpointed_paper_cycle_successor_edge(
        first_report_payload,
        genesis_payload,
        snapshot_payload,
        first_payload,
        calendar(),
    )
    prior = verified_prior_from_successor_edge(first_edge)
    snapshot_verification = _later_snapshot_verification()
    later = execute_checkpointed_verified_snapshot_paper_cycle(
        _later_cycle_request(snapshot_verification),
        prior,
        snapshot_verification,
        calendar(),
    )
    report_payload = serialize_checkpointed_paper_cycle_report(
        checkpointed_paper_cycle_report_from_result(later)
    )

    verification = verify_checkpointed_paper_cycle_report(
        report_payload,
        genesis_payload,
        serialize_daily_snapshot(snapshot_verification.snapshot),
        calendar(),
        verified_prior=prior,
    )

    assert verification.status is CheckpointedPaperCycleReportVerificationStatus.FAIL
    assert verification.diagnostics[0].code is (
        CheckpointedPaperCycleReportVerificationCode.PRIOR_CHECKPOINT_LINKAGE_FAILURE
    )
