"""Deterministic initialization of a paper ledger from explicit account state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import MAX_EMAX, MAX_PREC, MIN_EMIN, Context, Decimal, localcontext
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import OrderFill, OrderSide, Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.ledger.exceptions import InvalidPaperLedgerInitializationError
from trading_bot.ledger.ledger import PaperLedger

_ZERO = Decimal("0")
_EVIDENCE_VERSION = "paper-ledger-initialization-evidence-v1"


def _finite_decimal(value: object, name: str, *, positive: bool) -> Decimal:
    if type(value) is not Decimal:
        raise InvalidPaperLedgerInitializationError(f"{name} must be a Decimal")
    if not value.is_finite():
        raise InvalidPaperLedgerInitializationError(f"{name} must be finite")
    normalized = _ZERO if value == _ZERO else value
    if positive:
        if normalized <= _ZERO:
            raise InvalidPaperLedgerInitializationError(
                f"{name} must be finite and positive"
            )
    elif normalized < _ZERO:
        raise InvalidPaperLedgerInitializationError(
            f"{name} must be finite and nonnegative"
        )
    return normalized


def _canonical_decimal(value: Decimal) -> str:
    """Render an exact finite Decimal without using the ambient context."""
    if not value.is_finite():
        raise InvalidPaperLedgerInitializationError("identity Decimal must be finite")
    sign, digits, exponent = value.as_tuple()
    text = "".join(str(digit) for digit in digits)
    if not text or set(text) == {"0"}:
        return "0"
    while text.endswith("0"):
        text = text[:-1]
        exponent += 1
    prefix = "-" if sign else ""
    if exponent >= 0:
        return prefix + text + ("0" * exponent)
    places = -exponent
    if len(text) > places:
        return prefix + text[:-places] + "." + text[-places:]
    return prefix + "0." + ("0" * (places - len(text))) + text


class PaperLedgerInitializationMode(StrEnum):
    """The supported explicit opening-account representations."""

    CASH_ONLY = "CASH_ONLY"
    BOOTSTRAP_FILLS = "BOOTSTRAP_FILLS"


@dataclass(frozen=True, slots=True)
class PaperLedgerInitializationPosition:
    """One ordered average-cost position represented by a synthetic BUY fill."""

    symbol: Symbol
    quantity: Decimal
    average_cost: Decimal

    def __post_init__(self) -> None:
        if type(self.symbol) is not Symbol:
            raise InvalidPaperLedgerInitializationError("symbol must be a Symbol")
        object.__setattr__(
            self,
            "quantity",
            _finite_decimal(self.quantity, "quantity", positive=True),
        )
        object.__setattr__(
            self,
            "average_cost",
            _finite_decimal(self.average_cost, "average_cost", positive=True),
        )


@dataclass(frozen=True, slots=True)
class PaperLedgerInitializationRequest:
    """All caller-owned inputs required to build one deterministic ledger."""

    mode: PaperLedgerInitializationMode
    as_of: datetime
    available_cash: Decimal
    positions: tuple[PaperLedgerInitializationPosition, ...]
    identity_namespace: UUID
    identity_material: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.mode, PaperLedgerInitializationMode):
            raise InvalidPaperLedgerInitializationError(
                "mode must be PaperLedgerInitializationMode"
            )
        try:
            as_of = normalize_utc(self.as_of, "as_of")
        except (TypeError, ValueError) as error:
            raise InvalidPaperLedgerInitializationError(str(error)) from error
        available_cash = _finite_decimal(
            self.available_cash,
            "available_cash",
            positive=False,
        )
        try:
            positions = tuple(self.positions)
        except TypeError as error:
            raise InvalidPaperLedgerInitializationError(
                "positions must be iterable"
            ) from error
        if any(
            type(item) is not PaperLedgerInitializationPosition for item in positions
        ):
            raise InvalidPaperLedgerInitializationError(
                "positions must contain PaperLedgerInitializationPosition values"
            )
        if len({item.symbol for item in positions}) != len(positions):
            raise InvalidPaperLedgerInitializationError(
                "position symbols must be unique"
            )
        if type(self.identity_namespace) is not UUID:
            raise InvalidPaperLedgerInitializationError(
                "identity_namespace must be a UUID"
            )
        try:
            identity_material = tuple(self.identity_material)
        except TypeError as error:
            raise InvalidPaperLedgerInitializationError(
                "identity_material must be iterable"
            ) from error
        if not identity_material or any(
            type(item) is not str or not item.strip() for item in identity_material
        ):
            raise InvalidPaperLedgerInitializationError(
                "identity_material must contain nonblank strings"
            )
        if self.mode is PaperLedgerInitializationMode.CASH_ONLY:
            if positions:
                raise InvalidPaperLedgerInitializationError(
                    "CASH_ONLY initialization requires no positions"
                )
            if available_cash == _ZERO:
                raise InvalidPaperLedgerInitializationError(
                    "zero cash without positions cannot initialize PaperLedger"
                )
        elif not positions:
            raise InvalidPaperLedgerInitializationError(
                "BOOTSTRAP_FILLS initialization requires at least one position"
            )
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "available_cash", available_cash)
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "identity_material", identity_material)


@dataclass(frozen=True, slots=True)
class PaperLedgerInitializationEvidence:
    """Immutable synthetic account-state evidence produced during initialization."""

    initialization_id: UUID
    request: PaperLedgerInitializationRequest
    bootstrap_fills: tuple[OrderFill, ...]

    def __post_init__(self) -> None:
        if type(self.initialization_id) is not UUID:
            raise InvalidPaperLedgerInitializationError(
                "initialization_id must be a UUID"
            )
        if type(self.request) is not PaperLedgerInitializationRequest:
            raise InvalidPaperLedgerInitializationError(
                "request must be PaperLedgerInitializationRequest"
            )
        try:
            fills = tuple(self.bootstrap_fills)
        except TypeError as error:
            raise InvalidPaperLedgerInitializationError(
                "bootstrap_fills must be iterable"
            ) from error
        if any(type(item) is not OrderFill for item in fills):
            raise InvalidPaperLedgerInitializationError(
                "bootstrap_fills must contain OrderFill values"
            )
        if self.request.mode is PaperLedgerInitializationMode.CASH_ONLY:
            if fills:
                raise InvalidPaperLedgerInitializationError(
                    "CASH_ONLY initialization must not produce bootstrap fills"
                )
        else:
            if len(fills) != len(self.request.positions):
                raise InvalidPaperLedgerInitializationError(
                    "bootstrap fills must match initialized positions"
                )
            if len({item.fill_id for item in fills}) != len(fills) or len(
                {item.order_id for item in fills}
            ) != len(fills):
                raise InvalidPaperLedgerInitializationError(
                    "bootstrap fill and order IDs must be unique"
                )
            for ordinal, (position, fill) in enumerate(
                zip(self.request.positions, fills, strict=True)
            ):
                if (
                    fill != _bootstrap_fill(self.request, ordinal, position)
                    or fill.side is not OrderSide.BUY
                    or fill.commission != _ZERO
                ):
                    raise InvalidPaperLedgerInitializationError(
                        "bootstrap fill does not match its initialized position"
                    )
        expected_id = _evidence_id(self.request, fills)
        if self.initialization_id != expected_id:
            raise InvalidPaperLedgerInitializationError(
                "initialization_id does not match deterministic identity"
            )
        object.__setattr__(self, "bootstrap_fills", fills)


def initialize_paper_ledger(
    request: PaperLedgerInitializationRequest,
) -> tuple[PaperLedger, PaperLedgerInitializationEvidence]:
    """Build one ledger and immutable synthetic opening-state evidence."""
    if type(request) is not PaperLedgerInitializationRequest:
        raise TypeError("request must be PaperLedgerInitializationRequest")
    with localcontext(_initialization_context(request)):
        basis = sum(
            (item.quantity * item.average_cost for item in request.positions),
            start=_ZERO,
        )
        ledger = PaperLedger(request.available_cash + basis)
        fills = tuple(
            _bootstrap_fill(request, ordinal, position)
            for ordinal, position in enumerate(request.positions)
        )
        for fill in fills:
            ledger.apply_fill(fill)
    evidence = PaperLedgerInitializationEvidence(
        _evidence_id(request, fills),
        request,
        fills,
    )
    return ledger, evidence


def _bootstrap_fill(
    request: PaperLedgerInitializationRequest,
    ordinal: int,
    position: PaperLedgerInitializationPosition,
) -> OrderFill:
    material = "|".join(
        (
            *request.identity_material,
            str(ordinal),
            str(position.symbol),
            _canonical_decimal(position.quantity),
            _canonical_decimal(position.average_cost),
            request.as_of.isoformat(),
        )
    )
    return OrderFill(
        uuid5(request.identity_namespace, f"{material}|fill"),
        uuid5(request.identity_namespace, f"{material}|order"),
        position.symbol,
        OrderSide.BUY,
        position.quantity,
        position.average_cost,
        _ZERO,
        request.as_of,
    )


def _evidence_id(
    request: PaperLedgerInitializationRequest,
    fills: tuple[OrderFill, ...],
) -> UUID:
    material = "|".join(
        (
            _EVIDENCE_VERSION,
            request.mode.value,
            request.as_of.isoformat(),
            _canonical_decimal(request.available_cash),
            *request.identity_material,
            *(
                ":".join(
                    (
                        str(item.symbol),
                        _canonical_decimal(item.quantity),
                        _canonical_decimal(item.average_cost),
                    )
                )
                for item in request.positions
            ),
            *(str(item.fill_id) for item in fills),
        )
    )
    return uuid5(request.identity_namespace, material)


def _initialization_context(request: PaperLedgerInitializationRequest) -> Context:
    """Return a sufficient private context for exact bootstrap arithmetic."""
    terms = [
        (
            request.available_cash.as_tuple().exponent,
            len(request.available_cash.as_tuple().digits),
            request.available_cash.adjusted(),
        )
    ]
    for position in request.positions:
        quantity_tuple = position.quantity.as_tuple()
        cost_tuple = position.average_cost.as_tuple()
        terms.append(
            (
                quantity_tuple.exponent + cost_tuple.exponent,
                len(quantity_tuple.digits) + len(cost_tuple.digits),
                position.quantity.adjusted() + position.average_cost.adjusted() + 1,
            )
        )
    minimum_exponent = min(item[0] for item in terms)
    maximum_adjusted = max(item[2] for item in terms)
    carry_digits = len(str(len(terms))) + 1
    precision = max(28, maximum_adjusted - minimum_exponent + carry_digits)
    if precision > MAX_PREC:
        raise InvalidPaperLedgerInitializationError(
            "initialization values require unsupported Decimal precision"
        )
    return Context(prec=precision, Emax=MAX_EMAX, Emin=MIN_EMIN)
