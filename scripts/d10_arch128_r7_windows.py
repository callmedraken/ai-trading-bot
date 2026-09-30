"""Concrete fixed R7 Windows boundaries. Import/factory are inert.

No runner registration is added. Calling mutations requires the separate R7B
interlock and later explicit host authorization. All paths/plans are source owned.
"""

from __future__ import annotations

import ctypes
import getpass
import json
import os
import re
import subprocess
import sys
import weakref
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from scripts import d10_arch128_r4_orchestration as r4c
from scripts import d10_arch128_r4_windows as r4w
from scripts import d10_arch128_r6_reactivation as r6
from scripts import d10_arch128_r7_observation as observation
from scripts import d10_python_substrate_windows as substrate
from scripts import run_personal_desktop_d10_launch_guard as guard
from scripts.d10_protected_deployment import (
    CheckedFile,
    DeploymentBlocked,
    require_file,
)
from scripts.d10_protected_deployment_windows import (
    WindowsActivationLeaseBackend,
    WindowsCngVerifier,
    WindowsDeploymentBackend,
)
from scripts.d10_protected_replacement_windows import POWERSHELL
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    D10_ACTIVATION_LEASE_PUBLICATION_CONTRACT as PUBLICATION,
)
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    D10ActivationLease,
    canonical_json_bytes,
    format_utc_instant,
)

TRADING_PID_ENV = "AI_TRADING_BOT_ARCH128_R7_TRADING_PID"
OBSERVE_HELPER = Path(__file__).with_name("d10_arch128_r3_scheduler_observe.ps1")
UPDATE_HELPER = Path(__file__).with_name("d10_arch128_r7_scheduler_update.ps1")
MAX_TRANSPORT = 16 * 1024


def parse_trading_pid(value: str | None) -> int:
    if type(value) is not str or re.fullmatch(r"[0-9]+", value) is None:
        raise DeploymentBlocked("r7_trading_pid_required")
    try:
        pid = int(value)
    except ValueError:
        raise DeploymentBlocked("r7_trading_pid_invalid") from None
    if pid <= 0 or pid > 0xFFFFFFFF:
        raise DeploymentBlocked("r7_trading_pid_invalid")
    return pid


class WindowsR7EvidenceBackend(WindowsDeploymentBackend):
    """Dedicated initial evidence ACL and CREATE_NEW, empty-only provisioning."""

    def __init__(self, plan: r6.ReactivationPlan) -> None:
        observation.require_plan(plan)
        self._plan = plan
        super().__init__()

    def _allowed_directory_create(self, path: str) -> bool:
        return False

    def _allowed_file_create(self, path: str) -> bool:
        return type(path) is str and path == self._plan.evidence_path

    def _allowed_object_path(self, path: str, *, directory: bool) -> bool:
        return directory is False and self._allowed_file_create(path)

    def publish_create_only(self, installing_path: str, final_path: str) -> None:
        raise DeploymentBlocked("r7_evidence_publication_forbidden")

    def _build_security_descriptor(self, directory: bool) -> ctypes.c_void_p:
        if directory is not False:
            raise DeploymentBlocked("r7_evidence_directory_creation_forbidden")
        sddl = (
            "O:BA D:P(A;;FA;;;BA)(A;;FA;;;SY)"
            f"(A;;0x{guard.TRADING_EVIDENCE_FILE_ACCESS:08X};;;{guard.TRADING_SID})"
        )
        descriptor = ctypes.c_void_p()
        convert = self._bind(
            self._advapi,
            "ConvertStringSecurityDescriptorToSecurityDescriptorW",
            [
                ctypes.c_wchar_p,
                wintypes.DWORD,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_void_p,
            ],
            wintypes.BOOL,
        )
        if not convert(sddl, 1, ctypes.byref(descriptor), None) or not descriptor.value:
            raise DeploymentBlocked("r7_evidence_descriptor_unavailable")
        return descriptor

    def create_file(self, path: str, data: bytes) -> None:
        observation.require_evidence_path(path)
        if (
            not self._allowed_file_create(path)
            or type(data) is not bytes
            or data != b""
        ):
            raise DeploymentBlocked("r7_evidence_creation_not_exact_empty")
        self.require_administrator()
        descriptor, attributes = self._security_attributes(directory=False)
        handle = None
        try:
            try:
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
                    0x0002 | 0x00020000 | 0x00040000 | 0x00080000,
                    0,
                    ctypes.byref(attributes),
                    1,
                    guard.FILE_FLAG_OPEN_REPARSE_POINT | guard.FILE_FLAG_WRITE_THROUGH,
                    None,
                )
                if handle in (None, 0, ctypes.c_void_p(-1).value):
                    handle = None
                    raise DeploymentBlocked("r7_evidence_create_new_failed")
            finally:
                self._free_security_descriptor(descriptor)
        finally:
            if handle is not None:
                self._close_handle(int(handle))
        # Fresh independently opened handles verify zero bytes, final identity,
        # fixed NTFS/non-reparse/single-link facts and every initial ACL entry.
        self.observe_empty(path)

    def observe_empty(self, path: str) -> CheckedFile:
        observation.require_evidence_path(path)
        if not self._allowed_file_create(path):
            raise DeploymentBlocked("r7_evidence_path_differs_from_plan")
        first = None
        for _ in range(2):
            handle = self._open_existing(path, directory=False)
            try:
                before = self._inspect(handle)
                checked = CheckedFile(self._native_facts(path, before), b"", True)
                observation.require_empty_evidence(checked, path)
                if before != self._inspect(handle):
                    raise DeploymentBlocked("r7_evidence_pinned_identity_drift")
            finally:
                self._close_handle(handle)
            if first is not None and checked != first:
                raise DeploymentBlocked("r7_evidence_reopen_identity_drift")
            first = checked
        return first


