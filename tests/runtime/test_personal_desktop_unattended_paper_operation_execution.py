"""Focused PD4-D unattended Paper-v2 composition coverage."""

from __future__ import annotations

import ast
import inspect
from copy import copy, deepcopy
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from tests.market_data.daily_snapshot_test_support import calendar
from tests.runtime.test_personal_desktop_supervised_paper_operation_preparation import (
    ACCOUNT_ID,
    _post_lock_evidence,
    _selected_result,
)
from tests.runtime.test_personal_desktop_unattended_paper_startup_qualification import (
    _Admission,
    _inputs,
    _no_recovery,
    _recovery_blocked,
    _recovery_required,
    _storage_result,
)

from trading_bot.cli.paper_operation_execution import (
    PaperOperationExecutionClassification,
    PaperOperationExecutionDiagnosticCode,
    PaperOperationExecutionResult,
)
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    PaperOperationInspectionResult,
)
from trading_bot.runtime import (
    CheckpointedVerifiedSnapshotPaperCycleStatus,
    PersonalDesktopUnattendedPaperStartupQualificationResult,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_operation_execution as execution,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_startup_qualification as startup,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexState,
)
from trading_bot.runtime.personal_desktop_paper_runtime_output import (
    PersonalDesktopUnattendedInvocationPublicationResult,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageClassification,
)

SUCCESSOR_ID = UUID("90000000-0000-0000-0000-000000000009")
CYCLE_RESULT_ID = UUID("91000000-0000-0000-0000-000000000009")
WRONG_ID = UUID("92000000-0000-0000-0000-000000000009")
DISABLED = (False, False, False, False, False, False)
ENABLED = (False, False, False, False, True, False)
_Status = execution.PersonalDesktopUnattendedPaperOperationStatus


class _Capability:
    def __init__(self, events: list[object], name: str, binding: object = None) -> None:
        self.events = events
        self.name = name
        self.binding = binding

    def __enter__(self):  # type: ignore[no-untyped-def]
        self.events.append((self.name, "enter"))
        return self

    def __exit__(self, exc_type, exc, traceback):  # type: ignore[no-untyped-def]
        self.events.append((self.name, "exit", exc_type))
        return False

    def publish(self) -> PersonalDesktopUnattendedInvocationPublicationResult:
        self.events.append(("publish", self.binding))
        binding = self.binding
        return PersonalDesktopUnattendedInvocationPublicationResult(
            binding.invocation.invocation_id,
            binding.artifact_sha256,
            binding.artifact_byte_length,
            True,
            True,
            True,
        )


def _inspection(inputs, classification, *, wrong_identity=False):  # type: ignore[no-untyped-def]
    diagnostic = {
        PaperOperationClassification.PENDING: PaperOperationInspectionCode.PENDING,
        PaperOperationClassification.ALREADY_APPLIED: (
            PaperOperationInspectionCode.ALREADY_APPLIED
        ),
        PaperOperationClassification.BLOCKED: (
            PaperOperationInspectionCode.AMBIGUOUS_OPERATION_STATE
        ),
        PaperOperationClassification.CONFLICTING: (
            PaperOperationInspectionCode.LINEAGE_CONFLICT
        ),
    }[classification]
    return PaperOperationInspectionResult(
        classification,
        WRONG_ID if wrong_identity else inputs.intent.operation_id,
        inputs.intent.prior_lineage_evidence.terminal_checkpoint_id,
        inputs.application_id,
        None,
        (diagnostic,),
    )


def _completed_account(base, material, *, wrong_receipt=False):  # type: ignore[no-untyped-def]
    successor = SimpleNamespace(terminal_checkpoint_id=SUCCESSOR_ID)
    receipt = SimpleNamespace(
        receipt_id=(
            WRONG_ID if wrong_receipt else material.execution_inputs.intent.operation_id
        ),
        application_id=material.execution_inputs.application_id,
        status=execution.PaperOperationStatus.COMPLETED,
        intent=material.execution_inputs.intent,
        prior_lineage_evidence=(
            material.execution_inputs.intent.prior_lineage_evidence
        ),
        successor_lineage_evidence=successor,
        cycle_result_id=CYCLE_RESULT_ID,
    )
    values = vars(base).copy()
    values.update(lineage=successor, receipts=(receipt,))
    return SimpleNamespace(**values)


