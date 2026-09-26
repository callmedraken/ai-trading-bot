"""Source-only contracts for protected D10 P124-2/P124-3 checkpoints."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from scripts.build_d10_deployment_identity import (
    D10BuildResult,
    build_d10_deployment_identity,
)
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    D10_GUARD_RELATIVE_PATH,
    D10_LAUNCHER_RELATIVE_PATH,
    D10_SIGNING_KEY_ID,
    DeploymentAttestation,
    ExecutableManifest,
    canonical_relative_path,
    parse_deployment_attestation,
    parse_executable_manifest,
)

CERTIFIED_SOURCE_HEAD = "86f1021d244bf62bcf5a0f457c30eb98b998de90"
CERTIFIED_SOURCE_TREE = "cfa455811f6bd1b3373a66f6716afca9dbd254df"
PRODUCTION_PYTHON_VERSION = "3.14.3"
D10_PARENT = r"F:\AITradingBot"
D10_ROOT = D10_PARENT + r"\D10"
D10_SOURCE = D10_ROOT + r"\source"
D10_SOURCE_INSTALLING = D10_SOURCE + ".installing"
D10_GUARD = D10_ROOT + r"\launch-guard.py"
D10_GUARD_INSTALLING = D10_GUARD + ".installing"
D10_ATTESTATION = D10_ROOT + r"\deployment.attestation.json"
D10_SIGNATURE = D10_ROOT + r"\deployment.attestation.sig"
D10_MANIFEST = D10_ROOT + r"\executable-manifest.json"
D10_ACTIVATION_LEASE = D10_ROOT + r"\activation.lease.json"
D10_CACHE_PREFIX = D10_ROOT + r"\no-pycache"
TRUST_FINAL_PATHS = (D10_ATTESTATION, D10_SIGNATURE, D10_MANIFEST)
TRUST_INSTALLING_PATHS = tuple(p + ".installing" for p in TRUST_FINAL_PATHS)
P1242_RESERVED_PATHS = (
    D10_GUARD_INSTALLING,
    D10_SOURCE_INSTALLING,
    *TRUST_FINAL_PATHS,
    *TRUST_INSTALLING_PATHS,
    D10_ACTIVATION_LEASE,
    D10_ACTIVATION_LEASE + ".installing",
    D10_ACTIVATION_LEASE + ".tmp",
    D10_CACHE_PREFIX,
)
P1243_RESERVED_PATHS = (
    D10_GUARD_INSTALLING,
    D10_SOURCE_INSTALLING,
    D10_ACTIVATION_LEASE,
    D10_ACTIVATION_LEASE + ".installing",
    D10_ACTIVATION_LEASE + ".tmp",
    D10_CACHE_PREFIX,
    *TRUST_INSTALLING_PATHS,
)

TRADING_SID = "S-1-5-21-1397534616-3988210162-180023805-1009"
ADMINISTRATORS_SID = "S-1-5-32-544"
SYSTEM_SID = "S-1-5-18"
FILE_ALL_ACCESS = 0x001F01FF
TRADING_FILE_READ = 0x00120089
TRADING_DIRECTORY_READ = 0x001200A9
SIGNATURE_ALGORITHM = "ECDSA-P256"
SIGNATURE_HASH = "SHA-256"
SIGNATURE_ENCODING = "IEEE-P1363"
P256_ORDER = int("FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551", 16)
MAX_GUARD_BYTES = 512 * 1024
MAX_ATTESTATION_BYTES = 64 * 1024
MAX_SIGNATURE_BYTES = 64
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_SOURCE_FILE_BYTES = 1024 * 1024 * 1024
MAX_SOURCE_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_SOURCE_FILES = 100_000
MAX_TRANSCRIPT_BYTES = 1024 * 1024
REPARSE_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_GIT_OID = re.compile(r"[0-9a-f]{40}\Z")


class DeploymentBlocked(RuntimeError):
    """A P124 operation cannot continue under the frozen contract."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Ace:
    sid: str
    mask: int
    ace_type: int = 0
    flags: int = 0


