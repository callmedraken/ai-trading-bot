"""D1R6 source tests: fake host edges and disposable journals only."""

from __future__ import annotations

import ast
import copy
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import checkpoint_runner as runner
from scripts import run_test_certification as certification
from trading_bot.review_paper import pre_market_wake_overnight as q
from trading_bot.review_paper import pre_market_wake_overnight_host as host
from trading_bot.review_paper import pre_market_wake_qualification as d1r5

HEAD, TREE = "a" * 40, "b" * 40
OBSERVED = datetime(2026, 10, 15, 3, tzinfo=UTC)
PRINCIPAL = q.Principal(r"DESKTOP\Owner", "S-1-5-21-1-2-3-1001")
ROOT = Path(__file__).resolve().parents[2]


class Fake:
    def __init__(self, tmp_path):
        self.parent = tmp_path / "qualification"
        self.parent.mkdir()
        self.now = OBSERVED
        self.identity = PRINCIPAL
        self.task = {"status": "ABSENT"}
        self.creates = self.children = self.reads = self.sources = self.targets = 0
        self.on_create = None

    def source(self, head, tree):
        assert (head, tree) == (HEAD, TREE)
        self.sources += 1
        return (self.parent.parent / "repository",)

    def target(self):
        self.targets += 1
        return (self.parent.parent / "predecessor",)

    def clock(self):
        return self.now

    def principal(self):
        return self.identity

    def observe(self):
        self.reads += 1
        return copy.deepcopy(self.task)

    def create(self, plan):
        # Read back the physical bytes inside the fake native entry seam.
        records = q.parse_arm((self.parent / plan.arm_name).read_bytes())
        assert records[-1]["event"] == "TASK_CREATE_INTENT"
        self.creates += 1
        if self.on_create:
            return self.on_create(plan)
        self.task = {
            "status": "PRESENT",
            "task": plan.task,
            "state": 3,
            "last_result": 0,
        }
        return {"disposition": "CALL_RETURNED", "registration_attempts": 1}

    def child(self, plan):
        self.children += 1
        return 7


@pytest.fixture
def fake(tmp_path):
    return Fake(tmp_path)


def plan():
    return q.Plan(HEAD, TREE, OBSERVED, PRINCIPAL)


def armed(fake):
    assert q.arm(fake, HEAD, TREE, q.ARM_INTERLOCK) == "ARMED"
    return plan()


@pytest.mark.parametrize(
    "observed,day,trigger,close",
    [
        ("2026-10-15T03:00:00+00:00", "2026-10-15", "2026-10-15T13:20:00+00:00", 20),
        ("2026-03-08T20:00:00+00:00", "2026-03-09", "2026-03-09T13:20:00+00:00", 20),
        ("2026-11-01T23:00:00+00:00", "2026-11-02", "2026-11-02T14:20:00+00:00", 21),
        ("2026-11-26T23:00:00+00:00", "2026-11-27", "2026-11-27T14:20:00+00:00", 18),
        ("2026-12-23T23:00:00+00:00", "2026-12-24", "2026-12-24T14:20:00+00:00", 18),
    ],
)
def test_published_session_timing(observed, day, trigger, close):
    value = q.Plan(HEAD, TREE, datetime.fromisoformat(observed), PRINCIPAL)
    assert value.schedule.session_date.isoformat() == day
    assert value.trigger.isoformat() == trigger
    assert value.end - value.trigger == timedelta(minutes=15)
    assert value.schedule.closes_at.hour == close
    assert value.trigger == value.schedule.opens_at - timedelta(minutes=10)


@pytest.mark.parametrize(
    "observed,valid",
    [
        ("2026-10-14T19:20:00+00:00", True),
        ("2026-10-14T19:19:59.999999+00:00", False),
        ("2026-10-15T13:19:59.999999+00:00", True),
        ("2026-10-15T13:20:00+00:00", False),
        ("2026-10-16T23:00:00+00:00", False),
        ("2026-09-06T23:00:00+00:00", False),
        ("2026-12-24T23:00:00+00:00", False),
        ("2029-01-01T03:00:00+00:00", False),
    ],
)
def test_horizon_and_no_eligible_session(observed, valid):
    if valid:
        assert q.Plan(HEAD, TREE, datetime.fromisoformat(observed), PRINCIPAL).schedule
    else:
        with pytest.raises(ValueError):
            q.Plan(HEAD, TREE, datetime.fromisoformat(observed), PRINCIPAL)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_head", "0" * 40),
        ("source_tree", True),
        ("observed_at", datetime(2026, 10, 15)),
        ("principal", None),
    ],
)
def test_plan_rejects_invalid_authority(field, value):
    values = dict(
        source_head=HEAD, source_tree=TREE, observed_at=OBSERVED, principal=PRINCIPAL
    )
    values[field] = value
    with pytest.raises((ValueError, TypeError)):
        q.Plan(**values)


@pytest.mark.parametrize(
    "name,sid",
    [
        ("Owner", PRINCIPAL.sid),
        ("D\\x\n", PRINCIPAL.sid),
        (PRINCIPAL.name, "S-1-5-18"),
        (True, PRINCIPAL.sid),
        (PRINCIPAL.name, True),
    ],
)
def test_principal_boundary(name, sid):
    with pytest.raises(ValueError):
        q.Principal(name, sid)


def test_frozen_task_contract():
    task = plan().task
    assert task == {
        "task_path": r"\AITradingBot-Arch134-D1R6-OvernightWake-v1",
        "trigger_count": 1,
        "trigger_type": 1,
        "start_boundary": "2026-10-15T13:20:00+00:00",
        "end_boundary": "2026-10-15T13:35:00+00:00",
        "trigger_enabled": True,
        "repetition_interval": "",
        "repetition_duration": "",
        "repetition_stop": False,
        "random_delay": "",
        "principal_sid": PRINCIPAL.sid,
        "logon_type": 3,
        "run_level": 0,
        "action_count": 1,
        "action_type": 0,
        "command": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "arguments": (
            "-NoProfile -NonInteractive -ExecutionPolicy Bypass "
            '-File "F:\\AI\\worktrees\\'
            "ai-trading-bot-production-paper-overnight-wake-arming\\scripts\\"
            'arch134_d1r6_task_launcher.ps1"'
        ),
        "working_directory": str(q.WORKTREE),
        "enabled": True,
        "wake_to_run": True,
        "start_when_available": False,
        "restart_count": 0,
        "restart_interval": "",
        "allow_demand_start": False,
        "run_only_if_idle": False,
        "run_only_if_network_available": False,
        "disallow_start_if_on_batteries": False,
        "stop_if_going_on_batteries": False,
        "hidden": False,
        "multiple_instances": 2,
        "execution_time_limit": "PT20M",
        "allow_hard_terminate": True,
        "idle_stop": False,
        "idle_restart": False,
    }
    assert "D10" not in task["task_path"] and "PD4" not in task["task_path"]
    assert set(q.IMPLEMENTATION_ZERO_EFFECTS) >= {
        "REAL_SCHEDULER_READS",
        "REAL_SCHEDULER_MUTATIONS",
        "REAL_D1R5_EXECUTIONS",
        "REAL_CLOCK_SLEEPS",
    }


def test_preflight_is_read_only(fake):
    assert q.preflight(fake, HEAD, TREE) == plan()
    assert list(fake.parent.iterdir()) == []
    assert fake.creates == fake.children == 0


@pytest.mark.parametrize("collision", ["arm", "other_source_arm", "result", "task"])
def test_consumed_preflight_and_arm_block(fake, collision):
    value = plan()
    if collision == "arm":
        (fake.parent / value.arm_name).write_bytes(b"")
    elif collision == "other_source_arm":
        (
            fake.parent / (value.arm_prefix + "c" * 40 + "-" + "d" * 40 + ".jsonl")
        ).write_bytes(b"partial")
    elif collision == "result":
        (fake.parent / value.result_name).write_bytes(b"")
    else:
        fake.task = {"status": "UNKNOWN"}
    before = sorted(p.name for p in fake.parent.iterdir())
    with pytest.raises(ValueError):
        q.preflight(fake, HEAD, TREE)
    assert q.arm(fake, HEAD, TREE, q.ARM_INTERLOCK) == "BLOCKED"
    assert sorted(p.name for p in fake.parent.iterdir()) == before
    assert fake.creates == 0


@pytest.mark.parametrize(
    "boundary", ["source", "target", "principal", "clock", "observe"]
)
def test_preflight_failures_have_zero_mutation(fake, monkeypatch, boundary):
    def fail(*args):
        raise ValueError("sensitive exception text")

    monkeypatch.setattr(fake, boundary, fail)
    assert q.arm(fake, HEAD, TREE, q.ARM_INTERLOCK) == "BLOCKED"
    assert list(fake.parent.iterdir()) == [] and fake.creates == 0