class WindowsR7Reader(r4w.WindowsArch128ReadOnlyReader):
    """Preserve R4 native reads; route only exact current evidence to its policy."""

    def bind_evidence(self, evidence: WindowsR7EvidenceBackend) -> None:
        if hasattr(self, "_evidence"):
            raise DeploymentBlocked("r7_evidence_reader_already_bound")
        if type(evidence) is not WindowsR7EvidenceBackend:
            raise DeploymentBlocked("r7_evidence_reader_binding_not_exact")
        observation.require_plan(evidence._plan)
        self._evidence = evidence

    def read_file(self, path: str, limit: int) -> CheckedFile:
        evidence = getattr(self, "_evidence", None)
        if evidence is not None and path == evidence._plan.evidence_path:
            if type(limit) is not int or limit != 0:
                raise DeploymentBlocked("r7_evidence_read_must_be_empty")
            return evidence.observe_empty(path)
        return super().read_file(path, limit)


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise DeploymentBlocked("r7_transport_duplicate_json")
        result[key] = value
    return result


def _transport(helper: Path, payload: bytes | None = None) -> tuple[int, bytes, bytes]:
    if helper not in (OBSERVE_HELPER, UPDATE_HELPER) or (
        helper == OBSERVE_HELPER and payload is not None
    ):
        raise DeploymentBlocked("r7_transport_not_fixed")
    with subprocess.Popen(
        (
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper),
        ),
        stdin=subprocess.PIPE if payload is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        with ThreadPoolExecutor(max_workers=2) as readers:
            out = readers.submit(process.stdout.read, MAX_TRANSPORT + 1)
            err = readers.submit(process.stderr.read, 257)
            try:
                if payload is not None:
                    process.stdin.write(payload)
                    process.stdin.close()
                code = process.wait(timeout=60)
            except (Exception, KeyboardInterrupt):
                process.kill()
                process.wait()
                raise DeploymentBlocked("r7_transport_ambiguous") from None
            stdout, stderr = out.result(), err.result()
    if len(stdout) > MAX_TRANSPORT or len(stderr) > 256:
        raise DeploymentBlocked("r7_transport_bound")
    return code, stdout, stderr


