from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from trading_bot.domain import OrderType, TimeInForce
from trading_bot.execution import ExecutionInstruction, OrderEvent, OrderEventType

NOW = datetime(2026, 1, 2, 12, tzinfo=UTC)


def test_instruction_normalizes_timestamp_and_is_immutable() -> None:
    local = datetime(2026, 1, 2, 4, tzinfo=timezone(timedelta(hours=-8)))
    instruction = ExecutionInstruction(OrderType.MARKET, TimeInForce.DAY, local)
    assert instruction.created_at == NOW
    with pytest.raises(FrozenInstanceError):
        instruction.order_type = OrderType.LIMIT  # type: ignore[misc]


def test_limit_instruction_requires_positive_price() -> None:
    with pytest.raises(ValueError, match="require a limit_price"):
        ExecutionInstruction(OrderType.LIMIT, TimeInForce.DAY, NOW)
    with pytest.raises(ValueError, match="limit_price"):
        ExecutionInstruction(OrderType.LIMIT, TimeInForce.DAY, NOW, Decimal("0"))
    instruction = ExecutionInstruction(
        OrderType.LIMIT, TimeInForce.GOOD_TIL_CANCELED, NOW, Decimal("100.25")
    )
    assert instruction.limit_price == Decimal("100.25")


def test_market_instruction_rejects_limit_price() -> None:
    with pytest.raises(ValueError, match="must not"):
        ExecutionInstruction(OrderType.MARKET, TimeInForce.DAY, NOW, Decimal("100"))


def test_event_validation_and_utc_normalization() -> None:
    fill_id = uuid4()
    event = OrderEvent(
        uuid4(),
        uuid4(),
        OrderEventType.PARTIALLY_FILLED,
        NOW,
        fill_id=fill_id,
    )
    assert event.fill_id == fill_id
    assert event.occurred_at.tzinfo is UTC
    with pytest.raises(ValueError, match="fill_id"):
        OrderEvent(uuid4(), uuid4(), OrderEventType.FILLED, NOW)


def test_rejection_and_cancellation_reason_validation() -> None:
    with pytest.raises(ValueError, match="nonblank"):
        OrderEvent(uuid4(), uuid4(), OrderEventType.REJECTED, NOW, reason=" ")
    with pytest.raises(ValueError, match="nonblank"):
        OrderEvent(uuid4(), uuid4(), OrderEventType.CANCELED, NOW, reason="")
    assert (
        OrderEvent(
            uuid4(), uuid4(), OrderEventType.CANCELED, NOW, reason="user request"
        ).reason
        == "user request"
    )
