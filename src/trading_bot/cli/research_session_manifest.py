"""Deterministic audit envelope for completed walk-forward artifacts."""

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID, uuid5

from trading_bot.cli.exceptions import (
    ResearchSessionManifestError,
    ResearchSessionManifestJsonError,
    ResearchSessionManifestReadError,
    ResearchSessionManifestVerificationError,
)
from trading_bot.portfolio import MetadataEntry

RESEARCH_SESSION_MANIFEST_SCHEMA_VERSION = 1
RESEARCH_SESSION_PRODUCER_PROTOCOL = "ai-trading-bot-walk-forward-research-session-v1"
_IDENTITY_NAMESPACE = UUID("eaaeed7e-fc15-52d8-b35c-e1424621a913")
_IDENTITY_VERSION = "walk-forward-research-session-manifest-identity-v1"
_RESERVED_METADATA_PREFIX = "walk_forward_research_session_manifest_"
MAX_RESEARCH_SESSION_MANIFEST_BYTES = 4 * 1024 * 1024
_HASH_CHUNK_BYTES = 64 * 1024
_UTF8_BOM = b"\xef\xbb\xbf"


class ResearchSessionArtifactKind(StrEnum):
    """One supported rendered walk-forward artifact kind."""

    WALK_FORWARD_JSON = "WALK_FORWARD_JSON"
    WALK_FORWARD_CSV = "WALK_FORWARD_CSV"
    AGGREGATE_JSON = "AGGREGATE_JSON"
    AGGREGATE_CSV = "AGGREGATE_CSV"
    STABILITY_JSON = "STABILITY_JSON"
    STABILITY_CSV = "STABILITY_CSV"


class ResearchSessionHashAlgorithm(StrEnum):
    """The fixed version-one content hash algorithm."""

    SHA256 = "SHA256"


class ResearchSessionArtifactVerificationStatus(StrEnum):
    """Stable terminal status for one retained artifact record."""

    PASS = "PASS"
    MISSING_OR_NONREGULAR = "MISSING_OR_NONREGULAR"
    UNEXPECTED_IO = "UNEXPECTED_IO"
    BYTE_LENGTH_MISMATCH = "BYTE_LENGTH_MISMATCH"
    SHA256_MISMATCH = "SHA256_MISMATCH"


_CANONICAL_KINDS = tuple(ResearchSessionArtifactKind)
_FAMILY = {
    ResearchSessionArtifactKind.WALK_FORWARD_JSON: "walk_forward",
    ResearchSessionArtifactKind.WALK_FORWARD_CSV: "walk_forward",
    ResearchSessionArtifactKind.AGGREGATE_JSON: "aggregate",
    ResearchSessionArtifactKind.AGGREGATE_CSV: "aggregate",
    ResearchSessionArtifactKind.STABILITY_JSON: "stability",
    ResearchSessionArtifactKind.STABILITY_CSV: "stability",
}


def _exact_positive_int(value: object, name: str) -> int:
    if type(value) is not int or value < 1:
        raise ResearchSessionManifestError(f"{name} must be an exact positive integer")
    return value


