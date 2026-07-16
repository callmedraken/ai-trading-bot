from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from trading_bot.domain import (
    Order,
    OrderFill,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Symbol,
    TimeInForce,
)

NOW = datetime(2026, 1, 2, 12, tzinfo=UTC)


def make_request(**overrides: object) -> OrderRequest:
    values: dict[str, object] = {
        "symbol": Symbol("SPY"),
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "quantity": Decimal("2.5"),
        "time_in_force": TimeInForce.DAY,
        "submitted_at": NOW,
    }
    values.update(overrides)
    return OrderRequest.create(**values)  # type: ignore[arg-type]


def test_enum_names_and_values_are_consistent() -> None:
    assert OrderSide.BUY.value == "BUY"
    assert OrderType.LIMIT.value == "LIMIT"
    assert OrderStatus.PARTIALLY_FILLED.value == "PARTIALLY_FILLED"
    assert TimeInForce.GOOD_TIL_CANCELED.value == "GOOD_TIL_CANCELED"


def test_order_request_factory_generates_or_preserves_id() -> None:
    generated = make_request()
    supplied = uuid4()
    assert isinstance(generated.order_id, UUID)
    assert make_request(order_id=supplied).order_id == supplied
    assert generated.quantity == Decimal("2.5")


def test_order_request_normalizes_timestamp_to_utc() -> None:
    local = datetime(2026, 1, 2, 4, tzinfo=timezone(timedelta(hours=-8)))
    assert make_request(submitted_at=local).submitted_at == NOW


@pytest.mark.parametrize("quantity", [Decimal("0"), Decimal("-1")])
def test_order_request_rejects_nonpositive_quantity(quantity: Decimal) -> None:
    with pytest.raises(ValueError, match="quantity"):
        make_request(quantity=quantity)


def test_limit_order_requires_positive_limit_price() -> None:
    with pytest.raises(ValueError, match="require a limit_price"):
        make_request(order_type=OrderType.LIMIT)
    with pytest.raises(ValueError, match="limit_price"):
        make_request(order_type=OrderType.LIMIT, limit_price=Decimal("0"))
    request = make_request(order_type=OrderType.LIMIT, limit_price=Decimal("101.25"))
    assert request.limit_price == Decimal("101.25")


def test_market_order_rejects_limit_price() -> None:
    with pytest.raises(ValueError, match="must not"):
        make_request(limit_price=Decimal("100"))


def test_order_request_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        make_request(submitted_at=datetime(2026, 1, 2))


def make_fill(side: OrderSide = OrderSide.BUY, **overrides: object) -> OrderFill:
    values: dict[str, object] = {
        "fill_id": uuid4(),
        "order_id": uuid4(),
        "symbol": Symbol("SPY"),
        "side": side,
        "quantity": Decimal("2.5"),
        "price": Decimal("100.20"),
        "commission": Decimal("1.00"),
        "filled_at": NOW,
    }
    values.update(overrides)
    return OrderFill(**values)  # type: ignore[arg-type]


def test_fill_amounts_and_buy_cash_effect() -> None:
    fill = make_fill()
    assert fill.gross_amount == Decimal("250.500")
    assert fill.net_cash_effect == Decimal("-251.500")


def test_sell_cash_effect_is_positive_after_commission() -> None:
    fill = make_fill(OrderSide.SELL)
    assert fill.net_cash_effect == Decimal("249.500")


@pytest.mark.parametrize("field", ["quantity", "price"])
def test_fill_rejects_nonpositive_quantity_or_price(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        make_fill(**{field: Decimal("0")})


def test_fill_rejects_negative_commission_and_normalizes_time() -> None:
    with pytest.raises(ValueError, match="commission"):
        make_fill(commission=Decimal("-0.01"))
    local = datetime(2026, 1, 2, 4, tzinfo=timezone(timedelta(hours=-8)))
    assert make_fill(filled_at=local).filled_at == NOW


@pytest.mark.parametrize(
    ("status", "filled", "average"),
    [
        (OrderStatus.PENDING, Decimal("0"), None),
        (OrderStatus.SUBMITTED, Decimal("0"), None),
        (OrderStatus.PARTIALLY_FILLED, Decimal("1"), Decimal("100")),
        (OrderStatus.FILLED, Decimal("2.5"), Decimal("100")),
        (OrderStatus.CANCELED, Decimal("1"), Decimal("100")),
    ],
)
def test_valid_order_states(
    status: OrderStatus, filled: Decimal, average: Decimal | None
) -> None:
    order = Order(make_request(), status, filled, average)
    assert order.remaining_quantity == Decimal("2.5") - filled


@pytest.mark.parametrize("filled", [Decimal("-1"), Decimal("3")])
def test_order_rejects_out_of_range_filled_quantity(filled: Decimal) -> None:
    with pytest.raises(ValueError, match="filled_quantity"):
        Order(make_request(), filled_quantity=filled)


def test_filled_and_partially_filled_status_consistency() -> None:
    with pytest.raises(ValueError, match="full quantity"):
        Order(make_request(), OrderStatus.FILLED, Decimal("1"), Decimal("100"))
    with pytest.raises(ValueError, match="partial quantity"):
        Order(
            make_request(),
            OrderStatus.PARTIALLY_FILLED,
            Decimal("0"),
            Decimal("100"),
        )
    with pytest.raises(ValueError, match="average_fill_price"):
        Order(make_request(), OrderStatus.FILLED, Decimal("2.5"))


@pytest.mark.parametrize(
    "status",
    [
        OrderStatus.PENDING,
        OrderStatus.SUBMITTED,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
    ],
)
def test_nonfilled_statuses_cannot_claim_full_quantity(status: OrderStatus) -> None:
    reason = "risk check" if status is OrderStatus.REJECTED else None
    with pytest.raises(ValueError, match="full quantity"):
        Order(make_request(), status, Decimal("2.5"), Decimal("100"), reason)


def test_rejection_reason_consistency() -> None:
    rejected = Order(
        make_request(), OrderStatus.REJECTED, rejection_reason="risk limit"
    )
    assert rejected.rejection_reason == "risk limit"
    with pytest.raises(ValueError, match="nonblank"):
        Order(make_request(), OrderStatus.REJECTED, rejection_reason=" ")
    with pytest.raises(ValueError, match="non-rejected"):
        Order(make_request(), rejection_reason="not allowed")


def test_order_models_are_immutable() -> None:
    request = make_request()
    with pytest.raises(FrozenInstanceError):
        request.quantity = Decimal("5")  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        Order(request).status = OrderStatus.FILLED  # type: ignore[misc]
