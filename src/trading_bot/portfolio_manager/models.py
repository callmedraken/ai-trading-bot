"""Account-bound, observation-only Portfolio Manager domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc

_ZERO = Decimal("0")
_IDENTITY_NAMESPACE = UUID("b4b9ad1d-7ab8-5a2a-a631-522b2eb7ce20")


def canonical_decimal(value: Decimal) -> str:
    """Render a finite Decimal without consulting ambient Decimal context."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError("value must be a finite Decimal")
    if value == _ZERO:
        return "0"
    sign, digits_tuple, exponent = value.as_tuple()
    digits = list(digits_tuple)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exponent += 1
    prefix = "-" if sign else ""
    return f"{prefix}{''.join(str(digit) for digit in digits)}e{exponent}"


def _coefficient(value: Decimal) -> tuple[int, int]:
    sign, digits, exponent = value.as_tuple()
    coefficient = int("".join(str(digit) for digit in digits) or "0")
    return (-coefficient if sign else coefficient), exponent


def _from_coefficient(coefficient: int, exponent: int) -> Decimal:
    if coefficient == 0:
        return _ZERO
    sign = 1 if coefficient < 0 else 0
    digits = tuple(int(char) for char in str(abs(coefficient)))
    return Decimal((sign, digits, exponent))


def decimal_multiply(left: Decimal, right: Decimal) -> Decimal:
    """Multiply finite Decimals exactly, independent of the caller's context."""
    if not isinstance(left, Decimal) or not isinstance(right, Decimal):
        raise TypeError("decimal_multiply requires Decimal operands")
    if not left.is_finite() or not right.is_finite():
        raise ValueError("decimal_multiply requires finite operands")
    left_coefficient, left_exponent = _coefficient(left)
    right_coefficient, right_exponent = _coefficient(right)
    return _from_coefficient(
        left_coefficient * right_coefficient,
        left_exponent + right_exponent,
    )


def decimal_negate(value: Decimal) -> Decimal:
    """Negate without invoking the active Decimal context."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("decimal_negate requires a finite Decimal")
    return value.copy_negate()


def decimal_sum(values: tuple[Decimal, ...] | list[Decimal]) -> Decimal:
    """Sum finite Decimals exactly, independent of the caller's context."""
    if not values:
        return _ZERO
    if any(not isinstance(value, Decimal) or not value.is_finite() for value in values):
        raise ValueError("decimal_sum requires finite Decimal values")
    parts = tuple(_coefficient(value) for value in values)
    exponent = min(item[1] for item in parts)
    coefficient = sum(
        (
            value * (10 ** (value_exponent - exponent))
            for value, value_exponent in parts
        ),
        start=0,
    )
    return _from_coefficient(coefficient, exponent)


def decimal_subtract(left: Decimal, right: Decimal) -> Decimal:
    """Subtract finite Decimals exactly, independent of the caller's context."""
    return decimal_sum([left, decimal_negate(right)])


def _frame(values: tuple[str, ...]) -> str:
    return "".join(f"{len(value)}:{value}" for value in values)


def _identity(kind: str, values: tuple[str, ...]) -> UUID:
    return uuid5(_IDENTITY_NAMESPACE, _frame(("portfolio-manager/v1", kind, *values)))


def _decimal(value: Decimal | None, name: str) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a Decimal or None")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return _ZERO if value == _ZERO else value


