"""D8-B source-only reconstruction, gate isolation, and one-attempt tests."""

from __future__ import annotations

import ast
import ctypes
import inspect
from dataclasses import fields, replace
from uuid import UUID

import pytest
from tests.runtime.test_personal_desktop_unattended_settlement_qualification import (
    Harness as QualificationHarness,
)

from trading_bot.cli.paper_operation_execution import (
    PaperOperationExecutionClassification,
)
from trading_bot.cli.paper_operation_inspection import PaperOperationClassification
from trading_bot.runtime import (
    personal_desktop_unattended_paper_operation_execution as pd4d,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_startup_qualification as startup_module,
)
from trading_bot.runtime import (
    personal_desktop_unattended_settlement_execution as d8b,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObservation,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    FinalizedUnattendedDecisionForSessionClassification as Discovery,
)

OperationStatus = pd4d.PersonalDesktopUnattendedPaperOperationStatus
OperationDiagnostic = pd4d.PersonalDesktopUnattendedPaperOperationDiagnostic
Startup = startup_module.PersonalDesktopUnattendedPaperStartupStatus


@pytest.fixture(autouse=True)
def prohibit_native(monkeypatch):
    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda *args, **kwargs: pytest.fail("D8-B reached native production"),
        raising=False,
    )
    assert pd4d.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED is False
    yield
    assert pd4d.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED is False


class Harness(QualificationHarness):
    def __init__(self, monkeypatch):
        super().__init__(monkeypatch)
        self.calls = 0
        self.operation_status = (
            pd4d.PersonalDesktopUnattendedPaperOperationStatus.COMPLETED
        )
        self.operation_mutation = None
        self.execution_error = None

    def gate_state(self):
        state = list(self.gates)
        if state[6] is False:
            state[6] = (
                pd4d.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED
            )
        return tuple(state)

    def execute(self, c1, selected, plan, *, historical_cycle_configuration_payloads):
        self.calls += 1
        self.events.append("execute")
        assert self.gate_state() == (False,) * 6 + (True, False)
        assert c1 is self.authority
        assert selected is self.current.selected
        assert historical_cycle_configuration_payloads[-1] == plan.artifact_bytes
        if self.execution_error is not None:
            raise self.execution_error
        startup = self.startup(
            c1,
            selected,
            plan,
            historical_cycle_configuration_payloads=historical_cycle_configuration_payloads,
        )
        status = self.operation_status
        if status is OperationStatus.RECEIPT_RECOVERY_REQUIRED:
            result = pd4d.PersonalDesktopUnattendedPaperOperationResult(
                status,
                OperationDiagnostic.VERIFIED_TERMINAL_RECEIPT_MISSING,
                self.binding.decision.paper_account_id,
                None,
                None,
                None,
                startup.application_id,
                self.binding.decision.predecessor_checkpoint_id,
                UUID(int=888),
                False,
                False,
                None,
                None,
            )
        else:
            completed = (
                status is pd4d.PersonalDesktopUnattendedPaperOperationStatus.COMPLETED
            )
            diagnostic = {
                OperationStatus.COMPLETED: OperationDiagnostic.VERIFIED_COMPLETED,
                OperationStatus.ALREADY_APPLIED: (
                    OperationDiagnostic.VERIFIED_ALREADY_APPLIED
                ),
                OperationStatus.BLOCKED: OperationDiagnostic.EXECUTION_BLOCKED,
            }[status]
            result = pd4d.PersonalDesktopUnattendedPaperOperationResult(
                status,
                diagnostic,
                self.binding.decision.paper_account_id,
                startup.selected_snapshot_id,
                startup.invocation_id,
                startup.operation_id,
                startup.application_id,
                self.binding.decision.predecessor_checkpoint_id,
                UUID(int=777)
                if status
                is not pd4d.PersonalDesktopUnattendedPaperOperationStatus.BLOCKED
                else None,
                False,
                completed,
                PaperOperationExecutionClassification.COMPLETED if completed else None,
                PaperOperationClassification.ALREADY_APPLIED
                if status
                is not pd4d.PersonalDesktopUnattendedPaperOperationStatus.BLOCKED
                else None,
            )
        return self.operation_mutation(result) if self.operation_mutation else result

    def dependencies(self):
        qualified = super().dependencies()
        values = {
            field.name: getattr(qualified, field.name) for field in fields(qualified)
        }
        values["gate_state"] = self.gate_state
        values["execute"] = self.execute
        return d8b.DisposableSettlementExecutionDependencies(**values)

    def run(self, **overrides):
        return d8b.execute_personal_desktop_unattended_settlement_for_test(
            replace(self.dependencies(), **overrides)
        )


@pytest.fixture
def harness(monkeypatch):
    return Harness(monkeypatch)