@dataclass(frozen=True, slots=True)
class NativeObject:
    path: str
    final_path: str
    directory: bool
    owner_sid: str
    dacl_protected: bool
    aces: tuple[Ace, ...]
    reparse: bool
    drive_type: int
    volume_root: str
    filesystem: str
    volume_serial: int
    file_index: int
    links: int
    size: int


@dataclass(frozen=True, slots=True)
class CheckedFile:
    identity: NativeObject
    data: bytes
    stable: bool


@dataclass(frozen=True, slots=True)
class CheckedDirectory:
    identity: NativeObject
    children: tuple[str, ...]
    stable: bool


class DeploymentBackend(Protocol):
    def require_administrator(self) -> None: ...
    def bind_source_inventory(self, relative_paths: tuple[str, ...]) -> None: ...
    def require_absent(self, path: str) -> None: ...
    def create_directory(self, path: str) -> None: ...
    def create_file(self, path: str, data: bytes) -> None: ...
    def publish_create_only(self, installing_path: str, final_path: str) -> None: ...
    def read_file(self, path: str, limit: int) -> CheckedFile: ...
    def list_directory(self, path: str) -> CheckedDirectory: ...


@dataclass(frozen=True, slots=True)
class SourceFile:
    relative_path: str
    data: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class CertifiedMaterial:
    build: D10BuildResult
    manifest: ExecutableManifest
    attestation: DeploymentAttestation
    files: tuple[SourceFile, ...]
    guard_bytes: bytes


@dataclass(frozen=True, slots=True)
class OperationResult:
    transcript: bytes


@dataclass(frozen=True, slots=True)
class SigningIdentity:
    key_id: str
    algorithm: str
    digest_algorithm: str
    signature_encoding: str
    private_key_exportable: bool


@dataclass(frozen=True, slots=True)
class SigningRequest:
    key_id: str
    algorithm: str
    digest_algorithm: str
    signature_encoding: str
    message_sha256: bytes


@dataclass(frozen=True, slots=True)
class DetachedSignature:
    key_id: str
    algorithm: str
    digest_algorithm: str
    signature_encoding: str
    signature: bytes


class ExternalSigner(Protocol):
    """External non-exportable signing port; it accepts no key material."""

    @property
    def identity(self) -> SigningIdentity: ...
    def sign_digest(self, request: SigningRequest) -> DetachedSignature: ...


class SignatureVerifier(Protocol):
    @property
    def key_id(self) -> str: ...
    def verify(self, message: bytes, signature: bytes) -> bool: ...


def _regular_single_link(path: Path) -> bytes:
    try:
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or bool(getattr(before, "st_file_attributes", 0) & REPARSE_ATTRIBUTE)
            or before.st_nlink != 1
        ):
            raise DeploymentBlocked("source_object_type_or_links")
        data = path.read_bytes()
        after = path.lstat()
    except DeploymentBlocked:
        raise
    except OSError:
        raise DeploymentBlocked("source_object_unavailable") from None
    if (
        not stat.S_ISREG(after.st_mode)
        or stat.S_ISLNK(after.st_mode)
        or bool(getattr(after, "st_file_attributes", 0) & REPARSE_ATTRIBUTE)
        or after.st_nlink != 1
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or len(data) != after.st_size
    ):
        raise DeploymentBlocked("source_object_drift")
    return data


def _unsafe_component(component: str) -> bool:
    name = component.casefold()
    return (
        name in {".git", "__pycache__"}
        or name.endswith((".pyc", ".pyo"))
        or name.startswith("python-cache-")
    )


def validate_source_relative_path(value: str) -> str:
    """Require a canonical governed path with no cache or bytecode component."""
    try:
        canonical_relative_path(value)
    except Exception:
        raise DeploymentBlocked("manifest_source_path_invalid") from None
    if any(_unsafe_component(part) for part in value.split("/")):
        raise DeploymentBlocked("manifest_cache_or_git_entry")
    return value