def _execution_result(material, classification, *, wrong_identity=False):  # type: ignore[no-untyped-def]
    completed = classification in {
        PaperOperationExecutionClassification.COMPLETED,
        PaperOperationExecutionClassification.RECEIPT_RECOVERED,
    }
    pre = {
        PaperOperationExecutionClassification.COMPLETED: (
            PaperOperationClassification.PENDING
        ),
        PaperOperationExecutionClassification.RECEIPT_RECOVERED: (
            PaperOperationClassification.BLOCKED
        ),
        PaperOperationExecutionClassification.ALREADY_APPLIED: (
            PaperOperationClassification.ALREADY_APPLIED
        ),
    }.get(classification, PaperOperationClassification.PENDING)
    diagnostic = {
        PaperOperationExecutionClassification.COMPLETED: (
            PaperOperationExecutionDiagnosticCode.COMPLETED.value
        ),
        PaperOperationExecutionClassification.RECEIPT_RECOVERED: (
            PaperOperationExecutionDiagnosticCode.RECEIPT_RECOVERED.value
        ),
        PaperOperationExecutionClassification.ALREADY_APPLIED: (
            PaperOperationInspectionCode.ALREADY_APPLIED.value
        ),
    }.get(classification, "FAILED")
    return PaperOperationExecutionResult(
        classification,
        WRONG_ID if wrong_identity else material.execution_inputs.intent.operation_id,
        pre,
        material.execution_inputs.intent.prior_lineage_evidence.terminal_checkpoint_id,
        material.execution_inputs.application_id,
        CYCLE_RESULT_ID if completed else None,
        SUCCESSOR_ID if completed else None,
        Path("transition") if completed else None,
        Path("receipt") if completed else None,
        CheckpointedVerifiedSnapshotPaperCycleStatus.NO_ACTION if completed else None,
        diagnostic,
    )


