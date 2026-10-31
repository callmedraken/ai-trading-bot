"""P4 lifecycle tests use only temporary state and injected offline work."""

import ast
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from trading_bot import desktop_runtime as runtime

L = runtime.Lifecycle
D = runtime.Diagnostic
ROOT = Path(__file__).resolve().parents[2]
IDENTITY = runtime.ArtifactIdentity(
    "11d55269-7e13-57aa-a3bf-1e20e486204b", "b771cf92-a09f-5f18-86d3-e03b65e04fe9"
)


def eventually(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    assert predicate()


class FakeWorker:
    def __init__(self, *, fail_start=False, fail_close=False, gate=None):
        self.state = L.STOPPED
        self.fail_start = fail_start
        self.fail_close = fail_close
        self.gate = gate
        self.starts = self.stops = self.closes = self.reconciles = 0

    def start(self):
        self.starts += 1
        self.state = L.RUNNING
        if self.gate:
            self.gate.wait(2)
        if self.fail_start:
            raise ValueError("SECRET must never reach diagnostics")

    def request_stop(self):
        self.stops += 1

    def close(self, timeout):
        self.closes += 1
        if self.fail_close:
            return False
        self.state = L.STOPPED
        return True

    def reconcile_and_close(self, timeout):
        self.reconciles += 1
        return self.close(timeout)

    def health(self):
        return runtime.WorkerHealth(self.state)


@pytest.fixture
def make_supervisor(tmp_path):
    instances = []

    def make(trading=None, research=None, **kwargs):
        path = tmp_path / str(len(instances)) / "lifecycle.jsonl"
        journal = runtime.LifecycleJournal(path)
        supervisor = runtime.DesktopSupervisor(
            journal,
            (lambda: trading) if trading else runtime.LocalTradingWorker,
            (lambda: research) if research else runtime.LocalResearchWorker,
            **kwargs,
        )
        instances.append(supervisor)
        return supervisor, path

    yield make
    for supervisor in instances:
        supervisor.stop()
        supervisor.wait()
        supervisor.dispose()


def events(path):
    return [json.loads(line)["event"] for line in path.read_text().splitlines()]


def test_initial_stop_and_two_live_threads_are_concurrent(make_supervisor):
    supervisor, path = make_supervisor()
    assert supervisor.status().state is L.STOPPED
    assert not path.exists()
    assert supervisor.start()
    eventually(lambda: supervisor.status().state is L.RUNNING)
    status = supervisor.status()
    assert status.trading.state is status.research.state is L.RUNNING
    assert status.transport == "NOT_CONNECTED"
    assert status.mode == "SIMULATED_PAPER" and not status.live_enabled
    assert not supervisor.start()
    supervisor.stop()
    supervisor.stop()
    assert supervisor.wait()
    assert supervisor.status().state is L.STOPPED
    assert events(path) == [
        event.value
        for event in runtime.RuntimeEvent
        if event is not runtime.RuntimeEvent.WORKER_FAILED
    ]
    # Clean Stop supports another operator generation; workers are fresh objects.
    assert supervisor.start()
    eventually(lambda: supervisor.status().state is L.RUNNING)
    assert supervisor.status().generation == 2


def test_exactly_one_pair_and_reconcile_before_stopped(make_supervisor):
    trading, research = FakeWorker(), FakeWorker()
    supervisor, path = make_supervisor(trading, research)
    assert supervisor.start()
    eventually(lambda: supervisor.status().state is L.RUNNING)
    assert not supervisor.start()
    assert trading.starts == research.starts == 1
    supervisor.stop()
    assert supervisor.wait()
    assert trading.stops == research.stops == 1
    assert trading.reconciles == trading.closes == research.closes == 1
    sequence = events(path)
    assert sequence.index("TRADING_RECONCILED") < sequence.index("STOPPED")
    assert sequence.index("RESEARCH_STOPPED") < sequence.index("STOPPED")


@pytest.mark.parametrize("failed", ["trading", "research"])
def test_partial_start_failure_cleans_all_owned_workers(make_supervisor, failed):
    trading = FakeWorker(fail_start=failed == "trading")
    research = FakeWorker(fail_start=failed == "research")
    supervisor, path = make_supervisor(trading, research)
    assert supervisor.start()
    eventually(lambda: supervisor.status().state is L.FAILED)
    assert supervisor.wait()
    assert trading.closes == trading.reconciles == 1
    assert research.closes == (failed == "research")
    assert not supervisor.start()
    assert "WORKER_FAILED" in events(path)
    assert "STOPPED" not in events(path)
    assert "SECRET" not in path.read_text()


def test_stop_during_start_and_duplicate_start(make_supervisor):
    gate = Event()
    trading, research = FakeWorker(gate=gate), FakeWorker()
    supervisor, _ = make_supervisor(trading, research)
    supervisor.start()
    eventually(lambda: trading.starts == 1)
    assert not supervisor.start()
    supervisor.stop()
    gate.set()
    assert supervisor.wait()
    assert research.starts == 0
    assert trading.reconciles == 1
    assert supervisor.status().state is L.STOPPED


@pytest.mark.parametrize("failed", ["trading", "research"])
def test_close_failure_is_attention_and_blocks_generation(make_supervisor, failed):
    trading = FakeWorker(fail_close=failed == "trading")
    research = FakeWorker(fail_close=failed == "research")
    supervisor, path = make_supervisor(trading, research, close_timeout=0.05)
    supervisor.start()
    eventually(lambda: supervisor.status().state is L.RUNNING)
    supervisor.stop()
    assert not supervisor.wait()
    status = supervisor.status()
    assert status.state is L.FAILED and status.diagnostic is D.CLOSE_TIMEOUT
    assert not status.can_close and not supervisor.dispose()
    assert not supervisor.start()
    assert trading.stops == research.stops == 1
    assert trading.closes == research.closes == 1
    assert "STOPPED" not in events(path)


def test_blocked_close_is_bounded_and_still_owned(make_supervisor):
    gate = Event()
    trading, research = FakeWorker(), FakeWorker()
    original = research.close

    def blocked(timeout):
        gate.wait(3)
        return original(timeout)

    research.close = blocked
    supervisor, _ = make_supervisor(trading, research, close_timeout=0.02)
    try:
        supervisor.start()
        eventually(lambda: supervisor.status().state is L.RUNNING)
        supervisor.stop()
        eventually(lambda: supervisor.status().state is L.FAILED)
        assert trading.reconciles == 1
        assert not supervisor.status().can_close
        assert not supervisor.start()
    finally:
        gate.set()


def test_worker_failure_stops_peer_without_restart(make_supervisor):
    trading, research = FakeWorker(), FakeWorker()
    supervisor, _ = make_supervisor(trading, research)
    supervisor.start()
    eventually(lambda: supervisor.status().state is L.RUNNING)
    research.state = L.FAILED
    eventually(lambda: supervisor.status().state is L.FAILED)
    assert supervisor.wait()
    assert supervisor.status().diagnostic is D.WORKER_FAILED
    assert trading.reconciles == 1
    assert trading.starts == research.starts == 1
    assert not supervisor.start()


def test_real_research_queue_works_and_never_touches_trading(make_supervisor, tmp_path):
    calls = []
    gate = Event()
    job = runtime.InspectBundle(tmp_path / "bundle.json")

    def inspect(value):
        calls.append(value)
        gate.wait(2)
        return IDENTITY

    research = runtime.LocalResearchWorker(inspector=inspect)
    trading = FakeWorker()
    supervisor, _ = make_supervisor(trading, research)
    try:
        supervisor.start()
        eventually(lambda: supervisor.status().state is L.RUNNING)
        assert research.submit(job)
        eventually(lambda: len(calls) == 1)
        assert research.submit(job)
        assert not research.submit(job)
        assert supervisor.status().trading.state is L.RUNNING
        gate.set()
        eventually(lambda: supervisor.status().research.artifact == IDENTITY)
        assert trading.starts == 1 and trading.stops == trading.reconciles == 0
        supervisor.stop()
        assert supervisor.wait()
        assert not research.submit(job)
        assert supervisor.status().research.artifact == IDENTITY
    finally:
        gate.set()


def test_artifact_failure_is_sanitized_and_fatal(make_supervisor, tmp_path):
    def invalid(job):
        raise ValueError("SECRET arbitrary path/token/raw exception")

    research = runtime.LocalResearchWorker(
        runtime.InspectBundle(tmp_path / "bad.json"), invalid
    )
    supervisor, path = make_supervisor(research=research)
    supervisor.start()
    eventually(lambda: supervisor.status().state is L.FAILED)
    assert supervisor.wait()
    assert "SECRET" not in repr(supervisor.status()) + path.read_text()


@pytest.mark.parametrize("prior", ["STARTING", "RUNNING", "STOPPING", "FAILED"])
def test_unresolved_prior_state_blocks_fresh_start(tmp_path, prior):
    path = tmp_path / "journal.jsonl"
    journal = runtime.LifecycleJournal(path)
    journal.acquire()
    journal.append(runtime.RuntimeEvent.START_REQUESTED)
    if prior in ("RUNNING", "STOPPING"):
        for event in (
            runtime.RuntimeEvent.TRADING_STARTED,
            runtime.RuntimeEvent.RESEARCH_STARTED,
            runtime.RuntimeEvent.RUNNING,
        ):
            journal.append(event)
    if prior == "STOPPING":
        journal.append(runtime.RuntimeEvent.STOP_REQUESTED)
    if prior == "FAILED":
        journal.append(runtime.RuntimeEvent.WORKER_FAILED, D.WORKER_FAILED)
    journal.release()  # Simulate an explicitly reconciled stale lock, not effects.
    before = path.read_bytes()
    supervisor = runtime.DesktopSupervisor(runtime.LifecycleJournal(path))
    assert supervisor.status().diagnostic is D.PRIOR_UNRESOLVED
    assert not supervisor.start()
    assert path.read_bytes() == before
    assert supervisor.dispose()


def test_second_instance_is_blocked_and_clean_reopen_works(make_supervisor):
    supervisor, path = make_supervisor()
    second = runtime.DesktopSupervisor(runtime.LifecycleJournal(path))
    assert second.status().diagnostic is D.ALREADY_OWNED
    assert not second.start()
    assert second.dispose()
    supervisor.start()
    eventually(lambda: supervisor.status().state is L.RUNNING)
    supervisor.stop()
    assert supervisor.wait() and supervisor.dispose()
    reopened = runtime.DesktopSupervisor(runtime.LifecycleJournal(path))
    assert reopened.status().state is L.STOPPED
    assert reopened.status().generation == 1
    assert reopened.dispose()


@pytest.mark.parametrize(
    "corrupt",
    [
        "partial",
        "duplicate",
        "sequence",
        "generation",
        "timestamp",
        "event",
        "diagnostic",
        "unknown",
        "false_stop",
    ],
)
def test_journal_rejects_malformed_conflicting_state(tmp_path, corrupt):
    path = tmp_path / "journal.jsonl"
    journal = runtime.LifecycleJournal(path)
    journal.acquire()
    journal.append(runtime.RuntimeEvent.START_REQUESTED)
    journal.release()
    row = json.loads(path.read_text())
    if corrupt == "partial":
        body = b'{"event":'
    elif corrupt == "duplicate":
        body = (json.dumps(row)[:-1] + ',"sequence":1}\n').encode()
    else:
        if corrupt == "false_stop":
            row["event"] = "STOPPED"
        else:
            row[{"timestamp": "utc", "unknown": "extra"}.get(corrupt, corrupt)] = {
                "sequence": 2,
                "generation": 8,
                "timestamp": "2026-01-01T00:00:00",
                "event": "ARBITRARY",
                "diagnostic": "SECRET",
                "unknown": True,
            }[corrupt]
        body = (json.dumps(row) + "\n").encode()
    path.write_bytes(body)
    supervisor = runtime.DesktopSupervisor(runtime.LifecycleJournal(path))
    assert supervisor.status().diagnostic is D.JOURNAL_INVALID
    assert not supervisor.start()
    assert path.read_bytes() == body
    assert supervisor.dispose()


def test_persistence_failure_stops_both_and_never_claims_stopped(
    make_supervisor, monkeypatch
):
    supervisor, _ = make_supervisor()
    supervisor.start()
    eventually(lambda: supervisor.status().state is L.RUNNING)

    def fail(*args):
        raise OSError("SECRET disk detail")

    monkeypatch.setattr(supervisor._journal, "append", fail)
    supervisor.stop()
    assert supervisor.wait()
    assert supervisor.status().state is L.FAILED
    assert supervisor.status().diagnostic is D.JOURNAL_IO
    assert (
        supervisor.status().trading.state
        is supervisor.status().research.state
        is L.STOPPED
    )
    assert not supervisor.start()


def test_closed_health_and_identity_vocabulary():
    with pytest.raises(TypeError):
        runtime.WorkerHealth("ARBITRARY")
    with pytest.raises(TypeError):
        runtime.WorkerHealth(diagnostic="SECRET")
    with pytest.raises(ValueError):
        replace(IDENTITY, campaign_id="SECRET")


def test_bundle_inspection_is_bounded_readonly_and_never_selects_strategy(
    tmp_path, monkeypatch
):
    from hashlib import sha256
    from types import SimpleNamespace

    from trading_bot.experiments import desktop_research_campaign as campaign

    path = tmp_path / "bundle.json"
    payload = b'{"synthetic":"fixture"}'
    path.write_bytes(payload)
    fake = SimpleNamespace(
        campaign_id=IDENTITY.campaign_id,
        bundle_id=IDENTITY.bundle_id,
        to_bytes=lambda: payload,
    )
    reads = []

    def read(selected):
        reads.append(selected)
        return fake

    monkeypatch.setattr(campaign, "read_desktop_campaign_bundle", read)
    job = runtime.InspectBundle(path, sha256(payload).hexdigest(), IDENTITY)
    assert runtime.inspect_bundle(job) == IDENTITY
    assert reads == [path] and path.read_bytes() == payload
    with pytest.raises(ValueError):
        runtime.inspect_bundle(replace(job, expected_sha256="0" * 64))
    with pytest.raises(ValueError):
        runtime.inspect_bundle(replace(job, path=tmp_path / "holdout.csv"))
    assert reads == [path, path]  # CSV rejected before any reader invocation.
    assert path.read_bytes() == payload


def test_slow_health_never_blocks_operator_status_or_stop(make_supervisor):
    gate = Event()
    trading = FakeWorker()
    original = trading.health
    supervisor, _ = make_supervisor(trading=trading, close_timeout=0.03)
    supervisor.start()
    eventually(lambda: supervisor.status().state is L.RUNNING)
    entered = Event()

    def slow():
        entered.set()
        gate.wait(2)
        return original()

    trading.health = slow
    try:
        eventually(entered.is_set)
        start = time.monotonic()
        assert supervisor.status().trading.state is L.RUNNING
        supervisor.stop()
        assert time.monotonic() - start < 0.1
        eventually(lambda: supervisor.status().state is L.FAILED)
        assert not supervisor.status().can_close
    finally:
        gate.set()


def test_stop_during_slow_factory_never_starts_later_worker(make_supervisor):
    gate, entered = Event(), Event()
    trading = FakeWorker()
    supervisor, _ = make_supervisor()

    def construct():
        entered.set()
        gate.wait(2)
        return trading

    supervisor._trading_factory = construct
    try:
        supervisor.start()
        eventually(entered.is_set)
        supervisor.stop()
        gate.set()
        assert supervisor.wait()
        assert trading.starts == 0
        assert trading.closes == 1
        assert supervisor.status().state is L.STOPPED
    finally:
        gate.set()


def test_p4_imports_only_reviewed_local_boundaries_and_has_no_domain_mutations():
    allowed_project = {
        "trading_bot.desktop_runtime",
        "trading_bot.experiments.desktop_research_campaign",
        "trading_bot.gui.main_window",
        "trading_bot.gui.desktop_service",
    }
    paths = [
        ROOT / "src/trading_bot/desktop_runtime.py",
        ROOT / "scripts/run_desktop_bot.py",
        ROOT / "src/trading_bot/gui/desktop_control.py",
    ]
    forbidden = {
        "load_desktop_final_holdout",
        "inspect_desktop_dataset_integrity",
        "ResearchStrategyFinalHoldoutAdmission",
        "run_desktop_campaign",
        "eval",
        "exec",
        "__import__",
        "import_module",
    }
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("trading_bot"):
                    assert module in allowed_project
                assert not {alias.name for alias in node.names} & forbidden
                if module == "trading_bot.experiments.desktop_research_campaign":
                    assert [alias.name for alias in node.names] == [
                        "read_desktop_campaign_bundle"
                    ]
            if isinstance(node, ast.Name):
                assert node.id not in forbidden
            if isinstance(node, ast.Import):
                assert {a.name.split(".")[0] for a in node.names} <= {
                    "json",
                    "os",
                    "argparse",
                    "sys",
                }
    # Trading owns only its lifecycle primitives: no path, research, ledger,
    # risk, strategy or broker reference is supplied to it.
    tree = ast.parse(paths[0].read_text())
    trading = next(
        n
        for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "LocalTradingWorker"
    )
    calls = {
        n.func.id
        for n in ast.walk(trading)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert calls <= {"Event", "Lock", "WorkerHealth", "Thread", "RuntimeError"}


def test_production_composition_pins_readonly_bundle_and_external_state(
    monkeypatch, tmp_path
):
    from scripts import run_desktop_bot as launcher

    monkeypatch.setattr(launcher, "RUNTIME_JOURNAL", tmp_path / "state.jsonl")
    supervisor = launcher.build_supervisor()
    assert supervisor.status().state is L.STOPPED
    assert not (tmp_path / "state.jsonl").exists()
    assert launcher.ROOT not in launcher.RUNTIME_JOURNAL.parents
    assert launcher.ACCEPTED_CAMPAIGN == IDENTITY.campaign_id
    assert launcher.ACCEPTED_BUNDLE == IDENTITY.bundle_id
    assert supervisor.dispose()


def test_fresh_process_production_imports_have_no_effect_adapters():
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT), str(ROOT / "src"))))
    result = subprocess.run(
        [sys.executable, "-B", str(Path(__file__)), "--import-inventory"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    names = result.stdout.splitlines()
    assert "trading_bot.gui.main_window" in names
    assert not any(
        fragment in name
        for name in names
        for fragment in (
            ".robinhood",
            ".alpaca",
            ".credentials",
            ".scheduler",
            "_native",
            "_host",
        )
    )


if __name__ == "__main__" and sys.argv[1:] == ["--import-inventory"]:
    # A reviewed source file carries this fresh-process probe on Windows;
    # multiline Python is never transported through python -c.
    import trading_bot.gui.desktop_service
    import trading_bot.gui.main_window  # noqa: F401
    from scripts import run_desktop_bot  # noqa: F401

    print("\n".join(sorted(n for n in sys.modules if n.startswith("trading_bot."))))
