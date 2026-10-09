"""133-P fake-only admission, orchestration, native structure and authority tests."""

import ast
import ctypes
import hashlib
import json
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from scripts import checkpoint_runner as runner
from trading_bot.arch133_acl import read_only, retained_reads
from trading_bot.arch133_scheduler_installation import admission as operator
from trading_bot.arch133_scheduler_installation import operator as scheduler
from trading_bot.arch133_scheduler_installation import specification
from trading_bot.arch133_verifier import (
    binding,
    file_policy,
    token,
)
from trading_bot.domain import OrderSide, Symbol, TradeProposal
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.unattended_activation import ReviewPaperActivation
from trading_bot.review_paper.unattended_state_store import UnattendedStateStore
from trading_bot.risk import RiskLimits
from trading_bot.robinhood_execute_qualification_verifier import (
    qualification_fingerprint,
    read_qualification_store,
)

ROOT = Path(__file__).resolve().parents[2]
SECRET = "private-token-client-native-error-material"
AT = datetime(2026, 10, 5, 16, tzinfo=UTC)


@pytest.fixture(autouse=True)
def no_real_edges(monkeypatch):
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: pytest.fail("native reached"))
    monkeypatch.setattr(
        token.WindowsTradingTokenObserver,
        "observe",
        lambda _: pytest.fail("token reached"),
    )


@pytest.fixture
def fake(tmp_path, monkeypatch):
    f = SimpleNamespace(
        calls=[], root_reads=0, namespace_reads=0, runtime_reads=0, drift=None
    )
    for name, leaf in (
        ("ACTIVATION_PATH", "activation.json"),
        ("BINDING_PATH", "host-binding.json"),
        ("PAPER_PATH", "paper.sqlite"),
        ("STATE_PATH", "wake.sqlite"),
    ):
        monkeypatch.setattr(binding, name, tmp_path / leaf)
    # Only fixtures construct writers, and only under pytest's explicit temp root.
    ReviewPaperStore(binding.PAPER_PATH, starting_cash=Decimal("10000"))
    state = UnattendedStateStore(binding.STATE_PATH)
    runtime = binding.HostRuntimeIdentity(
        operator.PUBLISHED_RUNTIME_HEAD,
        operator.PUBLISHED_RUNTIME_TREE,
        binding.PRODUCTION_PYTHON_SHA256,
        binding.PRODUCTION_PYTHON_VERSION,
        "d" * 64,
    )
    act = ReviewPaperActivation(
        source_head=runtime.source_head,
        source_tree=runtime.source_tree,
        deployment_identity=runtime.deployment_identity,
        target_session_date=AT.date(),
        proposal=TradeProposal(
            UUID(int=1), Symbol("SPY"), OrderSide.BUY, Decimal("1"), AT, "frozen"
        ),
        risk_limits=RiskLimits(),
        new_trading_enabled=True,
        store_identity=UUID(int=2),
        store_path=str(binding.PAPER_PATH),
        starting_cash=Decimal("10000"),
        opening_buffer=timedelta(minutes=5),
        closing_buffer=timedelta(minutes=5),
        max_quote_age=timedelta(minutes=1),
        slippage_basis_points=Decimal("5"),
        commission=Decimal("0.1"),
        local_order_id=UUID(int=3),
        created_at=AT,
    )
    current = state.admit(act)
    host = binding.HostBinding(
        runtime,
        hashlib.sha256(act.to_json().encode()).hexdigest(),
        act.store_identity,
        qualification_fingerprint(*read_qualification_store(binding.PAPER_PATH))[
            "sha256"
        ],
        AT + timedelta(minutes=5),
    )
    binding.ACTIVATION_PATH.write_bytes(act.to_json().encode())
    binding.BINDING_PATH.write_bytes(host.to_json().encode())
    hashes = {
        name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
        for name in retained_reads.FINAL_NAMES
    }
    monkeypatch.setattr(operator, "FILE_HASHES", hashes)
    names = tuple((name, i + 10) for i, name in enumerate(retained_reads.FINAL_NAMES))
    root = read_only.DirectoryObservation(
        read_only.ADMINISTRATORS_SID, True, read_only.ROOT_ACES, operator.ROOT_IDENTITY
    )
    f.root, f.names, f.act, f.host, f.current, f.store = (
        root,
        names,
        act,
        host,
        current,
        state,
    )
    f.runtime = {
        "diagnostic_source_head": "a" * 40,
        "diagnostic_source_tree": "b" * 40,
        "bound_source_head": operator.EXECUTABLE_SOURCE_HEAD,
        "bound_source_tree": operator.EXECUTABLE_SOURCE_TREE,
        "python_sha256": binding.PRODUCTION_PYTHON_SHA256,
        "python_version": binding.PRODUCTION_PYTHON_VERSION,
        "wake_launcher_sha256": runtime.launcher_sha256,
    }

    def runtime_read():
        f.runtime_reads += 1
        return {
            **f.runtime,
            **(
                {"python_sha256": "e" * 64}
                if f.drift == "runtime" and f.runtime_reads > 1
                else {}
            ),
        }

    monkeypatch.setattr(operator, "_runtime", runtime_read)
    monkeypatch.setattr(operator, "_principal", lambda: f.calls.append("principal"))
    monkeypatch.setattr(
        read_only,
        "open_directory",
        lambda path, **kw: f.calls.append(("open", path, kw)) or path,
    )

    def close(handle):
        f.calls.append(("close", handle))
        if f.drift == "close":
            raise RuntimeError(SECRET)

    monkeypatch.setattr(read_only, "close_handle", close)

    def security(handle, path):
        if path != retained_reads.TARGET_PATH:
            return replace(root, identity=(1, 2)), "e" * 64
        f.root_reads += 1
        value = (
            replace(root, identity=(1, 2))
            if f.drift == "root" and f.root_reads > 1
            else f.root
        )
        return value, (
            "e" * 64 if f.drift == "security" else operator.ROOT_SECURITY_SHA256
        )

    monkeypatch.setattr(read_only, "inspect_directory_security", security)

    def namespace(handle):
        f.namespace_reads += 1
        return (
            names[:-1] if f.drift == "namespace" and f.namespace_reads > 1 else f.names
        )

    monkeypatch.setattr(retained_reads, "namespace", namespace)
    monkeypatch.setattr(retained_reads, "open_retained_file", lambda name: name)

    def snapshot(handle, name):
        return (
            (operator.ROOT_IDENTITY[0], dict(names)[name]),
            "e" * 64
            if f.drift == "hash"
            else hashlib.sha256((tmp_path / name).read_bytes()).hexdigest(),
        )

    monkeypatch.setattr(retained_reads, "file_snapshot", snapshot)

    def policy(handle):
        rights = 0x120089 if handle.endswith(".json") else 0x12019F
        return file_policy.FilePolicy(
            read_only.ADMINISTRATORS_SID,
            True,
            read_only.ADMIN_ACES + ((binding.TRADING_SID, rights, 0, 0),),
            "c" * 64,
        )

    monkeypatch.setattr(file_policy, "observe_file_policy", policy)

    return f


