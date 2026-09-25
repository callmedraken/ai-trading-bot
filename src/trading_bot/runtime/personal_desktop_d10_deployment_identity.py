"""Pure Architecture-123 A1 canonical deployment identity models."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass

from trading_bot.runtime.personal_desktop_unattended_one_week_soak_scheduler_contract import (  # noqa: E501
    D10_GUARD_SOURCE_RELATIVE_PATH,
    D10_LAUNCH_GUARD,
    D10_LAUNCHER_SOURCE_RELATIVE_PATH,
    D10_SCHEDULER_CONTRACT,
    D10_SCHEDULER_CONTRACT_SCHEMA,
    D10_SECOND_STAGE_LAUNCHER,
    is_frozen_one_week_soak_scheduler_contract,
)
from trading_bot.runtime.personal_desktop_unattended_one_week_soak_scheduler_contract import (  # noqa: E501
    D10_SOURCE_ROOT as D10_SEALED_SOURCE_ROOT,
)

EXECUTABLE_MANIFEST_SCHEMA = "personal-desktop-d10-executable-manifest/v1"
DEPLOYMENT_ATTESTATION_SCHEMA = "personal-desktop-d10-deployment-attestation/v2"
D10_SIGNING_KEY_ID = "AITradingBot/D10/DeploymentAttestation/v3"
D10_SOURCE_ROOT = str(D10_SEALED_SOURCE_ROOT)
D10_PRODUCTION_PYTHON = r"F:\AITradingBot\runtime\python.exe"
D10_GUARD_RELATIVE_PATH = D10_GUARD_SOURCE_RELATIVE_PATH
D10_LAUNCHER_RELATIVE_PATH = D10_LAUNCHER_SOURCE_RELATIVE_PATH
DEPLOYMENT_ID_NAMESPACE_V2 = uuid.UUID("703b383a-ee31-5ffb-8f61-09cb8edf146e")

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_GIT_OID = re.compile(r"[0-9a-f]{40}\Z")
_PYTHON_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
_DEVICE = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?\Z", re.I)
_ENTRY_FIELDS = frozenset({"relative_path", "byte_length", "sha256"})
_MANIFEST_FIELDS = frozenset({"schema", "entries"})
_ATTESTATION_FIELDS = frozenset(
    {
        "schema",
        "signing_key_id",
        "certified_source_head",
        "certified_source_tree",
        "source_root",
        "launch_guard",
        "launch_guard_byte_length",
        "launch_guard_sha256",
        "launcher",
        "scheduler_contract_schema",
        "approved_trading_sid",
        "production_python",
        "production_python_version",
        "executable_manifest_sha256",
        "executable_file_count",
        "deployment_id",
    }
)


class DeploymentIdentityError(ValueError):
    """Canonical D10 identity data violates the frozen source contract."""


def canonical_json_bytes(value: object) -> bytes:
    """Serialize JSON using the exact D10 UTF-8 representation."""
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except UnicodeError as exc:
        raise DeploymentIdentityError("invalid Unicode in canonical JSON") from exc


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DeploymentIdentityError("duplicate JSON field")
        result[key] = value
    return result


def _parse_json(data: bytes) -> dict[str, object]:
    if type(data) is not bytes:
        raise DeploymentIdentityError("canonical input must be bytes")
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                DeploymentIdentityError("non-finite JSON value")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DeploymentIdentityError("invalid UTF-8 JSON") from exc
    if type(value) is not dict:
        raise DeploymentIdentityError("JSON root must be an object")
    return value


def _require_fields(value: object, names: frozenset[str]) -> dict[str, object]:
    if type(value) is not dict or frozenset(value) != names:
        raise DeploymentIdentityError("field set is not exact")
    return value


def canonical_relative_path(value: str) -> str:
    """Validate a repository-relative portable Windows deployment path."""
    if type(value) is not str or not value or value.startswith("/"):
        raise DeploymentIdentityError("invalid relative path")
    if "\\" in value or ":" in value or "\x00" in value:
        raise DeploymentIdentityError("alternate, ADS, or device path")
    for component in value.split("/"):
        if (
            component in ("", ".", "..")
            or component.endswith((".", " "))
            or _DEVICE.fullmatch(component)
            or any(ord(char) < 32 or char in '<>"|?*' for char in component)
        ):
            raise DeploymentIdentityError("unsafe path component")
    if not (
        value.startswith("src/trading_bot/") or value == D10_LAUNCHER_RELATIVE_PATH
    ):
        raise DeploymentIdentityError("path is outside the governed deployment set")
    return value


@dataclass(frozen=True, slots=True)
class ExecutableManifestEntry:
    relative_path: str
    byte_length: int
    sha256: str

    def __post_init__(self) -> None:
        canonical_relative_path(self.relative_path)
        if type(self.byte_length) is not int or self.byte_length < 0:
            raise DeploymentIdentityError("byte_length must be a nonnegative exact int")
        if type(self.sha256) is not str or _SHA256.fullmatch(self.sha256) is None:
            raise DeploymentIdentityError("sha256 must be lowercase SHA-256")

    def to_dict(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "byte_length": self.byte_length,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class ExecutableManifest:
    schema: str
    entries: tuple[ExecutableManifestEntry, ...]

    def __post_init__(self) -> None:
        if type(self.schema) is not str or self.schema != EXECUTABLE_MANIFEST_SCHEMA:
            raise DeploymentIdentityError("unsupported manifest schema")
        if type(self.entries) is not tuple or not self.entries:
            raise DeploymentIdentityError("manifest entries must be a nonempty tuple")
        if any(type(entry) is not ExecutableManifestEntry for entry in self.entries):
            raise DeploymentIdentityError("invalid manifest entry")
        paths = [entry.relative_path for entry in self.entries]
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise DeploymentIdentityError("manifest paths are not strictly sorted")
        if len(paths) != len({path.casefold() for path in paths}):
            raise DeploymentIdentityError("casefold-colliding manifest paths")
        if D10_LAUNCHER_RELATIVE_PATH not in paths:
            raise DeploymentIdentityError("D10 launcher is missing from manifest")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def parse_executable_manifest(data: bytes) -> ExecutableManifest:
    value = _require_fields(_parse_json(data), _MANIFEST_FIELDS)
    entries = value["entries"]
    if type(entries) is not list:
        raise DeploymentIdentityError("manifest entries must be an array")
    model = ExecutableManifest(
        schema=value["schema"],
        entries=tuple(
            ExecutableManifestEntry(**_require_fields(entry, _ENTRY_FIELDS))
            for entry in entries
        ),
    )
    if model.canonical_bytes() != data:
        raise DeploymentIdentityError("manifest bytes are not canonical")
    return model


@dataclass(frozen=True, slots=True)
class DeploymentAttestation:
    schema: str
    signing_key_id: str
    certified_source_head: str
    certified_source_tree: str
    source_root: str
    launch_guard: str
    launch_guard_byte_length: int
    launch_guard_sha256: str
    launcher: str
    scheduler_contract_schema: str
    approved_trading_sid: str
    production_python: str
    production_python_version: str
    executable_manifest_sha256: str
    executable_file_count: int
    deployment_id: str

    def __post_init__(self) -> None:
        if type(self.schema) is not str or self.schema != DEPLOYMENT_ATTESTATION_SCHEMA:
            raise DeploymentIdentityError("unsupported attestation schema")
        if (
            type(self.signing_key_id) is not str
            or self.signing_key_id != D10_SIGNING_KEY_ID
        ):
            raise DeploymentIdentityError("wrong D10 signing key ID")
        for value in (self.certified_source_head, self.certified_source_tree):
            if type(value) is not str or _GIT_OID.fullmatch(value) is None:
                raise DeploymentIdentityError("Git identity must be lowercase 40-hex")
        if (
            not is_frozen_one_week_soak_scheduler_contract(D10_SCHEDULER_CONTRACT)
            or type(self.source_root) is not str
            or self.source_root != D10_SOURCE_ROOT
            or type(self.launch_guard) is not str
            or self.launch_guard != str(D10_LAUNCH_GUARD)
            or type(self.launcher) is not str
            or self.launcher != str(D10_SECOND_STAGE_LAUNCHER)
            or type(self.scheduler_contract_schema) is not str
            or self.scheduler_contract_schema != D10_SCHEDULER_CONTRACT_SCHEMA
            or type(self.approved_trading_sid) is not str
            or self.approved_trading_sid != D10_SCHEDULER_CONTRACT.principal_sid
            or type(self.production_python) is not str
            or self.production_python != D10_PRODUCTION_PYTHON
            or self.production_python
            != str(D10_SCHEDULER_CONTRACT.production_interpreter)
        ):
            raise DeploymentIdentityError(
                "attestation differs from source-owned D10 contract"
            )
        if (
            type(self.launch_guard_byte_length) is not int
            or self.launch_guard_byte_length < 0
        ):
            raise DeploymentIdentityError("invalid launch guard byte length")
        if (
            type(self.launch_guard_sha256) is not str
            or _SHA256.fullmatch(self.launch_guard_sha256) is None
        ):
            raise DeploymentIdentityError("invalid launch guard digest")
        version = (
            _PYTHON_VERSION.fullmatch(self.production_python_version)
            if type(self.production_python_version) is str
            else None
        )
        if version is None or int(version[1]) != 3 or int(version[2]) < 12:
            raise DeploymentIdentityError("invalid production Python version")
        if (
            type(self.executable_manifest_sha256) is not str
            or _SHA256.fullmatch(self.executable_manifest_sha256) is None
        ):
            raise DeploymentIdentityError("invalid executable manifest digest")
        if (
            type(self.executable_file_count) is not int
            or self.executable_file_count < 1
        ):
            raise DeploymentIdentityError("invalid executable file count")
        if (
            type(self.deployment_id) is not str
            or self.deployment_id != self.expected_id()
        ):
            raise DeploymentIdentityError(
                "deployment ID does not match canonical material"
            )

    def authority_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "signing_key_id": self.signing_key_id,
            "certified_source_head": self.certified_source_head,
            "certified_source_tree": self.certified_source_tree,
            "source_root": self.source_root,
            "launch_guard": self.launch_guard,
            "launch_guard_byte_length": self.launch_guard_byte_length,
            "launch_guard_sha256": self.launch_guard_sha256,
            "launcher": self.launcher,
            "scheduler_contract_schema": self.scheduler_contract_schema,
            "approved_trading_sid": self.approved_trading_sid,
            "production_python": self.production_python,
            "production_python_version": self.production_python_version,
            "executable_manifest_sha256": self.executable_manifest_sha256,
            "executable_file_count": self.executable_file_count,
        }

    def expected_id(self) -> str:
        """UUID5 of all authority fields in canonical JSON under the v2 namespace."""
        return str(
            uuid.uuid5(
                DEPLOYMENT_ID_NAMESPACE_V2,
                canonical_json_bytes(self.authority_dict()).decode("utf-8"),
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {**self.authority_dict(), "deployment_id": self.deployment_id}

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())


def build_deployment_attestation(
    *,
    certified_source_head: str,
    certified_source_tree: str,
    production_python_version: str,
    launch_guard_byte_length: int,
    launch_guard_sha256: str,
    executable_manifest_sha256: str,
    executable_file_count: int,
) -> DeploymentAttestation:
    """Construct deterministic unsigned attestation data from explicit facts."""
    fields = {
        "schema": DEPLOYMENT_ATTESTATION_SCHEMA,
        "signing_key_id": D10_SIGNING_KEY_ID,
        "certified_source_head": certified_source_head,
        "certified_source_tree": certified_source_tree,
        "source_root": D10_SOURCE_ROOT,
        "launch_guard": str(D10_LAUNCH_GUARD),
        "launch_guard_byte_length": launch_guard_byte_length,
        "launch_guard_sha256": launch_guard_sha256,
        "launcher": str(D10_SECOND_STAGE_LAUNCHER),
        "scheduler_contract_schema": D10_SCHEDULER_CONTRACT_SCHEMA,
        "approved_trading_sid": D10_SCHEDULER_CONTRACT.principal_sid,
        "production_python": D10_PRODUCTION_PYTHON,
        "production_python_version": production_python_version,
        "executable_manifest_sha256": executable_manifest_sha256,
        "executable_file_count": executable_file_count,
    }
    deployment_id = str(
        uuid.uuid5(
            DEPLOYMENT_ID_NAMESPACE_V2, canonical_json_bytes(fields).decode("utf-8")
        )
    )
    return DeploymentAttestation(**fields, deployment_id=deployment_id)


def parse_deployment_attestation(data: bytes) -> DeploymentAttestation:
    model = DeploymentAttestation(
        **_require_fields(_parse_json(data), _ATTESTATION_FIELDS)
    )
    if model.canonical_bytes() != data:
        raise DeploymentIdentityError("attestation bytes are not canonical")
    return model
