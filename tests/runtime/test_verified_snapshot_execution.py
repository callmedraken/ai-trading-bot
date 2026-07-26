"""Focused tests for one-shot prepared verified-snapshot paper execution."""

import builtins
import socket
from dataclasses import replace
from datetime import timedelta
from decimal import ROUND_DOWN, ROUND_UP, Decimal, localcontext
from uuid import UUID

import pytest
from tests.market_data.daily_snapshot_test_support import CAPTURED_AT, QQQ, SPY
from tests.runtime.test_verified_snapshot_preparation import (
    _policies,
    _request,
    _verification,
)

from trading_bot.domain import OrderSide, OrderStatus
from trading_bot.execution import PaperFillPolicy
from trading_bot.portfolio import MetadataEntry
from trading_bot.rebalancing import (
    RebalanceAssumptions,
    RebalanceProposalPolicy,
    RebalanceStatus,
)
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits, RiskOutcome
from trading_bot.runtime import (
    ExplicitQuantityTarget,
    ExplicitQuantityTargetPortfolio,
    InvalidPreparedVerifiedSnapshotPaperCycleError,
    PaperPortfolioRuntime,
    VerifiedSnapshotAccountPosition,
    VerifiedSnapshotAccountState,
    VerifiedSnapshotPaperCycleInsufficientCashError,
    VerifiedSnapshotPaperCycleRuntimeExecutionError,
    VerifiedSnapshotPaperCycleStatus,
    execute_prepared_verified_snapshot_paper_cycle,
    prepare_verified_snapshot_paper_cycle,
)

_ACCOUNT_STATE_ID = UUID("7b93f860-fef6-5bc0-a60b-746bb1f35c5e")
_TARGET_ID = UUID("bf8999ae-f854-553d-9fd8-4c49e3424442")


def _prepared(
    *,
    account_state: VerifiedSnapshotAccountState | None = None,
    target: ExplicitQuantityTargetPortfolio | None = None,
    open_references=None,
    policies=None,
    metadata: tuple[MetadataEntry, ...] = (),
):
    verification = _verification()
    request = _request(
        verification=verification,
        account_state=account_state,
        target=target,
        open_references=open_references,
        policies=policies,
    )
    if metadata:
        request = replace(request, metadata=metadata)
    return prepare_verified_snapshot_paper_cycle(
        request,
        verification,
        __import__(
            "tests.market_data.daily_snapshot_test_support",
            fromlist=["calendar"],
        ).calendar(),
    )


def _account(
    cash: str,
    positions: tuple[VerifiedSnapshotAccountPosition, ...] = (),
) -> VerifiedSnapshotAccountState:
    return VerifiedSnapshotAccountState(
        _ACCOUNT_STATE_ID,
        CAPTURED_AT - timedelta(minutes=1),
        Decimal(cash),
        positions,
    )


def _target(
    spy: str,
    qqq: str,
    cash: str,
) -> ExplicitQuantityTargetPortfolio:
    return ExplicitQuantityTargetPortfolio(
        _TARGET_ID,
        (
            ExplicitQuantityTarget(SPY, Decimal(spy)),
            ExplicitQuantityTarget(QQQ, Decimal(qqq)),
        ),
        Decimal(cash),
    )


def _held_spy() -> tuple[VerifiedSnapshotAccountPosition, ...]:
    return (
        VerifiedSnapshotAccountPosition(
            SPY,
            Decimal("10"),
            Decimal("100"),
        ),
    )


def _permissive_limits(**overrides) -> RiskLimits:
    values = dict(
        max_position_percent=Decimal("1"),
        max_total_exposure_percent=Decimal("1"),
        minimum_cash_reserve_percent=Decimal("0"),
    )
    values.update(overrides)
    return RiskLimits(**values)


def test_buy_only_executes_one_deterministic_full_fill() -> None:
    result = execute_prepared_verified_snapshot_paper_cycle(
        _prepared(
            account_state=_account("2000"),
            target=_target("0", "5", "985"),
        )
    )

    assert result.status is VerifiedSnapshotPaperCycleStatus.APPLIED
    assert tuple(fill.side for fill in result.cycle_fills) == (OrderSide.BUY,)
    assert result.cycle_fills[0].quantity == Decimal("5")
    assert result.cycle_fills[0].price == Decimal("204")
    assert result.final_account_state.cash == Decimal("980")
    assert result.final_account_state.positions[0].quantity == Decimal("5")
    assert result.runtime_result.order_result.orders[0].status is OrderStatus.PENDING
    assert (
        result.runtime_result.application_result.evaluations[0].updated_order.status
        is OrderStatus.FILLED
    )


