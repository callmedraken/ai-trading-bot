"""133-G provider-free pre-publication Architecture-133 host qualification.

This surface proves the exact Trading principal, corrected executable source and
shared protected Python identity while the entire Arch133 host namespace is
still absent. It never reads OAuth, constructs paper/state stores, touches Task
Scheduler, or creates publication material.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from trading_bot.review_paper import unattended_host_identity as identity
from trading_bot.runtime.personal_desktop_paper_account_token import (
    WindowsTradingTokenObserver,
    require_trading_token,
)

BOOTSTRAP_SCHEMA = "arch133-review-paper-host-bootstrap/v1"
BOOTSTRAP_LAUNCHER = (
    identity.SOURCE_ROOT / "scripts" / "run_arch133_unattended_host_preflight.py"
)


class UnattendedHostBootstrapError(RuntimeError):
    """Only fixed sanitized bootstrap diagnostics cross this boundary."""


@dataclass(frozen=True, slots=True)
class UnattendedHostBootstrapEvidence:
    source_branch: str
    source_head: str
    source_tree: str
    python_sha256: str
    python_version: str
    trading_sid: str
    host_root_absent: bool
    publication_objects: int = 0
    provider_calls: int = 0
    oauth_reads: int = 0
    scheduler_reads: int = 0
    scheduler_writes: int = 0


def _git(*arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(identity.SOURCE_ROOT), *arguments],
            input="",
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return completed.stdout.strip()
    except Exception:
        raise UnattendedHostBootstrapError(
            "host bootstrap source observation failed"
        ) from None


def _require_host_root_absent() -> None:
    """Prove absence through stat; permission/other errors are not absence."""
    try:
        os.stat(identity.HOST_ROOT, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError:
        raise UnattendedHostBootstrapError(
            "host bootstrap namespace absence unproven"
        ) from None
    raise UnattendedHostBootstrapError("host bootstrap namespace already exists")


def preflight_unattended_host_bootstrap() -> UnattendedHostBootstrapEvidence:
    """Q133-1 pre-publication read-only qualification; fail closed on any drift."""
    try:
        _require_host_root_absent()
        python_sha256 = hashlib.sha256(
            identity.PRODUCTION_PYTHON.read_bytes()
        ).hexdigest()
        if (
            sys.platform != "win32"
            or not sys.flags.isolated
            or not sys.dont_write_bytecode
            or sys.pycache_prefix != str(identity.NO_PYCACHE)
            or Path(sys.argv[0]).resolve(strict=True)
            != BOOTSTRAP_LAUNCHER.resolve(strict=True)
            or Path(sys.executable).resolve(strict=True)
            != identity.PRODUCTION_PYTHON.resolve(strict=True)
            or Path(__file__).resolve().parents[3]
            != identity.SOURCE_ROOT.resolve(strict=True)
            or ".".join(map(str, sys.version_info[:3]))
            != identity.PRODUCTION_PYTHON_VERSION
            or python_sha256 != identity.PRODUCTION_PYTHON_SHA256
        ):
            raise ValueError

        observation = WindowsTradingTokenObserver().observe()
        require_trading_token(identity.TRADING_SID, observation)

        branch = _git("branch", "--show-current")
        head = _git("rev-parse", "HEAD")
        tree = _git("rev-parse", "HEAD^{tree}")
        status = _git("status", "--porcelain=v1", "--untracked-files=all")
        if (
            branch != identity.SOURCE_BRANCH
            or re.fullmatch(r"[0-9a-f]{40}", head) is None
            or re.fullmatch(r"[0-9a-f]{40}", tree) is None
            or status
        ):
            raise ValueError

        # Race fence: publication/provisioning must remain absent throughout.
        _require_host_root_absent()
        return UnattendedHostBootstrapEvidence(
            branch,
            head,
            tree,
            python_sha256,
            identity.PRODUCTION_PYTHON_VERSION,
            identity.TRADING_SID,
            True,
        )
    except BaseException:
        raise UnattendedHostBootstrapError(
            "host bootstrap preflight failed closed"
        ) from None


def main(argv: list[str] | None = None) -> int:
    if sys.argv[1:] if argv is None else argv:
        print(
            '{"reason":"INVALID_ARGUMENTS","schema":"arch133-host-bootstrap/v1"}',
            file=sys.stderr,
        )
        return 2
    try:
        result = preflight_unattended_host_bootstrap()
        payload = asdict(result)
        payload["schema"] = BOOTSTRAP_SCHEMA
    except BaseException:
        print(
            '{"reason":"HOST_BOOTSTRAP_FAILED_CLOSED",'
            '"schema":"arch133-host-bootstrap/v1"}',
            file=sys.stderr,
        )
        return 3
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0
