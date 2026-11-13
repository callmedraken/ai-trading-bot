"""Provider-independent L43 contracts shared by the observer and adapters."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from trading_bot.domain import OrderSide
from trading_bot.live_prototype.live_controller import PreparedInvocation
from trading_bot.live_prototype.tiny_live_policy import (
    ExactOwnedSellProposal,
    ManualCloseTrigger,
    NormalizedSellReview,
    SellOrderArguments,
)

_ACCOUNT_NUMBER = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_PROVIDER_ORDER_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


class L43TransportError(RuntimeError):
    """Fixed, sanitized error for an injected L43 effect boundary."""

    def __init__(self, code: str) -> None:
        if type(code) is not str or _SAFE_CODE.fullmatch(code) is None:
            raise ValueError("L43 transport error code must be sanitized")
        self.code = code
        super().__init__(code)


class L43ReviewStatus(StrEnum):
    NORMALIZED_UNKNOWN = "NORMALIZED_UNKNOWN"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class L43ReviewNormalization:
    """A sanitized review result with no provider payload."""

    status: L43ReviewStatus
    review: NormalizedSellReview | None
    manual_close_trigger: ManualCloseTrigger | None
    reason_code: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, L43ReviewStatus):
            raise TypeError("review status must be closed")
        if self.review is not None and type(self.review) is not NormalizedSellReview:
            raise TypeError("normalized review must use the accepted contract")
        if self.manual_close_trigger is not None and not isinstance(
            self.manual_close_trigger, ManualCloseTrigger
        ):
            raise TypeError("manual-close trigger must be closed")
        if (
            type(self.reason_code) is not str
            or _SAFE_CODE.fullmatch(self.reason_code) is None
        ):
            raise ValueError("review reason must be sanitized ASCII")
        if self.status is L43ReviewStatus.NORMALIZED_UNKNOWN:
            if (
                self.review is None
                or self.manual_close_trigger
                is not ManualCloseTrigger.SELL_REVIEW_UNKNOWN
            ):
                raise ValueError("unknown review must retain a manual-close trigger")
            if self.review.outcome.value != "UNKNOWN":
                raise ValueError("raw provider output cannot assert review outcome")
            if self.review.semantics.value != "UNKNOWN":
                raise ValueError("raw provider output cannot assert review semantics")
        elif self.review is not None or self.manual_close_trigger is None:
            raise ValueError("blocked review requires only a manual-close trigger")


@dataclass(frozen=True, slots=True)
class L43PlacementReceipt:
    """The only provider fact allowed to cross the placement boundary."""

    provider_order_id: str

    def __post_init__(self) -> None:
        if (
            type(self.provider_order_id) is not str
            or _PROVIDER_ORDER_ID.fullmatch(self.provider_order_id) is None
        ):
            raise ValueError("provider order ID is not canonical")


class L43PreparedEffectCall(Protocol):
    """One schema-checked call that can be resolved and invoked once."""

    def resolve_callable(
        self, *, authority_sha256: str | None = None
    ) -> Callable[[PreparedInvocation], Awaitable[L43PlacementReceipt]]: ...


class L43EffectTransport(Protocol):
    """Injected entry/review/sell seam consumed structurally by the operator."""

    def prepare_entry_order(
        self,
        *,
        account_number: str,
        requested_dollars: Decimal,
        ref_id: str | None = None,
    ) -> AbstractAsyncContextManager[L43PreparedEffectCall]: ...

    def prepare_sell_order(
        self,
        *,
        account_number: str,
        arguments: SellOrderArguments,
    ) -> AbstractAsyncContextManager[L43PreparedEffectCall]: ...

    async def review_sell_order(
        self, *, account_number: str, proposal: ExactOwnedSellProposal
    ) -> L43ReviewNormalization: ...


@dataclass(frozen=True, slots=True)
class L43AccountIdentity:
    """Normalized account handle and fingerprint supplied by a read adapter."""

    account_number: str
    account_fingerprint: str

    def __post_init__(self) -> None:
        if (
            type(self.account_number) is not str
            or _ACCOUNT_NUMBER.fullmatch(self.account_number) is None
        ):
            raise ValueError("account handle is invalid")
        if (
            type(self.account_fingerprint) is not str
            or _SHA256.fullmatch(self.account_fingerprint) is None
        ):
            raise ValueError("account fingerprint is invalid")

    @property
    def fingerprint(self) -> str:
        return self.account_fingerprint


@dataclass(frozen=True, slots=True)
class L43PositionFact:
    """Normalized position facts required by the source-owned observer."""

    symbol: str
    quantity: Decimal
    shares_available_for_sells: Decimal
    position_type: str


@dataclass(frozen=True, slots=True)
class L43ExecutionFact:
    execution_id: str
    quantity: Decimal
    price: Decimal
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class L43DollarAmountFact:
    amount: Decimal
    currency_code: str


@dataclass(frozen=True, slots=True)
class L43OrderFact:
    """Normalized order and execution facts; no provider model crosses inward."""

    order_id: str
    symbol: str
    side: OrderSide
    state: str
    placed_agent: str
    agent_initiated: bool
    created_at: datetime
    market_hours: str
    time_in_force: str
    order_type: str
    cumulative_quantity: Decimal
    average_price: Decimal | None
    dollar_based_amount: L43DollarAmountFact | None
    executions: tuple[L43ExecutionFact, ...]

    def __post_init__(self) -> None:
        if type(self.agent_initiated) is not bool:
            raise TypeError("agent_initiated must be a bool")


@dataclass(frozen=True, slots=True)
class L43ReadPage:
    """One normalized page returned by an injected account/position/order read."""

    rows: tuple[object, ...]
    next_cursor: str | None


class L43PreEffectReadBoundary(Protocol):
    """Normalized account/position/order read seam consumed by the observer."""

    def get_accounts(self) -> L43AccountIdentity: ...

    def get_equity_positions(self, arguments: Mapping[str, object]) -> L43ReadPage: ...

    def get_equity_orders(self, arguments: Mapping[str, object]) -> L43ReadPage: ...


__all__ = [
    "L43AccountIdentity",
    "L43DollarAmountFact",
    "L43EffectTransport",
    "L43ExecutionFact",
    "L43OrderFact",
    "L43PlacementReceipt",
    "L43PositionFact",
    "L43PreparedEffectCall",
    "L43PreEffectReadBoundary",
    "L43ReadPage",
    "L43ReviewNormalization",
    "L43ReviewStatus",
    "L43TransportError",
]
