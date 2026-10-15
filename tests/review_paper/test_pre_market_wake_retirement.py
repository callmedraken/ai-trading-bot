"""D1R7 uses synthetic journals and mocked host/native edges exclusively."""

from __future__ import annotations

import hashlib
import inspect
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import checkpoint_runner as runner
from scripts import run_test_certification as certification
from trading_bot.review_paper import pre_market_wake_overnight as old
from trading_bot.review_paper import pre_market_wake_retirement as q
from trading_bot.review_paper import pre_market_wake_retirement_host as host

ROOT = Path(__file__).resolve().parents[2]
HEAD, TREE = "a" * 40, "b" * 40
PRINCIPAL = old.Principal(r"DOMAIN\John", "S-1-5-21-1-2-3-1001")


class Fake:
    def __init__(self, parent, plan):
        self.parent, self.plan = parent, plan
        self.deletes = 0
        self.absent = False
        self.fail = None
        self.observations = 0

    def source(self, head, tree):
        assert (head, tree) == (HEAD, TREE)
        if self.fail == "source":
            raise ValueError("source drift")
        return (self.parent.parent / "repository",)

    def target(self):
        if self.fail == "target":
            raise ValueError("target drift")
        return (self.parent.parent / "target",)

    def frozen(self):
        if self.fail == "frozen":
            raise ValueError("frozen drift")
        return (self.parent.parent / "frozen",)

    def observe(self):
        self.observations += 1
        return {
            "principal": {"name": PRINCIPAL.name, "sid": PRINCIPAL.sid},
            "observation": {"status": "ABSENT"}
            if self.absent
            else {
                "status": "PRESENT",
                "task": self.plan.task,
                "state": 3,
                "last_result": 2,
                "last_run": q.LAST_RUN,
                "next_run": None,
            },
        }

    def delete(self, plan):
        records = q.parse((self.parent / q.EVIDENCE_NAME).read_bytes())
        assert records[-1]["event"] == "TASK_DELETE_INTENT"
        assert records[-1]["delete_budget_consumed"] == 1
        assert plan == self.plan
        self.deletes += 1
        assert self.deletes == 1
        self.absent = True
        return {"disposition": "CALL_RETURNED", "deletion_attempts": 1}


@pytest.fixture
def fake(tmp_path, monkeypatch):
    parent = tmp_path / "qualification"
    parent.mkdir()
    plan = old.Plan(
        old.RECOVERY_PREDECESSOR_HEAD,
        old.RECOVERY_PREDECESSOR_TREE,
        datetime(2026, 10, 15, 0, tzinfo=UTC),
        PRINCIPAL,
    )
    records = tuple(
        {
            "schema": old.SCHEMA,
            "event": event,
            "facts": plan.facts,
            "effects": dict.fromkeys(old.ZERO_EFFECTS, 0),
            "scheduler_task_create_calls": int(i >= 4),
            "classification": "INDETERMINATE" if event == "FINAL" else None,
        }
        for i, event in enumerate((*old.EVENTS[:6], "FINAL"))
    )
    payload = old.serialize_arm(records)
    monkeypatch.setattr(old, "RECOVERY_PREDECESSOR_ARM_BYTES", len(payload))
    monkeypatch.setattr(
        old, "RECOVERY_PREDECESSOR_ARM_SHA256", hashlib.sha256(payload).hexdigest()
    )
    (parent / plan.arm_name).write_bytes(payload)
    return Fake(parent, plan)


def test_literal_incident_pins():
    assert old.RECOVERY_PREDECESSOR_HEAD == "3cf4284d017e362eee58a2f27526ab4de8f292a2"
    assert old.RECOVERY_PREDECESSOR_TREE == "16a48a12756bb6d810799444859334ce6305001d"
    assert old.RECOVERY_PREDECESSOR_ARM_BYTES == 16917
    assert (
        old.RECOVERY_PREDECESSOR_ARM_SHA256
        == "b62959f9988dcc42e4881e45ed95abcf4abc2b6d2932514c7253165e1223955c"
    )
    assert old.RECOVERY_PREDECESSOR_ARM_NAME == (
        "arch134-d1r6-2026-10-15-7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343-"
        "3cf4284d017e362eee58a2f27526ab4de8f292a2-16a48a12756bb6d810799444859334ce6305001d.jsonl"
    )
    assert q.INTERLOCK == "AUTHORIZE_ARCH134_D1R7_ONE_STALE_WAKE_RETIREMENT"
    assert q.BUDGETS == {
        "TASK_DELETE_BUDGET": 1,
        "TASK_CREATE_BUDGET": 0,
        "TASK_UPDATE_BUDGET": 0,
        "TASK_RUN_BUDGET": 0,
        "D1R5_EXECUTION_BUDGET": 0,
        "D1_OPERATIONS": 0,
        "D2_OPERATIONS": 0,
        "LIVE_EFFECTS": 0,
    }