def _case(
    *,
    gate_states: list[tuple[bool, bool, bool, bool, bool, bool]] | None = None,
    storage_states: list[PersonalDesktopUnattendedInvocationStorageClassification]
    | None = None,
    inspections: list[PaperOperationClassification] | None = None,
    recovery_results: list[object] | None = None,
    mutex_state: PaperAccountMutexState = PaperAccountMutexState.OWNED,
    executor_classification: PaperOperationExecutionClassification = (
        PaperOperationExecutionClassification.COMPLETED
    ),
    executor_wrong_identity: bool = False,
    final_receipt_wrong: bool = False,
    inspection_wrong_identity: bool = False,
    fail_c1_call: int | None = None,
    fail_p2_call: int | None = None,
    read_only_completed: bool = False,
):
    events: list[object] = []
    base = _post_lock_evidence()
    base.receipts = ()
    selected = _selected_result()
    planning = _inputs()
    gates = list(gate_states or [ENABLED])
    read_only = gates[0] == DISABLED
    stores = list(
        storage_states
        or [
            PersonalDesktopUnattendedInvocationStorageClassification.ABSENT,
            PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL,
            PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL,
        ]
    )
    inspection_states = list(
        inspections
        or [
            PaperOperationClassification.PENDING,
            PaperOperationClassification.PENDING,
            PaperOperationClassification.ALREADY_APPLIED,
        ]
    )
    recoveries = list(recovery_results or [_no_recovery(base), _no_recovery(base)])
    state: dict[str, object] = {"read_count": 0, "c1_count": 0, "p2_count": 0}

    def validate(authority):  # type: ignore[no-untyped-def]
        state["c1_count"] = int(state["c1_count"]) + 1
        events.append(("c1", authority))
        if state["c1_count"] == fail_c1_call:
            raise ValueError("C1 drift")
        return authority

    def match(permit, audit, authority):  # type: ignore[no-untyped-def]
        state["p2_count"] = int(state["p2_count"]) + 1
        events.append(("p2", authority))
        if state["p2_count"] == fail_p2_call:
            raise ValueError("P2 drift")

    def qualify(authority, configurations):  # type: ignore[no-untyped-def]
        events.append(("recovery", configurations))
        return recoveries.pop(0)

    def read(authority, configurations):  # type: ignore[no-untyped-def]
        state["read_count"] = int(state["read_count"]) + 1
        events.append(("account-read", configurations))
        if (
            (read_only and not read_only_completed)
            or state["read_count"] < 3
            or "material" not in state
        ):
            return SimpleNamespace(evidence=base)
        return SimpleNamespace(
            evidence=_completed_account(
                base, state["material"], wrong_receipt=final_receipt_wrong
            )
        )

    def require_account(value):  # type: ignore[no-untyped-def]
        return value.evidence

    def admit_healthy(value):  # type: ignore[no-untyped-def]
        events.append(("healthy-admission", value.evidence))
        return _Admission(events, ACCOUNT_ID, mutex_state, "mutex")

    def admit_recovery(value):  # type: ignore[no-untyped-def]
        events.append(("recovery-admission", value.paper_account_id))
        return _Admission(events, ACCOUNT_ID, mutex_state, "mutex")

    def build(account, snapshot, inputs, identified_calendar):  # type: ignore[no-untyped-def]
        material = startup._prepare_verified_paper_operation_from_account(
            account,
            snapshot,
            history_seed=inputs.history_seed,
            strategy_config=inputs.strategy_config,
            caller_idempotency_key=inputs.caller_idempotency_key,
            open_reference=inputs.open_reference,
            policies=inputs.policies,
            planning_at=inputs.planning_at,
            submitted_at=inputs.submitted_at,
            filled_at=inputs.filled_at,
            metadata=inputs.metadata,
            build_plan=startup.build_manual_paper_strategy_plan,
            verify_plan=startup.verify_manual_paper_strategy_plan,
            calendar=identified_calendar,
        )
        state["material"] = material
        state["pre_durable_material"] = material
        events.append(("build", material))
        return material

    def read_storage(authority, expected):  # type: ignore[no-untyped-def]
        classification = stores.pop(0) if len(stores) > 1 else stores[0]
        result = _storage_result(classification, expected)
        state["expected"] = expected
        events.append(("storage", classification, result))
        return result

    def inspect_operation(root, inputs):  # type: ignore[no-untyped-def]
        classification = (
            inspection_states.pop(0)
            if len(inspection_states) > 1
            else inspection_states[0]
        )
        events.append(("inspect", classification, inputs))
        return _inspection(
            inputs,
            classification,
            wrong_identity=inspection_wrong_identity,
        )

    def gate_state():  # type: ignore[no-untyped-def]
        value = gates.pop(0) if len(gates) > 1 else gates[0]
        events.append(("gates", value))
        return value

    qualification = startup._QualificationDependencies(
        validate,
        match,
        qualify,
        read,
        require_account,
        admit_healthy,
        admit_recovery,
        build,
        read_storage,
        inspect_operation,
        gate_state,
    )

    def resolve_storage(result):  # type: ignore[no-untyped-def]
        expected = state["expected"]
        actual = deepcopy(expected)
        events.append(("resolve-storage", result, actual, expected))
        return actual

    def open_publisher(result):  # type: ignore[no-untyped-def]
        events.append(("open-publisher", result))
        return _Capability(events, "publisher", state["expected"])

    def reconstruct(account, snapshot, plan, identified_calendar):  # type: ignore[no-untyped-def]
        events.append(("reconstruct", plan))
        material = execution._reconstruct_verified_paper_operation_from_plan(
            account, snapshot, plan, identified_calendar
        )
        state["material"] = material
        return material

    def open_output():  # type: ignore[no-untyped-def]
        events.append(("open-output",))
        return _Capability(events, "output")

    def execute_operation(root, inputs, output):  # type: ignore[no-untyped-def]
        events.append(("execute", root, inputs, output))
        return _execution_result(
            state["material"],
            executor_classification,
            wrong_identity=executor_wrong_identity,
        )

    dependencies = execution._ExecutionDependencies(
        qualification,
        resolve_storage,
        open_publisher,
        reconstruct,
        open_output,
        execute_operation,
    )
    disposable = (
        execution._open_disposable_unattended_paper_execution_authority_for_test(
            dependencies
        )
    )
    try:
        result = (
            execution._execute_personal_desktop_unattended_paper_operation_for_test(
                disposable, object(), selected, planning, calendar()
            )
        )
    except execution.PersonalDesktopUnattendedPaperEffectsDisabledError as error:
        result = error
    return result, events, disposable, state


