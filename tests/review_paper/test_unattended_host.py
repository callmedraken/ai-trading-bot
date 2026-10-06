"""133-E deterministic host boundaries; no real OAuth/provider/scheduler access."""

import ast
import hashlib
import json
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.domain import OrderSide, Symbol, TradeProposal
from trading_bot.review_paper import unattended_host as host
from trading_bot.review_paper import unattended_host_identity as identity
from trading_bot.review_paper import unattended_scheduler as scheduler
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.unattended_activation import ReviewPaperActivation
from trading_bot.review_paper.unattended_activation import ReviewPaperWakeState as State
from trading_bot.review_paper.unattended_execution import UnattendedExecutionResult
from trading_bot.review_paper.unattended_one_wake import (
    OneWakeClassification,
    OneWakeResult,
)
from trading_bot.review_paper.unattended_state_store import UnattendedStateStore
from trading_bot.risk import RiskLimits
from trading_bot.robinhood_execute_qualification_verifier import (
    qualification_fingerprint,
    read_qualification_store,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObservation,
)

PERSISTED_METADATA = host._persisted_oauth_available
EXECUTE = host.execute_one_unattended_review_paper_wake

AT = datetime(2026, 10, 5, 16, tzinfo=UTC)
SECRET = "fake-secret-never-evidence"


@pytest.fixture
def h(tmp_path, monkeypatch):
    value = SimpleNamespace(calls=[], executions=[], oauth=0, clocks=0, failure=None)
    for name, leaf in (
        ("BINDING_PATH", "binding.json"),
        ("ACTIVATION_PATH", "activation.json"),
        ("STATE_PATH", "wake.sqlite"),
        ("PAPER_PATH", "paper.sqlite"),
        ("EVIDENCE_PATH", "evidence.json"),
    ):
        monkeypatch.setattr(identity, name, tmp_path / leaf)
    value.paper = ReviewPaperStore(identity.PAPER_PATH, starting_cash=Decimal("10000"))
    value.state = UnattendedStateStore(identity.STATE_PATH)
    value.runtime = identity.HostRuntimeIdentity(
        "a" * 40, "b" * 40, "c" * 64, "3.14.0", "d" * 64
    )
    value.activation = ReviewPaperActivation(
        source_head=value.runtime.source_head,
        source_tree=value.runtime.source_tree,
        deployment_identity=value.runtime.deployment_identity,
        target_session_date=AT.date(),
        proposal=TradeProposal(
            UUID(int=1), Symbol("SPY"), OrderSide.BUY, Decimal("1"), AT, "frozen"
        ),
        risk_limits=RiskLimits(),
        new_trading_enabled=True,
        store_identity=UUID(int=2),
        store_path=str(identity.PAPER_PATH),
        starting_cash=Decimal("10000"),
        opening_buffer=timedelta(minutes=5),
        closing_buffer=timedelta(minutes=5),
        max_quote_age=timedelta(minutes=1),
        slippage_basis_points=Decimal("5"),
        commission=Decimal("0.1"),
        local_order_id=UUID(int=3),
        created_at=AT,
    )
    value.current = value.state.admit(value.activation)
    value.binding = identity.HostBinding(
        value.runtime,
        hashlib.sha256(value.activation.to_json().encode()).hexdigest(),
        value.activation.store_identity,
        qualification_fingerprint(*read_qualification_store(identity.PAPER_PATH))[
            "sha256"
        ],
        AT + timedelta(minutes=5),
    )

    def publish():
        identity.ACTIVATION_PATH.write_text(
            value.activation.to_json(), encoding="utf-8"
        )
        identity.BINDING_PATH.write_text(value.binding.to_json(), encoding="utf-8")

    value.publish = publish
    publish()

    def runtime(binding):
        value.calls.append("runtime")
        assert binding == value.binding
        if value.failure == "runtime":
            raise RuntimeError(SECRET)

    def clock():
        value.calls.append("clock")
        value.clocks += 1
        return AT

    def metadata():
        value.calls.append("metadata")
        value.oauth += 1
        if value.failure == "metadata":
            raise RuntimeError(SECRET)
        return value.failure != "unavailable"

    def execute(**kwargs):
        value.calls.append("execute")
        value.executions.append(kwargs)
        assert value.calls[0] == "runtime"
        assert kwargs["activation"] == value.activation
        assert kwargs["expected"] == value.current
        assert (
            kwargs["instants"].started_at
            == kwargs["instants"].pre_effect_at
            == kwargs["instants"].finished_at
            == AT
        )
        assert kwargs["binding"].quote_observed_clock is host._current_utc
        assert kwargs["binding"].oauth_valid_until == value.binding.oauth_valid_until
        assert type(kwargs["oauth_storage"]) is host.WindowsOAuthStorage
        if value.failure == "execute":
            raise RuntimeError(SECRET)
        current = value.state.transition(
            value.current, state=State.PREPARE_STARTED, at=AT
        )
        if value.failure == "overlap":
            replay = host.run_unattended_host()
            assert replay.execution_delegations == 0
            assert replay.state is State.PREPARE_STARTED
        quote_at = kwargs["binding"].quote_observed_clock()
        current = value.state.transition(current, state=State.STOPPED, at=quote_at)
        return UnattendedExecutionResult(
            OneWakeResult(
                value.activation.activation_id,
                current.wake.wake_id,
                (0, 1, 2),
                (State.READY, State.PREPARE_STARTED, State.STOPPED),
                None,
                (),
                None,
                None,
                0,
                0,
                State.STOPPED,
                OneWakeClassification.PRE_EFFECT_FAILURE,
            ),
            None,
            None,
            None,
            None,
        )

    monkeypatch.setattr(identity, "admit_host_runtime", runtime)
    monkeypatch.setattr(host, "_current_utc", clock)
    monkeypatch.setattr(host, "_persisted_oauth_available", metadata)
    monkeypatch.setattr(host, "execute_one_unattended_review_paper_wake", execute)
    monkeypatch.setattr(host.WindowsOAuthStorage, "__init__", lambda self: None)
    return value


