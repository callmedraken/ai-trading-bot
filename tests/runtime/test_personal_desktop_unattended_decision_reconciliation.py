"""D7-D independent finalized-decision reconciliation and containment matrix."""

from __future__ import annotations

import ast
import copy
import ctypes
import inspect
from dataclasses import fields, replace
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.runtime import personal_desktop_unattended_daily_cycle as daily
from trading_bot.runtime import (
    personal_desktop_unattended_decision_reconciliation as d7d,
)

from .test_personal_desktop_unattended_decision_publication import _storage
from .test_personal_desktop_unattended_decision_qualification import (
    Harness as D7AHarness,
)

Status = d7d.Status


@pytest.fixture(autouse=True)
def prohibit_production_and_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("D7-D reached native production or a prohibited effect boundary")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    from trading_bot.runtime import personal_desktop_paper_account_recovery as recovery
    from trading_bot.runtime import (
        personal_desktop_paper_receipt_recovery_execution as receipt,
    )
    from trading_bot.runtime import personal_desktop_paper_runtime_output as output
    from trading_bot.runtime import (
        personal_desktop_unattended_decision_publication as d6,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_market_data_capture as g5,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_decision_publication as publication,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_operation_execution as execution,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_storage_provisioning as admin,
    )

    for module, name in (
        (d6, "run_personal_desktop_unattended_decision_publication"),
        (publication, "issue_pre_open_decision_publication_permit"),
        (output, "open_personal_desktop_unattended_decision_output_capability"),
        (admin, "qualify_personal_desktop_unattended_storage_provisioning"),
        (admin, "provision_personal_desktop_unattended_storage"),
        (g5, "run_personal_desktop_unattended_market_data_capture"),
        (g5, "reconcile_personal_desktop_unattended_market_data_capture"),
        (execution, "execute_personal_desktop_unattended_paper_operation"),
        (recovery, "finalize_personal_desktop_paper_staging_recovery"),
        (receipt, "recover_personal_desktop_paper_receipt"),
        (daily, "run_personal_desktop_unattended_daily_cycle"),
    ):
        monkeypatch.setattr(module, name, forbidden)


class Harness(D7AHarness):
    def __init__(self, monkeypatch):
        super().__init__(monkeypatch)
        self.storage_state = d7d.Storage.FINALIZED_IDENTICAL
        self.discovery_state = d7d.Discovery.FINALIZED
        self.discovered_binding = self.binding
        self.discovery_reads = []
        self.discovery_proof_failure = False

    def discover_finalized(self, c1, execution):
        assert self.held and c1 is self.authority
        assert execution == self.binding.decision.intended_execution_session
        assert self.gates == [False] * 8
        self.events.append("discovery")
        binding = (
            self.discovered_binding
            if self.discovery_state is d7d.Discovery.FINALIZED
            else None
        )
        result = d7d.FinalizedUnattendedDecisionForSessionResult(
            self.discovery_state,
            execution,
            None if binding is None else binding.decision.decision_id,
            binding,
        )
        self.discovery_reads.append(result)
        return result

    def require_discovery(self, c1, result):
        assert self.held and c1 is self.authority
        assert result in self.discovery_reads
        self.events.append("discovery-proof")
        if self.discovery_proof_failure:
            raise ValueError("discovery lacks same-process current-C1 provenance")
        return result.binding

    def dependencies(self):
        return d7d.DisposableUnattendedDecisionReconciliationDependencies(
            gate_state=lambda: tuple(self.gates),
            acquire_c1=lambda: self.authority,
            validate_c1=self.validate,
            observe_token=self.observe_token,
            now=self.now,
            historical_configurations=lambda c1: (b"retained-configuration",),
            read_account=self.read_account,
            require_account=lambda account: account,
            admission=self.admission,
            read_selected=self.read_selected,
            require_selected=self.require_selected,
            inspect_history=self.inspect_history,
            build_history=self.bind_history,
            build_decision=self.build_decision,
            qualify_namespace=self.qualify_namespace,
            discover_finalized=self.discover_finalized,
            require_discovery=self.require_discovery,
            read_storage=self.read_storage,
            require_storage=self.require_storage,
        )

    def run(self, **overrides):
        result = d7d.reconcile_personal_desktop_unattended_decision_for_test(
            replace(self.dependencies(), **overrides)
        )
        assert result.real_effect_performed is False
        assert not self.held
        assert not set(self.events) & {
            "permit",
            "writer",
            "publish",
            "gate:True",
            "gate:False",
        }
        return result


