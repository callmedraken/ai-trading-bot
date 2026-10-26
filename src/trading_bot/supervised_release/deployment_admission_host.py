"""Closed preflight entry; evidence writing belongs solely to the runner."""

from __future__ import annotations

import os
from pathlib import Path

from trading_bot.supervised_release.deployment_admission import (
    BRANCH,
    NO_AUTHORITY,
    SCHEMA,
    ZERO_EFFECTS,
    QuiescenceObservation,
    ReviewedInvocation,
    SecurityObservation,
    SourceObservation,
    admission,
)
from trading_bot.supervised_release.deployment_admission_native import (
    AdmissionNativeReader,
    observe_quiescence,
    observe_security,
)
from trading_bot.supervised_release.deployment_admission_source import (
    LocalGitReader,
    observe_source,
    require_checkout_path,
)
from trading_bot.supervised_release.deployment_candidate import (
    REPOSITORY,
    SourceIdentity,
)

PREFIX = "AI_TRADING_BOT_ARCH134_ADMISSION_"


class HostCollectors:
    def __init__(self, root: Path, reader: LocalGitReader) -> None:
        self.root, self.reader = root, reader
        self.session = None
        self.diagnostic_process_starts = 0

    def source(self, invocation: ReviewedInvocation) -> SourceObservation:
        return observe_source(self.reader, invocation)

    def security(self, parent) -> SecurityObservation:
        return observe_security(self.session, parent)

    def quiescence(self) -> QuiescenceObservation:
        self.diagnostic_process_starts += 1
        return observe_quiescence(self.root)


class HostReader:
    def __init__(self, collectors: HostCollectors) -> None:
        self.collectors = collectors

    def read_session(self, release_id: str) -> HostSession:
        return HostSession(self.collectors, release_id)


class HostSession:
    def __init__(self, collectors: HostCollectors, release_id: str) -> None:
        self.collectors = collectors
        self.release_id = release_id

    def __enter__(self):
        self.scope = AdmissionNativeReader(self.release_id).read_session()
        session = self.scope.__enter__()
        self.collectors.session = session
        return session

    def __exit__(self, *args):
        try:
            return self.scope.__exit__(*args)
        finally:
            self.collectors.session = None


def preflight() -> dict[str, object]:
    """Exact reviewed identity is supplied only after ChatGPT source acceptance."""
    try:
        root = Path(__file__).absolute().parents[3]
        require_checkout_path(root)
        reference = os.environ.get(PREFIX + "REFERENCE", BRANCH)
        elevation = os.environ.get(PREFIX + "ELEVATED")
        if elevation not in {"true", "false"}:
            raise ValueError("REVIEWED_TOKEN_POLICY_REQUIRED")
        invocation = ReviewedInvocation(
            SourceIdentity(
                REPOSITORY,
                reference,
                os.environ.get(PREFIX + "HEAD", ""),
                os.environ.get(PREFIX + "TREE", ""),
            ),
            os.environ.get(PREFIX + "PRINCIPAL_SID", ""),
            elevation == "true",
        )
        reader = LocalGitReader(root)
        collectors = HostCollectors(root, reader)
        result = admission(invocation, collectors, HostReader(collectors))
        result["diagnostic_process_starts"] = (
            reader.diagnostic_process_starts + collectors.diagnostic_process_starts
        )
        from trading_bot.supervised_release.deployment_admission import encode_evidence

        encode_evidence(result)
        return result
    except (Exception, KeyboardInterrupt):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "INVOCATION",
            "effects": dict.fromkeys(ZERO_EFFECTS, 0),
            "authority": dict.fromkeys(NO_AUTHORITY, False),
        }
