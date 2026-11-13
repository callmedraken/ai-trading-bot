"""Guarded, tools/list-only observer for the agent-initiated partition schema.

This observer is separate from the consumed ``placed_agent`` observation. It
only records authenticated metadata for review; it is not connected to L43
production order-scope proof or any provider tool-dispatch path.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import sys
import threading
import webbrowser
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from trading_bot.robinhood_mcp.agent_initiated_partition_schema_qualifier import (
    AgentInitiatedPartitionSchemaClassification,
    AgentInitiatedPartitionSchemaMatch,
    AgentInitiatedPartitionSchemaMatcher,
    AgentInitiatedRuntimePartitionSchemaClassification,
    AgentInitiatedRuntimePartitionSchemaMatch,
    AgentInitiatedRuntimePartitionSchemaMatcher,
)
from trading_bot.robinhood_mcp.order_scope_schema_observer import (
    _admit_current_source,
    _AttemptCounters,
    _git_text,
    _is_reparse_point,
    _reject_reparse_ancestors,
    _SourceAdmission,
    _suppress_external_output,
    _write_evidence,
)

_OBSERVATION_SCHEMA = "arch147-agent-initiated-partition-schema-observation/v1"
_OBSERVATION_NAME = "ARCH147_L43_AGENT_INITIATED_PARTITION_SCHEMA_ONLY"
_RUNTIME_OBSERVATION_SCHEMA = (
    "arch147-agent-initiated-runtime-partition-eligibility-observation/v1"
)
_RUNTIME_OBSERVATION_NAME = (
    "ARCH147_L43_AGENT_INITIATED_RUNTIME_PARTITION_ELIGIBILITY_SCHEMA_ONLY"
)
_CANONICAL_WORKTREE = Path(r"F:\AI\worktrees\ai-trading-bot-live-prototype-current")
_EVIDENCE_ROOT = Path(r"F:\AI\temp")
_EVIDENCE_NAME = re.compile(r"arch147-agent-initiated-partition-[0-9a-f]{32}\Z")
_RUNTIME_EVIDENCE_NAME = re.compile(
    r"arch147-agent-initiated-runtime-proof-eligible-[0-9a-f]{32}\Z"
)
_REDIRECT_URI = "http://127.0.0.1:8765/robinhood/callback"


class AgentInitiatedPartitionObservationStatus(StrEnum):
    AUTHENTICATED_SCHEMA_MATCH_FOR_REVIEW = "AUTHENTICATED_SCHEMA_MATCH_FOR_REVIEW"
    AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW = (
        "AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW"
    )
    PROVIDER_SEMANTICS_UNPROVEN = "PROVIDER_SEMANTICS_UNPROVEN"
    RUNTIME_PROOF_ELIGIBILITY_UNPROVEN = "RUNTIME_PROOF_ELIGIBILITY_UNPROVEN"
    TARGET_TOOL_UNAVAILABLE = "TARGET_TOOL_UNAVAILABLE"
    SCHEMA_MALFORMED = "SCHEMA_MALFORMED"
    SOURCE_AUTHORITY_BLOCKED = "SOURCE_AUTHORITY_BLOCKED"
    OAUTH_SESSION_TOOLS_LIST_FAILURE = "OAUTH_SESSION_TOOLS_LIST_FAILURE"
    EVIDENCE_WRITE_FAILURE = "EVIDENCE_WRITE_FAILURE"


_ObservationStatus = AgentInitiatedPartitionObservationStatus
_REVIEW_MATCH = _ObservationStatus.AUTHENTICATED_SCHEMA_MATCH_FOR_REVIEW
_RUNTIME_REVIEW_MATCH = (
    _ObservationStatus.AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW
)
_SOURCE_BLOCKED = _ObservationStatus.SOURCE_AUTHORITY_BLOCKED
_TOOLS_LIST_FAILED = _ObservationStatus.OAUTH_SESSION_TOOLS_LIST_FAILURE


@dataclass(frozen=True, slots=True)
class AgentInitiatedPartitionObservationResult:
    status: AgentInitiatedPartitionObservationStatus
    reason: str
    evidence_file: Path | None
    evidence_sha256: str | None
    attempt_counters: dict[str, int]


class _ToolsListClient(Protocol):
    async def list_tools(self, *, cursor: str | None = None) -> object: ...


class _ObserverState(Protocol):
    _repo_root: Path
    _used: bool
    _guard: threading.Lock


_SchemaMatch = (
    AgentInitiatedPartitionSchemaMatch | AgentInitiatedRuntimePartitionSchemaMatch
)


class _MetadataOnlyTransport:
    """Restricted view that exposes tools/list and no arbitrary tool call."""

    __slots__ = ("_client", "_attempts", "failed")

    def __init__(self, client: _ToolsListClient, attempts: _AttemptCounters) -> None:
        self._client = client
        self._attempts = attempts
        self.failed = False

    async def list_tools(self, *, cursor: str | None) -> object:
        if cursor is not None and (
            type(cursor) is not str or not cursor or len(cursor) > 4096
        ):
            raise ValueError("invalid bounded metadata cursor")
        self._attempts.tools_list_attempts += 1
        try:
            result = await self._client.list_tools(cursor=cursor)
            self._attempts.tools_list_pages_received += 1
            return result
        except asyncio.CancelledError:
            self.failed = True
            raise RuntimeError("metadata listing failed") from None
        except Exception:
            self.failed = True
            raise RuntimeError("metadata listing failed") from None


class RobinhoodAgentInitiatedPartitionSchemaObserver:
    """Lazy, single-attempt observer with a source gate before OAuth/MCP."""

    __slots__ = ("_repo_root", "_used", "_guard")

    def __init__(self) -> None:
        self._repo_root = Path(__file__).resolve().parents[3]
        self._used = False
        self._guard = threading.Lock()

    async def observe(
        self, *, evidence_dir: Path
    ) -> AgentInitiatedPartitionObservationResult:
        return await _observe_with_profile(
            self,
            evidence_dir,
            reserve_evidence=_reserve_evidence_directory,
            run_session=_run_production_session,
            status_for_match=_match_status,
            evidence_material=_evidence_material,
        )


class RobinhoodAgentInitiatedRuntimePartitionSchemaObserver:
    """One-use, tools/list-only A2 observer with a separate evidence namespace."""

    __slots__ = ("_repo_root", "_used", "_guard")

    def __init__(self) -> None:
        self._repo_root = Path(__file__).resolve().parents[3]
        self._used = False
        self._guard = threading.Lock()

    async def observe(
        self, *, evidence_dir: Path
    ) -> AgentInitiatedPartitionObservationResult:
        return await _observe_with_profile(
            self,
            evidence_dir,
            reserve_evidence=_reserve_runtime_evidence_directory,
            run_session=_run_runtime_production_session,
            status_for_match=_runtime_match_status,
            evidence_material=_runtime_evidence_material,
        )


async def _observe_with_profile(
    observer: _ObserverState,
    evidence_dir: Path,
    *,
    reserve_evidence: Callable[[Path], Path],
    run_session: Callable[
        [_AttemptCounters, Path],
        Awaitable[tuple[_SchemaMatch | None, bool]],
    ],
    status_for_match: Callable[
        ..., tuple[AgentInitiatedPartitionObservationStatus, str]
    ],
    evidence_material: Callable[..., dict[str, object]],
) -> AgentInitiatedPartitionObservationResult:
    """Keep A1 and A2 custody, admission, one-use and cleanup paths identical."""
    attempts = _AttemptCounters()
    if not observer._guard.acquire(blocking=False):
        return AgentInitiatedPartitionObservationResult(
            AgentInitiatedPartitionObservationStatus.SOURCE_AUTHORITY_BLOCKED,
            "OBSERVER_ATTEMPT_ALREADY_USED",
            None,
            None,
            attempts.material(),
        )
    try:
        if observer._used:
            return AgentInitiatedPartitionObservationResult(
                AgentInitiatedPartitionObservationStatus.SOURCE_AUTHORITY_BLOCKED,
                "OBSERVER_ATTEMPT_ALREADY_USED",
                None,
                None,
                attempts.material(),
            )
        reserved = reserve_evidence(evidence_dir)
        observer._used = True
    except Exception:
        return AgentInitiatedPartitionObservationResult(
            AgentInitiatedPartitionObservationStatus.EVIDENCE_WRITE_FAILURE,
            "EVIDENCE_DESTINATION_UNAVAILABLE",
            None,
            None,
            attempts.material(),
        )
    finally:
        observer._guard.release()

    admission = _SourceAdmission()
    match: _SchemaMatch | None = None
    transport_failed = False
    status = _SOURCE_BLOCKED
    reason = "SOURCE_AUTHORITY_BLOCKED"
    try:
        admission = _admit_current_source(repo_root=observer._repo_root)
        if not admission.passed or not _module_origins_are_source_owned(
            repo_root=observer._repo_root
        ):
            status = _SOURCE_BLOCKED
            reason = "SOURCE_AUTHORITY_BLOCKED"
        else:
            source_failure = False
            with _suppress_external_output():
                try:
                    match, transport_failed = await run_session(
                        attempts, observer._repo_root
                    )
                except _SourceAuthorityFailure:
                    match = None
                    source_failure = True
                    status = _SOURCE_BLOCKED
                    reason = "SOURCE_AUTHORITY_BLOCKED"
                except (Exception, asyncio.CancelledError):
                    transport_failed = True
                    match = None
            if source_failure:
                pass
            elif match is not None and (
                match.source_head != admission.source_head
                or match.source_tree != admission.source_tree
            ):
                match = None
                status = _SOURCE_BLOCKED
                reason = "SOURCE_AUTHORITY_BLOCKED"
            elif transport_failed or match is None:
                match = None
                status = _TOOLS_LIST_FAILED
                reason = "OAUTH_SESSION_TOOLS_LIST_FAILURE"
            else:
                status, reason = status_for_match(match)
    except (Exception, asyncio.CancelledError):
        match = None
        status = _SOURCE_BLOCKED
        reason = "SOURCE_AUTHORITY_BLOCKED"

    evidence = evidence_material(
        admission=admission,
        match=match,
        status=status,
        reason=reason,
        attempts=attempts,
    )
    try:
        # The async session returned only after the client context shut down;
        # evidence is written after that cleanup and any source recheck.
        evidence_file, evidence_sha256 = _write_evidence(reserved, evidence)
    except Exception:
        return AgentInitiatedPartitionObservationResult(
            AgentInitiatedPartitionObservationStatus.EVIDENCE_WRITE_FAILURE,
            "EVIDENCE_WRITE_FAILURE",
            None,
            None,
            attempts.material(),
        )
    return AgentInitiatedPartitionObservationResult(
        status, reason, evidence_file, evidence_sha256, attempts.material()
    )


def _module_origins_are_source_owned(*, repo_root: Path) -> bool:
    try:
        expected_root = _CANONICAL_WORKTREE.resolve(strict=True)
        if (
            repo_root.resolve(strict=True) != expected_root
            or expected_root != _CANONICAL_WORKTREE
        ):
            return False
        from trading_bot.robinhood_mcp import order_scope_schema_observer

        matcher_module = sys.modules[AgentInitiatedPartitionSchemaMatcher.__module__]
        observer_module = sys.modules[__name__]
        return all(
            Path(module.__file__).resolve().parents[3] == expected_root
            for module in (matcher_module, observer_module, order_scope_schema_observer)
        )
    except (AttributeError, KeyError, OSError, RuntimeError):
        return False


async def _run_production_session(
    attempts: _AttemptCounters, repo_root: Path
) -> tuple[AgentInitiatedPartitionSchemaMatch | None, bool]:
    match, failed = await _run_schema_production_session(
        attempts, repo_root, runtime_proof_eligibility=False
    )
    if not isinstance(match, AgentInitiatedPartitionSchemaMatch) and match is not None:
        raise _SourceAuthorityFailure
    return match, failed


async def _run_runtime_production_session(
    attempts: _AttemptCounters, repo_root: Path
) -> tuple[AgentInitiatedRuntimePartitionSchemaMatch | None, bool]:
    match, failed = await _run_schema_production_session(
        attempts, repo_root, runtime_proof_eligibility=True
    )
    if (
        not isinstance(match, AgentInitiatedRuntimePartitionSchemaMatch)
        and match is not None
    ):
        raise _SourceAuthorityFailure
    return match, failed


async def _run_schema_production_session(
    attempts: _AttemptCounters,
    repo_root: Path,
    *,
    runtime_proof_eligibility: bool,
) -> tuple[
    AgentInitiatedPartitionSchemaMatch
    | AgentInitiatedRuntimePartitionSchemaMatch
    | None,
    bool,
]:
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    from trading_bot.robinhood_mcp import sdk_transport, windows_oauth

    if not all(
        _module_file_is_source_owned(module, repo_root)
        for module in (sdk_transport, windows_oauth)
    ):
        raise _SourceAuthorityFailure

    def launch_browser(url: str) -> object:
        if attempts.browser_launches >= 1:
            raise RuntimeError("browser flow limit reached")
        attempts.browser_launches += 1
        return webbrowser.open(url)

    oauth_factory = windows_oauth.create_windows_robinhood_oauth_factory(
        redirect_uri=_REDIRECT_URI, browser_opener=launch_browser
    )
    attempts.oauth_scope_entry_attempts += 1
    oauth_auth = oauth_factory()
    async with httpx2.AsyncClient(auth=oauth_auth) as http_client:
        stream = streamable_http_client(
            sdk_transport.ROBINHOOD_TRADING_MCP_URL, http_client=http_client
        )
        attempts.mcp_session_open_attempts += 1
        async with Client(stream) as client:
            transport = _MetadataOnlyTransport(client, attempts)
            matcher = (
                AgentInitiatedRuntimePartitionSchemaMatcher(repo_root=repo_root)
                if runtime_proof_eligibility
                else AgentInitiatedPartitionSchemaMatcher(repo_root=repo_root)
            )
            match = await matcher.match(tools_list=transport.list_tools)
    if not _local_source_still_clean(repo_root, match):
        raise _SourceAuthorityFailure
    return match, transport.failed


class _SourceAuthorityFailure(RuntimeError):
    pass


def _module_file_is_source_owned(module: object, repo_root: Path) -> bool:
    try:
        module_file = Path(module.__file__).resolve(strict=True)
        return module_file.parents[3] == repo_root.resolve(strict=True)
    except (AttributeError, IndexError, OSError, RuntimeError):
        return False


def _local_source_still_clean(
    repo_root: Path,
    match: AgentInitiatedPartitionSchemaMatch
    | AgentInitiatedRuntimePartitionSchemaMatch,
) -> bool:
    try:
        root = Path(_git_text(repo_root, "rev-parse", "--show-toplevel")).resolve(
            strict=True
        )
        branch = _git_text(repo_root, "branch", "--show-current")
        head = _git_text(repo_root, "rev-parse", "--verify", "HEAD").lower()
        tree = _git_text(repo_root, "rev-parse", "--verify", "HEAD^{tree}").lower()
        porcelain = _git_text(
            repo_root, "status", "--porcelain=v1", "--untracked-files=all"
        )
        expected_root = _CANONICAL_WORKTREE.resolve(strict=True)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
        return False
    return (
        root == expected_root
        and branch == "feature/robinhood-live-prototype-current"
        and head == match.source_head
        and tree == match.source_tree
        and not porcelain
    )


def _match_status(
    match: AgentInitiatedPartitionSchemaMatch,
) -> tuple[AgentInitiatedPartitionObservationStatus, str]:
    if (
        match.classification
        is AgentInitiatedPartitionSchemaClassification.UNAUTHENTICATED_SEMANTIC_MATCH
        and match.pagination_exhaustive
    ):
        return (
            AgentInitiatedPartitionObservationStatus.AUTHENTICATED_SCHEMA_MATCH_FOR_REVIEW,
            "AUTHENTICATED_SCHEMA_MATCH_FOR_REVIEW_ONLY",
        )
    if (
        match.classification
        is AgentInitiatedPartitionSchemaClassification.TOOL_UNAVAILABLE
    ):
        return (
            AgentInitiatedPartitionObservationStatus.TARGET_TOOL_UNAVAILABLE,
            "TARGET_TOOL_UNAVAILABLE",
        )
    if (
        match.classification
        is AgentInitiatedPartitionSchemaClassification.SCHEMA_MALFORMED
    ):
        return (
            AgentInitiatedPartitionObservationStatus.SCHEMA_MALFORMED,
            "SCHEMA_MALFORMED",
        )
    return (
        AgentInitiatedPartitionObservationStatus.PROVIDER_SEMANTICS_UNPROVEN,
        "PROVIDER_SEMANTICS_UNPROVEN",
    )


def _runtime_match_status(
    match: AgentInitiatedRuntimePartitionSchemaMatch,
) -> tuple[AgentInitiatedPartitionObservationStatus, str]:
    if (
        match.classification
        is AgentInitiatedRuntimePartitionSchemaClassification.RUNTIME_PROOF_ELIGIBLE
        and match.pagination_exhaustive
    ):
        return (
            _RUNTIME_REVIEW_MATCH,
            "AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW_ONLY",
        )
    if (
        match.classification
        is AgentInitiatedRuntimePartitionSchemaClassification.TOOL_UNAVAILABLE
    ):
        return (
            AgentInitiatedPartitionObservationStatus.TARGET_TOOL_UNAVAILABLE,
            "TARGET_TOOL_UNAVAILABLE",
        )
    if (
        match.classification
        is AgentInitiatedRuntimePartitionSchemaClassification.SCHEMA_MALFORMED
    ):
        return (
            AgentInitiatedPartitionObservationStatus.SCHEMA_MALFORMED,
            "SCHEMA_MALFORMED",
        )
    return (
        AgentInitiatedPartitionObservationStatus.RUNTIME_PROOF_ELIGIBILITY_UNPROVEN,
        "RUNTIME_PROOF_ELIGIBILITY_UNPROVEN",
    )


def _evidence_material(
    *,
    admission: _SourceAdmission,
    match: AgentInitiatedPartitionSchemaMatch | None,
    status: AgentInitiatedPartitionObservationStatus,
    reason: str,
    attempts: _AttemptCounters,
) -> dict[str, object]:
    return {
        "schema": _OBSERVATION_SCHEMA,
        "observation": _OBSERVATION_NAME,
        "source_head": _safe_object_id(admission.source_head),
        "source_tree": _safe_object_id(admission.source_tree),
        "remote_feature": {
            "head": _safe_object_id(admission.remote_feature_head),
            "tree": _safe_object_id(admission.remote_feature_tree),
        },
        "remote_develop": {
            "head": _safe_object_id(admission.remote_develop_head),
            "tree": _safe_object_id(admission.remote_develop_tree),
        },
        "source_authority": {
            "feature": admission.feature_authority,
            "prospective_develop": admission.prospective_develop_authority,
            "status": "PASS" if admission.passed else "BLOCKED",
        },
        "classification": (
            "AUTHENTICATED_METADATA_MATCH_FOR_REVIEW"
            if status is _REVIEW_MATCH
            else "NOT_CLASSIFIED"
            if match is None
            else match.classification.value
        ),
        "classifier_output_authenticated": False,
        "metadata_source_authenticated": (admission.passed and match is not None),
        "metadata_validation_boundary": (
            "SDK_PARSED_MODELS; VISIBLE_ALIAS_AND_TOOL_NAME_DUPLICATES_REJECTED; "
            "RAW_JSON_DUPLICATE_KEYS_UNOBSERVABLE"
        ),
        "contract_version": None if match is None else match.contract_version,
        "qualifier_evidence_sha256": None if match is None else match.evidence_sha256,
        "description_sha256": None if match is None else match.description_sha256,
        "input_schema_sha256": None if match is None else match.input_schema_sha256,
        "output_schema_sha256": None if match is None else match.output_schema_sha256,
        "agent_initiated_schema_sha256": (
            None if match is None else match.agent_initiated_schema_sha256
        ),
        "tools_list_pages": 0 if match is None else match.tools_list_pages,
        "exhaustive_pagination": False
        if match is None
        else match.pagination_exhaustive,
        "attempt_counters": attempts.material(),
        "status": status.value,
        "reason": reason,
        "production_order_scope_authority": "NOT_GRANTED",
    }


def _runtime_evidence_material(
    *,
    admission: _SourceAdmission,
    match: AgentInitiatedRuntimePartitionSchemaMatch | None,
    status: AgentInitiatedPartitionObservationStatus,
    reason: str,
    attempts: _AttemptCounters,
) -> dict[str, object]:
    eligible = match is not None and match.runtime_proof_eligible
    return {
        "schema": _RUNTIME_OBSERVATION_SCHEMA,
        "observation": _RUNTIME_OBSERVATION_NAME,
        "source_head": _safe_object_id(admission.source_head),
        "source_tree": _safe_object_id(admission.source_tree),
        "remote_feature": {
            "head": _safe_object_id(admission.remote_feature_head),
            "tree": _safe_object_id(admission.remote_feature_tree),
        },
        "remote_develop": {
            "head": _safe_object_id(admission.remote_develop_head),
            "tree": _safe_object_id(admission.remote_develop_tree),
        },
        "source_authority": {
            "feature": admission.feature_authority,
            "prospective_develop": admission.prospective_develop_authority,
            "status": "PASS" if admission.passed else "BLOCKED",
        },
        "classification": (
            "AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW"
            if status is _RUNTIME_REVIEW_MATCH
            else "NOT_CLASSIFIED"
            if match is None
            else match.classification.value
        ),
        "classifier_output_authenticated": False,
        "metadata_source_authenticated": (admission.passed and match is not None),
        "metadata_validation_boundary": (
            "SDK_PARSED_MODELS; VISIBLE_ALIAS_AND_TOOL_NAME_DUPLICATES_REJECTED; "
            "RAW_JSON_DUPLICATE_KEYS_UNOBSERVABLE"
        ),
        "contract_version": None if match is None else match.contract_version,
        "qualifier_evidence_sha256": None if match is None else match.evidence_sha256,
        "description_sha256": None if match is None else match.description_sha256,
        "input_schema_sha256": None if match is None else match.input_schema_sha256,
        "output_schema_sha256": None if match is None else match.output_schema_sha256,
        "agent_initiated_schema_sha256": (
            None if match is None else match.agent_initiated_schema_sha256
        ),
        "tools_list_pages": 0 if match is None else match.tools_list_pages,
        "exhaustive_pagination": False
        if match is None
        else match.pagination_exhaustive,
        "runtime_proof_eligibility": "ELIGIBLE" if eligible else "UNPROVEN",
        "partition_equality_proof": "NOT_PROVEN",
        "attempt_counters": attempts.material(),
        "status": status.value,
        "reason": reason,
        "production_order_scope_authority": "NOT_GRANTED",
    }


def _safe_object_id(value: str | None) -> str | None:
    return (
        value if type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) else None
    )


def _reserve_evidence_directory(evidence_dir: Path) -> Path:
    return _reserve_evidence_directory_matching(evidence_dir, _EVIDENCE_NAME)


def _reserve_runtime_evidence_directory(evidence_dir: Path) -> Path:
    return _reserve_evidence_directory_matching(evidence_dir, _RUNTIME_EVIDENCE_NAME)


def _reserve_evidence_directory_matching(
    evidence_dir: Path, evidence_name: re.Pattern[str]
) -> Path:
    if not isinstance(evidence_dir, Path):
        raise TypeError("evidence directory must be a Path")
    root = _EVIDENCE_ROOT.resolve(strict=True)
    if (
        root != _EVIDENCE_ROOT
        or root.drive.upper() != "F:"
        or evidence_dir.parent != _EVIDENCE_ROOT
        or evidence_name.fullmatch(evidence_dir.name) is None
    ):
        raise ValueError("evidence destination rejected")
    _reject_reparse_ancestors(root, stop=Path("F:/"))
    if evidence_dir.parent.resolve(strict=True) != root:
        raise ValueError("evidence destination rejected")
    if evidence_dir.exists() or evidence_dir.is_symlink():
        raise ValueError("evidence destination already exists")
    evidence_dir.mkdir()
    if (
        evidence_dir.is_symlink()
        or _is_reparse_point(evidence_dir)
        or evidence_dir.resolve(strict=True) != evidence_dir
    ):
        raise ValueError("evidence destination is a reparse point")
    _reject_reparse_ancestors(evidence_dir, stop=Path("F:/"))
    return evidence_dir


__all__ = [
    "AgentInitiatedPartitionObservationResult",
    "AgentInitiatedPartitionObservationStatus",
    "RobinhoodAgentInitiatedPartitionSchemaObserver",
    "RobinhoodAgentInitiatedRuntimePartitionSchemaObserver",
]