def test_sell_only_executes_and_reconciles_realized_profit_loss() -> None:
    result = execute_prepared_verified_snapshot_paper_cycle(
        _prepared(
            account_state=_account("972.50", _held_spy()),
            target=_target("5", "0", "1486.25"),
        )
    )

    assert tuple(fill.side for fill in result.cycle_fills) == (OrderSide.SELL,)
    assert result.cycle_fills[0].quantity == Decimal("5")
    assert result.final_account_state.cash == Decimal("1487.50")
    assert result.final_account_state.positions[0].quantity == Decimal("5")
    assert result.final_account_state.realized_profit_loss == Decimal("15")


def test_mixed_sell_buy_preserves_sells_before_buys_across_every_stage() -> None:
    result = execute_prepared_verified_snapshot_paper_cycle(_prepared())

    assert tuple(item.side.value for item in result.runtime_result.plan.trades) == (
        "SELL",
        "BUY",
    )
    assert tuple(
        item.side for item in result.runtime_result.proposal_result.proposals
    ) == (OrderSide.SELL, OrderSide.BUY)
    assert tuple(
        item.decision.proposal.side
        for item in result.runtime_result.risk_result.evaluations
    ) == (OrderSide.SELL, OrderSide.BUY)
    assert tuple(
        item.request.side for item in result.runtime_result.order_result.orders
    ) == (OrderSide.SELL, OrderSide.BUY)
    assert tuple(item.side for item in result.cycle_fills) == (
        OrderSide.SELL,
        OrderSide.BUY,
    )
    assert tuple(
        item.fill.side for item in result.runtime_result.application_result.evaluations
    ) == (OrderSide.SELL, OrderSide.BUY)


def test_complete_liquidation_removes_position_and_retains_profit() -> None:
    result = execute_prepared_verified_snapshot_paper_cycle(
        _prepared(
            account_state=_account("972.50", _held_spy()),
            target=_target("0", "0", "2000"),
        )
    )

    assert result.final_account_state.positions == ()
    assert result.final_account_state.cash == Decimal("2002.50")
    assert result.final_account_state.realized_profit_loss == Decimal("30")


def test_no_action_is_successful_complete_empty_cycle() -> None:
    result = execute_prepared_verified_snapshot_paper_cycle(
        _prepared(
            account_state=_account("972.50", _held_spy()),
            target=_target("10", "0", "972.50"),
        )
    )

    assert result.status is VerifiedSnapshotPaperCycleStatus.NO_ACTION
    assert result.cycle_fills == ()
    assert result.runtime_result.proposal_result.proposals == ()
    assert result.runtime_result.order_result.orders == ()
    assert result.pre_engine_state_id == result.post_engine_state_id
    assert result.pre_ledger_state_id == result.post_ledger_state_id
    assert result.final_account_state.cash == result.initial_cash


def test_all_risk_rejected_returns_no_action_and_creates_no_orders() -> None:
    limits = RiskLimits(
        max_position_percent=Decimal("0.80"),
        max_total_exposure_percent=Decimal("0.90"),
        minimum_cash_reserve_percent=Decimal("0.10"),
        allow_buying=False,
        allow_selling=False,
    )
    result = execute_prepared_verified_snapshot_paper_cycle(
        _prepared(
            policies=_policies(
                risk_limits=limits,
                trading_enabled=False,
            )
        )
    )

    assert result.status is VerifiedSnapshotPaperCycleStatus.NO_ACTION
    assert result.runtime_result.risk_result.rejected_count == 2
    assert result.runtime_result.order_result.orders == ()
    assert result.cycle_fills == ()


def test_resized_proposal_executes_existing_approved_quantity() -> None:
    limits = _permissive_limits(max_order_notional=Decimal("406"))
    result = execute_prepared_verified_snapshot_paper_cycle(
        _prepared(
            account_state=_account("2000"),
            target=_target("0", "5", "985"),
            policies=_policies(risk_limits=limits),
        )
    )

    evaluation = result.runtime_result.risk_result.evaluations[0]
    assert evaluation.decision.outcome is RiskOutcome.RESIZED
    assert evaluation.decision.approved_quantity == Decimal("2")
    assert result.runtime_result.order_result.orders[0].request.quantity == Decimal("2")
    assert result.cycle_fills[0].quantity == Decimal("2")


