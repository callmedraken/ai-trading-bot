"""Focused no-effect tests for Architecture-108 reconciliation."""

from __future__ import annotations

import ast
import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

import trading_bot.cli.pd2d2_post_mutation_reconciliation as harness
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
        outcome=PaperOperationOutcome.APPLIED,
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
            cash=harness.Decimal("24232.67"), positions=(object(),)
        ),
    )
    state: dict[str, object] = {}

    def lineage_verifier(genesis: object, *args: object) -> object:
        state["genesis"] = genesis
        calls.append(("lineage", args))
        return original_lineage

    def account_validator(account: object) -> object:
        calls.append(("validate_account", account))
        genesis = state["genesis"]
        return SimpleNamespace(
            anchor=SimpleNamespace(paper_account_id=harness._EXPECTED_PAPER_ACCOUNT_ID),
            genesis=genesis,
            lineage=installed_lineage,
            prior_checkpoint=SimpleNamespace(
                checkpoint_id=harness._EXPECTED_TERMINAL_ID
            ),
            successors=(SimpleNamespace(payload=b"successor"),),
            reports=(SimpleNamespace(payload=b"report"),),
            snapshots=(
                SimpleNamespace(
                    artifact_id=harness._EXPECTED_SELECTED_SNAPSHOT_ID,
                    payload=_SELECTED_BYTES,
                ),
            ),
            receipts=(receipt,),
        )

    genesis = harness.PaperAccountLineageArtifact(
        PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
        harness._EXPECTED_GENESIS_ID,
        _GENESIS_BYTES,
        sha256(_GENESIS_BYTES).hexdigest(),
        len(_GENESIS_BYTES),
    )
    state["genesis"] = genesis
    account_evidence = account_validator("seed")
    calls.clear()
    evidence_values = [account_evidence, account_evidence]

    def read_account(candidate: object, **kwargs: object) -> object:
        calls.append(("account_read", candidate, kwargs))
        return len([item for item in calls if item[0] == "account_read"]) - 1

    def validate_account(index: object) -> object:
        calls.append(("account_validate", index))
        return evidence_values[int(index)]

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
        bundle_preparer=lambda **kwargs: (calls.append(("bundle", kwargs)), bundle)[1],
        anchor_parser=lambda payload: anchor,
        genesis_verifier=lambda *args, **kwargs: genesis_verification,
        lineage_verifier=lineage_verifier,
        prior_deriver=lambda value: verified_prior,
        plan_builder=lambda *args: plan,
        plan_verifier=lambda *args, **kwargs: plan,
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
        genesis_verification=genesis_verification,
        inspection=inspection,
    )


def _run(case: SimpleNamespace) -> dict[str, object]:
    return harness._run_reconciliation_for_test(
        harness._open_disposable_reconciliation_authority_for_test(), case.deps
    )


def test_success_reconstructs_original_inputs_and_rereads_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(monkeypatch)
    result = _run(case)
    assert result["result"] == "RECONCILED"
    assert result["operation_id"] == str(harness._EXPECTED_OPERATION_ID)
    assert result["successor_checkpoint_id"] == str(harness._EXPECTED_TERMINAL_ID)
    reads = [item for item in case.calls if item[0] == "account_read"]
    assert len(reads) == 2
    assert all(
        item[2]["historical_cycle_configuration_payloads"] == (_PLAN_BYTES,)
        for item in reads
    )
    input_args = next(item[1] for item in case.calls if item[0] == "execution_inputs")
    assert input_args[3:6] == ((), (), ())
    assert input_args[7] == _GENESIS_BYTES
    assert input_args[0] is case.receipt.intent


@pytest.mark.parametrize(
    "module,name",
    (
        (
            harness.paper_security,
            "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED",
        ),
        (harness.paper_security, "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED"),
        (
            harness.execution_boundary,
            "PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED",
        ),
    ),
)
def test_any_true_gate_blocks_before_production_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    module: object,
    name: str,
) -> None:
    monkeypatch.setattr(module, name, True)
    monkeypatch.setattr(
        harness,
        "_production_dependencies",
        lambda: pytest.fail("production dependency constructed after unsafe gate"),
    )
    assert harness.main([]) == harness._EXIT_GATE


def test_parser_exposes_no_semantic_overrides() -> None:
    parser = harness.build_parser()
    assert parser.parse_args([]).__dict__ == {}
    with pytest.raises(harness._CliUsageError):
        parser.parse_args(["--root", "X"])


