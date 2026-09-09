"""PD2C source-only supervised Architecture-67 execution coverage."""

from __future__ import annotations

import ast
import inspect
import weakref
from dataclasses import replace
from hashlib import sha1
from pathlib import Path
from uuid import UUID

import pytest
from tests.runtime import (
    test_personal_desktop_supervised_paper_operation_preparation as prep_support,
)
from tests.runtime.test_windows_authority_capability import _production_validation

from trading_bot.cli.paper_operation_execution import (
    PaperOperationExecutionClassification,
    PaperOperationExecutionResult,
)
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    PaperOperationInspectionResult,
)
from trading_bot.runtime import (
    CheckpointedVerifiedSnapshotPaperCycleStatus,
    SelectedC3SnapshotPermit,
    SelectedC3SnapshotReadError,
    personal_desktop_paper_account_publication_freeze,
)
from trading_bot.runtime import manual_paper_selected_c3_snapshot as p2
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as execution,
)
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_preparation as preparation,
)
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED,
    PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED,
)
from trading_bot.runtime.personal_desktop_supervised_paper_operation_preparation import (  # noqa: E501
    PaperOperationPreparationReconciliationRequiredError,
)
from trading_bot.runtime.windows_authority import WindowsAuthorityError

FIXED_OPERATION_ROOT = r"F:\AITradingBot\Paper-v2\runtime"
RESULT_ID = UUID("81000000-0000-0000-0000-000000000001")
SUCCESSOR_ID = UUID("82000000-0000-0000-0000-000000000002")


def _public_kwargs() -> dict[str, object]:
    _, _, _, kwargs = prep_support._case()
    return {
        key: value
        for key, value in kwargs.items()
        if key
        not in {
            "supervised_cycle",
            "build_plan",
            "verify_plan",
            "match_selected_snapshot",
            "calendar",
        }
    }


def _fixed_root_case(
    monkeypatch: pytest.MonkeyPatch,
    *,
    state=prep_support.PaperAccountMutexState.OWNED,
):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(prep_support, "OPERATION_ROOT", FIXED_OPERATION_ROOT)
    return prep_support._case(state=state)


def _raw_result(
    inputs,  # type: ignore[no-untyped-def]
    classification: PaperOperationExecutionClassification,
) -> PaperOperationExecutionResult:
    committed = classification in {
        PaperOperationExecutionClassification.COMPLETED,
        PaperOperationExecutionClassification.RECEIPT_RECOVERED,
    }
    pre_execution = {
        PaperOperationExecutionClassification.ALREADY_APPLIED: (
            PaperOperationClassification.ALREADY_APPLIED
        ),
        PaperOperationExecutionClassification.CONFLICTING: (
            PaperOperationClassification.CONFLICTING
        ),
        PaperOperationExecutionClassification.RECEIPT_RECOVERED: (
            PaperOperationClassification.BLOCKED
        ),
    }.get(classification, PaperOperationClassification.PENDING)
    return PaperOperationExecutionResult(
        classification=classification,
        operation_id=inputs.intent.operation_id,
        pre_execution_classification=pre_execution,
        terminal_checkpoint_id=(
            inputs.intent.prior_lineage_evidence.terminal_checkpoint_id
        ),
        application_id=inputs.application_id,
        cycle_result_id=RESULT_ID if committed else None,
        successor_checkpoint_id=SUCCESSOR_ID if committed else None,
        transition_path=Path(r"X:\disposable\transition") if committed else None,
        receipt_path=Path(r"X:\disposable\receipt.json") if committed else None,
        outcome=(
            CheckpointedVerifiedSnapshotPaperCycleStatus.APPLIED if committed else None
        ),
        diagnostic_code=classification.value,
    )


def _inspection(
    inputs,  # type: ignore[no-untyped-def]
    classification: PaperOperationClassification,
    diagnostic: PaperOperationInspectionCode,
) -> PaperOperationInspectionResult:
    return PaperOperationInspectionResult(
        classification,
        inputs.intent.operation_id,
        inputs.intent.prior_lineage_evidence.terminal_checkpoint_id,
        inputs.application_id,
        None,
        (diagnostic,),
    )


def _execute_for_test(
    scope,  # type: ignore[no-untyped-def]
    executor,  # type: ignore[no-untyped-def]
):  # type: ignore[no-untyped-def]
    authority = (
        execution._open_disposable_supervised_paper_execution_authority_for_test()
    )
    return execution._execute_prepared_supervised_paper_operation_for_test(
        scope,
        executor=executor,
        authority=authority,
    )


