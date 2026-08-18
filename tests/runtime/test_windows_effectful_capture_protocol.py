from __future__ import annotations

import copy
import hashlib
import json
import pickle
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from trading_bot.domain import Symbol
from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
from trading_bot.runtime.windows_effectful_capture import (
    ProductionCaptureRequest,
    bind_production_capture_plan,
    build_production_provider_launch_plan,
    prepare_production_capture_plan,
)
import trading_bot.runtime.windows_effectful_capture_protocol as protocol
from trading_bot.runtime.windows_effectful_capture_protocol import (
    MAX_C3_CHILD_REQUEST_BYTES,
    MAX_C3_CHILD_RESULT_BYTES,
    ChildCleanupStatus,
    ChildResultClassification,
    IsolatedCaptureChildRequest,
    IsolatedCaptureChildResult,
    ProviderAttemptFenceState,
    VerifiedCapturedSnapshot,
    WindowsEffectfulCaptureProtocolError,
    build_isolated_capture_child_request,
    consume_verified_captured_snapshot_for_test,
    issue_verified_captured_snapshot_for_test,
    parse_isolated_capture_child_request,
    parse_isolated_capture_child_result,
    serialize_isolated_capture_child_request,
    serialize_isolated_capture_child_result,
)

_RESERVATION = "11111111-1111-4111-8111-111111111111"
_EXECUTION = "33333333-3333-4333-8333-333333333333"
_SNAPSHOT = UUID("44444444-4444-4444-8444-444444444444")
_APPROVED_SID = "S-1-5-21-1000-1001-1002-1009"
_RELEASE_DIGEST = "ab" * 32
_ARTIFACT_DIGEST = "cd" * 32
_ARTIFACT_IDENTITY_DIGEST = "ef" * 32
_CHILD_REQUEST_DIGEST = "cddd971503d3bc1687d39668c369d1479ea45419e7c52b2302d1d77c39e4edd2"
_CHILD_RESULT_DIGEST = "5dc0c72fc8c8439f16585d82d7b7c025ba583bc4e95f3152a08e634c967642d4"


def _capture_request() -> ProductionCaptureRequest:
    return ProductionCaptureRequest(
        ordered_universe=(Symbol("AAPL"), Symbol("MSFT")),
        request_window_start_date=date(2026, 8, 13),
        request_window_end_date=date(2026, 8, 14),
        target_session_date=date(2026, 8, 17),
    )


def _launch_plan():  # type: ignore[no-untyped-def]
    plan = prepare_production_capture_plan(
        _capture_request(),
        datetime(2026, 8, 17, 14, tzinfo=UTC),
    )
    return build_production_provider_launch_plan(
        bind_production_capture_plan(plan, _RESERVATION)
    )


def _child_request() -> IsolatedCaptureChildRequest:
    return build_isolated_capture_child_request(
        _launch_plan(),
        _EXECUTION,
        approved_account_sid=_APPROVED_SID,
        release_manifest_sha256=_RELEASE_DIGEST,
    )


def _success_result() -> IsolatedCaptureChildResult:
    return IsolatedCaptureChildResult(
        reservation_id=_RESERVATION,
        execution_id=_EXECUTION,
        child_request_sha256=_CHILD_REQUEST_DIGEST,
        fence_state=ProviderAttemptFenceState.ENTERED,
        classification=ChildResultClassification.SUCCEEDED,
        cleanup_status=ChildCleanupStatus.COMPLETE,
        snapshot_id=_SNAPSHOT,
        artifact_sha256=_ARTIFACT_DIGEST,
        artifact_byte_length=1234,
        http_status=200,
        provider_request_id="req-123",
    )


def test_child_request_has_frozen_golden_bytes_hash_and_round_trip() -> None:
    request = _child_request()
    payload = serialize_isolated_capture_child_request(request)

    assert len(payload) == 1007
    assert hashlib.sha256(payload).hexdigest() == _CHILD_REQUEST_DIGEST
    assert request.sha256 == _CHILD_REQUEST_DIGEST
    assert parse_isolated_capture_child_request(payload) == request
    assert b"APCA_API_KEY_ID" not in payload
    assert b"APCA_API_SECRET_KEY" not in payload


