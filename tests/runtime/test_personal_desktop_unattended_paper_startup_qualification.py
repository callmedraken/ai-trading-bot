"""Focused PD4-C read-only unattended startup qualification coverage."""

from __future__ import annotations

import ast
import inspect
from copy import copy, deepcopy
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from tests.market_data.daily_snapshot_test_support import CAPTURED_AT, SPY, calendar
from tests.runtime.test_manual_paper_strategy_plan import (
    _DEFAULT_CONFIG,
    _NEXT_SESSION,
    _verified_seed,
)
from tests.runtime.test_personal_desktop_supervised_paper_operation_preparation import (
    ACCOUNT_ID,
    CALLER_KEY,
    _post_lock_evidence,
    _selected_result,
)
from tests.runtime.test_verified_snapshot_preparation import _policies
from tests.runtime.test_windows_authority_capability import _production_validation

from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    PaperOperationInspectionResult,
)
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime import (
    PersonalDesktopUnattendedPaperStartupQualificationResult,
    PersonalDesktopUnattendedPaperStartupStatus,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_startup_qualification as startup,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexAcquisition,
    PaperAccountMutexState,
    paper_account_mutex_digest,
    paper_account_mutex_name,
)
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_qualification import (
    PaperReceiptRecoveryQualificationDiagnostic,
    PaperReceiptRecoveryQualificationResult,
    PaperReceiptRecoveryQualificationStatus,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageClassification,
    PersonalDesktopUnattendedInvocationStorageDiagnostic,
    PersonalDesktopUnattendedInvocationStorageReadResult,
)

OTHER_ACCOUNT_ID = "8415cd7b-bf36-5fba-bd58-a0f99119dc22"
MISSING_APPLICATION_ID = UUID("60000000-0000-0000-0000-000000000006")
MISSING_PREDECESSOR_ID = UUID("70000000-0000-0000-0000-000000000007")
WRONG_OPERATION_ID = UUID("80000000-0000-0000-0000-000000000008")


class _Account:
    def __init__(self, evidence: object) -> None:
        self.evidence = evidence


class _Admission:
    def __init__(
        self,
        events: list[object],
        account_id: str,
        state: PaperAccountMutexState,
        label: str,
    ) -> None:
        self.events = events
        self.label = label
        self.acquisition = PaperAccountMutexAcquisition(
            account_id,
            paper_account_mutex_name(account_id),
            paper_account_mutex_digest(account_id),
            state,
        )

    def __enter__(self):  # type: ignore[no-untyped-def]
        self.events.append((self.label, "enter"))
        return self

    def __exit__(self, exc_type, exc, traceback):  # type: ignore[no-untyped-def]
        self.events.append((self.label, "exit", exc_type))
        return False


def _inputs() -> startup._PlanningInputs:
    config = _DEFAULT_CONFIG
    return startup._PlanningInputs(
        _verified_seed(config, ("10", "10", "9")),
        config,
        CALLER_KEY,
        startup.CallerAssertedNextSessionOpenReference(
            SPY, _NEXT_SESSION, Decimal("12")
        ),
        _policies(),
        CAPTURED_AT + timedelta(minutes=1),
        CAPTURED_AT + timedelta(minutes=2),
        datetime(2025, 1, 7, 20, tzinfo=UTC),
        (MetadataEntry("source", "pd4-c-test"),),
        (b"historical-plan",),
    )


def _no_recovery(evidence: object | None = None):  # type: ignore[no-untyped-def]
    account = evidence or _post_lock_evidence()
    return PaperReceiptRecoveryQualificationResult(
        PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED,
        PaperReceiptRecoveryQualificationDiagnostic.VERIFIED_COMPLETE_ACCOUNT,
        account.anchor.paper_account_id,
        account.lineage.terminal_checkpoint_id,
        None,
        None,
    )


def _recovery_required(evidence: object | None = None):  # type: ignore[no-untyped-def]
    account = evidence or _post_lock_evidence()
    return PaperReceiptRecoveryQualificationResult(
        PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED,
        PaperReceiptRecoveryQualificationDiagnostic.VERIFIED_TERMINAL_RECEIPT_MISSING,
        account.anchor.paper_account_id,
        account.lineage.terminal_checkpoint_id,
        MISSING_APPLICATION_ID,
        MISSING_PREDECESSOR_ID,
    )


