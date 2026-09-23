"""Architecture-121 D8-R1 read-only deferred qualification regression matrix."""

from __future__ import annotations

import ast
import inspect
from dataclasses import fields, replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from tests.runtime.test_personal_desktop_unattended_settlement_qualification import (
    Harness as CurrentHarness,
)
from tests.runtime.test_personal_desktop_unattended_settlement_qualification import (
    prohibit_native_and_effects as prohibit_native_and_effects,
)

from trading_bot.runtime import (
    personal_desktop_single_deferred_settlement_qualification as d8r,
)
from trading_bot.runtime import (
    personal_desktop_unattended_settlement_qualification as d8a,
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


class Harness(CurrentHarness):
    def __init__(self, monkeypatch):
        super().__init__(monkeypatch)
        self.discovery_state = Discovery.FINALIZED
        self.deferred_proof_failure = False

    def discover(self, c1):
        assert c1 is self.authority
        self.events.append("deferred-discovery")
        completed = completed_xnys_session_at(datetime(2026, 8, 27, 12, tzinfo=UTC))
        binding = (
            self.discovery_binding
            if self.discovery_state is Discovery.FINALIZED
            else None
        )
        return SingleDeferredDecisionResult(
            self.discovery_state,
            completed if self.discovery_state is not Discovery.BLOCKED else None,
            self.execution.session if binding is not None else None,
            binding.decision.decision_id if binding is not None else None,
            binding,
        )

    def require_discovery(self, c1, result):
        assert c1 is self.authority
        self.events.append("deferred-proof")
        if self.deferred_proof_failure:
            raise ValueError("current-C1 proof unavailable")
        return result.binding

    def dependencies(self):
        original = d8a.DisposableSettlementQualificationDependencies(
            gate_state=lambda: tuple(self.gates),
            acquire_c1=self.acquire,
            validate_c1=lambda c1: c1,
            observe_token=self.observe_token,
            now=lambda: datetime(2026, 8, 27, 12, tzinfo=UTC),
            discover=self.discover,
            require_discovery=self.require_discovery,
            read_selected=self.selected,
            require_selected=self.selected_proof,
            build_open=d8r.build_c3_verified_daily_bar_open_binding,
            complete_plan=d8r.complete_manual_paper_strategy_plan,
            verify_plan=d8r.verify_manual_paper_strategy_plan,
            historical_configurations=lambda c1: (b"retained-configuration",),
            startup=self.startup,
        )
        return d8r.DisposableDeferredSettlementQualificationDependencies(
            **{field.name: getattr(original, field.name) for field in fields(original)}
        )

    def run(self, **overrides):
        result = d8r.qualify_personal_desktop_single_deferred_settlement_for_test(
            replace(self.dependencies(), **overrides)
        )
        assert result.real_effect_performed is False
        return result


@pytest.fixture
def harness(monkeypatch):
    return Harness(monkeypatch)


def test_zero_semantic_argument_and_bounded_result_shape():
    assert not inspect.signature(
        d8r.qualify_personal_desktop_single_deferred_settlement
    ).parameters
    assert not {"authority", "binding", "permit", "path", "handle", "credential"} & {
        field.name for field in fields(d8r.DeferredSettlementQualificationResult)
    }
    tree = ast.parse(inspect.getsource(d8r))
    assert not any(
        isinstance(node, ast.Attribute)
        and node.attr
        in {
            "execute_personal_desktop_unattended_paper_operation",
            "recover_personal_desktop_paper_receipt",
            "run_personal_desktop_unattended_decision_publication",
            "provision_personal_desktop_unattended_storage",
        }
        for node in ast.walk(tree)
    )


def test_exact_deferred_evidence_and_installed_only_configuration(harness):
    result = harness.run()
    assert result.classification is d8r.Status.EXECUTION_READY
    assert result.current_completed_session > result.deferred_execution_session
    assert result.deferred_execution_session == harness.execution.session
    assert result.decision_selected_session == harness.binding.decision.selected_session
    assert result.decision_id == harness.binding.decision.decision_id
    assert (
        result.execution_selected_snapshot_id
        == harness.execution.selected.audit.snapshot_id
    )
    assert result.final_plan_id is not None
    assert "startup" in harness.events
    assert harness.c1_reads == 2
    assert harness.token_reads >= 2
    assert result.all_eight_gates_closed is True


@pytest.mark.parametrize(
    "state,expected",
    [
        (Discovery.NONE, d8r.Status.NO_DEFERRED_SETTLEMENT),
        (Discovery.BLOCKED, d8r.Status.BLOCKED),
    ],
)
def test_candidate_state_mapping(harness, state, expected):
    harness.discovery_state = state
    result = harness.run()
    assert result.classification is expected
    assert "startup" not in harness.events


def test_current_c1_proof_and_token_drift_block(harness):
    harness.deferred_proof_failure = True
    assert harness.run().classification is d8r.Status.BLOCKED
    harness.deferred_proof_failure = False
    original = harness.observe_token
    calls = 0

    def drift():
        nonlocal calls
        calls += 1
        return (
            replace(original(), groups=(("S-1-1-0", 0),)) if calls > 1 else original()
        )

    assert harness.run(observe_token=drift).classification is d8r.Status.BLOCKED


@pytest.mark.parametrize(
    "mutate",
    [
        lambda h: h.selections.pop(h.execution.session),
        lambda h: h.selections.pop(h.binding.decision.selected_session),
        lambda h: h.selections.__setitem__(h.execution.session, h.current),
    ],
)
def test_selected_c3_s_and_e_exactness(harness, mutate):
    mutate(harness)
    assert harness.run().classification is d8r.Status.BLOCKED


def test_persisted_decision_canonical_replay_block(harness):
    forged = replace(harness.binding)
    object.__setattr__(forged, "artifact_bytes", b"tampered")
    harness.discovery_binding = forged
    assert harness.run().classification is d8r.Status.BLOCKED


def test_verified_open_and_final_plan_replay_block(harness):
    assert (
        harness.run(build_open=lambda *args: object()).classification
        is d8r.Status.BLOCKED
    )
    assert (
        harness.run(verify_plan=lambda *args, **kwargs: object()).classification
        is d8r.Status.BLOCKED
    )
    assert (
        harness.run(complete_plan=lambda *args: object()).classification
        is d8r.Status.BLOCKED
    )


def test_historical_configuration_is_installed_only(harness):
    result = harness.run(
        historical_configurations=lambda c1: (harness.binding.artifact_bytes,)
    )
    assert result.classification is d8r.Status.BLOCKED


@pytest.mark.parametrize(
    "state,expected",
    [
        (
            d8r.PersonalDesktopUnattendedPaperStartupStatus.HEALTHY_NO_PENDING_INVOCATION,
            d8r.Status.EXECUTION_READY,
        ),
        (
            d8r.PersonalDesktopUnattendedPaperStartupStatus.READY_SAME_INVOCATION,
            d8r.Status.EXECUTION_READY,
        ),
        (
            d8r.PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED,
            d8r.Status.ALREADY_APPLIED,
        ),
        (
            d8r.PersonalDesktopUnattendedPaperStartupStatus.RECEIPT_RECOVERY_REQUIRED,
            d8r.Status.RECEIPT_RECOVERY_REQUIRED,
        ),
        (d8r.PersonalDesktopUnattendedPaperStartupStatus.BLOCKED, d8r.Status.BLOCKED),
    ],
)
def test_predecessor_startup_mapping(harness, state, expected):
    harness.startup_state = state
    assert harness.run().classification is expected


@pytest.mark.parametrize("index", range(8))
def test_each_open_or_non_boolean_gate_blocks_before_native(harness, index):
    for value in (True, 0, None):
        harness.gates = [False] * 8
        harness.gates[index] = value
        assert harness.run().classification is d8r.Status.BLOCKED
        assert "deferred-discovery" not in harness.events


@pytest.mark.parametrize(
    "field",
    [
        "invocation_id",
        "application_id",
        "selected_snapshot_id",
        "terminal_checkpoint_id",
    ],
)
def test_exact_predecessor_and_startup_identities(harness, field):
    harness.startup_mutation = lambda result: replace(result, **{field: UUID(int=999)})
    assert harness.run().classification is d8r.Status.BLOCKED


def test_recovery_requires_exact_predecessor_and_application(harness):
    harness.startup_state = (
        d8r.PersonalDesktopUnattendedPaperStartupStatus.RECEIPT_RECOVERY_REQUIRED
    )
    for field in (
        "recovery_predecessor_checkpoint_id",
        "recovery_missing_application_id",
    ):
        harness.startup_mutation = lambda result, field=field: replace(
            result, **{field: UUID(int=999)}
        )
        assert harness.run().classification is d8r.Status.BLOCKED


def test_final_gate_and_c1_drift_block(harness):
    result = harness.run(
        gate_state=lambda: (
            tuple([False] * 8) if harness.c1_reads < 2 else tuple([True] + [False] * 7)
        )
    )
    assert result.classification is d8r.Status.BLOCKED
    harness.c1_reads = 0
    assert harness.run(acquire_c1=lambda: object()).classification is d8r.Status.BLOCKED