def _inspect_local_package(root: Path, manifest: ExecutableManifest) -> None:
    expected_files = {
        e.relative_path
        for e in manifest.entries
        if e.relative_path.startswith("src/trading_bot/")
    }
    expected_dirs = {"src/trading_bot"}
    for name in expected_files:
        parts = name.split("/")[:-1]
        expected_dirs.update("/".join(parts[:i]) for i in range(2, len(parts) + 1))
    actual_files: set[str] = set()
    actual_dirs: set[str] = set()
    source_root = root / "src" / "trading_bot"
    for current, dirs, files in os.walk(source_root, followlinks=False):
        current_path = Path(current)
        try:
            info = current_path.lstat()
        except OSError:
            raise DeploymentBlocked("source_directory_unavailable") from None
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or bool(getattr(info, "st_file_attributes", 0) & REPARSE_ATTRIBUTE)
        ):
            raise DeploymentBlocked("source_directory_type")
        actual_dirs.add(current_path.relative_to(root).as_posix())
        names = [*dirs, *files]
        if len(names) != len({n.casefold() for n in names}):
            raise DeploymentBlocked("source_case_collision")
        for name in dirs:
            child = current_path / name
            try:
                child_info = child.lstat()
            except OSError:
                raise DeploymentBlocked("source_directory_unavailable") from None
            if _unsafe_component(name):
                raise DeploymentBlocked("source_cache_or_git_entry")
            if (
                not stat.S_ISDIR(child_info.st_mode)
                or stat.S_ISLNK(child_info.st_mode)
                or bool(
                    getattr(child_info, "st_file_attributes", 0) & REPARSE_ATTRIBUTE
                )
            ):
                raise DeploymentBlocked("source_directory_type")
        for name in files:
            if _unsafe_component(name):
                raise DeploymentBlocked("source_cache_or_git_entry")
            child = current_path / name
            data = _regular_single_link(child)
            actual_files.add(child.relative_to(root).as_posix())
            if len(data) > MAX_SOURCE_FILE_BYTES:
                raise DeploymentBlocked("source_file_size_bound")
    if actual_files != expected_files or actual_dirs != expected_dirs:
        raise DeploymentBlocked("source_inventory_differs_from_manifest")


