"""C3 production composition with focused C3-C2/C3-C3B test seams."""

from __future__ import annotations

import hashlib
import json
import threading
import weakref
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import PureWindowsPath
from uuid import UUID

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.runtime.windows_authority import (
    WindowsAuthorityError,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)
from trading_bot.runtime.windows_effectful_capture import (
    BoundProductionCapturePlan,
    ProductionCapturePlan,
    ProductionCaptureRequest,
    ProductionProviderLaunchPlan,
    bind_production_capture_plan,
    build_production_provider_launch_plan,
    prepare_production_capture_plan,
)
from trading_bot.runtime.windows_effectful_capture_native import (
    PRODUCTION_C3_CHILD_BASE_ARGUMENTS,
    PRODUCTION_C3_PYTHON_EXECUTABLE,
    C3ParentCleanupStatus,
    C3ProcessOutcomeStatus,
    C3ResultTransportStatus,
    CtypesWindowsEffectfulCaptureNativeApi,
    NativeFileIdentity,
    NativeOpenedArtifact,
    SuspendedCaptureChild,
    WindowsEffectfulCaptureNativeApi,
    WindowsEffectfulCaptureProcessNotCreatedError,
    create_production_suspended_capture_child,
    create_suspended_capture_child_for_test,
    deliver_canonical_child_request,
    observe_resumed_capture_child,
    resume_suspended_capture_child,
)
from trading_bot.runtime.windows_effectful_capture_protocol import (
    ChildCleanupStatus,
    ChildResultClassification,
    IsolatedCaptureChildRequest,
    IsolatedCaptureChildResult,
    ProviderAttemptFenceState,
    VerifiedCapturedSnapshot,
    WindowsEffectfulCaptureProtocolError,
    _consume_production_verified_captured_snapshot,
    _issue_production_verified_captured_snapshot,
    _validate_production_verified_captured_snapshot,
    build_isolated_capture_child_request,
    parse_isolated_capture_child_request,
    parse_isolated_capture_child_result,
    serialize_isolated_capture_child_request,
    serialize_isolated_capture_child_result,
)
from trading_bot.runtime.windows_transactional_authority import (
    _PRODUCTION_C3_COMPOSITION_BINDING_CONSTRUCTOR,
    ConstructedProvider,
    ProcessCreationFailure,
    ProcessCreationReceipt,
    ProcessIntent,
    ProviderConstructionPermit,
    ResumeIntent,
    ResumeReceipt,
    WindowsTransactionalAuthority,
    _create_production_c3_composition_binding_issuer,
    _discard_unconsumed_production_c3_composition_bindings,
    _issue_production_c3_composition_binding,
)


class WindowsEffectfulCaptureCompositionError(WindowsAuthorityError):
    """C1/C2/C3 production composition is inconsistent or already closed."""


