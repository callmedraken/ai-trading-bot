"""Focused checkpoint-restored verified-snapshot paper-cycle coverage."""

import builtins
import socket
from dataclasses import FrozenInstanceError, replace
from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_UP, Decimal, localcontext
from pathlib import Path
from uuid import UUID

import pytest
from tests.market_data.daily_snapshot_test_support import (
    CAPTURED_AT,
    QQQ,
    SPY,
    calendar,
)
from tests.runtime.test_verified_snapshot_preparation import _policies, _verification

from trading_bot.domain import OrderSide
from trading_bot.execution import PaperFillPolicy
from trading_bot.market_calendar import TradingSession
from trading_bot.portfolio import MetadataEntry
from trading_bot.rebalancing import RebalanceAssumptions
from trading_bot.risk import RiskLimits, RiskOutcome
from trading_bot.runtime import (
    APPLICATION_ID_METADATA_KEY,
    CHECKPOINT_PRIOR_ID_METADATA_KEY,
    CHECKPOINT_PRIOR_SEQUENCE_METADATA_KEY,
    LINEAGE_PRIOR_ID_METADATA_KEY,
    CallerAssertedNextSessionOpenReference,
    CheckpointedVerifiedSnapshotPaperCycleCheckpointError,
    CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
    CheckpointedVerifiedSnapshotPaperCycleRequest,
    CheckpointedVerifiedSnapshotPaperCycleStatus,
    ExplicitQuantityTarget,
    ExplicitQuantityTargetPortfolio,
    InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError,
    InvalidCheckpointedVerifiedSnapshotPaperCycleRequestError,
    PaperAccountCheckpointPosition,
    PaperAccountGenesisRequest,
    PaperPortfolioRuntime,
    VerifiedDailySnapshotReference,
    create_genesis_paper_account_checkpoint,
    derive_checkpointed_verified_snapshot_application_id,
    execute_checkpointed_verified_snapshot_paper_cycle,
    serialize_paper_account_checkpoint,
    verify_genesis_paper_account_checkpoint,
)

_REQUEST_ID = UUID("9c35761f-40c1-5ea6-b220-f44f1945de25")
_TARGET_ID = UUID("d4c01c92-a47f-56d5-8027-8b48a60d8ed2")
_AS_OF = CAPTURED_AT - timedelta(minutes=1)


def _position(
    symbol=SPY,
    quantity: str = "10",
    basis: str = "1000",
) -> PaperAccountCheckpointPosition:
    return PaperAccountCheckpointPosition.from_exact_basis(
        symbol,
        Decimal(quantity),
        Decimal(basis),
    )


def _checkpoint_verification(
    *,
    cash: str = "972.50",
    positions: tuple[PaperAccountCheckpointPosition, ...] = (_position(),),
    realized: str = "0",
):
    checkpoint = create_genesis_paper_account_checkpoint(
        PaperAccountGenesisRequest(
            _AS_OF,
            Decimal(cash),
            positions,
            Decimal(realized),
            (MetadataEntry("source", "focused-test"),),
        )
    )
    payload = serialize_paper_account_checkpoint(checkpoint)
    return verify_genesis_paper_account_checkpoint(payload), payload


def _target(
    spy: str = "0",
    qqq: str = "5",
    cash: str = "985",
) -> ExplicitQuantityTargetPortfolio:
    return ExplicitQuantityTargetPortfolio(
        _TARGET_ID,
        (
            ExplicitQuantityTarget(SPY, Decimal(spy)),
            ExplicitQuantityTarget(QQQ, Decimal(qqq)),
        ),
        Decimal(cash),
    )


def _request(
    verification,
    *,
    target: ExplicitQuantityTargetPortfolio | None = None,
    policies=None,
    open_references=None,
    metadata: tuple[MetadataEntry, ...] = (),
) -> CheckpointedVerifiedSnapshotPaperCycleRequest:
    snapshot = verification.snapshot
    assert snapshot is not None
    return CheckpointedVerifiedSnapshotPaperCycleRequest(
        _REQUEST_ID,
        VerifiedDailySnapshotReference(
            snapshot.snapshot_id,
            verification.sha256,
            verification.byte_length,
        ),
        target or _target(),
        open_references
        or (
            CallerAssertedNextSessionOpenReference(
                SPY,
                TradingSession(date(2025, 1, 7)),
                Decimal("103"),
            ),
            CallerAssertedNextSessionOpenReference(
                QQQ,
                TradingSession(date(2025, 1, 7)),
                Decimal("204"),
            ),
        ),
        policies or _policies(),
        CAPTURED_AT + timedelta(minutes=1),
        CAPTURED_AT + timedelta(minutes=2),
        CAPTURED_AT + timedelta(hours=2),
        metadata,
    )


