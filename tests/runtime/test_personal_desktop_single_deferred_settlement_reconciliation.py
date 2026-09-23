"""D9-R1 independent deferred settlement reconciliation tests."""

from __future__ import annotations

import ast
import inspect
from dataclasses import fields, replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.runtime import (
    test_personal_desktop_unattended_settlement_reconciliation as base,
)
from tests.runtime.test_paper_operation import CONFIGURATION, _completed
from tests.runtime.test_personal_desktop_unattended_settlement_reconciliation import (
    prohibit_native_and_effects as prohibit_native_and_effects,
)
from tests.runtime.test_verified_snapshot_preparation import calendar

from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification as Operation,
)
from trading_bot.runtime import (
    personal_desktop_single_deferred_settlement_reconciliation as d9r,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_qualification import (
    PaperReceiptRecoveryQualificationStatus as Recovery,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    completed_xnys_session_at,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    SingleDeferredDecisionClassification as Discovery,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    SingleDeferredDecisionResult,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageClassification as Storage,
)
from trading_bot.runtime.windows_authority import AuthorityPrincipalError


class Harness(base.Harness):
    def __init__(self, monkeypatch):
        self.deferred_ready = False
        super().__init__(monkeypatch)
        self.deferred_ready = True
        self.deferred_state = Discovery.FINALIZED
        self.expected = d9r._reconstruct(self.dependencies())
        self.gate_reads = 0
        self.token_reads = 0
        self.c1_reads = 0
        self.events.clear()

    def deferred_discover(self, c1):
        assert c1 is self.authority
        self.events.append("deferred-discovery")
        completed = completed_xnys_session_at(datetime(2026, 8, 27, 12, tzinfo=UTC))
        binding = (
            self.discovery_binding
            if self.deferred_state is Discovery.FINALIZED
            else None
        )
        return SingleDeferredDecisionResult(
            self.deferred_state,
            completed if self.deferred_state is not Discovery.BLOCKED else None,
            self.execution.session if binding is not None else None,
            binding.decision.decision_id if binding is not None else None,
            binding,
        )

    def dependencies(self):
        old = super().dependencies()
        values = {field.name: getattr(old, field.name) for field in fields(old)}
        if self.deferred_ready:
            values.update(
                now=lambda: datetime(2026, 8, 27, 12, tzinfo=UTC),
                discover=self.deferred_discover,
            )
        return d9r.DisposableDeferredSettlementReconciliationDependencies(**values)

    def run(self, monkeypatch):
        monkeypatch.setattr(d9r, "_reconstruct", lambda d: self.expected)
        return d9r.reconcile_personal_desktop_single_deferred_settlement_for_test(
            self.dependencies()
        )


@pytest.fixture
def harness(monkeypatch):
    return Harness(monkeypatch)


def test_zero_semantic_arguments_and_bounded_result():
    assert not inspect.signature(
        d9r.reconcile_personal_desktop_single_deferred_settlement
    ).parameters
    names = {field.name for field in fields(d9r.DeferredSettlementReconciliationResult)}
    assert {"current_completed_session", "deferred_execution_session"} <= names
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
        d9r.DeferredSettlementReconciliationResult(
            d9r.Status.BLOCKED, real_effect_performed=True
        )


@pytest.mark.parametrize("gate", range(8))
@pytest.mark.parametrize("value", [True, 0, None, "False"])
def test_initial_gate_blocks_before_durable_discovery(harness, gate, value):
    harness.gates[gate] = value
    with pytest.raises(ValueError):
        d9r._reconstruct(harness.dependencies())
    assert "deferred-discovery" not in harness.events


def test_genuine_token_and_c1_before_discovery(harness):
    bad = replace(harness.observe_token(), elevated=True)
    with pytest.raises(AuthorityPrincipalError):
        d9r._reconstruct(replace(harness.dependencies(), observe_token=lambda: bad))
    with pytest.raises(ValueError):
        d9r._reconstruct(
            replace(
                harness.dependencies(),
                validate_c1=lambda c1: (_ for _ in ()).throw(ValueError("invalid C1")),
            )
        )
    assert "deferred-discovery" not in harness.events


@pytest.mark.parametrize("state", [Discovery.NONE, Discovery.BLOCKED])
def test_none_and_blocked_discovery_cannot_reconcile(harness, state):
    harness.deferred_state = state
    with pytest.raises(ValueError):
        d9r._reconstruct(harness.dependencies())


def test_copied_and_wrong_c1_discovery_fail(harness):
    with pytest.raises(ValueError):
        d9r._reconstruct(
            replace(
                harness.dependencies(),
                discover=lambda c1: replace(harness.deferred_discover(c1)),
                require_discovery=lambda c1, result: (_ for _ in ()).throw(
                    ValueError("unregistered")
                ),
            )
        )
    with pytest.raises(ValueError):
        d9r._reconstruct(
            replace(
                harness.dependencies(),
                require_discovery=lambda c1, result: (_ for _ in ()).throw(
                    ValueError("wrong C1")
                ),
            )
        )


def test_candidate_must_be_prior_to_current_completed(harness):
    original = harness.deferred_discover

    def wrong_current(c1):
        result = original(c1)
        object.__setattr__(
            result, "current_completed_session", result.execution_session
        )
        return result

    with pytest.raises(ValueError):
        d9r._reconstruct(replace(harness.dependencies(), discover=wrong_current))


def test_exact_deferred_decision_c3_open_plan_and_invocation(harness):
    expected = d9r._reconstruct(harness.dependencies())
    assert expected.completed > expected.deferred
    assert expected.deferred == harness.execution.session
    assert expected.execution.session == harness.execution.session
    assert expected.invocation.invocation.execution_session == expected.deferred
    assert (
        expected.plan.plan.request_core.open_references[0].session == expected.deferred
    )
    assert expected.configurations == (b"retained-configuration",)
    assert "deferred-discovery" in harness.events


def test_forged_decision_and_missing_c3_block(harness):
    forged = replace(harness.binding)
    object.__setattr__(forged, "artifact_bytes", b"forged")
    harness.discovery_binding = forged
    with pytest.raises(ValueError):
        d9r._reconstruct(harness.dependencies())
    harness.discovery_binding = harness.binding
    for session in (
        harness.execution.session,
        harness.binding.decision.selected_session,
    ):
        removed = harness.selections.pop(session)
        with pytest.raises((ValueError, KeyError)):
            d9r._reconstruct(harness.dependencies())
        harness.selections[session] = removed


def test_history_open_plan_and_historical_configuration_block(harness):
    for key, fn in (
        ("build_open", lambda *args: object()),
        ("complete_plan", lambda *args: object()),
        ("verify_plan", lambda *args, **kwargs: object()),
    ):
        with pytest.raises((ValueError, TypeError)):
            d9r._reconstruct(replace(harness.dependencies(), **{key: fn}))
    assert (
        d9r._production_dependencies().historical_configurations
        is d9r.resolve_personal_desktop_historical_cycle_configurations
    )
    first = harness.binding.decision.history_c3[0].selected_session
    saved = harness.selections.pop(first)
    with pytest.raises((ValueError, KeyError)):
        d9r._reconstruct(harness.dependencies())
    harness.selections[first] = saved


def test_pending_is_read_only_diagnostic(harness, monkeypatch):
    harness.storage = Storage.ABSENT
    result = harness.run(monkeypatch)
    assert result.classification is d9r.Status.NOT_APPLIED
    assert result.current_completed_session > result.deferred_execution_session
    assert result.real_effect_performed is False
    assert harness.storage_reads == 2
    assert harness.inspection_reads == 2
    assert harness.events.count("mutex-enter") == 1


def test_exact_terminal_missing_receipt_is_diagnostic(harness, monkeypatch):
    harness.account = harness._account(harness.successor)
    harness.recovery = Recovery.RECEIPT_RECOVERY_REQUIRED
    harness.operation = Operation.BLOCKED
    result = harness.run(monkeypatch)
    assert result.classification is d9r.Status.RECEIPT_RECOVERY_REQUIRED
    assert result.real_effect_performed is False


@pytest.mark.parametrize(
    "storage", [Storage.STAGING_PRESENT, Storage.CONFLICTING, Storage.BLOCKED]
)
def test_invocation_conflict_blocks(harness, monkeypatch, storage):
    harness.storage = storage
    assert harness.run(monkeypatch).classification is d9r.Status.BLOCKED


@pytest.mark.parametrize("operation", [Operation.BLOCKED, Operation.CONFLICTING])
def test_operation_conflict_blocks(harness, monkeypatch, operation):
    harness.operation = operation
    assert harness.run(monkeypatch).classification is d9r.Status.BLOCKED


def test_applied_requires_exact_receipt_successor_and_tip(harness, monkeypatch):
    harness.account = harness._account(harness.successor)
    harness.operation = Operation.ALREADY_APPLIED
    assert harness.run(monkeypatch).classification is d9r.Status.BLOCKED
    monkeypatch.setattr(
        d9r,
        "_completed_receipt",
        lambda account, material: (
            d9r.PaperOperationStatus.COMPLETED,
            harness.successor,
        ),
    )
    assert harness.run(monkeypatch).classification is d9r.Status.RECONCILED
    harness.storage = Storage.ABSENT
    assert harness.run(monkeypatch).classification is d9r.Status.BLOCKED


def test_repeated_unchanged_is_deterministic(harness, monkeypatch):
    first = harness.run(monkeypatch)
    second = harness.run(monkeypatch)
    assert first == second
    assert first.real_effect_performed is False


def test_final_drift_blocks(harness, monkeypatch):
    harness.gate_drift_on = 3
    assert harness.run(monkeypatch).classification is d9r.Status.BLOCKED
    harness.gate_drift_on = None
    harness.gate_reads = 0
    harness.token_drift = True
    harness.token_reads = 0
    assert harness.run(monkeypatch).classification is d9r.Status.BLOCKED
    harness.token_drift = False
    harness.storage_reads = 0
    harness.storage = Storage.FINALIZED_IDENTICAL
    harness.storage_drift = True
    assert harness.run(monkeypatch).classification is d9r.Status.BLOCKED
    harness.storage_drift = False
    harness.inspection_reads = 0
    harness.operation_drift = True
    assert harness.run(monkeypatch).classification is d9r.Status.BLOCKED


def test_no_effectful_path_or_gate_assignment():
    source = Path(d9r.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for forbidden in (
        "personal_desktop_single_deferred_settlement_execution",
        "execute_personal_desktop_unattended_paper_operation",
        "recover_personal_desktop_paper_receipt",
    ):
        assert forbidden not in source
    assert not any(
        isinstance(node, (ast.Assign, ast.AnnAssign))
        and "EFFECTS_ENABLED" in ast.unparse(node)
        for node in ast.walk(tree)
    )


def test_exact_completed_receipt_reverifies_and_checks_successor():
    receipt, genesis, snapshot, report, successor = _completed()
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
    status, terminal = d9r._completed_receipt(account, material)
    assert status is d9r.PaperOperationStatus.COMPLETED
    assert terminal == account.prior_checkpoint.checkpoint_id
    account.prior_checkpoint.checkpoint_id = (
        receipt.prior_lineage_evidence.terminal_checkpoint_id
    )
    with pytest.raises(ValueError):
        d9r._completed_receipt(account, material)
    account.prior_checkpoint.checkpoint_id = terminal
    account.successors = (SimpleNamespace(payload=b"wrong successor"),)
    with pytest.raises((ValueError, TypeError)):
        d9r._completed_receipt(account, material)


def test_alternate_invocation_for_deferred_session_blocks(harness, monkeypatch):
    harness.alternate_invocation = True
    dependencies = harness.dependencies()
    original = dependencies.require_storage

    def alternate(result):
        proof = original(result)
        return SimpleNamespace(
            authority=proof.authority,
            expected=proof.expected,
            classification=proof.classification,
            finalized=(
                harness.expected.invocation,
                SimpleNamespace(
                    invocation=SimpleNamespace(
                        execution_session=harness.expected.deferred
                    )
                ),
            ),
        )

    monkeypatch.setattr(d9r, "_reconstruct", lambda d: harness.expected)
    result = d9r.reconcile_personal_desktop_single_deferred_settlement_for_test(
        replace(dependencies, require_storage=alternate)
    )
    assert result.classification is d9r.Status.BLOCKED


def test_final_c1_and_account_tip_drift_block(harness, monkeypatch):
    monkeypatch.setattr(d9r, "_reconstruct", lambda d: harness.expected)
    bad_c1 = replace(harness.dependencies(), acquire_c1=lambda: object())
    assert (
        d9r.reconcile_personal_desktop_single_deferred_settlement_for_test(
            bad_c1
        ).classification
        is d9r.Status.BLOCKED
    )
    harness.final_account_drift = True
    assert harness.run(monkeypatch).classification is d9r.Status.BLOCKED
