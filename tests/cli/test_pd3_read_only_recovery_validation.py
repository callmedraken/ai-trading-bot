"""Focused no-effect tests for the PD3 read-only real-host harness."""

from __future__ import annotations

import ast
import gc
import json
import weakref
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

import trading_bot.cli.pd3_read_only_recovery_validation as harness
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
)
from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.paper_account_checkpoint import (
    PaperAccountCheckpointVerificationStatus,
)
from trading_bot.runtime.paper_account_lineage_verification import (
    PaperAccountLineageArtifactEvidence,
    PaperAccountLineageArtifactKind,
    PaperAccountLineageVerificationStatus,
)
from trading_bot.runtime.paper_operation import (
    PaperOperationArtifactEvidence,
    PaperOperationOutcome,
    PaperOperationStatus,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_qualification import (
    PaperReceiptRecoveryQualificationDiagnostic,
    PaperReceiptRecoveryQualificationStatus,
)

_ROOT = Path(__file__).resolve().parents[2]
_SELECTED_BYTES = b"selected-call-six"
_GENESIS_BYTES = b"original-genesis"
_ANCHOR_BYTES = b"anchor"
_MANIFEST_BYTES = b"manifest"
_PLAN_BYTES = b"frozen-plan"


class _Reader:
    def __init__(
        self, selected: object, calls: list[object], authority: object
    ) -> None:
        self._selected = selected
        calls.append(("reader", authority))
        self._calls = calls

    def read_selected_snapshot(self, selection_id: str) -> object:
        self._calls.append(("selected", selection_id))
        return self._selected


def _install_small_frozen_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        harness, "_EXPECTED_SELECTED_SHA256", sha256(_SELECTED_BYTES).hexdigest()
    )
    monkeypatch.setattr(harness, "_EXPECTED_SELECTED_BYTE_LENGTH", len(_SELECTED_BYTES))
    monkeypatch.setattr(
        harness, "_EXPECTED_GENESIS_SHA256", sha256(_GENESIS_BYTES).hexdigest()
    )
    monkeypatch.setattr(harness, "_EXPECTED_GENESIS_BYTE_LENGTH", len(_GENESIS_BYTES))
    monkeypatch.setattr(
        harness, "_EXPECTED_ANCHOR_SHA256", sha256(_ANCHOR_BYTES).hexdigest()
    )
    monkeypatch.setattr(harness, "_EXPECTED_ANCHOR_BYTE_LENGTH", len(_ANCHOR_BYTES))
    monkeypatch.setattr(
        harness, "_EXPECTED_MANIFEST_SHA256", sha256(_MANIFEST_BYTES).hexdigest()
    )
    monkeypatch.setattr(harness, "_EXPECTED_MANIFEST_BYTE_LENGTH", len(_MANIFEST_BYTES))
    monkeypatch.setattr(
        harness, "_EXPECTED_PLAN_SHA256", sha256(_PLAN_BYTES).hexdigest()
    )
    monkeypatch.setattr(harness, "_EXPECTED_PLAN_BYTE_LENGTH", len(_PLAN_BYTES))