@pytest.fixture
def harness(monkeypatch):
    return Harness(monkeypatch)


def test_exact_finalized_decision_reconciles_under_mutex(harness):
    result = harness.run()
    assert result.classification is Status.RECONCILED
    assert result.expected_decision_id == harness.binding.decision.decision_id
    assert result.finalized_decision_id == result.expected_decision_id
    assert result.session_discovery_classification is d7d.Discovery.FINALIZED
    assert result.storage_classification is d7d.Storage.FINALIZED_IDENTICAL
    assert result.namespace_classification is d7d.Namespace.PRESENT_VALID
    assert result.selected_history_count == result.required_history_count == 6
    assert result.all_eight_gates_closed
    assert harness.account_reads == 3
    assert harness.token_reads == 3
    assert harness.namespace_reads == 2
    assert (
        harness.events.index("account:1")
        < harness.events.index("lock")
        < harness.events.index("account:2")
        < harness.events.index("discovery")
        < harness.events.index("storage")
        < harness.events.index("account:3")
        < harness.events.index("release")
    )


@pytest.mark.parametrize("index", range(8))
@pytest.mark.parametrize("value", [True, 1, 0, None, "false"])
def test_each_initial_gate_blocks_before_reads(harness, index, value):
    harness.gates[index] = value
    assert harness.run().classification is Status.BLOCKED
    assert harness.account_reads == 0 and not harness.discovery_reads


@pytest.mark.parametrize("index", range(8))
@pytest.mark.parametrize("value", [True, 0])
def test_each_gate_drift_blocks_final_acceptance(harness, index, value):
    original = harness.qualify_namespace

    def namespace():
        result = original()
        if harness.namespace_reads == 2:
            harness.gates[index] = value
        return result

    assert harness.run(qualify_namespace=namespace).classification is Status.BLOCKED


@pytest.mark.parametrize(
    "classification,indices,expected",
    [
        (d7d.Window.WARMING_UP, (4, 5), Status.WARMING_UP),
        (d7d.Window.SESSION_GAP, (0, 5), Status.SESSION_GAP),
    ],
)
def test_unready_history_is_diagnostic_without_storage(
    harness, classification, indices, expected
):
    harness.window = replace(
        harness.window,
        classification=classification,
        selected=tuple(harness.items[index] for index in indices),
    )
    result = harness.run()
    assert result.classification is expected
    assert not harness.discovery_reads and not harness.storage_reads


@pytest.mark.parametrize(
    "classification", [d7d.Namespace.MISSING, d7d.Namespace.BLOCKED]
)
def test_namespace_must_be_present_valid(harness, classification):
    harness.namespace = classification
    result = harness.run()
    assert result.classification is Status.BLOCKED
    assert result.namespace_classification is classification
    assert not harness.discovery_reads


@pytest.mark.parametrize(
    "classification,expected",
    [
        (d7d.Discovery.NONE, Status.NOT_FINALIZED),
        (d7d.Discovery.BLOCKED, Status.BLOCKED),
    ],
)
def test_session_discovery_must_be_exact_finalized(harness, classification, expected):
    harness.discovery_state = classification
    result = harness.run()
    assert result.classification is expected
    assert not harness.storage_reads


def test_session_discovery_requires_same_process_current_c1_provenance(harness):
    harness.discovery_proof_failure = True
    assert harness.run().classification is Status.BLOCKED
    assert not harness.storage_reads


def test_selected_c3_requires_current_c1_provenance(harness):
    harness.proof_failure = "selected"
    assert harness.run().classification is Status.BLOCKED
    assert not harness.discovery_reads