def _execute(
    *,
    checkpoint=None,
    target=None,
    policies=None,
    open_references=None,
    metadata: tuple[MetadataEntry, ...] = (),
):
    snapshot_verification = _verification()
    checkpoint_verification, _ = checkpoint or _checkpoint_verification()
    request = _request(
        snapshot_verification,
        target=target,
        policies=policies,
        open_references=open_references,
        metadata=metadata,
    )
    return execute_checkpointed_verified_snapshot_paper_cycle(
        request,
        checkpoint_verification,
        snapshot_verification,
        calendar(),
    )


def _permissive_limits(**overrides) -> RiskLimits:
    values = dict(
        max_position_percent=Decimal("1"),
        max_total_exposure_percent=Decimal("1"),
        minimum_cash_reserve_percent=Decimal("0"),
    )
    values.update(overrides)
    return RiskLimits(**values)


def test_verified_genesis_restoration_preserves_exact_opening_account() -> None:
    exact_basis = "0.6"
    checkpoint = _checkpoint_verification(
        cash="0",
        positions=(_position(quantity="3", basis=exact_basis),),
        realized="-7.25",
    )
    result = _execute(
        checkpoint=checkpoint,
        target=_target("3", "0", "0"),
    )

    assert result.status is CheckpointedVerifiedSnapshotPaperCycleStatus.NO_ACTION
    assert result.opening_compact_state.cash == Decimal("0")
    assert result.opening_compact_state.positions[0].total_cost_basis == Decimal(
        exact_basis
    )
    assert result.opening_realized_profit_loss == Decimal("-7.25")
    assert result.final_realized_profit_loss == Decimal("-7.25")
    assert (
        result.opening_compact_state.positions == result.final_compact_state.positions
    )
    assert result.final_compact_state.as_of == result.preparation.filled_at
    assert result.restoration_evidence.compact_state_id == (
        result.opening_compact_state.compact_state_id
    )
    assert result.runtime_result.fill_result.fills == ()


def test_buy_cycle_uses_exact_compact_restored_ledger() -> None:
    result = _execute(
        checkpoint=_checkpoint_verification(cash="2000", positions=()),
        target=_target("0", "5", "985"),
    )

    assert tuple(fill.side for fill in result.cycle_fills) == (OrderSide.BUY,)
    assert result.final_compact_state.cash == Decimal("980")
    assert result.final_compact_state.positions[0].symbol == QQQ
    assert result.final_compact_state.positions[0].quantity == Decimal("5")
    assert result.final_compact_state.positions[0].total_cost_basis == Decimal("1020")
    assert result.opening_compact_state.realized_profit_loss == Decimal("0")


@pytest.mark.parametrize(
    ("target", "expected_quantity", "expected_basis", "expected_cash"),
    (
        (
            _target("5", "0", "1486.25"),
            Decimal("5"),
            Decimal("500"),
            Decimal("1487.50"),
        ),
        (_target("0", "0", "2000"), None, None, Decimal("2002.50")),
    ),
)
def test_partial_and_full_sell_preserve_exact_accounting(
    target,
    expected_quantity,
    expected_basis,
    expected_cash,
) -> None:
    result = _execute(target=target)

    assert tuple(fill.side for fill in result.cycle_fills) == (OrderSide.SELL,)
    assert result.final_compact_state.cash == expected_cash
    if expected_quantity is None:
        assert result.final_compact_state.positions == ()
    else:
        position = result.final_compact_state.positions[0]
        assert position.quantity == expected_quantity
        assert position.total_cost_basis == expected_basis
    expected_realized = Decimal("30") if expected_quantity is None else Decimal("15")
    assert result.final_realized_profit_loss == expected_realized


def test_mixed_sell_buy_preserves_ordering_and_checkpoint_metadata() -> None:
    result = _execute(metadata=(MetadataEntry("caller", "retained"),))

    assert tuple(fill.side for fill in result.cycle_fills) == (
        OrderSide.SELL,
        OrderSide.BUY,
    )
    assert tuple(item.key for item in result.preparation.metadata) == (
        "caller",
        CHECKPOINT_PRIOR_ID_METADATA_KEY,
        CHECKPOINT_PRIOR_SEQUENCE_METADATA_KEY,
        LINEAGE_PRIOR_ID_METADATA_KEY,
        APPLICATION_ID_METADATA_KEY,
    )
    assert result.preparation.metadata[-1].value == str(result.application_id)