def test_child_request_binds_exact_a1_plan_and_fixed_nonsecret_contracts() -> None:
    request = _child_request()
    launch = _launch_plan()

    assert request.reservation_id == _RESERVATION
    assert request.execution_id == _EXECUTION
    assert request.c2_request_sha256 == launch.c2_request_digest
    assert request.daily_snapshot_request_id == launch.provider_request.capture_request.request_id
    assert request.requested_at_utc == datetime(2026, 8, 17, 14, tzinfo=UTC)
    assert request.authorized_snapshot_session == launch.authorized_snapshot_session
    assert request.ordered_universe == (Symbol("AAPL"), Symbol("MSFT"))
    assert request.provider == ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
    assert request.approved_account_sid == _APPROVED_SID
    assert request.release_manifest_sha256 == _RELEASE_DIGEST


def test_child_request_rejects_bad_sid_digest_and_execution_identity() -> None:
    request = _child_request()

    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="SID"):
        replace(request, approved_account_sid="S-1-05-21")
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="SHA-256"):
        replace(request, release_manifest_sha256="AB" * 32)
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="canonical UUID"):
        replace(request, execution_id=_EXECUTION.upper())


def test_child_request_parser_rejects_unknown_duplicate_and_noncanonical_json() -> None:
    payload = serialize_isolated_capture_child_request(_child_request())
    root = json.loads(payload)

    root["unknown"] = 1
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="missing or unknown"):
        parse_isolated_capture_child_request(
            json.dumps(root, sort_keys=True, separators=(",", ":")).encode()
        )

    duplicate = payload[:-1] + b',"schema":1}'
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="strict JSON"):
        parse_isolated_capture_child_request(duplicate)

    spaced = json.dumps(json.loads(payload), sort_keys=True).encode()
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="not canonical"):
        parse_isolated_capture_child_request(spaced)


def test_child_request_parser_rejects_bom_and_oversize_transport() -> None:
    payload = serialize_isolated_capture_child_request(_child_request())

    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="BOM"):
        parse_isolated_capture_child_request(b"\xef\xbb\xbf" + payload)
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="byte length"):
        parse_isolated_capture_child_request(b"{" + b"x" * MAX_C3_CHILD_REQUEST_BYTES)


def test_child_request_parser_rejects_alternate_provider_and_credential_targets() -> None:
    root = json.loads(serialize_isolated_capture_child_request(_child_request()))
    root["provider"]["provider_id"] = "alternate-provider"
    payload = json.dumps(root, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="Alpaca"):
        parse_isolated_capture_child_request(payload)

    root = json.loads(serialize_isolated_capture_child_request(_child_request()))
    root["credential_targets"]["api_key_id"] = "alternate/key"
    payload = json.dumps(root, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="not fixed"):
        parse_isolated_capture_child_request(payload)


def test_success_result_has_frozen_golden_hash_and_round_trip() -> None:
    result = _success_result()
    payload = serialize_isolated_capture_child_result(result)

    assert len(payload) == 558
    assert hashlib.sha256(payload).hexdigest() == _CHILD_RESULT_DIGEST
    assert result.sha256 == _CHILD_RESULT_DIGEST
    assert parse_isolated_capture_child_result(payload) == result


def test_success_result_requires_entered_fence_cleanup_and_snapshot_evidence() -> None:
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="entered"):
        replace(_success_result(), fence_state=ProviderAttemptFenceState.NOT_ENTERED)
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="cleanup"):
        replace(_success_result(), cleanup_status=ChildCleanupStatus.FAILED)
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="snapshot_id"):
        replace(_success_result(), snapshot_id=None)


def test_non_success_result_cannot_claim_snapshot_artifact_authority() -> None:
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="cannot claim"):
        replace(
            _success_result(),
            classification=ChildResultClassification.SNAPSHOT_REJECTED,
        )


def test_request_invalid_is_only_structured_pre_fence_classification() -> None:
    result = IsolatedCaptureChildResult(
        reservation_id=_RESERVATION,
        execution_id=_EXECUTION,
        child_request_sha256=_CHILD_REQUEST_DIGEST,
        fence_state=ProviderAttemptFenceState.NOT_ENTERED,
        classification=ChildResultClassification.REQUEST_INVALID,
        cleanup_status=ChildCleanupStatus.COMPLETE,
    )
    assert parse_isolated_capture_child_result(
        serialize_isolated_capture_child_result(result)
    ) == result

    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="entered"):
        replace(result, classification=ChildResultClassification.SID_REJECTED)
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="transport evidence"):
        replace(result, http_status=400)


