"""Immutable records for Robinhood manual-approval paper trading."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce
from trading_bot.domain._validation import (
    normalize_utc,
    require_decimal,
    require_positive_decimal,
)
from trading_bot.risk import RiskOutcome

_RECORD_NAMESPACE = UUID("42946a0c-c466-5fd4-8c38-4be52668e5f5")
_FILL_NAMESPACE = UUID("47ff38fb-f48f-5cb1-84e0-924a2d5f62d5")
_BPS_DENOMINATOR = Decimal("10000")
_MAX_SLIPPAGE_BPS = Decimal("9999")


class ApprovalDeclineState(StrEnum):
    """Whether the external Robinhood approval is confirmed declined."""

    PENDING_DECLINE = "PENDING_DECLINE"
    DECLINED = "DECLINED"


@dataclass(frozen=True, slots=True)
class ApprovalPaperIntent:
    """One risk-approved local order bound to a Robinhood approval request."""

    approval_id: str
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
        if (
            not isinstance(self.approval_id, str)
            or not self.approval_id
            or self.approval_id != self.approval_id.strip()
            or len(self.approval_id) > 256
        ):
            raise ValueError("approval_id must be nonblank exact text up to 256 chars")
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
            raise ValueError(
                "rejected risk decisions cannot create approval-paper intent"
            )
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
class ApprovalPaperQuote:
    """Post-proposal bid/ask quote used for one synthetic market fill."""

    symbol: Symbol
    bid: Decimal
    ask: Decimal
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        bid = require_positive_decimal(self.bid, "bid")
        ask = require_positive_decimal(self.ask, "ask")
        if bid > ask:
            raise ValueError("bid must not exceed ask")
        object.__setattr__(
            self, "observed_at", normalize_utc(self.observed_at, "observed_at")
        )


@dataclass(frozen=True, slots=True)
class ApprovalPaperRecord:
    """Durable synthetic fill plus external-approval cleanup state."""

    record_id: UUID
    intent: ApprovalPaperIntent
    quote: ApprovalPaperQuote
    fill_id: UUID
    fill_price: Decimal
    commission: Decimal
    slippage_basis_points: Decimal
    filled_at: datetime
    decline_state: ApprovalDeclineState
    declined_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.record_id, UUID) or not isinstance(self.fill_id, UUID):
            raise TypeError("record_id and fill_id must be UUIDs")
        if not isinstance(self.intent, ApprovalPaperIntent):
            raise TypeError("intent must be ApprovalPaperIntent")
        if not isinstance(self.quote, ApprovalPaperQuote):
            raise TypeError("quote must be ApprovalPaperQuote")
        if self.quote.symbol != self.intent.symbol:
            raise ValueError("quote symbol must match intent symbol")
        if self.quote.observed_at < self.intent.proposed_at:
            raise ValueError("quote cannot precede Robinhood approval proposal")
        price = require_positive_decimal(self.fill_price, "fill_price")
        commission = require_decimal(self.commission, "commission")
        if commission < 0:
            raise ValueError("commission must be zero or greater")
        slippage = require_decimal(self.slippage_basis_points, "slippage_basis_points")
        if not Decimal("0") <= slippage <= _MAX_SLIPPAGE_BPS:
            raise ValueError("slippage_basis_points must be between 0 and 9999")
        expected_price = synthetic_market_fill_price(
            self.intent.side,
            self.quote,
            slippage,
        )
        if price != expected_price:
            raise ValueError("fill_price does not match quote/slippage policy")
        object.__setattr__(
            self, "filled_at", normalize_utc(self.filled_at, "filled_at")
        )
        if self.filled_at != self.quote.observed_at:
            raise ValueError("filled_at must equal quote observed_at")
        if not isinstance(self.decline_state, ApprovalDeclineState):
            raise TypeError("decline_state must be ApprovalDeclineState")
        if self.decline_state is ApprovalDeclineState.PENDING_DECLINE:
            if self.declined_at is not None:
                raise ValueError("pending decline must not contain declined_at")
        else:
            if self.declined_at is None:
                raise ValueError("declined record requires declined_at")
            normalized_declined = normalize_utc(self.declined_at, "declined_at")
            if normalized_declined < self.filled_at:
                raise ValueError("declined_at cannot precede synthetic fill")
            object.__setattr__(self, "declined_at", normalized_declined)
        if self.record_id != approval_paper_record_id(self.intent.approval_id):
            raise ValueError("record_id does not match approval_id")
        if self.fill_id != approval_paper_fill_id(self.intent.approval_id):
            raise ValueError("fill_id does not match approval_id")


def approval_paper_record_id(approval_id: str) -> UUID:
    """Derive one deterministic paper-record identity from an approval ID."""

    if not isinstance(approval_id, str) or not approval_id:
        raise ValueError("approval_id must be nonblank")
    return uuid5(_RECORD_NAMESPACE, approval_id)


def approval_paper_fill_id(approval_id: str) -> UUID:
    """Derive one deterministic synthetic-fill identity from an approval ID."""

    if not isinstance(approval_id, str) or not approval_id:
        raise ValueError("approval_id must be nonblank")
    return uuid5(_FILL_NAMESPACE, approval_id)


def synthetic_market_fill_price(
    side: OrderSide,
    quote: ApprovalPaperQuote,
    slippage_basis_points: Decimal,
) -> Decimal:
    """Apply conservative side-aware slippage to one post-proposal quote."""

    if not isinstance(side, OrderSide):
        raise TypeError("side must be an OrderSide")
    if not isinstance(quote, ApprovalPaperQuote):
        raise TypeError("quote must be ApprovalPaperQuote")
    slippage = require_decimal(slippage_basis_points, "slippage_basis_points")
    if not Decimal("0") <= slippage <= _MAX_SLIPPAGE_BPS:
        raise ValueError("slippage_basis_points must be between 0 and 9999")
    fraction = slippage / _BPS_DENOMINATOR
    if side is OrderSide.BUY:
        return quote.ask * (Decimal("1") + fraction)
    return quote.bid * (Decimal("1") - fraction)