def test_public_boundary_requires_genuine_c1_before_p2_b1_or_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        pytest.fail("forged C1 reached P2, B1, or Architecture 67")

    monkeypatch.setattr(
        preparation, "require_selected_c3_snapshot_matches_authority", forbidden
    )
    monkeypatch.setattr(
        preparation, "supervised_personal_desktop_paper_cycle", forbidden
    )
    monkeypatch.setattr(execution, "execute_paper_operation_once", forbidden)

    with pytest.raises(WindowsAuthorityError):
        execution.execute_supervised_personal_desktop_paper_operation(
            object(),  # type: ignore[arg-type]
            prep_support._selected_result(),
            **_public_kwargs(),
        )


def test_forged_p2_cannot_enter_public_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c1 = _production_validation(monkeypatch)
    monkeypatch.setattr(
        preparation,
        "supervised_personal_desktop_paper_cycle",
        lambda *args, **kwargs: pytest.fail("forged P2 reached B1"),
    )
    monkeypatch.setattr(
        execution,
        "execute_paper_operation_once",
        lambda *args, **kwargs: pytest.fail("forged P2 reached Architecture 67"),
    )

    with pytest.raises(SelectedC3SnapshotReadError, match="provenance"):
        execution.execute_supervised_personal_desktop_paper_operation(
            c1,
            prep_support._selected_result(),
            **_public_kwargs(),
        )


def test_disposable_p2_cannot_enter_public_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c1 = _production_validation(monkeypatch)
    provisional = prep_support._selected_result()
    core = object.__new__(p2._SelectedC3SnapshotReadCore)
    core._authority = None
    core._production = False
    reader = object.__new__(p2.DisposableSelectedC3SnapshotReadAuthorityForTest)
    reader._core = core
    registration = p2._ReadCoreRegistration(
        weakref.ref(reader), None, p2._DISPOSABLE_CORE_PROVENANCE
    )
    permit = object.__new__(SelectedC3SnapshotPermit)
    binding = p2._PermitBinding(
        weakref.ref(provisional.audit),
        weakref.ref(core),
        weakref.ref(reader),
        registration,
        (
            c1.machine_authority_id,
            c1.approved_account_sid,
            c1.authority_epoch_id,
        ),
    )
    with p2._PERMIT_REGISTRY_LOCK:
        p2._CORE_REGISTRY[core] = registration
        p2._PERMIT_REGISTRY[permit] = binding
    result = replace(provisional, permit=permit)
    try:
        with pytest.raises(SelectedC3SnapshotReadError, match="provenance"):
            execution.execute_supervised_personal_desktop_paper_operation(
                c1,
                result,
                **_public_kwargs(),
            )
    finally:
        with p2._PERMIT_REGISTRY_LOCK:
            p2._PERMIT_REGISTRY.pop(permit, None)
            p2._CORE_REGISTRY.pop(core, None)


def test_public_gate_false_stops_after_c1_p2_validation_before_enter_or_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []

    class ForbiddenPreparation:
        def __enter__(self):  # type: ignore[no-untyped-def]
            pytest.fail("disabled production execution entered PD2B3")

    def validated_preparation(*args, **kwargs):  # type: ignore[no-untyped-def]
        events.append(("c1-p2-validated", args, kwargs))
        return ForbiddenPreparation()

    monkeypatch.setattr(
        execution,
        "supervised_personal_desktop_paper_operation_preparation",
        validated_preparation,
    )
    monkeypatch.setattr(
        execution,
        "execute_paper_operation_once",
        lambda *args, **kwargs: pytest.fail(
            "disabled production execution reached A67"
        ),
    )

    with pytest.raises(
        execution.SupervisedPaperOperationEffectsDisabledError,
        match="effects are disabled",
    ):
        execution.execute_supervised_personal_desktop_paper_operation(
            object(),  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
            **_public_kwargs(),
        )
    assert len(events) == 1
    assert events[0][0] == "c1-p2-validated"


def test_public_signature_has_no_effect_or_execution_authority_overrides() -> None:
    parameters = inspect.signature(
        execution.execute_supervised_personal_desktop_paper_operation
    ).parameters
    assert tuple(parameters) == (
        "authority",
        "selected_snapshot",
        "history_seed",
        "strategy_config",
        "caller_idempotency_key",
        "open_reference",
        "policies",
        "planning_at",
        "submitted_at",
        "filled_at",
        "metadata",
        "historical_cycle_configuration_payloads",
    )
    prohibited = {
        "operation_root",
        "path",
        "execution_inputs",
        "intent",
        "paper_account_id",
        "prior",
        "lineage",
        "application_id",
        "operation_id",
        "preparation",
        "mutex_name",
        "sid",
        "native_handle",
        "timeout",
        "executor",
        "effect_gate",
        "recovery_mode",
    }
    assert prohibited.isdisjoint(parameters)