@pytest.mark.parametrize(
    "interlock", [None, "", "AUTHORIZE", q.ARM_INTERLOCK[:-1], True]
)
def test_exact_arm_interlock(fake, interlock):
    assert q.arm(fake, HEAD, TREE, interlock) == "BLOCKED"
    assert fake.sources == fake.targets == fake.reads == fake.creates == 0


def test_successful_arm_is_one_fenced_attempt(fake):
    value = armed(fake)
    records = q.parse_arm((fake.parent / value.arm_name).read_bytes())
    assert [r["event"] for r in records] == [*q.EVENTS, "FINAL"]
    assert records[-1]["classification"] == "ARMED"
    assert all(r["facts"] == value.facts for r in records)
    assert fake.creates == 1 and fake.children == 0
    assert q.arm(fake, HEAD, TREE, q.ARM_INTERLOCK) == "BLOCKED"
    assert fake.creates == 1


@pytest.mark.parametrize(
    "response",
    [
        None,
        {},
        {"disposition": "NOT_CALLED", "registration_attempts": 0},
        {"disposition": "CALL_RETURNED", "registration_attempts": True},
        {"disposition": "CALL_RETURNED", "registration_attempts": 2},
    ],
)
def test_ambiguous_native_result_consumed_no_retry(fake, response):
    fake.on_create = lambda p: response
    assert q.arm(fake, HEAD, TREE, q.ARM_INTERLOCK) == "INDETERMINATE"
    assert fake.creates == 1
    assert (
        q.parse_arm((fake.parent / plan().arm_name).read_bytes())[-1]["classification"]
        == "INDETERMINATE"
    )
    assert q.arm(fake, HEAD, TREE, q.ARM_INTERLOCK) == "BLOCKED"
    assert fake.creates == 1


def test_exception_after_entry_consumed(fake):
    def fail(p):
        raise RuntimeError("untrusted native exception")

    fake.on_create = fail
    assert q.arm(fake, HEAD, TREE, q.ARM_INTERLOCK) == "INDETERMINATE"
    assert fake.creates == 1


@pytest.mark.parametrize("field", list(plan().task))
def test_every_task_setting_drift_fails_closed(fake, field):
    def drift(p):
        task = p.task
        task[field] = None
        fake.task = {"status": "PRESENT", "task": task, "state": 3, "last_result": 0}
        return {"disposition": "CALL_RETURNED", "registration_attempts": 1}

    fake.on_create = drift
    assert q.arm(fake, HEAD, TREE, q.ARM_INTERLOCK) == "INDETERMINATE"
    assert fake.creates == 1


def test_second_post_create_observation_must_match(fake, monkeypatch):
    original = fake.observe

    def observe():
        result = original()
        if fake.creates and fake.reads >= 5:
            result["task"]["wake_to_run"] = False
        return result

    monkeypatch.setattr(fake, "observe", observe)
    assert q.arm(fake, HEAD, TREE, q.ARM_INTERLOCK) == "INDETERMINATE"
    assert fake.creates == 1


@pytest.mark.parametrize("point", [1, 2, 3, 4, 5, 6, 7, 8])
def test_fsync_failure_never_retries_or_exceeds_budget(fake, monkeypatch, point):
    calls = 0

    def sync(fd):
        nonlocal calls
        calls += 1
        if calls == point:
            raise OSError("durability failed")

    monkeypatch.setattr(q.os, "fsync", sync)
    result = q.arm(fake, HEAD, TREE, q.ARM_INTERLOCK)
    assert result in {"BLOCKED", "INDETERMINATE"}
    assert calls == point
    assert fake.creates == int(point >= 6)
    assert q.arm(fake, HEAD, TREE, q.ARM_INTERLOCK) == "BLOCKED"


@pytest.mark.parametrize("step", ["source", "target", "principal", "clock", "observe"])
def test_last_readmission_failure_prevents_native_entry(fake, monkeypatch, step):
    original = getattr(fake, step)
    calls = 0

    def boundary(*args):
        nonlocal calls
        calls += 1
        threshold = {
            "source": 3,
            "target": 3,
            "principal": 2,
            "clock": 2,
            "observe": 3,
        }[step]
        if calls == threshold:
            raise ValueError("drift")
        return original(*args)

    monkeypatch.setattr(fake, step, boundary)
    assert q.arm(fake, HEAD, TREE, q.ARM_INTERLOCK) == "BLOCKED"
    assert fake.creates == 0


@pytest.mark.parametrize("index", range(1, 9))
def test_canonical_prefixes_and_only_final_launch(fake, index):
    value = armed(fake)
    path = fake.parent / value.arm_name
    records = q.parse_arm(path.read_bytes())
    prefix = records[:index]
    payload = q.serialize_arm(prefix)
    assert payload.endswith(b"\n") and q.parse_arm(payload) == prefix
    path.write_bytes(payload)
    if index < 8:
        with pytest.raises(ValueError):
            q.launch(fake, HEAD, TREE)
        assert q.reconcile(fake, HEAD, TREE)["disposition"] == "ARM_EVIDENCE_INVALID"
    else:
        assert q.launch(fake, HEAD, TREE) == 7


@pytest.mark.parametrize(
    "kind",
    [
        "unknown",
        "missing",
        "counter_bool",
        "counter_nonzero",
        "calls_bool",
        "event",
        "schema",
        "head",
        "target",
        "session",
        "trigger",
        "settings",
        "principal",
        "facts_change",
        "order",
        "classification",
    ],
)
def test_closed_evidence_rejects_drift(fake, kind):
    value = armed(fake)
    records = copy.deepcopy(q.parse_arm((fake.parent / value.arm_name).read_bytes()))
    record = records[0]
    if kind == "unknown":
        record["extra"] = 1
    elif kind == "missing":
        del record["facts"]
    elif kind == "counter_bool":
        record["effects"][q.ZERO_EFFECTS[0]] = False
    elif kind == "counter_nonzero":
        record["effects"][q.ZERO_EFFECTS[0]] = 1
    elif kind == "calls_bool":
        record["scheduler_task_create_calls"] = False
    elif kind == "event":
        record["event"] = "TASK_CREATE_INTENT"
    elif kind == "schema":
        record["schema"] = "other/v1"
    elif kind == "head":
        record["facts"]["source_head"] = "x" * 40
    elif kind == "target":
        record["facts"]["target_head"] = "c" * 40
    elif kind == "session":
        record["facts"]["target_session"] = "2026-10-16"
    elif kind == "trigger":
        record["facts"]["task"]["start_boundary"] = record["facts"]["admission_open"]
    elif kind == "settings":
        record["facts"]["task"]["start_when_available"] = True
    elif kind == "principal":
        record["facts"]["principal_sid"] = "S-1-5-18"
    elif kind == "facts_change":
        records[2]["facts"]["source_tree"] = "c" * 40
    elif kind == "order":
        records = (records[1], records[0], *records[2:])
    elif kind == "classification":
        records[-1]["classification"] = "PASS"
    raw = b"".join(q.canonical(r) + b"\n" for r in records)
    with pytest.raises(ValueError):
        q.parse_arm(raw)


@pytest.mark.parametrize(
    "kind",
    [
        "empty",
        "bom",
        "space",
        "crlf",
        "missing_lf",
        "trailing",
        "oversize",
        "duplicate",
        "partial",
    ],
)
def test_noncanonical_evidence(fake, kind):
    value = armed(fake)
    payload = (fake.parent / value.arm_name).read_bytes()
    payload = {
        "empty": b"",
        "bom": b"\xef\xbb\xbf" + payload,
        "space": b" " + payload,
        "crlf": payload.replace(b"\n", b"\r\n"),
        "missing_lf": payload[:-1],
        "trailing": payload + b"\n",
        "oversize": b"x" * (q.MAX_BYTES + 1),
        "duplicate": payload.replace(b'"schema":', b'"schema":"x","schema":', 1),
        "partial": payload[:80],
    }[kind]
    with pytest.raises(ValueError):
        q.parse_arm(payload)


def test_launch_and_exact_child_invocation(fake, monkeypatch):
    value = armed(fake)
    assert q.launch(fake, HEAD, TREE) == 7
    assert fake.children == 1
    calls = []
    monkeypatch.setattr(
        host.subprocess,
        "run",
        lambda argv, **kw: calls.append((argv, kw)) or SimpleNamespace(returncode=9),
    )
    assert host._WindowsRuntime().child(value) == 9
    argv, kwargs = calls[0]
    assert argv == [
        str(q.PYTHON),
        "-I",
        "-B",
        str(q.WORKTREE / "scripts" / "arch134_d1r6_d1r5_child.py"),
        "--expected-head",
        q.TARGET_HEAD,
        "--expected-tree",
        q.TARGET_TREE,
        "--evidence",
        str(q.QUALIFICATION_PARENT / value.result_name),
        "--qualify-wake",
        d1r5.QUALIFY_WAKE_INTERLOCK,
    ]
    assert kwargs["cwd"] == str(q.TARGET_WORKTREE) and "shell" not in kwargs