@pytest.fixture
def edges(fake, monkeypatch):
    f = fake
    f.observation = {"status": "ABSENT"}
    f.clock = AT - timedelta(seconds=1)
    f.registrations = 0
    f.credentials = 0
    f.scheduler_reads = 0
    f.native_result = {
        "schema": scheduler.INSTALL_SCHEMA,
        "disposition": "CALL_RETURNED",
        "registration_attempts": 1,
    }
    f.after_password = None
    f.after_register = None
    f.registration_error = None
    f.guard_held = False
    f.admissions = 0
    observe = operator.observe_admission

    def admitted():
        f.admissions += 1
        return observe()

    def password():
        f.credentials += 1
        if f.after_password:
            f.after_password()
        return "fake-console-secret-never-real"

    @contextmanager
    def guard():
        f.guard_held = True
        try:
            yield
        finally:
            f.guard_held = False

    def native(script, request=None):
        if script == "arch133_scheduler_observe.ps1":
            assert request is None
            f.scheduler_reads += 2
            return {
                "schema": scheduler.OBSERVE_SCHEMA,
                "first": dict(f.observation),
                "second": dict(f.observation),
            }
        assert script == "arch133_scheduler_install.ps1"
        assert f.guard_held
        f.registrations += 1
        assert f.registrations == 1
        assert set(request) == {
            "activation_sha256",
            "start_boundary",
            "end_boundary",
            "password",
        }
        assert request["password"] == "fake-console-secret-never-real"
        if f.registration_error:
            raise f.registration_error(SECRET)
        spec = specification.build_unattended_scheduler_spec(
            operator.ReviewPaperActivation.from_json(f.act.to_json())
        )
        f.observation = {
            "status": "PRESENT",
            "projection_sha256": scheduler.desired_task(spec)["projection_sha256"],
            "xml_sha256": "a" * 64,
        }
        if f.after_register:
            f.after_register()
        return f.native_result

    monkeypatch.setattr(operator, "observe_admission", admitted)
    monkeypatch.setattr(operator, "registration_guard", guard)
    monkeypatch.setattr(scheduler, "_native", native)
    monkeypatch.setattr(scheduler, "_read_password", password)
    monkeypatch.setattr(scheduler, "_utc_now", lambda: f.clock)
    return f


def execute(f):
    plan = scheduler.operate("plan")
    assert plan["status"] == "PASS"
    return scheduler.operate("execute-once", plan["plan_sha256"])


def zero_effects(result, *, reads=0, writes=0):
    for name in scheduler.ZERO_EFFECTS:
        assert type(result[name]) is int
        if name not in {"scheduler_reads", "scheduler_writes", "credential_reads"}:
            assert result[name] == 0, name
    assert result["scheduler_writes"] == writes
    assert result["credential_reads"] == reads
    assert SECRET not in scheduler.canonical(result)
    assert "fake-console-secret-never-real" not in scheduler.canonical(result)


