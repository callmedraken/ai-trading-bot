"""Exact compact checkpoint state for the authoritative paper ledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Context, Decimal, localcontext
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from trading_bot.domain import Symbol
from trading_bot.ledger.exceptions import (
    CompactPaperLedgerRestorationError,
    InvalidCompactPaperLedgerStateError,
)

if TYPE_CHECKING:
    from trading_bot.ledger.ledger import PaperLedger

COMPACT_PAPER_LEDGER_ARITHMETIC_VERSION = "compact-paper-ledger-arithmetic-v1"
COMPACT_PAPER_LEDGER_STATE_MATERIAL_VERSION = "compact-paper-ledger-state-v1"
COMPACT_PAPER_LEDGER_STATE_NAMESPACE = UUID("86b4402e-fdbc-56a1-85b6-a5dcfdf05f67")
MAX_COMPACT_PAPER_LEDGER_POSITIONS = 100

_MAX_AUTHORITATIVE_SIGNIFICANT_DIGITS = 1024
_MAX_AUTHORITATIVE_SCALE = 1024
_MAX_AUTHORITATIVE_ADJUSTED_EXPONENT = 1024
_MAX_AVERAGE_SCALE = 3072
_MAX_AVERAGE_ADJUSTED_EXPONENT = 2048
_ARITHMETIC_CONTEXT = Context(prec=1024, Emax=999_999, Emin=-999_999)
_ZERO = Decimal("0")
_EMPTY_HISTORY_MARKER = "historical-fill-membership-empty"


class CompactPaperLedgerHistoryMode(StrEnum):
    """Historical state deliberately represented by a compact checkpoint."""

    EMPTY = "EMPTY"


class CompactPaperLedgerReconciliationStatus(StrEnum):
    """Outcome of exact in-memory compact-state restoration."""

    PASS = "PASS"


def _authoritative_decimal(
    value: object,
    name: str,
    *,
    allow_negative: bool,
    positive: bool,
) -> Decimal:
    if type(value) is not Decimal:
        raise InvalidCompactPaperLedgerStateError(f"{name} must be an exact Decimal")
    if not value.is_finite():
        raise InvalidCompactPaperLedgerStateError(f"{name} must be finite")
    normalized = _ZERO if value == _ZERO else value
    if positive and normalized <= _ZERO:
        raise InvalidCompactPaperLedgerStateError(f"{name} must be positive")
    if not positive and not allow_negative and normalized < _ZERO:
        raise InvalidCompactPaperLedgerStateError(f"{name} must be nonnegative")
    parts = normalized.as_tuple()
    if (
        len(parts.digits) > _MAX_AUTHORITATIVE_SIGNIFICANT_DIGITS
        or parts.exponent < -_MAX_AUTHORITATIVE_SCALE
        or (
            normalized != _ZERO
            and normalized.adjusted() > _MAX_AUTHORITATIVE_ADJUSTED_EXPONENT
        )
    ):
        raise InvalidCompactPaperLedgerStateError(
            f"{name} exceeds the supported Decimal bounds"
        )
    return normalized


def _utc(value: object, name: str) -> datetime:
    if type(value) is not datetime:
        raise InvalidCompactPaperLedgerStateError(f"{name} must be an exact datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidCompactPaperLedgerStateError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _positions(
    value: object,
) -> tuple[CompactPaperLedgerPosition, ...]:
    try:
        positions = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise InvalidCompactPaperLedgerStateError(
            "positions must be iterable"
        ) from error
    if any(type(item) is not CompactPaperLedgerPosition for item in positions):
        raise InvalidCompactPaperLedgerStateError(
            "positions must contain exact CompactPaperLedgerPosition values"
        )
    if len(positions) > MAX_COMPACT_PAPER_LEDGER_POSITIONS:
        raise InvalidCompactPaperLedgerStateError(
            "positions exceed the supported count"
        )
    if len({item.symbol for item in positions}) != len(positions):
        raise InvalidCompactPaperLedgerStateError("position symbols must be unique")
    return positions


def _canonical_decimal(value: Decimal) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise InvalidCompactPaperLedgerStateError(
            "identity Decimal must be exact and finite"
        )
    if value == _ZERO:
        return "0"
    sign, digits, exponent = value.as_tuple()
    coefficient = "".join(str(digit) for digit in digits)
    while coefficient.endswith("0"):
        coefficient = coefficient[:-1]
        exponent += 1
    if exponent >= 0:
        text = coefficient + ("0" * exponent)
    else:
        point = len(coefficient) + exponent
        text = (
            "0." + ("0" * (-point)) + coefficient
            if point <= 0
            else coefficient[:point] + "." + coefficient[point:]
        )
    return f"-{text}" if sign else text


def _framed(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(item.encode('utf-8'))}:{item}" for item in parts)


def derive_compact_paper_ledger_average_cost(
    quantity: Decimal,
    total_cost_basis: Decimal,
) -> Decimal:
    """Derive average cost under the immutable compact-ledger arithmetic policy."""
    normalized_quantity = _authoritative_decimal(
        quantity,
        "quantity",
        allow_negative=False,
        positive=True,
    )
    normalized_basis = _authoritative_decimal(
        total_cost_basis,
        "total_cost_basis",
        allow_negative=False,
        positive=True,
    )
    with localcontext(_ARITHMETIC_CONTEXT):
        average_cost = normalized_basis / normalized_quantity
    if not average_cost.is_finite() or average_cost <= _ZERO:
        raise InvalidCompactPaperLedgerStateError(
            "derived average_cost must be finite and positive"
        )
    return average_cost


@dataclass(frozen=True, slots=True)
class CompactPaperLedgerPosition:
    """One exact position whose total cost basis is authoritative."""

    symbol: Symbol
    quantity: Decimal
    total_cost_basis: Decimal
    average_cost: Decimal

    def __post_init__(self) -> None:
        if type(self.symbol) is not Symbol:
            raise InvalidCompactPaperLedgerStateError("symbol must be an exact Symbol")
        quantity = _authoritative_decimal(
            self.quantity,
            "quantity",
            allow_negative=False,
            positive=True,
        )
        total_cost_basis = _authoritative_decimal(
            self.total_cost_basis,
            "total_cost_basis",
            allow_negative=False,
            positive=True,
        )
        if type(self.average_cost) is not Decimal:
            raise InvalidCompactPaperLedgerStateError(
                "average_cost must be an exact Decimal"
            )
        if not self.average_cost.is_finite() or self.average_cost <= _ZERO:
            raise InvalidCompactPaperLedgerStateError(
                "average_cost must be finite and positive"
            )
        average_parts = self.average_cost.as_tuple()
        if (
            len(average_parts.digits) > _ARITHMETIC_CONTEXT.prec
            or average_parts.exponent < -_MAX_AVERAGE_SCALE
            or self.average_cost.adjusted() > _MAX_AVERAGE_ADJUSTED_EXPONENT
        ):
            raise InvalidCompactPaperLedgerStateError(
                "average_cost exceeds the supported Decimal bounds"
            )
        expected_average = derive_compact_paper_ledger_average_cost(
            quantity,
            total_cost_basis,
        )
        if self.average_cost != expected_average:
            raise InvalidCompactPaperLedgerStateError(
                "average_cost does not match exact total_cost_basis and quantity "
                f"under {COMPACT_PAPER_LEDGER_ARITHMETIC_VERSION}"
            )
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "total_cost_basis", total_cost_basis)
        object.__setattr__(self, "average_cost", expected_average)

    @classmethod
    def from_exact_basis(
        cls,
        symbol: Symbol,
        quantity: Decimal,
        total_cost_basis: Decimal,
    ) -> CompactPaperLedgerPosition:
        """Build a position and derive, rather than infer from, average cost."""
        average_cost = derive_compact_paper_ledger_average_cost(
            quantity,
            total_cost_basis,
        )
        return cls(symbol, quantity, total_cost_basis, average_cost)


@dataclass(frozen=True, slots=True)
class CompactPaperLedgerState:
    """Immutable exact accounting state with deliberately empty history."""

    compact_state_id: UUID
    as_of: datetime
    cash: Decimal
    positions: tuple[CompactPaperLedgerPosition, ...]
    realized_profit_loss: Decimal
    history_mode: CompactPaperLedgerHistoryMode = CompactPaperLedgerHistoryMode.EMPTY

    def __post_init__(self) -> None:
        if type(self.compact_state_id) is not UUID:
            raise InvalidCompactPaperLedgerStateError(
                "compact_state_id must be an exact UUID"
            )
        as_of = _utc(self.as_of, "as_of")
        cash = _authoritative_decimal(
            self.cash,
            "cash",
            allow_negative=False,
            positive=False,
        )
        realized = _authoritative_decimal(
            self.realized_profit_loss,
            "realized_profit_loss",
            allow_negative=True,
            positive=False,
        )
        positions = _positions(self.positions)
        if cash == _ZERO and not positions:
            raise InvalidCompactPaperLedgerStateError(
                "an all-zero account cannot be represented by PaperLedger"
            )
        if self.history_mode is not CompactPaperLedgerHistoryMode.EMPTY:
            raise InvalidCompactPaperLedgerStateError(
                "compact restoration requires intentionally empty history"
            )
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "cash", cash)
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "realized_profit_loss", realized)
        expected_id = _compact_state_id(
            as_of,
            cash,
            positions,
            realized,
            self.history_mode,
        )
        if self.compact_state_id != expected_id:
            raise InvalidCompactPaperLedgerStateError(
                "compact_state_id does not match canonical compact state"
            )

    @classmethod
    def create(
        cls,
        *,
        as_of: datetime,
        cash: Decimal,
        positions: tuple[CompactPaperLedgerPosition, ...],
        realized_profit_loss: Decimal,
    ) -> CompactPaperLedgerState:
        """Create exact compact state and its deterministic UUID5 identity."""
        normalized_as_of = _utc(as_of, "as_of")
        normalized_cash = _authoritative_decimal(
            cash,
            "cash",
            allow_negative=False,
            positive=False,
        )
        normalized_realized = _authoritative_decimal(
            realized_profit_loss,
            "realized_profit_loss",
            allow_negative=True,
            positive=False,
        )
        normalized_positions = _positions(positions)
        if normalized_cash == _ZERO and not normalized_positions:
            raise InvalidCompactPaperLedgerStateError(
                "an all-zero account cannot be represented by PaperLedger"
            )
        state_id = _compact_state_id(
            normalized_as_of,
            normalized_cash,
            normalized_positions,
            normalized_realized,
            CompactPaperLedgerHistoryMode.EMPTY,
        )
        return cls(
            state_id,
            normalized_as_of,
            normalized_cash,
            normalized_positions,
            normalized_realized,
        )


@dataclass(frozen=True, slots=True)
class CompactPaperLedgerRestorationEvidence:
    """Deterministic proof that a fresh compact-restored ledger reconciled."""

    compact_state_id: UUID
    restored_ledger_state_id: UUID
    reconciliation_status: CompactPaperLedgerReconciliationStatus

    def __post_init__(self) -> None:
        if (
            type(self.compact_state_id) is not UUID
            or type(self.restored_ledger_state_id) is not UUID
        ):
            raise CompactPaperLedgerRestorationError(
                "restoration evidence identities must be exact UUIDs"
            )
        if (
            self.reconciliation_status
            is not CompactPaperLedgerReconciliationStatus.PASS
        ):
            raise CompactPaperLedgerRestorationError(
                "restoration evidence requires PASS reconciliation"
            )


def _compact_state_id(
    as_of: datetime,
    cash: Decimal,
    positions: tuple[CompactPaperLedgerPosition, ...],
    realized_profit_loss: Decimal,
    history_mode: CompactPaperLedgerHistoryMode,
) -> UUID:
    parts = [
        COMPACT_PAPER_LEDGER_STATE_MATERIAL_VERSION,
        COMPACT_PAPER_LEDGER_ARITHMETIC_VERSION,
        as_of.isoformat(),
        _canonical_decimal(cash),
        _canonical_decimal(realized_profit_loss),
        str(len(positions)),
    ]
    for ordinal, position in enumerate(positions):
        parts.extend(
            (
                str(ordinal),
                str(position.symbol),
                _canonical_decimal(position.quantity),
                _canonical_decimal(position.total_cost_basis),
                _canonical_decimal(position.average_cost),
            )
        )
    parts.extend((history_mode.value, _EMPTY_HISTORY_MARKER))
    return uuid5(COMPACT_PAPER_LEDGER_STATE_NAMESPACE, _framed(tuple(parts)))


def compact_paper_ledger_state_id(state: CompactPaperLedgerState) -> UUID:
    """Return and independently validate one compact state's identity."""
    if type(state) is not CompactPaperLedgerState:
        raise TypeError("state must be an exact CompactPaperLedgerState")
    expected = _compact_state_id(
        state.as_of,
        state.cash,
        state.positions,
        state.realized_profit_loss,
        state.history_mode,
    )
    if state.compact_state_id != expected:
        raise InvalidCompactPaperLedgerStateError(
            "compact_state_id does not match canonical compact state"
        )
    return expected


