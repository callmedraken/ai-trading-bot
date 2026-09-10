"""PD3-C exact reconstruction of one qualified missing-receipt operation."""

from __future__ import annotations

import ast
import inspect
import weakref
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from tests.market_data.daily_snapshot_test_support import CAPTURED_AT, SPY
from tests.runtime.test_manual_paper_strategy_plan import (
    _DEFAULT_CONFIG,
    _NEXT_SESSION,
    _snapshot,
    _verified_seed,
)
from tests.runtime.test_personal_desktop_paper_account_read_authority import (
    Observer,
    artifact,
    evidence,
)
from tests.runtime.test_personal_desktop_paper_account_security import (
    SID,
)
from tests.runtime.test_verified_snapshot_preparation import _policies, calendar
from tests.runtime.test_windows_authority_capability import _production_validation

from trading_bot.market_data import serialize_daily_snapshot
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime import manual_paper_selected_c3_snapshot as p2
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import (
    personal_desktop_paper_receipt_recovery_qualification as qualification,
)
from trading_bot.runtime import (
    personal_desktop_paper_receipt_recovery_reconstruction as reconstruction,
)
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as execution_boundary,
)
from trading_bot.runtime.checkpointed_paper_cycle_report import (
    checkpointed_paper_cycle_report_from_result,
    checkpointed_paper_cycle_report_reference,
    serialize_checkpointed_paper_cycle_report,
)
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    execute_checkpointed_verified_snapshot_paper_cycle,
    verified_prior_from_full_lineage,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotAuditEvidence,
    SelectedC3SnapshotPermit,
    SelectedC3SnapshotReadResult,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperSelectedC3Assertion,
    ManualPaperStrategyPlanRequest,
    build_manual_paper_strategy_plan,
)
from trading_bot.runtime.paper_account_checkpoint import (
    PaperAccountGenesisRequest,
    create_genesis_paper_account_checkpoint,
    serialize_paper_account_checkpoint,
)
from trading_bot.runtime.paper_account_lineage_verification import (
    PaperAccountLineageArtifactKind,
    PaperAccountLineageVerificationStatus,
    verify_paper_account_lineage,
)
from trading_bot.runtime.paper_account_successor_checkpoint import (
    create_successor_paper_account_checkpoint,
    serialize_successor_paper_account_checkpoint,
)
from trading_bot.runtime.paper_operation import (
    PaperOperationArtifactEvidence,
    PaperOperationDiagnosticCode,
    PaperOperationOutcome,
    PaperOperationReceipt,
    PaperOperationStatus,
    create_paper_operation_intent,
    serialize_paper_operation_receipt,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountAnchor,
    derive_personal_desktop_paper_account_id,
    serialize_personal_desktop_paper_account_anchor,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    PersonalDesktopPaperAccountReadEvidence,
    PersonalDesktopPaperAccountRecoveryReadEvidence,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_qualification import (
    PaperReceiptRecoveryQualificationDiagnostic,
    PaperReceiptRecoveryQualificationResult,
    PaperReceiptRecoveryQualificationStatus,
)
from trading_bot.runtime.verified_snapshot_preparation import (
    CallerAssertedNextSessionOpenReference,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

SELECTION_ID = UUID("10000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("20000000-0000-0000-0000-000000000002")
ATTEMPT_ID = UUID("25000000-0000-0000-0000-000000000002")
TERMINAL_ID = UUID("30000000-0000-0000-0000-000000000003")
CALLER_KEY = UUID("cff0bcea-e6d9-548a-8371-a45fb95ce3b4")


@dataclass
class ReconstructionCase:
    authority: object
    qualification: PaperReceiptRecoveryQualificationResult
    selected: SelectedC3SnapshotReadResult
    forged_selected: SelectedC3SnapshotReadResult
    operation_root: Path
    semantic: dict[str, object]
    plan: object
    prior_lineage: object
    full_lineage: object
    result: object
    successor: object
    report: object
    receipt: PaperOperationReceipt
    p2_core: object
    p2_reader: object


def _selected_result() -> SelectedC3SnapshotReadResult:
    verification = _snapshot()
    assert verification.snapshot is not None
    payload = serialize_daily_snapshot(verification.snapshot)
    audit = SelectedC3SnapshotAuditEvidence(
        SELECTION_ID,
        SESSION_ID,
        ATTEMPT_ID,
        TERMINAL_ID,
        verification.snapshot.snapshot_id,
        verification.sha256,
        verification.byte_length,
        "1" * 64,
        "SUCCEEDED",
        "CONFIRMED",
        r"F:\AITradingBot\capture\selected.json",
    )
    return SelectedC3SnapshotReadResult(
        audit,
        object.__new__(SelectedC3SnapshotPermit),
        payload,
        verification,
    )


def _production_selected(
    authority: object,
    provisional: SelectedC3SnapshotReadResult,
) -> tuple[SelectedC3SnapshotReadResult, object, object]:
    core = object.__new__(p2._SelectedC3SnapshotReadCore)
    core._authority = authority
    core._production = True
    reader = object.__new__(p2.WindowsSelectedC3SnapshotReadAuthority)
    reader._authority = authority
    reader._core = core
    registration = p2._ReadCoreRegistration(
        weakref.ref(reader), authority, p2._PRODUCTION_CORE_PROVENANCE
    )
    permit = object.__new__(SelectedC3SnapshotPermit)
    binding = p2._PermitBinding(
        weakref.ref(provisional.audit),
        weakref.ref(core),
        weakref.ref(reader),
        registration,
        (
            authority.machine_authority_id,
            authority.approved_account_sid,
            authority.authority_epoch_id,
        ),
    )
    with p2._PERMIT_REGISTRY_LOCK:
        p2._CORE_REGISTRY[core] = registration
        p2._PERMIT_REGISTRY[permit] = binding
    return replace(provisional, permit=permit), core, reader


def _disposable_selected(
    authority: object,
) -> tuple[SelectedC3SnapshotReadResult, object, object]:
    provisional = _selected_result()
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
            authority.machine_authority_id,
            authority.approved_account_sid,
            authority.authority_epoch_id,
        ),
    )
    with p2._PERMIT_REGISTRY_LOCK:
        p2._CORE_REGISTRY[core] = registration
        p2._PERMIT_REGISTRY[permit] = binding
    return replace(provisional, permit=permit), core, reader


def _materialize_transition(
    operation_root: Path,
    application_id: UUID,
    report_payload: bytes,
    cycle_result_id: UUID,
    successor_payload: bytes,
    successor_id: UUID,
) -> None:
    operation_root.mkdir()
    (operation_root / "paper-operations").mkdir()
    transition = operation_root / f"paper-account-transition-{application_id}"
    transition.mkdir()
    report_path = transition / (
        f"checkpointed-paper-cycle-report-{cycle_result_id}.json"
    )
    report_path.write_bytes(report_payload)
    (transition / f"paper-account-checkpoint-{successor_id}.json").write_bytes(
        successor_payload
    )


@pytest.fixture
def reconstruction_case(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> ReconstructionCase:
    authority = _production_validation(monkeypatch)
    checkpoint = create_genesis_paper_account_checkpoint(
        PaperAccountGenesisRequest(
            datetime(2025, 1, 1, tzinfo=UTC),
            Decimal("100"),
            (),
            Decimal("0"),
        )
    )
    genesis_payload = serialize_paper_account_checkpoint(checkpoint)
    genesis = artifact(
        PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
        checkpoint.checkpoint_id,
        genesis_payload,
    )
    identity = dict(
        machine_authority_id=authority.machine_authority_id,
        approved_trading_sid=authority.approved_account_sid,
        genesis_checkpoint_id=str(genesis.artifact_id),
        genesis_sha256=genesis.sha256,
        genesis_byte_length=genesis.byte_length,
    )
    anchor = PersonalDesktopPaperAccountAnchor(
        derive_personal_desktop_paper_account_id(**identity), **identity
    )
    prior_lineage = verify_paper_account_lineage(
        genesis, genesis.artifact_id, (), (), (), calendar()
    )
    assert prior_lineage.status is PaperAccountLineageVerificationStatus.PASS
    assert prior_lineage.evidence is not None
    prior = verified_prior_from_full_lineage(prior_lineage)

    forged_selected = _selected_result()
    selected, p2_core, p2_reader = _production_selected(authority, forged_selected)
    config = _DEFAULT_CONFIG
    history_seed = _verified_seed(config, ("10", "10", "9"))
    open_reference = CallerAssertedNextSessionOpenReference(
        SPY, _NEXT_SESSION, Decimal("12")
    )
    policies = _policies()
    planning_at = CAPTURED_AT + timedelta(minutes=1)
    submitted_at = CAPTURED_AT + timedelta(minutes=2)
    filled_at = datetime(2025, 1, 7, 20, tzinfo=UTC)
    metadata = (MetadataEntry("source", "pd3-c-test"),)
    assertion = ManualPaperSelectedC3Assertion(
        selected.audit.selection_id,
        selected.audit.session_id,
        selected.audit.terminal_id,
        selected.audit.snapshot_id,
        selected.audit.artifact_sha256,
        selected.audit.artifact_byte_length,
    )
    plan = build_manual_paper_strategy_plan(
        ManualPaperStrategyPlanRequest(
            selected.verification,
            anchor.paper_account_id,
            assertion,
            prior,
            history_seed,
            config,
            str(CALLER_KEY),
            open_reference,
            policies,
            planning_at,
            submitted_at,
            filled_at,
            metadata,
        ),
        calendar(),
    )
    result = execute_checkpointed_verified_snapshot_paper_cycle(
        plan.checkpointed_request,
        prior,
        selected.verification,
        calendar(),
    )
    report = checkpointed_paper_cycle_report_from_result(result)
    report_payload = serialize_checkpointed_paper_cycle_report(report)
    successor = create_successor_paper_account_checkpoint(
        report.evidence.prior_checkpoint,
        report.evidence.prior_lineage_id,
        result,
        checkpointed_paper_cycle_report_reference(report_payload),
    )
    successor_payload = serialize_successor_paper_account_checkpoint(successor)
    successor_artifact = artifact(
        PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
        successor.checkpoint_id,
        successor_payload,
    )
    report_artifact = artifact(
        PaperAccountLineageArtifactKind.CYCLE_REPORT,
        report.report_id,
        report_payload,
    )
    snapshot_artifact = artifact(
        PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
        selected.audit.snapshot_id,
        selected.snapshot_bytes,
    )
    full_lineage = verify_paper_account_lineage(
        genesis,
        successor.checkpoint_id,
        (successor_artifact,),
        (report_artifact,),
        (snapshot_artifact,),
        calendar(),
    )
    assert full_lineage.status is PaperAccountLineageVerificationStatus.PASS
    assert full_lineage.evidence is not None
    intent = create_paper_operation_intent(
        CALLER_KEY,
        prior_lineage.evidence,
        evidence(genesis),
        evidence(snapshot_artifact),
        PaperOperationArtifactEvidence(plan.artifact_sha256, plan.artifact_byte_length),
        plan.checkpointed_request,
    )
    receipt = PaperOperationReceipt(
        1,
        intent.operation_id,
        intent,
        PaperOperationStatus.COMPLETED,
        PaperOperationOutcome.NO_ACTION
        if result.status.value == "NO_ACTION"
        else PaperOperationOutcome.APPLIED,
        PaperOperationDiagnosticCode.NONE,
        prior_lineage.evidence,
        full_lineage.evidence,
        evidence(report_artifact),
        evidence(successor_artifact),
        result.application_id,
        result.result_id,
    )

    account_evidence = PersonalDesktopPaperAccountReadEvidence(
        anchor,
        serialize_personal_desktop_paper_account_anchor(anchor),
        verified_prior_from_full_lineage(full_lineage),
        full_lineage.evidence,
        genesis,
        (successor_artifact,),
        (report_artifact,),
        (snapshot_artifact,),
        (),
    )
    recovery_read = PersonalDesktopPaperAccountRecoveryReadEvidence(
        account_evidence,
        result.application_id,
        genesis.artifact_id,
    )
    monkeypatch.setattr(
        qualification,
        "_perform_recovery_read",
        lambda *args, **kwargs: recovery_read,
    )
    qualified = qualification.qualify_personal_desktop_paper_receipt_recovery(authority)
    assert qualified.status is (
        PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
    )

    operation_root = tmp_path / "operation-root"
    _materialize_transition(
        operation_root,
        result.application_id,
        report_payload,
        result.result_id,
        successor_payload,
        successor.checkpoint_id,
    )
    monkeypatch.setattr(
        reconstruction,
        "PERSONAL_DESKTOP_PAPER_V2_RUNTIME",
        str(operation_root),
    )
    semantic: dict[str, object] = {
        "history_seed": history_seed,
        "strategy_config": config,
        "caller_idempotency_key": CALLER_KEY,
        "open_reference": open_reference,
        "policies": policies,
        "planning_at": planning_at,
        "submitted_at": submitted_at,
        "filled_at": filled_at,
        "metadata": metadata,
    }
    case = ReconstructionCase(
        authority,
        qualified,
        selected,
        forged_selected,
        operation_root,
        semantic,
        plan,
        prior_lineage,
        full_lineage,
        result,
        successor,
        report,
        receipt,
        p2_core,
        p2_reader,
    )
    try:
        yield case
    finally:
        with p2._PERMIT_REGISTRY_LOCK:
            p2._PERMIT_REGISTRY.pop(selected.permit, None)
            p2._CORE_REGISTRY.pop(p2_core, None)
        with qualification._REGISTRY_LOCK:
            qualification._REGISTRY.pop(qualified, None)


def _call(case: ReconstructionCase, **changes: object):
    semantic = {**case.semantic, **changes}
    return reconstruction.reconstruct_personal_desktop_paper_receipt_recovery_operation(
        case.authority,
        case.qualification,
        case.selected,
        **semantic,
    )


def test_registered_production_qualification_reconstructs_exact_operation(
    reconstruction_case: ReconstructionCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = reconstruction_case
    original_require = (
        reconstruction.require_validated_paper_receipt_recovery_qualification
    )
    consumed: list[object] = []

    def require(value):  # type: ignore[no-untyped-def]
        consumed.append(value)
        return original_require(value)

    monkeypatch.setattr(
        reconstruction,
        "require_validated_paper_receipt_recovery_qualification",
        require,
    )
    before = {
        path.relative_to(case.operation_root): path.read_bytes()
        for path in case.operation_root.rglob("*")
        if path.is_file()
    }
    result = _call(case)
    after = {
        path.relative_to(case.operation_root): path.read_bytes()
        for path in case.operation_root.rglob("*")
        if path.is_file()
    }

    assert consumed == [case.qualification, case.qualification]
    assert result.operation_id == case.receipt.intent.operation_id
    assert result.application_id == case.qualification.missing_application_id
    assert result.predecessor_checkpoint_id == (
        case.prior_lineage.evidence.terminal_checkpoint_id
    )
    assert result.installed_terminal_checkpoint_id == case.successor.checkpoint_id
    assert result.selected_snapshot_id == case.selected.audit.snapshot_id
    assert result.plan_id == case.plan.plan.plan_id
    assert result.plan_sha256 == case.plan.artifact_sha256
    assert result.plan_byte_length == case.plan.artifact_byte_length
    assert result.inspection_classification.value == "BLOCKED"
    assert result.inspection_diagnostic.value == "FINALIZED_TRANSITION_WITHOUT_RECEIPT"
    assert set(result.__slots__) == {
        "paper_account_id",
        "operation_id",
        "application_id",
        "predecessor_checkpoint_id",
        "installed_terminal_checkpoint_id",
        "selected_snapshot_id",
        "plan_id",
        "plan_sha256",
        "plan_byte_length",
        "inspection_classification",
        "inspection_diagnostic",
    }
    assert before == after


def test_predecessor_prefix_is_independently_reverified_without_terminal_edge(
    reconstruction_case: ReconstructionCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = reconstruction_case
    original = reconstruction.verify_paper_account_lineage
    calls: list[tuple[object, object, object, object]] = []

    def verify(genesis, terminal, successors, reports, snapshots, identified_calendar):  # type: ignore[no-untyped-def]
        calls.append((terminal, successors, reports, snapshots))
        return original(
            genesis, terminal, successors, reports, snapshots, identified_calendar
        )

    monkeypatch.setattr(reconstruction, "verify_paper_account_lineage", verify)
    _call(case)
    assert calls == [
        (
            case.qualification.predecessor_checkpoint_id,
            (),
            (),
            (),
        )
    ]


@pytest.mark.parametrize(
    "change",
    [
        "caller-key",
        "strategy-config",
        "history-seed",
        "open-reference",
        "policy",
        "planning-at",
        "submitted-at",
        "filled-at",
        "metadata",
    ],
)
def test_wrong_original_semantic_fact_blocks(
    reconstruction_case: ReconstructionCase,
    change: str,
) -> None:
    case = reconstruction_case
    replacements: dict[str, object]
    if change == "caller-key":
        replacements = {"caller_idempotency_key": UUID(int=999)}
    elif change == "strategy-config":
        replacements = {
            "strategy_config": MovingAverageCrossoverConfig(2, 4, Decimal("2"))
        }
    elif change == "history-seed":
        replacements = {
            "history_seed": _verified_seed(_DEFAULT_CONFIG, ("9", "9", "9"))
        }
    elif change == "open-reference":
        replacements = {
            "open_reference": replace(
                case.semantic["open_reference"],
                caller_asserted_open_reference_price=Decimal("13"),
            )
        }
    elif change == "policy":
        replacements = {
            "policies": replace(case.semantic["policies"], trading_enabled=False)
        }
    elif change == "metadata":
        replacements = {"metadata": (MetadataEntry("source", "wrong"),)}
    else:
        replacements = {
            change.replace("-", "_"): case.semantic[change.replace("-", "_")]
            + timedelta(seconds=1)
        }
    with pytest.raises(reconstruction.PaperReceiptRecoveryReconstructionError):
        _call(case, **replacements)


def test_wrong_and_disposable_p2_provenance_block(
    reconstruction_case: ReconstructionCase,
) -> None:
    case = reconstruction_case
    with pytest.raises(reconstruction.PaperReceiptRecoveryReconstructionError):
        reconstruction.reconstruct_personal_desktop_paper_receipt_recovery_operation(
            case.authority,
            case.qualification,
            case.forged_selected,
            **case.semantic,
        )
    disposable, core, reader = _disposable_selected(case.authority)
    assert reader is not None
    try:
        with pytest.raises(reconstruction.PaperReceiptRecoveryReconstructionError):
            reconstruction.reconstruct_personal_desktop_paper_receipt_recovery_operation(
                case.authority,
                case.qualification,
                disposable,
                **case.semantic,
            )
    finally:
        with p2._PERMIT_REGISTRY_LOCK:
            p2._PERMIT_REGISTRY.pop(disposable.permit, None)
            p2._CORE_REGISTRY.pop(core, None)


@pytest.mark.parametrize("kind", ["report", "successor"])
def test_altered_registered_terminal_artifact_blocks(
    reconstruction_case: ReconstructionCase,
    kind: str,
) -> None:
    case = reconstruction_case
    with qualification._REGISTRY_LOCK:
        recovery_read = qualification._REGISTRY[case.qualification]
        account = recovery_read.account
        if kind == "report":
            account = replace(
                account,
                reports=(
                    replace(
                        account.reports[0],
                        payload=account.reports[0].payload + b" ",
                    ),
                ),
            )
        else:
            account = replace(
                account,
                successors=(
                    replace(
                        account.successors[0],
                        payload=account.successors[0].payload + b" ",
                    ),
                ),
            )
        qualification._REGISTRY[case.qualification] = replace(
            recovery_read, account=account
        )
    with pytest.raises(reconstruction.PaperReceiptRecoveryReconstructionError):
        _call(case)


def test_qualification_public_and_registered_provenance_mismatch_blocks(
    reconstruction_case: ReconstructionCase,
) -> None:
    case = reconstruction_case
    object.__setattr__(case.qualification, "missing_application_id", UUID(int=444))
    with pytest.raises(reconstruction.PaperReceiptRecoveryReconstructionError):
        _call(case)


def test_qualification_registry_binding_drift_blocks(
    reconstruction_case: ReconstructionCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = reconstruction_case
    original = reconstruction.require_validated_paper_receipt_recovery_qualification
    registered = original(case.qualification)
    drifted = replace(registered)
    calls = 0

    def require(value):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return registered if calls == 1 else drifted

    monkeypatch.setattr(
        reconstruction,
        "require_validated_paper_receipt_recovery_qualification",
        require,
    )
    with pytest.raises(reconstruction.PaperReceiptRecoveryReconstructionError):
        _call(case)
    assert calls == 2


def test_unregistered_caller_disposable_and_blocked_qualifications_are_rejected(
    reconstruction_case: ReconstructionCase,
) -> None:
    case = reconstruction_case
    caller_constructed = PaperReceiptRecoveryQualificationResult(
        PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED,
        PaperReceiptRecoveryQualificationDiagnostic.VERIFIED_TERMINAL_RECEIPT_MISSING,
        case.qualification.paper_account_id,
        case.qualification.terminal_checkpoint_id,
        case.qualification.missing_application_id,
        case.qualification.predecessor_checkpoint_id,
    )
    disposable = (
        qualification._qualify_personal_desktop_paper_receipt_recovery_for_test(
            case.authority.machine_authority_id,
            SID,
            api=object(),  # type: ignore[arg-type]
            observer=Observer(),
            calendar=calendar(),
        )
    )
    blocked = PaperReceiptRecoveryQualificationResult(
        PaperReceiptRecoveryQualificationStatus.BLOCKED,
        PaperReceiptRecoveryQualificationDiagnostic.VERIFICATION_BLOCKED,
        None,
        None,
        None,
        None,
    )
    for candidate in (caller_constructed, disposable, blocked):
        with pytest.raises(reconstruction.PaperReceiptRecoveryReconstructionError):
            reconstruction.reconstruct_personal_desktop_paper_receipt_recovery_operation(
                case.authority,
                candidate,
                case.selected,
                **case.semantic,
            )


def test_healthy_no_recovery_qualification_cannot_reconstruct(
    reconstruction_case: ReconstructionCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = reconstruction_case
    with qualification._REGISTRY_LOCK:
        recovery_read = qualification._REGISTRY[case.qualification]
    healthy_read = replace(
        recovery_read,
        missing_application_id=None,
        missing_predecessor_checkpoint_id=None,
    )
    monkeypatch.setattr(
        qualification,
        "_perform_recovery_read",
        lambda *args, **kwargs: healthy_read,
    )
    healthy = qualification.qualify_personal_desktop_paper_receipt_recovery(
        case.authority
    )
    assert healthy.status is (
        PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED
    )
    with pytest.raises(reconstruction.PaperReceiptRecoveryReconstructionError):
        reconstruction.reconstruct_personal_desktop_paper_receipt_recovery_operation(
            case.authority,
            healthy,
            case.selected,
            **case.semantic,
        )


def test_a67_non_missing_receipt_classification_blocks(
    reconstruction_case: ReconstructionCase,
) -> None:
    case = reconstruction_case
    operation = (
        case.operation_root
        / "paper-operations"
        / f"paper-operation-{case.receipt.receipt_id}"
    )
    operation.mkdir()
    (operation / f"paper-operation-receipt-{case.receipt.receipt_id}.json").write_bytes(
        serialize_paper_operation_receipt(case.receipt)
    )
    with pytest.raises(reconstruction.PaperReceiptRecoveryReconstructionError):
        _call(case)


def test_public_surface_has_no_effect_or_caller_authority_inputs() -> None:
    signature = inspect.signature(
        reconstruction.reconstruct_personal_desktop_paper_receipt_recovery_operation
    )
    assert not {
        "operation_root",
        "sid",
        "mutex_name",
        "native_api",
        "output_capability",
        "recovery_callable",
        "executor",
        "inspector",
        "execution_inputs",
        "prior",
        "operation_id",
        "application_id",
        "request_id",
        "plan_id",
        "gate_override",
    } & set(signature.parameters)
    source = inspect.getsource(reconstruction)
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert (
        not {
            "recover_paper_operation_receipt_once",
            "execute_paper_operation_once",
            "open_personal_desktop_paper_runtime_output",
            "execute_checkpointed_verified_snapshot_paper_cycle",
        }
        & imported
    )
    for forbidden in (
        "recover_paper_operation_receipt_once",
        "execute_paper_operation_once",
        "open_personal_desktop_paper_runtime_output",
    ):
        assert not hasattr(reconstruction, forbidden)
    assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False
    assert (
        execution_boundary.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is False
    )