@dataclass(frozen=True, slots=True)
class C3C2NativeLaunchConfigurationForTest:
    """Explicit injected native launch material for the C3-C2 test seam only."""

    application_name: str
    arguments: tuple[str, ...]
    current_directory: str
    controlled_temp_directory: str
    storage_root: str
    parent_environment: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class C3C2ResumedCaptureForTest:
    """Semantic C3-C2 result; live handles remain in the private registry."""

    reservation_id: str
    execution_id: str
    child_request_sha256: str
    resume_receipt: ResumeReceipt

    def __reduce__(self) -> object:
        raise TypeError("C3-C2 resumed capture cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("C3-C2 resumed capture cannot be pickled")


_C3_C3B_OBSERVATION_ISSUER = object()
_C3_POST_RESUME_EVIDENCE_CONSTRUCTOR = object()
_PRODUCTION_C3_COMPOSITION_ISSUANCE_CONSTRUCTOR = object()
_PRODUCTION_C3_ROOT_CONSTRUCTOR = object()
_PRODUCTION_C3_ROOT_INITIALIZING = object()
_PRODUCTION_C3_ROOT_CONSTRUCTIONS_LOCK = threading.Lock()
_PRODUCTION_C3_ROOT_CONSTRUCTIONS: weakref.WeakKeyDictionary[
    WindowsEffectfulDailySnapshotCapture,
    object,
] = weakref.WeakKeyDictionary()


def _admit_production_c3_root_initialization(
    root: WindowsEffectfulDailySnapshotCapture,
) -> None:
    if type(root) is not WindowsEffectfulDailySnapshotCapture:
        raise TypeError("production C3 composition root cannot be subclassed")
    with _PRODUCTION_C3_ROOT_CONSTRUCTIONS_LOCK:
        if (
            _PRODUCTION_C3_ROOT_CONSTRUCTIONS.get(root)
            is not _PRODUCTION_C3_ROOT_CONSTRUCTOR
        ):
            raise WindowsEffectfulCaptureCompositionError(
                "production C3 composition root initialization is unavailable"
            )
        _PRODUCTION_C3_ROOT_CONSTRUCTIONS[root] = _PRODUCTION_C3_ROOT_INITIALIZING


def _discard_production_c3_root_construction(
    root: WindowsEffectfulDailySnapshotCapture,
) -> None:
    with _PRODUCTION_C3_ROOT_CONSTRUCTIONS_LOCK:
        _PRODUCTION_C3_ROOT_CONSTRUCTIONS.pop(root, None)


@dataclass(slots=True)
class _ProductionC3CompositionIssuanceRecord:
    root: WindowsEffectfulDailySnapshotCapture
    authority: ValidatedProductionAuthority
    adapter: _ProductionC3TransactionalAdapter
    issuer: object


_PRODUCTION_C3_COMPOSITION_ISSUANCES_LOCK = threading.Lock()
_PRODUCTION_C3_COMPOSITION_ISSUANCES: weakref.WeakKeyDictionary[
    _ProductionC3CompositionIssuance,
    _ProductionC3CompositionIssuanceRecord,
] = weakref.WeakKeyDictionary()


def _discard_production_c3_composition_issuances(
    root: WindowsEffectfulDailySnapshotCapture,
    adapter: _ProductionC3TransactionalAdapter,
) -> None:
    with _PRODUCTION_C3_COMPOSITION_ISSUANCES_LOCK:
        failed_issuances = tuple(
            issuance
            for issuance, record in _PRODUCTION_C3_COMPOSITION_ISSUANCES.items()
            if type(record) is _ProductionC3CompositionIssuanceRecord
            and record.root is root
            and record.adapter is adapter
        )
        for issuance in failed_issuances:
            _PRODUCTION_C3_COMPOSITION_ISSUANCES.pop(issuance, None)


class _ProductionC3CompositionIssuance:
    """Exact one-shot issuance retained only by one genuine production root."""

    __slots__ = ("_issuance_provenance", "__weakref__")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("production C3 composition issuances cannot be subclassed")

    def __new__(cls, *args: object) -> object:
        del args
        raise TypeError("production C3 composition issuance requires its root")

    def __init__(self, *args: object) -> None:
        del args
        raise TypeError("production C3 composition issuance requires its root")

    def issue_binding(self, root: WindowsEffectfulDailySnapshotCapture) -> object:
        if (
            type(self) is not _ProductionC3CompositionIssuance
            or self._issuance_provenance
            is not _PRODUCTION_C3_COMPOSITION_ISSUANCE_CONSTRUCTOR
        ):
            raise TypeError("production C3 composition issuance is invalid")
        with _PRODUCTION_C3_COMPOSITION_ISSUANCES_LOCK:
            record = _PRODUCTION_C3_COMPOSITION_ISSUANCES.get(self)
            if (
                type(record) is not _ProductionC3CompositionIssuanceRecord
                or record.issuer is not _PRODUCTION_C3_COMPOSITION_ISSUANCE_CONSTRUCTOR
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "production C3 composition issuance is unavailable"
                )
            adapter = record.adapter
            authority = record.authority
            if (
                type(root) is not WindowsEffectfulDailySnapshotCapture
                or root is not record.root
                or type(adapter) is not _ProductionC3TransactionalAdapter
                or root._adapter is not adapter
                or root._authority is not authority
                or root._production_c2_binding_issuance is not self
                or root._production_c2_binding_issued
                or adapter._capture is not root
                or adapter._authority is not authority
                or type(adapter._native_api)
                is not CtypesWindowsEffectfulCaptureNativeApi
                or adapter._closed
                or adapter._issuer is not None
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "production C3 composition binding is inconsistent"
                )
            del _PRODUCTION_C3_COMPOSITION_ISSUANCES[self]
            root._production_c2_binding_issued = True
        binding_issuer = _create_production_c3_composition_binding_issuer(
            _PRODUCTION_C3_COMPOSITION_BINDING_CONSTRUCTOR,
            authority=authority,
            adapter=adapter,
            composition_root=root,
            composition_issuance=self,
        )
        return _issue_production_c3_composition_binding(binding_issuer)

    def __copy__(self) -> object:
        raise TypeError("production C3 composition issuances cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("production C3 composition issuances cannot be deep-copied")

    def __reduce__(self) -> object:
        raise TypeError("production C3 composition issuances cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("production C3 composition issuances cannot be pickled")


def _create_production_c3_composition_issuance(
    root: WindowsEffectfulDailySnapshotCapture,
    authority: ValidatedProductionAuthority,
    adapter: _ProductionC3TransactionalAdapter,
) -> _ProductionC3CompositionIssuance:
    with _PRODUCTION_C3_ROOT_CONSTRUCTIONS_LOCK:
        construction = _PRODUCTION_C3_ROOT_CONSTRUCTIONS.pop(root, None)
    if (
        construction is not _PRODUCTION_C3_ROOT_INITIALIZING
        or type(root) is not WindowsEffectfulDailySnapshotCapture
        or type(adapter) is not _ProductionC3TransactionalAdapter
        or root._adapter is not adapter
        or root._authority is not authority
        or adapter._capture is not root
        or adapter._authority is not authority
        or type(adapter._native_api) is not CtypesWindowsEffectfulCaptureNativeApi
        or adapter._closed
        or adapter._issuer is not None
        or root._production_c2_binding_issued
    ):
        raise WindowsEffectfulCaptureCompositionError(
            "production C3 composition cannot issue its binding"
        )
    issuance = object.__new__(_ProductionC3CompositionIssuance)
    issuance._issuance_provenance = _PRODUCTION_C3_COMPOSITION_ISSUANCE_CONSTRUCTOR
    with _PRODUCTION_C3_COMPOSITION_ISSUANCES_LOCK:
        _PRODUCTION_C3_COMPOSITION_ISSUANCES[issuance] = (
            _ProductionC3CompositionIssuanceRecord(
                root=root,
                authority=authority,
                adapter=adapter,
                issuer=_PRODUCTION_C3_COMPOSITION_ISSUANCE_CONSTRUCTOR,
            )
        )
    return issuance


_C3_TERMINAL_AUTHORIZATION_CONSTRUCTOR = object()
_MAX_C3_CLEANUP_EVIDENCE_BYTES = 1024
_MAX_C3_TERMINAL_EVIDENCE_BYTES = 2048
_MAX_C3_TERMINAL_DIAGNOSTICS_BYTES = 512


@dataclass(frozen=True, slots=True)
class C3C3BObservationForTest:
    """Sanitized process-local C3-C3B observation with no durable authority."""

    reservation_id: str
    execution_id: str
    result_transport: C3ResultTransportStatus
    process_outcome: C3ProcessOutcomeStatus
    parent_cleanup: C3ParentCleanupStatus
    trusted_result: IsolatedCaptureChildResult | None
    _issuer: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._issuer is not _C3_C3B_OBSERVATION_ISSUER:
            raise TypeError("C3-C3B observations are issued only by the live registry")

    def __reduce__(self) -> object:
        raise TypeError("C3-C3B observation cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("C3-C3B observation cannot be pickled")


class _C3PostResumeEvidence:
    """Opaque one-shot capability issued only from an exact live C3 observation."""

    __slots__ = ("_issuer", "_permit")

    def __init__(self, constructor: object, issuer: object, permit: object) -> None:
        if constructor is not _C3_POST_RESUME_EVIDENCE_CONSTRUCTOR:
            raise TypeError("C3 post-resume evidence must be issued by the registry")
        self._issuer = issuer
        self._permit = permit

    def __copy__(self) -> object:
        raise TypeError("C3 post-resume evidence cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("C3 post-resume evidence cannot be deep-copied")

    def __reduce__(self) -> object:
        raise TypeError("C3 post-resume evidence cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("C3 post-resume evidence cannot be pickled")


@dataclass(frozen=True, slots=True)
class _C3PostResumeEvidenceIssuance:
    capability: _C3PostResumeEvidence
    permit: object
    issuer: object
    resume_receipt: ResumeReceipt
    observation: C3C3BObservationForTest
    child_request_sha256: str
    cleanup_json: bytes
    cleanup_digest: bytes


@dataclass(frozen=True, slots=True)
class _C3ObservationSnapshot:
    visible_values: tuple[object, ...]
    child_fence_state: str | None
    child_result_classification: str | None
    child_result_json: bytes | None


class C3StagingCleanupStatus(StrEnum):
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    ALREADY_RELEASED = "ALREADY_RELEASED"


class C3TerminalReason(StrEnum):
    VERIFIED_SNAPSHOT = "VERIFIED_SNAPSHOT"
    POST_FENCE_CHILD_FAILURE = "POST_FENCE_CHILD_FAILURE"
    PARENT_ARTIFACT_VERIFICATION_FAILED = "PARENT_ARTIFACT_VERIFICATION_FAILED"
    POST_RESUME_OUTCOME_AMBIGUOUS = "POST_RESUME_OUTCOME_AMBIGUOUS"


class _C3TerminalAuthorization:
    """Private one-shot authority for a deterministic non-success terminal."""

    __slots__ = ("_issuer", "_permit")

    def __init__(self, constructor: object, issuer: object, permit: object) -> None:
        if constructor is not _C3_TERMINAL_AUTHORIZATION_CONSTRUCTOR:
            raise TypeError("C3 terminal authority must be issued by the registry")
        self._issuer = issuer
        self._permit = permit

    def __copy__(self) -> object:
        raise TypeError("C3 terminal authority cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("C3 terminal authority cannot be deep-copied")

    def __reduce__(self) -> object:
        raise TypeError("C3 terminal authority cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("C3 terminal authority cannot be pickled")


@dataclass(frozen=True, slots=True)
class _C3TerminalIssuance:
    authorization: object
    permit: object
    issuer: object
    lineage: tuple[str, str, str, str, str]
    observation: C3C3BObservationForTest
    observation_snapshot: _C3ObservationSnapshot
    child_request_sha256: str
    verification_failure: str | None
    state: str
    disposition: str
    snapshot_digest: bytes | None
    evidence_json: bytes
    evidence_digest: bytes
    diagnostics_json: bytes
    diagnostics_digest: bytes
    staging_cleanup: C3StagingCleanupStatus


@dataclass(slots=True)
class _C3LiveProcessEntry:
    reservation_id: str
    process_intent_digest: bytes
    receipt: ProcessCreationReceipt
    child: SuspendedCaptureChild
    execution_id: str | None = None
    request_delivery_attempted: bool = False
    request_sha256: str | None = None
    child_request: IsolatedCaptureChildRequest | None = None
    resume_receipt: ResumeReceipt | None = None
    observed: bool = False
    observation: C3C3BObservationForTest | None = None
    observation_snapshot: _C3ObservationSnapshot | None = None
    evidence_issuance: _C3PostResumeEvidenceIssuance | None = None
    evidence_consumed: bool = False
    verified_snapshot: VerifiedCapturedSnapshot | None = None
    verification_failure: str | None = None
    verification_staging_cleanup: C3StagingCleanupStatus | None = None
    verification_started: bool = False
    terminal_issuance: _C3TerminalIssuance | None = None


class C3ArtifactVerificationFailure(StrEnum):
    INELIGIBLE_CHILD_RESULT = "INELIGIBLE_CHILD_RESULT"
    STAGING_IDENTITY_MISMATCH = "STAGING_IDENTITY_MISMATCH"
    STAGING_BYTES_INVALID = "STAGING_BYTES_INVALID"
    CHILD_CLAIM_MISMATCH = "CHILD_CLAIM_MISMATCH"
    OFFLINE_VERIFICATION_FAILED = "OFFLINE_VERIFICATION_FAILED"
    REQUEST_RECONCILIATION_FAILED = "REQUEST_RECONCILIATION_FAILED"
    PUBLICATION_FAILED = "PUBLICATION_FAILED"
    FINAL_REVERIFICATION_FAILED = "FINAL_REVERIFICATION_FAILED"
    STAGING_CLEANUP_FAILED = "STAGING_CLEANUP_FAILED"


@dataclass(frozen=True, slots=True)
class C3ArtifactIdentityEvidence:
    """Bounded canonical identity evidence derived only from parent observations."""

    snapshot_id: UUID
    final_canonical_filename: str
    artifact_sha256: str
    artifact_byte_length: int
    native_file_identity: NativeFileIdentity
    schema: int = 1

    def __post_init__(self) -> None:
        if type(self.snapshot_id) is not UUID:
            raise WindowsEffectfulCaptureCompositionError(
                "artifact identity snapshot ID is invalid"
            )
        expected_name = f"daily-market-data-snapshot-{self.snapshot_id}.json"
        if self.final_canonical_filename != expected_name:
            raise WindowsEffectfulCaptureCompositionError(
                "artifact identity filename is not canonical"
            )
        if (
            type(self.artifact_sha256) is not str
            or len(self.artifact_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.artifact_sha256
            )
        ):
            raise WindowsEffectfulCaptureCompositionError(
                "artifact identity SHA-256 is invalid"
            )
        if (
            type(self.artifact_byte_length) is not int
            or not 1 <= self.artifact_byte_length <= MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES
        ):
            raise WindowsEffectfulCaptureCompositionError(
                "artifact identity byte length is invalid"
            )
        if type(self.native_file_identity) is not NativeFileIdentity:
            raise WindowsEffectfulCaptureCompositionError(
                "artifact native identity is invalid"
            )
        if self.schema != 1:
            raise WindowsEffectfulCaptureCompositionError(
                "artifact identity schema is unsupported"
            )

    @property
    def canonical_bytes(self) -> bytes:
        payload = _canonical_json(
            {
                "artifact_byte_length": self.artifact_byte_length,
                "artifact_sha256": self.artifact_sha256,
                "final_canonical_filename": self.final_canonical_filename,
                "native_file_identity": self.native_file_identity.canonical_evidence(),
                "schema": self.schema,
                "snapshot_id": str(self.snapshot_id),
            }
        )
        if len(payload) > 1024:
            raise WindowsEffectfulCaptureCompositionError(
                "artifact identity evidence exceeds its reviewed byte bound"
            )
        return payload

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()


class _C3LiveProcessRegistry:
    """Private, process-local native authority with no durable reconstruction."""

    __slots__ = ("_entries", "_issuer", "_lock")

    def __init__(self) -> None:
        self._entries: list[_C3LiveProcessEntry] = []
        self._issuer = object()
        self._lock = threading.Lock()

    def register_created(
        self,
        *,
        reservation_id: str,
        process_intent_digest: bytes,
        receipt: ProcessCreationReceipt,
        child: SuspendedCaptureChild,
    ) -> None:
        with self._lock:
            if any(
                entry.reservation_id == reservation_id
                or entry.receipt is receipt
                or entry.child is child
                for entry in self._entries
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 live process registration is duplicate"
                )
            self._entries.append(
                _C3LiveProcessEntry(
                    reservation_id=reservation_id,
                    process_intent_digest=process_intent_digest,
                    receipt=receipt,
                    child=child,
                )
            )

    def bind_execution(
        self,
        *,
        receipt: ProcessCreationReceipt,
        reservation_id: str,
        execution_id: str,
    ) -> None:
        with self._lock:
            entry = self._find_receipt(receipt)
            if (
                entry.reservation_id != reservation_id
                or entry.process_intent_digest != receipt.process_intent_digest
                or entry.execution_id is not None
                or any(
                    other.execution_id == execution_id
                    for other in self._entries
                    if other is not entry
                )
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 live process execution binding is invalid"
                )
            entry.execution_id = execution_id

    def deliver_request(
        self, *, reservation_id: str, execution_id: str, payload: bytes
    ) -> None:
        with self._lock:
            entry = self._find_bound(reservation_id, execution_id)
            if entry.request_delivery_attempted:
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 child request delivery was already attempted"
                )
            entry.request_delivery_attempted = True
            child = entry.child
            child_request = parse_isolated_capture_child_request(payload)
            if (
                child_request.reservation_id != reservation_id
                or child_request.execution_id != execution_id
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 child request lineage is mismatched"
                )
        deliver_canonical_child_request(child, payload)
        with self._lock:
            entry = self._find_bound(reservation_id, execution_id)
            if entry.child is not child or entry.request_sha256 is not None:
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 child request delivery provenance changed"
                )
            entry.request_sha256 = hashlib.sha256(payload).hexdigest()
            entry.child_request = child_request

    def resume(self, intent: ResumeIntent) -> None:
        with self._lock:
            entry = self._find_bound(intent.reservation_id, intent.execution_id)
            if entry.request_sha256 is None:
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 child request is not completely delivered"
                )
            resume_suspended_capture_child(entry.child)

    def retain_resume_receipt(
        self, intent: ResumeIntent, receipt: ResumeReceipt
    ) -> None:
        with self._lock:
            entry = self._find_bound(intent.reservation_id, intent.execution_id)
            if (
                entry.resume_receipt is not None
                or receipt.reservation_id != intent.reservation_id
                or receipt.execution_id != intent.execution_id
                or receipt.resume_intent_digest != intent.intent_digest
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 resume receipt binding is invalid"
                )
            entry.resume_receipt = receipt

    def observe(self, resumed: C3C2ResumedCaptureForTest) -> C3C3BObservationForTest:
        with self._lock:
            entry = self._find_bound(resumed.reservation_id, resumed.execution_id)
            if (
                entry.resume_receipt is not resumed.resume_receipt
                or entry.request_sha256 != resumed.child_request_sha256
                or entry.observed
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 resumed child observation provenance is stale or mismatched"
                )
            entry.observed = True
            child = entry.child
            request_sha256 = entry.request_sha256

        native = observe_resumed_capture_child(child)
        trusted: IsolatedCaptureChildResult | None = None
        if native.result_transport is C3ResultTransportStatus.COMPLETE:
            payload = native.result_payload
            if payload is not None:
                try:
                    parsed = parse_isolated_capture_child_result(payload)
                except WindowsEffectfulCaptureProtocolError:
                    parsed = None
                if (
                    parsed is not None
                    and parsed.reservation_id == resumed.reservation_id
                    and parsed.execution_id == resumed.execution_id
                    and parsed.child_request_sha256 == request_sha256
                ):
                    trusted = parsed
        trusted_json = (
            None
            if trusted is None
            else serialize_isolated_capture_child_result(trusted)
        )
        observation = C3C3BObservationForTest(
            reservation_id=resumed.reservation_id,
            execution_id=resumed.execution_id,
            result_transport=native.result_transport,
            process_outcome=native.process_outcome,
            parent_cleanup=native.parent_cleanup,
            trusted_result=trusted,
            _issuer=_C3_C3B_OBSERVATION_ISSUER,
        )
        with self._lock:
            entry = self._find_bound(resumed.reservation_id, resumed.execution_id)
            if (
                entry.child is not child
                or entry.observation is not None
                or entry.observation_snapshot is not None
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 observation registration provenance changed"
                )
            entry.observation = observation
            entry.observation_snapshot = _C3ObservationSnapshot(
                visible_values=_c3_observation_visible_values(observation),
                child_fence_state=(
                    None if trusted is None else trusted.fence_state.value
                ),
                child_result_classification=(
                    None if trusted is None else trusted.classification.value
                ),
                child_result_json=trusted_json,
            )
        return observation

    def issue_post_resume_evidence(
        self,
        resumed: C3C2ResumedCaptureForTest,
        observation: C3C3BObservationForTest,
    ) -> object:
        with self._lock:
            entry = self._find_bound(resumed.reservation_id, resumed.execution_id)
            if (
                entry.resume_receipt is not resumed.resume_receipt
                or entry.request_sha256 != resumed.child_request_sha256
                or entry.observation is not observation
                or entry.evidence_issuance is not None
                or entry.evidence_consumed
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 evidence issuance provenance is stale or mismatched"
                )
            snapshot = self._require_observation_snapshot_unchanged(entry)
            if entry.observation is None:
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 evidence requires one exact observation"
                )
            if entry.observation.parent_cleanup not in {
                C3ParentCleanupStatus.COMPLETE,
                C3ParentCleanupStatus.FAILED,
            }:
                raise WindowsEffectfulCaptureCompositionError(
                    "unresolved C3 cleanup cannot issue durable evidence"
                )
            if (
                entry.observation.process_outcome
                is C3ProcessOutcomeStatus.TERMINATION_UNCONFIRMED
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "unconfirmed termination cannot issue durable C3 evidence"
                )
            cleanup_json = _build_c3_cleanup_json(entry, snapshot)
            if len(cleanup_json) > _MAX_C3_CLEANUP_EVIDENCE_BYTES:
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 cleanup evidence exceeds its reviewed byte bound"
                )
            cleanup_digest = hashlib.sha256(cleanup_json).digest()
            permit = object()
            capability = _C3PostResumeEvidence(
                _C3_POST_RESUME_EVIDENCE_CONSTRUCTOR,
                self._issuer,
                permit,
            )
            entry.evidence_issuance = _C3PostResumeEvidenceIssuance(
                capability=capability,
                permit=permit,
                issuer=self._issuer,
                resume_receipt=resumed.resume_receipt,
                observation=observation,
                child_request_sha256=resumed.child_request_sha256,
                cleanup_json=cleanup_json,
                cleanup_digest=cleanup_digest,
            )
            return capability

    def validate_post_resume_evidence(
        self,
        evidence: object,
        *,
        execution_id: str,
        reservation_id: str,
        resume_receipt: ResumeReceipt,
    ) -> tuple[bytes, bytes]:
        with self._lock:
            entry, issuance = self._validate_post_resume_evidence_locked(
                evidence,
                execution_id=execution_id,
                reservation_id=reservation_id,
                resume_receipt=resume_receipt,
            )
            del entry
            return issuance.cleanup_json, issuance.cleanup_digest

    def consume_post_resume_evidence(
        self,
        evidence: object,
        *,
        execution_id: str,
        reservation_id: str,
        resume_receipt: ResumeReceipt,
    ) -> None:
        with self._lock:
            entry, _issuance = self._validate_post_resume_evidence_locked(
                evidence,
                execution_id=execution_id,
                reservation_id=reservation_id,
                resume_receipt=resume_receipt,
            )
            entry.evidence_consumed = True

    def verify_captured_snapshot(
        self, lineage: tuple[str, str, str, str, str]
    ) -> VerifiedCapturedSnapshot:
        """Verify and publish while C2 holds the exact reservation arbiter."""

        if (
            type(lineage) is not tuple
            or len(lineage) != 5
            or any(type(value) is not str for value in lineage)
        ):
            raise TypeError("C3 verification lineage is invalid")
        session_id, attempt_id, claim_id, reservation_id, execution_id = lineage
        with self._lock:
            entry = self._find_bound(reservation_id, execution_id)
            if (
                entry.verified_snapshot is not None
                or entry.verification_failure is not None
                or entry.verification_started
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 artifact verification was already attempted"
                )
            entry.verification_started = True
            snapshot = self._require_observation_snapshot_unchanged(entry)
            child_request = entry.child_request
            trusted = entry.observation.trusted_result if entry.observation else None
            if not entry.evidence_consumed or child_request is None:
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 artifact verification requires persisted post-resume evidence"
                )
            child = entry.child

        failure = C3ArtifactVerificationFailure.STAGING_BYTES_INVALID
        final_handle: int | None = None
        staging_handle: int | None = None
        cleanup_attempted = False
        staging_cleanup = C3StagingCleanupStatus.FAILED
        try:
            if (
                trusted is None
                or trusted.classification is not ChildResultClassification.SUCCEEDED
                or trusted.fence_state is not ProviderAttemptFenceState.ENTERED
                or trusted.cleanup_status is not ChildCleanupStatus.COMPLETE
                or trusted.snapshot_id is None
                or trusted.artifact_sha256 is None
                or trusted.artifact_byte_length is None
            ):
                failure = C3ArtifactVerificationFailure.INELIGIBLE_CHILD_RESULT
                raise WindowsEffectfulCaptureCompositionError(
                    "child result is not eligible for artifact verification"
                )

            staging_handle, retained_identity, staging_path = child._retained_staging()
            api = child._api
            if api.get_file_identity(staging_handle) != retained_identity:
                failure = C3ArtifactVerificationFailure.STAGING_IDENTITY_MISMATCH
                raise WindowsEffectfulCaptureCompositionError(
                    "staging native identity changed"
                )
            staged_bytes = api.read_artifact_file(
                staging_handle, MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES
            )
            if (
                not staged_bytes
                or len(staged_bytes) > MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "staging artifact bytes are empty or oversized"
                )
            artifact_sha256 = hashlib.sha256(staged_bytes).hexdigest()
            artifact_length = len(staged_bytes)
            if (
                trusted.artifact_sha256 != artifact_sha256
                or trusted.artifact_byte_length != artifact_length
            ):
                failure = C3ArtifactVerificationFailure.CHILD_CLAIM_MISMATCH
                raise WindowsEffectfulCaptureCompositionError(
                    "child artifact claims do not match parent-observed bytes"
                )
            calendar = BoundMarketCalendar(
                XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()
            )
            verification = verify_daily_snapshot(
                staged_bytes,
                calendar,
                expected_sha256=artifact_sha256,
                expected_byte_length=artifact_length,
            )
            if not verification.passed or verification.snapshot is None:
                failure = C3ArtifactVerificationFailure.OFFLINE_VERIFICATION_FAILED
                raise WindowsEffectfulCaptureCompositionError(
                    "staging artifact failed offline verification"
                )
            verified = verification.snapshot
            if serialize_daily_snapshot(verified) != staged_bytes:
                failure = C3ArtifactVerificationFailure.OFFLINE_VERIFICATION_FAILED
                raise WindowsEffectfulCaptureCompositionError(
                    "staging artifact is not canonical"
                )
            if trusted.snapshot_id != verified.snapshot_id:
                failure = C3ArtifactVerificationFailure.CHILD_CLAIM_MISMATCH
                raise WindowsEffectfulCaptureCompositionError(
                    "child snapshot identity does not match verified bytes"
                )
            if not _snapshot_matches_child_request(verified, child_request):
                failure = C3ArtifactVerificationFailure.REQUEST_RECONCILIATION_FAILED
                raise WindowsEffectfulCaptureCompositionError(
                    "verified snapshot does not match the exact C3 request"
                )

            staging = PureWindowsPath(staging_path)
            expected_staging_name = f".c3-capture-{reservation_id}.staging"
            if staging.name != expected_staging_name:
                failure = C3ArtifactVerificationFailure.STAGING_IDENTITY_MISMATCH
                raise WindowsEffectfulCaptureCompositionError(
                    "staging name is not the exact reservation-derived name"
                )
            final_name = f"daily-market-data-snapshot-{verified.snapshot_id}.json"
            final_path = str(staging.parent / final_name)
            failure = C3ArtifactVerificationFailure.PUBLICATION_FAILED
            api.reject_casefold_collisions(str(staging.parent), (final_name,))
            if api.get_file_identity(staging_handle) != retained_identity:
                raise WindowsEffectfulCaptureCompositionError(
                    "staging identity changed before publication"
                )
            api.publish_staging_link(staging_handle, final_path)

            failure = C3ArtifactVerificationFailure.FINAL_REVERIFICATION_FAILED
            opened = api.open_final_artifact(final_path)
            if type(opened) is not NativeOpenedArtifact:
                raise WindowsEffectfulCaptureCompositionError(
                    "final artifact reopen result is invalid"
                )
            final_handle = opened.handle
            if opened.identity != retained_identity:
                raise WindowsEffectfulCaptureCompositionError(
                    "final artifact native identity does not match staging"
                )
            final_bytes = api.read_artifact_file(
                final_handle, MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES
            )
            if (
                final_bytes != staged_bytes
                or len(final_bytes) != artifact_length
                or hashlib.sha256(final_bytes).hexdigest() != artifact_sha256
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "final artifact bytes changed after publication"
                )
            final_verification = verify_daily_snapshot(
                final_bytes,
                calendar,
                expected_sha256=artifact_sha256,
                expected_byte_length=artifact_length,
            )
            if (
                not final_verification.passed
                or final_verification.snapshot != verified
                or final_verification.snapshot is None
                or serialize_daily_snapshot(final_verification.snapshot) != final_bytes
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "final artifact failed independent reverification"
                )
            closing_final_handle = final_handle
            final_handle = None
            api.close_handle(closing_final_handle)

            identity_evidence = C3ArtifactIdentityEvidence(
                snapshot_id=verified.snapshot_id,
                final_canonical_filename=final_name,
                artifact_sha256=artifact_sha256,
                artifact_byte_length=artifact_length,
                native_file_identity=retained_identity,
            )
            child_result_sha256 = hashlib.sha256(snapshot.child_result_json).hexdigest()

            failure = C3ArtifactVerificationFailure.STAGING_CLEANUP_FAILED
            if api.get_file_identity(staging_handle) != retained_identity:
                raise WindowsEffectfulCaptureCompositionError(
                    "staging identity changed before cleanup"
                )
            cleanup_attempted = True
            api.delete_staging_link(staging_handle)
            released = child._release_staging_handle()
            if released != staging_handle:
                raise WindowsEffectfulCaptureCompositionError(
                    "staging cleanup handle provenance changed"
                )
            staging_handle = None
            api.close_handle(released)
            staging_cleanup = C3StagingCleanupStatus.COMPLETE

            capability = _issue_production_verified_captured_snapshot(
                session_id=session_id,
                attempt_id=attempt_id,
                claim_id=claim_id,
                reservation_id=reservation_id,
                execution_id=execution_id,
                snapshot_id=verified.snapshot_id,
                artifact_sha256=artifact_sha256,
                artifact_byte_length=artifact_length,
                artifact_identity_sha256=identity_evidence.sha256,
                child_result_sha256=child_result_sha256,
            )
            with self._lock:
                current = self._find_bound(reservation_id, execution_id)
                if current is not entry or current.verified_snapshot is not None:
                    raise WindowsEffectfulCaptureCompositionError(
                        "C3 verifier registry provenance changed"
                    )
                current.verified_snapshot = capability
                current.verification_staging_cleanup = staging_cleanup
            return capability
        except BaseException:
            if final_handle is not None:
                try:
                    child._api.close_handle(final_handle)
                except Exception:
                    pass
            if staging_handle is None:
                try:
                    staging_handle, _retained_identity, _staging_path = (
                        child._retained_staging()
                    )
                except Exception:
                    staging_cleanup = C3StagingCleanupStatus.ALREADY_RELEASED
            if staging_handle is not None:
                try:
                    if not cleanup_attempted:
                        if (
                            child._api.get_file_identity(staging_handle)
                            != child._staging_identity
                        ):
                            staging_cleanup = C3StagingCleanupStatus.IDENTITY_MISMATCH
                        else:
                            cleanup_attempted = True
                            child._api.delete_staging_link(staging_handle)
                            staging_cleanup = C3StagingCleanupStatus.COMPLETE
                except Exception:
                    staging_cleanup = C3StagingCleanupStatus.FAILED
                try:
                    if child._staging_handle == staging_handle:
                        child._release_staging_handle()
                    child._api.close_handle(staging_handle)
                except Exception:
                    staging_cleanup = C3StagingCleanupStatus.FAILED
            with self._lock:
                current = self._find_bound(reservation_id, execution_id)
                current.verification_failure = failure.value
                current.verification_staging_cleanup = staging_cleanup
            raise WindowsEffectfulCaptureCompositionError(
                "C3 parent artifact verification failed"
            ) from None

    def validate_verified_snapshot(
        self,
        capability: VerifiedCapturedSnapshot,
        lineage: tuple[str, str, str, str, str],
    ) -> None:
        with self._lock:
            entry = self._find_bound(lineage[3], lineage[4])
            if entry.verified_snapshot is not capability:
                raise WindowsEffectfulCaptureCompositionError(
                    "verified snapshot is stale or unregistered"
                )
            values = _validate_production_verified_captured_snapshot(capability)
            if values[:5] != lineage:
                raise WindowsEffectfulCaptureCompositionError(
                    "verified snapshot complete C2 lineage is mismatched"
                )

    def verified_snapshot_lineage(
        self, capability: VerifiedCapturedSnapshot
    ) -> tuple[str, str, str, str, str]:
        with self._lock:
            values = _validate_production_verified_captured_snapshot(capability)
            lineage = values[:5]
            if any(type(value) is not str for value in lineage):
                raise WindowsEffectfulCaptureCompositionError(
                    "verified snapshot registry lineage is invalid"
                )
            typed = (lineage[0], lineage[1], lineage[2], lineage[3], lineage[4])
            entry = self._find_bound(typed[3], typed[4])
            if entry.verified_snapshot is not capability:
                raise WindowsEffectfulCaptureCompositionError(
                    "verified snapshot is stale or unregistered"
                )
        return typed

    def prepare_terminal(
        self,
        lineage: tuple[str, str, str, str, str],
        verified_snapshot: object | None,
    ) -> object:
        """Derive one terminal issuance while C2 holds the lifecycle arbiter."""

        if (
            type(lineage) is not tuple
            or len(lineage) != 5
            or any(type(value) is not str for value in lineage)
        ):
            raise TypeError("C3 terminal lineage is invalid")
        with self._lock:
            entry = self._find_bound(lineage[3], lineage[4])
            snapshot = self._require_observation_snapshot_unchanged(entry)
            if not entry.evidence_consumed or entry.observation is None:
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 terminal requires persisted post-resume evidence"
                )
            existing = entry.terminal_issuance
            if existing is not None:
                expected = (
                    existing.authorization if existing.state == "SUCCEEDED" else None
                )
                if verified_snapshot is not expected:
                    raise WindowsEffectfulCaptureCompositionError(
                        "C3 terminal retry authority is mismatched"
                    )
                self._validate_terminal_issuance_locked(
                    entry, existing.authorization, lineage
                )
                return existing.authorization

            trusted = entry.observation.trusted_result
            if verified_snapshot is not None:
                if entry.verified_snapshot is not verified_snapshot:
                    raise WindowsEffectfulCaptureCompositionError(
                        "verified snapshot is stale or unregistered"
                    )
                if type(verified_snapshot) is not VerifiedCapturedSnapshot:
                    raise TypeError("C3 success requires exact verified snapshot")
                values = _validate_production_verified_captured_snapshot(
                    verified_snapshot
                )
                if values[:5] != lineage:
                    raise WindowsEffectfulCaptureCompositionError(
                        "verified snapshot complete C2 lineage is mismatched"
                    )
                if (
                    trusted is None
                    or snapshot.child_fence_state
                    != ProviderAttemptFenceState.ENTERED.value
                    or snapshot.child_result_classification
                    != ChildResultClassification.SUCCEEDED.value
                    or snapshot.child_result_json is None
                    or hashlib.sha256(snapshot.child_result_json).hexdigest()
                    != verified_snapshot.child_result_sha256
                ):
                    raise WindowsEffectfulCaptureCompositionError(
                        "verified snapshot child result binding is inconsistent"
                    )
                state = "SUCCEEDED"
                disposition = "CONFIRMED"
                reason = C3TerminalReason.VERIFIED_SNAPSHOT
                snapshot_digest = bytes.fromhex(verified_snapshot.artifact_sha256)
                staging_cleanup = C3StagingCleanupStatus.COMPLETE
                artifact_verification = "VERIFIED"
                authorization: object = verified_snapshot
                permit = object()
            else:
                if entry.verified_snapshot is not None:
                    raise WindowsEffectfulCaptureCompositionError(
                        "C3 success requires the exact verified snapshot capability"
                    )
                if trusted is None:
                    state = "AMBIGUOUS"
                    disposition = "MAY_HAVE_OCCURRED"
                    reason = C3TerminalReason.POST_RESUME_OUTCOME_AMBIGUOUS
                elif trusted.fence_state is ProviderAttemptFenceState.NOT_ENTERED:
                    state = "AMBIGUOUS"
                    disposition = "MAY_HAVE_OCCURRED"
                    reason = C3TerminalReason.POST_RESUME_OUTCOME_AMBIGUOUS
                elif trusted.classification is not ChildResultClassification.SUCCEEDED:
                    state = "FAILED"
                    disposition = "CONFIRMED"
                    reason = C3TerminalReason.POST_FENCE_CHILD_FAILURE
                elif entry.verification_failure is not None:
                    state = "FAILED"
                    disposition = "CONFIRMED"
                    reason = C3TerminalReason.PARENT_ARTIFACT_VERIFICATION_FAILED
                else:
                    raise WindowsEffectfulCaptureCompositionError(
                        "successful child result requires D1 verification first"
                    )
                snapshot_digest = None
                artifact_verification = (
                    "NOT_ATTEMPTED"
                    if entry.verification_failure is None
                    else entry.verification_failure
                )
                if entry.verification_started:
                    staging_cleanup = (
                        entry.verification_staging_cleanup
                        or C3StagingCleanupStatus.FAILED
                    )
                else:
                    staging_cleanup = self._settle_staging_locked(entry)
                permit = object()
                authorization = _C3TerminalAuthorization(
                    _C3_TERMINAL_AUTHORIZATION_CONSTRUCTOR,
                    self._issuer,
                    permit,
                )

            evidence_json = _build_c3_terminal_evidence(
                entry=entry,
                snapshot=snapshot,
                lineage=lineage,
                state=state,
                disposition=disposition,
                artifact_verification=artifact_verification,
                verified_snapshot=(
                    verified_snapshot
                    if type(verified_snapshot) is VerifiedCapturedSnapshot
                    else None
                ),
                staging_cleanup=staging_cleanup,
            )
            diagnostics_json = _build_c3_terminal_diagnostics(
                entry.observation,
                reason=reason,
                artifact_verification=artifact_verification,
                staging_cleanup=staging_cleanup,
            )
            issuance = _C3TerminalIssuance(
                authorization=authorization,
                permit=permit,
                issuer=self._issuer,
                lineage=lineage,
                observation=entry.observation,
                observation_snapshot=snapshot,
                child_request_sha256=entry.request_sha256 or "",
                verification_failure=entry.verification_failure,
                state=state,
                disposition=disposition,
                snapshot_digest=snapshot_digest,
                evidence_json=evidence_json,
                evidence_digest=hashlib.sha256(evidence_json).digest(),
                diagnostics_json=diagnostics_json,
                diagnostics_digest=hashlib.sha256(diagnostics_json).digest(),
                staging_cleanup=staging_cleanup,
            )
            entry.terminal_issuance = issuance
            return authorization

    def validate_terminal(
        self,
        authorization: object,
        lineage: tuple[str, str, str, str, str],
    ) -> tuple[str, str, bytes | None, bytes, bytes, bytes, bytes]:
        with self._lock:
            entry = self._find_bound(lineage[3], lineage[4])
            issuance = self._validate_terminal_issuance_locked(
                entry, authorization, lineage
            )
            return (
                issuance.state,
                issuance.disposition,
                issuance.snapshot_digest,
                issuance.evidence_json,
                issuance.evidence_digest,
                issuance.diagnostics_json,
                issuance.diagnostics_digest,
            )

    def consume_terminal(
        self, authorization: object, lineage: tuple[str, str, str, str, str]
    ) -> None:
        with self._lock:
            entry = self._find_bound(lineage[3], lineage[4])
            issuance = self._validate_terminal_issuance_locked(
                entry, authorization, lineage
            )
            if issuance.state == "SUCCEEDED":
                if type(authorization) is not VerifiedCapturedSnapshot:
                    raise TypeError("C3 success requires exact verified snapshot")
                digest = _consume_production_verified_captured_snapshot(authorization)
                if digest != issuance.snapshot_digest:
                    raise WindowsEffectfulCaptureCompositionError(
                        "verified snapshot terminal digest changed"
                    )
            self._entries.remove(entry)
        try:
            entry.child.close()
        except Exception:
            pass

    def _validate_terminal_issuance_locked(
        self,
        entry: _C3LiveProcessEntry,
        authorization: object,
        lineage: tuple[str, str, str, str, str],
    ) -> _C3TerminalIssuance:
        issuance = entry.terminal_issuance
        if issuance is None or issuance.authorization is not authorization:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 terminal authority was consumed or not issued"
            )
        snapshot = self._require_observation_snapshot_unchanged(entry)
        if (
            issuance.issuer is not self._issuer
            or issuance.lineage != lineage
            or issuance.observation is not entry.observation
            or issuance.observation_snapshot != snapshot
            or issuance.child_request_sha256 != entry.request_sha256
            or issuance.verification_failure != entry.verification_failure
        ):
            raise WindowsEffectfulCaptureCompositionError(
                "C3 terminal authority exact-object binding mismatch"
            )
        if issuance.state == "SUCCEEDED":
            if entry.verified_snapshot is not authorization:
                raise WindowsEffectfulCaptureCompositionError(
                    "verified snapshot is stale or unregistered"
                )
            _validate_production_verified_captured_snapshot(authorization)
        elif (
            type(authorization) is not _C3TerminalAuthorization
            or authorization._issuer is not self._issuer
            or authorization._permit is not issuance.permit
        ):
            raise WindowsEffectfulCaptureCompositionError(
                "C3 non-success terminal authority binding mismatch"
            )
        return issuance

    @staticmethod
    def _settle_staging_locked(
        entry: _C3LiveProcessEntry,
    ) -> C3StagingCleanupStatus:
        child = entry.child
        if child.closed:
            return C3StagingCleanupStatus.ALREADY_RELEASED
        try:
            staging_handle, retained_identity, _staging_path = child._retained_staging()
        except Exception:
            return C3StagingCleanupStatus.ALREADY_RELEASED
        status = C3StagingCleanupStatus.FAILED
        try:
            if child._api.get_file_identity(staging_handle) != retained_identity:
                status = C3StagingCleanupStatus.IDENTITY_MISMATCH
            else:
                child._api.delete_staging_link(staging_handle)
                status = C3StagingCleanupStatus.COMPLETE
        except Exception:
            status = C3StagingCleanupStatus.FAILED
        try:
            released = child._release_staging_handle()
            if released != staging_handle:
                status = C3StagingCleanupStatus.FAILED
            child._api.close_handle(released)
        except Exception:
            status = C3StagingCleanupStatus.FAILED
        return status

    def _validate_post_resume_evidence_locked(
        self,
        evidence: object,
        *,
        execution_id: str,
        reservation_id: str,
        resume_receipt: ResumeReceipt,
    ) -> tuple[_C3LiveProcessEntry, _C3PostResumeEvidenceIssuance]:
        if type(evidence) is not _C3PostResumeEvidence:
            raise TypeError("C3 post-resume persistence requires exact evidence")
        entry = self._find_bound(reservation_id, execution_id)
        issuance = entry.evidence_issuance
        if issuance is None or entry.evidence_consumed:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 post-resume evidence was consumed or not issued"
            )
        snapshot = self._require_observation_snapshot_unchanged(entry)
        if (
            issuance.capability is not evidence
            or evidence._issuer is not self._issuer
            or evidence._issuer is not issuance.issuer
            or evidence._permit is not issuance.permit
            or entry.resume_receipt is not resume_receipt
            or issuance.resume_receipt is not resume_receipt
            or entry.observation is not issuance.observation
            or entry.request_sha256 != issuance.child_request_sha256
            or issuance.cleanup_json != _build_c3_cleanup_json(entry, snapshot)
            or hashlib.sha256(issuance.cleanup_json).digest() != issuance.cleanup_digest
        ):
            raise WindowsEffectfulCaptureCompositionError(
                "C3 post-resume evidence exact-object binding mismatch"
            )
        return entry, issuance

    def _require_observation_snapshot_unchanged(
        self, entry: _C3LiveProcessEntry
    ) -> _C3ObservationSnapshot:
        observation = entry.observation
        snapshot = entry.observation_snapshot
        if observation is None or snapshot is None:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 evidence requires a registered observation"
            )
        if snapshot.visible_values != _c3_observation_visible_values(observation):
            raise WindowsEffectfulCaptureCompositionError(
                "C3 observation fields changed after registration"
            )
        trusted = observation.trusted_result
        trusted_json = (
            None
            if trusted is None
            else serialize_isolated_capture_child_result(trusted)
        )
        if trusted_json != snapshot.child_result_json:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 trusted child result changed after observation"
            )
        return snapshot

    def request_sha256(self, reservation_id: str, execution_id: str) -> str:
        with self._lock:
            entry = self._find_bound(reservation_id, execution_id)
            if entry.request_sha256 is None:
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 child request is not completely delivered"
                )
            return entry.request_sha256

    def discard_receipt(self, receipt: ProcessCreationReceipt) -> None:
        with self._lock:
            entry = self._find_receipt(receipt)
            self._entries.remove(entry)
        entry.child.close()

    def close(self) -> None:
        with self._lock:
            entries = self._entries
            self._entries = []
        failed = False
        for entry in entries:
            try:
                entry.child.close()
            except Exception:
                failed = True
        if failed:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 live process registry cleanup failed"
            ) from None

    def semantic_snapshot(
        self,
    ) -> tuple[tuple[str, str | None, bool, bool, bool], ...]:
        with self._lock:
            return tuple(
                (
                    entry.reservation_id,
                    entry.execution_id,
                    entry.request_sha256 is not None,
                    entry.resume_receipt is not None,
                    entry.observation is not None,
                )
                for entry in self._entries
            )

    def _find_receipt(self, receipt: ProcessCreationReceipt) -> _C3LiveProcessEntry:
        matches = [entry for entry in self._entries if entry.receipt is receipt]
        if len(matches) != 1:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 live process receipt is stale or unregistered"
            )
        return matches[0]

    def _find_bound(
        self, reservation_id: str, execution_id: str
    ) -> _C3LiveProcessEntry:
        matches = [
            entry
            for entry in self._entries
            if entry.reservation_id == reservation_id
            and entry.execution_id == execution_id
        ]
        if len(matches) != 1:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 live process provenance is stale or mismatched"
            )
        return matches[0]


