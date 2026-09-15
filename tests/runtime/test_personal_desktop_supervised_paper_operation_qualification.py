"""PD2D1 source-only supervised read-only qualification coverage."""

from __future__ import annotations

import ast
import inspect
import weakref
from dataclasses import fields, replace
from hashlib import sha1
from pathlib import Path
from uuid import UUID

import pytest
from tests.runtime import (
    test_personal_desktop_supervised_paper_operation_preparation as prep_support,
)
from tests.runtime.test_windows_authority_capability import _production_validation

from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    PaperOperationInspectionResult,
)
from trading_bot.runtime import (
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
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_qualification as qualification,
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


def _inspection(
    inputs,  # type: ignore[no-untyped-def]
    classification: PaperOperationClassification = PaperOperationClassification.PENDING,
    code: PaperOperationInspectionCode = PaperOperationInspectionCode.PENDING,
) -> PaperOperationInspectionResult:
    return PaperOperationInspectionResult(
        classification=classification,
        operation_id=inputs.intent.operation_id,
        terminal_checkpoint_id=inputs.verified_prior.checkpoint_id,
        application_id=inputs.application_id,
        receipt_path=None,
        diagnostics=(code,),
    )


def _qualify_for_test(
    scope,  # type: ignore[no-untyped-def]
    inspector,  # type: ignore[no-untyped-def]
):  # type: ignore[no-untyped-def]
    authority = qualification._open_disposable_supervised_paper_qualification_authority_for_test()  # noqa: E501
    return qualification._qualify_prepared_supervised_paper_operation_for_test(
        scope,
        inspector=inspector,
        authority=authority,
    )


def test_execution_gate_true_blocks_before_preparation_or_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        execution,
        "PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED",
        True,
    )
    monkeypatch.setattr(
        qualification,
        "supervised_personal_desktop_paper_operation_preparation",
        lambda *args, **kwargs: pytest.fail("enabled execution gate reached PD2B3"),
    )
    monkeypatch.setattr(
        qualification,
        "inspect_paper_operation_root",
        lambda *args, **kwargs: pytest.fail("enabled execution gate reached inspector"),
    )

    with pytest.raises(
        qualification.SupervisedPaperOperationQualificationGateError,
        match="must remain disabled",
    ):
        qualification.qualify_supervised_personal_desktop_paper_operation(
            object(),  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
            **_public_kwargs(),
        )


