"""D8-A source-only settlement qualification and effect containment."""

from __future__ import annotations

import ast
import ctypes
import inspect
from dataclasses import fields, replace
from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from tests.runtime.test_personal_desktop_unattended_decision_qualification import (
    Harness as DecisionHarness,
)
from tests.runtime.test_personal_desktop_unattended_paper_decision_intent import (
    _session_read,
)

from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_startup_qualification as startup_module,
)
from trading_bot.runtime import (
    personal_desktop_unattended_settlement_qualification as d8a,
)
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    derive_checkpointed_verified_snapshot_application_id,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexState,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObservation,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    FinalizedUnattendedDecisionForSessionResult,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation import (
    create_personal_desktop_unattended_paper_invocation,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageClassification as Storage,
)
from trading_bot.runtime.verified_c3_daily_bar_open import (
    build_c3_verified_daily_bar_open_binding,
)

Diagnostic = startup_module.PersonalDesktopUnattendedPaperStartupDiagnostic
StartupResult = startup_module.PersonalDesktopUnattendedPaperStartupQualificationResult
Startup = startup_module.PersonalDesktopUnattendedPaperStartupStatus


@pytest.fixture(autouse=True)
def prohibit_native_and_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("D8-A reached native production or a prohibited effect")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    from trading_bot.runtime import (
        personal_desktop_paper_receipt_recovery_execution,
        personal_desktop_unattended_decision_publication,
        personal_desktop_unattended_market_data_capture,
        personal_desktop_unattended_paper_operation_execution,
        personal_desktop_unattended_paper_storage_provisioning,
    )

    for module, name in (
        (
            personal_desktop_unattended_market_data_capture,
            "run_personal_desktop_unattended_market_data_capture",
        ),
        (
            personal_desktop_unattended_decision_publication,
            "run_personal_desktop_unattended_decision_publication",
        ),
        (
            personal_desktop_unattended_paper_operation_execution,
            "execute_personal_desktop_unattended_paper_operation",
        ),
        (
            personal_desktop_paper_receipt_recovery_execution,
            "recover_personal_desktop_paper_receipt",
        ),
        (
            personal_desktop_unattended_paper_storage_provisioning,
            "provision_personal_desktop_unattended_storage",
        ),
    ):
        monkeypatch.setattr(module, name, forbidden)


