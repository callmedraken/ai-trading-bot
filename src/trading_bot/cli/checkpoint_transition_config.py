"""Strict nonsecret configuration for genesis and one checkpoint transition."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID

from trading_bot.cli.verified_snapshot_cycle_config import (
    parse_verified_snapshot_paper_cycle_config,
)
from trading_bot.domain import Symbol
from trading_bot.market_data import canonical_decimal
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime import (
    CheckpointedVerifiedSnapshotPaperCycleRequest,
    ExplicitQuantityTarget,
    ExplicitQuantityTargetPortfolio,
    PaperAccountCheckpointPosition,
    PaperAccountGenesisRequest,
    VerifiedDailySnapshotReference,
)

MAX_CHECKPOINT_TRANSITION_CONFIG_BYTES = 256 * 1024
CHECKPOINT_TRANSITION_CONFIG_SCHEMA_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{6})?Z$"
)
_RESERVED = ("checkpoint.", "lineage.", "application.")


class CheckpointTransitionConfigReadError(Exception):
    """Raised when caller configuration cannot be read within its bound."""


class CheckpointTransitionConfigSyntaxError(Exception):
    """Raised when caller configuration is not strict UTF-8 JSON."""


class CheckpointTransitionConfigValidationError(ValueError):
    """Raised when required caller intent is not canonical or complete."""


@dataclass(frozen=True, slots=True)
class GenesisCheckpointConfig:
    """Complete caller-authored opening-account assertion."""

    request: PaperAccountGenesisRequest


@dataclass(frozen=True, slots=True)
class CheckpointTransitionConfig:
    """Complete caller intent for one checkpoint-restored cycle."""

    request: CheckpointedVerifiedSnapshotPaperCycleRequest


def load_genesis_checkpoint_config(path: Path) -> GenesisCheckpointConfig:
    """Read one bounded strict genesis configuration."""
    return parse_genesis_checkpoint_config(_read(path))


def load_checkpoint_transition_config(path: Path) -> CheckpointTransitionConfig:
    """Read one bounded strict checkpoint-transition configuration."""
    return parse_checkpoint_transition_config(_read(path))


def parse_genesis_checkpoint_config(payload: bytes) -> GenesisCheckpointConfig:
    """Parse all required genesis opening-state fields without defaults."""
    root = _json(payload)
    raw = _object(root, {"schema_version", "opening_state"}, "root")
    _schema(raw["schema_version"])
    opening = _object(
        raw["opening_state"],
        {"as_of", "cash", "positions", "realized_profit_loss", "metadata"},
        "opening_state",
    )
    positions = tuple(
        _position(item, index)
        for index, item in enumerate(_array(opening["positions"], "positions", 100))
    )
    try:
        request = PaperAccountGenesisRequest(
            _timestamp(opening["as_of"], "opening_state.as_of"),
            _decimal(opening["cash"], "opening_state.cash"),
            positions,
            _decimal(
                opening["realized_profit_loss"], "opening_state.realized_profit_loss"
            ),
            _metadata(opening["metadata"]),
        )
    except (TypeError, ValueError) as error:
        raise CheckpointTransitionConfigValidationError(
            "opening_state does not reconcile"
        ) from error
    return GenesisCheckpointConfig(request)


def parse_checkpoint_transition_config(payload: bytes) -> CheckpointTransitionConfig:
    """Parse a no-account caller request using the established policy parser."""
    root = _json(payload)
    fields = {
        "schema_version",
        "request_id",
        "snapshot_reference",
        "target",
        "open_references",
        "policies",
        "planning_at",
        "submitted_at",
        "filled_at",
        "metadata",
    }
    raw = _object(root, fields, "root")
    _schema(raw["schema_version"])
    # The established strict parser owns the complete public policy grammar.
    # Its account assertion is intentionally synthetic and never reaches runtime.
    legacy = dict(raw)
    legacy["account_state"] = {
        "account_state_id": "00000000-0000-0000-0000-000000000000",
        "as_of": raw["planning_at"],
        "cash": "1",
        "positions": [],
    }
    try:
        prepared = parse_verified_snapshot_paper_cycle_config(
            json.dumps(legacy, separators=(",", ":")).encode("utf-8")
        ).preparation_request
        snapshot = _snapshot(raw["snapshot_reference"])
        target = _target(raw["target"])
        metadata = _metadata(raw["metadata"])
        request = CheckpointedVerifiedSnapshotPaperCycleRequest(
            prepared.request_id,
            snapshot,
            target,
            prepared.open_references,
            prepared.policies,
            prepared.planning_at,
            prepared.submitted_at,
            prepared.filled_at,
            metadata,
        )
    except (TypeError, ValueError) as error:
        raise CheckpointTransitionConfigValidationError(
            "transition configuration does not reconcile"
        ) from error
    return CheckpointTransitionConfig(request)


def _read(path: Path) -> bytes:
    if not isinstance(path, Path):
        raise CheckpointTransitionConfigReadError("configuration path is invalid")
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise CheckpointTransitionConfigReadError(
            "configuration cannot be read"
        ) from error
    if len(payload) > MAX_CHECKPOINT_TRANSITION_CONFIG_BYTES:
        raise CheckpointTransitionConfigReadError("configuration exceeds 256 KiB")
    return payload


def _json(payload: bytes) -> object:
    if type(payload) is not bytes or not payload:
        raise CheckpointTransitionConfigReadError("configuration bytes are invalid")
    if len(payload) > MAX_CHECKPOINT_TRANSITION_CONFIG_BYTES:
        raise CheckpointTransitionConfigReadError("configuration exceeds 256 KiB")
    if payload.startswith(b"\xef\xbb\xbf"):
        raise CheckpointTransitionConfigSyntaxError("configuration has a UTF-8 BOM")
    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_duplicates,
            parse_float=_float,
            parse_constant=_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckpointTransitionConfigSyntaxError(
            "configuration is not strict JSON"
        ) from error


def _duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CheckpointTransitionConfigSyntaxError("duplicate JSON object key")
        result[key] = value
    return result


def _float(_: str) -> None:
    raise CheckpointTransitionConfigSyntaxError("JSON floats are not permitted")


def _constant(_: str) -> None:
    raise CheckpointTransitionConfigSyntaxError("JSON constants are not permitted")


def _object(value: object, fields: set[str], path: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise CheckpointTransitionConfigValidationError(f"{path}: fields do not match")
    return value


def _array(value: object, path: str, maximum: int) -> list[object]:
    if type(value) is not list or len(value) > maximum:
        raise CheckpointTransitionConfigValidationError(
            f"{path}: invalid bounded array"
        )
    return value


def _schema(value: object) -> None:
    if type(value) is not int or value != CHECKPOINT_TRANSITION_CONFIG_SCHEMA_VERSION:
        raise CheckpointTransitionConfigValidationError("schema_version must be 1")


def _string(value: object, path: str, maximum: int = 4096) -> str:
    if type(value) is not str or len(value) > maximum:
        raise CheckpointTransitionConfigValidationError(f"{path}: invalid string")
    return value


def _decimal(value: object, path: str) -> Decimal:
    text = _string(value, path)
    try:
        parsed = Decimal(text)
    except InvalidOperation as error:
        raise CheckpointTransitionConfigValidationError(
            f"{path}: invalid Decimal"
        ) from error
    if not parsed.is_finite() or canonical_decimal(parsed) != text:
        raise CheckpointTransitionConfigValidationError(f"{path}: noncanonical Decimal")
    return parsed


def _timestamp(value: object, path: str) -> datetime:
    text = _string(value, path, 27)
    if _TIMESTAMP.fullmatch(text) is None:
        raise CheckpointTransitionConfigValidationError(f"{path}: invalid timestamp")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00").astimezone(UTC)
    except ValueError as error:
        raise CheckpointTransitionConfigValidationError(
            f"{path}: invalid timestamp"
        ) from error
    if parsed.isoformat().replace("+00:00", "Z") != text:
        raise CheckpointTransitionConfigValidationError(
            f"{path}: noncanonical timestamp"
        )
    return parsed


def _uuid(value: object, path: str) -> UUID:
    text = _string(value, path, 36)
    try:
        parsed = UUID(text)
    except ValueError as error:
        raise CheckpointTransitionConfigValidationError(
            f"{path}: invalid UUID"
        ) from error
    if str(parsed) != text:
        raise CheckpointTransitionConfigValidationError(f"{path}: noncanonical UUID")
    return parsed


def _snapshot(value: object) -> VerifiedDailySnapshotReference:
    raw = _object(
        value,
        {"snapshot_id", "artifact_sha256", "artifact_byte_length"},
        "snapshot_reference",
    )
    digest = _string(raw["artifact_sha256"], "snapshot_reference.artifact_sha256", 64)
    if _SHA256.fullmatch(digest) is None:
        raise CheckpointTransitionConfigValidationError(
            "snapshot_reference: invalid SHA-256"
        )
    if type(raw["artifact_byte_length"]) is not int or raw["artifact_byte_length"] <= 0:
        raise CheckpointTransitionConfigValidationError(
            "snapshot_reference: invalid byte length"
        )
    return VerifiedDailySnapshotReference(
        _uuid(raw["snapshot_id"], "snapshot_reference.snapshot_id"),
        digest,
        raw["artifact_byte_length"],
    )


def _target(value: object) -> ExplicitQuantityTargetPortfolio:
    raw = _object(value, {"target_id", "quantities", "target_cash"}, "target")
    quantities = tuple(
        ExplicitQuantityTarget(
            Symbol(
                _string(
                    _object(item, {"symbol", "quantity"}, "target.quantity")["symbol"],
                    "target.quantity.symbol",
                    10,
                )
            ),
            _decimal(
                _object(item, {"symbol", "quantity"}, "target.quantity")["quantity"],
                "target.quantity.quantity",
            ),
        )
        for item in _array(raw["quantities"], "target.quantities", 100)
    )
    return ExplicitQuantityTargetPortfolio(
        _uuid(raw["target_id"], "target.target_id"),
        quantities,
        _decimal(raw["target_cash"], "target.target_cash"),
    )


def _position(value: object, index: int) -> PaperAccountCheckpointPosition:
    raw = _object(
        value, {"symbol", "quantity", "total_cost_basis"}, f"positions[{index}]"
    )
    try:
        return PaperAccountCheckpointPosition.from_exact_basis(
            Symbol(_string(raw["symbol"], f"positions[{index}].symbol", 10)),
            _decimal(raw["quantity"], f"positions[{index}].quantity"),
            _decimal(raw["total_cost_basis"], f"positions[{index}].total_cost_basis"),
        )
    except (TypeError, ValueError) as error:
        raise CheckpointTransitionConfigValidationError(
            f"positions[{index}]: invalid"
        ) from error


def _metadata(value: object) -> tuple[MetadataEntry, ...]:
    entries = tuple(
        MetadataEntry(
            _string(
                _object(item, {"key", "value"}, "metadata")["key"], "metadata.key", 128
            ),
            _string(
                _object(item, {"key", "value"}, "metadata")["value"],
                "metadata.value",
                4096,
            ),
        )
        for item in _array(value, "metadata", 100)
    )
    if len({item.key for item in entries}) != len(entries) or any(
        item.key.startswith(_RESERVED) for item in entries
    ):
        raise CheckpointTransitionConfigValidationError("metadata keys are invalid")
    return entries