def test_exact_two_six_gate_states_are_accepted_and_committed_gate_is_false() -> None:
    assert (
        execution.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED
        is False
    )
    disabled, _, _, _ = _case(
        gate_states=[DISABLED],
        storage_states=[
            PersonalDesktopUnattendedInvocationStorageClassification.ABSENT
        ],
        inspections=[PaperOperationClassification.PENDING],
    )
    assert isinstance(
        disabled, execution.PersonalDesktopUnattendedPaperEffectsDisabledError
    )

    for index in range(6):
        invalid = list(DISABLED)
        invalid[index] = True
        if tuple(invalid) == ENABLED:
            continue
        result, events, _, _ = _case(gate_states=[tuple(invalid)])
        assert (
            result.status
            is execution.PersonalDesktopUnattendedPaperOperationStatus.BLOCKED
        )
        assert not any(
            event[0] in {"open-publisher", "open-output", "execute"} for event in events
        )
    result, _, _, _ = _case(
        gate_states=[(0, False, False, False, False, False)]  # type: ignore[list-item]
    )
    assert result.status is _Status.BLOCKED


def test_disabled_pending_finishes_read_only_without_effect_construction() -> None:
    result, events, _, state = _case(
        gate_states=[DISABLED],
        storage_states=[
            PersonalDesktopUnattendedInvocationStorageClassification.ABSENT
        ],
        inspections=[PaperOperationClassification.PENDING],
    )
    assert isinstance(
        result, execution.PersonalDesktopUnattendedPaperEffectsDisabledError
    )
    assert int(state["read_count"]) == 3
    assert sum(event[0] == "storage" for event in events) == 2
    assert sum(event[0] == "inspect" for event in events) == 2
    assert not any(
        event[0] in {"open-publisher", "open-output", "execute"} for event in events
    )
    assert events[-1][:2] == ("mutex", "exit")


def test_recovery_required_and_abandoned_mutex_never_reach_any_effect() -> None:
    recovery = _recovery_required()
    result, events, _, _ = _case(recovery_results=[recovery, recovery, recovery])
    assert result.status is _Status.RECEIPT_RECOVERY_REQUIRED
    assert not any(
        event[0]
        in {"build", "storage", "inspect", "open-publisher", "open-output", "execute"}
        for event in events
    )

    result, events, _, _ = _case(mutex_state=PaperAccountMutexState.ABANDONED_OWNER)
    assert (
        result.status is execution.PersonalDesktopUnattendedPaperOperationStatus.BLOCKED
    )
    assert not any(
        event[0]
        in {"build", "storage", "inspect", "open-publisher", "open-output", "execute"}
        for event in events
    )


@pytest.mark.parametrize(
    "classification",
    [
        PersonalDesktopUnattendedInvocationStorageClassification.STAGING_PRESENT,
        PersonalDesktopUnattendedInvocationStorageClassification.CONFLICTING,
        PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED,
    ],
)
def test_unsafe_b1_states_block_before_publication_or_execution(classification) -> None:  # type: ignore[no-untyped-def]
    result, events, _, _ = _case(storage_states=[classification])
    assert (
        result.status is execution.PersonalDesktopUnattendedPaperOperationStatus.BLOCKED
    )
    assert not any(
        event[0] in {"open-publisher", "open-output", "execute"} for event in events
    )


def test_absent_pending_publishes_once_closes_rereads_then_executes_once() -> None:
    result, events, _, state = _case()
    assert (
        result.status
        is execution.PersonalDesktopUnattendedPaperOperationStatus.COMPLETED
    )
    assert result.invocation_published is True
    assert result.executor_called is True
    assert sum(event[0] == "publish" for event in events) == 1
    assert sum(event[0] == "execute" for event in events) == 1
    names = [event[0] for event in events]
    assert names.index("publisher") < names.index("resolve-storage")
    publisher_exit = next(
        i for i, event in enumerate(events) if event[:2] == ("publisher", "exit")
    )
    execute_index = names.index("execute")
    output_exit = next(
        i for i, event in enumerate(events) if event[:2] == ("output", "exit")
    )
    final_read = max(i for i, event in enumerate(events) if event[0] == "account-read")
    mutex_exit = next(
        i for i, event in enumerate(events) if event[:2] == ("mutex", "exit")
    )
    assert publisher_exit < execute_index < output_exit < final_read < mutex_exit
    assert (
        state["material"].plan_binding.artifact_bytes
        in [event[1] for event in events if event[0] == "account-read"][-1]
    )
    assert execution._configuration_dependencies(
        (b"same", b"other", b"same"), b"same"
    ) == (b"same", b"other")


