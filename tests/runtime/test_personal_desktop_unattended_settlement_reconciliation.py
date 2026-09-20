"""D9-A source-only admission, durable classification, and containment tests."""

from __future__ import annotations

import ast
import ctypes
import inspect
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from tests.runtime.test_paper_operation import CONFIGURATION, _completed
from tests.runtime.test_personal_desktop_unattended_settlement_qualification import (
    Harness as DecisionHarness,
)
from tests.runtime.test_verified_snapshot_preparation import calendar

from trading_bot.cli import paper_operation_execution
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification as Operation,
)
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationInspectionCode,
    PaperOperationInspectionResult,
)
from trading_bot.runtime import (
    personal_desktop_unattended_settlement_reconciliation as d9,
)
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    derive_checkpointed_verified_snapshot_application_id,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexAcquisition,
    PaperAccountMutexState,
    paper_account_mutex_digest,
    paper_account_mutex_name,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_qualification import (
    PaperReceiptRecoveryQualificationDiagnostic as RecoveryDiagnostic,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_qualification import (
    PaperReceiptRecoveryQualificationResult as RecoveryResult,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_qualification import (
    PaperReceiptRecoveryQualificationStatus as Recovery,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageClassification as Storage,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageDiagnostic as StorageDiagnostic,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageReadResult as StorageResult,
)
from trading_bot.runtime.windows_authority import AuthorityPrincipalError


class _Admission:
    def __init__(self, account_id: str, events: list[str]) -> None:
        self.acquisition = PaperAccountMutexAcquisition(
            account_id,
            paper_account_mutex_name(account_id),
            paper_account_mutex_digest(account_id),
            PaperAccountMutexState.OWNED,
        )
        self.events = events

    def __enter__(self):
        self.events.append("mutex-enter")
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.events.append("mutex-exit")
        return False


@pytest.fixture(autouse=True)
def prohibit_native_and_effects(monkeypatch):
    from trading_bot.runtime import (
        personal_desktop_paper_receipt_recovery_execution,
        personal_desktop_paper_runtime_output,
        personal_desktop_unattended_capture_warmup,
        personal_desktop_unattended_decision_publication,
        personal_desktop_unattended_market_data_capture,
        personal_desktop_unattended_paper_operation_execution,
        personal_desktop_unattended_paper_storage_provisioning,
        personal_desktop_unattended_settlement_execution,
    )

    def forbidden(*args, **kwargs):
        pytest.fail("D9-A reached native production or a prohibited effect")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    for module, name in (
        (paper_operation_execution, "execute_paper_operation_once"),
        (
            personal_desktop_paper_receipt_recovery_execution,
            "recover_personal_desktop_paper_receipt",
        ),
        (
            personal_desktop_unattended_market_data_capture,
            "run_personal_desktop_unattended_market_data_capture",
        ),
        (
            personal_desktop_unattended_capture_warmup,
            "run_personal_desktop_unattended_capture_warmup",
        ),
        (
            personal_desktop_unattended_decision_publication,
            "run_personal_desktop_unattended_decision_publication",
        ),
        (
            personal_desktop_paper_runtime_output,
            "open_personal_desktop_unattended_invocation_output_capability",
        ),
        (
            personal_desktop_unattended_paper_operation_execution,
            "execute_personal_desktop_unattended_paper_operation_from_verified_plan",
        ),
        (
            personal_desktop_unattended_paper_storage_provisioning,
            "provision_personal_desktop_unattended_storage",
        ),
        (
            personal_desktop_unattended_settlement_execution,
            "execute_personal_desktop_unattended_settlement",
        ),
    ):
        monkeypatch.setattr(module, name, forbidden)


class Harness(DecisionHarness):
    def __init__(self, monkeypatch):
        super().__init__(monkeypatch)
        self.gate_reads = 0
        self.gate_drift_on = None
        self.token_reads = 0
        self.token_drift = False
        self.expected = d9._reconstruct(self.dependencies())
        self.gate_reads = 0
        self.token_reads = 0
        self.predecessor = self.expected.binding.decision.predecessor_checkpoint_id
        self.successor = UUID(int=777)
        self.operation_id = UUID(int=888)
        self.application_id = derive_checkpointed_verified_snapshot_application_id(
            self.predecessor, self.expected.plan.checkpointed_request.request_id
        )
        self.account = self._account(self.predecessor)
        self.account_reads = 0
        self.recovery_reads = 0
        self.storage_reads = 0
        self.inspection_reads = 0
        self.storage = Storage.FINALIZED_IDENTICAL
        self.operation = Operation.PENDING
        self.recovery = Recovery.NO_RECOVERY_REQUIRED
        self.final_gate_drift = False
        self.storage_proof = True
        self.account_drift = False
        self.final_account_drift = False
        self.storage_drift = False
        self.operation_drift = False
        self.alternate_invocation = False
        self.fail_build = False
        self.events.clear()

    def _account(self, terminal):
        checkpoints = (
            (self.predecessor,)
            if terminal == self.predecessor
            else (self.predecessor, terminal)
        )
        applications = () if terminal == self.predecessor else (self.application_id,)
        return SimpleNamespace(
            anchor=SimpleNamespace(
                paper_account_id=self.binding.decision.paper_account_id
            ),
            lineage=SimpleNamespace(
                terminal_checkpoint_id=terminal,
                checkpoint_ids=checkpoints,
                application_ids=applications,
            ),
            prior_checkpoint=SimpleNamespace(checkpoint_id=terminal),
            receipts=(),
        )

    def recovery_result(self):
        self.recovery_reads += 1
        if self.recovery is Recovery.RECEIPT_RECOVERY_REQUIRED:
            return RecoveryResult(
                self.recovery,
                RecoveryDiagnostic.VERIFIED_TERMINAL_RECEIPT_MISSING,
                self.binding.decision.paper_account_id,
                self.account.lineage.terminal_checkpoint_id,
                self.application_id,
                self.predecessor,
            )
        return RecoveryResult(
            self.recovery,
            RecoveryDiagnostic.VERIFIED_COMPLETE_ACCOUNT,
            self.binding.decision.paper_account_id,
            self.account.lineage.terminal_checkpoint_id,
            None,
            None,
        )

    def storage_result(self, c1, expected):
        assert c1 is self.authority
        self.storage_reads += 1
        if self.storage_drift and self.storage_reads == 2:
            self.storage = Storage.ABSENT
        classification = self.storage
        diagnostic = {
            Storage.ABSENT: StorageDiagnostic.VERIFIED_ABSENT,
            Storage.FINALIZED_IDENTICAL: StorageDiagnostic.VERIFIED_FINALIZED_IDENTICAL,
            Storage.STAGING_PRESENT: StorageDiagnostic.STAGING_PRESENT,
            Storage.CONFLICTING: StorageDiagnostic.VERIFIED_CONFLICT,
            Storage.BLOCKED: StorageDiagnostic.VERIFICATION_BLOCKED,
        }[classification]
        return StorageResult(
            classification,
            expected.invocation.invocation_id,
            (2 if self.alternate_invocation else 1)
            if classification is Storage.FINALIZED_IDENTICAL
            else 0,
            expected.invocation.invocation_id
            if classification is Storage.FINALIZED_IDENTICAL
            else None,
            diagnostic,
        )

    def inspect(self, root, inputs):
        self.inspection_reads += 1
        if self.operation_drift and self.inspection_reads == 2:
            self.operation = Operation.CONFLICTING
        assert root == Path(d9.PERSONAL_DESKTOP_PAPER_V2_RUNTIME)
        diagnostic = {
            Operation.PENDING: PaperOperationInspectionCode.PENDING,
            Operation.ALREADY_APPLIED: PaperOperationInspectionCode.ALREADY_APPLIED,
            Operation.BLOCKED: (
                PaperOperationInspectionCode.FINALIZED_TRANSITION_WITHOUT_RECEIPT
            ),
            Operation.CONFLICTING: PaperOperationInspectionCode.LINEAGE_CONFLICT,
        }[self.operation]
        return PaperOperationInspectionResult(
            self.operation,
            inputs.intent.operation_id,
            self.predecessor,
            inputs.application_id,
            Path("receipt.json")
            if self.operation is Operation.ALREADY_APPLIED
            else None,
            (diagnostic,),
        )

    def dependencies(self):
        base = super().dependencies()
        values = {
            field.name: getattr(base, field.name)
            for field in fields(base)
            if field.name != "startup"
        }

        def read_account(c1, configurations):
            assert c1 is self.authority
            assert configurations == self.expected.configurations
            self.account_reads += 1
            if self.account_drift and self.account_reads == 2:
                return self._account(self.successor)
            if self.final_account_drift and self.account_reads == 3:
                return self._account(self.successor)
            return self.account

        def require_storage(result):
            if not self.storage_proof:
                raise ValueError("storage lacks production provenance")
            finalized = (
                (self.expected.invocation,)
                if result.classification is Storage.FINALIZED_IDENTICAL
                else ()
            )
            if self.alternate_invocation and finalized:
                finalized = (
                    *finalized,
                    SimpleNamespace(
                        invocation=SimpleNamespace(
                            execution_session=self.expected.completed
                        )
                    ),
                )
            return SimpleNamespace(
                authority=self.authority,
                expected=self.expected.invocation,
                classification=result.classification,
                finalized=finalized,
            )

        def build_material(account, selected, plan, calendar):
            if self.fail_build:
                raise ValueError("prefix reconstruction failed")
            assert account is self.account
            assert selected == self.expected.original
            assert plan == self.expected.plan
            del calendar
            inputs = SimpleNamespace(
                intent=SimpleNamespace(
                    operation_id=self.operation_id,
                    prior_lineage_evidence=SimpleNamespace(
                        terminal_checkpoint_id=self.predecessor
                    ),
                ),
                application_id=self.application_id,
            )
            return d9.preparation.PreparedPaperOperationMaterial(plan, inputs)

        values.update(
            qualify_recovery=lambda c1, configs: self.recovery_result(),
            require_recovery=lambda result: SimpleNamespace(
                account=self.account,
                missing_application_id=result.missing_application_id,
                missing_predecessor_checkpoint_id=result.predecessor_checkpoint_id,
            ),
            read_account=read_account,
            require_account=lambda value: value,
            admit_healthy=lambda value: _Admission(
                self.binding.decision.paper_account_id, self.events
            ),
            admit_recovery=lambda value: _Admission(
                self.binding.decision.paper_account_id, self.events
            ),
            build_material=build_material,
            read_storage=self.storage_result,
            require_storage=require_storage,
            inspect_operation=self.inspect,
        )
        values["gate_state"] = self.gate_state

        def observe_token():
            self.token_reads += 1
            token = self.observe_token()
            if self.token_drift and self.token_reads == 2:
                return replace(token, groups=(*token.groups, ("S-1-5-99", 0)))
            return token

        values["observe_token"] = observe_token
        return d9.DisposableSettlementReconciliationDependencies(**values)

    def gate_state(self):
        self.gate_reads += 1
        if self.gate_drift_on == self.gate_reads:
            return (True, *(False for _ in range(7)))
        return tuple(self.gates)

    def run(self, monkeypatch):
        monkeypatch.setattr(d9, "_reconstruct", lambda d: self.expected)
        return d9.reconcile_personal_desktop_unattended_settlement_for_test(
            self.dependencies()
        )


@pytest.fixture
def harness(monkeypatch):
    return Harness(monkeypatch)


def test_zero_argument_and_bounded_result_shape():
    assert not inspect.signature(
        d9.reconcile_personal_desktop_unattended_settlement
    ).parameters
    names = {field.name for field in fields(d9.SettlementReconciliationResult)}
    assert not names & {
        "authority",
        "token",
        "binding",
        "plan",
        "receipt",
        "path",
        "handle",
        "capability",
    }
    with pytest.raises(ValueError):
        d9.SettlementReconciliationResult(d9.Status.BLOCKED, real_effect_performed=True)


@pytest.mark.parametrize("gate", range(8))
def test_each_open_gate_blocks_before_durable_discovery(harness, gate):
    harness.gates[gate] = True
    with pytest.raises(ValueError):
        d9._reconstruct(harness.dependencies())


@pytest.mark.parametrize("value", [0, 1, None, "False"])
def test_nonboolean_gate_blocks(harness, value):
    harness.gates[2] = value
    with pytest.raises(ValueError):
        d9._reconstruct(harness.dependencies())


def test_independent_decision_and_plan_reconstruction(harness):
    expected = d9._reconstruct(harness.dependencies())
    assert expected.binding == harness.binding
    assert expected.completed == harness.execution.session
    assert expected.invocation.invocation.plan_artifact == expected.plan.artifact_bytes
    assert expected.configurations == (b"retained-configuration",)
    harness.fail_proof = True
    with pytest.raises(ValueError):
        d9._reconstruct(harness.dependencies())


def test_trading_token_and_current_c1_required_before_discovery(harness):
    bad_token = replace(harness.observe_token(), elevated=True)
    with pytest.raises(AuthorityPrincipalError):
        d9._reconstruct(
            replace(harness.dependencies(), observe_token=lambda: bad_token)
        )

    def validate(c1):
        if c1 is not harness.authority:
            raise ValueError("C1 provenance unavailable")
        return c1

    with pytest.raises(ValueError):
        d9._reconstruct(
            replace(
                harness.dependencies(),
                acquire_c1=lambda: object(),
                validate_c1=validate,
            )
        )


def test_execution_c3_open_and_final_plan_replay_are_independent(harness):
    expected_open = harness.execution.selected

    def build_open(selected, c1):
        assert selected is expected_open
        return d9.build_c3_verified_daily_bar_open_binding(selected, c1)

    d9._reconstruct(replace(harness.dependencies(), build_open=build_open))
    with pytest.raises(ValueError):
        d9._reconstruct(
            replace(
                harness.dependencies(),
                verify_plan=lambda *args, **kwargs: object(),
            )
        )
    harness.selections[harness.execution.session] = harness.current
    with pytest.raises(ValueError):
        d9._reconstruct(harness.dependencies())


def test_historical_receipt_configuration_is_not_duplicated(harness):
    dependencies = replace(
        harness.dependencies(),
        historical_configurations=lambda c1: (harness.expected.plan.artifact_bytes,),
    )
    expected = d9._reconstruct(dependencies)
    assert expected.configurations == (expected.plan.artifact_bytes,)


def test_pending_and_absent_are_diagnostic_only(harness, monkeypatch):
    harness.storage = Storage.ABSENT
    result = harness.run(monkeypatch)
    assert result.classification is d9.Status.NOT_APPLIED
    assert result.real_effect_performed is False
    assert harness.storage_reads == 2
    assert harness.inspection_reads == 2
    assert [event for event in harness.events if event.startswith("mutex-")] == [
        "mutex-enter",
        "mutex-exit",
    ]


def test_unchanged_repeat_is_read_only_and_deterministic(harness, monkeypatch):
    first = harness.run(monkeypatch)
    second = harness.run(monkeypatch)
    assert first == second
    assert first.classification is d9.Status.NOT_APPLIED
    assert first.real_effect_performed is False
    assert harness.storage_reads == 4
    assert harness.inspection_reads == 4


def test_final_gate_and_token_drift_block(harness, monkeypatch):
    harness.gate_drift_on = 3
    assert harness.run(monkeypatch).classification is d9.Status.BLOCKED
    harness.gate_drift_on = None
    harness.gate_reads = 0
    harness.token_drift = True
    harness.token_reads = 0
    assert harness.run(monkeypatch).classification is d9.Status.BLOCKED


@pytest.mark.parametrize(
    "storage", [Storage.STAGING_PRESENT, Storage.CONFLICTING, Storage.BLOCKED]
)
def test_unsafe_invocation_storage_blocks(harness, monkeypatch, storage):
    harness.storage = storage
    assert harness.run(monkeypatch).classification is d9.Status.BLOCKED


@pytest.mark.parametrize("operation", [Operation.BLOCKED, Operation.CONFLICTING])
def test_unsafe_operation_state_blocks(harness, monkeypatch, operation):
    harness.operation = operation
    assert harness.run(monkeypatch).classification is d9.Status.BLOCKED


def test_storage_provenance_and_prelock_drift_block(harness, monkeypatch):
    harness.storage_proof = False
    assert harness.run(monkeypatch).classification is d9.Status.BLOCKED
    harness.storage_proof = True
    harness.account_drift = True
    harness.account_reads = 0
    assert harness.run(monkeypatch).classification is d9.Status.BLOCKED


def test_alternate_invocation_and_prefix_reconstruction_failure_block(
    harness, monkeypatch
):
    harness.alternate_invocation = True
    assert harness.run(monkeypatch).classification is d9.Status.BLOCKED
    harness.alternate_invocation = False
    harness.fail_build = True
    assert harness.run(monkeypatch).classification is d9.Status.BLOCKED


def test_exact_terminal_missing_receipt_is_diagnostic(harness, monkeypatch):
    harness.account = harness._account(harness.successor)
    harness.recovery = Recovery.RECEIPT_RECOVERY_REQUIRED
    harness.operation = Operation.BLOCKED
    result = harness.run(monkeypatch)
    assert result.classification is d9.Status.RECEIPT_RECOVERY_REQUIRED
    assert result.successor_checkpoint_id == harness.successor
    assert result.real_effect_performed is False


def test_wrong_missing_application_blocks(harness, monkeypatch):
    harness.account = harness._account(harness.successor)
    harness.recovery = Recovery.RECEIPT_RECOVERY_REQUIRED
    harness.operation = Operation.BLOCKED
    harness.application_id = UUID(int=999)
    assert harness.run(monkeypatch).classification is d9.Status.BLOCKED


def test_wrong_recovery_predecessor_blocks(harness, monkeypatch):
    harness.account = harness._account(harness.successor)
    harness.recovery = Recovery.RECEIPT_RECOVERY_REQUIRED
    harness.operation = Operation.BLOCKED
    original = harness.recovery_result

    def wrong_recovery():
        return replace(original(), predecessor_checkpoint_id=UUID(int=999))

    dependencies = replace(
        harness.dependencies(),
        qualify_recovery=lambda c1, configs: wrong_recovery(),
    )
    monkeypatch.setattr(d9, "_reconstruct", lambda d: harness.expected)
    result = d9.reconcile_personal_desktop_unattended_settlement_for_test(dependencies)
    assert result.classification is d9.Status.BLOCKED


def test_applied_requires_verified_receipt_and_current_q(harness, monkeypatch):
    harness.account = harness._account(harness.successor)
    harness.operation = Operation.ALREADY_APPLIED
    assert harness.run(monkeypatch).classification is d9.Status.BLOCKED
    monkeypatch.setattr(
        d9,
        "_completed_receipt",
        lambda account, material: (
            d9.PaperOperationStatus.COMPLETED,
            harness.successor,
        ),
    )
    assert harness.run(monkeypatch).classification is d9.Status.RECONCILED
    harness.storage = Storage.ABSENT
    assert harness.run(monkeypatch).classification is d9.Status.BLOCKED


def test_final_storage_drift_blocks(harness, monkeypatch):
    original = harness.storage_result

    def drift(c1, expected):
        if harness.storage_reads:
            harness.storage = Storage.ABSENT
        return original(c1, expected)

    monkeypatch.setattr(harness, "storage_result", drift)
    assert harness.run(monkeypatch).classification is d9.Status.BLOCKED


def test_final_operation_and_account_drift_block(harness, monkeypatch):
    harness.operation_drift = True
    assert harness.run(monkeypatch).classification is d9.Status.BLOCKED
    harness.operation_drift = False
    harness.operation = Operation.PENDING
    harness.inspection_reads = 0
    harness.final_account_drift = True
    harness.account_reads = 0
    assert harness.run(monkeypatch).classification is d9.Status.BLOCKED


def test_exact_completed_receipt_reverifies_and_requires_current_q():
    receipt, genesis, snapshot, report, successor = _completed()
    prior = receipt.prior_lineage_evidence
    inputs = SimpleNamespace(
        intent=receipt.intent,
        application_id=receipt.application_id,
        cycle_configuration_payload=CONFIGURATION,
        prior_genesis_checkpoint=genesis,
        prior_successor_checkpoints=(),
        prior_cycle_reports=(),
        prior_snapshots=(),
        completed_snapshot_payload=snapshot,
        calendar=calendar(),
    )
    material = SimpleNamespace(execution_inputs=inputs)
    account = SimpleNamespace(
        receipts=(receipt,),
        lineage=receipt.successor_lineage_evidence,
        prior_checkpoint=SimpleNamespace(
            checkpoint_id=receipt.successor_lineage_evidence.terminal_checkpoint_id
        ),
        reports=(SimpleNamespace(payload=report),),
        successors=(SimpleNamespace(payload=successor),),
    )

    status, terminal = d9._completed_receipt(account, material)
    assert status is d9.PaperOperationStatus.COMPLETED
    assert terminal != prior.terminal_checkpoint_id
    assert terminal == account.prior_checkpoint.checkpoint_id
    account.prior_checkpoint.checkpoint_id = prior.terminal_checkpoint_id
    with pytest.raises(ValueError):
        d9._completed_receipt(account, material)
    account.prior_checkpoint.checkpoint_id = terminal
    account.lineage = SimpleNamespace(
        edge_count=2,
        terminal_checkpoint_id=UUID(int=999),
    )
    with pytest.raises(ValueError):
        d9._completed_receipt(account, material)


def test_no_effect_assignment_or_execution_import():
    source = Path(d9.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {
        "execute_personal_desktop_unattended_settlement",
        "execute_personal_desktop_unattended_paper_operation_from_verified_plan",
        "execute_paper_operation_once",
        "recover_personal_desktop_paper_receipt",
    }
    assert not forbidden.intersection(source)
    assert "personal_desktop_unattended_settlement_qualification" not in source
    assert "personal_desktop_unattended_settlement_execution" not in source
    assert not any(
        isinstance(node, (ast.Assign, ast.AnnAssign))
        and "EFFECTS_ENABLED" in ast.unparse(node)
        for node in ast.walk(tree)
    )
