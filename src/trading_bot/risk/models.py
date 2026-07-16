"""Immutable inputs and outputs for deterministic risk evaluation."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from trading_bot.domain import Position, Symbol, TradeProposal
from trading_bot.domain._validation import (
    normalize_utc,
    require_decimal,
    require_positive_decimal,
)


class RiskOutcome(StrEnum):
    APPROVED = "APPROVED"
    RESIZED = "RESIZED"
    REJECTED = "REJECTED"


class RiskReasonCode(StrEnum):
    TRADING_DISABLED = "TRADING_DISABLED"
    BUYING_DISABLED = "BUYING_DISABLED"
    SELLING_DISABLED = "SELLING_DISABLED"
    PRICE_NOT_AVAILABLE = "PRICE_NOT_AVAILABLE"
    POSITION_NOT_FOUND = "POSITION_NOT_FOUND"
    CASH_CAPACITY = "CASH_CAPACITY"
    MINIMUM_CASH_RESERVE = "MINIMUM_CASH_RESERVE"
    MAX_ORDER_NOTIONAL = "MAX_ORDER_NOTIONAL"
    MAX_POSITION_PERCENT = "MAX_POSITION_PERCENT"
    MAX_NEW_POSITION_PERCENT = "MAX_NEW_POSITION_PERCENT"
    MAX_TOTAL_EXPOSURE_PERCENT = "MAX_TOTAL_EXPOSURE_PERCENT"
    SELL_QUANTITY_REDUCED = "SELL_QUANTITY_REDUCED"
    QUANTITY_INCREMENT = "QUANTITY_INCREMENT"
    QUANTITY_TOO_SMALL = "QUANTITY_TOO_SMALL"


@dataclass(frozen=True, slots=True)
class RiskReason:
    """A stable reason code with human-readable evaluation details."""

    code: RiskReasonCode
    message: str
    observed: Decimal | None = None
    limit: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, RiskReasonCode):
            raise TypeError("code must be a RiskReasonCode")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("message must be nonblank")
        for field_name in ("observed", "limit"):
            value = getattr(self, field_name)
            if value is not None:
                require_decimal(value, field_name)


@dataclass(frozen=True, slots=True)
class RiskContext:
    """An immutable account and market snapshot used for one evaluation."""

    cash: Decimal
    equity: Decimal
    positions: Mapping[Symbol, Position]
    current_price: Decimal | None
    total_market_exposure: Decimal
    new_trading_enabled: bool
    as_of: datetime

    def __post_init__(self) -> None:
        require_decimal(self.cash, "cash")
        require_positive_decimal(self.equity, "equity")
        require_decimal(self.total_market_exposure, "total_market_exposure")
        if self.cash < Decimal("0"):
            raise ValueError("cash must be zero or greater")
        if self.total_market_exposure < Decimal("0"):
            raise ValueError("total_market_exposure must be zero or greater")
        if not isinstance(self.new_trading_enabled, bool):
            raise TypeError("new_trading_enabled must be a bool")
        if self.current_price is not None:
            require_positive_decimal(self.current_price, "current_price")
        copied_positions: dict[Symbol, Position] = {}
        for symbol, position in self.positions.items():
            if not isinstance(symbol, Symbol) or not isinstance(position, Position):
                raise TypeError("positions must map Symbol values to Position values")
            if position.symbol != symbol:
                raise ValueError("position mapping keys must match position symbols")
            copied_positions[symbol] = position
        object.__setattr__(self, "positions", MappingProxyType(copied_positions))
        object.__setattr__(self, "as_of", normalize_utc(self.as_of, "as_of"))


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Deterministic limits expressed as Decimal fractions and amounts."""

    max_position_percent: Decimal = Decimal("0.20")
    max_total_exposure_percent: Decimal = Decimal("0.80")
    max_order_notional: Decimal | None = None
    max_new_position_percent: Decimal | None = None
    minimum_cash_reserve_percent: Decimal = Decimal("0.10")
    allow_fractional_shares: bool = True
    fractional_increment: Decimal = Decimal("0.001")
    allow_buying: bool = True
    allow_selling: bool = True
    estimated_commission: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for field_name in (
            "max_position_percent",
            "max_total_exposure_percent",
        ):
            value = require_positive_decimal(getattr(self, field_name), field_name)
            if value > Decimal("1"):
                raise ValueError(f"{field_name} must be no greater than 1")
        require_decimal(
            self.minimum_cash_reserve_percent, "minimum_cash_reserve_percent"
        )
        if not Decimal("0") <= self.minimum_cash_reserve_percent <= Decimal("1"):
            raise ValueError("minimum_cash_reserve_percent must be between 0 and 1")
        for field_name in ("max_order_notional", "max_new_position_percent"):
            value = getattr(self, field_name)
            if value is not None:
                require_positive_decimal(value, field_name)
        if (
            self.max_new_position_percent is not None
            and self.max_new_position_percent > Decimal("1")
        ):
            raise ValueError("max_new_position_percent must be no greater than 1")
        require_positive_decimal(self.fractional_increment, "fractional_increment")
        require_decimal(self.estimated_commission, "estimated_commission")
        if self.estimated_commission < Decimal("0"):
            raise ValueError("estimated_commission must be zero or greater")
        for field_name in (
            "allow_fractional_shares",
            "allow_buying",
            "allow_selling",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a bool")


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """The immutable result of evaluating one trade proposal."""

    proposal: TradeProposal
    outcome: RiskOutcome
    approved_quantity: Decimal
    reasons: tuple[RiskReason, ...]
    evaluated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.proposal, TradeProposal):
            raise TypeError("proposal must be a TradeProposal")
        if not isinstance(self.outcome, RiskOutcome):
            raise TypeError("outcome must be a RiskOutcome")
        require_decimal(self.approved_quantity, "approved_quantity")
        if not isinstance(self.reasons, tuple) or not all(
            isinstance(reason, RiskReason) for reason in self.reasons
        ):
            raise TypeError("reasons must be a tuple of RiskReason values")
        object.__setattr__(
            self, "evaluated_at", normalize_utc(self.evaluated_at, "evaluated_at")
        )
        desired = self.proposal.desired_quantity
        if self.outcome is RiskOutcome.APPROVED:
            if self.approved_quantity != desired:
                raise ValueError("approved decisions must retain desired quantity")
        elif self.outcome is RiskOutcome.RESIZED:
            if not Decimal("0") < self.approved_quantity < desired:
                raise ValueError(
                    "resized decisions require a smaller positive quantity"
                )
            if not self.reasons:
                raise ValueError("resized decisions require at least one reason")
        else:
            if self.approved_quantity != Decimal("0"):
                raise ValueError("rejected decisions must approve zero quantity")
            if not self.reasons:
                raise ValueError("rejected decisions require at least one reason")
