"""D7-A read-only candidate reconstruction, drift and containment matrix."""

import ast
import ctypes
import inspect
from dataclasses import fields, replace
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.runtime import personal_desktop_unattended_daily_cycle as daily
from trading_bot.runtime import personal_desktop_unattended_decision_qualification as d7
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObservation,
)

from .test_manual_paper_strategy_plan import _prior
from .test_personal_desktop_unattended_decision_publication import Harness as D6Harness
from .test_personal_desktop_unattended_decision_publication import _storage
from .test_personal_desktop_unattended_paper_decision_intent import (
    _HISTORY_DATES,
    _session_read,
)

Status = d7.Status


@pytest.fixture(autouse=True)
def prohibit_production_and_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("D7-A reached native production or an effect boundary")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    from trading_bot.runtime import personal_desktop_paper_runtime_output as output
    from trading_bot.runtime import (
        personal_desktop_unattended_decision_publication as d6,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_market_data_capture as g5,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_decision_publication as pub,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_operation_execution as execution,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_storage_provisioning as admin,
    )

    for module, name in (
        (d6, "run_personal_desktop_unattended_decision_publication"),
        (pub, "issue_pre_open_decision_publication_permit"),
        (output, "open_personal_desktop_unattended_decision_output_capability"),
        (admin, "qualify_personal_desktop_unattended_storage_provisioning"),
        (admin, "provision_personal_desktop_unattended_storage"),
        (g5, "run_personal_desktop_unattended_market_data_capture"),
        (g5, "reconcile_personal_desktop_unattended_market_data_capture"),
        (execution, "execute_personal_desktop_unattended_paper_operation"),
        (daily, "run_personal_desktop_unattended_daily_cycle"),
    ):
        monkeypatch.setattr(module, name, forbidden)


