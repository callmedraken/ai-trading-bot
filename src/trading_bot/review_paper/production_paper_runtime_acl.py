"""D1Q-R2 fixed native ACL operator. Import and diagnostic are inert/read-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from trading_bot.runtime.windows_authority_security import (
    ARCH134_RUNTIME_TARGETS,
    DELETE,
    FILE_ADD_FILE,
    FILE_ALL_ACCESS,
    FILE_EXECUTE,
    FILE_LIST_DIRECTORY,
    FILE_READ_ATTRIBUTES,
    FILE_READ_EA,
    FILE_TRAVERSE,
    INHERIT_ONLY_ACE,
    OBJECT_INHERIT_ACE,
    READ_CONTROL,
    SYNCHRONIZE,
    AuthorityObjectKind,
    SecurityAce,
    SecurityInspection,
    SecurityPolicy,
    WindowsHandle,
    apply_security_policy,
    close_security_object_checked,
    inspect_open_authority_object,
    inspect_security_object_identity,
    open_arch134_runtime_object,
    require_administrator_token,
    resolve_current_token_sid,
    sqlite_trading_file_rights,
)

BRANCH = "feature/robinhood-production-paper-runtime-acl"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
EXECUTE_INTERLOCK = "PROVISION_ARCH134_D1_RUNTIME_ACL_FOR_CURRENT_TOKEN"
ADMINISTRATORS = "S-1-5-32-544"
SYSTEM = "S-1-5-18"
DIAGNOSED_RX = (
    FILE_LIST_DIRECTORY
    | FILE_READ_EA
    | FILE_EXECUTE
    | FILE_READ_ATTRIBUTES
    | READ_CONTROL
    | SYNCHRONIZE
)
ROOT_RIGHTS = (
    FILE_TRAVERSE
    | FILE_LIST_DIRECTORY
    | FILE_ADD_FILE
    | FILE_READ_EA
    | FILE_READ_ATTRIBUTES
    | READ_CONTROL
    | SYNCHRONIZE
)
_LOGON_SID = re.compile(r"S-1-5-5-(0|[1-9][0-9]{0,9})-(0|[1-9][0-9]{0,9})\Z")
_USER_SID = re.compile(r"S-1-5-21-(?:[1-9][0-9]{0,9}-){3}[1-9][0-9]{0,9}\Z")


def runtime_policy(runtime_sid: str, *, directory: bool) -> SecurityPolicy:
    """Concrete protected policy; execute separately binds SID to token user."""
    if not _USER_SID.fullmatch(runtime_sid):
        raise ValueError("runtime principal class rejected")
    full = (
        SecurityAce(ADMINISTRATORS, FILE_ALL_ACCESS),
        SecurityAce(SYSTEM, FILE_ALL_ACCESS),
    )
    if directory:
        return SecurityPolicy(
            ADMINISTRATORS,
            (
                *full,
                SecurityAce(runtime_sid, ROOT_RIGHTS),
                SecurityAce(
                    runtime_sid,
                    sqlite_trading_file_rights() | DELETE,
                    ace_flags=OBJECT_INHERIT_ACE | INHERIT_ONLY_ACE,
                ),
            ),
        )
    return SecurityPolicy(
        ADMINISTRATORS, (*full, SecurityAce(runtime_sid, sqlite_trading_file_rights()))
    )


@dataclass(frozen=True)
class Observation:
    security: SecurityInspection
    identity: tuple[int, int, int]


class NativeRuntimeAcl:
    """Only fixed-target native primitives and bounded nonrecursive inventory."""

    def open(self, path: str, *, update: bool) -> WindowsHandle:
        return open_arch134_runtime_object(path, _kind(path), for_update=update)

    def inspect(self, handle: WindowsHandle, path: str) -> Observation:
        return Observation(
            inspect_open_authority_object(handle.value, path, _kind(path)),
            inspect_security_object_identity(handle),
        )

    def names(self) -> tuple[str, ...]:
        # The root is pinned without delete sharing. Never visit any child.
        names = []
        with os.scandir(ARCH134_RUNTIME_TARGETS[0]) as entries:
            for entry in entries:
                if len(names) == 2:
                    raise ValueError("runtime inventory ambiguity")
                names.append(entry.name)
        return tuple(sorted(names))

    def apply(self, handle: WindowsHandle, policy: SecurityPolicy) -> None:
        apply_security_policy(handle.value, policy)

    def close(self, handle: WindowsHandle) -> None:
        close_security_object_checked(handle)


def _kind(path: str) -> AuthorityObjectKind:
    if path not in ARCH134_RUNTIME_TARGETS:
        raise ValueError("fixed target rejected")
    return (
        AuthorityObjectKind.DIRECTORY
        if path == ARCH134_RUNTIME_TARGETS[0]
        else AuthorityObjectKind.FILE
    )


def _classify(observation: Observation, path: str, sid: str) -> str:
    s = observation.security
    if (
        s.expected_path != path
        or s.final_path != path
        or s.kind is not _kind(path)
        or s.is_reparse_point is not False
        or s.volume_root != "F:\\"
        or s.filesystem != "NTFS"
        or s.owner_sid != ADMINISTRATORS
        or len(observation.identity) != 3
        or any(type(v) is not int or v < 0 for v in observation.identity)
        or observation.identity[1] == 0
        or (s.kind is AuthorityObjectKind.FILE and observation.identity[2] != 1)
    ):
        raise ValueError("object admission rejected")
    if runtime_policy(sid, directory=s.kind is AuthorityObjectKind.DIRECTORY).matches(
        s
    ):
        return "ALREADY_PROVISIONED"
    if (
        s.dacl_protected is False
        and len(s.aces) == 3
        and s.aces[:2]
        == (
            SecurityAce(ADMINISTRATORS, FILE_ALL_ACCESS),
            SecurityAce(SYSTEM, FILE_ALL_ACCESS),
        )
        and _LOGON_SID.fullmatch(s.aces[2].principal_sid)
        and all(
            int(part) <= 0xFFFFFFFF for part in s.aces[2].principal_sid.split("-")[-2:]
        )
        and s.aces[2] == SecurityAce(s.aces[2].principal_sid, DIAGNOSED_RX)
    ):
        return "NEEDS_PROVISIONING"
    raise ValueError("security admission rejected")


def _observe(
    api: NativeRuntimeAcl, handles: dict[str, WindowsHandle], sid: str
) -> tuple[str, dict[str, Observation]]:
    if api.names() != ("armed-sessions.sqlite", "paper.sqlite"):
        raise ValueError("sidecar or inventory ambiguity")
    observations = {p: api.inspect(handles[p], p) for p in ARCH134_RUNTIME_TARGETS}
    states = {_classify(observations[p], p, sid) for p in ARCH134_RUNTIME_TARGETS}
    if len(states) != 1:
        raise ValueError("partial ACL state requires reconciliation")
    if len({o.identity[:2] for o in observations.values()}) != 3:
        raise ValueError("target identity ambiguity")
    if len({o.identity[0] for o in observations.values()}) != 1:
        raise ValueError("target volume ambiguity")
    if (
        states == {"NEEDS_PROVISIONING"}
        and len({o.security.aces[2].principal_sid for o in observations.values()}) != 1
    ):
        raise ValueError("logon security class drift")
    return states.pop(), observations


def _close_all(api: NativeRuntimeAcl, handles: dict[str, WindowsHandle]) -> None:
    ambiguous = False
    while handles:
        _, handle = handles.popitem()
        try:
            api.close(handle)
        except BaseException:
            ambiguous = True
    if ambiguous:
        raise ValueError("close ambiguity")


def inspect_or_provision(
    *,
    expected_runtime_sid: str | None = None,
    execute: bool = False,
    publish: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, object]:
    """Protected work binds the supplied SID to the elevated caller before open."""
    result: dict[str, object] = {
        "schema": "production-paper-runtime-acl/v1",
        "status": "BLOCKED",
        "result": "FAIL",
        "runtime_sid_digest": None,
        "acl_apply_attempts": 0,
        "acl_applies_verified": 0,
        "parent_mutations": 0,
        "recursive_mutations": 0,
        "credential_mutations": 0,
        "scheduler_mutations": 0,
        "provider_calls": 0,
        "paper_mutations": 0,
        "session_mutations": 0,
        "broker_mutations": 0,
    }
    handles: dict[str, WindowsHandle] = {}
    api = NativeRuntimeAcl()
    attempted = 0
    try:
        if execute:
            require_administrator_token()
        sid = resolve_current_token_sid()
        if not _USER_SID.fullmatch(sid) or (execute and expected_runtime_sid != sid):
            raise ValueError("current token binding rejected")
        result["runtime_sid_digest"] = hashlib.sha256(
            b"arch134-runtime-sid/v1\0" + sid.encode("ascii")
        ).hexdigest()
        for path in ARCH134_RUNTIME_TARGETS:
            handles[path] = api.open(path, update=execute)
        state, before = _observe(api, handles, sid)
        if execute and state == "NEEDS_PROVISIONING":
            # Re-observe all pinned targets immediately before the first apply.
            repeated_state, repeated = _observe(api, handles, sid)
            if repeated_state != state or repeated != before:
                raise ValueError("before state drift")
            for path in (
                ARCH134_RUNTIME_TARGETS[1],
                ARCH134_RUNTIME_TARGETS[2],
                ARCH134_RUNTIME_TARGETS[0],
            ):
                if api.names() != ("armed-sessions.sqlite", "paper.sqlite"):
                    raise ValueError("inventory drift")
                current = api.inspect(handles[path], path)
                if current != before[path]:
                    raise ValueError("pre-apply drift")
                policy = runtime_policy(
                    sid, directory=_kind(path) is AuthorityObjectKind.DIRECTORY
                )
                attempted += 1  # Even an unsuccessful native call may be ambiguous.
                result["acl_apply_attempts"] = attempted
                result.update(status="STOPPED_AFTER_APPLY", result="FAIL")
                if publish is not None:
                    publish(result)
                api.apply(handles[path], policy)
                after = api.inspect(handles[path], path)
                if (
                    after.identity != before[path].identity
                    or _classify(after, path, sid) != "ALREADY_PROVISIONED"
                ):
                    raise ValueError("post-apply drift")
                result["acl_applies_verified"] = attempted
            _close_all(api, handles)
            for path in ARCH134_RUNTIME_TARGETS:
                handles[path] = api.open(path, update=False)
            fresh_state, fresh = _observe(api, handles, sid)
            if fresh_state != "ALREADY_PROVISIONED" or any(
                fresh[p].identity != before[p].identity for p in ARCH134_RUNTIME_TARGETS
            ):
                raise ValueError("fresh verification drift")
            state = "PROVISIONED"
        _close_all(api, handles)
        result.update(status=state, result="PASS")
    except BaseException:
        try:
            _close_all(api, handles)
        except BaseException:
            pass
        result.update(
            status="STOPPED_AFTER_APPLY" if attempted else "BLOCKED", result="FAIL"
        )
    return result


def admit_source(head: str, tree: str) -> tuple[Path, ...]:
    """Exact clean branch/tree/origin/live remote and tracked import admission."""
    if any(re.fullmatch(r"[0-9a-f]{40}", value) is None for value in (head, tree)):
        raise ValueError("source identity rejected")
    root = Path(__file__).resolve().parents[3]

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()

    if (
        Path(git("rev-parse", "--show-toplevel")).resolve() != root
        or git("branch", "--show-current") != BRANCH
        or git("rev-parse", "HEAD") != head
        or git("rev-parse", "HEAD^{tree}") != tree
        or git("status", "--porcelain", "--untracked-files=no")
        or git("remote", "get-url", "origin") != ORIGIN
        or git("rev-parse", "origin/" + BRANCH) != head
        or git("rev-parse", "origin/" + BRANCH + "^{tree}") != tree
        or git("ls-remote", "origin", "refs/heads/" + BRANCH)
        != head + "\trefs/heads/" + BRANCH
    ):
        raise ValueError("source admission rejected")
    for name, module in tuple(sys.modules.items()):
        if name == "trading_bot" or name.startswith("trading_bot."):
            filename = getattr(module, "__file__", None)
            if not filename or not Path(filename).resolve().is_relative_to(
                root / "src"
            ):
                raise ValueError("mixed imports rejected")
            relative = Path(filename).resolve().relative_to(root).as_posix()
            git("ls-files", "--error-unmatch", "--", relative)
    return tuple(
        Path(line[9:]).resolve()
        for line in git("worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    )


def _evidence_path(path: Path, roots: tuple[Path, ...]) -> None:
    if (
        not path.is_absolute()
        or path.exists()
        or path.is_symlink()
        or not path.parent.is_dir()
        or ":" in path.name
        or any(
            path.resolve().is_relative_to(root.resolve())
            for root in (*roots, Path(r"F:\AITradingBot"))
        )
    ):
        raise ValueError("evidence rejected")
    for ancestor in (path, *path.parents):
        if ancestor.exists() and (
            ancestor.is_symlink()
            or getattr(ancestor.lstat(), "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("evidence redirection rejected")


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("invalid arguments")


def main(argv: list[str] | None = None) -> int:
    result: dict[str, object] = {
        "schema": "production-paper-runtime-acl/v1",
        "status": "BLOCKED",
        "result": "FAIL",
    }
    try:
        parser = _Parser(
            description="Fixed D1 runtime ACL diagnostic/provisioning only"
        )
        parser.add_argument("--expected-head", required=True)
        parser.add_argument("--expected-tree", required=True)
        modes = parser.add_mutually_exclusive_group(required=True)
        modes.add_argument("--diagnose", action="store_true")
        modes.add_argument("--execute", choices=(EXECUTE_INTERLOCK,))
        parser.add_argument("--expected-runtime-sid")
        parser.add_argument("--evidence", type=Path)
        args = parser.parse_args(argv)
        if args.diagnose and (
            args.evidence is not None or args.expected_runtime_sid is not None
        ):
            raise ValueError("diagnostic arguments rejected")
        if args.execute and (
            args.evidence is None or args.expected_runtime_sid is None
        ):
            raise ValueError("protected arguments required")
        roots = admit_source(args.expected_head, args.expected_tree)
        if args.diagnose:
            result = inspect_or_provision()
        else:
            _evidence_path(args.evidence, roots)
            # Fresh evidence is reserved and flushed before any native ACL attempt.
            with args.evidence.open("xb") as stream:

                def publish(state: dict[str, object]) -> None:
                    stream.seek(0)
                    stream.truncate()
                    stream.write(json.dumps(state, sort_keys=True).encode("ascii"))
                    stream.flush()
                    os.fsync(stream.fileno())

                publish(result)
                result = inspect_or_provision(
                    expected_runtime_sid=args.expected_runtime_sid,
                    execute=True,
                    publish=publish,
                )
                publish(result)
    except BaseException:
        result.update(
            status="STOPPED_AFTER_APPLY"
            if result.get("acl_apply_attempts")
            else "BLOCKED",
            result="FAIL",
        )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["result"] == "PASS" else 3