def _c3_observation_visible_values(
    observation: C3C3BObservationForTest,
) -> tuple[object, ...]:
    return (
        observation.reservation_id,
        observation.execution_id,
        observation.result_transport,
        observation.process_outcome,
        observation.parent_cleanup,
        observation.trusted_result,
        observation._issuer,
    )


def _build_c3_cleanup_json(
    entry: _C3LiveProcessEntry,
    snapshot: _C3ObservationSnapshot,
) -> bytes:
    observation = entry.observation
    request_sha256 = entry.request_sha256
    execution_id = entry.execution_id
    if observation is None or request_sha256 is None or execution_id is None:
        raise WindowsEffectfulCaptureCompositionError(
            "C3 cleanup evidence lineage is incomplete"
        )
    child_result_sha256 = (
        None
        if snapshot.child_result_json is None
        else hashlib.sha256(snapshot.child_result_json).hexdigest()
    )
    disposition = (
        "CONFIRMED"
        if snapshot.child_fence_state == ProviderAttemptFenceState.ENTERED.value
        else "MAY_HAVE_OCCURRED"
    )
    return json.dumps(
        {
            "child_fence_state": snapshot.child_fence_state,
            "child_request_sha256": request_sha256,
            "child_result_classification": snapshot.child_result_classification,
            "child_result_sha256": child_result_sha256,
            "execution_id": execution_id,
            "parent_cleanup": observation.parent_cleanup.value,
            "process_outcome": observation.process_outcome.value,
            "provider_call_disposition": disposition,
            "reservation_id": entry.reservation_id,
            "result_transport": observation.result_transport.value,
            "schema": 1,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _build_c3_terminal_evidence(
    *,
    entry: _C3LiveProcessEntry,
    snapshot: _C3ObservationSnapshot,
    lineage: tuple[str, str, str, str, str],
    state: str,
    disposition: str,
    artifact_verification: str,
    verified_snapshot: VerifiedCapturedSnapshot | None,
    staging_cleanup: C3StagingCleanupStatus,
) -> bytes:
    observation = entry.observation
    request_sha256 = entry.request_sha256
    if observation is None or request_sha256 is None:
        raise WindowsEffectfulCaptureCompositionError(
            "C3 terminal evidence lineage is incomplete"
        )
    child_result_sha256 = (
        None
        if snapshot.child_result_json is None
        else hashlib.sha256(snapshot.child_result_json).hexdigest()
    )
    payload = _canonical_json(
        {
            "artifact_identity_sha256": (
                None
                if verified_snapshot is None
                else verified_snapshot.artifact_identity_sha256
            ),
            "artifact_sha256": (
                None if verified_snapshot is None else verified_snapshot.artifact_sha256
            ),
            "artifact_verification": artifact_verification,
            "attempt_id": lineage[1],
            "child_fence_state": snapshot.child_fence_state,
            "child_request_sha256": request_sha256,
            "child_result_classification": snapshot.child_result_classification,
            "child_result_sha256": child_result_sha256,
            "claim_id": lineage[2],
            "execution_id": lineage[4],
            "parent_cleanup": observation.parent_cleanup.value,
            "process_outcome": observation.process_outcome.value,
            "provider_call_disposition": disposition,
            "reservation_id": lineage[3],
            "result_transport": observation.result_transport.value,
            "schema": 1,
            "session_id": lineage[0],
            "snapshot_id": (
                None
                if verified_snapshot is None
                else str(verified_snapshot.snapshot_id)
            ),
            "staging_cleanup": staging_cleanup.value,
            "terminal_state": state,
        }
    )
    if len(payload) > _MAX_C3_TERMINAL_EVIDENCE_BYTES:
        raise WindowsEffectfulCaptureCompositionError(
            "C3 terminal evidence exceeds its reviewed byte bound"
        )
    return payload


def _build_c3_terminal_diagnostics(
    observation: C3C3BObservationForTest,
    *,
    reason: C3TerminalReason,
    artifact_verification: str,
    staging_cleanup: C3StagingCleanupStatus,
) -> bytes:
    payload = _canonical_json(
        {
            "artifact_verification": artifact_verification,
            "parent_cleanup": observation.parent_cleanup.value,
            "reason": reason.value,
            "result_transport": observation.result_transport.value,
            "schema": 1,
            "staging_cleanup": staging_cleanup.value,
        }
    )
    if len(payload) > _MAX_C3_TERMINAL_DIAGNOSTICS_BYTES:
        raise WindowsEffectfulCaptureCompositionError(
            "C3 terminal diagnostics exceed their reviewed byte bound"
        )
    return payload


def _snapshot_matches_child_request(
    snapshot: object, request: IsolatedCaptureChildRequest
) -> bool:
    retained = getattr(snapshot, "request", None)
    return bool(
        retained is not None
        and retained.request_id == request.daily_snapshot_request_id
        and retained.requested_at == request.requested_at_utc
        and retained.symbols == request.capture_request.ordered_universe
        and retained.calendar == XNYS_CALENDAR_DESCRIPTOR
        and getattr(snapshot, "target_session", None)
        == request.authorized_snapshot_session
        and getattr(snapshot, "provider", None) == request.provider
        and request.provider == ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
    )


class C3C2TransactionalAdapterForTest:
    """C3-specific C2 adapter used only with the disposable authority seam."""

    __slots__ = (
        "_capture",
        "_expected_requests",
        "_launch",
        "_launch_plans",
        "_native_api",
        "_plan",
        "_registry",
    )

    def __init__(
        self,
        capture: WindowsEffectfulDailySnapshotCapture,
        plan: ProductionCapturePlan,
        launch: C3C2NativeLaunchConfigurationForTest,
        native_api: WindowsEffectfulCaptureNativeApi,
    ) -> None:
        if type(capture) is not WindowsEffectfulDailySnapshotCapture:
            raise TypeError("C3-C2 test adapter requires the C3 composition root")
        if type(plan) is not ProductionCapturePlan:
            raise TypeError("C3-C2 test adapter requires ProductionCapturePlan")
        if type(launch) is not C3C2NativeLaunchConfigurationForTest:
            raise TypeError("C3-C2 test adapter requires its exact launch config")
        self._capture = capture
        self._plan = plan
        self._launch = launch
        self._native_api = native_api
        self._registry = _C3LiveProcessRegistry()
        self._launch_plans: dict[str, ProductionProviderLaunchPlan] = {}
        self._expected_requests: dict[tuple[str, str], bytes] = {}

    def construct_provider(
        self, capability: ProviderConstructionPermit, *, fail: bool = False
    ) -> ConstructedProvider:
        if fail:
            raise WindowsEffectfulCaptureCompositionError(
                "injected C3 provider-plan construction failure"
            )
        reservation_id = capability.reservation_id
        if reservation_id in self._launch_plans:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 provider launch plan was already constructed"
            )
        bound = bind_production_capture_plan(self._plan, reservation_id)
        self._launch_plans[reservation_id] = build_production_provider_launch_plan(
            bound
        )
        from trading_bot.runtime.windows_transactional_authority import (
            issue_constructed_provider_for_test,
        )

        return issue_constructed_provider_for_test(reservation_id)

    def create_process(
        self, process_intent: ProcessIntent, *, fail: bool = False
    ) -> ProcessCreationReceipt | ProcessCreationFailure:
        if fail:
            raise WindowsEffectfulCaptureCompositionError(
                "injected C3 process creation failure"
            )
        reservation_id = process_intent.reservation_id
        if reservation_id not in self._launch_plans:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 process creation has no exact provider launch plan"
            )
        launch = self._launch
        staging_path = str(
            PureWindowsPath(launch.storage_root)
            / f".c3-capture-{reservation_id}.staging"
        )
        child = create_suspended_capture_child_for_test(
            application_name=launch.application_name,
            arguments=launch.arguments,
            current_directory=launch.current_directory,
            controlled_temp_directory=launch.controlled_temp_directory,
            staging_path=staging_path,
            parent_environment=launch.parent_environment,
            native_api=self._native_api,
        )
        try:
            from trading_bot.runtime.windows_transactional_authority import (
                issue_process_creation_receipt_for_test,
                process_success_evidence_for_test,
            )

            process_json, job_json, resume_json = process_success_evidence_for_test(
                reservation_id, process_intent.intent_digest
            )
            receipt = issue_process_creation_receipt_for_test(
                reservation_id,
                process_intent.intent_digest,
                process_json,
                hashlib.sha256(process_json).digest(),
                job_json,
                hashlib.sha256(job_json).digest(),
                resume_json,
                hashlib.sha256(resume_json).digest(),
            )
            self._registry.register_created(
                reservation_id=reservation_id,
                process_intent_digest=process_intent.intent_digest,
                receipt=receipt,
                child=child,
            )
            return receipt
        except BaseException:
            child.close()
            raise

    def resume_thread(
        self, resume_intent: ResumeIntent, *, fail: bool = False
    ) -> ResumeReceipt:
        if fail:
            raise WindowsEffectfulCaptureCompositionError("injected C3 resume failure")
        self._registry.resume(resume_intent)
        result_json = _canonical_json(
            {
                "execution_id": resume_intent.execution_id,
                "resume_intent_digest": resume_intent.intent_digest.hex(),
                "resume_result": "RESUMED",
                "schema": 1,
            }
        )
        from trading_bot.runtime.windows_transactional_authority import (
            issue_resume_receipt_for_test,
        )

        receipt = issue_resume_receipt_for_test(
            resume_intent.execution_id,
            resume_intent.reservation_id,
            resume_intent.intent_digest,
            result_json,
            hashlib.sha256(result_json).digest(),
        )
        self._registry.retain_resume_receipt(resume_intent, receipt)
        return receipt

    def bind_execution(
        self,
        receipt: ProcessCreationReceipt,
        reservation_id: str,
        execution_id: str,
    ) -> None:
        self._registry.bind_execution(
            receipt=receipt,
            reservation_id=reservation_id,
            execution_id=execution_id,
        )
        prepared = self._capture._prepare_execution(
            self._plan,
            reservation_id=reservation_id,
            execution_id=execution_id,
        )
        launch = self._launch_plans.get(reservation_id)
        if launch is None or launch != prepared.provider_launch_plan:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 prepared request does not match the constructed launch plan"
            )
        binding = (reservation_id, execution_id)
        if binding in self._expected_requests:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 child request binding is duplicate"
            )
        self._expected_requests[binding] = serialize_isolated_capture_child_request(
            prepared.child_request
        )

    def child_request_payload(self, reservation_id: str, execution_id: str) -> bytes:
        try:
            return self._expected_requests[(reservation_id, execution_id)]
        except KeyError:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 child request binding is stale or mismatched"
            ) from None

    def deliver_c3_child_request(
        self, execution_id: str, reservation_id: str, payload: bytes
    ) -> None:
        if payload != self.child_request_payload(reservation_id, execution_id):
            raise WindowsEffectfulCaptureCompositionError(
                "C3 child request bytes are not the exact execution binding"
            )
        self._registry.deliver_request(
            reservation_id=reservation_id,
            execution_id=execution_id,
            payload=payload,
        )

    def discard_receipt(self, receipt: ProcessCreationReceipt) -> None:
        self._registry.discard_receipt(receipt)

    def request_sha256(self, reservation_id: str, execution_id: str) -> str:
        return self._registry.request_sha256(reservation_id, execution_id)

    def validate_c3_post_resume_evidence(
        self,
        evidence: object,
        *,
        execution_id: str,
        reservation_id: str,
        resume_receipt: ResumeReceipt,
    ) -> tuple[bytes, bytes]:
        return self._registry.validate_post_resume_evidence(
            evidence,
            execution_id=execution_id,
            reservation_id=reservation_id,
            resume_receipt=resume_receipt,
        )

    def consume_c3_post_resume_evidence(
        self,
        evidence: object,
        *,
        execution_id: str,
        reservation_id: str,
        resume_receipt: ResumeReceipt,
    ) -> None:
        self._registry.consume_post_resume_evidence(
            evidence,
            execution_id=execution_id,
            reservation_id=reservation_id,
            resume_receipt=resume_receipt,
        )

    def verify_c3_captured_snapshot(
        self, lineage: tuple[str, str, str, str, str]
    ) -> VerifiedCapturedSnapshot:
        return self._registry.verify_captured_snapshot(lineage)

    def validate_c3_verified_snapshot(
        self,
        capability: VerifiedCapturedSnapshot,
        lineage: tuple[str, str, str, str, str],
    ) -> None:
        self._registry.validate_verified_snapshot(capability, lineage)

    def c3_verified_snapshot_lineage(
        self, capability: VerifiedCapturedSnapshot
    ) -> tuple[str, str, str, str, str]:
        return self._registry.verified_snapshot_lineage(capability)

    def prepare_c3_terminal(
        self,
        lineage: tuple[str, str, str, str, str],
        verified_snapshot: object | None,
    ) -> object:
        return self._registry.prepare_terminal(lineage, verified_snapshot)

    def validate_c3_terminal(
        self,
        authorization: object,
        lineage: tuple[str, str, str, str, str],
    ) -> tuple[str, str, bytes | None, bytes, bytes, bytes, bytes]:
        return self._registry.validate_terminal(authorization, lineage)

    def consume_c3_terminal(
        self,
        authorization: object,
        lineage: tuple[str, str, str, str, str],
    ) -> None:
        self._registry.consume_terminal(authorization, lineage)
        self._expected_requests.pop((lineage[3], lineage[4]), None)
        self._launch_plans.pop(lineage[3], None)

    def close(self) -> None:
        try:
            self._registry.close()
        finally:
            self._expected_requests.clear()
            self._launch_plans.clear()

    def __reduce__(self) -> object:
        raise TypeError("C3-C2 adapter cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("C3-C2 adapter cannot be pickled")


class _ProductionC3TransactionalAdapter(C3C2TransactionalAdapterForTest):
    """Fixed production C3 adapter; no deployment or native input is injectable."""

    __slots__ = (
        "_active_plans",
        "_authority",
        "_closed",
        "_issuer",
        "_pending_plan",
        "__weakref__",
    )

    def __init__(
        self,
        capture: WindowsEffectfulDailySnapshotCapture,
        authority: ValidatedProductionAuthority,
        native_api: CtypesWindowsEffectfulCaptureNativeApi,
    ) -> None:
        if type(capture) is not WindowsEffectfulDailySnapshotCapture:
            raise TypeError("production C3 adapter requires its composition root")
        if type(native_api) is not CtypesWindowsEffectfulCaptureNativeApi:
            raise TypeError("production C3 adapter requires the exact ctypes API")
        if capture._authority is not authority:
            raise TypeError("production C3 adapter requires its root authority")
        self._capture = capture
        self._authority = authority
        self._native_api = native_api
        self._registry = _C3LiveProcessRegistry()
        self._launch_plans = {}
        self._expected_requests = {}
        self._active_plans: dict[str, ProductionCapturePlan] = {}
        self._pending_plan: ProductionCapturePlan | None = None
        self._issuer: object | None = None
        self._closed = False

    def _bind_production_c2_issuer(self, issuer: object) -> None:
        self._require_open()
        required = (
            "issue_constructed_provider",
            "issue_process_creation_receipt",
            "issue_process_creation_failure",
            "issue_resume_receipt",
        )
        if self._issuer is not None or not all(
            callable(getattr(issuer, name, None)) for name in required
        ):
            raise WindowsEffectfulCaptureCompositionError(
                "production C2 issuer binding is invalid"
            )
        self._issuer = issuer

    def _revoke_production_c2_issuer(self, issuer: object) -> None:
        if self._issuer is issuer:
            self._issuer = None

    def register_capture_plan(self, plan: ProductionCapturePlan) -> None:
        self._require_open()
        if type(plan) is not ProductionCapturePlan:
            raise TypeError("production C3 adapter requires ProductionCapturePlan")
        if self._pending_plan is not None:
            raise WindowsEffectfulCaptureCompositionError(
                "production C3 already has a pending capture plan"
            )
        self._pending_plan = plan

    def construct_provider(
        self, capability: ProviderConstructionPermit, *, fail: bool = False
    ) -> ConstructedProvider:
        self._require_open()
        if fail:
            raise WindowsEffectfulCaptureCompositionError(
                "injected production C3 provider-plan failure"
            )
        reservation_id = capability.reservation_id
        plan = self._pending_plan
        if plan is None or reservation_id in self._launch_plans:
            raise WindowsEffectfulCaptureCompositionError(
                "production C3 has no unique pending plan for this reservation"
            )
        bound = bind_production_capture_plan(plan, reservation_id)
        self._launch_plans[reservation_id] = build_production_provider_launch_plan(
            bound
        )
        self._active_plans[reservation_id] = plan
        self._pending_plan = None
        issuer = self._require_issuer()
        return issuer.issue_constructed_provider(reservation_id)

    def create_process(
        self, process_intent: ProcessIntent, *, fail: bool = False
    ) -> ProcessCreationReceipt | ProcessCreationFailure:
        self._require_open()
        if fail:
            raise WindowsEffectfulCaptureCompositionError(
                "injected production C3 process creation failure"
            )
        reservation_id = process_intent.reservation_id
        if reservation_id not in self._launch_plans:
            raise WindowsEffectfulCaptureCompositionError(
                "production C3 process creation has no exact provider launch plan"
            )
        issuer = self._require_issuer()
        try:
            child = create_production_suspended_capture_child(
                reservation_id, self._native_api
            )
        except WindowsEffectfulCaptureProcessNotCreatedError:
            return issuer.issue_process_creation_failure(
                reservation_id, process_intent.intent_digest
            )
        try:
            receipt = issuer.issue_process_creation_receipt(
                reservation_id,
                process_intent.intent_digest,
                application_name=PRODUCTION_C3_PYTHON_EXECUTABLE,
                child_base_arguments=PRODUCTION_C3_CHILD_BASE_ARGUMENTS,
            )
            self._registry.register_created(
                reservation_id=reservation_id,
                process_intent_digest=process_intent.intent_digest,
                receipt=receipt,
                child=child,
            )
            return receipt
        except BaseException:
            child.close()
            raise

    def resume_thread(
        self, resume_intent: ResumeIntent, *, fail: bool = False
    ) -> ResumeReceipt:
        self._require_open()
        if fail:
            raise WindowsEffectfulCaptureCompositionError(
                "injected production C3 resume failure"
            )
        self._registry.resume(resume_intent)
        issuer = self._require_issuer()
        receipt = issuer.issue_resume_receipt(
            resume_intent.execution_id,
            resume_intent.reservation_id,
            resume_intent.intent_digest,
        )
        self._registry.retain_resume_receipt(resume_intent, receipt)
        return receipt

    def bind_execution(
        self,
        receipt: ProcessCreationReceipt,
        reservation_id: str,
        execution_id: str,
    ) -> None:
        self._require_open()
        self._registry.bind_execution(
            receipt=receipt,
            reservation_id=reservation_id,
            execution_id=execution_id,
        )
        try:
            plan = self._active_plans[reservation_id]
        except KeyError:
            raise WindowsEffectfulCaptureCompositionError(
                "production C3 execution has no exact capture plan"
            ) from None
        prepared = self._capture._prepare_execution(
            plan,
            reservation_id=reservation_id,
            execution_id=execution_id,
        )
        launch = self._launch_plans.get(reservation_id)
        if launch is None or launch != prepared.provider_launch_plan:
            raise WindowsEffectfulCaptureCompositionError(
                "production C3 request does not match its provider launch plan"
            )
        binding = (reservation_id, execution_id)
        if binding in self._expected_requests:
            raise WindowsEffectfulCaptureCompositionError(
                "production C3 child request binding is duplicate"
            )
        self._expected_requests[binding] = serialize_isolated_capture_child_request(
            prepared.child_request
        )

    def consume_c3_terminal(
        self,
        authorization: object,
        lineage: tuple[str, str, str, str, str],
    ) -> None:
        super().consume_c3_terminal(authorization, lineage)
        self._active_plans.pop(lineage[3], None)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            super().close()
        finally:
            self._active_plans.clear()
            self._pending_plan = None
            self._issuer = None

    def _require_issuer(self):
        issuer = self._issuer
        if issuer is None:
            raise WindowsEffectfulCaptureCompositionError(
                "production C3 adapter has no exact C2 issuer"
            )
        return issuer

    def _require_open(self) -> None:
        if self._closed:
            raise WindowsEffectfulCaptureCompositionError(
                "production C3 adapter is closed"
            )

    def __copy__(self) -> object:
        raise TypeError("production C3 adapter cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("production C3 adapter cannot be deep-copied")


@dataclass(frozen=True, slots=True)
class PreparedProductionCaptureExecution:
    """Nonsecret C3 material bound to one exact C2 reservation/execution pair."""

    capture_plan: ProductionCapturePlan
    bound_capture: BoundProductionCapturePlan
    provider_launch_plan: ProductionProviderLaunchPlan
    child_request: IsolatedCaptureChildRequest

    def __post_init__(self) -> None:
        if type(self.capture_plan) is not ProductionCapturePlan:
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution requires ProductionCapturePlan"
            )
        if type(self.bound_capture) is not BoundProductionCapturePlan:
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution requires BoundProductionCapturePlan"
            )
        if type(self.provider_launch_plan) is not ProductionProviderLaunchPlan:
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution requires ProductionProviderLaunchPlan"
            )
        if type(self.child_request) is not IsolatedCaptureChildRequest:
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution requires IsolatedCaptureChildRequest"
            )
        if self.bound_capture.plan is not self.capture_plan:
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution capture plan binding is inconsistent"
            )
        if self.provider_launch_plan.bound_capture is not self.bound_capture:
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution provider plan binding is inconsistent"
            )
        if self.child_request.reservation_id != self.bound_capture.reservation_id:
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution child reservation binding is inconsistent"
            )
        if (
            self.child_request.capture_request != self.capture_plan.request
            or self.child_request.c2_request_sha256
            != self.capture_plan.c2_request_digest
        ):
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution child request binding is inconsistent"
            )