@pytest.mark.parametrize(
    "argv",
    [
        ["--help"],
        ["--activation", SECRET],
        [SECRET],
        ["--"],
        ["--retry=1"],
        ["--session=2026-10-05"],
    ],
)
def test_zero_cli_arguments_reject_without_reading_authority(h, capsys, argv):
    assert host.main(argv) == 2
    assert h.calls == []
    assert SECRET not in capsys.readouterr().err


def test_argv_from_process_is_rejected_and_sanitized(h, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["launcher", SECRET])
    assert host.main() == 2
    assert h.calls == []
    assert SECRET not in capsys.readouterr().err


@pytest.mark.parametrize(
    "variable",
    [
        "ACTIVATION_PATH",
        "STATE_PATH",
        "PAPER_PATH",
        "EVIDENCE_PATH",
        "OAUTH_TOKEN",
        "SOURCE_HEAD",
        "RETRY",
        "SESSION",
        "PYTHONPATH",
    ],
)
def test_environment_cannot_supply_authority(h, monkeypatch, variable):
    monkeypatch.setenv(variable, SECRET)
    result = host.run_unattended_host()
    assert result.execution_delegations == 1
    assert h.clocks == 2
    assert h.oauth == 0


def test_once_delegation_and_duplicate_manual_launch(h):
    result = host.run_unattended_host()
    replay = host.run_unattended_host()
    assert result.execution_delegations == 1
    assert replay.execution_delegations == 0
    assert replay.state is State.STOPPED
    assert h.clocks == 2 and len(h.executions) == 1 and h.oauth == 0


def test_concurrent_launch_after_durable_consumption_is_read_only(h):
    h.failure = "overlap"
    host.run_unattended_host()
    assert h.clocks == 2 and len(h.executions) == 1


