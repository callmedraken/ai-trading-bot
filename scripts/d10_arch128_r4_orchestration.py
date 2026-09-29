"""Architecture-128 R4C inert staging and replacement orchestration.

Importing this module performs no host observation or mutation. All filesystem,
scheduler, signature-verifier, and native-rename boundaries are injected.
"""

from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from scripts import d10_arch128_r3_preflight as r3
from scripts import d10_arch128_r4_replacement as r4
from scripts.build_d10_deployment_identity import (
    D10BuildResult,
    build_d10_deployment_identity,
)
from scripts.d10_protected_deployment import (
    MAX_ATTESTATION_BYTES,
    MAX_GUARD_BYTES,
    MAX_MANIFEST_BYTES,
    MAX_SIGNATURE_BYTES,
    CertifiedMaterial,
    CheckedDirectory,
    CheckedFile,
    DeploymentBlocked,
    NativeObject,
    SourceFile,
    require_directory,
    require_file,
    require_native_object,
    require_parent_native_object,
    validate_source_relative_path,
    verify_signature,
)
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    format_utc_instant,
    parse_activation_lease,
)
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    D10_GUARD_RELATIVE_PATH,
    D10_LAUNCHER_RELATIVE_PATH,
    ExecutableManifest,
    parse_deployment_attestation,
    parse_executable_manifest,
)

PRODUCTION_PYTHON_VERSION = "3.14.3"
R1_SUMMARY_SHA256 = (
    "5a92e432c107bf5b091dc4da7984fb5f361dc570346fd0ed0503240963a27361"
)
R1_MANIFEST_PATH = Path(r4.R1_MATERIAL_ROOT) / "executable-manifest.json"
R1_ATTESTATION_PATH = (
    Path(r4.R1_MATERIAL_ROOT) / "deployment.attestation.unsigned.json"
)
R1_SUMMARY_PATH = Path(r4.R1_MATERIAL_ROOT) / "summary.json"
R2_SIGNATURE_PATH = Path(r4.R2_SIGNING_ROOT) / "deployment.attestation.sig"
R2_SUMMARY_PATH = Path(r4.R2_SIGNING_ROOT) / "summary.json"

_REPARSE_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)


class Reader(Protocol):
    def require_administrator(self) -> None: ...
    def list_directory(self, path: str) -> CheckedDirectory: ...
    def read_file(self, path: str, limit: int) -> CheckedFile: ...
    def absent(self, path: str) -> bool: ...


class Writer(Protocol):
    def require_administrator(self) -> None: ...
    def bind_source_inventory(self, relative_paths: tuple[str, ...]) -> None: ...
    def create_directory(self, path: str) -> None: ...
    def create_file(self, path: str, data: bytes) -> None: ...
    def publish_create_only(self, installing_path: str, final_path: str) -> None: ...


class SignatureVerifier(Protocol):
    @property
    def key_id(self) -> str: ...
    def verify(self, message: bytes, signature: bytes) -> bool: ...


SchedulerRead = Callable[[], dict[str, object]]
RenameCall = Callable[
    [Reader, r4.RenameStep, NativeObject, NativeObject],
    r4.MutationOutcome,
]


@dataclass(frozen=True, slots=True)
class SignedMaterial:
    material: CertifiedMaterial
    signature: bytes


@dataclass(frozen=True, slots=True)
class RootProof:
    root_native: NativeObject
    manifest: ExecutableManifest


@dataclass(frozen=True, slots=True)
class PreStageObservation:
    parent_native: NativeObject
    old_native: NativeObject
    scheduler: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True)
class AdmissionObservation:
    namespace: r4.NamespaceObservation
    facts: r4.AdmissionFacts
    parent_native: NativeObject
    old_native: NativeObject
    new_native: NativeObject
    scheduler: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True)
class PostRenameObservation:
    namespace: r4.NamespaceObservation
    facts: r4.PostRenameFacts
    parent_native: NativeObject
    old_native: NativeObject
    new_native: NativeObject
    scheduler: tuple[tuple[str, object], ...]


