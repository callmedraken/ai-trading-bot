"""Effect-free Architecture 148 runtime contracts.

These values describe source-owned decisions and injected evidence. They do not
open provider sessions or execute broker effects.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol
from uuid import UUID

from trading_bot.domain import OrderSide, Position, Symbol
from trading_bot.domain._validation import normalize_utc, require_decimal

QQQ = Symbol("QQQ")
TQQQ = Symbol("TQQQ")
SQQQ = Symbol("SQQQ")
TRADED_SYMBOLS = (TQQQ, SQQQ)
UNIVERSE_SYMBOLS = (QQQ, TQQQ, SQQQ)

_GIT_OBJECT_ID = re.compile(r"^[0-9a-f]{40}$")
_SAFE_FINGERPRINT = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def require_finite_decimal(value: Decimal, field_name: str) -> None:
    require_decimal(value, field_name)
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")


def decimal_sum_equals(left: Decimal, right: Decimal, total: Decimal) -> bool:
    """Compare a Decimal sum exactly without using the ambient context."""

    for name, value in (("left", left), ("right", right), ("total", total)):
        require_finite_decimal(value, name)
    common_exponent = min(
        left.as_tuple().exponent,
        right.as_tuple().exponent,
        total.as_tuple().exponent,
    )
    return _scaled_decimal_integer(left, common_exponent) + _scaled_decimal_integer(
        right, common_exponent
    ) == _scaled_decimal_integer(total, common_exponent)


def decimal_sum_less_or_equal(left: Decimal, right: Decimal, total: Decimal) -> bool:
    """Compare an exact Decimal sum to a total without ambient rounding."""

    for name, value in (("left", left), ("right", right), ("total", total)):
        require_finite_decimal(value, name)
    common_exponent = min(
        left.as_tuple().exponent,
        right.as_tuple().exponent,
        total.as_tuple().exponent,
    )
    return _scaled_decimal_integer(left, common_exponent) + _scaled_decimal_integer(
        right, common_exponent
    ) <= _scaled_decimal_integer(total, common_exponent)


def _scaled_decimal_integer(value: Decimal, exponent: int) -> int:
    sign, digits, value_exponent = value.as_tuple()
    coefficient = int("".join(str(digit) for digit in digits)) if digits else 0
    if sign:
        coefficient = -coefficient
    return coefficient * 10 ** (value_exponent - exponent)


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """The exact executable source identity bound to one runtime state."""

    head: str
    tree: str

    def __post_init__(self) -> None:
        for name in ("head", "tree"):
            value = getattr(self, name)
            if not isinstance(value, str) or _GIT_OBJECT_ID.fullmatch(value) is None:
                raise ValueError(f"{name} must be a lowercase 40-character Git ID")


@dataclass(frozen=True, slots=True)
class CompletedBar:
    """A five-minute QQQ bar timestamped at the interval's left edge."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    interpolated: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "timestamp", normalize_utc(self.timestamp, "timestamp")
        )
        for field_name in ("open", "high", "low", "close"):
            value = getattr(self, field_name)
            require_finite_decimal(value, field_name)
            if value <= Decimal("0"):
                raise ValueError(f"{field_name} must be positive")
        if self.high < max(self.open, self.low, self.close):
            raise ValueError("high must be at least open, low, and close")
        if self.low > min(self.open, self.high, self.close):
            raise ValueError("low must be at most open, high, and close")
        if not isinstance(self.volume, int) or isinstance(self.volume, bool):
            raise TypeError("volume must be an integer")
        if self.volume < 0:
            raise ValueError("volume must be nonnegative")
        if not isinstance(self.interpolated, bool):
            raise TypeError("interpolated must be a bool")

    @property
    def ends_at(self) -> datetime:
        from datetime import timedelta

        return self.timestamp + timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class PriceObservation:
    symbol: Symbol
    price: Decimal
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        require_finite_decimal(self.price, "price")
        if self.price <= Decimal("0"):
            raise ValueError("price must be positive")
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """Fakeable, already-acquired market facts for one cycle."""

    as_of: datetime
    completed_bars: tuple[CompletedBar, ...]
    in_progress_bars: tuple[CompletedBar, ...]
    execution_prices: Mapping[Symbol, PriceObservation]

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", normalize_utc(self.as_of, "as_of"))
        for name in ("completed_bars", "in_progress_bars"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or not all(
                isinstance(item, CompletedBar) for item in values
            ):
                raise TypeError(f"{name} must be a tuple of CompletedBar values")
        copied_prices: dict[Symbol, PriceObservation] = {}
        for symbol, observation in self.execution_prices.items():
            if not isinstance(symbol, Symbol) or not isinstance(
                observation, PriceObservation
            ):
                raise TypeError("execution_prices must map symbols to observations")
            if observation.symbol != symbol:
                raise ValueError("execution price key does not match its symbol")
            copied_prices[symbol] = observation
        object.__setattr__(self, "execution_prices", MappingProxyType(copied_prices))


class MarketRegime(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class MarketQuality(StrEnum):
    READY = "READY"
    NO_CURRENT_SESSION_DATA = "NO_CURRENT_SESSION_DATA"
    INSUFFICIENT_WARMUP = "INSUFFICIENT_WARMUP"
    STALE = "STALE"
    GAP = "GAP"
    INTERPOLATED = "INTERPOLATED"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class SignalPoint:
    bar_end: datetime
    close: Decimal
    session_vwap: Decimal
    ema20: Decimal
    ema50: Decimal
    rsi14: Decimal
    candidate: MarketRegime

    def __post_init__(self) -> None:
        object.__setattr__(self, "bar_end", normalize_utc(self.bar_end, "bar_end"))
        for name in ("close", "session_vwap", "ema20", "ema50", "rsi14"):
            require_finite_decimal(getattr(self, name), name)
        if not isinstance(self.candidate, MarketRegime):
            raise TypeError("candidate must be a MarketRegime")


@dataclass(frozen=True, slots=True)
class SignalAnalysis:
    quality: MarketQuality
    current_candidate: MarketRegime | None
    entry_confirmation: MarketRegime | None
    latest: SignalPoint | None
    previous: SignalPoint | None
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.quality, MarketQuality):
            raise TypeError("quality must be a MarketQuality")
        for name in ("current_candidate", "entry_confirmation"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, MarketRegime):
                raise TypeError(f"{name} must be a MarketRegime or None")
        for name in ("latest", "previous"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, SignalPoint):
                raise TypeError(f"{name} must be a SignalPoint or None")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("reason must be nonblank")


class TargetPosition(StrEnum):
    FLAT = "FLAT"
    TQQQ = "TQQQ"
    SQQQ = "SQQQ"

    @property
    def symbol(self) -> Symbol | None:
        if self is TargetPosition.TQQQ:
            return TQQQ
        if self is TargetPosition.SQQQ:
            return SQQQ
        return None


class IntentKind(StrEnum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    PROTECTIVE_STOP = "PROTECTIVE_STOP"


class IntentLifecycle(StrEnum):
    PROPOSED = "PROPOSED"
    SUPERSEDED = "SUPERSEDED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    MAY_HAVE_OCCURRED = "MAY_HAVE_OCCURRED"
    UNKNOWN = "UNKNOWN"
    RECONCILED = "RECONCILED"
    REJECTED = "REJECTED"


class OrderState(StrEnum):
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    PENDING_CANCEL = "PENDING_CANCEL"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"

    @property
    def terminal(self) -> bool:
        return self in (OrderState.FILLED, OrderState.CANCELED, OrderState.REJECTED)


class ReviewStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class ApprovalRequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ScopeFacts:
    account_fingerprint: str
    all_agents: bool
    exhausted: bool
    page_count: int
    observed_at: datetime
    symbols: tuple[Symbol, ...] | None = None

    def __post_init__(self) -> None:
        if _SAFE_FINGERPRINT.fullmatch(self.account_fingerprint) is None:
            raise ValueError("account_fingerprint must be a safe stable digest")
        for name in ("all_agents", "exhausted"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        if not isinstance(self.page_count, int) or isinstance(self.page_count, bool):
            raise TypeError("page_count must be an integer")
        if self.page_count < 1:
            raise ValueError("page_count must be positive")
        if self.symbols is not None:
            if not isinstance(self.symbols, tuple) or self.symbols != (TQQQ, SQQQ):
                raise ValueError("bounded scope must be exactly TQQQ then SQQQ")
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )


@dataclass(frozen=True, slots=True)
class AccountFacts:
    fingerprint: str
    active: bool
    agentic_allowed: bool
    cash: Decimal
    buying_power: Decimal
    unleveraged_buying_power: Decimal
    equity: Decimal
    total_market_exposure: Decimal
    observed_at: datetime

    def __post_init__(self) -> None:
        if _SAFE_FINGERPRINT.fullmatch(self.fingerprint) is None:
            raise ValueError("fingerprint must be a safe stable digest")
        for name in ("active", "agentic_allowed"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        for name in (
            "cash",
            "buying_power",
            "unleveraged_buying_power",
            "equity",
            "total_market_exposure",
        ):
            require_finite_decimal(getattr(self, name), name)
            if getattr(self, name) < Decimal("0"):
                raise ValueError(f"{name} must be nonnegative")
        if self.equity <= Decimal("0"):
            raise ValueError("equity must be positive")
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )


@dataclass(frozen=True, slots=True)
class TradabilityFacts:
    symbol: Symbol
    observed_at: datetime
    active: bool | None
    halted: bool | None
    regular_session_eligible: bool | None
    fractional_entry_supported: bool | None
    stop_market_supported: bool | None
    fractional_stop_supported: bool | None
    exact_stop_price_supported: bool | None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )
        for name in (
            "active",
            "halted",
            "regular_session_eligible",
            "fractional_entry_supported",
            "stop_market_supported",
            "fractional_stop_supported",
            "exact_stop_price_supported",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{name} must be bool or None")


@dataclass(frozen=True, slots=True)
class ProviderApprovalFact:
    approval_id: str
    account_fingerprint: str
    source_identity: SourceIdentity | None
    session_fingerprint: str
    state_revision: int
    intent_id: UUID | None
    ref_id: str | None
    symbol: Symbol
    side: OrderSide
    quantity: Decimal
    status: ApprovalRequestStatus
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.approval_id, str) or not self.approval_id:
            raise ValueError("approval_id must be nonblank")
        if _SAFE_FINGERPRINT.fullmatch(self.account_fingerprint) is None:
            raise ValueError("account_fingerprint must be a safe stable digest")
        if self.source_identity is not None and not isinstance(
            self.source_identity, SourceIdentity
        ):
            raise TypeError("source_identity must be SourceIdentity or None")
        if _SAFE_FINGERPRINT.fullmatch(self.session_fingerprint) is None:
            raise ValueError("session_fingerprint must be a safe stable digest")
        if (
            not isinstance(self.state_revision, int)
            or isinstance(self.state_revision, bool)
            or self.state_revision < 0
        ):
            raise ValueError("state_revision must be nonnegative")
        if self.intent_id is not None and not isinstance(self.intent_id, UUID):
            raise TypeError("intent_id must be UUID or None")
        if self.ref_id is not None and (
            not isinstance(self.ref_id, str) or not self.ref_id
        ):
            raise ValueError("ref_id must be nonblank when supplied")
        if not isinstance(self.symbol, Symbol) or not isinstance(self.side, OrderSide):
            raise TypeError("symbol/side has an invalid type")
        require_finite_decimal(self.quantity, "quantity")
        if self.quantity <= Decimal("0"):
            raise ValueError("quantity must be positive")
        if not isinstance(self.status, ApprovalRequestStatus):
            raise TypeError("status must be ApprovalRequestStatus")
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )


