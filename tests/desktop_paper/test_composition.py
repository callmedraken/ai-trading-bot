"""No-selection production boundary and accepted supervisor reuse."""

import importlib.util
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.desktop_paper.composition import DesktopPaperRuntime
from trading_bot.desktop_paper.configuration import create_paper_evaluation_config
from trading_bot.desktop_runtime import Lifecycle


@pytest.mark.parametrize(
    "change",
    [
        {"max_order_notional": Decimal("40000")},
        {"allow_fractional_shares": True},
        {"fill_commission": Decimal("0")},
        {"replay_interval_seconds": Decimal("0")},
    ],
)
def test_runtime_rejects_unreviewed_policy_changes_before_files(
    tmp_path,
    paper_config,
    paper_source_factory,
    paper_evaluator,
    change,
):
    config = create_paper_evaluation_config(
        paper_config.binding, replace(paper_config.policy, **change)
    )
    with pytest.raises(ValueError, match="PAPER_RUNTIME_POLICY_SUCCESSOR_REQUIRED"):
        DesktopPaperRuntime(
            config,
            evaluator=paper_evaluator,
            source_factory=paper_source_factory,
            database=tmp_path / "paper.sqlite",
            lifecycle=tmp_path / "lifecycle.jsonl",
        )
    assert list(tmp_path.iterdir()) == []


def test_no_binding_is_unavailable_before_creating_any_state(tmp_path):
    runtime = DesktopPaperRuntime(
        database=tmp_path / "paper.sqlite",
        lifecycle=tmp_path / "lifecycle.jsonl",
    )
    assert runtime.snapshot().binding is None
    assert runtime.snapshot().diagnostic == "PAPER_EVALUATION_SELECTION_REQUIRED"
    assert runtime.snapshot().financial is None
    assert not runtime.status().can_start
    assert not runtime.start()
    assert not runtime.clear_kill()
    assert not runtime.latch_kill()
    assert not runtime.set_new_buys_enabled(False)
    runtime.stop()
    assert runtime.wait() and runtime.dispose()
    assert list(tmp_path.iterdir()) == []


def test_new_launcher_has_no_selected_strategy():
    path = Path(__file__).resolve().parents[2] / "scripts/run_desktop_paper_bot.py"
    spec = importlib.util.spec_from_file_location("p5_launcher_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build_runtime().snapshot().binding is None


def test_production_import_graph_contains_no_transport_or_acquisition():
    root = Path(__file__).resolve().parents[2]
    code = (
        "import json,sys; "
        "import trading_bot.desktop_paper.composition; "
        "print(json.dumps(sorted(sys.modules)))"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root / "src")},
        capture_output=True,
        text=True,
        check=True,
    )
    imported = json.loads(result.stdout)
    assert not [
        name
        for name in imported
        if any(
            term in name.lower()
            for term in (
                "robinhood",
                "oauth",
                "alpaca",
                "credential",
                "final_holdout",
                "historical_research_acquisition",
            )
        )
    ]


def test_supervisor_owns_start_stop_and_refuses_clear_while_running(
    tmp_path,
    paper_config,
    paper_source_factory,
    paper_evaluator,
):
    runtime = DesktopPaperRuntime(
        paper_config,
        evaluator=paper_evaluator,
        source_factory=paper_source_factory,
        database=tmp_path / "paper.sqlite",
        lifecycle=tmp_path / "lifecycle.jsonl",
    )
    try:
        assert runtime.start()
        deadline = time.monotonic() + 3
        while (
            runtime.status().state is Lifecycle.STARTING and time.monotonic() < deadline
        ):
            time.sleep(0.005)
        assert runtime.status().state is Lifecycle.RUNNING
        assert not runtime.clear_kill()
        assert runtime.latch_kill()
    finally:
        runtime.stop()
        assert runtime.wait(3)
        assert runtime.dispose()
    assert runtime.status().state is Lifecycle.STOPPED


def test_stale_lifecycle_lock_does_not_construct_trading_store(
    tmp_path,
    paper_config,
    paper_source_factory,
    paper_evaluator,
):
    journal = tmp_path / "lifecycle.jsonl"
    journal.with_suffix(".jsonl.lock").write_text("stale-owner\n")
    runtime = DesktopPaperRuntime(
        paper_config,
        evaluator=paper_evaluator,
        source_factory=paper_source_factory,
        database=tmp_path / "paper.sqlite",
        lifecycle=journal,
    )
    assert runtime.status().state is Lifecycle.FAILED
    assert not runtime.start()
    assert not (tmp_path / "paper.sqlite").exists()
    assert journal.with_suffix(".jsonl.lock").exists()
    assert runtime.dispose()


def test_stopped_clear_is_durable_and_clean_restart_preserves_cursor(
    tmp_path,
    paper_config,
    paper_source_factory,
    paper_evaluator,
):
    runtime = DesktopPaperRuntime(
        paper_config,
        evaluator=paper_evaluator,
        source_factory=paper_source_factory,
        database=tmp_path / "paper.sqlite",
        lifecycle=tmp_path / "lifecycle.jsonl",
    )

    def wait_for(predicate):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.005)
        assert predicate()

    try:
        assert runtime.start()
        wait_for(lambda: runtime.status().state is Lifecycle.RUNNING)
        assert runtime.latch_kill()
        wait_for(lambda: runtime.snapshot().activity == "KILL_LATCHED")
        paused_cursor = runtime.snapshot().financial.cursor_index
        runtime.stop()
        assert runtime.wait(3)
        assert runtime.clear_kill()
        wait_for(lambda: not runtime.snapshot().financial.control.kill_latched)
        wait_for(lambda: runtime.status().can_start)
        assert runtime.snapshot().financial.cursor_index == paused_cursor
        assert runtime.start()
        wait_for(lambda: runtime.snapshot().activity == "EXHAUSTED")
        assert runtime.snapshot().financial.cursor_index == 4
    finally:
        runtime.stop()
        assert runtime.wait(3)
        assert runtime.dispose()