def _exact_nonnegative_int(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ResearchSessionManifestError(
            f"{name} must be an exact nonnegative integer"
        )
    return value


def _normalized_absolute(path: object, name: str) -> Path:
    if not isinstance(path, Path):
        raise ResearchSessionManifestError(f"{name} must be a Path")
    if not path.is_absolute() or path != path.resolve(strict=False):
        raise ResearchSessionManifestError(f"{name} must be an exact normalized path")
    return path


@dataclass(frozen=True, slots=True)
class CompletedResearchArtifact:
    """Exact bytes and destination of one already-rendered primary artifact."""

    destination: Path
    kind: ResearchSessionArtifactKind
    artifact_schema_version: int
    result_id: UUID
    content: bytes

    def __post_init__(self) -> None:
        _normalized_absolute(self.destination, "destination")
        if not isinstance(self.kind, ResearchSessionArtifactKind):
            raise ResearchSessionManifestError(
                "kind must be a ResearchSessionArtifactKind"
            )
        _exact_positive_int(self.artifact_schema_version, "artifact_schema_version")
        if type(self.result_id) is not UUID:
            raise ResearchSessionManifestError("result_id must be an exact UUID")
        if type(self.content) is not bytes:
            raise ResearchSessionManifestError("content must be exact bytes")


@dataclass(frozen=True, slots=True)
class ResearchSessionArtifactRecord:
    """Content evidence recorded for one primary artifact."""

    ordinal: int
    kind: ResearchSessionArtifactKind
    artifact_schema_version: int
    result_id: UUID
    path: str
    hash_algorithm: ResearchSessionHashAlgorithm
    content_hash: str
    byte_length: int

    def __post_init__(self) -> None:
        _exact_positive_int(self.ordinal, "ordinal")
        if not isinstance(self.kind, ResearchSessionArtifactKind):
            raise ResearchSessionManifestError(
                "kind must be a ResearchSessionArtifactKind"
            )
        _exact_positive_int(self.artifact_schema_version, "artifact_schema_version")
        if type(self.result_id) is not UUID:
            raise ResearchSessionManifestError("result_id must be an exact UUID")
        if type(self.path) is not str or not self.path or "\\" in self.path:
            raise ResearchSessionManifestError(
                "path must be a nonblank manifest-parent-relative POSIX path"
            )
        relative = PurePosixPath(self.path)
        if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
            raise ResearchSessionManifestError(
                "path must be a normalized manifest-parent-relative POSIX path"
            )
        if self.hash_algorithm is not ResearchSessionHashAlgorithm.SHA256:
            raise ResearchSessionManifestError("hash_algorithm must be SHA256")
        if (
            type(self.content_hash) is not str
            or len(self.content_hash) != 64
            or any(
                character not in "0123456789abcdef" for character in self.content_hash
            )
        ):
            raise ResearchSessionManifestError(
                "content_hash must be a lowercase SHA-256 digest"
            )
        _exact_nonnegative_int(self.byte_length, "byte_length")


@dataclass(frozen=True, slots=True)
class WalkForwardResearchSessionManifest:
    """Immutable downstream audit envelope for one completed CLI run."""

    manifest_id: UUID
    manifest_schema_version: int
    producer_protocol: str
    walk_forward_config_schema_version: int
    walk_forward_result_id: UUID
    aggregate_result_id: UUID | None
    stability_result_id: UUID | None
    session_label: str | None
    metadata: tuple[MetadataEntry, ...]
    artifacts: tuple[ResearchSessionArtifactRecord, ...]

    def __post_init__(self) -> None:
        if type(self.manifest_id) is not UUID:
            raise ResearchSessionManifestError("manifest_id must be an exact UUID")
        if self.manifest_schema_version != RESEARCH_SESSION_MANIFEST_SCHEMA_VERSION:
            raise ResearchSessionManifestError("unsupported manifest schema version")
        if self.producer_protocol != RESEARCH_SESSION_PRODUCER_PROTOCOL:
            raise ResearchSessionManifestError("unsupported producer protocol")
        _exact_positive_int(
            self.walk_forward_config_schema_version,
            "walk_forward_config_schema_version",
        )
        if type(self.walk_forward_result_id) is not UUID:
            raise ResearchSessionManifestError(
                "walk_forward_result_id must be an exact UUID"
            )
        for name in ("aggregate_result_id", "stability_result_id"):
            value = getattr(self, name)
            if value is not None and type(value) is not UUID:
                raise ResearchSessionManifestError(f"{name} must be an exact UUID")
        _validate_label_and_metadata(self.session_label, self.metadata)
        _validate_records(self.artifacts)
        family_ids: dict[str, UUID] = {}
        for artifact in self.artifacts:
            family = _FAMILY[artifact.kind]
            previous = family_ids.setdefault(family, artifact.result_id)
            if previous != artifact.result_id:
                raise ResearchSessionManifestError(
                    f"{family} artifacts must share one result ID"
                )
        if (
            self.walk_forward_result_id != family_ids["walk_forward"]
            or self.aggregate_result_id != family_ids.get("aggregate")
            or self.stability_result_id != family_ids.get("stability")
        ):
            raise ResearchSessionManifestError(
                "top-level result IDs must derive exactly from artifact records"
            )
        expected = _manifest_identity(self)
        if self.manifest_id != expected:
            raise ResearchSessionManifestError(
                "manifest_id does not reconcile with manifest contents"
            )


@dataclass(frozen=True, slots=True)
class ResearchSessionArtifactVerificationResult:
    """Immutable verification evidence for one retained artifact."""

    artifact: ResearchSessionArtifactRecord
    status: ResearchSessionArtifactVerificationStatus
    actual_byte_length: int | None = None
    actual_content_hash: str | None = None

    def __post_init__(self) -> None:
        if type(self.artifact) is not ResearchSessionArtifactRecord:
            raise TypeError("artifact must be an exact ResearchSessionArtifactRecord")
        if not isinstance(self.status, ResearchSessionArtifactVerificationStatus):
            raise TypeError(
                "status must be a ResearchSessionArtifactVerificationStatus"
            )
        if self.actual_byte_length is not None:
            _exact_nonnegative_int(self.actual_byte_length, "actual_byte_length")
        if self.actual_content_hash is not None and (
            type(self.actual_content_hash) is not str
            or len(self.actual_content_hash) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.actual_content_hash
            )
        ):
            raise TypeError("actual_content_hash must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class ResearchSessionManifestVerificationResult:
    """Immutable complete result of one offline manifest verification."""

    manifest: WalkForwardResearchSessionManifest
    artifacts: tuple[ResearchSessionArtifactVerificationResult, ...]

    def __post_init__(self) -> None:
        if type(self.manifest) is not WalkForwardResearchSessionManifest:
            raise TypeError(
                "manifest must be an exact WalkForwardResearchSessionManifest"
            )
        if type(self.artifacts) is not tuple or not all(
            type(item) is ResearchSessionArtifactVerificationResult
            for item in self.artifacts
        ):
            raise TypeError("artifacts must be an exact tuple of verification results")
        if tuple(item.artifact for item in self.artifacts) != self.manifest.artifacts:
            raise ValueError(
                "verification results must retain the exact manifest artifact order"
            )

    @property
    def passed(self) -> bool:
        """Whether every retained artifact passed."""

        return all(
            item.status is ResearchSessionArtifactVerificationStatus.PASS
            for item in self.artifacts
        )


def _validate_label_and_metadata(
    session_label: str | None, metadata: tuple[MetadataEntry, ...]
) -> None:
    if session_label is not None and (
        type(session_label) is not str
        or not session_label
        or session_label != session_label.strip()
    ):
        raise ResearchSessionManifestError(
            "session_label must be a nonblank unpadded string"
        )
    if type(metadata) is not tuple or not all(
        isinstance(item, MetadataEntry) for item in metadata
    ):
        raise ResearchSessionManifestError(
            "metadata must be an exact tuple of MetadataEntry values"
        )
    if len({item.key for item in metadata}) != len(metadata):
        raise ResearchSessionManifestError("metadata keys must be unique")
    if any(
        item.key.startswith(_RESERVED_METADATA_PREFIX)
        or item.key != item.key.strip()
        or item.value != item.value.strip()
        for item in metadata
    ):
        raise ResearchSessionManifestError(
            "metadata keys and values must be unpadded and use no reserved prefix"
        )


def _validate_records(
    artifacts: tuple[ResearchSessionArtifactRecord, ...],
) -> None:
    if type(artifacts) is not tuple or not artifacts:
        raise ResearchSessionManifestError("artifacts must be a nonempty exact tuple")
    if not all(isinstance(item, ResearchSessionArtifactRecord) for item in artifacts):
        raise ResearchSessionManifestError(
            "artifacts must contain ResearchSessionArtifactRecord values"
        )
    if tuple(item.ordinal for item in artifacts) != tuple(range(1, len(artifacts) + 1)):
        raise ResearchSessionManifestError("artifact ordinals must be contiguous")
    kinds = tuple(item.kind for item in artifacts)
    if len(set(kinds)) != len(kinds):
        raise ResearchSessionManifestError("artifact kinds must be unique")
    if kinds != tuple(kind for kind in _CANONICAL_KINDS if kind in kinds):
        raise ResearchSessionManifestError("artifacts must use canonical output order")
    if not any(_FAMILY[kind] == "walk_forward" for kind in kinds):
        raise ResearchSessionManifestError(
            "at least one walk-forward artifact is required"
        )


def _relative_path(destination: Path, manifest_parent: Path) -> str:
    try:
        value = os.path.relpath(destination, manifest_parent)
    except ValueError as error:
        raise ResearchSessionManifestError(
            "artifact and manifest destinations must be on the same volume"
        ) from error
    return PurePosixPath(Path(value).as_posix()).as_posix()


def build_walk_forward_research_session_manifest(
    *,
    manifest_path: Path,
    walk_forward_config_schema_version: int,
    artifacts: tuple[CompletedResearchArtifact, ...],
    session_label: str | None = None,
    metadata: tuple[MetadataEntry, ...] = (),
) -> WalkForwardResearchSessionManifest:
    """Build a manifest solely from exact completed artifact descriptors."""

    manifest_path = _normalized_absolute(manifest_path, "manifest_path")
    _exact_positive_int(
        walk_forward_config_schema_version, "walk_forward_config_schema_version"
    )
    _validate_label_and_metadata(session_label, metadata)
    if (
        type(artifacts) is not tuple
        or not artifacts
        or not all(isinstance(item, CompletedResearchArtifact) for item in artifacts)
    ):
        raise ResearchSessionManifestError(
            "artifacts must be a nonempty exact tuple of "
            "CompletedResearchArtifact values"
        )
    kinds = tuple(item.kind for item in artifacts)
    if len(set(kinds)) != len(kinds):
        raise ResearchSessionManifestError("artifact kinds must be unique")
    if kinds != tuple(kind for kind in _CANONICAL_KINDS if kind in kinds):
        raise ResearchSessionManifestError("artifacts must use canonical output order")
    if not any(_FAMILY[kind] == "walk_forward" for kind in kinds):
        raise ResearchSessionManifestError(
            "at least one walk-forward artifact is required"
        )
    family_ids: dict[str, UUID] = {}
    records = []
    for ordinal, artifact in enumerate(artifacts, start=1):
        family = _FAMILY[artifact.kind]
        previous = family_ids.setdefault(family, artifact.result_id)
        if previous != artifact.result_id:
            raise ResearchSessionManifestError(
                f"{family} artifacts must share one result ID"
            )
        records.append(
            ResearchSessionArtifactRecord(
                ordinal,
                artifact.kind,
                artifact.artifact_schema_version,
                artifact.result_id,
                _relative_path(artifact.destination, manifest_path.parent),
                ResearchSessionHashAlgorithm.SHA256,
                hashlib.sha256(artifact.content).hexdigest(),
                len(artifact.content),
            )
        )
    placeholder = object.__new__(WalkForwardResearchSessionManifest)
    values = {
        "manifest_id": UUID(int=0),
        "manifest_schema_version": RESEARCH_SESSION_MANIFEST_SCHEMA_VERSION,
        "producer_protocol": RESEARCH_SESSION_PRODUCER_PROTOCOL,
        "walk_forward_config_schema_version": walk_forward_config_schema_version,
        "walk_forward_result_id": family_ids["walk_forward"],
        "aggregate_result_id": family_ids.get("aggregate"),
        "stability_result_id": family_ids.get("stability"),
        "session_label": session_label,
        "metadata": metadata,
        "artifacts": tuple(records),
    }
    for name, value in values.items():
        object.__setattr__(placeholder, name, value)
    values["manifest_id"] = _manifest_identity(placeholder)
    return WalkForwardResearchSessionManifest(**values)


def _identity_field(value: object) -> str:
    text = "" if value is None else str(value)
    return f"{len(text.encode('utf-8'))}:{text}"


def _manifest_identity(manifest: WalkForwardResearchSessionManifest) -> UUID:
    material = [
        _IDENTITY_VERSION,
        manifest.manifest_schema_version,
        manifest.producer_protocol,
        manifest.walk_forward_config_schema_version,
        manifest.walk_forward_result_id,
        manifest.aggregate_result_id,
        manifest.stability_result_id,
        manifest.session_label,
        len(manifest.metadata),
    ]
    for item in manifest.metadata:
        material.extend((item.key, item.value))
    material.append(len(manifest.artifacts))
    for item in manifest.artifacts:
        material.extend(
            (
                item.ordinal,
                item.kind.value,
                item.artifact_schema_version,
                item.result_id,
                item.hash_algorithm.value,
                item.content_hash,
                item.byte_length,
            )
        )
    canonical = "|".join(_identity_field(item) for item in material)
    return uuid5(_IDENTITY_NAMESPACE, canonical)


def serialize_walk_forward_research_session_manifest_json(
    manifest: WalkForwardResearchSessionManifest, *, pretty: bool = False
) -> str:
    """Serialize one immutable manifest without inspecting primary artifacts."""

    if type(manifest) is not WalkForwardResearchSessionManifest:
        raise ResearchSessionManifestError(
            "manifest must be an exact WalkForwardResearchSessionManifest"
        )
    if type(pretty) is not bool:
        raise ResearchSessionManifestError("pretty must be an exact bool")
    payload = {
        "schema_version": manifest.manifest_schema_version,
        "walk_forward_research_session_manifest": {
            "manifest_id": str(manifest.manifest_id),
            "producer_protocol": manifest.producer_protocol,
            "walk_forward_config_schema_version": (
                manifest.walk_forward_config_schema_version
            ),
            "result_ids": {
                "walk_forward": str(manifest.walk_forward_result_id),
                "aggregate": (
                    None
                    if manifest.aggregate_result_id is None
                    else str(manifest.aggregate_result_id)
                ),
                "stability": (
                    None
                    if manifest.stability_result_id is None
                    else str(manifest.stability_result_id)
                ),
            },
            "session_label": manifest.session_label,
            "metadata": [
                {"key": item.key, "value": item.value} for item in manifest.metadata
            ],
            "artifacts": [
                {
                    "ordinal": item.ordinal,
                    "kind": item.kind.value,
                    "artifact_schema_version": item.artifact_schema_version,
                    "result_id": str(item.result_id),
                    "path": item.path,
                    "path_base": "MANIFEST_PARENT",
                    "hash": {
                        "algorithm": item.hash_algorithm.value,
                        "value": item.content_hash,
                    },
                    "byte_length": item.byte_length,
                }
                for item in manifest.artifacts
            ],
        },
    }
    options = {"indent": 2} if pretty else {"separators": (",", ":")}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, **options) + "\n"