@pytest.mark.parametrize(
    ("realized", "spy_open", "target", "expected_sign"),
    (
        ("-5", "103", _target(), 1),
        ("-5", "90", _target("5", "0", "1486.25"), -1),
    ),
)
def test_commissions_update_positive_and_negative_cumulative_realized_pnl(
    realized,
    spy_open,
    target,
    expected_sign,
) -> None:
    policies = _policies(
        assumptions=RebalanceAssumptions(fixed_commission=Decimal("1")),
        risk_limits=RiskLimits(
            max_position_percent=Decimal("1"),
            max_total_exposure_percent=Decimal("1"),
            minimum_cash_reserve_percent=Decimal("0"),
            estimated_commission=Decimal("1"),
        ),
        fill_policy=PaperFillPolicy(fixed_commission=Decimal("1")),
    )
    snapshot_verification = _verification()
    references = _request(snapshot_verification).open_references
    references = tuple(
        replace(
            item,
            caller_asserted_open_reference_price=(
                Decimal(spy_open)
                if item.symbol == SPY
                else item.caller_asserted_open_reference_price
            ),
        )
        for item in references
    )
    result = _execute(
        checkpoint=_checkpoint_verification(realized=realized),
        target=target,
        policies=policies,
        open_references=references,
    )

    assert all(fill.commission == Decimal("1") for fill in result.cycle_fills)
    assert result.opening_realized_profit_loss == Decimal(realized)
    assert (result.final_realized_profit_loss > 0) is (expected_sign > 0)
    assert (result.final_realized_profit_loss < 0) is (expected_sign < 0)


def test_no_action_and_all_risk_rejected_are_successful() -> None:
    no_action = _execute(target=_target("10", "0", "972.50"))
    rejecting = _policies(
        risk_limits=RiskLimits(
            max_position_percent=Decimal("1"),
            max_total_exposure_percent=Decimal("1"),
            minimum_cash_reserve_percent=Decimal("0"),
            allow_buying=False,
            allow_selling=False,
        ),
        trading_enabled=False,
    )
    rejected = _execute(policies=rejecting)

    for result in (no_action, rejected):
        assert result.status is CheckpointedVerifiedSnapshotPaperCycleStatus.NO_ACTION
        assert result.cycle_fills == ()
        assert result.pre_engine_state_id == result.post_engine_state_id
        assert result.pre_ledger_state_id == result.post_ledger_state_id
        assert result.opening_compact_state.cash == result.final_compact_state.cash
        assert (
            result.opening_compact_state.positions
            == result.final_compact_state.positions
        )
    assert rejected.runtime_result.risk_result.rejected_count == 2


def test_resized_and_mixed_risk_outcomes_keep_existing_behavior() -> None:
    resized = _execute(
        checkpoint=_checkpoint_verification(cash="2000", positions=()),
        target=_target("0", "5", "985"),
        policies=_policies(
            risk_limits=_permissive_limits(max_order_notional=Decimal("406"))
        ),
    )
    mixed = _execute(
        policies=_policies(
            risk_limits=RiskLimits(
                max_position_percent=Decimal("1"),
                max_total_exposure_percent=Decimal("1"),
                minimum_cash_reserve_percent=Decimal("0"),
                allow_buying=False,
                allow_selling=True,
            )
        )
    )

    assert resized.runtime_result.risk_result.evaluations[0].decision.outcome is (
        RiskOutcome.RESIZED
    )
    assert resized.cycle_fills[0].quantity == Decimal("2")
    assert mixed.runtime_result.risk_result.approved_count == 1
    assert mixed.runtime_result.risk_result.rejected_count == 1
    assert tuple(fill.side for fill in mixed.cycle_fills) == (OrderSide.SELL,)


def test_gap_up_failure_is_atomic_and_returns_no_partial_result() -> None:
    verification = _verification()
    references = tuple(
        replace(
            item,
            caller_asserted_open_reference_price=(
                Decimal("103") if item.symbol == SPY else Decimal("300")
            ),
        )
        for item in _request(verification).open_references
    )

    with pytest.raises(
        CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError
    ) as error:
        _execute(
            checkpoint=_checkpoint_verification(cash="2000", positions=()),
            target=_target("0", "9", "173"),
            policies=_policies(risk_limits=_permissive_limits()),
            open_references=references,
        )

    assert not hasattr(error.value, "result")
    assert not hasattr(error.value, "runtime")
    assert not hasattr(error.value, "ledger")