class Harness(DecisionHarness):
    def __init__(self, monkeypatch):
        super().__init__(monkeypatch)
        from trading_bot.runtime import verified_c3_daily_bar_open as open_module

        monkeypatch.setattr(
            open_module, "require_validated_production_authority", lambda c1: c1
        )
        monkeypatch.setattr(
            open_module,
            "require_selected_c3_snapshot_matches_authority",
            lambda *args: None,
        )
        self.execution = _session_read(date(2026, 8, 25), 106)
        self.selections = {item.session: item for item in (*self.items, self.execution)}
        self.discovery_state = d8a.Discovery.FINALIZED
        self.discovery_binding = self.binding
        self.fail_proof = False
        self.startup_state = Startup.HEALTHY_NO_PENDING_INVOCATION
        self.startup_mutation = None
        self.recovery_terminal_checkpoint_id = UUID(int=12)
        self.events = []
        self.c1_reads = 0

    def acquire(self):
        self.c1_reads += 1
        self.events.append("c1")
        return self.authority

    def discover(self, c1, session):
        assert c1 is self.authority
        assert session == self.execution.session
        self.events.append("discovery")
        binding = (
            self.discovery_binding
            if self.discovery_state is d8a.Discovery.FINALIZED
            else None
        )
        return FinalizedUnattendedDecisionForSessionResult(
            self.discovery_state,
            session,
            binding.decision.decision_id if binding is not None else None,
            binding,
        )

    def require_discovery(self, c1, result):
        assert c1 is self.authority
        self.events.append("discovery-proof")
        if self.fail_proof:
            raise ValueError("no same-process current-C1 proof")
        return result.binding

    def selected(self, c1, session):
        assert c1 is self.authority
        self.events.append(f"selected:{session.session_date}")
        return self.selections[session]

    def selected_proof(self, c1, result):
        assert c1 is self.authority
        self.events.append("selected-proof")

    def startup(self, c1, original, plan, *, historical_cycle_configuration_payloads):
        assert c1 is self.authority
        assert original == self.current.selected
        assert historical_cycle_configuration_payloads[-1] == plan.artifact_bytes
        self.events.append("startup")
        decision = self.binding.decision
        application = derive_checkpointed_verified_snapshot_application_id(
            decision.predecessor_checkpoint_id, plan.checkpointed_request.request_id
        )
        if self.startup_state is Startup.BLOCKED:
            return StartupResult(
                Startup.BLOCKED,
                Diagnostic.QUALIFICATION_BLOCKED,
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
        if self.startup_state is Startup.RECEIPT_RECOVERY_REQUIRED:
            result = StartupResult(
                self.startup_state,
                Diagnostic.VERIFIED_TERMINAL_RECEIPT_MISSING,
                decision.paper_account_id,
                None,
                None,
                None,
                None,
                self.recovery_terminal_checkpoint_id,
                None,
                None,
                None,
                application,
                decision.predecessor_checkpoint_id,
                PaperAccountMutexState.OWNED,
            )
        else:
            invocation = create_personal_desktop_unattended_paper_invocation(
                plan, d8a.personal_desktop_unattended_decision_calendar()
            )
            diagnostic = {
                Startup.HEALTHY_NO_PENDING_INVOCATION: (
                    Diagnostic.VERIFIED_ABSENT_PENDING
                ),
                Startup.READY_SAME_INVOCATION: Diagnostic.VERIFIED_IDENTICAL_PENDING,
                Startup.ALREADY_APPLIED: Diagnostic.VERIFIED_ALREADY_APPLIED,
            }[self.startup_state]
            operation_classification = (
                PaperOperationClassification.ALREADY_APPLIED
                if self.startup_state is Startup.ALREADY_APPLIED
                else PaperOperationClassification.PENDING
            )
            operation_diagnostic = (
                PaperOperationInspectionCode.ALREADY_APPLIED
                if self.startup_state is Startup.ALREADY_APPLIED
                else PaperOperationInspectionCode.PENDING
            )
            result = StartupResult(
                self.startup_state,
                diagnostic,
                decision.paper_account_id,
                decision.current_c3.snapshot_id,
                invocation.invocation_id,
                UUID(int=11),
                application,
                decision.predecessor_checkpoint_id,
                Storage.ABSENT
                if self.startup_state is Startup.HEALTHY_NO_PENDING_INVOCATION
                else Storage.FINALIZED_IDENTICAL,
                operation_classification,
                operation_diagnostic,
                None,
                None,
                PaperAccountMutexState.OWNED,
            )
        return self.startup_mutation(result) if self.startup_mutation else result

    def dependencies(self):
        return d8a.DisposableSettlementQualificationDependencies(
            gate_state=lambda: tuple(self.gates),
            acquire_c1=self.acquire,
            validate_c1=lambda c1: c1,
            observe_token=self.observe_token,
            now=lambda: datetime(2026, 8, 26, 12, tzinfo=UTC),
            discover=self.discover,
            require_discovery=self.require_discovery,
            read_selected=self.selected,
            require_selected=self.selected_proof,
            build_open=build_c3_verified_daily_bar_open_binding,
            complete_plan=d8a.complete_manual_paper_strategy_plan,
            verify_plan=d8a.verify_manual_paper_strategy_plan,
            historical_configurations=lambda c1: (b"retained-configuration",),
            startup=self.startup,
        )

    def run(self, **overrides):
        result = d8a.qualify_personal_desktop_unattended_settlement_for_test(
            replace(self.dependencies(), **overrides)
        )
        assert result.real_effect_performed is False
        return result


@pytest.fixture
def harness(monkeypatch):
    return Harness(monkeypatch)


def test_zero_argument_production_and_safe_result_shape():
    assert (
        len(
            inspect.signature(
                d8a.qualify_personal_desktop_unattended_settlement
            ).parameters
        )
        == 0
    )
    names = {item.name for item in fields(d8a.SettlementQualificationResult)}
    assert not names & {
        "authority",
        "binding",
        "permit",
        "path",
        "handle",
        "credential",
    }
    with pytest.raises(ValueError):
        d8a.SettlementQualificationResult(
            d8a.Status.BLOCKED, real_effect_performed=True
        )


@pytest.mark.parametrize("gate", range(8))
def test_each_initially_open_gate_blocks_before_discovery(harness, gate):
    harness.gates[gate] = True
    assert harness.run().classification is d8a.Status.BLOCKED
    assert "discovery" not in harness.events


@pytest.mark.parametrize("bad", [1, 0, None, "False"])
def test_non_boolean_gate_blocks(harness, bad):
    harness.gates[3] = bad
    assert harness.run().classification is d8a.Status.BLOCKED


def test_none_discovery_is_only_no_pending_path(harness):
    harness.discovery_state = d8a.Discovery.NONE
    result = harness.run()
    assert result.classification is d8a.Status.NO_SETTLEMENT_PENDING
    assert result.completed_execution_session == harness.execution.session
    assert result.all_eight_gates_closed
    assert "selected-proof" not in harness.events
    assert "startup" not in harness.events
    assert harness.c1_reads == 2


def test_blocked_discovery_and_missing_provenance(harness):
    harness.discovery_state = d8a.Discovery.BLOCKED
    assert harness.run().classification is d8a.Status.BLOCKED
    harness.events.clear()
    harness.discovery_state = d8a.Discovery.FINALIZED
    harness.fail_proof = True
    assert harness.run().classification is d8a.Status.BLOCKED
    assert "startup" not in harness.events


@pytest.mark.parametrize(
    "startup,expected",
    [
        (Startup.HEALTHY_NO_PENDING_INVOCATION, d8a.Status.EXECUTION_READY),
        (Startup.READY_SAME_INVOCATION, d8a.Status.EXECUTION_READY),
        (Startup.ALREADY_APPLIED, d8a.Status.ALREADY_APPLIED),
        (Startup.RECEIPT_RECOVERY_REQUIRED, d8a.Status.RECEIPT_RECOVERY_REQUIRED),
        (Startup.BLOCKED, d8a.Status.BLOCKED),
    ],
)
def test_exact_startup_classification_mapping(harness, startup, expected):
    harness.startup_state = startup
    result = harness.run()
    assert result.classification is expected
    assert result.all_eight_gates_closed
    assert result.decision_id == harness.binding.decision.decision_id
    assert (
        result.execution_selected_snapshot_id
        == harness.execution.selected.audit.snapshot_id
    )
    assert harness.c1_reads == 2
    assert harness.events.count("selected-proof") == 7


def test_verified_open_is_constructed_only_from_execution_selection(harness):
    selected_inputs = []

    def open_from_execution(selected, c1):
        selected_inputs.append(selected)
        return build_c3_verified_daily_bar_open_binding(selected, c1)

    assert (
        harness.run(build_open=open_from_execution).classification
        is d8a.Status.EXECUTION_READY
    )
    assert selected_inputs == [harness.execution.selected]


def test_canonical_decision_replay_rejects_tampering(harness):
    object.__setattr__(harness.binding, "artifact_sha256", "0" * 64)
    assert harness.run().classification is d8a.Status.BLOCKED
    assert "startup" not in harness.events


@pytest.mark.parametrize("kind", ["original", "history", "execution"])
def test_selected_c3_substitution_blocks(harness, kind):
    if kind == "original":
        session = harness.current.session
    elif kind == "history":
        session = harness.items[0].session
    else:
        session = harness.execution.session
    if kind == "execution":
        harness.selections.pop(session)
    else:
        harness.selections[session] = _session_read(session.session_date, 500)
    assert harness.run().classification is d8a.Status.BLOCKED
    assert "startup" not in harness.events


@pytest.mark.parametrize(
    "field,value",
    [
        ("selection_id", UUID(int=901)),
        ("session_id", UUID(int=902)),
        ("terminal_id", UUID(int=903)),
        ("snapshot_id", UUID(int=904)),
        ("artifact_sha256", "0" * 64),
        ("artifact_byte_length", 999),
    ],
)
def test_original_selected_c3_audit_mismatch_blocks(harness, field, value):
    object.__setattr__(harness.current.selected.audit, field, value)
    assert harness.run().classification is d8a.Status.BLOCKED
    assert "startup" not in harness.events


def test_candidate_plan_replay_failure_blocks(harness):
    result = harness.run(verify_plan=lambda *args, **kwargs: object())
    assert result.classification is d8a.Status.BLOCKED
    assert "startup" not in harness.events


def test_genuine_c1_validation_is_required_before_discovery(harness):
    def invalid(_c1):
        raise ValueError("no genuine production C1")

    assert harness.run(validate_c1=invalid).classification is d8a.Status.BLOCKED
    assert "discovery" not in harness.events


def test_production_wiring_uses_reviewed_read_only_boundaries():
    dependencies = d8a._production_dependencies()
    assert dependencies.gate_state is d8a.personal_desktop_unattended_effect_gate_state
    assert dependencies.acquire_c1 is d8a.acquire_validated_production_authority
    assert dependencies.validate_c1 is d8a.require_validated_production_authority
    assert dependencies.build_open is d8a.build_c3_verified_daily_bar_open_binding
    assert dependencies.complete_plan is d8a.complete_manual_paper_strategy_plan
    assert (
        dependencies.startup
        is d8a.qualify_personal_desktop_unattended_paper_startup_from_verified_plan
    )


def test_production_discovery_wrapper_rejects_substituted_binding(harness, monkeypatch):
    monkeypatch.setattr(
        d8a,
        "require_finalized_unattended_decision_for_execution_session",
        lambda result, c1: object(),
    )
    discovery = harness.discover(harness.authority, harness.execution.session)
    with pytest.raises(ValueError):
        d8a._production_dependencies().require_discovery(harness.authority, discovery)


@pytest.mark.parametrize(
    "field",
    [
        "invocation_id",
        "application_id",
        "selected_snapshot_id",
        "terminal_checkpoint_id",
    ],
)
def test_startup_identifier_tampering_blocks(harness, field):
    harness.startup_mutation = lambda result: replace(result, **{field: UUID(int=999)})
    assert harness.run().classification is d8a.Status.BLOCKED


def test_exact_terminal_missing_receipt_uses_distinct_successor(harness):
    harness.startup_state = Startup.RECEIPT_RECOVERY_REQUIRED
    predecessor = harness.binding.decision.predecessor_checkpoint_id
    successor = harness.recovery_terminal_checkpoint_id
    assert predecessor != successor

    result = harness.run()

    assert result.classification is d8a.Status.RECEIPT_RECOVERY_REQUIRED
    assert result.account_predecessor_checkpoint_id == predecessor
    assert result.terminal_checkpoint_id == successor
    assert result.real_effect_performed is False


def test_recovery_must_be_for_the_exact_predecessor(harness):
    harness.startup_state = Startup.RECEIPT_RECOVERY_REQUIRED
    harness.startup_mutation = lambda result: replace(
        result, recovery_predecessor_checkpoint_id=UUID(int=999)
    )
    assert harness.run().classification is d8a.Status.BLOCKED


def test_recovery_must_be_for_the_exact_application(harness):
    harness.startup_state = Startup.RECEIPT_RECOVERY_REQUIRED
    harness.startup_mutation = lambda result: replace(
        result, recovery_missing_application_id=UUID(int=999)
    )
    assert harness.run().classification is d8a.Status.BLOCKED


def test_final_gate_c1_and_token_drift_block(harness):
    result = harness.run(
        gate_state=lambda: (
            tuple([False] * 8) if harness.c1_reads < 2 else tuple([True] + [False] * 7)
        )
    )
    assert result.classification is d8a.Status.BLOCKED
    assert harness.c1_reads == 2
    harness.c1_reads = 0
    assert harness.run(acquire_c1=lambda: object()).classification is d8a.Status.BLOCKED
    original = harness.observe_token
    reads = 0

    def drift_token():
        nonlocal reads
        reads += 1
        if reads == 1:
            return original()
        return TradingTokenObservation("S-1-5-18", 1, False, False, ())

    assert harness.run(observe_token=drift_token).classification is d8a.Status.BLOCKED


def test_genuine_trading_token_required(harness):
    original = harness.token
    for bad in (
        replace(original, elevated=True),
        replace(original, groups=(("S-1-5-32-544", 4),)),
        replace(original, thread_token_present=True),
        replace(original, user_sid="S-1-5-18"),
        replace(original, token_type=2),
    ):
        assert (
            harness.run(observe_token=lambda bad=bad: bad).classification
            is d8a.Status.BLOCKED
        )


def test_source_contains_no_effect_entry_or_gate_assignment():
    source = inspect.getsource(d8a)
    tree = ast.parse(source)
    forbidden = {
        "execute_personal_desktop_unattended_paper_operation",
        "run_personal_desktop_unattended_market_data_capture",
        "run_personal_desktop_unattended_capture_warmup",
        "run_personal_desktop_unattended_decision_publication",
        "issue_pre_open_decision_publication_permit",
        "open_personal_desktop_unattended_decision_output_capability",
        "recover_personal_desktop_paper_receipt",
        "provision_personal_desktop_unattended_storage",
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names & forbidden
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not called & forbidden
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assert not any(
                "EFFECTS_ENABLED" in ast.unparse(target) for target in targets
            )