@dataclass(frozen=True, slots=True)
class ApprovalFacts:
    account_fingerprint: str
    source_identity: SourceIdentity
    session_fingerprint: str
    state_revision: int
    setting_enabled: bool | None
    unresolved_refs: tuple[str, ...]
    exhaustive: bool
    observed_at: datetime
    requests: tuple[ProviderApprovalFact, ...] = ()

    def __post_init__(self) -> None:
        if _SAFE_FINGERPRINT.fullmatch(self.account_fingerprint) is None:
            raise ValueError("account_fingerprint must be a safe stable digest")
        if not isinstance(self.source_identity, SourceIdentity):
            raise TypeError("source_identity must be SourceIdentity")
        if _SAFE_FINGERPRINT.fullmatch(self.session_fingerprint) is None:
            raise ValueError("session_fingerprint must be a safe stable digest")
        if (
            not isinstance(self.state_revision, int)
            or isinstance(self.state_revision, bool)
            or self.state_revision < 0
        ):
            raise ValueError("state_revision must be nonnegative")
        if self.setting_enabled is not None and not isinstance(
            self.setting_enabled, bool
        ):
            raise TypeError("setting_enabled must be bool or None")
        if not isinstance(self.unresolved_refs, tuple) or not all(
            isinstance(value, str) and value for value in self.unresolved_refs
        ):
            raise TypeError("unresolved_refs must be a tuple of nonblank strings")
        if not isinstance(self.exhaustive, bool):
            raise TypeError("exhaustive must be a bool")
        if not isinstance(self.requests, tuple) or not all(
            isinstance(value, ProviderApprovalFact) for value in self.requests
        ):
            raise TypeError("requests must be a tuple of ProviderApprovalFact values")
        if len({value.approval_id for value in self.requests}) != len(self.requests):
            raise ValueError("approval IDs must be unique")
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )


@dataclass(frozen=True, slots=True)
class BrokerOrderFact:
    provider_order_id: str
    account_fingerprint: str
    source_identity: SourceIdentity | None
    intent_id: UUID | None
    ref_id: str | None
    kind: IntentKind
    symbol: Symbol
    side: OrderSide
    state: OrderState
    requested_quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    stop_price: Decimal | None
    observed_at: datetime
    average_fill_price: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provider_order_id, str) or not self.provider_order_id:
            raise ValueError("provider_order_id must be nonblank")
        if _SAFE_FINGERPRINT.fullmatch(self.account_fingerprint) is None:
            raise ValueError("account_fingerprint must be a safe stable digest")
        if self.source_identity is not None and not isinstance(
            self.source_identity, SourceIdentity
        ):
            raise TypeError("source_identity must be SourceIdentity or None")
        if self.intent_id is not None and not isinstance(self.intent_id, UUID):
            raise TypeError("intent_id must be UUID or None")
        if self.ref_id is not None and (
            not isinstance(self.ref_id, str) or not self.ref_id
        ):
            raise ValueError("ref_id must be nonblank when supplied")
        if not isinstance(self.kind, IntentKind):
            raise TypeError("kind must be an IntentKind")
        if not isinstance(self.symbol, Symbol) or not isinstance(self.side, OrderSide):
            raise TypeError("order symbol/side has an invalid type")
        if not isinstance(self.state, OrderState):
            raise TypeError("state must be an OrderState")
        for name in ("requested_quantity", "filled_quantity", "remaining_quantity"):
            require_finite_decimal(getattr(self, name), name)
            if getattr(self, name) < Decimal("0"):
                raise ValueError(f"{name} must be nonnegative")
        if self.requested_quantity == Decimal("0"):
            raise ValueError("requested_quantity must be positive")
        if (
            self.filled_quantity > self.requested_quantity
            or self.remaining_quantity > self.requested_quantity
            or not decimal_sum_less_or_equal(
                self.filled_quantity,
                self.remaining_quantity,
                self.requested_quantity,
            )
        ):
            raise ValueError("filled plus remaining quantity exceeds request")
        if self.stop_price is not None:
            require_finite_decimal(self.stop_price, "stop_price")
            if self.stop_price <= Decimal("0"):
                raise ValueError("stop_price must be positive")
        if self.average_fill_price is not None:
            require_finite_decimal(self.average_fill_price, "average_fill_price")
            if self.average_fill_price <= Decimal("0"):
                raise ValueError("average_fill_price must be positive")
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )


@dataclass(frozen=True, slots=True)
class BrokerReviewFacts:
    account_fingerprint: str
    source_identity: SourceIdentity
    session_fingerprint: str
    state_revision: int
    ref_id: str
    terms_digest: str
    status: ReviewStatus
    warnings: tuple[str, ...]
    approval_required: bool
    observed_at: datetime

    def __post_init__(self) -> None:
        if _SAFE_FINGERPRINT.fullmatch(self.account_fingerprint) is None:
            raise ValueError("account_fingerprint must be a safe stable digest")
        if not isinstance(self.source_identity, SourceIdentity):
            raise TypeError("source_identity must be SourceIdentity")
        if _SAFE_FINGERPRINT.fullmatch(self.session_fingerprint) is None:
            raise ValueError("session_fingerprint must be a safe stable digest")
        if (
            not isinstance(self.state_revision, int)
            or isinstance(self.state_revision, bool)
            or self.state_revision < 0
        ):
            raise ValueError("state_revision must be nonnegative")
        for name in ("ref_id", "terms_digest"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} must be nonblank")
        if not isinstance(self.status, ReviewStatus):
            raise TypeError("status must be a ReviewStatus")
        if not isinstance(self.warnings, tuple) or not all(
            isinstance(value, str) and value.strip() for value in self.warnings
        ):
            raise TypeError("warnings must be a tuple of nonblank strings")
        if not isinstance(self.approval_required, bool):
            raise TypeError("approval_required must be a bool")
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )


@dataclass(frozen=True, slots=True)
class BrokerSnapshot:
    observed_at: datetime
    source_identity: SourceIdentity
    session_fingerprint: str
    state_revision: int
    account: AccountFacts
    positions: Mapping[Symbol, Position]
    position_owners: Mapping[Symbol, UUID | None]
    orders: tuple[BrokerOrderFact, ...]
    position_scope: ScopeFacts
    order_scope: ScopeFacts
    tradability: Mapping[Symbol, TradabilityFacts]
    approvals: ApprovalFacts
    review: BrokerReviewFacts | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )
        if not isinstance(self.account, AccountFacts):
            raise TypeError("account must be AccountFacts")
        if not isinstance(self.source_identity, SourceIdentity):
            raise TypeError("source_identity must be SourceIdentity")
        if _SAFE_FINGERPRINT.fullmatch(self.session_fingerprint) is None:
            raise ValueError("session_fingerprint must be a safe stable digest")
        if (
            not isinstance(self.state_revision, int)
            or isinstance(self.state_revision, bool)
            or self.state_revision < 0
        ):
            raise ValueError("state_revision must be nonnegative")
        for name in ("position_scope", "order_scope"):
            if not isinstance(getattr(self, name), ScopeFacts):
                raise TypeError(f"{name} must be ScopeFacts")
        if not isinstance(self.approvals, ApprovalFacts):
            raise TypeError("approvals must be ApprovalFacts")
        if self.review is not None and not isinstance(self.review, BrokerReviewFacts):
            raise TypeError("review must be BrokerReviewFacts or None")
        if not isinstance(self.orders, tuple) or not all(
            isinstance(order, BrokerOrderFact) for order in self.orders
        ):
            raise TypeError("orders must be a tuple of BrokerOrderFact values")
        for name in ("positions", "position_owners"):
            value = getattr(self, name)
            if not isinstance(value, Mapping):
                raise TypeError(f"{name} must be a mapping")
        copied_positions: dict[Symbol, Position] = {}
        for symbol, position in self.positions.items():
            if not isinstance(symbol, Symbol) or not isinstance(position, Position):
                raise TypeError("positions must map Symbol to Position")
            if position.symbol != symbol:
                raise ValueError("position key does not match its symbol")
            copied_positions[symbol] = position
        copied_owners: dict[Symbol, UUID | None] = {}
        for symbol, owner in self.position_owners.items():
            if not isinstance(symbol, Symbol):
                raise TypeError("position_owners keys must be Symbol values")
            if owner is not None and not isinstance(owner, UUID):
                raise TypeError("position owner must be UUID or None")
            copied_owners[symbol] = owner
        copied_tradability: dict[Symbol, TradabilityFacts] = {}
        for symbol, facts in self.tradability.items():
            if not isinstance(symbol, Symbol) or not isinstance(
                facts, TradabilityFacts
            ):
                raise TypeError("tradability must map Symbol to TradabilityFacts")
            if facts.symbol != symbol:
                raise ValueError("tradability key does not match its symbol")
            copied_tradability[symbol] = facts
        object.__setattr__(self, "positions", MappingProxyType(copied_positions))
        object.__setattr__(self, "position_owners", MappingProxyType(copied_owners))
        object.__setattr__(self, "tradability", MappingProxyType(copied_tradability))


@dataclass(frozen=True, slots=True)
class LogicalOrderIntent:
    intent_id: UUID
    ref_id: str
    logical_sequence: int
    kind: IntentKind
    symbol: Symbol
    side: OrderSide
    quantity: Decimal
    stop_price: Decimal | None
    source_identity: SourceIdentity
    owner_id: UUID
    lifecycle: IntentLifecycle
    terms_digest: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, UUID) or not isinstance(self.owner_id, UUID):
            raise TypeError("intent and owner identities must be UUID values")
        if not isinstance(self.ref_id, str) or not self.ref_id:
            raise ValueError("ref_id must be nonblank")
        if (
            not isinstance(self.logical_sequence, int)
            or isinstance(self.logical_sequence, bool)
            or self.logical_sequence < 1
        ):
            raise ValueError("logical_sequence must be a positive integer")
        if not isinstance(self.kind, IntentKind) or not isinstance(
            self.side, OrderSide
        ):
            raise TypeError("intent kind/side has an invalid type")
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if self.kind is IntentKind.ENTRY and (
            self.side is not OrderSide.BUY or self.symbol not in TRADED_SYMBOLS
        ):
            raise ValueError("ENTRY must buy TQQQ or SQQQ")
        if self.kind is IntentKind.EXIT and (
            self.side is not OrderSide.SELL
            or self.symbol not in TRADED_SYMBOLS
            or self.stop_price is not None
        ):
            raise ValueError("EXIT must sell TQQQ or SQQQ without a stop price")
        if self.kind is IntentKind.PROTECTIVE_STOP and (
            self.side is not OrderSide.SELL
            or self.symbol not in TRADED_SYMBOLS
            or self.stop_price is None
        ):
            raise ValueError("PROTECTIVE_STOP must sell TQQQ or SQQQ at a stop price")
        require_finite_decimal(self.quantity, "quantity")
        if self.quantity <= Decimal("0"):
            raise ValueError("quantity must be positive")
        if self.stop_price is not None:
            require_finite_decimal(self.stop_price, "stop_price")
            if self.stop_price <= Decimal("0"):
                raise ValueError("stop_price must be positive")
        if not isinstance(self.source_identity, SourceIdentity):
            raise TypeError("source_identity must be SourceIdentity")
        if not isinstance(self.lifecycle, IntentLifecycle):
            raise TypeError("lifecycle must be an IntentLifecycle")
        if not isinstance(self.terms_digest, str) or not self.terms_digest:
            raise ValueError("terms_digest must be nonblank")
        object.__setattr__(
            self, "created_at", normalize_utc(self.created_at, "created_at")
        )