def test_preflight_zero_mutation(fake):
    before = {p.name: p.read_bytes() for p in fake.parent.iterdir()}
    admitted = q.preflight(fake, HEAD, TREE)
    assert admitted.plan == fake.plan
    assert before == {p.name: p.read_bytes() for p in fake.parent.iterdir()}
    assert fake.deletes == 0


@pytest.mark.parametrize(
    "kind",
    [
        "source",
        "target",
        "frozen",
        "parent",
        "incident",
        "size",
        "hash",
        "launch",
        "result",
        "recovery",
        "retirement",
        "competing",
    ],
)
def test_each_admission_blocks(fake, monkeypatch, kind):
    if kind in {"source", "target", "frozen"}:
        fake.fail = kind
    elif kind == "parent":
        monkeypatch.setattr(
            old, "checked_parent", lambda *a: (_ for _ in ()).throw(ValueError())
        )
    elif kind == "incident":
        (fake.parent / fake.plan.arm_name).unlink()
    elif kind == "size":
        monkeypatch.setattr(old, "RECOVERY_PREDECESSOR_ARM_BYTES", 1)
    elif kind == "hash":
        monkeypatch.setattr(old, "RECOVERY_PREDECESSOR_ARM_SHA256", "0" * 64)
    else:
        name = {
            "launch": fake.plan.arm_name.replace(".jsonl", "-launch.jsonl"),
            "result": fake.plan.result_name,
            "recovery": "arch134-d1r6-consumed-arm-recovery-x.json",
            "retirement": q.EVIDENCE_NAME,
            "competing": fake.plan.arm_prefix + "extra.jsonl",
        }[kind]
        (fake.parent / name).write_bytes(b"collision")
    with pytest.raises((ValueError, OSError)):
        q.preflight(fake, HEAD, TREE)
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "BLOCKED"
    assert fake.deletes == 0


@pytest.mark.parametrize(
    "field",
    list(
        old.Plan(
            old.RECOVERY_PREDECESSOR_HEAD,
            old.RECOVERY_PREDECESSOR_TREE,
            datetime(2026, 10, 15, 0, tzinfo=UTC),
            PRINCIPAL,
        ).task
    ),
)
def test_every_task_projection_field_exact(fake, monkeypatch, field):
    observe = fake.observe

    def drift():
        value = observe()
        original = value["observation"]["task"][field]
        value["observation"]["task"][field] = (
            not original if type(original) is bool else "drift"
        )
        return value

    monkeypatch.setattr(fake, "observe", drift)
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "BLOCKED"
    assert fake.deletes == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("state", 4),
        ("state", 2),
        ("state", True),
        ("last_result", 0),
        ("last_result", 267011),
        ("last_result", 2.0),
        ("last_run", "2026-10-16T06:20:00"),
        ("last_run", "2026-10-15T13:20:00"),
        ("next_run", "1899-12-30T00:00:00"),
        ("next_run", "2026-10-16T06:20:00"),
        ("status", "ABSENT"),
        ("extra", 1),
    ],
)
def test_state_fingerprint_exact(fake, monkeypatch, field, value):
    observe = fake.observe

    def drift():
        result = observe()
        result["observation"][field] = value
        return result

    monkeypatch.setattr(fake, "observe", drift)
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "BLOCKED"
    assert fake.deletes == 0


@pytest.mark.parametrize("field", ["name", "sid"])
def test_principal_exact(fake, monkeypatch, field):
    observe = fake.observe

    def drift():
        result = observe()
        result["principal"][field] += "drift"
        return result

    monkeypatch.setattr(fake, "observe", drift)
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "BLOCKED"


