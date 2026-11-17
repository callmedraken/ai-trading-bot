"""Manual, review-only dispatch for the RHC2 B2 successor observation."""

from __future__ import annotations

import asyncio
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from uuid import uuid4

_CANONICAL_WORKTREE = Path(r"F:\AI\worktrees\ai-trading-bot-live-prototype-current")
_Q62_READER_MODULE = "trading_bot.live_prototype.l43_production_owner"
_Q62_READER_PATH = "src/trading_bot/live_prototype/l43_production_owner.py"
_EVIDENCE_PREFIX = "arch147-agent-initiated-runtime-partition-"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ATTEMPT_COUNTERS = frozenset(
    {
        "oauth_scope_entry_attempts",
        "browser_launch_attempts",
        "mcp_session_open_attempts",
        "tools_list_attempts",
        "tools_list_pages_received",
        "mcp_tool_invocation_attempts",
        "account_read_attempts",
        "order_read_attempts",
        "review_attempts",
        "placement_attempts",
        "cancellation_attempts",
        "other_tool_attempts",
    }
)


def _expected_worktree() -> Path:
    """Return the fixed production checkout, with a narrow fake-test seam."""
    return _CANONICAL_WORKTREE


def _blocked(reason: str) -> dict[str, object]:
    return {
        "status": "BLOCKED",
        "reason": reason,
        "disposition": "REVIEW_ONLY",
        "production_order_scope_authority": "NOT_GRANTED",
    }


def _module_origin_is_canonical(
    module: ModuleType, *, repo_root: Path, relative_path: str
) -> bool:
    module_path = getattr(module, "__file__", None)
    if type(module_path) is not str:
        return False
    expected_path = repo_root / relative_path
    try:
        return expected_path.is_file() and Path(module_path).resolve(strict=True) == (
            expected_path
        )
    except (OSError, RuntimeError, ValueError):
        return False


def _q62_reader_spec_is_canonical(*, repo_root: Path) -> bool:
    try:
        spec = importlib.util.find_spec(_Q62_READER_MODULE)
        module_path = None if spec is None else spec.origin
        expected_path = repo_root / _Q62_READER_PATH
        return (
            type(module_path) is str
            and expected_path.is_file()
            and Path(module_path).resolve(strict=True) == expected_path
        )
    except Exception:
        return False


def _read_q62_expected_account_fingerprint(*, repo_root: Path) -> str:
    from trading_bot.live_prototype import l43_production_owner as q62_owner

    if not _module_origin_is_canonical(
        q62_owner, repo_root=repo_root, relative_path=_Q62_READER_PATH
    ):
        raise ValueError("canonical Q62 reader origin differs")
    origin = q62_owner.read_canonical_q62_origin()
    if type(origin) is not q62_owner.Q62JournalOrigin:
        raise ValueError("canonical Q62 origin type differs")
    identity = origin.runtime_identity
    if type(identity) is not q62_owner.RuntimeIdentity:
        raise ValueError("canonical Q62 runtime identity type differs")
    fingerprint = identity.account_fingerprint
    if type(fingerprint) is not str or _SHA256.fullmatch(fingerprint) is None:
        raise ValueError("canonical Q62 account fingerprint differs")
    return fingerprint


def _run_preflight() -> dict[str, object]:
    """Run one source-gated observer attempt and return review-only evidence."""
    try:
        expected_root = _expected_worktree()
        repo_root = expected_root.resolve(strict=True)
        if repo_root != expected_root:
            return _blocked("CANONICAL_WORKTREE_REJECTED")
        from scripts import checkpoint_runner

        if not _module_origin_is_canonical(
            sys.modules[__name__],
            repo_root=repo_root,
            relative_path="scripts/arch147_rhc2_order_scope_successor_source.py",
        ) or not _module_origin_is_canonical(
            checkpoint_runner,
            repo_root=repo_root,
            relative_path="scripts/checkpoint_runner.py",
        ):
            return _blocked("SOURCE_MODULE_ORIGIN_REJECTED")
        if checkpoint_runner._arch147_rhc2_authority_check(repo_root):
            return _blocked("CHECKPOINT_REGISTRATION_REJECTED")
    except Exception:
        return _blocked("SOURCE_AUTHORITY_REJECTED")

    if not _q62_reader_spec_is_canonical(repo_root=repo_root):
        return _blocked("Q62_ORIGIN_REJECTED")

    try:
        from trading_bot.robinhood_mcp import (
            agent_initiated_runtime_partition_observer as b2,
        )

        if not b2._module_origins_are_source_owned(repo_root=repo_root):
            return _blocked("OBSERVER_MODULE_ORIGIN_REJECTED")
    except (Exception, asyncio.CancelledError, KeyboardInterrupt):
        return _blocked("OBSERVER_EXCEPTION")

    try:
        expected_account_fingerprint = _read_q62_expected_account_fingerprint(
            repo_root=repo_root
        )
    except Exception:
        return _blocked("Q62_ORIGIN_REJECTED")

    try:
        evidence_dir = b2._EVIDENCE_ROOT / (_EVIDENCE_PREFIX + uuid4().hex)
        instance = b2.RobinhoodAgentInitiatedRuntimePartitionObserver(
            expected_account_fingerprint=expected_account_fingerprint
        )
        result = asyncio.run(instance.observe(evidence_dir=evidence_dir))
    except (Exception, asyncio.CancelledError, KeyboardInterrupt):
        return _blocked("OBSERVER_EXCEPTION")

    if type(result) is not b2.AgentInitiatedRuntimePartitionObservationResult:
        return _blocked("OBSERVER_RESULT_REJECTED")
    evidence_file = result.evidence_file
    evidence_recorded = (
        isinstance(evidence_file, Path)
        and evidence_file == evidence_dir / "evidence.json"
        and type(result.evidence_sha256) is str
        and _SHA256.fullmatch(result.evidence_sha256) is not None
    )
    captured = (
        result.status is b2.AgentInitiatedRuntimePartitionObservationStatus.PROVEN
        and evidence_recorded
        and result.source_recheck_status == "PASS"
        and result.production_order_scope_authority == "NOT_GRANTED"
    )
    counters = {
        key: value
        for key, value in result.attempt_counters.items()
        if key in _ATTEMPT_COUNTERS and type(value) is int and value >= 0
    }
    return {
        "status": "PASS" if captured else "BLOCKED",
        "reason": result.reason,
        "disposition": "REVIEW_ONLY",
        "observer_status": result.status.value,
        "observer_evidence_path": str(evidence_file) if evidence_recorded else None,
        "observer_evidence_sha256": (
            result.evidence_sha256 if evidence_recorded else None
        ),
        "attempt_counters": counters,
        "source_head": result.source_head,
        "source_tree": result.source_tree,
        "source_recheck_status": result.source_recheck_status,
        "provider_dispatch_started": (
            result.provider_dispatch_started
            if type(result.provider_dispatch_started) is bool
            else None
        ),
        "production_order_scope_authority": "NOT_GRANTED",
    }
