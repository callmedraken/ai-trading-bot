from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.approval_paper import (
    ApprovalDeclineState,
    ApprovalPaperConflictError,
    ApprovalPaperIntent,
    ApprovalPaperQuote,
    ApprovalPaperStore,
    ApprovalPaperStoreError,
    UnsupportedApprovalPaperOrderError,
)
from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce
from trading_bot.ledger import PositionNotFoundError
from trading_bot.risk import RiskOutcome


def _intent(
    *,
    approval_id: str = "approval-1",
    side: OrderSide = OrderSide.BUY,
    desired: Decimal = Decimal("10"),
    approved: Decimal = Decimal("10"),
    outcome: RiskOutcome = RiskOutcome.APPROVED,
    order_type: OrderType = OrderType.MARKET,
    proposed_at: datetime | None = None,
) -> ApprovalPaperIntent:
    return ApprovalPaperIntent(
        approval_id=approval_id,
        proposal_id=UUID("11111111-1111-1111-1111-111111111111"),
        order_id=UUID(
            "22222222-2222-2222-2222-222222222222"
            if approval_id == "approval-1"
            else "33333333-3333-3333-3333-333333333333"
        ),
        symbol=Symbol("SPY"),
        side=side,
        desired_quantity=desired,
        approved_quantity=approved,
        risk_outcome=outcome,
        risk_reason_codes=(
            () if outcome is RiskOutcome.APPROVED else ("MAX_POSITION_PERCENT",)
        ),
        proposal_reason="model saw a validated trend signal",
        proposal_confidence=Decimal("0.72"),
        order_type=order_type,
        time_in_force=TimeInForce.DAY,
        proposed_at=proposed_at or datetime(2026, 10, 2, 15, 0, tzinfo=UTC),
        limit_price=Decimal("500") if order_type is OrderType.LIMIT else None,
    )


def _quote(
    *,
    bid: Decimal = Decimal("499"),
    ask: Decimal = Decimal("500"),
    observed_at: datetime | None = None,
) -> ApprovalPaperQuote:
    return ApprovalPaperQuote(
        Symbol("SPY"),
        bid,
        ask,
        observed_at or datetime(2026, 10, 2, 15, 0, 1, tzinfo=UTC),
    )


def test_market_buy_is_durable_idempotent_and_reconstructable(tmp_path) -> None:
    store = ApprovalPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    intent = _intent()
    quote = _quote()

    first = store.record_market_approval(
        intent,
        quote,
        slippage_basis_points=Decimal("10"),
    )
    second = store.record_market_approval(
        intent,
        quote,
        slippage_basis_points=Decimal("10"),
    )

    assert first == second
    assert first.fill_price == Decimal("500.500")
    assert first.decline_state is ApprovalDeclineState.PENDING_DECLINE
    assert len(store.history()) == 1

    ledger = store.reconstruct_ledger()
    assert ledger.cash == Decimal("4995.000")
    position = ledger.get_position(Symbol("SPY"))
    assert position is not None
    assert position.quantity == Decimal("10")
    assert position.average_cost == Decimal("500.500")

    reopened = ApprovalPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    assert reopened.history() == (first,)
    assert reopened.reconstruct_ledger().cash == ledger.cash


def test_same_approval_id_with_different_quote_is_conflict(tmp_path) -> None:
    store = ApprovalPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    intent = _intent()
    store.record_market_approval(intent, _quote())

    with pytest.raises(ApprovalPaperConflictError):
        store.record_market_approval(
            intent,
            _quote(ask=Decimal("501")),
        )


def test_sell_closes_virtual_position_and_realizes_profit(tmp_path) -> None:
    store = ApprovalPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    store.record_market_approval(
        _intent(),
        _quote(bid=Decimal("99"), ask=Decimal("100")),
    )
    sell_time = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)
    sell = _intent(
        approval_id="approval-2",
        side=OrderSide.SELL,
        proposed_at=sell_time,
    )
    store.record_market_approval(
        sell,
        _quote(
            bid=Decimal("110"),
            ask=Decimal("111"),
            observed_at=sell_time + timedelta(seconds=1),
        ),
    )

    ledger = store.reconstruct_ledger()
    assert ledger.cash == Decimal("10100")
    assert ledger.get_position(Symbol("SPY")) is None
    assert ledger.realized_profit_loss == Decimal("100")


def test_sell_without_virtual_position_is_not_persisted(tmp_path) -> None:
    store = ApprovalPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    sell = _intent(side=OrderSide.SELL)

    with pytest.raises(PositionNotFoundError):
        store.record_market_approval(sell, _quote())

    assert store.history() == ()


def test_decline_confirmation_is_durable_and_idempotent(tmp_path) -> None:
    store = ApprovalPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    record = store.record_market_approval(_intent(), _quote())
    declined_at = record.filled_at + timedelta(seconds=2)

    first = store.mark_declined("approval-1", declined_at=declined_at)
    second = store.mark_declined(
        "approval-1",
        declined_at=declined_at + timedelta(seconds=10),
    )

    assert first == second
    assert first.decline_state is ApprovalDeclineState.DECLINED
    assert first.declined_at == declined_at
    assert store.pending_declines() == ()


def test_limit_approval_is_explicitly_out_of_scope_for_phase_a(tmp_path) -> None:
    store = ApprovalPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )

    with pytest.raises(UnsupportedApprovalPaperOrderError):
        store.record_market_approval(
            _intent(order_type=OrderType.LIMIT),
            _quote(),
        )


def test_quote_must_follow_proposal() -> None:
    proposed = datetime(2026, 10, 2, 15, 0, 1, tzinfo=UTC)
    intent = _intent(proposed_at=proposed)

    with pytest.raises(ValueError, match="cannot precede"):
        ApprovalPaperStore(
            ":memory:",
            starting_cash=Decimal("10000"),
        ).record_market_approval(
            intent,
            _quote(observed_at=proposed - timedelta(microseconds=1)),
        )


def test_store_rejects_different_starting_cash_on_reopen(tmp_path) -> None:
    path = tmp_path / "paper.sqlite"
    ApprovalPaperStore(path, starting_cash=Decimal("10000"))

    with pytest.raises(ApprovalPaperStoreError, match="starting_cash mismatch"):
        ApprovalPaperStore(path, starting_cash=Decimal("25000"))


def test_resized_intent_preserves_ai_and_risk_audit_fields(tmp_path) -> None:
    store = ApprovalPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    intent = _intent(
        desired=Decimal("10"),
        approved=Decimal("5"),
        outcome=RiskOutcome.RESIZED,
    )

    record = store.record_market_approval(intent, _quote())
    restored = store.get(record.intent.approval_id)

    assert restored == record
    assert restored is not None
    assert restored.intent.proposal_reason == "model saw a validated trend signal"
    assert restored.intent.proposal_confidence == Decimal("0.72")
    assert restored.intent.risk_outcome is RiskOutcome.RESIZED
    assert restored.intent.risk_reason_codes == ("MAX_POSITION_PERCENT",)


def test_account_snapshot_uses_virtual_paper_state(tmp_path) -> None:
    store = ApprovalPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    store.record_market_approval(
        _intent(),
        _quote(bid=Decimal("99"), ask=Decimal("100")),
    )

    snapshot = store.create_account_snapshot(
        {Symbol("SPY"): Decimal("105")},
        timestamp=datetime(2026, 10, 2, 20, 0, tzinfo=UTC),
    )

    assert snapshot.cash == Decimal("9000")
    assert snapshot.positions_market_value == Decimal("1050")
    assert snapshot.equity == Decimal("10050")
    assert snapshot.unrealized_profit_loss == Decimal("50")
