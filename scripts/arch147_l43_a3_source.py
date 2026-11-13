"""Source-owned read-only A3 dispatch for the Architecture 147 L43 observer."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import stat
from pathlib import Path
from uuid import uuid4

_A2_EVIDENCE_PREFIX = "arch147-agent-initiated-runtime-proof-eligible-"
_SAFE_REASON = re.compile(r"[A-Z0-9_]{1,80}\Z")
_GIT_OBJECT_ID = re.compile(r"[0-9a-f]{40}\Z")
_REVIEW_REASON = "AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW_ONLY"


def _admission_identity(admission: object, a2: object):
    """Read only identity fields from the A2-owned typed source admission."""
    if not isinstance(admission, a2._SourceAdmission):
        return None, None
    head = admission.source_head
    tree = admission.source_tree
    if (
        type(head) is not str
        or _GIT_OBJECT_ID.fullmatch(head) is None
        or type(tree) is not str
        or _GIT_OBJECT_ID.fullmatch(tree) is None
    ):
        return None, None
    return head, tree


def _admission_matches(
    admission: object,
    a2: object,
    repo_root: Path,
    source_head: str,
    source_tree: str,
) -> bool:
    if not isinstance(admission, a2._SourceAdmission) or not admission.passed:
        return False
    head, tree = _admission_identity(admission, a2)
    if (head, tree) != (source_head, source_tree):
        return False
    try:
        return Path(admission.root).resolve(strict=True) == repo_root
    except (OSError, RuntimeError, TypeError, ValueError):
        return False


def _post_dispatch_source_recheck(
    a2: object, repo_root: Path, source_head: str, source_tree: str
) -> bool:
    try:
        admission = a2._admit_current_source(repo_root=repo_root)
    except Exception:
        return False
    return _admission_matches(admission, a2, repo_root, source_head, source_tree)


def _apply_source_recheck(
    result: dict[str, object], source_recheck_passed: bool
) -> dict[str, object]:
    result["source_recheck_status"] = "PASS" if source_recheck_passed else "BLOCKED"
    if not source_recheck_passed:
        result["status"] = "BLOCKED"
        result["reason"] = "OBSERVER_SOURCE_RECHECK_BLOCKED"
        result["disposition"] = "BLOCKED"
    return result


def _blocked_before_dispatch(
    reason: str, source_head: str | None, source_tree: str | None
) -> dict[str, object]:
    return {
        "status": "BLOCKED",
        "reason": reason,
        "disposition": "BLOCKED",
        "observer_dispatched": False,
        "observer_invocation_attempts": 0,
        "observer_status": "NOT_DISPATCHED",
        "observer_reason": reason,
        "observer_evidence_path": None,
        "observer_evidence_sha256": None,
        "observer_evidence_written": False,
        "observer_evidence_valid": None,
        "attempt_counters": {
            "oauth_scope_entry_attempts": 0,
            "mcp_session_open_attempts": 0,
            "tools_list_attempts": 0,
        },
        "attempt_counters_status": "KNOWN_NOT_DISPATCHED",
        "source_head": source_head,
        "source_tree": source_tree,
        "source_identity_status": (
            "AVAILABLE"
            if source_head is not None and source_tree is not None
            else "UNAVAILABLE"
        ),
        "partition_equality_proof": "NOT_PROVEN",
        "production_order_scope_authority": "NOT_GRANTED",
    }


def _evidence_path_is_observer_owned(expected_file: Path, a2: object) -> bool:
    """Reuse A2's fixed F: ancestry and reparse checks before reading evidence."""
    try:
        root = a2._EVIDENCE_ROOT.resolve(strict=True)
        if (
            root != a2._EVIDENCE_ROOT
            or expected_file.parent.parent != root
            or a2._RUNTIME_EVIDENCE_NAME.fullmatch(expected_file.parent.name) is None
        ):
            return False
        a2._reject_reparse_ancestors(root, stop=Path("F:/"))
        directory = expected_file.parent
        if (
            directory.is_symlink()
            or a2._is_reparse_point(directory)
            or directory.resolve(strict=True) != directory
        ):
            return False
        a2._reject_reparse_ancestors(directory, stop=Path("F:/"))
        fact = expected_file.lstat()
        return (
            stat.S_ISREG(fact.st_mode)
            and not stat.S_ISLNK(fact.st_mode)
            and not getattr(fact, "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        )
    except (OSError, RuntimeError, TypeError, ValueError):
        return False


def _evidence_summary(
    expected_file: Path,
    result: object,
    source_head: str,
    source_tree: str,
    a2: object,
) -> tuple[str | None, bool, bool]:
    """Bind the typed result to its fixed evidence path, digest, and source."""
    from trading_bot.robinhood_mcp.agent_initiated_partition_schema_observer import (
        AgentInitiatedPartitionObservationResult,
    )

    if (
        not isinstance(result, AgentInitiatedPartitionObservationResult)
        or result.evidence_file != expected_file
        or not _evidence_path_is_observer_owned(expected_file, a2)
    ):
        return None, False, False
    try:
        raw = expected_file.read_bytes()
    except OSError:
        return None, False, False
    digest = hashlib.sha256(raw).hexdigest()
    if result.evidence_sha256 != digest:
        return digest, True, False
    try:
        evidence = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return digest, True, False
    valid = (
        type(evidence) is dict
        and evidence.get("source_head") == source_head
        and evidence.get("source_tree") == source_tree
    )
    return digest, True, valid


def _partial_evidence_hash(expected_file: Path, a2: object) -> tuple[str | None, bool]:
    """Preserve a digest only from the checked A2-owned destination."""
    if not _evidence_path_is_observer_owned(expected_file, a2):
        return None, False
    try:
        return hashlib.sha256(expected_file.read_bytes()).hexdigest(), True
    except OSError:
        return None, False


def _exception_result(
    expected_file: Path,
    source_head: str,
    source_tree: str,
    a2: object,
) -> dict[str, object]:
    digest, evidence_written = _partial_evidence_hash(expected_file, a2)
    return {
        "status": "BLOCKED",
        "reason": "OBSERVER_EXCEPTION_AFTER_DISPATCH",
        "disposition": "BLOCKED",
        "observer_dispatched": True,
        "observer_invocation_attempts": 1,
        "observer_status": "OBSERVER_EXCEPTION_AFTER_DISPATCH",
        "observer_reason": "OBSERVER_EXCEPTION_AFTER_DISPATCH",
        "observer_evidence_path": str(expected_file),
        "observer_evidence_sha256": digest,
        "observer_evidence_written": evidence_written,
        "observer_evidence_valid": False if evidence_written else None,
        "attempt_counters": None,
        "attempt_counters_status": "UNKNOWN_AFTER_DISPATCH_EXCEPTION",
        "source_head": source_head,
        "source_tree": source_tree,
        "source_identity_status": "AVAILABLE",
        "partition_equality_proof": "NOT_PROVEN",
        "production_order_scope_authority": "NOT_GRANTED",
    }


def _typed_observer_fields(result: object, a2: object):
    """Keep only the A2 result's known status, reason, and counter material."""
    status = getattr(result, "status", None)
    status_type = a2.AgentInitiatedPartitionObservationStatus
    review_status = status_type.AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW
    if isinstance(status, status_type):
        status_value = status.value
    else:
        status_value = "OBSERVER_RESULT_INVALID"

    reason = getattr(result, "reason", None)
    safe_reason = (
        reason
        if type(reason) is str and _SAFE_REASON.fullmatch(reason)
        else "OBSERVER_RESULT_INVALID"
    )

    raw_counters = getattr(result, "attempt_counters", None)
    counter_keys = set(a2._AttemptCounters().material())
    counters_valid = (
        type(raw_counters) is dict
        and set(raw_counters) == counter_keys
        and all(type(value) is int and value >= 0 for value in raw_counters.values())
    )
    counters = dict(raw_counters) if counters_valid else None
    valid = (
        status_value != "OBSERVER_RESULT_INVALID"
        and safe_reason != "OBSERVER_RESULT_INVALID"
        and counters_valid
    )
    if status is review_status and safe_reason != _REVIEW_REASON:
        valid = False
    return status_value, safe_reason, counters, valid


def run_preflight() -> dict[str, object]:
    """Run the existing A2 observer once after independent source admission."""
    try:
        from scripts import checkpoint_runner as runner
        from trading_bot.robinhood_mcp import (
            agent_initiated_partition_schema_observer as a2,
        )

        canonical_root = a2._CANONICAL_WORKTREE
        repo_root = canonical_root.resolve(strict=True)
        if (
            repo_root != canonical_root
            or Path(runner.__file__).resolve(strict=True).parents[1] != repo_root
            or Path(__file__).resolve(strict=True).parents[1] != repo_root
            or Path(a2.__file__).resolve(strict=True).parents[3] != repo_root
        ):
            return _blocked_before_dispatch("CANONICAL_WORKTREE_REJECTED", None, None)
        spec = runner._checkpoint_specs().get(runner.ARCH147_PROTOTYPE_NAME)
        if (
            spec is None
            or spec.preflight is not runner._arch147_l43_a3_preflight
            or spec.execute is not None
            or spec.remote_head_env is not None
            or runner._arch147_prototype_authority_check(repo_root)
        ):
            return _blocked_before_dispatch("A3_REGISTRATION_REJECTED", None, None)
        admission = a2._admit_current_source(repo_root=repo_root)
    except Exception:
        return _blocked_before_dispatch("SOURCE_ADMISSION_BLOCKED", None, None)

    source_head, source_tree = _admission_identity(admission, a2)
    if source_head is None or source_tree is None:
        return _blocked_before_dispatch(
            "SOURCE_ADMISSION_BLOCKED",
            source_head,
            source_tree,
        )
    if not _admission_matches(admission, a2, repo_root, source_head, source_tree):
        return _blocked_before_dispatch(
            "SOURCE_ADMISSION_BLOCKED",
            source_head,
            source_tree,
        )

    try:
        evidence_dir = a2._EVIDENCE_ROOT / (_A2_EVIDENCE_PREFIX + uuid4().hex)
        destination_available = (
            not evidence_dir.exists() and not evidence_dir.is_symlink()
        )
    except (OSError, RuntimeError, ValueError):
        return _blocked_before_dispatch(
            "OBSERVER_EVIDENCE_DESTINATION_UNAVAILABLE", source_head, source_tree
        )
    if (
        not destination_available
        or evidence_dir.parent != a2._EVIDENCE_ROOT
        or a2._RUNTIME_EVIDENCE_NAME.fullmatch(evidence_dir.name) is None
    ):
        return _blocked_before_dispatch(
            "OBSERVER_EVIDENCE_DESTINATION_UNAVAILABLE", source_head, source_tree
        )
    expected_file = evidence_dir / "evidence.json"
    try:
        observer = a2.RobinhoodAgentInitiatedRuntimePartitionSchemaObserver()
    except (OSError, RuntimeError, TypeError, ValueError):
        return _blocked_before_dispatch(
            "OBSERVER_CONSTRUCTION_FAILED", source_head, source_tree
        )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        return _blocked_before_dispatch(
            "ASYNC_RUNNER_ALREADY_ACTIVE", source_head, source_tree
        )

    dispatched = False

    async def invoke_observer():
        nonlocal dispatched
        dispatched = True
        return await observer.observe(evidence_dir=evidence_dir)

    try:
        result = asyncio.run(invoke_observer())
    except (Exception, asyncio.CancelledError, KeyboardInterrupt):
        if not dispatched:
            return _blocked_before_dispatch(
                "OBSERVER_DISPATCH_NOT_STARTED", source_head, source_tree
            )
        failure = _exception_result(expected_file, source_head, source_tree, a2)
        return _apply_source_recheck(
            failure,
            _post_dispatch_source_recheck(a2, repo_root, source_head, source_tree),
        )

    if not isinstance(result, a2.AgentInitiatedPartitionObservationResult):
        failure = _exception_result(expected_file, source_head, source_tree, a2)
        return _apply_source_recheck(
            failure,
            _post_dispatch_source_recheck(a2, repo_root, source_head, source_tree),
        )

    source_recheck_passed = _post_dispatch_source_recheck(
        a2, repo_root, source_head, source_tree
    )
    try:
        evidence_sha256, evidence_written, evidence_valid = _evidence_summary(
            expected_file, result, source_head, source_tree, a2
        )
    except (Exception, asyncio.CancelledError, KeyboardInterrupt):
        evidence_sha256, evidence_written = _partial_evidence_hash(expected_file, a2)
        evidence_valid = False

    observer_status, observer_reason, attempt_counters, result_valid = (
        _typed_observer_fields(result, a2)
    )
    status_type = a2.AgentInitiatedPartitionObservationStatus
    review_status = status_type.AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW
    successful = result_valid and result.status is review_status and evidence_valid
    reason = (
        "OBSERVER_RESULT_INVALID"
        if not result_valid
        else observer_reason
        if evidence_valid and source_recheck_passed
        else "OBSERVER_SOURCE_RECHECK_BLOCKED"
        if not source_recheck_passed
        else "OBSERVER_EVIDENCE_INVALID"
    )
    return _apply_source_recheck(
        {
            "status": "PASS" if successful else "BLOCKED",
            "reason": reason,
            "disposition": "SUCCESS_REVIEW_ONLY" if successful else "BLOCKED",
            "observer_dispatched": True,
            "observer_invocation_attempts": 1,
            "observer_status": observer_status,
            "observer_reason": observer_reason,
            "observer_evidence_path": str(expected_file),
            "observer_evidence_sha256": evidence_sha256,
            "observer_evidence_written": evidence_written,
            "observer_evidence_valid": evidence_valid,
            "attempt_counters": attempt_counters,
            "attempt_counters_status": "KNOWN"
            if attempt_counters is not None
            else "INVALID",
            "source_head": source_head,
            "source_tree": source_tree,
            "source_identity_status": "AVAILABLE",
            "partition_equality_proof": "NOT_PROVEN",
            "production_order_scope_authority": "NOT_GRANTED",
        },
        source_recheck_passed,
    )