def _read_scheduler_projection() -> dict[str, object]:
    code, out, err = _transport(OBSERVE_HELPER)
    if code != 0 or err or not out:
        raise DeploymentBlocked("r7_com_observation_failed")
    try:
        value = json.loads(out.decode("utf-8"), object_pairs_hook=_unique_pairs)
        if (
            type(value) is not dict
            or set(value) != {"schema", "status", "first", "second"}
            or value["schema"] != "arch128-r3-scheduler-observation/v1"
            or value["status"] != "OBSERVED"
            or type(value["first"]) is not dict
            or value["first"] != value["second"]
        ):
            raise ValueError
        return value["second"]
    except (ValueError, UnicodeError):
        raise DeploymentBlocked("r7_com_projection_invalid") from None


@dataclass(slots=True, weakref_slot=True, repr=False)
class SchedulerCredential:
    password: str = field(repr=False)

    def consume(self) -> str:
        secret = self.password
        self.password = ""
        if type(secret) is not str or not secret:
            raise DeploymentBlocked("r7_credential_consumed_or_missing")
        return secret


def _require_interactive_console() -> None:
    """Prove real console handles, excluding redirected input and device TTYs."""
    kernel = ctypes.WinDLL(r"C:\Windows\System32\kernel32.dll", use_last_error=True)
    get_handle = kernel.GetStdHandle
    get_handle.argtypes = [wintypes.DWORD]
    get_handle.restype = wintypes.HANDLE
    get_mode = kernel.GetConsoleMode
    get_mode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    get_mode.restype = wintypes.BOOL
    for identifier in (-10, -12):
        handle = get_handle(identifier & 0xFFFFFFFF)
        mode = wintypes.DWORD()
        if handle in (None, 0, ctypes.c_void_p(-1).value) or not get_mode(
            handle, ctypes.byref(mode)
        ):
            raise DeploymentBlocked("r7_real_interactive_console_required")


def _interactive_credential() -> SchedulerCredential:
    if (
        os.name != "nt"
        or sys.stdin is not sys.__stdin__
        or not sys.stdin.isatty()
        or not sys.stderr.isatty()
    ):
        raise DeploymentBlocked("r7_interactive_console_required")
    _require_interactive_console()
    # On Windows with the original real console stdin, getpass uses getwch;
    # its redirected-input fallback is excluded by the admission above.
    secret = getpass.getpass("Trading password for protected Architecture-128 R7: ")
    if type(secret) is not str or not secret:
        raise DeploymentBlocked("r7_interactive_credential_unavailable")
    return SchedulerCredential(secret)


def _scheduler_update(
    plan: r6.ReactivationPlan, credential: SchedulerCredential
) -> r6.MutationDisposition:
    secret = credential.consume()
    payload = b""
    try:
        observation.require_plan(plan)
        payload = (
            canonical_json_bytes(
                {
                    "activation_utc": format_utc_instant(
                        plan.lease.accepted_activation_utc
                    ),
                    "password": secret,
                }
            )
            + b"\n"
        )
        if len(payload) > MAX_TRANSPORT:
            return r6.MutationDisposition.NOT_CALLED
        code, out, err = _transport(UPDATE_HELPER, payload)
        value = json.loads(out.decode("utf-8"), object_pairs_hook=_unique_pairs)
        if (
            err
            or type(value) is not dict
            or set(value) != {"schema", "disposition"}
            or value["schema"] != "arch128-r7-scheduler-update/v1"
        ):
            return r6.MutationDisposition.INDETERMINATE
        disposition = r6.MutationDisposition(value["disposition"])
        if (code, disposition) not in (
            (0, r6.MutationDisposition.CALL_RETURNED),
            (1, r6.MutationDisposition.NOT_CALLED),
            (2, r6.MutationDisposition.INDETERMINATE),
        ):
            return r6.MutationDisposition.INDETERMINATE
        return disposition
    except (Exception, KeyboardInterrupt):
        return r6.MutationDisposition.INDETERMINATE
    finally:
        credential.password = ""
        secret = ""
        payload = b""


