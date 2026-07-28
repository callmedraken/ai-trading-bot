"""Strict manifest loading for explicit offline checkpoint lineage verification."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from trading_bot.market_data import MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES
from trading_bot.runtime import (
    MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
    MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES,
    MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactKind,
)

PAPER_ACCOUNT_LINEAGE_MANIFEST_SCHEMA_VERSION = 1
MAX_PAPER_ACCOUNT_LINEAGE_MANIFEST_BYTES = 1024 * 1024
MAX_PAPER_ACCOUNT_LINEAGE_MANIFEST_ARTIFACTS = 10_000
MAX_PAPER_ACCOUNT_LINEAGE_PATH_CHARACTERS = 4096

_ROOT_FIELDS = {
    "schema_version",
    "genesis_checkpoint",
    "terminal_checkpoint_id",
    "successor_checkpoints",
    "cycle_reports",
    "snapshots",
}
_ARTIFACT_FIELDS = {"artifact_id", "path", "sha256", "byte_length"}
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PaperAccountLineageManifestReadError(Exception):
    """Raised when the manifest or an explicitly listed file is unsafe."""


class PaperAccountLineageManifestSyntaxError(Exception):
    """Raised when manifest bytes are not bounded strict JSON."""


class PaperAccountLineageManifestValidationError(ValueError):
    """Raised when the strict manifest schema is invalid."""


@dataclass(frozen=True, slots=True)
class PaperAccountLineageManifest:
    genesis_checkpoint: PaperAccountLineageArtifact
    terminal_checkpoint_id: UUID
    successor_checkpoints: tuple[PaperAccountLineageArtifact, ...]
    cycle_reports: tuple[PaperAccountLineageArtifact, ...]
    snapshots: tuple[PaperAccountLineageArtifact, ...]


def load_paper_account_lineage_manifest(
    path: Path,
) -> PaperAccountLineageManifest:
    """Read one safe manifest and only its explicitly listed regular files."""
    if not isinstance(path, Path):
        raise PaperAccountLineageManifestReadError("manifest path is invalid")
    manifest_path = _absolute(path)
    payload = _read_regular(
        manifest_path,
        MAX_PAPER_ACCOUNT_LINEAGE_MANIFEST_BYTES,
        "manifest",
    )
    tree = _json(payload)
    root = _object(tree, _ROOT_FIELDS, "root")
    if (
        type(root["schema_version"]) is not int
        or root["schema_version"] != PAPER_ACCOUNT_LINEAGE_MANIFEST_SCHEMA_VERSION
    ):
        raise PaperAccountLineageManifestValidationError(
            "unsupported lineage manifest schema"
        )
    base = manifest_path.parent
    genesis = _artifact(
        root["genesis_checkpoint"],
        "genesis_checkpoint",
        base,
        PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
        MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES,
    )
    successors = _artifact_array(
        root["successor_checkpoints"],
        "successor_checkpoints",
        base,
        PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
        MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
    )
    reports = _artifact_array(
        root["cycle_reports"],
        "cycle_reports",
        base,
        PaperAccountLineageArtifactKind.CYCLE_REPORT,
        MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
    )
    snapshots = _artifact_array(
        root["snapshots"],
        "snapshots",
        base,
        PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
        MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
    )
    return PaperAccountLineageManifest(
        genesis,
        _uuid(root["terminal_checkpoint_id"], "terminal_checkpoint_id"),
        successors,
        reports,
        snapshots,
    )


def _artifact_array(
    value: object,
    label: str,
    base: Path,
    kind: PaperAccountLineageArtifactKind,
    maximum: int,
) -> tuple[PaperAccountLineageArtifact, ...]:
    if type(value) is not list:
        raise PaperAccountLineageManifestValidationError(f"{label} must be an array")
    if len(value) > MAX_PAPER_ACCOUNT_LINEAGE_MANIFEST_ARTIFACTS:
        raise PaperAccountLineageManifestValidationError(
            f"{label} exceeds its artifact bound"
        )
    return tuple(
        _artifact(item, f"{label}[{index}]", base, kind, maximum)
        for index, item in enumerate(value)
    )


def _artifact(
    value: object,
    label: str,
    base: Path,
    kind: PaperAccountLineageArtifactKind,
    maximum: int,
) -> PaperAccountLineageArtifact:
    raw = _object(value, _ARTIFACT_FIELDS, label)
    path_text = _string(raw["path"], f"{label}.path")
    artifact_path = Path(path_text)
    if not artifact_path.is_absolute():
        artifact_path = base / artifact_path
    payload = _read_regular(_absolute(artifact_path), maximum, label)
    length = raw["byte_length"]
    if type(length) is not int or length < 0:
        raise PaperAccountLineageManifestValidationError(
            f"{label}.byte_length must be a nonnegative integer"
        )
    digest = _string(raw["sha256"], f"{label}.sha256")
    if _SHA256_PATTERN.fullmatch(digest) is None:
        raise PaperAccountLineageManifestValidationError(
            f"{label}.sha256 must be lowercase SHA-256 text"
        )
    return PaperAccountLineageArtifact(
        kind,
        _uuid(raw["artifact_id"], f"{label}.artifact_id"),
        payload,
        digest,
        length,
    )


def _read_regular(path: Path, maximum: int, label: str) -> bytes:
    _safe_chain(path)
    try:
        before = os.lstat(path)
        if not _real_regular(before):
            raise PaperAccountLineageManifestReadError(
                f"{label} is not a safe regular file"
            )
        with path.open("rb") as stream:
            payload = stream.read(maximum + 1)
        after = os.lstat(path)
    except PaperAccountLineageManifestReadError:
        raise
    except OSError as error:
        raise PaperAccountLineageManifestReadError(f"{label} cannot be read") from error
    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
        raise PaperAccountLineageManifestReadError(f"{label} changed while reading")
    if not _real_regular(after):
        raise PaperAccountLineageManifestReadError(
            f"{label} is not a safe regular file"
        )
    if len(payload) > maximum:
        raise PaperAccountLineageManifestReadError(f"{label} exceeds its byte bound")
    return payload


def _safe_chain(path: Path) -> None:
    for item in (path, *path.parents):
        try:
            retained = os.lstat(item)
        except OSError as error:
            raise PaperAccountLineageManifestReadError(
                "artifact path chain is unavailable"
            ) from error
        if stat.S_ISLNK(retained.st_mode) or _reparse(retained):
            raise PaperAccountLineageManifestReadError("artifact path chain is unsafe")


def _real_regular(value: os.stat_result) -> bool:
    return (
        stat.S_ISREG(value.st_mode)
        and not stat.S_ISLNK(value.st_mode)
        and not _reparse(value)
    )


def _reparse(value: os.stat_result) -> bool:
    return bool(
        getattr(value, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _absolute(path: Path) -> Path:
    try:
        return Path(os.path.abspath(path))
    except (OSError, ValueError) as error:
        raise PaperAccountLineageManifestReadError(
            "artifact path is invalid"
        ) from error


def _json(payload: bytes) -> object:
    if payload.startswith(b"\xef\xbb\xbf"):
        raise PaperAccountLineageManifestSyntaxError("manifest BOM is not permitted")
    try:
        text = payload.decode("utf-8", errors="strict")
        return json.loads(
            text,
            object_pairs_hook=_duplicates,
            parse_float=_float,
            parse_constant=_constant,
        )
    except PaperAccountLineageManifestSyntaxError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PaperAccountLineageManifestSyntaxError(
            "manifest is not strict UTF-8 JSON"
        ) from error


def _duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PaperAccountLineageManifestSyntaxError(
                "duplicate manifest object key"
            )
        result[key] = value
    return result


def _float(_: str) -> None:
    raise PaperAccountLineageManifestSyntaxError("JSON floats are not permitted")


def _constant(_: str) -> None:
    raise PaperAccountLineageManifestSyntaxError("JSON constants are not permitted")


def _object(value: object, fields: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise PaperAccountLineageManifestValidationError(f"{label} fields are invalid")
    return value


def _string(value: object, label: str) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > MAX_PAPER_ACCOUNT_LINEAGE_PATH_CHARACTERS
    ):
        raise PaperAccountLineageManifestValidationError(f"{label} is invalid")
    return value


def _uuid(value: object, label: str) -> UUID:
    if type(value) is not str:
        raise PaperAccountLineageManifestValidationError(f"{label} must be UUID text")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as error:
        raise PaperAccountLineageManifestValidationError(
            f"{label} must be lowercase canonical UUID text"
        ) from error
    if str(parsed) != value:
        raise PaperAccountLineageManifestValidationError(
            f"{label} must be lowercase canonical UUID text"
        )
    return parsed
