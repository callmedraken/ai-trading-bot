"""Immutable schema-1 GENESIS paper-account checkpoints and offline proof."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid5

from trading_bot.domain import Symbol
from trading_bot.execution import OrderEngine, current_order_engine_state_id
from trading_bot.ledger import (
    MAX_COMPACT_PAPER_LEDGER_POSITIONS,
    CompactPaperLedgerPosition,
    CompactPaperLedgerRestorationEvidence,
    CompactPaperLedgerState,
    PaperLedger,
    derive_compact_paper_ledger_average_cost,
    restore_paper_ledger_from_compact_state,
)
from trading_bot.market_data.daily_snapshot_identity import (
    canonical_decimal,
    canonical_timestamp,
)
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime.exceptions import (
    InvalidPaperAccountCheckpointRequestError,
    PaperAccountCheckpointReconciliationError,
    PaperAccountCheckpointReplayError,
    PaperAccountCheckpointSchemaError,
    PaperAccountCheckpointSyntaxError,
    PaperAccountCheckpointVerificationError,
)

PAPER_ACCOUNT_CHECKPOINT_SCHEMA_VERSION = 1
PAPER_ACCOUNT_CHECKPOINT_ACCOUNT_STATE_MATERIAL_VERSION = (
    "paper-account-checkpoint-account-state-v1"
)
PAPER_ACCOUNT_CHECKPOINT_LINEAGE_MATERIAL_VERSION = (
    "paper-account-checkpoint-genesis-lineage-v1"
)
PAPER_ACCOUNT_CHECKPOINT_MATERIAL_VERSION = "paper-account-checkpoint-v1"
PAPER_ACCOUNT_CHECKPOINT_ACCOUNT_STATE_NAMESPACE = UUID(
    "5b1b7f21-2711-5944-9356-505731409380"
)
PAPER_ACCOUNT_CHECKPOINT_LINEAGE_NAMESPACE = UUID(
    "779d7a43-8e72-54ea-a12c-e6db102093aa"
)
PAPER_ACCOUNT_CHECKPOINT_NAMESPACE = UUID("44dc8ade-819a-5865-92f8-a5a0f10c82ee")
MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES = 1024 * 1024
MAX_PAPER_ACCOUNT_CHECKPOINT_METADATA = 100
MAX_PAPER_ACCOUNT_CHECKPOINT_METADATA_KEY_CHARACTERS = 128
MAX_PAPER_ACCOUNT_CHECKPOINT_METADATA_VALUE_CHARACTERS = 4096
MAX_PAPER_ACCOUNT_CHECKPOINT_DECIMAL_CHARACTERS = 4096

_ROOT_FIELDS = frozenset({"checkpoint", "schema_version"})
_CHECKPOINT_FIELDS = frozenset(
    {
        "account_state",
        "checkpoint_id",
        "empty_engine_state_id",
        "kind",
        "lineage_id",
        "metadata",
        "prior_checkpoint",
        "producing_cycle",
        "sequence",
    }
)
_ACCOUNT_STATE_FIELDS = frozenset(
    {
        "account_state_id",
        "as_of",
        "cash",
        "compact_ledger_state_id",
        "positions",
        "realized_profit_loss",
    }
)
_POSITION_FIELDS = frozenset({"average_cost", "quantity", "symbol", "total_cost_basis"})
_METADATA_FIELDS = frozenset({"key", "value"})
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{6})?Z$"
)
_RESERVED_METADATA_PREFIXES = ("checkpoint.", "lineage.", "application.")


class PaperAccountCheckpointKind(StrEnum):
    """Checkpoint kinds currently supported by the immutable schema."""

    GENESIS = "GENESIS"


class PaperAccountCheckpointVerificationStatus(StrEnum):
    """Outcome of offline genesis checkpoint verification."""

    PASS = "PASS"
    FAIL = "FAIL"


class PaperAccountCheckpointVerificationCode(StrEnum):
    """Stable, ordered offline-verification classifications."""

    CHECKPOINT_BYTE_LENGTH_MISMATCH = "CHECKPOINT_BYTE_LENGTH_MISMATCH"
    CHECKPOINT_SHA256_MISMATCH = "CHECKPOINT_SHA256_MISMATCH"
    CHECKPOINT_SYNTAX_FAILURE = "CHECKPOINT_SYNTAX_FAILURE"
    STRICT_SCHEMA_CANONICALIZATION_FAILURE = "STRICT_SCHEMA_CANONICALIZATION_FAILURE"
    IDENTITY_RECONCILIATION_FAILURE = "IDENTITY_RECONCILIATION_FAILURE"
    RESTORATION_RECONCILIATION_FAILURE = "RESTORATION_RECONCILIATION_FAILURE"


def _framed(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(item.encode('utf-8'))}:{item}" for item in parts)


def _utc(value: object, name: str, error_type: type[ValueError]) -> datetime:
    if type(value) is not datetime:
        raise error_type(f"{name} must be an exact datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise error_type(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _metadata(value: object, error_type: type[ValueError]) -> tuple[MetadataEntry, ...]:
    try:
        entries = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise error_type("metadata must be iterable") from error
    if len(entries) > MAX_PAPER_ACCOUNT_CHECKPOINT_METADATA:
        raise error_type("metadata exceeds the schema bound")
    if any(type(entry) is not MetadataEntry for entry in entries):
        raise error_type("metadata must contain exact MetadataEntry values")
    keys = tuple(entry.key for entry in entries)
    if len(set(keys)) != len(keys):
        raise error_type("metadata keys must be unique")
    for entry in entries:
        if (
            len(entry.key) > MAX_PAPER_ACCOUNT_CHECKPOINT_METADATA_KEY_CHARACTERS
            or len(entry.value) > MAX_PAPER_ACCOUNT_CHECKPOINT_METADATA_VALUE_CHARACTERS
        ):
            raise error_type("metadata text exceeds the schema bound")
        if entry.key.startswith(_RESERVED_METADATA_PREFIXES):
            raise error_type("metadata key uses a reserved checkpoint prefix")
    return entries


def _checkpoint_positions(
    value: object, error_type: type[ValueError]
) -> tuple[PaperAccountCheckpointPosition, ...]:
    try:
        positions = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise error_type("positions must be iterable") from error
    if len(positions) > MAX_COMPACT_PAPER_LEDGER_POSITIONS:
        raise error_type("positions exceed the schema bound")
    if any(
        type(position) is not PaperAccountCheckpointPosition for position in positions
    ):
        raise error_type(
            "positions must contain exact PaperAccountCheckpointPosition values"
        )
    if len({position.symbol for position in positions}) != len(positions):
        raise error_type("position symbols must be unique")
    return positions


def _compact_positions(
    positions: tuple[PaperAccountCheckpointPosition, ...],
) -> tuple[CompactPaperLedgerPosition, ...]:
    return tuple(
        CompactPaperLedgerPosition(
            position.symbol,
            position.quantity,
            position.total_cost_basis,
            position.average_cost,
        )
        for position in positions
    )


def _account_state_id(
    as_of: datetime,
    cash: Decimal,
    positions: tuple[PaperAccountCheckpointPosition, ...],
    realized_profit_loss: Decimal,
) -> UUID:
    parts = [
        PAPER_ACCOUNT_CHECKPOINT_ACCOUNT_STATE_MATERIAL_VERSION,
        canonical_timestamp(as_of),
        canonical_decimal(cash),
        canonical_decimal(realized_profit_loss),
        str(len(positions)),
    ]
    for ordinal, position in enumerate(positions):
        parts.extend(
            (
                str(ordinal),
                str(position.symbol),
                canonical_decimal(position.quantity),
                canonical_decimal(position.total_cost_basis),
                canonical_decimal(position.average_cost),
            )
        )
    return uuid5(
        PAPER_ACCOUNT_CHECKPOINT_ACCOUNT_STATE_NAMESPACE, _framed(tuple(parts))
    )


def _lineage_id(account_state_id: UUID, metadata: tuple[MetadataEntry, ...]) -> UUID:
    parts = [
        PAPER_ACCOUNT_CHECKPOINT_LINEAGE_MATERIAL_VERSION,
        PaperAccountCheckpointKind.GENESIS.value,
        str(account_state_id),
        str(len(metadata)),
    ]
    for ordinal, entry in enumerate(metadata):
        parts.extend((str(ordinal), entry.key, entry.value))
    return uuid5(PAPER_ACCOUNT_CHECKPOINT_LINEAGE_NAMESPACE, _framed(tuple(parts)))


def _empty_engine_state_id() -> UUID:
    return current_order_engine_state_id(OrderEngine())


def _checkpoint_id(
    account_state: PaperAccountCheckpointAccountState,
    empty_engine_state_id: UUID,
    lineage_id: UUID,
    metadata: tuple[MetadataEntry, ...],
) -> UUID:
    parts = [
        PAPER_ACCOUNT_CHECKPOINT_MATERIAL_VERSION,
        PaperAccountCheckpointKind.GENESIS.value,
        "0",
        str(account_state.account_state_id),
        str(account_state.compact_ledger_state_id),
        str(empty_engine_state_id),
        str(lineage_id),
        str(len(metadata)),
    ]
    for ordinal, entry in enumerate(metadata):
        parts.extend((str(ordinal), entry.key, entry.value))
    return uuid5(PAPER_ACCOUNT_CHECKPOINT_NAMESPACE, _framed(tuple(parts)))


@dataclass(frozen=True, slots=True)
class PaperAccountCheckpointPosition:
    """One ordered exact position with authoritative total cost basis."""

    symbol: Symbol
    quantity: Decimal
    total_cost_basis: Decimal
    average_cost: Decimal

    def __post_init__(self) -> None:
        try:
            compact = CompactPaperLedgerPosition(
                self.symbol,
                self.quantity,
                self.total_cost_basis,
                self.average_cost,
            )
        except (TypeError, ValueError) as error:
            raise InvalidPaperAccountCheckpointRequestError(str(error)) from error
        object.__setattr__(self, "symbol", compact.symbol)
        object.__setattr__(self, "quantity", compact.quantity)
        object.__setattr__(self, "total_cost_basis", compact.total_cost_basis)
        object.__setattr__(self, "average_cost", compact.average_cost)

    @classmethod
    def from_exact_basis(
        cls,
        symbol: Symbol,
        quantity: Decimal,
        total_cost_basis: Decimal,
    ) -> PaperAccountCheckpointPosition:
        """Create a position using the existing compact-ledger Decimal policy."""
        try:
            average_cost = derive_compact_paper_ledger_average_cost(
                quantity, total_cost_basis
            )
        except (TypeError, ValueError) as error:
            raise InvalidPaperAccountCheckpointRequestError(str(error)) from error
        return cls(symbol, quantity, total_cost_basis, average_cost)


@dataclass(frozen=True, slots=True)
class PaperAccountGenesisRequest:
    """Explicit caller assertion; no broker or historical evidence is retained."""

    as_of: datetime
    cash: Decimal
    positions: tuple[PaperAccountCheckpointPosition, ...]
    realized_profit_loss: Decimal
    metadata: tuple[MetadataEntry, ...] = ()
    open_orders: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        positions = _checkpoint_positions(
            self.positions, InvalidPaperAccountCheckpointRequestError
        )
        try:
            compact = CompactPaperLedgerState.create(
                as_of=_utc(
                    self.as_of,
                    "as_of",
                    InvalidPaperAccountCheckpointRequestError,
                ),
                cash=self.cash,
                positions=_compact_positions(positions),
                realized_profit_loss=self.realized_profit_loss,
            )
        except (TypeError, ValueError) as error:
            raise InvalidPaperAccountCheckpointRequestError(str(error)) from error
        object.__setattr__(self, "as_of", compact.as_of)
        object.__setattr__(self, "cash", compact.cash)
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "realized_profit_loss", compact.realized_profit_loss)
        object.__setattr__(
            self,
            "metadata",
            _metadata(self.metadata, InvalidPaperAccountCheckpointRequestError),
        )
        try:
            open_orders = tuple(self.open_orders)
        except TypeError as error:
            raise InvalidPaperAccountCheckpointRequestError(
                "open_orders must be iterable"
            ) from error
        if open_orders:
            raise InvalidPaperAccountCheckpointRequestError(
                "GENESIS checkpoints cannot retain open orders"
            )
        object.__setattr__(self, "open_orders", ())


@dataclass(frozen=True, slots=True)
class PaperAccountCheckpointAccountState:
    """Exact retained account state and independent account/compact identities."""

    account_state_id: UUID
    compact_ledger_state_id: UUID
    as_of: datetime
    cash: Decimal
    positions: tuple[PaperAccountCheckpointPosition, ...]
    realized_profit_loss: Decimal

    def __post_init__(self) -> None:
        if (
            type(self.account_state_id) is not UUID
            or type(self.compact_ledger_state_id) is not UUID
        ):
            raise PaperAccountCheckpointReconciliationError(
                "account state identities must be exact UUIDs"
            )
        positions = _checkpoint_positions(
            self.positions, PaperAccountCheckpointReconciliationError
        )
        try:
            compact = CompactPaperLedgerState.create(
                as_of=_utc(
                    self.as_of,
                    "as_of",
                    PaperAccountCheckpointReconciliationError,
                ),
                cash=self.cash,
                positions=_compact_positions(positions),
                realized_profit_loss=self.realized_profit_loss,
            )
        except (TypeError, ValueError) as error:
            raise PaperAccountCheckpointReconciliationError(str(error)) from error
        expected_account_id = _account_state_id(
            compact.as_of, compact.cash, positions, compact.realized_profit_loss
        )
        if self.account_state_id != expected_account_id:
            raise PaperAccountCheckpointReconciliationError(
                "account_state_id does not match canonical account state"
            )
        if self.compact_ledger_state_id != compact.compact_state_id:
            raise PaperAccountCheckpointReconciliationError(
                "compact_ledger_state_id does not match canonical compact state"
            )
        object.__setattr__(self, "as_of", compact.as_of)
        object.__setattr__(self, "cash", compact.cash)
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "realized_profit_loss", compact.realized_profit_loss)

    @classmethod
    def from_genesis_request(
        cls, request: PaperAccountGenesisRequest
    ) -> PaperAccountCheckpointAccountState:
        """Derive exact state identities from a validated opening assertion."""
        if type(request) is not PaperAccountGenesisRequest:
            raise TypeError("request must be an exact PaperAccountGenesisRequest")
        compact = CompactPaperLedgerState.create(
            as_of=request.as_of,
            cash=request.cash,
            positions=_compact_positions(request.positions),
            realized_profit_loss=request.realized_profit_loss,
        )
        return cls(
            _account_state_id(
                compact.as_of,
                compact.cash,
                request.positions,
                compact.realized_profit_loss,
            ),
            compact.compact_state_id,
            compact.as_of,
            compact.cash,
            request.positions,
            compact.realized_profit_loss,
        )

    def compact_state(self) -> CompactPaperLedgerState:
        """Reconstruct only exact compact state, never historical executions."""
        return CompactPaperLedgerState(
            self.compact_ledger_state_id,
            self.as_of,
            self.cash,
            _compact_positions(self.positions),
            self.realized_profit_loss,
        )


@dataclass(frozen=True, slots=True)
class PaperAccountCheckpointReference:
    """Artifact evidence intentionally excluded from checkpoint domain identity."""

    checkpoint_id: UUID
    sequence: int
    artifact_sha256: str
    artifact_byte_length: int

    def __post_init__(self) -> None:
        if type(self.checkpoint_id) is not UUID:
            raise InvalidPaperAccountCheckpointRequestError(
                "checkpoint_id must be an exact UUID"
            )
        if type(self.sequence) is not int or self.sequence != 0:
            raise InvalidPaperAccountCheckpointRequestError(
                "GENESIS checkpoint sequence must be zero"
            )
        if (
            type(self.artifact_sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.artifact_sha256) is None
        ):
            raise InvalidPaperAccountCheckpointRequestError(
                "artifact_sha256 must be lowercase SHA-256 text"
            )
        if type(self.artifact_byte_length) is not int or self.artifact_byte_length < 0:
            raise InvalidPaperAccountCheckpointRequestError(
                "artifact_byte_length must be a nonnegative integer"
            )


@dataclass(frozen=True, slots=True)
class PaperAccountCheckpoint:
    """One immutable GENESIS checkpoint; successors and lineage edges are absent."""

    checkpoint_id: UUID
    kind: PaperAccountCheckpointKind
    sequence: int
    account_state: PaperAccountCheckpointAccountState
    empty_engine_state_id: UUID
    lineage_id: UUID
    metadata: tuple[MetadataEntry, ...] = ()
    prior_checkpoint: None = None
    producing_cycle: None = None

    def __post_init__(self) -> None:
        if (
            type(self.checkpoint_id) is not UUID
            or type(self.empty_engine_state_id) is not UUID
            or type(self.lineage_id) is not UUID
        ):
            raise PaperAccountCheckpointReconciliationError(
                "checkpoint identities must be exact UUIDs"
            )
        if self.kind is not PaperAccountCheckpointKind.GENESIS:
            raise PaperAccountCheckpointReconciliationError(
                "schema 1 supports GENESIS checkpoints only"
            )
        if type(self.sequence) is not int or self.sequence != 0:
            raise PaperAccountCheckpointReconciliationError(
                "GENESIS checkpoint sequence must be zero"
            )
        if type(self.account_state) is not PaperAccountCheckpointAccountState:
            raise PaperAccountCheckpointReconciliationError(
                "account_state must be exact"
            )
        if self.prior_checkpoint is not None or self.producing_cycle is not None:
            raise PaperAccountCheckpointReconciliationError(
                "GENESIS has no prior or producing references"
            )
        metadata = _metadata(self.metadata, PaperAccountCheckpointReconciliationError)
        expected_engine_id = _empty_engine_state_id()
        if self.empty_engine_state_id != expected_engine_id:
            raise PaperAccountCheckpointReconciliationError(
                "empty_engine_state_id is not canonical"
            )
        expected_lineage_id = _lineage_id(self.account_state.account_state_id, metadata)
        if self.lineage_id != expected_lineage_id:
            raise PaperAccountCheckpointReconciliationError(
                "lineage_id does not match canonical genesis lineage"
            )
        expected_checkpoint_id = _checkpoint_id(
            self.account_state,
            self.empty_engine_state_id,
            self.lineage_id,
            metadata,
        )
        if self.checkpoint_id != expected_checkpoint_id:
            raise PaperAccountCheckpointReconciliationError(
                "checkpoint_id does not match canonical checkpoint"
            )
        object.__setattr__(self, "metadata", metadata)

    @property
    def compact_ledger_state_id(self) -> UUID:
        """Return the separately namespaced compact-ledger fingerprint."""
        return self.account_state.compact_ledger_state_id


@dataclass(frozen=True, slots=True)
class PaperAccountCheckpointVerificationDiagnostic:
    """One non-identity explanation for a deterministic verification failure."""

    code: PaperAccountCheckpointVerificationCode
    detail: str

    def __post_init__(self) -> None:
        if type(self.code) is not PaperAccountCheckpointVerificationCode:
            raise PaperAccountCheckpointVerificationError(
                "verification diagnostic code is invalid"
            )
        if type(self.detail) is not str or not self.detail:
            raise PaperAccountCheckpointVerificationError(
                "verification diagnostic detail must be nonblank"
            )


@dataclass(frozen=True, slots=True)
class PaperAccountCheckpointVerificationResult:
    """PASS-only reconstructed state, or immutable offline failure evidence."""

    status: PaperAccountCheckpointVerificationStatus
    checkpoint_byte_length: int
    checkpoint_sha256: str
    checkpoint: PaperAccountCheckpoint | None
    restored_ledger: PaperLedger | None
    restoration_evidence: CompactPaperLedgerRestorationEvidence | None
    diagnostics: tuple[PaperAccountCheckpointVerificationDiagnostic, ...]

    def __post_init__(self) -> None:
        if type(self.status) is not PaperAccountCheckpointVerificationStatus:
            raise PaperAccountCheckpointVerificationError(
                "verification status is invalid"
            )
        if (
            type(self.checkpoint_byte_length) is not int
            or self.checkpoint_byte_length < 0
        ):
            raise PaperAccountCheckpointVerificationError(
                "checkpoint_byte_length is invalid"
            )
        if (
            type(self.checkpoint_sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.checkpoint_sha256) is None
        ):
            raise PaperAccountCheckpointVerificationError(
                "checkpoint_sha256 is invalid"
            )
        if any(
            type(item) is not PaperAccountCheckpointVerificationDiagnostic
            for item in self.diagnostics
        ):
            raise PaperAccountCheckpointVerificationError(
                "verification diagnostics are invalid"
            )
        pass_result = self.status is PaperAccountCheckpointVerificationStatus.PASS
        complete = (
            type(self.checkpoint) is PaperAccountCheckpoint
            and type(self.restored_ledger) is PaperLedger
            and type(self.restoration_evidence) is CompactPaperLedgerRestorationEvidence
        )
        if pass_result and (not complete or self.diagnostics):
            raise PaperAccountCheckpointVerificationError(
                "PASS result requires reconstructed checkpoint and ledger only"
            )
        if not pass_result and (complete or not self.diagnostics):
            raise PaperAccountCheckpointVerificationError(
                "FAIL result cannot expose reconstructed state"
            )


def create_genesis_paper_account_checkpoint(
    request: PaperAccountGenesisRequest,
) -> PaperAccountCheckpoint:
    """Create deterministic history-free GENESIS state from caller assertion."""
    if type(request) is not PaperAccountGenesisRequest:
        raise TypeError("request must be an exact PaperAccountGenesisRequest")
    account_state = PaperAccountCheckpointAccountState.from_genesis_request(request)
    engine_id = _empty_engine_state_id()
    lineage_id = _lineage_id(account_state.account_state_id, request.metadata)
    return PaperAccountCheckpoint(
        _checkpoint_id(account_state, engine_id, lineage_id, request.metadata),
        PaperAccountCheckpointKind.GENESIS,
        0,
        account_state,
        engine_id,
        lineage_id,
        request.metadata,
    )


def serialize_paper_account_checkpoint(checkpoint: PaperAccountCheckpoint) -> bytes:
    """Render schema-1 checkpoint data as canonical compact ASCII JSON bytes."""
    if type(checkpoint) is not PaperAccountCheckpoint:
        raise TypeError("checkpoint must be an exact PaperAccountCheckpoint")
    state = checkpoint.account_state
    tree = {
        "schema_version": PAPER_ACCOUNT_CHECKPOINT_SCHEMA_VERSION,
        "checkpoint": {
            "checkpoint_id": str(checkpoint.checkpoint_id),
            "kind": checkpoint.kind.value,
            "sequence": checkpoint.sequence,
            "account_state": {
                "account_state_id": str(state.account_state_id),
                "compact_ledger_state_id": str(state.compact_ledger_state_id),
                "as_of": canonical_timestamp(state.as_of),
                "cash": canonical_decimal(state.cash),
                "positions": [
                    {
                        "symbol": str(position.symbol),
                        "quantity": canonical_decimal(position.quantity),
                        "total_cost_basis": canonical_decimal(
                            position.total_cost_basis
                        ),
                        "average_cost": canonical_decimal(position.average_cost),
                    }
                    for position in state.positions
                ],
                "realized_profit_loss": canonical_decimal(state.realized_profit_loss),
            },
            "empty_engine_state_id": str(checkpoint.empty_engine_state_id),
            "lineage_id": str(checkpoint.lineage_id),
            "metadata": [
                {"key": entry.key, "value": entry.value}
                for entry in checkpoint.metadata
            ],
            "prior_checkpoint": None,
            "producing_cycle": None,
        },
    }
    try:
        rendered = json.dumps(
            tree,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeError) as error:
        raise PaperAccountCheckpointSchemaError(
            "checkpoint cannot be rendered as canonical JSON"
        ) from error
    payload = (rendered + "\n").encode("utf-8")
    if len(payload) > MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES:
        raise PaperAccountCheckpointSchemaError(
            "checkpoint exceeds the schema byte bound"
        )
    return payload


def _strict_object(
    value: object, fields: frozenset[str], path: str
) -> dict[str, object]:
    if type(value) is not dict:
        raise PaperAccountCheckpointSchemaError(f"{path}: expected object")
    if set(value) != fields:
        raise PaperAccountCheckpointSchemaError(f"{path}: fields do not match schema")
    return value


def _strict_list(value: object, path: str, maximum: int) -> list[object]:
    if type(value) is not list:
        raise PaperAccountCheckpointSchemaError(f"{path}: expected array")
    if len(value) > maximum:
        raise PaperAccountCheckpointSchemaError(f"{path}: array exceeds schema bound")
    return value


def _strict_string(value: object, path: str, maximum: int) -> str:
    if type(value) is not str:
        raise PaperAccountCheckpointSchemaError(f"{path}: expected string")
    if len(value) > maximum:
        raise PaperAccountCheckpointSchemaError(f"{path}: string exceeds schema bound")
    return value


def _strict_uuid(value: object, path: str) -> UUID:
    text = _strict_string(value, path, 36)
    try:
        parsed = UUID(text)
    except (TypeError, ValueError, AttributeError) as error:
        raise PaperAccountCheckpointSchemaError(
            f"{path}: expected canonical UUID"
        ) from error
    if str(parsed) != text:
        raise PaperAccountCheckpointSchemaError(f"{path}: UUID is not canonical")
    return parsed


def _strict_decimal(value: object, path: str) -> Decimal:
    text = _strict_string(value, path, MAX_PAPER_ACCOUNT_CHECKPOINT_DECIMAL_CHARACTERS)
    try:
        parsed = Decimal(text)
    except InvalidOperation as error:
        raise PaperAccountCheckpointSchemaError(f"{path}: invalid Decimal") from error
    if not parsed.is_finite() or canonical_decimal(parsed) != text:
        raise PaperAccountCheckpointSchemaError(
            f"{path}: expected exponent-free canonical Decimal"
        )
    return parsed


def _strict_timestamp(value: object, path: str) -> datetime:
    text = _strict_string(value, path, 27)
    if _TIMESTAMP_PATTERN.fullmatch(text) is None:
        raise PaperAccountCheckpointSchemaError(
            f"{path}: expected canonical UTC timestamp"
        )
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00").astimezone(UTC)
    except ValueError as error:
        raise PaperAccountCheckpointSchemaError(
            f"{path}: invalid UTC timestamp"
        ) from error
    if canonical_timestamp(parsed) != text:
        raise PaperAccountCheckpointSchemaError(f"{path}: timestamp is not canonical")
    return parsed


def _strict_symbol(value: object, path: str) -> Symbol:
    text = _strict_string(value, path, 10)
    try:
        symbol = Symbol(text)
    except (TypeError, ValueError) as error:
        raise PaperAccountCheckpointSchemaError(f"{path}: invalid symbol") from error
    if str(symbol) != text:
        raise PaperAccountCheckpointSchemaError(f"{path}: symbol is not canonical")
    return symbol


def _parse_checkpoint_tree(tree: object) -> PaperAccountCheckpoint:
    root = _strict_object(tree, _ROOT_FIELDS, "root")
    if (
        type(root["schema_version"]) is not int
        or root["schema_version"] != PAPER_ACCOUNT_CHECKPOINT_SCHEMA_VERSION
    ):
        raise PaperAccountCheckpointSchemaError(
            "root.schema_version: unsupported schema version"
        )
    raw = _strict_object(root["checkpoint"], _CHECKPOINT_FIELDS, "checkpoint")
    if raw["kind"] != PaperAccountCheckpointKind.GENESIS.value:
        raise PaperAccountCheckpointSchemaError(
            "checkpoint.kind: schema 1 supports GENESIS only"
        )
    if type(raw["sequence"]) is not int or raw["sequence"] != 0:
        raise PaperAccountCheckpointSchemaError(
            "checkpoint.sequence: GENESIS sequence must be zero"
        )
    if raw["prior_checkpoint"] is not None or raw["producing_cycle"] is not None:
        raise PaperAccountCheckpointSchemaError(
            "checkpoint: GENESIS references must be absent"
        )
    state = _strict_object(
        raw["account_state"], _ACCOUNT_STATE_FIELDS, "checkpoint.account_state"
    )
    parsed_positions: list[PaperAccountCheckpointPosition] = []
    raw_positions = _strict_list(
        state["positions"],
        "checkpoint.account_state.positions",
        MAX_COMPACT_PAPER_LEDGER_POSITIONS,
    )
    for ordinal, raw_position in enumerate(raw_positions):
        path = f"checkpoint.account_state.positions[{ordinal}]"
        position = _strict_object(raw_position, _POSITION_FIELDS, path)
        try:
            parsed_positions.append(
                PaperAccountCheckpointPosition(
                    _strict_symbol(position["symbol"], f"{path}.symbol"),
                    _strict_decimal(position["quantity"], f"{path}.quantity"),
                    _strict_decimal(
                        position["total_cost_basis"], f"{path}.total_cost_basis"
                    ),
                    _strict_decimal(position["average_cost"], f"{path}.average_cost"),
                )
            )
        except (TypeError, ValueError) as error:
            raise PaperAccountCheckpointSchemaError(str(error)) from error
    parsed_metadata: list[MetadataEntry] = []
    raw_metadata = _strict_list(
        raw["metadata"], "checkpoint.metadata", MAX_PAPER_ACCOUNT_CHECKPOINT_METADATA
    )
    for ordinal, raw_entry in enumerate(raw_metadata):
        path = f"checkpoint.metadata[{ordinal}]"
        entry = _strict_object(raw_entry, _METADATA_FIELDS, path)
        try:
            parsed_metadata.append(
                MetadataEntry(
                    _strict_string(
                        entry["key"],
                        f"{path}.key",
                        MAX_PAPER_ACCOUNT_CHECKPOINT_METADATA_KEY_CHARACTERS,
                    ),
                    _strict_string(
                        entry["value"],
                        f"{path}.value",
                        MAX_PAPER_ACCOUNT_CHECKPOINT_METADATA_VALUE_CHARACTERS,
                    ),
                )
            )
        except (TypeError, ValueError) as error:
            raise PaperAccountCheckpointSchemaError(str(error)) from error
    try:
        parsed_state = PaperAccountCheckpointAccountState(
            _strict_uuid(
                state["account_state_id"], "checkpoint.account_state.account_state_id"
            ),
            _strict_uuid(
                state["compact_ledger_state_id"],
                "checkpoint.account_state.compact_ledger_state_id",
            ),
            _strict_timestamp(state["as_of"], "checkpoint.account_state.as_of"),
            _strict_decimal(state["cash"], "checkpoint.account_state.cash"),
            tuple(parsed_positions),
            _strict_decimal(
                state["realized_profit_loss"],
                "checkpoint.account_state.realized_profit_loss",
            ),
        )
        return PaperAccountCheckpoint(
            _strict_uuid(raw["checkpoint_id"], "checkpoint.checkpoint_id"),
            PaperAccountCheckpointKind.GENESIS,
            0,
            parsed_state,
            _strict_uuid(
                raw["empty_engine_state_id"], "checkpoint.empty_engine_state_id"
            ),
            _strict_uuid(raw["lineage_id"], "checkpoint.lineage_id"),
            tuple(parsed_metadata),
        )
    except (TypeError, ValueError) as error:
        raise PaperAccountCheckpointSchemaError(str(error)) from error


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PaperAccountCheckpointSchemaError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_float(value: str) -> None:
    raise PaperAccountCheckpointSchemaError(
        f"JSON floating-point number is not permitted: {value}"
    )


def _reject_constant(value: str) -> None:
    raise PaperAccountCheckpointSchemaError(
        f"nonstandard JSON constant is not permitted: {value}"
    )


def parse_paper_account_checkpoint(payload: bytes) -> PaperAccountCheckpoint:
    """Strictly parse only byte-for-byte canonical schema-1 checkpoint JSON."""
    if type(payload) is not bytes:
        raise TypeError("payload must be exact bytes")
    if not payload or len(payload) > MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES:
        raise PaperAccountCheckpointSyntaxError(
            "checkpoint bytes are empty or exceed the schema bound"
        )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise PaperAccountCheckpointSyntaxError(
            "checkpoint JSON must not contain a UTF-8 BOM"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PaperAccountCheckpointSyntaxError(
            "checkpoint JSON must be UTF-8"
        ) from error
    try:
        tree: Any = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, PaperAccountCheckpointSchemaError) as error:
        raise PaperAccountCheckpointSyntaxError(
            "checkpoint JSON is not strict canonical JSON"
        ) from error
    checkpoint = _parse_checkpoint_tree(tree)
    if serialize_paper_account_checkpoint(checkpoint) != payload:
        raise PaperAccountCheckpointSchemaError(
            "checkpoint bytes are not canonical schema-1 JSON"
        )
    return checkpoint


def _diagnostic(
    code: PaperAccountCheckpointVerificationCode, detail: str
) -> PaperAccountCheckpointVerificationDiagnostic:
    return PaperAccountCheckpointVerificationDiagnostic(code, detail)


def _failed(
    length: int,
    digest: str,
    diagnostics: list[PaperAccountCheckpointVerificationDiagnostic],
) -> PaperAccountCheckpointVerificationResult:
    return PaperAccountCheckpointVerificationResult(
        PaperAccountCheckpointVerificationStatus.FAIL,
        length,
        digest,
        None,
        None,
        None,
        tuple(diagnostics),
    )


def verify_genesis_paper_account_checkpoint(
    payload: bytes,
    *,
    expected_checkpoint_sha256: str | None = None,
    expected_checkpoint_byte_length: int | None = None,
) -> PaperAccountCheckpointVerificationResult:
    """Offline-only parse, identity proof, restoration, and byte reconciliation."""
    if type(payload) is not bytes:
        raise TypeError("payload must be exact bytes")
    if expected_checkpoint_sha256 is not None and (
        type(expected_checkpoint_sha256) is not str
        or _SHA256_PATTERN.fullmatch(expected_checkpoint_sha256) is None
    ):
        raise PaperAccountCheckpointVerificationError(
            "expected_checkpoint_sha256 must be lowercase SHA-256 text or None"
        )
    if expected_checkpoint_byte_length is not None and (
        type(expected_checkpoint_byte_length) is not int
        or expected_checkpoint_byte_length < 0
    ):
        raise PaperAccountCheckpointVerificationError(
            "expected_checkpoint_byte_length must be a nonnegative integer or None"
        )
    length = len(payload)
    digest = sha256(payload).hexdigest()
    diagnostics: list[PaperAccountCheckpointVerificationDiagnostic] = []
    if (
        expected_checkpoint_byte_length is not None
        and expected_checkpoint_byte_length != length
    ):
        diagnostics.append(
            _diagnostic(
                PaperAccountCheckpointVerificationCode.CHECKPOINT_BYTE_LENGTH_MISMATCH,
                "checkpoint byte length differs from supplied artifact evidence",
            )
        )
    if expected_checkpoint_sha256 is not None and expected_checkpoint_sha256 != digest:
        diagnostics.append(
            _diagnostic(
                PaperAccountCheckpointVerificationCode.CHECKPOINT_SHA256_MISMATCH,
                "checkpoint SHA-256 differs from supplied artifact evidence",
            )
        )
    if diagnostics:
        return _failed(length, digest, diagnostics)
    try:
        checkpoint = parse_paper_account_checkpoint(payload)
    except PaperAccountCheckpointSyntaxError as error:
        return _failed(
            length,
            digest,
            [
                _diagnostic(
                    PaperAccountCheckpointVerificationCode.CHECKPOINT_SYNTAX_FAILURE,
                    str(error),
                )
            ],
        )
    except (
        PaperAccountCheckpointSchemaError,
        PaperAccountCheckpointReconciliationError,
    ) as error:
        return _failed(
            length,
            digest,
            [
                _diagnostic(
                    PaperAccountCheckpointVerificationCode.STRICT_SCHEMA_CANONICALIZATION_FAILURE,
                    str(error),
                )
            ],
        )
    try:
        rebuilt = create_genesis_paper_account_checkpoint(
            PaperAccountGenesisRequest(
                checkpoint.account_state.as_of,
                checkpoint.account_state.cash,
                checkpoint.account_state.positions,
                checkpoint.account_state.realized_profit_loss,
                checkpoint.metadata,
            )
        )
        if rebuilt != checkpoint:
            raise PaperAccountCheckpointReconciliationError(
                "recomputed checkpoint differs from retained checkpoint"
            )
    except (TypeError, ValueError) as error:
        return _failed(
            length,
            digest,
            [
                _diagnostic(
                    PaperAccountCheckpointVerificationCode.IDENTITY_RECONCILIATION_FAILURE,
                    str(error),
                )
            ],
        )
    try:
        expected_state = checkpoint.account_state.compact_state()
        ledger, evidence = restore_paper_ledger_from_compact_state(expected_state)
        restored = ledger.export_compact_checkpoint_state(
            as_of=checkpoint.account_state.as_of
        )
        if (
            restored != expected_state
            or ledger.fills
            or not ledger.is_compact_restored
            or serialize_paper_account_checkpoint(checkpoint) != payload
        ):
            raise PaperAccountCheckpointReconciliationError(
                "restored ledger or canonical bytes do not reconcile"
            )
    except (TypeError, ValueError, ArithmeticError) as error:
        return _failed(
            length,
            digest,
            [
                _diagnostic(
                    PaperAccountCheckpointVerificationCode.RESTORATION_RECONCILIATION_FAILURE,
                    str(error),
                )
            ],
        )
    return PaperAccountCheckpointVerificationResult(
        PaperAccountCheckpointVerificationStatus.PASS,
        length,
        digest,
        checkpoint,
        ledger,
        evidence,
        (),
    )


def replay_verified_genesis_paper_account_checkpoint(
    result: PaperAccountCheckpointVerificationResult,
) -> tuple[PaperAccountCheckpoint, PaperLedger, CompactPaperLedgerRestorationEvidence]:
    """Return reconstructed state only from a complete offline PASS result."""
    if type(result) is not PaperAccountCheckpointVerificationResult:
        raise TypeError(
            "result must be an exact PaperAccountCheckpointVerificationResult"
        )
    if result.status is not PaperAccountCheckpointVerificationStatus.PASS:
        raise PaperAccountCheckpointReplayError(
            "checkpoint replay requires a PASS verification result"
        )
    assert result.checkpoint is not None
    assert result.restored_ledger is not None
    assert result.restoration_evidence is not None
    return result.checkpoint, result.restored_ledger, result.restoration_evidence
