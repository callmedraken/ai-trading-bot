"""Read-only B2 host preflight. This module has NO acquisition dispatcher.

The reviewed operator command supplies accepted exact source HEAD/TREE. Fake
observations can only return SIMULATED readiness, never real-host READY.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from trading_bot.experiments import historical_research_native as adapters
from trading_bot.experiments.historical_research_custody import (
    ACQUISITION_CHECKPOINT,
    CUSTODY_ROOT,
    CUSTODY_SDDL,
    OPEN_ROOT,
    frozen_request_descriptors,
    require_accepted_historical_session_authority,
)
from trading_bot.experiments.historical_research_native_custody import (
    ATTEMPT_CLAIM_PATH,
    OPEN_SDDL,
    CustodyFreshState,
    WindowsCustodyNative,
    WindowsHistoricalResearchCustody,
)
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
    reconcile_historical_session_model,
)
from trading_bot.runtime.windows_authority_security import resolve_current_token_sid

SOURCE_CHECKPOINT = "arch146-b-pre-b2-readiness-source"
SOURCE_BRANCH = "feature/research-arch146-b-pre-b2-readiness-current"
SOURCE_WORKTREE = r"F:\AI\worktrees\ai-trading-bot-146b-pre-b2-readiness-current"
READY = "READY_FOR_ONE_ARCH146_B2_ACQUISITION_ATTEMPT"


@dataclass(frozen=True, slots=True)
class B2PreflightReport:
    classification: str
    source_head: str
    source_tree: str
    authority_identity: str
    authority_digest: str
    session_count: int
    binding: dict
    checkpoint: str = ACQUISITION_CHECKPOINT
    source_checkpoint: str = SOURCE_CHECKPOINT
    credential_secret_reads: int = 0
    provider_calls: int = 0
    writes: int = 0
    acl_mutations: int = 0
    acquisition_authorized: bool = False


class WindowsB2ReadOnlyObserver:
    """The sole real observer, with no HTTP, credential-read or write capability."""

    def __init__(self) -> None:
        self._native = WindowsCustodyNative()

    def current_sid(self) -> str:
        return resolve_current_token_sid()

    def fresh_state(self) -> CustodyFreshState:
        return self._native.observe_fresh()

    def close(self) -> None:
        self._native.close()


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


def _source(root: Path, head: str, tree: str) -> None:
    if any(
        type(item) is not str or re.fullmatch(r"[0-9a-f]{40}", item) is None
        for item in (head, tree)
    ):
        raise ValueError
    if root.resolve() != Path(SOURCE_WORKTREE).resolve():
        raise ValueError
    if (
        Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root.resolve()
        or _git(root, "branch", "--show-current") != SOURCE_BRANCH
        or _git(root, "rev-parse", "HEAD") != head
        or _git(root, "rev-parse", "HEAD^{tree}") != tree
        or _git(root, "status", "--porcelain")
        or _git(root, "remote", "get-url", "origin")
        != "https://github.com/callmedraken/ai-trading-bot.git"
        or _git(root, "ls-remote", "origin", "refs/heads/" + SOURCE_BRANCH).split()
        != [head, "refs/heads/" + SOURCE_BRANCH]
    ):
        raise ValueError


def _evaluate(head: str, tree: str, observer, *, simulated: bool) -> B2PreflightReport:
    authority = published_historical_session_authority()
    require_accepted_historical_session_authority(authority)
    reconciliation = reconcile_historical_session_model(authority)
    binding = {
        "requests": frozen_request_descriptors(),
        "credential_adapter": (
            adapters.WindowsHistoricalResearchCredentialSource.__name__
        ),
        "credential_targets": adapters.CREDENTIAL_TARGETS,
        "credential_account_sid": adapters.CREDENTIAL_ACCOUNT_SID,
        "credential_binding_disposition": adapters.CREDENTIAL_BINDING_DISPOSITION,
        "transport_adapter": adapters.HttpsHistoricalResearchTransport.__name__,
        "custody_adapter": WindowsHistoricalResearchCustody.__name__,
        "open_root": OPEN_ROOT,
        "custody_root": CUSTODY_ROOT,
        "attempt_claim": ATTEMPT_CLAIM_PATH,
        "custody_sddl": CUSTODY_SDDL,
        "open_sddl": OPEN_SDDL,
        "model_reconciliation": reconciliation,
        "fresh_state": "NOT_OBSERVED",
        "local_ntfs": "NOT_OBSERVED",
        "non_reparse": "NOT_OBSERVED",
        "source_binding": "SIMULATED" if simulated else "EXACT_REVIEWED_COMMAND",
    }
    classification = adapters.CREDENTIAL_BINDING_DISPOSITION
    try:
        if adapters.CREDENTIAL_ACCOUNT_SID is not None:
            if observer.current_sid() != adapters.CREDENTIAL_ACCOUNT_SID:
                classification = "BLOCKED_CREDENTIAL_ACCOUNT_SID_MISMATCH"
            else:
                state = observer.fresh_state()
                binding.update(
                    fresh_state=state.classification,
                    local_ntfs=state.local_ntfs,
                    non_reparse=state.non_reparse,
                )
                state.verify()
                classification = (
                    "SIMULATED_B2_PREREQUISITES_PASS" if simulated else READY
                )
    except Exception:
        classification = "BLOCKED_HOST_FRESHNESS_OR_POLICY_UNPROVEN"
    finally:
        try:
            observer.close()
        except Exception:
            classification = "BLOCKED_HOST_OBSERVATION_CLOSE_AMBIGUITY"
    return B2PreflightReport(
        classification,
        head,
        tree,
        authority.identity,
        authority.digest,
        len(authority.sessions),
        binding,
    )


def evaluate_b2_preflight_for_test(observer) -> B2PreflightReport:
    """No supplied observation can grant real-host readiness."""
    return _evaluate("0" * 40, "0" * 40, observer, simulated=True)


def run_real_b2_readonly_preflight(
    root: Path,
    *,
    accepted_head: str,
    accepted_tree: str,
) -> B2PreflightReport:
    """Only a separately reviewed real invocation can reach the real observer."""
    _source(root, accepted_head, accepted_tree)
    result = _evaluate(
        accepted_head, accepted_tree, WindowsB2ReadOnlyObserver(), simulated=False
    )
    _source(root, accepted_head, accepted_tree)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accepted-head", required=True)
    parser.add_argument("--accepted-tree", required=True)
    args = parser.parse_args(argv)
    try:
        report = run_real_b2_readonly_preflight(
            Path.cwd(),
            accepted_head=args.accepted_head,
            accepted_tree=args.accepted_tree,
        )
    except Exception:
        print(
            '{"classification":"BLOCKED_EXACT_SOURCE_UNPROVEN","acquisition_authorized":false}'
        )
        return 1
    print(json.dumps(asdict(report), sort_keys=True))
    return 0 if report.classification == READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
