"""Shared deterministic simulator initialization for offline CLIs."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import OrderFill, OrderSide, Symbol
from trading_bot.execution import OrderEngine
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.ledger import PaperLedger
from trading_bot.runtime import PaperPortfolioRuntime
from trading_bot.simulation import OptimizedPaperPortfolioSimulator

_BOOTSTRAP_NAMESPACE = UUID("20e175f9-81ad-5985-b460-15a79acbb41e")
_BOOTSTRAP_VERSION = "optimized-simulation-cli-bootstrap-v1"


class InitializationMode(StrEnum):
    CASH_ONLY = "CASH_ONLY"
    BOOTSTRAP_FILLS = "BOOTSTRAP_FILLS"


@dataclass(frozen=True, slots=True)
class InitialPositionConfig:
    symbol: Symbol
    quantity: Decimal
    average_cost: Decimal


@dataclass(frozen=True, slots=True)
class InitialLedgerConfig:
    initialization_mode: InitializationMode
    as_of: datetime
    available_cash: Decimal
    positions: tuple[InitialPositionConfig, ...]


def initialize_ledger(
    request_id: UUID, initial: InitialLedgerConfig
) -> tuple[PaperLedger, tuple[OrderFill, ...]]:
    """Create a ledger, applying deterministic zero-commission bootstrap fills."""
    if initial.initialization_mode is InitializationMode.CASH_ONLY:
        return PaperLedger(initial.available_cash), ()
    basis = sum(
        (item.quantity * item.average_cost for item in initial.positions),
        start=Decimal("0"),
    )
    ledger = PaperLedger(initial.available_cash + basis)
    fills = []
    for ordinal, position in enumerate(initial.positions):
        material = "|".join(
            (
                _BOOTSTRAP_VERSION,
                str(request_id),
                initial.initialization_mode.value,
                str(ordinal),
                str(position.symbol),
                canonical_decimal(position.quantity),
                canonical_decimal(position.average_cost),
                initial.as_of.isoformat(),
            )
        )
        fill = OrderFill(
            uuid5(_BOOTSTRAP_NAMESPACE, f"{material}|fill"),
            uuid5(_BOOTSTRAP_NAMESPACE, f"{material}|order"),
            position.symbol,
            OrderSide.BUY,
            position.quantity,
            position.average_cost,
            Decimal("0"),
            initial.as_of,
        )
        ledger.apply_fill(fill)
        fills.append(fill)
    return ledger, tuple(fills)


def build_optimized_simulator(
    request_id: UUID,
    initial: InitialLedgerConfig,
    simulator_type=OptimizedPaperPortfolioSimulator,  # type: ignore[no-untyped-def]
) -> tuple[
    OptimizedPaperPortfolioSimulator,
    tuple[OrderFill, ...],
]:
    """Build one fresh authoritative engine/runtime/simulator stack."""
    ledger, fills = initialize_ledger(request_id, initial)
    runtime = PaperPortfolioRuntime(OrderEngine(), ledger)
    return simulator_type(runtime), fills
