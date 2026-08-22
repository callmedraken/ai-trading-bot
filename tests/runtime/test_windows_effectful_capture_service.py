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


class _ExploitShapeAdapter:
    """Structurally compatible fake that reproduced the original defect."""

    def __init__(self) -> None:
        self.delivered_issuer: object | None = None

    def _bind_production_c2_issuer(self, issuer: object) -> None:
        self.delivered_issuer = issuer

    def construct_provider(self, *args: object, **kwargs: object) -> object:
        raise AssertionError((args, kwargs))

    def create_process(self, *args: object, **kwargs: object) -> object:
        raise AssertionError((args, kwargs))

    def resume_thread(self, *args: object, **kwargs: object) -> object:
        raise AssertionError((args, kwargs))

    def deliver_c3_child_request(self, *args: object, **kwargs: object) -> None:
        raise AssertionError((args, kwargs))

    def validate_c3_post_resume_evidence(
        self, *args: object, **kwargs: object
    ) -> object:
        raise AssertionError((args, kwargs))

    def consume_c3_post_resume_evidence(self, *args: object, **kwargs: object) -> None:
        raise AssertionError((args, kwargs))

    def prepare_c3_terminal(self, *args: object, **kwargs: object) -> object:
        raise AssertionError((args, kwargs))

    def validate_c3_terminal(self, *args: object, **kwargs: object) -> object:
        raise AssertionError((args, kwargs))

    def consume_c3_terminal(self, *args: object, **kwargs: object) -> None:
        raise AssertionError((args, kwargs))


class _CapturedTransactionalAuthority:
    def __init__(self, authority: ValidatedProductionAuthority) -> None:
        self.authority = authority
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1


def _capture_with_unconsumed_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    WindowsEffectfulDailySnapshotCapture,
    object,
    object,
]:
    authority = _authority()
    monkeypatch.setattr(
        service_module,
        "require_validated_production_authority",
        lambda candidate: candidate,
    )
    monkeypatch.setattr(
        authority_module,
        "require_validated_production_authority",
        lambda candidate: candidate,
    )
    monkeypatch.setattr(
        CtypesWindowsEffectfulCaptureNativeApi,
        "__init__",
        lambda self: None,
    )
    captured: list[object] = []
    original_factory = WindowsTransactionalAuthority._for_production_c3

    def intercept_factory(cls: type[object], binding: object) -> object:
        del cls
        captured.append(binding)
        return _CapturedTransactionalAuthority(authority)

    with monkeypatch.context() as intercept:
        intercept.setattr(
            WindowsTransactionalAuthority,
            "_for_production_c3",
            classmethod(intercept_factory),
        )
        capture = WindowsEffectfulDailySnapshotCapture(authority)
    assert len(captured) == 1
    return capture, captured[0], original_factory


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
        authority_module,
        "require_validated_production_authority",
        lambda candidate: candidate,
    )
    monkeypatch.setattr(
        CtypesWindowsEffectfulCaptureNativeApi,
        "__init__",
        lambda self: None,
    )
    return WindowsEffectfulDailySnapshotCapture(authority), authority


def test_original_arbitrary_adapter_exploit_cannot_acquire_production_issuer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    monkeypatch.setattr(
        authority_module,
        "require_validated_production_authority",
        lambda candidate: candidate,
    )
    adapter = _ExploitShapeAdapter()

    with pytest.raises(TypeError):
        WindowsTransactionalAuthority._for_production_c3(authority, adapter)
    with pytest.raises(TypeError, match="exact composition binding"):
        WindowsTransactionalAuthority._for_production_c3(adapter)
    with pytest.raises(TypeError, match="requires its exact issuer"):
        authority_module._issue_production_c3_composition_binding(object())

    assert adapter.delivered_issuer is None