def test_zero_parameter_production_and_sanitized_result():
    assert not inspect.signature(
        d8b.execute_personal_desktop_unattended_settlement
    ).parameters
    assert not {field.name for field in fields(d8b.SettlementExecutionResult)} & {
        "authority",
        "binding",
        "selected",
        "plan",
        "path",
        "handle",
        "token",
        "capability",
    }
    assert (
        d8b._production_dependencies().execute
        is pd4d.execute_personal_desktop_unattended_paper_operation_from_verified_plan
    )


def test_pd4d_verified_plan_wrapper_uses_existing_composition(harness, monkeypatch):
    opened = d8b.build_c3_verified_daily_bar_open_binding(
        harness.execution.selected, harness.authority
    )
    plan = d8b.complete_manual_paper_strategy_plan(
        harness.binding.decision.prepared_decision,
        opened,
        d8b.personal_desktop_unattended_decision_calendar(),
    )
    expected = object()

    def reconstruct(account, selected, verified_plan, calendar):
        assert account is expected
        assert selected is harness.current.selected
        assert verified_plan is plan
        assert calendar is not None
        return expected

    def compose(authority, selected, inputs, calendar, dependencies, *, _issuer):
        assert authority is harness.authority
        assert selected is harness.current.selected
        assert inputs.historical_configurations[-1] == plan.artifact_bytes
        assert (
            dependencies.qualification.build_material(
                expected, selected, inputs, calendar
            )
            is expected
        )
        assert _issuer is pd4d._PRODUCTION_EXECUTION_ISSUER
        return expected

    monkeypatch.setattr(
        pd4d, "reconstruct_verified_paper_operation_from_plan", reconstruct
    )
    monkeypatch.setattr(
        pd4d, "_compose_personal_desktop_unattended_paper_operation", compose
    )
    assert (
        pd4d.execute_personal_desktop_unattended_paper_operation_from_verified_plan(
            harness.authority,
            harness.current.selected,
            plan,
            historical_cycle_configuration_payloads=(plan.artifact_bytes,),
        )
        is expected
    )


@pytest.mark.parametrize("index", range(8))
def test_each_open_gate_blocks_before_discovery(harness, index):
    harness.gates[index] = True
    assert harness.run().classification is d8b.Status.BLOCKED
    assert "discovery" not in harness.events
    assert harness.calls == 0


@pytest.mark.parametrize("index", range(8))
@pytest.mark.parametrize("bad", [1, 0, None, "False"])
def test_non_boolean_gate_blocks(harness, index, bad):
    harness.gates[index] = bad
    assert harness.run().classification is d8b.Status.BLOCKED
    assert harness.calls == 0


def test_no_decision_and_existing_durable_states_never_open_effect(harness):
    harness.discovery_state = Discovery.NONE
    assert harness.run().classification is d8b.Status.SETTLEMENT_NOT_READY
    assert harness.calls == 0
    harness.discovery_state = Discovery.FINALIZED
    harness.startup_state = Startup.ALREADY_APPLIED
    applied = harness.run()
    assert applied.classification is d8b.Status.SETTLEMENT_ALREADY_APPLIED
    assert applied.real_effect_performed is False
    assert harness.calls == 0
    harness.startup_state = Startup.RECEIPT_RECOVERY_REQUIRED
    recovery = harness.run()
    assert recovery.classification is d8b.Status.RECEIPT_RECOVERY_REQUIRED
    assert recovery.account_predecessor_checkpoint_id != recovery.final_checkpoint_id
    assert recovery.real_effect_performed is False
    assert harness.calls == 0
    harness.startup_state = Startup.BLOCKED
    assert harness.run().classification is d8b.Status.BLOCKED
    assert harness.calls == 0


def test_contradictory_startup_operation_blocks_before_gate(harness):
    harness.startup_mutation = lambda result: replace(
        result, operation_classification=PaperOperationClassification.ALREADY_APPLIED
    )
    assert harness.run().classification is d8b.Status.BLOCKED
    assert harness.calls == 0


def test_fresh_reconstruction_and_single_completed_call(harness):
    result = harness.run()
    assert result.classification is d8b.Status.SETTLEMENT_COMPLETED
    assert result.real_effect_performed is True
    assert result.all_eight_gates_closed is True
    assert result.decision_id == harness.binding.decision.decision_id
    assert result.final_plan_id is not None
    assert harness.calls == 1
    assert harness.c1_reads >= 3
    assert harness.events.count("selected-proof") == 7
    assert harness.events.index("discovery") < harness.events.index("execute")


def test_discovery_tamper_and_plan_mismatch_block_before_effect(harness):
    harness.fail_proof = True
    assert harness.run().classification is d8b.Status.BLOCKED
    assert harness.calls == 0
    harness.fail_proof = False
    assert (
        harness.run(verify_plan=lambda *a, **k: object()).classification
        is d8b.Status.BLOCKED
    )
    assert harness.calls == 0


def test_selected_history_and_execution_substitution_block(harness):
    harness.selections.pop(harness.execution.session)
    assert harness.run().classification is d8b.Status.BLOCKED
    assert harness.calls == 0