def _case(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    _install_small_frozen_bytes(monkeypatch)
    calls: list[object] = []
    authority = SimpleNamespace(
        machine_authority_id=harness._EXPECTED_MACHINE_AUTHORITY_ID,
        authority_epoch_id=harness._EXPECTED_AUTHORITY_EPOCH_ID,
        approved_account_sid=harness._EXPECTED_TRADING_SID,
    )
    snapshot = SimpleNamespace(
        snapshot_id=harness._EXPECTED_SELECTED_SNAPSHOT_ID,
        target_session=TradingSession(harness._EXPECTED_TARGET_SESSION.session_date),
        request=SimpleNamespace(symbols=(Symbol("SPY"),)),
        bars=(SimpleNamespace(bar=SimpleNamespace(symbol=Symbol("SPY"))),),
    )
    selected = SimpleNamespace(
        snapshot_bytes=_SELECTED_BYTES,
        audit=SimpleNamespace(
            selection_id=harness._EXPECTED_SELECTION_ID,
            session_id=harness._EXPECTED_SELECTION_ID,
            terminal_id=harness._EXPECTED_SELECTION_ID,
            snapshot_id=harness._EXPECTED_SELECTED_SNAPSHOT_ID,
            artifact_sha256=sha256(_SELECTED_BYTES).hexdigest(),
            artifact_byte_length=len(_SELECTED_BYTES),
        ),
        verification=SimpleNamespace(snapshot=snapshot),
        provider_call_performed=False,
        database_mutation_performed=False,
    )
    bundle = SimpleNamespace(
        genesis_bytes=_GENESIS_BYTES,
        anchor_bytes=_ANCHOR_BYTES,
        manifest_bytes=_MANIFEST_BYTES,
    )
    anchor = SimpleNamespace(
        paper_account_id=harness._EXPECTED_PAPER_ACCOUNT_ID,
        machine_authority_id=harness._EXPECTED_MACHINE_AUTHORITY_ID,
        approved_trading_sid=harness._EXPECTED_TRADING_SID,
        genesis_checkpoint_id=str(harness._EXPECTED_GENESIS_ID),
        genesis_sha256=sha256(_GENESIS_BYTES).hexdigest(),
        genesis_byte_length=len(_GENESIS_BYTES),
    )
    checkpoint = SimpleNamespace(
        checkpoint_id=harness._EXPECTED_GENESIS_ID,
        account_state=SimpleNamespace(
            as_of=harness._EXPECTED_GENESIS_AS_OF,
            cash=harness.Decimal("25000"),
            positions=(),
            realized_profit_loss=harness.Decimal("0"),
        ),
        metadata=(),
    )
    genesis_verification = SimpleNamespace(
        status=PaperAccountCheckpointVerificationStatus.PASS,
        diagnostics=(),
        checkpoint=checkpoint,
        checkpoint_sha256=sha256(_GENESIS_BYTES).hexdigest(),
        checkpoint_byte_length=len(_GENESIS_BYTES),
    )
    original_evidence = SimpleNamespace(
        edge_count=0,
        checkpoint_ids=(harness._EXPECTED_GENESIS_ID,),
    )
    original_lineage = SimpleNamespace(
        status=PaperAccountLineageVerificationStatus.PASS,
        diagnostics=(),
        evidence=original_evidence,
    )
    verified_prior = SimpleNamespace(checkpoint_id=harness._EXPECTED_GENESIS_ID)
    prior_plan = SimpleNamespace(checkpoint_id=harness._EXPECTED_GENESIS_ID)
    selected_assertion = SimpleNamespace(
        selection_id=harness._EXPECTED_SELECTION_ID,
        snapshot_id=harness._EXPECTED_SELECTED_SNAPSHOT_ID,
    )
    checkpointed_request = SimpleNamespace(request_id=harness._EXPECTED_REQUEST_ID)
    plan = SimpleNamespace(
        plan=SimpleNamespace(
            plan_id=harness._EXPECTED_PLAN_ID,
            caller_idempotency_key=str(harness._EXPECTED_CALLER_IDEMPOTENCY_KEY),
            selected_c3_assertion=selected_assertion,
            prior_checkpoint=prior_plan,
        ),
        artifact_bytes=_PLAN_BYTES,
        artifact_sha256=sha256(_PLAN_BYTES).hexdigest(),
        artifact_byte_length=len(_PLAN_BYTES),
        checkpointed_request=checkpointed_request,
    )
    terminal_evidence = PaperAccountLineageArtifactEvidence(
        PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
        harness._EXPECTED_GENESIS_ID,
        sha256(_GENESIS_BYTES).hexdigest(),
        len(_GENESIS_BYTES),
    )
    snapshot_evidence = PaperAccountLineageArtifactEvidence(
        PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
        harness._EXPECTED_SELECTED_SNAPSHOT_ID,
        sha256(_SELECTED_BYTES).hexdigest(),
        len(_SELECTED_BYTES),
    )
    config_evidence = PaperOperationArtifactEvidence(
        sha256(_PLAN_BYTES).hexdigest(), len(_PLAN_BYTES)
    )
    intent = SimpleNamespace(
        operation_id=harness._EXPECTED_OPERATION_ID,
        caller_idempotency_key=harness._EXPECTED_CALLER_IDEMPOTENCY_KEY,
        request=checkpointed_request,
        prior_lineage_evidence=original_evidence,
        terminal_checkpoint_artifact=terminal_evidence,
        completed_snapshot_artifact=snapshot_evidence,
        cycle_configuration_artifact=config_evidence,
    )
    receipt = SimpleNamespace(
        receipt_id=harness._EXPECTED_OPERATION_ID,
        intent=intent,
        application_id=harness._EXPECTED_APPLICATION_ID,
        status=PaperOperationStatus.COMPLETED,
        outcome=PaperOperationOutcome.NO_ACTION,
        prior_lineage_evidence=original_evidence,
        cycle_result_id=harness._EXPECTED_CYCLE_RESULT_ID,
        successor_checkpoint_artifact=SimpleNamespace(
            artifact_id=harness._EXPECTED_TERMINAL_ID
        ),
    )
    successor = SimpleNamespace(
        checkpoint_id=harness._EXPECTED_TERMINAL_ID,
        prior_checkpoint=SimpleNamespace(checkpoint_id=harness._EXPECTED_GENESIS_ID),
        application_id=harness._EXPECTED_APPLICATION_ID,
        sequence=1,
    )
    report = SimpleNamespace(
        evidence=SimpleNamespace(
            application_id=harness._EXPECTED_APPLICATION_ID,
            cycle_result_id=harness._EXPECTED_CYCLE_RESULT_ID,
            request=SimpleNamespace(
                snapshot_reference=SimpleNamespace(
                    snapshot_id=harness._EXPECTED_SELECTED_SNAPSHOT_ID,
                    artifact_sha256=sha256(_SELECTED_BYTES).hexdigest(),
                    artifact_byte_length=len(_SELECTED_BYTES),
                )
            ),
        )
    )
    installed_lineage = SimpleNamespace(
        edge_count=1,
        checkpoint_ids=(harness._EXPECTED_GENESIS_ID, harness._EXPECTED_TERMINAL_ID),
        application_ids=(harness._EXPECTED_APPLICATION_ID,),
        cycle_result_ids=(harness._EXPECTED_CYCLE_RESULT_ID,),
        snapshot_ids=(harness._EXPECTED_SELECTED_SNAPSHOT_ID,),
        terminal_checkpoint_id=harness._EXPECTED_TERMINAL_ID,
        terminal_compact_state=SimpleNamespace(
            cash=harness.Decimal("25000"), positions=()
        ),
    )
    recovery_result = SimpleNamespace(
        qualification_status=PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED,
        paper_account_id=harness._EXPECTED_PAPER_ACCOUNT_ID,
        operation_id=None,
        application_id=None,
        predecessor_checkpoint_id=None,
        installed_terminal_checkpoint_id=harness._EXPECTED_TERMINAL_ID,
        pre_recovery_classification=None,
        recovery_classification=None,
        recovery_diagnostic=(
            PaperReceiptRecoveryQualificationDiagnostic.VERIFIED_COMPLETE_ACCOUNT.value
        ),
        receipt_evidence_produced=False,
        post_recovery_classification=None,
    )
    state: dict[str, object] = {}

    def lineage_verifier(genesis: object, *args: object) -> object:
        state["genesis"] = genesis
        calls.append(("lineage", args))
        return original_lineage

    genesis = harness.PaperAccountLineageArtifact(
        PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
        harness._EXPECTED_GENESIS_ID,
        _GENESIS_BYTES,
        sha256(_GENESIS_BYTES).hexdigest(),
        len(_GENESIS_BYTES),
    )
    state["genesis"] = genesis
    snapshot_artifact = SimpleNamespace(
        artifact_id=harness._EXPECTED_SELECTED_SNAPSHOT_ID,
        sha256=sha256(_SELECTED_BYTES).hexdigest(),
        byte_length=len(_SELECTED_BYTES),
        payload=_SELECTED_BYTES,
    )
    account_evidence = SimpleNamespace(
        anchor=SimpleNamespace(paper_account_id=harness._EXPECTED_PAPER_ACCOUNT_ID),
        genesis=genesis,
        lineage=installed_lineage,
        prior_checkpoint=SimpleNamespace(checkpoint_id=harness._EXPECTED_TERMINAL_ID),
        successors=(SimpleNamespace(payload=b"successor"),),
        reports=(SimpleNamespace(payload=b"report"),),
        snapshots=(snapshot_artifact,),
        receipts=(receipt,),
    )
    evidence_values = [account_evidence, account_evidence]

    def read_account(candidate: object, **kwargs: object) -> object:
        calls.append(("account_read", candidate, kwargs))
        return len([item for item in calls if item[0] == "account_read"]) - 1

    def validate_account(index: object) -> object:
        calls.append(("account_validate", index))
        return evidence_values[int(index)]

    def validate_recovery(*args: object, **kwargs: object) -> object:
        calls.append(("recovery_boundary", args, kwargs))
        return recovery_result

    def execution_inputs_builder(*args: object) -> object:
        calls.append(("execution_inputs", args))
        return SimpleNamespace(intent=args[0])

    inspection = SimpleNamespace(
        classification=PaperOperationClassification.ALREADY_APPLIED,
        diagnostics=(PaperOperationInspectionCode.ALREADY_APPLIED,),
        operation_id=harness._EXPECTED_OPERATION_ID,
        application_id=harness._EXPECTED_APPLICATION_ID,
        terminal_checkpoint_id=harness._EXPECTED_GENESIS_ID,
    )
    deps = harness._Dependencies(
        publication_preflight=lambda: calls.append(("publication",)),
        history_seed_loader=lambda: SimpleNamespace(),
        authority_loader=lambda: authority,
        selected_reader_factory=lambda candidate: _Reader(selected, calls, candidate),
        provenance_validator=lambda *args: calls.append(("provenance", args)),
        bundle_preparer=lambda **kwargs: (calls.append(("bundle", kwargs)), bundle)[1],
        anchor_parser=lambda payload: anchor,
        genesis_verifier=lambda *args, **kwargs: genesis_verification,
        lineage_verifier=lineage_verifier,
        prior_deriver=lambda value: verified_prior,
        plan_builder=lambda *args: plan,
        plan_verifier=lambda *args, **kwargs: plan,
        recovery_boundary=validate_recovery,
        account_reader=read_account,
        account_validator=validate_account,
        successor_parser=lambda payload: successor,
        report_parser=lambda payload: report,
        intent_builder=lambda *args: intent,
        application_id_deriver=lambda *args: harness._EXPECTED_APPLICATION_ID,
        execution_inputs_builder=execution_inputs_builder,
        inspector=lambda *args: inspection,
    )
    monkeypatch.setattr(
        harness, "ManualPaperSelectedC3Assertion", lambda *args: selected_assertion
    )
    monkeypatch.setattr(
        harness, "ManualPaperStrategyPlanRequest", lambda *args: SimpleNamespace()
    )
    return SimpleNamespace(
        deps=deps,
        calls=calls,
        evidence_values=evidence_values,
        installed_lineage=installed_lineage,
        receipt=receipt,
        successor=successor,
        report=report,
        plan=plan,
        selected=selected,
        authority=authority,
        recovery_result=recovery_result,
        inspection=inspection,
    )


def _run(case: SimpleNamespace) -> dict[str, object]:
    return harness._run_validation_for_test(
        harness._open_disposable_validation_authority_for_test(), case.deps
    )


def test_exact_healthy_result_proves_both_read_only_classifications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(monkeypatch)
    result = _run(case)
    assert result == {
        "account_cash": "25000",
        "all_effect_gates_false": True,
        "application_id": str(harness._EXPECTED_APPLICATION_ID),
        "cycle_result_id": str(harness._EXPECTED_CYCLE_RESULT_ID),
        "genesis_checkpoint_id": str(harness._EXPECTED_GENESIS_ID),
        "inspection_classification": "ALREADY_APPLIED",
        "inspection_diagnostic": "ALREADY_APPLIED",
        "operation_id": str(harness._EXPECTED_OPERATION_ID),
        "paper_account_id": harness._EXPECTED_PAPER_ACCOUNT_ID,
        "plan_byte_length": len(_PLAN_BYTES),
        "plan_id": str(harness._EXPECTED_PLAN_ID),
        "plan_sha256": sha256(_PLAN_BYTES).hexdigest(),
        "position_count": 0,
        "qualification_diagnostic": "VERIFIED_COMPLETE_ACCOUNT",
        "qualification_status": "NO_RECOVERY_REQUIRED",
        "receipt_evidence_produced": False,
        "receipt_outcome": "NO_ACTION",
        "receipt_status": "COMPLETED",
        "recovery_invocation_performed": False,
        "result": "VALIDATED",
        "schema": harness._SCHEMA,
        "selected_snapshot_id": str(harness._EXPECTED_SELECTED_SNAPSHOT_ID),
        "selection_id": str(harness._EXPECTED_SELECTION_ID),
        "terminal_checkpoint_id": str(harness._EXPECTED_TERMINAL_ID),
    }
    boundary = next(item for item in case.calls if item[0] == "recovery_boundary")
    assert boundary[1][:2] == (case.authority, case.selected)
    assert boundary[2]["historical_cycle_configuration_payloads"] == (_PLAN_BYTES,)
    assert [item[1] for item in case.calls if item[0] == "provenance"] == [
        (case.authority, case.selected),
        (case.authority, case.selected),
    ]
    reads = [item for item in case.calls if item[0] == "account_read"]
    assert len(reads) == 2
    assert all(
        item[2]["historical_cycle_configuration_payloads"] == (_PLAN_BYTES,)
        for item in reads
    )


def test_selected_reader_remains_alive_through_all_selected_result_uses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(monkeypatch)
    original_factory = case.deps.selected_reader_factory
    original_validator = case.deps.account_validator
    reader_reference: weakref.ReferenceType[_Reader] | None = None

    def selected_reader_factory(authority: object) -> _Reader:
        nonlocal reader_reference
        reader = original_factory(authority)
        reader_reference = weakref.ref(reader)
        return reader

    def account_validator(account: object) -> object:
        gc.collect()
        assert reader_reference is not None
        assert reader_reference() is not None
        return original_validator(account)

    case.deps = replace(
        case.deps,
        selected_reader_factory=selected_reader_factory,
        account_validator=account_validator,
    )
    assert _run(case)["result"] == "VALIDATED"


@pytest.mark.parametrize(
    "field",
    (
        "publication",
        "provisioning_recovery",
        "supervised_execution",
        "receipt_recovery",
    ),
)
def test_every_bad_gate_state_is_rejected_without_changing_a_real_gate(
    field: str,
) -> None:
    values = {
        "publication": False,
        "provisioning_recovery": False,
        "supervised_execution": False,
        "receipt_recovery": False,
    }
    values[field] = True
    assert not harness._gate_state_is_safe(harness._EffectGateState(**values))


def test_bad_gate_state_blocks_before_production_dependency_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        harness,
        "_effect_gate_state",
        lambda: harness._EffectGateState(True, False, False, False),
    )
    monkeypatch.setattr(
        harness,
        "_production_dependencies",
        lambda: pytest.fail("production dependencies constructed after unsafe gate"),
    )
    assert harness.main([]) == harness._EXIT_GATE