class WindowsEffectfulDailySnapshotCapture:
    """C3 production composition root for the fixed reviewed deployment."""

    __slots__ = (
        "_adapter",
        "_authority",
        "_closed",
        "_production_c2_binding_issuance",
        "_production_c2_binding_issued",
        "_transactional",
        "__weakref__",
    )

    def __new__(
        cls, authority: ValidatedProductionAuthority
    ) -> WindowsEffectfulDailySnapshotCapture:
        del authority
        if cls is not WindowsEffectfulDailySnapshotCapture:
            raise TypeError("production C3 composition root cannot be subclassed")
        root = super().__new__(cls)
        with _PRODUCTION_C3_ROOT_CONSTRUCTIONS_LOCK:
            _PRODUCTION_C3_ROOT_CONSTRUCTIONS[root] = _PRODUCTION_C3_ROOT_CONSTRUCTOR
        return root

    def __init__(self, authority: ValidatedProductionAuthority) -> None:
        _admit_production_c3_root_initialization(self)
        adapter: _ProductionC3TransactionalAdapter | None = None
        transactional: WindowsTransactionalAuthority | None = None
        try:
            validated = require_validated_production_authority(authority)
            if (
                validated.provider_id != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id
                or validated.permitted_provider_operation
                != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation
            ):
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 authority is not bound to the exact Alpaca daily "
                    "snapshot operation"
                )
            self._authority = validated
            native_api = CtypesWindowsEffectfulCaptureNativeApi()
            adapter = _ProductionC3TransactionalAdapter(self, validated, native_api)
            self._closed = False
            self._production_c2_binding_issued = False
            self._adapter = adapter
            issuance = _create_production_c3_composition_issuance(
                self, validated, adapter
            )
            self._production_c2_binding_issuance = issuance
            binding = issuance.issue_binding(self)
            transactional = WindowsTransactionalAuthority._for_production_c3(binding)
            self._transactional = transactional
        except BaseException:
            _discard_production_c3_root_construction(self)
            if adapter is not None:
                try:
                    _discard_production_c3_composition_issuances(self, adapter)
                except BaseException:
                    pass
                try:
                    _discard_unconsumed_production_c3_composition_bindings(
                        self, adapter
                    )
                except BaseException:
                    pass
                try:
                    adapter.close()
                except BaseException:
                    pass
            if transactional is not None:
                try:
                    transactional.close()
                except BaseException:
                    pass
            raise

    @property
    def authority(self) -> ValidatedProductionAuthority:
        return self._authority

    @property
    def approved_account_sid(self) -> str:
        return self._authority.approved_account_sid

    @property
    def release_manifest_sha256(self) -> str:
        return self._authority.release_manifest_digest

    def prepare_capture_plan(
        self,
        request: ProductionCaptureRequest,
        requested_at_utc: datetime,
    ) -> ProductionCapturePlan:
        self._require_open()
        plan = prepare_production_capture_plan(request, requested_at_utc)
        adapter = getattr(self, "_adapter", None)
        if type(adapter) is _ProductionC3TransactionalAdapter:
            adapter.register_capture_plan(plan)
        return plan

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        failures: list[BaseException] = []
        for resource in (self._adapter, self._transactional):
            try:
                resource.close()
            except BaseException as error:
                failures.append(error)
        if failures:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 production composition cleanup was incomplete"
            ) from failures[0]

    def _prepare_execution(
        self,
        plan: ProductionCapturePlan,
        *,
        reservation_id: str,
        execution_id: str,
    ) -> PreparedProductionCaptureExecution:
        self._require_open()
        bound = bind_production_capture_plan(plan, reservation_id)
        launch = build_production_provider_launch_plan(bound)
        child_request = build_isolated_capture_child_request(
            launch,
            execution_id,
            approved_account_sid=self._authority.approved_account_sid,
            release_manifest_sha256=self._authority.release_manifest_digest,
        )
        return PreparedProductionCaptureExecution(
            capture_plan=plan,
            bound_capture=bound,
            provider_launch_plan=launch,
            child_request=child_request,
        )

    def _require_open(self) -> None:
        if self._closed:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 production capture composition is closed"
            )