class Harness(D6Harness):
    def __init__(self, monkeypatch):
        super().__init__(monkeypatch)
        self.account.prior_checkpoint = _prior()
        self.account.anchor.paper_account_id = (
            d7.PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.paper_account_id
        )
        monkeypatch.setattr(
            daily, "require_validated_production_authority", lambda value: value
        )
        self.items = tuple(
            _session_read(day, 100 + index) for index, day in enumerate(_HISTORY_DATES)
        ) + (self.current,)
        config = daily.personal_desktop_unattended_strategy_config()
        self.history = d7.build_selected_c3_strategy_history_binding(
            self.authority, self.items[:-1], self.current, config
        )
        self.binding = daily.build_personal_desktop_unattended_next_decision(
            self.authority,
            self.current,
            self.history,
            self.account,
            self.current.selected.verification.snapshot.audit.captured_at,
            config,
            daily.personal_desktop_unattended_paper_policies(),
        )
        self.window = d7.SelectedC3StrategyHistoryWindowResult(
            d7.Window.READY, tuple(i.session for i in self.items), self.items
        )
        self.namespace = d7.Namespace.PRESENT_VALID
        self.token = TradingTokenObservation(
            d7.PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
            1,
            False,
            False,
            (),
        )
        self.token_reads = 0
        self.namespace_reads = 0
        self.proof_failure = None

    def observe_token(self):
        self.token_reads += 1
        self.events.append("token")
        return self.token

    def inspect_history(self, c1, selected, config):
        assert self.held and c1 is self.authority and selected is self.current
        assert config == daily.personal_desktop_unattended_strategy_config()
        self.events.append("history-window")
        return self.window

    def bind_history(self, c1, history, current, config):
        assert self.held and history == self.items[:-1] and current is self.current
        self.events.append("history")
        assert (
            d7.build_selected_c3_strategy_history_binding(c1, history, current, config)
            == self.history
        )
        return self.history

    def require_selected(self, c1, selected):
        assert self.held and c1 is self.authority
        self.events.append("selected-proof")
        if self.proof_failure == "selected":
            raise ValueError("selected C3/current C1 mismatch")

    def qualify_namespace(self):
        assert self.held
        self.namespace_reads += 1
        self.events.append("namespace")
        return self.namespace

    def read_storage(self, c1, expected):
        assert self.held and c1 is self.authority and expected is self.binding
        assert self.gates == [False] * 8
        self.events.append("storage")
        result = _storage(expected, self.storage_state)
        self.storage_reads.append(result)
        return result

    def require_storage(self, c1, expected, storage):
        super().require_storage(c1, expected, storage)
        if self.proof_failure == "storage":
            raise ValueError("storage lacks same-process provenance")

    def dependencies(self):
        return d7.DisposableUnattendedDecisionQualificationDependencies(
            lambda: tuple(self.gates),
            lambda: self.authority,
            self.validate,
            self.observe_token,
            self.now,
            lambda c1: (b"retained-configuration",),
            self.read_account,
            lambda account: account,
            self.admission,
            self.read_selected,
            self.require_selected,
            self.inspect_history,
            self.bind_history,
            self.build_decision,
            self.qualify_namespace,
            self.read_storage,
            self.require_storage,
        )

    def run(self, **overrides):
        result = d7.qualify_personal_desktop_unattended_decision_for_test(
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


def test_exact_six_session_ready_and_mutex(harness):
    result = harness.run()
    assert result.classification is Status.READY
    assert result.candidate_decision_id == harness.binding.decision.decision_id
    assert result.selected_history_count == result.required_history_count == 6
    assert result.deadline_open and result.all_eight_gates_closed
    assert result.completed_session == harness.current.session
    assert result.selected_snapshot_id == harness.current.selected.audit.snapshot_id
    assert (
        result.intended_execution_session
        == harness.binding.decision.intended_execution_session
    )
    assert result.regular_open == d7.xnys_regular_open(
        result.intended_execution_session
    )
    assert (
        harness.account_reads == 3
        and harness.token_reads == 3
        and harness.namespace_reads == 2
    )
    assert (
        harness.events.index("account:1")
        < harness.events.index("lock")
        < harness.events.index("account:2")
    )
    assert (
        harness.events.index("account:2")
        < harness.events.index("decision")
        < harness.events.index("account:3")
        < harness.events.index("release")
    )


@pytest.mark.parametrize("index", range(8))
@pytest.mark.parametrize("value", [True, 1, 0, None, "false"])
def test_each_gate_blocks_before_reads(harness, index, value):
    harness.gates[index] = value
    assert harness.run().classification is Status.BLOCKED
    assert harness.account_reads == 0 and not harness.storage_reads


@pytest.mark.parametrize(
    "state,expected",
    [
        (d7.Storage.ABSENT, Status.READY),
        (d7.Storage.FINALIZED_IDENTICAL, Status.ALREADY_FINALIZED),
        (d7.Storage.STAGING_PRESENT, Status.BLOCKED),
        (d7.Storage.CONFLICTING, Status.BLOCKED),
        (d7.Storage.BLOCKED, Status.BLOCKED),
    ],
)
def test_storage_states(harness, state, expected):
    harness.storage_state = state
    assert harness.run().classification is expected
    assert len(harness.storage_reads) == 1


@pytest.mark.parametrize(
    "offset,expected",
    [
        (-1, Status.READY),
        (0, Status.MISSED_DECISION_DEADLINE),
        (1, Status.MISSED_DECISION_DEADLINE),
    ],
)
def test_deadline_edges(harness, offset, expected):
    harness.observed = d7.xnys_regular_open(
        harness.binding.decision.intended_execution_session
    ) + timedelta(microseconds=offset)
    result = harness.run()
    assert result.classification is expected
    assert result.deadline_open is (offset < 0)


def test_finalized_identical_after_deadline_is_zero_write(harness):
    harness.storage_state = d7.Storage.FINALIZED_IDENTICAL
    harness.observed = d7.xnys_regular_open(
        harness.binding.decision.intended_execution_session
    )
    result = harness.run()
    assert (
        result.classification is Status.ALREADY_FINALIZED and not result.deadline_open
    )


def test_namespace_missing_never_reads_storage(harness):
    harness.namespace = d7.Namespace.MISSING
    result = harness.run()
    assert result.classification is Status.NAMESPACE_MISSING
    assert (
        result.candidate_decision_id is not None
        and result.storage_classification is None
    )
    assert not harness.storage_reads


@pytest.mark.parametrize(
    "classification,indices,expected",
    [
        (d7.Window.WARMING_UP, (4, 5), Status.WARMING_UP),
        (d7.Window.SESSION_GAP, (0, 5), Status.SESSION_GAP),
    ],
)
def test_history_unready(harness, classification, indices, expected):
    harness.window = replace(
        harness.window,
        classification=classification,
        selected=tuple(harness.items[i] for i in indices),
    )
    result = harness.run()
    assert result.classification is expected and result.selected_history_count == 2
    assert (
        harness.account_reads == 3
        and not harness.storage_reads
        and "decision" not in harness.events
    )


@pytest.mark.parametrize("failure", ["selected", "storage"])
def test_current_c1_provenance_mismatch(harness, failure):
    harness.proof_failure = failure
    assert harness.run().classification is Status.BLOCKED


@pytest.mark.parametrize("read", [1, 2, 3])
def test_account_identity_and_predecessor(harness, read):
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


def test_prelock_predecessor_drift_reconstructs_postlock(harness):
    original = harness.read_account

    def prelock(c1, historical):
        account = original(c1, historical)
        if harness.account_reads == 1:
            return SimpleNamespace(
                anchor=account.anchor,
                prior_checkpoint=SimpleNamespace(checkpoint_id=UUID(int=1)),
            )
        return account

    def admission(prelock):
        assert prelock.prior_checkpoint.checkpoint_id == UUID(int=1)
        return harness.admission(harness.account)

    assert (
        harness.run(read_account=prelock, admission=admission).classification
        is Status.READY
    )


def test_final_predecessor_drift(harness):
    harness.drift_at = 3
    assert harness.run().classification is Status.BLOCKED


@pytest.mark.parametrize("point", [1, 2, 3])
@pytest.mark.parametrize("bad", ["sid", "admin", "thread", "elevated", "drift"])
def test_token_invalid_or_drift(harness, point, bad):
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


@pytest.mark.parametrize("drift", ["c1", "gates", "namespace"])
def test_final_drift(harness, drift):
    if drift == "c1":
        calls = 0

        def validate(c1):
            nonlocal calls
            calls += 1
            return object() if calls == 3 else c1

        overrides = {"validate_c1": validate}
    elif drift == "gates":
        original = harness.qualify_namespace

        def namespace():
            value = original()
            if harness.namespace_reads == 2:
                harness.gates[1] = True
            return value

        overrides = {"qualify_namespace": namespace}
    else:
        values = iter((d7.Namespace.PRESENT_VALID, d7.Namespace.MISSING))
        overrides = {"qualify_namespace": lambda: next(values)}
    assert harness.run(**overrides).classification is Status.BLOCKED


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
def test_candidate_replay_and_binding_checks(harness, field, value):
    object.__setattr__(harness.binding.decision, field, value)
    assert harness.run().classification is Status.BLOCKED
    assert not harness.storage_reads


def test_candidate_exact_history_and_planning_replay(harness):
    # A legitimate, replayable alternative decision must still match the
    # selected history and durable planning time supplied by this invocation.
    window = replace(
        harness.window,
        selected=(_session_read(date(2026, 8, 17), 999), *harness.items[1:]),
    )
    assert (
        harness.run(
            inspect_history=lambda *args: window,
            build_history=lambda *args: harness.history,
        ).classification
        is Status.BLOCKED
    )


def test_unknown_storage_and_namespace_block(harness):
    assert (
        harness.run(read_storage=lambda *args: object()).classification
        is Status.BLOCKED
    )
    assert (
        harness.run(qualify_namespace=lambda: "PRESENT_VALID").classification
        is Status.BLOCKED
    )


def test_no_reusable_authority(harness):
    result = harness.run()
    assert set(f.name for f in fields(result)) == {
        "classification",
        "completed_session",
        "selected_snapshot_id",
        "selected_history_count",
        "required_history_count",
        "candidate_decision_id",
        "intended_execution_session",
        "regular_open",
        "account_predecessor_checkpoint_id",
        "namespace_classification",
        "storage_classification",
        "deadline_open",
        "all_eight_gates_closed",
        "real_effect_performed",
    }
    assert (
        inspect.signature(d7.qualify_personal_desktop_unattended_decision).parameters
        == {}
    )
    with pytest.raises(ValueError):
        replace(result, real_effect_performed=True)


def test_source_has_no_effect_calls_or_gate_assignments():
    source = inspect.getsource(d7)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            assert (
                "personal_desktop_unattended_decision_publication"
                not in ast.unparse(node)
            )
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assert all("EFFECTS_ENABLED" not in ast.unparse(t) for t in targets)
    for prohibited in (
        "issue_pre_open_decision_publication_permit",
        "open_personal_desktop_unattended_decision_output_capability",
        "publish(",
        "provision_personal_desktop_unattended_storage",
        "run_personal_desktop_unattended_market_data_capture",
        "execute_personal_desktop_unattended_paper_operation",
        "scheduler",
        "broker",
        "live",
    ):
        assert prohibited not in source


@pytest.mark.parametrize("index", range(8))
@pytest.mark.parametrize("value", [True, 0])
def test_each_final_gate_drift(harness, index, value):
    original = harness.qualify_namespace

    def namespace():
        result = original()
        if harness.namespace_reads == 2:
            harness.gates[index] = value
        return result

    assert harness.run(qualify_namespace=namespace).classification is Status.BLOCKED


@pytest.mark.parametrize("fault", ["order", "classification", "sessions", "current"])
def test_history_window_source_contract(harness, fault):
    if fault == "order":
        window = replace(harness.window, selected=tuple(reversed(harness.items)))
    elif fault == "classification":
        window = replace(harness.window, classification=d7.Window.WARMING_UP)
    elif fault == "sessions":
        window = replace(
            harness.window,
            required_sessions=tuple(reversed(harness.window.required_sessions)),
        )
    else:
        window = replace(
            harness.window,
            selected=harness.items[:-1],
            classification=d7.Window.SESSION_GAP,
        )
    assert (
        harness.run(inspect_history=lambda *args: window).classification
        is Status.BLOCKED
    )


def test_postlock_c1_drift_blocks_before_candidate(harness):
    calls = 0

    def validate(c1):
        nonlocal calls
        calls += 1
        return object() if calls == 2 else c1

    assert harness.run(validate_c1=validate).classification is Status.BLOCKED
    assert "decision" not in harness.events


def test_deadline_can_close_during_qualification(harness):
    harness.times = iter(
        (
            harness.observed,
            d7.xnys_regular_open(harness.binding.decision.intended_execution_session),
        )
    )
    assert harness.run().classification is Status.MISSED_DECISION_DEADLINE


def test_production_dependency_wiring_is_read_only(monkeypatch):
    monkeypatch.setattr(
        d7, "WindowsTradingTokenObserver", lambda: SimpleNamespace(observe=lambda: None)
    )
    deps = d7._production_dependencies()
    assert deps.admission is d7.supervised_paper_cycle_admission
    assert deps.build_decision is d7.build_personal_desktop_unattended_next_decision
    assert deps.build_history is d7.build_selected_c3_strategy_history_binding
    assert deps.read_storage is d7.read_personal_desktop_unattended_decision_storage
    assert deps.qualify_namespace is d7.qualify_trading_unattended_decision_namespace


@pytest.mark.parametrize(
    "fault", ["authority", "expected", "classification", "execution_conflict"]
)
def test_production_storage_provenance_checks(harness, monkeypatch, fault):
    monkeypatch.setattr(
        d7, "WindowsTradingTokenObserver", lambda: SimpleNamespace(observe=lambda: None)
    )
    monkeypatch.setattr(d7, "require_validated_production_authority", lambda c1: c1)
    storage = _storage(harness.binding, d7.Storage.ABSENT)
    evidence = SimpleNamespace(
        authority=harness.authority,
        expected=harness.binding,
        classification=d7.Storage.ABSENT,
        finalized=(),
    )
    if fault == "execution_conflict":
        evidence.finalized = (
            SimpleNamespace(
                decision=SimpleNamespace(
                    intended_execution_session=harness.binding.decision.intended_execution_session
                )
            ),
        )
    else:
        setattr(evidence, fault, object())
    monkeypatch.setattr(
        d7,
        "require_validated_personal_desktop_unattended_decision_storage_read",
        lambda result: evidence,
    )
    with pytest.raises(ValueError):
        d7._production_dependencies().require_storage(
            harness.authority, harness.binding, storage
        )


@pytest.mark.parametrize("fault", ["planning", "config", "caller"])
def test_replayable_alternative_candidate_still_blocks(harness, monkeypatch, fault):
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
    history = d7.build_selected_c3_strategy_history_binding(
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
    assert (
        d7.verify_personal_desktop_unattended_paper_decision_intent(
            candidate.artifact_bytes, d7.personal_desktop_unattended_decision_calendar()
        )
        == candidate
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
    assert not harness.storage_reads


def test_namespace_missing_after_deadline_never_reads_storage(harness):
    harness.namespace = d7.Namespace.MISSING
    harness.observed = d7.xnys_regular_open(
        harness.binding.decision.intended_execution_session
    )
    assert harness.run().classification is Status.MISSED_DECISION_DEADLINE
    assert not harness.storage_reads


def test_genuine_production_c1_is_required(monkeypatch):
    # The public same-process validator rejects field-shaped substitutes.
    from trading_bot.runtime.windows_authority import WindowsAuthorityError

    with pytest.raises(WindowsAuthorityError):
        d7.require_validated_production_authority(
            SimpleNamespace(approved_account_sid="Trading")
        )


def test_final_c1_is_freshly_acquired(harness):
    values = iter((harness.authority, object()))
    assert (
        harness.run(
            acquire_c1=lambda: next(values), validate_c1=lambda c1: c1
        ).classification
        is Status.BLOCKED
    )
    assert harness.account_reads == 3
