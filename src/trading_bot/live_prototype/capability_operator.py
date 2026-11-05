"""Source-admitted Architecture 147 L41 capability observation operator."""

from __future__ import annotations

import argparse
import json
import re
import stat
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from scripts.current_source_authority import (
    PublicationContext,
    evaluate_source_authority,
)

from trading_bot.live_prototype.capability_collector import (
    CapabilityCallCounts,
    CapabilityCollection,
    ReadOnlyCapabilityBoundary,
    collect_capabilities,
)
from trading_bot.live_prototype.capability_observer import (
    CapabilityReport,
    OverallStatus,
    classify_capabilities,
)
from trading_bot.live_prototype.capability_transport import (
    CapabilityTransportCounts,
    RobinhoodCapabilityTransport,
)

L41_FEATURE_BRANCH = "feature/robinhood-live-prototype-current"
L41_CHECKPOINT_OWNER = "arch147-live-prototype"
_CANONICAL_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-live-prototype-current")
_EXPECTED_ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
_EVIDENCE_ROOT = Path(r"F:\AI\temp")
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")


@dataclass(frozen=True, slots=True)
class SourceAdmission:
    """Exact local and live-remote identities accepted before future reads."""

    branch: str
    head: str
    tree: str
    origin_feature_head: str
    origin_feature_tree: str | None
    origin_develop_head: str
    origin_develop_tree: str | None
    feature_authority: str
    prospective_develop_authority: str

    def __post_init__(self) -> None:
        if self.branch != L41_FEATURE_BRANCH:
            raise ValueError("L41_SOURCE_BRANCH_INVALID")
        identities = (
            self.head,
            self.tree,
            self.origin_feature_head,
            self.origin_develop_head,
        )
        if any(
            type(value) is not str or _SHA1.fullmatch(value) is None
            for value in identities
        ):
            raise ValueError("L41_SOURCE_IDENTITY_INVALID")
        for value in (self.origin_feature_tree, self.origin_develop_tree):
            if value is not None and (
                type(value) is not str or _SHA1.fullmatch(value) is None
            ):
                raise ValueError("L41_SOURCE_TREE_INVALID")
        if self.feature_authority not in {"PASS", "NOT_RUN"} or (
            self.prospective_develop_authority not in {"PASS", "NOT_RUN"}
        ):
            raise ValueError("L41_SOURCE_AUTHORITY_INVALID")


@dataclass(frozen=True, slots=True)
class CapabilityEvidence:
    """Typed evidence envelope; native credential reads remain unobserved."""

    status: OverallStatus
    reason: str
    source: SourceAdmission | None
    report: CapabilityReport
    transport_counts: CapabilityTransportCounts | None
    collector_counts: CapabilityCallCounts | None
    collector_invocations: int
    native_credential_read_count: int | None = None


@dataclass(frozen=True, slots=True)
class CapabilityOperatorResult:
    """Sanitized result returned by the source-owned command boundary."""

    status: OverallStatus
    reason: str
    evidence_path: Path | None
    evidence: CapabilityEvidence


class _SourceAdmissionBlocked(RuntimeError):
    """Fixed source-admission failure without Git/provider diagnostic text."""

    def __init__(self, source: SourceAdmission | None = None) -> None:
        self.source = source
        super().__init__("L41_SOURCE_ADMISSION_BLOCKED")


class _OwnedTransport(ReadOnlyCapabilityBoundary, Protocol):
    call_counts: CapabilityTransportCounts

    def __enter__(self) -> ReadOnlyCapabilityBoundary: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool: ...