def _fingerprint(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("account fingerprint must be lowercase SHA-256 hex")
    return value


class AccountBindingStatus(StrEnum):
    BOUND = "BOUND"
    SELECTION_REQUIRED = "SELECTION_REQUIRED"
    MULTIPLE_ELIGIBLE_ACCOUNTS = "MULTIPLE_ELIGIBLE_ACCOUNTS"
    SELECTED_ACCOUNT_UNAVAILABLE = "SELECTED_ACCOUNT_UNAVAILABLE"
    NO_ELIGIBLE_ACCOUNT = "NO_ELIGIBLE_ACCOUNT"


@dataclass(frozen=True, slots=True)
class AccountCandidate:
    """Sanitized account choice; raw account identifiers are never retained."""

    fingerprint: str
    eligible: bool

    def __post_init__(self) -> None:
        if _fingerprint(self.fingerprint) is None:
            raise ValueError("fingerprint is required")
        if not isinstance(self.eligible, bool):
            raise TypeError("eligible must be a bool")


@dataclass(frozen=True, slots=True)
class AccountBinding:
    """Explicit user-selected account fingerprint for PM state isolation."""

    fingerprint: str

    def __post_init__(self) -> None:
        if _fingerprint(self.fingerprint) is None:
            raise ValueError("fingerprint is required")

    @property
    def state_namespace(self) -> str:
        return f"portfolio-manager/{self.fingerprint}"


@dataclass(frozen=True, slots=True)
class AccountBindingResult:
    status: AccountBindingStatus
    binding: AccountBinding | None
    eligible_fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, AccountBindingStatus):
            raise TypeError("status must be AccountBindingStatus")
        fingerprints = tuple(self.eligible_fingerprints)
        if any(_fingerprint(item) is None for item in fingerprints):
            raise ValueError("eligible_fingerprints must contain SHA-256 values")
        if len(set(fingerprints)) != len(fingerprints):
            raise ValueError("eligible fingerprints must be unique")
        if self.status is AccountBindingStatus.BOUND:
            if self.binding is None or self.binding.fingerprint not in fingerprints:
                raise ValueError("BOUND requires a selected eligible account")
        elif self.binding is not None:
            raise ValueError("blocked account selection cannot carry a binding")
        object.__setattr__(self, "eligible_fingerprints", fingerprints)


class ObservationProvenance(StrEnum):
    SYNTHETIC = "SYNTHETIC"
    ROBINHOOD_READ_ONLY = "ROBINHOOD_READ_ONLY"


class OrderCoverage(StrEnum):
    SYNTHETIC_COMPLETE = "SYNTHETIC_COMPLETE"
    ROBINHOOD_AGENTIC_BOUNDED = "ROBINHOOD_AGENTIC_BOUNDED"
    UNKNOWN = "UNKNOWN"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class ObservationCondition(StrEnum):
    ACCOUNT_NOT_BOUND = "ACCOUNT_NOT_BOUND"
    ACCOUNT_MISMATCH = "ACCOUNT_MISMATCH"
    MULTIPLE_ELIGIBLE_ACCOUNTS = "MULTIPLE_ELIGIBLE_ACCOUNTS"
    PORTFOLIO_INCOMPLETE = "PORTFOLIO_INCOMPLETE"
    POSITIONS_INCOMPLETE = "POSITIONS_INCOMPLETE"
    QUOTES_INCOMPLETE = "QUOTES_INCOMPLETE"
    PAGINATION_INCOMPLETE = "PAGINATION_INCOMPLETE"
    ORDER_SCOPE_INCOMPLETE = "ORDER_SCOPE_INCOMPLETE"
    DUPLICATE_ORDER_ID = "DUPLICATE_ORDER_ID"
    UNKNOWN_ORDER_OWNER = "UNKNOWN_ORDER_OWNER"
    UNKNOWN_ORDER_STATE = "UNKNOWN_ORDER_STATE"
    UNSUPPORTED_ASSET = "UNSUPPORTED_ASSET"
    SHORT_POSITION = "SHORT_POSITION"
    POSITION_TYPE_UNKNOWN = "POSITION_TYPE_UNKNOWN"
    NEGATIVE_CASH = "NEGATIVE_CASH"
    MISSING_CASH = "MISSING_CASH"
    MISSING_BROKER_EQUITY = "MISSING_BROKER_EQUITY"
    MISSING_BUYING_POWER = "MISSING_BUYING_POWER"
    MISSING_UNLEVERAGED_BUYING_POWER = "MISSING_UNLEVERAGED_BUYING_POWER"
    BROKER_EQUITY_DIFFERS_FROM_LOCAL = "BROKER_EQUITY_DIFFERS_FROM_LOCAL"
    MISSING_PRICE = "MISSING_PRICE"
    STALE_PRICE = "STALE_PRICE"
    MISSING_VALUATION = "MISSING_VALUATION"
    RECONCILIATION_UNCERTAIN = "RECONCILIATION_UNCERTAIN"


