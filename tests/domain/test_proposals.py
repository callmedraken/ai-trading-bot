from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from trading_bot.domain import OrderSide, Symbol, TradeProposal


def test_trade_proposal_factory_normalizes_time_and_generates_id() -> None:
    local = datetime(2026, 1, 2, 4, tzinfo=timezone(timedelta(hours=-8)))
    proposal = TradeProposal.create(
        symbol=Symbol("SPY"),
        side=OrderSide.BUY,
        desired_quantity=Decimal("1.5"),
        created_at=local,
        reason="momentum signal",
        confidence=Decimal("0.75"),
    )
    assert isinstance(proposal.proposal_id, UUID)
    assert proposal.created_at == datetime(2026, 1, 2, 12, tzinfo=UTC)
    assert proposal.confidence == Decimal("0.75")


def test_trade_proposal_preserves_supplied_id() -> None:
    proposal_id = uuid4()
    proposal = TradeProposal.create(
        proposal_id=proposal_id,
        symbol=Symbol("SPY"),
        side=OrderSide.SELL,
        desired_quantity=Decimal("1"),
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        reason="rebalance",
    )
    assert proposal.proposal_id == proposal_id


@pytest.mark.parametrize("quantity", [Decimal("0"), Decimal("-1")])
def test_trade_proposal_rejects_nonpositive_quantity(quantity: Decimal) -> None:
    with pytest.raises(ValueError, match="desired_quantity"):
        TradeProposal.create(
            symbol=Symbol("SPY"),
            side=OrderSide.BUY,
            desired_quantity=quantity,
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
            reason="test",
        )


@pytest.mark.parametrize("reason", ["", "   "])
def test_trade_proposal_rejects_blank_reason(reason: str) -> None:
    with pytest.raises(ValueError, match="reason"):
        TradeProposal.create(
            symbol=Symbol("SPY"),
            side=OrderSide.BUY,
            desired_quantity=Decimal("1"),
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
            reason=reason,
        )


@pytest.mark.parametrize("confidence", [Decimal("-0.01"), Decimal("1.01")])
def test_trade_proposal_rejects_confidence_outside_unit_range(
    confidence: Decimal,
) -> None:
    with pytest.raises(ValueError, match="confidence"):
        TradeProposal.create(
            symbol=Symbol("SPY"),
            side=OrderSide.BUY,
            desired_quantity=Decimal("1"),
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
            reason="test",
            confidence=confidence,
        )


def test_trade_proposal_accepts_confidence_boundaries_and_is_immutable() -> None:
    for confidence in (Decimal("0"), Decimal("1")):
        proposal = TradeProposal.create(
            symbol=Symbol("SPY"),
            side=OrderSide.BUY,
            desired_quantity=Decimal("1"),
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
            reason="test",
            confidence=confidence,
        )
        with pytest.raises(FrozenInstanceError):
            proposal.reason = "changed"  # type: ignore[misc]
