"""C3 production composition and focused C3-C2 orchestration seam."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
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
    SuspendedCaptureChild,
    WindowsEffectfulCaptureNativeApi,
    create_suspended_capture_child_for_test,
    deliver_canonical_child_request,
    resume_suspended_capture_child,
)
from trading_bot.runtime.windows_effectful_capture_protocol import (
    IsolatedCaptureChildRequest,
    build_isolated_capture_child_request,
    serialize_isolated_capture_child_request,
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


@dataclass(slots=True)
class _C3LiveProcessEntry:
    reservation_id: str
    process_intent_digest: bytes
    receipt: ProcessCreationReceipt
    child: SuspendedCaptureChild
    execution_id: str | None = None
    request_sha256: str | None = None


class _C3LiveProcessRegistry:
    """Private, process-local native authority with no durable reconstruction."""

    __slots__ = ("_entries", "_lock")

    def __init__(self) -> None:
        self._entries: list[_C3LiveProcessEntry] = []
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
            if entry.request_sha256 is not None:
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 child request delivery was already completed"
                )
            deliver_canonical_child_request(entry.child, payload)
            entry.request_sha256 = hashlib.sha256(payload).hexdigest()

    def resume(self, intent: ResumeIntent) -> None:
        with self._lock:
            entry = self._find_bound(intent.reservation_id, intent.execution_id)
            if entry.request_sha256 is None:
                raise WindowsEffectfulCaptureCompositionError(
                    "C3 child request is not completely delivered"
                )
            resume_suspended_capture_child(entry.child)

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

    def semantic_snapshot(self) -> tuple[tuple[str, str | None, bool], ...]:
        with self._lock:
            return tuple(
                (
                    entry.reservation_id,
                    entry.execution_id,
                    entry.request_sha256 is not None,
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

        return issue_resume_receipt_for_test(
            resume_intent.execution_id,
            resume_intent.reservation_id,
            resume_intent.intent_digest,
            result_json,
            hashlib.sha256(result_json).digest(),
        )

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
) -> tuple[tuple[str, str | None, bool], ...]:
    """Return semantic registry state without exposing any native handle value."""

    if type(adapter) is not C3C2TransactionalAdapterForTest:
        raise TypeError("registry inspection requires the exact C3-C2 test adapter")
    return adapter._registry.semantic_snapshot()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