def test_parser_exposes_no_semantic_overrides_and_sanitizes_bad_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = harness.build_parser()
    assert parser.parse_args([]).__dict__ == {}
    with pytest.raises(harness._CliUsageError):
        parser.parse_args(["--root", r"C:\secret\Paper-v2"])
    assert harness.main(["--root", r"C:\secret\Paper-v2"]) == harness._EXIT_USAGE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "C:\\secret" not in captured.err
    assert json.loads(captured.err) == {
        "reason": "INVALID_ARGUMENTS",
        "schema": harness._SCHEMA,
    }


@pytest.mark.parametrize(
    "status",
    (
        PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED,
        PaperReceiptRecoveryQualificationStatus.BLOCKED,
    ),
)
def test_recovery_required_or_blocked_public_result_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    status: PaperReceiptRecoveryQualificationStatus,
) -> None:
    case = _case(monkeypatch)
    case.recovery_result.qualification_status = status
    with pytest.raises(harness._ValidationError):
        _run(case)
    assert not any(item[0] == "account_read" for item in case.calls)


@pytest.mark.parametrize(
    "target,field,value",
    (
        ("authority", "machine_authority_id", "wrong"),
        ("authority", "authority_epoch_id", "wrong"),
        ("authority", "approved_account_sid", "wrong"),
        ("selected_audit", "selection_id", harness._EXPECTED_GENESIS_ID),
        ("selected_audit", "snapshot_id", harness._EXPECTED_GENESIS_ID),
        ("selected", "provider_call_performed", True),
        ("selected", "database_mutation_performed", True),
    ),
)
def test_wrong_c1_or_p2_evidence_blocks(
    monkeypatch: pytest.MonkeyPatch, target: str, field: str, value: object
) -> None:
    case = _case(monkeypatch)
    candidate = {
        "authority": case.authority,
        "selected": case.selected,
        "selected_audit": case.selected.audit,
    }[target]
    setattr(candidate, field, value)
    with pytest.raises(harness._ValidationError):
        _run(case)