@pytest.mark.parametrize("boundary", ["source", "target", "principal"])
def test_launch_readmission_failure_zero_child(fake, monkeypatch, boundary):
    armed(fake)
    monkeypatch.setattr(
        fake, boundary, lambda *a: (_ for _ in ()).throw(ValueError("drift"))
    )
    with pytest.raises(ValueError):
        q.launch(fake, HEAD, TREE)
    assert fake.children == 0


def test_launch_consumed_result_blocks(fake):
    value = armed(fake)
    (fake.parent / value.result_name).write_bytes(b"")
    with pytest.raises(ValueError):
        q.launch(fake, HEAD, TREE)
    assert fake.children == 0


def d1r5_result(fake, classification="PASS"):
    value = plan()
    source_calls = 0

    def source():
        nonlocal source_calls
        source_calls += 1
        if classification == "SOURCE_REJECTED" and source_calls == 3:
            raise ValueError
        return (fake.parent.parent / "repository",)

    start = value.trigger
    wake = value.end
    if classification == "WAKE_TOO_EARLY":
        wake -= timedelta(seconds=1)
    if classification == "WAKE_TOO_LATE":
        wake += timedelta(seconds=61)
    if classification == "WAKE_SESSION_INVALID":
        wake += timedelta(days=1)
    times = iter((start, start, wake))

    def sleeper(seconds):
        if classification == "WAIT_FAILED":
            raise OSError

    d1r5.qualify_pre_market_wake(
        expected_head=q.TARGET_HEAD,
        expected_tree=q.TARGET_TREE,
        qualify_wake=d1r5.QUALIFY_WAKE_INTERLOCK,
        evidence=fake.parent / value.result_name,
        admit_source=source,
        clock=lambda: next(times),
        sleeper=sleeper,
    )
    return fake.parent / value.result_name


@pytest.mark.parametrize(
    "classification",
    [
        "PASS",
        "SOURCE_REJECTED",
        "WAIT_FAILED",
        "WAKE_TOO_EARLY",
        "WAKE_TOO_LATE",
        "WAKE_SESSION_INVALID",
    ],
)
def test_reconcile_d1r5_authority(fake, classification):
    armed(fake)
    d1r5_result(fake, classification)
    before = {p.name: p.read_bytes() for p in fake.parent.iterdir()}
    result = q.reconcile(fake, HEAD, TREE)
    assert result["evidence"] == (
        "PASS" if classification == "PASS" else "D1R5_TERMINAL_FAILURE"
    )
    assert {p.name: p.read_bytes() for p in fake.parent.iterdir()} == before
    assert fake.creates == 1 and fake.children == 0


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("prefix", "D1R5_INCOMPLETE"),
        ("corrupt", "D1R5_INVALID"),
        ("wrong_source", "D1R5_INVALID"),
        ("wrong_session", "D1R5_INVALID"),
        ("absent", "NO_D1R5_EVIDENCE"),
        ("pending", "PENDING"),
    ],
)
def test_reconcile_dispositions(fake, kind, expected):
    value = armed(fake)
    fake.now = value.end + timedelta(minutes=21)
    if kind not in {"absent", "pending"}:
        path = d1r5_result(fake)
        if kind == "corrupt":
            path.write_bytes(b"garbage")
        elif kind == "prefix":
            path.write_bytes(path.read_bytes().splitlines(keepends=True)[0])
        elif kind == "wrong_source":
            path.write_bytes(
                path.read_bytes().replace(q.TARGET_HEAD.encode(), b"c" * 40)
            )
        else:
            path.write_bytes(path.read_bytes().replace(b"2026-10-15", b"2026-10-16"))
    elif kind == "pending":
        fake.now = value.end
    assert q.reconcile(fake, HEAD, TREE)["evidence"] == expected


@pytest.mark.parametrize("last_result", [0, 1, 267009, 0xFFFFFFFF])
def test_scheduler_exit_never_overrides_evidence(fake, last_result):
    value = armed(fake)
    fake.now = value.end + timedelta(minutes=21)
    fake.task["last_result"] = last_result
    assert q.reconcile(fake, HEAD, TREE)["evidence"] == "NO_D1R5_EVIDENCE"
    d1r5_result(fake)
    assert q.reconcile(fake, HEAD, TREE)["evidence"] == "PASS"
    fake.task = {"status": "ABSENT"}
    assert q.reconcile(fake, HEAD, TREE) == {
        "disposition": "TASK_DRIFT_OR_MISSING",
        "evidence": "PASS",
        "task": "TASK_DRIFT_OR_MISSING",
    }


@pytest.mark.parametrize("target", [False, True])
@pytest.mark.parametrize(
    "boundary",
    [
        "root",
        "branch",
        "head",
        "tree",
        "dirty",
        "origin",
        "tracking_head",
        "tracking_tree",
        "remote",
        "worktrees",
        "imports",
        "package_path",
        "ok",
    ],
)
def test_both_source_admissions(fake, monkeypatch, target, boundary):
    own = Path(host.__file__).resolve().parents[3]
    target_root = fake.parent.parent / "predecessor"
    monkeypatch.setattr(host, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(q, "WORKTREE", own)
    monkeypatch.setattr(q, "TARGET_WORKTREE", target_root)
    root = target_root if target else own
    branch = host.TARGET_BRANCH if target else host.BRANCH
    head, tree = (q.TARGET_HEAD, q.TARGET_TREE) if target else (HEAD, TREE)
    responses = {
        ("rev-parse", "--show-toplevel"): str(root),
        ("branch", "--show-current"): branch,
        ("rev-parse", "HEAD"): head,
        ("rev-parse", "HEAD^{tree}"): tree,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
        ("remote", "get-url", "origin"): host.ORIGIN,
        ("rev-parse", "origin/" + branch): head,
        ("rev-parse", "origin/" + branch + "^{tree}"): tree,
        ("ls-remote", "origin", "refs/heads/" + branch): head
        + "\trefs/heads/"
        + branch,
        ("worktree", "list", "--porcelain"): "worktree "
        + str(own)
        + "\nworktree "
        + str(target_root),
    }
    keys = [
        "root",
        "branch",
        "head",
        "tree",
        "dirty",
        "origin",
        "tracking_head",
        "tracking_tree",
        "remote",
        "worktrees",
    ]
    if boundary in keys:
        responses[list(responses)[keys.index(boundary)]] = "mismatch"
    if boundary == "imports":
        monkeypatch.setitem(
            host.sys.modules,
            "trading_bot.drift",
            SimpleNamespace(__file__=str(target_root / "bad.py")),
        )
    if boundary == "package_path":
        monkeypatch.setitem(
            host.sys.modules,
            "trading_bot.drift",
            SimpleNamespace(
                __file__=str(own / "src" / "good.py"), __path__=[str(target_root)]
            ),
        )
    monkeypatch.setattr(
        host.subprocess,
        "run",
        lambda argv, **kw: SimpleNamespace(stdout=responses[tuple(argv[3:])]),
    )
    if boundary == "ok":
        assert root.resolve() in host.admit_source(head, tree, target=target)
    else:
        with pytest.raises(ValueError):
            host.admit_source(head, tree, target=target)


@pytest.mark.parametrize(
    "argument",
    [
        "--session-date",
        "--exchange",
        "--trigger",
        "--task",
        "--provider",
        "--evidence",
        "--expected-h",
        "--arm-x",
    ],
)
def test_no_caller_semantic_authority(argument):
    with pytest.raises(ValueError):
        host.build_parser().parse_args(["preflight", argument, "x"])


def test_help_and_import_are_inert(monkeypatch):
    monkeypatch.setattr(
        host.subprocess,
        "run",
        lambda *a, **kw: pytest.fail("native process during help"),
    )
    with pytest.raises(SystemExit) as stopped:
        host.main(["--help"])
    assert stopped.value.code == 0
    assert host.main(["arm"]) == 2


def test_transport_input_is_stdin_and_output_is_closed(monkeypatch):
    calls = []
    monkeypatch.setattr(
        host.subprocess,
        "run",
        lambda argv, **kw: (
            calls.append((argv, kw))
            or SimpleNamespace(
                returncode=0,
                stdout=b'{"disposition":"CALL_RETURNED","registration_attempts":1}\r\n',
            )
        ),
    )
    assert host._WindowsRuntime().create(plan())["registration_attempts"] == 1
    argv, kwargs = calls[0]
    assert argv == [
        q.POWERSHELL,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(q.WORKTREE / "scripts" / "arch134_d1r6_scheduler_create.ps1"),
        "-Mode",
        "Create",
    ]
    assert kwargs.get("shell", False) is False
    assert type(kwargs["input"]) is bytes
    assert kwargs["input"].endswith(b"\n")
    assert "principal_sid" not in " ".join(argv)
    assert (
        not {"text", "encoding", "errors", "env", "universal_newlines"} & kwargs.keys()
    )


def test_static_capability_closure_and_fixed_transport():
    allowed = {
        "__future__",
        "argparse",
        "json",
        "hashlib",
        "os",
        "re",
        "stat",
        "subprocess",
        "sys",
        "dataclasses",
        "datetime",
        "pathlib",
        "typing",
        "zoneinfo",
        "trading_bot.review_paper",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.review_paper.pre_market_wake_qualification",
        "trading_bot.review_paper.session_admission",
    }
    for module in (q, host):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        imports = {
            n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
        } | {
            a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
        }
        assert imports <= allowed
        calls = {
            getattr(n.func, "attr", getattr(n.func, "id", ""))
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
        }
        assert not calls & {
            "eval",
            "exec",
            "__import__",
            "import_module",
            "sleep",
            "Popen",
            "system",
            "unlink",
            "chmod",
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "run"
            ):
                assert not any(k.arg == "shell" for k in node.keywords)
                assert isinstance(node.args[0], ast.List)
    text = (ROOT / "scripts/arch134_d1r6_scheduler_create.ps1").read_text(
        encoding="utf-8"
    )
    action_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("$action.Arguments =")
    ]
    assert action_lines == ["$action.Arguments = '" + plan().task["arguments"] + "'"]
    assert text.count(".RegisterTaskDefinition(") == 1
    assert "$definition, 2, $identity.sid, $null, 3, $null)" in text
    for forbidden in (
        "Set-ExecutionPolicy",
        "TASK_UPDATE",
        ".Run(",
        ".Stop(",
        "DeleteTask",
        "Register-ScheduledTask",
        "Invoke-Expression",
        "-ComObject 'WScript.Shell'",
        "Get-Credential",
        "CredentialManager",
    ):
        assert forbidden not in text
    assert "$service.Connect()" in text and "$service.Connect(" not in text.replace(
        "$service.Connect()", ""
    )
    assert "WakeToRun = $true" in text and "StartWhenAvailable = $false" in text
    launcher = (ROOT / "scripts/arch134_d1r6_task_launcher.ps1").read_text(
        encoding="utf-8"
    )
    assert "$args.Count -ne 0" in launcher and "-I -B" in launcher
    child = (ROOT / "scripts/arch134_d1r6_d1r5_child.py").read_text(encoding="utf-8")
    assert (
        str(q.TARGET_WORKTREE) in child
        and "pre_market_wake_qualification_host import main" in child
    )


