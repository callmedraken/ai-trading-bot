"""PD3-D2 source-owned receipt-recovery composition and ordering."""

from __future__ import annotations

import ast
import inspect
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from tests.runtime.test_personal_desktop_paper_receipt_recovery_reconstruction import (
    reconstruction_case as reconstruction_case,
)

from trading_bot.cli.paper_operation_execution import (
    PaperOperationExecutionClassification,
)
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    PaperOperationInspectionResult,
)
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import (
    personal_desktop_paper_receipt_recovery_execution as execution,
)
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as supervised_execution,
)
from trading_bot.runtime.paper_operation import PaperOperationStatus
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexAcquisition,
    PaperAccountMutexState,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_qualification import (
    PaperReceiptRecoveryQualificationDiagnostic,
    PaperReceiptRecoveryQualificationResult,
    PaperReceiptRecoveryQualificationStatus,
)

ACCOUNT = "11111111-1111-1111-1111-111111111111"
OPERATION = UUID("22222222-2222-2222-2222-222222222222")
APPLICATION = UUID("33333333-3333-3333-3333-333333333333")
PREDECESSOR = UUID("44444444-4444-4444-4444-444444444444")
TERMINAL = UUID("55555555-5555-5555-5555-555555555555")
NOW = datetime(2026, 1, 1, tzinfo=UTC)
CONFIGURATION = b'{"configuration":"current"}'


def _qualification(
    status: PaperReceiptRecoveryQualificationStatus,
    *,
    application: UUID = APPLICATION,
) -> PaperReceiptRecoveryQualificationResult:
    if status is PaperReceiptRecoveryQualificationStatus.BLOCKED:
        return PaperReceiptRecoveryQualificationResult(
            status,
            PaperReceiptRecoveryQualificationDiagnostic.VERIFICATION_BLOCKED,
            None,
            None,
            None,
            None,
        )
    if status is PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED:
        return PaperReceiptRecoveryQualificationResult(
            status,
            PaperReceiptRecoveryQualificationDiagnostic.VERIFIED_COMPLETE_ACCOUNT,
            ACCOUNT,
            TERMINAL,
            None,
            None,
        )
    return PaperReceiptRecoveryQualificationResult(
        status,
        PaperReceiptRecoveryQualificationDiagnostic.VERIFIED_TERMINAL_RECEIPT_MISSING,
        ACCOUNT,
        TERMINAL,
        application,
        PREDECESSOR,
    )


def _inspection(
    classification: PaperOperationClassification,
    *,
    operation: UUID = OPERATION,
    application: UUID = APPLICATION,
    terminal: UUID = PREDECESSOR,
) -> PaperOperationInspectionResult:
    diagnostic = {
        PaperOperationClassification.BLOCKED: (
            PaperOperationInspectionCode.FINALIZED_TRANSITION_WITHOUT_RECEIPT
        ),
        PaperOperationClassification.ALREADY_APPLIED: (
            PaperOperationInspectionCode.ALREADY_APPLIED
        ),
        PaperOperationClassification.PENDING: PaperOperationInspectionCode.PENDING,
        PaperOperationClassification.CONFLICTING: (
            PaperOperationInspectionCode.CALLER_IDEMPOTENCY_CONFLICT
        ),
    }[classification]
    return PaperOperationInspectionResult(
        classification,
        operation,
        terminal,
        application,
        None,
        (diagnostic,),
    )


def _binding() -> SimpleNamespace:
    result = SimpleNamespace(
        paper_account_id=ACCOUNT,
        operation_id=OPERATION,
        application_id=APPLICATION,
        predecessor_checkpoint_id=PREDECESSOR,
        installed_terminal_checkpoint_id=TERMINAL,
        inspection_classification=PaperOperationClassification.BLOCKED,
        inspection_diagnostic=(
            PaperOperationInspectionCode.FINALIZED_TRANSITION_WITHOUT_RECEIPT
        ),
    )
    inputs = SimpleNamespace(
        intent=SimpleNamespace(operation_id=OPERATION),
        application_id=APPLICATION,
        cycle_configuration_payload=CONFIGURATION,
    )
    return SimpleNamespace(result=result, execution_inputs=inputs)


