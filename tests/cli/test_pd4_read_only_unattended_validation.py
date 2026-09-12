"""Focused no-effect tests for the PD4-F1 read-only validation harness."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from dataclasses import fields, replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

import trading_bot.cli.pd4_read_only_unattended_validation as harness
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
)
from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import (
    personal_desktop_paper_receipt_recovery_execution as receipt_recovery,
)
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as supervised_execution,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_operation_execution as unattended_execution,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_storage_provisioning as storage_provisioning,
)
from trading_bot.runtime.paper_account_checkpoint import (
    PaperAccountCheckpointVerificationStatus,
)
from trading_bot.runtime.paper_account_lineage_verification import (
    PaperAccountLineageVerificationStatus,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexState,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageClassification,
)

_ROOT = Path(__file__).resolve().parents[2]
_STARTUP = harness.startup_qualification
PersonalDesktopUnattendedPaperStartupDiagnostic = (
    _STARTUP.PersonalDesktopUnattendedPaperStartupDiagnostic
)
PersonalDesktopUnattendedPaperStartupQualificationResult = (
    _STARTUP.PersonalDesktopUnattendedPaperStartupQualificationResult
)
PersonalDesktopUnattendedPaperStartupStatus = (
    _STARTUP.PersonalDesktopUnattendedPaperStartupStatus
)
_SELECTED_BYTES = b"selected-call-six"
_GENESIS_BYTES = b"original-genesis"
_ANCHOR_BYTES = b"anchor"
_MANIFEST_BYTES = b"manifest"
_PLAN_BYTES = b"frozen-plan"


class _Reader:
    def __init__(self, selected: object, calls: list[object]) -> None:
        self._selected = selected
        self._calls = calls

    def read_selected_snapshot(self, selection_id: str) -> object:
        self._calls.append(("selected", selection_id))
        return self._selected


def _result(
    status: PersonalDesktopUnattendedPaperStartupStatus,
) -> PersonalDesktopUnattendedPaperStartupQualificationResult:
    diagnostic = {
        PersonalDesktopUnattendedPaperStartupStatus.HEALTHY_NO_PENDING_INVOCATION: (
            PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_ABSENT_PENDING
        ),
        PersonalDesktopUnattendedPaperStartupStatus.READY_SAME_INVOCATION: (
            PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_IDENTICAL_PENDING
        ),
        PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED: (
            PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_ALREADY_APPLIED
        ),
        PersonalDesktopUnattendedPaperStartupStatus.RECEIPT_RECOVERY_REQUIRED: (
            PersonalDesktopUnattendedPaperStartupDiagnostic.VERIFIED_TERMINAL_RECEIPT_MISSING
        ),
        PersonalDesktopUnattendedPaperStartupStatus.BLOCKED: (
            PersonalDesktopUnattendedPaperStartupDiagnostic.QUALIFICATION_BLOCKED
        ),
    }[status]
    if status is PersonalDesktopUnattendedPaperStartupStatus.BLOCKED:
        return PersonalDesktopUnattendedPaperStartupQualificationResult(
            status,
            diagnostic,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
    if status is PersonalDesktopUnattendedPaperStartupStatus.RECEIPT_RECOVERY_REQUIRED:
        return PersonalDesktopUnattendedPaperStartupQualificationResult(
            status,
            diagnostic,
            harness._EXPECTED_PAPER_ACCOUNT_ID,
            None,
            None,
            None,
            None,
            harness._EXPECTED_GENESIS_ID,
            None,
            None,
            None,
            UUID("00000000-0000-4000-8000-000000000001"),
            UUID("00000000-0000-4000-8000-000000000002"),
            PaperAccountMutexState.OWNED,
        )
    return PersonalDesktopUnattendedPaperStartupQualificationResult(
        status,
        diagnostic,
        harness._EXPECTED_PAPER_ACCOUNT_ID,
        harness._EXPECTED_SELECTED_SNAPSHOT_ID,
        UUID("00000000-0000-4000-8000-000000000003"),
        harness._PROFILE.operation_id,
        harness._PROFILE.application_id,
        harness._EXPECTED_GENESIS_ID,
        PersonalDesktopUnattendedInvocationStorageClassification.ABSENT,
        PaperOperationClassification.ALREADY_APPLIED,
        PaperOperationInspectionCode.ALREADY_APPLIED,
        None,
        None,
        PaperAccountMutexState.OWNED,
    )


def _case(
    monkeypatch: pytest.MonkeyPatch,
    *,
    status: PersonalDesktopUnattendedPaperStartupStatus = (
        PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED
    ),
) -> SimpleNamespace:
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
    profile = replace(
        harness._PROFILE,
        plan_sha256=sha256(_PLAN_BYTES).hexdigest(),
        plan_byte_length=len(_PLAN_BYTES),
    )
    monkeypatch.setattr(harness, "_PROFILE", profile)

    calls: list[object] = []
    authority = SimpleNamespace(
        machine_authority_id=harness._EXPECTED_MACHINE_AUTHORITY_ID,
        authority_epoch_id=harness._EXPECTED_AUTHORITY_EPOCH_ID,
        approved_account_sid=harness._EXPECTED_TRADING_SID,
    )
    selected = SimpleNamespace(
        audit=SimpleNamespace(
            selection_id=harness._EXPECTED_SELECTION_ID,
            session_id=harness._EXPECTED_SELECTION_ID,
            terminal_id=harness._EXPECTED_SELECTION_ID,
            snapshot_id=harness._EXPECTED_SELECTED_SNAPSHOT_ID,
            artifact_sha256=sha256(_SELECTED_BYTES).hexdigest(),
            artifact_byte_length=len(_SELECTED_BYTES),
        ),
        snapshot_bytes=_SELECTED_BYTES,
        verification=SimpleNamespace(
            snapshot=SimpleNamespace(
                snapshot_id=harness._EXPECTED_SELECTED_SNAPSHOT_ID,
                target_session=TradingSession(
                    harness._EXPECTED_TARGET_SESSION.session_date
                ),
                request=SimpleNamespace(symbols=(Symbol("SPY"),)),
                bars=(SimpleNamespace(bar=SimpleNamespace(symbol=Symbol("SPY"))),),
            )
        ),
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
    lineage = SimpleNamespace(
        status=PaperAccountLineageVerificationStatus.PASS,
        diagnostics=(),
        evidence=SimpleNamespace(
            edge_count=0, checkpoint_ids=(harness._EXPECTED_GENESIS_ID,)
        ),
    )
    prior = SimpleNamespace(checkpoint_id=harness._EXPECTED_GENESIS_ID)
    assertion = SimpleNamespace(
        selection_id=harness._EXPECTED_SELECTION_ID,
        snapshot_id=harness._EXPECTED_SELECTED_SNAPSHOT_ID,
    )
    plan = SimpleNamespace(
        plan=SimpleNamespace(
            plan_id=profile.plan_id,
            caller_idempotency_key=str(profile.caller_idempotency_key),
            selected_c3_assertion=assertion,
            prior_checkpoint=prior,
        ),
        checkpointed_request=SimpleNamespace(request_id=profile.request_id),
        artifact_bytes=_PLAN_BYTES,
        artifact_sha256=profile.plan_sha256,
        artifact_byte_length=profile.plan_byte_length,
    )

    def qualifier(*args: object, **kwargs: object) -> object:
        calls.append(("qualifier", args, kwargs))
        return _result(status)

    closed = harness._EffectGateState(False, False, False, False, False, False)
    deps = harness._Dependencies(
        publication_preflight=lambda: calls.append(("publication",)),
        history_seed_loader=lambda: SimpleNamespace(),
        authority_loader=lambda: authority,
        selected_reader_factory=lambda candidate: (
            calls.append(("reader", candidate)),
            _Reader(selected, calls),
        )[1],
        provenance_validator=lambda *args: calls.append(("provenance", args)),
        bundle_preparer=lambda **kwargs: (
            calls.append(("bundle", kwargs)),
            bundle,
        )[1],
        anchor_parser=lambda payload: anchor,
        genesis_verifier=lambda *args, **kwargs: genesis_verification,
        lineage_verifier=lambda *args: lineage,
        prior_deriver=lambda value: prior,
        plan_builder=lambda *args: plan,
        plan_verifier=lambda *args, **kwargs: plan,
        qualifier=qualifier,
        gate_state=lambda: closed,
    )
    monkeypatch.setattr(
        harness, "ManualPaperSelectedC3Assertion", lambda *args: assertion
    )
    monkeypatch.setattr(
        harness, "ManualPaperStrategyPlanRequest", lambda *args: SimpleNamespace()
    )
    return SimpleNamespace(
        deps=deps,
        calls=calls,
        authority=authority,
        selected=selected,
        plan=plan,
    )


def _run(case: SimpleNamespace) -> dict[str, object]:
    return harness._run_validation_for_test(
        harness._open_disposable_validation_authority_for_test(), case.deps
    )


def test_parser_has_no_semantic_arguments_and_rejection_is_sanitized(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert harness.build_parser().parse_args([]).__dict__ == {}
    hostile = r"--paper-account=C:\secret\credential-material"
    with pytest.raises(harness._CliUsageError):
        harness.build_parser().parse_args([hostile])
    assert harness.main([hostile]) == harness._EXIT_USAGE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "secret" not in captured.err
    assert json.loads(captured.err) == {
        "reason": "INVALID_ARGUMENTS",
        "schema": harness._SCHEMA,
    }


def test_launcher_is_cwd_and_ambient_package_independent(tmp_path: Path) -> None:
    alternate_root = tmp_path / "alternate-package"
    alternate_cli = alternate_root / "trading_bot" / "cli"
    alternate_cli.mkdir(parents=True)
    (alternate_root / "trading_bot" / "__init__.py").write_text("")
    (alternate_cli / "__init__.py").write_text("")
    (alternate_cli / "pd4_read_only_unattended_validation.py").write_text(
        "def main(argv=None):\n    print('alternate package selected')\n    return 73\n"
    )
    away = tmp_path / "away"
    away.mkdir()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(alternate_root)
    script = _ROOT / "scripts" / "validate_pd4_read_only_unattended.py"
    expected = "Validate the frozen PD4-C read-only unattended boundary."
    for command in (
        [sys.executable, "-I", str(script), "--help"],
        [sys.executable, str(script), "--help"],
    ):
        completed = subprocess.run(
            command,
            cwd=away,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0
        assert expected in completed.stdout
        assert "alternate package selected" not in completed.stdout
        assert completed.stderr == ""


def test_validation_reads_call_six_and_invokes_pd4c_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(monkeypatch)
    record = _run(case)
    assert record["result"] == "VALIDATED"
    assert record["qualification_status"] == "ALREADY_APPLIED"
    assert record["selected_snapshot_id"] == str(harness._EXPECTED_SELECTED_SNAPSHOT_ID)
    assert record["provider_call_performed"] is False
    assert record["database_mutation_performed"] is False
    assert record["invocation_published"] is False
    assert record["execution_performed"] is False
    assert record["recovery_performed"] is False
    assert record["scheduler_modified"] is False
    assert record["unattended_operation_authorized"] is False
    assert [item for item in case.calls if item[0] == "selected"] == [
        ("selected", str(harness._EXPECTED_SELECTION_ID))
    ]
    qualifiers = [item for item in case.calls if item[0] == "qualifier"]
    assert len(qualifiers) == 1
    assert qualifiers[0][1][:2] == (case.authority, case.selected)
    assert qualifiers[0][2]["historical_cycle_configuration_payloads"] == (_PLAN_BYTES,)
    assert len([item for item in case.calls if item[0] == "provenance"]) == 2


@pytest.mark.parametrize(
    "field",
    (
        "publication",
        "provisioning_recovery",
        "supervised_execution",
        "receipt_recovery",
        "unattended_execution",
        "unattended_storage_provisioning",
    ),
)
def test_every_single_open_gate_fails_closed(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    case = _case(monkeypatch)
    values = {item.name: False for item in fields(harness._EffectGateState)}
    values[field] = True
    case.deps = replace(
        case.deps, gate_state=lambda: harness._EffectGateState(**values)
    )
    with pytest.raises(harness._ValidationError):
        _run(case)
    assert not any(item[0] == "publication" for item in case.calls)


def test_all_six_real_effect_gates_remain_false() -> None:
    assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False
    assert (
        supervised_execution.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is False
    )
    assert (
        receipt_recovery.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED
        is False
    )
    assert (
        unattended_execution.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED
        is False
    )
    assert (
        storage_provisioning.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED
        is False
    )


@pytest.mark.parametrize(
    "field",
    ("provider_call_performed", "database_mutation_performed"),
)
def test_selected_p2_effect_claim_is_rejected_before_qualification(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    case = _case(monkeypatch)
    setattr(case.selected, field, True)
    with pytest.raises(harness._ValidationError):
        _run(case)
    assert not any(item[0] == "qualifier" for item in case.calls)


@pytest.mark.parametrize(
    "target,field,value",
    (
        ("plan", "artifact_sha256", "0" * 64),
        ("plan", "artifact_byte_length", 999),
        ("plan_plan", "plan_id", UUID("00000000-0000-4000-8000-000000000004")),
    ),
)
def test_historical_plan_must_match_exact_frozen_identity_digest_and_length(
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    field: str,
    value: object,
) -> None:
    case = _case(monkeypatch)
    candidate = {"plan": case.plan, "plan_plan": case.plan.plan}[target]
    setattr(candidate, field, value)
    with pytest.raises(harness._ValidationError):
        _run(case)
    assert not any(item[0] == "qualifier" for item in case.calls)


def test_historical_plan_profile_is_the_accepted_first_operation() -> None:
    assert harness._PROFILE.plan_id == UUID("78292abe-6d6c-5ddf-8ffb-46eb8a914fdb")
    assert (
        harness._PROFILE.plan_sha256
        == "7f62c90df051f5c4998cc3303b7a97dfb80294dfd743662c2f9930422cb83666"
    )
    assert harness._PROFILE.plan_byte_length == 6199


@pytest.mark.parametrize("status", tuple(PersonalDesktopUnattendedPaperStartupStatus))
def test_every_pd4c_status_is_evidence_only_and_preserved(
    monkeypatch: pytest.MonkeyPatch,
    status: PersonalDesktopUnattendedPaperStartupStatus,
) -> None:
    case = _case(monkeypatch, status=status)
    record = _run(case)
    assert record["qualification_status"] == status.value
    assert record["result"] == "VALIDATED"
    assert record["unattended_operation_authorized"] is False
    assert record["execution_performed"] is False
    assert record["recovery_performed"] is False
    assert len([item for item in case.calls if item[0] == "qualifier"]) == 1


def test_nonexact_pd4c_result_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    case = _case(monkeypatch)
    case.deps = replace(case.deps, qualifier=lambda *args, **kwargs: SimpleNamespace())
    with pytest.raises(harness._ValidationError):
        _run(case)


def test_main_emits_one_sanitized_non_authorizing_record(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    case = _case(
        monkeypatch, status=PersonalDesktopUnattendedPaperStartupStatus.BLOCKED
    )
    monkeypatch.setattr(harness, "_production_dependencies", lambda: case.deps)
    assert harness.main([]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert len(captured.out.splitlines()) == 1
    record = json.loads(captured.out)
    assert record["qualification_status"] == "BLOCKED"
    assert record["paper_account_id"] is None
    forbidden = ("F:\\", "C:\\", "Traceback", "Exception", "secret", "token")
    assert all(item not in captured.out for item in forbidden)


def test_source_has_no_forbidden_effect_boundary_or_dependency() -> None:
    path = (
        _ROOT / "src" / "trading_bot" / "cli" / "pd4_read_only_unattended_validation.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {
        "execute_personal_desktop_unattended_paper_operation",
        "open_personal_desktop_unattended_invocation_output_capability",
        "open_personal_desktop_unattended_paper_runtime_output_capability",
        "recover_personal_desktop_paper_receipt",
        "execute_paper_operation_once",
        "provider_call",
        "broker_order",
        "live_order",
        "schtasks",
        "register_task",
        "run_task",
    }
    called = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert called.isdisjoint(forbidden)
    assert set(harness._Dependencies.__dataclass_fields__).isdisjoint(forbidden)
    production = harness._production_dependencies()
    expected_qualifier = (
        harness.startup_qualification.qualify_personal_desktop_unattended_paper_startup
    )
    assert production.qualifier is expected_qualifier


def test_publication_freeze_and_provider_call_six_remain_unchanged() -> None:
    harness._require_frozen_publication()
    assert str(harness._EXPECTED_SELECTION_ID) == "36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280"
    assert (
        harness._EXPECTED_SELECTED_SHA256
        == "31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d"
    )
    assert harness._EXPECTED_SELECTED_BYTE_LENGTH == 1291


def test_disposable_seam_rejects_genuine_production_callables() -> None:
    production = harness._production_dependencies()
    for field in fields(harness._Dependencies):
        values = {
            item.name: (lambda *args, **kwargs: None)
            for item in fields(harness._Dependencies)
        }
        values[field.name] = getattr(production, field.name)
        with pytest.raises(TypeError):
            harness._run_validation_for_test(
                harness._open_disposable_validation_authority_for_test(),
                harness._Dependencies(**values),
            )