def test_checkpoint_inventory_and_frozen_predecessors():
    spec = runner._checkpoint_specs()[runner.ARCH134_D1R6_NAME]
    assert spec.remote_branch == host.BRANCH and spec.preflight is spec.execute is None
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), host.BRANCH, "push")
        == spec.name
    )
    assert runner.resolve_ci_certification_profile(spec.name) == "robinhood"
    assert runner._arch134_d1r6_authority_check(ROOT) == ()
    assert runner._arch134_d1r5_authority_check(ROOT) == ()
    assert {
        profile: len(
            certification.select_inventory(
                certification.discover_inventory(ROOT), profile
            )
        )
        for profile in certification.PROFILES
    } == {"full": 201, "robinhood": 112, "legacy": 222, "exhaustive": 423}
    expected = {
        "ARCH134_D1R5_TEST_PIN_OVERRIDES": (
            "6a95f4afc8640dfa0c672f5d77cda06ae57171c0199128a3ddd1d8b0debaac4a"
        ),
        "ARCH134_D1R5_SOURCE_PINS": (
            "370e14ff9a9453b4e001278921c3d1084c6ff94c8e34be76d430cb2b2adae575"
        ),
    }
    assert runner.ARCH134_D1R6_PREDECESSOR_DIGESTS == expected
    for name, digest in expected.items():
        assert hashlib.sha256(q.canonical(getattr(runner, name))).hexdigest() == digest


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "extra",
        "executable",
        "wrong_blob",
        "predecessor",
        "source_predecessor",
    ],
)
def test_successor_overlay_fails_closed(monkeypatch, kind):
    pins = dict(runner.ARCH134_D1R6_TEST_PIN_OVERRIDES)
    first = next(iter(pins))
    if kind == "missing":
        pins.pop(first)
    elif kind == "extra":
        pins["tests/extra.py"] = "a" * 40
    elif kind == "executable":
        pins["src/trading_bot/review_paper/armed_session.py"] = "a" * 40
    elif kind == "wrong_blob":
        pins[first] = "a" * 40
    elif kind == "predecessor":
        monkeypatch.setattr(
            runner,
            "ARCH134_D1R5_TEST_PIN_OVERRIDES",
            runner.ARCH134_D1R5_TEST_PIN_OVERRIDES | {first: "f" * 40},
        )
    else:
        monkeypatch.setattr(runner, "ARCH134_D1R5_SOURCE_PINS", {})
    monkeypatch.setattr(runner, "ARCH134_D1R6_TEST_PIN_OVERRIDES", pins)
    with pytest.raises(ValueError):
        runner._arch134_d1r6_test_pin(
            first, runner.ARCH134_D1R5_TEST_PIN_OVERRIDES[first]
        )
    assert runner._arch134_d1r6_authority_check(ROOT)


def test_wrong_predecessor_argument_rejected():
    first = next(iter(runner.ARCH134_D1R6_TEST_PIN_OVERRIDES))
    with pytest.raises(ValueError):
        runner._arch134_d1r6_test_pin(first, "f" * 40)


def test_launch_fence_blocks_second_delegation_even_without_d1r5_result(fake):
    value = armed(fake)
    assert q.launch(fake, HEAD, TREE) == 7
    assert not (fake.parent / value.result_name).exists()
    with pytest.raises(FileExistsError):
        q.launch(fake, HEAD, TREE)
    assert fake.children == 1


def test_launch_failure_is_consumed(fake, monkeypatch):
    value = armed(fake)

    def child(p):
        fake.children += 1
        assert (
            (fake.parent / value.arm_name.replace(".jsonl", "-launch.jsonl"))
            .read_bytes()
            .endswith(b"\n")
        )
        raise OSError("process entry uncertain")

    monkeypatch.setattr(fake, "child", child)
    with pytest.raises(OSError):
        q.launch(fake, HEAD, TREE)
    with pytest.raises(FileExistsError):
        q.launch(fake, HEAD, TREE)
    assert fake.children == 1


def test_launch_fsync_failure_zero_child(fake, monkeypatch):
    armed(fake)
    monkeypatch.setattr(
        q.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("sync"))
    )
    with pytest.raises(OSError):
        q.launch(fake, HEAD, TREE)
    with pytest.raises(FileExistsError):
        q.launch(fake, HEAD, TREE)
    assert fake.children == 0


def test_reconcile_d1r5_start_window_terminal(fake):
    value = armed(fake)
    times = iter((value.trigger, value.end))
    d1r5.qualify_pre_market_wake(
        expected_head=q.TARGET_HEAD,
        expected_tree=q.TARGET_TREE,
        qualify_wake=d1r5.QUALIFY_WAKE_INTERLOCK,
        evidence=fake.parent / value.result_name,
        admit_source=lambda: (fake.parent.parent / "repository",),
        clock=lambda: next(times),
        sleeper=lambda seconds: pytest.fail("sleep"),
    )
    assert q.reconcile(fake, HEAD, TREE)["evidence"] == "D1R5_TERMINAL_FAILURE"


def test_powershell_syntax_only_no_native_execution():
    # Production transport is inspected only; parsing never invokes its statements.
    text = (ROOT / "scripts/arch134_d1r6_scheduler_create.ps1").read_text(
        encoding="utf-8"
    )
    assert text.count("RegisterTaskDefinition") == 1
    assert "$attempted = $true" in text
    assert text.index("$attempted = $true") < text.index(".RegisterTaskDefinition(")
    for assignment in (
        "LogonType = 3",
        "RunLevel = 0",
        "AllowDemandStart = $false",
        "RestartCount = 0",
        "ExecutionTimeLimit = 'PT20M'",
    ):
        assert assignment in text


