"""Closed host entry for the Architecture 134 diagnostic successor."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from trading_bot.supervised_release import (
    deployment_admission_diagnostic_r3 as diagnostic,
)
from trading_bot.supervised_release.bundle import MAX_BUNDLE_BYTES, MAX_FILES
from trading_bot.supervised_release.deployment_admission import (
    NO_AUTHORITY,
    ZERO_EFFECTS,
)
from trading_bot.supervised_release.deployment_admission_host import (
    HostCollectors,
    HostReader,
)
from trading_bot.supervised_release.deployment_admission_source import (
    CLOSURE_PATH,
    DESIGN,
)
from trading_bot.supervised_release.deployment_candidate import (
    CANDIDATE,
    REPOSITORY,
    SourceIdentity,
)


class R3LocalGitReader:
    """Fixed read-only Git vocabulary. Diagnostic children are separately counted."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.diagnostic_process_starts = 0

    def query(self, *args: str, input_bytes: bytes | None = None) -> bytes:
        fixed = {
            ("remote", "get-url", "origin"),
            ("branch", "--show-current"),
            ("status", "--porcelain=v1", "--untracked-files=all"),
            ("diff", "--cached", "--name-only"),
            ("ls-files", "-v", "-z"),
            ("rev-parse", "--is-shallow-repository"),
            ("rev-parse", "--show-toplevel"),
            ("rev-parse", "--git-path", "info/grafts"),
            ("ls-tree", "-r", "-z", CANDIDATE.head),
            ("cat-file", "blob", DESIGN.head + ":" + CLOSURE_PATH),
            (
                "config",
                "--local",
                "--get-regexp",
                r"^(extensions\.partialclone|remote\..*\.promisor|core\.worktree)$",
            ),
        }
        allowed = args in fixed
        if len(args) == 2 and args[0] == "rev-parse":
            allowed = (
                allowed
                or args[1]
                in {
                    "HEAD",
                    "HEAD^{tree}",
                    "refs/remotes/origin/develop",
                    "refs/remotes/origin/" + diagnostic.BRANCH,
                }
                or re.fullmatch(r"[0-9a-f]{40}\^\{tree\}", args[1]) is not None
            )
        if len(args) == 3 and args[0] == "merge-base":
            allowed = all(
                re.fullmatch("[0-9a-f]{40}", item) is not None for item in args[1:]
            )
        if args == ("cat-file", "--batch"):
            allowed = (
                type(input_bytes) is bytes
                and len(input_bytes) <= MAX_FILES * 41
                and re.fullmatch(rb"(?:[0-9a-f]{40}\n)+", input_bytes) is not None
            )
        elif input_bytes is not None:
            allowed = False
        if not allowed:
            raise ValueError("GIT_VOCABULARY")
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith("GIT_")
        }
        env.update(
            GIT_OPTIONAL_LOCKS="0",
            GIT_NO_LAZY_FETCH="1",
            GIT_TERMINAL_PROMPT="0",
            GCM_INTERACTIVE="Never",
        )
        self.diagnostic_process_starts += 1
        result = subprocess.run(
            (
                "git",
                "--no-replace-objects",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                "-c",
                "core.hooksPath=",
                "-C",
                str(self.root),
                *args,
            ),
            input=input_bytes,
            capture_output=True,
            check=False,
            env=env,
            timeout=60,
        )
        absent_config = (
            args
            == (
                "config",
                "--local",
                "--get-regexp",
                r"^(extensions\.partialclone|remote\..*\.promisor|core\.worktree)$",
            )
            and result.returncode == 1
        )
        if (
            (result.returncode and not absent_config)
            or result.stderr
            or len(result.stdout) > MAX_BUNDLE_BYTES
        ):
            raise ValueError("LOCAL_GIT_OBSERVATION")
        return result.stdout


PREFIX = "AI_TRADING_BOT_ARCH134_ADMISSION_"


def preflight() -> dict[str, object]:
    """Run the same read-only host graph with sanitized diagnostic output."""
    try:
        root = Path(__file__).absolute().parents[3]
        reference = os.environ.get(PREFIX + "REFERENCE", diagnostic.BRANCH)
        elevation = os.environ.get(PREFIX + "ELEVATED")
        if elevation not in {"true", "false"}:
            raise ValueError("REVIEWED_TOKEN_POLICY_REQUIRED")
        invocation = diagnostic.ReviewedInvocation(
            SourceIdentity(
                REPOSITORY,
                reference,
                os.environ.get(PREFIX + "HEAD", ""),
                os.environ.get(PREFIX + "TREE", ""),
            ),
            os.environ.get(PREFIX + "PRINCIPAL_SID", ""),
            elevation == "true",
        )
        reader = R3LocalGitReader(root)
        collectors = HostCollectors(root, reader)
        result = diagnostic.admission(invocation, collectors, HostReader(collectors))
        result["diagnostic_process_starts"] = (
            reader.diagnostic_process_starts + collectors.diagnostic_process_starts
        )
        diagnostic.encode_evidence(result)
        return result
    except (Exception, KeyboardInterrupt):
        return {
            "schema": diagnostic.SCHEMA,
            "status": "BLOCKED",
            "reason": "HOST",
            "diagnostic_code": diagnostic.HOST_UNKNOWN,
            "effects": dict.fromkeys(ZERO_EFFECTS, 0),
            "authority": dict.fromkeys(NO_AUTHORITY, False),
        }