def _stable_regular_file(path: Path, limit: int) -> bytes:
    if not isinstance(path, Path) or type(limit) is not int or not 0 < limit:
        raise DeploymentBlocked("arch128_external_file_input_invalid")
    try:
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or bool(getattr(before, "st_file_attributes", 0) & _REPARSE_ATTRIBUTE)
            or before.st_nlink != 1
            or before.st_size > limit
        ):
            raise DeploymentBlocked("arch128_external_file_type_or_bound")
        data = path.read_bytes()
        after = path.lstat()
    except DeploymentBlocked:
        raise
    except OSError:
        raise DeploymentBlocked("arch128_external_file_unavailable") from None
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or len(data) != after.st_size
    ):
        raise DeploymentBlocked("arch128_external_file_drift")
    return data


def _material_from_build(
    repository_root: Path,
    built: D10BuildResult,
) -> CertifiedMaterial:
    identity = r4.NEW_IDENTITY
    manifest = parse_executable_manifest(built.executable_manifest_bytes)
    attestation = parse_deployment_attestation(
        built.unsigned_deployment_attestation_bytes
    )
    if (
        built.certified_source_head != identity.certified_source_head
        or built.certified_source_tree != identity.certified_source_tree
        or built.deployment_id != identity.deployment_id
        or built.executable_manifest_sha256 != identity.manifest_sha256
        or built.executable_file_count != identity.executable_file_count
        or manifest.digest != identity.manifest_sha256
        or len(manifest.entries) != identity.executable_file_count
        or sum(entry.byte_length for entry in manifest.entries)
        != identity.executable_total_bytes
        or hashlib.sha256(attestation.canonical_bytes()).hexdigest()
        != identity.unsigned_attestation_sha256
        or attestation.certified_source_head != identity.certified_source_head
        or attestation.certified_source_tree != identity.certified_source_tree
        or attestation.launch_guard_byte_length != identity.guard_byte_length
        or attestation.launch_guard_sha256 != identity.guard_sha256
    ):
        raise DeploymentBlocked("arch128_e6_builder_identity_drift")

    files: list[SourceFile] = []
    for entry in manifest.entries:
        validate_source_relative_path(entry.relative_path)
        path = repository_root.joinpath(*entry.relative_path.split("/"))
        data = _stable_regular_file(path, max(1, entry.byte_length))
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != entry.byte_length or digest != entry.sha256:
            raise DeploymentBlocked("arch128_e6_source_bytes_drift")
        files.append(SourceFile(entry.relative_path, data, digest))

    guard = _stable_regular_file(
        repository_root.joinpath(*D10_GUARD_RELATIVE_PATH.split("/")),
        MAX_GUARD_BYTES,
    )
    if (
        len(guard) != identity.guard_byte_length
        or hashlib.sha256(guard).hexdigest() != identity.guard_sha256
        or D10_LAUNCHER_RELATIVE_PATH
        not in {entry.relative_path for entry in manifest.entries}
    ):
        raise DeploymentBlocked("arch128_e6_guard_identity_drift")

    return CertifiedMaterial(
        built,
        manifest,
        attestation,
        tuple(files),
        guard,
    )