@pytest.mark.parametrize(
    "classification",
    [
        d7d.Storage.ABSENT,
        d7d.Storage.STAGING_PRESENT,
        d7d.Storage.CONFLICTING,
        d7d.Storage.BLOCKED,
    ],
)
def test_only_finalized_identical_storage_reconciles(harness, classification):
    harness.storage_state = classification
    assert harness.run().classification is Status.BLOCKED


def test_storage_requires_same_process_current_c1_provenance(harness):
    harness.proof_failure = "storage"
    assert harness.run().classification is Status.BLOCKED


def test_discovered_binding_must_equal_independent_candidate(harness):
    different = copy.deepcopy(harness.binding)
    object.__setattr__(different.decision, "decision_id", UUID(int=1))
    harness.discovered_binding = different
    assert harness.run().classification is Status.BLOCKED
    assert not harness.storage_reads


@pytest.mark.parametrize(
    "field", ["artifact_bytes", "artifact_sha256", "artifact_byte_length"]
)
def test_exact_finalized_canonical_artifact_is_required(harness, field):
    changes = {
        "artifact_bytes": harness.binding.artifact_bytes + b" ",
        "artifact_sha256": "0" * 64,
        "artifact_byte_length": harness.binding.artifact_byte_length + 1,
    }
    harness.discovered_binding = copy.deepcopy(harness.binding)
    object.__setattr__(harness.discovered_binding, field, changes[field])
    assert harness.run().classification is Status.BLOCKED
    assert not harness.storage_reads


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_deadline_state_never_invalidates_exact_finalized_reconciliation(
    harness, offset
):
    harness.observed = d7d.xnys_regular_open(
        harness.binding.decision.intended_execution_session
    ) + timedelta(microseconds=offset)
    result = harness.run()
    assert result.classification is Status.RECONCILED
    assert result.observed_before_open is (offset < 0)


@pytest.mark.parametrize("read", [1, 2, 3])
def test_account_identity_mismatch_blocks(harness, read):
    original = harness.read_account

    def changed(c1, historical):
        account = original(c1, historical)
        if harness.account_reads == read:
            return SimpleNamespace(
                anchor=SimpleNamespace(paper_account_id="different"),
                prior_checkpoint=account.prior_checkpoint,
            )
        return account

    assert harness.run(read_account=changed).classification is Status.BLOCKED


@pytest.mark.parametrize("read", [2, 3])
def test_predecessor_drift_blocks_under_mutex(harness, read):
    harness.drift_at = read
    assert harness.run().classification is Status.BLOCKED


def test_prelock_to_postlock_predecessor_drift_blocks(harness):
    original = harness.read_account

    def changed(c1, historical):
        account = original(c1, historical)
        if harness.account_reads == 1:
            return SimpleNamespace(
                anchor=account.anchor,
                prior_checkpoint=SimpleNamespace(checkpoint_id=UUID(int=1)),
            )
        return account

    def admission(prelock):
        return harness.admission(harness.account)

    assert (
        harness.run(read_account=changed, admission=admission).classification
        is Status.BLOCKED
    )


@pytest.mark.parametrize("point", [1, 2, 3])
@pytest.mark.parametrize("bad", ["sid", "admin", "thread", "elevated", "drift"])
def test_trading_token_required_and_drift_blocks(harness, point, bad):
    original = harness.observe_token

    def observe():
        token = original()
        if harness.token_reads == point:
            changes = {
                "sid": {"user_sid": "S-1-5-21-1-2-3-1009"},
                "admin": {"groups": (("S-1-5-32-544", 4),)},
                "thread": {"thread_token_present": True},
                "elevated": {"elevated": True},
                "drift": {"groups": (("S-1-1-0", 4),)},
            }
            return replace(token, **changes[bad])
        return token

    assert harness.run(observe_token=observe).classification is Status.BLOCKED


