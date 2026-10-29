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
from hashlib import sha256
from pathlib import Path

from trading_bot.experiments import historical_research_native as adapters
from trading_bot.experiments.historical_research_custody import (
    ACQUISITION_CHECKPOINT,
    CUSTODY_ROOT,
    CUSTODY_SDDL,
    OPEN_ROOT,
    HistoricalResearchCustodyError,
    HistoricalSessionAuthority,
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
    operator_sid: str | None
    operator_elevated: bool | None
    operator_administrator: bool | None
    credential_source: str = adapters.CREDENTIAL_SOURCE
    credential_persistence: str = adapters.CREDENTIAL_PERSISTENCE
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

    def operator_token(self) -> adapters.ResearchOperatorToken:
        return adapters.observe_research_operator_token()

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
            adapters.EphemeralHistoricalResearchCredentialSource.__name__
        ),
        "credential_source": adapters.CREDENTIAL_SOURCE,
        "credential_persistence": adapters.CREDENTIAL_PERSISTENCE,
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
    classification = "BLOCKED_RESEARCH_CREDENTIAL_POLICY"
    token = None
    try:
        if adapters.credential_binding_is_current():
            observed = observer.operator_token()
            if type(observed) is not adapters.ResearchOperatorToken:
                raise ValueError
            # Never report arbitrary exception/input strings as observed identity.
            observed.verify_sid()
            if (
                type(observed.elevated) is not bool
                or type(observed.administrator) is not bool
            ):
                raise ValueError
            token = observed
            classification = "BLOCKED_RESEARCH_OPERATOR_TOKEN"
            observed.verify()
            classification = "BLOCKED_HOST_FRESHNESS_OR_POLICY_UNPROVEN"
            state = observer.fresh_state()
            binding.update(
                fresh_state=state.classification,
                local_ntfs=state.local_ntfs,
                non_reparse=state.non_reparse,
            )
            state.verify()
            if observer.operator_token() != token:
                raise ValueError
            classification = "SIMULATED_B2_PREREQUISITES_PASS" if simulated else READY
    except Exception:
        if classification != "BLOCKED_RESEARCH_OPERATOR_TOKEN":
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
        token.sid if token is not None else None,
        token.elevated if token is not None else None,
        token.administrator if token is not None else None,
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
    if result.classification == READY:
        # Only this real observer path mints provenance. Parsed/replaced/fake
        # reports cannot mint acceptance, even with a matching caller hash.
        _REAL_PREFLIGHTS.append((result, preflight_report_bytes(result), root))
    return result


# Nonsecret, process-local provenance only. No file/credential persistence and
# no acceptance from a parsed report. Later operator wiring must retain the
# real report across independent review; no acquisition dispatcher exists yet.
_REAL_PREFLIGHTS: list[tuple[B2PreflightReport, bytes, Path]] = []


def preflight_report_bytes(report: B2PreflightReport) -> bytes:
    return json.dumps(asdict(report), sort_keys=True, separators=(",", ":")).encode()


class AcceptedB2Preflight:
    """Explicit independent acceptance of one exact real nonsecret report.

    Construct only after review, with its independently accepted SHA256. This
    binds prerequisites; it does not authorize acquisition or supply a SID.
    """

    def __init__(
        self, report: B2PreflightReport, *, accepted_report_sha256: str
    ) -> None:
        observed = next(
            (entry for entry in _REAL_PREFLIGHTS if entry[0] is report), None
        )
        if (
            type(report) is not B2PreflightReport
            or observed is None
            or observed[1] != preflight_report_bytes(report)
            or sha256(observed[1]).hexdigest() != accepted_report_sha256
        ):
            raise HistoricalResearchCustodyError("accepted real preflight required")
        self._report = report
        self._bytes = observed[1]
        self._root = observed[2]

    def recheck(self) -> None:
        report = self._report
        authority = published_historical_session_authority()
        binding = report.binding
        if (
            preflight_report_bytes(report) != self._bytes
            or report.classification != READY
            or report.acquisition_authorized is not False
            or any(
                (
                    report.credential_secret_reads,
                    report.provider_calls,
                    report.writes,
                    report.acl_mutations,
                )
            )
            or report.credential_source != adapters.CREDENTIAL_SOURCE
            or report.credential_persistence != adapters.CREDENTIAL_PERSISTENCE
            or report.authority_identity != authority.identity
            or report.authority_digest != authority.digest
            or report.session_count != len(authority.sessions)
            or binding["requests"] != frozen_request_descriptors()
            or binding["open_root"] != OPEN_ROOT
            or binding["custody_root"] != CUSTODY_ROOT
            or binding["attempt_claim"] != ATTEMPT_CLAIM_PATH
            or binding["custody_sddl"] != CUSTODY_SDDL
            or binding["open_sddl"] != OPEN_SDDL
            or binding["source_binding"] != "EXACT_REVIEWED_COMMAND"
        ):
            raise HistoricalResearchCustodyError("accepted preflight contract drift")
        require_accepted_historical_session_authority(authority)
        reconcile_historical_session_model(authority)
        _source(self._root, report.source_head, report.source_tree)
        token = adapters.observe_research_operator_token()
        token.verify()
        if token != adapters.ResearchOperatorToken(
            report.operator_sid, report.operator_elevated, report.operator_administrator
        ):
            raise HistoricalResearchCustodyError("accepted preflight operator drift")

    def verify_acquisition(
        self, head: str, tree: str, authority: HistoricalSessionAuthority
    ) -> None:
        if (head, tree) != (
            self._report.source_head,
            self._report.source_tree,
        ) or authority != published_historical_session_authority():
            raise HistoricalResearchCustodyError("acquisition preflight binding drift")
        self.recheck()


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