class _DuplicateJsonKeyError(ValueError):
    pass


class _NonstandardJsonConstantError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError(key)
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise _NonstandardJsonConstantError(value)


def load_walk_forward_research_session_manifest(
    path: Path,
) -> WalkForwardResearchSessionManifest:
    """Read and strictly reconstruct one retained manifest."""

    try:
        with path.open("rb") as stream:
            content = stream.read(MAX_RESEARCH_SESSION_MANIFEST_BYTES + 1)
    except (OSError, ValueError) as error:
        raise ResearchSessionManifestReadError("cannot read manifest") from error
    if len(content) > MAX_RESEARCH_SESSION_MANIFEST_BYTES:
        raise ResearchSessionManifestReadError(
            "manifest exceeds maximum byte size of 4194304"
        )
    return parse_walk_forward_research_session_manifest_bytes(content)


def parse_walk_forward_research_session_manifest_bytes(
    content: bytes,
) -> WalkForwardResearchSessionManifest:
    """Strictly reconstruct an immutable manifest without filesystem access."""

    if type(content) is not bytes:
        raise TypeError("content must be exact bytes")
    if len(content) > MAX_RESEARCH_SESSION_MANIFEST_BYTES:
        raise ResearchSessionManifestReadError(
            "manifest exceeds maximum byte size of 4194304"
        )
    if content.startswith(_UTF8_BOM):
        raise ResearchSessionManifestReadError("UTF-8 BOM is unsupported")
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ResearchSessionManifestReadError("manifest is not valid UTF-8") from error
    try:
        raw = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except _DuplicateJsonKeyError as error:
        key = json.dumps(str(error), ensure_ascii=False)
        raise ResearchSessionManifestJsonError(
            f"duplicate JSON object key: {key}"
        ) from error
    except _NonstandardJsonConstantError as error:
        value = json.dumps(str(error), ensure_ascii=False)
        raise ResearchSessionManifestJsonError(
            f"nonstandard JSON constant: {value}"
        ) from error
    except json.JSONDecodeError as error:
        raise ResearchSessionManifestJsonError(
            f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error
    return parse_walk_forward_research_session_manifest(raw)


def _manifest_object(value: Any, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ResearchSessionManifestError(f"{path}: must be an object")
    return value


def _manifest_exact_keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    missing = sorted(expected - value.keys())
    if missing:
        raise ResearchSessionManifestError(
            f"{path}.{missing[0]}: required field is missing"
        )
    unknown = sorted(value.keys() - expected)
    if unknown:
        raise ResearchSessionManifestError(f"{path}.{unknown[0]}: unknown field")


def _manifest_integer(value: Any, path: str, *, nonnegative: bool = False) -> int:
    if type(value) is not int:
        raise ResearchSessionManifestError(f"{path}: must be an exact integer")
    minimum = 0 if nonnegative else 1
    if value < minimum:
        qualifier = "nonnegative" if nonnegative else "positive"
        raise ResearchSessionManifestError(
            f"{path}: must be an exact {qualifier} integer"
        )
    return value


def _manifest_string(value: Any, path: str) -> str:
    if type(value) is not str:
        raise ResearchSessionManifestError(f"{path}: must be an exact string")
    return value


def _manifest_uuid(value: Any, path: str) -> UUID:
    text = _manifest_string(value, path)
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError) as error:
        raise ResearchSessionManifestError(
            f"{path}: must be a canonical UUID string"
        ) from error
    if str(parsed) != text:
        raise ResearchSessionManifestError(f"{path}: must be a canonical UUID string")
    return parsed


def _manifest_enum(value: Any, enum_type: type[StrEnum], path: str) -> StrEnum:
    text = _manifest_string(value, path)
    try:
        return enum_type(text)
    except ValueError as error:
        raise ResearchSessionManifestError(f"{path}: invalid enum value") from error


def parse_walk_forward_research_session_manifest(
    raw: Any,
) -> WalkForwardResearchSessionManifest:
    """Reconstruct schema-one JSON using only retained structural evidence."""

    root = _manifest_object(raw, "$")
    _manifest_exact_keys(
        root, {"schema_version", "walk_forward_research_session_manifest"}, "$"
    )
    version = _manifest_integer(root["schema_version"], "$.schema_version")
    if version != RESEARCH_SESSION_MANIFEST_SCHEMA_VERSION:
        raise ResearchSessionManifestError(
            "$.schema_version: unsupported manifest schema version"
        )
    base = "$.walk_forward_research_session_manifest"
    item = _manifest_object(root["walk_forward_research_session_manifest"], base)
    _manifest_exact_keys(
        item,
        {
            "manifest_id",
            "producer_protocol",
            "walk_forward_config_schema_version",
            "result_ids",
            "session_label",
            "metadata",
            "artifacts",
        },
        base,
    )
    result_path = f"{base}.result_ids"
    result_ids = _manifest_object(item["result_ids"], result_path)
    _manifest_exact_keys(
        result_ids, {"walk_forward", "aggregate", "stability"}, result_path
    )
    metadata_raw = item["metadata"]
    if type(metadata_raw) is not list:
        raise ResearchSessionManifestError(f"{base}.metadata: must be an array")
    metadata = []
    for index, raw_entry in enumerate(metadata_raw):
        path = f"{base}.metadata[{index}]"
        entry = _manifest_object(raw_entry, path)
        _manifest_exact_keys(entry, {"key", "value"}, path)
        try:
            metadata.append(
                MetadataEntry(
                    _manifest_string(entry["key"], f"{path}.key"),
                    _manifest_string(entry["value"], f"{path}.value"),
                )
            )
        except (TypeError, ValueError) as error:
            raise ResearchSessionManifestError(f"{path}: {error}") from error
    artifacts_raw = item["artifacts"]
    if type(artifacts_raw) is not list:
        raise ResearchSessionManifestError(f"{base}.artifacts: must be an array")
    artifacts = []
    for index, raw_artifact in enumerate(artifacts_raw):
        path = f"{base}.artifacts[{index}]"
        artifact = _manifest_object(raw_artifact, path)
        _manifest_exact_keys(
            artifact,
            {
                "ordinal",
                "kind",
                "artifact_schema_version",
                "result_id",
                "path",
                "path_base",
                "hash",
                "byte_length",
            },
            path,
        )
        if (
            _manifest_string(artifact["path_base"], f"{path}.path_base")
            != "MANIFEST_PARENT"
        ):
            raise ResearchSessionManifestError(f"{path}.path_base: invalid enum value")
        hash_path = f"{path}.hash"
        hash_item = _manifest_object(artifact["hash"], hash_path)
        _manifest_exact_keys(hash_item, {"algorithm", "value"}, hash_path)
        try:
            artifacts.append(
                ResearchSessionArtifactRecord(
                    ordinal=_manifest_integer(artifact["ordinal"], f"{path}.ordinal"),
                    kind=ResearchSessionArtifactKind(
                        _manifest_enum(
                            artifact["kind"],
                            ResearchSessionArtifactKind,
                            f"{path}.kind",
                        )
                    ),
                    artifact_schema_version=_manifest_integer(
                        artifact["artifact_schema_version"],
                        f"{path}.artifact_schema_version",
                    ),
                    result_id=_manifest_uuid(
                        artifact["result_id"], f"{path}.result_id"
                    ),
                    path=_manifest_string(artifact["path"], f"{path}.path"),
                    hash_algorithm=ResearchSessionHashAlgorithm(
                        _manifest_enum(
                            hash_item["algorithm"],
                            ResearchSessionHashAlgorithm,
                            f"{hash_path}.algorithm",
                        )
                    ),
                    content_hash=_manifest_string(
                        hash_item["value"], f"{hash_path}.value"
                    ),
                    byte_length=_manifest_integer(
                        artifact["byte_length"],
                        f"{path}.byte_length",
                        nonnegative=True,
                    ),
                )
            )
        except ResearchSessionManifestError:
            raise
        except (TypeError, ValueError) as error:
            raise ResearchSessionManifestError(f"{path}: {error}") from error
    paths = [artifact.path for artifact in artifacts]
    if len(set(paths)) != len(paths):
        raise ResearchSessionManifestError(
            f"{base}.artifacts: retained artifact paths must be unique"
        )
    session_label = item["session_label"]
    if session_label is not None:
        session_label = _manifest_string(session_label, f"{base}.session_label")
    aggregate_id = result_ids["aggregate"]
    stability_id = result_ids["stability"]
    try:
        return WalkForwardResearchSessionManifest(
            manifest_id=_manifest_uuid(item["manifest_id"], f"{base}.manifest_id"),
            manifest_schema_version=version,
            producer_protocol=_manifest_string(
                item["producer_protocol"], f"{base}.producer_protocol"
            ),
            walk_forward_config_schema_version=_manifest_integer(
                item["walk_forward_config_schema_version"],
                f"{base}.walk_forward_config_schema_version",
            ),
            walk_forward_result_id=_manifest_uuid(
                result_ids["walk_forward"], f"{result_path}.walk_forward"
            ),
            aggregate_result_id=(
                None
                if aggregate_id is None
                else _manifest_uuid(aggregate_id, f"{result_path}.aggregate")
            ),
            stability_result_id=(
                None
                if stability_id is None
                else _manifest_uuid(stability_id, f"{result_path}.stability")
            ),
            session_label=session_label,
            metadata=tuple(metadata),
            artifacts=tuple(artifacts),
        )
    except ResearchSessionManifestError as error:
        if str(error).startswith("$"):
            raise
        raise ResearchSessionManifestError(f"{base}: {error}") from error


def _is_reparse_point(result: os.stat_result) -> bool:
    attributes = getattr(result, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _changed_during_read(before: os.stat_result, after: os.stat_result) -> bool:
    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    return any(getattr(before, name) != getattr(after, name) for name in fields)


def _artifact_verification(
    artifact: ResearchSessionArtifactRecord, manifest_parent: Path
) -> ResearchSessionArtifactVerificationResult:
    current = manifest_parent
    parts = PurePosixPath(artifact.path).parts
    for component in parts[:-1]:
        current = current / component
        try:
            component_stat = current.lstat()
        except FileNotFoundError:
            return ResearchSessionArtifactVerificationResult(
                artifact,
                ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
            )
        except OSError:
            return ResearchSessionArtifactVerificationResult(
                artifact, ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
            )
        if (
            stat.S_ISLNK(component_stat.st_mode)
            or _is_reparse_point(component_stat)
            or not stat.S_ISDIR(component_stat.st_mode)
        ):
            return ResearchSessionArtifactVerificationResult(
                artifact,
                ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
            )
    path = manifest_parent.joinpath(*parts)
    try:
        retained_stat = path.lstat()
    except FileNotFoundError:
        return ResearchSessionArtifactVerificationResult(
            artifact,
            ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
        )
    except OSError:
        return ResearchSessionArtifactVerificationResult(
            artifact, ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
        )
    if (
        stat.S_ISLNK(retained_stat.st_mode)
        or _is_reparse_point(retained_stat)
        or not stat.S_ISREG(retained_stat.st_mode)
    ):
        return ResearchSessionArtifactVerificationResult(
            artifact,
            ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
        )
    try:
        with path.open("rb") as stream:
            opened_before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(opened_before.st_mode)
                or _is_reparse_point(opened_before)
                or (retained_stat.st_dev, retained_stat.st_ino)
                != (opened_before.st_dev, opened_before.st_ino)
            ):
                return ResearchSessionArtifactVerificationResult(
                    artifact,
                    ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO,
                )
            digest = hashlib.sha256()
            byte_length = 0
            while chunk := stream.read(_HASH_CHUNK_BYTES):
                byte_length += len(chunk)
                digest.update(chunk)
            opened_after = os.fstat(stream.fileno())
    except FileNotFoundError:
        return ResearchSessionArtifactVerificationResult(
            artifact,
            ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
        )
    except OSError:
        return ResearchSessionArtifactVerificationResult(
            artifact, ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
        )
    actual_hash = digest.hexdigest()
    if _changed_during_read(opened_before, opened_after):
        return ResearchSessionArtifactVerificationResult(
            artifact,
            ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO,
            byte_length,
            actual_hash,
        )
    if byte_length != artifact.byte_length:
        return ResearchSessionArtifactVerificationResult(
            artifact,
            ResearchSessionArtifactVerificationStatus.BYTE_LENGTH_MISMATCH,
            byte_length,
            actual_hash,
        )
    if actual_hash != artifact.content_hash:
        return ResearchSessionArtifactVerificationResult(
            artifact,
            ResearchSessionArtifactVerificationStatus.SHA256_MISMATCH,
            byte_length,
            actual_hash,
        )
    return ResearchSessionArtifactVerificationResult(
        artifact,
        ResearchSessionArtifactVerificationStatus.PASS,
        byte_length,
        actual_hash,
    )


def verify_walk_forward_research_session_manifest(
    manifest: WalkForwardResearchSessionManifest, *, manifest_path: Path
) -> ResearchSessionManifestVerificationResult:
    """Verify exact primary bytes without parsing or invoking workflow behavior."""

    if type(manifest) is not WalkForwardResearchSessionManifest:
        raise ResearchSessionManifestVerificationError(
            "manifest must be an exact WalkForwardResearchSessionManifest"
        )
    manifest_path = _normalized_absolute(manifest_path, "manifest_path")
    return ResearchSessionManifestVerificationResult(
        manifest,
        tuple(
            _artifact_verification(artifact, manifest_path.parent)
            for artifact in manifest.artifacts
        ),
    )
