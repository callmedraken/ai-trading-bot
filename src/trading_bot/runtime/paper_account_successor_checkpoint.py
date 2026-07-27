"""Immutable successor checkpoints produced by checkpointed paper cycles."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
from uuid import UUID, uuid5

from trading_bot.execution import OrderEngine, current_order_engine_state_id
from trading_bot.ledger import (
    MAX_COMPACT_PAPER_LEDGER_POSITIONS,
    CompactPaperLedgerPosition,
    CompactPaperLedgerState,
    PaperLedger,
    restore_paper_ledger_from_compact_state,
)
from trading_bot.market_data import IdentifiedMarketCalendar, canonical_decimal
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    CheckpointedVerifiedSnapshotPaperCycleResult,
)
from trading_bot.runtime.exceptions import (
    SuccessorPaperAccountCheckpointReconciliationError,
    SuccessorPaperAccountCheckpointSchemaError,
    SuccessorPaperAccountCheckpointSyntaxError,
)
from trading_bot.runtime.verified_snapshot_preparation import (
    VerifiedDailySnapshotReference,
)

PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_SCHEMA_VERSION = 1
PAPER_ACCOUNT_SUCCESSOR_ACCOUNT_STATE_MATERIAL_VERSION = (
    "paper-account-successor-account-state-v1"
)
PAPER_ACCOUNT_SUCCESSOR_LINEAGE_MATERIAL_VERSION = "paper-account-successor-lineage-v1"
PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_MATERIAL_VERSION = (
    "paper-account-successor-checkpoint-v1"
)
PAPER_ACCOUNT_SUCCESSOR_ACCOUNT_STATE_NAMESPACE = UUID(
    "ad59d3e4-9e99-5416-9e33-49180f7d92f1"
)
PAPER_ACCOUNT_SUCCESSOR_LINEAGE_NAMESPACE = UUID("b7e4f9db-7cae-5479-bbe2-85c3e29614df")
PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_NAMESPACE = UUID(
    "52e04c7b-ff0e-50c1-a23a-3b319d970c51"
)
MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES = 1024 * 1024
MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_METADATA = 100
MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_METADATA_KEY_CHARACTERS = 128
MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_METADATA_VALUE_CHARACTERS = 4096
MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_DECIMAL_CHARACTERS = 4096
MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_INTEGER = (1 << 63) - 1

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{6})?Z$"
)
_ROOT_FIELDS = frozenset({"schema_version", "checkpoint"})
_CHECKPOINT_FIELDS = frozenset(
    {
        "checkpoint_id",
        "kind",
        "sequence",
        "account_state",
        "empty_engine_state_id",
        "lineage_id",
        "prior_lineage_id",
        "prior_checkpoint",
        "application_id",
        "producing_cycle",
        "snapshot_reference",
        "metadata",
    }
)
_ACCOUNT_STATE_FIELDS = frozenset(
    {
        "account_state_id",
        "compact_state_id",
        "as_of",
        "cash",
        "positions",
        "realized_profit_loss_before",
        "realized_profit_loss_after",
    }
)
_POSITION_FIELDS = frozenset({"symbol", "quantity", "total_cost_basis", "average_cost"})
_REFERENCE_FIELDS = frozenset(
    {"checkpoint_id", "sequence", "artifact_sha256", "artifact_byte_length"}
)
_REPORT_REFERENCE_FIELDS = frozenset(
    {"report_id", "cycle_result_id", "artifact_sha256", "artifact_byte_length"}
)
_SNAPSHOT_REFERENCE_FIELDS = frozenset(
    {"snapshot_id", "artifact_sha256", "artifact_byte_length"}
)
_METADATA_FIELDS = frozenset({"key", "value"})


class PaperAccountSuccessorCheckpointKind(StrEnum):
    """The only successor kind available in milestone 2D."""

    CYCLE_SUCCESSOR = "CYCLE_SUCCESSOR"


class PaperAccountCheckpointEdgeVerificationStatus(StrEnum):
    """Outcome of one complete verified predecessor-to-successor edge."""

    PASS = "PASS"
    FAIL = "FAIL"


class PaperAccountCheckpointEdgeVerificationCode(StrEnum):
    """Stable one-edge offline verification failure codes."""

    SUCCESSOR_BYTE_LENGTH_MISMATCH = "SUCCESSOR_BYTE_LENGTH_MISMATCH"
    SUCCESSOR_SHA256_MISMATCH = "SUCCESSOR_SHA256_MISMATCH"
    REPORT_REPLAY_FAILURE = "REPORT_REPLAY_FAILURE"
    SUCCESSOR_SYNTAX_FAILURE = "SUCCESSOR_SYNTAX_FAILURE"
    SUCCESSOR_SCHEMA_FAILURE = "SUCCESSOR_SCHEMA_FAILURE"
    EDGE_REFERENCE_MISMATCH = "EDGE_REFERENCE_MISMATCH"
    SUCCESSOR_RECONCILIATION_FAILURE = "SUCCESSOR_RECONCILIATION_FAILURE"


@dataclass(frozen=True, slots=True)
class PaperAccountCheckpointEdgeVerificationDiagnostic:
    """One non-identity explanation for a failed offline edge verification."""

    code: PaperAccountCheckpointEdgeVerificationCode
    detail: str

    def __post_init__(self) -> None:
        if type(self.code) is not PaperAccountCheckpointEdgeVerificationCode:
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "edge verification diagnostic code is invalid"
            )
        if type(self.detail) is not str or not self.detail.strip():
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "edge verification diagnostic detail is invalid"
            )


@dataclass(frozen=True, slots=True)
class PaperAccountCheckpointEdgeVerificationResult:
    """PASS-only reconstructed report result, successor, and restored ledger."""

    status: PaperAccountCheckpointEdgeVerificationStatus
    successor_byte_length: int
    successor_sha256: str
    cycle_result: CheckpointedVerifiedSnapshotPaperCycleResult | None
    successor_checkpoint: PaperAccountSuccessorCheckpoint | None
    restored_successor_ledger: PaperLedger | None
    diagnostics: tuple[PaperAccountCheckpointEdgeVerificationDiagnostic, ...]

    def __post_init__(self) -> None:
        if type(self.status) is not PaperAccountCheckpointEdgeVerificationStatus:
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "edge verification status is invalid"
            )
        if (
            type(self.successor_byte_length) is not int
            or self.successor_byte_length < 0
            or type(self.successor_sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.successor_sha256) is None
        ):
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "successor artifact evidence is invalid"
            )
        diagnostics = tuple(self.diagnostics)
        if any(
            type(item) is not PaperAccountCheckpointEdgeVerificationDiagnostic
            for item in diagnostics
        ):
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "edge verification diagnostics are invalid"
            )
        complete = (
            type(self.cycle_result) is CheckpointedVerifiedSnapshotPaperCycleResult
            and type(self.successor_checkpoint) is PaperAccountSuccessorCheckpoint
            and type(self.restored_successor_ledger) is PaperLedger
        )
        if self.status is PaperAccountCheckpointEdgeVerificationStatus.PASS:
            if not complete or diagnostics:
                raise SuccessorPaperAccountCheckpointReconciliationError(
                    "PASS must expose complete reconstructed edge evidence only"
                )
        elif complete or not diagnostics:
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "FAIL must not expose reconstructed edge evidence"
            )
        object.__setattr__(self, "diagnostics", diagnostics)


def _framed(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(item.encode('utf-8'))}:{item}" for item in parts)


def _metadata(value: object) -> tuple[MetadataEntry, ...]:
    try:
        items = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise SuccessorPaperAccountCheckpointReconciliationError(
            "metadata must be iterable"
        ) from error
    if (
        len(items) > MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_METADATA
        or any(type(item) is not MetadataEntry for item in items)
        or len({item.key for item in items}) != len(items)
        or any(
            len(item.key)
            > MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_METADATA_KEY_CHARACTERS
            or len(item.value)
            > MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_METADATA_VALUE_CHARACTERS
            for item in items
        )
    ):
        raise SuccessorPaperAccountCheckpointReconciliationError(
            "metadata does not meet successor checkpoint bounds"
        )
    return items


@dataclass(frozen=True, slots=True)
class PriorPaperAccountCheckpointReference:
    """Exact prior-checkpoint transport evidence outside financial identity."""

    checkpoint_id: UUID
    sequence: int
    artifact_sha256: str
    artifact_byte_length: int

    def __post_init__(self) -> None:
        if (
            type(self.checkpoint_id) is not UUID
            or type(self.sequence) is not int
            or self.sequence < 0
            or type(self.artifact_sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.artifact_sha256) is None
            or type(self.artifact_byte_length) is not int
            or self.artifact_byte_length < 0
        ):
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "prior checkpoint reference is invalid"
            )


@dataclass(frozen=True, slots=True)
class CheckpointedPaperCycleReportReference:
    """Canonical cycle-report transport evidence for one successor edge."""

    report_id: UUID
    cycle_result_id: UUID
    artifact_sha256: str
    artifact_byte_length: int

    def __post_init__(self) -> None:
        if (
            type(self.report_id) is not UUID
            or type(self.cycle_result_id) is not UUID
            or type(self.artifact_sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.artifact_sha256) is None
            or type(self.artifact_byte_length) is not int
            or self.artifact_byte_length < 1
        ):
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "producing report reference is invalid"
            )


@dataclass(frozen=True, slots=True)
class SuccessorPaperAccountState:
    """Exact final compact account state and retained cumulative P&L evidence."""

    account_state_id: UUID
    compact_state: CompactPaperLedgerState
    realized_profit_loss_before: Decimal

    def __post_init__(self) -> None:
        if type(self.account_state_id) is not UUID:
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "account_state_id must be an exact UUID"
            )
        if type(self.compact_state) is not CompactPaperLedgerState:
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "compact_state must be exact CompactPaperLedgerState"
            )
        if (
            type(self.realized_profit_loss_before) is not Decimal
            or not self.realized_profit_loss_before.is_finite()
        ):
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "realized_profit_loss_before must be an exact finite Decimal"
            )
        expected = _successor_account_state_id(
            self.compact_state,
            self.realized_profit_loss_before,
        )
        if self.account_state_id != expected:
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "account_state_id does not match canonical successor state"
            )

    @property
    def as_of(self) -> datetime:
        return self.compact_state.as_of

    @property
    def cash(self) -> Decimal:
        return self.compact_state.cash

    @property
    def positions(self) -> tuple[CompactPaperLedgerPosition, ...]:
        return self.compact_state.positions

    @property
    def realized_profit_loss_after(self) -> Decimal:
        return self.compact_state.realized_profit_loss


@dataclass(frozen=True, slots=True)
class PaperAccountSuccessorCheckpoint:
    """One immutable successor produced by exactly one checkpointed cycle."""

    checkpoint_id: UUID
    kind: PaperAccountSuccessorCheckpointKind
    sequence: int
    account_state: SuccessorPaperAccountState
    empty_engine_state_id: UUID
    lineage_id: UUID
    prior_lineage_id: UUID
    prior_checkpoint: PriorPaperAccountCheckpointReference
    application_id: UUID
    producing_cycle: CheckpointedPaperCycleReportReference
    snapshot_reference: VerifiedDailySnapshotReference
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "checkpoint_id",
            "empty_engine_state_id",
            "lineage_id",
            "prior_lineage_id",
            "application_id",
        ):
            if type(getattr(self, name)) is not UUID:
                raise SuccessorPaperAccountCheckpointReconciliationError(
                    f"{name} must be an exact UUID"
                )
        if self.kind is not PaperAccountSuccessorCheckpointKind.CYCLE_SUCCESSOR:
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "successor checkpoint kind is invalid"
            )
        if type(self.sequence) is not int or self.sequence <= 0:
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "successor sequence must be positive"
            )
        for name, expected in (
            ("account_state", SuccessorPaperAccountState),
            ("prior_checkpoint", PriorPaperAccountCheckpointReference),
            ("producing_cycle", CheckpointedPaperCycleReportReference),
            ("snapshot_reference", VerifiedDailySnapshotReference),
        ):
            if type(getattr(self, name)) is not expected:
                raise SuccessorPaperAccountCheckpointReconciliationError(
                    f"{name} has an invalid type"
                )
        metadata = _metadata(self.metadata)
        if self.sequence != self.prior_checkpoint.sequence + 1:
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "successor sequence must be prior sequence plus one"
            )
        expected_engine = current_order_engine_state_id(OrderEngine())
        if self.empty_engine_state_id != expected_engine:
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "successor checkpoint must retain the canonical empty engine"
            )
        expected_lineage = _successor_lineage_id(
            self.prior_lineage_id,
            self.prior_checkpoint.checkpoint_id,
            self.producing_cycle.cycle_result_id,
            self.sequence,
        )
        if self.lineage_id != expected_lineage:
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "successor lineage_id does not reconcile"
            )
        expected_checkpoint = _successor_checkpoint_id(
            self.account_state,
            self.empty_engine_state_id,
            self.lineage_id,
            self.prior_checkpoint,
            self.application_id,
            self.producing_cycle,
            self.snapshot_reference,
            metadata,
        )
        if self.checkpoint_id != expected_checkpoint:
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "successor checkpoint_id does not reconcile"
            )
        object.__setattr__(self, "metadata", metadata)


def _successor_account_state_id(
    compact_state: CompactPaperLedgerState,
    realized_before: Decimal,
) -> UUID:
    return uuid5(
        PAPER_ACCOUNT_SUCCESSOR_ACCOUNT_STATE_NAMESPACE,
        _framed(
            (
                PAPER_ACCOUNT_SUCCESSOR_ACCOUNT_STATE_MATERIAL_VERSION,
                str(compact_state.compact_state_id),
                canonical_decimal(realized_before),
                canonical_decimal(compact_state.realized_profit_loss),
            )
        ),
    )


def _successor_lineage_id(
    prior_lineage_id: UUID,
    prior_checkpoint_id: UUID,
    cycle_result_id: UUID,
    sequence: int,
) -> UUID:
    return uuid5(
        PAPER_ACCOUNT_SUCCESSOR_LINEAGE_NAMESPACE,
        _framed(
            (
                PAPER_ACCOUNT_SUCCESSOR_LINEAGE_MATERIAL_VERSION,
                str(prior_lineage_id),
                str(prior_checkpoint_id),
                str(cycle_result_id),
                str(sequence),
            )
        ),
    )


def derive_successor_paper_account_lineage_id(
    prior_lineage_id: UUID,
    prior_checkpoint_id: UUID,
    producing_cycle_result_id: UUID,
    successor_sequence: int,
) -> UUID:
    if (
        type(prior_lineage_id) is not UUID
        or type(prior_checkpoint_id) is not UUID
        or type(producing_cycle_result_id) is not UUID
        or type(successor_sequence) is not int
        or successor_sequence <= 0
    ):
        raise TypeError("successor lineage material is invalid")
    derived = _successor_lineage_id(
        prior_lineage_id,
        prior_checkpoint_id,
        producing_cycle_result_id,
        successor_sequence,
    )
    return derived


def _successor_checkpoint_id(
    account_state: SuccessorPaperAccountState,
    empty_engine_state_id: UUID,
    lineage_id: UUID,
    prior: PriorPaperAccountCheckpointReference,
    application_id: UUID,
    producing_cycle: CheckpointedPaperCycleReportReference,
    snapshot: VerifiedDailySnapshotReference,
    metadata: tuple[MetadataEntry, ...],
) -> UUID:
    parts = [
        PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_MATERIAL_VERSION,
        PaperAccountSuccessorCheckpointKind.CYCLE_SUCCESSOR.value,
        str(prior.sequence + 1),
        str(account_state.account_state_id),
        str(account_state.compact_state.compact_state_id),
        str(empty_engine_state_id),
        str(lineage_id),
        str(prior.checkpoint_id),
        str(application_id),
        str(producing_cycle.cycle_result_id),
        str(snapshot.snapshot_id),
        str(len(metadata)),
    ]
    for ordinal, entry in enumerate(metadata):
        parts.extend((str(ordinal), entry.key, entry.value))
    return uuid5(PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_NAMESPACE, _framed(tuple(parts)))


def create_successor_paper_account_checkpoint(
    prior_checkpoint: PriorPaperAccountCheckpointReference,
    prior_lineage_id: UUID,
    cycle_result: CheckpointedVerifiedSnapshotPaperCycleResult,
    producing_cycle: CheckpointedPaperCycleReportReference,
    metadata: tuple[MetadataEntry, ...] = (),
) -> PaperAccountSuccessorCheckpoint:
    """Derive one immutable successor without mutating the prior checkpoint."""
    if (
        type(prior_checkpoint) is not PriorPaperAccountCheckpointReference
        or type(prior_lineage_id) is not UUID
        or type(cycle_result) is not CheckpointedVerifiedSnapshotPaperCycleResult
        or type(producing_cycle) is not CheckpointedPaperCycleReportReference
    ):
        raise TypeError("successor checkpoint inputs must be exact immutable models")
    metadata = _metadata(metadata)
    if (
        prior_checkpoint.checkpoint_id != cycle_result.prior_checkpoint_id
        or prior_checkpoint.sequence != cycle_result.prior_sequence
        or prior_checkpoint.artifact_sha256 != cycle_result.prior_checkpoint_sha256
        or prior_checkpoint.artifact_byte_length
        != cycle_result.prior_checkpoint_byte_length
        or prior_lineage_id != cycle_result.prior_lineage_id
        or producing_cycle.cycle_result_id != cycle_result.result_id
    ):
        raise SuccessorPaperAccountCheckpointReconciliationError(
            "prior or producing report reference does not match cycle result"
        )
    account_state = SuccessorPaperAccountState(
        _successor_account_state_id(
            cycle_result.final_compact_state,
            cycle_result.opening_realized_profit_loss,
        ),
        cycle_result.final_compact_state,
        cycle_result.opening_realized_profit_loss,
    )
    sequence = prior_checkpoint.sequence + 1
    lineage_id = derive_successor_paper_account_lineage_id(
        prior_lineage_id,
        prior_checkpoint.checkpoint_id,
        cycle_result.result_id,
        sequence,
    )
    empty_engine_state_id = current_order_engine_state_id(OrderEngine())
    checkpoint_id = _successor_checkpoint_id(
        account_state,
        empty_engine_state_id,
        lineage_id,
        prior_checkpoint,
        cycle_result.application_id,
        producing_cycle,
        cycle_result.snapshot_reference,
        metadata,
    )
    return PaperAccountSuccessorCheckpoint(
        checkpoint_id,
        PaperAccountSuccessorCheckpointKind.CYCLE_SUCCESSOR,
        sequence,
        account_state,
        empty_engine_state_id,
        lineage_id,
        prior_lineage_id,
        prior_checkpoint,
        cycle_result.application_id,
        producing_cycle,
        cycle_result.snapshot_reference,
        metadata,
    )


def serialize_successor_paper_account_checkpoint(
    checkpoint: PaperAccountSuccessorCheckpoint,
) -> bytes:
    """Render one successor checkpoint as canonical schema-1 JSON."""
    if type(checkpoint) is not PaperAccountSuccessorCheckpoint:
        raise SuccessorPaperAccountCheckpointSchemaError(
            "checkpoint must be an exact successor checkpoint"
        )
    state = checkpoint.account_state
    compact = state.compact_state
    tree = {
        "schema_version": PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_SCHEMA_VERSION,
        "checkpoint": {
            "checkpoint_id": str(checkpoint.checkpoint_id),
            "kind": checkpoint.kind.value,
            "sequence": checkpoint.sequence,
            "account_state": {
                "account_state_id": str(state.account_state_id),
                "compact_state_id": str(compact.compact_state_id),
                "as_of": canonical_timestamp(compact.as_of),
                "cash": canonical_decimal(compact.cash),
                "positions": [
                    {
                        "symbol": str(position.symbol),
                        "quantity": canonical_decimal(position.quantity),
                        "total_cost_basis": canonical_decimal(
                            position.total_cost_basis
                        ),
                        "average_cost": canonical_decimal(position.average_cost),
                    }
                    for position in compact.positions
                ],
                "realized_profit_loss_before": canonical_decimal(
                    state.realized_profit_loss_before
                ),
                "realized_profit_loss_after": canonical_decimal(
                    compact.realized_profit_loss
                ),
            },
            "empty_engine_state_id": str(checkpoint.empty_engine_state_id),
            "lineage_id": str(checkpoint.lineage_id),
            "prior_lineage_id": str(checkpoint.prior_lineage_id),
            "prior_checkpoint": _reference_tree(checkpoint.prior_checkpoint),
            "application_id": str(checkpoint.application_id),
            "producing_cycle": _report_reference_tree(checkpoint.producing_cycle),
            "snapshot_reference": _snapshot_reference_tree(
                checkpoint.snapshot_reference
            ),
            "metadata": [
                {"key": entry.key, "value": entry.value}
                for entry in checkpoint.metadata
            ],
        },
    }
    payload = _canonical_json_bytes(tree)
    if len(payload) > MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES:
        raise SuccessorPaperAccountCheckpointSchemaError(
            "successor checkpoint exceeds schema byte bound"
        )
    return payload


def parse_successor_paper_account_checkpoint(
    payload: bytes,
) -> PaperAccountSuccessorCheckpoint:
    """Strictly parse only canonical successor-checkpoint JSON bytes."""
    tree = _load_json(payload)
    root = _object(tree, _ROOT_FIELDS, "root")
    if (
        type(root["schema_version"]) is not int
        or root["schema_version"] != PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_SCHEMA_VERSION
    ):
        raise SuccessorPaperAccountCheckpointSchemaError("unsupported schema version")
    raw = _object(root["checkpoint"], _CHECKPOINT_FIELDS, "checkpoint")
    if raw["kind"] != PaperAccountSuccessorCheckpointKind.CYCLE_SUCCESSOR.value:
        raise SuccessorPaperAccountCheckpointSchemaError("invalid successor kind")
    account = _object(raw["account_state"], _ACCOUNT_STATE_FIELDS, "account_state")
    positions = tuple(
        _position(value, f"account_state.positions[{index}]")
        for index, value in enumerate(
            _list(
                account["positions"],
                "account_state.positions",
                MAX_COMPACT_PAPER_LEDGER_POSITIONS,
            )
        )
    )
    try:
        compact = CompactPaperLedgerState(
            _uuid(account["compact_state_id"], "account_state.compact_state_id"),
            _timestamp(account["as_of"], "account_state.as_of"),
            _decimal(account["cash"], "account_state.cash"),
            positions,
            _decimal(
                account["realized_profit_loss_after"],
                "account_state.realized_profit_loss_after",
            ),
        )
        account_state = SuccessorPaperAccountState(
            _uuid(account["account_state_id"], "account_state.account_state_id"),
            compact,
            _decimal(
                account["realized_profit_loss_before"],
                "account_state.realized_profit_loss_before",
            ),
        )
        metadata = tuple(
            MetadataEntry(
                _string(
                    item["key"],
                    "metadata.key",
                    MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_METADATA_KEY_CHARACTERS,
                ),
                _string(
                    item["value"],
                    "metadata.value",
                    MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_METADATA_VALUE_CHARACTERS,
                ),
            )
            for item in (
                _object(value, _METADATA_FIELDS, "metadata")
                for value in _list(
                    raw["metadata"],
                    "metadata",
                    MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_METADATA,
                )
            )
        )
        checkpoint = PaperAccountSuccessorCheckpoint(
            _uuid(raw["checkpoint_id"], "checkpoint.checkpoint_id"),
            PaperAccountSuccessorCheckpointKind.CYCLE_SUCCESSOR,
            _integer(raw["sequence"], "checkpoint.sequence"),
            account_state,
            _uuid(raw["empty_engine_state_id"], "checkpoint.empty_engine_state_id"),
            _uuid(raw["lineage_id"], "checkpoint.lineage_id"),
            _uuid(raw["prior_lineage_id"], "checkpoint.prior_lineage_id"),
            _reference(raw["prior_checkpoint"], "checkpoint.prior_checkpoint"),
            _uuid(raw["application_id"], "checkpoint.application_id"),
            _report_reference(raw["producing_cycle"], "checkpoint.producing_cycle"),
            _snapshot_reference(
                raw["snapshot_reference"], "checkpoint.snapshot_reference"
            ),
            metadata,
        )
    except (TypeError, ValueError) as error:
        raise SuccessorPaperAccountCheckpointSchemaError(
            "successor checkpoint immutable models do not reconcile"
        ) from error
    if serialize_successor_paper_account_checkpoint(checkpoint) != payload:
        raise SuccessorPaperAccountCheckpointSchemaError(
            "successor checkpoint bytes are not canonical"
        )
    return checkpoint


def restore_successor_paper_account_checkpoint(
    checkpoint: PaperAccountSuccessorCheckpoint,
):
    """Restore one successor's exact compact state through the public API."""
    if type(checkpoint) is not PaperAccountSuccessorCheckpoint:
        raise TypeError("checkpoint must be an exact successor checkpoint")
    return restore_paper_ledger_from_compact_state(
        checkpoint.account_state.compact_state
    )