def test_absent_result_completion_deadline_is_conservative(fake):
    value = armed(fake)
    fake.now = value.end + timedelta(minutes=20)
    assert q.reconcile(fake, HEAD, TREE)["evidence"] == "PENDING"
    fake.now += timedelta(microseconds=1)
    assert q.reconcile(fake, HEAD, TREE)["evidence"] == "NO_D1R5_EVIDENCE"


def test_additional_predecessor_overlay_is_exact_and_test_only(monkeypatch):
    baseline = runner.ARCH134_D1R6_ADDITIONAL_PREDECESSOR_PINS
    assert len(baseline) == 6
    assert all(
        path.startswith("tests/") and path.endswith(".py")
        for path in runner.ARCH134_D1R6_TEST_PIN_OVERRIDES
    )
    assert (
        hashlib.sha256(q.canonical(baseline)).hexdigest()
        == "572d83c4a3938678894c0cb9072c182373fbce4f596c4b66c26b51f07e2089ab"
    )
    for path, predecessor in baseline.items():
        assert (
            runner._arch134_d1r6_test_pin(path, predecessor)
            == runner.ARCH134_D1R6_TEST_PIN_OVERRIDES[path]
        )
    monkeypatch.setattr(runner, "ARCH134_D1R6_ADDITIONAL_PREDECESSOR_PINS", {})
    with pytest.raises(ValueError):
        runner._arch134_d1r6_test_pin(
            next(iter(baseline)), next(iter(baseline.values()))
        )


@pytest.mark.parametrize("mode", ["Principal", "Observe", "Create"])
def test_all_scheduler_modes_use_only_fixed_process_policy(monkeypatch, mode):
    calls = []
    response = {
        "Principal": {"name": PRINCIPAL.name, "sid": PRINCIPAL.sid},
        "Observe": {"status": "ABSENT"},
        "Create": {"disposition": "CALL_RETURNED", "registration_attempts": 1},
    }[mode]
    monkeypatch.setattr(
        host.subprocess,
        "run",
        lambda argv, **kwargs: (
            calls.append((argv, kwargs))
            or SimpleNamespace(returncode=0, stdout=q.canonical(response) + b"\r\n")
        ),
    )
    assert (
        host._WindowsRuntime()._scheduler(mode, plan() if mode == "Create" else None)
        == response
    )
    argv, kwargs = calls[0]
    assert argv == [
        q.POWERSHELL,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(q.WORKTREE / "scripts" / "arch134_d1r6_scheduler_create.ps1"),
        "-Mode",
        mode,
    ]
    assert kwargs.get("shell", False) is False
    assert (
        not {"text", "encoding", "errors", "env", "universal_newlines"} & kwargs.keys()
    )
    assert type(kwargs["input"]) is bytes
    expected = b"{}\n"
    if mode == "Create":
        expected = (
            q.canonical(
                {
                    "start_boundary": "2026-10-15T13:20:00+00:00",
                    "end_boundary": "2026-10-15T13:35:00+00:00",
                    "principal_name": PRINCIPAL.name,
                    "principal_sid": PRINCIPAL.sid,
                }
            )
            + b"\n"
        )
    assert kwargs["input"] == expected
    assert kwargs["input"].count(b"\n") == 1
    assert b"\r" not in kwargs["input"]
    assert kwargs["capture_output"] is True
    assert kwargs["timeout"] == 45
    assert kwargs["check"] is False
    assert len(calls) == 1


@pytest.mark.parametrize(
    "option,value",
    [
        ("--execution-policy", "Unrestricted"),
        ("--execution-policy", "bypass"),
        ("--execution-policy", "ByPass"),
        ("--execution-policy", "Bypass"),
        ("--policy", "Bypass"),
        ("--powershell", "caller.exe"),
        ("--scheduler-script", "caller.ps1"),
    ],
)
def test_caller_cannot_select_policy_executable_or_script(option, value):
    with pytest.raises(ValueError):
        host.build_parser().parse_args(["preflight", option, value])


@pytest.mark.parametrize(
    "keyword,value",
    [
        ("execution_policy", "Unrestricted"),
        ("execution_policy", "bypass"),
        ("execution_policy", "Bypass"),
        ("script", "caller.ps1"),
        ("executable", "caller.exe"),
    ],
)
def test_transport_has_no_caller_policy_or_path_surface(monkeypatch, keyword, value):
    monkeypatch.setattr(
        host.subprocess, "run", lambda *a, **kw: pytest.fail("process entered")
    )
    with pytest.raises(TypeError):
        host._WindowsRuntime()._scheduler("Observe", **{keyword: value})


def test_principal_crlf_output_keeps_raw_lf_stdin(monkeypatch):
    def binary_only(argv, **kwargs):
        assert type(kwargs["input"]) is bytes
        assert kwargs["input"] == b"{}\n"
        assert (
            not {"text", "encoding", "errors", "env", "universal_newlines"}
            & kwargs.keys()
        )
        assert kwargs.get("shell", False) is False
        return SimpleNamespace(
            returncode=0,
            stdout=b'{"name":"DOMAIN\\\\User","sid":"S-1-5-21-1-2-3-1001"}\r\n',
            stderr=b"",
        )

    monkeypatch.setattr(host.subprocess, "run", binary_only)
    assert host._WindowsRuntime().principal() == q.Principal(
        r"DOMAIN\User", PRINCIPAL.sid
    )


@pytest.mark.parametrize("length,accepted", [(16384, True), (16385, False)])
def test_scheduler_stdout_limit_counts_raw_bytes(monkeypatch, length, accepted):
    monkeypatch.setattr(
        host.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(
            returncode=0, stdout=b"{}" + b" " * (length - 2), stderr=b""
        ),
    )
    if accepted:
        assert host._WindowsRuntime()._scheduler("Observe") == {}
    else:
        with pytest.raises(ValueError, match="scheduler unavailable"):
            host._WindowsRuntime()._scheduler("Observe")


def test_scheduler_invalid_utf8_stdout_rejected(monkeypatch):
    monkeypatch.setattr(
        host.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(
            returncode=0, stdout=b"\xff{}\r\n", stderr=b""
        ),
    )
    with pytest.raises(ValueError):
        host._WindowsRuntime()._scheduler("Observe")


def test_scheduler_transport_keyword_closure_is_binary_only():
    tree = ast.parse(Path(host.__file__).read_text(encoding="utf-8"))
    scheduler = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_scheduler"
    )
    calls = [
        node
        for node in ast.walk(scheduler)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
    ]
    assert len(calls) == 1
    assert {keyword.arg for keyword in calls[0].keywords} == {
        "input",
        "capture_output",
        "timeout",
        "check",
    }


# All incident files below are synthetic and live only under pytest's external
# temporary root. Never read the real host journal or invoke native host modes.
INCIDENT_PRINCIPAL = q.Principal(
    r"DESKTOP-I4DOKM7\John", "S-1-5-21-1397534616-3988210162-180023805-1005"
)


def incident_records():
    value = q.Plan(
        q.RECOVERY_PREDECESSOR_HEAD,
        q.RECOVERY_PREDECESSOR_TREE,
        OBSERVED,
        INCIDENT_PRINCIPAL,
    )
    records = tuple(
        {
            "schema": q.SCHEMA,
            "event": event,
            "facts": value.facts,
            "effects": dict.fromkeys(q.ZERO_EFFECTS, 0),
            "scheduler_task_create_calls": int(index >= 4),
            "classification": "INDETERMINATE" if event == "FINAL" else None,
        }
        for index, event in enumerate((*q.EVENTS[:6], "FINAL"))
    )
    return value, records


def pin_synthetic_journal(monkeypatch, payload):
    # Only synthetic bytes are admitted in tests, without possessing real evidence.
    monkeypatch.setattr(q, "RECOVERY_PREDECESSOR_ARM_BYTES", len(payload))
    monkeypatch.setattr(
        q, "RECOVERY_PREDECESSOR_ARM_SHA256", hashlib.sha256(payload).hexdigest()
    )


@pytest.fixture
def consumed(fake, monkeypatch):
    value, records = incident_records()
    payload = q.serialize_arm(records)
    pin_synthetic_journal(monkeypatch, payload)
    (fake.parent / q.RECOVERY_PREDECESSOR_ARM_NAME).write_bytes(payload)
    fake.identity = INCIDENT_PRINCIPAL
    fake.task = {
        "status": "PRESENT",
        "task": value.task,
        "state": 3,
        "last_result": 267011,
    }
    return fake, value, payload


def recovered(consumed):
    fake, value, payload = consumed
    assert q.recover(fake, HEAD, TREE, q.RECOVERY_INTERLOCK) == "RECOVERED"
    assert (fake.parent / value.arm_name).read_bytes() == payload
    return fake, value