@dataclass(frozen=True, slots=True)
class ApprovalRequiredReceipt:
    approval_id: str
    intent_id: UUID
    ref_id: str
    terms_digest: str
    account_fingerprint: str
    source_identity: SourceIdentity
    session_fingerprint: str
    state_revision: int
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.approval_id, str) or not self.approval_id:
            raise ValueError("approval_id must be nonblank")
        if not isinstance(self.intent_id, UUID):
            raise TypeError("intent_id must be UUID")
        for name in ("ref_id", "terms_digest"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} must be nonblank")
        if _SAFE_FINGERPRINT.fullmatch(self.account_fingerprint) is None:
            raise ValueError("account_fingerprint must be a safe stable digest")
        if not isinstance(self.source_identity, SourceIdentity):
            raise TypeError("source_identity must be SourceIdentity")
        if _SAFE_FINGERPRINT.fullmatch(self.session_fingerprint) is None:
            raise ValueError("session_fingerprint must be a safe stable digest")
        if (
            not isinstance(self.state_revision, int)
            or isinstance(self.state_revision, bool)
            or self.state_revision < 0
        ):
            raise ValueError("state_revision must be nonnegative")
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )


@dataclass(frozen=True, slots=True)
class OwnedPositionRecord:
    symbol: Symbol
    entry_intent_id: UUID
    quantity: Decimal
    average_entry_fill: Decimal
    hard_stop_price: Decimal
    stop_intent_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.symbol not in TRADED_SYMBOLS:
            raise ValueError("owned position symbol must be TQQQ or SQQQ")
        if not isinstance(self.entry_intent_id, UUID):
            raise TypeError("entry_intent_id must be UUID")
        if self.stop_intent_id is not None and not isinstance(
            self.stop_intent_id, UUID
        ):
            raise TypeError("stop_intent_id must be UUID or None")
        for name in ("quantity", "average_entry_fill", "hard_stop_price"):
            require_finite_decimal(getattr(self, name), name)
            if getattr(self, name) <= Decimal("0"):
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class RuntimeState:
    owner_id: UUID
    source_identity: SourceIdentity
    session_fingerprint: str
    account_fingerprint: str
    revision: int
    next_sequence: int
    intents: tuple[LogicalOrderIntent, ...]
    positions: Mapping[Symbol, OwnedPositionRecord]
    approval_receipts: tuple[ApprovalRequiredReceipt, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.owner_id, UUID):
            raise TypeError("owner_id must be UUID")
        if not isinstance(self.source_identity, SourceIdentity):
            raise TypeError("source_identity must be SourceIdentity")
        if _SAFE_FINGERPRINT.fullmatch(self.session_fingerprint) is None:
            raise ValueError("session_fingerprint must be a safe stable digest")
        if _SAFE_FINGERPRINT.fullmatch(self.account_fingerprint) is None:
            raise ValueError("account_fingerprint must be a safe stable digest")
        for name, minimum in (("revision", 0), ("next_sequence", 1)):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
        if not isinstance(self.intents, tuple) or not all(
            isinstance(item, LogicalOrderIntent) for item in self.intents
        ):
            raise TypeError("intents must be a tuple of LogicalOrderIntent values")
        if not isinstance(self.approval_receipts, tuple) or not all(
            isinstance(item, ApprovalRequiredReceipt) for item in self.approval_receipts
        ):
            raise TypeError("approval_receipts must be a tuple of receipts")
        if not isinstance(self.positions, Mapping):
            raise TypeError("positions must be a mapping")
        intent_ids = [intent.intent_id for intent in self.intents]
        ref_ids = [intent.ref_id for intent in self.intents]
        sequences = [intent.logical_sequence for intent in self.intents]
        if len(intent_ids) != len(set(intent_ids)):
            raise ValueError("runtime state contains duplicate intent IDs")
        if len(ref_ids) != len(set(ref_ids)):
            raise ValueError("runtime state contains duplicate ref_ids")
        if len(sequences) != len(set(sequences)):
            raise ValueError("runtime state contains duplicate logical sequences")
        pending_intents = tuple(
            intent
            for intent in self.intents
            if intent.lifecycle
            in (
                IntentLifecycle.PROPOSED,
                IntentLifecycle.APPROVAL_REQUIRED,
                IntentLifecycle.MAY_HAVE_OCCURRED,
                IntentLifecycle.UNKNOWN,
            )
        )
        if len(pending_intents) > 1:
            raise ValueError("runtime state contains multiple unresolved intents")
        receipt_ids = [receipt.approval_id for receipt in self.approval_receipts]
        receipt_intents = [receipt.intent_id for receipt in self.approval_receipts]
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("runtime state contains duplicate approval IDs")
        if len(receipt_intents) != len(set(receipt_intents)):
            raise ValueError("runtime state contains duplicate approval receipts")
        if any(sequence >= self.next_sequence for sequence in sequences):
            raise ValueError("next_sequence must exceed every persisted sequence")
        for intent in self.intents:
            if (
                intent.owner_id != self.owner_id
                or intent.source_identity != self.source_identity
            ):
                raise ValueError("intent owner/source differs from runtime state")
        intent_by_id = {intent.intent_id: intent for intent in self.intents}
        receipt_intent_ids = {receipt.intent_id for receipt in self.approval_receipts}
        if any(
            intent.lifecycle is IntentLifecycle.APPROVAL_REQUIRED
            and intent.intent_id not in receipt_intent_ids
            for intent in self.intents
        ):
            raise ValueError("approval-required intent has no authenticated receipt")
        for receipt in self.approval_receipts:
            intent = intent_by_id.get(receipt.intent_id)
            if (
                intent is None
                or intent.lifecycle is not IntentLifecycle.APPROVAL_REQUIRED
                or receipt.ref_id != intent.ref_id
                or receipt.terms_digest != intent.terms_digest
                or receipt.source_identity != self.source_identity
                or receipt.account_fingerprint != self.account_fingerprint
                or receipt.session_fingerprint != self.session_fingerprint
                or receipt.state_revision > self.revision
            ):
                raise ValueError(
                    "approval receipt has no exact persisted intent binding"
                )
        copied_positions: dict[Symbol, OwnedPositionRecord] = {}
        for symbol, record in self.positions.items():
            if not isinstance(symbol, Symbol) or not isinstance(
                record, OwnedPositionRecord
            ):
                raise TypeError("positions must map Symbol to OwnedPositionRecord")
            if record.symbol != symbol:
                raise ValueError("owned position key does not match its symbol")
            copied_positions[symbol] = record
        object.__setattr__(self, "positions", MappingProxyType(copied_positions))