@pytest.mark.parametrize(
    "interlock", ["", None, True, q.INTERLOCK.lower(), q.INTERLOCK + " "]
)
def test_exact_interlock(fake, interlock):
    assert q.retire(fake, HEAD, TREE, interlock) == "BLOCKED"
    assert not (fake.parent / q.EVIDENCE_NAME).exists()
    assert fake.deletes == 0


def test_retired_once_double_absence_and_unchanged_incident(fake):
    path = fake.parent / fake.plan.arm_name
    before, stamp = path.read_bytes(), path.stat().st_mtime_ns
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "RETIRED"
    records = q.parse((fake.parent / q.EVIDENCE_NAME).read_bytes())
    assert tuple(r["event"] for r in records) == (*q.EVENTS, "FINAL")
    assert records[-1]["deletion_attempts"] == 1
    assert records[-1]["classification"] == "RETIRED"
    assert fake.observations == 9  # preflight + 6 final admissions + 2 absence
    assert q.reconcile(fake, HEAD, TREE) == {
        "status": "PASS",
        "classification": "RETIRED",
    }
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "BLOCKED"
    assert fake.deletes == 1
    assert (path.read_bytes(), path.stat().st_mtime_ns) == (before, stamp)


@pytest.mark.parametrize(
    "response,expected",
    [
        ({"disposition": "NOT_CALLED", "deletion_attempts": 0}, "BLOCKED"),
        ({"disposition": "INDETERMINATE", "deletion_attempts": 1}, "INDETERMINATE"),
        ({"disposition": "CALL_RETURNED", "deletion_attempts": True}, "INDETERMINATE"),
        ({"disposition": "CALL_RETURNED", "deletion_attempts": 2}, "INDETERMINATE"),
        ({}, "INDETERMINATE"),
        (None, "INDETERMINATE"),
    ],
)
def test_transport_results_no_retry(fake, monkeypatch, response, expected):
    calls = []
    monkeypatch.setattr(fake, "delete", lambda p: calls.append(p) or response)
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == expected
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "BLOCKED"
    assert len(calls) == 1
    assert (
        q.parse((fake.parent / q.EVIDENCE_NAME).read_bytes())[-1]["classification"]
        == expected
    )


@pytest.mark.parametrize(
    "point", ["before_entry", "after_entry", "first_absence", "second_absence"]
)
def test_ambiguity_consumed(fake, monkeypatch, point):
    delete = fake.delete

    def fail(plan):
        if point == "before_entry":
            raise OSError("process entry unknown")
        result = delete(plan)
        if point == "after_entry":
            raise OSError("post-entry")
        observations = iter(
            ({"status": "PRESENT"}, {"status": "ABSENT"})
            if point == "first_absence"
            else ({"status": "ABSENT"}, {"status": "PRESENT"})
        )
        monkeypatch.setattr(
            fake,
            "observe",
            lambda: {
                "principal": {"name": PRINCIPAL.name, "sid": PRINCIPAL.sid},
                "observation": next(observations),
            },
        )
        return result

    monkeypatch.setattr(fake, "delete", fail)
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "INDETERMINATE"
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "BLOCKED"
    assert fake.deletes <= 1
    assert q.reconcile(fake, HEAD, TREE)["status"] == "STOP"


@pytest.mark.parametrize("boundary", range(1, 10))
def test_fsync_failure_never_retries(fake, monkeypatch, boundary):
    calls = []
    sync = q.os.fsync

    def fsync(fd):
        calls.append(fd)
        if len(calls) == boundary:
            raise OSError("fsync ambiguous")
        sync(fd)

    monkeypatch.setattr(q.os, "fsync", fsync)
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == (
        "BLOCKED" if boundary < 6 else "INDETERMINATE"
    )
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "BLOCKED"
    assert len(calls) == boundary
    assert fake.deletes == int(boundary > 6)


