"""133-J fixed retained-root diagnostic. Imports expose no mutation or provider APIs."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path

from trading_bot.arch133_acl import read_only, retained_reads

TARGET_PATH = retained_reads.TARGET_PATH
SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133j")
SOURCE_BRANCH = "feature/robinhood-unattended-review-paper-133j"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
SCHEMA = "arch133j-retained-production-root-diagnostic/v1"
ZERO_EFFECTS = {
    "provider_calls": 0,
    "oauth_reads": 0,
    "scheduler_reads": 0,
    "scheduler_writes": 0,
    "broker_effects": 0,
    "acl_mutations": 0,
    "file_mutations": 0,
}


class DiagnosticError(RuntimeError):
    """Fixed, sanitized failure only."""


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _source(expected_head: str, expected_tree: str) -> dict[str, str]:
    if any(
        type(value) is not str or re.fullmatch(r"[0-9a-f]{40}", value) is None
        for value in (expected_head, expected_tree)
    ):
        raise DiagnosticError("diagnostic source rejected")

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
            raise DiagnosticError("diagnostic source rejected")
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
        or git("rev-parse", "HEAD") != expected_head
        or git("rev-parse", "HEAD^{tree}") != expected_tree
        or git("rev-parse", "refs/remotes/origin/" + SOURCE_BRANCH) != expected_head
    ):
        raise DiagnosticError("diagnostic source rejected")
    return {"source_head": expected_head, "source_tree": expected_tree}


def diagnose_retained_root(expected_head: str, expected_tree: str) -> dict:
    """Operator-only read-only evidence; exact reviewed source IDs are required."""
    evidence = {
        "schema": SCHEMA,
        "target_path": TARGET_PATH,
        "source_head": None,
        "source_tree": None,
        "open_requested_access": read_only.MUTABLE_ROOT_ACCESS,
        "open_share_mode": read_only.ROOT_SHARE_MODE,
        "open_disposition": read_only.ROOT_DISPOSITION,
        "open_flags": read_only.ROOT_FLAGS,
        "open_success": False,
        "open_win32_error": None,
        "final_path": None,
        "identity": None,
        "filesystem": None,
        "reparse": None,
        "owner_sid": None,
        "dacl_protected": None,
        "ordered_aces": None,
        "policy_classification": "UNOBSERVED",
        "stable_reobservation": False,
        "namespace_exactness": False,
        "root_security_before_sha256": None,
        "root_security_after_sha256": None,
        "root_security_unchanged": False,
        "file_hashes_before": None,
        "file_hashes_after": None,
        "file_hashes_unchanged": False,
        "stage": "SOURCE_ADMISSION",
        "status": "FAILED_CLOSED",
        **ZERO_EFFECTS,
    }
    try:
        source = _source(expected_head, expected_tree)
        evidence.update(source)
        # The exact production open is attempted once. Failure cannot reach another
        # open, alternate root API, namespace read, file read, or fallback rights.
        evidence["stage"] = "EXACT_ROOT_OPEN"
        try:
            handle = read_only.open_directory(TARGET_PATH, mutable=True)
        except read_only.RootOpenError as exc:
            if type(exc.win32_error) is int and 0 <= exc.win32_error <= 0xFFFFFFFF:
                evidence["open_win32_error"] = exc.win32_error
            return evidence
        evidence["open_success"] = True
        with ExitStack() as held:
            held.callback(read_only.close_handle, handle)
            evidence["stage"] = "ROOT_SECURITY_BEFORE"
            before, security_before = read_only.inspect_directory_security(
                handle, TARGET_PATH
            )
            evidence.update(
                {
                    "final_path": "\\\\?\\" + TARGET_PATH,
                    "identity": before.identity,
                    "filesystem": before.filesystem,
                    "reparse": before.reparse,
                    "owner_sid": before.owner_sid,
                    "dacl_protected": before.protected,
                    "ordered_aces": before.aces,
                    "policy_classification": before.classification(),
                    "root_security_before_sha256": security_before,
                }
            )
            # Pin each ancestor against rename/delete for path-based four-file opens.
            evidence["stage"] = "ANCESTOR_PINS"
            parents = []
            for path in ("F:\\", r"F:\AITradingBot"):
                parent = read_only.open_directory(path)
                held.callback(read_only.close_handle, parent)
                parents.append(
                    (parent, path, read_only.inspect_directory(parent, path))
                )
            evidence["stage"] = "NAMESPACE_BEFORE"
            names_before = retained_reads.namespace(handle)
            evidence["stage"] = "FILE_HASHES_BEFORE"
            files = []
            hashes_before = {}
            for name in retained_reads.FINAL_NAMES:
                file_handle = retained_reads.open_retained_file(name)
                held.callback(read_only.close_handle, file_handle)
                identity, digest = retained_reads.file_snapshot(file_handle, name)
                if identity != (before.identity[0], dict(names_before)[name]):
                    raise DiagnosticError("diagnostic namespace identity rejected")
                files.append((file_handle, name, identity))
                hashes_before[name] = digest
            evidence["file_hashes_before"] = hashes_before
            evidence["stage"] = "NAMESPACE_AFTER"
            names_after = retained_reads.namespace(handle)
            evidence["namespace_exactness"] = names_before == names_after
            evidence["stage"] = "FILE_HASHES_AFTER"
            hashes_after = {}
            for file_handle, name, identity in files:
                current_identity, digest = retained_reads.file_snapshot(
                    file_handle, name
                )
                if current_identity != identity:
                    raise DiagnosticError("diagnostic file identity changed")
                hashes_after[name] = digest
            evidence["file_hashes_after"] = hashes_after
            evidence["file_hashes_unchanged"] = hashes_after == hashes_before
            evidence["stage"] = "ROOT_SECURITY_AFTER"
            after, security_after = read_only.inspect_directory_security(
                handle, TARGET_PATH
            )
            evidence["root_security_after_sha256"] = security_after
            evidence["root_security_unchanged"] = security_after == security_before
            evidence["stable_reobservation"] = before == after
            evidence["stage"] = "REOBSERVATION"
            if (
                before.classification() != "ADMIN_SYSTEM_ONLY"
                or before.filesystem != "NTFS"
                or before.reparse is not False
                or not all(
                    evidence[key]
                    for key in (
                        "stable_reobservation",
                        "namespace_exactness",
                        "root_security_unchanged",
                        "file_hashes_unchanged",
                    )
                )
                or any(
                    read_only.inspect_directory(h, p) != obs for h, p, obs in parents
                )
                or _source(expected_head, expected_tree) != source
            ):
                raise DiagnosticError("diagnostic reobservation rejected")
            evidence["stage"] = "HANDLE_CLOSE"
        # Close failures preserve observed fields, but can never produce PASS.
        if _source(expected_head, expected_tree) != source:
            raise DiagnosticError("diagnostic source changed")
        evidence["stage"] = "COMPLETE"
        evidence["status"] = "PASS"
    except BaseException:
        pass
    return evidence


def main(argv: list[str] | None = None) -> int:
    """Only the exact source-bound grammar is accepted; no path/env override."""
    try:
        args = sys.argv[1:] if argv is None else argv
        if (
            len(args) != 5
            or args[0:2] != ["diagnose", "--source-head"]
            or args[3] != "--source-tree"
            or any(re.fullmatch(r"[0-9a-f]{40}", args[i]) is None for i in (2, 4))
        ):
            raise DiagnosticError("diagnostic arguments rejected")
        result = diagnose_retained_root(args[2], args[4])
        print(canonical(result))
        return 0 if result["status"] == "PASS" else 3
    except BaseException:
        print(
            '{"reason":"RETAINED_DIAGNOSTIC_FAILED_CLOSED","schema":"' + SCHEMA + '"}',
            file=sys.stderr,
        )
        return 3
