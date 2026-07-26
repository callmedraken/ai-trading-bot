"""Deterministic audit envelope for completed walk-forward artifacts."""

import hashlib
import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid5

from trading_bot.cli.exceptions import (
    ResearchSessionManifestError,
    ResearchSessionManifestVerificationError,
)
from trading_bot.portfolio import MetadataEntry

RESEARCH_SESSION_MANIFEST_SCHEMA_VERSION = 1
RESEARCH_SESSION_PRODUCER_PROTOCOL = "ai-trading-bot-walk-forward-research-session-v1"
_IDENTITY_NAMESPACE = UUID("eaaeed7e-fc15-52d8-b35c-e1424621a913")
_IDENTITY_VERSION = "walk-forward-research-session-manifest-identity-v1"
_RESERVED_METADATA_PREFIX = "walk_forward_research_session_manifest_"


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


def verify_walk_forward_research_session_manifest(
    manifest: WalkForwardResearchSessionManifest, *, manifest_path: Path
) -> None:
    """Verify exact primary bytes without parsing or invoking workflow behavior."""

    if type(manifest) is not WalkForwardResearchSessionManifest:
        raise ResearchSessionManifestVerificationError(
            "manifest must be an exact WalkForwardResearchSessionManifest"
        )
    manifest_path = _normalized_absolute(manifest_path, "manifest_path")
    for artifact in manifest.artifacts:
        path = manifest_path.parent.joinpath(*PurePosixPath(artifact.path).parts)
        try:
            if not path.is_file():
                raise ResearchSessionManifestVerificationError(
                    f"artifact is not a regular file: {path}"
                )
            content = path.read_bytes()
        except OSError as error:
            raise ResearchSessionManifestVerificationError(
                f"cannot read artifact: {path}: {error}"
            ) from error
        if len(content) != artifact.byte_length:
            raise ResearchSessionManifestVerificationError(
                f"artifact byte length mismatch: {path}"
            )
        if hashlib.sha256(content).hexdigest() != artifact.content_hash:
            raise ResearchSessionManifestVerificationError(
                f"artifact SHA-256 mismatch: {path}"
            )
