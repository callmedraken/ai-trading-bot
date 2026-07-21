"""Internal deterministic fingerprints for public engine and ledger state."""

from decimal import Decimal
from uuid import UUID, uuid5

from trading_bot.domain import Order, OrderFill
from trading_bot.execution.engine import OrderEngine
from trading_bot.execution.models import OrderEvent
from trading_bot.ledger import PaperLedger

_ZERO = Decimal("0")
_NAMESPACE = UUID("07373b22-6336-568d-b4ba-b684544997a2")


def canonical_decimal(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("state Decimal values must be finite")
    normalized = _ZERO if value == _ZERO else value.normalize()
    return format(normalized, "f")


def engine_snapshot(engine: OrderEngine):  # type: ignore[no-untyped-def]
    orders = tuple(engine.orders.items())
    events = engine.get_events()
    fills = tuple((order_id, engine.get_fills(order_id)) for order_id, _ in orders)
    return orders, events, fills


def ledger_snapshot(ledger: PaperLedger):  # type: ignore[no-untyped-def]
    positions = tuple(sorted(ledger.positions.items(), key=lambda item: item[0].value))
    return ledger.cash, ledger.realized_profit_loss, positions, ledger.fills


def _order_material(order: Order) -> str:
    request = order.request
    return ":".join(
        (
            str(request.order_id),
            str(request.symbol),
            request.side.value,
            request.order_type.value,
            canonical_decimal(request.quantity),
            request.time_in_force.value,
            request.submitted_at.isoformat(),
            "none"
            if request.limit_price is None
            else canonical_decimal(request.limit_price),
            order.status.value,
            canonical_decimal(order.filled_quantity),
            "none"
            if order.average_fill_price is None
            else canonical_decimal(order.average_fill_price),
            "none" if order.rejection_reason is None else order.rejection_reason,
        )
    )


def _fill_material(fill: OrderFill) -> str:
    return ":".join(
        (
            str(fill.fill_id),
            str(fill.order_id),
            str(fill.symbol),
            fill.side.value,
            canonical_decimal(fill.quantity),
            canonical_decimal(fill.price),
            canonical_decimal(fill.commission),
            fill.filled_at.isoformat(),
        )
    )


def _event_material(event: OrderEvent) -> str:
    return ":".join(
        (
            str(event.event_id),
            str(event.order_id),
            event.event_type.value,
            event.occurred_at.isoformat(),
            "none" if event.fill_id is None else str(event.fill_id),
            "none" if event.reason is None else event.reason,
        )
    )


def engine_state_id(snapshot) -> UUID:  # type: ignore[no-untyped-def]
    orders, events, fills = snapshot
    material = "|".join(
        (
            "paper-fill-application-engine-state-v1",
            ";".join(_order_material(order) for _, order in orders),
            ";".join(_event_material(event) for event in events),
            ";".join(
                f"{order_id}=[{','.join(_fill_material(fill) for fill in history)}]"
                for order_id, history in fills
            ),
        )
    )
    return uuid5(_NAMESPACE, material)


def ledger_state_id(snapshot) -> UUID:  # type: ignore[no-untyped-def]
    cash, realized, positions, fills = snapshot
    material = "|".join(
        (
            "paper-fill-application-ledger-state-v1",
            canonical_decimal(cash),
            canonical_decimal(realized),
            ";".join(
                f"{symbol}:{canonical_decimal(position.quantity)}:"
                f"{canonical_decimal(position.average_cost)}"
                for symbol, position in positions
            ),
            ";".join(_fill_material(fill) for fill in fills),
        )
    )
    return uuid5(_NAMESPACE, material)