def admit_l41_source(repo_root: Path | None = None) -> SourceAdmission:
    """Require exact clean local source, matching live refs and both authorities."""

    try:
        root = (
            Path(__file__).resolve().parents[3]
            if repo_root is None
            else Path(repo_root).resolve(strict=True)
        )
        expected_root = _CANONICAL_ROOT.resolve(strict=True)
    except (OSError, RuntimeError):
        raise _SourceAdmissionBlocked() from None
    if str(root).casefold() != str(expected_root).casefold():
        raise _SourceAdmissionBlocked() from None

    try:
        branch = _git_output(root, "branch", "--show-current")
        if branch != L41_FEATURE_BRANCH:
            raise _SourceAdmissionBlocked()
        if _git_output(root, "status", "--porcelain=v1", "--untracked-files=all"):
            raise _SourceAdmissionBlocked()
        head = _git_output(root, "rev-parse", "--verify", "HEAD")
        tree = _git_output(root, "rev-parse", "HEAD^{tree}")
        if _SHA1.fullmatch(head) is None or _SHA1.fullmatch(tree) is None:
            raise _SourceAdmissionBlocked()
        if _git_output(root, "remote", "get-url", "origin") != _EXPECTED_ORIGIN:
            raise _SourceAdmissionBlocked()
        feature_head = _remote_head(root, L41_FEATURE_BRANCH)
        develop_head = _remote_head(root, "develop")
    except _SourceAdmissionBlocked:
        raise
    except Exception:
        raise _SourceAdmissionBlocked() from None

    feature_tree = tree if feature_head == head else None
    develop_tree = tree if develop_head == head else None
    identity = SourceAdmission(
        branch=branch,
        head=head,
        tree=tree,
        origin_feature_head=feature_head,
        origin_feature_tree=feature_tree,
        origin_develop_head=develop_head,
        origin_develop_tree=develop_tree,
        feature_authority="NOT_RUN",
        prospective_develop_authority="NOT_RUN",
    )
    if feature_head != head or develop_head != head:
        raise _SourceAdmissionBlocked(identity) from None
    try:
        feature = evaluate_source_authority(
            root, publication_context=PublicationContext.FEATURE
        )
        prospective = evaluate_source_authority(
            root, publication_context=PublicationContext.PROSPECTIVE_DEVELOP
        )
    except Exception:
        raise _SourceAdmissionBlocked(identity) from None

    authority_ok = all(
        result.passed
        and result.head == head
        and result.tree == tree
        and L41_CHECKPOINT_OWNER in result.checkpoints
        for result in (feature, prospective)
    )
    if not authority_ok:
        raise _SourceAdmissionBlocked(identity) from None
    return SourceAdmission(
        branch=identity.branch,
        head=identity.head,
        tree=identity.tree,
        origin_feature_head=identity.origin_feature_head,
        origin_feature_tree=identity.origin_feature_tree,
        origin_develop_head=identity.origin_develop_head,
        origin_develop_tree=identity.origin_develop_tree,
        feature_authority="PASS",
        prospective_develop_authority="PASS",
    )


