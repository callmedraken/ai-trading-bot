"""Native admission and fixed mutation primitives for one D10 replacement.

Importing this module performs no host observation. The only scheduler transport
is the reviewed, fixed Architecture-126 COM helper beside this source file.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import ntpath
import os
import re
import struct
import subprocess
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from scripts import d10_protected_replacement as replacement
from scripts.d10_protected_deployment import (
    MAX_ATTESTATION_BYTES,
    MAX_GUARD_BYTES,
    MAX_MANIFEST_BYTES,
    MAX_SIGNATURE_BYTES,
    MAX_SOURCE_FILE_BYTES,
    Ace,
    CertifiedMaterial,
    CheckedDirectory,
    CheckedFile,
    DeploymentBlocked,
    NativeObject,
    build_certified_material,
    require_directory,
    require_native_object,
    require_parent_native_object,
    verify_signature,
)
from scripts.d10_protected_deployment_windows import (
    WindowsCngVerifier,
    WindowsReplacementStagingBackend,
)
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    D10_LAUNCHER_RELATIVE_PATH,
    ExecutableManifest,
    build_deployment_attestation,
    parse_deployment_attestation,
    parse_executable_manifest,
)

POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
SCHEDULER_HELPER = Path(__file__).with_name("d10_p125_d5_scheduler_observe.ps1")
SCHEDULER_SCHEMA = "d5-task-scheduler-com-observation/v1"
LEGACY_D5_XML_SHA256 = (
    "8005373fad791c85776b4a35b662d46e06fec4ea40ac9ebfead9f413715da457"
)
MAX_SCHEDULER_STDOUT = 16 * 1024
MAX_SCHEDULER_STDERR = 256
MAX_XML_BYTES = 1024 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_DELETE = 0x00010000
_READ_CONTROL = 0x00020000
_SYNCHRONIZE = 0x00100000
_FILE_LIST_DIRECTORY = 0x0001
_FILE_ADD_SUBDIRECTORY = 0x0004
_FILE_TRAVERSE = 0x0020
_FILE_READ_ATTRIBUTES = 0x0080
_FILE_SHARE_READ = 0x00000001
_OPEN_EXISTING = 3
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_RENAME_INFO_CLASS = 3

_EXPECTED_SCHEDULER = {
    "task_path": r"\AITradingBot-PD4-UnattendedPaper-v1",
    "principal_sid": "S-1-5-21-1397534616-3988210162-180023805-1009",
    "logon_type": 1,
    "run_level": 0,
    "action_count": 1,
    "action_type": 0,
    "action_path": r"F:\AITradingBot\runtime\python.exe",
    "action_arguments": (
        r'-I "F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts'
        r'\run_personal_desktop_unattended_capture_warmup.py"'
    ),
    "action_working_directory": r"F:\AI\worktrees\ai-trading-bot-personal-desktop",
    "trigger_count": 1,
    "trigger_type": 2,
    "trigger_enabled": True,
    "trigger_start_boundary": "2026-09-15T01:30:00",
    "trigger_days_interval": 1,
    "trigger_random_delay": "",
    "repetition_interval": "",
    "repetition_duration": "",
    "repetition_stop_at_duration_end": False,
    "multiple_instances": 2,
    "disallow_start_if_on_batteries": False,
    "stop_if_going_on_batteries": False,
    "allow_demand_start": True,
    "start_when_available": True,
    "run_only_if_network_available": False,
    "run_only_if_idle": False,
    "enabled": True,
    "hidden": False,
    "wake_to_run": True,
    "execution_time_limit": "PT1H",
    "priority": 7,
    "restart_count": 0,
    "restart_interval": "",
}
_SCHEDULER_FIELDS = frozenset({*_EXPECTED_SCHEDULER, "xml_byte_length", "xml_sha256"})
# Frozen historical P124-5 status for this S5-R8 -> S5-R10 lineage only.
_FROZEN_PRIOR_P1245_LINEAGE = (
    "2fd79986-fb50-5fe4-800a-2d4aa5e7307c",
    "9f3d111b-25bb-5ee4-9abf-f5215a32b826",
    "NOT_RUN_NO_D10_ACTIVATION_OR_SCHEDULER_MUTATION",
)


class AdmissionBlocked(RuntimeError):
    """A closed, sanitized read-only admission failure."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class SchedulerObservation:
    semantics: tuple[tuple[str, object], ...]
    xml_byte_length: int
    xml_sha256: str


def _parse_scheduler_record(data: bytes) -> SchedulerObservation:
    if type(data) is not bytes or not 0 < len(data) <= MAX_SCHEDULER_STDOUT:
        raise AdmissionBlocked("scheduler_transport_size")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeError, ValueError, TypeError):
        raise AdmissionBlocked("scheduler_transport_malformed") from None
    if (
        type(value) is not dict
        or set(value) != {"schema", "status", "first", "second"}
        or value["schema"] != SCHEDULER_SCHEMA
        or value["status"] != "OBSERVED"
    ):
        raise AdmissionBlocked("scheduler_transport_schema")
    first = _scheduler_read(value["first"])
    second = _scheduler_read(value["second"])
    if first != second:
        raise AdmissionBlocked("scheduler_two_read_drift")
    return first


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def _scheduler_read(value: object) -> SchedulerObservation:
    if type(value) is not dict or set(value) != _SCHEDULER_FIELDS:
        raise AdmissionBlocked("scheduler_projection_fields")
    for key, expected in _EXPECTED_SCHEDULER.items():
        observed = value[key]
        if type(observed) is not type(expected) or observed != expected:
            raise AdmissionBlocked("scheduler_semantic_drift")
    length, digest = value["xml_byte_length"], value["xml_sha256"]
    if (
        type(length) is not int
        or not 0 < length <= MAX_XML_BYTES
        or type(digest) is not str
        or _SHA256.fullmatch(digest) is None
    ):
        raise AdmissionBlocked("scheduler_xml_evidence_invalid")
    return SchedulerObservation(
        tuple(sorted(_EXPECTED_SCHEDULER.items())), length, digest
    )


def _observe_d5_scheduler(run: object) -> SchedulerObservation:
    """Invoke only the fixed zero-semantic-argument COM helper and validate it."""
    command = (
        POWERSHELL,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SCHEDULER_HELPER),
    )
    try:
        result = run(command, capture_output=True, check=False, timeout=30)
    except Exception:
        raise AdmissionBlocked("scheduler_transport_unavailable") from None
    if type(result.returncode) is not int or result.returncode != 0:
        raise AdmissionBlocked("scheduler_transport_exit")
    if (
        type(result.stderr) is not bytes
        or len(result.stderr) > MAX_SCHEDULER_STDERR
        or result.stderr
    ):
        raise AdmissionBlocked("scheduler_transport_stderr")
    if type(result.stdout) is not bytes or len(result.stdout) > MAX_SCHEDULER_STDOUT:
        raise AdmissionBlocked("scheduler_transport_type")
    return _parse_scheduler_record(result.stdout)


def observe_d5_scheduler() -> SchedulerObservation:
    """Read the fixed D5 task with the reviewed local COM helper."""
    return _observe_d5_scheduler(_run_scheduler_bounded)


def _run_scheduler_bounded(
    command: tuple[str, ...], *, capture_output: bool, check: bool, timeout: int
) -> subprocess.CompletedProcess[bytes]:
    """Cap both pipes while independently draining them; never accept stdin."""
    if (
        command
        != (
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCHEDULER_HELPER),
        )
        or capture_output is not True
        or check is not False
        or timeout != 30
    ):
        raise AdmissionBlocked("scheduler_transport_options")
    with subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        assert process.stdout is not None and process.stderr is not None
        with ThreadPoolExecutor(max_workers=2) as readers:
            stdout = readers.submit(process.stdout.read, MAX_SCHEDULER_STDOUT + 1)
            stderr = readers.submit(process.stderr.read, MAX_SCHEDULER_STDERR + 1)
            try:
                exit_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise AdmissionBlocked("scheduler_transport_timeout") from None
            return subprocess.CompletedProcess(
                command, exit_code, stdout.result(), stderr.result()
            )