def test_existing_runtime_is_invoked_exactly_once(monkeypatch) -> None:
    original = PaperPortfolioRuntime.run_cycle
    calls = []

    def counted(self, request):
        calls.append(request.request_id)
        return original(self, request)

    monkeypatch.setattr(PaperPortfolioRuntime, "run_cycle", counted)
    result = _execute()

    assert calls == [result.request_id]


@pytest.mark.parametrize(
    "prefix",
    ("checkpoint.", "lineage.", "application."),
)
def test_caller_reserved_metadata_is_rejected(prefix: str) -> None:
    verification = _verification()

    with pytest.raises(InvalidCheckpointedVerifiedSnapshotPaperCycleRequestError):
        _request(
            verification,
            metadata=(MetadataEntry(f"{prefix}caller", "forbidden"),),
        )


def test_application_and_result_identities_are_deterministic() -> None:
    first = _execute()
    second = _execute()

    assert first == second
    assert (
        first.application_id
        == derive_checkpointed_verified_snapshot_application_id(
            first.prior_checkpoint_id,
            first.request_id,
        )
        == UUID("2c819894-4911-5c62-b4f6-eb8cfa55f326")
    )
    assert (
        first.result_id
        == second.result_id
        == UUID("a7b57ef8-4507-5747-8c3b-8055bd51b7de")
    )
    assert first.preparation.preparation_id == second.preparation.preparation_id
    assert first.runtime_result.result_id == second.runtime_result.result_id
    assert first.runtime_result.application_result.result_id == (
        second.runtime_result.application_result.result_id
    )
    assert first.opening_compact_state.compact_state_id == (
        second.opening_compact_state.compact_state_id
    )
    assert first.final_compact_state.compact_state_id == (
        second.final_compact_state.compact_state_id
    )


def test_execution_is_independent_of_ambient_decimal_context() -> None:
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_DOWN
        low = _execute()
        assert context.prec == 6
        assert context.rounding is ROUND_DOWN
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_UP
        high = _execute()
        assert context.prec == 50
        assert context.rounding is ROUND_UP

    assert low == high


def test_result_reconciliation_rejects_changed_final_compact_state() -> None:
    result = _execute()
    changed = result.final_compact_state.create(
        as_of=result.final_compact_state.as_of,
        cash=result.final_compact_state.cash + Decimal("1"),
        positions=result.final_compact_state.positions,
        realized_profit_loss=result.final_compact_state.realized_profit_loss,
    )

    with pytest.raises(InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError):
        replace(result, final_compact_state=changed)


def test_private_mutable_state_does_not_escape_and_result_is_immutable() -> None:
    result = _execute()

    for name in ("runtime", "engine", "ledger", "planner", "__dict__"):
        assert not hasattr(result, name)
    with pytest.raises(FrozenInstanceError):
        result.status = CheckpointedVerifiedSnapshotPaperCycleStatus.NO_ACTION  # type: ignore[misc]


def test_provider_network_filesystem_and_broker_boundaries_are_not_invoked(
    monkeypatch,
) -> None:
    snapshot_verification = _verification()
    checkpoint_verification, _ = _checkpoint_verification()
    request = _request(snapshot_verification)
    bound_calendar = calendar()

    def fail(*args, **kwargs):
        raise AssertionError("out-of-bound operation invoked")

    monkeypatch.setattr(builtins, "open", fail)
    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(Path, "write_bytes", fail)
    monkeypatch.setattr(
        "trading_bot.market_data.AlpacaDailySnapshotProvider.fetch",
        fail,
    )

    result = execute_checkpointed_verified_snapshot_paper_cycle(
        request,
        checkpoint_verification,
        snapshot_verification,
        bound_calendar,
    )

    assert result.status is CheckpointedVerifiedSnapshotPaperCycleStatus.APPLIED


def test_incomplete_checkpoint_or_snapshot_verification_is_rejected() -> None:
    snapshot_verification = _verification()
    checkpoint_verification, payload = _checkpoint_verification()
    request = _request(snapshot_verification)
    failed_checkpoint = verify_genesis_paper_account_checkpoint(payload + b" ")

    with pytest.raises(CheckpointedVerifiedSnapshotPaperCycleCheckpointError):
        execute_checkpointed_verified_snapshot_paper_cycle(
            request,
            failed_checkpoint,
            snapshot_verification,
            calendar(),
        )
    with pytest.raises(InvalidCheckpointedVerifiedSnapshotPaperCycleRequestError):
        execute_checkpointed_verified_snapshot_paper_cycle(
            request,
            checkpoint_verification,
            object(),  # type: ignore[arg-type]
            calendar(),
        )
