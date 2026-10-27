"""Closed host entry for the Architecture 134 diagnostic successor."""

from __future__ import annotations

import os
from pathlib import Path

from trading_bot.supervised_release import (
    deployment_admission_diagnostic_r1 as diagnostic,
)
from trading_bot.supervised_release.deployment_admission import (
    NO_AUTHORITY,
    ZERO_EFFECTS,
)
from trading_bot.supervised_release.deployment_admission_host import (
    HostCollectors,
    HostReader,
)
from trading_bot.supervised_release.deployment_admission_source import (
    LocalGitReader,
)
from trading_bot.supervised_release.deployment_candidate import (
    REPOSITORY,
    SourceIdentity,
)

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
        reader = LocalGitReader(root, tracking_branch=diagnostic.BRANCH)
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
