"""Architecture-94 P3: immutable account anchor and complete read-only lineage.

Historical snapshots are exact report-bound replay dependencies, never P2
selection permits. Only A66/A63 perform deterministic historical replay. This
module has no coordinator, strategy, execution, provider, or mutation API.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import threading
import weakref
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Protocol
from uuid import UUID

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    verify_daily_snapshot,
)
from trading_bot.runtime.checkpointed_paper_cycle_report import (
    MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
    parse_checkpointed_paper_cycle_report,
)
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    VerifiedPriorCheckpoint,
    verified_prior_from_full_lineage,
)
from trading_bot.runtime.paper_account_checkpoint import (
    MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES,
)
from trading_bot.runtime.paper_account_lineage_verification import (
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactEvidence,
    PaperAccountLineageArtifactKind,
    PaperAccountLineageEvidence,
    PaperAccountLineageVerificationStatus,
    verify_paper_account_lineage,
)
from trading_bot.runtime.paper_account_successor_checkpoint import (
    MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
    PaperAccountSuccessorCheckpoint,
    parse_successor_paper_account_checkpoint,
)
from trading_bot.runtime.paper_operation import (
    MAX_PAPER_OPERATION_RECEIPT_BYTES,
    parse_paper_operation_receipt,
)
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    WindowsAuthorityError,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)
from trading_bot.runtime.windows_paper_account_mutex import (
    GlobalPaperAccountMutex,
    PaperAccountMutexAcquisition,
)
from trading_bot.runtime.windows_paper_account_security import (
    PRODUCTION_PAPER_ROOT,
    WindowsPaperAccountReadSession,
    enumerate_paper_directory,
)

MANUAL_PAPER_ACCOUNT_AUTHORITY_SCHEMA = "manual-paper-account-authority/v1"
MANUAL_PAPER_ACCOUNT_ANCHOR_FILENAME = "manual-paper-account-authority.json"
MAX_MANUAL_PAPER_ANCHOR_BYTES = 4096
MAX_MANUAL_PAPER_ROOT_ENTRIES = 1024
MAX_MANUAL_PAPER_INVENTORY_BYTES = 256 * 1024 * 1024
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_TRANSITION = re.compile(rf"paper-account-transition-({_UUID})")
_REPORT = re.compile(rf"checkpointed-paper-cycle-report-({_UUID})\.json")
_CHECKPOINT = re.compile(rf"paper-account-checkpoint-({_UUID})\.json")
_OPERATION = re.compile(rf"paper-operation-({_UUID})")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SID = re.compile(r"S-1-5-21-(?:[0-9]+-){3}[0-9]+")


class ManualPaperAccountAuthorityError(WindowsAuthorityError):
    """Stable bounded failure; no native error, path listing, or C1 exposure."""


def _uuid_text(value: object) -> UUID:
    if type(value) is not str or re.fullmatch(_UUID, value) is None:
        raise ManualPaperAccountAuthorityError("ANCHOR_UUID_INVALID")
    return UUID(value)


@dataclass(frozen=True, slots=True)
class ManualPaperAccountAnchor:
    paper_account_id: UUID
    machine_authority_id: str
    approved_trading_sid: str
    genesis_checkpoint_id: UUID
    genesis_sha256: str
    genesis_byte_length: int
    schema: str = MANUAL_PAPER_ACCOUNT_AUTHORITY_SCHEMA

    def __post_init__(self) -> None:
        if (
            self.schema != MANUAL_PAPER_ACCOUNT_AUTHORITY_SCHEMA
            or type(self.schema) is not str
            or type(self.paper_account_id) is not UUID
            or type(self.genesis_checkpoint_id) is not UUID
            or type(self.machine_authority_id) is not str
            or not 1 <= len(self.machine_authority_id) <= 128
            or not self.machine_authority_id.isascii()
            or any(ord(c) < 33 or ord(c) > 126 for c in self.machine_authority_id)
            or type(self.approved_trading_sid) is not str
            or len(self.approved_trading_sid) > 184
            or _SID.fullmatch(self.approved_trading_sid) is None
            or type(self.genesis_sha256) is not str
            or _SHA256.fullmatch(self.genesis_sha256) is None
            or type(self.genesis_byte_length) is not int
            or not 1 <= self.genesis_byte_length <= MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES
        ):
            raise ManualPaperAccountAuthorityError("ANCHOR_FIELDS_INVALID")


def serialize_manual_paper_account_anchor(anchor: ManualPaperAccountAnchor) -> bytes:
    """Pure canonical encoding only; this API never provisions an anchor."""
    if type(anchor) is not ManualPaperAccountAnchor:
        raise ManualPaperAccountAuthorityError("ANCHOR_TYPE_INVALID")
    anchor.__post_init__()
    return (
        json.dumps(
            {
                "schema": anchor.schema,
                "paper_account_id": str(anchor.paper_account_id),
                "machine_authority_id": anchor.machine_authority_id,
                "approved_trading_sid": anchor.approved_trading_sid,
                "genesis_checkpoint_id": str(anchor.genesis_checkpoint_id),
                "genesis_sha256": anchor.genesis_sha256,
                "genesis_byte_length": anchor.genesis_byte_length,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("utf-8")


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ManualPaperAccountAuthorityError("ANCHOR_DUPLICATE_FIELD")
        result[key] = value
    return result


def _reject_number(value: str) -> None:
    raise ManualPaperAccountAuthorityError("ANCHOR_NUMBER_INVALID")


def parse_manual_paper_account_anchor(payload: bytes) -> ManualPaperAccountAnchor:
    """Reject unknown/missing/duplicate fields and every noncanonical encoding."""
    try:
        if (
            type(payload) is not bytes
            or not 0 < len(payload) <= MAX_MANUAL_PAPER_ANCHOR_BYTES
        ):
            raise ManualPaperAccountAuthorityError("ANCHOR_LENGTH_INVALID")
        tree = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_object_pairs,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
        if type(tree) is not dict or set(tree) != {
            "schema",
            "paper_account_id",
            "machine_authority_id",
            "approved_trading_sid",
            "genesis_checkpoint_id",
            "genesis_sha256",
            "genesis_byte_length",
        }:
            raise ManualPaperAccountAuthorityError("ANCHOR_FIELDS_INVALID")
        tree["paper_account_id"] = _uuid_text(tree["paper_account_id"])
        tree["genesis_checkpoint_id"] = _uuid_text(tree["genesis_checkpoint_id"])
        anchor = ManualPaperAccountAnchor(**tree)
        if serialize_manual_paper_account_anchor(anchor) != payload:
            raise ManualPaperAccountAuthorityError("ANCHOR_NONCANONICAL")
        return anchor
    except ManualPaperAccountAuthorityError:
        raise
    except Exception:
        raise ManualPaperAccountAuthorityError("ANCHOR_PARSE_FAILED") from None


@dataclass(frozen=True, slots=True)
class ManualPaperAccountEvidence:
    """Audit facts only; a detached preflight is never lock admission."""

    anchor: ManualPaperAccountAnchor
    lineage: PaperAccountLineageEvidence
    verified_prior: VerifiedPriorCheckpoint
    finalized_transition_count: int
    historical_snapshot_dependencies: tuple[PaperAccountLineageArtifactEvidence, ...]

    @property
    def paper_account_id(self) -> UUID:
        return self.anchor.paper_account_id

    @property
    def machine_authority_id(self) -> str:
        return self.anchor.machine_authority_id

    @property
    def approved_trading_sid(self) -> str:
        return self.anchor.approved_trading_sid

    @property
    def terminal_checkpoint_id(self) -> UUID:
        return self.verified_prior.checkpoint_id

    @property
    def terminal_sequence(self) -> int:
        return self.verified_prior.sequence

    @property
    def terminal_sha256(self) -> str:
        return self.verified_prior.checkpoint_sha256

    @property
    def terminal_byte_length(self) -> int:
        return self.verified_prior.checkpoint_byte_length


class _ReadSession(Protocol):
    def __enter__(self) -> _ReadSession: ...
    def __exit__(self, *args: object) -> None: ...
    def inventory(self, path: str, role: str, limit: int) -> tuple[str, ...]: ...
    def read(self, path: str, role: str, limit: int) -> bytes: ...
    def finish(self) -> None: ...


class _Mutex(Protocol):
    acquisition: PaperAccountMutexAcquisition | None

    def __enter__(self) -> _Mutex: ...
    def __exit__(self, *args: object) -> None: ...


@dataclass(frozen=True, slots=True)
class _Binding:
    machine_id: str
    sid: str
    paper_root: str
    capture_root: str
    read_session: Callable[[], _ReadSession]
    mutex: Callable[[UUID], _Mutex]
    production: bool


_AUTHORITIES: weakref.WeakKeyDictionary[object, _Binding] = weakref.WeakKeyDictionary()
_SCOPES: weakref.WeakKeyDictionary[object, tuple[object, ...]] = (
    weakref.WeakKeyDictionary()
)
_REGISTRY_LOCK = threading.RLock()


class _Sealed:
    __slots__ = ("__weakref__",)

    def __copy__(self) -> object:
        raise TypeError("P3 authority cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        raise TypeError("P3 authority cannot be copied")

    def __reduce_ex__(self, protocol: int) -> object:
        raise TypeError("P3 authority cannot be serialized")


class LockedManualPaperAccount(_Sealed):
    """Opaque thread-bound scope, invalidated before releasing its account mutex."""

    __slots__ = ()

    def __init__(self) -> None:
        raise TypeError("locked P3 scopes are issued only after revalidation")

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("locked P3 scopes cannot be subclassed")

    @property
    def evidence(self) -> ManualPaperAccountEvidence:
        return _scope_record(self)[2]

    @property
    def acquisition(self) -> PaperAccountMutexAcquisition:
        return _scope_record(self)[3]


def _binding(authority: object) -> _Binding:
    with _REGISTRY_LOCK:
        if (
            type(authority)
            not in {
                WindowsManualPaperAccountAuthority,
                DisposableManualPaperAccountAuthorityForTest,
            }
            or authority not in _AUTHORITIES
        ):
            raise ManualPaperAccountAuthorityError("P3_AUTHORITY_PROVENANCE_INVALID")
        return _AUTHORITIES[authority]


def _scope_record(scope: LockedManualPaperAccount) -> tuple:
    with _REGISTRY_LOCK:
        if type(scope) is not LockedManualPaperAccount or scope not in _SCOPES:
            raise ManualPaperAccountAuthorityError("P3_LOCK_SCOPE_INACTIVE")
        record = _SCOPES[scope]
        authority, binding, _, _, thread_id = record
        if _binding(authority) is not binding or thread_id != threading.get_ident():
            raise ManualPaperAccountAuthorityError("P3_LOCK_SCOPE_INVALID")
        return record


def require_locked_manual_paper_account(
    scope: LockedManualPaperAccount, evidence: ManualPaperAccountEvidence
) -> LockedManualPaperAccount:
    """P4 consumption gate: exact live production scope and retained audit object."""
    record = _scope_record(scope)
    if not record[1].production or record[2] is not evidence:
        raise ManualPaperAccountAuthorityError("P3_LOCK_SCOPE_PROVENANCE_INVALID")
    return scope


class WindowsManualPaperAccountAuthority(_Sealed):
    """Attenuate genuine C1 to machine, Trading SID, and fixed read boundaries."""

    __slots__ = ()

    def __init__(self, authority: ValidatedProductionAuthority) -> None:
        with _REGISTRY_LOCK:
            if self in _AUTHORITIES:
                raise ManualPaperAccountAuthorityError(
                    "P3_AUTHORITY_ALREADY_INITIALIZED"
                )
            try:
                validated = require_validated_production_authority(authority)
                sid, machine = (
                    validated.approved_account_sid,
                    validated.machine_authority_id,
                )
            except Exception:
                raise ManualPaperAccountAuthorityError(
                    "P3_REQUIRES_GENUINE_C1"
                ) from None
            # Closures retain strings only, never the C1 capability.
            _AUTHORITIES[self] = _Binding(
                machine,
                sid,
                str(PRODUCTION_PAPER_ROOT),
                str(PRODUCTION_AUTHORITY_PATHS.capture_output),
                lambda: WindowsPaperAccountReadSession(sid),
                lambda account: GlobalPaperAccountMutex(account, trading_sid=sid),
                True,
            )

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("production P3 authority cannot be subclassed")

    def preflight(self) -> ManualPaperAccountEvidence:
        return _preflight(_binding(self))

    def locked_revalidate(
        self, *, expected: ManualPaperAccountEvidence | None = None
    ) -> AbstractContextManager[LockedManualPaperAccount]:
        """Hold the account lock around fresh proof; no execution is performed."""
        return _locked_revalidate(self, expected)


@contextmanager
def _locked_revalidate(
    authority: object, expected: ManualPaperAccountEvidence | None
) -> Iterator[LockedManualPaperAccount]:
    binding = _binding(authority)
    before = _preflight(binding)
    if expected is not None and (
        type(expected) is not ManualPaperAccountEvidence or expected != before
    ):
        raise ManualPaperAccountAuthorityError("P3_STALE_EXPECTED_ACCOUNT")
    with binding.mutex(before.paper_account_id) as lock:
        # Includes abandoned ownership; never reuse before-lock proof.
        fresh = _preflight(binding)
        if fresh.anchor != before.anchor or (
            expected is not None and fresh != expected
        ):
            raise ManualPaperAccountAuthorityError("P3_ACCOUNT_CHANGED_BEFORE_LOCK")
        if type(lock.acquisition) is not PaperAccountMutexAcquisition:
            raise ManualPaperAccountAuthorityError("P3_MUTEX_ACQUISITION_INVALID")
        scope = object.__new__(LockedManualPaperAccount)
        with _REGISTRY_LOCK:
            _SCOPES[scope] = (
                authority,
                binding,
                fresh,
                lock.acquisition,
                threading.get_ident(),
            )
        try:
            yield scope
        finally:
            with _REGISTRY_LOCK:
                _SCOPES.pop(scope, None)


def _artifact(
    kind: PaperAccountLineageArtifactKind, identity: UUID, payload: bytes
) -> PaperAccountLineageArtifact:
    return PaperAccountLineageArtifact(
        kind, identity, payload, hashlib.sha256(payload).hexdigest(), len(payload)
    )


def _artifact_evidence(
    artifact: PaperAccountLineageArtifact,
) -> PaperAccountLineageArtifactEvidence:
    return PaperAccountLineageArtifactEvidence(
        artifact.kind, artifact.artifact_id, artifact.sha256, artifact.byte_length
    )


@dataclass(frozen=True, slots=True)
class _Transition:
    successor: PaperAccountSuccessorCheckpoint
    checkpoint: PaperAccountLineageArtifact
    report: PaperAccountLineageArtifact
    snapshot: PaperAccountLineageArtifact


def _join(root: str, name: str, production: bool) -> str:
    return str((PureWindowsPath(root) if production else Path(root)) / name)


class _Inventory:
    def __init__(self, session: _ReadSession, binding: _Binding) -> None:
        self.session = session
        self.binding = binding
        self.bytes_read = 0

    def names(self, path: str, role: str, limit: int) -> tuple[str, ...]:
        names = self.session.inventory(path, role, limit)
        if type(names) is not tuple or len(names) > limit:
            raise ManualPaperAccountAuthorityError("P3_ENUMERATION_OVERFLOW")
        if any(
            type(name) is not str
            or not name
            or len(name) > 150
            or "/" in name
            or "\\" in name
            or ":" in name
            for name in names
        ):
            raise ManualPaperAccountAuthorityError("P3_UNSAFE_NAME")
        if len({name.casefold() for name in names}) != len(names):
            raise ManualPaperAccountAuthorityError("P3_CASEFOLD_COLLISION")
        if any(name.startswith(".") or name.endswith(".staging") for name in names):
            raise ManualPaperAccountAuthorityError("P3_STAGING_OR_UNKNOWN_STATE")
        return names

    def read(self, path: str, role: str, limit: int) -> bytes:
        remaining = MAX_MANUAL_PAPER_INVENTORY_BYTES - self.bytes_read
        if remaining <= 0:
            raise ManualPaperAccountAuthorityError("P3_BYTE_BUDGET_EXCEEDED")
        payload = self.session.read(path, role, min(limit, remaining))
        if type(payload) is not bytes or not 0 < len(payload) <= min(limit, remaining):
            raise ManualPaperAccountAuthorityError("P3_ARTIFACT_LENGTH_INVALID")
        self.bytes_read += len(payload)
        return payload

    def join(self, root: str, name: str) -> str:
        return _join(root, name, self.binding.production)

    def transition(self, root: str, name: str, application_id: UUID) -> _Transition:
        path = self.join(root, name)
        names = self.names(path, "output-directory", 2)
        report_names = [name for name in names if _REPORT.fullmatch(name)]
        checkpoint_names = [name for name in names if _CHECKPOINT.fullmatch(name)]
        if len(names) != 2 or len(report_names) != 1 or len(checkpoint_names) != 1:
            raise ManualPaperAccountAuthorityError("P3_TRANSITION_LAYOUT_INVALID")
        report_bytes = self.read(
            self.join(path, report_names[0]),
            "output-file",
            MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
        )
        report = parse_checkpointed_paper_cycle_report(report_bytes)
        if (
            report_names[0]
            != f"checkpointed-paper-cycle-report-{report.evidence.cycle_result_id}.json"
            or report.evidence.application_id != application_id
        ):
            raise ManualPaperAccountAuthorityError("P3_REPORT_LAYOUT_MISMATCH")
        ref = report.evidence.request.snapshot_reference
        snapshot_bytes = self.read(
            self.join(
                self.binding.capture_root,
                f"daily-market-data-snapshot-{ref.snapshot_id}.json",
            ),
            "snapshot",
            MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
        )
        if (
            len(snapshot_bytes) != ref.artifact_byte_length
            or hashlib.sha256(snapshot_bytes).hexdigest() != ref.artifact_sha256
        ):
            raise ManualPaperAccountAuthorityError("P3_HISTORICAL_SNAPSHOT_MISMATCH")
        verified = verify_daily_snapshot(
            snapshot_bytes,
            _calendar(),
            expected_sha256=ref.artifact_sha256,
            expected_byte_length=ref.artifact_byte_length,
        )
        if (
            not verified.passed
            or verified.diagnostics
            or verified.snapshot is None
            or verified.snapshot.snapshot_id != ref.snapshot_id
        ):
            raise ManualPaperAccountAuthorityError("P3_HISTORICAL_SNAPSHOT_INVALID")
        checkpoint_bytes = self.read(
            self.join(path, checkpoint_names[0]),
            "output-file",
            MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
        )
        successor = parse_successor_paper_account_checkpoint(checkpoint_bytes)
        if (
            checkpoint_names[0]
            != f"paper-account-checkpoint-{successor.checkpoint_id}.json"
            or successor.application_id != application_id
            or successor.producing_cycle.report_id != report.report_id
        ):
            raise ManualPaperAccountAuthorityError("P3_SUCCESSOR_LAYOUT_MISMATCH")
        return _Transition(
            successor,
            _artifact(
                PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
                successor.checkpoint_id,
                checkpoint_bytes,
            ),
            _artifact(
                PaperAccountLineageArtifactKind.CYCLE_REPORT,
                report.report_id,
                report_bytes,
            ),
            _artifact(
                PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
                ref.snapshot_id,
                snapshot_bytes,
            ),
        )

    def operations(self, root: str) -> None:
        """Validate the known audit namespace without granting receipt authority."""
        path = self.join(root, "paper-operations")
        names = self.names(path, "output-directory", MAX_MANUAL_PAPER_ROOT_ENTRIES)
        for name in names:
            match = _OPERATION.fullmatch(name)
            if match is None:
                raise ManualPaperAccountAuthorityError("P3_OPERATION_LAYOUT_INVALID")
            directory = self.join(path, name)
            expected = f"paper-operation-receipt-{match.group(1)}.json"
            if self.names(directory, "output-directory", 1) != (expected,):
                raise ManualPaperAccountAuthorityError("P3_RECEIPT_LAYOUT_INVALID")
            receipt = parse_paper_operation_receipt(
                self.read(
                    self.join(directory, expected),
                    "output-file",
                    MAX_PAPER_OPERATION_RECEIPT_BYTES,
                )
            )
            operation_id = UUID(match.group(1))
            if (
                receipt.receipt_id != operation_id
                or receipt.intent.operation_id != operation_id
            ):
                raise ManualPaperAccountAuthorityError("P3_RECEIPT_ID_MISMATCH")
            # Canonical structure only: receipts neither enter the account graph
            # nor establish caller-key/operation authority. Exact receipt replay
            # and its dependencies remain the P4/existing A67 inspection boundary.


def _calendar() -> BoundMarketCalendar:
    return BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())


def _ordered_chain(
    genesis_id: UUID, transitions: tuple[_Transition, ...]
) -> tuple[_Transition, ...]:
    children: dict[UUID, _Transition] = {}
    checkpoints = {genesis_id}
    reports: set[UUID] = set()
    applications: set[UUID] = set()
    for edge in transitions:
        model = edge.successor
        parent = model.prior_checkpoint.checkpoint_id
        if (
            parent in children
            or model.checkpoint_id in checkpoints
            or edge.report.artifact_id in reports
            or model.application_id in applications
        ):
            raise ManualPaperAccountAuthorityError("P3_FORK_OR_REUSE")
        children[parent] = edge
        checkpoints.add(model.checkpoint_id)
        reports.add(edge.report.artifact_id)
        applications.add(model.application_id)
    ordered = []
    visited = {genesis_id}
    current = genesis_id
    while current in children:
        edge = children[current]
        current = edge.successor.checkpoint_id
        if current in visited:
            raise ManualPaperAccountAuthorityError("P3_GRAPH_CYCLE")
        visited.add(current)
        ordered.append(edge)
    if len(ordered) != len(transitions):
        raise ManualPaperAccountAuthorityError("P3_DISCONNECTED_OR_UNUSED_TRANSITION")
    return tuple(ordered)


def _preflight(binding: _Binding) -> ManualPaperAccountEvidence:
    try:
        with binding.read_session() as session:
            inventory = _Inventory(session, binding)
            root = binding.paper_root
            names = inventory.names(root, "root", MAX_MANUAL_PAPER_ROOT_ENTRIES)
            if MANUAL_PAPER_ACCOUNT_ANCHOR_FILENAME not in names:
                raise ManualPaperAccountAuthorityError("P3_ANCHOR_MISSING")
            anchor = parse_manual_paper_account_anchor(
                inventory.read(
                    inventory.join(root, MANUAL_PAPER_ACCOUNT_ANCHOR_FILENAME),
                    "anchor",
                    MAX_MANUAL_PAPER_ANCHOR_BYTES,
                )
            )
            if (
                anchor.machine_authority_id != binding.machine_id
                or anchor.approved_trading_sid != binding.sid
            ):
                raise ManualPaperAccountAuthorityError("P3_ANCHOR_AUTHORITY_MISMATCH")
            genesis_directory = f"paper-account-genesis-{anchor.genesis_checkpoint_id}"
            if genesis_directory not in names:
                raise ManualPaperAccountAuthorityError("P3_ANCHORED_GENESIS_MISSING")
            path = inventory.join(root, genesis_directory)
            filename = f"paper-account-checkpoint-{anchor.genesis_checkpoint_id}.json"
            if inventory.names(path, "genesis-directory", 1) != (filename,):
                raise ManualPaperAccountAuthorityError("P3_GENESIS_LAYOUT_INVALID")
            genesis_bytes = inventory.read(
                inventory.join(path, filename),
                "genesis-file",
                MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES,
            )
            genesis = _artifact(
                PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
                anchor.genesis_checkpoint_id,
                genesis_bytes,
            )
            if (genesis.sha256, genesis.byte_length) != (
                anchor.genesis_sha256,
                anchor.genesis_byte_length,
            ):
                raise ManualPaperAccountAuthorityError("P3_GENESIS_ANCHOR_MISMATCH")
            transitions = []
            for name in names:
                if name in {MANUAL_PAPER_ACCOUNT_ANCHOR_FILENAME, genesis_directory}:
                    continue
                if name == "paper-operations":
                    inventory.operations(root)
                    continue
                match = _TRANSITION.fullmatch(name)
                if match is None:
                    raise ManualPaperAccountAuthorityError("P3_UNKNOWN_ROOT_STATE")
                transitions.append(
                    inventory.transition(root, name, UUID(match.group(1)))
                )
            chain = _ordered_chain(anchor.genesis_checkpoint_id, tuple(transitions))
            terminal = (
                chain[-1].checkpoint.artifact_id
                if chain
                else anchor.genesis_checkpoint_id
            )
            successors = tuple(edge.checkpoint for edge in chain)
            reports = tuple(edge.report for edge in chain)
            snapshots = tuple(edge.snapshot for edge in chain)
            verification = verify_paper_account_lineage(
                genesis, terminal, successors, reports, snapshots, _calendar()
            )
            evidence = verification.evidence
            if (
                verification.status is not PaperAccountLineageVerificationStatus.PASS
                or verification.diagnostics
                or evidence is None
            ):
                raise ManualPaperAccountAuthorityError("P3_FULL_LINEAGE_FAILED")
            if (
                evidence.edge_count != len(transitions)
                or evidence.genesis_checkpoint_id != anchor.genesis_checkpoint_id
                or evidence.terminal_checkpoint_id != terminal
                or evidence.checkpoint_ids
                != (
                    anchor.genesis_checkpoint_id,
                    *(edge.checkpoint.artifact_id for edge in chain),
                )
                or evidence.application_ids
                != tuple(edge.successor.application_id for edge in chain)
                or evidence.cycle_result_ids
                != tuple(
                    edge.successor.producing_cycle.cycle_result_id for edge in chain
                )
                or evidence.snapshot_ids
                != tuple(item.artifact_id for item in snapshots)
                or evidence.checkpoint_artifacts
                != tuple(_artifact_evidence(item) for item in (genesis, *successors))
                or evidence.report_artifacts
                != tuple(_artifact_evidence(item) for item in reports)
                or evidence.snapshot_artifacts
                != tuple(_artifact_evidence(item) for item in snapshots)
            ):
                raise ManualPaperAccountAuthorityError("P3_INVENTORY_LINEAGE_MISMATCH")
            prior = verified_prior_from_full_lineage(verification)
            if prior.checkpoint_id != terminal or prior.sequence != len(transitions):
                raise ManualPaperAccountAuthorityError("P3_TERMINAL_MISMATCH")
            session.finish()
            return ManualPaperAccountEvidence(
                anchor, evidence, prior, len(transitions), evidence.snapshot_artifacts
            )
    except ManualPaperAccountAuthorityError:
        raise
    except Exception:
        raise ManualPaperAccountAuthorityError(
            "P3_UNSAFE_OR_UNVERIFIABLE_STATE"
        ) from None


class DisposablePaperAccountReadSessionForTest:
    """Explicit portable test seam; not a production Windows security claim."""

    def __init__(self) -> None:
        self._facts: dict[str, tuple[int, ...]] = {}
        self._listings: dict[str, tuple[frozenset[str], int]] = {}

    def __enter__(self) -> DisposablePaperAccountReadSessionForTest:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    @staticmethod
    def _inspect(path: str, directory: bool) -> tuple[int, ...]:
        selected = Path(path)
        for parent in (*reversed(selected.parents), selected):
            info = parent.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & (
                0x400 | 0x40
            ):
                raise ManualPaperAccountAuthorityError("P3_UNSAFE_TEST_OBJECT")
            if parent != selected and not stat.S_ISDIR(info.st_mode):
                raise ManualPaperAccountAuthorityError("P3_UNSAFE_TEST_PARENT")
        info = selected.lstat()
        if not (
            stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        ):
            raise ManualPaperAccountAuthorityError("P3_UNSAFE_TEST_OBJECT")
        return (
            (info.st_dev, info.st_ino)
            if directory
            else (
                info.st_dev,
                info.st_ino,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
            )
        )

    def inventory(self, path: str, role: str, limit: int) -> tuple[str, ...]:
        self._facts[path] = self._inspect(path, True)
        names = enumerate_paper_directory(path, limit)
        self._listings[path] = (frozenset(names), limit)
        return names

    def read(self, path: str, role: str, limit: int) -> bytes:
        before = self._inspect(path, False)
        with open(path, "rb") as source:
            opened = os.fstat(source.fileno())
            if (opened.st_dev, opened.st_ino) != before[:2]:
                raise ManualPaperAccountAuthorityError("P3_TEST_OBJECT_SUBSTITUTED")
            payload = source.read(limit + 1)
        if self._inspect(path, False) != before:
            raise ManualPaperAccountAuthorityError("P3_TEST_OBJECT_CHANGED")
        self._facts[path] = before
        return payload

    def finish(self) -> None:
        for path, facts in self._facts.items():
            if self._inspect(path, path in self._listings) != facts:
                raise ManualPaperAccountAuthorityError("P3_TEST_OBJECT_CHANGED")
        for path, (names, limit) in self._listings.items():
            if frozenset(enumerate_paper_directory(path, limit)) != names:
                raise ManualPaperAccountAuthorityError("P3_TEST_INVENTORY_CHANGED")


class DisposableManualPaperAccountAuthorityForTest(_Sealed):
    """Explicit disposable root and read/mutex seams; cannot issue production proof."""

    __slots__ = ()

    def __init__(
        self,
        *,
        paper_root: Path,
        capture_root: Path,
        machine_authority_id: str,
        approved_trading_sid: str,
        mutex_factory: Callable[[UUID], _Mutex],
        read_session_factory: Callable[
            [], _ReadSession
        ] = DisposablePaperAccountReadSessionForTest,
    ) -> None:
        for root in (paper_root, capture_root):
            if (
                not isinstance(root, Path)
                or not root.is_absolute()
                or PureWindowsPath(str(root.resolve())).is_relative_to(
                    PRODUCTION_AUTHORITY_PATHS.root.parent
                )
            ):
                raise ManualPaperAccountAuthorityError("P3_TEST_ROOT_NOT_DISPOSABLE")
        with _REGISTRY_LOCK:
            if self in _AUTHORITIES:
                raise ManualPaperAccountAuthorityError(
                    "P3_AUTHORITY_ALREADY_INITIALIZED"
                )
            _AUTHORITIES[self] = _Binding(
                machine_authority_id,
                approved_trading_sid,
                str(paper_root),
                str(capture_root),
                read_session_factory,
                mutex_factory,
                False,
            )

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("disposable P3 authority cannot be subclassed")

    def preflight(self) -> ManualPaperAccountEvidence:
        return _preflight(_binding(self))

    def locked_revalidate(
        self, *, expected: ManualPaperAccountEvidence | None = None
    ) -> AbstractContextManager[LockedManualPaperAccount]:
        return _locked_revalidate(self, expected)