def test_transport_and_http_failure_fields_are_consistent() -> None:
    base = IsolatedCaptureChildResult(
        reservation_id=_RESERVATION,
        execution_id=_EXECUTION,
        child_request_sha256=_CHILD_REQUEST_DIGEST,
        fence_state=ProviderAttemptFenceState.ENTERED,
        classification=ChildResultClassification.TRANSPORT_FAILED,
        cleanup_status=ChildCleanupStatus.COMPLETE,
    )
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="cannot claim"):
        replace(base, http_status=503)

    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="requires"):
        replace(base, classification=ChildResultClassification.HTTP_FAILED)

    http_failure = replace(
        base,
        classification=ChildResultClassification.HTTP_FAILED,
        http_status=403,
        provider_request_id="req-safe",
    )
    assert parse_isolated_capture_child_result(
        serialize_isolated_capture_child_result(http_failure)
    ) == http_failure


def test_result_rejects_unsafe_provider_request_id() -> None:
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="printable ASCII"):
        replace(_success_result(), provider_request_id="request\nsecret")


def test_result_parser_rejects_unknown_classification_duplicate_and_oversize() -> None:
    payload = serialize_isolated_capture_child_result(_success_result())
    root = json.loads(payload)
    root["classification"] = "MAYBE"
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="closed-set"):
        parse_isolated_capture_child_result(
            json.dumps(root, sort_keys=True, separators=(",", ":")).encode()
        )

    duplicate = payload[:-1] + b',"schema":1}'
    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="strict JSON"):
        parse_isolated_capture_child_result(duplicate)

    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="byte length"):
        parse_isolated_capture_child_result(b"{" + b"x" * MAX_C3_CHILD_RESULT_BYTES)


def test_child_success_result_is_evidence_not_verifier_authority() -> None:
    result = _success_result()
    assert type(result) is IsolatedCaptureChildResult
    assert not isinstance(result, VerifiedCapturedSnapshot)
    assert not hasattr(protocol, "issue_verified_captured_snapshot")

    with pytest.raises(TypeError, match="parent verifier"):
        VerifiedCapturedSnapshot(
            reservation_id=_RESERVATION,
            execution_id=_EXECUTION,
            snapshot_id=_SNAPSHOT,
            artifact_sha256=_ARTIFACT_DIGEST,
            artifact_byte_length=1234,
            artifact_identity_sha256=_ARTIFACT_IDENTITY_DIGEST,
            child_result_sha256=_CHILD_RESULT_DIGEST,
            _issuer=object(),
            _permit=object(),  # type: ignore[arg-type]
        )


def _verified_capability() -> VerifiedCapturedSnapshot:
    return issue_verified_captured_snapshot_for_test(
        reservation_id=_RESERVATION,
        execution_id=_EXECUTION,
        snapshot_id=_SNAPSHOT,
        artifact_sha256=_ARTIFACT_DIGEST,
        artifact_byte_length=1234,
        artifact_identity_sha256=_ARTIFACT_IDENTITY_DIGEST,
        child_result_sha256=_CHILD_RESULT_DIGEST,
    )


def test_verified_snapshot_capability_is_exact_lineage_bound_and_one_shot() -> None:
    capability = _verified_capability()

    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="another C2 lineage"):
        consume_verified_captured_snapshot_for_test(
            capability,
            reservation_id="22222222-2222-4222-8222-222222222222",
            execution_id=_EXECUTION,
        )

    digest = consume_verified_captured_snapshot_for_test(
        capability,
        reservation_id=_RESERVATION,
        execution_id=_EXECUTION,
    )
    assert digest == bytes.fromhex(_ARTIFACT_DIGEST)

    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="already consumed"):
        consume_verified_captured_snapshot_for_test(
            capability,
            reservation_id=_RESERVATION,
            execution_id=_EXECUTION,
        )


def test_verified_snapshot_capability_detects_visible_field_tampering() -> None:
    capability = _verified_capability()
    object.__setattr__(capability, "artifact_sha256", "12" * 32)

    with pytest.raises(WindowsEffectfulCaptureProtocolError, match="registry binding"):
        consume_verified_captured_snapshot_for_test(
            capability,
            reservation_id=_RESERVATION,
            execution_id=_EXECUTION,
        )


def test_verified_snapshot_capability_cannot_be_pickled_or_copied() -> None:
    capability = _verified_capability()

    with pytest.raises(TypeError, match="pickled"):
        pickle.dumps(capability)
    with pytest.raises(TypeError):
        copy.copy(capability)
