"""Immutable Qt-free presentation records for verified paper-account state."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum, StrEnum
from uuid import UUID

from trading_bot.ledger import (
    MAX_COMPACT_PAPER_LEDGER_POSITIONS,
    derive_compact_paper_ledger_average_cost,
)

MAX_PAPER_ACCOUNT_MESSAGE_CHARACTERS = 512
MAX_PAPER_ACCOUNT_SYMBOL_CHARACTERS = 10
MAX_PAPER_ACCOUNT_POSITIONS = MAX_COMPACT_PAPER_LEDGER_POSITIONS

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PaperAccountPageStatus(Enum):
    """Bounded availability state for the read-only Paper Account page."""

    VERIFIED = "verified"
    UNAVAILABLE = "unavailable"


class PaperAccountCheckpointKindView(StrEnum):
    """Closed checkpoint-kind vocabulary exposed by the GUI."""

    GENESIS = "GENESIS"
    CYCLE_SUCCESSOR = "CYCLE_SUCCESSOR"


def _require_message(value: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError("paper-account page message must be non-empty text")
    if len(value) > MAX_PAPER_ACCOUNT_MESSAGE_CHARACTERS:
        raise ValueError("paper-account page message exceeds the presentation bound")


def _require_uuid(value: UUID, field_name: str) -> None:
    if type(value) is not UUID:
        raise TypeError(f"{field_name} must be an exact UUID")


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if type(value) is not datetime:
        raise TypeError(f"{field_name} must be an exact datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_decimal(
    value: Decimal,
    field_name: str,
    *,
    positive: bool = False,
    nonnegative: bool = False,
) -> None:
    if type(value) is not Decimal:
        raise TypeError(f"{field_name} must be an exact Decimal")
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")
    if positive and value <= 0:
        raise ValueError(f"{field_name} must be positive")
    if nonnegative and value < 0:
        raise ValueError(f"{field_name} must be nonnegative")


def _require_sha256(value: str, field_name: str) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be lowercase SHA-256 text")


@dataclass(frozen=True, slots=True)
class PaperAccountPositionView:
    """One exact verified compact-ledger position for presentation."""

    symbol: str
    quantity: Decimal
    total_cost_basis: Decimal
    average_cost: Decimal

    def __post_init__(self) -> None:
        if type(self.symbol) is not str:
            raise TypeError("symbol must be an exact string")
        if (
            not self.symbol
            or self.symbol != self.symbol.strip()
            or len(self.symbol) > MAX_PAPER_ACCOUNT_SYMBOL_CHARACTERS
            or any(
                ord(character) < 0x21 or ord(character) > 0x7E
                for character in self.symbol
            )
        ):
            raise ValueError("symbol must be bounded printable ASCII text")

        _require_decimal(self.quantity, "quantity", positive=True)
        _require_decimal(self.total_cost_basis, "total_cost_basis", positive=True)
        _require_decimal(self.average_cost, "average_cost", positive=True)
        try:
            expected_average = derive_compact_paper_ledger_average_cost(
                self.quantity,
                self.total_cost_basis,
            )
        except (TypeError, ValueError, ArithmeticError) as error:
            raise ValueError("position accounting values are invalid") from error
        if self.average_cost != expected_average:
            raise ValueError(
                "average_cost does not match quantity and total_cost_basis"
            )


@dataclass(frozen=True, slots=True)
class VerifiedPaperAccountView:
    """Common account state from one complete reviewed checkpoint proof."""

    checkpoint_kind: PaperAccountCheckpointKindView
    sequence: int
    checkpoint_id: UUID
    lineage_id: UUID
    account_state_id: UUID
    compact_state_id: UUID
    as_of: datetime
    cash: Decimal
    realized_profit_loss: Decimal
    positions: tuple[PaperAccountPositionView, ...]
    artifact_sha256: str
    artifact_byte_length: int

    def __post_init__(self) -> None:
        if type(self.checkpoint_kind) is not PaperAccountCheckpointKindView:
            raise TypeError("checkpoint_kind must be a PaperAccountCheckpointKindView")
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("sequence must be a nonnegative exact integer")
        if (
            self.checkpoint_kind is PaperAccountCheckpointKindView.GENESIS
            and self.sequence != 0
        ):
            raise ValueError("GENESIS sequence must be zero")
        if (
            self.checkpoint_kind is PaperAccountCheckpointKindView.CYCLE_SUCCESSOR
            and self.sequence == 0
        ):
            raise ValueError("CYCLE_SUCCESSOR sequence must be positive")

        _require_uuid(self.checkpoint_id, "checkpoint_id")
        _require_uuid(self.lineage_id, "lineage_id")
        _require_uuid(self.account_state_id, "account_state_id")
        _require_uuid(self.compact_state_id, "compact_state_id")
        _require_aware_datetime(self.as_of, "as_of")
        _require_decimal(self.cash, "cash", nonnegative=True)
        _require_decimal(self.realized_profit_loss, "realized_profit_loss")

        try:
            positions = tuple(self.positions)
        except TypeError as error:
            raise TypeError("positions must be iterable") from error
        if len(positions) > MAX_PAPER_ACCOUNT_POSITIONS:
            raise ValueError("positions exceed the presentation count bound")
        if any(type(item) is not PaperAccountPositionView for item in positions):
            raise TypeError("positions must contain exact PaperAccountPositionView values")
        if len({item.symbol for item in positions}) != len(positions):
            raise ValueError("position symbols must be unique")

        _require_sha256(self.artifact_sha256, "artifact_sha256")
        if type(self.artifact_byte_length) is not int or self.artifact_byte_length < 0:
            raise ValueError("artifact_byte_length must be a nonnegative exact integer")
        object.__setattr__(self, "positions", positions)


@dataclass(frozen=True, slots=True)
class PaperAccountPageState:
    """One verified checkpoint account state or a bounded unavailable state."""

    status: PaperAccountPageStatus
    message: str
    account: VerifiedPaperAccountView | None

    def __post_init__(self) -> None:
        if type(self.status) is not PaperAccountPageStatus:
            raise TypeError("status must be a PaperAccountPageStatus")
        _require_message(self.message)
        if self.status is PaperAccountPageStatus.VERIFIED:
            if type(self.account) is not VerifiedPaperAccountView:
                raise ValueError("verified paper-account state requires one account")
        elif self.account is not None:
            raise ValueError("unavailable paper-account state must not contain an account")


def unavailable_paper_account_state() -> PaperAccountPageState:
    """Return the deterministic default with no verified checkpoint connected."""
    return PaperAccountPageState(
        status=PaperAccountPageStatus.UNAVAILABLE,
        message=(
            "No verified paper-account checkpoint is connected to this read-only GUI."
        ),
        account=None,
    )
