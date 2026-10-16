"""133-K fixed retained-root recovery. The only mutation is the frozen root ACL call.

No publication, store, scratch, provider or scheduler capability is imported.
An attempted call consumes process authority even when acknowledgement is lost.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from threading import Lock

from trading_bot.arch133_acl import (
    administrator,
    read_only,
    retained_reads,
    root_policy_apply,
)
from trading_bot.arch133_acl.root_policy_apply import apply_root_policy_status

TARGET_PATH = retained_reads.TARGET_PATH
PARENTS = ("F:\\", r"F:\AITradingBot")
SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133k")
SOURCE_BRANCH = "feature/robinhood-unattended-review-paper-133k"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
PLAN_SCHEMA = "arch133k-retained-root-acl-recovery-plan/v1"
RESULT_SCHEMA = "arch133k-retained-root-acl-recovery/v1"
ROOT_IDENTITY = (1855336320, 1407374886183770)
PRE_SECURITY_SHA256 = "b8fc336502437d1599a257da32a20bb62966663bb20fa44694d614c0f59361a3"
FILE_HASHES = {
    "activation.json": (
        "37873b490c3f2ccced53431c599e40ca54fdc008e09e9bfdb38eb61d10f3cab2"
    ),
    "host-binding.json": (
        "c1106d1937dab615da0f12eb9170c020add2ffdece3d3b88a10d2edf26eb47ab"
    ),
    "paper.sqlite": (
        "384828dd21e9abc82afabec955184eed22cf57839e72bcd43c74d162534663b9"
    ),
    "wake.sqlite": ("210812b956aba6d59dcf3cfbf398ebd628c972cfffbb6dd39bd96ef308a6887f"),
}
ZERO_EFFECTS = {
    "provider_calls": 0,
    "oauth_reads": 0,
    "scheduler_reads": 0,
    "scheduler_writes": 0,
    "broker_effects": 0,
    "file_mutations": 0,
}
_attempt_consumed = False
_attempt_lock = Lock()


class RecoveryError(RuntimeError):
    """Fixed sanitized diagnostics only."""


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _source() -> dict[str, str]:
    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(SOURCE_ROOT), *args],
            input="",
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        if len(result.stdout) > 4096:
            raise RecoveryError("recovery source rejected")
        return result.stdout.strip()

    if (
        sys.platform != "win32"
        or not sys.flags.isolated
        or not sys.dont_write_bytecode
        or Path(__file__).resolve().parents[3] != SOURCE_ROOT.resolve(strict=True)
        or Path(git("rev-parse", "--show-toplevel")).resolve(strict=True)
        != SOURCE_ROOT.resolve(strict=True)
        or git("branch", "--show-current") != SOURCE_BRANCH
        or git("remote", "get-url", "origin") != ORIGIN
        or git("status", "--porcelain=v1", "--untracked-files=all")
    ):
        raise RecoveryError("recovery source rejected")
    head, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    tracking = "refs/remotes/origin/" + SOURCE_BRANCH
    if (
        any(re.fullmatch(r"[0-9a-f]{40}", value) is None for value in (head, tree))
        or git("rev-parse", tracking) != head
        or git("rev-parse", tracking + "^{tree}") != tree
    ):
        raise RecoveryError("recovery source rejected")
    # The reviewed canonical plan binds these exact IDs without a self-hash cycle.
    return {"source_head": head, "source_tree": tree}


def _require_parent(observed: read_only.DirectoryObservation, role: str) -> None:
    """The accepted 133-I-R1 concrete-rights admission for these same parents."""
    admins = {read_only.ADMINISTRATORS_SID, read_only.SYSTEM_SID}
    if role == "VOLUME":
        allowed = 0x1F01FF & ~(0x40 | 0x40000 | 0x80000)
        flags_allowed = 0x1B
    elif role == "PARENT":
        allowed, flags_allowed = 0x1200A9, 0x13
    else:
        raise RecoveryError("recovery parent role rejected")
    if (
        observed.owner_sid not in admins
        or observed.filesystem != "NTFS"
        or observed.reparse is not False
    ):
        raise RecoveryError("recovery parent rejected")
    full = set()
    for sid, mask, kind, flags in observed.aces:
        if kind != 0 or flags & ~flags_allowed:
            raise RecoveryError("recovery parent ACE rejected")
        if role == "VOLUME" and flags & 8:
            if not flags & 3:
                raise RecoveryError("recovery volume template rejected")
            continue
        if sid in admins:
            if mask == 0x1F01FF:
                full.add(sid)
        elif mask & ~allowed:
            raise RecoveryError("recovery parent replacement rejected")
    if full != admins:
        raise RecoveryError("recovery parent control rejected")


class _RetainedRoot:
    """One held root open, pinned parents/files, no reopen or fallback authority."""

    def __init__(self) -> None:
        self.held = ExitStack()
        self.used = False
        self.attempted = False
        self.native_attempts = 0
        self.handle = None
        self.parents = []
        self.files = []

    def __enter__(self) -> _RetainedRoot:
        if self.used or _attempt_consumed:
            raise RecoveryError("recovery authority consumed")
        self.used = True
        try:
            self.source = _source()
            self.sid = administrator.administrator_sid()
            for path in PARENTS:
                handle = read_only.open_directory(path)
                self.held.callback(read_only.close_handle, handle)
                observation, digest = read_only.inspect_directory_security(handle, path)
                _require_parent(
                    observation, "VOLUME" if path == PARENTS[0] else "PARENT"
                )
                self.parents.append((handle, path, observation, digest))
            self.handle = read_only.open_directory(TARGET_PATH, mutable=True)
            self.held.callback(read_only.close_handle, self.handle)
            self.names = retained_reads.namespace(self.handle)
            if tuple(name for name, _ in self.names) != retained_reads.FINAL_NAMES:
                raise RecoveryError("recovery namespace rejected")
            for name in retained_reads.FINAL_NAMES:
                handle = retained_reads.open_retained_file(name)
                self.held.callback(read_only.close_handle, handle)
                self.files.append((handle, name))
            return self
        except BaseException:
            self.held.close()
            raise

    def __exit__(self, *exc: object) -> None:
        self.held.close()

    def root(self) -> tuple[read_only.DirectoryObservation, str]:
        return read_only.inspect_directory_security(self.handle, TARGET_PATH)

    def retained(self, *, strict: bool = True) -> dict:
        names = retained_reads.namespace(self.handle)
        hashes = {}
        for handle, name in self.files:
            identity, digest = retained_reads.file_snapshot(handle, name)
            if identity != (ROOT_IDENTITY[0], dict(names).get(name)):
                raise RecoveryError("recovery retained identity rejected")
            hashes[name] = digest
        if strict and (names != self.names or hashes != FILE_HASHES):
            raise RecoveryError("recovery retained state changed")
        return {"namespace": names, "file_hashes": hashes}

    def finish(self) -> None:
        if _source() != self.source or administrator.administrator_sid() != self.sid:
            raise RecoveryError("recovery source or administrator changed")
        for handle, path, observation, digest in self.parents:
            if read_only.inspect_directory_security(handle, path) != (
                observation,
                digest,
            ):
                raise RecoveryError("recovery parent changed")

    def snapshot(self) -> dict:
        before, digest = self.root()
        if (
            before.identity != ROOT_IDENTITY
            or before.classification() != "ADMIN_SYSTEM_ONLY"
            or before.filesystem != "NTFS"
            or before.reparse is not False
            or digest != PRE_SECURITY_SHA256
        ):
            raise RecoveryError("recovery retained baseline rejected")
        retained = self.retained()
        self.finish()
        return {
            **self.source,
            "administrator_sid": self.sid,
            "trading_sid": read_only.TRADING_SID,
            "root_identity": before.identity,
            "pre_application_policy": before.classification(),
            "pre_root_security_sha256": digest,
            "parents": [
                {"path": path, **asdict(obs), "security_sha256": security}
                for _, path, obs, security in self.parents
            ],
            **retained,
        }

    def apply_once(self, reviewed: str, authorization: str) -> int:
        global _attempt_consumed
        if self.handle is None or self.attempted:
            raise RecoveryError("recovery attempt rejected")
        _authority(reviewed, authorization)
        plan = _plan(self)
        if plan["plan_sha256"] != reviewed:
            raise RecoveryError("recovery reviewed pre-state changed")
        current = self.snapshot()
        if current != {key: plan[key] for key in current}:
            raise RecoveryError("recovery immediate pre-state changed")
        with _attempt_lock:
            if _attempt_consumed:
                raise RecoveryError("recovery authority consumed")
            self.attempted = _attempt_consumed = True
        previous = root_policy_apply.native_application_attempts()
        try:
            return apply_root_policy_status(self.handle)
        finally:
            self.native_attempts = (
                root_policy_apply.native_application_attempts() - previous
            )


def _plan(backend: _RetainedRoot) -> dict:
    first = backend.snapshot()
    if backend.snapshot() != first:
        raise RecoveryError("recovery plan drift")
    payload = {
        "schema": PLAN_SCHEMA,
        "target_path": TARGET_PATH,
        "final_path": "\\\\?\\" + TARGET_PATH,
        **first,
        "filesystem": "NTFS",
        "reparse": False,
        "open_requested_access": read_only.MUTABLE_ROOT_ACCESS,
        "open_share_mode": read_only.ROOT_SHARE_MODE,
        "open_disposition": read_only.ROOT_DISPOSITION,
        "open_flags": read_only.ROOT_FLAGS,
        "intended_owner_sid": read_only.ADMINISTRATORS_SID,
        "intended_dacl_protected": True,
        "intended_aces": read_only.ROOT_ACES,
        "acl_mutation_attempts": 0,
        **ZERO_EFFECTS,
    }
    return {**payload, "plan_sha256": hashlib.sha256(canonical(payload)).hexdigest()}


def plan_recovery() -> dict:
    """Operator-only, read-only plan. Source gates must never call this surface."""
    try:
        with _RetainedRoot() as backend:
            result = _plan(backend)
        if _source() != backend.source:
            raise RecoveryError("recovery source changed")
        return result
    except BaseException:
        raise RecoveryError("recovery planning failed closed") from None


def _authority(reviewed: str, authorization: str) -> None:
    if (
        type(reviewed) is not str
        or re.fullmatch(r"[0-9a-f]{64}", reviewed) is None
        or type(authorization) is not str
        or authorization != "AUTHORIZE Q133-K ROOT-ACL " + reviewed
        or not sys.stdin.isatty()
        or _attempt_consumed
    ):
        raise RecoveryError("recovery authorization rejected")


def execute_recovery_once(reviewed: str, authorization: str) -> dict:
    """PROTECTED: one application, no retry after any attempted native call."""
    _authority(reviewed, authorization)  # Before source/native observations.
    evidence = {
        "schema": RESULT_SCHEMA,
        "target_path": TARGET_PATH,
        "source_head": None,
        "source_tree": None,
        "administrator_sid": None,
        "trading_sid": read_only.TRADING_SID,
        "plan_sha256": reviewed,
        "root_identity_before": None,
        "root_identity_after": None,
        "pre_application_policy": "UNOBSERVED",
        "pre_root_security_sha256": None,
        "native_set_security_info_status": None,
        "post_application_policy": "UNOBSERVED",
        "post_root_security_sha256": None,
        "exact_intended_policy_match": False,
        "namespace_unchanged": False,
        "file_hashes_before": None,
        "file_hashes_after": None,
        "file_hashes_unchanged": False,
        "filesystem": None,
        "reparse": None,
        "acl_mutation_attempts": 0,
        "status": "FAILED_CLOSED",
        **ZERO_EFFECTS,
    }
    backend = _RetainedRoot()
    try:
        with backend:
            plan = _plan(backend)
            if plan["plan_sha256"] != reviewed:
                raise RecoveryError("recovery reviewed plan changed")
            for key in (
                "source_head",
                "source_tree",
                "administrator_sid",
                "pre_application_policy",
                "pre_root_security_sha256",
            ):
                evidence[key] = plan[key]
            evidence["root_identity_before"] = plan["root_identity"]
            evidence["file_hashes_before"] = plan["file_hashes"]
            # Independently admit all held pre-state immediately before consumption.
            current = backend.snapshot()
            if current != {key: plan[key] for key in current}:
                raise RecoveryError("recovery pre-state changed")
            call_succeeded = False
            try:
                status = backend.apply_once(reviewed, authorization)
                if type(status) is int and 0 <= status <= 0xFFFFFFFF:
                    evidence["native_set_security_info_status"] = status
                    call_succeeded = True
            except BaseException:
                pass
            finally:
                evidence["acl_mutation_attempts"] = backend.native_attempts
                # Independent root readback even on nonzero status or exception.
                after, security = backend.root()
                evidence.update(
                    {
                        "root_identity_after": after.identity,
                        "post_application_policy": after.classification(),
                        "post_root_security_sha256": security,
                        "filesystem": after.filesystem,
                        "reparse": after.reparse,
                        "exact_intended_policy_match": (
                            after.classification() == "EXACT_INTENDED_ROOT"
                            and after.identity == ROOT_IDENTITY
                            and after.filesystem == "NTFS"
                            and after.reparse is False
                        ),
                    }
                )
            retained = backend.retained(strict=False)
            evidence["namespace_unchanged"] = retained["namespace"] == plan["namespace"]
            evidence["file_hashes_after"] = retained["file_hashes"]
            evidence["file_hashes_unchanged"] = (
                retained["file_hashes"] == plan["file_hashes"]
            )
            backend.finish()
            passed = (
                call_succeeded
                and backend.native_attempts == 1
                and evidence["native_set_security_info_status"] == 0
                and evidence["exact_intended_policy_match"]
                and evidence["namespace_unchanged"]
                and evidence["file_hashes_unchanged"]
            )
        if _source() == backend.source and passed:
            evidence["status"] = "PASS"
    except BaseException:
        pass
    evidence["acl_mutation_attempts"] = backend.native_attempts
    return evidence


def main(argv: list[str] | None = None) -> int:
    """Exact grammar; the plan is recomputed before a real terminal prompt."""
    try:
        args = sys.argv[1:] if argv is None else argv
        if args == ["plan"]:
            result = plan_recovery()
        elif (
            len(args) == 3
            and args[:2] == ["execute-once", "--reviewed-plan-sha256"]
            and re.fullmatch(r"[0-9a-f]{64}", args[2]) is not None
            and sys.stdin.isatty()
        ):
            if plan_recovery()["plan_sha256"] != args[2]:
                raise RecoveryError("recovery reviewed plan changed")
            print(
                "Type AUTHORIZE Q133-K ROOT-ACL followed by the reviewed plan SHA-256:",
                file=sys.stderr,
            )
            authorization = sys.stdin.readline(160).rstrip("\r\n")
            result = execute_recovery_once(args[2], authorization)
        else:
            raise RecoveryError("recovery arguments rejected")
        print(canonical(result).decode("utf-8"))
        return 0 if result.get("status", "PASS") == "PASS" else 3
    except BaseException:
        print(
            '{"reason":"RETAINED_RECOVERY_FAILED_CLOSED","schema":"'
            + RESULT_SCHEMA
            + '"}',
            file=sys.stderr,
        )
        return 3