def test_fixed_spec_and_canonical_function(edges):
    act = operator.ReviewPaperActivation.from_json(edges.act.to_json())
    spec = specification.build_unattended_scheduler_spec(act)
    from trading_bot.review_paper.unattended_scheduler import (
        build_unattended_scheduler_spec,
    )

    canonical = build_unattended_scheduler_spec(edges.act)
    assert spec.start_boundary == canonical.start_boundary == AT
    assert spec.end_boundary == canonical.end_boundary
    desired = scheduler.desired_task(spec)
    assert desired["task_path"] == r"\AITradingBot-Arch133-SingleSessionReviewPaper-v1"
    assert desired["principal"] == r"DESKTOP-I4DOKM7\Trading"
    assert desired["principal_sid"] == binding.TRADING_SID
    assert desired["executable"] == r"F:\AITradingBot\runtime\python.exe"
    assert desired["arguments"] == ["-I", "-B", str(binding.LAUNCHER)]
    assert desired["working_directory"] == str(binding.SOURCE_ROOT)
    assert desired["windows_settings"]["enabled"] is False
    assert desired["windows_settings"]["allow_demand_start"] is False
    assert desired["windows_settings"]["logon_type"] == "Password"
    assert desired["restart_count"] == 0
    assert desired["restart_interval"] is desired["repetition"] is None
    assert desired["start_when_available"] is desired["scheduler_is_authority"] is False
    assert (
        not desired["semantic_arguments"] and not desired["scheduler_owned_environment"]
    )


@pytest.mark.parametrize(
    "session",
    [
        datetime(2026, 10, 5, 12, tzinfo=UTC),
        datetime(2026, 11, 27, 12, tzinfo=UTC),
        datetime(2026, 12, 24, 12, tzinfo=UTC),
    ],
)
def test_scheduler_boundaries_ordinary_and_early_close(edges, session):
    act = replace(
        edges.act,
        target_session_date=session.date(),
        created_at=session,
        proposal=replace(edges.act.proposal, created_at=session),
    )
    inert = operator.ReviewPaperActivation.from_json(act.to_json())
    spec = specification.build_unattended_scheduler_spec(inert)
    from trading_bot.review_paper.unattended_scheduler import (
        build_unattended_scheduler_spec,
    )

    expected = build_unattended_scheduler_spec(act)
    assert (spec.start_boundary, spec.end_boundary) == (
        expected.start_boundary,
        expected.end_boundary,
    )


@pytest.mark.parametrize(
    "delta", [timedelta(0), timedelta(seconds=1), timedelta(days=1)]
)
@pytest.mark.parametrize("mode", ["plan", "execute-once"])
def test_stale_before_credentials_or_scheduler(edges, delta, mode):
    edges.clock = AT + delta
    result = scheduler.operate(mode, "a" * 64 if mode == "execute-once" else None)
    assert result["disposition"] == "STALE_EXPIRED"
    assert result["status"] == "BLOCKED"
    assert edges.credentials == edges.registrations == edges.scheduler_reads == 0
    zero_effects(result)


def test_plan_absent_read_only_and_hash_stable(edges):
    first = scheduler.operate("plan")
    edges.clock += timedelta(microseconds=1)
    second = scheduler.operate("plan")
    assert first == second
    assert first["disposition"] == "ABSENT"
    material = {
        k: v
        for k, v in first.items()
        if k not in scheduler.ZERO_EFFECTS and k not in {"status", "plan_sha256"}
    }
    assert scheduler.sha256(material) == first["plan_sha256"]
    assert edges.credentials == edges.registrations == 0
    zero_effects(first)


def test_absent_single_create_double_readback_and_unchanged_stores(edges):
    before = {
        name: (binding.PAPER_PATH.parent / name).read_bytes()
        for name in retained_reads.FINAL_NAMES
    }
    result = execute(edges)
    assert result["status"] == "PASS"
    assert result["disposition"] == "CREATED_VERIFIED"
    assert edges.registrations == edges.credentials == 1
    assert edges.observation["status"] == "PRESENT"
    assert {
        name: (binding.PAPER_PATH.parent / name).read_bytes()
        for name in retained_reads.FINAL_NAMES
    } == before
    inert = operator.ReviewPaperActivation.from_json(edges.act.to_json())
    with sqlite3.connect(binding.STATE_PATH) as connection:
        assert operator._state_semantics(connection, inert).current(inert).revision == 0
    zero_effects(result, reads=1, writes=1)


def matching(f):
    spec = specification.build_unattended_scheduler_spec(
        operator.ReviewPaperActivation.from_json(f.act.to_json())
    )
    f.observation = {
        "status": "PRESENT",
        "projection_sha256": scheduler.desired_task(spec)["projection_sha256"],
        "xml_sha256": "a" * 64,
    }


def test_matching_no_password_or_registration(edges):
    matching(edges)
    result = execute(edges)
    assert result["status"] == "PASS" and result["disposition"] == "ALREADY_MATCHING"
    assert edges.registrations == edges.credentials == 0
    zero_effects(result)


def test_unexpected_existing_blocks_before_credential(edges):
    matching(edges)
    edges.observation["projection_sha256"] = "b" * 64
    plan = scheduler.operate("plan")
    assert plan["disposition"] == "UNEXPECTED_EXISTING" and plan["status"] == "BLOCKED"
    result = scheduler.operate("execute-once", plan["plan_sha256"])
    assert result["status"] == "BLOCKED"
    assert edges.credentials == edges.registrations == 0
    zero_effects(result)


@pytest.mark.parametrize(
    "value", [None, "", "A" * 64, "g" * 64, "a" * 63, "a" * 65, "../../injected", 0]
)
def test_invalid_reviewed_hash_no_admission(edges, value):
    result = scheduler.operate("execute-once", value)
    assert result["status"] == "BLOCKED"
    assert (
        edges.admissions
        == edges.credentials
        == edges.registrations
        == edges.scheduler_reads
        == 0
    )