def _reference_tree(
    reference: PriorPaperAccountCheckpointReference,
) -> dict[str, object]:
    return {
        "checkpoint_id": str(reference.checkpoint_id),
        "sequence": reference.sequence,
        "artifact_sha256": reference.artifact_sha256,
        "artifact_byte_length": reference.artifact_byte_length,
    }


def _report_reference_tree(
    reference: CheckpointedPaperCycleReportReference,
) -> dict[str, object]:
    return {
        "report_id": str(reference.report_id),
        "cycle_result_id": str(reference.cycle_result_id),
        "artifact_sha256": reference.artifact_sha256,
        "artifact_byte_length": reference.artifact_byte_length,
    }


def _snapshot_reference_tree(
    reference: VerifiedDailySnapshotReference,
) -> dict[str, object]:
    return {
        "snapshot_id": str(reference.snapshot_id),
        "artifact_sha256": reference.artifact_sha256,
        "artifact_byte_length": reference.artifact_byte_length,
    }


def _canonical_json_bytes(tree: object) -> bytes:
    try:
        return (
            json.dumps(
                tree,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise SuccessorPaperAccountCheckpointSchemaError(
            "successor checkpoint cannot be canonically rendered"
        ) from error


def _load_json(payload: bytes) -> object:
    if (
        type(payload) is not bytes
        or not payload
        or len(payload) > MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES
    ):
        raise SuccessorPaperAccountCheckpointSyntaxError(
            "successor checkpoint bytes are invalid or exceed bounds"
        )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise SuccessorPaperAccountCheckpointSyntaxError("successor checkpoint has BOM")
    try:
        text = payload.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_duplicate_keys,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        SuccessorPaperAccountCheckpointSchemaError,
    ) as error:
        raise SuccessorPaperAccountCheckpointSyntaxError(
            "successor checkpoint JSON is not strict"
        ) from error


def _object(value: object, fields: frozenset[str], path: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise SuccessorPaperAccountCheckpointSchemaError(
            f"{path}: fields do not match schema"
        )
    return value


def _list(value: object, path: str, maximum: int) -> list[object]:
    if type(value) is not list or len(value) > maximum:
        raise SuccessorPaperAccountCheckpointSchemaError(
            f"{path}: invalid bounded array"
        )
    return value


def _string(value: object, path: str, maximum: int) -> str:
    if type(value) is not str or len(value) > maximum:
        raise SuccessorPaperAccountCheckpointSchemaError(f"{path}: invalid string")
    return value


def _uuid(value: object, path: str) -> UUID:
    text = _string(value, path, 36)
    try:
        parsed = UUID(text)
    except (TypeError, ValueError, AttributeError) as error:
        raise SuccessorPaperAccountCheckpointSchemaError(
            f"{path}: invalid UUID"
        ) from error
    if str(parsed) != text:
        raise SuccessorPaperAccountCheckpointSchemaError(
            f"{path}: UUID is not canonical"
        )
    return parsed


def _decimal(value: object, path: str) -> Decimal:
    text = _string(
        value, path, MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_DECIMAL_CHARACTERS
    )
    try:
        parsed = Decimal(text)
    except InvalidOperation as error:
        raise SuccessorPaperAccountCheckpointSchemaError(
            f"{path}: invalid Decimal"
        ) from error
    if not parsed.is_finite() or canonical_decimal(parsed) != text:
        raise SuccessorPaperAccountCheckpointSchemaError(
            f"{path}: Decimal is not canonical"
        )
    return parsed


def _timestamp(value: object, path: str) -> datetime:
    text = _string(value, path, 27)
    if _TIMESTAMP_PATTERN.fullmatch(text) is None:
        raise SuccessorPaperAccountCheckpointSchemaError(
            f"{path}: invalid UTC timestamp"
        )
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00").astimezone(UTC)
    except ValueError as error:
        raise SuccessorPaperAccountCheckpointSchemaError(
            f"{path}: invalid timestamp"
        ) from error
    if canonical_timestamp(parsed) != text:
        raise SuccessorPaperAccountCheckpointSchemaError(
            f"{path}: timestamp is not canonical"
        )
    return parsed


def _integer(value: object, path: str) -> int:
    if (
        type(value) is not int
        or value < 0
        or value > MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_INTEGER
    ):
        raise SuccessorPaperAccountCheckpointSchemaError(f"{path}: invalid integer")
    return value


def _position(value: object, path: str) -> CompactPaperLedgerPosition:
    raw = _object(value, _POSITION_FIELDS, path)
    from trading_bot.domain import Symbol

    try:
        symbol = Symbol(_string(raw["symbol"], f"{path}.symbol", 10))
        position = CompactPaperLedgerPosition(
            symbol,
            _decimal(raw["quantity"], f"{path}.quantity"),
            _decimal(raw["total_cost_basis"], f"{path}.total_cost_basis"),
            _decimal(raw["average_cost"], f"{path}.average_cost"),
        )
    except (TypeError, ValueError) as error:
        raise SuccessorPaperAccountCheckpointSchemaError(
            f"{path}: invalid position"
        ) from error
    if str(symbol) != raw["symbol"]:
        raise SuccessorPaperAccountCheckpointSchemaError(
            f"{path}: symbol is not canonical"
        )
    return position


def _reference(value: object, path: str) -> PriorPaperAccountCheckpointReference:
    raw = _object(value, _REFERENCE_FIELDS, path)
    return PriorPaperAccountCheckpointReference(
        _uuid(raw["checkpoint_id"], f"{path}.checkpoint_id"),
        _integer(raw["sequence"], f"{path}.sequence"),
        _string(raw["artifact_sha256"], f"{path}.artifact_sha256", 64),
        _integer(raw["artifact_byte_length"], f"{path}.artifact_byte_length"),
    )


def _report_reference(
    value: object, path: str
) -> CheckpointedPaperCycleReportReference:
    raw = _object(value, _REPORT_REFERENCE_FIELDS, path)
    return CheckpointedPaperCycleReportReference(
        _uuid(raw["report_id"], f"{path}.report_id"),
        _uuid(raw["cycle_result_id"], f"{path}.cycle_result_id"),
        _string(raw["artifact_sha256"], f"{path}.artifact_sha256", 64),
        _integer(raw["artifact_byte_length"], f"{path}.artifact_byte_length"),
    )


def _snapshot_reference(value: object, path: str) -> VerifiedDailySnapshotReference:
    raw = _object(value, _SNAPSHOT_REFERENCE_FIELDS, path)
    return VerifiedDailySnapshotReference(
        _uuid(raw["snapshot_id"], f"{path}.snapshot_id"),
        _string(raw["artifact_sha256"], f"{path}.artifact_sha256", 64),
        _integer(raw["artifact_byte_length"], f"{path}.artifact_byte_length"),
    )


def _duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise SuccessorPaperAccountCheckpointSchemaError(
                "duplicate JSON object key"
            )
        result[key] = value
    return result


def _reject_float(value: str) -> None:
    raise SuccessorPaperAccountCheckpointSchemaError("JSON float is not permitted")


def _reject_constant(value: str) -> None:
    raise SuccessorPaperAccountCheckpointSchemaError("JSON constant is not permitted")


def verify_checkpointed_paper_cycle_successor_edge(
    report_payload: bytes,
    prior_checkpoint_payload: bytes,
    snapshot_payload: bytes,
    successor_checkpoint_payload: bytes,
    calendar: IdentifiedMarketCalendar,
    *,
    expected_successor_sha256: str | None = None,
    expected_successor_byte_length: int | None = None,
) -> PaperAccountCheckpointEdgeVerificationResult:
    """Verify one complete checkpointed-cycle edge without lineage traversal."""
    from trading_bot.ledger import export_compact_paper_ledger_state
    from trading_bot.runtime.checkpointed_paper_cycle_report import (
        CheckpointedPaperCycleReportVerificationStatus,
        checkpointed_paper_cycle_report_reference,
        verify_checkpointed_paper_cycle_report,
    )

    if (
        type(report_payload) is not bytes
        or type(prior_checkpoint_payload) is not bytes
        or type(snapshot_payload) is not bytes
        or type(successor_checkpoint_payload) is not bytes
    ):
        raise SuccessorPaperAccountCheckpointReconciliationError(
            "edge artifacts must be exact bytes"
        )
    if expected_successor_sha256 is not None and (
        type(expected_successor_sha256) is not str
        or _SHA256_PATTERN.fullmatch(expected_successor_sha256) is None
    ):
        raise SuccessorPaperAccountCheckpointReconciliationError(
            "expected_successor_sha256 is invalid"
        )
    if expected_successor_byte_length is not None and (
        type(expected_successor_byte_length) is not int
        or expected_successor_byte_length < 0
    ):
        raise SuccessorPaperAccountCheckpointReconciliationError(
            "expected_successor_byte_length is invalid"
        )
    successor_length = len(successor_checkpoint_payload)
    successor_hash = sha256(successor_checkpoint_payload).hexdigest()
    diagnostics: list[PaperAccountCheckpointEdgeVerificationDiagnostic] = []
    if (
        expected_successor_byte_length is not None
        and successor_length != expected_successor_byte_length
    ):
        diagnostics.append(
            _edge_diagnostic(
                PaperAccountCheckpointEdgeVerificationCode.SUCCESSOR_BYTE_LENGTH_MISMATCH,
                "successor byte length differs from supplied artifact evidence",
            )
        )
    if (
        expected_successor_sha256 is not None
        and successor_hash != expected_successor_sha256
    ):
        diagnostics.append(
            _edge_diagnostic(
                PaperAccountCheckpointEdgeVerificationCode.SUCCESSOR_SHA256_MISMATCH,
                "successor SHA-256 differs from supplied artifact evidence",
            )
        )
    if diagnostics:
        return _edge_failed(successor_length, successor_hash, diagnostics)
    report_verification = verify_checkpointed_paper_cycle_report(
        report_payload,
        prior_checkpoint_payload,
        snapshot_payload,
        calendar,
    )
    if (
        report_verification.status
        is not CheckpointedPaperCycleReportVerificationStatus.PASS
    ):
        diagnostics.append(
            _edge_diagnostic(
                PaperAccountCheckpointEdgeVerificationCode.REPORT_REPLAY_FAILURE,
                "prior checkpoint, snapshot, or checkpointed-cycle report "
                "failed replay",
            )
        )
        return _edge_failed(successor_length, successor_hash, diagnostics)
    try:
        successor = parse_successor_paper_account_checkpoint(
            successor_checkpoint_payload
        )
    except SuccessorPaperAccountCheckpointSyntaxError as error:
        diagnostics.append(
            _edge_diagnostic(
                PaperAccountCheckpointEdgeVerificationCode.SUCCESSOR_SYNTAX_FAILURE,
                str(error),
            )
        )
        return _edge_failed(successor_length, successor_hash, diagnostics)
    except SuccessorPaperAccountCheckpointSchemaError as error:
        diagnostics.append(
            _edge_diagnostic(
                PaperAccountCheckpointEdgeVerificationCode.SUCCESSOR_SCHEMA_FAILURE,
                str(error),
            )
        )
        return _edge_failed(successor_length, successor_hash, diagnostics)
    assert report_verification.report is not None
    assert report_verification.cycle_result is not None
    cycle_result = report_verification.cycle_result
    try:
        report_reference = checkpointed_paper_cycle_report_reference(report_payload)
        expected = create_successor_paper_account_checkpoint(
            report_verification.report.evidence.prior_checkpoint,
            report_verification.report.evidence.prior_lineage_id,
            cycle_result,
            report_reference,
            successor.metadata,
        )
        if (
            successor != expected
            or successor.producing_cycle != report_reference
            or successor.account_state.compact_state != cycle_result.final_compact_state
            or successor.account_state.realized_profit_loss_before
            != cycle_result.opening_realized_profit_loss
        ):
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "successor checkpoint differs from exact replayed edge evidence"
            )
        ledger, evidence = restore_successor_paper_account_checkpoint(successor)
        if (
            not ledger.is_compact_restored
            or ledger.fills
            or evidence.compact_state_id
            != successor.account_state.compact_state.compact_state_id
            or export_compact_paper_ledger_state(
                ledger,
                as_of=successor.account_state.as_of,
            )
            != successor.account_state.compact_state
        ):
            raise SuccessorPaperAccountCheckpointReconciliationError(
                "restored successor ledger does not reconcile"
            )
    except SuccessorPaperAccountCheckpointReconciliationError as error:
        diagnostics.append(
            _edge_diagnostic(
                PaperAccountCheckpointEdgeVerificationCode.SUCCESSOR_RECONCILIATION_FAILURE,
                str(error),
            )
        )
        return _edge_failed(successor_length, successor_hash, diagnostics)
    return PaperAccountCheckpointEdgeVerificationResult(
        PaperAccountCheckpointEdgeVerificationStatus.PASS,
        successor_length,
        successor_hash,
        cycle_result,
        successor,
        ledger,
        (),
    )


def _edge_diagnostic(
    code: PaperAccountCheckpointEdgeVerificationCode,
    detail: str,
) -> PaperAccountCheckpointEdgeVerificationDiagnostic:
    return PaperAccountCheckpointEdgeVerificationDiagnostic(code, detail)


def _edge_failed(
    successor_length: int,
    successor_hash: str,
    diagnostics: list[PaperAccountCheckpointEdgeVerificationDiagnostic],
) -> PaperAccountCheckpointEdgeVerificationResult:
    return PaperAccountCheckpointEdgeVerificationResult(
        PaperAccountCheckpointEdgeVerificationStatus.FAIL,
        successor_length,
        successor_hash,
        None,
        None,
        None,
        tuple(diagnostics),
    )