def test_binding_rejects_lookalikes_copy_pickle_and_visible_reconstruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture, binding, factory = _capture_with_unconsumed_binding(monkeypatch)
    binding_type = authority_module._ProductionC3CompositionBinding

    class LookalikeBinding:
        _issuance_provenance = binding._issuance_provenance

    reconstructed = object.__new__(binding_type)
    reconstructed._issuance_provenance = binding._issuance_provenance
    try:
        with pytest.raises(TypeError, match="require their issuer"):
            binding_type()
        with pytest.raises(TypeError, match="cannot be copied"):
            copy(binding)
        with pytest.raises(TypeError, match="cannot be deep-copied"):
            deepcopy(binding)
        with pytest.raises(TypeError, match="cannot be (serialized|pickled)"):
            pickle.dumps(binding)
        with pytest.raises(TypeError, match="exact composition binding"):
            factory(LookalikeBinding())
        with pytest.raises(TypeError, match="invalid or already consumed"):
            factory(reconstructed)
    finally:
        capture.close()


def test_exact_binding_is_one_shot_and_cannot_cross_root_authority_or_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture_a, binding_a, factory = _capture_with_unconsumed_binding(monkeypatch)
    capture_b, binding_b, _factory_b = _capture_with_unconsumed_binding(monkeypatch)
    assert capture_a.authority is not capture_b.authority
    assert capture_a._adapter is not capture_b._adapter
    assert capture_a._production_c2_binding_issuance is not (
        capture_b._production_c2_binding_issuance
    )
    with authority_module._PRODUCTION_C3_COMPOSITION_BINDINGS_LOCK:
        issuance_a = authority_module._PRODUCTION_C3_COMPOSITION_BINDINGS[binding_a]
        issuance_b = authority_module._PRODUCTION_C3_COMPOSITION_BINDINGS[binding_b]
        assert issuance_a.authority is capture_a.authority
        assert issuance_a.adapter is capture_a._adapter
        assert issuance_a.composition_root is capture_a
        assert (
            issuance_a.composition_issuance is capture_a._production_c2_binding_issuance
        )
        assert issuance_b.authority is capture_b.authority
        assert issuance_b.adapter is capture_b._adapter
        assert issuance_b.composition_root is capture_b

    transactional_a = factory(binding_a)
    transactional_b = factory(binding_b)
    capture_a._transactional = transactional_a
    capture_b._transactional = transactional_b
    try:
        assert transactional_a.authority is capture_a.authority
        assert transactional_a._context.external_adapter is capture_a._adapter
        assert transactional_a._context.external_adapter is not capture_b._adapter
        assert transactional_b.authority is capture_b.authority
        assert transactional_b._context.external_adapter is capture_b._adapter
        with pytest.raises(TypeError, match="invalid or already consumed"):
            factory(binding_a)
        with pytest.raises(
            WindowsEffectfulCaptureCompositionError,
            match="issuance is unavailable",
        ):
            capture_a._production_c2_binding_issuance.issue_binding(capture_b)
    finally:
        capture_a.close()
        capture_b.close()


def test_post_claim_binding_failure_revokes_issuer_and_never_restores_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture, binding, factory = _capture_with_unconsumed_binding(monkeypatch)
    adapter = capture._adapter
    delivered: list[object] = []
    original_bind = type(adapter)._bind_production_c2_issuer

    def fail_after_delivery(self: object, issuer: object) -> None:
        original_bind(self, issuer)
        delivered.append(issuer)
        raise RuntimeError("injected post-claim binding failure")

    monkeypatch.setattr(
        type(adapter),
        "_bind_production_c2_issuer",
        fail_after_delivery,
    )
    try:
        with pytest.raises(RuntimeError, match="post-claim"):
            factory(binding)
        assert len(delivered) == 1
        assert delivered[0]._active is False
        assert adapter._issuer is None
        with pytest.raises(TypeError, match="invalid or already consumed"):
            factory(binding)
    finally:
        capture.close()


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
    assert capture._transactional._context.external_adapter is capture._adapter
    assert capture._adapter._authority is authority
    assert capture._adapter._capture is capture
    assert type(capture._adapter._native_api) is CtypesWindowsEffectfulCaptureNativeApi