def test_frozen_real_incident_constants():
    assert q.RECOVERY_PREDECESSOR_HEAD == "3cf4284d017e362eee58a2f27526ab4de8f292a2"
    assert q.RECOVERY_PREDECESSOR_TREE == "16a48a12756bb6d810799444859334ce6305001d"
    assert q.RECOVERY_PREDECESSOR_ARM_BYTES == 16917
    assert q.RECOVERY_PREDECESSOR_ARM_SHA256 == (
        "b62959f9988dcc42e4881e45ed95abcf4abc2b6d2932514c7253165e1223955c"
    )
    assert q.RECOVERY_TARGET_SESSION == "2026-10-15"
    value, _ = incident_records()
    assert value.arm_name == q.RECOVERY_PREDECESSOR_ARM_NAME
    assert q.RECOVERY_INTERLOCK == "AUTHORIZE_ARCH134_D1R6_ONE_CONSUMED_ARM_RECOVERY"


def test_consumed_predecessor_exact_and_readonly(consumed):
    fake, value, payload = consumed
    path = fake.parent / value.arm_name
    before = path.stat()
    assert q.read_consumed_predecessor(path) == value
    assert path.read_bytes() == payload
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    with pytest.raises(ValueError):
        q.load_armed(fake, HEAD, TREE)
    with pytest.raises(ValueError):
        q.launch(fake, HEAD, TREE)
    assert q.reconcile(fake, HEAD, TREE)["evidence"] == "ARM_EVIDENCE_INVALID"
    assert fake.creates == fake.children == 0


@pytest.mark.parametrize("kind", ["filename", "bytes", "sha", "directory", "hardlink"])
def test_predecessor_file_identity_rejected(consumed, monkeypatch, kind):
    fake, value, payload = consumed
    path = fake.parent / value.arm_name
    if kind == "filename":
        path = fake.parent / "wrong.jsonl"
        path.write_bytes(payload)
    elif kind == "bytes":
        monkeypatch.setattr(q, "RECOVERY_PREDECESSOR_ARM_BYTES", len(payload) + 1)
    elif kind == "sha":
        monkeypatch.setattr(q, "RECOVERY_PREDECESSOR_ARM_SHA256", "0" * 64)
    elif kind == "directory":
        path.unlink()
        path.mkdir()
    else:
        (fake.parent / "linked.jsonl").hardlink_to(path)
    with pytest.raises(ValueError):
        q.read_consumed_predecessor(path)


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "extra",
        "event",
        "returned",
        "blocked",
        "armed",
        "session",
        "head",
        "tree",
        "target",
        "facts",
        "effects",
        "create",
    ],
)
def test_predecessor_structural_drift_rejected(consumed, monkeypatch, kind):
    fake, value, _ = consumed
    _, raw = incident_records()
    records = list(copy.deepcopy(raw))
    if kind == "missing":
        records.pop(5)
    elif kind == "extra":
        records.insert(6, dict(records[5]))
    elif kind in {"event", "returned"}:
        records[5 if kind == "returned" else 1]["event"] = "TASK_CONFIRMED"
    elif kind in {"blocked", "armed"}:
        records[-1]["classification"] = kind.upper()
    elif kind == "effects":
        records[2]["effects"][q.ZERO_EFFECTS[0]] = 1
    elif kind == "create":
        records[4]["scheduler_task_create_calls"] = 0
    else:
        field = {
            "session": "target_session",
            "head": "source_head",
            "tree": "source_tree",
            "target": "target_head",
            "facts": "observed_at",
        }[kind]
        for record in records:
            record["facts"][field] = {
                "session": "2026-10-16",
                "head": HEAD,
                "tree": TREE,
                "target": HEAD,
                "facts": "2026-10-15T04:00:00+00:00",
            }[kind]
    payload = b"".join(q.canonical(r) + b"\n" for r in records)
    # Exercise structure independently of the real incident's byte/hash fence.
    pin_synthetic_journal(monkeypatch, payload)
    (fake.parent / value.arm_name).write_bytes(payload)
    if kind == "facts":
        # A self-consistent changed observation is rejected by the frozen hash.
        monkeypatch.setattr(q, "RECOVERY_PREDECESSOR_ARM_SHA256", "0" * 64)
    with pytest.raises(ValueError):
        q.read_consumed_predecessor(fake.parent / value.arm_name)


def test_recovery_preflight_ready_zero_writes(consumed):
    fake, value, payload = consumed
    assert q.recover_preflight(fake, HEAD, TREE) == value
    assert list(fake.parent.iterdir()) == [fake.parent / value.arm_name]
    assert (fake.parent / value.arm_name).read_bytes() == payload
    assert fake.creates == fake.children == 0


@pytest.mark.parametrize(
    "kind",
    [
        "state",
        "result",
        "task",
        "principal",
        "time",
        "backward",
        "result_file",
        "fence",
        "recovery",
        "other_arm",
        "source",
        "target",
    ],
)
def test_recovery_preflight_every_drift_blocks(consumed, monkeypatch, kind):
    fake, value, payload = consumed
    if kind == "state":
        fake.task["state"] = 4
    elif kind == "result":
        fake.task["last_result"] = 0
    elif kind == "task":
        fake.task["task"]["start_when_available"] = True
    elif kind == "principal":
        fake.identity = PRINCIPAL
    elif kind == "time":
        fake.now = value.trigger
    elif kind == "backward":
        fake.now = OBSERVED - timedelta(seconds=1)
    elif kind in {"source", "target"}:
        monkeypatch.setattr(fake, kind, lambda *a: (_ for _ in ()).throw(ValueError()))
    else:
        name = {
            "result_file": value.result_name,
            "fence": value.arm_name.replace(".jsonl", "-launch.jsonl"),
            "recovery": q.recovery_name(HEAD, TREE),
            "other_arm": value.arm_prefix + "other.jsonl",
        }[kind]
        (fake.parent / name).write_bytes(b"")
    with pytest.raises(ValueError):
        q.recover_preflight(fake, HEAD, TREE)
    assert fake.creates == fake.children == 0
    assert (fake.parent / value.arm_name).read_bytes() == payload


@pytest.mark.parametrize("state", [0, 1, 2, 4, True, "3", None])
def test_recovery_only_ready_state(consumed, state):
    fake, _, _ = consumed
    fake.task["state"] = state
    with pytest.raises(ValueError):
        q.recover_preflight(fake, HEAD, TREE)


@pytest.mark.parametrize("result", [0, 1, 267009, 267010, True, "267011", None])
def test_recovery_only_has_not_run_result(consumed, result):
    fake, _, _ = consumed
    fake.task["last_result"] = result
    with pytest.raises(ValueError):
        q.recover_preflight(fake, HEAD, TREE)


@pytest.mark.parametrize(
    "interlock", [None, "", True, q.ARM_INTERLOCK, q.RECOVERY_INTERLOCK[:-1]]
)
def test_recovery_exact_interlock(consumed, interlock):
    fake, _, _ = consumed
    with pytest.raises(ValueError):
        q.recover(fake, HEAD, TREE, interlock)
    assert (
        fake.sources == fake.targets == fake.reads == fake.creates == fake.children == 0
    )


def test_recovery_exclusive_durable_reread(consumed, monkeypatch):
    fake, value, _ = consumed
    events = []
    original_open, original_read, original_fsync = (
        Path.open,
        q._read_recovery_file,
        q.os.fsync,
    )
    destination = fake.parent / q.recovery_name(HEAD, TREE)

    class Output:
        def __enter__(self):
            self.stream = original_open(destination, "xb")
            return self

        def __exit__(self, *args):
            self.stream.close()

        def write(self, payload):
            events.append("write")
            return self.stream.write(payload)

        def flush(self):
            events.append("flush")
            self.stream.flush()

        def fileno(self):
            return self.stream.fileno()

    def opening(path, mode="r", *args, **kwargs):
        if path == destination and mode == "xb":
            events.append("xb")
            return Output()
        return original_open(path, mode, *args, **kwargs)

    def reading(path, maximum):
        if path == destination:
            events.append("reread")
        return original_read(path, maximum)

    monkeypatch.setattr(Path, "open", opening)
    monkeypatch.setattr(q, "_read_recovery_file", reading)
    monkeypatch.setattr(
        q.os, "fsync", lambda fd: (events.append("fsync"), original_fsync(fd))
    )
    recovered(consumed)
    assert events == ["xb", "write", "flush", "fsync", "reread"]
    assert fake.reads == 3 and fake.sources == fake.targets == 3
    q.parse_recovery(destination.read_bytes(), HEAD, TREE, value)
    with pytest.raises(ValueError):
        q.recover(fake, HEAD, TREE, q.RECOVERY_INTERLOCK)
    assert fake.creates == fake.children == 0


