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
    return initialize_canonical_ledger(
        mode=initial.initialization_mode.value,
        as_of=initial.as_of,
        available_cash=initial.available_cash,
        positions=tuple(
            (item.symbol, item.quantity, item.average_cost)
            for item in initial.positions
        ),
        identity_namespace=_BOOTSTRAP_NAMESPACE,
        identity_material=(
            _BOOTSTRAP_VERSION,
            str(request_id),
            initial.initialization_mode.value,
        ),
    )


def initialize_canonical_ledger(
    *,
    mode: str,
    as_of: datetime,
    available_cash: Decimal,
    positions: tuple[tuple[Symbol, Decimal, Decimal], ...],
    identity_namespace: UUID,
    identity_material: tuple[str, ...],
) -> tuple[PaperLedger, tuple[OrderFill, ...]]:
    """Build a ledger from canonical values and caller-owned identity material."""
    if mode == InitializationMode.CASH_ONLY.value:
        return PaperLedger(available_cash), ()
    basis = sum(
        (quantity * unit_cost for _, quantity, unit_cost in positions),
        start=Decimal("0"),
    )
    ledger = PaperLedger(available_cash + basis)
    fills = []
    for ordinal, (symbol, quantity, unit_cost) in enumerate(positions):
        material = "|".join(
            (
                *identity_material,
                str(ordinal),
                str(symbol),
                canonical_decimal(quantity),
                canonical_decimal(unit_cost),
                as_of.isoformat(),
            )
        )
        fill = OrderFill(
            uuid5(identity_namespace, f"{material}|fill"),
            uuid5(identity_namespace, f"{material}|order"),
            symbol,
            OrderSide.BUY,
            quantity,
            unit_cost,
            Decimal("0"),
            as_of,
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