def test_reinitialization_is_rejected_before_mutation_and_original_close_owns_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture, authority = _capture(monkeypatch)
    adapter = capture._adapter
    transactional = capture._transactional
    issuance = capture._production_c2_binding_issuance
    result_issuer = transactional._production_c3_issuer
    assert result_issuer is not None
    adapter_issuer = adapter._issuer
    initial_state = (
        capture._authority,
        capture._adapter,
        capture._transactional,
        capture._production_c2_binding_issuance,
        capture._production_c2_binding_issued,
        capture._closed,
        transactional._production_c3_issuer,
        adapter._issuer,
    )
    closed_adapters: list[object] = []
    original_close = type(adapter).close

    def observe_close(self: object) -> None:
        closed_adapters.append(self)
        original_close(self)

    monkeypatch.setattr(type(adapter), "close", observe_close)
    revalidation_calls = 0

    def reject_revalidation(_candidate: object) -> object:
        nonlocal revalidation_calls
        revalidation_calls += 1
        raise AssertionError("reinitialization reached authority validation")

    monkeypatch.setattr(
        service_module,
        "require_validated_production_authority",
        reject_revalidation,
    )

    for candidate in (authority, _authority()):
        with pytest.raises(
            WindowsEffectfulCaptureCompositionError,
            match="root initialization is unavailable",
        ):
            capture.__init__(candidate)
        assert (
            capture._authority,
            capture._adapter,
            capture._transactional,
            capture._production_c2_binding_issuance,
            capture._production_c2_binding_issued,
            capture._closed,
            transactional._production_c3_issuer,
            adapter._issuer,
        ) == initial_state
        assert capture._authority is authority
        assert capture._adapter is adapter
        assert capture._transactional is transactional
        assert capture._production_c2_binding_issuance is issuance
        assert capture._production_c2_binding_issued is True
        assert capture._closed is False
        assert transactional._production_c3_issuer is result_issuer
        assert result_issuer._active is True
        assert adapter._issuer is adapter_issuer

    assert revalidation_calls == 0
    plan = capture.prepare_capture_plan(
        _request(), datetime(2026, 8, 18, 14, tzinfo=UTC)
    )
    assert adapter._pending_plan is plan

    capture.close()
    capture.close()

    assert closed_adapters == [adapter]
    assert adapter._closed is True
    assert adapter._pending_plan is None
    assert result_issuer._active is False


def _assert_failed_root_is_not_retained(
    root: WindowsEffectfulDailySnapshotCapture,
    adapter: object,
) -> None:
    with service_module._PRODUCTION_C3_ROOT_CONSTRUCTIONS_LOCK:
        assert root not in service_module._PRODUCTION_C3_ROOT_CONSTRUCTIONS
    with service_module._PRODUCTION_C3_COMPOSITION_ISSUANCES_LOCK:
        assert all(
            record.root is not root and record.adapter is not adapter
            for record in service_module._PRODUCTION_C3_COMPOSITION_ISSUANCES.values()
        )
    with authority_module._PRODUCTION_C3_COMPOSITION_BINDINGS_LOCK:
        assert all(
            record.composition_root is not root and record.adapter is not adapter
            for record in authority_module._PRODUCTION_C3_COMPOSITION_BINDINGS.values()
        )


