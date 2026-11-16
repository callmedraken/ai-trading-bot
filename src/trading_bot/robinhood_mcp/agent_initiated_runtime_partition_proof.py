"""Closed, provider-independent proof of the L43 B2 agent partition.

The proof consumes the narrow normalized B2 read boundary only. It deliberately
does not construct a provider, discover a tool, read credentials, or grant
the production order-scope authority owned by the L43 composition.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from trading_bot.live_prototype.l43_production_owner import L43SourceIdentity
from trading_bot.live_prototype.l43_provider_contracts import (
    L43AccountIdentity,
)

B2_PROOF_CONTRACT_VERSION = "ARCH147_L43_B2_AGENT_INITIATED_RUNTIME_PARTITION/v2"
_SYMBOL = "SPY"
_MAX_PAGES = 40
_MAX_ROWS = 10_000
_MAX_CURSOR_LENGTH = 4096
_ORDER_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REASON = re.compile(r"[A-Z][A-Z0-9_]{0,127}\Z")


class AgentInitiatedRuntimePartitionProofStatus(StrEnum):
    PROVEN = "PROVEN"
    NOT_PROVEN = "NOT_PROVEN"


class B2FailureReason(StrEnum):
    SOURCE_READER_INVALID = "SOURCE_READER_INVALID"
    SOURCE_IDENTITY_INVALID = "SOURCE_IDENTITY_INVALID"
    ACCOUNT_EXPECTATION_INVALID = "ACCOUNT_EXPECTATION_INVALID"
    READ_BOUNDARY_INVALID = "READ_BOUNDARY_INVALID"
    SOURCE_READ_FAILED = "SOURCE_READ_FAILED"
    SOURCE_MISMATCH = "SOURCE_MISMATCH"
    ACCOUNT_READ_EXCEPTION = "ACCOUNT_READ_EXCEPTION"
    ACCOUNT_INVALID = "ACCOUNT_INVALID"
    ACCOUNT_MISMATCH = "ACCOUNT_MISMATCH"
    SOURCE_RECHECK_FAILED = "SOURCE_RECHECK_FAILED"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    TRANSPORT_TOOL_DISPATCH_FAILURE = "TRANSPORT_TOOL_DISPATCH_FAILURE"
    PROVIDER_RESULT_ENVELOPE_FAILURE = "PROVIDER_RESULT_ENVELOPE_FAILURE"
    PAGINATION_ENVELOPE_CURSOR_FAILURE = "PAGINATION_ENVELOPE_CURSOR_FAILURE"
    ORDER_COLLECTION_SHAPE_FAILURE = "ORDER_COLLECTION_SHAPE_FAILURE"
    ORDER_ROW_SHAPE_FAILURE = "ORDER_ROW_SHAPE_FAILURE"
    REQUIRED_B2_FIELD_FAILURE = "REQUIRED_B2_FIELD_FAILURE"
    AGENT_INITIATED_STRICT_BOOL_FAILURE = "AGENT_INITIATED_STRICT_BOOL_FAILURE"
    CANONICAL_ROW_SERIALIZATION_FAILURE = "CANONICAL_ROW_SERIALIZATION_FAILURE"
    DUPLICATE_ORDER_IDENTITY = "DUPLICATE_ORDER_IDENTITY"
    SAME_ID_MATERIAL_CONFLICT = "SAME_ID_MATERIAL_CONFLICT"
    PAGE_INVALID = "PAGE_INVALID"
    ROW_BOUND_EXCEEDED = "ROW_BOUND_EXCEEDED"
    CURSOR_REPEATED = "CURSOR_REPEATED"
    PAGINATION_INCOMPLETE = "PAGINATION_INCOMPLETE"
    TRUE_PARTITION_ROW_INVALID = "TRUE_PARTITION_ROW_INVALID"
    FALSE_PARTITION_ROW_INVALID = "FALSE_PARTITION_ROW_INVALID"
    ALL_UNIVERSE_CHANGED = "ALL_UNIVERSE_CHANGED"
    PARTITION_OVERLAP = "PARTITION_OVERLAP"
    PARTITION_UNION_MISMATCH = "PARTITION_UNION_MISMATCH"
    PARTITION_EQUALITY_PROVEN = "PARTITION_EQUALITY_PROVEN"


class B2CompatibilityFailure(RuntimeError):
    """Closed B2 failure; only the reason enum may cross the proof boundary."""

    def __init__(self, reason: B2FailureReason) -> None:
        if not isinstance(reason, B2FailureReason):
            raise TypeError("B2 failure reason must use the closed enum")
        self.reason = reason
        super().__init__(reason.value)


@dataclass(frozen=True, slots=True)
class B2OrderFact:
    """Minimal normalized B2 order fact with complete-row mutation binding."""

    order_id: str
    symbol: str
    agent_initiated: bool
    row_material_sha256: str


@dataclass(frozen=True, slots=True)
class B2OrderReadPage:
    rows: tuple[B2OrderFact, ...]
    next_cursor: str | None


class B2PreEffectReadBoundary(Protocol):
    def get_accounts(self) -> L43AccountIdentity: ...

    def get_equity_orders(self, arguments: Mapping[str, object]) -> B2OrderReadPage: ...


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
        if type(self.reason) is not str or self.reason not in _B2_REASON_VALUES:
            raise ValueError("proof reason is not in the closed taxonomy")
        if self.contract_version != B2_PROOF_CONTRACT_VERSION:
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
    def __init__(self, reason: B2FailureReason) -> None:
        if not isinstance(reason, B2FailureReason):
            raise TypeError("internal proof reason must use the closed enum")
        self.reason = reason


_B2_REASON_VALUES = frozenset(reason.value for reason in B2FailureReason)


def is_b2_failure_reason(value: object) -> bool:
    return type(value) is str and value in _B2_REASON_VALUES


_READS = (
    _ReadSpec("ALL_BEFORE", None),
    _ReadSpec("TRUE", True),
    _ReadSpec("FALSE", False),
    _ReadSpec("ALL_AFTER", None),
)


def prove_agent_initiated_partition(
    read: B2PreEffectReadBoundary,
    *,
    repo_root: Path | None = None,
    source_reader: Callable[[], L43SourceIdentity] | None = None,
    expected_source: L43SourceIdentity | None = None,
    expected_account_fingerprint: str | None = None,
) -> AgentInitiatedRuntimePartitionProofResult:
    """Prove the exact four-read SPY partition using normalized B2 facts.

    The function is intentionally an injected seam.  It returns a closed
    result for every invalid, incomplete, conflicting, or exceptional input;
    provider exceptions and raw payloads never enter the result evidence.
    """

    if source_reader is None:
        if not isinstance(repo_root, Path):
            return _result(reason=B2FailureReason.SOURCE_READER_INVALID)

        def repo_source_reader() -> L43SourceIdentity:
            return _read_source_identity(repo_root)

        source_reader = repo_source_reader
    if not callable(source_reader):
        return _result(reason=B2FailureReason.SOURCE_READER_INVALID)
    if expected_source is not None and type(expected_source) is not L43SourceIdentity:
        return _result(reason=B2FailureReason.SOURCE_IDENTITY_INVALID)
    if expected_account_fingerprint is not None and not _SHA256.fullmatch(
        expected_account_fingerprint
    ):
        return _result(reason=B2FailureReason.ACCOUNT_EXPECTATION_INVALID)
    if not all(
        callable(getattr(read, name, None))
        for name in ("get_accounts", "get_equity_orders")
    ):
        return _result(reason=B2FailureReason.READ_BOUNDARY_INVALID)

    try:
        source_before = source_reader()
    except Exception:
        return _result(reason=B2FailureReason.SOURCE_READ_FAILED)
    if type(source_before) is not L43SourceIdentity:
        return _result(reason=B2FailureReason.SOURCE_IDENTITY_INVALID)
    if expected_source is not None and source_before != expected_source:
        return _result(
            reason=B2FailureReason.SOURCE_MISMATCH,
            source=source_before,
        )

    try:
        account = read.get_accounts()
    except B2CompatibilityFailure as failure:
        return _result(reason=failure.reason, source=source_before)
    except Exception:
        return _result(
            reason=B2FailureReason.ACCOUNT_READ_EXCEPTION, source=source_before
        )
    if type(account) is not L43AccountIdentity:
        return _result(reason=B2FailureReason.ACCOUNT_INVALID, source=source_before)
    if (
        expected_account_fingerprint is not None
        and account.fingerprint != expected_account_fingerprint
    ):
        return _result(
            reason=B2FailureReason.ACCOUNT_MISMATCH,
            source=source_before,
            account_fingerprint=account.fingerprint,
        )

    snapshots: list[_ReadSnapshot] = []
    canonical_by_id: dict[str, tuple[str, str, bool, str]] = {}
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
            reason=B2FailureReason.SOURCE_RECHECK_FAILED,
            source=source_before,
            account_fingerprint=account.fingerprint,
            logical_reads=tuple(item.evidence for item in snapshots),
        )
    if type(source_after) is not L43SourceIdentity:
        return _result(
            reason=B2FailureReason.SOURCE_IDENTITY_INVALID,
            source=source_before,
            account_fingerprint=account.fingerprint,
            logical_reads=tuple(item.evidence for item in snapshots),
        )
    if source_after != source_before:
        return _result(
            reason=B2FailureReason.SOURCE_CHANGED,
            source=source_before,
            account_fingerprint=account.fingerprint,
            logical_reads=tuple(item.evidence for item in snapshots),
        )

    all_before, true_read, false_read, all_after = snapshots
    if all_before.ids != all_after.ids:
        return _result(
            reason=B2FailureReason.ALL_UNIVERSE_CHANGED,
            source=source_before,
            account_fingerprint=account.fingerprint,
            logical_reads=tuple(item.evidence for item in snapshots),
        )
    if true_read.ids & false_read.ids:
        return _result(
            reason=B2FailureReason.PARTITION_OVERLAP,
            source=source_before,
            account_fingerprint=account.fingerprint,
            logical_reads=tuple(item.evidence for item in snapshots),
        )
    if true_read.ids | false_read.ids != all_before.ids:
        return _result(
            reason=B2FailureReason.PARTITION_UNION_MISMATCH,
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
            "ARCH147_L43_B2_CANONICAL_ORDER_MATERIAL_V2",
            account.fingerprint,
            _SYMBOL,
            tuple(sorted(canonical_by_id.items())),
        )
    )
    return _result(
        reason=B2FailureReason.PARTITION_EQUALITY_PROVEN,
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
    read: B2PreEffectReadBoundary,
    *,
    account: L43AccountIdentity,
    spec: _ReadSpec,
    canonical_by_id: dict[str, tuple[str, str, bool, str]],
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
        except B2CompatibilityFailure as failure:
            raise _ProofFailure(failure.reason) from None
        except Exception:
            raise _ProofFailure(
                B2FailureReason.TRANSPORT_TOOL_DISPATCH_FAILURE
            ) from None
        if type(page) is not B2OrderReadPage or type(page.rows) is not tuple:
            raise _ProofFailure(B2FailureReason.PAGE_INVALID)
        cursor = page.next_cursor
        if cursor is not None and (
            type(cursor) is not str or not cursor or len(cursor) > _MAX_CURSOR_LENGTH
        ):
            raise _ProofFailure(B2FailureReason.PAGINATION_ENVELOPE_CURSOR_FAILURE)
        if cursor is not None and cursor in seen_cursors:
            raise _ProofFailure(B2FailureReason.CURSOR_REPEATED)
        if row_count + len(page.rows) > _MAX_ROWS:
            raise _ProofFailure(B2FailureReason.ROW_BOUND_EXCEEDED)
        for row in page.rows:
            try:
                material = _canonical_b2_order_material(row)
            except B2CompatibilityFailure as failure:
                raise _ProofFailure(failure.reason) from None
            except Exception:
                raise _ProofFailure(B2FailureReason.ORDER_ROW_SHAPE_FAILURE) from None
            order_id = material[0]
            if order_id in ids:
                raise _ProofFailure(B2FailureReason.DUPLICATE_ORDER_IDENTITY)
            if spec.agent_initiated is True and row.agent_initiated is not True:
                raise _ProofFailure(B2FailureReason.TRUE_PARTITION_ROW_INVALID)
            if spec.agent_initiated is False and row.agent_initiated is not False:
                raise _ProofFailure(B2FailureReason.FALSE_PARTITION_ROW_INVALID)
            ids.add(order_id)
            previous = canonical_by_id.get(order_id)
            if previous is not None and previous != material:
                raise _ProofFailure(B2FailureReason.SAME_ID_MATERIAL_CONFLICT)
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
    raise _ProofFailure(B2FailureReason.PAGINATION_INCOMPLETE)


def validate_b2_order_fields(
    order_id: object, symbol: object, agent_initiated: object
) -> tuple[str, str, bool]:
    if type(order_id) is not str or _ORDER_ID.fullmatch(order_id) is None:
        raise B2CompatibilityFailure(B2FailureReason.REQUIRED_B2_FIELD_FAILURE)
    if type(symbol) is not str or symbol != _SYMBOL:
        raise B2CompatibilityFailure(B2FailureReason.REQUIRED_B2_FIELD_FAILURE)
    if type(agent_initiated) is not bool:
        raise B2CompatibilityFailure(
            B2FailureReason.AGENT_INITIATED_STRICT_BOOL_FAILURE
        )
    return order_id, symbol, agent_initiated


def _canonical_b2_order_material(order: object) -> tuple[str, str, bool, str]:
    if type(order) is not B2OrderFact:
        raise B2CompatibilityFailure(B2FailureReason.ORDER_ROW_SHAPE_FAILURE)
    order_id, symbol, agent_initiated = validate_b2_order_fields(
        order.order_id, order.symbol, order.agent_initiated
    )
    if type(order.row_material_sha256) is not str or not _SHA256.fullmatch(
        order.row_material_sha256
    ):
        raise B2CompatibilityFailure(
            B2FailureReason.CANONICAL_ROW_SERIALIZATION_FAILURE
        )
    return (
        order_id,
        symbol,
        agent_initiated,
        order.row_material_sha256,
    )


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
    reason: B2FailureReason,
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
    if not isinstance(reason, B2FailureReason):
        raise TypeError("proof result reason must use the closed taxonomy")
    reason_value = reason.value
    source_head = None if source is None else source.source_head
    source_tree = None if source is None else source.source_tree
    payload = {
        "contract_version": B2_PROOF_CONTRACT_VERSION,
        "status": status.value,
        "reason": reason_value,
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
        reason=reason_value,
        contract_version=B2_PROOF_CONTRACT_VERSION,
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
    "B2CompatibilityFailure",
    "B2FailureReason",
    "B2OrderFact",
    "B2OrderReadPage",
    "B2PreEffectReadBoundary",
    "B2_PROOF_CONTRACT_VERSION",
    "AgentInitiatedLogicalReadEvidence",
    "AgentInitiatedRuntimePartitionProofResult",
    "AgentInitiatedRuntimePartitionProofStatus",
    "prove_agent_initiated_partition",
    "is_b2_failure_reason",
    "validate_b2_order_fields",
]