class RuntimeStateStore(Protocol):
    """Injected create-once state owner; production provisioning is deferred."""

    def load(
        self, owner_id: UUID, source_identity: SourceIdentity
    ) -> RuntimeState | None:
        """Return the exact owner's state or None when no state is provisioned."""

    def compare_and_swap(
        self, expected_revision: int, next_state: RuntimeState
    ) -> bool:
        """Persist once if the durable state still has the expected revision."""


class AdmissionBlocker(StrEnum):
    STATE_UNAVAILABLE = "STATE_UNAVAILABLE"
    STATE_IDENTITY_MISMATCH = "STATE_IDENTITY_MISMATCH"
    ACCOUNT_IDENTITY_MISMATCH = "ACCOUNT_IDENTITY_MISMATCH"
    STATE_CONFLICT = "STATE_CONFLICT"
    STATE_ADVANCED_THIS_CYCLE = "STATE_ADVANCED_THIS_CYCLE"
    SOURCE_IDENTITY_MISMATCH = "SOURCE_IDENTITY_MISMATCH"
    SESSION_IDENTITY_MISMATCH = "SESSION_IDENTITY_MISMATCH"
    SAME_CYCLE_FLIP_BLOCKED = "SAME_CYCLE_FLIP_BLOCKED"
    AFTER_SESSION_NO_QUEUE = "AFTER_SESSION_NO_QUEUE"
    MARKET_DATA_STALE = "MARKET_DATA_STALE"
    MARKET_DATA_GAP = "MARKET_DATA_GAP"
    MARKET_DATA_INTERPOLATED = "MARKET_DATA_INTERPOLATED"
    MARKET_DATA_INVALID = "MARKET_DATA_INVALID"
    INSUFFICIENT_WARMUP = "INSUFFICIENT_WARMUP"
    SESSION_UNAVAILABLE = "SESSION_UNAVAILABLE"
    ENTRY_WINDOW_CLOSED = "ENTRY_WINDOW_CLOSED"
    BROKER_SNAPSHOT_STALE = "BROKER_SNAPSHOT_STALE"
    ACCOUNT_INELIGIBLE = "ACCOUNT_INELIGIBLE"
    BROKER_SCOPE_INCOMPLETE = "BROKER_SCOPE_INCOMPLETE"
    BUYING_POWER_UNSAFE = "BUYING_POWER_UNSAFE"
    POSITION_CONFLICT = "POSITION_CONFLICT"
    FOREIGN_POSITION = "FOREIGN_POSITION"
    UNRESOLVED_ORDER = "UNRESOLVED_ORDER"
    TRADABILITY_UNKNOWN = "TRADABILITY_UNKNOWN"
    NOT_TRADABLE = "NOT_TRADABLE"
    PRICE_STALE = "PRICE_STALE"
    APPROVAL_STATE_UNKNOWN = "APPROVAL_STATE_UNKNOWN"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    BROKER_REVIEW_MISSING = "BROKER_REVIEW_MISSING"
    BROKER_REVIEW_STALE = "BROKER_REVIEW_STALE"
    BROKER_REVIEW_MISMATCH = "BROKER_REVIEW_MISMATCH"
    BROKER_REVIEW_REJECTED = "BROKER_REVIEW_REJECTED"
    BROKER_REVIEW_WARNING = "BROKER_REVIEW_WARNING"
    RISK_REJECTED = "RISK_REJECTED"
    STOP_UNPROTECTED = "STOP_UNPROTECTED"
    STOP_CONFLICT = "STOP_CONFLICT"
    STOP_INCOMPATIBLE = "STOP_INCOMPATIBLE"
    UNKNOWN_INTENT = "UNKNOWN_INTENT"
    FORCED_FLAT = "FORCED_FLAT"
    STOP_BREACH = "STOP_BREACH"
    SAFETY_FAILURE = "SAFETY_FAILURE"
    REGIME_EXIT = "REGIME_EXIT"
    PERSISTENCE_UNAVAILABLE = "PERSISTENCE_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class EffectProposal:
    intent: LogicalOrderIntent
    status: str
    execution_attempted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.intent, LogicalOrderIntent):
            raise TypeError("intent must be LogicalOrderIntent")
        if not isinstance(self.status, str) or not self.status:
            raise ValueError("status must be nonblank")
        if self.execution_attempted is not False:
            raise ValueError("148-A never attempts an effect")