def _recovery_result(
    classification: PaperOperationExecutionClassification = (
        PaperOperationExecutionClassification.RECEIPT_RECOVERED
    ),
    *,
    operation: UUID = OPERATION,
    application: UUID = APPLICATION,
) -> SimpleNamespace:
    recovered = (
        classification is PaperOperationExecutionClassification.RECEIPT_RECOVERED
    )
    return SimpleNamespace(
        classification=classification,
        diagnostic_code="RECEIPT_RECOVERED" if recovered else classification.value,
        operation_id=operation,
        application_id=application,
        terminal_checkpoint_id=PREDECESSOR,
        pre_execution_classification=(
            PaperOperationClassification.BLOCKED
            if recovered
            else PaperOperationClassification.ALREADY_APPLIED
        ),
        successor_checkpoint_id=TERMINAL if recovered else None,
        receipt_path=Path("disposable-receipt") if recovered else None,
    )


def _post_evidence(*, include_receipt: bool = True) -> SimpleNamespace:
    receipt = SimpleNamespace(
        receipt_id=OPERATION,
        application_id=APPLICATION,
        status=PaperOperationStatus.COMPLETED,
        intent=SimpleNamespace(operation_id=OPERATION),
        prior_lineage_evidence=SimpleNamespace(terminal_checkpoint_id=PREDECESSOR),
        successor_lineage_evidence=SimpleNamespace(terminal_checkpoint_id=TERMINAL),
    )
    return SimpleNamespace(
        anchor=SimpleNamespace(paper_account_id=ACCOUNT),
        lineage=SimpleNamespace(terminal_checkpoint_id=TERMINAL),
        receipts=(receipt,) if include_receipt else (),
    )


class _Scope(AbstractContextManager["_Scope"]):
    def __init__(
        self,
        events: list[str],
        label: str,
        *,
        state: PaperAccountMutexState = PaperAccountMutexState.OWNED,
        account_id: str = ACCOUNT,
    ) -> None:
        self.events = events
        self.label = label
        self.acquisition = PaperAccountMutexAcquisition(
            account_id,
            "disposable",
            "0" * 64,
            state,
        )

    def __enter__(self) -> _Scope:
        self.events.append(f"{self.label}-enter")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
        self.events.append(f"{self.label}-exit")


def _run(
    events: list[str],
    *,
    pre: PaperReceiptRecoveryQualificationResult | None = None,
    post: PaperReceiptRecoveryQualificationResult | None = None,
    mutex_state: PaperAccountMutexState = PaperAccountMutexState.OWNED,
    inspections: tuple[PaperOperationInspectionResult, ...] | None = None,
    recovered: object | None = None,
    post_evidence: object | None = None,
    historical: tuple[bytes, ...] = (CONFIGURATION,),
) -> execution.PersonalDesktopPaperReceiptRecoveryResult:
    pre = pre or _qualification(
        PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
    )
    post = post or _qualification(
        PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
    )
    retained_inspections = list(
        inspections
        or (
            _inspection(PaperOperationClassification.BLOCKED),
            _inspection(PaperOperationClassification.ALREADY_APPLIED),
        )
    )

    def pre_qualify(*args, **kwargs):  # type: ignore[no-untyped-def]
        events.append("pre-qualify")
        return pre

    def post_qualify(*args, **kwargs):  # type: ignore[no-untyped-def]
        events.append("post-qualify")
        return post

    def admit(value):  # type: ignore[no-untyped-def]
        assert value is pre
        events.append("admit")
        return _Scope(events, "mutex", state=mutex_state)

    def reconstruct(*args, **kwargs):  # type: ignore[no-untyped-def]
        assert args[1] is post
        events.append("reconstruct")
        return _binding()

    def inspect_operation(*args):  # type: ignore[no-untyped-def]
        events.append("inspect")
        return retained_inspections.pop(0)

    def open_output():
        events.append("output-open")
        return _Scope(events, "output")

    def recover(*args, **kwargs):  # type: ignore[no-untyped-def]
        events.append("recover")
        return recovered or _recovery_result()

    def read(*args, **kwargs):  # type: ignore[no-untyped-def]
        expected = (
            historical if CONFIGURATION in historical else (*historical, CONFIGURATION)
        )
        assert kwargs["historical_cycle_configuration_payloads"] == expected
        events.append("post-read")
        return object()

    def validate(value):  # type: ignore[no-untyped-def]
        events.append("post-validate")
        return post_evidence or _post_evidence()

    authority = (
        execution._open_disposable_paper_receipt_recovery_execution_authority_for_test()
    )
    return execution._recover_personal_desktop_paper_receipt_for_test(
        object(),
        object(),
        history_seed=object(),
        strategy_config=object(),
        caller_idempotency_key=UUID(int=1),
        open_reference=object(),
        policies=object(),
        planning_at=NOW,
        submitted_at=NOW,
        filled_at=NOW,
        pre_lock_qualifier=pre_qualify,
        post_lock_qualifier=post_qualify,
        admission_factory=admit,
        reconstructor=reconstruct,
        inspector=inspect_operation,
        output_capability_factory=open_output,
        recovery=recover,
        post_reader=read,
        post_read_validator=validate,
        execution_authority=authority,
        historical_cycle_configuration_payloads=historical,
    )


