"""One-shot, sanitized PM2A read qualification attempt.

Importing this module is inert. The explicit operation reserves an attempt ID
and records the exact authorized source before opening any provider session.
Each attempt ID is create-once; a reserved directory left by a crash is
consumed and cannot be retried. A separately reviewed attempt must use a new
ID. Provider access is limited to the existing read schema qualifier and the
five-method current read transport.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final

from trading_bot.desktop_paper.robinhood_read import data
from trading_bot.portfolio_manager.models import (
    PortfolioObservation,
)
from trading_bot.portfolio_manager.observation import (
    PortfolioObservationError,
    account_candidates,
    observe_robinhood_portfolio,
)
from trading_bot.robinhood_mcp.current_read_schema_qualification import (
    CurrentReadSchemaQualification,
    SchemaQualificationStatus,
    qualify_current_read_provider,
)
from trading_bot.robinhood_mcp.current_read_transport import (
    READ_TOOLS,
    RobinhoodCurrentReadTransport,
)

_REPO_ROOT: Final = Path(__file__).resolve().parents[3]
_EXPECTED_WORKTREE: Final = Path(
    r"F:\AI\worktrees\ai-trading-bot-portfolio-manager-current"
)
_ATTEMPT_ROOT: Final = Path(r"F:\AI\temp")
_EXPECTED_ORIGIN: Final = "https://github.com/callmedraken/ai-trading-bot.git"
_FEATURE_REF: Final = "refs/heads/feature/robinhood-portfolio-manager-current"
_DEVELOP_REF: Final = "refs/heads/develop"
_OBJECT_ID = re.compile(r"[0-9a-f]{40}\Z")
_FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")
_ATTEMPT_ID = re.compile(r"[0-9a-f]{32}\Z")
_SAFE_REASON = re.compile(r"[A-Z0-9_]{1,64}\Z")
_QUOTE_MAX_AGE = timedelta(minutes=5)


class QualificationAttemptStatus(StrEnum):
    OBSERVED = "OBSERVED"
    SCHEMA_INCOMPLETE = "SCHEMA_INCOMPLETE"
    SCHEMA_MALFORMED = "SCHEMA_MALFORMED"
    READ_INCOMPLETE = "READ_INCOMPLETE"
    SOURCE_AUTHORITY_BLOCKED = "SOURCE_AUTHORITY_BLOCKED"
    SOURCE_CHANGED_BEFORE_PROVIDER = "SOURCE_CHANGED_BEFORE_PROVIDER"
    SOURCE_CHANGED_DURING_ATTEMPT = "SOURCE_CHANGED_DURING_ATTEMPT"
    ATTEMPT_ALREADY_CONSUMED = "ATTEMPT_ALREADY_CONSUMED"
    EVIDENCE_WRITE_FAILURE = "EVIDENCE_WRITE_FAILURE"
    ASYNC_CONTEXT_REJECTED = "ASYNC_CONTEXT_REJECTED"


@dataclass(frozen=True, slots=True)
class QualificationAttemptResult:
    status: QualificationAttemptStatus
    reason: str
    evidence_file: Path | None
    evidence_sha256: str | None


@dataclass(frozen=True, slots=True)
class _SourceIdentity:
    repository: str
    branch: str
    head: str
    tree: str
    origin: str
    remote_feature_head: str
    remote_develop_head: str
    feature_authority: str
    prospective_develop_authority: str


@dataclass(slots=True)
class _AttemptCounts:
    oauth_factory_attempts: int = 0
    mcp_session_open_attempts: int = 0
    tools_list_call_attempts: int = 0
    tools_list_pages_received: int = 0
    read_tool_invocation_counts: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(READ_TOOLS, 0)
    )
    observed_account_count: int | None = None
    eligible_account_count: int | None = None
    position_page_attempts: int = 0
    position_pages_received: int = 0
    position_rows_received: int = 0
    order_page_attempts: int = 0
    order_pages_received: int = 0
    order_rows_received: int = 0

    def schema_event(self, name: str) -> None:
        if name == "oauth_factory":
            self.oauth_factory_attempts += 1
        elif name == "mcp_session":
            self.mcp_session_open_attempts += 1
        elif name == "tools_list_call":
            self.tools_list_call_attempts += 1
        elif name == "tools_list_page":
            self.tools_list_pages_received += 1


class _CountingReadBoundary:
    """Count safe row/page facts while delegating only the current read API."""

    __slots__ = ("_read", "_counts")

    def __init__(self, read: object, counts: _AttemptCounts) -> None:
        self._read = read
        self._counts = counts

    def __enter__(self) -> _CountingReadBoundary:
        enter = getattr(self._read, "__enter__", None)
        if callable(enter):
            enter()
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        leave = getattr(self._read, "__exit__", None)
        return bool(leave(exc_type, exc, traceback)) if callable(leave) else False

    def get_accounts(self) -> Mapping[str, object]:
        self._counts.read_tool_invocation_counts["get_accounts"] += 1
        payload = self._read.get_accounts()
        try:
            rows = data(payload).get("accounts")
            if isinstance(rows, list):
                self._counts.observed_account_count = len(rows)
            candidates = account_candidates(payload)
            self._counts.eligible_account_count = sum(
                1 for item in candidates if item.eligible
            )
        except Exception:
            pass
        return payload

    def get_portfolio(self, arguments: Mapping[str, object]) -> Mapping[str, object]:
        self._counts.read_tool_invocation_counts["get_portfolio"] += 1
        return self._read.get_portfolio(arguments)

    def get_equity_positions(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self._counts.read_tool_invocation_counts["get_equity_positions"] += 1
        self._counts.position_page_attempts += 1
        payload = self._read.get_equity_positions(arguments)
        self._count_rows(payload, "positions")
        return payload

    def get_equity_quotes(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self._counts.read_tool_invocation_counts["get_equity_quotes"] += 1
        return self._read.get_equity_quotes(arguments)

    def get_equity_orders(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self._counts.read_tool_invocation_counts["get_equity_orders"] += 1
        self._counts.order_page_attempts += 1
        payload = self._read.get_equity_orders(arguments)
        self._count_rows(payload, "orders")
        return payload

    def _count_rows(self, payload: Mapping[str, object], key: str) -> None:
        if key == "positions":
            self._counts.position_pages_received += 1
        else:
            self._counts.order_pages_received += 1
        try:
            rows = data(payload).get(key)
        except Exception:
            return
        if isinstance(rows, list):
            if key == "positions":
                self._counts.position_rows_received += len(rows)
            else:
                self._counts.order_rows_received += len(rows)


def run_pm2a_qualification_attempt(
    *,
    attempt_id: str,
    expected_source_head: str,
    expected_source_tree: str,
    selected_account_fingerprint: str,
    oauth_factory: Callable[[], object],
) -> QualificationAttemptResult:
    """Explicitly run one schema-first, read-only attempt and preserve evidence.

    The attempt ID selects one immutable directory below ``F:\\AI\\temp``.
    The source is admitted before reservation and checked again after the
    reservation, immediately before any OAuth/provider operation. Incomplete
    or malformed schemas terminate before a read tool can be invoked.
    """
    if not isinstance(attempt_id, str) or _ATTEMPT_ID.fullmatch(attempt_id) is None:
        raise ValueError("attempt_id must be 32 lowercase hexadecimal characters")
    if not callable(oauth_factory):
        raise TypeError("oauth_factory must be callable")
    if (
        not isinstance(expected_source_head, str)
        or _OBJECT_ID.fullmatch(expected_source_head) is None
        or not isinstance(expected_source_tree, str)
        or _OBJECT_ID.fullmatch(expected_source_tree) is None
    ):
        raise ValueError("expected source HEAD and tree must be lowercase Git IDs")
    if (
        not isinstance(selected_account_fingerprint, str)
        or _FINGERPRINT.fullmatch(selected_account_fingerprint) is None
    ):
        raise ValueError("selected_account_fingerprint must be a SHA-256 fingerprint")
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        return QualificationAttemptResult(
            QualificationAttemptStatus.ASYNC_CONTEXT_REJECTED,
            "ASYNC_CONTEXT_REJECTED",
            None,
            None,
        )

    try:
        source = _capture_source_identity()
    except Exception:
        return QualificationAttemptResult(
            QualificationAttemptStatus.SOURCE_AUTHORITY_BLOCKED,
            "SOURCE_AUTHORITY_BLOCKED",
            None,
            None,
        )
    if source.head != expected_source_head or source.tree != expected_source_tree:
        return QualificationAttemptResult(
            QualificationAttemptStatus.SOURCE_AUTHORITY_BLOCKED,
            "REVIEWED_SOURCE_MISMATCH",
            None,
            None,
        )

    try:
        attempt_dir, attempt_record_sha256 = _reserve_attempt(
            attempt_id,
            source,
            expected_source_head=expected_source_head,
            expected_source_tree=expected_source_tree,
            selected_account_fingerprint=selected_account_fingerprint,
        )
    except FileExistsError:
        return QualificationAttemptResult(
            QualificationAttemptStatus.ATTEMPT_ALREADY_CONSUMED,
            "ATTEMPT_ALREADY_CONSUMED",
            None,
            None,
        )
    except Exception:
        return QualificationAttemptResult(
            QualificationAttemptStatus.EVIDENCE_WRITE_FAILURE,
            "ATTEMPT_RESERVATION_FAILED",
            None,
            None,
        )

    counts = _AttemptCounts()
    status = QualificationAttemptStatus.SOURCE_CHANGED_BEFORE_PROVIDER
    reason = "SOURCE_CHANGED_BEFORE_PROVIDER"
    schema_result: CurrentReadSchemaQualification | None = None
    observation: PortfolioObservation | None = None
    observation_error: str | None = None
    try:
        try:
            current_source = _capture_source_identity()
        except Exception:
            raise _SourceChanged from None
        if current_source != source:
            raise _SourceChanged
        schema_result = asyncio.run(
            qualify_current_read_provider(oauth_factory, on_attempt=counts.schema_event)
        )
        if schema_result.status is SchemaQualificationStatus.INCOMPLETE:
            status = QualificationAttemptStatus.SCHEMA_INCOMPLETE
            reason = "PROVIDER_SCHEMA_INCOMPLETE"
        elif schema_result.status is SchemaQualificationStatus.MALFORMED:
            status = QualificationAttemptStatus.SCHEMA_MALFORMED
            reason = "PROVIDER_SCHEMA_MALFORMED"
        elif not _schema_supports_current_read_surface(schema_result):
            status = QualificationAttemptStatus.SCHEMA_INCOMPLETE
            reason = "CURRENT_READ_SCHEMA_INSUFFICIENT"
        else:
            try:
                current_source = _capture_source_identity()
            except Exception:
                raise _SourceChanged from None
            if current_source != source:
                raise _SourceChanged
            transport = _make_read_transport(oauth_factory)
            boundary = _CountingReadBoundary(transport, counts)
            try:
                observation = observe_robinhood_portfolio(
                    boundary,
                    observed_at=datetime.now(UTC),
                    selected_account_fingerprint=selected_account_fingerprint,
                )
                status = QualificationAttemptStatus.OBSERVED
                reason = "OBSERVATION_RETURNED"
            except PortfolioObservationError as exc:
                status = QualificationAttemptStatus.READ_INCOMPLETE
                reason = _safe_reason(exc.code, "READ_OPERATION_INCOMPLETE")
                if exc.condition is not None:
                    observation_error = exc.condition.value
            finally:
                _merge_transport_counts(counts, transport)
    except _SourceChanged:
        status = (
            QualificationAttemptStatus.SOURCE_CHANGED_DURING_ATTEMPT
            if schema_result is not None
            else QualificationAttemptStatus.SOURCE_CHANGED_BEFORE_PROVIDER
        )
        reason = status.value
    except Exception:
        status = QualificationAttemptStatus.READ_INCOMPLETE
        reason = "QUALIFICATION_OPERATION_FAILED"

    try:
        source_recheck = _capture_source_identity()
        source_stable = (
            source_recheck == source
            and source_recheck.head == expected_source_head
            and source_recheck.tree == expected_source_tree
        )
    except Exception:
        source_recheck = None
        source_stable = False
    if not source_stable:
        status = QualificationAttemptStatus.SOURCE_CHANGED_DURING_ATTEMPT
        reason = "SOURCE_CHANGED_DURING_ATTEMPT"

    evidence = _evidence_material(
        attempt_id=attempt_id,
        expected_source_head=expected_source_head,
        expected_source_tree=expected_source_tree,
        source=source,
        source_stable=source_stable,
        status=status,
        reason=reason,
        attempt_record_sha256=attempt_record_sha256,
        selected_account_fingerprint=selected_account_fingerprint,
        schema_result=schema_result,
        observation=observation,
        observation_error=observation_error,
        counts=counts,
    )
    try:
        path, digest = _write_once(attempt_dir / "evidence.json", evidence)
    except Exception:
        return QualificationAttemptResult(
            QualificationAttemptStatus.EVIDENCE_WRITE_FAILURE,
            "EVIDENCE_WRITE_FAILURE",
            None,
            None,
        )
    return QualificationAttemptResult(status, reason, path, digest)


class _SourceChanged(RuntimeError):
    pass


def _capture_source_identity() -> _SourceIdentity:
    root = Path(_git_text(_REPO_ROOT, "rev-parse", "--show-toplevel")).resolve(
        strict=True
    )
    branch = _git_text(_REPO_ROOT, "branch", "--show-current")
    head = _git_text(_REPO_ROOT, "rev-parse", "--verify", "HEAD").lower()
    tree = _git_text(_REPO_ROOT, "show", "-s", "--format=%T", "HEAD").lower()
    porcelain = _git_text(
        _REPO_ROOT, "status", "--porcelain=v1", "--untracked-files=all"
    )
    origin = _git_text(_REPO_ROOT, "remote", "get-url", "origin")
    if (
        root != _EXPECTED_WORKTREE
        or branch != "feature/robinhood-portfolio-manager-current"
        or origin != _EXPECTED_ORIGIN
        or porcelain
        or _OBJECT_ID.fullmatch(head) is None
        or _OBJECT_ID.fullmatch(tree) is None
    ):
        raise _SourceChanged
    remote = _git_text(
        _REPO_ROOT,
        "ls-remote",
        "--refs",
        "origin",
        _FEATURE_REF,
        _DEVELOP_REF,
    )
    refs: dict[str, str] = {}
    for line in remote.splitlines():
        parts = line.split("\t")
        if len(parts) != 2 or parts[1] in refs:
            raise _SourceChanged
        refs[parts[1]] = parts[0].lower()
    feature_head = refs.get(_FEATURE_REF)
    develop_head = refs.get(_DEVELOP_REF)
    if (
        set(refs) != {_FEATURE_REF, _DEVELOP_REF}
        or feature_head != head
        or _OBJECT_ID.fullmatch(develop_head or "") is None
        or _git_status(_REPO_ROOT, "merge-base", "--is-ancestor", develop_head, head)
        != 0
    ):
        raise _SourceChanged

    from scripts import current_source_authority

    if Path(current_source_authority.__file__).resolve().parents[1] != root:
        raise _SourceChanged
    feature = current_source_authority.evaluate_source_authority(
        _REPO_ROOT,
        publication_context=current_source_authority.PublicationContext.FEATURE,
    )
    prospective = current_source_authority.evaluate_source_authority(
        _REPO_ROOT,
        publication_context=current_source_authority.PublicationContext.PROSPECTIVE_DEVELOP,
    )
    if (
        not feature.passed
        or not prospective.passed
        or feature.head != head
        or feature.tree != tree
        or prospective.head != head
        or prospective.tree != tree
    ):
        raise _SourceChanged
    return _SourceIdentity(
        str(root),
        branch,
        head,
        tree,
        origin,
        feature_head,
        develop_head,
        "PASS",
        "PASS",
    )


def _reserve_attempt(
    attempt_id: str,
    source: _SourceIdentity,
    *,
    expected_source_head: str,
    expected_source_tree: str,
    selected_account_fingerprint: str,
) -> tuple[Path, str]:
    root = _resolve_attempt_root()
    directory = root / f"arch152-pm2a-attempt-{attempt_id}"
    directory.mkdir()
    _, digest = _write_once(
        directory / "attempt.json",
        {
            "schema": "arch152-pm2a-attempt-reservation/v1",
            "attempt_id": attempt_id,
            "expected_source_head": expected_source_head,
            "expected_source_tree": expected_source_tree,
            "selected_account_fingerprint": selected_account_fingerprint,
            "consumption": "CONSUMED_ON_RESERVATION",
            "source": asdict(source),
            "reserved_at_utc": datetime.now(UTC).isoformat(),
        },
    )
    return directory, digest


def _resolve_attempt_root() -> Path:
    root = _ATTEMPT_ROOT.resolve(strict=True)
    if root != _ATTEMPT_ROOT or root.drive.upper() != "F:":
        raise ValueError("attempt root rejected")
    return root


def _evidence_material(
    *,
    attempt_id: str,
    expected_source_head: str,
    expected_source_tree: str,
    source: _SourceIdentity,
    source_stable: bool,
    status: QualificationAttemptStatus,
    reason: str,
    attempt_record_sha256: str,
    selected_account_fingerprint: str,
    schema_result: CurrentReadSchemaQualification | None,
    observation: PortfolioObservation | None,
    observation_error: str | None,
    counts: _AttemptCounts,
) -> dict[str, object]:
    read_counts = dict(counts.read_tool_invocation_counts)
    if observation is not None:
        quotes_available = sum(
            position.current_price is not None for position in observation.positions
        )
        fresh_quotes = sum(
            position.current_price is not None
            and position.price_observed_at is not None
            and observation.observed_at >= position.price_observed_at
            and observation.observed_at - position.price_observed_at <= _QUOTE_MAX_AGE
            for position in observation.positions
        )
        conditions = sorted(item.value for item in observation.conditions)
        order_scope = observation.coverage.order_scope.value
        account_fingerprint = observation.account_fingerprint
        account_bound = observation.coverage.account_bound
        pagination_complete = observation.coverage.pagination_complete
        cash_available = observation.cash is not None
        buying_power_available = observation.buying_power is not None
        unleveraged_buying_power_available = (
            observation.unleveraged_buying_power is not None
        )
    else:
        quotes_available = 0
        fresh_quotes = 0
        conditions = [observation_error or _safe_reason(reason, "UNKNOWN")]
        order_scope = "SCHEMA_ONLY_UNPROVEN"
        account_fingerprint = None
        account_bound = False
        pagination_complete = False
        cash_available = None
        buying_power_available = None
        unleveraged_buying_power_available = None
    if schema_result is None:
        schema = None
    else:
        schema = {
            "status": schema_result.status.value,
            "tools_list_pages": schema_result.tools_list_pages,
            "pagination_complete": schema_result.pagination_complete,
            "quarantined_tool_count": schema_result.quarantined_tool_count,
            "order_scope": schema_result.order_scope.value,
            "read_tools": [
                {
                    "name": tool.name,
                    "advertised": tool.advertised,
                    "input_schema_sha256": tool.input_schema_sha256,
                    "output_schema_sha256": tool.output_schema_sha256,
                    "input_arguments_complete": tool.input_arguments_complete,
                    "arguments": [
                        {
                            "name": argument.name,
                            "required": argument.required,
                            "types": argument.types,
                        }
                        for argument in tool.arguments
                    ],
                    "account_argument_status": tool.account_argument_status.value,
                    "pagination_arguments": tool.pagination_arguments,
                    "order_filter_arguments": tool.order_filter_arguments,
                    "result_schema_shape_complete": tool.result_schema_shape_complete,
                    "result_account_binding_paths": tool.result_account_binding_paths,
                    "result_pagination_paths": tool.result_pagination_paths,
                }
                for tool in schema_result.read_tools
            ],
        }
    invoked = [name for name in READ_TOOLS if read_counts[name] > 0]
    return {
        "schema": "arch152-pm2a-read-qualification-evidence/v1",
        "attempt_id": attempt_id,
        "expected_source_head": expected_source_head,
        "expected_source_tree": expected_source_tree,
        "source": asdict(source),
        "attempt_record_sha256": attempt_record_sha256,
        "source_stable_after_attempt": source_stable,
        "status": status.value,
        "reason": _safe_reason(reason, "QUALIFICATION_FAILED"),
        "account_fingerprint": account_fingerprint or selected_account_fingerprint,
        "observed_account_count": counts.observed_account_count,
        "eligible_account_count": counts.eligible_account_count,
        "selected_account_bound": account_bound,
        "provider_attempts": {
            "oauth_factory_attempts": counts.oauth_factory_attempts,
            "mcp_session_open_attempts": counts.mcp_session_open_attempts,
            "tools_list_call_attempts": counts.tools_list_call_attempts,
            "tools_list_pages_received": counts.tools_list_pages_received,
        },
        "read_tools_invoked": invoked,
        "read_tool_invocation_counts": read_counts,
        "position_pages": {
            "attempts": counts.position_page_attempts,
            "received": counts.position_pages_received,
            "rows": counts.position_rows_received,
        },
        "order_pages": {
            "attempts": counts.order_page_attempts,
            "received": counts.order_pages_received,
            "rows": counts.order_rows_received,
        },
        "pagination_complete": pagination_complete,
        "quotes_available_positions": quotes_available,
        "quotes_fresh_positions": fresh_quotes,
        "cash_available": cash_available,
        "buying_power_available": buying_power_available,
        "unleveraged_buying_power_available": unleveraged_buying_power_available,
        "cash_reservation_semantics": "UNKNOWN",
        "order_scope": order_scope,
        "unknown_or_incomplete_conditions": conditions,
        "effect_attempts": {
            "review": 0,
            "placement": 0,
            "cancellation": 0,
            "transfer": 0,
            "other": 0,
        },
        "schema_qualification": schema,
    }


def _schema_supports_current_read_surface(
    result: CurrentReadSchemaQualification,
) -> bool:
    """Require the closed schema surface used by the static PM read path."""
    if result.status is not SchemaQualificationStatus.COMPLETE:
        return False
    tools = {item.name: item for item in result.read_tools if item.advertised}
    if set(tools) != set(READ_TOOLS):
        return False
    required_arguments = {
        "get_accounts": {},
        "get_portfolio": {"account_number": {"string"}},
        "get_equity_positions": {
            "account_number": {"string"},
            "cursor": {"null", "string"},
        },
        "get_equity_quotes": {"symbols": {"array"}},
        "get_equity_orders": {
            "account_number": {"string"},
            "cursor": {"null", "string"},
            "placed_agent": {"string"},
            "created_at_gte": {"string"},
        },
    }
    for name, expected in required_arguments.items():
        fact = tools[name]
        if not fact.input_arguments_complete:
            return False
        actual = {item.name: set(item.types or ()) for item in fact.arguments}
        if any(
            argument not in actual or not types.issubset(actual[argument])
            for argument, types in expected.items()
        ):
            return False
    for name in ("get_accounts", "get_portfolio"):
        fact = tools[name]
        paths = fact.result_account_binding_paths
        if paths is None or not any(
            path.rsplit(".", 1)[-1] == "account_number" for path in paths
        ):
            return False
    for name, row_name in (
        ("get_equity_positions", "positions"),
        ("get_equity_orders", "orders"),
    ):
        fact = tools[name]
        account_paths = fact.result_account_binding_paths
        page_paths = fact.result_pagination_paths
        if (
            not fact.result_schema_shape_complete
            or account_paths is None
            or not any(
                path.rsplit(".", 1)[-1] == "account_number" and row_name in path
                for path in account_paths
            )
            or page_paths is None
            or not any(
                path.rsplit(".", 1)[-1] in {"next", "next_cursor", "nextCursor"}
                for path in page_paths
            )
        ):
            return False
    return all(item.result_schema_shape_complete for item in tools.values())


def _merge_transport_counts(counts: _AttemptCounts, transport: object) -> None:
    provider = getattr(transport, "_provider_attempt_counts", ())
    for name, value in provider:
        if name == "oauth_factory_attempts":
            counts.oauth_factory_attempts += value
        elif name == "mcp_session_open_attempts":
            counts.mcp_session_open_attempts += value
        elif name == "tools_list_call_attempts":
            counts.tools_list_call_attempts += value
        elif name == "tools_list_pages_received":
            counts.tools_list_pages_received += value


def _make_read_transport(
    oauth_factory: Callable[[], object],
) -> RobinhoodCurrentReadTransport:
    return RobinhoodCurrentReadTransport(oauth_factory)


def _write_once(path: Path, material: Mapping[str, object]) -> tuple[Path, str]:
    raw = (
        json.dumps(
            material,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return path, hashlib.sha256(raw).hexdigest()


def _git_text(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ("git", "-C", str(root), *arguments),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
    )
    if result.returncode != 0:
        raise ValueError("source identity unavailable")
    return result.stdout.strip()


def _git_status(root: Path, *arguments: str) -> int:
    result = subprocess.run(
        ("git", "-C", str(root), *arguments),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
    )
    return result.returncode


def _safe_reason(value: str, fallback: str) -> str:
    return value if _SAFE_REASON.fullmatch(value) else fallback