def build_certified_material(
    repository_root: Path,
    *,
    builder: Callable[..., D10BuildResult] | None = None,
) -> CertifiedMaterial:
    """Use existing A123 builder with only the frozen executable identity."""
    if not isinstance(repository_root, Path):
        raise DeploymentBlocked("repository_root_type")
    selected_builder = build_d10_deployment_identity if builder is None else builder
    try:
        built = selected_builder(
            repository_root=repository_root,
            expected_head=CERTIFIED_SOURCE_HEAD,
            expected_tree=CERTIFIED_SOURCE_TREE,
            production_python_version=PRODUCTION_PYTHON_VERSION,
        )
        if (
            built.certified_source_head != CERTIFIED_SOURCE_HEAD
            or built.certified_source_tree != CERTIFIED_SOURCE_TREE
            or _GIT_OID.fullmatch(built.certified_source_head) is None
            or _GIT_OID.fullmatch(built.certified_source_tree) is None
        ):
            raise DeploymentBlocked("certified_identity_mismatch")
        manifest = parse_executable_manifest(built.executable_manifest_bytes)
        attestation = parse_deployment_attestation(
            built.unsigned_deployment_attestation_bytes
        )
        if (
            manifest.canonical_bytes() != built.executable_manifest_bytes
            or attestation.canonical_bytes()
            != built.unsigned_deployment_attestation_bytes
            or manifest.digest != built.executable_manifest_sha256
            or attestation.deployment_id != built.deployment_id
            or attestation.certified_source_head != CERTIFIED_SOURCE_HEAD
            or attestation.certified_source_tree != CERTIFIED_SOURCE_TREE
            or attestation.executable_manifest_sha256 != manifest.digest
            or attestation.executable_file_count != len(manifest.entries)
            or len(manifest.entries) != built.executable_file_count
            or attestation.production_python_version != PRODUCTION_PYTHON_VERSION
        ):
            raise DeploymentBlocked("canonical_builder_output_mismatch")
        total = sum(e.byte_length for e in manifest.entries)
        if (
            len(manifest.entries) > MAX_SOURCE_FILES
            or total > MAX_SOURCE_TOTAL_BYTES
            or any(e.byte_length > MAX_SOURCE_FILE_BYTES for e in manifest.entries)
            or len(built.executable_manifest_bytes) > MAX_MANIFEST_BYTES
            or len(built.unsigned_deployment_attestation_bytes) > MAX_ATTESTATION_BYTES
        ):
            raise DeploymentBlocked("certified_material_size_bound")
        _inspect_local_package(repository_root, manifest)
        files = []
        for entry in manifest.entries:
            parts = entry.relative_path.split("/")
            validate_source_relative_path(entry.relative_path)
            data = _regular_single_link(repository_root.joinpath(*parts))
            digest = hashlib.sha256(data).hexdigest()
            if len(data) != entry.byte_length or digest != entry.sha256:
                raise DeploymentBlocked("source_bytes_differ_from_manifest")
            files.append(SourceFile(entry.relative_path, data, digest))
        guard_bytes = _regular_single_link(
            repository_root.joinpath(*D10_GUARD_RELATIVE_PATH.split("/"))
        )
        if (
            len(guard_bytes) != attestation.launch_guard_byte_length
            or hashlib.sha256(guard_bytes).hexdigest()
            != attestation.launch_guard_sha256
            or not 0 < len(guard_bytes) <= MAX_GUARD_BYTES
            or D10_LAUNCHER_RELATIVE_PATH
            not in {i.relative_path for i in manifest.entries}
        ):
            raise DeploymentBlocked("guard_or_launcher_identity_mismatch")
        return CertifiedMaterial(
            built, manifest, attestation, tuple(files), guard_bytes
        )
    except DeploymentBlocked:
        raise
    except Exception:
        raise DeploymentBlocked("certified_source_or_builder_rejected") from None


def expected_policy(directory: bool) -> tuple[str, bool, tuple[Ace, ...]]:
    return (
        ADMINISTRATORS_SID,
        True,
        (
            Ace(ADMINISTRATORS_SID, FILE_ALL_ACCESS),
            Ace(SYSTEM_SID, FILE_ALL_ACCESS),
            Ace(
                TRADING_SID, TRADING_DIRECTORY_READ if directory else TRADING_FILE_READ
            ),
        ),
    )


def expected_parent_policy() -> tuple[str, bool, tuple[Ace, ...]]:
    return (
        ADMINISTRATORS_SID,
        True,
        (Ace(ADMINISTRATORS_SID, FILE_ALL_ACCESS), Ace(SYSTEM_SID, FILE_ALL_ACCESS)),
    )


def require_parent_native_object(item: NativeObject) -> None:
    owner, protected, aces = expected_parent_policy()
    if (
        type(item) is not NativeObject
        or item.path != D10_PARENT
        or item.final_path != D10_PARENT
        or item.directory is not True
        or item.reparse is not False
        or item.drive_type != 3
        or item.volume_root != "F:\\"
        or item.filesystem != "NTFS"
        or item.owner_sid != owner
        or item.dacl_protected is not protected
        or item.aces != aces
        or item.links != 1
    ):
        raise DeploymentBlocked("d10_parent_policy_mismatch")


def require_native_object(item: NativeObject, path: str, *, directory: bool) -> None:
    if path == D10_PARENT:
        raise DeploymentBlocked("d10_object_path_policy_mismatch")
    owner, protected, aces = expected_policy(directory)
    if (
        type(item) is not NativeObject
        or item.path != path
        or item.final_path != path
        or item.directory is not directory
        or item.reparse is not False
        or item.drive_type != 3
        or item.volume_root != "F:\\"
        or item.filesystem != "NTFS"
        or item.owner_sid != owner
        or item.dacl_protected is not protected
        or item.aces != aces
        or item.links != 1
        or (not directory and (type(item.size) is not int or item.size < 0))
    ):
        raise DeploymentBlocked("native_path_type_acl_or_identity_drift")


