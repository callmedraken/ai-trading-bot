"""Authoritative in-memory accounting for a simulated account."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING
from uuid import UUID

from trading_bot.domain import OrderFill, OrderSide, Position, Symbol
from trading_bot.domain._validation import require_positive_decimal
from trading_bot.ledger.exceptions import (
    DuplicateFillError,
    InsufficientCashError,
    InsufficientPositionError,
    PositionNotFoundError,
    PriceNotAvailableError,
)
from trading_bot.ledger.models import AccountSnapshot

if TYPE_CHECKING:
    from trading_bot.ledger.checkpoint_state import CompactPaperLedgerState


@dataclass(frozen=True, slots=True)
class _LedgerPosition:
    quantity: Decimal
    total_cost_basis: Decimal

    @property
    def average_cost(self) -> Decimal:
        return self.total_cost_basis / self.quantity


class PaperLedger:
    """Apply completed fills to a long-only, no-margin paper account."""

    def __init__(self, starting_cash: Decimal) -> None:
        require_positive_decimal(starting_cash, "starting_cash")
        self._cash = starting_cash
        self._realized_profit_loss = Decimal("0")
        self._positions: dict[Symbol, _LedgerPosition] = {}
        self._fills: list[OrderFill] = []
        self._fill_ids: set[UUID] = set()
        self._is_compact_restored = False

    @property
    def cash(self) -> Decimal:
        return self._cash

    @property
    def realized_profit_loss(self) -> Decimal:
        return self._realized_profit_loss

    @property
    def positions(self) -> Mapping[Symbol, Position]:
        snapshot = {
            symbol: Position(symbol, position.quantity, position.average_cost)
            for symbol, position in self._positions.items()
        }
        return MappingProxyType(snapshot)

    @property
    def fills(self) -> tuple[OrderFill, ...]:
        return tuple(self._fills)

    @property
    def is_compact_restored(self) -> bool:
        """Whether history and duplicate-fill membership were compacted away.

        A true value means ``fills`` is intentionally empty at restoration and
        must not be interpreted as complete historical duplicate-fill evidence.
        """
        return self._is_compact_restored

    def export_compact_checkpoint_state(
        self,
        *,
        as_of: datetime,
    ) -> CompactPaperLedgerState:
        """Return exact compact accounting state in current position order."""
        from trading_bot.ledger.checkpoint_state import (
            CompactPaperLedgerPosition,
            CompactPaperLedgerState,
        )

        positions = tuple(
            CompactPaperLedgerPosition.from_exact_basis(
                symbol,
                position.quantity,
                position.total_cost_basis,
            )
            for symbol, position in self._positions.items()
        )
        return CompactPaperLedgerState.create(
            as_of=as_of,
            cash=self._cash,
            positions=positions,
            realized_profit_loss=self._realized_profit_loss,
        )

    @classmethod
    def from_compact_checkpoint_state(
        cls,
        state: CompactPaperLedgerState,
    ) -> PaperLedger:
        """Build a fresh ledger without reconstructing any historical fills."""
        from trading_bot.ledger.checkpoint_state import CompactPaperLedgerState

        if type(state) is not CompactPaperLedgerState:
            raise TypeError("state must be an exact CompactPaperLedgerState")
        ledger = cls.__new__(cls)
        ledger._cash = state.cash
        ledger._realized_profit_loss = state.realized_profit_loss
        ledger._positions = {
            item.symbol: _LedgerPosition(item.quantity, item.total_cost_basis)
            for item in state.positions
        }
        ledger._fills = []
        ledger._fill_ids = set()
        ledger._is_compact_restored = True
        return ledger

    def get_position(self, symbol: Symbol) -> Position | None:
        """Return a fresh public view of an owned position, if present."""
        if not isinstance(symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        position = self._positions.get(symbol)
        if position is None:
            return None
        return Position(symbol, position.quantity, position.average_cost)

    def apply_fill(self, fill: OrderFill) -> None:
        """Validate and atomically apply one completed fill."""
        if not isinstance(fill, OrderFill):
            raise TypeError("fill must be an OrderFill")
        if fill.fill_id in self._fill_ids:
            raise DuplicateFillError(f"fill {fill.fill_id} has already been applied")

        if fill.side is OrderSide.BUY:
            new_cash, new_position, realized_change = self._calculate_buy(fill)
            remove_position = False
        else:
            new_cash, new_position, realized_change = self._calculate_sell(fill)
            remove_position = new_position is None

        # No state changes occur before every calculation and validation succeeds.
        self._cash = new_cash
        self._realized_profit_loss += realized_change
        if remove_position:
            del self._positions[fill.symbol]
        else:
            assert new_position is not None
            self._positions[fill.symbol] = new_position
        self._fills.append(fill)
        self._fill_ids.add(fill.fill_id)

    def _calculate_buy(
        self, fill: OrderFill
    ) -> tuple[Decimal, _LedgerPosition, Decimal]:
        cash_required = fill.gross_amount + fill.commission
        if cash_required > self._cash:
            raise InsufficientCashError(
                f"buy requires {cash_required}, but only {self._cash} cash is available"
            )
        current = self._positions.get(fill.symbol)
        current_quantity = current.quantity if current else Decimal("0")
        current_basis = current.total_cost_basis if current else Decimal("0")
        position = _LedgerPosition(
            quantity=current_quantity + fill.quantity,
            total_cost_basis=current_basis + cash_required,
        )
        return self._cash - cash_required, position, Decimal("0")

    def _calculate_sell(
        self, fill: OrderFill
    ) -> tuple[Decimal, _LedgerPosition | None, Decimal]:
        current = self._positions.get(fill.symbol)
        if current is None:
            raise PositionNotFoundError(f"no open position exists for {fill.symbol}")
        if fill.quantity > current.quantity:
            raise InsufficientPositionError(
                f"cannot sell {fill.quantity} {fill.symbol}; owned quantity is "
                f"{current.quantity}"
            )

        removed_basis = current.average_cost * fill.quantity
        cash_credit = fill.gross_amount - fill.commission
        new_cash = self._cash + cash_credit
        if new_cash < Decimal("0"):
            raise InsufficientCashError(
                "sell commission would make account cash negative"
            )
        realized_change = cash_credit - removed_basis
        remaining_quantity = current.quantity - fill.quantity
        if remaining_quantity == Decimal("0"):
            new_position = None
        else:
            new_position = _LedgerPosition(
                quantity=remaining_quantity,
                total_cost_basis=current.total_cost_basis - removed_basis,
            )
        return new_cash, new_position, realized_change

    def create_account_snapshot(
        self, prices: Mapping[Symbol, Decimal], timestamp: datetime
    ) -> AccountSnapshot:
        """Value current positions without changing accounting state."""
        market_value = Decimal("0")
        remaining_cost_basis = Decimal("0")
        for symbol, position in self._positions.items():
            if symbol not in prices:
                raise PriceNotAvailableError(
                    f"no current price is available for {symbol}"
                )
            price = prices[symbol]
            try:
                require_positive_decimal(price, f"price for {symbol}")
            except (TypeError, ValueError) as error:
                raise PriceNotAvailableError(
                    f"current price for {symbol} must be a positive Decimal"
                ) from error
            market_value += position.quantity * price
            remaining_cost_basis += position.total_cost_basis

        equity = self._cash + market_value
        return AccountSnapshot(
            timestamp=timestamp,
            cash=self._cash,
            positions_market_value=market_value,
            equity=equity,
            buying_power=self._cash,
            realized_profit_loss=self._realized_profit_loss,
            unrealized_profit_loss=market_value - remaining_cost_basis,
        )