def test_private_disposable_seam_requires_issued_authority_before_preparation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, _, events, _ = _fixed_root_case(monkeypatch)
    with pytest.raises(TypeError, match="test issuer"):
        execution._DisposableSupervisedPaperExecutionAuthorityForTest()
    with pytest.raises(TypeError, match="authority is invalid"):
        execution._execute_prepared_supervised_paper_operation_for_test(
            scope,
            executor=lambda root, inputs: pytest.fail("executor called"),
            authority=object(),  # type: ignore[arg-type]
        )
    assert events == []


def test_binding_and_executor_are_used_only_while_exact_preparation_is_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, cycle, events, _ = _fixed_root_case(monkeypatch)
    original = execution._require_active_prepared_paper_operation_binding
    observed_inputs: list[object] = []

    def require_binding(active):  # type: ignore[no-untyped-def]
        assert active is scope
        assert cycle.active
        events.append("pd2c-binding")
        return original(active)

    def executor(root, inputs):  # type: ignore[no-untyped-def]
        assert cycle.active
        assert events[-1] == "pd2c-binding"
        assert root == Path(FIXED_OPERATION_ROOT)
        observed_inputs.append(inputs)
        return _raw_result(
            inputs, PaperOperationExecutionClassification.ALREADY_APPLIED
        )

    monkeypatch.setattr(
        execution, "_require_active_prepared_paper_operation_binding", require_binding
    )
    result = _execute_for_test(scope, executor)

    assert result.executor_called is True
    assert len(observed_inputs) == 1
    assert events[-1] == ("b1-exit", None)
    with pytest.raises(
        preparation.SupervisedPaperOperationPreparationError,
        match="not active",
    ):
        original(scope)


