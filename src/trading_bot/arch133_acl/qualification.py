"""133-I scratch-only native qualification. Importing this module has no effects.

The sole mutation destination is the versioned literal SCRATCH_PATH. No HostRoot
or trading/runtime/provider/scheduler code is imported. All failures retain the
scratch object; there is no cleanup, repair, retry or caller-selected path API.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from trading_bot.arch133_acl import primitive

SCRATCH_PATH = r"F:\AI\temp\arch133i-root-acl-qualification-v1"
PARENTS = ("F:\\", r"F:\AI", r"F:\AI\temp")
SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133i")
SOURCE_BRANCH = "feature/robinhood-unattended-review-paper-133i"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
SCHEMA = "arch133i-scratch-root-acl-qualification/v1"
ZERO_EFFECTS = {
    "provider_calls": 0,
    "oauth_reads": 0,
    "scheduler_reads": 0,
    "scheduler_writes": 0,
    "broker_effects": 0,
    "production_arch133_mutations": 0,
}


class QualificationError(RuntimeError):
    """Only fixed, bounded evidence may cross the qualification boundary."""


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
            raise QualificationError("scratch source rejected")
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
        raise QualificationError("scratch source rejected")
    head, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    if any(re.fullmatch(r"[0-9a-f]{40}", value) is None for value in (head, tree)):
        raise QualificationError("scratch source rejected")
    return {"source_head": head, "source_tree": tree}


def _require_parent_security(
    observed: primitive.DirectoryObservation, role: str
) -> None:
    """Admit the volume and components using distinct concrete-rights policies."""
    administrators = {primitive.ADMINISTRATORS_SID, primitive.SYSTEM_SID}
    if role == "VOLUME":
        # Data/sibling creation and DELETE on the volume cannot replace its child.
        # Generic/unknown effective rights cannot hide replacement authority.
        non_admin_rights = 0x1F01FF & ~(0x40 | 0x40000 | 0x80000)
        allowed_flags = 0x1B  # OI, CI, IO, INHERITED; no NO_PROPAGATE.
    elif role == "PARENT":
        # Components remain read/traverse-only for every unrelated principal.
        non_admin_rights = 0x1200A9
        allowed_flags = 0x13  # OI, CI, INHERITED; no inherit-only templates.
    else:
        raise QualificationError("scratch parent role rejected")
    if observed.owner_sid not in administrators:
        raise QualificationError("scratch parent owner rejected")
    full: set[str] = set()
    for sid, mask, kind, flags in observed.aces:
        if kind != 0 or flags & ~allowed_flags:
            raise QualificationError("scratch parent ACE rejected")
        if role == "VOLUME" and flags & 0x08:
            if not flags & 0x03:
                raise QualificationError("scratch volume template rejected")
            # Templates do not act on this volume or count as effective control.
            # Each governed component is inspected independently below.
            continue
        if sid in administrators:
            if mask == 0x1F01FF:
                full.add(sid)
        elif mask & ~non_admin_rights:
            raise QualificationError("scratch parent replacement rejected")
    if full != administrators:
        raise QualificationError("scratch parent full control rejected")


class ScratchNative:
    """Fixed namespace, pinned no-follow parents, one native creation/application."""

    def __init__(self) -> None:
        self._armed = False
        self._attempted = False
        self._applied = False
        self._held = ExitStack()
        self._handle = None
        self._parents: tuple[primitive.DirectoryObservation, ...] = ()
        self._parent_handles: list[tuple[int, str]] = []
        self._source_facts: dict[str, str] = {}
        self._sid = ""
        self._guarded = False

    def __enter__(self) -> ScratchNative:
        return self

    def __exit__(self, *exc: object) -> None:
        self._guarded = False
        self._held.close()

    @contextmanager
    def guard(self) -> Iterator[None]:
        self._sid = primitive.administrator_sid()
        facts = []
        for path in PARENTS:
            handle = primitive.open_directory(path)
            self._held.callback(primitive.close_handle, handle)
            self._parent_handles.append((handle, path))
            observed = primitive.inspect_directory(handle, path)
            _require_parent_security(
                observed, "VOLUME" if path == PARENTS[0] else "PARENT"
            )
            facts.append(observed)
        self._parents = tuple(facts)
        self._guarded = True
        try:
            yield
        finally:
            self._guarded = False

    def _absent(self) -> None:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        attributes = kernel.GetFileAttributesW
        attributes.argtypes, attributes.restype = [ctypes.c_wchar_p], ctypes.c_uint32
        if attributes(SCRATCH_PATH) != 0xFFFFFFFF or ctypes.get_last_error() != 2:
            raise QualificationError("scratch occupied or absence unproven")

    def snapshot(self) -> dict:
        if not self._guarded or self._attempted:
            raise QualificationError("scratch admission rejected")
        self._absent()
        facts = _source()
        if self._source_facts and facts != self._source_facts:
            raise QualificationError("scratch source changed")
        self._source_facts = facts
        self.finish()
        return {
            **facts,
            "administrator_sid": self._sid,
            "trading_sid": primitive.TRADING_SID,
            "parents_sha256": hashlib.sha256(
                canonical(
                    [
                        [item.owner_sid, item.protected, item.aces, item.identity]
                        for item in self._parents
                    ]
                )
            ).hexdigest(),
        }

    def finish(self) -> None:
        if not self._guarded or _source() != self._source_facts:
            raise QualificationError("scratch source or guard changed")
        if (
            tuple(
                primitive.inspect_directory(handle, path)
                for handle, path in self._parent_handles
            )
            != self._parents
        ):
            raise QualificationError("scratch parent changed")

    def arm_once(self, reviewed: str, authorization: str) -> None:
        if (
            not self._guarded
            or self._armed
            or self._attempted
            or type(reviewed) is not str
            or re.fullmatch(r"[0-9a-f]{64}", reviewed) is None
            or type(authorization) is not str
            or authorization != "AUTHORIZE Q133-I SCRATCH " + reviewed
            or _plan(self)["plan_sha256"] != reviewed
        ):
            raise QualificationError("scratch native authorization rejected")
        self._armed = True

    def create_root_once(self) -> None:
        if not self._guarded or not self._armed or self._attempted:
            raise QualificationError("scratch already attempted")
        self._attempted = True  # Consume before probing/creating, even on ambiguity.
        self._absent()
        primitive.create_admin_directory(SCRATCH_PATH)
        self._handle = primitive.open_directory(SCRATCH_PATH, mutable=True)
        self._held.callback(primitive.close_handle, self._handle)

    def inspect(self) -> primitive.DirectoryObservation:
        if self._handle is None:
            raise QualificationError("scratch handle missing")
        return primitive.inspect_directory(self._handle, SCRATCH_PATH)

    def apply_once(self) -> int:
        if (
            not self._guarded
            or not self._armed
            or not self._attempted
            or self._handle is None
            or self._applied
        ):
            raise QualificationError("scratch application already attempted")
        self._applied = True
        return primitive.apply_root_policy_status(self._handle)


def _plan(backend: ScratchNative) -> dict:
    payload = {
        "schema": "arch133i-scratch-root-acl-plan/v1",
        "scratch_path": SCRATCH_PATH,
        **backend.snapshot(),
        "scratch_absent": True,
        "filesystem": "NTFS",
        "reparse": False,
        "intended_owner_sid": primitive.ADMINISTRATORS_SID,
        "intended_dacl_protected": True,
        "intended_aces": primitive.ROOT_ACES,
        **ZERO_EFFECTS,
    }
    return {**payload, "plan_sha256": hashlib.sha256(canonical(payload)).hexdigest()}


def _execute_once(backend: ScratchNative, reviewed: str, authorization: str) -> dict:
    # Reject malformed authority even before observing native/source state.
    if (
        type(reviewed) is not str
        or re.fullmatch(r"[0-9a-f]{64}", reviewed) is None
        or type(authorization) is not str
        or authorization != "AUTHORIZE Q133-I SCRATCH " + reviewed
    ):
        raise QualificationError("scratch authorization rejected")
    plan = _plan(backend)
    if plan["plan_sha256"] != reviewed:
        raise QualificationError("scratch reviewed plan changed")
    evidence = {
        "schema": SCHEMA,
        "scratch_path": SCRATCH_PATH,
        "source_head": plan["source_head"],
        "source_tree": plan["source_tree"],
        "administrator_sid": plan["administrator_sid"],
        "trading_sid": primitive.TRADING_SID,
        "plan_sha256": reviewed,
        "pre_application_policy": "UNOBSERVED",
        "native_set_security_info_status": None,
        "post_application_policy": "UNOBSERVED",
        "exact_intended_policy_match": False,
        "filesystem": "NTFS",
        "reparse": False,
        "status": "FAILED_CLOSED",
        **ZERO_EFFECTS,
    }
    try:
        backend.arm_once(reviewed, authorization)
        backend.create_root_once()
        before = backend.inspect()
        evidence["pre_application_policy"] = before.classification()
        if (
            before.classification() != "ADMIN_SYSTEM_ONLY"
            or before.filesystem != "NTFS"
            or before.reparse is not False
        ):
            raise QualificationError("scratch creation policy rejected")
        status = backend.apply_once()
        if type(status) is not int or not 0 <= status <= 0xFFFFFFFF:
            raise QualificationError("scratch native status rejected")
        evidence["native_set_security_info_status"] = status
        # Always read independently, including nonzero native status. Never retry.
        after = backend.inspect()
        evidence["post_application_policy"] = after.classification()
        exact = (
            after.classification() == "EXACT_INTENDED_ROOT"
            and after.identity == before.identity
            and after.filesystem == "NTFS"
            and after.reparse is False
        )
        evidence["exact_intended_policy_match"] = exact
        backend.finish()
        if status == 0 and exact:
            evidence["status"] = "PASS"
    except BaseException:
        pass  # Retain bounded fields only, including a status already returned.
    return evidence


def plan_scratch() -> dict:
    """Provider-free read-only plan; never create the scratch root."""
    try:
        with ScratchNative() as backend, backend.guard():
            first = _plan(backend)
            if _plan(backend) != first:
                raise QualificationError("scratch plan drift")
            return first
    except BaseException:
        raise QualificationError("scratch planning failed closed") from None


def execute_scratch_once(reviewed: str, authorization: str) -> dict:
    """PROTECTED: fresh reviewed plan + exact authority; fixed destination only."""
    result = None
    try:
        if (
            type(reviewed) is not str
            or re.fullmatch(r"[0-9a-f]{64}", reviewed) is None
            or type(authorization) is not str
            or authorization != "AUTHORIZE Q133-I SCRATCH " + reviewed
        ):
            raise QualificationError("scratch authorization rejected")
        with ScratchNative() as backend, backend.guard():
            result = _execute_once(backend, reviewed, authorization)
        return result
    except BaseException:
        if result is not None:
            result["status"] = "FAILED_CLOSED"
            return result
        raise QualificationError(
            "scratch stopped; no retry or repair authorized"
        ) from None


def main(argv: list[str] | None = None) -> int:
    """Exact CLI grammar only; authorization must arrive on real terminal stdin."""
    try:
        args = sys.argv[1:] if argv is None else argv
        if args == ["plan"]:
            result = plan_scratch()
        elif (
            len(args) == 3
            and args[:2] == ["execute-once", "--reviewed-plan-sha256"]
            and re.fullmatch(r"[0-9a-f]{64}", args[2]) is not None
            and sys.stdin.isatty()
        ):
            if plan_scratch()["plan_sha256"] != args[2]:
                raise QualificationError("scratch plan changed")
            print(
                "Type AUTHORIZE Q133-I SCRATCH followed by the reviewed plan SHA-256:",
                file=sys.stderr,
            )
            authorization = sys.stdin.readline(160).rstrip("\r\n")
            result = execute_scratch_once(args[2], authorization)
        else:
            raise QualificationError("scratch arguments rejected")
        print(canonical(result).decode("utf-8"))
        return 0 if result.get("status", "PASS") == "PASS" else 3
    except BaseException:
        print(
            '{"reason":"SCRATCH_QUALIFICATION_FAILED_CLOSED",'
            '"schema":"arch133i-scratch-root-acl-qualification/v1"}',
            file=sys.stderr,
        )
        return 3
