"""Immutable Qt-free production strategy presentation; no authority."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import UUID

from trading_bot.strategies.production import (
    MOVING_AVERAGE_STRATEGY_ID,
    MOVING_AVERAGE_STRATEGY_VERSION,
)

MAX_PRODUCTION_STRATEGY_BYTES = 16 * 1024
MAX_STRATEGY_WINDOW = 1_000_000
MAX_STRATEGY_QUANTITY_CHARACTERS = 128


class ProductionStrategyPageStatus(Enum):
    UNAVAILABLE = "UNAVAILABLE"
    AVAILABLE = "AVAILABLE"
    ATTENTION = "ATTENTION"


class ProductionStrategyDiagnostic(Enum):
    NO_CONTRACT = "No production strategy contract is selected."
    RECORDED = "Explicit production strategy contract is available read-only."
    INVALID = "Selected production strategy contract is unreadable or invalid."


@dataclass(frozen=True, slots=True)
class ProductionStrategyContractView:
    contract_id: UUID
    target_session_date: date
    source_head: str
    source_tree: str
    strategy_id: str
    strategy_version: str
    symbol: str
    short_window: int
    long_window: int
    desired_quantity: Decimal

    def __post_init__(self) -> None:
        if type(self.contract_id) is not UUID or self.contract_id.version != 5:
            raise ValueError("Exact UUID5 contract identity required")
        if type(self.target_session_date) is not date:
            raise TypeError("Exact strategy session date required")
        for value in (self.source_head, self.source_tree):
            if type(value) is not str or re.fullmatch(r"[0-9a-f]{40}", value) is None:
                raise ValueError("Invalid strategy source digest")
        for value, expected in (
            (self.strategy_id, MOVING_AVERAGE_STRATEGY_ID),
            (self.strategy_version, MOVING_AVERAGE_STRATEGY_VERSION),
        ):
            if type(value) is not str or value != expected:
                raise ValueError("Unsupported strategy vocabulary")
        if (
            type(self.symbol) is not str
            or re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,15}", self.symbol) is None
        ):
            raise ValueError("Invalid bounded strategy symbol")
        for value in (self.short_window, self.long_window):
            if type(value) is not int or not 1 <= value <= MAX_STRATEGY_WINDOW:
                raise ValueError("Invalid bounded strategy window")
        if self.short_window >= self.long_window:
            raise ValueError("Strategy window ordering required")
        quantity = self.desired_quantity
        if type(quantity) is not Decimal or not quantity.is_finite() or quantity <= 0:
            raise ValueError("Positive exact finite strategy quantity required")
        # Bound fixed-point rendering before allocating it, independently of context.
        digits = quantity.as_tuple().digits
        exponent = quantity.as_tuple().exponent
        if len(digits) + abs(exponent) > MAX_STRATEGY_QUANTITY_CHARACTERS:
            raise ValueError("Strategy quantity exceeds presentation bound")


@dataclass(frozen=True, slots=True)
class ProductionStrategyPageState:
    status: ProductionStrategyPageStatus
    diagnostic: ProductionStrategyDiagnostic
    contract: ProductionStrategyContractView | None = None

    def __post_init__(self) -> None:
        if (
            type(self.status) is not ProductionStrategyPageStatus
            or type(self.diagnostic) is not ProductionStrategyDiagnostic
        ):
            raise TypeError("Exact strategy classifications required")
        expected = {
            ProductionStrategyDiagnostic.NO_CONTRACT: (
                ProductionStrategyPageStatus.UNAVAILABLE
            ),
            ProductionStrategyDiagnostic.RECORDED: (
                ProductionStrategyPageStatus.AVAILABLE
            ),
            ProductionStrategyDiagnostic.INVALID: (
                ProductionStrategyPageStatus.ATTENTION
            ),
        }[self.diagnostic]
        if self.status is not expected:
            raise ValueError("Strategy classifications conflict")
        if self.status is ProductionStrategyPageStatus.AVAILABLE:
            if type(self.contract) is not ProductionStrategyContractView:
                raise TypeError("Available strategy requires exact view")
        elif self.contract is not None:
            raise ValueError(
                "Invalid or unavailable strategy cannot contain a contract"
            )

    @property
    def message(self) -> str:
        return self.diagnostic.value


def unavailable_production_strategy_state() -> ProductionStrategyPageState:
    return ProductionStrategyPageState(
        ProductionStrategyPageStatus.UNAVAILABLE,
        ProductionStrategyDiagnostic.NO_CONTRACT,
    )