def test_postlock_c1_drift_blocks_before_reconstruction(harness):
    calls = 0

    def validate(c1):
        nonlocal calls
        calls += 1
        return object() if calls == 2 else c1

    assert harness.run(validate_c1=validate).classification is Status.BLOCKED
    assert "decision" not in harness.events


def test_final_fresh_c1_drift_blocks(harness):
    values = iter((harness.authority, object()))
    assert (
        harness.run(
            acquire_c1=lambda: next(values), validate_c1=lambda value: value
        ).classification
        is Status.BLOCKED
    )


def test_final_namespace_requalification_drift_blocks(harness):
    values = iter((d7d.Namespace.PRESENT_VALID, d7d.Namespace.MISSING))
    assert (
        harness.run(qualify_namespace=lambda: next(values)).classification
        is Status.BLOCKED
    )


@pytest.mark.parametrize("fault", ["order", "classification", "sessions", "current"])
def test_history_source_order_session_and_classification_are_exact(harness, fault):
    if fault == "order":
        window = replace(harness.window, selected=tuple(reversed(harness.items)))
    elif fault == "classification":
        window = replace(harness.window, classification=d7d.Window.WARMING_UP)
    elif fault == "sessions":
        window = replace(
            harness.window,
            required_sessions=tuple(reversed(harness.window.required_sessions)),
        )
    else:
        window = replace(
            harness.window,
            selected=harness.items[:-1],
            classification=d7d.Window.SESSION_GAP,
        )
    assert (
        harness.run(inspect_history=lambda *args: window).classification
        is Status.BLOCKED
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("intended_execution_session", None),
        ("predecessor_checkpoint_id", UUID(int=1)),
        ("paper_account_id", "other"),
        ("history_c3", ()),
        ("decision_id", UUID(int=1)),
    ],
)
def test_candidate_replay_and_source_bindings_are_required(harness, field, value):
    object.__setattr__(harness.binding.decision, field, value)
    assert harness.run().classification is Status.BLOCKED
    assert not harness.discovery_reads


@pytest.mark.parametrize("fault", ["planning", "config", "caller"])
def test_replayable_candidate_must_match_source_owned_inputs(
    harness, monkeypatch, fault
):
    config = daily.personal_desktop_unattended_strategy_config()
    planning = harness.current.selected.verification.snapshot.audit.captured_at
    if fault == "planning":
        planning += timedelta(seconds=1)
    elif fault == "config":
        config = replace(config, short_window=2)
    else:
        original = daily.derive_personal_desktop_unattended_daily_cycle_idempotency_key
        monkeypatch.setattr(
            daily,
            "derive_personal_desktop_unattended_daily_cycle_idempotency_key",
            lambda *args: UUID(int=1),
        )
    history = d7d.build_selected_c3_strategy_history_binding(
        harness.authority, harness.items[:-1], harness.current, config
    )
    candidate = daily.build_personal_desktop_unattended_next_decision(
        harness.authority,
        harness.current,
        history,
        harness.account,
        planning,
        config,
        daily.personal_desktop_unattended_paper_policies(),
    )
    if fault == "caller":
        monkeypatch.setattr(
            daily,
            "derive_personal_desktop_unattended_daily_cycle_idempotency_key",
            original,
        )
    assert (
        harness.run(build_decision=lambda *args: candidate).classification
        is Status.BLOCKED
    )


def test_result_exposes_no_reusable_authority(harness):
    result = harness.run()
    assert set(field.name for field in fields(result)) == {
        "classification",
        "completed_session",
        "selected_snapshot_id",
        "selected_history_count",
        "required_history_count",
        "expected_decision_id",
        "finalized_decision_id",
        "intended_execution_session",
        "regular_open",
        "observed_before_open",
        "account_predecessor_checkpoint_id",
        "namespace_classification",
        "session_discovery_classification",
        "storage_classification",
        "all_eight_gates_closed",
        "real_effect_performed",
    }
    assert (
        inspect.signature(d7d.reconcile_personal_desktop_unattended_decision).parameters
        == {}
    )
    with pytest.raises(ValueError):
        replace(result, real_effect_performed=True)


