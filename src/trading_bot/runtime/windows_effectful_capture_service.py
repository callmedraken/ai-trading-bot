"""C3 production composition with focused C3-C2/C3-C3B test seams."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
from trading_bot.runtime.windows_authority import WindowsAuthorityError
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
    C3ParentCleanupStatus,
    C3ProcessOutcomeStatus,
    C3ResultTransportStatus,
    SuspendedCaptureChild,
    WindowsEffectfulCaptureNativeApi,
    create_suspended_capture_child_for_test,
    deliver_canonical_child_request,
    observe_resumed_capture_child,
    resume_suspended_capture_child,
)
from trading_bot.runtime.windows_effectful_capture_protocol import (
    IsolatedCaptureChildRequest,
    IsolatedCaptureChildResult,
    ProviderAttemptFenceState,
    WindowsEffectfulCaptureProtocolError,
    build_isolated_capture_child_request,
    parse_isolated_capture_child_result,
    serialize_isolated_capture_child_request,
    serialize_isolated_capture_child_result,
)
from trading_bot.runtime.windows_transactional_authority import (
    ConstructedProvider,
    ProcessCreationFailure,
    ProcessCreationReceipt,
    ProcessIntent,
    ProviderConstructionPermit,
    ResumeIntent,
    ResumeReceipt,
    WindowsTransactionalAuthority,
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
    staging_path: str
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
_MAX_C3_CLEANUP_EVIDENCE_BYTES = 1024


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


@dataclass(slots=True)
class _C3LiveProcessEntry:
    reservation_id: str
    process_intent_digest: bytes
    receipt: ProcessCreationReceipt
    child: SuspendedCaptureChild
    execution_id: str | None = None
    request_delivery_attempted: bool = False
    request_sha256: str | None = None
    resume_receipt: ResumeReceipt | None = None
    observed: bool = False
    observation: C3C3BObservationForTest | None = None
    observation_snapshot: _C3ObservationSnapshot | None = None
    evidence_issuance: _C3PostResumeEvidenceIssuance | None = None
    evidence_consumed: bool = False


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
        deliver_canonical_child_request(child, payload)
        with self._lock:
            entry = self._find_bound(reservation_id, execution_id)
            if entry.child is not child or entry.request_sha256 is not None:
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 child request delivery provenance changed"
                )
            entry.request_sha256 = hashlib.sha256(payload).hexdigest()

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
        child = create_suspended_capture_child_for_test(
            application_name=launch.application_name,
            arguments=launch.arguments,
            current_directory=launch.current_directory,
            controlled_temp_directory=launch.controlled_temp_directory,
            staging_path=launch.staging_path,
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
    """C3 production composition root with no external effects in A3."""

    __slots__ = ("_authority", "_closed", "_transactional")

    def __init__(self, authority: ValidatedProductionAuthority) -> None:
        validated = require_validated_production_authority(authority)
        if (
            validated.provider_id != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id
            or validated.permitted_provider_operation
            != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation
        ):
            raise WindowsEffectfulCaptureCompositionError(
                "C3 authority is not bound to the exact Alpaca daily snapshot operation"
            )
        self._authority = validated
        self._transactional = WindowsTransactionalAuthority(validated)
        self._closed = False

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
        return prepare_production_capture_plan(request, requested_at_utc)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._transactional.close()

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
