"""Current prototype source-only route and ownership regressions."""

from pathlib import Path

from scripts.source_authority import current_owner

from scripts import checkpoint_runner as runner
from scripts import run_test_certification as certification


def test_prototype_has_no_protected_dispatch_and_maps_full():
    root = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[runner.ARCH147_PROTOTYPE_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), spec.remote_branch, "push"
        )
        == spec.name
    )
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] == "full"
    assert runner._arch147_prototype_authority_check(root) == ()
    assert current_owner("_arch147_prototype_authority_check") == "checkpoint_runner"
    inventory = certification.discover_inventory(root)
    full = set(certification.select_inventory(inventory, "full"))
    assert {m for m in inventory if m.startswith("tests/live_prototype/")} <= full
    assert all(m in full for m in runner.ARCH147_PROTOTYPE_TESTS if m.endswith(".py"))


def test_prototype_rejects_effectful_dispatch_without_invoking_it(monkeypatch):
    from dataclasses import replace

    root = Path(runner.__file__).resolve().parents[1]
    specs = runner._checkpoint_specs()
    spec = specs[runner.ARCH147_PROTOTYPE_NAME]
    calls = []
    specs[spec.name] = replace(spec, preflight=lambda: calls.append("effect"))
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert (
        "147 prototype source-only registration drift"
        in runner._arch147_prototype_authority_check(root)
    )
    assert calls == []


def test_new_application_has_no_production_transport_or_dynamic_dispatch():
    import ast

    root = Path(runner.__file__).resolve().parents[1]
    paths = tuple((root / "src/trading_bot/live_prototype").glob("*.py")) + (
        root / "scripts/run_live_prototype.py",
    )
    forbidden = (
        "robinhood_mcp",
        "desktop_live.execution",
        "windows_oauth",
        "httpx",
        "requests",
        "sqlite3",
        "subprocess",
        "socket",
    )
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = [
            n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
        ]
        imported += [
            a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
        ]
        assert not any(word in name for name in imported for word in forbidden), path
        assert not any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in {"eval", "exec", "__import__"}
            for n in ast.walk(tree)
        ), path