def test_finalized_identical_uses_actual_binding_without_republication() -> None:
    result, events, _, state = _case(
        storage_states=[
            PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL
        ],
        inspections=[
            PaperOperationClassification.PENDING,
            PaperOperationClassification.PENDING,
            PaperOperationClassification.PENDING,
            PaperOperationClassification.ALREADY_APPLIED,
        ],
    )
    assert (
        result.status
        is execution.PersonalDesktopUnattendedPaperOperationStatus.COMPLETED
    )
    assert result.invocation_published is False
    assert not any(event[0] in {"open-publisher", "publish"} for event in events)
    resolved = next(event[2] for event in events if event[0] == "resolve-storage")
    reconstructed = next(event[1] for event in events if event[0] == "reconstruct")
    assert reconstructed is resolved.replayed_plan
    assert reconstructed is not state["pre_durable_material"].plan_binding
    assert state["material"].plan_binding is reconstructed


def test_post_durable_reinspection_and_already_applied_are_zero_write() -> None:
    result, events, _, _ = _case(
        storage_states=[
            PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL
        ],
        inspections=[
            PaperOperationClassification.ALREADY_APPLIED,
            PaperOperationClassification.ALREADY_APPLIED,
            PaperOperationClassification.ALREADY_APPLIED,
        ],
    )
    assert (
        result.status
        is execution.PersonalDesktopUnattendedPaperOperationStatus.ALREADY_APPLIED
    )
    assert sum(event[0] == "inspect" for event in events) == 3
    assert not any(
        event[0] in {"open-publisher", "publish", "open-output", "execute"}
        for event in events
    )

    result, events, _, _ = _case(
        gate_states=[DISABLED],
        storage_states=[
            PersonalDesktopUnattendedInvocationStorageClassification.ABSENT
        ],
        inspections=[PaperOperationClassification.ALREADY_APPLIED],
        read_only_completed=True,
    )
    assert result.status is _Status.ALREADY_APPLIED
    assert not any(
        event[0] in {"open-publisher", "publish", "open-output", "execute"}
        for event in events
    )


def test_executor_internal_already_applied_convergence_is_accepted() -> None:
    result, events, _, _ = _case(
        executor_classification=PaperOperationExecutionClassification.ALREADY_APPLIED
    )
    assert result.status is _Status.ALREADY_APPLIED
    assert result.executor_called is True
    assert sum(event[0] == "execute" for event in events) == 1


@pytest.mark.parametrize(
    "classification",
    [
        PaperOperationExecutionClassification.RECEIPT_RECOVERED,
        PaperOperationExecutionClassification.EXECUTION_FAILED,
        PaperOperationExecutionClassification.BLOCKED,
        PaperOperationExecutionClassification.CONFLICTING,
    ],
)
def test_nonfresh_success_executor_results_block_without_retry(classification) -> None:  # type: ignore[no-untyped-def]
    result, events, _, _ = _case(executor_classification=classification)
    assert (
        result.status is execution.PersonalDesktopUnattendedPaperOperationStatus.BLOCKED
    )
    assert sum(event[0] == "execute" for event in events) == 1
    assert not any(event[0] in {"cleanup", "retry", "recover"} for event in events)


def test_execution_identity_mismatch_and_final_reconciliation_fail_closed() -> None:
    result, events, _, _ = _case(executor_wrong_identity=True)
    assert (
        result.status is execution.PersonalDesktopUnattendedPaperOperationStatus.BLOCKED
    )
    assert sum(event[0] == "execute" for event in events) == 1

    result, _, _, _ = _case(final_receipt_wrong=True)
    assert (
        result.status is execution.PersonalDesktopUnattendedPaperOperationStatus.BLOCKED
    )

    result, events, _, _ = _case(
        inspections=[
            PaperOperationClassification.PENDING,
            PaperOperationClassification.PENDING,
            PaperOperationClassification.PENDING,
        ]
    )
    assert (
        result.status is execution.PersonalDesktopUnattendedPaperOperationStatus.BLOCKED
    )
    assert sum(event[0] == "execute" for event in events) == 1