def test_pre_lock_blocked_stops_before_mutex_output_and_recovery() -> None:
    events: list[str] = []
    with pytest.raises(execution.PersonalDesktopPaperReceiptRecoveryBlockedError):
        _run(
            events,
            pre=_qualification(PaperReceiptRecoveryQualificationStatus.BLOCKED),
        )
    assert events == ["pre-qualify"]


def test_pre_lock_no_recovery_is_benign_zero_write() -> None:
    events: list[str] = []
    result = _run(
        events,
        pre=_qualification(
            PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED
        ),
    )
    assert result.qualification_status is (
        PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED
    )
    assert result.operation_id is None
    assert result.receipt_evidence_produced is False
    assert events == ["pre-qualify"]


def test_recovery_holds_mutex_through_post_read_final_inspection_and_close() -> None:
    events: list[str] = []
    result = _run(events)
    assert result.recovery_classification is (
        PaperOperationExecutionClassification.RECEIPT_RECOVERED
    )
    assert result.receipt_evidence_produced is True
    assert events == [
        "pre-qualify",
        "admit",
        "mutex-enter",
        "post-qualify",
        "reconstruct",
        "output-open",
        "output-enter",
        "inspect",
        "recover",
        "post-read",
        "post-validate",
        "inspect",
        "output-exit",
        "mutex-exit",
    ]
    assert events.count("recover") == 1


def test_abandoned_owner_stops_before_post_lock_work() -> None:
    events: list[str] = []
    with pytest.raises(execution.PersonalDesktopPaperReceiptRecoveryBlockedError):
        _run(events, mutex_state=PaperAccountMutexState.ABANDONED_OWNER)
    assert events == ["pre-qualify", "admit", "mutex-enter", "mutex-exit"]


@pytest.mark.parametrize(
    "status",
    [
        PaperReceiptRecoveryQualificationStatus.BLOCKED,
        PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED,
    ],
)
def test_post_lock_blocked_or_healthy_never_reconstructs_or_recovers(
    status: PaperReceiptRecoveryQualificationStatus,
) -> None:
    events: list[str] = []
    post = _qualification(status)
    if status is PaperReceiptRecoveryQualificationStatus.BLOCKED:
        with pytest.raises(execution.PersonalDesktopPaperReceiptRecoveryBlockedError):
            _run(events, post=post)
    else:
        result = _run(events, post=post)
        assert result.qualification_status is (
            PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED
        )
        assert result.operation_id is None
    assert events == [
        "pre-qualify",
        "admit",
        "mutex-enter",
        "post-qualify",
        "mutex-exit",
    ]


def test_changed_post_lock_target_blocks_before_reconstruction() -> None:
    events: list[str] = []
    post = _qualification(
        PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED,
        application=UUID(int=999),
    )
    with pytest.raises(execution.PersonalDesktopPaperReceiptRecoveryBlockedError):
        _run(events, post=post)
    assert "reconstruct" not in events
    assert "output-open" not in events