def test_mismatching_operation_root_blocks_before_executor_and_unwinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del monkeypatch
    scope, _, events, _ = prep_support._case()
    calls = 0

    def executor(root, inputs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        pytest.fail("mismatching root reached executor")

    with pytest.raises(
        execution.SupervisedPaperOperationRootMismatchError,
        match="fixed Paper-v2 runtime",
    ):
        _execute_for_test(scope, executor)
    assert calls == 0
    assert events[-1] == (
        "b1-exit",
        execution.SupervisedPaperOperationRootMismatchError,
    )


@pytest.mark.parametrize(
    "classification",
    [
        PaperOperationExecutionClassification.ALREADY_APPLIED,
        PaperOperationExecutionClassification.BLOCKED,
        PaperOperationExecutionClassification.CONFLICTING,
        PaperOperationExecutionClassification.EXECUTION_FAILED,
        PaperOperationExecutionClassification.COMPLETED,
        PaperOperationExecutionClassification.RECEIPT_RECOVERED,
    ],
)
def test_a67_classifications_are_represented_once_without_authority(
    monkeypatch: pytest.MonkeyPatch,
    classification: PaperOperationExecutionClassification,
) -> None:
    scope, _, events, _ = _fixed_root_case(monkeypatch)
    calls = 0

    def executor(root, inputs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return _raw_result(inputs, classification)

    result = _execute_for_test(scope, executor)
    assert calls == 1
    assert result.execution_classification is classification
    assert result.operation_id == scope._audit.operation_id
    assert result.application_id == scope._audit.application_id
    assert result.diagnostic_code == classification.value
    assert result.executor_called is True
    assert result.transition_evidence_produced is (
        classification
        in {
            PaperOperationExecutionClassification.COMPLETED,
            PaperOperationExecutionClassification.RECEIPT_RECOVERED,
        }
    )
    assert result.receipt_evidence_produced is result.transition_evidence_produced
    assert not hasattr(result, "operation_root")
    assert not hasattr(result, "transition_path")
    assert not hasattr(result, "receipt_path")
    assert not hasattr(result, "execution_inputs")
    assert not hasattr(result, "execute")
    assert events[-1] == ("b1-exit", None)


def test_disposable_authority_is_one_shot_and_cannot_grant_second_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, _, _, _ = _fixed_root_case(monkeypatch)
    second, _, second_events, _ = _fixed_root_case(monkeypatch)
    authority = (
        execution._open_disposable_supervised_paper_execution_authority_for_test()
    )
    calls = 0

    def executor(root, inputs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return _raw_result(
            inputs, PaperOperationExecutionClassification.ALREADY_APPLIED
        )

    execution._execute_prepared_supervised_paper_operation_for_test(
        first, executor=executor, authority=authority
    )
    with pytest.raises(TypeError, match="consumed"):
        execution._execute_prepared_supervised_paper_operation_for_test(
            second, executor=executor, authority=authority
        )
    assert calls == 1
    assert second_events == []


def test_executor_exception_propagates_once_and_unwinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, cycle, events, _ = _fixed_root_case(monkeypatch)
    calls = 0

    def executor(root, inputs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        assert cycle.active
        raise RuntimeError("executor failed")

    with pytest.raises(RuntimeError, match="executor failed"):
        _execute_for_test(scope, executor)
    assert calls == 1
    assert events[-1] == ("b1-exit", RuntimeError)


def test_wrong_executor_return_type_fails_closed_once_and_unwinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, _, events, _ = _fixed_root_case(monkeypatch)
    calls = 0

    def executor(root, inputs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return object()

    with pytest.raises(
        execution.SupervisedPaperOperationResultReconciliationError,
        match="invalid result type",
    ):
        _execute_for_test(scope, executor)
    assert calls == 1
    assert events[-1] == (
        "b1-exit",
        execution.SupervisedPaperOperationResultReconciliationError,
    )


@pytest.mark.parametrize("mismatch", ["operation_id", "application_id"])
def test_executor_result_identity_mismatch_fails_closed_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    scope, _, events, _ = _fixed_root_case(monkeypatch)
    calls = 0

    def executor(root, inputs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        result = _raw_result(
            inputs, PaperOperationExecutionClassification.ALREADY_APPLIED
        )
        return replace(result, **{mismatch: UUID(int=999)})

    with pytest.raises(
        execution.SupervisedPaperOperationResultReconciliationError,
        match="result identities",
    ):
        _execute_for_test(scope, executor)
    assert calls == 1
    assert events[-1] == (
        "b1-exit",
        execution.SupervisedPaperOperationResultReconciliationError,
    )


def test_frozen_profile_failure_precedes_inspection_output_policy_and_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, _, events, _ = _fixed_root_case(monkeypatch)

    def mismatch(**kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        raise ValueError("frozen mismatch")

    monkeypatch.setattr(
        execution,
        "reconcile_personal_desktop_first_paper_operation",
        mismatch,
    )
    authority = (
        execution._open_disposable_supervised_paper_execution_authority_for_test()
    )
    with pytest.raises(
        execution.SupervisedPaperOperationFrozenProfileMismatchError,
        match="frozen first operation",
    ):
        execution._execute_prepared_supervised_paper_operation_for_test(
            scope,
            executor=lambda *args: pytest.fail("mismatch reached executor"),
            inspector=lambda *args: pytest.fail("mismatch reached inspection"),
            output_capability_factory=lambda: pytest.fail(
                "mismatch reached output policy"
            ),
            authority=authority,
        )
    assert events[-1] == (
        "b1-exit",
        execution.SupervisedPaperOperationFrozenProfileMismatchError,
    )


@pytest.mark.parametrize(
    ("classification", "diagnostic"),
    [
        (
            PaperOperationClassification.ALREADY_APPLIED,
            PaperOperationInspectionCode.ALREADY_APPLIED,
        ),
        (
            PaperOperationClassification.CONFLICTING,
            PaperOperationInspectionCode.LINEAGE_CONFLICT,
        ),
        (
            PaperOperationClassification.BLOCKED,
            PaperOperationInspectionCode.FINALIZED_TRANSITION_WITHOUT_RECEIPT,
        ),
        (
            PaperOperationClassification.BLOCKED,
            PaperOperationInspectionCode.VALID_FAILED_RECEIPT,
        ),
        (
            PaperOperationClassification.BLOCKED,
            PaperOperationInspectionCode.OPERATION_STAGING_EXISTS,
        ),
        (
            PaperOperationClassification.BLOCKED,
            PaperOperationInspectionCode.TRANSITION_STAGING_EXISTS,
        ),
        (
            PaperOperationClassification.BLOCKED,
            PaperOperationInspectionCode.INVALID_OPERATION_STATE,
        ),
        (
            PaperOperationClassification.BLOCKED,
            PaperOperationInspectionCode.UNSAFE_OPERATION_ROOT,
        ),
    ],
)
def test_first_run_non_pending_state_calls_no_output_policy_or_executor(
    monkeypatch: pytest.MonkeyPatch,
    classification: PaperOperationClassification,
    diagnostic: PaperOperationInspectionCode,
) -> None:
    scope, _, events, _ = _fixed_root_case(monkeypatch)
    monkeypatch.setattr(
        execution,
        "reconcile_personal_desktop_first_paper_operation",
        lambda **kwargs: None,
    )

    def inspector(root, inputs):  # type: ignore[no-untyped-def]
        assert root == Path(FIXED_OPERATION_ROOT)
        return _inspection(inputs, classification, diagnostic)

    authority = (
        execution._open_disposable_supervised_paper_execution_authority_for_test()
    )
    with pytest.raises(
        execution.SupervisedPaperOperationFirstRunAdmissionError,
        match="PENDING/PENDING",
    ):
        execution._execute_prepared_supervised_paper_operation_for_test(
            scope,
            executor=lambda *args: pytest.fail("non-PENDING reached executor"),
            inspector=inspector,
            output_capability_factory=lambda: pytest.fail(
                "non-PENDING reached output policy"
            ),
            authority=authority,
        )
    assert events[-1] == (
        "b1-exit",
        execution.SupervisedPaperOperationFirstRunAdmissionError,
    )


def test_first_run_exact_pending_enters_policy_and_calls_executor_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, cycle, events, _ = _fixed_root_case(monkeypatch)
    monkeypatch.setattr(
        execution,
        "reconcile_personal_desktop_first_paper_operation",
        lambda **kwargs: None,
    )
    calls = 0
    capability = object()

    class OutputContext:
        def __enter__(self):  # type: ignore[no-untyped-def]
            assert cycle.active
            events.append("output-enter")
            return capability

        def __exit__(self, exc_type, exc, traceback):  # type: ignore[no-untyped-def]
            events.append(("output-exit", exc_type))

    def inspector(root, inputs):  # type: ignore[no-untyped-def]
        events.append("strict-inspection")
        return _inspection(
            inputs,
            PaperOperationClassification.PENDING,
            PaperOperationInspectionCode.PENDING,
        )

    def executor(root, inputs, output_capability):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        assert cycle.active
        assert output_capability is capability
        assert events[-1] == "output-enter"
        return _raw_result(inputs, PaperOperationExecutionClassification.COMPLETED)

    authority = (
        execution._open_disposable_supervised_paper_execution_authority_for_test()
    )
    result = execution._execute_prepared_supervised_paper_operation_for_test(
        scope,
        executor=executor,
        inspector=inspector,
        output_capability_factory=OutputContext,
        authority=authority,
    )
    assert calls == 1
    assert (
        result.execution_classification
        is PaperOperationExecutionClassification.COMPLETED
    )
    assert events.index("strict-inspection") < events.index("output-enter")
    assert events[-2:] == [("output-exit", None), ("b1-exit", None)]


def test_abandoned_owner_never_reaches_binding_or_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, _, events, _ = _fixed_root_case(
        monkeypatch,
        state=prep_support.PaperAccountMutexState.ABANDONED_OWNER,
    )
    with pytest.raises(
        PaperOperationPreparationReconciliationRequiredError,
        match="requires reconciliation",
    ):
        _execute_for_test(
            scope,
            lambda root, inputs: pytest.fail("abandoned owner reached executor"),
        )
    assert "post-lock-evidence" not in events
    assert events[-1] == ("b1-exit", None)


def test_pd2c_isolated_surface_keeps_all_effect_gates_false() -> None:
    assert execution.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED is (
        False
    )
    assert PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False

    import trading_bot.runtime as runtime_public

    assert not hasattr(
        runtime_public,
        "_execute_prepared_supervised_paper_operation_for_test",
    )
    assert not hasattr(
        runtime_public,
        "_open_disposable_supervised_paper_execution_authority_for_test",
    )

    source = Path(execution.__file__).read_text(encoding="utf-8")
    imported_modules = {
        node.module or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    }
    assert not any(
        boundary in module
        for module in imported_modules
        for boundary in (
            "provider",
            "broker",
            "live",
            "scheduler",
            "credential",
            "paper_account_mutex",
            "paper_account_security",
        )
    )
    assert source.count("executor=_execute_architecture_67") == 1
    core_source = inspect.getsource(
        execution._execute_prepared_supervised_paper_operation
    )
    assert core_source.count("result = executor(") == 1

    freeze_payload = Path(
        personal_desktop_paper_account_publication_freeze.__file__
    ).read_bytes()
    git_blob_material = (
        b"blob " + str(len(freeze_payload)).encode("ascii") + b"\0" + freeze_payload
    )
    assert (
        sha1(git_blob_material, usedforsecurity=False).hexdigest()
        == "b125cbb1c80a827f74018cf2955b9a27ba69fa90"
    )
