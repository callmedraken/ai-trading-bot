from __future__ import annotations

import pickle
from copy import copy, deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
from inspect import signature

import pytest

import trading_bot.runtime.windows_effectful_capture_service as service_module
import trading_bot.runtime.windows_transactional_authority as authority_module
from trading_bot.domain import Symbol
from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    WindowsAuthorityBootstrap,
    WindowsAuthorityError,
)
from trading_bot.runtime.windows_authority_schema import (
    PRODUCTION_SCHEMA_ARTIFACT_SHA256,
    PRODUCTION_SCHEMA_ID,
    PRODUCTION_SCHEMA_VERSION,
    ProductionAuthorityEvidence,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    acquire_validated_production_authority_for_test,
)
from trading_bot.runtime.windows_effectful_capture import ProductionCaptureRequest
from trading_bot.runtime.windows_effectful_capture_native import (
    PRODUCTION_C3_CHILD_BASE_ARGUMENTS,
    PRODUCTION_C3_CHILD_MODULE,
    PRODUCTION_C3_CONTROLLED_TEMP_ROOT,
    PRODUCTION_C3_PYTHON_EXECUTABLE,
    PRODUCTION_C3_RUNTIME_ROOT,
    CtypesWindowsEffectfulCaptureNativeApi,
)
from trading_bot.runtime.windows_effectful_capture_service import (
    WindowsEffectfulCaptureCompositionError,
    WindowsEffectfulDailySnapshotCapture,
    prepare_production_execution_for_test,
)
from trading_bot.runtime.windows_transactional_authority import (
    ExternalAuthorityBoundaryUnavailable,
    WindowsTransactionalAuthority,
    issue_constructed_provider_for_test,
)

_RESERVATION = "11111111-1111-4111-8111-111111111111"
_EXECUTION = "33333333-3333-4333-8333-333333333333"
_OTHER_RESERVATION = "44444444-4444-4444-8444-444444444444"


def _authority() -> ValidatedProductionAuthority:
    bootstrap = WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=7,
        machine_authority_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        authority_epoch_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        signing_key_id="test-key",
        approved_account_sid="S-1-5-21-1",
        database_path=str(PRODUCTION_AUTHORITY_PATHS.database),
        output_root=str(PRODUCTION_AUTHORITY_PATHS.capture_output),
        provider_id=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        permitted_provider_operation=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
        authority_policy_version="authority-policy/v1",
        claim_policy_version="claim-policy/v1",
        database_identity_digest="ab" * 32,
    )
    evidence = ProductionAuthorityEvidence(
        database_path=str(PRODUCTION_AUTHORITY_PATHS.database),
        schema_id=PRODUCTION_SCHEMA_ID,
        schema_version=PRODUCTION_SCHEMA_VERSION,
        schema_digest=PRODUCTION_SCHEMA_ARTIFACT_SHA256,
        metadata_digest="33" * 32,
        migration_id="migration-v1",
        release_manifest_digest="11" * 32,
        sqlite_build_manifest_digest="22" * 32,
    )
    return acquire_validated_production_authority_for_test(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        production_evidence=evidence,
    )


def _request() -> ProductionCaptureRequest:
    return ProductionCaptureRequest(
        ordered_universe=(Symbol("AAPL"), Symbol("MSFT")),
        request_window_start_date=date(2026, 8, 17),
        request_window_end_date=date(2026, 8, 17),
        target_session_date=date(2026, 8, 18),
    )


class _FakeTransactionalAuthority:
    def __init__(
        self, authority: ValidatedProductionAuthority, adapter: object | None = None
    ) -> None:
        self.authority = authority
        self.adapter = adapter
        self.close_count = 0

    @classmethod
    def _for_production_c3(
        cls, authority: ValidatedProductionAuthority, adapter: object
    ) -> _FakeTransactionalAuthority:
        instance = cls(authority, adapter)
        adapter._bind_production_c2_issuer(_FakeProductionIssuer())
        return instance

    def close(self) -> None:
        self.close_count += 1


class _FakeProductionIssuer:
    def issue_constructed_provider(self, reservation_id: str) -> object:
        raise AssertionError(reservation_id)

    def issue_process_creation_receipt(self, *args: object, **kwargs: object) -> object:
        raise AssertionError((args, kwargs))

    def issue_process_creation_failure(self, *args: object) -> object:
        raise AssertionError(args)

    def issue_resume_receipt(self, *args: object) -> object:
        raise AssertionError(args)