@pytest.mark.parametrize(
    "boundary", ["source", "target", "principal", "clock", "observe"]
)
@pytest.mark.parametrize("point", [2, 3])
def test_final_recovery_readmissions_block_publication(
    consumed, monkeypatch, boundary, point
):
    fake, value, payload = consumed
    original = getattr(fake, boundary)
    calls = 0

    def changing(*args):
        nonlocal calls
        calls += 1
        if calls == point:
            raise ValueError("drift")
        return original(*args)

    monkeypatch.setattr(fake, boundary, changing)
    with pytest.raises(ValueError):
        q.recover(fake, HEAD, TREE, q.RECOVERY_INTERLOCK)
    assert not (fake.parent / q.recovery_name(HEAD, TREE)).exists()
    assert (fake.parent / value.arm_name).read_bytes() == payload
    assert fake.creates == fake.children == 0


@pytest.mark.parametrize(
    "point", ["write", "short", "flush", "fsync", "close", "reread", "parse"]
)
def test_recovery_publication_ambiguity_consumed(consumed, monkeypatch, point):
    fake, value, payload = consumed
    destination = fake.parent / q.recovery_name(HEAD, TREE)
    original_open, original_read, original_parse = (
        Path.open,
        q._read_recovery_file,
        q.parse_recovery,
    )

    class Output:
        def __enter__(self):
            self.stream = original_open(destination, "xb")
            return self

        def __exit__(self, *args):
            self.stream.close()
            if point == "close":
                raise OSError("close")

        def write(self, data):
            if point == "write":
                raise OSError("write")
            if point == "short":
                return self.stream.write(data[:30])
            return self.stream.write(data)

        def flush(self):
            if point == "flush":
                raise OSError("flush")
            self.stream.flush()

        def fileno(self):
            return self.stream.fileno()

    def opening(path, mode="r", *args, **kwargs):
        if path == destination and mode == "xb":
            return Output()
        return original_open(path, mode, *args, **kwargs)

    def reading(path, maximum):
        if path == destination and point == "reread":
            raise OSError("reread")
        return original_read(path, maximum)

    monkeypatch.setattr(Path, "open", opening)
    monkeypatch.setattr(q, "_read_recovery_file", reading)
    if point == "fsync":
        monkeypatch.setattr(q.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError()))
    if point == "parse":
        monkeypatch.setattr(
            q, "parse_recovery", lambda *a: (_ for _ in ()).throw(ValueError())
        )
    with pytest.raises((ValueError, OSError)):
        q.recover(fake, HEAD, TREE, q.RECOVERY_INTERLOCK)
    assert destination.exists()
    monkeypatch.setattr(q, "parse_recovery", original_parse)
    with pytest.raises(ValueError):
        q.recover(fake, HEAD, TREE, q.RECOVERY_INTERLOCK)
    assert (fake.parent / value.arm_name).read_bytes() == payload
    assert fake.creates == fake.children == 0


@pytest.mark.parametrize("field", list(incident_records()[0].task))
def test_recovered_launch_every_task_drift_blocks(consumed, field):
    fake, value = recovered(consumed)
    fake.task["task"][field] = None
    with pytest.raises(ValueError):
        q.launch(fake, HEAD, TREE)
    assert not (
        fake.parent / value.arm_name.replace(".jsonl", "-launch.jsonl")
    ).exists()
    assert fake.creates == fake.children == 0


def test_recovered_launch_once_and_reconcile(consumed):
    fake, value = recovered(consumed)
    assert q.reconcile(fake, HEAD, TREE) == {
        "disposition": "PENDING",
        "evidence": "PENDING",
        "task": "MATCH",
    }
    fake.now = value.trigger
    assert q.launch(fake, HEAD, TREE) == 7
    assert fake.children == 1 and fake.creates == 0
    with pytest.raises(ValueError):
        q.launch(fake, HEAD, TREE)
    assert fake.children == 1
    fake.task["last_result"] = 0
    fake.now = value.end + timedelta(minutes=21)
    assert q.reconcile(fake, HEAD, TREE)["evidence"] == "NO_D1R5_EVIDENCE"
    d1r5_result(fake)
    assert q.reconcile(fake, HEAD, TREE)["evidence"] == "PASS"
    fake.task["task"]["wake_to_run"] = False
    assert q.reconcile(fake, HEAD, TREE) == {
        "disposition": "TASK_DRIFT_OR_MISSING",
        "evidence": "PASS",
        "task": "TASK_DRIFT_OR_MISSING",
    }


@pytest.mark.parametrize(
    "kind",
    [
        "source",
        "target",
        "principal",
        "result",
        "fence",
        "malformed",
        "duplicate",
        "predecessor",
        "recovery_source",
        "other_arm",
    ],
)
def test_recovered_launch_authority_drift_blocks(consumed, monkeypatch, kind):
    fake, value = recovered(consumed)
    if kind in {"source", "target"}:
        monkeypatch.setattr(fake, kind, lambda *a: (_ for _ in ()).throw(ValueError()))
    elif kind == "principal":
        fake.identity = PRINCIPAL
    elif kind == "predecessor":
        (fake.parent / value.arm_name).write_bytes(b"changed")
    elif kind == "recovery_source":
        monkeypatch.setattr(
            fake, "source", lambda *a: (fake.parent.parent / "repository",)
        )
        with pytest.raises(ValueError):
            q.launch(fake, "c" * 40, "d" * 40)
        assert fake.children == 0
        return
    else:
        name = {
            "result": value.result_name,
            "fence": value.arm_name.replace(".jsonl", "-launch.jsonl"),
            "malformed": q.recovery_name(HEAD, TREE),
            "duplicate": q.recovery_name("c" * 40, TREE),
            "other_arm": value.arm_prefix + "other.jsonl",
        }[kind]
        (fake.parent / name).write_bytes(b"bad")
    with pytest.raises(ValueError):
        q.launch(fake, HEAD, TREE)
    assert fake.creates == fake.children == 0


@pytest.mark.parametrize("kind", ["duplicate", "malformed", "principal", "source"])
def test_reconciliation_recovery_fail_closed(consumed, monkeypatch, kind):
    fake, _ = recovered(consumed)
    if kind == "principal":
        fake.identity = PRINCIPAL
    elif kind == "source":
        monkeypatch.setattr(
            fake, "source", lambda *a: (_ for _ in ()).throw(ValueError())
        )
    else:
        (
            fake.parent
            / q.recovery_name("c" * 40 if kind == "duplicate" else HEAD, TREE)
        ).write_bytes(b"bad")
    assert q.reconcile(fake, HEAD, TREE)["disposition"] == "ARM_EVIDENCE_INVALID"
    assert fake.creates == fake.children == 0


@pytest.mark.parametrize(
    "kind",
    [
        "extra",
        "source",
        "facts",
        "budget",
        "effects",
        "classification",
        "event",
        "duplicate",
        "crlf",
        "bytes",
        "hash",
    ],
)
def test_recovery_parser_closed(consumed, kind):
    fake, value = recovered(consumed)
    payload = (fake.parent / q.recovery_name(HEAD, TREE)).read_bytes()
    import json

    record = json.loads(payload)
    if kind == "extra":
        record["extra"] = 0
    elif kind == "source":
        record["source_head"] = "c" * 40
    elif kind == "facts":
        record["facts"]["principal_sid"] = PRINCIPAL.sid
    elif kind == "budget":
        record["budgets"]["SCHEDULER_CREATE_BUDGET"] = 1
    elif kind == "effects":
        record["effects"][q.ZERO_EFFECTS[0]] = False
    elif kind in {"classification", "event"}:
        record[kind] = "ARMED"
    elif kind == "bytes":
        record["predecessor_bytes"] += 1
    elif kind == "hash":
        record["predecessor_sha256"] = "0" * 64
    payload = q.canonical(record) + b"\n"
    if kind == "duplicate":
        payload = payload.replace(b'"schema":', b'"schema":"x","schema":')
    elif kind == "crlf":
        payload = payload.replace(b"\n", b"\r\n")
    with pytest.raises(ValueError):
        q.parse_recovery(payload, HEAD, TREE, value)


def test_recovery_authority_effect_closure():
    tree = ast.parse(Path(q.__file__).read_text(encoding="utf-8"))
    protected = {
        "recover",
        "recover_preflight",
        "read_consumed_predecessor",
        "load_launch_authority",
        "parse_recovery",
        "_recovery_ready",
    }
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in protected:
            calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)]
            assert not any(
                isinstance(n.func, ast.Attribute)
                and n.func.attr
                in {"create", "child", "unlink", "rename", "replace", "chmod"}
                or isinstance(n.func, ast.Name)
                and n.func.id == "arm"
                for n in calls
            )
    assert q.RECOVERY_ZERO_BUDGETS == (
        "SCHEDULER_CREATE_BUDGET",
        "SCHEDULER_UPDATE_BUDGET",
        "SCHEDULER_DELETE_BUDGET",
        "TASK_RUN_BUDGET",
        "D1R5_EXECUTION_BUDGET",
    )


