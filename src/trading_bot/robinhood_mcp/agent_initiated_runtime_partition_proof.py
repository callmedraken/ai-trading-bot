"""Closed, provider-independent proof of the L43 agent partition.

The proof consumes the normalized L43 read boundary only.  It deliberately
does not construct a provider, discover a tool, read credentials, or grant
the production order-scope authority owned by the L43 composition.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from trading_bot.domain import OrderSide
from trading_bot.live_prototype.l43_production_owner import L43SourceIdentity
from trading_bot.live_prototype.l43_provider_contracts import (
    L43AccountIdentity,
    L43DollarAmountFact,
    L43ExecutionFact,
    L43OrderFact,
    L43PreEffectReadBoundary,
    L43ReadPage,
)

_CONTRACT_VERSION = "ARCH147_L43_B2_AGENT_INITIATED_RUNTIME_PARTITION/v1"
_SYMBOL = "SPY"
_MAX_PAGES = 40
_MAX_ROWS = 10_000
_MAX_CURSOR_LENGTH = 4096
_ORDER_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_TEXT = re.compile(r"[^\x00-\x1f\x7f]{1,256}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REASON = re.compile(r"[A-Z][A-Z0-9_]{0,127}\Z")


class AgentInitiatedRuntimePartitionProofStatus(StrEnum):
    PROVEN = "PROVEN"
    NOT_PROVEN = "NOT_PROVEN"


@dataclass(frozen=True, slots=True)
class AgentInitiatedLogicalReadEvidence:
    """Safe evidence for one logical read; no account or order ID is exposed."""

    label: str
    agent_initiated: bool | None
    query_sha256: str
    page_count: int
    row_count: int
    exhaustive: bool

    def __post_init__(self) -> None:
        if not _REASON.fullmatch(self.label):
            raise ValueError("logical read label is invalid")
        if self.agent_initiated is not None and type(self.agent_initiated) is not bool:
            raise TypeError("logical read filter must be a strict bool or None")
        if type(self.query_sha256) is not str or not _SHA256.fullmatch(
            self.query_sha256
        ):
            raise ValueError("logical read query digest is invalid")
        if (
            type(self.page_count) is not int
            or self.page_count < 0
            or type(self.row_count) is not int
            or self.row_count < 0
            or type(self.exhaustive) is not bool
        ):
            raise ValueError("logical read counts are invalid")

    def material(self) -> dict[str, object]:
        return {
            "label": self.label,
            "agent_initiated": self.agent_initiated,
            "query_sha256": self.query_sha256,
            "page_count": self.page_count,
            "row_count": self.row_count,
            "exhaustive": self.exhaustive,
        }


@dataclass(frozen=True, slots=True)
class AgentInitiatedRuntimePartitionProofResult:
    """Closed proof result; ``PROVEN`` never implies production authority."""

    status: AgentInitiatedRuntimePartitionProofStatus
    reason: str
    contract_version: str
    source_head: str | None
    source_tree: str | None
    account_fingerprint: str | None
    symbol: str
    logical_reads: tuple[AgentInitiatedLogicalReadEvidence, ...]
    stable_all_universe_digest: str | None
    true_partition_digest: str | None
    false_partition_digest: str | None
    canonical_order_material_digest: str | None
    partition_equality_proof: str
    production_order_scope_authority: str
    evidence_json: bytes
    evidence_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, AgentInitiatedRuntimePartitionProofStatus):
            raise TypeError("proof status must use the closed status type")
        if type(self.reason) is not str or _REASON.fullmatch(self.reason) is None:
            raise ValueError("proof reason must be sanitized")
        if self.contract_version != _CONTRACT_VERSION:
            raise ValueError("proof contract version is invalid")
        if self.source_head is not None and not _git_sha(self.source_head):
            raise ValueError("proof source HEAD is invalid")
        if self.source_tree is not None and not _git_sha(self.source_tree):
            raise ValueError("proof source tree is invalid")
        if (self.source_head is None) != (self.source_tree is None):
            raise ValueError("proof source identity is incomplete")
        if self.account_fingerprint is not None and not _SHA256.fullmatch(
            self.account_fingerprint
        ):
            raise ValueError("proof account fingerprint is invalid")
        if self.symbol != _SYMBOL:
            raise ValueError("proof symbol is invalid")
        if self.partition_equality_proof not in {"PROVEN", "NOT_PROVEN"}:
            raise ValueError("proof equality result is invalid")
        if self.production_order_scope_authority != "NOT_GRANTED":
            raise ValueError("production order-scope authority must remain closed")
        for digest, label in (
            (self.stable_all_universe_digest, "all-universe digest"),
            (self.true_partition_digest, "true partition digest"),
            (self.false_partition_digest, "false partition digest"),
            (self.canonical_order_material_digest, "canonical material digest"),
        ):
            if digest is not None and not _SHA256.fullmatch(digest):
                raise ValueError(f"{label} is invalid")
        if self.status is AgentInitiatedRuntimePartitionProofStatus.PROVEN:
            if (
                len(self.logical_reads) != 4
                or self.partition_equality_proof != "PROVEN"
                or any(not item.exhaustive for item in self.logical_reads)
                or any(
                    value is None
                    for value in (
                        self.stable_all_universe_digest,
                        self.true_partition_digest,
                        self.false_partition_digest,
                        self.canonical_order_material_digest,
                    )
                )
            ):
                raise ValueError("successful proof is incomplete")
        elif self.partition_equality_proof != "NOT_PROVEN":
            raise ValueError("failed proof cannot assert equality")
        if type(self.evidence_json) is not bytes:
            raise TypeError("proof evidence must be canonical bytes")
        if not _SHA256.fullmatch(self.evidence_sha256):
            raise ValueError("proof evidence digest is invalid")
        if hashlib.sha256(self.evidence_json).hexdigest() != self.evidence_sha256:
            raise ValueError("proof evidence digest does not match bytes")

    @property
    def proven(self) -> bool:
        return self.status is AgentInitiatedRuntimePartitionProofStatus.PROVEN


@dataclass(frozen=True, slots=True)
class _ReadSpec:
    label: str
    agent_initiated: bool | None


@dataclass(frozen=True, slots=True)
class _ReadSnapshot:
    evidence: AgentInitiatedLogicalReadEvidence
    ids: frozenset[str]


class _ProofFailure(Exception):
    def __init__(self, reason: str) -> None:
        if _REASON.fullmatch(reason) is None:
            raise ValueError("internal proof reason is not sanitized")
        self.reason = reason


_READS = (
    _ReadSpec("ALL_BEFORE", None),
    _ReadSpec("TRUE", True),
    _ReadSpec("FALSE", False),
    _ReadSpec("ALL_AFTER", None),
)


def prove_agent_initiated_partition(
    read: L43PreEffectReadBoundary,
    *,
    repo_root: Path | None = None,
    source_reader: Callable[[], L43SourceIdentity] | None = None,
    expected_source: L43SourceIdentity | None = None,
    expected_account_fingerprint: str | None = None,
) -> AgentInitiatedRuntimePartitionProofResult:
    """Prove the exact four-read SPY partition using normalized L43 facts.

    The function is intentionally an injected seam.  It returns a closed
    result for every invalid, incomplete, conflicting, or exceptional input;
    provider exceptions and raw payloads never enter the result evidence.
    """

    if source_reader is None:
        if not isinstance(repo_root, Path):
            return _result(reason="SOURCE_READER_INVALID")

        def repo_source_reader() -> L43SourceIdentity:
            return _read_source_identity(repo_root)

        source_reader = repo_source_reader
    if not callable(source_reader):
        return _result(reason="SOURCE_READER_INVALID")
    if expected_source is not None and type(expected_source) is not L43SourceIdentity:
        return _result(reason="SOURCE_IDENTITY_INVALID")
    if expected_account_fingerprint is not None and not _SHA256.fullmatch(
        expected_account_fingerprint
    ):
        return _result(reason="ACCOUNT_EXPECTATION_INVALID")
    if not all(
        callable(getattr(read, name, None))
        for name in ("get_accounts", "get_equity_orders")
    ):
        return _result(reason="READ_BOUNDARY_INVALID")

    try:
        source_before = source_reader()
    except Exception:
        return _result(reason="SOURCE_READ_FAILED")
    if type(source_before) is not L43SourceIdentity:
        return _result(reason="SOURCE_IDENTITY_INVALID")
    if expected_source is not None and source_before != expected_source:
        return _result(
            reason="SOURCE_MISMATCH",
            source=source_before,
        )

    try:
        account = read.get_accounts()
    except Exception:
        return _result(reason="ACCOUNT_READ_EXCEPTION", source=source_before)
    if type(account) is not L43AccountIdentity:
        return _result(reason="ACCOUNT_INVALID", source=source_before)
    if (
        expected_account_fingerprint is not None
        and account.fingerprint != expected_account_fingerprint
    ):
        return _result(
            reason="ACCOUNT_MISMATCH",
            source=source_before,
            account_fingerprint=account.fingerprint,
        )

    snapshots: list[_ReadSnapshot] = []
    canonical_by_id: dict[str, tuple[object, ...]] = {}
    for spec in _READS:
        try:
            snapshot = _read_logical_orders(
                read,
                account=account,
                spec=spec,
                canonical_by_id=canonical_by_id,
            )
        except _ProofFailure as failure:
            return _result(
                reason=failure.reason,
                source=source_before,
                account_fingerprint=account.fingerprint,
                logical_reads=tuple(item.evidence for item in snapshots),
            )
        snapshots.append(snapshot)

    try:
        source_after = source_reader()
    except Exception:
        return _result(
            reason="SOURCE_RECHECK_FAILED",
            source=source_before,
            account_fingerprint=account.fingerprint,
            logical_reads=tuple(item.evidence for item in snapshots),
        )
    if type(source_after) is not L43SourceIdentity:
        return _result(
            reason="SOURCE_IDENTITY_INVALID",
            source=source_before,
            account_fingerprint=account.fingerprint,
            logical_reads=tuple(item.evidence for item in snapshots),
        )
    if source_after != source_before:
        return _result(
            reason="SOURCE_CHANGED",
            source=source_before,
            account_fingerprint=account.fingerprint,
            logical_reads=tuple(item.evidence for item in snapshots),
        )

    all_before, true_read, false_read, all_after = snapshots
    if all_before.ids != all_after.ids:
        return _result(
            reason="ALL_UNIVERSE_CHANGED",
            source=source_before,
            account_fingerprint=account.fingerprint,
            logical_reads=tuple(item.evidence for item in snapshots),
        )
    if true_read.ids & false_read.ids:
        return _result(
            reason="PARTITION_OVERLAP",
            source=source_before,
            account_fingerprint=account.fingerprint,
            logical_reads=tuple(item.evidence for item in snapshots),
        )
    if true_read.ids | false_read.ids != all_before.ids:
        return _result(
            reason="PARTITION_UNION_MISMATCH",
            source=source_before,
            account_fingerprint=account.fingerprint,
            logical_reads=tuple(item.evidence for item in snapshots),
        )

    all_ids = tuple(sorted(all_before.ids))
    true_ids = tuple(sorted(true_read.ids))
    false_ids = tuple(sorted(false_read.ids))
    all_universe_digest = _digest(
        ("ARCH147_L43_B2_ALL_UNIVERSE_V1", account.fingerprint, _SYMBOL, all_ids)
    )
    true_partition_digest = _digest(
        ("ARCH147_L43_B2_TRUE_PARTITION_V1", account.fingerprint, _SYMBOL, true_ids)
    )
    false_partition_digest = _digest(
        ("ARCH147_L43_B2_FALSE_PARTITION_V1", account.fingerprint, _SYMBOL, false_ids)
    )
    canonical_material_digest = _digest(
        (
            "ARCH147_L43_B2_CANONICAL_ORDER_MATERIAL_V1",
            account.fingerprint,
            _SYMBOL,
            tuple(sorted(canonical_by_id.items())),
        )
    )
    return _result(
        reason="PARTITION_EQUALITY_PROVEN",
        status=AgentInitiatedRuntimePartitionProofStatus.PROVEN,
        source=source_before,
        account_fingerprint=account.fingerprint,
        logical_reads=tuple(item.evidence for item in snapshots),
        stable_all_universe_digest=all_universe_digest,
        true_partition_digest=true_partition_digest,
        false_partition_digest=false_partition_digest,
        canonical_order_material_digest=canonical_material_digest,
        partition_equality_proof="PROVEN",
    )


def _read_logical_orders(
    read: L43PreEffectReadBoundary,
    *,
    account: L43AccountIdentity,
    spec: _ReadSpec,
    canonical_by_id: dict[str, tuple[object, ...]],
) -> _ReadSnapshot:
    query_sha256 = _digest(
        (
            "ARCH147_L43_B2_ORDER_QUERY_V1",
            account.fingerprint,
            _SYMBOL,
            spec.agent_initiated,
        )
    )
    base_request: dict[str, object] = {
        "account_number": account.account_number,
        "symbol": _SYMBOL,
    }
    if spec.agent_initiated is not None:
        base_request["agent_initiated"] = spec.agent_initiated

    request = dict(base_request)
    seen_cursors: set[str] = set()
    ids: set[str] = set()
    page_count = 0
    row_count = 0
    for _ in range(_MAX_PAGES):
        page_count += 1
        try:
            page = read.get_equity_orders(request)
        except Exception:
            raise _ProofFailure(f"{spec.label}_READ_EXCEPTION") from None
        if type(page) is not L43ReadPage or not isinstance(page.rows, tuple):
            raise _ProofFailure(f"{spec.label}_PAGE_INVALID")
        cursor = page.next_cursor
        if cursor is not None and (
            type(cursor) is not str or not cursor or len(cursor) > _MAX_CURSOR_LENGTH
        ):
            raise _ProofFailure(f"{spec.label}_CURSOR_INVALID")
        if cursor is not None and cursor in seen_cursors:
            raise _ProofFailure(f"{spec.label}_CURSOR_REPEATED")
        if row_count + len(page.rows) > _MAX_ROWS:
            raise _ProofFailure(f"{spec.label}_ROW_BOUND_EXCEEDED")
        for row in page.rows:
            try:
                material = _canonical_order_material(row)
            except Exception:
                raise _ProofFailure(f"{spec.label}_FACT_INVALID") from None
            order_id = material[0]
            if order_id in ids:
                raise _ProofFailure(f"{spec.label}_DUPLICATE_ORDER_ID")
            if spec.agent_initiated is True and row.agent_initiated is not True:
                raise _ProofFailure("TRUE_PARTITION_ROW_INVALID")
            if spec.agent_initiated is False and row.agent_initiated is not False:
                raise _ProofFailure("FALSE_PARTITION_ROW_INVALID")
            ids.add(order_id)
            previous = canonical_by_id.get(order_id)
            if previous is not None and previous != material:
                raise _ProofFailure("ORDER_FACT_CONFLICT")
            canonical_by_id[order_id] = material
        row_count += len(page.rows)
        if cursor is None:
            evidence = AgentInitiatedLogicalReadEvidence(
                label=spec.label,
                agent_initiated=spec.agent_initiated,
                query_sha256=query_sha256,
                page_count=page_count,
                row_count=row_count,
                exhaustive=True,
            )
            return _ReadSnapshot(
                evidence=evidence,
                ids=frozenset(ids),
            )
        seen_cursors.add(cursor)
        request = {**base_request, "cursor": cursor}
    raise _ProofFailure(f"{spec.label}_PAGINATION_INCOMPLETE")


def _canonical_order_material(order: object) -> tuple[object, ...]:
    if type(order) is not L43OrderFact:
        raise ValueError("normalized order fact has an invalid type")
    if type(order.agent_initiated) is not bool:
        raise ValueError("normalized agent_initiated is not strict")
    if type(order.symbol) is not str or order.symbol != _SYMBOL:
        raise ValueError("normalized order is outside SPY scope")
    if type(order.order_id) is not str or _ORDER_ID.fullmatch(order.order_id) is None:
        raise ValueError("normalized order ID is invalid")
    if not isinstance(order.side, OrderSide):
        raise ValueError("normalized side is invalid")
    for value in (
        order.state,
        order.placed_agent,
        order.market_hours,
        order.time_in_force,
        order.order_type,
    ):
        if type(value) is not str or _TEXT.fullmatch(value) is None:
            raise ValueError("normalized order text is invalid")
    created_at = _timestamp(order.created_at)
    cumulative_quantity = _decimal(order.cumulative_quantity)
    average_price = (
        None if order.average_price is None else _decimal(order.average_price)
    )
    dollar_amount = order.dollar_based_amount
    if dollar_amount is not None:
        if type(dollar_amount) is not L43DollarAmountFact:
            raise ValueError("normalized dollar amount is invalid")
        currency_code = dollar_amount.currency_code
        if type(currency_code) is not str or _TEXT.fullmatch(currency_code) is None:
            raise ValueError("normalized currency is invalid")
        dollar_amount_material = _decimal(dollar_amount.amount)
        currency_material = currency_code
    else:
        dollar_amount_material = ""
        currency_material = ""
    executions = order.executions
    if type(executions) is not tuple:
        raise ValueError("normalized executions are invalid")
    execution_material = []
    execution_ids: set[str] = set()
    for execution in executions:
        if type(execution) is not L43ExecutionFact:
            raise ValueError("normalized execution is invalid")
        execution_id = execution.execution_id
        if (
            type(execution_id) is not str
            or _ORDER_ID.fullmatch(execution_id) is None
            or execution_id in execution_ids
        ):
            raise ValueError("normalized execution ID is invalid")
        execution_ids.add(execution_id)
        execution_material.append(
            (
                execution_id,
                _decimal(execution.quantity),
                _decimal(execution.price),
                _timestamp(execution.timestamp),
            )
        )
    return (
        order.order_id,
        order.symbol,
        order.side.value,
        order.state.casefold(),
        order.placed_agent,
        order.agent_initiated,
        created_at,
        cumulative_quantity,
        average_price,
        order.order_type.casefold(),
        order.market_hours.casefold(),
        order.time_in_force.casefold(),
        dollar_amount_material,
        currency_material,
        tuple(execution_material),
    )


def _decimal(value: object) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError("normalized decimal is invalid")
    if value == 0:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _timestamp(value: object) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("normalized timestamp is invalid")
    return value.astimezone(UTC).isoformat()


def _read_source_identity(repo_root: Path) -> L43SourceIdentity:
    if not isinstance(repo_root, Path):
        raise TypeError("source root must be a Path")
    return L43SourceIdentity(
        source_head=_git_text(repo_root, "HEAD"),
        source_tree=_git_text(repo_root, "HEAD^{tree}"),
    )


def _git_text(repo_root: Path, revision: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", revision],
        check=True,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    if not value:
        raise ValueError("git source identity is empty")
    return value


def _git_sha(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{40}\Z", value) is not None


def _digest(material: object) -> str:
    payload = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _result(
    *,
    reason: str,
    status: AgentInitiatedRuntimePartitionProofStatus = (
        AgentInitiatedRuntimePartitionProofStatus.NOT_PROVEN
    ),
    source: L43SourceIdentity | None = None,
    account_fingerprint: str | None = None,
    logical_reads: tuple[AgentInitiatedLogicalReadEvidence, ...] = (),
    stable_all_universe_digest: str | None = None,
    true_partition_digest: str | None = None,
    false_partition_digest: str | None = None,
    canonical_order_material_digest: str | None = None,
    partition_equality_proof: str = "NOT_PROVEN",
) -> AgentInitiatedRuntimePartitionProofResult:
    if _REASON.fullmatch(reason) is None:
        raise ValueError("proof result reason is not sanitized")
    source_head = None if source is None else source.source_head
    source_tree = None if source is None else source.source_tree
    payload = {
        "contract_version": _CONTRACT_VERSION,
        "status": status.value,
        "reason": reason,
        "source_head": source_head,
        "source_tree": source_tree,
        "account_fingerprint": account_fingerprint,
        "symbol": _SYMBOL,
        "logical_reads": [item.material() for item in logical_reads],
        "stable_all_universe_digest": stable_all_universe_digest,
        "true_partition_digest": true_partition_digest,
        "false_partition_digest": false_partition_digest,
        "canonical_order_material_digest": canonical_order_material_digest,
        "partition_equality_proof": partition_equality_proof,
        "production_order_scope_authority": "NOT_GRANTED",
    }
    evidence_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return AgentInitiatedRuntimePartitionProofResult(
        status=status,
        reason=reason,
        contract_version=_CONTRACT_VERSION,
        source_head=source_head,
        source_tree=source_tree,
        account_fingerprint=account_fingerprint,
        symbol=_SYMBOL,
        logical_reads=logical_reads,
        stable_all_universe_digest=stable_all_universe_digest,
        true_partition_digest=true_partition_digest,
        false_partition_digest=false_partition_digest,
        canonical_order_material_digest=canonical_order_material_digest,
        partition_equality_proof=partition_equality_proof,
        production_order_scope_authority="NOT_GRANTED",
        evidence_json=evidence_json,
        evidence_sha256=hashlib.sha256(evidence_json).hexdigest(),
    )


__all__ = [
    "AgentInitiatedLogicalReadEvidence",
    "AgentInitiatedRuntimePartitionProofResult",
    "AgentInitiatedRuntimePartitionProofStatus",
    "prove_agent_initiated_partition",
]