def require_file(checked: CheckedFile, path: str, expected: bytes) -> None:
    if type(checked) is not CheckedFile:
        raise DeploymentBlocked("native_file_result_type")
    require_native_object(checked.identity, path, directory=False)
    if (
        checked.stable is not True
        or type(checked.data) is not bytes
        or checked.data != expected
        or checked.identity.size != len(expected)
    ):
        raise DeploymentBlocked("final_bytes_or_identity_reverification_failed")


def require_directory(checked: CheckedDirectory, path: str, children: set[str]) -> None:
    if type(checked) is not CheckedDirectory:
        raise DeploymentBlocked("native_directory_result_type")
    require_native_object(checked.identity, path, directory=True)
    names = checked.children
    if (
        checked.stable is not True
        or type(names) is not tuple
        or len(names) != len(set(names))
        or len(names) != len({n.casefold() for n in names})
        or any(
            not n
            or n in (".", "..")
            or any(c in n for c in ("\\", "/", ":", "\x00"))
            or n.endswith((" ", "."))
            for n in names
        )
        or set(names) != children
    ):
        raise DeploymentBlocked("native_inventory_missing_extra_or_case_collision")


def verify_snapshot(
    backend: DeploymentBackend, root: str, files: tuple[SourceFile, ...]
) -> None:
    dirs: dict[str, set[str]] = {root: set()}
    file_names: dict[str, set[str]] = {}
    for item in files:
        parts = item.relative_path.split("/")
        parent = root
        for part in parts[:-1]:
            dirs.setdefault(parent, set()).add(part)
            parent += "\\" + part
            dirs.setdefault(parent, set())
        file_names.setdefault(parent, set()).add(parts[-1])
    if dirs.get(root) != {"src", "scripts"} or dirs.get(root + r"\src") != {
        "trading_bot"
    }:
        raise DeploymentBlocked("sealed_source_layout_mismatch")
    if file_names.get(root + r"\scripts") != {
        "run_personal_desktop_unattended_one_week_soak.py"
    }:
        raise DeploymentBlocked("sealed_source_launcher_layout_mismatch")
    for directory in sorted(dirs, key=lambda p: (p.count("\\"), p)):
        require_directory(
            backend.list_directory(directory),
            directory,
            dirs[directory] | file_names.get(directory, set()),
        )
    for item in files:
        path = root + "\\" + item.relative_path.replace("/", "\\")
        require_file(backend.read_file(path, max(1, len(item.data))), path, item.data)


def require_parent(backend: DeploymentBackend) -> None:
    checked = backend.list_directory(D10_PARENT)
    if type(checked) is not CheckedDirectory or checked.stable is not True:
        raise DeploymentBlocked("d10_parent_identity_unstable")
    require_parent_native_object(checked.identity)


def verify_provisioned_state(
    backend: DeploymentBackend,
    material: CertifiedMaterial,
    *,
    trust_bytes: tuple[bytes, bytes, bytes] | None = None,
) -> None:
    """Reopen fixed final objects; require exact owner/DACL, inventory, and bytes."""
    require_parent(backend)
    root_children = {"launch-guard.py", "source"}
    if trust_bytes is not None:
        root_children.update(
            {
                "deployment.attestation.json",
                "deployment.attestation.sig",
                "executable-manifest.json",
            }
        )
    require_directory(backend.list_directory(D10_ROOT), D10_ROOT, root_children)
    require_file(
        backend.read_file(D10_GUARD, MAX_GUARD_BYTES), D10_GUARD, material.guard_bytes
    )
    verify_snapshot(backend, D10_SOURCE, material.files)
    for path in (
        D10_GUARD_INSTALLING,
        D10_SOURCE_INSTALLING,
        *TRUST_INSTALLING_PATHS,
        D10_ACTIVATION_LEASE,
        D10_ACTIVATION_LEASE + ".installing",
        D10_ACTIVATION_LEASE + ".tmp",
        D10_CACHE_PREFIX,
    ):
        backend.require_absent(path)
    if trust_bytes is None:
        for path in TRUST_FINAL_PATHS:
            backend.require_absent(path)
    else:
        for path, data in zip(TRUST_FINAL_PATHS, trust_bytes, strict=True):
            require_file(backend.read_file(path, max(1, len(data))), path, data)