def test_mixed_approval_rejection_is_applied_and_rejected_has_no_order() -> None:
    limits = RiskLimits(
        max_position_percent=Decimal("0.80"),
        max_total_exposure_percent=Decimal("0.90"),
        minimum_cash_reserve_percent=Decimal("0.10"),
        allow_buying=False,
        allow_selling=True,
    )
    result = execute_prepared_verified_snapshot_paper_cycle(
        _prepared(policies=_policies(risk_limits=limits))
    )

    assert result.status is VerifiedSnapshotPaperCycleStatus.APPLIED
    assert result.runtime_result.risk_result.approved_count == 1
    assert result.runtime_result.risk_result.rejected_count == 1
    assert tuple(
        item.request.symbol for item in result.runtime_result.order_result.orders
    ) == (SPY,)
    assert tuple(item.symbol for item in result.cycle_fills) == (SPY,)


def test_sell_proceeds_enabled_fund_later_buy() -> None:
    result = execute_prepared_verified_snapshot_paper_cycle(
        _prepared(
            account_state=_account("0", _held_spy()),
            target=_target("0", "4.11", "193.17"),
            policies=_policies(risk_limits=_permissive_limits()),
        )
    )

    assert tuple(item.side for item in result.cycle_fills) == (
        OrderSide.SELL,
        OrderSide.BUY,
    )
    assert result.runtime_result.risk_result.withheld_sell_proceeds == Decimal("0")


def test_sell_proceeds_withheld_produce_eligible_partial_sell_only_plan() -> None:
    policies = _policies(
        assumptions=RebalanceAssumptions(use_planned_sell_proceeds=False),
        risk_limits=_permissive_limits(),
        risk_policy=PortfolioRiskPolicy(False),
    )
    result = execute_prepared_verified_snapshot_paper_cycle(
        _prepared(
            account_state=_account("0", _held_spy()),
            target=_target("0", "4.11", "193.17"),
            policies=policies,
        )
    )

    assert result.runtime_result.plan.status is RebalanceStatus.PARTIAL
    assert tuple(item.side for item in result.cycle_fills) == (OrderSide.SELL,)
    assert result.runtime_result.risk_result.withheld_sell_proceeds == Decimal(
        "1027.500"
    )


def test_ineligible_partial_plan_raises_typed_runtime_failure() -> None:
    policies = replace(
        _policies(
            assumptions=RebalanceAssumptions(use_planned_sell_proceeds=False),
            risk_limits=_permissive_limits(),
            risk_policy=PortfolioRiskPolicy(False),
        ),
        proposal_policy=RebalanceProposalPolicy(False),
    )
    prepared = _prepared(
        account_state=_account("0", _held_spy()),
        target=_target("0", "4.11", "193.17"),
        policies=policies,
    )

    with pytest.raises(VerifiedSnapshotPaperCycleRuntimeExecutionError):
        execute_prepared_verified_snapshot_paper_cycle(prepared)


def test_deterministic_full_fills_match_every_order_exactly() -> None:
    result = execute_prepared_verified_snapshot_paper_cycle(_prepared())

    orders = result.runtime_result.order_result.orders
    for order, fill, application in zip(
        orders,
        result.cycle_fills,
        result.runtime_result.application_result.evaluations,
        strict=True,
    ):
        assert fill.order_id == order.request.order_id
        assert fill.quantity == order.request.quantity
        assert application.updated_order.filled_quantity == order.request.quantity
        assert application.updated_order.status is OrderStatus.FILLED


def test_invokes_existing_runtime_exactly_once(monkeypatch) -> None:
    original = PaperPortfolioRuntime.run_cycle
    calls = []

    def counted(self, request):
        calls.append(request.request_id)
        return original(self, request)

    monkeypatch.setattr(PaperPortfolioRuntime, "run_cycle", counted)

    result = execute_prepared_verified_snapshot_paper_cycle(_prepared())

    assert calls == [result.preparation.request_id]


def test_gap_up_insufficient_cash_is_typed_atomic_failure() -> None:
    base = _prepared(
        account_state=_account("2000"),
        target=_target("0", "9", "173"),
        policies=_policies(risk_limits=_permissive_limits()),
    )
    references = tuple(
        replace(
            item,
            caller_asserted_open_reference_price=(
                Decimal("103") if item.symbol == SPY else Decimal("300")
            ),
        )
        for item in base.open_references
    )
    prepared = _prepared(
        account_state=_account("2000"),
        target=_target("0", "9", "173"),
        open_references=references,
        policies=_policies(risk_limits=_permissive_limits()),
    )

    with pytest.raises(VerifiedSnapshotPaperCycleInsufficientCashError) as error:
        execute_prepared_verified_snapshot_paper_cycle(prepared)

    assert not hasattr(error.value, "runtime")
    assert not hasattr(error.value, "ledger")