def test_execution_gate_false_enters_preparation_and_inspects_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, cycle, events, _ = _fixed_root_case(monkeypatch)
    calls = 0

    def inspector(root, inputs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        assert cycle.active
        assert root == Path(FIXED_OPERATION_ROOT)
        return _inspection(inputs)

    monkeypatch.setattr(
        qualification,
        "supervised_personal_desktop_paper_operation_preparation",
        lambda *args, **kwargs: scope,
    )
    monkeypatch.setattr(qualification, "inspect_paper_operation_root", inspector)

    result = qualification.qualify_supervised_personal_desktop_paper_operation(
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        **_public_kwargs(),
    )

    assert calls == 1
    assert result.qualification_status is (
        qualification.SupervisedPaperOperationQualificationStatus.READY
    )
    assert events[-1] == ("b1-exit", None)


def test_public_boundary_requires_genuine_c1_before_p2_b1_or_inspector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        pytest.fail("forged C1 reached P2, B1, or inspector")

    monkeypatch.setattr(
        preparation, "require_selected_c3_snapshot_matches_authority", forbidden
    )
    monkeypatch.setattr(
        preparation, "supervised_personal_desktop_paper_cycle", forbidden
    )
    monkeypatch.setattr(qualification, "inspect_paper_operation_root", forbidden)

    with pytest.raises(WindowsAuthorityError):
        qualification.qualify_supervised_personal_desktop_paper_operation(
            object(),  # type: ignore[arg-type]
            prep_support._selected_result(),
            **_public_kwargs(),
        )


def test_forged_p2_cannot_enter_public_qualification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c1 = _production_validation(monkeypatch)
    monkeypatch.setattr(
        preparation,
        "supervised_personal_desktop_paper_cycle",
        lambda *args, **kwargs: pytest.fail("forged P2 reached B1"),
    )
    monkeypatch.setattr(
        qualification,
        "inspect_paper_operation_root",
        lambda *args, **kwargs: pytest.fail("forged P2 reached inspector"),
    )

    with pytest.raises(SelectedC3SnapshotReadError, match="provenance"):
        qualification.qualify_supervised_personal_desktop_paper_operation(
            c1,
            prep_support._selected_result(),
            **_public_kwargs(),
        )


def test_disposable_p2_cannot_enter_public_qualification(
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
            qualification.qualify_supervised_personal_desktop_paper_operation(
                c1,
                result,
                **_public_kwargs(),
            )
    finally:
        with p2._PERMIT_REGISTRY_LOCK:
            p2._PERMIT_REGISTRY.pop(permit, None)
            p2._CORE_REGISTRY.pop(core, None)


def test_public_signature_accepts_only_c1_p2_and_pure_planning_inputs() -> None:
    parameters = inspect.signature(
        qualification.qualify_supervised_personal_desktop_paper_operation
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
        "terminal_checkpoint_id",
        "preparation",
        "mutex_name",
        "sid",
        "native_handle",
        "timeout",
        "inspector",
        "readiness",
        "execution_gate",
        "recovery",
    }
    assert prohibited.isdisjoint(parameters)


def test_private_disposable_seam_requires_issued_one_shot_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, _, events, _ = _fixed_root_case(monkeypatch)
    with pytest.raises(TypeError, match="test issuer"):
        qualification._DisposableSupervisedPaperQualificationAuthorityForTest()
    with pytest.raises(TypeError, match="authority is invalid"):
        qualification._qualify_prepared_supervised_paper_operation_for_test(
            scope,
            inspector=lambda root, inputs: pytest.fail("inspector called"),
            authority=object(),  # type: ignore[arg-type]
        )
    assert events == []

    first_authority = qualification._open_disposable_supervised_paper_qualification_authority_for_test()  # noqa: E501
    qualification._qualify_prepared_supervised_paper_operation_for_test(
        scope,
        inspector=lambda root, inputs: _inspection(inputs),
        authority=first_authority,
    )
    second, _, second_events, _ = _fixed_root_case(monkeypatch)
    with pytest.raises(TypeError, match="consumed"):
        qualification._qualify_prepared_supervised_paper_operation_for_test(
            second,
            inspector=lambda root, inputs: _inspection(inputs),
            authority=first_authority,
        )
    assert second_events == []


def test_binding_and_inspector_stay_under_exact_active_mutex_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, cycle, events, _ = _fixed_root_case(monkeypatch)
    original = qualification._require_active_prepared_paper_operation_binding
    observed_inputs: list[object] = []

    def require_binding(active):  # type: ignore[no-untyped-def]
        assert active is scope
        assert cycle.active
        events.append("pd2d1-binding")
        return original(active)

    def inspector(root, inputs):  # type: ignore[no-untyped-def]
        assert cycle.active
        assert events[-1] == "pd2d1-binding"
        assert root == Path(FIXED_OPERATION_ROOT)
        assert inputs is original(scope).execution_inputs
        observed_inputs.append(inputs)
        return _inspection(inputs)

    monkeypatch.setattr(
        qualification,
        "_require_active_prepared_paper_operation_binding",
        require_binding,
    )
    result = _qualify_for_test(scope, inspector)

    assert result.inspector_called is True
    assert len(observed_inputs) == 1
    assert events[-1] == ("b1-exit", None)
    with pytest.raises(
        preparation.SupervisedPaperOperationPreparationError,
        match="not active",
    ):
        original(scope)


def test_fixed_root_mismatch_blocks_before_inspection_and_unwinds() -> None:
    scope, _, events, _ = prep_support._case()
    calls = 0

    def inspector(root, inputs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        pytest.fail("mismatching root reached inspector")

    with pytest.raises(
        qualification.SupervisedPaperOperationQualificationRootMismatchError,
        match="fixed Paper-v2 runtime",
    ):
        _qualify_for_test(scope, inspector)
    assert calls == 0
    assert events[-1] == (
        "b1-exit",
        qualification.SupervisedPaperOperationQualificationRootMismatchError,
    )


def test_exact_pending_pending_is_ready_and_result_is_non_authorizing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, _, events, _ = _fixed_root_case(monkeypatch)
    result = _qualify_for_test(scope, lambda root, inputs: _inspection(inputs))

    assert result.paper_account_id == prep_support.ACCOUNT_ID
    assert result.selected_snapshot_id == scope._audit.selected_snapshot_id
    assert result.plan_id == scope._audit.plan_id
    assert result.operation_id == scope._audit.operation_id
    assert result.application_id == scope._audit.application_id
    assert result.inspection_classification is PaperOperationClassification.PENDING
    assert result.inspection_diagnostic is PaperOperationInspectionCode.PENDING
    assert result.qualification_status is (
        qualification.SupervisedPaperOperationQualificationStatus.READY
    )
    assert result.inspector_called is True
    assert {item.name for item in fields(result)}.isdisjoint(
        {
            "operation_root",
            "path",
            "receipt_path",
            "transition_path",
            "execution_inputs",
            "preparation",
            "binding",
            "execute",
        }
    )
    assert not any(
        isinstance(getattr(result, item.name), Path) for item in fields(result)
    )
    assert not callable(getattr(result, "execute", None))
    assert events[-1] == ("b1-exit", None)


@pytest.mark.parametrize(
    ("classification", "code"),
    (
        (
            PaperOperationClassification.ALREADY_APPLIED,
            PaperOperationInspectionCode.ALREADY_APPLIED,
        ),
        (
            PaperOperationClassification.CONFLICTING,
            PaperOperationInspectionCode.CALLER_IDEMPOTENCY_CONFLICT,
        ),
        (
            PaperOperationClassification.BLOCKED,
            PaperOperationInspectionCode.STALE_TERMINAL_CHECKPOINT,
        ),
        (
            PaperOperationClassification.BLOCKED,
            PaperOperationInspectionCode.OPERATION_STAGING_EXISTS,
        ),
    ),
)
def test_every_other_valid_inspection_is_not_ready_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    classification: PaperOperationClassification,
    code: PaperOperationInspectionCode,
) -> None:
    scope, _, events, _ = _fixed_root_case(monkeypatch)
    calls = 0

    def inspector(root, inputs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return _inspection(inputs, classification, code)

    result = _qualify_for_test(scope, inspector)

    assert calls == 1
    assert result.inspection_classification is classification
    assert result.inspection_diagnostic is code
    assert result.qualification_status is (
        qualification.SupervisedPaperOperationQualificationStatus.NOT_READY
    )
    assert events[-1] == ("b1-exit", None)


def test_inspector_exception_propagates_once_and_unwinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, cycle, events, _ = _fixed_root_case(monkeypatch)
    calls = 0

    def inspector(root, inputs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        assert cycle.active
        raise RuntimeError("inspector failed")

    with pytest.raises(RuntimeError, match="inspector failed"):
        _qualify_for_test(scope, inspector)
    assert calls == 1
    assert events[-1] == ("b1-exit", RuntimeError)


def test_wrong_inspector_return_type_fails_closed_once_and_unwinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, _, events, _ = _fixed_root_case(monkeypatch)
    calls = 0

    def inspector(root, inputs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return object()

    with pytest.raises(
        qualification.SupervisedPaperOperationQualificationReconciliationError,
        match="invalid result type",
    ):
        _qualify_for_test(scope, inspector)
    assert calls == 1
    assert events[-1] == (
        "b1-exit",
        qualification.SupervisedPaperOperationQualificationReconciliationError,
    )


@pytest.mark.parametrize(
    "mismatch", ["operation_id", "application_id", "terminal_checkpoint_id"]
)
def test_inspection_identity_mismatch_fails_closed_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    scope, _, events, _ = _fixed_root_case(monkeypatch)
    calls = 0

    def inspector(root, inputs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return replace(_inspection(inputs), **{mismatch: UUID(int=999)})

    with pytest.raises(
        qualification.SupervisedPaperOperationQualificationReconciliationError,
        match="inspection identities",
    ):
        _qualify_for_test(scope, inspector)
    assert calls == 1
    assert events[-1] == (
        "b1-exit",
        qualification.SupervisedPaperOperationQualificationReconciliationError,
    )


def test_abandoned_owner_never_reaches_inspector(
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
        _qualify_for_test(
            scope,
            lambda root, inputs: pytest.fail("abandoned owner reached inspector"),
        )
    assert "post-lock-evidence" not in events
    assert events[-1] == ("b1-exit", None)


def test_gate_change_during_scope_fails_closed_before_inspection_and_unwinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, _, events, _ = _fixed_root_case(monkeypatch)
    original_enter = scope.__class__.__enter__

    def enter_and_enable(self):  # type: ignore[no-untyped-def]
        active = original_enter(self)
        monkeypatch.setattr(
            execution,
            "PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED",
            True,
        )
        return active

    monkeypatch.setattr(scope.__class__, "__enter__", enter_and_enable)
    with pytest.raises(
        qualification.SupervisedPaperOperationQualificationGateError,
        match="must remain disabled",
    ):
        _qualify_for_test(
            scope,
            lambda root, inputs: pytest.fail("changed gate reached inspector"),
        )
    assert events[-1] == (
        "b1-exit",
        qualification.SupervisedPaperOperationQualificationGateError,
    )


def test_pd2d1_surface_keeps_gates_freeze_and_effect_dependencies_closed() -> None:
    assert execution.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED is (
        False
    )
    assert PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False

    import trading_bot.runtime as runtime_public

    assert not hasattr(
        runtime_public,
        "_qualify_prepared_supervised_paper_operation_for_test",
    )
    assert not hasattr(
        runtime_public,
        "_open_disposable_supervised_paper_qualification_authority_for_test",
    )

    source = Path(qualification.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    imported_modules = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert {
        "execute_paper_operation_once",
        "commit_transition_directory",
        "commit_paper_operation_receipt",
    }.isdisjoint(imported_names)
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
            "cli.paper_operation_execution",
        )
    )
    inspector_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "inspector"
    ]
    assert len(inspector_calls) == 1
    assert source.count("inspector=inspect_paper_operation_root") == 1

    freeze_payload = (
        Path(personal_desktop_paper_account_publication_freeze.__file__)
        .read_text(encoding="utf-8")
        .encode("utf-8")
    )
    git_blob_material = (
        b"blob " + str(len(freeze_payload)).encode("ascii") + b"\0" + freeze_payload
    )
    assert (
        sha1(git_blob_material, usedforsecurity=False).hexdigest()
        == "b125cbb1c80a827f74018cf2955b9a27ba69fa90"
    )