@pytest.mark.parametrize(
    "state",
    [
        State.PREPARE_STARTED,
        State.PREPARED,
        State.REVIEW_STARTED,
        State.COMPLETED,
        State.STOPPED,
        State.INDETERMINATE,
    ],
)
def test_terminal_and_reconciliation_states_have_zero_execution_clock_oauth(h, state):
    current = h.current
    sequence = [State.PREPARE_STARTED, State.PREPARED, State.REVIEW_STARTED]
    if state is State.STOPPED:
        sequence = [State.STOPPED]
    elif state in (State.COMPLETED, State.INDETERMINATE):
        sequence.append(state)
    else:
        sequence = sequence[: sequence.index(state) + 1]
    for step in sequence:
        current = h.state.transition(current, state=step, at=AT)
    result = host.run_unattended_host()
    assert result.state is state and result.execution_delegations == 0
    assert h.clocks == h.oauth == len(h.executions) == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_head", "e" * 40),
        ("source_tree", "e" * 40),
        ("deployment_identity", "e" * 64),
        ("store_identity", UUID(int=9)),
        ("store_path", r"F:\different\paper.sqlite"),
    ],
)
def test_exact_activation_binding_before_clock_and_edges(h, field, value):
    changed = replace(h.activation, **{field: value})
    identity.STATE_PATH.unlink()
    h.state.admit(changed)
    h.activation = changed
    h.binding = replace(
        h.binding,
        activation_sha256=hashlib.sha256(changed.to_json().encode()).hexdigest(),
    )
    h.publish()
    with pytest.raises(identity.UnattendedHostError, match="host wake failed closed"):
        host.run_unattended_host()
    assert h.clocks == h.oauth == len(h.executions) == 0


@pytest.mark.parametrize(
    "mutation",
    ["whitespace", "duplicate", "missing", "unknown", "noncanonical", "unpublished"],
)
def test_activation_publication_is_exact_canonical(h, mutation):
    raw = h.activation.to_json()
    if mutation == "whitespace":
        raw += "\n"
    elif mutation == "duplicate":
        raw = raw.replace("{", '{"schema":"wrong",', 1)
    elif mutation in ("missing", "unknown"):
        data = json.loads(raw)
        if mutation == "missing":
            del data["store_identity"]
        else:
            data[SECRET] = SECRET
        raw = json.dumps(data)
    elif mutation == "noncanonical":
        raw = json.dumps(json.loads(raw), indent=2)
    else:
        identity.ACTIVATION_PATH.unlink()
    if mutation != "unpublished":
        identity.ACTIVATION_PATH.write_text(raw, encoding="utf-8")
    with pytest.raises(identity.UnattendedHostError):
        host.run_unattended_host()
    assert h.clocks == h.oauth == len(h.executions) == 0


@pytest.mark.parametrize("failure", ["runtime", "execute"])
def test_fixed_errors_no_retry_and_no_raw_exception(h, failure, capsys):
    h.failure = failure
    assert host.main([]) == 3
    assert SECRET not in capsys.readouterr().err
    assert h.clocks <= 2 and len(h.executions) <= 1 and h.oauth == 0


def test_q133_1_is_read_only_and_never_constructs_writer(h, monkeypatch):
    before = h.state.snapshot()
    paper_before = identity.PAPER_PATH.read_bytes()
    monkeypatch.setattr(
        host, "UnattendedStateStore", lambda *a, **k: pytest.fail("writer")
    )
    monkeypatch.setattr(
        host, "ReviewPaperStore", lambda *a, **k: pytest.fail("paper constructor")
    )
    result = host.preflight_unattended_host()
    assert result.persisted_oauth_available is True
    assert result.consumed_wake_authority == result.execution_delegations == 0
    assert h.clocks == 0 and h.oauth == 1 and not h.executions
    assert h.state.snapshot() == before
    assert identity.PAPER_PATH.read_bytes() == paper_before
    assert result.scheduler.semantic_arguments == ()


@pytest.mark.parametrize("failure", ["metadata", "unavailable", "runtime"])
def test_preflight_failure_has_zero_delegation_and_fixed_error(h, failure):
    h.failure = failure
    with pytest.raises(
        identity.UnattendedHostError, match="host preflight failed closed"
    ):
        host.preflight_unattended_host()
    assert h.clocks == len(h.executions) == 0


def test_preflight_rejects_consumed_authority_before_oauth(h):
    h.state.transition(h.current, state=State.PREPARE_STARTED, at=AT)
    with pytest.raises(identity.UnattendedHostError):
        host.preflight_unattended_host()
    assert h.oauth == h.clocks == len(h.executions) == 0


def test_paper_predecessor_drift_blocks_clock_and_execution(h):
    h.binding = replace(h.binding, paper_predecessor_sha256="0" * 64)
    h.publish()
    with pytest.raises(identity.UnattendedHostError):
        host.run_unattended_host()
    assert h.clocks == h.oauth == len(h.executions) == 0


