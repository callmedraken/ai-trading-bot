"""Immutable records for Robinhood review-based paper trading."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid5

from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce
from trading_bot.domain._validation import (
    normalize_utc,
    require_decimal,
    require_positive_decimal,
)
from trading_bot.risk import RiskOutcome

_TRADE_NAMESPACE = UUID("e68a2c7e-59fd-5679-935c-ab78814b5b45")
_FILL_NAMESPACE = UUID("cde151e5-5a25-5aab-8ec6-9d39e58ba13e")
_BPS_DENOMINATOR = Decimal("10000")
_MAX_SLIPPAGE_BPS = Decimal("9999")


def _nonnegative_decimal(value: Decimal, name: str) -> Decimal:
    normalized = require_decimal(value, name)
    if normalized < Decimal("0"):
        raise ValueError(f"{name} must be zero or greater")
    return normalized


def canonical_order_checks(value: Mapping[str, object]) -> str:
    """Return stable JSON for Robinhood's open-ended order_checks object."""

    if not isinstance(value, Mapping):
        raise TypeError("order_checks must be a mapping")
    try:
        encoded = json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValueError("order_checks must contain JSON-compatible values") from error
    decoded = json.loads(encoded)
    if not isinstance(decoded, dict):
        raise ValueError("order_checks must encode a JSON object")
    return encoded


@dataclass(frozen=True, slots=True)
class ReviewPaperIntent:
    """One deterministic risk-approved order selected for paper review."""

    proposal_id: UUID
    order_id: UUID
    symbol: Symbol
    side: OrderSide
    desired_quantity: Decimal
    approved_quantity: Decimal
    risk_outcome: RiskOutcome
    risk_reason_codes: tuple[str, ...]
    proposal_reason: str
    proposal_confidence: Decimal | None
    order_type: OrderType
    time_in_force: TimeInForce
    proposed_at: datetime
    limit_price: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, UUID) or not isinstance(
            self.order_id, UUID
        ):
            raise TypeError("proposal_id and order_id must be UUIDs")
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be an OrderSide")
        desired = require_positive_decimal(self.desired_quantity, "desired_quantity")
        approved = require_positive_decimal(self.approved_quantity, "approved_quantity")
        if not isinstance(self.risk_outcome, RiskOutcome):
            raise TypeError("risk_outcome must be a RiskOutcome")
        if self.risk_outcome is RiskOutcome.REJECTED:
            raise ValueError("rejected risk decisions cannot create paper intent")
        if self.risk_outcome is RiskOutcome.APPROVED and approved != desired:
            raise ValueError("APPROVED intent must retain desired quantity")
        if self.risk_outcome is RiskOutcome.RESIZED and not approved < desired:
            raise ValueError(
                "RESIZED intent requires approved_quantity < desired_quantity"
            )
        if not isinstance(self.risk_reason_codes, tuple) or not all(
            isinstance(item, str) and item.strip() and item == item.strip()
            for item in self.risk_reason_codes
        ):
            raise TypeError("risk_reason_codes must be exact nonblank strings")
        if len(set(self.risk_reason_codes)) != len(self.risk_reason_codes):
            raise ValueError("risk_reason_codes must be unique")
        if (
            not isinstance(self.proposal_reason, str)
            or not self.proposal_reason.strip()
        ):
            raise ValueError("proposal_reason must be nonblank")
        if self.proposal_confidence is not None:
            require_decimal(self.proposal_confidence, "proposal_confidence")
            if not Decimal("0") <= self.proposal_confidence <= Decimal("1"):
                raise ValueError("proposal_confidence must be between 0 and 1")
        if not isinstance(self.order_type, OrderType):
            raise TypeError("order_type must be an OrderType")
        if not isinstance(self.time_in_force, TimeInForce):
            raise TypeError("time_in_force must be a TimeInForce")
        object.__setattr__(
            self, "proposed_at", normalize_utc(self.proposed_at, "proposed_at")
        )
        if self.order_type is OrderType.LIMIT:
            if self.limit_price is None:
                raise ValueError("limit intent requires limit_price")
            require_positive_decimal(self.limit_price, "limit_price")
        elif self.limit_price is not None:
            raise ValueError("market intent must not contain limit_price")


@dataclass(frozen=True, slots=True)
class RobinhoodReviewQuote:
    """Validated subset of review_equity_order quote_data."""

    symbol: Symbol
    adjusted_previous_close: Decimal
    ask_price: Decimal
    bid_price: Decimal
    has_traded: bool
    last_non_reg_trade_price: Decimal | None
    last_trade_price: Decimal
    previous_close: Decimal
    previous_close_date: str | None
    state: str
    venue_ask_time: datetime
    venue_bid_time: datetime
    venue_last_non_reg_trade_time: datetime | None
    venue_last_trade_time: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        require_positive_decimal(
            self.adjusted_previous_close, "adjusted_previous_close"
        )
        _nonnegative_decimal(self.ask_price, "ask_price")
        _nonnegative_decimal(self.bid_price, "bid_price")
        if not isinstance(self.has_traded, bool):
            raise TypeError("has_traded must be a bool")
        if self.last_non_reg_trade_price is not None:
            require_positive_decimal(
                self.last_non_reg_trade_price,
                "last_non_reg_trade_price",
            )
        require_positive_decimal(self.last_trade_price, "last_trade_price")
        require_positive_decimal(self.previous_close, "previous_close")
        if self.previous_close_date is not None and (
            not isinstance(self.previous_close_date, str)
            or not self.previous_close_date.strip()
        ):
            raise ValueError("previous_close_date must be nonblank when supplied")
        if not isinstance(self.state, str) or not self.state.strip():
            raise ValueError("state must be nonblank")
        for name in (
            "venue_ask_time",
            "venue_bid_time",
            "venue_last_trade_time",
        ):
            object.__setattr__(
                self,
                name,
                normalize_utc(getattr(self, name), name),
            )
        if self.venue_last_non_reg_trade_time is not None:
            object.__setattr__(
                self,
                "venue_last_non_reg_trade_time",
                normalize_utc(
                    self.venue_last_non_reg_trade_time,
                    "venue_last_non_reg_trade_time",
                ),
            )