def test_order_fill_state_and_bootstrap_evidence_reconcile() -> None:
    result = execute_prepared_verified_snapshot_paper_cycle(_prepared())

    assert result.bootstrap_evidence.request.available_cash == result.initial_cash
    assert len(result.bootstrap_evidence.bootstrap_fills) == 1
    assert result.runtime_result.pre_ledger_state_id == result.pre_ledger_state_id
    assert result.runtime_result.post_ledger_state_id == result.post_ledger_state_id
    assert result.runtime_result.application_result.post_ledger_state_id == (
        result.post_ledger_state_id
    )
    assert result.final_account_state.cash == Decimal("982.500")
    assert tuple(item.symbol for item in result.final_account_state.positions) == (QQQ,)


def test_equal_independent_execution_has_identical_complete_evidence() -> None:
    first = execute_prepared_verified_snapshot_paper_cycle(_prepared())
    second = execute_prepared_verified_snapshot_paper_cycle(_prepared())

    assert first == second
    assert (
        first.result_id
        == second.result_id
        == UUID("afac18a6-bd93-5dc0-bf9e-518751a88a33")
    )
    assert first.runtime_result.result_id == second.runtime_result.result_id
    assert tuple(item.fill_id for item in first.cycle_fills) == tuple(
        item.fill_id for item in second.cycle_fills
    )
    assert first.pre_engine_state_id == second.pre_engine_state_id
    assert first.post_engine_state_id == second.post_engine_state_id
    assert first.pre_ledger_state_id == second.pre_ledger_state_id
    assert first.post_ledger_state_id == second.post_ledger_state_id


def test_execution_is_isolated_from_ambient_decimal_context() -> None:
    prepared = _prepared()
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_DOWN
        low = execute_prepared_verified_snapshot_paper_cycle(prepared)
        assert context.prec == 6
        assert context.rounding is ROUND_DOWN
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_UP
        high = execute_prepared_verified_snapshot_paper_cycle(prepared)
        assert context.prec == 50
        assert context.rounding is ROUND_UP

    assert low == high


def test_result_does_not_expose_private_mutable_runtime_state() -> None:
    result = execute_prepared_verified_snapshot_paper_cycle(_prepared())

    assert not hasattr(result, "runtime")
    assert not hasattr(result, "engine")
    assert not hasattr(result, "ledger")
    assert not hasattr(result, "planner")
    assert not hasattr(result, "__dict__")


def test_provider_network_and_filesystem_sentinels_are_never_invoked(
    monkeypatch,
) -> None:
    prepared = _prepared()

    def fail(*args, **kwargs):
        raise AssertionError("out-of-bound operation invoked")

    monkeypatch.setattr(builtins, "open", fail)
    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(
        "trading_bot.market_data.AlpacaDailySnapshotProvider.fetch",
        fail,
    )

    result = execute_prepared_verified_snapshot_paper_cycle(prepared)

    assert result.status is VerifiedSnapshotPaperCycleStatus.APPLIED


def test_rejects_non_prepared_input() -> None:
    with pytest.raises(InvalidPreparedVerifiedSnapshotPaperCycleError):
        execute_prepared_verified_snapshot_paper_cycle(object())  # type: ignore[arg-type]


def test_fill_policy_slippage_and_commission_remain_existing_runtime_behavior() -> None:
    policies = _policies(
        assumptions=RebalanceAssumptions(fixed_commission=Decimal("1")),
        risk_limits=RiskLimits(
            max_position_percent=Decimal("0.80"),
            max_total_exposure_percent=Decimal("0.90"),
            minimum_cash_reserve_percent=Decimal("0.10"),
            estimated_commission=Decimal("1"),
        ),
        fill_policy=PaperFillPolicy(
            slippage_basis_points=Decimal("10"),
            fixed_commission=Decimal("1"),
        ),
    )
    result = execute_prepared_verified_snapshot_paper_cycle(
        _prepared(policies=policies)
    )

    sell, buy = result.cycle_fills
    assert sell.price == Decimal("102.897")
    assert buy.price == Decimal("204.204")
    assert sell.commission == buy.commission == Decimal("1")