class ReadOnlyNative(Protocol):
    def require_administrator(self) -> None: ...
    def list_directory(self, path: str) -> CheckedDirectory: ...
    def read_file(self, path: str, limit: int) -> CheckedFile: ...
    def absent(self, path: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class AdmissionObservation:
    namespace: replacement.NamespaceObservation
    facts: replacement.AdmissionFacts
    scheduler: SchedulerObservation
    parent_native: NativeObject | None = None
    old_native: NativeObject | None = None
    new_native: NativeObject | None = None


@dataclass(frozen=True, slots=True)
class CleanupObservation:
    state: replacement.CleanupState
    plan: replacement.RetiredCleanupPlan | None = None
    parent_native: NativeObject | None = None
    parent_children: tuple[str, ...] = ()
    scheduler: SchedulerObservation | None = None
    admitted_objects: tuple[NativeObject, ...] = ()


class _RecordingNative:
    """Keep native identity evidence from one complete observation pass."""

    def __init__(self, native: ReadOnlyNative):
        self.native = native
        self.objects: list[NativeObject] = []

    def require_administrator(self) -> None:
        self.native.require_administrator()

    def list_directory(self, path: str) -> CheckedDirectory:
        checked = self.native.list_directory(path)
        if type(checked) is CheckedDirectory and type(checked.identity) is NativeObject:
            self.objects.append(checked.identity)
        return checked

    def read_file(self, path: str, limit: int) -> CheckedFile:
        checked = self.native.read_file(path, limit)
        if type(checked) is CheckedFile and type(checked.identity) is NativeObject:
            self.objects.append(checked.identity)
        return checked

    def absent(self, path: str) -> bool:
        return self.native.absent(path)


def _checked_directory(
    native: ReadOnlyNative, path: str, names: set[str]
) -> NativeObject:
    checked = native.list_directory(path)
    require_directory(checked, path, names)
    return checked.identity


def _checked_file(native: ReadOnlyNative, path: str, limit: int) -> bytes:
    checked = native.read_file(path, limit)
    if type(checked) is not CheckedFile or checked.stable is not True:
        raise AdmissionBlocked("native_file_unstable")
    require_native_object(checked.identity, path, directory=False)
    if (
        type(checked.data) is not bytes
        or len(checked.data) != checked.identity.size
        or len(checked.data) > limit
    ):
        raise AdmissionBlocked("native_file_length_or_identity")
    return checked.data


def _expect_absent(native: ReadOnlyNative, path: str) -> None:
    if native.absent(path) is not True:
        raise AdmissionBlocked("fixed_path_present_or_indeterminate")


def _require_reserved_siblings(names: tuple[str, ...], admitted: set[str]) -> None:
    if any(
        name.casefold().startswith(("d10.replacement-", "d10.retired-"))
        and name not in admitted
        for name in names
    ):
        raise AdmissionBlocked("replacement_reserved_sibling_conflict")


def _snapshot(native: ReadOnlyNative, root: str, manifest: ExecutableManifest) -> int:
    source = root + r"\source"
    directories: dict[str, set[str]] = {source: set()}
    for entry in manifest.entries:
        parts = entry.relative_path.split("/")
        parent = source
        for part in parts[:-1]:
            directories[parent].add(part)
            parent += "\\" + part
            directories.setdefault(parent, set())
        directories[parent].add(parts[-1])
    if directories[source] != {"src", "scripts"}:
        raise AdmissionBlocked("source_layout_invalid")
    serial: int | None = None
    for path in sorted(directories, key=lambda item: (item.count("\\"), item)):
        item = _checked_directory(native, path, directories[path])
        if serial is None:
            serial = item.volume_serial
        elif item.volume_serial != serial:
            raise AdmissionBlocked("native_volume_drift")
    for entry in manifest.entries:
        path = source + "\\" + entry.relative_path.replace("/", "\\")
        checked = native.read_file(path, max(1, entry.byte_length))
        if type(checked) is not CheckedFile or checked.stable is not True:
            raise AdmissionBlocked("source_file_unstable")
        require_native_object(checked.identity, path, directory=False)
        if (
            checked.identity.volume_serial != serial
            or type(checked.data) is not bytes
            or len(checked.data) != entry.byte_length
            or hashlib.sha256(checked.data).hexdigest() != entry.sha256
        ):
            raise AdmissionBlocked("source_manifest_byte_drift")
    if D10_LAUNCHER_RELATIVE_PATH not in {e.relative_path for e in manifest.entries}:
        raise AdmissionBlocked("source_launcher_missing")
    assert serial is not None
    return serial


def _verify_old(
    native: ReadOnlyNative,
    verifier: object,
    root: str = replacement.CANONICAL_PATH,
) -> tuple[ExecutableManifest, int]:
    if root not in (replacement.CANONICAL_PATH, replacement.RETIRED_PATH):
        raise AdmissionBlocked("old_root_path_unreviewed")
    identity = replacement.OLD_IDENTITY
    serial = _checked_directory(
        native,
        root,
        {
            "source",
            "launch-guard.py",
            "deployment.attestation.json",
            "deployment.attestation.sig",
            "executable-manifest.json",
        },
    ).volume_serial
    manifest_bytes = _checked_file(
        native, root + r"\executable-manifest.json", MAX_MANIFEST_BYTES
    )
    if hashlib.sha256(manifest_bytes).hexdigest() != identity.manifest_sha256:
        raise AdmissionBlocked("old_manifest_digest")
    manifest = parse_executable_manifest(manifest_bytes)
    if (
        len(manifest.entries) != identity.executable_file_count
        or sum(e.byte_length for e in manifest.entries)
        != identity.executable_total_bytes
    ):
        raise AdmissionBlocked("old_manifest_count_or_size")
    guard = _checked_file(native, root + r"\launch-guard.py", MAX_GUARD_BYTES)
    if (
        len(guard) != identity.guard_byte_length
        or hashlib.sha256(guard).hexdigest() != identity.guard_sha256
    ):
        raise AdmissionBlocked("old_guard_identity")
    attestation_bytes = _checked_file(
        native, root + r"\deployment.attestation.json", MAX_ATTESTATION_BYTES
    )
    if (
        hashlib.sha256(attestation_bytes).hexdigest()
        != identity.unsigned_attestation_sha256
    ):
        raise AdmissionBlocked("old_attestation_digest")
    attestation = parse_deployment_attestation(attestation_bytes)
    if (
        attestation.deployment_id != identity.deployment_id
        or attestation.executable_manifest_sha256 != manifest.digest
        or attestation.executable_file_count != len(manifest.entries)
        or attestation.launch_guard_sha256 != identity.guard_sha256
        or attestation.launch_guard_byte_length != identity.guard_byte_length
    ):
        raise AdmissionBlocked("old_attestation_identity")
    signature = _checked_file(
        native, root + r"\deployment.attestation.sig", MAX_SIGNATURE_BYTES
    )
    if hashlib.sha256(signature).hexdigest() != identity.detached_signature_sha256:
        raise AdmissionBlocked("old_signature_digest")
    verify_signature(verifier, attestation_bytes, signature)
    if _snapshot(native, root, manifest) != serial:
        raise AdmissionBlocked("old_volume_drift")
    return manifest, serial


def _verify_new(
    native: ReadOnlyNative,
    manifest: ExecutableManifest,
    root: str = replacement.STAGING_PATH,
) -> int:
    if root not in (replacement.CANONICAL_PATH, replacement.STAGING_PATH):
        raise AdmissionBlocked("new_root_path_unreviewed")
    identity = replacement.NEW_IDENTITY
    serial = _checked_directory(
        native, root, {"source", "launch-guard.py"}
    ).volume_serial
    guard = _checked_file(native, root + r"\launch-guard.py", MAX_GUARD_BYTES)
    if (
        len(guard) != identity.guard_byte_length
        or hashlib.sha256(guard).hexdigest() != identity.guard_sha256
    ):
        raise AdmissionBlocked("new_guard_identity")
    expected_attestation = build_deployment_attestation(
        certified_source_head=identity.certified_source_head,
        certified_source_tree=identity.certified_source_tree,
        production_python_version="3.14.3",
        launch_guard_byte_length=identity.guard_byte_length,
        launch_guard_sha256=identity.guard_sha256,
        executable_manifest_sha256=manifest.digest,
        executable_file_count=len(manifest.entries),
    )
    if (
        expected_attestation.deployment_id != identity.deployment_id
        or hashlib.sha256(expected_attestation.canonical_bytes()).hexdigest()
        != identity.unsigned_attestation_sha256
        or _snapshot(native, root, manifest) != serial
    ):
        raise AdmissionBlocked("new_staging_identity")
    for name in (
        "deployment.attestation.json",
        "deployment.attestation.sig",
        "executable-manifest.json",
        "activation.lease.json",
        "activation.lease.json.installing",
        "activation.lease.json.tmp",
        "no-pycache",
    ):
        _expect_absent(native, root + "\\" + name)
    return serial


def _verify_signed_new(
    native: ReadOnlyNative, verifier: object
) -> tuple[ExecutableManifest, int]:
    """Independently prove canonical P124-3 signed S5-R10 trust and source."""
    root = replacement.CANONICAL_PATH
    identity = replacement.NEW_IDENTITY
    serial = _checked_directory(
        native,
        root,
        {
            "source",
            "launch-guard.py",
            "deployment.attestation.json",
            "deployment.attestation.sig",
            "executable-manifest.json",
        },
    ).volume_serial
    manifest_bytes = _checked_file(
        native, root + r"\executable-manifest.json", MAX_MANIFEST_BYTES
    )
    if hashlib.sha256(manifest_bytes).hexdigest() != identity.manifest_sha256:
        raise AdmissionBlocked("signed_canonical_manifest_digest")
    manifest = parse_executable_manifest(manifest_bytes)
    if (
        len(manifest.entries) != identity.executable_file_count
        or sum(entry.byte_length for entry in manifest.entries)
        != identity.executable_total_bytes
    ):
        raise AdmissionBlocked("signed_canonical_manifest_inventory")
    guard = _checked_file(native, root + r"\launch-guard.py", MAX_GUARD_BYTES)
    if (
        len(guard) != identity.guard_byte_length
        or hashlib.sha256(guard).hexdigest() != identity.guard_sha256
    ):
        raise AdmissionBlocked("signed_canonical_guard_identity")
    attestation_bytes = _checked_file(
        native, root + r"\deployment.attestation.json", MAX_ATTESTATION_BYTES
    )
    expected_attestation = build_deployment_attestation(
        certified_source_head=identity.certified_source_head,
        certified_source_tree=identity.certified_source_tree,
        production_python_version="3.14.3",
        launch_guard_byte_length=identity.guard_byte_length,
        launch_guard_sha256=identity.guard_sha256,
        executable_manifest_sha256=manifest.digest,
        executable_file_count=len(manifest.entries),
    )
    if (
        expected_attestation.deployment_id != identity.deployment_id
        or attestation_bytes != expected_attestation.canonical_bytes()
        or hashlib.sha256(attestation_bytes).hexdigest()
        != identity.unsigned_attestation_sha256
    ):
        raise AdmissionBlocked("signed_canonical_attestation_identity")
    signature = _checked_file(
        native, root + r"\deployment.attestation.sig", MAX_SIGNATURE_BYTES
    )
    verify_signature(verifier, attestation_bytes, signature)
    if _snapshot(native, root, manifest) != serial:
        raise AdmissionBlocked("signed_canonical_source_volume")
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
        _expect_absent(native, root + "\\" + name)
    return manifest, serial


def _retired_subset(
    native: ReadOnlyNative, verifier: object, parent_serial: int
) -> tuple[replacement.CleanupState, replacement.RetiredCleanupPlan | None]:
    """Classify only the fixed retired namespace; no observed name becomes a target."""
    root = replacement.RETIRED_PATH
    checked = native.list_directory(root)
    if type(checked) is not CheckedDirectory or checked.stable is not True:
        raise AdmissionBlocked("retired_root_unstable")
    require_native_object(checked.identity, root, directory=True)
    if checked.identity.volume_serial != parent_serial:
        raise AdmissionBlocked("retired_volume_drift")
    fixed = {
        "source",
        "launch-guard.py",
        "deployment.attestation.json",
        "deployment.attestation.sig",
        "executable-manifest.json",
    }
    names = checked.children
    if (
        type(names) is not tuple
        or len(names) != len(set(names))
        or len(names) != len({name.casefold() for name in names})
        or not set(names) <= fixed
    ):
        raise AdmissionBlocked("retired_unexpected_inventory")
    for name in fixed - set(names):
        _expect_absent(native, root + "\\" + name)
    manifest: ExecutableManifest | None = None
    if "executable-manifest.json" in names:
        manifest_bytes = _checked_file(
            native, root + r"\executable-manifest.json", MAX_MANIFEST_BYTES
        )
        if (
            hashlib.sha256(manifest_bytes).hexdigest()
            != replacement.OLD_IDENTITY.manifest_sha256
        ):
            raise AdmissionBlocked("retired_manifest_drift")
        manifest = parse_executable_manifest(manifest_bytes)
        if (
            len(manifest.entries) != replacement.OLD_IDENTITY.executable_file_count
            or sum(e.byte_length for e in manifest.entries)
            != replacement.OLD_IDENTITY.executable_total_bytes
        ):
            raise AdmissionBlocked("retired_manifest_inventory_drift")
    elif "source" in names:
        # The manifest is deleted only after every source file and source dir.
        raise AdmissionBlocked("retired_manifest_missing_with_source")
    for name, limit, digest in (
        ("launch-guard.py", MAX_GUARD_BYTES, replacement.OLD_IDENTITY.guard_sha256),
        (
            "deployment.attestation.json",
            MAX_ATTESTATION_BYTES,
            replacement.OLD_IDENTITY.unsigned_attestation_sha256,
        ),
        (
            "deployment.attestation.sig",
            MAX_SIGNATURE_BYTES,
            replacement.OLD_IDENTITY.detached_signature_sha256,
        ),
    ):
        if (
            name in names
            and hashlib.sha256(
                _checked_file(native, root + "\\" + name, limit)
            ).hexdigest()
            != digest
        ):
            raise AdmissionBlocked("retired_trust_byte_drift")
    if "deployment.attestation.sig" in names and "deployment.attestation.json" in names:
        verify_signature(
            verifier,
            _checked_file(
                native, root + r"\deployment.attestation.json", MAX_ATTESTATION_BYTES
            ),
            _checked_file(
                native, root + r"\deployment.attestation.sig", MAX_SIGNATURE_BYTES
            ),
        )
    source_complete = "source" in names
    if manifest is not None and "source" in names:
        source = root + r"\source"
        directories: dict[str, set[str]] = {source: set()}
        for entry in manifest.entries:
            parts = entry.relative_path.split("/")
            parent = source
            for part in parts[:-1]:
                directories[parent].add(part)
                parent += "\\" + part
                directories.setdefault(parent, set())
            directories[parent].add(parts[-1])
        observed_names: dict[str, tuple[str, ...]] = {}
        for path in sorted(directories, key=lambda item: (item.count("\\"), item)):
            if path != source:
                parent_path = ntpath.dirname(path)
                if ntpath.basename(path) not in observed_names.get(parent_path, ()):
                    _expect_absent(native, path)
                    source_complete = False
                    continue
            directory = native.list_directory(path)
            if type(directory) is not CheckedDirectory or directory.stable is not True:
                raise AdmissionBlocked("retired_source_directory_unstable")
            require_native_object(directory.identity, path, directory=True)
            if (
                directory.identity.volume_serial != parent_serial
                or type(directory.children) is not tuple
                or not set(directory.children) <= directories[path]
                or len(directory.children) != len(set(directory.children))
                or len(directory.children)
                != len({name.casefold() for name in directory.children})
            ):
                raise AdmissionBlocked("retired_source_inventory_conflict")
            observed_names[path] = directory.children
            if set(directory.children) != directories[path]:
                source_complete = False
        for entry in manifest.entries:
            path = source + "\\" + entry.relative_path.replace("/", "\\")
            parent_path = ntpath.dirname(path)
            if ntpath.basename(path) not in observed_names.get(parent_path, ()):
                _expect_absent(native, path)
                source_complete = False
                continue
            checked_file = _checked_file(native, path, max(1, entry.byte_length))
            if (
                len(checked_file) != entry.byte_length
                or hashlib.sha256(checked_file).hexdigest() != entry.sha256
            ):
                raise AdmissionBlocked("retired_source_byte_drift")
    if set(names) != fixed or not source_complete:
        return replacement.CleanupState.PARTIAL_RETIRED, None
    full_manifest, serial = _verify_old(native, verifier, root)
    if serial != parent_serial:
        raise AdmissionBlocked("retired_full_volume_drift")
    attestation = _checked_file(
        native, root + r"\deployment.attestation.json", MAX_ATTESTATION_BYTES
    )
    signature = _checked_file(
        native, root + r"\deployment.attestation.sig", MAX_SIGNATURE_BYTES
    )
    return (
        replacement.CleanupState.FULL_RETIRED,
        replacement.build_retired_cleanup_plan(full_manifest, attestation, signature),
    )


def _cleanup_once(
    native: ReadOnlyNative, verifier: object, scheduler_run: object
) -> CleanupObservation:
    native.require_administrator()
    parent = native.list_directory(replacement.PARENT_PATH)
    if type(parent) is not CheckedDirectory or parent.stable is not True:
        raise AdmissionBlocked("cleanup_parent_unstable")
    require_parent_native_object(parent.identity)
    names = parent.children
    canonical_leaf = ntpath.basename(replacement.CANONICAL_PATH)
    retired_leaf = ntpath.basename(replacement.RETIRED_PATH)
    staging_leaf = ntpath.basename(replacement.STAGING_PATH)
    if (
        type(names) is not tuple
        or len(names) != len(set(names))
        or len(names) != len({name.casefold() for name in names})
        or canonical_leaf not in names
        or staging_leaf in names
    ):
        raise AdmissionBlocked("cleanup_parent_namespace")
    _require_reserved_siblings(
        names, {retired_leaf} if retired_leaf in names else set()
    )
    _expect_absent(native, replacement.STAGING_PATH)
    manifest, canonical_serial = _verify_signed_new(native, verifier)
    if (
        manifest.digest != replacement.NEW_IDENTITY.manifest_sha256
        or canonical_serial != parent.identity.volume_serial
    ):
        raise AdmissionBlocked("cleanup_canonical_volume")
    retired_absent = native.absent(replacement.RETIRED_PATH) is True
    if retired_absent != (retired_leaf not in names):
        raise AdmissionBlocked("cleanup_retired_parent_drift")
    if retired_absent:
        state, plan = replacement.CleanupState.RETIRED_ABSENT, None
    else:
        state, plan = _retired_subset(native, verifier, parent.identity.volume_serial)
    scheduler = _observe_d5_scheduler(scheduler_run)
    final_parent = native.list_directory(replacement.PARENT_PATH)
    if (
        type(final_parent) is not CheckedDirectory
        or final_parent.stable is not True
        or final_parent != parent
    ):
        raise AdmissionBlocked("cleanup_parent_revalidation_drift")
    return CleanupObservation(state, plan, parent.identity, names, scheduler)


def _observe_cleanup(
    native: ReadOnlyNative, verifier: object, scheduler_run: object
) -> CleanupObservation:
    try:
        first_native, second_native = _RecordingNative(native), _RecordingNative(native)
        first = _cleanup_once(first_native, verifier, scheduler_run)
        second = _cleanup_once(second_native, verifier, scheduler_run)
        if first != second or first_native.objects != second_native.objects:
            raise AdmissionBlocked("cleanup_two_read_drift")
        by_path: dict[str, NativeObject] = {}
        for item in second_native.objects:
            if item.path in by_path and item != by_path[item.path]:
                raise AdmissionBlocked("cleanup_intra_read_identity_drift")
            by_path[item.path] = item
        return replace(second, admitted_objects=tuple(second_native.objects))
    except Exception:
        return CleanupObservation(replacement.CleanupState.CONFLICTING)


def _observe_once(
    native: ReadOnlyNative, verifier: object
) -> tuple[replacement.NamespaceObservation, int]:
    native.require_administrator()
    parent = native.list_directory(replacement.PARENT_PATH)
    if type(parent) is not CheckedDirectory or parent.stable is not True:
        raise AdmissionBlocked("parent_unstable")
    require_parent_native_object(parent.identity)
    names = parent.children
    if (
        type(names) is not tuple
        or len(names) != len(set(names))
        or len(names) != len({name.casefold() for name in names})
        or replacement.CANONICAL_PATH.rsplit("\\", 1)[-1] not in names
        or replacement.STAGING_PATH.rsplit("\\", 1)[-1] not in names
        or replacement.RETIRED_PATH.rsplit("\\", 1)[-1] in names
    ):
        raise AdmissionBlocked("replacement_parent_namespace")
    _require_reserved_siblings(names, {replacement.STAGING_PATH.rsplit("\\", 1)[-1]})
    _expect_absent(native, replacement.RETIRED_PATH)
    manifest, old_serial = _verify_old(native, verifier)
    new_serial = _verify_new(native, manifest)
    if old_serial != new_serial or old_serial != parent.identity.volume_serial:
        raise AdmissionBlocked("replacement_volume_mismatch")
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
        _expect_absent(native, replacement.CANONICAL_PATH + "\\" + name)
    return (
        replacement.NamespaceObservation(
            replacement.RootObservation(
                replacement.CANONICAL_PATH, True, replacement.OLD_IDENTITY
            ),
            replacement.RootObservation(
                replacement.STAGING_PATH, True, replacement.NEW_IDENTITY
            ),
            replacement.RootObservation(replacement.RETIRED_PATH, False),
            unexpected_reserved_names_absent=True,
        ),
        old_serial,
    )


def _observe_admission(
    native: ReadOnlyNative, verifier: object, scheduler_run: object
) -> AdmissionObservation:
    """Test seam for two complete fresh read-only observations."""
    try:
        first_native = _RecordingNative(native)
        first, serial = _observe_once(first_native, verifier)
        scheduler_first = _observe_d5_scheduler(scheduler_run)
        second_native = _RecordingNative(native)
        second, second_serial = _observe_once(second_native, verifier)
        scheduler_second = _observe_d5_scheduler(scheduler_run)
        if (
            first != second
            or serial != second_serial
            or first_native.objects != second_native.objects
            or scheduler_first != scheduler_second
            or any(item.volume_serial != serial for item in second_native.objects)
        ):
            raise AdmissionBlocked("admission_revalidation_drift")
    except AdmissionBlocked:
        raise
    except Exception:
        raise AdmissionBlocked("admission_observation_failed") from None
    old_exact = (
        second.canonical.present is True
        and second.canonical.identity == replacement.OLD_IDENTITY
    )
    new_exact = (
        second.staging.present is True
        and second.staging.identity == replacement.NEW_IDENTITY
    )
    scheduler_exact = dict(scheduler_second.semantics) == _EXPECTED_SCHEDULER
    lineage_exact = _FROZEN_PRIOR_P1245_LINEAGE == (
        replacement.OLD_DEPLOYMENT_ID,
        replacement.NEW_DEPLOYMENT_ID,
        "NOT_RUN_NO_D10_ACTIVATION_OR_SCHEDULER_MUTATION",
    )
    # The two completed observations above independently checked every native
    # policy, absence, volume, scheduler, and identity predicate before this point.
    facts = replacement.AdmissionFacts(
        administrator_exact=True,
        protected_parent_exact=True,
        old_canonical_exact=old_exact,
        new_staging_exact=new_exact,
        activation_and_cache_absent=True,
        unexpected_reserved_names_absent=True,
        d5_capture_only_scheduler_exact=scheduler_exact,
        no_prior_d10_activation_or_scheduler_mutation=(
            lineage_exact and old_exact and scheduler_exact
        ),
        same_local_ntfs_volume=True,
        staging_verified_before_old_mutation=new_exact,
        final_revalidation_complete=True,
    )
    if not facts.all_exact():
        raise AdmissionBlocked("admission_facts_incomplete")
    by_path = {item.path: item for item in second_native.objects}
    return AdmissionObservation(
        second,
        facts,
        scheduler_second,
        by_path.get(replacement.PARENT_PATH),
        by_path.get(replacement.CANONICAL_PATH),
        by_path.get(replacement.STAGING_PATH),
    )


def observe_admission() -> AdmissionObservation:
    """Observe fixed native paths and Task Scheduler; accept no caller evidence."""
    return _observe_admission(
        _WindowsReplacementReader(), WindowsCngVerifier(), _run_scheduler_bounded
    )


def _unobserved_namespace() -> replacement.NamespaceObservation:
    return replacement.NamespaceObservation(
        replacement.RootObservation(replacement.CANONICAL_PATH, None),
        replacement.RootObservation(replacement.STAGING_PATH, None),
        replacement.RootObservation(replacement.RETIRED_PATH, None),
        unexpected_reserved_names_absent=False,
    )


def _namespace_once(
    native: ReadOnlyNative, verifier: object
) -> tuple[replacement.NamespaceObservation, int | None]:
    native.require_administrator()
    parent = native.list_directory(replacement.PARENT_PATH)
    if type(parent) is not CheckedDirectory or parent.stable is not True:
        raise AdmissionBlocked("namespace_parent_unstable")
    require_parent_native_object(parent.identity)
    names = parent.children
    fixed_names = {
        replacement.CANONICAL_PATH.rsplit("\\", 1)[-1],
        replacement.STAGING_PATH.rsplit("\\", 1)[-1],
        replacement.RETIRED_PATH.rsplit("\\", 1)[-1],
    }
    names_exact = (
        type(names) is tuple
        and all(type(name) is str for name in names)
        and len(names) == len(set(names))
        and len(names) == len({name.casefold() for name in names})
    )
    if not names_exact:
        raise AdmissionBlocked("namespace_parent_inventory_invalid")
    reserved_names_exact = not any(
        name.casefold().startswith(("d10.replacement-", "d10.retired-"))
        and name not in fixed_names
        for name in names
    ) and all(
        name == fixed
        for name in names
        for fixed in fixed_names
        if name.casefold() == fixed.casefold()
    )
    paths = (
        replacement.CANONICAL_PATH,
        replacement.STAGING_PATH,
        replacement.RETIRED_PATH,
    )
    present: dict[str, bool] = {}
    for path in paths:
        absent = native.absent(path)
        if type(absent) is not bool:
            raise AdmissionBlocked("namespace_root_presence_indeterminate")
        is_present = not absent
        listed = path.rsplit("\\", 1)[-1] in names
        if listed is not is_present:
            raise AdmissionBlocked("namespace_parent_root_drift")
        present[path] = is_present

    old_manifest: ExecutableManifest | None = None
    old_path: str | None = None
    old_serial: int | None = None
    for path in (replacement.CANONICAL_PATH, replacement.RETIRED_PATH):
        if not present[path]:
            continue
        try:
            candidate, serial = _verify_old(native, verifier, path)
        except (AdmissionBlocked, DeploymentBlocked):
            continue
        if serial != parent.identity.volume_serial:
            continue
        old_manifest, old_path, old_serial = candidate, path, serial
        break

    roots: dict[str, replacement.RootObservation] = {}
    for path in paths:
        if not present[path]:
            roots[path] = replacement.RootObservation(path, False)
            continue
        if path == old_path:
            roots[path] = replacement.RootObservation(
                path, True, replacement.OLD_IDENTITY
            )
            continue
        identity = None
        if old_manifest is not None and path in (
            replacement.CANONICAL_PATH,
            replacement.STAGING_PATH,
        ):
            try:
                serial = _verify_new(native, old_manifest, path)
            except (AdmissionBlocked, DeploymentBlocked):
                pass
            else:
                if serial == old_serial == parent.identity.volume_serial:
                    identity = replacement.NEW_IDENTITY
        roots[path] = replacement.RootObservation(path, True, identity)
    return (
        replacement.NamespaceObservation(
            roots[replacement.CANONICAL_PATH],
            roots[replacement.STAGING_PATH],
            roots[replacement.RETIRED_PATH],
            unexpected_reserved_names_absent=reserved_names_exact,
        ),
        old_serial,
    )


def _observe_namespace(
    native: ReadOnlyNative, verifier: object
) -> replacement.NamespaceObservation:
    """Return only two matching, complete fixed-path namespace observations."""
    try:
        first_native = _RecordingNative(native)
        first, first_serial = _namespace_once(first_native, verifier)
        second_native = _RecordingNative(native)
        second, second_serial = _namespace_once(second_native, verifier)
        if (
            first != second
            or first_serial != second_serial
            or first_native.objects != second_native.objects
        ):
            return _unobserved_namespace()
        return second
    except Exception:
        return _unobserved_namespace()


def observe_namespace() -> replacement.NamespaceObservation:
    """Classify the fixed namespace using only stable native read operations."""
    return _observe_namespace(_WindowsReplacementReader(), WindowsCngVerifier())


def _post_publication_once(
    native: ReadOnlyNative,
    verifier: object,
    scheduler_run: object,
    admission: AdmissionObservation,
) -> tuple[
    replacement.NamespaceObservation,
    replacement.PostPublicationFacts,
    SchedulerObservation,
]:
    native.require_administrator()
    parent = native.list_directory(replacement.PARENT_PATH)
    if type(parent) is not CheckedDirectory or parent.stable is not True:
        raise AdmissionBlocked("post_parent_unstable")
    require_parent_native_object(parent.identity)
    names = parent.children
    if (
        type(names) is not tuple
        or any(type(name) is not str for name in names)
        or len(names) != len(set(names))
        or len(names) != len({name.casefold() for name in names})
    ):
        raise AdmissionBlocked("post_parent_inventory_invalid")
    canonical_leaf = replacement.CANONICAL_PATH.rsplit("\\", 1)[-1]
    staging_leaf = replacement.STAGING_PATH.rsplit("\\", 1)[-1]
    retired_leaf = replacement.RETIRED_PATH.rsplit("\\", 1)[-1]
    reserved_names_exact = (
        canonical_leaf in names
        and retired_leaf in names
        and staging_leaf not in names
        and not any(
            name.casefold().startswith(("d10.replacement-", "d10.retired-"))
            and name != retired_leaf
            for name in names
        )
        and all(
            name == fixed
            for name in names
            for fixed in (canonical_leaf, staging_leaf, retired_leaf)
            if name.casefold() == fixed.casefold()
        )
    )

    staging_absent = native.absent(replacement.STAGING_PATH) is True
    if not staging_absent:
        raise AdmissionBlocked("post_staging_present")
    manifest, retired_serial = _verify_old(native, verifier, replacement.RETIRED_PATH)
    canonical_serial = _verify_new(native, manifest, replacement.CANONICAL_PATH)
    trust_paths = tuple(
        replacement.CANONICAL_PATH + "\\" + name
        for name in (
            "deployment.attestation.json",
            "deployment.attestation.sig",
            "executable-manifest.json",
            "deployment.attestation.json.installing",
            "deployment.attestation.sig.installing",
            "executable-manifest.json.installing",
        )
    )
    lease_cache_paths = tuple(
        replacement.CANONICAL_PATH + "\\" + name
        for name in (
            "activation.lease.json",
            "activation.lease.json.installing",
            "activation.lease.json.tmp",
            "no-pycache",
        )
    )
    canonical_trust_absent = all(native.absent(path) is True for path in trust_paths)
    activation_and_cache_absent = all(
        native.absent(path) is True for path in lease_cache_paths
    )
    scheduler = _observe_d5_scheduler(scheduler_run)

    result = _post_publication_result(
        native,
        admission,
        parent.identity,
        names,
        retired_serial,
        canonical_serial,
        canonical_trust_absent,
        activation_and_cache_absent,
        scheduler,
        reserved_names_exact,
    )
    final_parent = native.list_directory(replacement.PARENT_PATH)
    if (
        type(final_parent) is not CheckedDirectory
        or final_parent.stable is not True
        or final_parent.identity != parent.identity
        or final_parent.children != names
    ):
        raise AdmissionBlocked("post_parent_revalidation_drift")
    return result


def _post_publication_result(
    native: ReadOnlyNative,
    admission: AdmissionObservation,
    parent_identity: NativeObject,
    names: tuple[str, ...],
    retired_serial: int,
    canonical_serial: int,
    canonical_trust_absent: bool,
    activation_and_cache_absent: bool,
    scheduler: SchedulerObservation,
    reserved_names_exact: bool,
) -> tuple[
    replacement.NamespaceObservation,
    replacement.PostPublicationFacts,
    SchedulerObservation,
]:
    if not reserved_names_exact:
        _require_reserved_siblings(
            names, {replacement.RETIRED_PATH.rsplit("\\", 1)[-1]}
        )
    canonical = native.list_directory(replacement.CANONICAL_PATH)
    retired = native.list_directory(replacement.RETIRED_PATH)
    if (
        type(canonical) is not CheckedDirectory
        or canonical.stable is not True
        or type(retired) is not CheckedDirectory
        or retired.stable is not True
    ):
        raise AdmissionBlocked("post_root_identity_unstable")
    expected_new = replace(
        admission.new_native,
        path=replacement.CANONICAL_PATH,
        final_path=replacement.CANONICAL_PATH,
    )
    expected_old = replace(
        admission.old_native,
        path=replacement.RETIRED_PATH,
        final_path=replacement.RETIRED_PATH,
    )
    new_exact = canonical.identity == expected_new
    old_exact = retired.identity == expected_old
    same_volume = (
        parent_identity.volume_serial
        == canonical.identity.volume_serial
        == retired.identity.volume_serial
        and parent_identity.volume_root
        == canonical.identity.volume_root
        == retired.identity.volume_root
        and parent_identity.filesystem
        == canonical.identity.filesystem
        == retired.identity.filesystem
        == "NTFS"
        and parent_identity.drive_type
        == canonical.identity.drive_type
        == retired.identity.drive_type
        == 3
    )
    parent_exact = parent_identity == admission.parent_native
    new_exact = new_exact and canonical_serial == parent_identity.volume_serial
    old_exact = old_exact and retired_serial == parent_identity.volume_serial
    scheduler_exact = dict(scheduler.semantics) == _EXPECTED_SCHEDULER
    namespace = replacement.NamespaceObservation(
        replacement.RootObservation(
            replacement.CANONICAL_PATH,
            True,
            replacement.NEW_IDENTITY if new_exact else None,
        ),
        replacement.RootObservation(replacement.STAGING_PATH, False),
        replacement.RootObservation(
            replacement.RETIRED_PATH,
            True,
            replacement.OLD_IDENTITY if old_exact else None,
        ),
        unexpected_reserved_names_absent=reserved_names_exact,
    )
    facts = replacement.PostPublicationFacts(
        new_canonical_exact=new_exact,
        staging_absent=True,
        old_retired_exact=old_exact,
        canonical_trust_absent=canonical_trust_absent,
        activation_and_cache_absent=activation_and_cache_absent,
        d5_capture_only_scheduler_exact=scheduler_exact,
        protected_parent_exact=parent_exact,
        same_local_ntfs_volume=same_volume,
        unexpected_reserved_names_absent=reserved_names_exact,
    )
    return namespace, facts, scheduler


def _false_post_publication() -> tuple[
    replacement.NamespaceObservation, replacement.PostPublicationFacts
]:
    return (
        _unobserved_namespace(),
        replacement.PostPublicationFacts(
            new_canonical_exact=False,
            staging_absent=False,
            old_retired_exact=False,
            canonical_trust_absent=False,
            activation_and_cache_absent=False,
            d5_capture_only_scheduler_exact=False,
            protected_parent_exact=False,
            same_local_ntfs_volume=False,
            unexpected_reserved_names_absent=False,
        ),
    )


def _observe_post_publication(
    native: ReadOnlyNative,
    verifier: object,
    scheduler_run: object,
    admission: AdmissionObservation,
) -> tuple[
    replacement.NamespaceObservation,
    replacement.PostPublicationFacts,
]:
    try:
        first_native = _RecordingNative(native)
        first = _post_publication_once(first_native, verifier, scheduler_run, admission)
        second_native = _RecordingNative(native)
        second = _post_publication_once(
            second_native, verifier, scheduler_run, admission
        )
        if first != second or first_native.objects != second_native.objects:
            raise AdmissionBlocked("post_publication_revalidation_drift")
        return second[0], second[1]
    except Exception:
        return _false_post_publication()


def observe_post_publication(
    admission: AdmissionObservation,
) -> tuple[replacement.NamespaceObservation, replacement.PostPublicationFacts]:
    """Independently reobserve every fixed post-publication fact twice."""
    if type(admission) is not AdmissionObservation:
        return _false_post_publication()
    return _observe_post_publication(
        _WindowsReplacementReader(),
        WindowsCngVerifier(),
        _run_scheduler_bounded,
        admission,
    )


def _require_s5_r10_material(material: CertifiedMaterial) -> None:
    identity = replacement.NEW_IDENTITY
    if type(material) is not CertifiedMaterial:
        raise AdmissionBlocked("staging_material_type")
    manifest = material.manifest
    attestation = material.attestation
    if (
        manifest.digest != identity.manifest_sha256
        or len(manifest.entries) != identity.executable_file_count
        or sum(entry.byte_length for entry in manifest.entries)
        != identity.executable_total_bytes
        or len(material.guard_bytes) != identity.guard_byte_length
        or hashlib.sha256(material.guard_bytes).hexdigest() != identity.guard_sha256
        or attestation.deployment_id != identity.deployment_id
        or attestation.certified_source_head != identity.certified_source_head
        or attestation.certified_source_tree != identity.certified_source_tree
        or attestation.executable_manifest_sha256 != manifest.digest
        or attestation.executable_file_count != len(manifest.entries)
        or attestation.launch_guard_byte_length != len(material.guard_bytes)
        or attestation.launch_guard_sha256 != identity.guard_sha256
        or hashlib.sha256(attestation.canonical_bytes()).hexdigest()
        != identity.unsigned_attestation_sha256
        or tuple(item.relative_path for item in material.files)
        != tuple(entry.relative_path for entry in manifest.entries)
    ):
        raise AdmissionBlocked("staging_material_identity")
    for item, entry in zip(material.files, manifest.entries, strict=True):
        if (
            type(item.data) is not bytes
            or len(item.data) != entry.byte_length
            or hashlib.sha256(item.data).hexdigest() != entry.sha256
            or item.sha256 != entry.sha256
        ):
            raise AdmissionBlocked("staging_material_bytes")


def _construct_fixed_staging(
    material: CertifiedMaterial,
    writer: WindowsReplacementStagingBackend,
    reader: ReadOnlyNative,
    verifier: object,
    scheduler_run: object,
) -> None:
    """Test seam; create only the fixed inert S5-R10 staging payload."""
    _require_s5_r10_material(material)
    try:
        reader.require_administrator()
        parent = reader.list_directory(replacement.PARENT_PATH)
        if type(parent) is not CheckedDirectory or parent.stable is not True:
            raise AdmissionBlocked("staging_parent_unstable")
        require_parent_native_object(parent.identity)
        names = parent.children
        if (
            type(names) is not tuple
            or len(names) != len(set(names))
            or len(names) != len({name.casefold() for name in names})
            or replacement.CANONICAL_PATH.rsplit("\\", 1)[-1] not in names
            or replacement.STAGING_PATH.rsplit("\\", 1)[-1] in names
            or replacement.RETIRED_PATH.rsplit("\\", 1)[-1] in names
        ):
            raise AdmissionBlocked("staging_namespace_conflict")
        _require_reserved_siblings(names, set())
        _expect_absent(reader, replacement.STAGING_PATH)
        _expect_absent(reader, replacement.RETIRED_PATH)
        old_manifest, old_serial = _verify_old(reader, verifier)
        if (
            old_manifest.digest != material.manifest.digest
            or old_serial != parent.identity.volume_serial
            or _FROZEN_PRIOR_P1245_LINEAGE
            != (
                replacement.OLD_DEPLOYMENT_ID,
                replacement.NEW_DEPLOYMENT_ID,
                "NOT_RUN_NO_D10_ACTIVATION_OR_SCHEDULER_MUTATION",
            )
        ):
            raise AdmissionBlocked("staging_old_lineage_or_volume")
        for name in (
            "activation.lease.json",
            "activation.lease.json.installing",
            "activation.lease.json.tmp",
            "no-pycache",
        ):
            _expect_absent(reader, replacement.CANONICAL_PATH + "\\" + name)
        scheduler = _observe_d5_scheduler(scheduler_run)
        writer.bind_source_inventory(
            tuple(entry.relative_path for entry in material.manifest.entries)
        )
        root = replacement.STAGING_PATH
        installing = root + r"\source.installing"
        writer.create_directory(root)
        writer.create_directory(installing)
        directories: set[str] = set()
        for entry in material.manifest.entries:
            parent_path = installing
            for component in entry.relative_path.split("/")[:-1]:
                parent_path += "\\" + component
                directories.add(parent_path)
        for directory in sorted(directories, key=lambda path: (path.count("\\"), path)):
            writer.create_directory(directory)
        for item in material.files:
            writer.create_file(
                installing + "\\" + item.relative_path.replace("/", "\\"),
                item.data,
            )
        writer.publish_create_only(installing, root + r"\source")
        writer.create_file(root + r"\launch-guard.py.installing", material.guard_bytes)
        writer.publish_create_only(
            root + r"\launch-guard.py.installing", root + r"\launch-guard.py"
        )
        if _verify_new(reader, material.manifest) != old_serial:
            raise AdmissionBlocked("staging_volume_drift")
        final_parent = reader.list_directory(replacement.PARENT_PATH)
        if (
            type(final_parent) is not CheckedDirectory
            or final_parent.stable is not True
            or final_parent.identity != parent.identity
            or replacement.STAGING_PATH.rsplit("\\", 1)[-1] not in final_parent.children
            or _observe_d5_scheduler(scheduler_run) != scheduler
        ):
            raise AdmissionBlocked("staging_postverification_drift")
        _require_reserved_siblings(
            final_parent.children, {replacement.STAGING_PATH.rsplit("\\", 1)[-1]}
        )
    except (AdmissionBlocked, DeploymentBlocked):
        raise
    except Exception:
        raise AdmissionBlocked("staging_native_indeterminate") from None


def construct_fixed_staging(repository_root: Path) -> None:
    """Build exact certified bytes, then create and reverify fixed staging."""
    material = build_certified_material(repository_root)
    _construct_fixed_staging(
        material,
        WindowsReplacementStagingBackend(),
        _WindowsReplacementReader(),
        WindowsCngVerifier(),
        _run_scheduler_bounded,
    )


class _ByHandleInfo(ctypes.Structure):
    _fields_ = [
        ("attributes", wintypes.DWORD),
        ("creation_low", wintypes.DWORD),
        ("creation_high", wintypes.DWORD),
        ("access_low", wintypes.DWORD),
        ("access_high", wintypes.DWORD),
        ("write_low", wintypes.DWORD),
        ("write_high", wintypes.DWORD),
        ("volume_serial", wintypes.DWORD),
        ("size_high", wintypes.DWORD),
        ("size_low", wintypes.DWORD),
        ("links", wintypes.DWORD),
        ("file_index_high", wintypes.DWORD),
        ("file_index_low", wintypes.DWORD),
    ]


class _AclSize(ctypes.Structure):
    _fields_ = [
        ("ace_count", wintypes.DWORD),
        ("bytes_used", wintypes.DWORD),
        ("bytes_free", wintypes.DWORD),
    ]


class _AceHeader(ctypes.Structure):
    _fields_ = [
        ("kind", ctypes.c_ubyte),
        ("flags", ctypes.c_ubyte),
        ("size", wintypes.WORD),
    ]


class _AccessAce(ctypes.Structure):
    _fields_ = [
        ("header", _AceHeader),
        ("mask", wintypes.DWORD),
        ("sid_start", wintypes.DWORD),
    ]


class _FindData(ctypes.Structure):
    _fields_ = [
        ("attributes", wintypes.DWORD),
        ("creation", wintypes.FILETIME),
        ("access", wintypes.FILETIME),
        ("write", wintypes.FILETIME),
        ("size_high", wintypes.DWORD),
        ("size_low", wintypes.DWORD),
        ("reserved0", wintypes.DWORD),
        ("reserved1", wintypes.DWORD),
        ("name", ctypes.c_wchar * 260),
        ("alternate", ctypes.c_wchar * 14),
        ("file_type", wintypes.DWORD),
        ("creator_type", wintypes.DWORD),
        ("finder_flags", wintypes.WORD),
    ]


class _WindowsReplacementReader:
    """Native no-follow reader with only fixed replacement namespace admission."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise AdmissionBlocked("windows_native_required")
        try:
            self._kernel = ctypes.WinDLL(
                r"C:\Windows\System32\kernel32.dll", use_last_error=True
            )
            self._advapi = ctypes.WinDLL(
                r"C:\Windows\System32\advapi32.dll", use_last_error=True
            )
        except Exception:
            raise AdmissionBlocked("windows_native_unavailable") from None

    @staticmethod
    def _bind(library: object, name: str, args: list[object], result: object):
        function = getattr(library, name)
        function.argtypes = args
        function.restype = result
        return function

    @staticmethod
    def _allowed(path: str, *, directory: bool | None) -> bool:
        if type(path) is not str or ntpath.normpath(path) != path:
            return False
        if path == replacement.PARENT_PATH:
            return directory is True
        for root in (
            replacement.CANONICAL_PATH,
            replacement.STAGING_PATH,
            replacement.RETIRED_PATH,
        ):
            if path == root:
                return directory in (True, None)
            if not path.startswith(root + "\\"):
                continue
            relative = path[len(root) + 1 :]
            if relative == "source":
                return directory is True
            if relative.startswith("source\\"):
                source_relative = relative[len("source\\") :]
                parts = source_relative.split("\\")
                return (
                    all(
                        part
                        and part not in (".", "..")
                        and not part.endswith((" ", "."))
                        for part in parts
                    )
                    and parts[0] in ("src", "scripts")
                    and not any(":" in part or "/" in part for part in parts)
                    and directory in (True, False)
                )
            allowed_names = {
                "launch-guard.py",
                "deployment.attestation.json",
                "deployment.attestation.sig",
                "executable-manifest.json",
                "activation.lease.json",
                "activation.lease.json.installing",
                "activation.lease.json.tmp",
                "no-pycache",
                "launch-guard.py.installing",
                "source.installing",
                "deployment.attestation.json.installing",
                "deployment.attestation.sig.installing",
                "executable-manifest.json.installing",
            }
            return relative in allowed_names and directory in (False, None)
        return False

    def require_administrator(self) -> None:
        primary = wintypes.HANDLE()
        duplicate = wintypes.HANDLE()
        sid = ctypes.c_void_p()
        try:
            get_process = self._bind(
                self._kernel, "GetCurrentProcess", [], wintypes.HANDLE
            )
            open_token = self._bind(
                self._advapi,
                "OpenProcessToken",
                [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)],
                wintypes.BOOL,
            )
            if (
                not open_token(get_process(), 0x0008 | 0x0002, ctypes.byref(primary))
                or not primary.value
            ):
                raise AdmissionBlocked("administrator_token_unavailable")
            elevation, returned = wintypes.DWORD(), wintypes.DWORD()
            token_info = self._bind(
                self._advapi,
                "GetTokenInformation",
                [
                    wintypes.HANDLE,
                    ctypes.c_int,
                    ctypes.c_void_p,
                    wintypes.DWORD,
                    ctypes.POINTER(wintypes.DWORD),
                ],
                wintypes.BOOL,
            )
            if (
                not token_info(
                    primary,
                    20,
                    ctypes.byref(elevation),
                    ctypes.sizeof(elevation),
                    ctypes.byref(returned),
                )
                or returned.value != ctypes.sizeof(elevation)
                or elevation.value != 1
            ):
                raise AdmissionBlocked("administrator_elevation_required")
            duplicate_token = self._bind(
                self._advapi,
                "DuplicateToken",
                [wintypes.HANDLE, ctypes.c_int, ctypes.POINTER(wintypes.HANDLE)],
                wintypes.BOOL,
            )
            if (
                not duplicate_token(primary, 2, ctypes.byref(duplicate))
                or not duplicate.value
            ):
                raise AdmissionBlocked("administrator_duplicate_unavailable")
            convert = self._bind(
                self._advapi,
                "ConvertStringSidToSidW",
                [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)],
                wintypes.BOOL,
            )
            if not convert("S-1-5-32-544", ctypes.byref(sid)) or not sid.value:
                raise AdmissionBlocked("administrator_sid_unavailable")
            member = wintypes.BOOL()
            check = self._bind(
                self._advapi,
                "CheckTokenMembership",
                [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL)],
                wintypes.BOOL,
            )
            if not check(duplicate, sid, ctypes.byref(member)) or member.value != 1:
                raise AdmissionBlocked("administrator_membership_required")
        except AdmissionBlocked:
            raise
        except Exception:
            raise AdmissionBlocked("administrator_native_failure") from None
        finally:
            if sid.value:
                if self._bind(
                    self._kernel, "LocalFree", [ctypes.c_void_p], ctypes.c_void_p
                )(sid):
                    raise AdmissionBlocked("administrator_cleanup_failed")
            for handle in (duplicate, primary):
                if handle.value and not self._bind(
                    self._kernel, "CloseHandle", [wintypes.HANDLE], wintypes.BOOL
                )(handle):
                    raise AdmissionBlocked("administrator_cleanup_failed")

    def _open(self, path: str, *, directory: bool | None) -> int | None:
        if not self._allowed(path, directory=directory):
            raise AdmissionBlocked("native_path_unreviewed")
        create = self._bind(
            self._kernel,
            "CreateFileW",
            [
                ctypes.c_wchar_p,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            ],
            wintypes.HANDLE,
        )
        access = (
            0x00020000
            | 0x00100000
            | ((0x0001 | 0x0080) if directory is not None else 0)
        )
        flags = 0x00200000 | (0x02000000 if directory is not False else 0)
        handle = create(path, access, 1, None, 3, flags, None)
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            if directory is None and ctypes.get_last_error() in (2, 3):
                return None
            raise AdmissionBlocked("native_open_unavailable")
        return int(handle)

    def _open_rename_source(self, path: str) -> int:
        if path not in (replacement.CANONICAL_PATH, replacement.STAGING_PATH):
            raise AdmissionBlocked("rename_source_path_unreviewed")
        create = self._bind(
            self._kernel,
            "CreateFileW",
            [
                ctypes.c_wchar_p,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            ],
            wintypes.HANDLE,
        )
        handle = create(
            path,
            _DELETE
            | _READ_CONTROL
            | _SYNCHRONIZE
            | _FILE_LIST_DIRECTORY
            | _FILE_READ_ATTRIBUTES,
            _FILE_SHARE_READ,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_OPEN_REPARSE_POINT | _FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            raise AdmissionBlocked("rename_source_open_unavailable")
        return int(handle)

    def _open_rename_parent(self) -> int:
        create = self._bind(
            self._kernel,
            "CreateFileW",
            [
                ctypes.c_wchar_p,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            ],
            wintypes.HANDLE,
        )
        handle = create(
            replacement.PARENT_PATH,
            _FILE_LIST_DIRECTORY
            | _FILE_ADD_SUBDIRECTORY
            | _FILE_TRAVERSE
            | _FILE_READ_ATTRIBUTES
            | _READ_CONTROL
            | _SYNCHRONIZE,
            _FILE_SHARE_READ,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_OPEN_REPARSE_POINT | _FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            raise AdmissionBlocked("rename_parent_open_unavailable")
        return int(handle)

    def _close(self, handle: int) -> None:
        if not self._bind(
            self._kernel, "CloseHandle", [wintypes.HANDLE], wintypes.BOOL
        )(handle):
            raise AdmissionBlocked("native_close_failed")

    def absent(self, path: str) -> bool:
        handle = self._open(path, directory=None)
        if handle is None:
            return True
        self._close(handle)
        return False

    def _free(self, pointer: object) -> None:
        if self._bind(self._kernel, "LocalFree", [ctypes.c_void_p], ctypes.c_void_p)(
            pointer
        ):
            raise AdmissionBlocked("native_allocation_release_failed")

    def _sid(self, pointer: object) -> str:
        value = ctypes.c_wchar_p()
        convert = self._bind(
            self._advapi,
            "ConvertSidToStringSidW",
            [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)],
            wintypes.BOOL,
        )
        if not convert(pointer, ctypes.byref(value)) or not value.value:
            raise AdmissionBlocked("native_sid_unavailable")
        try:
            return value.value
        finally:
            self._free(ctypes.cast(value, ctypes.c_void_p))

    def _security(self, handle: int) -> tuple[str, bool, tuple[Ace, ...]]:
        owner, dacl, descriptor = (
            ctypes.c_void_p(),
            ctypes.c_void_p(),
            ctypes.c_void_p(),
        )
        get_security = self._bind(
            self._advapi,
            "GetSecurityInfo",
            [
                wintypes.HANDLE,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            ],
            wintypes.DWORD,
        )
        status = get_security(
            handle,
            1,
            1 | 4,
            ctypes.byref(owner),
            None,
            ctypes.byref(dacl),
            None,
            ctypes.byref(descriptor),
        )
        if status:
            if descriptor.value:
                self._free(descriptor)
            raise AdmissionBlocked("native_security_unavailable")
        if not owner.value or not dacl.value or not descriptor.value:
            if descriptor.value:
                self._free(descriptor)
            raise AdmissionBlocked("native_security_incomplete")
        try:
            control, revision = wintypes.WORD(), wintypes.DWORD()
            get_control = self._bind(
                self._advapi,
                "GetSecurityDescriptorControl",
                [
                    ctypes.c_void_p,
                    ctypes.POINTER(wintypes.WORD),
                    ctypes.POINTER(wintypes.DWORD),
                ],
                wintypes.BOOL,
            )
            if not get_control(
                descriptor, ctypes.byref(control), ctypes.byref(revision)
            ):
                raise AdmissionBlocked("native_security_control_unavailable")
            size = _AclSize()
            acl_info = self._bind(
                self._advapi,
                "GetAclInformation",
                [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD],
                wintypes.BOOL,
            )
            if (
                not acl_info(dacl, ctypes.byref(size), ctypes.sizeof(size), 2)
                or size.ace_count > 16
            ):
                raise AdmissionBlocked("native_acl_unavailable")
            get_ace = self._bind(
                self._advapi,
                "GetAce",
                [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)],
                wintypes.BOOL,
            )
            aces = []
            for index in range(size.ace_count):
                pointer = ctypes.c_void_p()
                if not get_ace(dacl, index, ctypes.byref(pointer)) or not pointer.value:
                    raise AdmissionBlocked("native_ace_unavailable")
                header = ctypes.cast(pointer, ctypes.POINTER(_AceHeader)).contents
                if header.kind in (0, 1):
                    access = ctypes.cast(pointer, ctypes.POINTER(_AccessAce)).contents
                    ace_sid = self._sid(ctypes.c_void_p(pointer.value + 8))
                    mask = int(access.mask)
                else:
                    ace_sid, mask = "UNSUPPORTED", 0
                aces.append(Ace(ace_sid, mask, int(header.kind), int(header.flags)))
            return self._sid(owner), bool(control.value & 0x1000), tuple(aces)
        finally:
            self._free(descriptor)

    def _inspect(self, handle: int, path: str) -> NativeObject:
        get_final = self._bind(
            self._kernel,
            "GetFinalPathNameByHandleW",
            [wintypes.HANDLE, ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD],
            wintypes.DWORD,
        )
        final = ctypes.create_unicode_buffer(32768)
        length = get_final(handle, final, len(final), 0)
        if not length or length >= len(final) or not final.value.startswith("\\\\?\\"):
            raise AdmissionBlocked("native_final_path_unavailable")
        final_path = final.value[4:]
        info = _ByHandleInfo()
        get_info = self._bind(
            self._kernel,
            "GetFileInformationByHandle",
            [wintypes.HANDLE, ctypes.POINTER(_ByHandleInfo)],
            wintypes.BOOL,
        )
        if not get_info(handle, ctypes.byref(info)):
            raise AdmissionBlocked("native_handle_info_unavailable")
        file_index = (int(info.file_index_high) << 32) | int(info.file_index_low)
        if file_index == 0 or info.links != 1:
            raise AdmissionBlocked("native_handle_identity_invalid")
        volume = ctypes.create_unicode_buffer(32768)
        get_volume = self._bind(
            self._kernel,
            "GetVolumePathNameW",
            [ctypes.c_wchar_p, ctypes.c_wchar_p, wintypes.DWORD],
            wintypes.BOOL,
        )
        if not get_volume(final_path, volume, len(volume)):
            raise AdmissionBlocked("native_volume_path_unavailable")
        drive = self._bind(
            self._kernel, "GetDriveTypeW", [ctypes.c_wchar_p], wintypes.UINT
        )(volume.value)
        filesystem = ctypes.create_unicode_buffer(64)
        serial = wintypes.DWORD()
        volume_info = self._bind(
            self._kernel,
            "GetVolumeInformationW",
            [
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_wchar_p,
                wintypes.DWORD,
            ],
            wintypes.BOOL,
        )
        if (
            not volume_info(
                volume.value,
                None,
                0,
                ctypes.byref(serial),
                None,
                None,
                filesystem,
                len(filesystem),
            )
            or serial.value != info.volume_serial
        ):
            raise AdmissionBlocked("native_volume_identity_unavailable")
        owner, protected, aces = self._security(handle)
        return NativeObject(
            path,
            final_path,
            bool(info.attributes & 0x10),
            owner,
            protected,
            aces,
            bool(info.attributes & 0x400),
            int(drive),
            volume.value,
            filesystem.value,
            int(info.volume_serial),
            file_index,
            int(info.links),
            (int(info.size_high) << 32) | int(info.size_low),
        )

    def _reopen_matches(self, path: str, directory: bool, item: NativeObject) -> None:
        reopened = self._open(path, directory=directory)
        assert reopened is not None
        try:
            if self._inspect(reopened, path) != item:
                raise AdmissionBlocked("native_path_identity_drift")
        finally:
            self._close(reopened)

    def read_file(self, path: str, limit: int) -> CheckedFile:
        if type(limit) is not int or not 0 < limit <= 1024 * 1024 * 1024:
            raise AdmissionBlocked("native_read_bound_invalid")
        handle = self._open(path, directory=False)
        assert handle is not None
        try:
            before = self._inspect(handle, path)
            require_native_object(before, path, directory=False)
            if before.size > limit:
                raise AdmissionBlocked("native_file_size_bound")
            read = self._bind(
                self._kernel,
                "ReadFile",
                [
                    wintypes.HANDLE,
                    ctypes.c_void_p,
                    wintypes.DWORD,
                    ctypes.POINTER(wintypes.DWORD),
                    ctypes.c_void_p,
                ],
                wintypes.BOOL,
            )
            data = bytearray()
            while len(data) < before.size:
                chunk = min(before.size - len(data), 1024 * 1024)
                buffer = ctypes.create_string_buffer(chunk)
                received = wintypes.DWORD()
                if (
                    not read(handle, buffer, chunk, ctypes.byref(received), None)
                    or received.value == 0
                ):
                    raise AdmissionBlocked("native_file_read_incomplete")
                data.extend(buffer.raw[: received.value])
            if self._inspect(handle, path) != before:
                raise AdmissionBlocked("native_file_identity_drift")
        finally:
            self._close(handle)
        self._reopen_matches(path, False, before)
        return CheckedFile(before, bytes(data), True)

    def list_directory(self, path: str) -> CheckedDirectory:
        handle = self._open(path, directory=True)
        assert handle is not None
        try:
            before = self._inspect(handle, path)
            if path == replacement.PARENT_PATH:
                require_parent_native_object(before)
            else:
                require_native_object(before, path, directory=True)
            first = self._bind(
                self._kernel,
                "FindFirstFileW",
                [ctypes.c_wchar_p, ctypes.POINTER(_FindData)],
                wintypes.HANDLE,
            )
            next_file = self._bind(
                self._kernel,
                "FindNextFileW",
                [wintypes.HANDLE, ctypes.POINTER(_FindData)],
                wintypes.BOOL,
            )
            data = _FindData()
            find = first(path + r"\*", ctypes.byref(data))
            names: list[str] = []
            if find in (None, 0, ctypes.c_void_p(-1).value):
                if ctypes.get_last_error() != 2:
                    raise AdmissionBlocked("native_directory_inventory_unavailable")
            else:
                try:
                    while True:
                        if data.name not in (".", ".."):
                            names.append(data.name)
                        if next_file(find, ctypes.byref(data)):
                            continue
                        if ctypes.get_last_error() != 18:
                            raise AdmissionBlocked(
                                "native_directory_inventory_incomplete"
                            )
                        break
                finally:
                    if not self._bind(
                        self._kernel, "FindClose", [wintypes.HANDLE], wintypes.BOOL
                    )(find):
                        raise AdmissionBlocked("native_find_close_failed")
            if self._inspect(handle, path) != before:
                raise AdmissionBlocked("native_directory_identity_drift")
        finally:
            self._close(handle)

        self._reopen_matches(path, True, before)
        return CheckedDirectory(before, tuple(sorted(names)), True)


class _FileDispositionInfo(ctypes.Structure):
    _fields_ = [("delete_file", ctypes.c_ubyte)]


class _FixedRetiredDeletionNative(_WindowsReplacementReader):
    """Exclusive, no-follow disposition only for one freshly admitted plan."""

    def __init__(self, plan: replacement.RetiredCleanupPlan) -> None:
        if type(plan) is not replacement.RetiredCleanupPlan:
            raise AdmissionBlocked("cleanup_plan_unreviewed")
        super().__init__()
        self._plan = plan
        self._targets = {target.path: target for target in plan.targets}
        self._parents = {replacement.PARENT_PATH} | {
            target.path for target in plan.targets if target.directory
        }

    def _cleanup_open(self, path: str, *, parent: bool, directory: bool) -> int:
        if parent:
            if path not in self._parents or not self._allowed(path, directory=True):
                raise AdmissionBlocked("cleanup_parent_path_unreviewed")
            access = (
                _FILE_LIST_DIRECTORY
                | _FILE_TRAVERSE
                | _FILE_READ_ATTRIBUTES
                | _READ_CONTROL
                | _SYNCHRONIZE
            )
            share = _FILE_SHARE_READ | 2 | 4
        else:
            target = self._targets.get(path)
            if (
                target is None
                or target.directory is not directory
                or not self._allowed(path, directory=directory)
            ):
                raise AdmissionBlocked("cleanup_target_path_unreviewed")
            access = _DELETE | _READ_CONTROL | _FILE_READ_ATTRIBUTES | _SYNCHRONIZE
            access |= (_FILE_LIST_DIRECTORY | _FILE_TRAVERSE) if directory else 0x0001
            share = 0
        create = self._bind(
            self._kernel,
            "CreateFileW",
            [
                ctypes.c_wchar_p,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            ],
            wintypes.HANDLE,
        )
        handle = create(
            path,
            access,
            share,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_OPEN_REPARSE_POINT | _FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            raise AdmissionBlocked("cleanup_exclusive_open_unavailable")
        return int(handle)

    def _pinned_names(self, handle: int) -> tuple[str, ...]:
        get_info = self._bind(
            self._kernel,
            "GetFileInformationByHandleEx",
            [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
            wintypes.BOOL,
        )
        names: list[str] = []
        info_class = 11  # FileIdBothDirectoryRestartInfo; then class 10 to resume.
        while True:
            buffer = ctypes.create_string_buffer(65536)
            if not get_info(handle, info_class, buffer, len(buffer)):
                if ctypes.get_last_error() == 18:  # ERROR_NO_MORE_FILES
                    break
                raise AdmissionBlocked("cleanup_pinned_inventory_unavailable")
            info_class = 10
            raw = buffer.raw
            offset = 0
            while True:
                if offset + 104 > len(raw):
                    raise AdmissionBlocked("cleanup_pinned_inventory_bounds")
                next_offset, name_length = (
                    struct.unpack_from("<I", raw, offset)[0],
                    struct.unpack_from("<I", raw, offset + 60)[0],
                )
                if (
                    name_length % 2
                    or not name_length
                    or offset + 104 + name_length > len(raw)
                    or (next_offset and 104 + name_length > next_offset)
                ):
                    raise AdmissionBlocked("cleanup_pinned_name_bounds")
                try:
                    name = raw[offset + 104 : offset + 104 + name_length].decode(
                        "utf-16-le", errors="strict"
                    )
                except UnicodeError:
                    raise AdmissionBlocked("cleanup_pinned_name_encoding") from None
                if name not in (".", ".."):
                    if (
                        not name
                        or name.endswith((" ", "."))
                        or any(char in name for char in "\\/:\x00")
                        or name.casefold() in {item.casefold() for item in names}
                    ):
                        raise AdmissionBlocked("cleanup_pinned_name_invalid")
                    names.append(name)
                    if len(names) > 4096:
                        raise AdmissionBlocked("cleanup_pinned_inventory_bound")
                if next_offset == 0:
                    break
                if next_offset < 104 or offset + next_offset >= len(raw):
                    raise AdmissionBlocked("cleanup_pinned_entry_bounds")
                offset += next_offset
        return tuple(sorted(names))

    def _pinned_file(self, handle: int, expected_size: int) -> bytes:
        if not 0 <= expected_size <= MAX_SOURCE_FILE_BYTES:
            raise AdmissionBlocked("cleanup_pinned_file_bound")
        read = self._bind(
            self._kernel,
            "ReadFile",
            [
                wintypes.HANDLE,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                ctypes.c_void_p,
            ],
            wintypes.BOOL,
        )
        data = bytearray()
        while len(data) < expected_size:
            count = min(expected_size - len(data), 1024 * 1024)
            buffer = ctypes.create_string_buffer(count)
            received = wintypes.DWORD()
            if (
                not read(handle, buffer, count, ctypes.byref(received), None)
                or not 0 < received.value <= count
            ):
                raise AdmissionBlocked("cleanup_pinned_file_read")
            data.extend(buffer.raw[: received.value])
        probe = ctypes.create_string_buffer(1)
        received = wintypes.DWORD()
        if (
            not read(handle, probe, 1, ctypes.byref(received), None)
            or received.value != 0
        ):
            raise AdmissionBlocked("cleanup_pinned_file_trailing_data")
        return bytes(data)

    def _set_disposition(self, handle: int) -> bool:
        info = _FileDispositionInfo(1)
        set_info = self._bind(
            self._kernel,
            "SetFileInformationByHandle",
            [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
            wintypes.BOOL,
        )
        return bool(set_info(handle, 4, ctypes.byref(info), ctypes.sizeof(info)))


def _cleanup_identity_exact(
    native: _FixedRetiredDeletionNative, handle: int, expected: NativeObject
) -> None:
    observed = native._inspect(handle, expected.path)
    if expected.path == replacement.PARENT_PATH:
        require_parent_native_object(observed)
    else:
        require_native_object(observed, expected.path, directory=expected.directory)
    exact_observed = (
        replace(observed, size=expected.size) if expected.directory else observed
    )
    if exact_observed != expected:
        raise AdmissionBlocked("cleanup_pinned_identity_drift")


def _delete_fixed_target(
    native: _FixedRetiredDeletionNative,
    target: replacement.RetiredCleanupTarget,
    parent_identity: NativeObject,
    target_identity: NativeObject,
    expected_parent_names: tuple[str, ...],
    expected_target_names: tuple[str, ...],
) -> replacement.MutationOutcome:
    """One attempt only. Any uncertain native result permanently stops this session."""
    parent_handle: int | None = None
    target_handle: int | None = None
    target_close_attempted = False
    outcome = replacement.MutationOutcome.INDETERMINATE
    try:
        if (
            type(target) is not replacement.RetiredCleanupTarget
            or native._targets.get(target.path) != target
            or ntpath.dirname(target.path) != parent_identity.path
            or target_identity.path != target.path
            or ntpath.basename(target.path) not in expected_parent_names
        ):
            raise AdmissionBlocked("cleanup_step_plan_mismatch")
        parent_handle = native._cleanup_open(
            parent_identity.path, parent=True, directory=True
        )
        target_handle = native._cleanup_open(
            target.path, parent=False, directory=target.directory
        )
        _cleanup_identity_exact(native, parent_handle, parent_identity)
        _cleanup_identity_exact(native, target_handle, target_identity)
        if native._pinned_names(parent_handle) != expected_parent_names:
            raise AdmissionBlocked("cleanup_parent_inventory_drift")
        if target.directory:
            if (
                native._pinned_names(target_handle) != expected_target_names
                or expected_target_names
            ):
                raise AdmissionBlocked("cleanup_target_inventory_drift")
        else:
            if (
                target.byte_length != target_identity.size
                or hashlib.sha256(
                    native._pinned_file(target_handle, target.byte_length)
                ).hexdigest()
                != target.sha256
            ):
                raise AdmissionBlocked("cleanup_target_byte_drift")
        _cleanup_identity_exact(native, parent_handle, parent_identity)
        _cleanup_identity_exact(native, target_handle, target_identity)
        if not native._set_disposition(target_handle):
            raise AdmissionBlocked("cleanup_disposition_false")
        target_close_attempted = True
        native._close(target_handle)
        target_handle = None
        expected_after = tuple(
            name
            for name in expected_parent_names
            if name != ntpath.basename(target.path)
        )
        if native._pinned_names(parent_handle) != expected_after:
            raise AdmissionBlocked("cleanup_parent_post_inventory")
        if native.absent(target.path) is not True:
            raise AdmissionBlocked("cleanup_target_post_presence")
        _cleanup_identity_exact(native, parent_handle, parent_identity)
        outcome = replacement.MutationOutcome.SUCCESS
    except Exception:
        outcome = replacement.MutationOutcome.INDETERMINATE
    finally:
        if target_handle is not None and not target_close_attempted:
            try:
                native._close(target_handle)
            except Exception:
                outcome = replacement.MutationOutcome.INDETERMINATE
        if parent_handle is not None:
            try:
                native._close(parent_handle)
            except Exception:
                outcome = replacement.MutationOutcome.INDETERMINATE
    return outcome


class _FixedRetiredCleanupSession:
    def __init__(
        self, observation: CleanupObservation, native: _FixedRetiredDeletionNative
    ):
        if (
            observation.state is not replacement.CleanupState.FULL_RETIRED
            or type(observation.plan) is not replacement.RetiredCleanupPlan
            or type(observation.parent_native) is not NativeObject
        ):
            raise AdmissionBlocked("cleanup_session_not_admitted")
        self.plan = observation.plan
        self._native = native
        self._admitted = {item.path: item for item in observation.admitted_objects}
        self._admitted[replacement.PARENT_PATH] = observation.parent_native
        for target in self.plan.targets:
            if (
                target.path not in self._admitted
                or ntpath.dirname(target.path) not in self._admitted
            ):
                raise AdmissionBlocked("cleanup_plan_identity_missing")
        self._parent_names = observation.parent_children
        self.completed_targets = 0
        self._stopped = False

    def delete_next(self) -> replacement.MutationOutcome:
        if self._stopped or self.completed_targets >= len(self.plan.targets):
            raise AdmissionBlocked("cleanup_session_exhausted")
        target = self.plan.targets[self.completed_targets]
        parent = ntpath.dirname(target.path)
        deleted = {item.path for item in self.plan.targets[: self.completed_targets]}
        if parent == replacement.PARENT_PATH:
            names = tuple(
                name
                for name in self._parent_names
                if name != ntpath.basename(replacement.RETIRED_PATH)
                or replacement.RETIRED_PATH not in deleted
            )
        else:
            names = tuple(
                name
                for name in self.plan.children_of(parent)
                if parent + "\\" + name not in deleted
            )
        child_names = (
            ()
            if not target.directory
            else tuple(
                name
                for name in self.plan.children_of(target.path)
                if target.path + "\\" + name not in deleted
            )
        )
        result = _delete_fixed_target(
            self._native,
            target,
            self._admitted[parent],
            self._admitted[target.path],
            tuple(sorted(names)),
            tuple(sorted(child_names)),
        )
        if result is replacement.MutationOutcome.SUCCESS:
            self.completed_targets += 1
        else:
            self._stopped = True
        return result


def begin_fixed_retired_cleanup_session() -> tuple[
    CleanupObservation, _FixedRetiredCleanupSession | None
]:
    """Open a cleanup session only after fresh protected admission."""
    native = _WindowsReplacementReader()
    observation = _observe_cleanup(native, WindowsCngVerifier(), _run_scheduler_bounded)
    if observation.state is not replacement.CleanupState.FULL_RETIRED:
        return observation, None
    assert observation.plan is not None
    return observation, _FixedRetiredCleanupSession(
        observation, _FixedRetiredDeletionNative(observation.plan)
    )


def observe_retired_cleanup_post() -> bool:
    """Fresh independent two-pass proof after root deletion or idempotent absence."""
    observation = _observe_cleanup(
        _WindowsReplacementReader(), WindowsCngVerifier(), _run_scheduler_bounded
    )
    return observation.state is replacement.CleanupState.RETIRED_ABSENT


class _FileRenameInfo(ctypes.Structure):
    _fields_ = [
        ("replace_if_exists", ctypes.c_ubyte),
        ("root_directory", ctypes.c_void_p),
        ("file_name_length", wintypes.DWORD),
        ("file_name", ctypes.c_ubyte * 1),
    ]


def _fixed_rename_paths(step: replacement.RenameStep) -> tuple[str, str]:
    if step is replacement.RenameStep.OLD_TO_RETIRED:
        return replacement.CANONICAL_PATH, replacement.RETIRED_PATH
    if step is replacement.RenameStep.STAGING_TO_CANONICAL:
        return replacement.STAGING_PATH, replacement.CANONICAL_PATH
    raise AdmissionBlocked("rename_step_unreviewed")


def _fixed_rename_info(step: replacement.RenameStep, parent_handle: int):
    _, destination = _fixed_rename_paths(step)
    leaf = destination.rsplit("\\", 1)[-1]
    if (
        type(parent_handle) is not int
        or parent_handle in (0, ctypes.c_void_p(-1).value)
        or not leaf
        or any(character in leaf for character in "\\/:\x00")
    ):
        raise AdmissionBlocked("rename_destination_invalid")
    encoded = leaf.encode("utf-16-le")
    offset = _FileRenameInfo.file_name.offset
    buffer = ctypes.create_string_buffer(
        ctypes.sizeof(_FileRenameInfo) + len(encoded) + 2
    )
    info = _FileRenameInfo.from_buffer(buffer)
    info.replace_if_exists = 0
    info.root_directory = parent_handle
    info.file_name_length = len(encoded)
    ctypes.memmove(ctypes.addressof(buffer) + offset, encoded, len(encoded))
    return buffer


def _set_fixed_rename(
    native: _WindowsReplacementReader,
    step: replacement.RenameStep,
    source_handle: int,
    parent_handle: int,
) -> replacement.RenameDiagnostic | None:
    info = _fixed_rename_info(step, parent_handle)
    set_information = native._bind(
        native._kernel,
        "SetFileInformationByHandle",
        [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
        wintypes.BOOL,
    )
    pointer, size = ctypes.byref(info), len(info)
    ctypes.set_last_error(0)
    if not set_information(source_handle, _FILE_RENAME_INFO_CLASS, pointer, size):
        error = ctypes.get_last_error()
        # ctypes stores a C int; interpret its signed slot as the Win32 DWORD.
        if type(error) is int and -0x80000000 <= error < 0:
            error += 0x100000000
        return replacement.RenameDiagnostic(
            step, replacement.RenameFailureStage.NATIVE_FALSE, error
        )
    return None


def _rename_fixed_step(
    native: _WindowsReplacementReader,
    step: replacement.RenameStep,
    expected_source: NativeObject,
    expected_parent: NativeObject,
) -> tuple[replacement.MutationOutcome, replacement.RenameDiagnostic | None]:
    """One handle-pinned rename; any uncertainty consumes this attempt."""
    source_path, destination_path = _fixed_rename_paths(step)
    parent_handle: int | None = None
    source_handle: int | None = None
    outcome = replacement.MutationOutcome.INDETERMINATE
    cleanup_ambiguous = False
    native_succeeded = False
    diagnostic = replacement.RenameDiagnostic(
        step, replacement.RenameFailureStage.PRE_CALL
    )
    try:
        if (
            type(expected_source) is not NativeObject
            or type(expected_parent) is not NativeObject
        ):
            raise AdmissionBlocked("rename_admitted_identity_missing")
        parent_handle = native._open_rename_parent()
        source_handle = native._open_rename_source(source_path)
        parent_before = native._inspect(parent_handle, replacement.PARENT_PATH)
        source_before = native._inspect(source_handle, source_path)
        require_parent_native_object(parent_before)
        require_native_object(source_before, source_path, directory=True)
        if (
            parent_before != expected_parent
            or source_before != expected_source
            or source_before.volume_serial != parent_before.volume_serial
            or source_before.volume_root != parent_before.volume_root
        ):
            raise AdmissionBlocked("rename_pinned_identity_drift")
        if native.absent(destination_path) is not True:
            raise AdmissionBlocked("rename_destination_present")
        if (
            native._inspect(parent_handle, replacement.PARENT_PATH) != parent_before
            or native._inspect(source_handle, source_path) != source_before
        ):
            raise AdmissionBlocked("rename_pre_call_drift")
        diagnostic = _set_fixed_rename(native, step, source_handle, parent_handle)
        if diagnostic is None:
            native_succeeded = True
            expected_after = replace(source_before, final_path=destination_path)
            if (
                native._inspect(source_handle, source_path) != expected_after
                or native._inspect(parent_handle, replacement.PARENT_PATH)
                != parent_before
            ):
                raise AdmissionBlocked("rename_post_call_drift")
            outcome = replacement.MutationOutcome.SUCCESS
    except Exception:
        diagnostic = replacement.RenameDiagnostic(
            step,
            replacement.RenameFailureStage.POST_CALL_VERIFY
            if native_succeeded
            else replacement.RenameFailureStage.PRE_CALL,
        )
        outcome = replacement.MutationOutcome.INDETERMINATE
    finally:
        for handle in (source_handle, parent_handle):
            if handle is not None:
                try:
                    native._close(handle)
                except Exception:
                    cleanup_ambiguous = True
    if cleanup_ambiguous:
        return (
            replacement.MutationOutcome.INDETERMINATE,
            replacement.RenameDiagnostic(
                step, replacement.RenameFailureStage.CLOSE_AMBIGUITY
            ),
        )
    return outcome, diagnostic


class _FixedRenameSession:
    """Expose two fixed steps only in one freshly admitted invocation."""

    def __init__(
        self,
        native: _WindowsReplacementReader,
        admission: AdmissionObservation,
        verifier: object,
        scheduler_run: object,
    ) -> None:
        if (
            type(admission) is not AdmissionObservation
            or type(admission.facts) is not replacement.AdmissionFacts
            or not admission.facts.all_exact()
            or type(admission.parent_native) is not NativeObject
            or type(admission.old_native) is not NativeObject
            or type(admission.new_native) is not NativeObject
        ):
            raise AdmissionBlocked("rename_session_admission_incomplete")
        result = replacement.begin_replacement(admission.namespace, admission.facts)
        if result.phase is not replacement.Phase.READY_TO_RETIRE_OLD:
            raise AdmissionBlocked("rename_session_not_ready")
        self._native = native
        self._admission = admission
        self._verifier = verifier
        self._scheduler_run = scheduler_run
        self.result = result

    @property
    def admission(self) -> AdmissionObservation:
        """Expose the immutable read-only proof needed for final verification."""
        return self._admission

    def retire_old_root(self) -> replacement.MutationOutcome:
        if self.result.phase is not replacement.Phase.READY_TO_RETIRE_OLD:
            raise AdmissionBlocked("rename_step_not_ready")
        outcome = replacement.MutationOutcome.INDETERMINATE
        diagnostic = replacement.RenameDiagnostic(
            replacement.RenameStep.OLD_TO_RETIRED,
            replacement.RenameFailureStage.PRE_CALL,
        )
        try:
            fresh = _observe_admission(
                self._native, self._verifier, self._scheduler_run
            )
            if (
                fresh.namespace != self._admission.namespace
                or fresh.facts != self._admission.facts
                or fresh.scheduler != self._admission.scheduler
                or fresh.parent_native != self._admission.parent_native
                or fresh.old_native != self._admission.old_native
                or fresh.new_native != self._admission.new_native
            ):
                raise AdmissionBlocked("rename_final_admission_drift")
            outcome, diagnostic = _rename_fixed_step(
                self._native,
                replacement.RenameStep.OLD_TO_RETIRED,
                fresh.old_native,
                fresh.parent_native,
            )
        except Exception:
            outcome = replacement.MutationOutcome.INDETERMINATE
        self.result = replacement.record_rename(
            self.result, replacement.RenameStep.OLD_TO_RETIRED, outcome, diagnostic
        )
        return outcome

    def publish_staged_root(self) -> replacement.MutationOutcome:
        if self.result.phase is not replacement.Phase.READY_TO_PUBLISH_NEW:
            raise AdmissionBlocked("rename_step_not_ready")
        outcome = replacement.MutationOutcome.INDETERMINATE
        diagnostic = replacement.RenameDiagnostic(
            replacement.RenameStep.STAGING_TO_CANONICAL,
            replacement.RenameFailureStage.PRE_CALL,
        )
        try:
            self._native.require_administrator()
            parent = self._native.list_directory(replacement.PARENT_PATH)
            require_parent_native_object(parent.identity)
            names = parent.children
            if (
                parent.stable is not True
                or parent.identity != self._admission.parent_native
                or type(names) is not tuple
                or len(names) != len(set(names))
                or len(names) != len({name.casefold() for name in names})
                or replacement.CANONICAL_PATH.rsplit("\\", 1)[-1] in names
                or replacement.STAGING_PATH.rsplit("\\", 1)[-1] not in names
                or replacement.RETIRED_PATH.rsplit("\\", 1)[-1] not in names
            ):
                raise AdmissionBlocked("rename_second_namespace_drift")
            _require_reserved_siblings(
                names,
                {
                    replacement.STAGING_PATH.rsplit("\\", 1)[-1],
                    replacement.RETIRED_PATH.rsplit("\\", 1)[-1],
                },
            )
            _expect_absent(self._native, replacement.CANONICAL_PATH)
            manifest, old_serial = _verify_old(
                self._native, self._verifier, replacement.RETIRED_PATH
            )
            retired = self._native.list_directory(replacement.RETIRED_PATH)
            expected_retired = replace(
                self._admission.old_native,
                path=replacement.RETIRED_PATH,
                final_path=replacement.RETIRED_PATH,
            )
            if (
                type(retired) is not CheckedDirectory
                or retired.stable is not True
                or retired.identity != expected_retired
                or _verify_new(self._native, manifest) != old_serial
                or old_serial != parent.identity.volume_serial
                or _observe_d5_scheduler(self._scheduler_run)
                != self._admission.scheduler
            ):
                raise AdmissionBlocked("rename_second_admission_drift")
            outcome, diagnostic = _rename_fixed_step(
                self._native,
                replacement.RenameStep.STAGING_TO_CANONICAL,
                self._admission.new_native,
                self._admission.parent_native,
            )
        except Exception:
            outcome = replacement.MutationOutcome.INDETERMINATE
        self.result = replacement.record_rename(
            self.result,
            replacement.RenameStep.STAGING_TO_CANONICAL,
            outcome,
            diagnostic,
        )
        return outcome


def begin_fixed_rename_session() -> _FixedRenameSession:
    """Fresh read-only admission; return only in-process fixed-step authority."""
    native = _WindowsReplacementReader()
    verifier = WindowsCngVerifier()
    admission = _observe_admission(native, verifier, _run_scheduler_bounded)
    return _FixedRenameSession(native, admission, verifier, _run_scheduler_bounded)


def validate_recovery_material(repository_root: Path) -> None:
    """Validate the certified material input read-only; never rebuild staging."""
    _require_s5_r10_material(build_certified_material(repository_root))