def test_pre_call_already_applied_is_benign_and_skips_recovery() -> None:
    events: list[str] = []
    already = _inspection(PaperOperationClassification.ALREADY_APPLIED)
    result = _run(events, inspections=(already, already))
    assert result.recovery_classification is (
        PaperOperationExecutionClassification.ALREADY_APPLIED
    )
    assert result.receipt_evidence_produced is False
    assert "recover" not in events


def test_recovery_call_already_applied_race_is_benign_zero_write() -> None:
    events: list[str] = []
    result = _run(
        events,
        recovered=_recovery_result(
            PaperOperationExecutionClassification.ALREADY_APPLIED
        ),
    )
    assert result.recovery_classification is (
        PaperOperationExecutionClassification.ALREADY_APPLIED
    )
    assert result.receipt_evidence_produced is False
    assert events.count("recover") == 1


@pytest.mark.parametrize(
    "classification",
    [PaperOperationClassification.PENDING, PaperOperationClassification.CONFLICTING],
)
def test_any_other_pre_call_inspection_blocks_without_recovery(
    classification: PaperOperationClassification,
) -> None:
    events: list[str] = []
    with pytest.raises(execution.PersonalDesktopPaperReceiptRecoveryBlockedError):
        _run(events, inspections=(_inspection(classification),))
    assert "recover" not in events
    assert events[-2:] == ["output-exit", "mutex-exit"]


@pytest.mark.parametrize("failure", ["operation-id", "classification"])
def test_invalid_recovery_result_blocks_without_retry(failure: str) -> None:
    events: list[str] = []
    if failure == "operation-id":
        recovered = _recovery_result(operation=UUID(int=777))
    else:
        recovered = SimpleNamespace(
            classification=PaperOperationExecutionClassification.BLOCKED,
            diagnostic_code="BLOCKED",
            operation_id=OPERATION,
            application_id=APPLICATION,
            terminal_checkpoint_id=PREDECESSOR,
            pre_execution_classification=PaperOperationClassification.BLOCKED,
            successor_checkpoint_id=None,
            receipt_path=None,
        )
    with pytest.raises(execution.PersonalDesktopPaperReceiptRecoveryBlockedError):
        _run(events, recovered=recovered)
    assert events.count("recover") == 1
    assert events[-2:] == ["output-exit", "mutex-exit"]


def test_post_recovery_ordinary_read_requires_exact_verified_receipt() -> None:
    events: list[str] = []
    with pytest.raises(execution.PersonalDesktopPaperReceiptRecoveryBlockedError):
        _run(events, post_evidence=_post_evidence(include_receipt=False))
    assert "post-read" in events
    assert "post-validate" in events
    assert events[-2:] == ["output-exit", "mutex-exit"]


def test_final_inspection_must_be_exact_already_applied() -> None:
    events: list[str] = []
    missing = _inspection(PaperOperationClassification.BLOCKED)
    with pytest.raises(execution.PersonalDesktopPaperReceiptRecoveryBlockedError):
        _run(events, inspections=(missing, missing))
    assert events.count("recover") == 1
    assert events[-2:] == ["output-exit", "mutex-exit"]


def test_exception_closes_capability_and_releases_mutex() -> None:
    events: list[str] = []

    class Boom:
        @property
        def classification(self):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _run(events, recovered=Boom())
    assert events.count("recover") == 1
    assert events[-2:] == ["output-exit", "mutex-exit"]


def test_reconstructed_configuration_is_appended_once_when_not_historical() -> None:
    events: list[str] = []
    _run(events, historical=(b'{"configuration":"old"}',))
    assert events.count("post-read") == 1


@pytest.mark.parametrize(
    "state",
    [
        execution._EffectGateState(False, False, False, False),
        execution._EffectGateState(True, True, False, False),
        execution._EffectGateState(True, False, True, False),
        execution._EffectGateState(True, False, False, True),
    ],
)
def test_all_four_effect_gate_states_must_be_exact(
    state: execution._EffectGateState,
) -> None:
    with pytest.raises(
        execution.PersonalDesktopPaperReceiptRecoveryEffectsDisabledError
    ):
        execution._require_effect_gate_state(state)
    execution._require_effect_gate_state(
        execution._EffectGateState(True, False, False, False)
    )