@pytest.mark.parametrize(
    "target,field,value",
    (
        ("plan", "artifact_sha256", "0" * 64),
        ("plan", "artifact_byte_length", 999),
        ("plan_plan", "plan_id", harness.UUID("00000000-0000-4000-8000-000000000001")),
        ("request", "request_id", harness.UUID("00000000-0000-4000-8000-000000000002")),
    ),
)
def test_wrong_plan_evidence_blocks(
    monkeypatch: pytest.MonkeyPatch, target: str, field: str, value: object
) -> None:
    case = _case(monkeypatch)
    candidate = {
        "plan": case.plan,
        "plan_plan": case.plan.plan,
        "request": case.plan.checkpointed_request,
    }[target]
    setattr(candidate, field, value)
    with pytest.raises(harness._ValidationError):
        _run(case)


@pytest.mark.parametrize(
    "target,field,value",
    (
        ("lineage", "terminal_checkpoint_id", harness._EXPECTED_GENESIS_ID),
        ("lineage", "checkpoint_ids", (harness._EXPECTED_GENESIS_ID,)),
        ("lineage", "application_ids", (harness._EXPECTED_OPERATION_ID,)),
        ("lineage", "cycle_result_ids", (harness._EXPECTED_OPERATION_ID,)),
        ("lineage_state", "cash", harness.Decimal("24999")),
        ("lineage_state", "positions", (object(),)),
        ("receipt", "receipt_id", harness._EXPECTED_APPLICATION_ID),
        ("receipt", "application_id", harness._EXPECTED_OPERATION_ID),
        ("receipt", "status", PaperOperationStatus.FAILED),
        ("receipt", "outcome", PaperOperationOutcome.APPLIED),
        ("inspection", "operation_id", harness._EXPECTED_APPLICATION_ID),
        ("inspection", "classification", PaperOperationClassification.PENDING),
    ),
)
def test_wrong_account_terminal_receipt_or_a67_evidence_blocks(
    monkeypatch: pytest.MonkeyPatch, target: str, field: str, value: object
) -> None:
    case = _case(monkeypatch)
    candidate = {
        "lineage": case.installed_lineage,
        "lineage_state": case.installed_lineage.terminal_compact_state,
        "receipt": case.receipt,
        "inspection": case.inspection,
    }[target]
    setattr(candidate, field, value)
    with pytest.raises(harness._ValidationError):
        _run(case)


