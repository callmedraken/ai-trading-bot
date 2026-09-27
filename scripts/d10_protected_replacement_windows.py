"""Read-only native admission for the one Architecture-125 D10 replacement.

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
import subprocess
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from scripts import d10_protected_replacement as replacement
from scripts.d10_protected_deployment import (
    MAX_ATTESTATION_BYTES,
    MAX_GUARD_BYTES,
    MAX_MANIFEST_BYTES,
    MAX_SIGNATURE_BYTES,
    Ace,
    CheckedDirectory,
    CheckedFile,
    NativeObject,
    require_directory,
    require_native_object,
    require_parent_native_object,
    verify_signature,
)
from scripts.d10_protected_deployment_windows import WindowsCngVerifier
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

_EXPECTED_SCHEDULER = {
    "task_path": r"\AITradingBot-PD4-UnattendedPaper-v1",
    "principal_sid": "S-1-5-21-1397534616-3988210162-180023805-1009",
    "logon_type": 1,
    "run_level": 0,
    "action_count": 1,
    "action_type": 0,
    "action_path": r"F:\AITradingBot\runtime\python.exe",
    "action_arguments": (
        r"-I F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts"
        r"\run_personal_desktop_unattended_capture_warmup.py"
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
    native: ReadOnlyNative, verifier: object
) -> tuple[ExecutableManifest, int]:
    root = replacement.CANONICAL_PATH
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


def _verify_new(native: ReadOnlyNative, manifest: ExecutableManifest) -> int:
    root = replacement.STAGING_PATH
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
    return AdmissionObservation(second, facts, scheduler_second)


def observe_admission() -> AdmissionObservation:
    """Observe fixed native paths and Task Scheduler; accept no caller evidence."""
    return _observe_admission(
        _WindowsReplacementReader(), WindowsCngVerifier(), _run_scheduler_bounded
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
        if path == replacement.RETIRED_PATH:
            return directory is None
        for root in (replacement.CANONICAL_PATH, replacement.STAGING_PATH):
            if path == root:
                return directory is True
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