def _recovery_blocked() -> PaperReceiptRecoveryQualificationResult:
    return PaperReceiptRecoveryQualificationResult(
        PaperReceiptRecoveryQualificationStatus.BLOCKED,
        PaperReceiptRecoveryQualificationDiagnostic.VERIFICATION_BLOCKED,
        None,
        None,
        None,
        None,
    )


def _storage_result(classification, expected):  # type: ignore[no-untyped-def]
    diagnostics = {
        PersonalDesktopUnattendedInvocationStorageClassification.ABSENT: (
            PersonalDesktopUnattendedInvocationStorageDiagnostic.VERIFIED_ABSENT
        ),
        PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL: (
            PersonalDesktopUnattendedInvocationStorageDiagnostic.VERIFIED_FINALIZED_IDENTICAL
        ),
        PersonalDesktopUnattendedInvocationStorageClassification.STAGING_PRESENT: (
            PersonalDesktopUnattendedInvocationStorageDiagnostic.STAGING_PRESENT
        ),
        PersonalDesktopUnattendedInvocationStorageClassification.CONFLICTING: (
            PersonalDesktopUnattendedInvocationStorageDiagnostic.VERIFIED_CONFLICT
        ),
        PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED: (
            PersonalDesktopUnattendedInvocationStorageDiagnostic.VERIFICATION_BLOCKED
        ),
    }
    identical = (
        classification
        is PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL
    )
    return PersonalDesktopUnattendedInvocationStorageReadResult(
        classification,
        expected.invocation.invocation_id,
        1 if identical else 0,
        expected.invocation.invocation_id if identical else None,
        diagnostics[classification],
    )


def _changed_account_id(evidence: object, account_id: str) -> object:
    values = vars(evidence).copy()
    values["anchor"] = SimpleNamespace(paper_account_id=account_id)
    return SimpleNamespace(**values)


def _drifted(evidence: object) -> object:
    return SimpleNamespace(**vars(evidence), final_read_drift=True)