def test_source_contains_no_effect_gate_assignment_or_prohibited_boundary():
    source = inspect.getsource(d7d)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assert all(
                "EFFECTS_ENABLED" not in ast.unparse(target) for target in targets
            )
    for prohibited in (
        "run_personal_desktop_unattended_decision_publication",
        "issue_pre_open_decision_publication_permit",
        "open_personal_desktop_unattended_decision_output_capability",
        ".publish(",
        "run_personal_desktop_unattended_market_data_capture",
        "provision_personal_desktop_unattended_storage",
        "execute_personal_desktop_unattended_paper_operation",
        "recover_personal_desktop_paper_receipt",
        "finalize_personal_desktop_paper_staging_recovery",
        "scheduler",
        "broker",
        "live",
    ):
        assert prohibited not in source


def test_production_dependency_wiring_is_read_only(monkeypatch):
    monkeypatch.setattr(
        d7d,
        "WindowsTradingTokenObserver",
        lambda: SimpleNamespace(observe=lambda: None),
    )
    dependencies = d7d._production_dependencies()
    assert dependencies.admission is d7d.supervised_paper_cycle_admission
    assert (
        dependencies.build_decision
        is d7d.build_personal_desktop_unattended_next_decision
    )
    assert (
        dependencies.read_storage
        is d7d.read_personal_desktop_unattended_decision_storage
    )
    assert (
        dependencies.qualify_namespace
        is d7d.qualify_trading_unattended_decision_namespace
    )


def test_production_discovery_requires_genuine_current_c1_provenance(
    harness, monkeypatch
):
    monkeypatch.setattr(
        d7d,
        "WindowsTradingTokenObserver",
        lambda: SimpleNamespace(observe=lambda: None),
    )
    monkeypatch.setattr(d7d, "require_validated_production_authority", lambda c1: c1)
    result = d7d.FinalizedUnattendedDecisionForSessionResult(
        d7d.Discovery.FINALIZED,
        harness.binding.decision.intended_execution_session,
        harness.binding.decision.decision_id,
        harness.binding,
    )
    monkeypatch.setattr(
        d7d,
        "require_finalized_unattended_decision_for_execution_session",
        lambda discovery, c1: copy.deepcopy(discovery.binding),
    )
    with pytest.raises(ValueError):
        d7d._production_dependencies().require_discovery(harness.authority, result)


def test_another_finalized_decision_targeting_same_session_blocks_storage_proof(
    harness, monkeypatch
):
    monkeypatch.setattr(
        d7d,
        "WindowsTradingTokenObserver",
        lambda: SimpleNamespace(observe=lambda: None),
    )
    monkeypatch.setattr(d7d, "require_validated_production_authority", lambda c1: c1)
    storage = _storage(harness.binding, d7d.Storage.FINALIZED_IDENTICAL)
    other = copy.deepcopy(harness.binding)
    object.__setattr__(other.decision, "decision_id", UUID(int=1))
    evidence = SimpleNamespace(
        authority=harness.authority,
        expected=harness.binding,
        classification=d7d.Storage.FINALIZED_IDENTICAL,
        finalized=(harness.binding, other),
    )
    monkeypatch.setattr(
        d7d,
        "require_validated_personal_desktop_unattended_decision_storage_read",
        lambda result: evidence,
    )
    with pytest.raises(ValueError):
        d7d._production_dependencies().require_storage(
            harness.authority, harness.binding, storage
        )


def test_exact_paper_account_identity_is_required(harness):
    harness.account.anchor.paper_account_id = UUID(int=1)
    assert harness.run().classification is Status.BLOCKED


def test_genuine_production_c1_is_required():
    from trading_bot.runtime.windows_authority import WindowsAuthorityError

    with pytest.raises(WindowsAuthorityError):
        d7d.require_validated_production_authority(
            SimpleNamespace(approved_account_sid="Trading")
        )


def test_genuine_trading_token_type_is_required(harness):
    assert (
        harness.run(
            observe_token=lambda: SimpleNamespace(user_sid="Trading")
        ).classification
        is Status.BLOCKED
    )
