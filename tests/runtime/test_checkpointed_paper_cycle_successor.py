"""Focused immutable successor-checkpoint and one-edge verification coverage."""

from dataclasses import replace
from decimal import Decimal
from hashlib import sha256

import pytest
from tests.runtime.test_checkpointed_verified_snapshot_execution import (
    _checkpoint_verification,
    _execute,
    _position,
    _target,
)
from tests.runtime.test_verified_snapshot_preparation import (
    _policies,
    _verification,
    calendar,
)

from trading_bot.execution import PaperFillPolicy
from trading_bot.market_data import serialize_daily_snapshot
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
    parse_checkpointed_paper_cycle_report,
    parse_successor_paper_account_checkpoint,
    serialize_checkpointed_paper_cycle_report,
    serialize_successor_paper_account_checkpoint,
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