def canonical_transcript(payload: dict[str, object]) -> bytes:
    data = (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )
    if len(data) > MAX_TRANSCRIPT_BYTES:
        raise DeploymentBlocked("transcript_size_bound")
    return data


def operation_transcript(
    operation: str,
    material: CertifiedMaterial,
    *,
    paths: tuple[str, ...],
    signature: bytes | None = None,
) -> bytes:
    if operation not in {"P124-2", "P124-3"}:
        raise DeploymentBlocked("transcript_operation_unknown")
    value: dict[str, object] = {
        "schema": "personal-desktop-d10-protected-deployment/v1",
        "operation": operation,
        "status": "PASS",
        "certified_source_head": CERTIFIED_SOURCE_HEAD,
        "certified_source_tree": CERTIFIED_SOURCE_TREE,
        "executable_manifest_sha256": material.manifest.digest,
        "executable_file_count": len(material.files),
        "executable_bytes": sum(len(i.data) for i in material.files),
        "unsigned_attestation_sha256": hashlib.sha256(
            material.attestation.canonical_bytes()
        ).hexdigest(),
        "launch_guard_sha256": hashlib.sha256(material.guard_bytes).hexdigest(),
        "published_paths": list(paths),
        "native_reverification": "PASS",
        "activation_authority": "NONE",
        "scheduler_authority": "NONE",
        "trading_authority": "NONE",
    }
    if signature is not None:
        value.update(
            {
                "signing_key_id": D10_SIGNING_KEY_ID,
                "signature_protocol": {
                    "algorithm": SIGNATURE_ALGORITHM,
                    "hash": SIGNATURE_HASH,
                    "encoding": SIGNATURE_ENCODING,
                },
                "signature_byte_length": len(signature),
                "signature_sha256": hashlib.sha256(signature).hexdigest(),
            }
        )
    return canonical_transcript(value)


def require_signer_identity(identity: SigningIdentity) -> None:
    if (
        type(identity) is not SigningIdentity
        or identity.key_id != D10_SIGNING_KEY_ID
        or identity.algorithm != SIGNATURE_ALGORITHM
        or identity.digest_algorithm != SIGNATURE_HASH
        or identity.signature_encoding != SIGNATURE_ENCODING
        or identity.private_key_exportable is not False
    ):
        raise DeploymentBlocked("signing_identity_or_protocol_mismatch")


def require_signature(signature: bytes) -> None:
    if type(signature) is not bytes or len(signature) != MAX_SIGNATURE_BYTES:
        raise DeploymentBlocked("signature_encoding_or_length_invalid")
    r, s = int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big")
    if not 0 < r < P256_ORDER or not 0 < s < P256_ORDER:
        raise DeploymentBlocked("signature_scalar_noncanonical")


def verify_signature(
    verifier: SignatureVerifier, message: bytes, signature: bytes
) -> None:
    require_signature(signature)
    if getattr(verifier, "key_id", None) != D10_SIGNING_KEY_ID:
        raise DeploymentBlocked("signature_verifier_key_mismatch")
    try:
        valid = verifier.verify(message, signature)
    except Exception:
        raise DeploymentBlocked("detached_signature_verification_failed") from None
    if valid is not True:
        raise DeploymentBlocked("detached_signature_invalid")