class WindowsR7Boundaries:
    """Single-use concrete R6 ordering, with a source-clock-derived exact plan."""

    def __init__(self, trading_pid: int) -> None:
        if type(trading_pid) is not int or not 0 < trading_pid <= 0xFFFFFFFF:
            raise DeploymentBlocked("r7_trading_pid_invalid")
        self._pid = trading_pid
        self._phase = "NEW"
        self._plan = None
        self._credential = None
        self._evidence_verified = False
        # Construction binds DLLs only: no token, credential, I/O, or mutation.
        self._reader = WindowsR7Reader()
        self._verifier = WindowsCngVerifier()
        self._lease = WindowsActivationLeaseBackend()

    def _require_phase(self, *phases: str) -> None:
        if self._phase not in phases:
            raise DeploymentBlocked("r7_boundary_order_invalid")

    def _require_plan(self, plan: r6.ReactivationPlan) -> None:
        observation.require_plan(plan)
        if plan != self._plan:
            raise DeploymentBlocked("r7_boundary_plan_drift")

    def _require_path(self, path: str) -> None:
        observation.require_evidence_path(path)
        if self._plan is None or path != self._plan.evidence_path:
            raise DeploymentBlocked("r7_boundary_path_drift")

    def _require_active_window(self) -> None:
        if (
            not self._plan.lease.accepted_activation_utc
            <= datetime.now(UTC)
            < self._plan.lease.end_utc
        ):
            raise DeploymentBlocked("r7_activation_window_expired")

    def activation_clock(self) -> datetime:
        self._require_phase("ADMITTED")
        instant = datetime.now(UTC).replace(microsecond=0)
        self._plan = r6.derive_reactivation_plan(instant)
        self._phase = "PLANNED"
        return instant

    def observe_admission(
        self, stage: str, plan: r6.ReactivationPlan | None
    ) -> r6.AdmissionObservation:
        observation.require_stage(stage, plan)
        phases = {
            "INITIAL": "NEW",
            "AFTER_CREDENTIAL": "CREDENTIAL",
            "BEFORE_LEASE": "SCHEDULER_VERIFIED",
            "FINAL": "LEASE_PUBLISHED",
        }
        self._require_phase(phases[stage])
        if plan is not None:
            self._require_plan(plan)
        self._phase = "ADMISSION_ATTEMPTED"
        result = r4c.observe_r7_complete(
            self._reader, self._verifier, _read_scheduler_projection, stage, plan
        )
        self._phase = {
            "INITIAL": "ADMITTED",
            "AFTER_CREDENTIAL": "FRESH",
            "BEFORE_LEASE": "BEFORE_LEASE",
            "FINAL": "FINAL",
        }[stage]
        self._evidence_verified = False
        return result

    def create_empty_evidence(self, path: str) -> None:
        self._require_phase("PLANNED")
        self._require_path(path)
        self._phase = "EVIDENCE_ATTEMPTED"
        self._evidence = WindowsR7EvidenceBackend(self._plan)
        self._reader.bind_evidence(self._evidence)
        self._evidence.create_file(path, b"")
        self._phase = "CREATED"

    def observe_evidence(self, path: str) -> r6.EvidenceObservation:
        self._require_phase("CREATED", "FRESH", "BEFORE_LEASE", "FINAL")
        self._require_path(path)
        checked = self._evidence.observe_empty(path)
        result = observation.require_empty_evidence(checked, path)
        self._evidence_verified = True
        return result

    def probe_trading_append_open(self, path: str) -> r6.TradingOpenObservation:
        self._require_phase("CREATED")
        self._require_path(path)
        if not self._evidence_verified:
            raise DeploymentBlocked("r7_evidence_not_verified")
        self._phase = "PROBE_ATTEMPTED"
        result = substrate.probe_trading_evidence_append_open(
            self._pid, self._plan.lease
        )
        expected = r6.TradingOpenObservation(
            guard.TRADING_SID,
            guard.TRADING_EVIDENCE_FILE_ACCESS,
            1,
            3,
            guard.FILE_FLAG_OPEN_REPARSE_POINT | guard.FILE_FLAG_WRITE_THROUGH,
            True,
            0,
        )
        if type(result) is not r6.TradingOpenObservation or result != expected:
            raise DeploymentBlocked("r7_trading_probe_not_exact")
        self._phase = "PROBED"
        return result

    def acquire_scheduler_credential(self) -> SchedulerCredential:
        self._require_phase("PROBED")
        self._phase = "CREDENTIAL_ATTEMPTED"
        credential = _interactive_credential()
        self._credential = weakref.ref(credential)
        self._phase = "CREDENTIAL"
        return credential

    def update_scheduler(
        self, plan: r6.ReactivationPlan, credential: object
    ) -> r6.MutationDisposition:
        self._require_phase("FRESH")
        self._require_plan(plan)
        if (
            type(credential) is not SchedulerCredential
            or self._credential is None
            or credential is not self._credential()
            or not self._evidence_verified
        ):
            raise DeploymentBlocked("r7_scheduler_credential_or_evidence_missing")
        self._phase = "SCHEDULER_ATTEMPTED"
        try:
            self._require_active_window()
            result = _scheduler_update(plan, credential)
        finally:
            credential.password = ""
            self._credential = None
        if result is r6.MutationDisposition.CALL_RETURNED:
            self._phase = "SCHEDULER_RETURNED"
        return result

    def read_scheduler(
        self,
    ) -> r6.scheduler_contract.OneWeekSoakSchedulerDeploymentSpec:
        self._require_phase(
            "SCHEDULER_RETURNED", "SCHEDULER_VERIFIED", "BEFORE_LEASE", "FINAL"
        )
        observation.require_scheduler(
            _read_scheduler_projection(), self._plan.scheduler
        )
        if self._phase == "SCHEDULER_RETURNED":
            self._phase = "SCHEDULER_VERIFIED"
        return self._plan.scheduler

    def publish_lease(
        self, lease: D10ActivationLease
    ) -> r6.LeasePublicationObservation:
        self._require_phase("BEFORE_LEASE")
        if (
            lease != self._plan.lease
            or type(lease) is not D10ActivationLease
            or not self._evidence_verified
        ):
            raise DeploymentBlocked("r7_lease_not_exact_plan")
        self._phase = "LEASE_ATTEMPTED"
        self._require_active_window()
        self._lease.require_administrator()
        for path in (
            PUBLICATION.temporary_path,
            PUBLICATION.installing_path,
            PUBLICATION.final_path,
        ):
            if self._reader.absent(path) is not True:
                raise DeploymentBlocked("r7_lease_collision")
        data = lease.canonical_bytes()
        self._lease.create_file(PUBLICATION.temporary_path, data)
        previous = self._reader.read_file(PUBLICATION.temporary_path, 64 * 1024)
        require_file(previous, PUBLICATION.temporary_path, data)
        steps = ["TMP_CREATED_AND_VERIFIED"]
        for source, destination, step in (
            (
                PUBLICATION.temporary_path,
                PUBLICATION.installing_path,
                "TMP_TO_INSTALLING_VERIFIED",
            ),
            (
                PUBLICATION.installing_path,
                PUBLICATION.final_path,
                "INSTALLING_TO_FINAL_VERIFIED",
            ),
        ):
            self._require_active_window()
            observation.require_scheduler(
                _read_scheduler_projection(), self._plan.scheduler
            )
            if self._reader.absent(destination) is not True:
                raise DeploymentBlocked("r7_lease_publication_collision")
            self._lease.publish_create_only(source, destination)
            current = self._reader.read_file(destination, 64 * 1024)
            require_file(current, destination, data)
            if (
                current.identity
                != replace(previous.identity, path=destination, final_path=destination)
                or self._reader.absent(source) is not True
            ):
                raise DeploymentBlocked("r7_lease_native_publication_drift")
            previous = current
            steps.append(step)
        self._phase = "LEASE_PUBLISHED"
        return r6.LeasePublicationObservation(
            r6.MutationDisposition.PUBLISHED_VERIFIED, tuple(steps)
        )


def host_factory() -> tuple[r6.Boundaries, Callable[[], datetime]]:
    """Fixed environment PID hint; authority remains native token proof + R7B."""
    boundaries = WindowsR7Boundaries(parse_trading_pid(os.environ.get(TRADING_PID_ENV)))
    return boundaries, boundaries.activation_clock
