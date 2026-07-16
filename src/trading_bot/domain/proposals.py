"""High-level trading intent shared across system boundaries."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID, uuid4

from trading_bot.domain._validation import (
    normalize_utc,
    require_decimal,
    require_positive_decimal,
)
from trading_bot.domain.enums import OrderSide
from trading_bot.domain.market import Symbol


@dataclass(frozen=True, slots=True)
class TradeProposal:
    """An immutable expression of trading intent, not an executable order."""

    proposal_id: UUID
    symbol: Symbol
    side: OrderSide
    desired_quantity: Decimal
    created_at: datetime
    reason: str
    confidence: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, UUID):
            raise TypeError("proposal_id must be a UUID")
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be an OrderSide")
        require_positive_decimal(self.desired_quantity, "desired_quantity")
        object.__setattr__(
            self, "created_at", normalize_utc(self.created_at, "created_at")
        )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a nonblank string")
        if self.confidence is not None:
            require_decimal(self.confidence, "confidence")
            if not Decimal("0") <= self.confidence <= Decimal("1"):
                raise ValueError("confidence must be between 0 and 1")

    @classmethod
    def create(
        cls,
        *,
        symbol: Symbol,
        side: OrderSide,
        desired_quantity: Decimal,
        created_at: datetime,
        reason: str,
        confidence: Decimal | None = None,
        proposal_id: UUID | None = None,
    ) -> Self:
        """Create a proposal, generating its identifier when omitted."""
        return cls(
            proposal_id=proposal_id or uuid4(),
            symbol=symbol,
            side=side,
            desired_quantity=desired_quantity,
            created_at=created_at,
            reason=reason,
            confidence=confidence,
        )