def test_second_account_read_drift_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    case = _case(monkeypatch)
    case.evidence_values[1] = SimpleNamespace(drift=True)
    with pytest.raises(harness._ValidationError):
        _run(case)


def test_main_output_is_one_deterministic_sanitized_record(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    case = _case(monkeypatch)
    monkeypatch.setattr(harness, "_production_dependencies", lambda: case.deps)
    assert harness.main([]) == 0
    first = capsys.readouterr()
    assert first.err == ""
    assert len(first.out.splitlines()) == 1
    assert json.loads(first.out)["result"] == "VALIDATED"
    case = _case(monkeypatch)
    monkeypatch.setattr(harness, "_production_dependencies", lambda: case.deps)
    assert harness.main([]) == 0
    second = capsys.readouterr()
    assert second.err == ""
    assert second.out == first.out
    forbidden = ("F:\\", "C:\\", "Traceback", "Exception", "handle", "secret")
    assert all(value not in first.out for value in forbidden)


def test_disposable_seam_rejects_every_genuine_production_callable() -> None:
    production = harness._production_dependencies()
    for field in production.__dataclass_fields__:
        fake_values = {
            name: (lambda *args, **kwargs: None)
            for name in production.__dataclass_fields__
        }
        fake_values[field] = getattr(production, field)
        deps = harness._Dependencies(**fake_values)
        with pytest.raises(TypeError):
            harness._run_validation_for_test(
                harness._open_disposable_validation_authority_for_test(), deps
            )


def test_import_is_guarded_and_harness_imports_no_effect_primitive() -> None:
    path = (
        _ROOT / "src" / "trading_bot" / "cli" / "pd3_read_only_recovery_validation.py"
    )
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert 'if __name__ == "__main__"' in source
    forbidden_imports = {
        "trading_bot.cli.paper_operation_execution",
        "trading_bot.runtime.personal_desktop_paper_runtime_output",
    }
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert imported_modules.isdisjoint(forbidden_imports)
    forbidden_call_names = {
        "recover_paper_operation_receipt_once",
        "execute_paper_operation_once",
        "execute_checkpointed_verified_snapshot_paper_cycle",
        "open_personal_desktop_paper_receipt_recovery_output_capability",
        "provider_call",
        "broker_order",
        "run",
    }
    called_names = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert called_names.isdisjoint(forbidden_call_names)


def test_all_four_source_effect_gates_remain_false() -> None:
    security = (
        _ROOT
        / "src"
        / "trading_bot"
        / "runtime"
        / "personal_desktop_paper_account_security.py"
    ).read_text(encoding="utf-8")
    supervised = (
        _ROOT
        / "src"
        / "trading_bot"
        / "runtime"
        / "personal_desktop_supervised_paper_operation_execution.py"
    ).read_text(encoding="utf-8")
    recovery = (
        _ROOT
        / "src"
        / "trading_bot"
        / "runtime"
        / "personal_desktop_paper_receipt_recovery_execution.py"
    ).read_text(encoding="utf-8")
    assert "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False" in security
    assert "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED = False" in security
    assert (
        "PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False"
        in supervised
    )
    assert (
        "PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED = False" in recovery
    )