def test_binding_roundtrip_and_runtime_identity_are_immutable(h):
    assert identity.HostBinding.from_json(h.binding.to_json()) == h.binding
    assert (
        h.runtime.deployment_identity
        != replace(h.runtime, python_sha256="0" * 64).deployment_identity
    )
    with pytest.raises(FrozenInstanceError):
        h.binding.store_identity = UUID(int=9)


@pytest.mark.parametrize(
    "mutation",
    ["extra", "newline", "duplicate", "bad-runtime", "bad-expiry", "bad-schema"],
)
def test_binding_rejects_noncanonical_and_unknown_material(h, mutation):
    data = json.loads(h.binding.to_json())
    if mutation == "extra":
        data[SECRET] = SECRET
    elif mutation == "bad-runtime":
        data["runtime"]["source_head"] = SECRET
    elif mutation == "bad-expiry":
        data["oauth_valid_until"] = "2026-10-05T16:00:00"
    elif mutation == "bad-schema":
        data["schema"] = SECRET
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"))
    if mutation == "newline":
        raw += "\n"
    elif mutation == "duplicate":
        raw = raw.replace("{", '{"schema":"duplicate",', 1)
    with pytest.raises(identity.UnattendedHostError, match="host binding invalid"):
        identity.HostBinding.from_json(raw)


def test_scheduler_exact_single_session_action_is_pure_and_distinct(h):
    spec = scheduler.build_unattended_scheduler_spec(h.activation)
    assert spec.task_path == r"\AITradingBot-Arch133-SingleSessionReviewPaper-v1"
    assert "D10" not in spec.task_path and "D10" not in spec.executable
    assert spec.executable == r"F:\AITradingBot\Arch133\runtime\python.exe"
    assert spec.arguments == ("-I", "-B", scheduler.LAUNCHER)
    assert spec.semantic_arguments == spec.scheduler_owned_environment == ()
    assert spec.start_boundary == AT
    assert spec.end_boundary == datetime(2026, 10, 5, 19, 55, tzinfo=UTC)
    assert spec.trigger_type == "TIME"
    assert spec.multiple_instances_policy == "IgnoreNew"
    assert spec.restart_count == 0 and spec.restart_interval is spec.repetition is None
    assert (
        not spec.start_when_available
        and not spec.installation_authorized
        and not spec.scheduler_is_authority
    )
    with pytest.raises(FrozenInstanceError):
        spec.arguments = (SECRET,)


def test_scheduler_published_early_close_and_no_other_session(h):
    activation = replace(
        h.activation,
        target_session_date=datetime(2026, 11, 27).date(),
        created_at=datetime(2026, 11, 26, tzinfo=UTC),
    )
    spec = scheduler.build_unattended_scheduler_spec(activation)
    assert spec.start_boundary == datetime(2026, 11, 27, 14, 35, tzinfo=UTC)
    assert spec.end_boundary == datetime(2026, 11, 27, 17, 55, tzinfo=UTC)
    with pytest.raises(ValueError):
        scheduler.build_unattended_scheduler_spec(
            replace(activation, target_session_date=datetime(2026, 11, 26).date())
        )


def test_source_has_no_scheduler_inspection_mutation_loop_or_oauth_renewal():
    for module in (host, scheduler):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, (ast.While, ast.AsyncFor)) for node in ast.walk(tree)
        )
        text = {
            n.id if isinstance(n, ast.Name) else n.attr
            for n in ast.walk(tree)
            if isinstance(n, (ast.Name, ast.Attribute))
        }
        for name in (
            "subprocess",
            "schtasks",
            "OAuthClientProvider",
            "getenv",
            "environ",
            "sleep",
            "refresh",
            "set_tokens",
            "create_windows_robinhood_oauth_factory",
        ):
            assert name not in text
    tree = ast.parse(Path(host.__file__).read_text(encoding="utf-8"))
    assert (
        sum(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "execute_one_unattended_review_paper_wake"
            for n in ast.walk(tree)
        )
        == 1
    )