def _capture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[WindowsEffectfulDailySnapshotCapture, ValidatedProductionAuthority]:
    authority = _authority()
    monkeypatch.setattr(
        service_module,
        "require_validated_production_authority",
        lambda candidate: candidate,
    )
    monkeypatch.setattr(
        service_module,
        "WindowsTransactionalAuthority",
        _FakeTransactionalAuthority,
    )
    monkeypatch.setattr(
        CtypesWindowsEffectfulCaptureNativeApi,
        "__init__",
        lambda self: None,
    )
    return WindowsEffectfulDailySnapshotCapture(authority), authority


def test_production_composition_rejects_test_c1_capability() -> None:
    with pytest.raises(WindowsAuthorityError, match="non-production provenance"):
        WindowsEffectfulDailySnapshotCapture(_authority())


def test_public_constructor_has_no_injection_surface() -> None:
    assert tuple(signature(WindowsEffectfulDailySnapshotCapture).parameters) == (
        "authority",
    )
    assert tuple(signature(WindowsTransactionalAuthority).parameters) == ("authority",)


def test_bare_production_transactional_authority_remains_effectfully_inert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    monkeypatch.setattr(
        authority_module,
        "require_validated_production_authority",
        lambda value: value,
    )

    transactional = WindowsTransactionalAuthority(authority)
    try:
        assert transactional._context.external_adapter is None
        assert transactional._production_c3_issuer is None
    finally:
        transactional.close()


def test_composition_retains_exact_c1_facts_and_owns_c2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture, authority = _capture(monkeypatch)

    assert capture.authority is authority
    assert capture.approved_account_sid == authority.approved_account_sid
    assert capture.release_manifest_sha256 == authority.release_manifest_digest
    assert capture._transactional.authority is authority
    assert capture._transactional.adapter is capture._adapter
    assert type(capture._adapter._native_api) is CtypesWindowsEffectfulCaptureNativeApi


def test_fixed_production_deployment_and_private_adapter_are_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture, _authority_value = _capture(monkeypatch)
    adapter = capture._adapter

    assert PRODUCTION_C3_RUNTIME_ROOT == r"F:\AITradingBot\runtime"
    assert PRODUCTION_C3_PYTHON_EXECUTABLE == r"F:\AITradingBot\runtime\python.exe"
    assert PRODUCTION_C3_CONTROLLED_TEMP_ROOT == r"F:\AITradingBot\temp"
    assert PRODUCTION_C3_CHILD_MODULE == (
        "trading_bot.runtime.windows_effectful_capture_child"
    )
    assert PRODUCTION_C3_CHILD_BASE_ARGUMENTS == (
        "-m",
        PRODUCTION_C3_CHILD_MODULE,
    )
    assert str(PRODUCTION_AUTHORITY_PATHS.capture_output) == (
        r"F:\AITradingBot\Authority\capture-output"
    )
    assert type(adapter._native_api) is CtypesWindowsEffectfulCaptureNativeApi
    with pytest.raises(TypeError):
        copy(adapter)
    with pytest.raises(TypeError):
        deepcopy(adapter)
    with pytest.raises(TypeError):
        pickle.dumps(adapter)