def test_token_c1_and_final_gate_drift_block(harness):
    assert (
        harness.run(
            validate_c1=lambda c1: (_ for _ in ()).throw(ValueError())
        ).classification
        is d8b.Status.BLOCKED
    )
    assert harness.calls == 0
    invalid = TradingTokenObservation("S-1-5-18", 1, False, False, ())
    assert (
        harness.run(observe_token=lambda: invalid).classification is d8b.Status.BLOCKED
    )
    assert harness.calls == 0

    def drift():
        return (
            tuple([True] + [False] * 7)
            if harness.c1_reads >= 2
            else harness.gate_state()
        )

    assert harness.run(gate_state=drift).classification is d8b.Status.BLOCKED
    assert harness.calls == 0


def test_post_call_token_or_c1_drift_is_ambiguous_without_retry(harness):
    valid = harness.observe_token
    reads = 0

    def drift_token():
        nonlocal reads
        reads += 1
        if reads >= 3:
            return TradingTokenObservation("S-1-5-18", 1, False, False, ())
        return valid()

    token_result = harness.run(observe_token=drift_token)
    assert token_result.classification is d8b.Status.SETTLEMENT_OUTCOME_AMBIGUOUS
    assert token_result.real_effect_performed is True
    assert harness.calls == 1

    harness.calls = 0
    reads = 0

    def drift_c1():
        nonlocal reads
        reads += 1
        return harness.authority if reads < 3 else object()

    c1_result = harness.run(acquire_c1=drift_c1)
    assert c1_result.classification is d8b.Status.SETTLEMENT_OUTCOME_AMBIGUOUS
    assert c1_result.real_effect_performed is True
    assert harness.calls == 1


@pytest.mark.parametrize(
    "status,expected",
    [
        (
            pd4d.PersonalDesktopUnattendedPaperOperationStatus.ALREADY_APPLIED,
            d8b.Status.SETTLEMENT_ALREADY_APPLIED,
        ),
        (
            pd4d.PersonalDesktopUnattendedPaperOperationStatus.RECEIPT_RECOVERY_REQUIRED,
            d8b.Status.RECEIPT_RECOVERY_REQUIRED,
        ),
        (
            pd4d.PersonalDesktopUnattendedPaperOperationStatus.BLOCKED,
            d8b.Status.SETTLEMENT_OUTCOME_AMBIGUOUS,
        ),
    ],
)
def test_pd4d_result_mapping(harness, status, expected):
    harness.operation_status = status
    result = harness.run()
    assert result.classification is expected
    assert result.real_effect_performed is False
    assert result.all_eight_gates_closed is True
    assert harness.calls == 1


def test_mismatched_pd4d_identity_is_ambiguous_without_retry(harness):
    harness.operation_mutation = lambda result: replace(
        result, operation_id=UUID(int=999)
    )
    result = harness.run()
    assert result.classification is d8b.Status.SETTLEMENT_OUTCOME_AMBIGUOUS
    assert result.real_effect_performed is True
    assert harness.calls == 1


def test_unrelated_pd4d_recovery_is_ambiguous_without_repair(harness):
    harness.operation_status = OperationStatus.RECEIPT_RECOVERY_REQUIRED
    harness.operation_mutation = lambda result: replace(
        result, application_id=UUID(int=999)
    )
    result = harness.run()
    assert result.classification is d8b.Status.SETTLEMENT_OUTCOME_AMBIGUOUS
    assert result.real_effect_performed is False
    assert harness.calls == 1


def test_blocked_pd4d_after_executor_crossing_is_ambiguous(harness):
    harness.operation_status = OperationStatus.BLOCKED
    harness.operation_mutation = lambda result: replace(result, executor_called=True)
    result = harness.run()
    assert result.classification is d8b.Status.SETTLEMENT_OUTCOME_AMBIGUOUS
    assert result.real_effect_performed is True
    assert harness.calls == 1


def test_exception_after_gate_open_is_ambiguous_and_one_attempt(harness):
    harness.execution_error = RuntimeError("unknown outcome")
    result = harness.run()
    assert result.classification is d8b.Status.SETTLEMENT_OUTCOME_AMBIGUOUS
    assert result.real_effect_performed is False
    assert harness.calls == 1


def test_source_assigns_only_exact_unattended_gate():
    tree = ast.parse(inspect.getsource(d8b))
    assigned = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assigned.update(
                ast.unparse(target)
                for target in targets
                if "EFFECTS_ENABLED" in ast.unparse(target)
            )
    assert assigned == {
        "pd4d.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED"
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names & {
        "execute_paper_operation_once",
        "recover_personal_desktop_paper_receipt",
        "run_personal_desktop_unattended_market_data_capture",
        "run_personal_desktop_unattended_decision_publication",
        "provision_personal_desktop_unattended_storage",
        "open_personal_desktop_unattended_invocation_output_capability",
        "open_personal_desktop_unattended_paper_runtime_output_capability",
    }
    assert (
        "personal_desktop_unattended_settlement_qualification"
        not in inspect.getsource(d8b)
    )