@pytest.mark.parametrize("point", ["write", "flush", "close", "short"])
def test_file_write_ambiguity_consumed(fake, monkeypatch, point):
    opened = Path.open

    class Stream:
        def __init__(self, real):
            self.real = real

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.real.close()
            if point == "close":
                raise OSError("close ambiguous")

        def write(self, chunk):
            if point == "write":
                self.real.write(chunk)
                raise OSError("write ambiguous")
            if point == "short":
                return self.real.write(chunk[:3])
            return self.real.write(chunk)

        def flush(self):
            self.real.flush()
            if point == "flush":
                raise OSError("flush ambiguous")

        def fileno(self):
            return self.real.fileno()

    def opening(path, mode="r", *args, **kwargs):
        real = opened(path, mode, *args, **kwargs)
        return Stream(real) if mode == "xb" and path.name == q.EVIDENCE_NAME else real

    monkeypatch.setattr(Path, "open", opening)
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == (
        "INDETERMINATE" if point == "close" else "BLOCKED"
    )
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "BLOCKED"
    assert fake.deletes == int(point == "close")


@pytest.mark.parametrize(
    "kind", ["source", "target", "frozen", "incident", "result", "launch", "recovery"]
)
def test_final_mutable_readmission(fake, monkeypatch, kind):
    admit = q._admit
    calls = []

    def drift(*args, **kwargs):
        calls.append(1)
        if len(calls) == 7:
            if kind in {"source", "target", "frozen"}:
                fake.fail = kind
            else:
                name = {
                    "incident": fake.plan.arm_name,
                    "result": fake.plan.result_name,
                    "launch": fake.plan.arm_name.replace(".jsonl", "-launch.jsonl"),
                    "recovery": "arch134-d1r6-consumed-arm-recovery-x.json",
                }[kind]
                (fake.parent / name).write_bytes(b"drift")
        return admit(*args, **kwargs)

    monkeypatch.setattr(q, "_admit", drift)
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "BLOCKED"
    assert fake.deletes == 0


@pytest.mark.parametrize(
    "kind",
    [
        "absent_journal",
        "present_task",
        "prefix",
        "bad_bytes",
        "wrong_source",
        "wrong_calls",
        "effects",
        "budget",
        "incident_changed",
        "extra",
    ],
)
def test_reconcile_requires_evidence_and_actual_absence(fake, kind):
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "RETIRED"
    path = fake.parent / q.EVIDENCE_NAME
    records = list(q.parse(path.read_bytes()))
    if kind == "absent_journal":
        path.unlink()
    elif kind == "present_task":
        fake.absent = False
    elif kind == "prefix":
        path.write_bytes(q.serialize(tuple(records[:-1])))
    elif kind == "bad_bytes":
        path.write_bytes(path.read_bytes() + b" ")
    elif kind == "incident_changed":
        (fake.parent / fake.plan.arm_name).write_bytes(b"changed")
    elif kind == "extra":
        (fake.parent / "arch134-d1r7-stale-wake-retirement-other").write_bytes(b"x")
    else:
        if kind == "wrong_source":
            for r in records:
                r["facts"]["source_head"] = "c" * 40
        elif kind == "wrong_calls":
            records[-1]["deletion_attempts"] = 0
        elif kind == "effects":
            records[-1]["effects"]["D1_OPERATIONS"] = 1
        else:
            records[-1]["facts"]["budgets"]["TASK_DELETE_BUDGET"] = 2
        path.write_bytes(b"".join(old.canonical(r) + b"\n" for r in records))
    assert q.reconcile(fake, HEAD, TREE)["status"] == "STOP"
    assert fake.deletes == 1


def test_absence_alone_never_passes(fake):
    fake.absent = True
    assert q.reconcile(fake, HEAD, TREE)["status"] == "STOP"
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "BLOCKED"


@pytest.mark.parametrize("mode", ["Observe", "Delete"])
def test_fixed_binary_transport(monkeypatch, fake, mode):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert argv == [
            old.POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(q.WORKTREE / "scripts" / "arch134_d1r7_scheduler_retire.ps1"),
            "-Mode",
            mode,
        ]
        request = (
            {}
            if mode == "Observe"
            else {
                "interlock": q.INTERLOCK,
            }
        )
        assert kwargs == {
            "input": old.canonical(request) + b"\n",
            "capture_output": True,
            "timeout": 45,
            "check": False,
        }
        return SimpleNamespace(returncode=0, stdout=b'{"ok":true}\r\n')

    monkeypatch.setattr(host.subprocess, "run", run)
    assert host._WindowsRuntime()._scheduler(
        mode, fake.plan if mode == "Delete" else None
    ) == {"ok": True}
    assert len(calls) == 1


