"""Canonical, versioned identities for durable logical order intents."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid5

from trading_bot.domain import OrderSide, Symbol

from .models import IntentKind, IntentLifecycle, LogicalOrderIntent, SourceIdentity

_INTENT_NAMESPACE = UUID("5c78d324-5e83-5dd8-a85e-1a835317fc57")


def canonical_decimal(value: Decimal) -> str:
    """Render a finite Decimal without ambient-context normalization."""

    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("canonical decimal must be finite")
    sign, digits_tuple, exponent = value.as_tuple()
    digits = list(digits_tuple)
    if not any(digits):
        return "0"
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exponent += 1
    coefficient = "".join(str(digit) for digit in digits)
    if exponent >= 0:
        result = coefficient + ("0" * exponent)
    else:
        point = len(coefficient) + exponent
        if point > 0:
            result = f"{coefficient[:point]}.{coefficient[point:]}"
        else:
            result = f"0.{('0' * -point)}{coefficient}"
    return f"-{result}" if sign else result


def order_terms_material(
    *,
    kind: IntentKind,
    symbol: Symbol,
    side: OrderSide,
    quantity: Decimal,
    stop_price: Decimal | None,
) -> str:
    """Return the exact logical terms bound by review and persisted intents."""

    return "\n".join(
        (
            "arch148-order-terms/v1",
            kind.value,
            symbol.value,
            side.value,
            canonical_decimal(quantity),
            "none" if stop_price is None else canonical_decimal(stop_price),
        )
    )


def create_order_intent(
    *,
    owner_id: UUID,
    source_identity: SourceIdentity,
    logical_sequence: int,
    kind: IntentKind,
    symbol: Symbol,
    side: OrderSide,
    quantity: Decimal,
    stop_price: Decimal | None,
    created_at: datetime,
    lifecycle: IntentLifecycle = IntentLifecycle.PROPOSED,
) -> LogicalOrderIntent:
    """Create stable intent/ref IDs from owner, source, sequence and economics."""

    terms = order_terms_material(
        kind=kind,
        symbol=symbol,
        side=side,
        quantity=quantity,
        stop_price=stop_price,
    )
    canonical = "\n".join(
        (
            "arch148-logical-order-intent/v1",
            owner_id.hex,
            source_identity.head,
            source_identity.tree,
            str(logical_sequence),
            terms,
        )
    )
    intent_id = uuid5(_INTENT_NAMESPACE, f"intent\n{canonical}")
    ref_id = str(uuid5(_INTENT_NAMESPACE, f"ref\n{canonical}"))
    return LogicalOrderIntent(
        intent_id=intent_id,
        ref_id=ref_id,
        logical_sequence=logical_sequence,
        kind=kind,
        symbol=symbol,
        side=side,
        quantity=quantity,
        stop_price=stop_price,
        source_identity=source_identity,
        owner_id=owner_id,
        lifecycle=lifecycle,
        terms_digest=sha256(terms.encode("utf-8")).hexdigest(),
        created_at=created_at,
    )