@pytest.mark.parametrize(
    "field", ("checkpoint_sha256", "checkpoint_byte_length", "status")
)
def test_exact_original_genesis_is_required(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    case = _case(monkeypatch)
    value = "0" * 64 if field == "checkpoint_sha256" else 999
    if field == "status":
        value = object()
    case.genesis_verification.__dict__[field] = value
    with pytest.raises(harness._ReconciliationError):
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
def test_exact_plan_replay_identity_hash_and_length_are_required(
    monkeypatch: pytest.MonkeyPatch, target: str, field: str, value: object
) -> None:
    case = _case(monkeypatch)
    selected = {
        "plan": case.plan,
        "plan_plan": case.plan.plan,
        "request": case.plan.checkpointed_request,
    }[target]
    selected.__dict__[field] = value
    with pytest.raises(harness._ReconciliationError):
        _run(case)


@pytest.mark.parametrize(
    "collection", ("successors", "reports", "snapshots", "receipts")
)
@pytest.mark.parametrize("count", (0, 2))
def test_zero_or_multiple_installed_artifacts_fail(
    monkeypatch: pytest.MonkeyPatch, collection: str, count: int
) -> None:
    case = _case(monkeypatch)
    evidence = case.evidence_values[0]
    item = getattr(evidence, collection)[0]
    setattr(evidence, collection, (item,) * count)
    with pytest.raises(harness._ReconciliationError):
        _run(case)


@pytest.mark.parametrize(
    "target,field,value",
    (
        ("successor", "checkpoint_id", harness._EXPECTED_GENESIS_ID),
        (
            "successor_prior",
            "checkpoint_id",
            harness._EXPECTED_TERMINAL_ID,
        ),
        ("successor", "sequence", 2),
        ("successor", "application_id", harness._EXPECTED_OPERATION_ID),
        ("report_evidence", "application_id", harness._EXPECTED_OPERATION_ID),
        ("report_evidence", "cycle_result_id", harness._EXPECTED_OPERATION_ID),
        ("lineage", "terminal_checkpoint_id", harness._EXPECTED_GENESIS_ID),
    ),
)
def test_wrong_transition_or_terminal_evidence_fails(
    monkeypatch: pytest.MonkeyPatch, target: str, field: str, value: object
) -> None:
    case = _case(monkeypatch)
    selected = {
        "successor": case.successor,
        "successor_prior": case.successor.prior_checkpoint,
        "report_evidence": case.report.evidence,
        "lineage": case.installed_lineage,
    }[target]
    setattr(selected, field, value)
    with pytest.raises(harness._ReconciliationError):
        _run(case)


@pytest.mark.parametrize(
    "target,field,value",
    (
        ("receipt", "receipt_id", harness._EXPECTED_APPLICATION_ID),
        ("receipt", "application_id", harness._EXPECTED_OPERATION_ID),
        ("receipt", "status", PaperOperationStatus.FAILED),
        ("intent", "caller_idempotency_key", harness._EXPECTED_OPERATION_ID),
        ("intent", "operation_id", harness._EXPECTED_APPLICATION_ID),
        ("intent", "prior_lineage_evidence", SimpleNamespace(wrong=True)),
        (
            "intent",
            "cycle_configuration_artifact",
            SimpleNamespace(sha256="0" * 64, byte_length=len(_PLAN_BYTES)),
        ),
    ),
)
def test_wrong_receipt_identity_status_or_intent_fails(
    monkeypatch: pytest.MonkeyPatch, target: str, field: str, value: object
) -> None:
    case = _case(monkeypatch)
    selected = case.receipt if target == "receipt" else case.receipt.intent
    setattr(selected, field, value)
    with pytest.raises(harness._ReconciliationError):
        _run(case)


@pytest.mark.parametrize(
    "classification,diagnostic",
    (
        (PaperOperationClassification.PENDING, PaperOperationInspectionCode.PENDING),
        (
            PaperOperationClassification.BLOCKED,
            PaperOperationInspectionCode.INVALID_OPERATION_STATE,
        ),
        (
            PaperOperationClassification.CONFLICTING,
            PaperOperationInspectionCode.LINEAGE_CONFLICT,
        ),
        (
            PaperOperationClassification.ALREADY_APPLIED,
            PaperOperationInspectionCode.PENDING,
        ),
    ),
)
def test_any_inspection_other_than_exact_already_applied_fails(
    monkeypatch: pytest.MonkeyPatch,
    classification: PaperOperationClassification,
    diagnostic: PaperOperationInspectionCode,
) -> None:
    case = _case(monkeypatch)
    case.inspection.classification = classification
    case.inspection.diagnostics = (diagnostic,)
    with pytest.raises(harness._ReconciliationError):
        _run(case)


def test_second_account_reread_drift_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    case = _case(monkeypatch)
    case.evidence_values[1] = SimpleNamespace(drift=True)
    with pytest.raises(harness._ReconciliationError):
        _run(case)


def test_main_emits_one_frozen_reconciled_record(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    case = _case(monkeypatch)
    monkeypatch.setattr(harness, "_production_dependencies", lambda: case.deps)
    assert harness.main([]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    lines = captured.out.splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["result"] == "RECONCILED"
    assert record["plan_id"] == str(harness._EXPECTED_PLAN_ID)
    assert record["selected_snapshot_id"] == str(harness._EXPECTED_SELECTED_SNAPSHOT_ID)


def test_all_three_source_gates_are_false() -> None:
    assert (
        harness.paper_security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED
        is False
    )
    assert (
        harness.paper_security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED
        is False
    )
    assert (
        harness.execution_boundary.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is False
    )


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
            harness._run_reconciliation_for_test(
                harness._open_disposable_reconciliation_authority_for_test(), deps
            )


def test_launcher_uses_src_bootstrap_and_guarded_main() -> None:
    path = _ROOT / "scripts" / "reconcile_first_personal_desktop_paper_operation.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert 'parents[1] / "src"' in source
    assert "sys.path.insert" in source
    assert any(isinstance(node, ast.If) for node in tree.body)
    assert 'if __name__ == "__main__"' in source


def test_harness_has_no_effectful_boundary_calls() -> None:
    path = (
        _ROOT / "src" / "trading_bot" / "cli" / "pd2d2_post_mutation_reconciliation.py"
    )
    source = path.read_text(encoding="utf-8")
    forbidden = (
        "execute_paper_operation_once",
        "recover_paper_operation",
        "execute_supervised_personal_desktop_paper_operation(",
        "provider_call(",
        "broker_order",
        "live_order",
        "scheduler.run",
    )
    assert all(value not in source for value in forbidden)


def test_all_source_effect_gates_remain_false() -> None:
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
    assert "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False" in security
    assert "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED = False" in security
    assert (
        "PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False"
        in supervised
    )