@pytest.mark.parametrize(
    "code,payload,accepted",
    [
        (2, b'{"disposition":"NOT_CALLED","deletion_attempts":0}', True),
        (2, b'{"disposition":"INDETERMINATE","deletion_attempts":1}', False),
        (0, b'{"x":1,"x":1}', False),
        (0, b"x" * 16385, False),
    ],
)
def test_helper_failure_classification(monkeypatch, fake, code, payload, accepted):
    monkeypatch.setattr(
        host.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(returncode=code, stdout=payload),
    )
    if accepted:
        assert host._WindowsRuntime().delete(fake.plan)["disposition"] == "NOT_CALLED"
    else:
        with pytest.raises(ValueError):
            host._WindowsRuntime().delete(fake.plan)


@pytest.mark.parametrize(
    "mode", ["Create", "Update", "Run", "Stop", "Principal", "delete", ""]
)
def test_no_extra_native_modes(monkeypatch, mode):
    monkeypatch.setattr(
        host.subprocess, "run", lambda *a, **kw: pytest.fail("native process")
    )
    with pytest.raises(ValueError):
        host._WindowsRuntime()._scheduler(mode)


@pytest.mark.parametrize(
    "mode",
    ["arm", "launch", "recover", "create", "delete", "run", "prepare", "execute"],
)
def test_no_extra_runtime_modes(mode):
    with pytest.raises(ValueError):
        host.build_parser().parse_args([mode])


def test_powershell_closed_fingerprint_and_single_delete():
    text = (ROOT / "scripts/arch134_d1r7_scheduler_retire.ps1").read_text()
    assert text.count(".DeleteTask(") == 1
    for token in (
        ".RegisterTaskDefinition(",
        ".Run(",
        ".Stop(",
        ".NewTask(",
        ".Create(",
        "Set-ExecutionPolicy",
    ):
        assert token not in text
    assert "[ValidateSet('Observe','Delete')]" in text
    assert "function Get-ConsumedPrincipal" in text
    assert old.RECOVERY_PREDECESSOR_ARM_SHA256 in text
    assert str(old.RECOVERY_PREDECESSOR_ARM_BYTES) in text
    assert old.RECOVERY_PREDECESSOR_ARM_NAME in text
    assert "$consumedAgain = Get-ConsumedPrincipal" in text
    assert "principal_name" not in text[text.index("try {\n    if ($args.Count") :]
    assert (
        "$observed = Get-TaskObservation\n"
        "        Assert-FrozenObservation $observed $identityAgain\n"
        "        $attempted = $true\n"
        "        $null = $folder.DeleteTask(" in text
    )
    assert "DeleteTask('AITradingBot-Arch134-D1R6-OvernightWake-v1', 0)" in text
    for token in (
        "DateTimeOffset",
        "ToUniversalTime",
        "TicksPerSecond",
        "NTAccount",
        "SecurityIdentifier",
        "2026-10-15T06:20:00",
        "1899-12-30T00:00:00",
    ):
        assert token in text
    # R3 observation algorithms are copied exactly, with no changed semantics.
    predecessor = (ROOT / "scripts/arch134_d1r6_scheduler_create.ps1").read_text()
    start, end = "function Convert-ObservedBoundary", "function Get-TaskObservation"
    assert (
        text[text.index(start) : text.index(end)]
        == predecessor[predecessor.index(start) : predecessor.index(end)]
    )
    for field in Fake.__dict__:  # Fake has no child/create/run seam either.
        assert field not in {"child", "create", "run"}
    assert (
        set(q.Runtime.__dict__) & {"child", "create", "run", "update", "stop"} == set()
    )
    assert "pre_market_wake_overnight_host" not in inspect.getsource(host)
    assert "subprocess" not in inspect.getsource(q)


def test_registry_and_inventory():
    spec = runner._checkpoint_specs()[runner.ARCH134_D1R7_NAME]
    assert spec.preflight is spec.execute is None
    assert spec.remote_branch == host.BRANCH
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), host.BRANCH, "push")
        == spec.name
    )
    assert runner.resolve_ci_certification_profile(spec.name) == "robinhood"
    assert runner._arch134_d1r7_authority_check(ROOT) == ()
    assert {
        p: len(
            certification.select_inventory(certification.discover_inventory(ROOT), p)
        )
        for p in certification.PROFILES
    } == {"full": 177, "robinhood": 100, "legacy": 215, "exhaustive": 392}