def _run(
    *,
    recovery_results: list[PaperReceiptRecoveryQualificationResult] | None = None,
    account_evidences: list[object] | None = None,
    mutex_state: PaperAccountMutexState = PaperAccountMutexState.OWNED,
    mutex_account_id: str = ACCOUNT_ID,
    storage_classification=(
        PersonalDesktopUnattendedInvocationStorageClassification.ABSENT
    ),
    operation_classification: PaperOperationClassification = (
        PaperOperationClassification.PENDING
    ),
    final_operation_classification: PaperOperationClassification | None = None,
    operation_diagnostic: PaperOperationInspectionCode | None = None,
    identity_mismatch: bool = False,
    gates: list[tuple[bool, bool, bool, bool, bool, bool]] | None = None,
    fail_c1_call: int | None = None,
    fail_p2_call: int | None = None,
    build_error: Exception | None = None,
):  # type: ignore[no-untyped-def]
    events: list[object] = []
    evidence = _post_lock_evidence()
    recoveries = list(
        recovery_results or [_no_recovery(evidence), _no_recovery(evidence)]
    )
    accounts = [_Account(item) for item in (account_evidences or [evidence] * 3)]
    gate_values = list(gates or [(False, False, False, False, False, False)])
    selected = _selected_result()
    c1 = object()
    calls = {"c1": 0, "p2": 0}
    inspection_calls = 0

    def validate(authority):  # type: ignore[no-untyped-def]
        calls["c1"] += 1
        events.append(("c1", calls["c1"], authority))
        if calls["c1"] == fail_c1_call:
            raise ValueError("C1 drift")
        return authority

    def match(permit, audit, authority):  # type: ignore[no-untyped-def]
        calls["p2"] += 1
        events.append(("p2", calls["p2"], authority))
        if calls["p2"] == fail_p2_call:
            raise ValueError("P2 drift")

    def qualify(authority, configurations):  # type: ignore[no-untyped-def]
        events.append(("recovery", authority, configurations))
        return recoveries.pop(0)

    def read(authority, configurations):  # type: ignore[no-untyped-def]
        events.append(("account-read", authority, configurations))
        return accounts.pop(0)

    def require_account(account):  # type: ignore[no-untyped-def]
        events.append(("account-evidence", account.evidence))
        return account.evidence

    def admit_healthy(account):  # type: ignore[no-untyped-def]
        events.append(("healthy-admission", account.evidence))
        return _Admission(events, mutex_account_id, mutex_state, "healthy-mutex")

    def admit_recovery(result):  # type: ignore[no-untyped-def]
        events.append(("recovery-admission", result.paper_account_id))
        return _Admission(events, mutex_account_id, mutex_state, "recovery-mutex")

    def build(account, selected_snapshot, planning, identified_calendar):  # type: ignore[no-untyped-def]
        events.append(("build", account))
        if build_error is not None:
            raise build_error
        return startup._prepare_verified_paper_operation_from_account(
            account,
            selected_snapshot,
            history_seed=planning.history_seed,
            strategy_config=planning.strategy_config,
            caller_idempotency_key=planning.caller_idempotency_key,
            open_reference=planning.open_reference,
            policies=planning.policies,
            planning_at=planning.planning_at,
            submitted_at=planning.submitted_at,
            filled_at=planning.filled_at,
            metadata=planning.metadata,
            build_plan=startup.build_manual_paper_strategy_plan,
            verify_plan=startup.verify_manual_paper_strategy_plan,
            calendar=identified_calendar,
        )

    def read_storage(authority, expected):  # type: ignore[no-untyped-def]
        events.append(("storage", authority, expected))
        return _storage_result(storage_classification, expected)

    def inspect_operation(root, material):  # type: ignore[no-untyped-def]
        nonlocal inspection_calls
        inspection_calls += 1
        events.append(("inspect", root, material))
        classification = operation_classification
        if inspection_calls > 1 and final_operation_classification is not None:
            classification = final_operation_classification
        code = operation_diagnostic
        if code is None:
            code = {
                PaperOperationClassification.PENDING: (
                    PaperOperationInspectionCode.PENDING
                ),
                PaperOperationClassification.ALREADY_APPLIED: (
                    PaperOperationInspectionCode.ALREADY_APPLIED
                ),
                PaperOperationClassification.CONFLICTING: (
                    PaperOperationInspectionCode.LINEAGE_CONFLICT
                ),
                PaperOperationClassification.BLOCKED: (
                    PaperOperationInspectionCode.INVALID_OPERATION_STATE
                ),
            }[classification]
        inputs = material
        return PaperOperationInspectionResult(
            classification,
            WRONG_OPERATION_ID if identity_mismatch else inputs.intent.operation_id,
            inputs.intent.prior_lineage_evidence.terminal_checkpoint_id,
            inputs.application_id,
            None,
            (code,),
        )

    def gate_state():  # type: ignore[no-untyped-def]
        value = gate_values.pop(0) if len(gate_values) > 1 else gate_values[0]
        events.append(("gates", value))
        return value

    dependencies = startup._QualificationDependencies(
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
    disposable = startup._create_disposable_startup_qualification_authority_for_test(
        dependencies
    )
    result = startup._qualify_personal_desktop_unattended_paper_startup_for_test(
        disposable, c1, selected, _inputs(), calendar()
    )
    return result, events, disposable


@pytest.mark.parametrize(
    ("storage", "operation", "expected"),
    [
        (
            PersonalDesktopUnattendedInvocationStorageClassification.ABSENT,
            PaperOperationClassification.PENDING,
            PersonalDesktopUnattendedPaperStartupStatus.HEALTHY_NO_PENDING_INVOCATION,
        ),
        (
            PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL,
            PaperOperationClassification.PENDING,
            PersonalDesktopUnattendedPaperStartupStatus.READY_SAME_INVOCATION,
        ),
        (
            PersonalDesktopUnattendedInvocationStorageClassification.ABSENT,
            PaperOperationClassification.ALREADY_APPLIED,
            PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED,
        ),
        (
            PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL,
            PaperOperationClassification.ALREADY_APPLIED,
            PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED,
        ),
    ],
)
def test_exact_b1_a67_classification_matrix(storage, operation, expected):  # type: ignore[no-untyped-def]
    result, events, _ = _run(
        storage_classification=storage,
        operation_classification=operation,
    )

    assert result.status is expected
    assert result.storage_classification is storage
    assert result.operation_classification is operation
    assert sum(event[0] == "inspect" for event in events) == 2


@pytest.mark.parametrize("armed_index", range(6))
def test_every_committed_effect_gate_must_remain_false(armed_index: int) -> None:
    gate = [False] * 6
    gate[armed_index] = True
    result, events, _ = _run(gates=[tuple(gate)])  # type: ignore[list-item]

    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    assert not any(event[0] == "recovery" for event in events)


@pytest.mark.parametrize(
    ("kind", "call"),
    [
        ("c1", 1),
        ("p2", 1),
        ("c1", 3),
        ("p2", 3),
        ("c1", 4),
        ("p2", 4),
    ],
)
def test_c1_p2_provenance_is_checked_before_and_during_mutex(kind, call):  # type: ignore[no-untyped-def]
    result, events, _ = _run(
        fail_c1_call=call if kind == "c1" else None,
        fail_p2_call=call if kind == "p2" else None,
    )

    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    if call == 1:
        assert not any(event[0] == "account-read" for event in events)
    else:
        assert any(event[:2] == ("healthy-mutex", "exit") for event in events)


def test_healthy_order_uses_strict_prelock_read_same_pd2a_mutex_and_postlock_truth():
    pre = _post_lock_evidence()
    pre.prior_checkpoint = object()
    post = _post_lock_evidence()
    result, events, _ = _run(account_evidences=[pre, post, post])

    assert result.status is (
        PersonalDesktopUnattendedPaperStartupStatus.HEALTHY_NO_PENDING_INVOCATION
    )
    names = [event[0] for event in events]
    assert names.index("account-read") < names.index("healthy-admission")
    assert names.index("healthy-admission") < names.index("healthy-mutex")
    build_event = next(event for event in events if event[0] == "build")
    assert build_event[1] is post
    assert build_event[1].prior_checkpoint is not pre.prior_checkpoint
    admission = next(event for event in events if event[0] == "healthy-admission")
    assert admission[1] is pre
    inspect_events = [event for event in events if event[0] == "inspect"]
    assert all(
        event[1] == Path(PERSONAL_DESKTOP_PAPER_V2_RUNTIME) for event in inspect_events
    )
    assert events[-1][:2] == ("healthy-mutex", "exit")


def test_postlock_account_id_must_match_prelock_and_mutex_identity() -> None:
    evidence = _post_lock_evidence()
    changed = _changed_account_id(evidence, OTHER_ACCOUNT_ID)
    result, events, _ = _run(account_evidences=[evidence, changed, changed])

    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    assert not any(event[0] == "build" for event in events)
    result, events, _ = _run(mutex_account_id=OTHER_ACCOUNT_ID)
    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    assert not any(event[0] == "build" for event in events)


def test_abandoned_owner_blocks_and_releases_without_plan_or_a67() -> None:
    result, events, _ = _run(mutex_state=PaperAccountMutexState.ABANDONED_OWNER)

    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    assert result.mutex_acquisition_state is PaperAccountMutexState.ABANDONED_OWNER
    assert not any(event[0] in {"build", "storage", "inspect"} for event in events)
    assert any(event[:2] == ("healthy-mutex", "exit") for event in events)


def test_prelock_recovery_blocked_never_acquires_or_builds() -> None:
    result, events, _ = _run(recovery_results=[_recovery_blocked()])

    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    assert not any("admission" in event[0] for event in events)
    assert not any(event[0] in {"account-read", "build", "inspect"} for event in events)


def test_exact_missing_receipt_is_requalified_twice_while_recovery_mutex_is_held():
    recovery = _recovery_required()
    result, events, _ = _run(recovery_results=[recovery, recovery, recovery])

    assert result.status is (
        PersonalDesktopUnattendedPaperStartupStatus.RECEIPT_RECOVERY_REQUIRED
    )
    assert result.recovery_missing_application_id == MISSING_APPLICATION_ID
    assert result.recovery_predecessor_checkpoint_id == MISSING_PREDECESSOR_ID
    assert sum(event[0] == "recovery" for event in events) == 3
    assert not any(
        event[0] in {"account-read", "build", "storage", "inspect"} for event in events
    )
    assert events[-1][:2] == ("recovery-mutex", "exit")


@pytest.mark.parametrize(
    "drift",
    [_recovery_blocked(), _no_recovery(), None],
)
def test_recovery_required_drift_or_abandonment_blocks(drift) -> None:  # type: ignore[no-untyped-def]
    recovery = _recovery_required()
    if drift is None:
        result, events, _ = _run(
            recovery_results=[recovery],
            mutex_state=PaperAccountMutexState.ABANDONED_OWNER,
        )
    else:
        result, events, _ = _run(recovery_results=[recovery, drift])

    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    assert not any(event[0] in {"build", "storage", "inspect"} for event in events)
    assert any(event[:2] == ("recovery-mutex", "exit") for event in events)


def test_postlock_transition_to_recovery_required_blocks_fresh_path() -> None:
    result, events, _ = _run(recovery_results=[_no_recovery(), _recovery_required()])

    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    assert not any(event[0] in {"build", "storage", "inspect"} for event in events)


@pytest.mark.parametrize(
    "classification",
    [
        PersonalDesktopUnattendedInvocationStorageClassification.STAGING_PRESENT,
        PersonalDesktopUnattendedInvocationStorageClassification.CONFLICTING,
        PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED,
    ],
)
def test_unsafe_b1_storage_states_block_before_a67(classification) -> None:  # type: ignore[no-untyped-def]
    result, events, _ = _run(storage_classification=classification)

    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    assert result.storage_classification is classification
    assert not any(event[0] == "inspect" for event in events)


@pytest.mark.parametrize(
    ("classification", "diagnostic"),
    [
        (
            PaperOperationClassification.CONFLICTING,
            PaperOperationInspectionCode.LINEAGE_CONFLICT,
        ),
        (
            PaperOperationClassification.BLOCKED,
            PaperOperationInspectionCode.AMBIGUOUS_OPERATION_STATE,
        ),
        (
            PaperOperationClassification.PENDING,
            PaperOperationInspectionCode.ALREADY_APPLIED,
        ),
        (
            PaperOperationClassification.ALREADY_APPLIED,
            PaperOperationInspectionCode.PENDING,
        ),
    ],
)
def test_conflicting_ambiguous_or_identity_mismatched_a67_blocks(
    classification, diagnostic
):  # type: ignore[no-untyped-def]
    result, _, _ = _run(
        operation_classification=classification,
        operation_diagnostic=diagnostic,
    )
    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED

    result, _, _ = _run(identity_mismatch=True)
    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED


def test_exact_postlock_plan_and_invocation_replay_are_mandatory(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    result, events, _ = _run(build_error=ValueError("plan replay differs"))
    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    assert not any(event[0] == "storage" for event in events)

    monkeypatch.setattr(
        startup,
        "verify_personal_desktop_unattended_paper_invocation",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("replay differs")),
    )
    result, events, _ = _run()
    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    assert not any(event[0] == "storage" for event in events)


def test_expected_invocation_and_a67_inputs_derive_only_from_postlock_plan() -> None:
    result, events, _ = _run()
    build_account = next(event[1] for event in events if event[0] == "build")
    expected = next(event[2] for event in events if event[0] == "storage")
    inspection_inputs = next(event[2] for event in events if event[0] == "inspect")

    assert expected.replayed_plan.plan.prior_checkpoint.checkpoint_id == (
        build_account.prior_checkpoint.checkpoint_id
    )
    assert expected.invocation.paper_account_id == build_account.anchor.paper_account_id
    assert result.operation_id == inspection_inputs.intent.operation_id
    assert result.application_id == inspection_inputs.application_id


def test_final_account_reread_and_c1_p2_gate_drift_protection_stay_under_mutex():
    evidence = _post_lock_evidence()
    result, events, _ = _run(account_evidences=[evidence, evidence, _drifted(evidence)])
    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    final_read_index = max(
        index for index, event in enumerate(events) if event[0] == "account-read"
    )
    exit_index = next(
        index
        for index, event in enumerate(events)
        if event[:2] == ("healthy-mutex", "exit")
    )
    assert final_read_index < exit_index

    closed = (False, False, False, False, False, False)
    drifted = (False, False, False, False, True, False)
    result, _, _ = _run(gates=[closed, closed, drifted])
    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    result, _, _ = _run(gates=[closed, closed, closed, drifted])
    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    result, _, _ = _run(
        final_operation_classification=PaperOperationClassification.ALREADY_APPLIED
    )
    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED


def test_mutex_releases_on_body_exception_and_disposable_seam_is_one_shot():
    result, events, disposable = _run(build_error=RuntimeError("stop"))

    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    assert any(event[:2] == ("healthy-mutex", "exit") for event in events)
    with pytest.raises(TypeError, match="spent"):
        startup._qualify_personal_desktop_unattended_paper_startup_for_test(
            disposable, object(), _selected_result(), _inputs(), calendar()
        )
    with pytest.raises(TypeError):
        copy(disposable)
    with pytest.raises(TypeError):
        deepcopy(disposable)


def test_public_result_is_sanitized_non_authorizing_and_no_effect_surface_is_called():
    result, events, _ = _run()
    names = {field.name for field in fields(result)}

    assert type(result) is PersonalDesktopUnattendedPaperStartupQualificationResult
    assert not names & {
        "path",
        "artifact_bytes",
        "plan_bytes",
        "handle",
        "mutex_name",
        "mutex_digest",
        "output_capability",
        "execution_inputs",
        "authority",
        "recovery_authority",
    }
    assert not any(
        event[0] in {"publish", "execute", "recover", "provider", "broker", "scheduler"}
        for event in events
    )
    tree = ast.parse(inspect.getsource(startup))
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not called_names & {
        "execute_paper_operation",
        "recover_paper_operation_receipt",
        "publish_personal_desktop_unattended_invocation",
    }


def test_public_boundary_rejects_forged_c1_and_p2_before_any_account_read(monkeypatch):  # type: ignore[no-untyped-def]
    forbidden = lambda *args, **kwargs: (_ for _ in ()).throw(  # noqa: E731
        AssertionError("filesystem read reached")
    )
    monkeypatch.setattr(startup, "read_personal_desktop_paper_account", forbidden)
    monkeypatch.setattr(
        startup, "qualify_personal_desktop_paper_receipt_recovery", forbidden
    )
    kwargs = dict(
        history_seed=_inputs().history_seed,
        strategy_config=_inputs().strategy_config,
        caller_idempotency_key=CALLER_KEY,
        open_reference=_inputs().open_reference,
        policies=_inputs().policies,
        planning_at=_inputs().planning_at,
        submitted_at=_inputs().submitted_at,
        filled_at=_inputs().filled_at,
    )
    result = startup.qualify_personal_desktop_unattended_paper_startup(
        object(),  # type: ignore[arg-type]
        _selected_result(),
        **kwargs,
    )
    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED

    result = startup.qualify_personal_desktop_unattended_paper_startup(
        _production_validation(monkeypatch),
        _selected_result(),
        **kwargs,
    )
    assert result.status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED


def test_same_existing_pd2a_admission_is_composed_without_new_lock_or_effect_api():
    source = inspect.getsource(startup)

    assert "supervised_paper_cycle_admission" in source
    assert "paper_receipt_recovery_admission" in source
    assert "_PaperAccountMutex(" not in source
    assert "PAPER_ACCOUNT_MUTEX_WAIT_MILLISECONDS" not in source
    assert "output_capability" not in source