@dataclass(frozen=True, slots=True)
class RobinhoodEquityOrderReview:
    """One parsed review_equity_order response used for a synthetic fill."""

    symbol: Symbol
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    quote: RobinhoodReviewQuote
    order_checks_json: str
    reviewed_at: datetime
    market_data_disclosure: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be an OrderSide")
        if not isinstance(self.order_type, OrderType):
            raise TypeError("order_type must be an OrderType")
        require_positive_decimal(self.quantity, "quantity")
        if not isinstance(self.quote, RobinhoodReviewQuote):
            raise TypeError("quote must be RobinhoodReviewQuote")
        if self.quote.symbol != self.symbol:
            raise ValueError("review quote symbol must match review symbol")
        if not isinstance(self.order_checks_json, str):
            raise TypeError("order_checks_json must be a string")
        try:
            decoded = json.loads(self.order_checks_json)
        except json.JSONDecodeError as error:
            raise ValueError("order_checks_json must be valid JSON") from error
        if not isinstance(decoded, dict):
            raise ValueError("order_checks_json must encode an object")
        expected = canonical_order_checks(decoded)
        if self.order_checks_json != expected:
            raise ValueError("order_checks_json must use canonical JSON")
        object.__setattr__(
            self, "reviewed_at", normalize_utc(self.reviewed_at, "reviewed_at")
        )
        if self.market_data_disclosure is not None and not isinstance(
            self.market_data_disclosure, str
        ):
            raise TypeError("market_data_disclosure must be a string or None")


@dataclass(frozen=True, slots=True)
class ReviewPaperRecord:
    """Durable synthetic fill derived from one exact Robinhood review."""

    paper_trade_id: UUID
    intent: ReviewPaperIntent
    review: RobinhoodEquityOrderReview
    fill_id: UUID
    fill_price: Decimal
    commission: Decimal
    slippage_basis_points: Decimal
    filled_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.paper_trade_id, UUID) or not isinstance(
            self.fill_id, UUID
        ):
            raise TypeError("paper_trade_id and fill_id must be UUIDs")
        if not isinstance(self.intent, ReviewPaperIntent):
            raise TypeError("intent must be ReviewPaperIntent")
        if not isinstance(self.review, RobinhoodEquityOrderReview):
            raise TypeError("review must be RobinhoodEquityOrderReview")
        require_positive_decimal(self.fill_price, "fill_price")
        commission = require_decimal(self.commission, "commission")
        if commission < Decimal("0"):
            raise ValueError("commission must be zero or greater")
        slippage = require_decimal(self.slippage_basis_points, "slippage_basis_points")
        if not Decimal("0") <= slippage <= _MAX_SLIPPAGE_BPS:
            raise ValueError("slippage_basis_points must be between 0 and 9999")
        expected_price, expected_time = synthetic_review_fill(
            self.intent.side,
            self.review.quote,
            slippage,
        )
        if self.fill_price != expected_price:
            raise ValueError("fill_price does not match review quote/slippage policy")
        object.__setattr__(
            self, "filled_at", normalize_utc(self.filled_at, "filled_at")
        )
        if self.filled_at != expected_time:
            raise ValueError("filled_at does not match side-specific quote timestamp")
        if self.paper_trade_id != review_paper_trade_id(self.intent.order_id):
            raise ValueError("paper_trade_id does not match order_id")
        if self.fill_id != review_paper_fill_id(self.intent.order_id):
            raise ValueError("fill_id does not match order_id")


def review_paper_trade_id(order_id: UUID) -> UUID:
    if not isinstance(order_id, UUID):
        raise TypeError("order_id must be a UUID")
    return uuid5(_TRADE_NAMESPACE, str(order_id))


def review_paper_fill_id(order_id: UUID) -> UUID:
    if not isinstance(order_id, UUID):
        raise TypeError("order_id must be a UUID")
    return uuid5(_FILL_NAMESPACE, str(order_id))


def synthetic_review_fill(
    side: OrderSide,
    quote: RobinhoodReviewQuote,
    slippage_basis_points: Decimal,
) -> tuple[Decimal, datetime]:
    """Return side-aware synthetic fill price and authoritative quote time."""

    if not isinstance(side, OrderSide):
        raise TypeError("side must be an OrderSide")
    if not isinstance(quote, RobinhoodReviewQuote):
        raise TypeError("quote must be RobinhoodReviewQuote")
    slippage = require_decimal(slippage_basis_points, "slippage_basis_points")
    if not Decimal("0") <= slippage <= _MAX_SLIPPAGE_BPS:
        raise ValueError("slippage_basis_points must be between 0 and 9999")
    if not quote.has_traded:
        raise ValueError("review quote must represent an instrument that has traded")
    if quote.state != "active":
        raise ValueError("review quote instrument must be active")
    fraction = slippage / _BPS_DENOMINATOR
    if side is OrderSide.BUY:
        reference = quote.ask_price
        timestamp = quote.venue_ask_time
        multiplier = Decimal("1") + fraction
    else:
        reference = quote.bid_price
        timestamp = quote.venue_bid_time
        multiplier = Decimal("1") - fraction
    if reference <= Decimal("0"):
        raise ValueError("side-specific review quote price must be positive")
    return reference * multiplier, timestamp