def load_fixed_signed_material(
    verifier: SignatureVerifier,
    *,
    builder: Callable[..., D10BuildResult] = build_d10_deployment_identity,
) -> SignedMaterial:
    """Rebuild E6 from the fixed byte-exact checkout and bind R1/R2 evidence."""

    repository_root = Path(r4.R1_BYTE_EXACT_WORKTREE)
    built = builder(
        repository_root=repository_root,
        expected_head=r4.NEW_IDENTITY.certified_source_head,
        expected_tree=r4.NEW_IDENTITY.certified_source_tree,
        production_python_version=PRODUCTION_PYTHON_VERSION,
    )
    material = _material_from_build(repository_root, built)

    manifest_bytes = _stable_regular_file(R1_MANIFEST_PATH, MAX_MANIFEST_BYTES)
    attestation_bytes = _stable_regular_file(
        R1_ATTESTATION_PATH,
        MAX_ATTESTATION_BYTES,
    )
    r1_summary = _stable_regular_file(R1_SUMMARY_PATH, 1024 * 1024)
    signature = _stable_regular_file(R2_SIGNATURE_PATH, MAX_SIGNATURE_BYTES)
    r2_summary_bytes = _stable_regular_file(R2_SUMMARY_PATH, 1024 * 1024)

    if (
        manifest_bytes != material.manifest.canonical_bytes()
        or hashlib.sha256(manifest_bytes).hexdigest()
        != r4.NEW_IDENTITY.manifest_sha256
        or attestation_bytes != material.attestation.canonical_bytes()
        or hashlib.sha256(attestation_bytes).hexdigest()
        != r4.NEW_IDENTITY.unsigned_attestation_sha256
        or hashlib.sha256(r1_summary).hexdigest() != R1_SUMMARY_SHA256
        or hashlib.sha256(signature).hexdigest()
        != r4.NEW_IDENTITY.detached_signature_sha256
    ):
        raise DeploymentBlocked("arch128_r1_r2_material_drift")

    try:
        r2_summary = json.loads(r2_summary_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise DeploymentBlocked("arch128_r2_summary_invalid") from None
    if (
        type(r2_summary) is not dict
        or r2_summary.get("schema") != "arch128-r2-signing/v1"
        or r2_summary.get("status") != "PASS"
        or r2_summary.get("deployment_id") != r4.NEW_DEPLOYMENT_ID
        or r2_summary.get("attestation_sha256")
        != r4.NEW_IDENTITY.unsigned_attestation_sha256
        or r2_summary.get("signature_sha256")
        != r4.NEW_IDENTITY.detached_signature_sha256
        or r2_summary.get("signature_byte_length") != 64
        or r2_summary.get("signature_verification") != "PASS"
    ):
        raise DeploymentBlocked("arch128_r2_summary_identity_drift")

    verify_signature(verifier, attestation_bytes, signature)
    return SignedMaterial(material, signature)


def _read_exact(reader: Reader, path: str, limit: int) -> bytes:
    checked = reader.read_file(path, limit)
    if type(checked) is not CheckedFile or type(checked.data) is not bytes:
        raise DeploymentBlocked("arch128_read_result_type")
    require_file(checked, path, checked.data)
    if len(checked.data) > limit:
        raise DeploymentBlocked("arch128_read_bound")
    return checked.data


def _verify_source(
    reader: Reader,
    root: str,
    manifest: ExecutableManifest,
) -> None:
    source_root = root + r"\source"
    directories: dict[str, set[str]] = {source_root: set()}
    for entry in manifest.entries:
        directory = source_root
        parts = entry.relative_path.split("/")
        for component in parts[:-1]:
            directories[directory].add(component)
            directory += "\\" + component
            directories.setdefault(directory, set())
        directories[directory].add(parts[-1])

    for path, children in sorted(directories.items()):
        require_directory(reader.list_directory(path), path, children)

    for entry in manifest.entries:
        path = source_root + "\\" + entry.relative_path.replace("/", "\\")
        data = _read_exact(reader, path, max(1, entry.byte_length))
        if (
            len(data) != entry.byte_length
            or hashlib.sha256(data).hexdigest() != entry.sha256
        ):
            raise DeploymentBlocked("arch128_signed_source_bytes_drift")


def _verify_signed_root(
    reader: Reader,
    verifier: SignatureVerifier,
    root: str,
    identity: r4.DeploymentIdentity,
    extra_children: set[str],
) -> RootProof:
    children = {
        "source",
        "launch-guard.py",
        "deployment.attestation.json",
        "deployment.attestation.sig",
        "executable-manifest.json",
        *extra_children,
    }
    checked_root = reader.list_directory(root)
    require_directory(checked_root, root, children)

    manifest_bytes = _read_exact(
        reader,
        root + r"\executable-manifest.json",
        MAX_MANIFEST_BYTES,
    )
    manifest = parse_executable_manifest(manifest_bytes)
    if (
        hashlib.sha256(manifest_bytes).hexdigest() != identity.manifest_sha256
        or len(manifest.entries) != identity.executable_file_count
        or sum(entry.byte_length for entry in manifest.entries)
        != identity.executable_total_bytes
    ):
        raise DeploymentBlocked("arch128_signed_manifest_identity_drift")

    guard = _read_exact(reader, root + r"\launch-guard.py", MAX_GUARD_BYTES)
    if (
        len(guard) != identity.guard_byte_length
        or hashlib.sha256(guard).hexdigest() != identity.guard_sha256
    ):
        raise DeploymentBlocked("arch128_signed_guard_identity_drift")

    attestation_bytes = _read_exact(
        reader,
        root + r"\deployment.attestation.json",
        MAX_ATTESTATION_BYTES,
    )
    attestation = parse_deployment_attestation(attestation_bytes)
    if (
        hashlib.sha256(attestation_bytes).hexdigest()
        != identity.unsigned_attestation_sha256
        or attestation.deployment_id != identity.deployment_id
        or attestation.certified_source_head != identity.certified_source_head
        or attestation.certified_source_tree != identity.certified_source_tree
        or attestation.executable_manifest_sha256 != manifest.digest
        or attestation.executable_file_count != len(manifest.entries)
        or attestation.launch_guard_sha256 != identity.guard_sha256
        or attestation.launch_guard_byte_length != identity.guard_byte_length
    ):
        raise DeploymentBlocked("arch128_signed_attestation_identity_drift")

    signature = _read_exact(
        reader,
        root + r"\deployment.attestation.sig",
        MAX_SIGNATURE_BYTES,
    )
    if (
        identity.detached_signature_sha256 is not None
        and hashlib.sha256(signature).hexdigest()
        != identity.detached_signature_sha256
    ):
        raise DeploymentBlocked("arch128_signed_signature_digest_drift")
    verify_signature(verifier, attestation_bytes, signature)
    _verify_source(reader, root, manifest)
    return RootProof(checked_root.identity, manifest)


def _verify_old_root(
    reader: Reader,
    verifier: SignatureVerifier,
    root: str,
) -> RootProof:
    if root not in (r4.CANONICAL_PATH, r4.RETIRED_PATH):
        raise DeploymentBlocked("arch128_old_root_unreviewed")
    proof = _verify_signed_root(
        reader,
        verifier,
        root,
        r4.OLD_IDENTITY,
        {"activation.lease.json"},
    )
    lease_bytes = _read_exact(
        reader,
        root + r"\activation.lease.json",
        64 * 1024,
    )
    lease = parse_activation_lease(lease_bytes)
    if (
        hashlib.sha256(lease_bytes).hexdigest() != r4.OLD_LEASE_SHA256
        or lease.deployment_id != r4.OLD_DEPLOYMENT_ID
        or lease.attestation_sha256 != r4.OLD_IDENTITY.unsigned_attestation_sha256
        or lease.certified_source_head != r4.OLD_IDENTITY.certified_source_head
        or lease.certified_source_tree != r4.OLD_IDENTITY.certified_source_tree
        or format_utc_instant(lease.accepted_activation_utc)
        != r4.OLD_ACTIVATION_UTC
        or format_utc_instant(lease.end_utc) != r4.OLD_END_UTC
        or lease.soak_id != r4.OLD_SOAK_ID
    ):
        raise DeploymentBlocked("arch128_old_lease_identity_drift")

    for name in (
        "activation.lease.json.installing",
        "activation.lease.json.tmp",
        "no-pycache",
        "evidence",
    ):
        if reader.absent(root + "\\" + name) is not True:
            raise DeploymentBlocked("arch128_old_unexpected_runtime_object")
    return proof


def _verify_new_root(
    reader: Reader,
    verifier: SignatureVerifier,
    root: str,
) -> RootProof:
    if root not in (r4.STAGING_PATH, r4.CANONICAL_PATH):
        raise DeploymentBlocked("arch128_new_root_unreviewed")
    proof = _verify_signed_root(
        reader,
        verifier,
        root,
        r4.NEW_IDENTITY,
        {"evidence"},
    )
    evidence = reader.list_directory(root + r"\evidence")
    require_directory(evidence, root + r"\evidence", set())

    for name in (
        "activation.lease.json",
        "activation.lease.json.installing",
        "activation.lease.json.tmp",
        "no-pycache",
        "launch-guard.py.installing",
        "source.installing",
        "deployment.attestation.json.installing",
        "deployment.attestation.sig.installing",
        "executable-manifest.json.installing",
    ):
        if reader.absent(root + "\\" + name) is not True:
            raise DeploymentBlocked("arch128_new_unexpected_runtime_object")
    return proof


def _expected_reserved_names(*paths: str) -> set[str]:
    return {path.rsplit("\\", 1)[-1] for path in paths}


def _parent_native(reader: Reader, expected_reserved: set[str]) -> NativeObject:
    checked = reader.list_directory(r4.PARENT_PATH)
    if type(checked) is not CheckedDirectory or checked.stable is not True:
        raise DeploymentBlocked("arch128_parent_unstable")
    require_parent_native_object(checked.identity)
    names = checked.children
    if (
        type(names) is not tuple
        or len(names) != len(set(names))
        or len(names) != len({name.casefold() for name in names})
    ):
        raise DeploymentBlocked("arch128_parent_inventory_invalid")
    reserved = {
        name
        for name in names
        if name.casefold() == "d10"
        or name.casefold().startswith(("d10.", "d10-"))
    }
    if reserved != expected_reserved:
        raise DeploymentBlocked("arch128_reserved_namespace_drift")
    return checked.identity


def _scheduler_exact(read: SchedulerRead) -> tuple[tuple[str, object], ...]:
    expected = r3._expected_scheduler()
    first = read()
    second = read()
    if (
        type(first) is not dict
        or type(second) is not dict
        or first != second
        or set(first) != set(expected)
        or any(
            type(first[key]) is not type(value) or first[key] != value
            for key, value in expected.items()
        )
    ):
        raise DeploymentBlocked("arch128_scheduler_drift")
    return tuple(sorted(first.items()))


def _pre_stage_once(
    reader: Reader,
    verifier: SignatureVerifier,
    scheduler_read: SchedulerRead,
) -> PreStageObservation:
    reader.require_administrator()
    parent = _parent_native(reader, _expected_reserved_names(r4.CANONICAL_PATH))
    if (
        reader.absent(r4.STAGING_PATH) is not True
        or reader.absent(r4.RETIRED_PATH) is not True
        or reader.absent(r4.HISTORICAL_S5R8_RETIRED_PATH) is not True
    ):
        raise DeploymentBlocked("arch128_pre_stage_namespace_not_clean")
    old = _verify_old_root(reader, verifier, r4.CANONICAL_PATH)
    if old.root_native.volume_serial != parent.volume_serial:
        raise DeploymentBlocked("arch128_pre_stage_volume_drift")
    return PreStageObservation(parent, old.root_native, _scheduler_exact(scheduler_read))


def observe_pre_stage(
    reader: Reader,
    verifier: SignatureVerifier,
    scheduler_read: SchedulerRead,
) -> PreStageObservation:
    first = _pre_stage_once(reader, verifier, scheduler_read)
    second = _pre_stage_once(reader, verifier, scheduler_read)
    if first != second:
        raise DeploymentBlocked("arch128_pre_stage_two_read_drift")
    return second


def _ready_once(
    reader: Reader,
    verifier: SignatureVerifier,
    scheduler_read: SchedulerRead,
) -> AdmissionObservation:
    reader.require_administrator()
    parent = _parent_native(
        reader,
        _expected_reserved_names(r4.CANONICAL_PATH, r4.STAGING_PATH),
    )
    if (
        reader.absent(r4.RETIRED_PATH) is not True
        or reader.absent(r4.HISTORICAL_S5R8_RETIRED_PATH) is not True
    ):
        raise DeploymentBlocked("arch128_ready_namespace_conflict")
    old = _verify_old_root(reader, verifier, r4.CANONICAL_PATH)
    new = _verify_new_root(reader, verifier, r4.STAGING_PATH)
    if not (
        old.root_native.volume_serial
        == new.root_native.volume_serial
        == parent.volume_serial
    ):
        raise DeploymentBlocked("arch128_ready_volume_drift")

    namespace = r4.NamespaceObservation(
        r4.RootObservation(r4.CANONICAL_PATH, True, r4.OLD_IDENTITY),
        r4.RootObservation(r4.STAGING_PATH, True, r4.NEW_IDENTITY),
        r4.RootObservation(r4.RETIRED_PATH, False),
        True,
        True,
    )
    facts = r4.AdmissionFacts(*([True] * len(r4.AdmissionFacts.__dataclass_fields__)))
    return AdmissionObservation(
        namespace,
        facts,
        parent,
        old.root_native,
        new.root_native,
        _scheduler_exact(scheduler_read),
    )


def observe_ready(
    reader: Reader,
    verifier: SignatureVerifier,
    scheduler_read: SchedulerRead,
) -> AdmissionObservation:
    first = _ready_once(reader, verifier, scheduler_read)
    second = _ready_once(reader, verifier, scheduler_read)
    if first != second:
        raise DeploymentBlocked("arch128_ready_two_read_drift")
    return second


def _post_once(
    reader: Reader,
    verifier: SignatureVerifier,
    scheduler_read: SchedulerRead,
    state: r4.NamespaceState,
) -> PostRenameObservation:
    reader.require_administrator()
    if reader.absent(r4.HISTORICAL_S5R8_RETIRED_PATH) is not True:
        raise DeploymentBlocked("arch128_historical_retired_reappeared")

    if state is r4.NamespaceState.RETIRED_WINDOW:
        parent = _parent_native(
            reader,
            _expected_reserved_names(r4.STAGING_PATH, r4.RETIRED_PATH),
        )
        if reader.absent(r4.CANONICAL_PATH) is not True:
            raise DeploymentBlocked("arch128_retired_window_canonical_present")
        old = _verify_old_root(reader, verifier, r4.RETIRED_PATH)
        new = _verify_new_root(reader, verifier, r4.STAGING_PATH)
        namespace = r4.NamespaceObservation(
            r4.RootObservation(r4.CANONICAL_PATH, False),
            r4.RootObservation(r4.STAGING_PATH, True, r4.NEW_IDENTITY),
            r4.RootObservation(r4.RETIRED_PATH, True, r4.OLD_IDENTITY),
            True,
            True,
        )
    elif state is r4.NamespaceState.COMPLETE:
        parent = _parent_native(
            reader,
            _expected_reserved_names(r4.CANONICAL_PATH, r4.RETIRED_PATH),
        )
        if reader.absent(r4.STAGING_PATH) is not True:
            raise DeploymentBlocked("arch128_complete_staging_present")
        old = _verify_old_root(reader, verifier, r4.RETIRED_PATH)
        new = _verify_new_root(reader, verifier, r4.CANONICAL_PATH)
        namespace = r4.NamespaceObservation(
            r4.RootObservation(r4.CANONICAL_PATH, True, r4.NEW_IDENTITY),
            r4.RootObservation(r4.STAGING_PATH, False),
            r4.RootObservation(r4.RETIRED_PATH, True, r4.OLD_IDENTITY),
            True,
            True,
        )
    else:
        raise DeploymentBlocked("arch128_post_state_unreviewed")

    if not (
        old.root_native.volume_serial
        == new.root_native.volume_serial
        == parent.volume_serial
    ):
        raise DeploymentBlocked("arch128_post_volume_drift")

    facts = r4.PostRenameFacts(
        *([True] * len(r4.PostRenameFacts.__dataclass_fields__))
    )
    return PostRenameObservation(
        namespace,
        facts,
        parent,
        old.root_native,
        new.root_native,
        _scheduler_exact(scheduler_read),
    )


def observe_post(
    reader: Reader,
    verifier: SignatureVerifier,
    scheduler_read: SchedulerRead,
    state: r4.NamespaceState,
) -> PostRenameObservation:
    first = _post_once(reader, verifier, scheduler_read, state)
    second = _post_once(reader, verifier, scheduler_read, state)
    if first != second:
        raise DeploymentBlocked("arch128_post_two_read_drift")
    return second


def _require_signed_material(signed: SignedMaterial) -> None:
    if (
        type(signed) is not SignedMaterial
        or type(signed.material) is not CertifiedMaterial
    ):
        raise DeploymentBlocked("arch128_signed_material_type")

    material = signed.material
    identity = r4.NEW_IDENTITY
    manifest = material.manifest
    attestation = material.attestation

    if (
        manifest.digest != identity.manifest_sha256
        or len(manifest.entries) != identity.executable_file_count
        or sum(entry.byte_length for entry in manifest.entries)
        != identity.executable_total_bytes
        or len(material.guard_bytes) != identity.guard_byte_length
        or hashlib.sha256(material.guard_bytes).hexdigest()
        != identity.guard_sha256
        or hashlib.sha256(attestation.canonical_bytes()).hexdigest()
        != identity.unsigned_attestation_sha256
        or attestation.deployment_id != identity.deployment_id
        or attestation.certified_source_head != identity.certified_source_head
        or attestation.certified_source_tree != identity.certified_source_tree
        or attestation.executable_manifest_sha256 != manifest.digest
        or attestation.executable_file_count != len(manifest.entries)
        or hashlib.sha256(signed.signature).hexdigest()
        != identity.detached_signature_sha256
        or len(signed.signature) != MAX_SIGNATURE_BYTES
        or tuple(item.relative_path for item in material.files)
        != tuple(entry.relative_path for entry in manifest.entries)
    ):
        raise DeploymentBlocked("arch128_signed_material_identity_drift")

    for item, entry in zip(material.files, manifest.entries, strict=True):
        if (
            type(item.data) is not bytes
            or len(item.data) != entry.byte_length
            or hashlib.sha256(item.data).hexdigest() != entry.sha256
            or item.sha256 != entry.sha256
        ):
            raise DeploymentBlocked("arch128_signed_material_source_drift")


def _write_staging_payload_unchecked(
    signed: SignedMaterial,
    writer: Writer,
) -> None:
    material = signed.material
    writer.require_administrator()
    writer.bind_source_inventory(
        tuple(entry.relative_path for entry in material.manifest.entries)
    )

    root = r4.STAGING_PATH
    installing = root + r"\source.installing"
    writer.create_directory(root)
    writer.create_directory(installing)

    directories: set[str] = set()
    for entry in material.manifest.entries:
        parent = installing
        for component in entry.relative_path.split("/")[:-1]:
            parent += "\\" + component
            directories.add(parent)
    for directory in sorted(
        directories,
        key=lambda value: (value.count("\\"), value),
    ):
        writer.create_directory(directory)

    for item in material.files:
        writer.create_file(
            installing + "\\" + item.relative_path.replace("/", "\\"),
            item.data,
        )
    writer.publish_create_only(installing, root + r"\source")

    writer.create_file(root + r"\launch-guard.py.installing", material.guard_bytes)
    writer.publish_create_only(
        root + r"\launch-guard.py.installing",
        root + r"\launch-guard.py",
    )

    trust = (
        (
            "deployment.attestation.json",
            material.attestation.canonical_bytes(),
        ),
        ("deployment.attestation.sig", signed.signature),
        ("executable-manifest.json", material.manifest.canonical_bytes()),
    )
    for name, data in trust:
        installing_path = root + "\\" + name + ".installing"
        final_path = root + "\\" + name
        writer.create_file(installing_path, data)
        writer.publish_create_only(installing_path, final_path)

    writer.create_directory(r4.NEW_EVIDENCE_ROOT)


def write_staging_payload(
    signed: SignedMaterial,
    writer: Writer,
) -> None:
    _require_signed_material(signed)
    _write_staging_payload_unchecked(signed, writer)

def construct_staging(
    signed: SignedMaterial,
    writer: Writer,
    reader: Reader,
    verifier: SignatureVerifier,
    scheduler_read: SchedulerRead,
    *,
    pre_observer: Callable[
        [Reader, SignatureVerifier, SchedulerRead],
        PreStageObservation,
    ] = observe_pre_stage,
    ready_observer: Callable[
        [Reader, SignatureVerifier, SchedulerRead],
        AdmissionObservation,
    ] = observe_ready,
    payload_writer: Callable[
        [SignedMaterial, Writer],
        None,
    ] = write_staging_payload,
) -> AdmissionObservation:
    _require_signed_material(signed)
    verify_signature(
        verifier,
        signed.material.attestation.canonical_bytes(),
        signed.signature,
    )
    pre = pre_observer(reader, verifier, scheduler_read)
    payload_writer(signed, writer)
    ready = ready_observer(reader, verifier, scheduler_read)
    if ready.scheduler != pre.scheduler:
        raise DeploymentBlocked("arch128_staging_scheduler_drift")
    return ready


class ReplacementSession:
    """Single in-process two-step authority; no retry or rollback path."""

    def __init__(
        self,
        reader: Reader,
        verifier: SignatureVerifier,
        scheduler_read: SchedulerRead,
        admission: AdmissionObservation,
        rename_call: RenameCall,
        *,
        ready_observer: Callable[
            [Reader, SignatureVerifier, SchedulerRead],
            AdmissionObservation,
        ] = observe_ready,
        post_observer: Callable[
            [Reader, SignatureVerifier, SchedulerRead, r4.NamespaceState],
            PostRenameObservation,
        ] = observe_post,
    ) -> None:
        self.reader = reader
        self.verifier = verifier
        self.scheduler_read = scheduler_read
        self.admission = admission
        self.rename_call = rename_call
        self.ready_observer = ready_observer
        self.post_observer = post_observer
        self.result = r4.begin_replacement(admission.namespace, admission.facts)
        self.retired: PostRenameObservation | None = None
        self.stopped = False

    def retire_old(self) -> r4.ReplacementResult:
        if self.stopped or self.result.phase is not r4.Phase.READY_TO_RETIRE_OLD:
            raise DeploymentBlocked("arch128_retire_step_not_ready")
        try:
            fresh = self.ready_observer(
                self.reader,
                self.verifier,
                self.scheduler_read,
            )
        except Exception:
            self.stopped = True
            raise
        if fresh != self.admission:
            self.stopped = True
            raise DeploymentBlocked("arch128_retire_final_admission_drift")

        try:
            outcome = self.rename_call(
                self.reader,
                r4.RenameStep.OLD_TO_RETIRED,
                fresh.old_native,
                fresh.parent_native,
            )
        except Exception:
            outcome = r4.MutationOutcome.INDETERMINATE
        self.result = r4.record_rename(
            self.result,
            r4.RenameStep.OLD_TO_RETIRED,
            outcome,
        )
        if outcome is not r4.MutationOutcome.SUCCESS:
            self.stopped = True
            return self.result

        try:
            retired = self.post_observer(
                self.reader,
                self.verifier,
                self.scheduler_read,
                r4.NamespaceState.RETIRED_WINDOW,
            )
            self.result = r4.confirm_retired_window(
                self.result,
                retired.namespace,
                retired.facts,
            )
            self.retired = retired
        except Exception:
            self.result = r4.fail_post_rename_verification(self.result)
            self.stopped = True
        return self.result

    def publish_new(self) -> r4.ReplacementResult:
        if (
            self.stopped
            or self.retired is None
            or self.result.phase is not r4.Phase.READY_TO_PUBLISH_NEW
        ):
            raise DeploymentBlocked("arch128_publish_step_not_ready")

        try:
            fresh = self.post_observer(
                self.reader,
                self.verifier,
                self.scheduler_read,
                r4.NamespaceState.RETIRED_WINDOW,
            )
        except Exception:
            self.stopped = True
            raise
        if fresh != self.retired:
            self.stopped = True
            raise DeploymentBlocked("arch128_publish_final_admission_drift")

        try:
            outcome = self.rename_call(
                self.reader,
                r4.RenameStep.STAGING_TO_CANONICAL,
                fresh.new_native,
                fresh.parent_native,
            )
        except Exception:
            outcome = r4.MutationOutcome.INDETERMINATE
        self.result = r4.record_rename(
            self.result,
            r4.RenameStep.STAGING_TO_CANONICAL,
            outcome,
        )
        if outcome is not r4.MutationOutcome.SUCCESS:
            self.stopped = True
            return self.result

        try:
            complete = self.post_observer(
                self.reader,
                self.verifier,
                self.scheduler_read,
                r4.NamespaceState.COMPLETE,
            )
            self.result = r4.confirm_complete(
                self.result,
                complete.namespace,
                complete.facts,
            )
        except Exception:
            self.result = r4.fail_post_rename_verification(self.result)
            self.stopped = True
        return self.result