def test_hash_drift_before_password(edges):
    plan = scheduler.operate("plan")
    result = scheduler.operate("execute-once", "e" * 64)
    assert result["disposition"] == "PLAN_DRIFT"
    assert edges.credentials == edges.registrations == 0
    assert plan["plan_sha256"] != "e" * 64


@pytest.mark.parametrize(
    "drift", ["root", "security", "namespace", "hash", "runtime", "close"]
)
def test_admission_drift_before_scheduler(edges, drift):
    edges.drift = drift
    result = scheduler.operate("plan")
    assert result["status"] == "BLOCKED"
    assert edges.credentials == edges.registrations == edges.scheduler_reads == 0


@pytest.mark.parametrize(
    "target", ["activation.json", "host-binding.json", "paper.sqlite", "wake.sqlite"]
)
def test_password_pause_retained_drift_blocks_registration(edges, target):
    edges.after_password = lambda: (binding.PAPER_PATH.parent / target).write_bytes(
        b"drift"
    )
    result = execute(edges)
    assert result["status"] == "BLOCKED"
    assert edges.credentials == 1 and edges.registrations == 0
    zero_effects(result, reads=1)


def test_password_pause_scheduler_drift(edges):
    edges.after_password = lambda: matching(edges)
    result = execute(edges)
    assert (
        result["status"] == "BLOCKED"
        and result["disposition"] == "PASSWORD_PAUSE_DRIFT"
    )
    assert edges.registrations == 0


def test_password_pause_start_arrival_blocks(edges):
    edges.after_password = lambda: setattr(edges, "clock", AT)
    result = execute(edges)
    assert result["disposition"] == "STALE_EXPIRED"
    assert edges.registrations == 0
    zero_effects(result, reads=1)


@pytest.mark.parametrize(
    "exception", [RuntimeError, subprocess.TimeoutExpired, KeyboardInterrupt]
)
def test_registration_exception_indeterminate_no_retry(edges, exception):
    if exception is subprocess.TimeoutExpired:
        edges.registration_error = lambda *args: subprocess.TimeoutExpired("fixed", 30)
    else:
        edges.registration_error = exception
    result = execute(edges)
    assert result["status"] == result["disposition"] == "INDETERMINATE"
    assert edges.registrations == 1
    zero_effects(result, reads=1, writes=1)


@pytest.mark.parametrize(
    "native",
    [
        {},
        {"disposition": "CALL_RETURNED"},
        {
            "schema": scheduler.INSTALL_SCHEMA,
            "disposition": "INDETERMINATE",
            "registration_attempts": 1,
        },
    ],
)
def test_ambiguous_result_indeterminate(edges, native):
    edges.native_result = native
    result = execute(edges)
    assert result["status"] == "INDETERMINATE" and edges.registrations == 1


def test_native_not_called_stops_no_retry(edges):
    edges.native_result = {
        "schema": scheduler.INSTALL_SCHEMA,
        "disposition": "NOT_CALLED",
        "registration_attempts": 0,
    }
    result = execute(edges)
    assert result["status"] == "BLOCKED" and result["disposition"] == "NATIVE_BLOCKED"
    assert edges.registrations == 1
    zero_effects(result, reads=1)


@pytest.mark.parametrize("drift", ["task", "paper", "state", "runtime"])
def test_post_registration_drift_is_indeterminate(edges, drift):
    def change():
        if drift == "task":
            edges.observation = {"status": "ABSENT"}
        elif drift == "runtime":
            edges.drift = "runtime"
        else:
            (
                binding.PAPER_PATH if drift == "paper" else binding.STATE_PATH
            ).write_bytes(b"drift")

    edges.after_register = change
    result = execute(edges)
    assert result["status"] == "INDETERMINATE"
    assert edges.registrations == 1


@pytest.mark.parametrize(
    "args",
    [
        ["--session", "2026-10-09"],
        ["plan", "--task", "evil"],
        ["plan", "--path", "evil"],
        ["execute-once", "--principal", "evil"],
        ["execute-once", "--reviewed-plan-sha256", "a" * 64, "--retry"],
        ["retry"],
        [],
    ],
)
def test_no_caller_injection(edges, args, capsys):
    assert scheduler.main(args) == 3
    assert edges.admissions == 0
    assert "evil" not in capsys.readouterr().out


def test_password_requires_console_before_getpass(monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "_require_interactive_console",
        lambda: (_ for _ in ()).throw(ValueError()),
    )
    monkeypatch.setattr(
        scheduler.getpass, "getpass", lambda *a: pytest.fail("password read")
    )
    with pytest.raises(ValueError):
        scheduler._read_password()


def test_redirected_console_rejected(monkeypatch):
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: True))
    with pytest.raises(ValueError):
        scheduler._require_interactive_console()