@pytest.mark.parametrize("frozen", [False, True])
@pytest.mark.parametrize(
    "drift",
    [None, "root", "branch", "head", "tree", "status", "origin", "registry", "remote"],
)
def test_exact_host_source_admission(monkeypatch, tmp_path, frozen, drift):
    # No Git or native host process executes; every response is modeled.
    own = tmp_path / "retirement"
    live = tmp_path / "live"
    own.mkdir()
    live.mkdir()
    monkeypatch.setattr(q, "WORKTREE", own)
    monkeypatch.setattr(old, "WORKTREE", live)
    monkeypatch.setattr(
        host,
        "__file__",
        str(own / "src/trading_bot/review_paper/pre_market_wake_retirement_host.py"),
    )
    monkeypatch.setattr(host.sys, "modules", {})
    monkeypatch.setattr(host, "os", SimpleNamespace(name="nt"))
    head, tree = (
        (old.RECOVERY_PREDECESSOR_HEAD, old.RECOVERY_PREDECESSOR_TREE)
        if frozen
        else (HEAD, TREE)
    )
    root = live if frozen else own
    branch = host.FROZEN_BRANCH if frozen else host.BRANCH
    answers = {
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
        ("merge-base", host.BASE_HEAD, head): host.BASE_HEAD,
        ("worktree", "list", "--porcelain"): "worktree "
        + str(own)
        + "\nworktree "
        + str(live),
    }
    keys = {
        "root": ("rev-parse", "--show-toplevel"),
        "branch": ("branch", "--show-current"),
        "head": ("rev-parse", "HEAD"),
        "tree": ("rev-parse", "HEAD^{tree}"),
        "status": ("status", "--porcelain=v1", "--untracked-files=all"),
        "origin": ("remote", "get-url", "origin"),
        "registry": ("worktree", "list", "--porcelain"),
        "remote": ("ls-remote", "origin", "refs/heads/" + branch),
    }
    if drift:
        answers[keys[drift]] = "drift"
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert argv[:3] == ["git", "-C", str(root)]
        return SimpleNamespace(stdout=answers[tuple(argv[3:])])

    monkeypatch.setattr(host.subprocess, "run", run)
    # Frozen predecessor intentionally ignores a moved remote; never fast-forward it.
    if drift is None or (frozen and drift == "remote"):
        assert host.admit_source(head, tree, frozen=frozen) == (own, live)
    else:
        with pytest.raises(ValueError):
            host.admit_source(head, tree, frozen=frozen)
    assert not any("merge" in argv or "fetch" in argv for argv in calls)
    if frozen:
        assert not any("ls-remote" in argv for argv in calls)


@pytest.mark.parametrize(
    "head,tree",
    [
        ("c" * 40, old.RECOVERY_PREDECESSOR_TREE),
        (old.RECOVERY_PREDECESSOR_HEAD, "d" * 40),
    ],
)
def test_frozen_host_identity_cannot_be_selected(monkeypatch, head, tree):
    monkeypatch.setattr(
        host.subprocess, "run", lambda *a, **kw: pytest.fail("git entry")
    )
    with pytest.raises(ValueError):
        host.admit_source(head, tree, frozen=True)


@pytest.mark.parametrize("mode", ["preflight", "retire", "reconcile"])
def test_host_dispatch_mocked_only(fake, monkeypatch, capsys, mode):
    monkeypatch.setattr(host, "_WindowsRuntime", lambda: fake)
    if mode == "reconcile":
        assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "RETIRED"
    args = [mode, "--expected-head", HEAD, "--expected-tree", TREE]
    if mode == "retire":
        args += ["--retire", q.INTERLOCK]
    assert host.main(args) == 0
    assert '"status": "PASS"' in capsys.readouterr().out


