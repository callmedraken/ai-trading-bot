"""Current prototype source-only route and ownership regressions."""

import ast
from pathlib import Path

from scripts.source_authority import current_owner

from scripts import checkpoint_runner as runner
from scripts import run_test_certification as certification

_L41_IMPORT_ALLOWLIST = {
    "src/trading_bot/live_prototype/capability_operator.py": {
        ("import", "subprocess", None),
        (
            "from",
            "trading_bot.robinhood_mcp.windows_oauth",
            "create_windows_robinhood_oauth_factory",
        ),
    },
    "src/trading_bot/live_prototype/capability_transport.py": {
        (
            "from",
            "trading_bot.robinhood_mcp.sdk_transport",
            "ROBINHOOD_TRADING_MCP_URL",
        ),
        ("import", "httpx2", None),
        ("from", "mcp", "Client"),
        (
            "from",
            "mcp.client.streamable_http",
            "streamable_http_client",
        ),
    },
    "src/trading_bot/live_prototype/capability_schema_discovery_interactive.py": {
        (
            "from",
            "trading_bot.robinhood_mcp.windows_oauth",
            "create_windows_robinhood_oauth_factory",
        ),
    },
    "src/trading_bot/live_prototype/capability_schema_discovery_l41r3.py": {
        (
            "from",
            "trading_bot.robinhood_mcp.windows_oauth",
            "create_windows_robinhood_oauth_factory",
        ),
        (
            "from",
            "trading_bot.robinhood_mcp.sdk_transport",
            "ROBINHOOD_TRADING_MCP_URL",
        ),
        ("import", "httpx2", None),
        ("from", "mcp", "Client"),
        ("from", "mcp.client.streamable_http", "streamable_http_client"),
    },
}
_FORBIDDEN_PRODUCTION_IMPORTS = (
    "robinhood_mcp",
    "desktop_live.execution",
    "windows_oauth",
    "httpx",
    "requests",
    "sqlite3",
    "subprocess",
    "socket",
)


def _production_imports(path: str, tree: ast.AST) -> list[tuple[str, str, str | None]]:
    records: list[tuple[str, str, str | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            records.extend(
                ("from", node.module or "", alias.name) for alias in node.names
            )
        elif isinstance(node, ast.Import):
            records.extend(("import", alias.name, alias.asname) for alias in node.names)
    allowed = _L41_IMPORT_ALLOWLIST.get(path, set())
    return [
        record
        for record in records
        if any(token in record[1] for token in _FORBIDDEN_PRODUCTION_IMPORTS)
        and record not in allowed
    ]


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


def test_l41_capability_family_is_prepublication_owned():
    root = Path(runner.__file__).resolve().parents[1]
    capability_tests = {
        path.relative_to(root).as_posix()
        for path in (root / "tests/live_prototype").glob("test_capability_*.py")
    }

    assert capability_tests
    assert capability_tests <= set(runner.ARCH147_PROTOTYPE_TESTS)


def test_l41r2_interactive_schema_family_is_prepublication_owned():
    root = Path(runner.__file__).resolve().parents[1]
    production = (
        "src/trading_bot/live_prototype/capability_schema_discovery_interactive.py"
    )
    test = "tests/live_prototype/test_capability_schema_discovery_interactive.py"

    assert (root / production).is_file()
    assert (root / test).is_file()
    assert "src/trading_bot/live_prototype" in runner.ARCH147_PROTOTYPE_RUFF
    assert test in runner.ARCH147_PROTOTYPE_TESTS
    assert runner._arch147_prototype_authority_check(root) == ()


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
    root = Path(runner.__file__).resolve().parents[1]
    paths = tuple((root / "src/trading_bot/live_prototype").glob("*.py")) + (
        root / "scripts/run_live_prototype.py",
    )
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        relative_path = path.relative_to(root).as_posix()
        assert not _production_imports(relative_path, tree), path
        assert not any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in {"eval", "exec", "__import__"}
            for n in ast.walk(tree)
        ), path


def test_unrelated_prototype_module_still_rejects_production_import():
    unrelated = ast.parse(
        "from trading_bot.robinhood_mcp.current_live_transport import "
        "RobinhoodCurrentLiveTransport"
    )

    assert _production_imports(
        "src/trading_bot/live_prototype/unrelated_service.py", unrelated
    )