def test_final_b1_and_gate_drift_after_write_block_without_cleanup_or_retry() -> None:
    result, events, _, _ = _case(
        storage_states=[
            PersonalDesktopUnattendedInvocationStorageClassification.ABSENT,
            PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL,
            PersonalDesktopUnattendedInvocationStorageClassification.CONFLICTING,
        ]
    )
    assert (
        result.status is execution.PersonalDesktopUnattendedPaperOperationStatus.BLOCKED
    )
    assert sum(event[0] == "publish" for event in events) == 1
    assert sum(event[0] == "execute" for event in events) == 1

    result, events, _, _ = _case(gate_states=[ENABLED] * 4 + [DISABLED])
    assert (
        result.status is execution.PersonalDesktopUnattendedPaperOperationStatus.BLOCKED
    )
    assert sum(event[0] == "execute" for event in events) <= 1
    assert not any(event[0] in {"cleanup", "retry", "recover"} for event in events)

    for failure in ("c1", "p2"):
        result, events, _, _ = _case(
            fail_c1_call=5 if failure == "c1" else None,
            fail_p2_call=5 if failure == "p2" else None,
        )
        assert result.status is _Status.BLOCKED
        assert sum(event[0] == "execute" for event in events) == 1
        assert not any(event[0] in {"cleanup", "retry", "recover"} for event in events)


def test_disposable_authority_is_one_shot_and_rejects_production_mutators() -> None:
    _, _, disposable, _ = _case()
    with pytest.raises(TypeError, match="spent"):
        execution._execute_personal_desktop_unattended_paper_operation_for_test(
            disposable, object(), _selected_result(), _inputs(), calendar()
        )
    with pytest.raises(TypeError):
        copy(disposable)
    with pytest.raises(TypeError):
        deepcopy(disposable)

    dependencies = execution._production_execution_dependencies()
    with pytest.raises(TypeError, match="production mutation"):
        execution._open_disposable_unattended_paper_execution_authority_for_test(
            dependencies
        )


def test_pd4_c_public_result_is_not_execution_authority_and_result_is_sanitized() -> (
    None
):
    assert (
        "PersonalDesktopUnattendedPaperStartupQualificationResult"
        not in inspect.getsource(execution)
    )
    assert (
        "startup_qualification_result"
        not in inspect.signature(
            execution.execute_personal_desktop_unattended_paper_operation
        ).parameters
    )
    assert PersonalDesktopUnattendedPaperStartupQualificationResult not in {
        field.type
        for field in fields(execution.PersonalDesktopUnattendedPaperOperationResult)
    }
    planning = _inputs()
    forged = startup._blocked_result()
    rejected = execution.execute_personal_desktop_unattended_paper_operation(
        forged,  # type: ignore[arg-type]
        _selected_result(),
        history_seed=planning.history_seed,
        strategy_config=planning.strategy_config,
        caller_idempotency_key=planning.caller_idempotency_key,
        open_reference=planning.open_reference,
        policies=planning.policies,
        planning_at=planning.planning_at,
        submitted_at=planning.submitted_at,
        filled_at=planning.filled_at,
        metadata=planning.metadata,
        historical_cycle_configuration_payloads=planning.historical_configurations,
    )
    assert rejected.status is _Status.BLOCKED
    assert rejected.executor_called is False
    assert rejected.invocation_published is False
    result, events, _, _ = _case()
    names = {field.name for field in fields(result)}
    assert not names & {
        "path",
        "artifact_bytes",
        "plan_bytes",
        "handle",
        "mutex_name",
        "mutex_digest",
        "execution_inputs",
        "output_capability",
        "storage_authority",
    }
    tree = ast.parse(inspect.getsource(execution))
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "recover_paper_operation_receipt_once" not in called
    assert not any(event[0] in {"provider", "broker", "scheduler"} for event in events)


def test_prelock_recovery_blocked_stops_before_mutex_or_effects() -> None:
    result, events, _, _ = _case(recovery_results=[_recovery_blocked()])
    assert (
        result.status is execution.PersonalDesktopUnattendedPaperOperationStatus.BLOCKED
    )
    assert not any(
        event[0] in {"mutex", "open-publisher", "open-output", "execute"}
        for event in events
    )