def prepare_production_execution_for_test(
    capture: WindowsEffectfulDailySnapshotCapture,
    plan: ProductionCapturePlan,
    *,
    reservation_id: str,
    execution_id: str,
) -> PreparedProductionCaptureExecution:
    """Explicit test seam for the future internal C2-to-child binding step."""

    if type(capture) is not WindowsEffectfulDailySnapshotCapture:
        raise TypeError(
            "test execution preparation requires WindowsEffectfulDailySnapshotCapture"
        )
    return capture._prepare_execution(
        plan,
        reservation_id=reservation_id,
        execution_id=execution_id,
    )


def create_c3_c2_transactional_adapter_for_test(
    capture: WindowsEffectfulDailySnapshotCapture,
    plan: ProductionCapturePlan,
    launch: C3C2NativeLaunchConfigurationForTest,
    native_api: WindowsEffectfulCaptureNativeApi,
) -> C3C2TransactionalAdapterForTest:
    """Create the explicit disposable-service adapter for focused C3-C2 tests."""

    return C3C2TransactionalAdapterForTest(capture, plan, launch, native_api)


def execute_c3_c2_resume_for_test(
    capture: WindowsEffectfulDailySnapshotCapture,
    transactional: WindowsTransactionalAuthority,
    adapter: C3C2TransactionalAdapterForTest,
    plan: ProductionCapturePlan,
    process_intent: ProcessIntent,
) -> C3C2ResumedCaptureForTest:
    """Execute exactly the C3-C2 suspended-create/request/resume ordering."""

    if type(capture) is not WindowsEffectfulDailySnapshotCapture:
        raise TypeError("C3-C2 execution requires the C3 composition root")
    if type(transactional) is not WindowsTransactionalAuthority:
        raise TypeError("C3-C2 execution requires WindowsTransactionalAuthority")
    if type(adapter) is not C3C2TransactionalAdapterForTest:
        raise TypeError("C3-C2 execution requires its exact test adapter")
    if type(plan) is not ProductionCapturePlan:
        raise TypeError("C3-C2 execution requires ProductionCapturePlan")
    if type(process_intent) is not ProcessIntent:
        raise TypeError("C3-C2 execution requires ProcessIntent")
    if (
        capture._transactional is not transactional
        or adapter._capture is not capture
        or adapter._plan is not plan
    ):
        raise WindowsEffectfulCaptureCompositionError(
            "C3-C2 service composition is mismatched"
        )

    process_result = transactional.create_process(process_intent)
    if type(process_result) is not ProcessCreationReceipt:
        raise WindowsEffectfulCaptureCompositionError(
            "C3-C2 suspended creation did not issue a success receipt"
        )
    reservation_id = process_intent.reservation_id
    try:
        execution_id = transactional.record_execution(reservation_id, process_result)
    except BaseException:
        adapter.discard_receipt(process_result)
        raise
    adapter.bind_execution(process_result, reservation_id, execution_id)

    payload = adapter.child_request_payload(reservation_id, execution_id)
    transactional.deliver_c3_child_request(execution_id, reservation_id, payload)

    resume_intent = transactional.commit_resume_intent(execution_id, reservation_id)
    resume_receipt = transactional.resume_thread(resume_intent)
    return C3C2ResumedCaptureForTest(
        reservation_id=reservation_id,
        execution_id=execution_id,
        child_request_sha256=adapter.request_sha256(reservation_id, execution_id),
        resume_receipt=resume_receipt,
    )