def _git_output(repo_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError("L41_SOURCE_GIT_UNAVAILABLE")
    return completed.stdout.strip()


def _remote_head(repo_root: Path, branch: str) -> str:
    reference = f"refs/heads/{branch}"
    output = _git_output(
        repo_root, "ls-remote", "--exit-code", "--heads", "origin", reference
    )
    rows = output.splitlines()
    if len(rows) != 1:
        raise _SourceAdmissionBlocked()
    pieces = rows[0].split("\t")
    if len(pieces) != 2 or pieces[1] != reference or _SHA1.fullmatch(pieces[0]) is None:
        raise _SourceAdmissionBlocked()
    return pieces[0]


def run_l41_read_only_observation(*, evidence_dir: Path) -> CapabilityOperatorResult:
    """Run after source admission, writing one create-only sanitized evidence file."""

    return _run_with_dependencies(
        evidence_dir,
        source_admitter=admit_l41_source,
        oauth_factory_builder=_create_windows_oauth_factory,
        transport_builder=RobinhoodCapabilityTransport,
        collector=collect_capabilities,
    )


def _run_with_dependencies(
    evidence_dir: Path,
    *,
    source_admitter: Callable[[Path], SourceAdmission],
    oauth_factory_builder: Callable[[], object],
    transport_builder: Callable[[object], _OwnedTransport],
    collector: Callable[[ReadOnlyCapabilityBoundary], CapabilityCollection],
) -> CapabilityOperatorResult:
    report = classify_capabilities(None)
    empty_transport_counts = CapabilityTransportCounts(0, 0, 0, 0)
    empty_collector_counts = CapabilityCallCounts(0, 0)
    try:
        output_dir = _fresh_evidence_dir(evidence_dir)
    except Exception:
        return _result_without_file(
            OverallStatus.BLOCKED,
            "L41_EVIDENCE_PATH_INVALID",
            None,
            report,
            empty_transport_counts,
            empty_collector_counts,
            0,
        )

    root = Path(__file__).resolve().parents[3]
    source: SourceAdmission | None = None
    try:
        source = source_admitter(root)
        if type(source) is not SourceAdmission or not _source_is_accepted(source):
            source = None
            raise _SourceAdmissionBlocked()
    except Exception as error:
        if type(error) is _SourceAdmissionBlocked and type(error.source) is (
            SourceAdmission
        ):
            source = error.source
        return _write_result(
            output_dir,
            OverallStatus.BLOCKED,
            "L41_SOURCE_ADMISSION_BLOCKED",
            source,
            report,
            empty_transport_counts,
            empty_collector_counts,
            0,
        )

    try:
        oauth_factory = oauth_factory_builder()
    except Exception:
        return _write_result(
            output_dir,
            OverallStatus.BLOCKED,
            "L41_OAUTH_FACTORY_FAILED",
            source,
            report,
            empty_transport_counts,
            empty_collector_counts,
            0,
        )

    try:
        transport = transport_builder(oauth_factory)
    except Exception:
        return _write_result(
            output_dir,
            OverallStatus.BLOCKED,
            "L41_TRANSPORT_CREATE_FAILED",
            source,
            report,
            empty_transport_counts,
            empty_collector_counts,
            0,
        )

    collection: CapabilityCollection | None = None
    collection_invocations = 0
    reason = "L41_OBSERVATION_FAILED"
    status = OverallStatus.BLOCKED
    try:
        with transport as boundary:
            collection_invocations += 1
            candidate = collector(boundary)
            if type(candidate) is not CapabilityCollection:
                raise TypeError("L41_COLLECTION_INVALID")
            collection = candidate
        if collection.report.status in OverallStatus:
            status = collection.report.status
            reason = collection.reason
    except Exception:
        status = OverallStatus.BLOCKED
        reason = "L41_OBSERVATION_FAILED"

    transport_counts = _transport_counts(transport)
    collector_counts = (
        None
        if collection_invocations and collection is None
        else empty_collector_counts
        if collection is None
        else _valid_collector_counts(collection.call_counts)
    )
    report = report if collection is None else collection.report
    if collection_invocations and collection is None:
        reason = "L41_OBSERVATION_FAILED"
        status = OverallStatus.BLOCKED
    if transport_counts is None:
        reason = "L41_ATTEMPT_COUNTS_UNAVAILABLE"
        status = OverallStatus.BLOCKED
    elif collection_invocations and collector_counts is None:
        reason = "L41_COLLECTOR_COUNTS_UNAVAILABLE"
        status = OverallStatus.BLOCKED
    elif (
        collector_counts is not None
        and collection is not None
        and (
            transport_counts.get_accounts_attempts != collector_counts.get_accounts
            or transport_counts.get_equity_tradability_attempts
            != collector_counts.get_equity_tradability
        )
    ):
        reason = "L41_ATTEMPT_COUNT_MISMATCH"
        status = OverallStatus.BLOCKED
    if status is OverallStatus.READY_FOR_L42 and not _ready_effects_proven(
        transport_counts,
        collector_counts,
        collection_invocations,
    ):
        reason = "L41_READY_EFFECT_ACCOUNTING_BLOCKED"
        status = OverallStatus.BLOCKED
    return _write_result(
        output_dir,
        status,
        reason,
        source,
        report,
        transport_counts,
        collector_counts,
        collection_invocations,
    )


def _create_windows_oauth_factory() -> Callable[[], object]:
    from trading_bot.robinhood_mcp.windows_oauth import (
        create_windows_robinhood_oauth_factory,
    )

    return create_windows_robinhood_oauth_factory(
        redirect_uri="http://127.0.0.1:8765/robinhood/callback",
        browser_opener=_forbid_interactive_oauth,
    )


def _forbid_interactive_oauth(_url: str) -> None:
    raise RuntimeError("L41_INTERACTIVE_OAUTH_FORBIDDEN")


def _source_is_accepted(source: SourceAdmission) -> bool:
    return (
        source.branch == L41_FEATURE_BRANCH
        and _SHA1.fullmatch(source.head) is not None
        and _SHA1.fullmatch(source.tree) is not None
        and source.origin_feature_head == source.head
        and source.origin_feature_tree == source.tree
        and source.origin_develop_head == source.head
        and source.origin_develop_tree == source.tree
        and source.feature_authority == "PASS"
        and source.prospective_develop_authority == "PASS"
    )


def _transport_counts(transport: object) -> CapabilityTransportCounts | None:
    try:
        counts = transport.call_counts
        if type(counts) is not CapabilityTransportCounts or not _transport_counts_valid(
            counts
        ):
            return None
        return counts
    except Exception:
        return None


def _transport_counts_valid(counts: CapabilityTransportCounts) -> bool:
    try:
        allowed = (
            counts.oauth_scope_entry_attempts,
            counts.mcp_session_open_attempts,
            counts.get_accounts_attempts,
            counts.get_equity_tradability_attempts,
        )
        forbidden = (
            counts.other_tool_attempts,
            counts.review_equity_order_attempts,
            counts.place_equity_order_attempts,
            counts.cancel_equity_order_attempts,
        )
        return (
            all(type(value) is int and value in {0, 1} for value in allowed)
            and all(type(value) is int and value == 0 for value in forbidden)
            and counts.native_credential_read_count is None
            and counts.credential_store_accounting
            == "OAUTH_SCOPE_ONCE_NATIVE_READS_SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED"
        )
    except Exception:
        return False


def _valid_collector_counts(counts: object) -> CapabilityCallCounts | None:
    if type(counts) is not CapabilityCallCounts:
        return None
    try:
        allowed = (counts.get_accounts, counts.get_equity_tradability)
        forbidden = (
            counts.other_tool_calls,
            counts.review_equity_order,
            counts.place_equity_order,
            counts.cancel_equity_order,
        )
        if not all(type(value) is int and value in {0, 1} for value in allowed):
            return None
        if not all(type(value) is int and value == 0 for value in forbidden):
            return None
        return counts
    except Exception:
        return None


def _ready_effects_proven(
    transport_counts: CapabilityTransportCounts | None,
    collector_counts: CapabilityCallCounts | None,
    collector_invocations: int,
) -> bool:
    return (
        type(transport_counts) is CapabilityTransportCounts
        and _transport_counts_valid(transport_counts)
        and transport_counts.oauth_scope_entry_attempts == 1
        and transport_counts.mcp_session_open_attempts == 1
        and transport_counts.get_accounts_attempts == 1
        and transport_counts.get_equity_tradability_attempts == 1
        and type(collector_counts) is CapabilityCallCounts
        and _valid_collector_counts(collector_counts) is collector_counts
        and collector_counts.get_accounts == 1
        and collector_counts.get_equity_tradability == 1
        and type(collector_invocations) is int
        and collector_invocations == 1
    )


def _fresh_evidence_dir(candidate: Path) -> Path:
    path = Path(candidate)
    parent_root = _EVIDENCE_ROOT.resolve(strict=True)
    if (
        not path.is_absolute()
        or path.drive.casefold() != "f:"
        or path.exists()
        or path.is_symlink()
    ):
        raise ValueError("L41_EVIDENCE_PATH_INVALID")
    parent = path.parent.resolve(strict=True)
    if path.parent != parent or not parent.is_relative_to(parent_root):
        raise ValueError("L41_EVIDENCE_PATH_INVALID")
    current = parent
    while True:
        if current.resolve(strict=True) != current or _has_reparse_point(current):
            raise ValueError("L41_EVIDENCE_PATH_INVALID")
        if current == parent_root:
            break
        if current.parent == current or not current.is_relative_to(parent_root):
            raise ValueError("L41_EVIDENCE_PATH_INVALID")
        current = current.parent
    path.mkdir()
    return path


def _has_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(path.stat(), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _result_without_file(
    status: OverallStatus,
    reason: str,
    source: SourceAdmission | None,
    report: CapabilityReport,
    transport_counts: CapabilityTransportCounts | None,
    collector_counts: CapabilityCallCounts | None,
    collector_invocations: int,
) -> CapabilityOperatorResult:
    return CapabilityOperatorResult(
        status,
        reason,
        None,
        CapabilityEvidence(
            status,
            reason,
            source,
            report,
            transport_counts,
            collector_counts,
            collector_invocations,
        ),
    )


def _write_result(
    output_dir: Path,
    status: OverallStatus,
    reason: str,
    source: SourceAdmission | None,
    report: CapabilityReport,
    transport_counts: CapabilityTransportCounts | None,
    collector_counts: CapabilityCallCounts | None,
    collector_invocations: int,
) -> CapabilityOperatorResult:
    evidence = CapabilityEvidence(
        status,
        reason,
        source,
        report,
        transport_counts,
        collector_counts,
        collector_invocations,
    )
    path = output_dir / "evidence.json"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(
                json.dumps(
                    _evidence_payload(evidence),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
                + "\n"
            )
    except Exception:
        return _result_without_file(
            OverallStatus.BLOCKED,
            "L41_EVIDENCE_WRITE_FAILED",
            source,
            report,
            transport_counts,
            collector_counts,
            collector_invocations,
        )
    return CapabilityOperatorResult(status, reason, path, evidence)


def _evidence_payload(evidence: CapabilityEvidence) -> dict[str, object]:
    source = evidence.source
    counts = evidence.transport_counts
    collector_counts = evidence.collector_counts
    return {
        "schema": "arch147-l41-capability-observation/v1",
        "status": evidence.status.value,
        "reason": evidence.reason,
        "source": None
        if source is None
        else {
            "branch": source.branch,
            "head": source.head,
            "tree": source.tree,
            "origin_feature_head": source.origin_feature_head,
            "origin_feature_tree": source.origin_feature_tree,
            "origin_develop_head": source.origin_develop_head,
            "origin_develop_tree": source.origin_develop_tree,
            "feature_authority": source.feature_authority,
            "prospective_develop_authority": source.prospective_develop_authority,
        },
        "capability_report": {
            "status": evidence.report.status.value,
            "account_fingerprint": evidence.report.account_fingerprint,
            "account_type": evidence.report.account_type,
            "facts": [
                {
                    "fact_id": fact.fact_id.value,
                    "classification": fact.classification.value,
                    "rationale_code": fact.rationale_code,
                    "evidence_sha256": fact.evidence_sha256,
                    "provenance": _provenance_payload(fact.provenance),
                }
                for fact in evidence.report.facts
            ],
        },
        "attempts": {
            "oauth_scope_entry_attempts": None
            if counts is None
            else counts.oauth_scope_entry_attempts,
            "native_credential_read_count": evidence.native_credential_read_count,
            "credential_store_accounting": (
                "NATIVE_READS_SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED"
            ),
            "mcp_session_open_attempts": None
            if counts is None
            else counts.mcp_session_open_attempts,
            "get_accounts_attempts": None
            if counts is None
            else counts.get_accounts_attempts,
            "get_equity_tradability_attempts": None
            if counts is None
            else counts.get_equity_tradability_attempts,
            "collector_invocations": evidence.collector_invocations,
            "collector_get_accounts_attempts": None
            if collector_counts is None
            else collector_counts.get_accounts,
            "collector_get_equity_tradability_attempts": None
            if collector_counts is None
            else collector_counts.get_equity_tradability,
            "other_tool_attempts": None
            if counts is None
            else counts.other_tool_attempts,
            "review_equity_order_attempts": None
            if counts is None
            else counts.review_equity_order_attempts,
            "place_equity_order_attempts": None
            if counts is None
            else counts.place_equity_order_attempts,
            "cancel_equity_order_attempts": None
            if counts is None
            else counts.cancel_equity_order_attempts,
        },
    }


def _provenance_payload(provenance: object) -> dict[str, object] | None:
    if provenance is None:
        return None
    return {
        "source_identifier": provenance.source_identifier,
        "canonical_url_or_document_id": provenance.canonical_url_or_document_id,
        "retrieved_on": None
        if provenance.retrieved_on is None
        else provenance.retrieved_on.isoformat(),
        "accepted_on": None
        if provenance.accepted_on is None
        else provenance.accepted_on.isoformat(),
        "content_sha256": provenance.content_sha256,
        "semantic_claim_ids": list(provenance.semantic_claim_ids),
    }


def build_parser() -> argparse.ArgumentParser:
    """Build an inert CLI parser; parsing help performs no admission or I/O."""

    parser = argparse.ArgumentParser(
        description="Run the source-admitted Architecture 147 L41 observer."
    )
    parser.add_argument(
        "--evidence-dir",
        required=True,
        type=Path,
        metavar="PATH",
        help="fresh absolute external F:\\AI\\temp evidence directory",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the source-admitted observer after parsing its bounded output path."""

    args = build_parser().parse_args(argv)
    result = run_l41_read_only_observation(evidence_dir=args.evidence_dir)
    print(
        json.dumps(
            {
                "status": result.status.value,
                "reason": result.reason,
                "evidence_path": None
                if result.evidence_path is None
                else str(result.evidence_path),
            },
            sort_keys=True,
        )
    )
    return 0 if result.status is OverallStatus.READY_FOR_L42 else 1


if __name__ == "__main__":
    raise SystemExit(main())