class PositionType(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"


class OrderOwnership(StrEnum):
    BOT = "BOT"
    EXTERNAL = "EXTERNAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class PositionObservation:
    """Provider facts about one equity/ETF holding; no tax lots or entry dates."""

    symbol: Symbol
    quantity: Decimal
    available_to_sell: Decimal
    average_cost: Decimal | None
    current_price: Decimal | None
    price_observed_at: datetime | None
    supported: bool = True
    position_type: PositionType = PositionType.LONG

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        for name in ("quantity", "available_to_sell", "average_cost", "current_price"):
            object.__setattr__(self, name, _decimal(getattr(self, name), name))
        if self.quantity is None or self.available_to_sell is None:
            raise TypeError("quantity and available_to_sell are required")
        if self.available_to_sell < _ZERO:
            raise ValueError("available_to_sell must be nonnegative")
        if self.quantity >= _ZERO and self.available_to_sell > self.quantity:
            raise ValueError("available_to_sell cannot exceed a long quantity")
        if self.average_cost is not None and self.average_cost < _ZERO:
            raise ValueError("average_cost must be nonnegative when known")
        if self.current_price is not None and self.current_price <= _ZERO:
            raise ValueError("current_price must be positive when known")
        if self.current_price is None:
            if self.price_observed_at is not None:
                raise ValueError("missing price cannot have an observation timestamp")
        else:
            if self.price_observed_at is None:
                raise ValueError("known price requires an observation timestamp")
            object.__setattr__(
                self,
                "price_observed_at",
                normalize_utc(self.price_observed_at, "price_observed_at"),
            )
        if not isinstance(self.supported, bool):
            raise TypeError("supported must be a bool")
        if not isinstance(self.position_type, PositionType):
            raise TypeError("position_type must be PositionType")
        expected_type = (
            PositionType.SHORT
            if self.quantity < _ZERO
            else PositionType.FLAT
            if self.quantity == _ZERO
            else PositionType.LONG
        )
        if self.position_type not in {expected_type, PositionType.UNKNOWN}:
            raise ValueError("position_type disagrees with observed quantity")

    @property
    def market_value(self) -> Decimal | None:
        if self.current_price is None:
            return None
        return decimal_multiply(self.quantity, self.current_price)

    @property
    def unrealized_pnl(self) -> Decimal | None:
        if self.average_cost is None or self.current_price is None:
            return None
        return decimal_multiply(
            decimal_subtract(self.current_price, self.average_cost), self.quantity
        )


@dataclass(frozen=True, slots=True)
class OrderObservation:
    """A bounded observed order; IDs are memory-only identifiers, not attribution."""

    order_id: str = field(repr=False)
    symbol: Symbol
    side: str
    state: str
    quantity: Decimal | None
    filled_quantity: Decimal
    created_at: datetime
    ownership: OrderOwnership = OrderOwnership.UNKNOWN

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, str) or not self.order_id.strip():
            raise ValueError("order_id must be nonblank")
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if self.side not in {"buy", "sell", "BUY", "SELL"}:
            raise ValueError("side must be buy or sell")
        if not isinstance(self.state, str) or not self.state.strip():
            raise ValueError("state must be nonblank")
        object.__setattr__(self, "quantity", _decimal(self.quantity, "quantity"))
        filled = _decimal(self.filled_quantity, "filled_quantity")
        if filled is None or filled < _ZERO:
            raise ValueError("filled_quantity must be nonnegative")
        if self.quantity is not None and self.quantity < _ZERO:
            raise ValueError("quantity must be nonnegative")
        if self.quantity is not None and filled > self.quantity:
            raise ValueError("filled_quantity cannot exceed quantity")
        object.__setattr__(self, "filled_quantity", filled)
        object.__setattr__(
            self, "created_at", normalize_utc(self.created_at, "created_at")
        )
        if not isinstance(self.ownership, OrderOwnership):
            raise TypeError("ownership must be OrderOwnership")

    @property
    def pending(self) -> bool:
        normalized = self.state.casefold()
        return normalized not in {
            "filled",
            "canceled",
            "cancelled",
            "rejected",
            "expired",
        }