def test_disposable_authority_is_one_shot_and_rejects_production_recovery() -> None:
    authority = (
        execution._open_disposable_paper_receipt_recovery_execution_authority_for_test()
    )

    def fake(*args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    common = dict(
        authority=object(),
        selected_snapshot=object(),
        history_seed=object(),
        strategy_config=object(),
        caller_idempotency_key=UUID(int=1),
        open_reference=object(),
        policies=object(),
        planning_at=NOW,
        submitted_at=NOW,
        filled_at=NOW,
        pre_lock_qualifier=fake,
        post_lock_qualifier=fake,
        admission_factory=fake,
        reconstructor=fake,
        inspector=fake,
        output_capability_factory=fake,
        recovery=execution.recover_paper_operation_receipt_once,
        post_reader=fake,
        post_read_validator=fake,
        execution_authority=authority,
    )
    with pytest.raises(TypeError, match="production wiring"):
        execution._recover_personal_desktop_paper_receipt_for_test(**common)
    common["recovery"] = fake
    common["pre_lock_qualifier"] = lambda *args, **kwargs: _qualification(
        PaperReceiptRecoveryQualificationStatus.BLOCKED
    )
    with pytest.raises(execution.PersonalDesktopPaperReceiptRecoveryBlockedError):
        execution._recover_personal_desktop_paper_receipt_for_test(**common)
    with pytest.raises(TypeError, match="consumed"):
        execution._recover_personal_desktop_paper_receipt_for_test(**common)


def test_public_boundary_has_no_caller_selected_authority_or_effect_seams() -> None:
    signature = inspect.signature(execution.recover_personal_desktop_paper_receipt)
    assert not {
        "qualification",
        "reconstruction",
        "execution_inputs",
        "operation_id",
        "application_id",
        "request_id",
        "plan_id",
        "root",
        "path",
        "mutex_name",
        "trading_sid",
        "native_api",
        "output_capability",
        "inspector",
        "recovery_callable",
        "gate_override",
        "provider",
        "broker",
    } & set(signature.parameters)
    source = inspect.getsource(execution)
    imported = {
        alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "recover_paper_operation_receipt_once" in imported
    assert (
        not {
            "execute_paper_operation_once",
            "execute_checkpointed_verified_snapshot_paper_cycle",
            "provider",
            "broker",
            "scheduler",
        }
        & imported
    )
    assert execution.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED is False
    assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False
    assert (
        supervised_execution.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is False
    )


def test_production_gate_blocks_after_internal_reconstruction_before_output(
    reconstruction_case,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = reconstruction_case
    events: list[str] = []
    original_reconstructor = (
        execution._reconstruct_personal_desktop_paper_receipt_recovery_operation
    )

    def qualify(*args, **kwargs):  # type: ignore[no-untyped-def]
        events.append("qualify")
        return case.qualification

    def admit(value):  # type: ignore[no-untyped-def]
        assert value is case.qualification
        events.append("admit")
        return _Scope(events, "mutex", account_id=value.paper_account_id)

    def reconstruct(*args, **kwargs):  # type: ignore[no-untyped-def]
        events.append("reconstruct")
        kwargs["operation_root"] = case.operation_root
        return original_reconstructor(*args, **kwargs)

    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        pytest.fail("disabled production gate reached an output or recovery effect")

    monkeypatch.setattr(
        execution,
        "qualify_personal_desktop_paper_receipt_recovery",
        qualify,
    )
    monkeypatch.setattr(execution, "paper_receipt_recovery_admission", admit)
    monkeypatch.setattr(
        execution,
        "_reconstruct_personal_desktop_paper_receipt_recovery_operation",
        reconstruct,
    )
    monkeypatch.setattr(
        execution,
        "open_personal_desktop_paper_receipt_recovery_output_capability",
        forbidden,
    )
    monkeypatch.setattr(
        execution,
        "recover_paper_operation_receipt_once",
        forbidden,
    )

    with pytest.raises(
        execution.PersonalDesktopPaperReceiptRecoveryEffectsDisabledError
    ):
        execution.recover_personal_desktop_paper_receipt(
            case.authority,
            case.selected,
            **case.semantic,
        )
    assert events == [
        "qualify",
        "admit",
        "mutex-enter",
        "qualify",
        "reconstruct",
        "mutex-exit",
    ]