def c3_c2_registry_snapshot_for_test(
    adapter: C3C2TransactionalAdapterForTest,
) -> tuple[tuple[str, str | None, bool, bool, bool], ...]:
    """Return semantic registry state without exposing any native handle value."""

    if type(adapter) is not C3C2TransactionalAdapterForTest:
        raise TypeError("registry inspection requires the exact C3-C2 test adapter")
    return adapter._registry.semantic_snapshot()


def observe_c3_c3b_for_test(
    adapter: C3C2TransactionalAdapterForTest,
    resumed: C3C2ResumedCaptureForTest,
) -> C3C3BObservationForTest:
    """Run the exact process-local C3-C3B observation test seam once."""

    if type(adapter) is not C3C2TransactionalAdapterForTest:
        raise TypeError("C3-C3B observation requires its exact adapter")
    if type(resumed) is not C3C2ResumedCaptureForTest:
        raise TypeError("C3-C3B observation requires its exact resumed receipt")
    return adapter._registry.observe(resumed)


def issue_c3_post_resume_evidence_for_test(
    adapter: C3C2TransactionalAdapterForTest,
    resumed: C3C2ResumedCaptureForTest,
    observation: C3C3BObservationForTest,
) -> object:
    """Issue one opaque durable-evidence permit from an exact C3-C3B result."""

    if type(adapter) is not C3C2TransactionalAdapterForTest:
        raise TypeError("C3 evidence issuance requires its exact adapter")
    if type(resumed) is not C3C2ResumedCaptureForTest:
        raise TypeError("C3 evidence issuance requires its exact resumed capture")
    if type(observation) is not C3C3BObservationForTest:
        raise TypeError("C3 evidence issuance requires its exact observation")
    return adapter._registry.issue_post_resume_evidence(resumed, observation)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