@pytest.fixture
def runtime_h(tmp_path, monkeypatch):
    root = tmp_path / "source"
    file = root / "src" / "trading_bot" / "review_paper" / "identity.py"
    file.parent.mkdir(parents=True)
    python = tmp_path / "python.exe"
    launcher = root / "scripts" / "launch.py"
    launcher.parent.mkdir()
    python.write_bytes(b"reviewed-runtime")
    launcher.write_bytes(b"reviewed-launcher")
    runtime = identity.HostRuntimeIdentity(
        "a" * 40,
        "b" * 40,
        hashlib.sha256(python.read_bytes()).hexdigest(),
        "3.14.0",
        hashlib.sha256(launcher.read_bytes()).hexdigest(),
    )
    binding = identity.HostBinding(
        runtime, "c" * 64, UUID(int=2), "d" * 64, AT + timedelta(minutes=5)
    )
    fake_sys = SimpleNamespace(
        platform="win32",
        flags=SimpleNamespace(isolated=1),
        dont_write_bytecode=True,
        executable=str(python),
        pycache_prefix=str(tmp_path / "no-pycache"),
        argv=[str(launcher)],
        version_info=(3, 14, 0),
    )
    calls = []
    monkeypatch.setattr(identity, "sys", fake_sys)
    monkeypatch.setattr(identity, "__file__", str(file))
    monkeypatch.setattr(identity, "SOURCE_ROOT", root)
    monkeypatch.setattr(identity, "PRODUCTION_PYTHON", python)
    monkeypatch.setattr(identity, "LAUNCHER", launcher)
    monkeypatch.setattr(identity, "HOST_ROOT", tmp_path / "host")
    monkeypatch.setattr(identity, "NO_PYCACHE", tmp_path / "no-pycache")

    def source(**kwargs):
        calls.append(kwargs)
        assert kwargs == dict(
            expected_branch=identity.SOURCE_BRANCH,
            expected_head=runtime.source_head,
            expected_tree=runtime.source_tree,
        )
        return (root,)

    monkeypatch.setattr(identity, "admit_robinhood_paper_source", source)
    monkeypatch.setattr(
        identity,
        "WindowsTradingTokenObserver",
        lambda: SimpleNamespace(
            observe=lambda: TradingTokenObservation(
                identity.TRADING_SID, 1, False, False, ()
            )
        ),
    )
    return SimpleNamespace(
        binding=binding, sys=fake_sys, calls=calls, python=python, launcher=launcher
    )


def test_runtime_independently_measures_exact_executables_and_source(runtime_h):
    identity.admit_host_runtime(runtime_h.binding)
    assert len(runtime_h.calls) == 1


@pytest.mark.parametrize(
    "drift",
    [
        "python",
        "launcher",
        "version",
        "isolation",
        "bytecode",
        "platform",
        "source",
        "principal",
        "cached-bytecode",
        "cache-prefix",
        "entrypoint",
    ],
)
def test_runtime_drift_blocks_before_provider_metadata(runtime_h, monkeypatch, drift):
    if drift in ("python", "launcher"):
        getattr(runtime_h, drift).write_bytes(SECRET.encode())
    elif drift == "version":
        runtime_h.sys.version_info = (3, 14, 1)
    elif drift == "isolation":
        runtime_h.sys.flags.isolated = 0
    elif drift == "bytecode":
        runtime_h.sys.dont_write_bytecode = False
    elif drift == "platform":
        runtime_h.sys.platform = "linux"
    elif drift == "cached-bytecode":
        identity.NO_PYCACHE.mkdir()
    elif drift == "cache-prefix":
        runtime_h.sys.pycache_prefix = SECRET
    elif drift == "entrypoint":
        runtime_h.sys.argv = [SECRET]
    elif drift == "principal":
        monkeypatch.setattr(
            identity,
            "WindowsTradingTokenObserver",
            lambda: SimpleNamespace(
                observe=lambda: TradingTokenObservation("wrong", 1, False, False, ())
            ),
        )
    else:

        def fail(**kwargs):
            raise RuntimeError(SECRET)

        monkeypatch.setattr(identity, "admit_robinhood_paper_source", fail)
    with pytest.raises(
        identity.UnattendedHostError, match="host source/runtime admission failed"
    ):
        identity.admit_host_runtime(runtime_h.binding)


