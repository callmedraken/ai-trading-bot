"""One-use, metadata-only observer for Robinhood order-scope semantics.

The production observer is inert until ``observe`` is explicitly called. That
operation admits the exact current source before creating OAuth or MCP state,
uses only MCP ``tools/list``, and writes digests and bounded evidence. A positive
classification is review evidence only; it grants no order or live authority.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import stat
import subprocess
import sys
import threading
import webbrowser
from collections.abc import Mapping, Sequence
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from io import StringIO
from pathlib import Path
from typing import Protocol

from trading_bot.robinhood_mcp.order_scope_schema_qualifier import (
    OrderScopeClassification,
    OrderScopeQualification,
    RobinhoodOrderScopeSchemaQualifier,
)

_OBSERVATION_SCHEMA = "arch147-robinhood-order-scope-observation/v1"
_OBSERVATION_NAME = "ARCH147_L43_ORDER_SCOPE_SCHEMA_ONLY"
_TARGET_TOOL = "get_equity_orders"
_CANONICAL_WORKTREE = Path(r"F:\AI\worktrees\ai-trading-bot-live-prototype-current")
_EVIDENCE_ROOT = Path(r"F:\AI\temp")
_EXPECTED_ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
_FEATURE_REF = "refs/heads/feature/robinhood-live-prototype-current"
_DEVELOP_REF = "refs/heads/develop"
_REDIRECT_URI = "http://127.0.0.1:8765/robinhood/callback"
_OBJECT_ID = re.compile(r"[0-9a-f]{40}\Z")
_EVIDENCE_NAME = re.compile(r"arch147-order-scope-schema-[0-9a-f]{32}\Z")
_SAFE_SCHEMA_TYPES = frozenset(
    {"array", "boolean", "integer", "null", "number", "object", "string"}
)
_OUTPUT_LOCK = threading.Lock()
_MISSING = object()


class OrderScopeObservationStatus(StrEnum):
    SCOPE_PROVEN_FOR_REVIEW = "SCOPE_PROVEN_FOR_REVIEW"
    PROVIDER_SEMANTICS_UNPROVEN = "PROVIDER_SEMANTICS_UNPROVEN"
    TARGET_TOOL_UNAVAILABLE = "TARGET_TOOL_UNAVAILABLE"
    SCHEMA_MALFORMED = "SCHEMA_MALFORMED"
    SOURCE_AUTHORITY_BLOCKED = "SOURCE_AUTHORITY_BLOCKED"
    OAUTH_SESSION_TOOLS_LIST_FAILURE = "OAUTH_SESSION_TOOLS_LIST_FAILURE"
    EVIDENCE_WRITE_FAILURE = "EVIDENCE_WRITE_FAILURE"


@dataclass(frozen=True, slots=True)
class OrderScopeObservationResult:
    status: OrderScopeObservationStatus
    reason: str
    evidence_file: Path | None
    evidence_sha256: str | None
    attempt_counters: dict[str, int]


@dataclass(frozen=True, slots=True)
class _SourceAdmission:
    root: str | None = None
    branch: str | None = None
    source_head: str | None = None
    source_tree: str | None = None
    porcelain: str = ""
    origin: str | None = None
    remote_feature_head: str | None = None
    remote_develop_head: str | None = None
    feature_authority: str = "NOT_RUN"
    prospective_develop_authority: str = "NOT_RUN"
    reason: str | None = "SOURCE_AUTHORITY_BLOCKED"

    @property
    def passed(self) -> bool:
        return (
            self.reason is None
            and self.source_head is not None
            and self.source_tree is not None
            and self.feature_authority == "PASS"
            and self.prospective_develop_authority == "PASS"
        )

    @property
    def remote_feature_tree(self) -> str | None:
        return (
            self.source_tree if self.remote_feature_head == self.source_head else None
        )

    @property
    def remote_develop_tree(self) -> str | None:
        return (
            self.source_tree if self.remote_develop_head == self.source_head else None
        )


@dataclass(slots=True)
class _AttemptCounters:
    oauth_scope_entry_attempts: int = 0
    browser_launches: int = 0
    mcp_session_open_attempts: int = 0
    tools_list_attempts: int = 0
    tools_list_pages_received: int = 0
    mcp_tool_invocation_attempts: int = 0
    account_reads: int = 0
    position_reads: int = 0
    order_reads: int = 0
    review_calls: int = 0
    placement_calls: int = 0
    cancellation_calls: int = 0
    other_tool_calls: int = 0

    def material(self) -> dict[str, int]:
        return asdict(self)


class _ToolsListClient(Protocol):
    async def list_tools(self, *, cursor: str | None = None) -> object: ...


class _MetadataToolsListTransport:
    """Only expose bounded metadata listing; provider dispatch is absent."""

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
            page = await self._client.list_tools(cursor=cursor)
            self._attempts.tools_list_pages_received += 1
        except asyncio.CancelledError:
            self.failed = True
            raise RuntimeError("metadata listing failed") from None
        except Exception:
            self.failed = True
            raise RuntimeError("metadata listing failed") from None
        return _normalize_page(page)


class RobinhoodOrderScopeSchemaObserver:
    """Lazy, single-attempt production observer."""

    __slots__ = (
        "_repo_root",
        "_used",
        "_guard",
    )

    def __init__(self) -> None:
        self._repo_root = Path(__file__).resolve().parents[3]
        self._used = False
        self._guard = threading.Lock()

    async def observe(self, *, evidence_dir: Path) -> OrderScopeObservationResult:
        """Run one explicit schema-only attempt and preserve sanitized evidence."""
        attempts = _AttemptCounters()
        if not self._guard.acquire(blocking=False):
            return OrderScopeObservationResult(
                OrderScopeObservationStatus.SOURCE_AUTHORITY_BLOCKED,
                "OBSERVER_ATTEMPT_ALREADY_USED",
                None,
                None,
                attempts.material(),
            )
        try:
            if self._used:
                return OrderScopeObservationResult(
                    OrderScopeObservationStatus.SOURCE_AUTHORITY_BLOCKED,
                    "OBSERVER_ATTEMPT_ALREADY_USED",
                    None,
                    None,
                    attempts.material(),
                )
            reserved = _reserve_evidence_directory(evidence_dir)
            self._used = True
        except Exception:
            return OrderScopeObservationResult(
                OrderScopeObservationStatus.EVIDENCE_WRITE_FAILURE,
                "EVIDENCE_DESTINATION_UNAVAILABLE",
                None,
                None,
                attempts.material(),
            )
        finally:
            self._guard.release()

        admission = _empty_admission()
        qualification: OrderScopeQualification | None = None
        transport_failed = False
        status = OrderScopeObservationStatus.SOURCE_AUTHORITY_BLOCKED
        reason = "SOURCE_AUTHORITY_BLOCKED"
        try:
            admission = _admit_current_source(repo_root=self._repo_root)
            if not admission.passed:
                status = OrderScopeObservationStatus.SOURCE_AUTHORITY_BLOCKED
                reason = admission.reason or "SOURCE_AUTHORITY_BLOCKED"
            else:
                with _suppress_external_output():
                    try:
                        qualification, transport_failed = await _run_production_session(
                            attempts, self._repo_root
                        )
                    except (Exception, asyncio.CancelledError):
                        transport_failed = True
                        qualification = None
                if qualification is not None and (
                    qualification.source_head != admission.source_head
                    or qualification.source_tree != admission.source_tree
                ):
                    qualification = None
                    status = OrderScopeObservationStatus.SOURCE_AUTHORITY_BLOCKED
                    reason = "SOURCE_AUTHORITY_BLOCKED"
                elif transport_failed:
                    status = (
                        OrderScopeObservationStatus.OAUTH_SESSION_TOOLS_LIST_FAILURE
                    )
                    reason = "OAUTH_SESSION_TOOLS_LIST_FAILURE"
                elif qualification is None:
                    status = (
                        OrderScopeObservationStatus.OAUTH_SESSION_TOOLS_LIST_FAILURE
                    )
                    reason = "OAUTH_SESSION_TOOLS_LIST_FAILURE"
                else:
                    status, reason = _result_status(qualification)
        except (Exception, asyncio.CancelledError):
            status = OrderScopeObservationStatus.SOURCE_AUTHORITY_BLOCKED
            reason = "SOURCE_AUTHORITY_BLOCKED"

        evidence = _evidence_material(
            admission=admission,
            qualification=qualification,
            status=status,
            reason=reason,
            attempts=attempts,
        )
        try:
            evidence_file, evidence_sha256 = _write_evidence(reserved, evidence)
        except Exception:
            return OrderScopeObservationResult(
                OrderScopeObservationStatus.EVIDENCE_WRITE_FAILURE,
                "EVIDENCE_WRITE_FAILURE",
                None,
                None,
                attempts.material(),
            )
        return OrderScopeObservationResult(
            status, reason, evidence_file, evidence_sha256, attempts.material()
        )


def _empty_admission() -> _SourceAdmission:
    return _SourceAdmission()


def _admit_current_source(*, repo_root: Path) -> _SourceAdmission:
    snapshot: _SourceAdmission | None = None
    try:
        expected_root = _CANONICAL_WORKTREE.resolve(strict=True)
        if (
            repo_root.resolve(strict=True) != expected_root
            or _loaded_checkout_root() != expected_root
            or expected_root != _CANONICAL_WORKTREE
        ):
            return _empty_admission()
        snapshot = _read_git_snapshot(repo_root)
        initial_snapshot = snapshot
        if (
            Path(snapshot.root or "").resolve(strict=True) != expected_root
            or snapshot.branch != "feature/robinhood-live-prototype-current"
            or snapshot.origin != _EXPECTED_ORIGIN
            or not _valid_object_id(snapshot.source_head)
            or not _valid_object_id(snapshot.source_tree)
            or bool(snapshot.porcelain)
            or snapshot.remote_feature_head != snapshot.source_head
            or snapshot.remote_develop_head != snapshot.source_head
        ):
            return replace(snapshot, reason="SOURCE_AUTHORITY_BLOCKED")

        from scripts import current_source_authority

        qualifier = sys.modules[RobinhoodOrderScopeSchemaQualifier.__module__]
        if (
            Path(current_source_authority.__file__).resolve().parents[1]
            != expected_root
            or Path(qualifier.__file__).resolve().parents[3] != expected_root
        ):
            return replace(snapshot, reason="SOURCE_AUTHORITY_BLOCKED")

        contexts = (
            ("feature_authority", current_source_authority.PublicationContext.FEATURE),
            (
                "prospective_develop_authority",
                current_source_authority.PublicationContext.PROSPECTIVE_DEVELOP,
            ),
        )
        for field, context in contexts:
            result = current_source_authority.evaluate_source_authority(
                repo_root, publication_context=context
            )
            snapshot = replace(snapshot, **{field: "PASS" if result.passed else "FAIL"})
            if (
                not result.passed
                or result.head != snapshot.source_head
                or result.tree != snapshot.source_tree
            ):
                return replace(snapshot, reason="SOURCE_AUTHORITY_BLOCKED")
        if _read_git_snapshot(repo_root) != initial_snapshot:
            return replace(snapshot, reason="SOURCE_AUTHORITY_BLOCKED")
        return replace(snapshot, reason=None)
    except Exception:
        return (
            _empty_admission()
            if snapshot is None
            else replace(snapshot, reason="SOURCE_AUTHORITY_BLOCKED")
        )


def _loaded_checkout_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_git_snapshot(repo_root: Path) -> _SourceAdmission:
    root = _git_text(repo_root, "rev-parse", "--show-toplevel")
    branch = _git_text(repo_root, "branch", "--show-current")
    head = _git_text(repo_root, "rev-parse", "--verify", "HEAD").lower()
    tree = _git_text(repo_root, "rev-parse", "--verify", "HEAD^{tree}").lower()
    porcelain = _git_text(
        repo_root, "status", "--porcelain=v1", "--untracked-files=all"
    )
    origin = _git_text(repo_root, "remote", "get-url", "origin")
    if origin != _EXPECTED_ORIGIN:
        raise ValueError("origin mismatch")
    refs = _git_text(
        repo_root, "ls-remote", "--refs", "origin", _FEATURE_REF, _DEVELOP_REF
    )
    identities: dict[str, str] = {}
    for line in refs.splitlines():
        parts = line.split("\t")
        if len(parts) != 2 or parts[1] in identities:
            raise ValueError("remote refs malformed")
        identities[parts[1]] = parts[0].lower()
    feature_head = identities.get(_FEATURE_REF)
    develop_head = identities.get(_DEVELOP_REF)
    if (
        set(identities) != {_FEATURE_REF, _DEVELOP_REF}
        or not _valid_object_id(feature_head)
        or not _valid_object_id(develop_head)
    ):
        raise ValueError("required live refs unavailable")
    return _SourceAdmission(
        root=root,
        branch=branch,
        source_head=head,
        source_tree=tree,
        porcelain=porcelain,
        origin=origin,
        remote_feature_head=feature_head,
        remote_develop_head=develop_head,
        reason=None,
    )


def _git_text(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ("git", "-C", str(repo_root), *arguments),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        env={
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
        },
    )
    if result.returncode != 0:
        raise ValueError("git source authority unavailable")
    return result.stdout.strip()


def _valid_object_id(value: object) -> bool:
    return type(value) is str and _OBJECT_ID.fullmatch(value) is not None


def _safe_object_id(value: str | None) -> str | None:
    return value if _valid_object_id(value) else None


async def _run_production_session(
    attempts: _AttemptCounters, repo_root: Path
) -> tuple[OrderScopeQualification | None, bool]:
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    from trading_bot.robinhood_mcp.sdk_transport import ROBINHOOD_TRADING_MCP_URL
    from trading_bot.robinhood_mcp.windows_oauth import (
        create_windows_robinhood_oauth_factory,
    )

    def launch_browser(url: str) -> object:
        if attempts.browser_launches >= 1:
            raise RuntimeError("browser flow limit reached")
        attempts.browser_launches += 1
        return webbrowser.open(url)

    oauth_factory = create_windows_robinhood_oauth_factory(
        redirect_uri=_REDIRECT_URI, browser_opener=launch_browser
    )
    attempts.oauth_scope_entry_attempts += 1
    oauth_auth = oauth_factory()
    async with httpx2.AsyncClient(auth=oauth_auth) as http_client:
        stream = streamable_http_client(
            ROBINHOOD_TRADING_MCP_URL, http_client=http_client
        )
        attempts.mcp_session_open_attempts += 1
        async with Client(stream) as client:
            qualification, failed = await _qualify(client, attempts, repo_root)
    return qualification, failed


async def _qualify(
    client: _ToolsListClient,
    attempts: _AttemptCounters,
    repo_root: Path,
) -> tuple[OrderScopeQualification, bool]:
    transport = _MetadataToolsListTransport(client, attempts)
    qualifier = RobinhoodOrderScopeSchemaQualifier(repo_root=repo_root)
    qualification = await qualifier.observe(test_tools_list=transport.list_tools)
    return qualification, transport.failed


_SCHEMA_ALIASES = ("input_schema", "inputSchema")
_CURSOR_ALIASES = ("next_cursor", "nextCursor")


def _normalize_page(page: object) -> dict[str, object]:
    tools = _read_field(page, "tools")
    if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes, bytearray)):
        raise ValueError("metadata tool page malformed")
    normalized: list[dict[str, object]] = []
    for entry in tools:
        name = _read_field(entry, "name")
        if type(name) is not str or not name:
            raise ValueError("metadata tool name malformed")
        item: dict[str, object] = {"name": name}
        if name == _TARGET_TOOL:
            description = _read_field(entry, "description")
            schema = _read_alias(entry, _SCHEMA_ALIASES)
            if description is not _MISSING:
                item["description"] = description
            if schema is not _MISSING:
                item["input_schema"] = schema
        normalized.append(item)
    next_cursor = _read_alias(page, _CURSOR_ALIASES, allow_identical=True)
    return {"tools": normalized, "next_cursor": next_cursor}


def _read_field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value.get(name, _MISSING)
    try:
        return getattr(value, name)
    except AttributeError:
        return _MISSING


def _read_alias(
    value: object, aliases: tuple[str, ...], *, allow_identical: bool = False
) -> object:
    present = [(name, _read_field(value, name)) for name in aliases]
    present = [(name, item) for name, item in present if item is not _MISSING]
    if len(present) > 1 and (
        not allow_identical or any(item != present[0][1] for _, item in present[1:])
    ):
        raise ValueError("ambiguous metadata field")
    return (None if allow_identical else _MISSING) if not present else present[0][1]


_RESULTS = {
    OrderScopeClassification.PROVEN_ACCOUNT_WIDE_ALL_AGENTS: (
        OrderScopeObservationStatus.SCOPE_PROVEN_FOR_REVIEW,
        "SCOPE_PROVEN_FOR_REVIEW_ONLY",
    ),
    OrderScopeClassification.UNPROVEN_PROVIDER_SEMANTICS: (
        OrderScopeObservationStatus.PROVIDER_SEMANTICS_UNPROVEN,
        "PROVIDER_SEMANTICS_UNPROVEN",
    ),
    OrderScopeClassification.TOOL_UNAVAILABLE: (
        OrderScopeObservationStatus.TARGET_TOOL_UNAVAILABLE,
        "TARGET_TOOL_UNAVAILABLE",
    ),
    OrderScopeClassification.SCHEMA_MALFORMED: (
        OrderScopeObservationStatus.SCHEMA_MALFORMED,
        "SCHEMA_MALFORMED",
    ),
    OrderScopeClassification.SOURCE_AUTHORITY_FAILED: (
        OrderScopeObservationStatus.SOURCE_AUTHORITY_BLOCKED,
        "SOURCE_AUTHORITY_BLOCKED",
    ),
}


def _result_status(
    qualification: OrderScopeQualification,
) -> tuple[OrderScopeObservationStatus, str]:
    return _RESULTS[qualification.classification]


def _evidence_material(
    *,
    admission: _SourceAdmission,
    qualification: OrderScopeQualification | None,
    status: OrderScopeObservationStatus,
    reason: str,
    attempts: _AttemptCounters,
) -> dict[str, object]:
    facts = {} if qualification is None else asdict(qualification)
    placed = facts.get("placed_agent")
    if placed is not None:
        placed["schema_type"] = _safe_schema_type(placed["schema_type"])
    classification = (
        qualification.classification.value
        if qualification is not None
        else (
            OrderScopeClassification.SOURCE_AUTHORITY_FAILED.value
            if status is OrderScopeObservationStatus.SOURCE_AUTHORITY_BLOCKED
            else "NOT_CLASSIFIED"
        )
    )
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
            "status": (
                "PASS"
                if admission.passed
                and status is not OrderScopeObservationStatus.SOURCE_AUTHORITY_BLOCKED
                else "BLOCKED"
            ),
        },
        "classification": classification,
        "qualifier_evidence_sha256": facts.get("evidence_sha256"),
        "target_tool_name": _TARGET_TOOL,
        "description_sha256": facts.get("description_sha256"),
        "input_schema_sha256": facts.get("input_schema_sha256"),
        "placed_agent_schema": placed,
        "tools_list_page_count": max(
            facts.get("tools_list_pages", 0),
            attempts.tools_list_pages_received,
        ),
        "exhaustive_pagination": facts.get("pagination_exhaustive", False),
        "attempt_counters": attempts.material(),
        "status": status.value,
        "reason": reason,
    }


def _safe_schema_type(value: str | None) -> str | None:
    if value is None:
        return None
    pieces = value.split("|")
    if not pieces or any(piece not in _SAFE_SCHEMA_TYPES for piece in pieces):
        return "UNRECOGNIZED"
    return "|".join(sorted(set(pieces)))


def _reserve_evidence_directory(evidence_dir: Path) -> Path:
    if not isinstance(evidence_dir, Path):
        raise TypeError("evidence directory must be a Path")
    root = _EVIDENCE_ROOT.resolve(strict=True)
    if (
        root != _EVIDENCE_ROOT
        or root.drive.upper() != "F:"
        or _is_reparse_point(root)
        or evidence_dir.parent != _EVIDENCE_ROOT
        or _EVIDENCE_NAME.fullmatch(evidence_dir.name) is None
    ):
        raise ValueError("evidence destination rejected")
    _reject_reparse_ancestors(root, stop=Path("F:/"))
    parent = evidence_dir.parent.resolve(strict=True)
    if parent != root or evidence_dir.exists() or evidence_dir.is_symlink():
        raise ValueError("evidence destination rejected")
    if evidence_dir.exists() or evidence_dir.is_symlink():
        raise ValueError("evidence destination already exists")
    evidence_dir.mkdir()
    if evidence_dir.is_symlink() or _is_reparse_point(evidence_dir):
        raise ValueError("evidence destination is a reparse point")
    return evidence_dir


def _reject_reparse_ancestors(path: Path, *, stop: Path) -> None:
    current = path
    while True:
        if current.is_symlink() or _is_reparse_point(current):
            raise ValueError("evidence path contains a reparse point")
        if current == stop:
            return
        if current.parent == current or not current.is_relative_to(stop):
            raise ValueError("evidence path is outside the fixed root")
        current = current.parent


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = getattr(path.stat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _write_evidence(
    evidence_dir: Path, material: dict[str, object]
) -> tuple[Path, str]:
    _verify_reserved_evidence_directory(evidence_dir)
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
    path = evidence_dir / "evidence.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return path, hashlib.sha256(raw).hexdigest()


def _verify_reserved_evidence_directory(directory: Path) -> None:
    root = _EVIDENCE_ROOT.resolve(strict=True)
    if (
        root != _EVIDENCE_ROOT
        or directory.parent != root
        or directory.resolve(strict=True) != directory
        or not directory.is_dir()
    ):
        raise ValueError("evidence directory changed")
    _reject_reparse_ancestors(directory, stop=Path("F:/"))


@contextmanager
def _suppress_external_output():
    """Silence provider writes, inherited stream handlers, and library logs."""
    if not _OUTPUT_LOCK.acquire(blocking=False):
        raise RuntimeError("overlapping provider output suppression rejected")
    try:
        for stream in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__):
            try:
                stream.flush()
            except Exception:
                pass
        saved_fds: list[tuple[int, int]] = []
        sink = os.open(os.devnull, os.O_WRONLY)
        previous_disable = logging.root.manager.disable
        try:
            for fd in (1, 2):
                saved = os.dup(fd)
                saved_fds.append((fd, saved))
                os.dup2(sink, fd)
            logging.disable(logging.CRITICAL)
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                yield
        finally:
            logging.disable(previous_disable)
            for stream in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__):
                try:
                    stream.flush()
                except Exception:
                    pass
            for fd, saved in reversed(saved_fds):
                os.dup2(saved, fd)
                os.close(saved)
            os.close(sink)
    finally:
        _OUTPUT_LOCK.release()


__all__ = [
    "OrderScopeObservationResult",
    "OrderScopeObservationStatus",
    "RobinhoodOrderScopeSchemaObserver",
]