@pytest.mark.parametrize("mode", ["recover", "recover-preflight"])
@pytest.mark.parametrize("missing", ["head", "tree", "interlock", "arm"])
def test_host_recovery_argument_authority(monkeypatch, mode, missing):
    argv = [mode, "--expected-head", HEAD, "--expected-tree", TREE]
    if mode == "recover":
        argv += ["--recover", q.RECOVERY_INTERLOCK]
    if missing in {"head", "tree"}:
        index = argv.index("--expected-" + missing)
        del argv[index : index + 2]
    elif missing == "interlock":
        if mode == "recover":
            del argv[-2:]
        else:
            argv += ["--recover", q.RECOVERY_INTERLOCK]
    else:
        argv += ["--arm", q.ARM_INTERLOCK]
    monkeypatch.setattr(host, "_WindowsRuntime", lambda: pytest.fail("runtime reached"))
    assert host.main(argv) == 2


@pytest.mark.parametrize(
    "mode,expected", [("recover-preflight", "RECOVERY_READY"), ("recover", "RECOVERED")]
)
def test_host_recovery_modes_fake_only(consumed, monkeypatch, capsys, mode, expected):
    fake, _, _ = consumed
    monkeypatch.setattr(host, "_WindowsRuntime", lambda: fake)
    argv = [mode, "--expected-head", HEAD, "--expected-tree", TREE]
    if mode == "recover":
        argv += ["--recover", q.RECOVERY_INTERLOCK]
    assert host.main(argv) == 0
    assert expected in capsys.readouterr().out
    assert fake.creates == fake.children == 0


def modeled_scheduler_projection(task):
    # A fixture model of the PS read-only projection; native resolution is never
    # called. The static test below anchors every production conversion step.
    import re

    projected = copy.deepcopy(task)
    for key in ("start_boundary", "end_boundary"):
        text = projected[key]
        if not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,7})?(?:Z|[+-][0-9]{2}:[0-9]{2})",
            text,
        ):
            raise ValueError("boundary unavailable")
        instant = datetime.fromisoformat(text)
        fraction = text.split(".", 1)[1] if "." in text else ""
        fraction = re.split(r"Z|[+-]", fraction)[0]
        if instant.microsecond or any(c != "0" for c in fraction):
            raise ValueError("boundary precision drift")
        projected[key] = instant.astimezone(UTC).isoformat(timespec="seconds")
    user = projected["principal_sid"]
    if user not in {"John", INCIDENT_PRINCIPAL.sid}:
        raise ValueError("principal unavailable")
    projected["principal_sid"] = INCIDENT_PRINCIPAL.sid
    return projected


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-10-15T06:20:00-07:00", "2026-10-15T06:35:00-07:00"),
        ("2026-10-15T13:20:00+00:00", "2026-10-15T13:35:00+00:00"),
        ("2026-10-15T15:20:00+02:00", "2026-10-15T09:35:00-04:00"),
        ("2026-10-15T13:20:00Z", "2026-10-15T13:35:00.0000000Z"),
    ],
)
@pytest.mark.parametrize("user", ["John", INCIDENT_PRINCIPAL.sid])
def test_modeled_real_host_projection_exact(start, end, user):
    value, _ = incident_records()
    raw = value.task | {
        "start_boundary": start,
        "end_boundary": end,
        "principal_sid": user,
    }
    assert modeled_scheduler_projection(raw) == value.task


@pytest.mark.parametrize(
    "field,value",
    [
        ("start_boundary", "2026-10-15T13:20:00"),
        ("end_boundary", "2026-10-15T13:35:00"),
        ("start_boundary", "bad"),
        ("end_boundary", "2026-02-30T13:35:00Z"),
        ("start_boundary", "2026-10-15T13:20:00.1Z"),
        ("end_boundary", "2026-10-15T13:35:00.0000001Z"),
        ("end_boundary", "2026-10-15T13:35:00+24:00"),
        ("principal_sid", "missing-user"),
        ("principal_sid", "S-bad"),
    ],
)
def test_modeled_projection_fail_closed(field, value):
    task = incident_records()[0].task | {field: value}
    with pytest.raises(ValueError):
        modeled_scheduler_projection(task)


def test_native_projection_conversion_source_contract():
    text = (ROOT / "scripts/arch134_d1r6_scheduler_create.ps1").read_text(
        encoding="utf-8"
    )
    boundary = text.split("function Convert-ObservedBoundary", 1)[1].split(
        "function Convert-ObservedPrincipalSid", 1
    )[0]
    assert (
        "[DateTimeOffset]::Parse($Value, "
        "[Globalization.CultureInfo]::InvariantCulture, "
        "[Globalization.DateTimeStyles]::None)" in boundary
    )
    assert "(?:Z|[+-][0-9]{2}:[0-9]{2})$" in boundary
    assert "TicksPerSecond" in boundary
    assert (
        ".ToUniversalTime().ToString(\"yyyy-MM-dd'T'HH:mm:sszzz\", "
        "[Globalization.CultureInfo]::InvariantCulture)" in boundary
    )
    principal = text.split("function Convert-ObservedPrincipalSid", 1)[1].split(
        "function Get-TaskObservation", 1
    )[0]
    assert "[Security.Principal.SecurityIdentifier]::new($Value).Value" in principal
    assert "[Security.Principal.NTAccount]::new($Value)" in principal
    assert ".Translate([Security.Principal.SecurityIdentifier]).Value" in principal
    projection = text.split("$projected = @{", 1)[1].split("# COM", 1)[0]
    assert (
        "start_boundary=(Convert-ObservedBoundary ([string]$trigger.StartBoundary))"
        in projection
    )
    assert (
        "end_boundary=(Convert-ObservedBoundary ([string]$trigger.EndBoundary))"
        in projection
    )
    assert (
        "principal_sid=(Convert-ObservedPrincipalSid ([string]$principal.UserId))"
        in projection
    )


@pytest.mark.parametrize("with_recovery", [False, True])
def test_competing_current_source_arm_blocks_recovery(consumed, with_recovery):
    fake, value, _ = consumed
    if with_recovery:
        recovered(consumed)
    # A competing source/session authority must never be silently preferred.
    (fake.parent / plan().arm_name).write_bytes(b"invalid")
    with pytest.raises(ValueError):
        if with_recovery:
            q.launch(fake, HEAD, TREE)
        else:
            q.recover_preflight(fake, HEAD, TREE)
    assert fake.creates == fake.children == 0
    assert q.reconcile(fake, HEAD, TREE)["evidence"] == "ARM_EVIDENCE_INVALID"


def test_nonincident_ordinary_arm_unchanged_with_historical_predecessor(fake):
    # A historical consumed incident is never used as ordinary launch authority.
    fake.now = datetime(2026, 10, 16, 3, tzinfo=UTC)
    value = q.Plan(HEAD, TREE, fake.now, fake.identity)
    assert q.arm(fake, HEAD, TREE, q.ARM_INTERLOCK) == "ARMED"
    (fake.parent / q.RECOVERY_PREDECESSOR_ARM_NAME).write_bytes(b"historical")
    assert q.load_launch_authority(fake, HEAD, TREE) == value
    assert q.launch(fake, HEAD, TREE) == 7
    assert fake.children == 1


@pytest.mark.parametrize("kind", ["recovery", "predecessor"])
def test_artifact_change_during_final_launch_readmission_blocks(
    consumed, monkeypatch, kind
):
    fake, value = recovered(consumed)
    original = fake.source
    calls = 0

    def source(*args):
        nonlocal calls
        calls += 1
        if calls == 3:
            name = q.recovery_name(HEAD, TREE) if kind == "recovery" else value.arm_name
            (fake.parent / name).write_bytes(b"changed")
        return original(*args)

    monkeypatch.setattr(fake, "source", source)
    with pytest.raises(ValueError):
        q.launch(fake, HEAD, TREE)
    assert fake.children == fake.creates == 0


def test_predecessor_change_at_final_recovery_admission_blocks(consumed, monkeypatch):
    fake, value, _ = consumed
    original = fake.source
    calls = 0

    def source(*args):
        nonlocal calls
        calls += 1
        if calls == 3:
            (fake.parent / value.arm_name).write_bytes(b"changed")
        return original(*args)

    monkeypatch.setattr(fake, "source", source)
    with pytest.raises(ValueError):
        q.recover(fake, HEAD, TREE, q.RECOVERY_INTERLOCK)
    assert not (fake.parent / q.recovery_name(HEAD, TREE)).exists()
    assert fake.children == fake.creates == 0