@dataclass(frozen=True, slots=True)
class ObservationCoverage:
    account_bound: bool
    portfolio_complete: bool
    positions_complete: bool
    quotes_complete: bool
    pagination_complete: bool
    order_scope: OrderCoverage

    def __post_init__(self) -> None:
        for name in (
            "account_bound",
            "portfolio_complete",
            "positions_complete",
            "quotes_complete",
            "pagination_complete",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        if not isinstance(self.order_scope, OrderCoverage):
            raise TypeError("order_scope must be OrderCoverage")

    @property
    def valuation_complete(self) -> bool:
        return (
            self.portfolio_complete and self.positions_complete and self.quotes_complete
        )

    @property
    def order_visibility_complete(self) -> bool:
        return self.order_scope is OrderCoverage.SYNTHETIC_COMPLETE


@dataclass(frozen=True, slots=True)
class PortfolioObservation:
    """One account-bound observed snapshot, including incomplete facts as facts."""

    observed_at: datetime
    account_fingerprint: str | None
    broker_reported_equity: Decimal | None
    cash: Decimal | None
    buying_power: Decimal | None
    unleveraged_buying_power: Decimal | None
    positions: tuple[PositionObservation, ...]
    orders: tuple[OrderObservation, ...]
    coverage: ObservationCoverage
    provenance: ObservationProvenance
    conditions: tuple[ObservationCondition, ...] = ()
    observed_account_fingerprint: str | None = None
    broker_reported_position_value: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )
        object.__setattr__(
            self, "account_fingerprint", _fingerprint(self.account_fingerprint)
        )
        observed_fingerprint = _fingerprint(self.observed_account_fingerprint)
        if observed_fingerprint is None:
            observed_fingerprint = self.account_fingerprint
        object.__setattr__(self, "observed_account_fingerprint", observed_fingerprint)
        for name in (
            "broker_reported_equity",
            "cash",
            "buying_power",
            "unleveraged_buying_power",
            "broker_reported_position_value",
        ):
            object.__setattr__(self, name, _decimal(getattr(self, name), name))
        positions = tuple(self.positions)
        orders = tuple(self.orders)
        conditions = tuple(self.conditions)
        if any(not isinstance(item, PositionObservation) for item in positions):
            raise TypeError("positions must contain PositionObservation values")
        if len({item.symbol for item in positions}) != len(positions):
            raise ValueError("position symbols must be unique")
        if any(not isinstance(item, OrderObservation) for item in orders):
            raise TypeError("orders must contain OrderObservation values")
        if any(not isinstance(item, ObservationCondition) for item in conditions):
            raise TypeError("conditions must contain ObservationCondition values")
        generated: list[ObservationCondition] = list(conditions)
        if not isinstance(self.coverage, ObservationCoverage):
            raise TypeError("coverage must be ObservationCoverage")
        if not isinstance(self.provenance, ObservationProvenance):
            raise TypeError("provenance must be ObservationProvenance")
        if self.account_fingerprint is None or not self.coverage.account_bound:
            generated.append(ObservationCondition.ACCOUNT_NOT_BOUND)
        if self.observed_account_fingerprint != self.account_fingerprint:
            generated.append(ObservationCondition.ACCOUNT_MISMATCH)
        if not self.coverage.portfolio_complete:
            generated.append(ObservationCondition.PORTFOLIO_INCOMPLETE)
        if not self.coverage.positions_complete:
            generated.append(ObservationCondition.POSITIONS_INCOMPLETE)
        if not self.coverage.quotes_complete:
            generated.append(ObservationCondition.QUOTES_INCOMPLETE)
        if not self.coverage.pagination_complete:
            generated.append(ObservationCondition.PAGINATION_INCOMPLETE)
        if self.coverage.order_scope is not OrderCoverage.SYNTHETIC_COMPLETE:
            generated.append(ObservationCondition.ORDER_SCOPE_INCOMPLETE)
        if self.cash is not None and self.cash < _ZERO:
            generated.append(ObservationCondition.NEGATIVE_CASH)
        if self.cash is None:
            generated.append(ObservationCondition.MISSING_CASH)
        if self.broker_reported_equity is None:
            generated.append(ObservationCondition.MISSING_BROKER_EQUITY)
        if self.buying_power is None:
            generated.append(ObservationCondition.MISSING_BUYING_POWER)
        if self.unleveraged_buying_power is None:
            generated.append(ObservationCondition.MISSING_UNLEVERAGED_BUYING_POWER)
        if any(not item.supported for item in positions):
            generated.append(ObservationCondition.UNSUPPORTED_ASSET)
        if any(item.quantity < _ZERO for item in positions):
            generated.append(ObservationCondition.SHORT_POSITION)
        if any(item.position_type is PositionType.UNKNOWN for item in positions):
            generated.append(ObservationCondition.POSITION_TYPE_UNKNOWN)
        if any(item.current_price is None for item in positions):
            generated.append(ObservationCondition.MISSING_PRICE)
        if self.cash is None or any(item.market_value is None for item in positions):
            generated.append(ObservationCondition.MISSING_VALUATION)
        if len({item.order_id for item in orders}) != len(orders):
            generated.append(ObservationCondition.DUPLICATE_ORDER_ID)
        if any(item.ownership is OrderOwnership.UNKNOWN for item in orders):
            generated.append(ObservationCondition.UNKNOWN_ORDER_OWNER)
        if any(
            item.pending
            and item.state.casefold()
            not in {
                "open",
                "queued",
                "partially_filled",
                "pending",
                "confirmed",
                "placed",
            }
            for item in orders
        ):
            generated.append(ObservationCondition.UNKNOWN_ORDER_STATE)
        if (
            self.provenance is ObservationProvenance.ROBINHOOD_READ_ONLY
            and self.coverage.order_scope is OrderCoverage.SYNTHETIC_COMPLETE
        ):
            generated.append(ObservationCondition.RECONCILIATION_UNCERTAIN)
        # Keep the original provider order and the first occurrence of each condition.
        normalized_conditions = tuple(dict.fromkeys(generated))
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "orders", orders)
        object.__setattr__(self, "conditions", normalized_conditions)
        if (
            self.broker_reported_equity is not None
            and self.locally_computed_equity is not None
            and self.broker_reported_equity != self.locally_computed_equity
        ):
            object.__setattr__(
                self,
                "conditions",
                tuple(
                    dict.fromkeys(
                        (
                            *normalized_conditions,
                            ObservationCondition.BROKER_EQUITY_DIFFERS_FROM_LOCAL,
                        )
                    )
                ),
            )

    @property
    def snapshot_id(self) -> UUID:
        values = [
            self.observed_at.isoformat(),
            self.account_fingerprint or "none",
            self.observed_account_fingerprint or "none",
            self.provenance.value,
            *(
                "none" if value is None else canonical_decimal(value)
                for value in (
                    self.broker_reported_equity,
                    self.cash,
                    self.buying_power,
                    self.unleveraged_buying_power,
                    self.broker_reported_position_value,
                )
            ),
            *(
                str(getattr(self.coverage, name))
                for name in (
                    "account_bound",
                    "portfolio_complete",
                    "positions_complete",
                    "quotes_complete",
                    "pagination_complete",
                    "order_scope",
                )
            ),
        ]
        for position in self.positions:
            values.extend(
                (
                    "position",
                    str(position.symbol),
                    canonical_decimal(position.quantity),
                    canonical_decimal(position.available_to_sell),
                    "none"
                    if position.average_cost is None
                    else canonical_decimal(position.average_cost),
                    "none"
                    if position.current_price is None
                    else canonical_decimal(position.current_price),
                    "none"
                    if position.price_observed_at is None
                    else position.price_observed_at.isoformat(),
                    str(position.supported),
                    position.position_type.value,
                )
            )
        for order in self.orders:
            values.extend(
                (
                    "order",
                    order.order_id,
                    str(order.symbol),
                    order.side.casefold(),
                    order.state.casefold(),
                    "none"
                    if order.quantity is None
                    else canonical_decimal(order.quantity),
                    canonical_decimal(order.filled_quantity),
                    order.created_at.isoformat(),
                    order.ownership.value,
                )
            )
        values.extend(condition.value for condition in self.conditions)
        return _identity("observation", tuple(values))

    @property
    def locally_computed_equity(self) -> Decimal | None:
        if self.cash is None or any(
            item.market_value is None for item in self.positions
        ):
            return None
        return decimal_sum(
            [
                self.cash,
                *(
                    item.market_value
                    for item in self.positions
                    if item.market_value is not None
                ),
            ]
        )

    @property
    def broker_to_local_equity_difference(self) -> Decimal | None:
        local_equity = self.locally_computed_equity
        if self.broker_reported_equity is None or local_equity is None:
            return None
        return decimal_subtract(self.broker_reported_equity, local_equity)

    @property
    def valuation_complete(self) -> bool:
        return (
            self.coverage.valuation_complete
            and self.locally_computed_equity is not None
        )

    @property
    def preview_eligible(self) -> bool:
        blocking_conditions = {
            ObservationCondition.ACCOUNT_NOT_BOUND,
            ObservationCondition.ACCOUNT_MISMATCH,
            ObservationCondition.MULTIPLE_ELIGIBLE_ACCOUNTS,
            ObservationCondition.PORTFOLIO_INCOMPLETE,
            ObservationCondition.POSITIONS_INCOMPLETE,
            ObservationCondition.QUOTES_INCOMPLETE,
            ObservationCondition.PAGINATION_INCOMPLETE,
            ObservationCondition.UNSUPPORTED_ASSET,
            ObservationCondition.SHORT_POSITION,
            ObservationCondition.POSITION_TYPE_UNKNOWN,
            ObservationCondition.NEGATIVE_CASH,
            ObservationCondition.MISSING_CASH,
            ObservationCondition.MISSING_BROKER_EQUITY,
            ObservationCondition.MISSING_BUYING_POWER,
            ObservationCondition.MISSING_UNLEVERAGED_BUYING_POWER,
            ObservationCondition.MISSING_PRICE,
            ObservationCondition.MISSING_VALUATION,
            ObservationCondition.STALE_PRICE,
            ObservationCondition.RECONCILIATION_UNCERTAIN,
            ObservationCondition.BROKER_EQUITY_DIFFERS_FROM_LOCAL,
            ObservationCondition.ORDER_SCOPE_INCOMPLETE,
            ObservationCondition.DUPLICATE_ORDER_ID,
            ObservationCondition.UNKNOWN_ORDER_OWNER,
            ObservationCondition.UNKNOWN_ORDER_STATE,
        }
        return self.valuation_complete and not bool(
            blocking_conditions.intersection(self.conditions)
        )