def test_no_trading_or_provider_imports():
    import ast

    for module in (q, host):
        tree = ast.parse(inspect.getsource(module))
        imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert imports <= {
            None,
            "__future__",
            "pathlib",
            "typing",
            "dataclasses",
            "trading_bot.review_paper",
            "trading_bot.review_paper.pre_market_wake_qualification",
        }
        text = inspect.getsource(module)
        for token in (
            "QUALIFY_WAKE_INTERLOCK",
            "Popen(",
            "sqlite3",
            "httpx",
            "Credential",
            "requests.",
            ".child(",
            ".create(",
        ):
            assert token not in text


def test_native_expected_task_fields_match_frozen_plan():
    text = (ROOT / "scripts/arch134_d1r7_scheduler_retire.ps1").read_text()
    plan = old.Plan(
        old.RECOVERY_PREDECESSOR_HEAD,
        old.RECOVERY_PREDECESSOR_TREE,
        datetime(2026, 10, 15, 0, tzinfo=UTC),
        PRINCIPAL,
    )
    block = text.partition("    $expected = @{\n")[2].partition("    }\n")[0]
    expected = {}
    for key, value in plan.task.items():
        if key == "principal_sid":
            wanted = "$Identity.sid"
        elif type(value) is bool:
            wanted = "$true" if value else "$false"
        elif type(value) is int:
            wanted = str(value)
        else:
            wanted = "'" + value.replace("'", "''") + "'"
        expected[key] = wanted
    actual = dict(line.strip().split("=", 1) for line in block.splitlines())
    assert actual == expected


@pytest.mark.parametrize("point", ["write", "flush", "short"])
@pytest.mark.parametrize("boundary", [6, 7])
def test_intent_and_returned_io_ambiguity_never_retries(
    fake, monkeypatch, point, boundary
):
    opened = Path.open
    counts = {"write": 0, "flush": 0}

    class Stream:
        def __init__(self, real):
            self.real = real

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.real.close()

        def write(self, chunk):
            counts["write"] += 1
            if counts["write"] == boundary and point in {"write", "short"}:
                written = self.real.write(chunk if point == "write" else chunk[:3])
                if point == "write":
                    raise OSError("write uncertain")
                return written
            return self.real.write(chunk)

        def flush(self):
            counts["flush"] += 1
            self.real.flush()
            if counts["flush"] == boundary and point == "flush":
                raise OSError("flush uncertain")

        def fileno(self):
            return self.real.fileno()

    def opening(path, mode="r", *args, **kwargs):
        real = opened(path, mode, *args, **kwargs)
        return Stream(real) if mode == "xb" and path.name == q.EVIDENCE_NAME else real

    monkeypatch.setattr(Path, "open", opening)
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "INDETERMINATE"
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "BLOCKED"
    assert counts["write"] == boundary
    assert fake.deletes == int(boundary == 7)


def test_final_reread_failure_is_consumed(fake, monkeypatch):
    monkeypatch.setattr(q, "read_evidence", lambda *a: (_ for _ in ()).throw(OSError()))
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "INDETERMINATE"
    assert q.retire(fake, HEAD, TREE, q.INTERLOCK) == "BLOCKED"
    assert fake.deletes == 1


@pytest.mark.parametrize(
    "point", ["missing", "extra", "executable", "wrong_pin", "predecessor"]
)
def test_retirement_successor_pins_fail_closed(monkeypatch, point):
    overrides = dict(runner.ARCH134_D1R7_TEST_PIN_OVERRIDES)
    first = next(iter(overrides))
    before, _ = overrides[first]
    if point == "missing":
        overrides.pop(first)
    elif point == "extra":
        overrides["tests/unreviewed.py"] = ("a" * 40, "b" * 40)
    elif point == "executable":
        overrides["src/trading_bot/review_paper/armed_session.py"] = (
            "a" * 40,
            "b" * 40,
        )
    elif point == "wrong_pin":
        overrides[first] = (before, "0" * 40)
    else:
        monkeypatch.setattr(runner, "ARCH134_D1R6_SOURCE_PINS", {})
    monkeypatch.setattr(runner, "ARCH134_D1R7_TEST_PIN_OVERRIDES", overrides)
    with pytest.raises(ValueError):
        runner._arch134_d1r7_test_pin(first, before)
    # The inherited authority fails closed on the same changed pin dictionaries.
    assert runner._arch134_d1r7_authority_check(ROOT)