@pytest.mark.parametrize(
    "at", [AT - timedelta(hours=3), AT + timedelta(hours=5), AT + timedelta(days=1)]
)
def test_actual_133d_missed_or_unadmitted_session_has_no_oauth_or_catchup(
    h, monkeypatch, at
):
    # Existing 133-C owns the no-session/no-effect classification; no host loop.
    if at < h.activation.created_at:
        h.activation = replace(
            h.activation,
            proposal=replace(h.activation.proposal, created_at=at - timedelta(days=1)),
            created_at=at - timedelta(days=1),
        )
        h.binding = replace(
            h.binding,
            activation_sha256=hashlib.sha256(
                h.activation.to_json().encode()
            ).hexdigest(),
        )
        identity.STATE_PATH.unlink()
        h.current = h.state.admit(h.activation)
        h.publish()

    def clock():
        h.clocks += 1
        return at

    async def forbidden(self):
        pytest.fail("OAuth before session admission")

    monkeypatch.setattr(host, "_current_utc", clock)
    monkeypatch.setattr(host, "execute_one_unattended_review_paper_wake", EXECUTE)
    monkeypatch.setattr(host.WindowsOAuthStorage, "get_tokens", forbidden)
    result = host.run_unattended_host()
    assert result.state is State.STOPPED
    assert result.status == "SESSION_NOT_ADMITTED"
    assert h.clocks == 1
    assert host.run_unattended_host().execution_delegations == 0


@pytest.mark.parametrize(
    "token_type,access,expires,expected",
    [
        ("Bearer", SECRET, 300, True),
        ("bearer", SECRET, None, True),
        ("Bearer", "", 300, False),
        ("other", SECRET, 300, False),
        ("Bearer", SECRET, 0, False),
        ("Bearer", SECRET, -1, False),
    ],
)
def test_oauth_metadata_uses_only_accepted_persisted_storage(
    h, monkeypatch, token_type, access, expires, expected
):
    calls = []

    async def tokens(self):
        calls.append("persisted")
        return SimpleNamespace(
            token_type=token_type, access_token=access, expires_in=expires
        )

    monkeypatch.setattr(host.WindowsOAuthStorage, "get_tokens", tokens)
    assert PERSISTED_METADATA() is expected
    assert calls == ["persisted"]


def test_preflight_and_wake_discard_secret_output(h, monkeypatch, capfd):
    def metadata():
        print(SECRET)
        print(SECRET, file=sys.stderr)
        raise RuntimeError(SECRET)

    monkeypatch.setattr(host, "_persisted_oauth_available", metadata)
    with pytest.raises(identity.UnattendedHostError) as error:
        host.preflight_unattended_host()
    captured = capfd.readouterr()
    assert SECRET not in captured.out + captured.err + str(error.value)


def test_preflight_racing_consumption_never_passes(h, monkeypatch):
    def metadata():
        h.state.transition(h.current, state=State.PREPARE_STARTED, at=AT)
        return True

    monkeypatch.setattr(host, "_persisted_oauth_available", metadata)
    with pytest.raises(identity.UnattendedHostError):
        host.preflight_unattended_host()
    assert len(h.executions) == 0


def test_single_activation_state_binding_rejects_extra_activation(h):
    h.state.admit(replace(h.activation, local_order_id=UUID(int=44)))
    with pytest.raises(identity.UnattendedHostError):
        host.run_unattended_host()
    assert h.clocks == h.oauth == len(h.executions) == 0


def test_missing_state_does_not_create_or_admit(h):
    identity.STATE_PATH.unlink()
    with pytest.raises(identity.UnattendedHostError):
        host.run_unattended_host()
    assert not identity.STATE_PATH.exists()
    assert h.clocks == h.oauth == len(h.executions) == 0


def test_malformed_execution_classification_never_becomes_evidence(
    h, monkeypatch, capsys
):
    original = host.execute_one_unattended_review_paper_wake

    def bad(**kwargs):
        result = original(**kwargs)
        return replace(
            result,
            wake=replace(result.wake, classification=SimpleNamespace(value=SECRET)),
        )

    monkeypatch.setattr(host, "execute_one_unattended_review_paper_wake", bad)
    assert host.main([]) == 3
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err
    assert len(h.executions) == 1


def test_launcher_selects_own_source_and_has_no_semantic_scheduler_input():
    launcher = (
        Path(host.__file__).resolve().parents[3]
        / "scripts"
        / "run_arch133_unattended_review_paper.py"
    )
    tree = ast.parse(launcher.read_text())
    assert "environ" not in {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
    }
    assert any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "main"
        and not n.args
        and not n.keywords
        for n in ast.walk(tree)
    )
