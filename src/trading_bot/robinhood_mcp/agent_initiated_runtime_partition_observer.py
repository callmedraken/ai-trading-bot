"""Guarded, one-use B2 runtime partition observation boundary.

The accepted B2 proof owns partition semantics.  This module owns only the
source/evidence guards, the restricted account/order provider transport,
attempt accounting, and review-only evidence custody.  Construction is inert;
provider dispatch is possible only from the explicit ``observe`` call.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
import threading
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from trading_bot.live_prototype.l43_production_owner import L43SourceIdentity
from trading_bot.robinhood_mcp.agent_initiated_runtime_partition_proof import (
    AgentInitiatedLogicalReadEvidence,
    AgentInitiatedRuntimePartitionProofResult,
    AgentInitiatedRuntimePartitionProofStatus,
    prove_agent_initiated_partition,
)
from trading_bot.robinhood_mcp.l43_read_adapter import (
    RobinhoodL43B2PreEffectReadAdapter,
)
from trading_bot.robinhood_mcp.order_scope_schema_observer import (
    _admit_current_source,
    _is_reparse_point,
    _reject_reparse_ancestors,
    _SourceAdmission,
    _suppress_external_output,
)
from trading_bot.robinhood_mcp.order_scope_schema_observer import (
    _write_evidence as _write_custody_evidence,
)

_OBSERVATION_SCHEMA = "arch147-agent-initiated-runtime-partition-observation/v1"
_OBSERVATION_NAME = "ARCH147_L43_AGENT_INITIATED_RUNTIME_PARTITION_OBSERVER"
_PROOF_CONTRACT_VERSION = "ARCH147_L43_B2_AGENT_INITIATED_RUNTIME_PARTITION/v1"
_CANONICAL_WORKTREE = Path(r"F:\AI\worktrees\ai-trading-bot-live-prototype-current")
_EVIDENCE_ROOT = Path(r"F:\AI\temp")
_EXPECTED_ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
_EXPECTED_BRANCH = "feature/robinhood-live-prototype-current"
_REDIRECT_URI = "http://127.0.0.1:8765/robinhood/callback"
_EVIDENCE_NAME = re.compile(r"arch147-agent-initiated-runtime-partition-[0-9a-f]{32}\Z")
_OBJECT_ID = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REASON = re.compile(r"[A-Z][A-Z0-9_]{0,127}\Z")
_TOOLS = frozenset(("get_accounts", "get_equity_orders"))
_MAX_TOOLS_LIST_PAGES = 20
_MAX_CURSOR_LENGTH = 4096


class AgentInitiatedRuntimePartitionObservationStatus(StrEnum):
    PROVEN = "PROVEN"
    NOT_PROVEN = "NOT_PROVEN"
    BLOCKED = "BLOCKED"
    SOURCE_AUTHORITY_BLOCKED = "SOURCE_AUTHORITY_BLOCKED"
    PROVIDER_EXCEPTION = "PROVIDER_EXCEPTION"
    MALFORMED_RESULT = "MALFORMED_RESULT"
    EVIDENCE_WRITE_FAILURE = "EVIDENCE_WRITE_FAILURE"
    OBSERVER_ATTEMPT_ALREADY_USED = "OBSERVER_ATTEMPT_ALREADY_USED"


@dataclass(frozen=True, slots=True)
class AgentInitiatedRuntimePartitionObservationResult:
    """Consumed review evidence; no field grants production order authority."""

    status: AgentInitiatedRuntimePartitionObservationStatus
    reason: str
    evidence_file: Path | None
    evidence_sha256: str | None
    attempt_counters: dict[str, int]
    source_head: str | None
    source_tree: str | None
    source_recheck_status: str
    provider_dispatch_started: bool
    production_order_scope_authority: str = "NOT_GRANTED"

    def __post_init__(self) -> None:
        if not isinstance(self.status, AgentInitiatedRuntimePartitionObservationStatus):
            raise TypeError("observation status must use the closed status type")
        if type(self.reason) is not str or _REASON.fullmatch(self.reason) is None:
            raise ValueError("observation reason must be sanitized")
        if type(self.attempt_counters) is not dict:
            raise TypeError("attempt counters must be a dictionary")
        if any(
            type(key) is not str or type(value) is not int or value < 0
            for key, value in self.attempt_counters.items()
        ):
            raise ValueError("attempt counters must be bounded nonnegative integers")
        if (
            self.source_head is not None
            and _OBJECT_ID.fullmatch(self.source_head) is None
        ):
            raise ValueError("source HEAD is invalid")
        if (
            self.source_tree is not None
            and _OBJECT_ID.fullmatch(self.source_tree) is None
        ):
            raise ValueError("source tree is invalid")
        if self.source_recheck_status not in {"PASS", "BLOCKED", "NOT_RUN"}:
            raise ValueError("source recheck status is invalid")
        if self.production_order_scope_authority != "NOT_GRANTED":
            raise ValueError("production order-scope authority is closed")


@dataclass(slots=True)
class _AttemptCounters:
    oauth_scope_entry_attempts: int = 0
    browser_launch_attempts: int = 0
    mcp_session_open_attempts: int = 0
    tools_list_attempts: int = 0
    tools_list_pages_received: int = 0
    mcp_tool_invocation_attempts: int = 0
    account_read_attempts: int = 0
    order_read_attempts: int = 0
    review_attempts: int = 0
    placement_attempts: int = 0
    cancellation_attempts: int = 0
    other_tool_attempts: int = 0

    def material(self) -> dict[str, int]:
        return asdict(self)


@dataclass(slots=True)
class _DispatchState:
    started: bool = False


class _ToolsListClient(Protocol):
    async def list_tools(self, *, cursor: str | None = None) -> object: ...

    async def call_tool(self, name: str, arguments: Mapping[str, object]) -> object: ...


class _B2ReadError(RuntimeError):
    """Internal fixed diagnostic; provider text never crosses the boundary."""


class RobinhoodB2ReadTransport:
    """Blocking transport with exactly account/order reads and counted attempts."""

    __slots__ = (
        "_oauth_factory",
        "_session_factory",
        "_attempts",
        "_dispatch_state",
    )

    def __init__(
        self,
        oauth_factory: Callable[[], object],
        attempts: _AttemptCounters,
        dispatch_state: _DispatchState,
    ) -> None:
        if not callable(oauth_factory):
            raise TypeError("OAuth factory must be callable")
        self._oauth_factory = oauth_factory
        self._session_factory: (
            Callable[[], AbstractAsyncContextManager[object]] | None
        ) = None
        self._attempts = attempts
        self._dispatch_state = dispatch_state

    @classmethod
    def for_test(
        cls,
        session_factory: Callable[[], AbstractAsyncContextManager[object]],
        attempts: _AttemptCounters,
        dispatch_state: _DispatchState,
    ) -> RobinhoodB2ReadTransport:
        instance = cls(lambda: None, attempts, dispatch_state)
        instance._session_factory = session_factory
        return instance

    def get_accounts(self) -> Mapping[str, object]:
        return self._invoke("get_accounts", {})

    def get_equity_orders(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        if not isinstance(arguments, Mapping):
            raise _B2ReadError("ORDER_ARGUMENTS_INVALID")
        return self._invoke("get_equity_orders", arguments)

    def _invoke(
        self, name: str, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        if name not in _TOOLS:
            raise _B2ReadError("READ_TOOL_REJECTED")
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise _B2ReadError("READ_EVENT_LOOP_REJECTED")
        try:
            return asyncio.run(self._request(name, dict(arguments)))
        except _B2ReadError:
            raise
        except Exception:
            raise _B2ReadError("READ_REQUEST_FAILED") from None

    async def _request(
        self, name: str, arguments: dict[str, object]
    ) -> Mapping[str, object]:
        session_factory = self._session_factory
        if session_factory is not None:
            self._attempts.mcp_session_open_attempts += 1
            async with session_factory() as client:
                return await self._read(client, name, arguments)

        try:
            import httpx2
            from mcp import Client
            from mcp.client.streamable_http import streamable_http_client
        except ImportError:
            raise _B2ReadError("MCP_DEPENDENCY_UNAVAILABLE") from None

        self._attempts.oauth_scope_entry_attempts += 1
        self._dispatch_state.started = True
        oauth_auth = self._oauth_factory()
        from trading_bot.robinhood_mcp.sdk_transport import ROBINHOOD_TRADING_MCP_URL

        async with httpx2.AsyncClient(auth=oauth_auth, timeout=60) as http_client:
            stream = streamable_http_client(
                ROBINHOOD_TRADING_MCP_URL, http_client=http_client
            )
            self._attempts.mcp_session_open_attempts += 1
            async with Client(stream) as client:
                return await self._read(client, name, arguments)

    async def _read(
        self, client: _ToolsListClient, name: str, arguments: dict[str, object]
    ) -> Mapping[str, object]:
        await self._require_b2_tools(client)
        if name == "get_accounts":
            if arguments:
                raise _B2ReadError("ACCOUNT_ARGUMENTS_INVALID")
            self._attempts.account_read_attempts += 1
        elif name == "get_equity_orders":
            self._attempts.order_read_attempts += 1
        else:
            raise _B2ReadError("READ_TOOL_REJECTED")
        self._attempts.mcp_tool_invocation_attempts += 1
        self._dispatch_state.started = True
        try:
            result = await client.call_tool(name, arguments)
        except Exception:
            raise _B2ReadError("READ_DISPATCH_FAILED") from None
        if getattr(result, "is_error", None) is not False:
            raise _B2ReadError("READ_RESULT_INVALID")
        payload = getattr(result, "structured_content", None)
        if not isinstance(payload, Mapping):
            raise _B2ReadError("READ_RESULT_INVALID")
        return dict(payload)

    async def _require_b2_tools(self, client: _ToolsListClient) -> None:
        cursor: str | None = None
        seen: set[str] = set()
        advertised: set[str] = set()
        for _ in range(_MAX_TOOLS_LIST_PAGES):
            self._attempts.tools_list_attempts += 1
            try:
                listing = await client.list_tools(cursor=cursor)
            except Exception:
                raise _B2ReadError("TOOLS_LIST_FAILED") from None
            self._attempts.tools_list_pages_received += 1
            tools = getattr(listing, "tools", None)
            if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes)):
                raise _B2ReadError("TOOLS_LIST_INVALID")
            for tool in tools:
                name = getattr(tool, "name", None)
                if type(name) is not str or not name:
                    raise _B2ReadError("TOOLS_LIST_INVALID")
                if name in _TOOLS:
                    advertised.add(name)
            next_cursor = getattr(listing, "next_cursor", None)
            if next_cursor is None:
                break
            if (
                type(next_cursor) is not str
                or not next_cursor
                or len(next_cursor) > _MAX_CURSOR_LENGTH
                or next_cursor in seen
            ):
                raise _B2ReadError("TOOLS_LIST_CURSOR_INVALID")
            seen.add(next_cursor)
            cursor = next_cursor
        else:
            raise _B2ReadError("TOOLS_LIST_BOUND_EXCEEDED")
        if advertised != _TOOLS:
            raise _B2ReadError("B2_READ_CAPABILITY_MISSING")


class RobinhoodAgentInitiatedRuntimePartitionObserver:
    """One-use source-gated observer; positive evidence remains review-only."""

    __slots__ = ("_repo_root", "_used", "_guard")

    def __init__(self) -> None:
        self._repo_root = Path(__file__).resolve().parents[3]
        self._used = False
        self._guard = threading.Lock()

    async def observe(
        self, *, evidence_dir: Path
    ) -> AgentInitiatedRuntimePartitionObservationResult:
        attempts = _AttemptCounters()
        if not self._guard.acquire(blocking=False):
            return _result(
                AgentInitiatedRuntimePartitionObservationStatus.OBSERVER_ATTEMPT_ALREADY_USED,
                "OBSERVER_ATTEMPT_ALREADY_USED",
                attempts=attempts,
                source_recheck_status="NOT_RUN",
            )
        try:
            if self._used:
                return _result(
                    AgentInitiatedRuntimePartitionObservationStatus.OBSERVER_ATTEMPT_ALREADY_USED,
                    "OBSERVER_ATTEMPT_ALREADY_USED",
                    attempts=attempts,
                    source_recheck_status="NOT_RUN",
                )
            self._used = True
        finally:
            self._guard.release()

        admission = _SourceAdmission()
        source_head: str | None = None
        source_tree: str | None = None
        reserved: Path | None = None
        proof_result: object | None = None
        proof_summary: dict[str, object] | None = None
        source_recheck_status = "NOT_RUN"
        status = AgentInitiatedRuntimePartitionObservationStatus.BLOCKED
        reason = "SOURCE_AUTHORITY_BLOCKED"
        dispatch_state = _DispatchState()

        if not _canonical_checkout_is_unambiguous(self._repo_root):
            return _result(
                AgentInitiatedRuntimePartitionObservationStatus.SOURCE_AUTHORITY_BLOCKED,
                "CANONICAL_WORKTREE_REJECTED",
                attempts=attempts,
                source_recheck_status=source_recheck_status,
            )
        try:
            admission = _admit_current_source(repo_root=self._repo_root)
        except Exception:
            admission = _SourceAdmission()
        source_head = _safe_object_id(admission.source_head)
        source_tree = _safe_object_id(admission.source_tree)
        if not admission.passed:
            return _result(
                AgentInitiatedRuntimePartitionObservationStatus.SOURCE_AUTHORITY_BLOCKED,
                admission.reason or "SOURCE_AUTHORITY_BLOCKED",
                attempts=attempts,
                source_head=source_head,
                source_tree=source_tree,
                source_recheck_status=source_recheck_status,
            )
        if not _module_origins_are_source_owned(repo_root=self._repo_root):
            return _result(
                AgentInitiatedRuntimePartitionObservationStatus.SOURCE_AUTHORITY_BLOCKED,
                "MODULE_ORIGIN_REJECTED",
                attempts=attempts,
                source_head=source_head,
                source_tree=source_tree,
                source_recheck_status=source_recheck_status,
            )

        try:
            reserved = _reserve_evidence_directory(evidence_dir)
        except Exception:
            return _result(
                AgentInitiatedRuntimePartitionObservationStatus.EVIDENCE_WRITE_FAILURE,
                "EVIDENCE_DESTINATION_REJECTED",
                attempts=attempts,
                source_head=source_head,
                source_tree=source_tree,
                source_recheck_status=source_recheck_status,
            )

        expected_source = L43SourceIdentity(source_head, source_tree)
        try:
            with _suppress_external_output():
                # Run the blocking proof/transport in a worker with no active
                # event loop; the proof engine itself is intentionally sync.
                proof_result = await asyncio.to_thread(
                    _run_production_session,
                    attempts,
                    dispatch_state,
                    self._repo_root,
                    expected_source,
                )
        except (Exception, asyncio.CancelledError):
            status = AgentInitiatedRuntimePartitionObservationStatus.PROVIDER_EXCEPTION
            reason = "PROVIDER_EXCEPTION"
        else:
            proof_summary, validation_reason = _validate_proof_result(
                proof_result, expected_source
            )
            if validation_reason is not None:
                status = (
                    AgentInitiatedRuntimePartitionObservationStatus.MALFORMED_RESULT
                )
                reason = validation_reason
            else:
                assert proof_summary is not None
                if (
                    proof_result.status
                    is AgentInitiatedRuntimePartitionProofStatus.PROVEN
                ):
                    status = AgentInitiatedRuntimePartitionObservationStatus.PROVEN
                else:
                    status = AgentInitiatedRuntimePartitionObservationStatus.NOT_PROVEN
                reason = proof_result.reason

        source_recheck_status = (
            "PASS" if _source_recheck(self._repo_root, expected_source) else "BLOCKED"
        )
        if source_recheck_status != "PASS":
            status = AgentInitiatedRuntimePartitionObservationStatus.BLOCKED
            reason = "SOURCE_RECHECK_BLOCKED"

        evidence = _evidence_material(
            admission=admission,
            status=status,
            reason=reason,
            proof_summary=proof_summary,
            attempts=attempts,
            source_recheck_status=source_recheck_status,
        )
        try:
            evidence_file, evidence_sha256 = _write_evidence(reserved, evidence)
        except Exception:
            return _result(
                AgentInitiatedRuntimePartitionObservationStatus.EVIDENCE_WRITE_FAILURE,
                "EVIDENCE_WRITE_FAILURE",
                attempts=attempts,
                source_head=source_head,
                source_tree=source_tree,
                source_recheck_status=source_recheck_status,
                provider_dispatch_started=dispatch_state.started,
            )
        return _result(
            status,
            reason,
            evidence_file=evidence_file,
            evidence_sha256=evidence_sha256,
            attempts=attempts,
            source_head=source_head,
            source_tree=source_tree,
            source_recheck_status=source_recheck_status,
            provider_dispatch_started=dispatch_state.started,
        )


def _run_production_session(
    attempts: _AttemptCounters,
    dispatch_state: _DispatchState,
    repo_root: Path,
    expected_source: L43SourceIdentity,
) -> AgentInitiatedRuntimePartitionProofResult:
    from trading_bot.robinhood_mcp.windows_oauth import (
        create_windows_robinhood_oauth_factory,
    )

    def launch_browser(url: str) -> object:
        if attempts.browser_launch_attempts >= 1:
            raise _B2ReadError("BROWSER_FLOW_LIMIT")
        attempts.browser_launch_attempts += 1
        return webbrowser.open(url)

    oauth_factory = create_windows_robinhood_oauth_factory(
        redirect_uri=_REDIRECT_URI, browser_opener=launch_browser
    )
    transport = RobinhoodB2ReadTransport(oauth_factory, attempts, dispatch_state)
    adapter = RobinhoodL43B2PreEffectReadAdapter(transport)
    return prove_agent_initiated_partition(
        adapter,
        repo_root=repo_root,
        expected_source=expected_source,
    )


def _validate_proof_result(
    result: object, expected_source: L43SourceIdentity
) -> tuple[dict[str, object] | None, str | None]:
    if not isinstance(result, AgentInitiatedRuntimePartitionProofResult):
        return None, "PROOF_RESULT_TYPE_INVALID"
    if not isinstance(result.status, AgentInitiatedRuntimePartitionProofStatus):
        return None, "PROOF_STATUS_INVALID"
    if type(result.reason) is not str or _REASON.fullmatch(result.reason) is None:
        return None, "PROOF_REASON_INVALID"
    if result.contract_version != _PROOF_CONTRACT_VERSION:
        return None, "PROOF_CONTRACT_INVALID"
    if (result.source_head, result.source_tree) != (
        expected_source.source_head,
        expected_source.source_tree,
    ):
        return None, "PROOF_SOURCE_INVALID"
    if result.symbol != "SPY":
        return None, "PROOF_SYMBOL_INVALID"
    if result.production_order_scope_authority != "NOT_GRANTED":
        return None, "PROOF_AUTHORITY_INVALID"
    if result.partition_equality_proof not in {"PROVEN", "NOT_PROVEN"}:
        return None, "PROOF_EQUALITY_INVALID"
    if result.status is AgentInitiatedRuntimePartitionProofStatus.PROVEN:
        if result.partition_equality_proof != "PROVEN":
            return None, "PROOF_SUCCESS_INVALID"
    elif result.partition_equality_proof != "NOT_PROVEN":
        return None, "PROOF_FAILURE_INVALID"
    if result.account_fingerprint is not None and not _SHA256.fullmatch(
        result.account_fingerprint
    ):
        return None, "PROOF_ACCOUNT_INVALID"
    if (
        type(result.evidence_json) is not bytes
        or type(result.evidence_sha256) is not str
    ):
        return None, "PROOF_EVIDENCE_INVALID"
    if hashlib.sha256(result.evidence_json).hexdigest() != result.evidence_sha256:
        return None, "PROOF_EVIDENCE_HASH_INVALID"
    try:
        payload = json.loads(result.evidence_json.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "PROOF_EVIDENCE_JSON_INVALID"
    if not _safe_proof_payload(payload, result):
        return None, "PROOF_EVIDENCE_SHAPE_INVALID"
    expected_reads = (
        ("ALL_BEFORE", None),
        ("TRUE", True),
        ("FALSE", False),
        ("ALL_AFTER", None),
    )
    if (
        type(result.logical_reads) is not tuple
        or not 0 <= len(result.logical_reads) <= 4
    ):
        return None, "PROOF_LOGICAL_READS_INVALID"
    summaries: list[dict[str, object]] = []
    for item, (label, filter_value) in zip(
        result.logical_reads, expected_reads, strict=False
    ):
        if type(item) is not AgentInitiatedLogicalReadEvidence:
            return None, "PROOF_LOGICAL_READ_INVALID"
        if (item.label, item.agent_initiated) != (label, filter_value):
            return None, "PROOF_LOGICAL_READ_ORDER_INVALID"
        if not item.exhaustive:
            return None, "PROOF_LOGICAL_READ_NOT_EXHAUSTIVE"
        summaries.append(item.material())
    if (
        result.status is AgentInitiatedRuntimePartitionProofStatus.PROVEN
        and len(result.logical_reads) != 4
    ):
        return None, "PROOF_SUCCESS_LOGICAL_READS_INVALID"
    if result.status is AgentInitiatedRuntimePartitionProofStatus.PROVEN and any(
        value is None
        for value in (
            result.stable_all_universe_digest,
            result.true_partition_digest,
            result.false_partition_digest,
            result.canonical_order_material_digest,
        )
    ):
        return None, "PROOF_SUCCESS_DIGESTS_INVALID"
    for value in (
        result.stable_all_universe_digest,
        result.true_partition_digest,
        result.false_partition_digest,
        result.canonical_order_material_digest,
    ):
        if value is not None and not _SHA256.fullmatch(value):
            return None, "PROOF_DIGEST_INVALID"
    return {
        "contract_version": result.contract_version,
        "status": result.status.value,
        "reason": result.reason,
        "evidence_sha256": result.evidence_sha256,
        "account_fingerprint": result.account_fingerprint,
        "logical_reads": summaries,
        "stable_all_universe_digest": result.stable_all_universe_digest,
        "true_partition_digest": result.true_partition_digest,
        "false_partition_digest": result.false_partition_digest,
        "canonical_order_material_digest": result.canonical_order_material_digest,
        "partition_equality_proof": result.partition_equality_proof,
    }, None


def _safe_proof_payload(
    payload: object, result: AgentInitiatedRuntimePartitionProofResult
) -> bool:
    if not isinstance(payload, dict):
        return False
    expected_keys = {
        "account_fingerprint",
        "canonical_order_material_digest",
        "contract_version",
        "false_partition_digest",
        "logical_reads",
        "partition_equality_proof",
        "production_order_scope_authority",
        "reason",
        "source_head",
        "source_tree",
        "stable_all_universe_digest",
        "status",
        "symbol",
        "true_partition_digest",
    }
    if set(payload) != expected_keys:
        return False
    if any(
        isinstance(key, str)
        and any(
            token in key.casefold()
            for token in (
                "account_number",
                "order_id",
                "token",
                "oauth",
                "callback",
                "raw",
            )
        )
        for key in payload
    ):
        return False
    return all(
        payload[key] == expected
        for key, expected in {
            "contract_version": result.contract_version,
            "status": result.status.value,
            "reason": result.reason,
            "source_head": result.source_head,
            "source_tree": result.source_tree,
            "account_fingerprint": result.account_fingerprint,
            "symbol": result.symbol,
            "logical_reads": [item.material() for item in result.logical_reads],
            "stable_all_universe_digest": result.stable_all_universe_digest,
            "true_partition_digest": result.true_partition_digest,
            "false_partition_digest": result.false_partition_digest,
            "canonical_order_material_digest": result.canonical_order_material_digest,
            "partition_equality_proof": result.partition_equality_proof,
            "production_order_scope_authority": "NOT_GRANTED",
        }.items()
    )


def _source_recheck(repo_root: Path, expected_source: L43SourceIdentity) -> bool:
    try:
        admission = _admit_current_source(repo_root=repo_root)
    except Exception:
        return False
    return (
        admission.passed
        and admission.source_head == expected_source.source_head
        and admission.source_tree == expected_source.source_tree
        and admission.branch == _EXPECTED_BRANCH
        and admission.origin == _EXPECTED_ORIGIN
        and not admission.porcelain
    )


def _canonical_checkout_is_unambiguous(repo_root: Path) -> bool:
    try:
        expected = _CANONICAL_WORKTREE.resolve(strict=True)
        _reject_reparse_ancestors(expected, stop=Path("F:/"))
        return (
            expected == _CANONICAL_WORKTREE
            and repo_root.resolve(strict=True) == expected
            and Path(__file__).resolve(strict=True).parents[3] == expected
        )
    except (OSError, RuntimeError, ValueError):
        return False


def _module_origins_are_source_owned(*, repo_root: Path) -> bool:
    try:
        from scripts import current_source_authority
        from trading_bot.robinhood_mcp import (
            agent_initiated_runtime_partition_proof as proof_module,
        )
        from trading_bot.robinhood_mcp import (
            l43_read_adapter,
            order_scope_schema_observer,
        )

        expected = _CANONICAL_WORKTREE.resolve(strict=True)
        modules = (
            sys.modules[__name__],
            proof_module,
            l43_read_adapter,
            order_scope_schema_observer,
        )
        return (
            repo_root.resolve(strict=True) == expected
            and all(
                Path(module.__file__).resolve(strict=True).parents[3] == expected
                for module in modules
            )
            and Path(current_source_authority.__file__).resolve(strict=True).parents[1]
            == expected
        )
    except (AttributeError, IndexError, KeyError, OSError, RuntimeError):
        return False


def _reserve_evidence_directory(evidence_dir: Path) -> Path:
    if not isinstance(evidence_dir, Path):
        raise TypeError("evidence directory must be a Path")
    root = _EVIDENCE_ROOT.resolve(strict=True)
    if (
        root != _EVIDENCE_ROOT
        or root.drive.upper() != "F:"
        or evidence_dir.parent != _EVIDENCE_ROOT
        or _EVIDENCE_NAME.fullmatch(evidence_dir.name) is None
    ):
        raise ValueError("evidence destination rejected")
    _reject_reparse_ancestors(root, stop=Path("F:/"))
    if evidence_dir.exists() or evidence_dir.is_symlink():
        raise ValueError("evidence destination already exists")
    if evidence_dir.parent.resolve(strict=True) != root:
        raise ValueError("evidence destination rejected")
    evidence_dir.mkdir()
    if (
        evidence_dir.is_symlink()
        or _is_reparse_point(evidence_dir)
        or evidence_dir.resolve(strict=True) != evidence_dir
    ):
        raise ValueError("evidence destination is a reparse point")
    _reject_reparse_ancestors(evidence_dir, stop=Path("F:/"))
    return evidence_dir


def _write_evidence(
    evidence_dir: Path, material: dict[str, object]
) -> tuple[Path, str]:
    return _write_custody_evidence(evidence_dir, material)


def _evidence_material(
    *,
    admission: _SourceAdmission,
    status: AgentInitiatedRuntimePartitionObservationStatus,
    reason: str,
    proof_summary: dict[str, object] | None,
    attempts: _AttemptCounters,
    source_recheck_status: str,
) -> dict[str, object]:
    return {
        "schema": _OBSERVATION_SCHEMA,
        "observation": _OBSERVATION_NAME,
        "source_head": _safe_object_id(admission.source_head),
        "source_tree": _safe_object_id(admission.source_tree),
        "source_branch": _EXPECTED_BRANCH,
        "source_authority": {
            "feature": admission.feature_authority,
            "prospective_develop": admission.prospective_develop_authority,
            "status": "PASS" if admission.passed else "BLOCKED",
        },
        "b2_proof_contract_version": _PROOF_CONTRACT_VERSION,
        "b2_result": proof_summary,
        "b2_result_status": (
            None if proof_summary is None else proof_summary["status"]
        ),
        "b2_result_reason": (
            None if proof_summary is None else proof_summary["reason"]
        ),
        "b2_evidence_sha256": (
            None if proof_summary is None else proof_summary["evidence_sha256"]
        ),
        "account_fingerprint": (
            None if proof_summary is None else proof_summary["account_fingerprint"]
        ),
        "logical_reads": (
            [] if proof_summary is None else proof_summary["logical_reads"]
        ),
        "stable_all_universe_digest": (
            None
            if proof_summary is None
            else proof_summary["stable_all_universe_digest"]
        ),
        "true_partition_digest": (
            None if proof_summary is None else proof_summary["true_partition_digest"]
        ),
        "false_partition_digest": (
            None if proof_summary is None else proof_summary["false_partition_digest"]
        ),
        "canonical_order_material_digest": (
            None
            if proof_summary is None
            else proof_summary["canonical_order_material_digest"]
        ),
        "partition_equality_proof": (
            "NOT_PROVEN"
            if proof_summary is None
            else proof_summary["partition_equality_proof"]
        ),
        "attempt_counters": attempts.material(),
        "source_recheck_status": source_recheck_status,
        "status": status.value,
        "reason": reason,
        "production_order_scope_authority": "NOT_GRANTED",
    }


def _result(
    status: AgentInitiatedRuntimePartitionObservationStatus,
    reason: str,
    *,
    attempts: _AttemptCounters,
    evidence_file: Path | None = None,
    evidence_sha256: str | None = None,
    source_head: str | None = None,
    source_tree: str | None = None,
    source_recheck_status: str = "NOT_RUN",
    provider_dispatch_started: bool = False,
) -> AgentInitiatedRuntimePartitionObservationResult:
    return AgentInitiatedRuntimePartitionObservationResult(
        status=status,
        reason=reason,
        evidence_file=evidence_file,
        evidence_sha256=evidence_sha256,
        attempt_counters=attempts.material(),
        source_head=source_head,
        source_tree=source_tree,
        source_recheck_status=source_recheck_status,
        provider_dispatch_started=provider_dispatch_started,
    )


def _safe_object_id(value: object) -> str | None:
    return value if type(value) is str and _OBJECT_ID.fullmatch(value) else None


__all__ = [
    "AgentInitiatedRuntimePartitionObservationResult",
    "AgentInitiatedRuntimePartitionObservationStatus",
    "RobinhoodAgentInitiatedRuntimePartitionObserver",
    "RobinhoodB2ReadTransport",
]
