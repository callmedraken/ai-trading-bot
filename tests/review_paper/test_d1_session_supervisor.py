"""D1R9 source-only: fake clocks/native edges and disposable external stores."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from tests.review_paper.test_d1_session_execution import Fake as ExecutionFake

from scripts import arch134_d1r9_bridge as bridge
from scripts import checkpoint_runner as runner
from scripts import run_test_certification as certification
from trading_bot.review_paper import d1_session_authorization as q
from trading_bot.review_paper import d1_session_execution_store as e
from trading_bot.review_paper import d1_session_supervisor as c
from trading_bot.review_paper import d1_session_supervisor_host as host
from trading_bot.review_paper import d1_session_supervisor_store as s

ROOT = Path(__file__).resolve().parents[2]
SOURCE = dict(branch=s.BRANCH, head="c" * 40, tree="d" * 40)
NY = ZoneInfo("America/New_York")


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=NY).astimezone(UTC)


class Crash(BaseException):
    pass


class Fake:
    def __init__(self, root):
        self.parent = root / "qualification"
        self.parent.mkdir()
        self.now = instant("2026-10-17T12:00")
        self.events = []
        self.children = []
        self.waits = []
        self.scheduler = True
        self.scheduler_fault = False
        self.drift = None
        self.liveness = True
        self.child_fault = None
        self.crash_after = None
        self.effect_root = root / "effects"
        self.effect_root.mkdir()
        self.execution = ExecutionFake(self.effect_root)
        self.execution.parent = self.parent
        self.execution.source = q.Source(**s.D1R8)
        self.binding = {
            key: dict(device=1, inode=i + 1, bytes=1, sha256="a" * 64)
            for i, key in enumerate(("paper", "sessions", "python"))
        }

    def clock(self):
        return self.now

    def admit(self, facts):
        self.events.append("admit")
        assert facts["source"] == SOURCE
        assert facts["d1r7"] == s.D1R7 and facts["d1r8"] == s.D1R8
        if self.drift == "source":
            raise ValueError("fake source drift")
        return (self.parent.parent / "repository",)

    def predecessors(self):
        self.events.append("predecessors")
        if self.drift == "predecessor":
            raise ValueError("fake immutable predecessor drift")

    def runtime_binding(self):
        return copy.deepcopy(self.binding)

    def admit_runtime(self, binding, *, entered=False):
        self.events.append("runtime")
        assert binding == self.binding
        if self.drift == "runtime":
            raise ValueError("fake runtime drift")

    def scheduler_matches(self):
        self.events.append("scheduler_observe")
        return self.scheduler

    def scheduler_create(self):
        assert self.journal().state == "SCHEDULER_CREATE_INTENT"
        self.events.append("scheduler_create")
        self.scheduler = True
        if self.scheduler_fault:
            raise OSError("uncertain native ack")

    def scheduler_run(self):
        assert self.journal().state == "SCHEDULER_RUN_INTENT"
        self.events.append("scheduler_run")

    def child_idle(self):
        return self.liveness

    def child(self, kind):
        journal = self.journal()
        assert journal.state == kind.upper() + "_DELEGATION_INTENT"
        assert journal.rows[-1]["effects"][kind + "_attempts"] == 1
        assert all(
            event in self.events[-3:] for event in ("admit", "predecessors", "runtime")
        )
        self.children.append(kind)
        if self.child_fault == kind:
            raise OSError("uncertain child entry")
        if self.child_fault == kind + "_partial":
            path = (
                c.d1r7_path(self.parent, c.validate_binding(journal.facts))
                if kind == "d1r7"
                else self.execution.output
            )
            path.write_bytes(b'{"partial":')
        elif kind == "d1r7":
            plan = q.Plan(q.Source(**s.D1R7), q.Source(**s.D1R8), self.now)
            self.execution.publish(plan=plan)
        else:
            self.execution.now = self.now
            result = self.execution.run()
            assert result in {"PAPER_EXECUTED", "NO_SIGNAL", "RISK_REJECTED"}
        if self.crash_after == kind:
            raise Crash()

    def wait(self, seconds):
        assert 0 < seconds <= 60
        self.waits.append(seconds)
        raise Crash()

    def authorize(self):
        return c.authorize(self, SOURCE, c.INTERLOCK)

    def journal(self):
        active = s.find_active(self.parent)
        if active is not None:
            return active
        paths = list(self.parent.glob("arch134-d1r9-SPY-*.jsonl"))
        return s.Journal.load(paths[0])


@pytest.fixture
def fake(tmp_path):
    return Fake(tmp_path)


@pytest.mark.parametrize(
    "at,target",
    [
        ("2026-10-16T16:01", "2026-10-19"),
        ("2026-10-17T12:00", "2026-10-19"),
        ("2026-10-18T12:00", "2026-10-19"),
        ("2026-11-26T12:00", "2026-11-27"),
        ("2026-10-19T08:00", "2026-10-19"),
        ("2026-10-19T09:20", "2026-10-19"),
        ("2026-10-19T09:25", "2026-10-19"),
        ("2026-10-19T09:35", "2026-10-19"),
        ("2026-10-19T15:54:59", "2026-10-19"),
        ("2026-10-19T15:55", "2026-10-20"),
        ("2026-11-27T12:54:59", "2026-11-27"),
        ("2026-11-27T12:55", "2026-11-30"),
        ("2026-10-30T17:00", "2026-11-02"),
        ("2027-03-12T17:00", "2027-03-15"),
    ],
)
def test_arbitrary_time_published_selection(at, target):
    assert c.select_target(instant(at)).isoformat() == target


@pytest.mark.parametrize(
    "at",
    [datetime(2026, 10, 19), instant("2029-01-02T12:00"), instant("2025-12-31T12:00")],
)
def test_unsupported_or_naive_clock_fails_closed(at):
    with pytest.raises(ValueError):
        c.select_target(at)


@pytest.mark.parametrize(
    "at,state",
    [
        ("2026-10-17T12:00", "NEXT_SESSION_WAIT"),
        ("2026-10-19T08:00", "PREMARKET_WAIT"),
        ("2026-10-19T09:20", "D1R8_WAIT"),
        ("2026-10-19T09:25", "D1R8_WAIT"),
        ("2026-10-19T09:34:59", "D1R8_WAIT"),
    ],
)
def test_restart_every_wait_recomputes_fixed_target(fake, at, state):
    fake.now = instant(at)
    journal = fake.authorize()
    assert c.step(fake, journal) == state
    resumed = s.Journal.load(journal.path)
    assert c.step(fake, resumed) == state
    assert len(fake.children) == int(state == "D1R8_WAIT")
    assert resumed.facts["target_session"] == "2026-10-19"
    assert len(resumed.rows) == len(journal.rows)
    fake.now = instant("2026-10-19T09:35")
    assert c.step(fake, resumed) == "PAPER_EXECUTED"
    assert fake.children == ["d1r7", "d1r8"]


@pytest.mark.parametrize("at", ["2026-10-19T09:35", "2026-10-19T10:00"])
def test_late_start_bridges_without_second_prompt(fake, at, monkeypatch):
    fake.now = instant(at)
    monkeypatch.setattr(
        "builtins.input", lambda *a: pytest.fail("second operator prompt")
    )
    journal = fake.authorize()
    assert c.step(fake, journal) == "PAPER_EXECUTED"
    publication = next(
        row["proof"] for row in journal.rows if row["event"] == "D1R7_READY"
    )
    payload = fake.execution.predecessor.read_bytes()
    assert publication == dict(
        bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest()
    )
    assert fake.execution.proof.publication_confirmed is True
    assert fake.execution.proof.d1r7_sha256 == publication["sha256"]
    effects = fake.execution.rows()[-1]["effects"]
    assert effects["paper_fill_mutations"] == 1
    assert all(effects[key] <= value for key, value in e.BUDGETS.items())
    assert all(effects[key] == 0 for key, value in e.BUDGETS.items() if value == 0)
    assert journal.rows[-1]["effects"] == dict(
        d1r7_attempts=1,
        d1r8_attempts=1,
        scheduler_creates=0,
        scheduler_updates=0,
        scheduler_runs=1,
    )


@pytest.mark.parametrize("kind", ["d1r7", "d1r8"])
def test_restart_after_complete_child_independently_reconciles(fake, kind):
    fake.now = instant("2026-10-19T10:00")
    fake.crash_after = kind
    journal = fake.authorize()
    with pytest.raises(Crash):
        c.step(fake, journal)
    assert journal.state == kind.upper() + "_DELEGATION_INTENT"
    fake.crash_after = None
    resumed = s.Journal.load(journal.path)
    if kind == "d1r8":
        fake.now = instant("2026-10-20T10:00")
    assert c.step(fake, resumed) == "PAPER_EXECUTED"
    assert fake.children == ["d1r7", "d1r8"]
    assert c.step(fake, s.Journal.load(journal.path)) == "PAPER_EXECUTED"
    assert fake.children == ["d1r7", "d1r8"]


@pytest.mark.parametrize("fault", ["d1r7", "d1r8", "d1r7_partial", "d1r8_partial"])
def test_ambiguous_child_entry_is_consumed_and_never_retried(fake, fault):
    fake.now = instant("2026-10-19T10:00")
    fake.child_fault = fault
    journal = fake.authorize()
    assert c.step(fake, journal) == "INDETERMINATE"
    count = len(fake.children)
    fake.child_fault = None
    assert c.step(fake, s.Journal.load(journal.path)) == "INDETERMINATE"
    assert len(fake.children) == count


@pytest.mark.parametrize("kind", ["d1r7", "d1r8"])
def test_intent_without_child_entry_or_evidence_never_launches(fake, kind):
    fake.now = instant("2026-10-19T10:00")
    journal = fake.authorize()
    journal.append("D1R7_DELEGATION_INTENT", fake.now)
    if kind == "d1r8":
        fake.child("d1r7")
        publication, _ = c.proof_d1r7(fake, c.validate_binding(journal.facts))
        journal.append("D1R7_READY", fake.now, proof=publication)
        journal.append("D1R8_DELEGATION_INTENT", fake.now)
    before = list(fake.children)
    assert c.step(fake, s.Journal.load(journal.path)) == "INDETERMINATE"
    assert fake.children == before


def test_uncertain_liveness_blocks_even_complete_child_artifact(fake):
    fake.now = instant("2026-10-19T10:00")
    fake.crash_after = "d1r7"
    journal = fake.authorize()
    with pytest.raises(Crash):
        c.step(fake, journal)
    fake.liveness = False
    assert c.step(fake, s.Journal.load(journal.path)) == "INDETERMINATE"
    assert fake.children == ["d1r7"]


@pytest.mark.parametrize("drift", ["source", "runtime", "predecessor"])
def test_readmission_drift_never_enters_children(fake, drift):
    journal = fake.authorize()
    fake.drift = drift
    fake.now = instant("2026-10-19T10:00")
    assert c.step(fake, journal) == "BLOCKED"
    assert fake.children == []


def test_forward_clock_misses_fixed_session_never_rolls(fake):
    journal = fake.authorize()
    fake.now = instant("2026-10-20T10:00")
    assert c.step(fake, journal) == "SESSION_MISSED"
    assert journal.facts["target_session"] == "2026-10-19"
    assert fake.children == []


def test_backward_clock_is_safe_terminal(fake):
    journal = fake.authorize()
    assert c.step(fake, journal) == "NEXT_SESSION_WAIT"
    fake.now -= timedelta(seconds=1)
    assert c.step(fake, journal) == "BLOCKED"
    assert fake.children == []


def test_quantum_and_no_serialized_sleep_authority(fake):
    journal = fake.authorize()
    with pytest.raises(Crash):
        c.supervise(fake, journal)
    assert fake.waits == [60]
    rows = copy.deepcopy(journal.rows)
    rows[0]["remaining_seconds"] = 1
    with pytest.raises(ValueError):
        s.parse(b"".join(s.canonical(row) + b"\n" for row in rows))
    fake.now = instant("2026-10-19T09:20")
    assert c.step(fake, s.Journal.load(journal.path)) == "D1R8_WAIT"


def test_target_and_slot_cannot_be_changed_or_reauthorized(fake):
    journal = fake.authorize()
    original = journal.path.read_bytes()
    fake.now += timedelta(hours=1)
    with pytest.raises(ValueError):
        fake.authorize()
    assert journal.path.read_bytes() == original
    facts = copy.deepcopy(journal.facts)
    facts["target_session"] = "2026-10-20"
    with pytest.raises(ValueError):
        c.validate_binding(facts)
    assert s.reservation_name("2026-10-19") == journal.path.name
    assert SOURCE["head"] not in journal.path.name


@pytest.mark.parametrize("payload", [b"", b"{}\n", b'{"partial":', b"null\n"])
def test_invalid_authorization_cannot_resume_or_repair(fake, payload):
    path = fake.parent / s.reservation_name("2026-10-19")
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        s.find_active(fake.parent)
    assert path.read_bytes() == payload
    assert fake.children == []


def test_exclusive_empty_reservation_stays_consumed(fake):
    path = fake.parent / s.reservation_name("2026-10-19")
    path.touch()
    with pytest.raises(FileExistsError):
        s.Journal.reserve(fake.parent, c.make_facts(SOURCE, fake.now, fake.binding))
    assert path.read_bytes() == b""


def test_durable_scheduler_intent_and_ack_separate_from_trading(fake):
    fake.scheduler = False
    journal = fake.authorize()
    assert [row["event"] for row in journal.rows] == [
        *s.INITIAL,
        "SCHEDULER_CREATE_INTENT",
        "SCHEDULER_CREATE_ACK",
        "SUPERVISOR_READY",
        "SCHEDULER_RUN_INTENT",
        "SCHEDULER_RUN_ACK",
    ]
    assert journal.rows[-1]["effects"]["scheduler_creates"] == 1
    assert fake.events.count("scheduler_create") == 1
    assert fake.children == []
    assert c.step(fake, journal) == "NEXT_SESSION_WAIT"


def test_uncertain_scheduler_ack_is_consumed_no_native_retry(fake):
    fake.scheduler = False
    fake.scheduler_fault = True
    journal = fake.authorize()
    assert journal.state == "FINAL"
    assert journal.rows[-1]["classification"] == "INDETERMINATE"
    assert c.step(fake, s.Journal.load(journal.path)) == "INDETERMINATE"
    assert fake.events.count("scheduler_create") == 1
    assert fake.children == []


@pytest.mark.parametrize(
    "selector",
    [
        "--date",
        "--session",
        "--exchange",
        "--strategy",
        "--symbol",
        "--provider",
        "--account",
        "--runtime",
        "--evidence",
        "--order-id",
        "--price",
        "--quantity",
        "--interlock",
        "--d1r7-interlock",
        "--d1r8-interlock",
        "--task",
        "--command",
        "--sleep",
        "--res",
    ],
)
def test_cli_rejects_semantic_selectors(selector):
    with pytest.raises(ValueError):
        host.build_parser().parse_args(["--resume", selector, "forbidden"])


def test_no_active_resume_and_terminal_resume_zero_host_effects(fake, monkeypatch):
    monkeypatch.setattr(host.bridge, "ROOT", ROOT)
    monkeypatch.setattr(host, "FixedRuntime", lambda: fake)
    for mode in ("--resume", "--status"):
        assert host.main([mode]) == 0
    assert fake.events == [] and fake.children == []
    journal = fake.authorize()
    c.finish(fake, journal, "BLOCKED")
    fake.events.clear()
    assert host.main(["--resume"]) == 0
    assert fake.events == [] and fake.children == []


def test_help_and_imports_are_inert(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("import/help attempted host effect")

    monkeypatch.setattr(bridge.subprocess, "run", forbidden)
    monkeypatch.setattr(bridge.subprocess, "Popen", forbidden)
    monkeypatch.setattr(s, "find_active", forbidden)
    monkeypatch.setattr("builtins.input", forbidden)
    for module in (bridge, host):
        importlib.reload(module)
    with pytest.raises(SystemExit) as result:
        host.build_parser().parse_args(["--help"])
    assert result.value.code == 0


def test_standard_library_codec_and_bridge_cannot_mix_child_packages():
    tree = ast.parse(Path(s.__file__).read_text(encoding="utf-8-sig"))
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert all("trading_bot" not in ast.unparse(node) for node in imports)
    source = Path(bridge.__file__).read_text(encoding="utf-8-sig")
    assert source.index('sys.path.insert(0, str(root / "src"))') < source.index(
        "from trading_bot.review_paper"
    )
    assert "already occupied" in source
    for name in ("d1r7", "d1r8"):
        adapter = (ROOT / f"scripts/arch134_d1r9_{name}_child.py").read_text(
            encoding="utf-8-sig"
        )
        assert f'child_main("{name}")' in adapter
        assert "subprocess" not in adapter


def test_scheduler_definition_is_process_plumbing_only():
    source = (ROOT / "scripts/arch134_d1r9_scheduler.ps1").read_text(
        encoding="utf-8-sig"
    )
    for required in (
        "Triggers.Create(9)",
        "LogonType = 3",
        "RunLevel = 0",
        "WakeToRun = $false",
        "MultipleInstances = 2",
        "RestartCount = 3",
        "RestartInterval = 'PT1M'",
        "--resume",
        "RegisterTaskDefinition($taskName, $definition, 2,",
        "arch134_d1r9_bridge.py",
        "ExecutionTimeLimit = 'PT0S'",
    ):
        assert required in source
    assert "D1R6" not in source
    assert source.count("$task.Run($null)") == 1 and ".DeleteTask(" not in source
    assert "9:30" not in source and "9:20" not in source


def test_child_import_guard_rejects_mixed_roots(monkeypatch):
    class Mixed:
        __file__ = str(ROOT / "src/trading_bot/elsewhere.py")

    monkeypatch.setitem(sys.modules, "trading_bot.fake_mixed", Mixed())
    with pytest.raises(ValueError, match="mixed"):
        bridge.admit_imports(bridge.R7_ROOT)


def test_journal_flush_readback_identity_and_attempt_limits(fake, monkeypatch):
    calls = []
    fsync = s.os.fsync
    monkeypatch.setattr(s.os, "fsync", lambda fd: (calls.append(fd), fsync(fd))[1])
    journal = fake.authorize()
    assert len(calls) == len(journal.rows)
    journal.append("D1R7_DELEGATION_INTENT", fake.now)
    with pytest.raises(ValueError):
        journal.append("D1R7_DELEGATION_INTENT", fake.now)
    journal.path.write_bytes(journal.payload + b" ")
    with pytest.raises(ValueError):
        journal.append("FINAL", fake.now, classification="INDETERMINATE")


def test_child_and_scheduler_claims_are_single_use(fake):
    for kind in ("d1r7", "d1r8", "scheduler"):
        path = fake.parent / (kind + ".claim")
        s.exclusive(path, b"claimed\n")
        with pytest.raises(FileExistsError):
            s.exclusive(path, b"again\n")
        assert path.read_bytes() == b"claimed\n"


def test_checkpoint_registration_inventory_and_frozen_children():
    name = "arch134-d1r9-arbitrary-time-d1-supervisor"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert runner.ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), s.BRANCH, "push")
        == name
    )
    assert runner.resolve_ci_certification_profile(name) == "robinhood"
    assert runner._arch134_d1r9_authority_check(ROOT) == ()
    inventory = certification.discover_inventory(ROOT)
    counts = {
        p: len(certification.select_inventory(inventory, p))
        for p in certification.PROFILES
    }
    assert counts == {"full": 183, "robinhood": 102, "legacy": 222, "exhaustive": 405}
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 68


@pytest.mark.parametrize("outcome", ["NO_SIGNAL", "RISK_REJECTED"])
def test_safe_nonexecution_terminals_preserve_child_effect_limits(fake, outcome):
    fake.now = instant("2026-10-19T10:00")
    if outcome == "NO_SIGNAL":
        fake.execution.raw.closes = (10, 10, 10, 10)
    else:
        fake.execution.rh.price = "1000000000000"
    journal = fake.authorize()
    assert c.step(fake, journal) == outcome
    effects = fake.execution.rows()[-1]["effects"]
    assert effects["execute_attempts"] == effects["paper_fill_mutations"] == 0
    if outcome == "NO_SIGNAL":
        assert effects["robinhood_credential_reads"] == effects["prepare_attempts"] == 0
        assert fake.execution.rh.calls == []
    assert all(effects[k] == 0 for k, budget in e.BUDGETS.items() if budget == 0)


@pytest.mark.parametrize("child", ["d1r7", "d1r8"])
@pytest.mark.parametrize(
    "mutation",
    ["corrupt", "wrong_target", "wrong_source", "wrong_successor", "incomplete"],
)
def test_complete_looking_but_invalid_child_artifacts_never_retry(
    fake, child, mutation
):
    fake.now = instant("2026-10-19T10:00")
    fake.crash_after = child
    journal = fake.authorize()
    with pytest.raises(Crash):
        c.step(fake, journal)
    target = c.validate_binding(journal.facts)
    path = (
        c.d1r7_path(fake.parent, target) if child == "d1r7" else fake.execution.output
    )
    payload = path.read_bytes()
    if mutation == "corrupt":
        payload += b"!"
    elif mutation == "incomplete":
        payload = b"\n".join(payload.splitlines()[:-1]) + b"\n"
    elif mutation == "wrong_target":
        payload = payload.replace(b"2026-10-19", b"2026-10-20")
    elif mutation == "wrong_source":
        payload = payload.replace(s.D1R7["head"].encode(), b"f" * 40)
    else:
        payload = payload.replace(s.D1R8["tree"].encode(), b"e" * 40)
    path.write_bytes(payload)
    before = list(fake.children)
    assert c.step(fake, s.Journal.load(journal.path)) == "INDETERMINATE"
    assert fake.children == before and path.read_bytes() == payload


@pytest.mark.parametrize("root_index", [0, 1, 2])
@pytest.mark.parametrize(
    "field",
    [
        "branch",
        "head",
        "tree",
        "dirty",
        "origin",
        "push_origin",
        "upstream",
        "tracking_head",
        "tracking_tree",
        "remote",
        "registry",
    ],
)
def test_exact_three_source_readmission_matrix(fake, monkeypatch, root_index, field):
    # The fixed production locations/interpreter are admitted through fake Git;
    # the test must not depend on John's F: checkouts or virtual environment.
    producer = fake.parent.parent / "producer-source"
    consumer = fake.parent.parent / "consumer-source"
    producer.mkdir()
    consumer.mkdir()
    monkeypatch.setattr(bridge, "ROOT", ROOT)
    monkeypatch.setattr(bridge, "R7_ROOT", producer)
    monkeypatch.setattr(bridge, "R8_ROOT", consumer)
    monkeypatch.setattr(bridge, "PYTHON", Path(sys.executable))
    monkeypatch.setattr(bridge, "load_store", lambda: s)
    facts = c.make_facts(SOURCE, fake.now, fake.binding)
    pairs = [(ROOT, SOURCE), (bridge.R7_ROOT, s.D1R7), (bridge.R8_ROOT, s.D1R8)]
    seen = []

    def git(root, *args):
        seen.append((root, args))
        source = next(value for path, value in pairs if path == root)
        branch = source["branch"]
        responses = {
            ("rev-parse", "--show-toplevel"): str(root),
            ("branch", "--show-current"): branch,
            ("rev-parse", "HEAD"): source["head"],
            ("rev-parse", "HEAD^{tree}"): source["tree"],
            ("status", "--porcelain=v1", "--untracked-files=all"): "",
            ("remote", "get-url", "origin"): s.ORIGIN,
            ("remote", "get-url", "--push", "origin"): s.ORIGIN,
            ("rev-parse", "--symbolic-full-name", "@{upstream}"): "refs/remotes/origin/"
            + branch,
            ("rev-parse", "origin/" + branch): source["head"],
            ("rev-parse", "origin/" + branch + "^{tree}"): source["tree"],
            ("ls-remote", "origin", "refs/heads/" + branch): source["head"]
            + "\trefs/heads/"
            + branch,
            ("worktree", "list", "--porcelain"): "\n".join(
                "worktree " + str(p) for p, _ in pairs
            ),
        }
        keys = dict(
            zip(
                (
                    "root",
                    "branch",
                    "head",
                    "tree",
                    "dirty",
                    "origin",
                    "push_origin",
                    "upstream",
                    "tracking_head",
                    "tracking_tree",
                    "remote",
                    "registry",
                ),
                responses,
                strict=True,
            )
        )
        if root == pairs[root_index][0] and args == keys[field]:
            return "drift"
        return responses[args]

    monkeypatch.setattr(bridge, "git", git)
    with pytest.raises(ValueError):
        bridge.admit_sources(facts)
    assert seen


def test_scheduler_claim_requires_durable_intent_and_is_never_retried(
    fake, monkeypatch
):
    monkeypatch.setattr(bridge, "PARENT", fake.parent)
    monkeypatch.setattr(bridge, "load_store", lambda: s)
    monkeypatch.setattr(bridge, "admit_sources", lambda facts: ())
    monkeypatch.setattr(bridge, "admit_runtime", lambda *a, **kw: None)
    monkeypatch.setattr(bridge.sys, "argv", ["fixed-bridge"])
    assert bridge.scheduler_claim() == "BLOCKED"
    fake.scheduler = False
    fake.scheduler_fault = True
    # Simulate restart at the native intent, before Create returns.
    journal = s.Journal.reserve(
        fake.parent, c.make_facts(SOURCE, fake.now, fake.binding)
    )
    for event in ("SOURCES_ADMITTED", "TARGET_BOUND", "SCHEDULER_CREATE_INTENT"):
        journal.append(event, fake.now)
    assert bridge.scheduler_claim() == "CREATE"
    assert bridge.scheduler_claim() == "BLOCKED"
    assert c.step(fake, s.Journal.load(journal.path)) == "INDETERMINATE"
    assert fake.events.count("scheduler_create") == 0


def test_child_adapters_reject_absent_authority_without_imports_or_processes(
    fake, monkeypatch
):
    monkeypatch.setattr(bridge, "PARENT", fake.parent)
    monkeypatch.setattr(bridge, "load_store", lambda: s)
    monkeypatch.setattr(bridge.sys, "argv", ["fixed-child"])
    monkeypatch.setattr(
        bridge,
        "admit_sources",
        lambda facts: pytest.fail("source touched without authorization"),
    )
    for kind in ("d1r7", "d1r8"):
        assert bridge.child_main(kind) == 2
    assert fake.children == []


def test_runtime_drift_and_post_entry_identity_rules(fake, monkeypatch):
    monkeypatch.setattr(bridge, "runtime_binding", fake.runtime_binding)
    bridge.admit_runtime(fake.binding)
    wrong = copy.deepcopy(fake.binding)
    wrong["paper"]["sha256"] = "b" * 64
    with pytest.raises(ValueError):
        bridge.admit_runtime(wrong)
    bridge.admit_runtime(wrong, entered=True)
    wrong["paper"]["inode"] += 1
    with pytest.raises(ValueError):
        bridge.admit_runtime(wrong, entered=True)


def test_lifetime_lock_serializes_supervisors_and_children(fake):
    path = fake.parent / "test.lock"
    with s.lock(path):
        with pytest.raises(OSError), s.lock(path):
            pytest.fail("duplicate lock owner")
    with s.lock(path):
        pass


@pytest.mark.parametrize("pending", [False, True])
def test_demand_start_intent_ack_controls_restart_authority(fake, pending):
    facts = c.make_facts(SOURCE, fake.now, fake.binding)
    journal = s.Journal.reserve(fake.parent, facts)
    for event in (
        "SOURCES_ADMITTED",
        "TARGET_BOUND",
        "SUPERVISOR_READY",
        "SCHEDULER_RUN_INTENT",
    ):
        journal.append(event, fake.now)
    if not pending:
        journal.append("SCHEDULER_RUN_ACK", fake.now)
    result = c.step(fake, s.Journal.load(journal.path))
    assert result == ("INDETERMINATE" if pending else "NEXT_SESSION_WAIT")
    assert fake.events.count("scheduler_run") == 0
    assert fake.children == []


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "executable", "value", "predecessor"]
)
def test_d1r9_final_overlay_fails_closed(monkeypatch, mutation):
    pins = dict(runner.ARCH134_D1R9_TEST_PIN_OVERRIDES)
    path = next(iter(pins))
    prior = runner.ARCH134_D1R9_PREDECESSOR_TEST_PINS[path]
    if mutation == "missing":
        pins.pop(path)
    elif mutation == "extra":
        pins["tests/unknown.py"] = "a" * 40
    elif mutation == "executable":
        pins["src/trading_bot/review_paper/d1_session_execution.py"] = "a" * 40
    elif mutation == "value":
        pins[path] = "f" * 40
    else:
        prior = "e" * 40
    monkeypatch.setattr(runner, "ARCH134_D1R9_TEST_PIN_OVERRIDES", pins)
    with pytest.raises(ValueError):
        runner._arch134_d1r9_test_pin(path, prior)


def test_interactive_authorizer_hands_runtime_to_fixed_task(fake, monkeypatch):
    fake.now = instant("2026-10-19T10:00")
    monkeypatch.setattr(host.bridge, "ROOT", ROOT)
    monkeypatch.setattr(host, "FixedRuntime", lambda: fake)
    monkeypatch.setattr(host.sys.stdin, "isatty", lambda: True)
    prompts = []
    monkeypatch.setattr(
        "builtins.input", lambda prompt: (prompts.append(prompt), c.INTERLOCK)[1]
    )
    assert (
        host.main(
            [
                "--authorize",
                "--accepted-head",
                SOURCE["head"],
                "--accepted-tree",
                SOURCE["tree"],
            ]
        )
        == 0
    )
    assert len(prompts) == 1 and fake.children == []
    assert fake.journal().state == "SCHEDULER_RUN_ACK"
    assert fake.events.count("scheduler_run") == 1
    assert host.main(["--resume"]) == 0
    assert len(prompts) == 1 and fake.children == ["d1r7", "d1r8"]
    assert fake.events.count("scheduler_run") == 1


@pytest.mark.parametrize(
    "initial,target_day",
    [("2026-10-30T17:00", "2026-11-02"), ("2027-03-12T17:00", "2027-03-15")],
)
def test_dst_wait_reconciliation_uses_published_local_open(fake, initial, target_day):
    fake.now = instant(initial)
    journal = fake.authorize()
    assert c.step(fake, journal) == "NEXT_SESSION_WAIT"
    fake.now = instant(target_day + "T09:19:59")
    assert c.step(fake, s.Journal.load(journal.path)) == "PREMARKET_WAIT"
    fake.now = instant(target_day + "T09:20")
    assert c.step(fake, s.Journal.load(journal.path)) == "D1R8_WAIT"
    assert fake.children == ["d1r7"]


def test_early_close_wait_cannot_cross_admission_cutoff(fake):
    fake.now = instant("2026-11-26T12:00")
    journal = fake.authorize()
    assert journal.facts["target_session"] == "2026-11-27"
    fake.now = instant("2026-11-27T12:55")
    assert c.step(fake, s.Journal.load(journal.path)) == "SESSION_MISSED"
    assert fake.children == []


def test_slow_readmission_crossing_close_cannot_enter_consumer(fake, monkeypatch):
    fake.now = instant("2026-10-19T09:20")
    journal = fake.authorize()
    assert c.step(fake, journal) == "D1R8_WAIT"
    fake.now = instant("2026-10-19T15:54:59")
    original = fake.admit_runtime

    def delayed(*args, **kwargs):
        original(*args, **kwargs)
        fake.now = instant("2026-10-19T15:55")

    monkeypatch.setattr(fake, "admit_runtime", delayed)
    assert c.step(fake, journal) == "SESSION_MISSED"
    assert fake.children == ["d1r7"]


def test_backward_clock_between_readmissions_never_enters_child(fake, monkeypatch):
    fake.now = instant("2026-10-19T08:00")
    journal = fake.authorize()
    assert c.step(fake, journal) == "PREMARKET_WAIT"
    fake.now = instant("2026-10-19T09:20")
    original = fake.admit_runtime
    calls = []

    def regress(*args, **kwargs):
        original(*args, **kwargs)
        calls.append(1)
        if len(calls) == 2:
            fake.now -= timedelta(seconds=1)

    monkeypatch.setattr(fake, "admit_runtime", regress)
    assert c.step(fake, journal) == "BLOCKED"
    assert fake.children == []