def export_compact_paper_ledger_state(
    ledger: PaperLedger,
    *,
    as_of: datetime,
) -> CompactPaperLedgerState:
    """Export exact accounting state without synthesizing or retaining history."""
    from trading_bot.ledger.ledger import PaperLedger

    if type(ledger) is not PaperLedger:
        raise TypeError("ledger must be an exact PaperLedger")
    return ledger.export_compact_checkpoint_state(as_of=as_of)


def restore_paper_ledger_from_compact_state(
    state: CompactPaperLedgerState,
) -> tuple[PaperLedger, CompactPaperLedgerRestorationEvidence]:
    """Restore and exactly reconcile a fresh ledger with intentionally empty history."""
    from trading_bot.execution.state_fingerprints import (
        current_paper_ledger_state_id,
    )
    from trading_bot.ledger.ledger import PaperLedger

    if type(state) is not CompactPaperLedgerState:
        raise TypeError("state must be an exact CompactPaperLedgerState")
    compact_paper_ledger_state_id(state)
    ledger = PaperLedger.from_compact_checkpoint_state(state)
    try:
        with localcontext(_ARITHMETIC_CONTEXT):
            reconstructed = ledger.export_compact_checkpoint_state(as_of=state.as_of)
            restored_ledger_state_id = current_paper_ledger_state_id(ledger)
    except (TypeError, ValueError, ArithmeticError) as error:
        raise CompactPaperLedgerRestorationError(
            "restored ledger could not be reconciled"
        ) from error
    if (
        reconstructed != state
        or ledger.cash != state.cash
        or ledger.realized_profit_loss != state.realized_profit_loss
        or ledger.fills
        or not ledger.is_compact_restored
    ):
        raise CompactPaperLedgerRestorationError(
            "restored ledger differs from exact compact state"
        )
    return ledger, CompactPaperLedgerRestorationEvidence(
        state.compact_state_id,
        restored_ledger_state_id,
        CompactPaperLedgerReconciliationStatus.PASS,
    )