@dataclass(frozen=True, slots=True)
class CycleStatus:
    as_of: datetime
    current_candidate: MarketRegime | None
    entry_confirmation: MarketRegime | None
    desired_position: TargetPosition
    actual_position: TargetPosition | None
    action: IntentKind | None
    blockers: tuple[AdmissionBlocker, ...]
    mandatory_exit_reasons: tuple[AdmissionBlocker, ...]
    protective_stop_ready: bool
    live_ready: bool
    state: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", normalize_utc(self.as_of, "as_of"))
        if not isinstance(self.desired_position, TargetPosition):
            raise TypeError("desired_position must be a TargetPosition")
        if self.actual_position is not None and not isinstance(
            self.actual_position, TargetPosition
        ):
            raise TypeError("actual_position must be a TargetPosition or None")
        if self.action is not None and not isinstance(self.action, IntentKind):
            raise TypeError("action must be IntentKind or None")
        for name in ("blockers", "mandatory_exit_reasons"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or not all(
                isinstance(item, AdmissionBlocker) for item in values
            ):
                raise TypeError(f"{name} must be a tuple of AdmissionBlocker values")
        for name in ("protective_stop_ready", "live_ready"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        if not isinstance(self.state, str) or not self.state:
            raise ValueError("state must be nonblank")


@dataclass(frozen=True, slots=True)
class CycleResult:
    signal: SignalAnalysis
    status: CycleStatus
    intent: LogicalOrderIntent | None
    effect_proposal: EffectProposal | None


class BrokerSnapshotProvider(Protocol):
    """Deferred adapter contract; 148-A accepts facts and never calls it."""

    def read_snapshot(self, as_of: datetime) -> BrokerSnapshot:
        """Return fresh account, position, order, approval, and tradability facts."""


class MarketSnapshotProvider(Protocol):
    """Deferred adapter contract; 148-A accepts facts and never calls it."""

    def read_snapshot(self, as_of: datetime) -> MarketSnapshot:
        """Return completed bars and fresh execution-price observations."""