def test_private_stdin_no_secret_argv_environment_or_evidence(monkeypatch):
    captured = []

    def run(argv, **kwargs):
        captured.append((argv, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout=scheduler.canonical(
                {
                    "schema": scheduler.INSTALL_SCHEMA,
                    "disposition": "CALL_RETURNED",
                    "registration_attempts": 1,
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", run)
    request = {"password": SECRET}
    scheduler._native("arch133_scheduler_install.ps1", request)
    argv, kwargs = captured[0]
    assert SECRET not in str(argv) and SECRET not in str(kwargs["env"])
    assert SECRET in kwargs["input"] and kwargs["input"].endswith("\n")
    assert request["password"] is None
    assert kwargs["capture_output"] and kwargs["timeout"] == 30


def test_unstable_double_read_blocks(edges, monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "_native",
        lambda *a: {
            "schema": scheduler.OBSERVE_SCHEMA,
            "first": {"status": "ABSENT"},
            "second": {"status": "PRESENT"},
        },
    )
    result = scheduler.operate("plan")
    assert (
        result["status"] == "BLOCKED" and edges.credentials == edges.registrations == 0
    )


def test_success_requires_stable_double_post_readback(edges, monkeypatch):
    native = scheduler._native

    def unstable(script, request=None):
        value = native(script, request)
        if script.endswith("observe.ps1") and edges.registrations:
            value["second"]["xml_sha256"] = "c" * 64
        return value

    monkeypatch.setattr(scheduler, "_native", unstable)
    result = execute(edges)
    assert result["status"] == "INDETERMINATE" and edges.registrations == 1


def test_semantic_xml_whitespace_and_complete_field_drift(edges):
    spec = specification.build_unattended_scheduler_spec(
        operator.ReviewPaperActivation.from_json(edges.act.to_json())
    )
    xml = scheduler.TASK_XML.format(
        start=scheduler.boundary(spec.start_boundary),
        end=scheduler.boundary(spec.end_boundary),
    )
    baseline = scheduler.xml_fingerprint(xml)
    assert scheduler.xml_fingerprint(xml.replace("><", ">\n  <")) == baseline
    for old, new in [
        ("<Enabled>false", "<Enabled>true"),
        ("IgnoreNew", "Parallel"),
        ("Password", "S4U"),
        ("LeastPrivilege", "HighestAvailable"),
        ("<Priority>7", "<Priority>8"),
        ("<AllowStartOnDemand>false", "<AllowStartOnDemand>true"),
        ("<ExecutionTimeLimit>PT1H", "<ExecutionTimeLimit>PT0S"),
        ("<RunOnlyIfIdle>false", "<RunOnlyIfIdle>true"),
        ("<WakeToRun>false", "<WakeToRun>true"),
        ("<Hidden>false", "<Hidden>true"),
        ("<StartWhenAvailable>false", "<StartWhenAvailable>true"),
        ("<RunOnlyIfNetworkAvailable>false", "<RunOnlyIfNetworkAvailable>true"),
        ("<DisallowStartIfOnBatteries>true", "<DisallowStartIfOnBatteries>false"),
        ("<StopIfGoingOnBatteries>true", "<StopIfGoingOnBatteries>false"),
        ("</Triggers>", "<BootTrigger/></Triggers>"),
        (
            "</Settings>",
            "<RestartOnFailure><Interval>PT1M</Interval><Count>1</Count></RestartOnFailure></Settings>",
        ),
        (
            "</TimeTrigger>",
            "<Repetition><Interval>PT1M</Interval></Repetition></TimeTrigger>",
        ),
        ("-I -B", "-I -B --injected"),
    ]:
        assert old in xml
        assert scheduler.xml_fingerprint(xml.replace(old, new)) != baseline, old


def test_native_scripts_fixed_create_only_and_full_xml_contract():
    scripts = {
        name: (ROOT / "scripts" / f"arch133_scheduler_{name}.ps1").read_text(
            encoding="utf-8"
        )
        for name in ("definition", "observe", "install")
    }
    all_source = "\n".join(scripts.values())
    assert all_source.count(".RegisterTaskDefinition(") == 1
    assert "$definition, 2," in scripts["install"]
    assert "$password, 1, $null" in scripts["install"]
    for forbidden in (
        "TASK_CREATE_OR_UPDATE",
        "DeleteTask",
        ".Run(",
        "Start-ScheduledTask",
        "schtasks",
        ".Stop(",
        ".Enabled =",
        "Invoke-Expression",
        "Get-Credential",
        "D10",
    ):
        assert forbidden not in all_source
    assert (
        "$args.Count -ne 0" in scripts["observe"]
        and "$args.Count -ne 0" in scripts["install"]
    )
    assert scripts["observe"].count("Read-FixedTask\n") == 2
    assert scripts["install"].count("Read-FixedTask\n") == 2
    template = (
        scripts["definition"].split("    return @'\n", 1)[1].split("\n'@.Replace", 1)[0]
    )
    assert (
        template.replace("$START$", "{start}").replace("$END$", "{end}")
        == scheduler.TASK_XML
    )


def test_fresh_import_closure_no_effect_modules(tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import ctypes,json,sys\n"
        "sys.path.insert(0,sys.argv[1])\n"
        "def reject(*a,**k): raise AssertionError('native import')\n"
        "ctypes.WinDLL=reject\n"
        "import trading_bot.arch133_scheduler_installation.operator\n"
        "print(json.dumps(sorted(n for n in sys.modules "
        "if n.startswith('trading_bot'))))\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(probe), str(ROOT / "src")],
        capture_output=True,
        text=True,
        check=True,
    )
    names = json.loads(result.stdout)
    assert not any(
        name.startswith(
            (
                "trading_bot.review_paper",
                "trading_bot.runtime",
                "trading_bot.robinhood",
                "trading_bot.arch133_publication",
                "trading_bot.arch133_diagnostic",
            )
        )
        for name in names
    )
    assert "trading_bot.arch133_verifier.credentials" not in names
    from scripts import checkpoint_runner as runner

    assert names == sorted(runner.ARCH133_SCHEDULER_MODULES)
    forbidden = {
        "run_unattended_host",
        "execute_one_unattended_review_paper_wake",
        "ReviewPaperStore",
        "UnattendedStateStore",
        "transition_review_paper_wake",
        "WindowsOAuthStorage",
        "CredReadW",
        "CredWriteW",
        "MCPClient",
        "set_tokens",
        "place_equity_order",
        "cancel_equity_order",
    }
    for name in names:
        path = ROOT / "src" / Path(*name.split("."))
        path = path / "__init__.py" if path.is_dir() else path.with_suffix(".py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
            n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
        }
        assert not found & forbidden, name


@pytest.mark.parametrize(
    "args",
    [
        ["plan"],
        ["execute-once", "--reviewed-plan-sha256", "a" * 64],
        ["plan", "--path", "evil"],
    ],
)
def test_copied_launcher_rejected_before_import(tmp_path, args):
    copy = tmp_path / "launcher.py"
    copy.write_text(
        (ROOT / "scripts/run_arch133_scheduler_installation.py").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(copy), *args], capture_output=True, text=True
    )
    assert (
        result.returncode == 3
        and result.stdout == "ARCH133P_RUNTIME_BLOCKED\n"
        and not result.stderr
    )


def test_registration_guard_holds_four_deny_write_handles(fake):
    fake.calls.clear()
    with operator.registration_guard():
        assert not any(isinstance(c, tuple) and c[0] == "close" for c in fake.calls)
    assert len([c for c in fake.calls if isinstance(c, tuple) and c[0] == "close"]) == 5


@pytest.fixture
def native_fixture(tmp_path, request):
    # Every native command in this external fixture is a fake. No production
    # transport is invoked; the copied script cannot construct real COM.
    for name in ("definition", "observe", "install"):
        source = (ROOT / "scripts" / f"arch133_scheduler_{name}.ps1").read_text(
            encoding="utf-8"
        )
        if name == "install":
            # A distinct fake name cannot be shadowed by module command imports.
            assert source.count("Get-FileHash -LiteralPath") == 1
            source = source.replace(
                "Get-FileHash -LiteralPath", "Get-FakeActivationHash -LiteralPath"
            )
            assert "Get-FileHash" not in source
            source = source.replace(
                "[Security.Principal.WindowsIdentity]::GetCurrent()",
                "$global:FakeIdentity",
            )
            # Only this copied fake transport reports a bounded failure location.
            # Never emit the exception message or request/credential material.
            source = source.replace(
                "} catch {\n    if ($attempted)",
                "} catch {\n"
                "    [Console]::Error.WriteLine('FAKE_INSTALLER_STAGE=' + "
                "[string]$_.InvocationInfo.ScriptLineNumber + ';TYPE=' + "
                "$_.Exception.GetType().FullName)\n"
                "    if ($attempted)",
            )
            if getattr(request, "param", False):
                # Newer Windows JSON parsers may coerce ISO UTC strings.
                source = source.replace(
                    "$request = $line | ConvertFrom-Json",
                    "$request = $line | ConvertFrom-Json\n"
                    "$request.start_boundary = [DateTime]::Parse("
                    "$request.start_boundary)\n"
                    "$request.end_boundary = [DateTime]::Parse("
                    "$request.end_boundary)",
                )
        (tmp_path / f"arch133_scheduler_{name}.ps1").write_text(
            source, encoding="utf-8"
        )
    wrapper = tmp_path / "fake_native.ps1"
    wrapper.write_text(
        r"""
param([string]$Mode)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$global:FakeIdentity = [pscustomobject]@{
    Name='DESKTOP-I4DOKM7\Trading'
    User=[pscustomobject]@{Value='S-1-5-21-1397534616-3988210162-180023805-1009'}
}
$global:FakeCalls = 0
$global:FakeHashReads = 0
function Get-FakeActivationHash {
    param([string]$LiteralPath, [string]$Algorithm)
    if ($LiteralPath -cne 'F:\AITradingBot\Arch133\activation.json' -or
        $Algorithm -cne 'SHA256') { throw 'unexpected file access' }
    $global:FakeHashReads += 1
    $hashCountPath = Join-Path $PSScriptRoot 'hash-count.txt'
    [IO.File]::WriteAllText($hashCountPath, [string]$global:FakeHashReads)
    return [pscustomobject]@{
        Hash='37873b490c3f2ccced53431c599e40ca54fdc008e09e9bfdb38eb61d10f3cab2'
    }
}
function New-Object {
    param([string]$ComObject)
    if ($ComObject -cne 'Schedule.Service') { throw 'unexpected COM' }
    $service = [pscustomobject]@{}
    $service | Add-Member ScriptMethod Connect {
        if ($args.Count) { throw 'remote forbidden' }
    }
    $service | Add-Member ScriptMethod GetFolder {
        param($path)
        if ($path -cne '\') { throw 'folder forbidden' }
        $folder = [pscustomobject]@{}
        $folder | Add-Member ScriptMethod GetTask {
            param($name)
            if ($name -cne 'AITradingBot-Arch133-SingleSessionReviewPaper-v1') {
                throw 'task forbidden'
            }
            if ($global:FakeMode -in @('absent','create','create-exception','stale')) {
                throw [Runtime.InteropServices.COMException]::new('absent',-2147024894)
            }
            $xml = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'task.xml'))
            return [pscustomobject]@{
                Path='\AITradingBot-Arch133-SingleSessionReviewPaper-v1'
                Xml=$xml;State=1
            }
        }
        $folder | Add-Member ScriptMethod RegisterTaskDefinition {
            param($name,$definition,$flags,$sid,$secret,$logon,$sddl)
            if ($name -cne 'AITradingBot-Arch133-SingleSessionReviewPaper-v1' -or
                $flags -ne 2 -or $sid -cne $global:FakeIdentity.User.Value -or
                $logon -ne 1 -or $secret -cne 'fake-native-test-secret' -or
                $null -ne $sddl) { throw 'registration contract drift' }
            $global:FakeCalls += 1
            $counterPath = Join-Path $PSScriptRoot 'call-count.txt'
            [IO.File]::WriteAllText($counterPath, [string]$global:FakeCalls)
            if ($global:FakeMode -ceq 'create-exception') {
                throw 'fake ambiguous native result'
            }
        }
        return $folder
    }
    $service | Add-Member ScriptMethod NewTask {
        param($flags)
        if ($flags -ne 0) { throw 'definition flags invalid' }
        return [pscustomobject]@{XmlText=''}
    }
    return $service
}
$global:FakeMode = $Mode
if ($Mode -in @('create','create-exception','stale','present-install')) {
    & (Join-Path $PSScriptRoot 'arch133_scheduler_install.ps1')
} else {
    & (Join-Path $PSScriptRoot 'arch133_scheduler_observe.ps1')
}
exit $LASTEXITCODE
""",
        encoding="utf-8",
    )
    return tmp_path, wrapper


@pytest.mark.parametrize("mode", ["absent", "present"])
def test_fake_com_observer_and_cross_language_fingerprint(native_fixture, mode):
    temp, wrapper = native_fixture
    xml = scheduler.TASK_XML.format(
        start="2026-10-09T13:35:00.000000Z", end="2026-10-09T19:55:00.000000Z"
    )
    (temp / "task.xml").write_text(xml, encoding="utf-8")
    result = subprocess.run(
        [
            scheduler.POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(wrapper),
            mode,
        ],
        input="",
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert not result.stderr and result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["first"] == data["second"]
    if mode == "absent":
        assert data["first"] == {"status": "ABSENT"}
    else:
        assert data["first"]["projection_sha256"] == scheduler.xml_fingerprint(xml)
        assert (
            data["first"]["xml_sha256"]
            == hashlib.sha256((temp / "task.xml").read_bytes()).hexdigest()
        )
    assert not (temp / "call-count.txt").exists()


@pytest.mark.parametrize("native_fixture", [False, True], indirect=True)
@pytest.mark.parametrize(
    "mode", ["create", "create-exception", "stale", "present-install"]
)
def test_fake_com_installer_exact_one_create_or_no_call(native_fixture, mode):
    temp, wrapper = native_fixture
    # Future synthetic boundaries only, sent over the fake private pipe.
    start = datetime.now(UTC) + (
        timedelta(days=1) if mode != "stale" else -timedelta(days=1)
    )
    end = start + timedelta(hours=1)
    (temp / "task.xml").write_text(
        scheduler.TASK_XML.format(
            start=scheduler.boundary(start), end=scheduler.boundary(end)
        ),
        encoding="utf-8",
    )
    request = {
        "activation_sha256": (
            "37873b490c3f2ccced53431c599e40ca54fdc008e09e9bfdb38eb61d10f3cab2"
        ),
        "start_boundary": scheduler.boundary(start),
        "end_boundary": scheduler.boundary(end),
        "password": "fake-native-test-secret",
    }
    result = subprocess.run(
        [
            scheduler.POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(wrapper),
            mode,
        ],
        input=scheduler.canonical(request) + "\n",
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode == (2 if mode == "create-exception" else 1):
        # Expected fake exceptions report only a source line and exception type.
        assert result.stderr.startswith("FAKE_INSTALLER_STAGE="), result.stderr
        assert "fake-native-test-secret" not in result.stderr
    else:
        assert not result.stderr, result.stderr
    data = json.loads(result.stdout)
    assert "fake-native-test-secret" not in result.stdout
    if mode == "create":
        assert result.returncode == 0 and data["disposition"] == "CALL_RETURNED", (
            result.stderr
        )
    elif mode == "create-exception":
        assert result.returncode == 2 and data["disposition"] == "INDETERMINATE"
    else:
        assert result.returncode == 1 and data["disposition"] == "NOT_CALLED"
    count = 1 if mode.startswith("create") else 0
    assert data["registration_attempts"] == count
    calls = temp / "call-count.txt"
    assert (int(calls.read_text()) if calls.exists() else 0) == count
    hashes = temp / "hash-count.txt"
    assert (int(hashes.read_text()) if hashes.exists() else 0) == count


def test_133p_source_checkpoint_has_no_protected_callbacks():
    from scripts import checkpoint_runner as runner

    name = "arch133-robinhood-single-session-scheduler-installation"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133p"
    assert runner.ACTIVE_CI_CHECKPOINTS[-5:-3] == (
        "arch133-robinhood-publication-state-paper-corrected",
        name,
    )
    assert runner._arch133_scheduler_installation_authority_check(ROOT) == ()


@pytest.fixture
def authority_copy(tmp_path, monkeypatch):
    # P's local pin/capability checks remain real. O and the complete
    # predecessor chain have dedicated PASS and rejection proofs.
    monkeypatch.setattr(
        runner, "_arch133_publication_corrected_authority_check", lambda _: ()
    )
    for relative in (
        *runner.ARCH133_SCHEDULER_PINS,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    return tmp_path


@pytest.fixture
def workflow_authority_copy(authority_copy, monkeypatch):
    # Runner-file ordering delegates to H's whole-batch check. Keep that real
    # validation alongside P's local workflow check; full chaining is separate.
    monkeypatch.setattr(
        runner,
        "_arch133_publication_corrected_authority_check",
        runner._arch133_host_publication_authority_check,
    )
    for relative in runner.ARCH133_PUBLICATION_PINS:
        destination = authority_copy / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    return authority_copy


_ORIGINAL_133P_PIN_CASES = [
    "src/trading_bot/arch133_scheduler_installation/operator.py",
    "src/trading_bot/arch133_scheduler_installation/admission.py",
    "src/trading_bot/arch133_scheduler_installation/specification.py",
    "scripts/arch133_scheduler_definition.ps1",
    "scripts/arch133_scheduler_observe.ps1",
    "scripts/arch133_scheduler_install.ps1",
    "scripts/run_arch133_scheduler_installation.py",
    "src/trading_bot/review_paper/unattended_scheduler.py",
]


@pytest.mark.parametrize(
    "relative",
    tuple(dict.fromkeys((*_ORIGINAL_133P_PIN_CASES, *runner.ARCH133_SCHEDULER_PINS))),
)
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133p_source_pins_fail_closed(authority_copy, relative, mutation):
    from scripts import checkpoint_runner as runner

    path = authority_copy / relative
    if mutation == "missing":
        path.unlink()
    else:
        with path.open("a", encoding="utf-8") as target:
            target.write(
                "\nUNREVIEWED = True\n"
                if path.suffix == ".py"
                else "\n# changed native transport\n"
            )
    assert runner._arch133_scheduler_installation_authority_check(authority_copy)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133p_registration_workflow_drift_fails_closed(
    workflow_authority_copy, target, mutation
):
    from scripts import checkpoint_runner as runner

    path = workflow_authority_copy / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    name = "arch133-robinhood-single-session-scheduler-installation"
    prior = "arch133-robinhood-publication-state-paper-corrected"
    line = f'    "{name}",\n' if target == "runner" else f"              {name} `\n"
    previous = (
        f'    "{prior}",\n' if target == "runner" else f"              {prior} `\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        text = text.replace(previous + line, line + previous)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_scheduler_installation_authority_check(
        workflow_authority_copy
    )


@pytest.mark.parametrize(
    "field",
    [
        "preflight",
        "execute",
        "remote_head_env",
        "remote_branch",
        "tests",
        "ruff_paths",
        "authority_check",
    ],
)
def test_133p_registration_capability_injection(authority_copy, monkeypatch, field):
    from scripts import checkpoint_runner as runner

    name = "arch133-robinhood-single-session-scheduler-installation"
    specs = runner._checkpoint_specs()
    value = (
        (lambda *a: pytest.fail("protected callback"))
        if field in ("preflight", "execute", "authority_check")
        else (() if field in ("tests", "ruff_paths") else "injected")
    )
    specs[name] = replace(specs[name], **{field: value})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_scheduler_installation_authority_check(authority_copy)


@pytest.mark.parametrize(
    "exit_code,disposition,attempts",
    [
        (2, "CALL_RETURNED", 1),
        (0, "INDETERMINATE", 1),
        (0, "CALL_RETURNED", True),
        (1, "CALL_RETURNED", 1),
        (0, "NOT_CALLED", 0),
    ],
)
def test_native_exit_acknowledgement_disagreement_blocks(
    monkeypatch, exit_code, disposition, attempts
):
    data = {
        "schema": scheduler.INSTALL_SCHEMA,
        "disposition": disposition,
        "registration_attempts": attempts,
    }
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=exit_code, stdout=scheduler.canonical(data), stderr=""
        ),
    )
    request = {"password": "fake-pipe-secret"}
    with pytest.raises(ValueError):
        scheduler._native("arch133_scheduler_install.ps1", request)
    assert request["password"] is None


def test_copied_local_scheduler_authority_baseline_passes(authority_copy):
    assert runner._arch133_scheduler_installation_authority_check(authority_copy) == ()


@pytest.mark.parametrize("failure", [(), ("predecessor rejected",)])
def test_scheduler_predecessor_called_once_and_rejection_propagates(
    monkeypatch, failure
):
    seen = []

    def previous(root):
        seen.append(root)
        return failure

    monkeypatch.setattr(
        runner, "_arch133_publication_corrected_authority_check", previous
    )
    assert runner._arch133_scheduler_installation_authority_check(ROOT) == failure
    assert seen == [ROOT]


def test_copied_workflow_scheduler_authority_baseline_passes(workflow_authority_copy):
    assert (
        runner._arch133_scheduler_installation_authority_check(workflow_authority_copy)
        == ()
    )