def test_production_adapter_issues_exact_production_provenance_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    monkeypatch.setattr(
        service_module, "require_validated_production_authority", lambda value: value
    )
    monkeypatch.setattr(
        authority_module,
        "require_validated_production_authority",
        lambda value: value,
    )
    monkeypatch.setattr(
        CtypesWindowsEffectfulCaptureNativeApi,
        "__init__",
        lambda self: None,
    )
    capture = WindowsEffectfulDailySnapshotCapture(authority)
    transactional = capture._transactional
    issuer = capture._adapter._issuer
    assert issuer is not None
    context_token = authority_module._CURRENT_SERVICE_CONTEXT.set(
        transactional._context
    )
    try:
        provider = issuer.issue_constructed_provider(_RESERVATION)
        receipt = issuer.issue_process_creation_receipt(
            _RESERVATION,
            b"i" * 32,
            application_name=PRODUCTION_C3_PYTHON_EXECUTABLE,
            child_base_arguments=PRODUCTION_C3_CHILD_BASE_ARGUMENTS,
        )
        resume = issuer.issue_resume_receipt(_EXECUTION, _RESERVATION, b"r" * 32)
        for value, production_issuer, test_issuer, label in (
            (
                provider,
                authority_module._CONSTRUCTED_PROVIDER_ISSUER,
                authority_module._TEST_CONSTRUCTED_PROVIDER_ISSUER,
                "constructed provider",
            ),
            (
                receipt,
                authority_module._PROCESS_RESULT_ISSUER,
                authority_module._TEST_PROCESS_RESULT_ISSUER,
                "process creation result",
            ),
            (
                resume,
                authority_module._RESUME_RESULT_ISSUER,
                authority_module._TEST_RESUME_RESULT_ISSUER,
                "resume receipt",
            ),
        ):
            authority_module._require_service_provenance(
                value,
                production_issuer=production_issuer,
                test_issuer=test_issuer,
                label=label,
                test_only=False,
            )
        process_evidence = (
            authority_module._require_production_process_success_evidence(receipt)
        )
        assert b"SUSPENDED_CHILD_CREATED" in process_evidence[0]
        assert b"AT_PROCESS_CREATION" in process_evidence[1]
        assert b"EXACT_PRIMARY_THREAD_RETAINED" in process_evidence[2]

        reconstructed = replace(provider)
        with pytest.raises(ValueError, match="exact object"):
            authority_module.registered_constructed_provider_reservation_id_for_test(
                reconstructed
            )
        test_provider = issue_constructed_provider_for_test(_RESERVATION)
        with pytest.raises(
            ExternalAuthorityBoundaryUnavailable, match="production service provenance"
        ):
            authority_module._require_service_provenance(
                test_provider,
                production_issuer=authority_module._CONSTRUCTED_PROVIDER_ISSUER,
                test_issuer=authority_module._TEST_CONSTRUCTED_PROVIDER_ISSUER,
                label="constructed provider",
                test_only=False,
            )
    finally:
        authority_module._CURRENT_SERVICE_CONTEXT.reset(context_token)
        capture.close()


def test_plan_to_child_binding_uses_c1_sid_and_release_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture, authority = _capture(monkeypatch)
    plan = capture.prepare_capture_plan(
        _request(),
        datetime(2026, 8, 18, 14, tzinfo=UTC),
    )
    assert capture._adapter._pending_plan is plan

    prepared = prepare_production_execution_for_test(
        capture,
        plan,
        reservation_id=_RESERVATION,
        execution_id=_EXECUTION,
    )

    assert prepared.capture_plan is plan
    assert prepared.bound_capture.reservation_id == _RESERVATION
    assert prepared.child_request.execution_id == _EXECUTION
    assert prepared.child_request.approved_account_sid == authority.approved_account_sid
    assert (
        prepared.child_request.release_manifest_sha256
        == authority.release_manifest_digest
    )
    assert prepared.child_request.c2_request_sha256 == plan.c2_request_digest
    assert (
        prepared.child_request.daily_snapshot_request_id
        == prepared.provider_launch_plan.provider_request.capture_request.request_id
    )


def test_public_planning_api_does_not_accept_authority_overrides() -> None:
    parameters = signature(
        WindowsEffectfulDailySnapshotCapture.prepare_capture_plan
    ).parameters
    assert tuple(parameters) == ("self", "request", "requested_at_utc")
    forbidden = {
        "adapter",
        "external_adapter",
        "approved_account_sid",
        "release_manifest_sha256",
        "output_path",
        "destination",
        "snapshot_digest",
    }
    assert forbidden.isdisjoint(parameters)


def test_close_is_idempotent_and_blocks_future_planning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture, _authority_value = _capture(monkeypatch)
    transactional = capture._transactional

    capture.close()
    capture.close()

    assert transactional.close_count == 1
    assert capture._adapter._closed is True
    assert capture._adapter._registry.semantic_snapshot() == ()
    with pytest.raises(WindowsEffectfulCaptureCompositionError, match="closed"):
        capture.prepare_capture_plan(
            _request(),
            datetime(2026, 8, 18, 14, tzinfo=UTC),
        )


def test_prepared_execution_rejects_cross_bound_child_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture, _authority_value = _capture(monkeypatch)
    plan = capture.prepare_capture_plan(
        _request(),
        datetime(2026, 8, 18, 14, tzinfo=UTC),
    )
    prepared = prepare_production_execution_for_test(
        capture,
        plan,
        reservation_id=_RESERVATION,
        execution_id=_EXECUTION,
    )
    other = prepare_production_execution_for_test(
        capture,
        plan,
        reservation_id=_OTHER_RESERVATION,
        execution_id=_EXECUTION,
    )

    with pytest.raises(
        WindowsEffectfulCaptureCompositionError,
        match="child reservation",
    ):
        replace(prepared, child_request=other.child_request)