def test_composition_issuance_failure_closes_adapter_and_is_not_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    monkeypatch.setattr(
        service_module,
        "require_validated_production_authority",
        lambda candidate: candidate,
    )
    monkeypatch.setattr(
        CtypesWindowsEffectfulCaptureNativeApi,
        "__init__",
        lambda self: None,
    )
    closed_adapters: list[object] = []
    created_issuances: list[object] = []
    adapter_type = service_module._ProductionC3TransactionalAdapter
    original_close = adapter_type.close
    original_issuance = service_module._create_production_c3_composition_issuance

    def observe_close(self: object) -> None:
        closed_adapters.append(self)
        original_close(self)

    def fail_issuance(*args: object) -> object:
        issuance = original_issuance(*args)
        created_issuances.append(issuance)
        raise RuntimeError("injected composition issuance failure")

    monkeypatch.setattr(adapter_type, "close", observe_close)
    monkeypatch.setattr(
        service_module,
        "_create_production_c3_composition_issuance",
        fail_issuance,
    )
    root = WindowsEffectfulDailySnapshotCapture.__new__(
        WindowsEffectfulDailySnapshotCapture, authority
    )

    with pytest.raises(RuntimeError, match="composition issuance failure"):
        root.__init__(authority)

    assert len(closed_adapters) == 1
    adapter = closed_adapters[0]
    assert adapter is root._adapter
    assert adapter._closed is True
    assert adapter._issuer is None
    assert len(created_issuances) == 1
    with service_module._PRODUCTION_C3_COMPOSITION_ISSUANCES_LOCK:
        assert (
            created_issuances[0]
            not in service_module._PRODUCTION_C3_COMPOSITION_ISSUANCES
        )
    _assert_failed_root_is_not_retained(root, adapter)
    with pytest.raises(
        WindowsEffectfulCaptureCompositionError,
        match="root initialization is unavailable",
    ):
        root.__init__(authority)
    assert closed_adapters == [adapter]


def test_binding_creation_failure_closes_adapter_and_clears_registries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    monkeypatch.setattr(
        service_module,
        "require_validated_production_authority",
        lambda candidate: candidate,
    )
    monkeypatch.setattr(
        CtypesWindowsEffectfulCaptureNativeApi,
        "__init__",
        lambda self: None,
    )
    closed_adapters: list[object] = []
    created_bindings: list[object] = []
    adapter_type = service_module._ProductionC3TransactionalAdapter
    original_close = adapter_type.close
    original_binding = service_module._issue_production_c3_composition_binding

    def observe_close(self: object) -> None:
        closed_adapters.append(self)
        original_close(self)

    def fail_binding(issuer: object) -> object:
        binding = original_binding(issuer)
        created_bindings.append(binding)
        raise RuntimeError("injected composition binding failure")

    monkeypatch.setattr(adapter_type, "close", observe_close)
    monkeypatch.setattr(
        service_module,
        "_issue_production_c3_composition_binding",
        fail_binding,
    )
    root = WindowsEffectfulDailySnapshotCapture.__new__(
        WindowsEffectfulDailySnapshotCapture, authority
    )

    with pytest.raises(RuntimeError, match="composition binding failure"):
        root.__init__(authority)

    assert len(closed_adapters) == 1
    adapter = closed_adapters[0]
    assert adapter is root._adapter
    assert adapter._closed is True
    assert adapter._issuer is None
    assert root._production_c2_binding_issued is True
    assert len(created_bindings) == 1
    with authority_module._PRODUCTION_C3_COMPOSITION_BINDINGS_LOCK:
        assert (
            created_bindings[0]
            not in authority_module._PRODUCTION_C3_COMPOSITION_BINDINGS
        )
    with pytest.raises(TypeError, match="invalid or already consumed"):
        WindowsTransactionalAuthority._for_production_c3(created_bindings[0])
    _assert_failed_root_is_not_retained(root, adapter)
    with pytest.raises(
        WindowsEffectfulCaptureCompositionError,
        match="root initialization is unavailable",
    ):
        root.__init__(authority)
    assert closed_adapters == [adapter]


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
    issuer = transactional._production_c3_issuer
    assert issuer is not None

    capture.close()
    capture.close()

    assert issuer._active is False
    assert transactional._production_c3_issuer is None
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
