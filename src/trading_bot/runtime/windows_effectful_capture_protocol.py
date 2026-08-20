"""Canonical non-effectful C3 child protocol and verifier capability contracts."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import weakref
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
    ProviderDescriptor,
)
from trading_bot.runtime.windows_effectful_capture import (
    ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
    ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
    C3_CHILD_OPERATION_VERSION,
    C3_CREDENTIAL_POLICY_VERSION,
    C3_OUTPUT_POLICY_VERSION,
    ProductionCaptureRequest,
    ProductionProviderLaunchPlan,
    WindowsEffectfulCapturePlanError,
    derive_daily_snapshot_request_id,
    prepare_production_capture_plan,
)

C3_CHILD_REQUEST_SCHEMA_VERSION = 1
C3_CHILD_RESULT_SCHEMA_VERSION = 1
MAX_C3_CHILD_REQUEST_BYTES = 16_384
MAX_C3_CHILD_RESULT_BYTES = 8_192

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SID_PATTERN = re.compile(r"^S-1-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*))+$")
_SAFE_REQUEST_ID_PATTERN = re.compile(r"^[!-~]{1,128}$")
_CHILD_REQUEST_FIELDS = frozenset(
    {
        "approved_account_sid",
        "authorized_snapshot_session",
        "c2_request",
        "c2_request_sha256",
        "credential_policy_version",
        "credential_targets",
        "daily_snapshot_request_id",
        "execution_id",
        "output_policy_version",
        "protocol",
        "provider",
        "release_manifest_sha256",
        "requested_at_utc",
        "reservation_id",
        "schema",
    }
)
_C2_REQUEST_FIELDS = frozenset(
    {
        "bar_interval",
        "child_operation_version",
        "ordered_universe",
        "output_policy_version",
        "permitted_provider_operation",
        "provider_id",
        "request_limit",
        "request_window_end_date",
        "request_window_start_date",
        "target_session_date",
    }
)
_PROVIDER_FIELDS = frozenset({"adapter_version", "feed", "operation", "provider_id"})
_CREDENTIAL_TARGET_FIELDS = frozenset({"api_key_id", "api_secret_key"})
_CHILD_RESULT_FIELDS = frozenset(
    {
        "artifact_byte_length",
        "artifact_sha256",
        "child_request_sha256",
        "classification",
        "cleanup_status",
        "execution_id",
        "fence_state",
        "http_status",
        "protocol",
        "provider_request_id",
        "reservation_id",
        "schema",
        "snapshot_id",
    }
)


class WindowsEffectfulCaptureProtocolError(ValueError):
    """A C3 child protocol value or process-local verifier capability is invalid."""


class ProviderAttemptFenceState(StrEnum):
    NOT_ENTERED = "NOT_ENTERED"
    ENTERED = "ENTERED"


class ChildResultClassification(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    REQUEST_INVALID = "REQUEST_INVALID"
    SID_REJECTED = "SID_REJECTED"
    CREDENTIAL_FAILED = "CREDENTIAL_FAILED"
    TRANSPORT_FAILED = "TRANSPORT_FAILED"
    HTTP_FAILED = "HTTP_FAILED"
    PROVIDER_RESPONSE_INVALID = "PROVIDER_RESPONSE_INVALID"
    SNAPSHOT_REJECTED = "SNAPSHOT_REJECTED"
    SERIALIZATION_FAILED = "SERIALIZATION_FAILED"
    STAGING_FAILED = "STAGING_FAILED"
    INTERNAL_FAILED = "INTERNAL_FAILED"


class ChildCleanupStatus(StrEnum):
    """Child-local secret/native cleanup completed before final result emission."""

    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class IsolatedCaptureChildRequest:
    """Exact nonsecret request supplied to the suspended C3 child before resume."""

    reservation_id: str
    execution_id: str
    capture_request: ProductionCaptureRequest
    c2_request_sha256: str
    daily_snapshot_request_id: UUID
    requested_at_utc: datetime
    authorized_snapshot_session: TradingSession
    approved_account_sid: str
    release_manifest_sha256: str
    provider: ProviderDescriptor = ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
    credential_policy_version: str = C3_CREDENTIAL_POLICY_VERSION
    output_policy_version: str = C3_OUTPUT_POLICY_VERSION
    api_key_id_credential_target: str = ALPACA_API_KEY_ID_CREDENTIAL_TARGET
    api_secret_key_credential_target: str = ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET

    def __post_init__(self) -> None:
        reservation_id = _canonical_uuid_text(self.reservation_id, "reservation_id")
        execution_id = _canonical_uuid_text(self.execution_id, "execution_id")
        if type(self.capture_request) is not ProductionCaptureRequest:
            raise WindowsEffectfulCaptureProtocolError(
                "capture_request must be ProductionCaptureRequest"
            )
        _require_sha256(self.c2_request_sha256, "c2_request_sha256")
        if type(self.daily_snapshot_request_id) is not UUID:
            raise WindowsEffectfulCaptureProtocolError(
                "daily_snapshot_request_id must be an exact UUID"
            )
        requested_at = _canonical_utc_datetime(
            self.requested_at_utc, "requested_at_utc"
        )
        if type(self.authorized_snapshot_session) is not TradingSession:
            raise WindowsEffectfulCaptureProtocolError(
                "authorized_snapshot_session must be TradingSession"
            )
        _require_canonical_sid(self.approved_account_sid)
        _require_sha256(self.release_manifest_sha256, "release_manifest_sha256")
        if self.provider != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR:
            raise WindowsEffectfulCaptureProtocolError(
                "child request provider must be the exact Alpaca descriptor"
            )
        fixed = {
            "credential_policy_version": C3_CREDENTIAL_POLICY_VERSION,
            "output_policy_version": C3_OUTPUT_POLICY_VERSION,
            "api_key_id_credential_target": ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
            "api_secret_key_credential_target": ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
        }
        for field_name, expected in fixed.items():
            if getattr(self, field_name) != expected:
                raise WindowsEffectfulCaptureProtocolError(
                    f"child request {field_name} is not fixed"
                )
        _reconcile_child_request_semantics(
            capture_request=self.capture_request,
            reservation_id=reservation_id,
            requested_at_utc=requested_at,
            c2_request_sha256=self.c2_request_sha256,
            authorized_snapshot_session=self.authorized_snapshot_session,
            daily_snapshot_request_id=self.daily_snapshot_request_id,
        )
        object.__setattr__(self, "reservation_id", reservation_id)
        object.__setattr__(self, "execution_id", execution_id)
        object.__setattr__(self, "requested_at_utc", requested_at)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(
            serialize_isolated_capture_child_request(self)
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class IsolatedCaptureChildResult:
    """Bounded sanitized child evidence; never snapshot authorization by itself."""

    reservation_id: str
    execution_id: str
    child_request_sha256: str
    fence_state: ProviderAttemptFenceState
    classification: ChildResultClassification
    cleanup_status: ChildCleanupStatus
    snapshot_id: UUID | None = None
    artifact_sha256: str | None = None
    artifact_byte_length: int | None = None
    http_status: int | None = None
    provider_request_id: str | None = None

    def __post_init__(self) -> None:
        reservation_id = _canonical_uuid_text(self.reservation_id, "reservation_id")
        execution_id = _canonical_uuid_text(self.execution_id, "execution_id")
        _require_sha256(self.child_request_sha256, "child_request_sha256")
        if type(self.fence_state) is not ProviderAttemptFenceState:
            raise WindowsEffectfulCaptureProtocolError(
                "fence_state must be ProviderAttemptFenceState"
            )
        if type(self.classification) is not ChildResultClassification:
            raise WindowsEffectfulCaptureProtocolError(
                "classification must be ChildResultClassification"
            )
        if type(self.cleanup_status) is not ChildCleanupStatus:
            raise WindowsEffectfulCaptureProtocolError(
                "cleanup_status must be ChildCleanupStatus"
            )
        _validate_result_snapshot_fields(self)
        _validate_result_transport_fields(self)
        if (
            self.classification is not ChildResultClassification.REQUEST_INVALID
            and self.fence_state is not ProviderAttemptFenceState.ENTERED
        ):
            raise WindowsEffectfulCaptureProtocolError(
                "post-request child classifications require an entered provider fence"
            )
        if self.fence_state is ProviderAttemptFenceState.NOT_ENTERED and (
            self.http_status is not None or self.provider_request_id is not None
        ):
            raise WindowsEffectfulCaptureProtocolError(
                "pre-fence child result cannot contain provider transport evidence"
            )
        _validate_result_classification_transport(self)
        object.__setattr__(self, "reservation_id", reservation_id)
        object.__setattr__(self, "execution_id", execution_id)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(serialize_isolated_capture_child_result(self)).hexdigest()


def build_isolated_capture_child_request(
    launch_plan: ProductionProviderLaunchPlan,
    execution_id: str,
    *,
    approved_account_sid: str,
    release_manifest_sha256: str,
) -> IsolatedCaptureChildRequest:
    """Bind one reviewed provider-launch plan to the exact C2 execution identity."""

    if type(launch_plan) is not ProductionProviderLaunchPlan:
        raise WindowsEffectfulCaptureProtocolError(
            "launch_plan must be ProductionProviderLaunchPlan"
        )
    bound = launch_plan.bound_capture
    capture_request = bound.daily_snapshot_request
    return IsolatedCaptureChildRequest(
        reservation_id=launch_plan.reservation_id,
        execution_id=execution_id,
        capture_request=bound.plan.request,
        c2_request_sha256=launch_plan.c2_request_digest,
        daily_snapshot_request_id=capture_request.request_id,
        requested_at_utc=capture_request.requested_at,
        authorized_snapshot_session=launch_plan.authorized_snapshot_session,
        approved_account_sid=approved_account_sid,
        release_manifest_sha256=release_manifest_sha256,
        provider=launch_plan.provider,
        credential_policy_version=launch_plan.credential_policy_version,
        output_policy_version=launch_plan.output_policy_version,
        api_key_id_credential_target=launch_plan.api_key_id_credential_target,
        api_secret_key_credential_target=launch_plan.api_secret_key_credential_target,
    )


def serialize_isolated_capture_child_request(
    request: IsolatedCaptureChildRequest,
) -> bytes:
    if type(request) is not IsolatedCaptureChildRequest:
        raise WindowsEffectfulCaptureProtocolError(
            "child request serializer requires IsolatedCaptureChildRequest"
        )
    payload = _canonical_json(
        {
            "approved_account_sid": request.approved_account_sid,
            "authorized_snapshot_session": (
                request.authorized_snapshot_session.session_date.isoformat()
            ),
            "c2_request": request.capture_request.to_c2_request_dict(),
            "c2_request_sha256": request.c2_request_sha256,
            "credential_policy_version": request.credential_policy_version,
            "credential_targets": {
                "api_key_id": request.api_key_id_credential_target,
                "api_secret_key": request.api_secret_key_credential_target,
            },
            "daily_snapshot_request_id": str(request.daily_snapshot_request_id),
            "execution_id": request.execution_id,
            "output_policy_version": request.output_policy_version,
            "protocol": C3_CHILD_OPERATION_VERSION,
            "provider": {
                "adapter_version": request.provider.adapter_version,
                "feed": request.provider.feed,
                "operation": request.provider.operation,
                "provider_id": request.provider.provider_id,
            },
            "release_manifest_sha256": request.release_manifest_sha256,
            "requested_at_utc": _canonical_timestamp(request.requested_at_utc),
            "reservation_id": request.reservation_id,
            "schema": C3_CHILD_REQUEST_SCHEMA_VERSION,
        }
    )
    if len(payload) > MAX_C3_CHILD_REQUEST_BYTES:
        raise WindowsEffectfulCaptureProtocolError(
            "child request exceeds its byte bound"
        )
    return payload


def parse_isolated_capture_child_request(payload: bytes) -> IsolatedCaptureChildRequest:
    root = _parse_canonical_object(payload, MAX_C3_CHILD_REQUEST_BYTES, "child request")
    if frozenset(root) != _CHILD_REQUEST_FIELDS:
        raise WindowsEffectfulCaptureProtocolError(
            "child request has a missing or unknown field"
        )
    if (
        type(root["schema"]) is not int
        or root["schema"] != C3_CHILD_REQUEST_SCHEMA_VERSION
    ):
        raise WindowsEffectfulCaptureProtocolError(
            "child request schema is unsupported"
        )
    if root["protocol"] != C3_CHILD_OPERATION_VERSION:
        raise WindowsEffectfulCaptureProtocolError(
            "child request protocol is unsupported"
        )
    capture_request = _capture_request_from_object(root["c2_request"])
    provider = _provider_from_object(root["provider"])
    targets = root["credential_targets"]
    if type(targets) is not dict or frozenset(targets) != _CREDENTIAL_TARGET_FIELDS:
        raise WindowsEffectfulCaptureProtocolError(
            "child request credential targets are invalid"
        )
    request = IsolatedCaptureChildRequest(
        reservation_id=root["reservation_id"],
        execution_id=root["execution_id"],
        capture_request=capture_request,
        c2_request_sha256=root["c2_request_sha256"],
        daily_snapshot_request_id=_canonical_uuid(
            root["daily_snapshot_request_id"], "daily_snapshot_request_id"
        ),
        requested_at_utc=_parse_canonical_timestamp(root["requested_at_utc"]),
        authorized_snapshot_session=TradingSession(
            _parse_canonical_date(
                root["authorized_snapshot_session"], "authorized_snapshot_session"
            )
        ),
        approved_account_sid=root["approved_account_sid"],
        release_manifest_sha256=root["release_manifest_sha256"],
        provider=provider,
        credential_policy_version=root["credential_policy_version"],
        output_policy_version=root["output_policy_version"],
        api_key_id_credential_target=targets["api_key_id"],
        api_secret_key_credential_target=targets["api_secret_key"],
    )
    if serialize_isolated_capture_child_request(request) != payload:
        raise WindowsEffectfulCaptureProtocolError(
            "child request bytes are not canonical"
        )
    return request


def serialize_isolated_capture_child_result(
    result: IsolatedCaptureChildResult,
) -> bytes:
    if type(result) is not IsolatedCaptureChildResult:
        raise WindowsEffectfulCaptureProtocolError(
            "child result serializer requires IsolatedCaptureChildResult"
        )
    payload = _canonical_json(
        {
            "artifact_byte_length": result.artifact_byte_length,
            "artifact_sha256": result.artifact_sha256,
            "child_request_sha256": result.child_request_sha256,
            "classification": result.classification.value,
            "cleanup_status": result.cleanup_status.value,
            "execution_id": result.execution_id,
            "fence_state": result.fence_state.value,
            "http_status": result.http_status,
            "protocol": C3_CHILD_OPERATION_VERSION,
            "provider_request_id": result.provider_request_id,
            "reservation_id": result.reservation_id,
            "schema": C3_CHILD_RESULT_SCHEMA_VERSION,
            "snapshot_id": None
            if result.snapshot_id is None
            else str(result.snapshot_id),
        }
    )
    if len(payload) > MAX_C3_CHILD_RESULT_BYTES:
        raise WindowsEffectfulCaptureProtocolError(
            "child result exceeds its byte bound"
        )
    return payload


def parse_isolated_capture_child_result(payload: bytes) -> IsolatedCaptureChildResult:
    root = _parse_canonical_object(payload, MAX_C3_CHILD_RESULT_BYTES, "child result")
    if frozenset(root) != _CHILD_RESULT_FIELDS:
        raise WindowsEffectfulCaptureProtocolError(
            "child result has a missing or unknown field"
        )
    if (
        type(root["schema"]) is not int
        or root["schema"] != C3_CHILD_RESULT_SCHEMA_VERSION
    ):
        raise WindowsEffectfulCaptureProtocolError("child result schema is unsupported")
    if root["protocol"] != C3_CHILD_OPERATION_VERSION:
        raise WindowsEffectfulCaptureProtocolError(
            "child result protocol is unsupported"
        )
    try:
        fence_state = ProviderAttemptFenceState(root["fence_state"])
        classification = ChildResultClassification(root["classification"])
        cleanup_status = ChildCleanupStatus(root["cleanup_status"])
    except (TypeError, ValueError) as error:
        raise WindowsEffectfulCaptureProtocolError(
            "child result contains an unsupported closed-set value"
        ) from error
    snapshot_id = (
        None
        if root["snapshot_id"] is None
        else _canonical_uuid(root["snapshot_id"], "snapshot_id")
    )
    result = IsolatedCaptureChildResult(
        reservation_id=root["reservation_id"],
        execution_id=root["execution_id"],
        child_request_sha256=root["child_request_sha256"],
        fence_state=fence_state,
        classification=classification,
        cleanup_status=cleanup_status,
        snapshot_id=snapshot_id,
        artifact_sha256=root["artifact_sha256"],
        artifact_byte_length=root["artifact_byte_length"],
        http_status=root["http_status"],
        provider_request_id=root["provider_request_id"],
    )
    if serialize_isolated_capture_child_result(result) != payload:
        raise WindowsEffectfulCaptureProtocolError(
            "child result bytes are not canonical"
        )
    return result


class _VerifiedSnapshotPermit:
    __slots__ = ("consumed", "lock", "__weakref__")

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.consumed = False


class _VerifiedSnapshotIssuer:
    pass


_PRODUCTION_VERIFIED_SNAPSHOT_ISSUER = _VerifiedSnapshotIssuer()
_TEST_VERIFIED_SNAPSHOT_ISSUER = _VerifiedSnapshotIssuer()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class VerifiedCapturedSnapshot:
    """Opaque process-local proof of successful parent artifact verification."""

    session_id: str
    attempt_id: str
    claim_id: str
    reservation_id: str
    execution_id: str
    snapshot_id: UUID
    artifact_sha256: str
    artifact_byte_length: int
    artifact_identity_sha256: str
    child_result_sha256: str
    _issuer: object = field(repr=False, compare=False)
    _permit: _VerifiedSnapshotPermit = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._issuer not in (
            _PRODUCTION_VERIFIED_SNAPSHOT_ISSUER,
            _TEST_VERIFIED_SNAPSHOT_ISSUER,
        ):
            raise TypeError(
                "VerifiedCapturedSnapshot can only be issued by the parent verifier"
            )
        _canonical_uuid_text(self.session_id, "session_id")
        _canonical_uuid_text(self.attempt_id, "attempt_id")
        _canonical_uuid_text(self.claim_id, "claim_id")
        _canonical_uuid_text(self.reservation_id, "reservation_id")
        _canonical_uuid_text(self.execution_id, "execution_id")
        if type(self.snapshot_id) is not UUID:
            raise WindowsEffectfulCaptureProtocolError(
                "snapshot_id must be an exact UUID"
            )
        _require_sha256(self.artifact_sha256, "artifact_sha256")
        _require_snapshot_byte_length(self.artifact_byte_length)
        _require_sha256(self.artifact_identity_sha256, "artifact_identity_sha256")
        _require_sha256(self.child_result_sha256, "child_result_sha256")
        if type(self._permit) is not _VerifiedSnapshotPermit:
            raise TypeError("VerifiedCapturedSnapshot permit is invalid")

    def __reduce__(self) -> object:
        raise TypeError("VerifiedCapturedSnapshot cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        raise TypeError("VerifiedCapturedSnapshot cannot be pickled")


@dataclass(frozen=True, slots=True)
class _VerifiedSnapshotIssuance:
    capability: weakref.ReferenceType[VerifiedCapturedSnapshot]
    values: tuple[object, ...]
    issuer: object


_VERIFIED_SNAPSHOT_REGISTRY_LOCK = threading.Lock()
_VERIFIED_SNAPSHOT_REGISTRY: weakref.WeakKeyDictionary[
    _VerifiedSnapshotPermit, _VerifiedSnapshotIssuance
] = weakref.WeakKeyDictionary()


def issue_verified_captured_snapshot_for_test(
    *,
    session_id: str | None = None,
    attempt_id: str | None = None,
    claim_id: str | None = None,
    reservation_id: str,
    execution_id: str,
    snapshot_id: UUID,
    artifact_sha256: str,
    artifact_byte_length: int,
    artifact_identity_sha256: str,
    child_result_sha256: str,
) -> VerifiedCapturedSnapshot:
    """Explicit test seam isolated from the C3-D1 production verifier issuer."""

    session_id = reservation_id if session_id is None else session_id
    attempt_id = reservation_id if attempt_id is None else attempt_id
    claim_id = reservation_id if claim_id is None else claim_id
    return _issue_verified_captured_snapshot(
        session_id=session_id,
        attempt_id=attempt_id,
        claim_id=claim_id,
        reservation_id=reservation_id,
        execution_id=execution_id,
        snapshot_id=snapshot_id,
        artifact_sha256=artifact_sha256,
        artifact_byte_length=artifact_byte_length,
        artifact_identity_sha256=artifact_identity_sha256,
        child_result_sha256=child_result_sha256,
        issuer=_TEST_VERIFIED_SNAPSHOT_ISSUER,
    )


def _issue_production_verified_captured_snapshot(
    *,
    session_id: str,
    attempt_id: str,
    claim_id: str,
    reservation_id: str,
    execution_id: str,
    snapshot_id: UUID,
    artifact_sha256: str,
    artifact_byte_length: int,
    artifact_identity_sha256: str,
    child_result_sha256: str,
) -> VerifiedCapturedSnapshot:
    return _issue_verified_captured_snapshot(
        session_id=session_id,
        attempt_id=attempt_id,
        claim_id=claim_id,
        reservation_id=reservation_id,
        execution_id=execution_id,
        snapshot_id=snapshot_id,
        artifact_sha256=artifact_sha256,
        artifact_byte_length=artifact_byte_length,
        artifact_identity_sha256=artifact_identity_sha256,
        child_result_sha256=child_result_sha256,
        issuer=_PRODUCTION_VERIFIED_SNAPSHOT_ISSUER,
    )


def _issue_verified_captured_snapshot(
    *,
    session_id: str,
    attempt_id: str,
    claim_id: str,
    reservation_id: str,
    execution_id: str,
    snapshot_id: UUID,
    artifact_sha256: str,
    artifact_byte_length: int,
    artifact_identity_sha256: str,
    child_result_sha256: str,
    issuer: _VerifiedSnapshotIssuer,
) -> VerifiedCapturedSnapshot:
    permit = _VerifiedSnapshotPermit()
    capability = VerifiedCapturedSnapshot(
        session_id=session_id,
        attempt_id=attempt_id,
        claim_id=claim_id,
        reservation_id=reservation_id,
        execution_id=execution_id,
        snapshot_id=snapshot_id,
        artifact_sha256=artifact_sha256,
        artifact_byte_length=artifact_byte_length,
        artifact_identity_sha256=artifact_identity_sha256,
        child_result_sha256=child_result_sha256,
        _issuer=issuer,
        _permit=permit,
    )
    issuance = _VerifiedSnapshotIssuance(
        capability=weakref.ref(capability),
        values=_verified_snapshot_visible_values(capability),
        issuer=issuer,
    )
    with _VERIFIED_SNAPSHOT_REGISTRY_LOCK:
        _VERIFIED_SNAPSHOT_REGISTRY[permit] = issuance
    return capability


def _validate_production_verified_captured_snapshot(
    capability: VerifiedCapturedSnapshot,
) -> tuple[object, ...]:
    """Validate exact production issuance without consuming terminal authority."""

    if type(capability) is not VerifiedCapturedSnapshot:
        raise TypeError("verified snapshot validation requires exact capability")
    if capability._issuer is not _PRODUCTION_VERIFIED_SNAPSHOT_ISSUER:
        raise TypeError("production verifier requires a production-issued capability")
    permit = capability._permit
    if type(permit) is not _VerifiedSnapshotPermit:
        raise WindowsEffectfulCaptureProtocolError(
            "verified snapshot registry binding is invalid"
        )
    with permit.lock:
        with _VERIFIED_SNAPSHOT_REGISTRY_LOCK:
            issuance = _VERIFIED_SNAPSHOT_REGISTRY.get(permit)
            values = _verified_snapshot_visible_values(capability)
            if (
                permit.consumed
                or issuance is None
                or issuance.capability() is not capability
                or issuance.issuer is not _PRODUCTION_VERIFIED_SNAPSHOT_ISSUER
                or issuance.values != values
            ):
                raise WindowsEffectfulCaptureProtocolError(
                    "verified snapshot exact-object registry binding mismatch"
                )
            return issuance.values


def consume_verified_captured_snapshot_for_test(
    capability: VerifiedCapturedSnapshot,
    *,
    reservation_id: str,
    execution_id: str,
) -> bytes:
    """Consume one exact test-issued verifier capability and return its digest bytes."""

    if type(capability) is not VerifiedCapturedSnapshot:
        raise TypeError("verified snapshot consumption requires exact capability")
    if capability._issuer is not _TEST_VERIFIED_SNAPSHOT_ISSUER:
        raise TypeError("test consumer requires a test-issued verified snapshot")
    expected_reservation = _canonical_uuid_text(reservation_id, "reservation_id")
    expected_execution = _canonical_uuid_text(execution_id, "execution_id")
    permit = capability._permit
    if type(permit) is not _VerifiedSnapshotPermit:
        raise WindowsEffectfulCaptureProtocolError(
            "verified snapshot registry binding is invalid"
        )
    with permit.lock:
        with _VERIFIED_SNAPSHOT_REGISTRY_LOCK:
            issuance = _VERIFIED_SNAPSHOT_REGISTRY.get(permit)
            if permit.consumed or issuance is None:
                raise WindowsEffectfulCaptureProtocolError(
                    "verified snapshot was already consumed or not issued"
                )
            if (
                issuance.capability() is not capability
                or issuance.issuer is not capability._issuer
                or issuance.values != _verified_snapshot_visible_values(capability)
            ):
                raise WindowsEffectfulCaptureProtocolError(
                    "verified snapshot exact-object registry binding mismatch"
                )
            if (
                capability.reservation_id != expected_reservation
                or capability.execution_id != expected_execution
            ):
                raise WindowsEffectfulCaptureProtocolError(
                    "verified snapshot belongs to another C2 lineage"
                )
            del _VERIFIED_SNAPSHOT_REGISTRY[permit]
            permit.consumed = True
    return bytes.fromhex(capability.artifact_sha256)


def _reconcile_child_request_semantics(
    *,
    capture_request: ProductionCaptureRequest,
    reservation_id: str,
    requested_at_utc: datetime,
    c2_request_sha256: str,
    authorized_snapshot_session: TradingSession,
    daily_snapshot_request_id: UUID,
) -> None:
    try:
        plan = prepare_production_capture_plan(capture_request, requested_at_utc)
        expected_request_id = derive_daily_snapshot_request_id(plan, reservation_id)
    except WindowsEffectfulCapturePlanError as error:
        raise WindowsEffectfulCaptureProtocolError(
            "child request C2-to-snapshot bridge is inconsistent"
        ) from error
    if plan.c2_request_digest != c2_request_sha256:
        raise WindowsEffectfulCaptureProtocolError(
            "child request C2 request digest is inconsistent"
        )
    if plan.authorized_snapshot_session != authorized_snapshot_session:
        raise WindowsEffectfulCaptureProtocolError(
            "child request authorized snapshot session is inconsistent"
        )
    if expected_request_id != daily_snapshot_request_id:
        raise WindowsEffectfulCaptureProtocolError(
            "child request daily snapshot identity is inconsistent"
        )


def _verified_snapshot_visible_values(
    capability: VerifiedCapturedSnapshot,
) -> tuple[object, ...]:
    return (
        capability.session_id,
        capability.attempt_id,
        capability.claim_id,
        capability.reservation_id,
        capability.execution_id,
        capability.snapshot_id,
        capability.artifact_sha256,
        capability.artifact_byte_length,
        capability.artifact_identity_sha256,
        capability.child_result_sha256,
    )


def _validate_result_snapshot_fields(result: IsolatedCaptureChildResult) -> None:
    fields = (result.snapshot_id, result.artifact_sha256, result.artifact_byte_length)
    if result.classification is ChildResultClassification.SUCCEEDED:
        if result.fence_state is not ProviderAttemptFenceState.ENTERED:
            raise WindowsEffectfulCaptureProtocolError(
                "successful child result requires an entered provider fence"
            )
        if result.cleanup_status is not ChildCleanupStatus.COMPLETE:
            raise WindowsEffectfulCaptureProtocolError(
                "successful child result requires complete child-local cleanup"
            )
        if result.snapshot_id is None:
            raise WindowsEffectfulCaptureProtocolError(
                "successful child result requires snapshot_id"
            )
        if type(result.snapshot_id) is not UUID:
            raise WindowsEffectfulCaptureProtocolError(
                "snapshot_id must be an exact UUID"
            )
        _require_sha256(result.artifact_sha256, "artifact_sha256")
        _require_snapshot_byte_length(result.artifact_byte_length)
    elif any(value is not None for value in fields):
        raise WindowsEffectfulCaptureProtocolError(
            "non-success child result cannot claim snapshot artifact authority"
        )


def _validate_result_transport_fields(result: IsolatedCaptureChildResult) -> None:
    if result.http_status is not None and (
        type(result.http_status) is not int or not 100 <= result.http_status <= 599
    ):
        raise WindowsEffectfulCaptureProtocolError(
            "http_status must be an exact HTTP status integer or None"
        )
    if result.provider_request_id is not None and (
        type(result.provider_request_id) is not str
        or _SAFE_REQUEST_ID_PATTERN.fullmatch(result.provider_request_id) is None
    ):
        raise WindowsEffectfulCaptureProtocolError(
            "provider_request_id must be bounded printable ASCII or None"
        )


def _validate_result_classification_transport(
    result: IsolatedCaptureChildResult,
) -> None:
    no_http = {
        ChildResultClassification.REQUEST_INVALID,
        ChildResultClassification.SID_REJECTED,
        ChildResultClassification.CREDENTIAL_FAILED,
        ChildResultClassification.TRANSPORT_FAILED,
    }
    if result.classification in no_http and (
        result.http_status is not None or result.provider_request_id is not None
    ):
        raise WindowsEffectfulCaptureProtocolError(
            "pre-HTTP child classification cannot claim provider response evidence"
        )
    if result.classification is ChildResultClassification.HTTP_FAILED:
        if result.http_status is None or result.http_status == 200:
            raise WindowsEffectfulCaptureProtocolError(
                "HTTP failure requires a non-200 sanitized HTTP status"
            )
    post_http_success = {
        ChildResultClassification.PROVIDER_RESPONSE_INVALID,
        ChildResultClassification.SNAPSHOT_REJECTED,
        ChildResultClassification.SERIALIZATION_FAILED,
        ChildResultClassification.STAGING_FAILED,
        ChildResultClassification.SUCCEEDED,
    }
    if result.classification in post_http_success and result.http_status != 200:
        raise WindowsEffectfulCaptureProtocolError(
            "post-HTTP child classification requires HTTP status 200"
        )


def _capture_request_from_object(value: object) -> ProductionCaptureRequest:
    if type(value) is not dict or frozenset(value) != _C2_REQUEST_FIELDS:
        raise WindowsEffectfulCaptureProtocolError(
            "child request c2_request is not the exact capture_request/v2 object"
        )
    try:
        symbols = _symbols_from_object(value["ordered_universe"])
        capture_request = ProductionCaptureRequest(
            ordered_universe=symbols,
            request_window_start_date=_parse_canonical_date(
                value["request_window_start_date"], "request_window_start_date"
            ),
            request_window_end_date=_parse_canonical_date(
                value["request_window_end_date"], "request_window_end_date"
            ),
            target_session_date=_parse_canonical_date(
                value["target_session_date"], "target_session_date"
            ),
        )
    except WindowsEffectfulCapturePlanError as error:
        raise WindowsEffectfulCaptureProtocolError(
            "child request c2_request violates the C3 capture contract"
        ) from error
    if _canonical_json(value) != capture_request.canonical_c2_request_json():
        raise WindowsEffectfulCaptureProtocolError(
            "child request c2_request fixed semantics are inconsistent"
        )
    return capture_request


def _provider_from_object(value: object) -> ProviderDescriptor:
    if type(value) is not dict or frozenset(value) != _PROVIDER_FIELDS:
        raise WindowsEffectfulCaptureProtocolError("child request provider is invalid")
    try:
        provider = ProviderDescriptor(
            provider_id=value["provider_id"],
            adapter_version=value["adapter_version"],
            operation=value["operation"],
            feed=value["feed"],
        )
    except (TypeError, ValueError) as error:
        raise WindowsEffectfulCaptureProtocolError(
            "child request provider is invalid"
        ) from error
    if provider != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR:
        raise WindowsEffectfulCaptureProtocolError(
            "child request provider must be the exact Alpaca descriptor"
        )
    return provider


def _symbols_from_object(value: object) -> tuple[Symbol, ...]:
    if type(value) is not list or not value:
        raise WindowsEffectfulCaptureProtocolError(
            "child request ordered_universe must be a nonempty list"
        )
    symbols: list[Symbol] = []
    for entry in value:
        if type(entry) is not str:
            raise WindowsEffectfulCaptureProtocolError(
                "child request ordered_universe members must be strings"
            )
        try:
            symbol = Symbol(entry)
        except (TypeError, ValueError) as error:
            raise WindowsEffectfulCaptureProtocolError(
                "child request ordered_universe member is invalid"
            ) from error
        if str(symbol) != entry:
            raise WindowsEffectfulCaptureProtocolError(
                "child request ordered_universe member is not canonical"
            )
        symbols.append(symbol)
    if len(set(symbols)) != len(symbols):
        raise WindowsEffectfulCaptureProtocolError(
            "child request ordered_universe must be duplicate-free"
        )
    return tuple(symbols)


def _parse_canonical_object(payload: bytes, limit: int, label: str) -> dict[str, Any]:
    if type(payload) is not bytes:
        raise WindowsEffectfulCaptureProtocolError(f"{label} must be exact bytes")
    if not payload or len(payload) > limit:
        raise WindowsEffectfulCaptureProtocolError(f"{label} byte length is invalid")
    if payload.startswith(b"\xef\xbb\xbf"):
        raise WindowsEffectfulCaptureProtocolError(f"{label} must not contain a BOM")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise WindowsEffectfulCaptureProtocolError(
            f"{label} must be valid UTF-8"
        ) from error
    try:
        root = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonstandard_constant,
        )
    except (json.JSONDecodeError, WindowsEffectfulCaptureProtocolError) as error:
        raise WindowsEffectfulCaptureProtocolError(
            f"{label} must be strict JSON"
        ) from error
    if type(root) is not dict:
        raise WindowsEffectfulCaptureProtocolError(f"{label} root must be an object")
    return root


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _canonical_uuid(value: object, field_name: str) -> UUID:
    text = _canonical_uuid_text(value, field_name)
    return UUID(text)


def _canonical_uuid_text(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise WindowsEffectfulCaptureProtocolError(
            f"{field_name} must be a canonical UUID string"
        )
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise WindowsEffectfulCaptureProtocolError(
            f"{field_name} must be a canonical UUID string"
        ) from error
    if str(parsed) != value:
        raise WindowsEffectfulCaptureProtocolError(
            f"{field_name} must be a canonical UUID string"
        )
    return value


def _require_sha256(value: object, field_name: str) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise WindowsEffectfulCaptureProtocolError(
            f"{field_name} must be lowercase SHA-256 text"
        )


def _require_snapshot_byte_length(value: object) -> None:
    if (
        type(value) is not int
        or value <= 0
        or value > MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES
    ):
        raise WindowsEffectfulCaptureProtocolError(
            "artifact_byte_length must be within the daily snapshot byte bound"
        )


def _require_canonical_sid(value: object) -> None:
    if (
        type(value) is not str
        or len(value) > 184
        or _SID_PATTERN.fullmatch(value) is None
    ):
        raise WindowsEffectfulCaptureProtocolError(
            "approved_account_sid must be canonical SID text"
        )


def _canonical_utc_datetime(value: object, field_name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise WindowsEffectfulCaptureProtocolError(
            f"{field_name} must be a timezone-aware datetime"
        )
    return value.astimezone(UTC)


def _canonical_timestamp(value: datetime) -> str:
    normalized = _canonical_utc_datetime(value, "timestamp")
    if normalized.microsecond:
        return normalized.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_canonical_timestamp(value: object) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise WindowsEffectfulCaptureProtocolError(
            "requested_at_utc must be canonical UTC timestamp text"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise WindowsEffectfulCaptureProtocolError(
            "requested_at_utc must be canonical UTC timestamp text"
        ) from error
    normalized = _canonical_utc_datetime(parsed, "requested_at_utc")
    if _canonical_timestamp(normalized) != value:
        raise WindowsEffectfulCaptureProtocolError(
            "requested_at_utc must be canonical UTC timestamp text"
        )
    return normalized


def _parse_canonical_date(value: object, field_name: str) -> date:
    if type(value) is not str:
        raise WindowsEffectfulCaptureProtocolError(
            f"{field_name} must be canonical date text"
        )
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise WindowsEffectfulCaptureProtocolError(
            f"{field_name} must be canonical date text"
        ) from error
    if parsed.isoformat() != value:
        raise WindowsEffectfulCaptureProtocolError(
            f"{field_name} must be canonical date text"
        )
    return parsed


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WindowsEffectfulCaptureProtocolError(
                "protocol JSON contains a duplicate key"
            )
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise WindowsEffectfulCaptureProtocolError(
        f"protocol JSON constant {value!r} is unsupported"
    )
