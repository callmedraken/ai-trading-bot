"""Current prototype read-only preflight route and ownership regressions."""

import ast
import asyncio
import hashlib
import inspect
import json
import logging
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts.source_authority import current_owner

from scripts import arch147_l43_q1_source as q1_source
from scripts import checkpoint_runner as runner
from scripts import run_test_certification as certification
from trading_bot.live_prototype import l43_qualification_preflight as q1

_PRODUCTION_IMPORT_ALLOWLIST = {
    "src/trading_bot/live_prototype/capability_operator.py": {
        ("import", "subprocess", None),
        (
            "from",
            "trading_bot.robinhood_mcp.windows_oauth",
            "create_windows_robinhood_oauth_factory",
        ),
    },
    "src/trading_bot/live_prototype/tiny_live_readiness_observer.py": {
        ("import", "subprocess", None),
        (
            "from",
            "trading_bot.robinhood_mcp.current_read_transport",
            "RobinhoodCurrentReadTransport",
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
    "src/trading_bot/live_prototype/capability_schema_discovery_l41r4.py": {
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
    "src/trading_bot/live_prototype/capability_schema_discovery_l41r5.py": {
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
    "src/trading_bot/live_prototype/l43_runtime.py": {
        (
            "from",
            "trading_bot.robinhood_mcp.l43_production_composition",
            "DEFAULT_ROBINHOOD_REDIRECT_URI",
        ),
        (
            "from",
            "trading_bot.robinhood_mcp.l43_production_composition",
            "L43ProductionPreEffectComposition",
        ),
        (
            "from",
            "trading_bot.robinhood_mcp.l43_transport",
            "L43RobinhoodTransport",
        ),
        (
            "from",
            "trading_bot.robinhood_mcp.order_scope_evidence_admission",
            "OrderScopeEvidenceAuthority",
        ),
        (
            "from",
            "trading_bot.robinhood_mcp.order_scope_evidence_admission",
            "load_order_scope_evidence_authority",
        ),
    },
    "src/trading_bot/live_prototype/l43_qualification_preflight.py": {
        ("import", "subprocess", None),
        (
            "from",
            "trading_bot.robinhood_mcp.l43_production_composition",
            "L43ProductionPreEffectComposition",
        ),
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
    allowed = _PRODUCTION_IMPORT_ALLOWLIST.get(path, set())
    return [
        record
        for record in records
        if any(token in record[1] for token in _FORBIDDEN_PRODUCTION_IMPORTS)
        and record not in allowed
    ]


def test_prototype_has_no_protected_dispatch_and_maps_full():
    root = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[runner.ARCH147_PROTOTYPE_NAME]
    assert spec.preflight is runner._arch147_l43_a3_preflight
    assert spec.execute is None
    assert spec.remote_head_env is None
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


def test_b2o_source_and_test_are_prototype_owned_but_checkpoint_stays_manual():
    root = Path(runner.__file__).resolve().parents[1]
    observer_source = (
        "src/trading_bot/robinhood_mcp/agent_initiated_runtime_partition_observer.py"
    )
    b2o_runner_source = "scripts/arch147_l43_b2_runtime_partition_source.py"
    observer_test = (
        "tests/robinhood_mcp/test_agent_initiated_runtime_partition_observer.py"
    )
    prototype = runner._checkpoint_specs()[runner.ARCH147_PROTOTYPE_NAME]
    inventory = certification.discover_inventory(root)

    assert (root / observer_source).is_file()
    assert (root / b2o_runner_source).is_file()
    assert (root / observer_test).is_file()
    assert runner.ARCH147_PROTOTYPE_TESTS.count(observer_test) == 1
    assert prototype.tests.count(observer_test) == 1
    assert runner.ARCH147_PROTOTYPE_RUFF.count(observer_source) == 1
    assert runner.ARCH147_PROTOTYPE_RUFF.count(b2o_runner_source) == 1
    assert prototype.ruff_paths.count(observer_source) == 1
    assert prototype.ruff_paths.count(b2o_runner_source) == 1
    assert inventory.count(observer_test) == 1

    assert runner.ARCH147_B2O_NAME not in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert runner.ARCH147_B2O_NAME not in runner.ACTIVE_CI_CHECKPOINTS
    assert runner.ARCH147_B2O_NAME not in runner.CI_CERTIFICATION_PROFILES
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), runner.ARCH147_PROTOTYPE_BRANCH, "push"
        )
        == runner.ARCH147_PROTOTYPE_NAME
    )


def test_arch147_guard_is_in_prepublication_admission_for_prototype_changes():
    guard = "tests/runtime/checkpoint_runner/test_arch147_prototype.py"
    selected = runner._prepublication_admission_tests(
        ("src/trading_bot/live_prototype/l43_effect_operator.py",)
    )

    assert selected.count(guard) == 1


def test_arch147_route_owned_changes_select_the_complete_owned_test_set():
    composition_source = "src/trading_bot/robinhood_mcp/l43_production_composition.py"
    runtime_source = "src/trading_bot/live_prototype/l43_runtime.py"
    unrelated_source = "src/trading_bot/domain/unrelated.py"
    composition_test = "tests/robinhood_mcp/test_l43_production_composition.py"
    runtime_test = "tests/live_prototype/test_l43_runtime.py"
    guard = "tests/runtime/checkpoint_runner/test_arch147_prototype.py"

    selected = runner._prepublication_admission_tests(
        (composition_source, runtime_source)
    )
    assert set(runner.ARCH147_PROTOTYPE_TESTS) <= set(selected)
    assert selected.count(composition_test) == 1
    assert selected.count(runtime_test) == 1
    assert selected.count(guard) == 1

    unrelated = runner._prepublication_admission_tests((unrelated_source,))
    assert composition_test not in unrelated
    assert runtime_test not in unrelated
    assert guard not in unrelated

    infrastructure = runner._prepublication_admission_tests(
        ("scripts/checkpoint_runner.py",)
    )
    assert set(runner.PREPUBLICATION_INFRASTRUCTURE_COHERENCE_TESTS) <= set(
        infrastructure
    )

    combined = runner._prepublication_admission_tests(
        ("scripts/checkpoint_runner.py", composition_source)
    )
    assert set(runner.ARCH147_PROTOTYPE_TESTS) <= set(combined)
    assert set(runner.PREPUBLICATION_INFRASTRUCTURE_COHERENCE_TESTS) <= set(combined)
    assert len(combined) == len(set(combined))


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


def test_l41r4_schema_classification_successor_is_prepublication_owned():
    root = Path(runner.__file__).resolve().parents[1]
    production = "src/trading_bot/live_prototype/capability_schema_discovery_l41r4.py"
    test = "tests/live_prototype/test_capability_schema_discovery_l41r4.py"

    assert (root / production).is_file()
    assert (root / test).is_file()
    assert "src/trading_bot/live_prototype" in runner.ARCH147_PROTOTYPE_RUFF
    assert test in runner.ARCH147_PROTOTYPE_TESTS
    assert runner._arch147_prototype_authority_check(root) == ()


def test_l41r5_schema_semantic_recovery_successor_is_prepublication_owned():
    root = Path(runner.__file__).resolve().parents[1]
    production = "src/trading_bot/live_prototype/capability_schema_discovery_l41r5.py"
    test = "tests/live_prototype/test_capability_schema_discovery_l41r5.py"

    assert (root / production).is_file()
    assert (root / test).is_file()
    assert "src/trading_bot/live_prototype" in runner.ARCH147_PROTOTYPE_RUFF
    assert runner.ARCH147_PROTOTYPE_TESTS.count(test) == 1
    assert runner._arch147_prototype_authority_check(root) == ()


def test_l41r6_consumed_evidence_and_rule_binding_are_prepublication_owned():
    root = Path(runner.__file__).resolve().parents[1]
    source_files = (
        "src/trading_bot/live_prototype/consumed_l41r5_evidence.py",
        "src/trading_bot/live_prototype/capability_rule_binding_l41r6.py",
    )
    test_files = (
        "tests/live_prototype/test_consumed_l41r5_evidence.py",
        "tests/live_prototype/test_capability_rule_binding_l41r6.py",
    )

    assert all((root / path).is_file() for path in source_files + test_files)
    assert "src/trading_bot/live_prototype" in runner.ARCH147_PROTOTYPE_RUFF
    assert all(runner.ARCH147_PROTOTYPE_TESTS.count(path) == 1 for path in test_files)
    assert runner._arch147_prototype_authority_check(root) == ()


def test_l43_agent_initiated_schema_source_test_pairs_are_prepublication_owned():
    root = Path(runner.__file__).resolve().parents[1]
    pairs = (
        (
            "src/trading_bot/robinhood_mcp/agent_initiated_partition_schema_qualifier.py",
            "tests/robinhood_mcp/test_agent_initiated_partition_schema_qualifier.py",
        ),
        (
            "src/trading_bot/robinhood_mcp/agent_initiated_partition_schema_observer.py",
            "tests/robinhood_mcp/test_agent_initiated_partition_schema_observer.py",
        ),
        (
            "src/trading_bot/robinhood_mcp/agent_initiated_partition_schema_qualifier.py",
            "tests/robinhood_mcp/test_agent_initiated_runtime_partition_schema.py",
        ),
        (
            "src/trading_bot/robinhood_mcp/agent_initiated_partition_schema_observer.py",
            "tests/robinhood_mcp/test_agent_initiated_runtime_partition_schema.py",
        ),
    )
    spec = runner._checkpoint_specs()[runner.ARCH147_PROTOTYPE_NAME]
    inventory = certification.discover_inventory(root)
    full = certification.select_inventory(inventory, "full")

    assert spec.tests == runner.ARCH147_PROTOTYPE_TESTS
    assert spec.ruff_paths == runner.ARCH147_PROTOTYPE_RUFF
    for source, test in pairs:
        assert (root / source).is_file()
        assert (root / test).is_file()
        assert runner.ARCH147_PROTOTYPE_TESTS.count(test) == 1
        assert spec.tests.count(test) == 1
        assert full.count(test) == 1
        assert runner.ARCH147_PROTOTYPE_RUFF.count(source) == 1
        assert source in spec.ruff_paths
    assert runner._arch147_prototype_authority_check(root) == ()


def test_l43_b2_runtime_partition_source_test_pair_is_prepublication_owned():
    root = Path(runner.__file__).resolve().parents[1]
    source = "src/trading_bot/robinhood_mcp/agent_initiated_runtime_partition_proof.py"
    test = "tests/robinhood_mcp/test_agent_initiated_runtime_partition_proof.py"
    spec = runner._checkpoint_specs()[runner.ARCH147_PROTOTYPE_NAME]
    inventory = certification.discover_inventory(root)
    full = certification.select_inventory(inventory, "full")

    assert (root / source).is_file()
    assert (root / test).is_file()
    assert runner.ARCH147_PROTOTYPE_RUFF.count(source) == 1
    assert runner.ARCH147_PROTOTYPE_TESTS.count(test) == 1
    assert spec.ruff_paths.count(source) == 1
    assert spec.tests.count(test) == 1
    assert full.count(test) == 1
    assert runner._arch147_prototype_authority_check(root) == ()


def test_rhc3_evidence_admission_and_composition_are_prepublication_owned():
    root = Path(runner.__file__).resolve().parents[1]
    pairs = (
        (
            "src/trading_bot/robinhood_mcp/order_scope_evidence_admission.py",
            "tests/robinhood_mcp/test_order_scope_evidence_admission.py",
        ),
        (
            "src/trading_bot/robinhood_mcp/l43_production_composition.py",
            "tests/robinhood_mcp/test_l43_production_composition.py",
        ),
    )
    spec = runner._checkpoint_specs()[runner.ARCH147_PROTOTYPE_NAME]
    inventory = certification.discover_inventory(root)
    full = certification.select_inventory(inventory, "full")

    assert spec.tests == runner.ARCH147_PROTOTYPE_TESTS
    assert spec.ruff_paths == runner.ARCH147_PROTOTYPE_RUFF
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] == "full"
    for source, test in pairs:
        assert (root / source).is_file()
        assert (root / test).is_file()
        assert runner.ARCH147_PROTOTYPE_RUFF.count(source) == 1
        assert spec.ruff_paths.count(source) == 1
        assert runner.ARCH147_PROTOTYPE_TESTS.count(test) == 1
        assert spec.tests.count(test) == 1
        assert full.count(test) == 1
        assert source not in runner.ARCH147_RHC2_RUFF
        assert test not in runner.ARCH147_RHC2_TESTS
    assert runner._arch147_prototype_authority_check(root) == ()


def test_rhc2_successor_is_manually_owned_by_the_current_prototype_route():
    from scripts import arch147_rhc2_order_scope_successor_source as rhc2
    from scripts import current_source_authority

    root = Path(runner.__file__).resolve().parents[1]
    source = "scripts/arch147_rhc2_order_scope_successor_source.py"
    observer_test = (
        "tests/robinhood_mcp/test_agent_initiated_runtime_partition_observer.py"
    )
    spec = runner._checkpoint_specs()[runner.ARCH147_RHC2_NAME]

    assert (root / source).is_file()
    assert spec.preflight is runner._arch147_rhc2_preflight
    assert spec.execute is None
    assert spec.remote_branch is None
    assert spec.remote_head_env is None
    assert spec.ruff_paths.count(source) == 1
    assert runner.ARCH147_RHC2_RUFF.count(source) == 1
    assert runner.ARCH147_PROTOTYPE_RUFF.count(source) == 1
    assert spec.tests.count(observer_test) == 1
    assert runner.ARCH147_PROTOTYPE_TESTS.count(observer_test) == 1
    assert inspect.signature(rhc2._run_preflight).parameters == {}
    assert not hasattr(rhc2, "run_preflight")
    prototype_tree = ast.parse(
        inspect.getsource(runner._arch147_prototype_authority_check)
    )
    prototype_calls = {
        node.func.id
        for node in ast.walk(prototype_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "_arch147_rhc2_authority_check" in prototype_calls
    assert "_arch147_rhc2_preflight" not in prototype_calls
    assert current_source_authority.historical_preflight_dispatch_failures(root) == ()
    assert runner._arch147_rhc2_authority_check(root) == ()
    assert runner._arch147_prototype_authority_check(root) == ()


def test_rhc2_origin_guard_requires_the_resolved_module_inside_lexical_root(
    tmp_path: Path,
):
    from types import ModuleType

    from scripts import arch147_rhc2_order_scope_successor_source as rhc2

    root = tmp_path / "checkout"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    expected = scripts / "checkpoint_runner.py"
    expected.write_text("# expected source\n", encoding="ascii")
    module = ModuleType("fake_checkpoint_runner")
    module.__file__ = str(expected)

    assert rhc2._module_origin_is_canonical(
        module, repo_root=root, relative_path="scripts/checkpoint_runner.py"
    )

    foreign = tmp_path / "foreign_runner.py"
    foreign.write_text("# foreign source\n", encoding="ascii")
    module.__file__ = str(foreign)
    assert not rhc2._module_origin_is_canonical(
        module, repo_root=root, relative_path="scripts/checkpoint_runner.py"
    )


def test_l43_read_normalization_source_test_pairs_are_prepublication_owned():
    root = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[runner.ARCH147_PROTOTYPE_NAME]
    pairs = (
        (
            "src/trading_bot/robinhood_mcp/l43_read_adapter.py",
            "tests/robinhood_mcp/test_l43_read_adapter.py",
        ),
        (
            "src/trading_bot/live_prototype/l43_pre_effect_observation.py",
            "tests/live_prototype/test_l43_pre_effect_observation.py",
        ),
    )
    inventory = certification.discover_inventory(root)
    full = certification.select_inventory(inventory, "full")

    assert spec.tests == runner.ARCH147_PROTOTYPE_TESTS
    assert spec.ruff_paths == runner.ARCH147_PROTOTYPE_RUFF
    assert (
        runner.ARCH147_PROTOTYPE_RUFF.count(
            "src/trading_bot/robinhood_mcp/l43_read_adapter.py"
        )
        == 1
    )
    for source, test in pairs:
        assert (root / source).is_file()
        assert (root / test).is_file()
        assert runner.ARCH147_PROTOTYPE_TESTS.count(test) == 1
        assert spec.tests.count(test) == 1
        assert full.count(test) == 1
        assert runner._arch147_prototype_authority_check(root) == ()


def test_rhc3p_reconciliation_and_transport_are_prototype_owned():
    root = Path(runner.__file__).resolve().parents[1]
    registry = runner._checkpoint_specs()
    spec = registry[runner.ARCH147_PROTOTYPE_NAME]
    source_tests = (
        (
            "src/trading_bot/live_prototype/l43_post_effect_reconciler.py",
            "tests/live_prototype/test_l43_post_effect_reconciler.py",
        ),
        (
            "src/trading_bot/live_prototype/l43_effect_operator.py",
            "tests/live_prototype/test_l43_effect_operator.py",
        ),
        (
            "src/trading_bot/robinhood_mcp/l43_transport.py",
            "tests/robinhood_mcp/test_l43_transport.py",
        ),
    )
    inventory = certification.discover_inventory(root)
    full = certification.select_inventory(inventory, "full")
    ruff_owned = set(runner.ARCH147_PROTOTYPE_RUFF)

    assert spec.tests == runner.ARCH147_PROTOTYPE_TESTS
    assert spec.ruff_paths == runner.ARCH147_PROTOTYPE_RUFF
    assert spec.execute is None
    assert spec.preflight is runner._arch147_l43_a3_preflight
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] == "full"
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(spec.name) == 1
    assert (
        sum(
            item.remote_branch == runner.ARCH147_PROTOTYPE_BRANCH
            for item in registry.values()
        )
        == 1
    )
    assert (
        runner.resolve_ci_checkpoint(registry, runner.ARCH147_PROTOTYPE_BRANCH, "push")
        == spec.name
    )
    assert "src/trading_bot/live_prototype" in ruff_owned
    assert (
        runner.ARCH147_PROTOTYPE_RUFF.count(
            "src/trading_bot/robinhood_mcp/l43_transport.py"
        )
        == 1
    )
    assert "src/trading_bot/robinhood_mcp/l43_transport.py" not in (
        runner.ARCH147_RHC2_RUFF
    )
    for source, test in source_tests:
        assert (root / source).is_file()
        assert (root / test).is_file()
        assert runner.ARCH147_PROTOTYPE_TESTS.count(test) == 1
        assert spec.tests.count(test) == 1
        assert full.count(test) == 1
        assert test not in runner.ARCH147_RHC2_TESTS
    assert runner._arch147_prototype_authority_check(root) == ()


def test_rhc4_runtime_composition_and_restricted_live_mode_are_prototype_owned():
    root = Path(runner.__file__).resolve().parents[1]
    registry = runner._checkpoint_specs()
    spec = registry[runner.ARCH147_PROTOTYPE_NAME]
    source_tests = (
        (
            "src/trading_bot/live_prototype/l43_runtime.py",
            "tests/live_prototype/test_l43_runtime.py",
        ),
        (
            "src/trading_bot/live_prototype/l43_pre_effect_observation.py",
            "tests/live_prototype/test_l43_pre_effect_observation.py",
        ),
        (
            "src/trading_bot/live_prototype/restricted_live_application_service.py",
            "tests/live_prototype/test_restricted_live_application.py",
        ),
        (
            "scripts/run_live_prototype.py",
            "tests/live_prototype/test_launcher.py",
        ),
    )
    inventory = certification.discover_inventory(root)
    full = certification.select_inventory(inventory, "full")
    ruff_paths = runner.ARCH147_PROTOTYPE_RUFF

    def ruff_ownership_count(source: str) -> int:
        return sum(
            path == source
            or ((root / path).is_dir() and source.startswith(path.rstrip("/") + "/"))
            for path in ruff_paths
        )

    assert spec.tests == runner.ARCH147_PROTOTYPE_TESTS
    assert spec.ruff_paths == runner.ARCH147_PROTOTYPE_RUFF
    assert spec.preflight is runner._arch147_l43_a3_preflight
    assert spec.execute is None
    assert spec.remote_head_env is None
    assert spec.remote_branch == runner.ARCH147_PROTOTYPE_BRANCH
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] == "full"
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(spec.name) == 1
    assert (
        sum(
            item.remote_branch == runner.ARCH147_PROTOTYPE_BRANCH
            for item in registry.values()
        )
        == 1
    )
    assert (
        runner.resolve_ci_checkpoint(registry, runner.ARCH147_PROTOTYPE_BRANCH, "push")
        == spec.name
    )
    assert runner.ARCH147_PROTOTYPE_RUFF.count("src/trading_bot/live_prototype") == 1

    for source, test in source_tests:
        assert (root / source).is_file()
        assert (root / test).is_file()
        assert ruff_ownership_count(source) == 1
        assert runner.ARCH147_PROTOTYPE_TESTS.count(test) == 1
        assert spec.tests.count(test) == 1
        assert full.count(test) == 1
        assert inventory.count(test) == 1
        assert test not in runner.ARCH147_RHC2_TESTS
    assert runner._arch147_prototype_authority_check(root) == ()


def test_tiny_live_pivot_source_test_pairs_are_prepublication_owned():
    root = Path(runner.__file__).resolve().parents[1]
    pairs = (
        (
            "src/trading_bot/live_prototype/tiny_live_capability_admission.py",
            "tests/live_prototype/test_capability_tiny_live_admission.py",
        ),
        (
            "src/trading_bot/live_prototype/tiny_live_policy.py",
            "tests/live_prototype/test_tiny_live_policy.py",
        ),
        (
            "src/trading_bot/live_prototype/tiny_live_readiness_operator.py",
            "tests/live_prototype/test_tiny_live_readiness_operator.py",
        ),
        (
            "src/trading_bot/live_prototype/tiny_live_readiness_observer.py",
            "tests/live_prototype/test_tiny_live_readiness_observer.py",
        ),
    )
    registry = runner._checkpoint_specs()
    spec = registry[runner.ARCH147_PROTOTYPE_NAME]
    assert "src/trading_bot/live_prototype" in runner.ARCH147_PROTOTYPE_RUFF
    assert spec.preflight is runner._arch147_l43_a3_preflight
    assert spec.execute is None
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] == "full"
    assert all("l41r7" not in name.casefold() for name in registry)
    assert all(
        "l41r7" not in path.casefold()
        for path in runner.ARCH147_PROTOTYPE_TESTS + runner.ARCH147_PROTOTYPE_RUFF
    )

    inventory = certification.discover_inventory(root)
    full = set(certification.select_inventory(inventory, "full"))
    for source, test in pairs:
        source_path = root / source
        assert source_path.is_file()
        assert (root / test).is_file()
        assert runner.ARCH147_PROTOTYPE_TESTS.count(test) == 1
        assert test in spec.tests
        assert test in full
        source_text = source_path.read_text(encoding="utf-8")
        assert "l41r7" not in source_text.casefold()
        tree = ast.parse(source_text)
        assert not _production_imports(source, tree)
        imported_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_names.append(node.module or "")
                imported_names.extend(alias.name for alias in node.names)
        assert all("final_holdout" not in name.casefold() for name in imported_names)
        assert not any(
            (
                isinstance(node, ast.Name)
                and node.id in {"FINAL_HOLDOUT", "final_holdout"}
            )
            or (
                isinstance(node, ast.Attribute)
                and node.attr in {"FINAL_HOLDOUT", "final_holdout"}
            )
            or (
                isinstance(node, ast.Constant)
                and node.value in {"FINAL_HOLDOUT", "final_holdout"}
            )
            for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"eval", "exec", "__import__"}
            for node in ast.walk(tree)
        )
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
        "147 prototype A3 registration drift"
        in runner._arch147_prototype_authority_check(root)
    )
    assert calls == []


def test_live_prototype_imports_are_allowlisted_and_use_no_dynamic_dispatch():
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


_A3_HEAD = "a" * 40
_A3_TREE = "b" * 40
_A3_REASON = "AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW_ONLY"


def _a3_admission(a2, *, head: str = _A3_HEAD, tree: str = _A3_TREE, **changes):
    return replace(
        a2._SourceAdmission(
            root=str(a2._CANONICAL_WORKTREE),
            branch=runner.ARCH147_PROTOTYPE_BRANCH,
            source_head=head,
            source_tree=tree,
            porcelain="",
            origin="https://github.com/callmedraken/ai-trading-bot.git",
            remote_feature_head=head,
            remote_develop_head=head,
            feature_authority="PASS",
            prospective_develop_authority="PASS",
            reason=None,
        ),
        **changes,
    )


def _run_a3_fake_observer(
    monkeypatch,
    tmp_path: Path,
    *,
    observer_status=None,
    observer_reason: str = _A3_REASON,
    exception: bool = False,
    admission=None,
    post_admission=None,
    post_admission_exception: bool = False,
    module_mode: bool = False,
    events: list[str] | None = None,
    invalid_counter_text: str | None = None,
):
    from trading_bot.robinhood_mcp import (
        agent_initiated_partition_schema_observer as a2,
    )

    monkeypatch.setattr(
        a2, "_CANONICAL_WORKTREE", Path(runner.__file__).resolve().parents[1]
    )
    monkeypatch.setattr(a2, "_EVIDENCE_ROOT", tmp_path / "a2")
    a2._EVIDENCE_ROOT.mkdir()
    monkeypatch.setattr(a2, "_reject_reparse_ancestors", lambda path, *, stop: None)
    admission_calls = 0

    def admit_current_source(*, repo_root: Path):
        nonlocal admission_calls
        admission_calls += 1
        if events is not None:
            events.append(f"a2_source_admission_{admission_calls}")
        if admission_calls > 1:
            if post_admission_exception:
                raise RuntimeError("local source detail must not enter evidence")
            if post_admission is not None:
                return post_admission
        return admission or _a3_admission(a2)

    monkeypatch.setattr(a2, "_admit_current_source", admit_current_source)

    state = {
        "head": _A3_HEAD,
        "tree": _A3_TREE,
        "branch": runner.ARCH147_PROTOTYPE_BRANCH,
        "porcelain": "",
    }
    state_reads = 0

    def git_state(repo_root):
        nonlocal state_reads
        state_reads += 1
        if events is not None:
            events.append(f"runner_source_state_{state_reads}")
        return dict(state)

    monkeypatch.setattr(runner, "_git_state", git_state)
    monkeypatch.setattr(
        runner,
        "_remote_branch_head",
        lambda repo_root, branch: (
            events.append("runner_remote_admission") or _A3_HEAD
            if events is not None
            else _A3_HEAD
        ),
    )
    calls = []
    status_type = a2.AgentInitiatedPartitionObservationStatus
    status = (
        observer_status or status_type.AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW
    )

    class FakeObserver:
        def __init__(self):
            calls.append("constructed")
            if events is not None:
                events.append("observer_constructed")

        async def observe(self, *, evidence_dir: Path):
            calls.append("dispatched")
            if events is not None:
                events.append("observer_dispatched")
            assert evidence_dir.parent == a2._EVIDENCE_ROOT
            assert not evidence_dir.exists()
            evidence_dir.mkdir()
            evidence_file = evidence_dir / "evidence.json"
            evidence_file.write_text(
                json.dumps(
                    {
                        "source_head": _A3_HEAD,
                        "source_tree": _A3_TREE,
                        "partition_equality_proof": "NOT_PROVEN",
                        "production_order_scope_authority": "NOT_GRANTED",
                    }
                ),
                encoding="utf-8",
            )
            if exception:
                raise RuntimeError("provider or exception text must not be copied")
            attempts = a2._AttemptCounters()
            attempts.oauth_scope_entry_attempts = 1
            attempts.mcp_session_open_attempts = 1
            attempts.tools_list_attempts = 1
            attempts.tools_list_pages_received = 1
            attempt_material = attempts.material()
            if invalid_counter_text is not None:
                attempt_material["tools_list_attempts"] = invalid_counter_text
            raw = evidence_file.read_bytes()
            return a2.AgentInitiatedPartitionObservationResult(
                status,
                observer_reason,
                evidence_file,
                hashlib.sha256(raw).hexdigest(),
                attempt_material,
            )

    monkeypatch.setattr(
        a2, "RobinhoodAgentInitiatedRuntimePartitionSchemaObserver", FakeObserver
    )
    spec = runner._checkpoint_specs()[runner.ARCH147_PROTOTYPE_NAME]
    if module_mode:
        import runpy
        import subprocess
        import sys

        git_state_reads = 0
        real_subprocess_run = subprocess.run

        def fake_subprocess_run(command, *args, **kwargs):
            nonlocal git_state_reads
            values = tuple(str(value) for value in command)
            if values and values[0] == "git":
                if values[1:3] == ("ls-remote", "origin"):
                    if events is not None:
                        events.append("runner_remote_admission")
                    ref = values[-1]
                    return subprocess.CompletedProcess(
                        command, 0, f"{_A3_HEAD}\t{ref}\n", ""
                    )
                arguments = values[1:]
                if arguments[:2] == ("rev-parse", "HEAD"):
                    return subprocess.CompletedProcess(command, 0, _A3_HEAD, "")
                if arguments[:2] == ("rev-parse", "HEAD^{tree}"):
                    return subprocess.CompletedProcess(command, 0, _A3_TREE, "")
                if arguments[:2] == ("rev-parse", "--abbrev-ref"):
                    return subprocess.CompletedProcess(
                        command, 0, runner.ARCH147_PROTOTYPE_BRANCH, ""
                    )
                if arguments[:1] == ("status",):
                    git_state_reads += 1
                    if events is not None:
                        events.append(f"runner_source_state_{git_state_reads}")
                    return subprocess.CompletedProcess(command, 0, "", "")
            return real_subprocess_run(command, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
        argv = sys.argv
        monkeypatch.setattr(
            sys,
            "argv",
            [
                str(Path(runner.__file__)),
                "preflight",
                runner.ARCH147_PROTOTYPE_NAME,
                "--evidence-root",
                str(tmp_path / "runner"),
            ],
        )
        try:
            runpy.run_path(runner.__file__, run_name="__main__")
        except SystemExit as exc:
            assert exc.code == 0
        finally:
            monkeypatch.setattr(sys, "argv", argv)
        reports = tuple((tmp_path / "runner").rglob("report.json"))
        assert len(reports) == 1
        report_path = reports[0]
        report = json.loads(report_path.read_text(encoding="utf-8"))
        passed = report["status"] == "PASS"
    else:
        passed, report_path = runner.preflight_checkpoint(
            spec,
            repo_root=Path(runner.__file__).resolve().parents[1],
            evidence_root=tmp_path / "runner",
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
    return passed, report, calls


def test_a3_registration_and_active_test_ownership_are_exact():
    from scripts import arch147_l43_a3_source as a3
    from scripts import current_source_authority

    root = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[runner.ARCH147_PROTOTYPE_NAME]
    guard = "tests/runtime/checkpoint_runner/test_arch147_prototype.py"
    observer_test = (
        "tests/robinhood_mcp/test_agent_initiated_runtime_partition_schema.py"
    )
    assert spec.preflight is runner._arch147_l43_a3_preflight
    assert spec.execute is None
    assert spec.remote_head_env is None
    assert spec.ruff_paths.count("scripts/arch147_l43_a3_source.py") == 1
    assert (root / "scripts/arch147_l43_a3_source.py").is_file()
    assert spec.tests.count(guard) == 1
    assert spec.tests.count(observer_test) == 1
    assert runner._prepublication_admission_tests((guard,)).count(guard) == 1
    assert (
        runner._prepublication_admission_tests(
            ("scripts/arch147_l43_a3_source.py",)
        ).count(guard)
        == 1
    )
    assert inspect.signature(a3.run_preflight).parameters == {}
    assert inspect.signature(runner._arch147_l43_a3_preflight).parameters == {}
    from trading_bot.robinhood_mcp import (
        agent_initiated_partition_schema_observer as a2,
    )

    assert list(
        inspect.signature(
            a2.RobinhoodAgentInitiatedRuntimePartitionSchemaObserver.observe
        ).parameters
    ) == ["self", "evidence_dir"]
    assert not hasattr(a2._MetadataOnlyTransport, "call_tool")
    assert runner.preflight_checkpoint is runner._arch147_p6_preflight_checkpoint
    assert current_source_authority.historical_preflight_dispatch_failures(root) == ()
    assert runner._supervised_installation_operator_authority_check(root) == ()
    assert runner._arch147_prototype_authority_check(root) == ()


def test_a3_source_callback_rejects_registration_drift_before_admission(
    monkeypatch, tmp_path: Path
):
    from dataclasses import replace

    from scripts import arch147_l43_a3_source as a3
    from trading_bot.robinhood_mcp import (
        agent_initiated_partition_schema_observer as a2,
    )

    spec = runner._checkpoint_specs()[runner.ARCH147_PROTOTYPE_NAME]
    monkeypatch.setattr(
        a2, "_CANONICAL_WORKTREE", Path(runner.__file__).resolve().parents[1]
    )
    monkeypatch.setattr(
        runner,
        "_checkpoint_specs",
        lambda: {
            runner.ARCH147_PROTOTYPE_NAME: replace(
                spec, preflight=lambda: {"status": "PASS"}
            )
        },
    )
    admission_calls = []
    monkeypatch.setattr(
        a2,
        "_admit_current_source",
        lambda *, repo_root: admission_calls.append(repo_root),
    )
    result = a3.run_preflight()
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "A3_REGISTRATION_REJECTED"
    assert admission_calls == []


def test_a3_generic_source_admission_blocks_before_callback(
    monkeypatch, tmp_path: Path
):
    from scripts import arch147_l43_a3_source as a3

    state = {
        "head": _A3_HEAD,
        "tree": _A3_TREE,
        "branch": runner.ARCH147_PROTOTYPE_BRANCH,
        "porcelain": "",
    }
    callback_calls = []
    monkeypatch.setattr(runner, "_git_state", lambda repo_root: dict(state))
    monkeypatch.setattr(
        runner, "_remote_branch_head", lambda repo_root, branch: "c" * 40
    )
    monkeypatch.setattr(a3, "run_preflight", lambda: callback_calls.append("called"))
    spec = runner._checkpoint_specs()[runner.ARCH147_PROTOTYPE_NAME]
    with pytest.raises(RuntimeError, match="live remote branch head"):
        runner.preflight_checkpoint(
            spec,
            repo_root=Path(runner.__file__).resolve().parents[1],
            evidence_root=tmp_path / "generic-block",
        )
    assert callback_calls == []


def test_a3_existing_public_preflight_chain_orders_both_source_gates_before_observer(
    monkeypatch, tmp_path: Path
):
    events = []
    passed, report, calls = _run_a3_fake_observer(monkeypatch, tmp_path, events=events)
    assert passed is True
    assert report["result"]["status"] == "PASS"
    assert report["result"]["observer_invocation_attempts"] == 1
    assert events.index("runner_source_state_1") < events.index(
        "runner_remote_admission"
    )
    assert events.index("runner_remote_admission") < events.index(
        "a2_source_admission_1"
    )
    assert events.index("a2_source_admission_1") < events.index("observer_constructed")
    assert events.index("observer_dispatched") < events.index("a2_source_admission_2")
    assert events.index("a2_source_admission_2") < events.index("runner_source_state_2")
    assert calls == ["constructed", "dispatched"]


def test_a3_module_mode_preflight_uses_same_registered_callback(
    monkeypatch, tmp_path: Path
):
    events = []
    passed, report, calls = _run_a3_fake_observer(
        monkeypatch, tmp_path, module_mode=True, events=events
    )
    assert passed is True
    assert report["result"]["status"] == "PASS"
    assert report["result"]["observer_invocation_attempts"] == 1
    assert events.index("runner_remote_admission") < events.index(
        "a2_source_admission_1"
    )
    assert events.index("a2_source_admission_1") < events.index("observer_dispatched")
    assert calls == ["constructed", "dispatched"]


def test_a3_post_dispatch_source_recheck_blocks_and_preserves_evidence(
    monkeypatch, tmp_path: Path
):
    from trading_bot.robinhood_mcp import (
        agent_initiated_partition_schema_observer as a2,
    )

    changed = _a3_admission(a2, head="c" * 40, tree="d" * 40)
    passed, report, calls = _run_a3_fake_observer(
        monkeypatch,
        tmp_path,
        post_admission=changed,
    )
    result = report["result"]
    assert passed is False
    assert result["reason"] == "OBSERVER_SOURCE_RECHECK_BLOCKED"
    assert result["source_recheck_status"] == "BLOCKED"
    assert result["observer_invocation_attempts"] == 1
    assert result["observer_evidence_written"] is True
    assert result["observer_evidence_sha256"] is not None
    assert result["attempt_counters"]["tools_list_attempts"] == 1
    assert calls == ["constructed", "dispatched"]


def test_a3_blocked_observer_admission_records_zero_provider_attempts(
    monkeypatch, tmp_path: Path
):
    from trading_bot.robinhood_mcp import (
        agent_initiated_partition_schema_observer as a2,
    )

    blocked = _a3_admission(
        a2,
        reason="SOURCE_AUTHORITY_BLOCKED",
        feature_authority="FAIL",
    )
    passed, report, calls = _run_a3_fake_observer(
        monkeypatch, tmp_path, admission=blocked
    )
    result = report["result"]
    assert passed is False
    assert result["reason"] == "SOURCE_ADMISSION_BLOCKED"
    assert result["observer_invocation_attempts"] == 0
    assert result["attempt_counters"]["oauth_scope_entry_attempts"] == 0
    assert result["attempt_counters"]["mcp_session_open_attempts"] == 0
    assert result["attempt_counters"]["tools_list_attempts"] == 0
    assert calls == []


def test_a3_positive_observer_result_is_bound_review_only(monkeypatch, tmp_path: Path):
    from trading_bot.robinhood_mcp import (
        agent_initiated_partition_schema_observer as a2,
    )

    assert a2._CANONICAL_WORKTREE == Path(
        r"F:\AI\worktrees\ai-trading-bot-live-prototype-current"
    )
    assert a2._EVIDENCE_ROOT == Path(r"F:\AI\temp")
    passed, report, calls = _run_a3_fake_observer(monkeypatch, tmp_path)
    result = report["result"]
    evidence_path = Path(result["observer_evidence_path"])
    assert passed is True
    assert report["status"] == "PASS"
    assert result["disposition"] == "SUCCESS_REVIEW_ONLY"
    assert result["observer_dispatched"] is True
    assert result["observer_invocation_attempts"] == 1
    assert (
        result["observer_status"] == "AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW"
    )
    assert result["observer_evidence_valid"] is True
    assert (
        result["observer_evidence_sha256"]
        == hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    )
    assert result["source_head"] == _A3_HEAD
    assert result["source_tree"] == _A3_TREE
    assert result["partition_equality_proof"] == "NOT_PROVEN"
    assert result["production_order_scope_authority"] == "NOT_GRANTED"
    assert evidence_path.parent.parent == tmp_path / "a2"
    assert a2._RUNTIME_EVIDENCE_NAME.fullmatch(evidence_path.parent.name)
    assert calls == ["constructed", "dispatched"]


def test_a3_observer_failure_is_preserved_without_retry(monkeypatch, tmp_path: Path):
    from trading_bot.robinhood_mcp import (
        agent_initiated_partition_schema_observer as a2,
    )

    status = (
        a2.AgentInitiatedPartitionObservationStatus.RUNTIME_PROOF_ELIGIBILITY_UNPROVEN
    )
    passed, report, calls = _run_a3_fake_observer(
        monkeypatch,
        tmp_path,
        observer_status=status,
        observer_reason="RUNTIME_PROOF_ELIGIBILITY_UNPROVEN",
    )
    result = report["result"]
    assert passed is False
    assert result["observer_status"] == "RUNTIME_PROOF_ELIGIBILITY_UNPROVEN"
    assert result["observer_reason"] == "RUNTIME_PROOF_ELIGIBILITY_UNPROVEN"
    assert result["reason"] == "RUNTIME_PROOF_ELIGIBILITY_UNPROVEN"
    assert result["observer_evidence_valid"] is True
    assert result["observer_invocation_attempts"] == 1
    assert result["attempt_counters"]["tools_list_attempts"] == 1
    assert calls == ["constructed", "dispatched"]


def test_a3_malformed_typed_result_strings_are_not_copied(monkeypatch, tmp_path: Path):
    raw_secret = "provider exception token-secret counter-secret"
    passed, report, calls = _run_a3_fake_observer(
        monkeypatch,
        tmp_path,
        observer_reason=raw_secret,
        invalid_counter_text=raw_secret,
    )
    result = report["result"]
    serialized = json.dumps(report)
    assert passed is False
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "OBSERVER_RESULT_INVALID"
    assert result["observer_reason"] == "OBSERVER_RESULT_INVALID"
    assert result["attempt_counters"] is None
    assert result["attempt_counters_status"] == "INVALID"
    assert raw_secret not in serialized
    assert calls == ["constructed", "dispatched"]


def test_a3_escaped_observer_exception_keeps_evidence_and_unknown_counts(
    monkeypatch, tmp_path: Path
):
    passed, report, calls = _run_a3_fake_observer(monkeypatch, tmp_path, exception=True)
    result = report["result"]
    assert passed is False
    assert result["status"] == "BLOCKED"
    assert result["observer_status"] == "OBSERVER_EXCEPTION_AFTER_DISPATCH"
    assert result["observer_invocation_attempts"] == 1
    assert result["attempt_counters"] is None
    assert result["attempt_counters_status"] == "UNKNOWN_AFTER_DISPATCH_EXCEPTION"
    assert result["observer_evidence_written"] is True
    assert result["observer_evidence_sha256"] is not None
    assert "provider or exception text" not in json.dumps(report)
    assert calls == ["constructed", "dispatched"]


def test_a3_post_dispatch_admission_exception_preserves_observer_result(
    monkeypatch, tmp_path: Path
):
    passed, report, calls = _run_a3_fake_observer(
        monkeypatch, tmp_path, post_admission_exception=True
    )
    result = report["result"]
    assert passed is False
    assert report["source"]["identity_stable"] is True
    assert result["reason"] == "OBSERVER_SOURCE_RECHECK_BLOCKED"
    assert result["source_recheck_status"] == "BLOCKED"
    assert (
        result["observer_status"] == "AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW"
    )
    assert result["observer_evidence_sha256"] is not None
    assert result["attempt_counters"]["tools_list_attempts"] == 1
    assert calls == ["constructed", "dispatched"]


def _q1_accepted_snapshot() -> q1_source._SourceSnapshot:
    head = "a" * 40
    return q1_source._SourceSnapshot(
        root_is_canonical=True,
        windows_host=True,
        canonical_origin=True,
        clean=True,
        branch=q1_source.FEATURE_BRANCH,
        local_head=head,
        local_tree="b" * 40,
        feature_head=head,
        develop_head=head,
    )


def _q1_blocked_result() -> dict[str, object]:
    return q1._safe_result(
        q1._Context(
            source=None,
            origin=None,
            snapshot=None,
            pre_effect=None,
            requested_entry_usd=Decimal("10.00"),
            counts_unknown=False,
        ),
        q1.QualificationOutcome.BLOCKED,
        ("FAKE_READ_BLOCKED",),
        challenge=None,
    )


def _q1_ready_result() -> dict[str, object]:
    source = SimpleNamespace(source_head="a" * 40, source_tree="b" * 40)
    origin = SimpleNamespace(
        runtime_identity=SimpleNamespace(
            config_digest="c" * 64,
            binding_digest="d" * 64,
        ),
        journal_sha256="e" * 64,
    )
    snapshot = SimpleNamespace(last_sequence=1, journal_sha256="f" * 64)
    plan = SimpleNamespace(
        account_fingerprint="1" * 64,
        session=SimpleNamespace(target_session="2026-11-17"),
        binding_sha256="2" * 64,
    )
    pre_effect = SimpleNamespace(
        plan=plan,
        evidence_sha256="3" * 64,
        blockers=frozenset(),
        robinhood_read_count=1,
        robinhood_page_count=1,
        alpaca_provider_call_count=1,
        credential_read_count=1,
    )
    context = SimpleNamespace(
        source=source,
        origin=origin,
        snapshot=snapshot,
        pre_effect=pre_effect,
        requested_entry_usd=Decimal("10.00"),
        counts_unknown=False,
    )
    return q1._safe_result(
        context,
        q1.QualificationOutcome.READY_FOR_EXACT_ENTRY_AUTHORIZATION_REVIEW,
        (),
        challenge="4" * 64,
    )


def test_q1_is_manual_read_only_and_existing_full_route_remains_unique():
    root = Path(runner.__file__).resolve().parents[1]
    specs = runner._checkpoint_specs()
    spec = specs[runner.ARCH147_Q1_NAME]
    prototype_spec = specs[runner.ARCH147_PROTOTYPE_NAME]
    prototype_test_owner = "tests/runtime/checkpoint_runner/test_arch147_prototype.py"

    assert (
        sum(candidate.name == runner.ARCH147_Q1_NAME for candidate in specs.values())
        == 1
    )
    assert prototype_test_owner in spec.tests
    assert prototype_test_owner in prototype_spec.tests
    assert (
        "tests/runtime/checkpoint_runner/test_retained_arch128_130.py" not in spec.tests
    )
    assert spec.preflight is runner._arch147_q1_preflight
    assert spec.execute is None
    assert spec.remote_branch is None
    assert spec.remote_head_env is None
    assert runner.ARCH147_Q1_NAME not in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert runner.ARCH147_Q1_NAME not in runner.CI_CERTIFICATION_PROFILES
    assert runner._arch147_q1_authority_check(root) == ()
    assert current_owner("ARCH147_Q1_NAME") == "checkpoint_runner"
    assert current_owner("ARCH147_Q1_TESTS") == "checkpoint_runner"
    assert current_owner("ARCH147_Q1_RUFF") == "checkpoint_runner"
    assert current_owner("_arch147_q1_authority_check") == "checkpoint_runner"
    assert current_owner("_arch147_q1_preflight") == "checkpoint_runner"
    assert current_owner("scripts/arch147_l43_q1_source.py") == "checkpoint_runner"
    assert (
        runner.resolve_ci_checkpoint(specs, runner.ARCH147_PROTOTYPE_BRANCH, "push")
        == runner.ARCH147_PROTOTYPE_NAME
    )
    assert runner.CI_CERTIFICATION_PROFILES[runner.ARCH147_PROTOTYPE_NAME] == "full"
    assert q1._is_sanitized_result(_q1_blocked_result())


def test_q1_source_and_tests_are_prepublication_owned_with_family_growth():
    guard = "tests/runtime/checkpoint_runner/test_arch147_prototype.py"
    q1_paths = runner.ARCH147_Q1_RUFF
    for path in q1_paths:
        selected = runner._prepublication_admission_tests((path,))
        assert guard in selected
        assert all(test in selected for test in runner.ARCH147_Q1_TESTS)
        assert selected.count(guard) == 1

    for synthetic in (
        "src/trading_bot/live_prototype/future_q1_component.py",
        "tests/live_prototype/test_future_q1_component.py",
    ):
        selected = runner._prepublication_admission_tests((synthetic,))
        assert guard in selected
        assert all(test in selected for test in runner.ARCH147_Q1_TESTS)

    unrelated = runner._prepublication_admission_tests(
        ("src/trading_bot/domain/unrelated_component.py",)
    )
    assert guard not in unrelated
    assert not any(test in unrelated for test in runner.ARCH147_Q1_TESTS)

    authority_infrastructure = runner._prepublication_admission_tests(
        ("scripts/source_authority.py",)
    )
    assert guard in authority_infrastructure
    assert all(test in authority_infrastructure for test in runner.ARCH147_Q1_TESTS)


def test_q1_source_gate_blocks_before_import_and_records_known_zero_calls(monkeypatch):
    blocked = replace(_q1_accepted_snapshot(), develop_head="c" * 40)
    monkeypatch.setattr(q1_source, "_capture_source_snapshot", lambda: blocked)

    def unexpected_import():
        pytest.fail("Q1 module loaded before accepted-source admission")

    monkeypatch.setattr(q1_source, "_load_q1_owner", unexpected_import)
    report = q1_source.run_preflight()

    assert report["status"] == "BLOCKED"
    assert report["source_admission"]["status"] == "BLOCKED"
    assert report["dispatch"] == {
        "status": "NOT_STARTED",
        "provider_call_counts": {
            "robinhood_reads": 0,
            "robinhood_pages": 0,
            "alpaca_provider_calls": 0,
            "credential_reads": 0,
        },
        "reason_codes": [],
    }
    assert report["qualification"] is None


def test_q1_runner_callback_delegates_only_to_registered_adapter(monkeypatch):
    sentinel = {"status": "BLOCKED"}
    monkeypatch.setattr(q1_source, "run_preflight", lambda: sentinel)

    assert runner._arch147_q1_preflight() is sentinel
    assert inspect.signature(runner._arch147_q1_preflight).parameters == {}


def test_q1_keeps_source_admission_pass_independent_of_blocked_result(monkeypatch):
    accepted = _q1_accepted_snapshot()
    monkeypatch.setattr(q1_source, "_capture_source_snapshot", lambda: accepted)
    result = _q1_blocked_result()
    owner = SimpleNamespace(
        _run_protected_preflight=lambda: result,
        _is_sanitized_result=q1._is_sanitized_result,
    )
    monkeypatch.setattr(q1_source, "_load_q1_owner", lambda: owner)

    report = q1_source.run_preflight()

    assert report["status"] == "BLOCKED"
    assert report["source_admission"]["status"] == "PASS"
    assert report["dispatch"]["status"] == "COMPLETED"
    assert report["qualification"] == result


def test_q1_source_drift_redacts_ready_challenge_but_preserves_result_digest(
    monkeypatch,
):
    before = _q1_accepted_snapshot()
    after = replace(
        before,
        local_head="c" * 40,
        local_tree="d" * 40,
        feature_head="c" * 40,
        develop_head="c" * 40,
    )
    snapshots = iter((before, after))
    monkeypatch.setattr(q1_source, "_capture_source_snapshot", lambda: next(snapshots))
    result = _q1_ready_result()
    assert q1._is_sanitized_result(result)
    owner = SimpleNamespace(
        _run_protected_preflight=lambda: result,
        _is_sanitized_result=q1._is_sanitized_result,
    )
    monkeypatch.setattr(q1_source, "_load_q1_owner", lambda: owner)

    report = q1_source.run_preflight()

    assert report["status"] == "BLOCKED"
    assert report["source_admission"]["status"] == "BLOCKED"
    assert report["dispatch"]["status"] == "COMPLETED"
    invalidated = report["qualification"]
    assert invalidated["status"] == "BLOCKED"
    assert invalidated["outcome"] == "BLOCKED"
    assert invalidated["result_sha256"]
    assert "challenge_sha256" not in invalidated
    assert invalidated["provider_call_counts"] == result["provider_call_counts"]


@pytest.mark.parametrize(
    "failure_type",
    (RuntimeError, asyncio.CancelledError, KeyboardInterrupt),
)
def test_q1_escaped_failure_is_sanitized_and_keeps_counts_unknown(
    monkeypatch, capsys, failure_type
):
    accepted = _q1_accepted_snapshot()
    monkeypatch.setattr(q1_source, "_capture_source_snapshot", lambda: accepted)
    calls = []

    def escaped_failure():
        calls.append("started")
        print("raw-provider-payload")
        logging.getLogger("q1-test").error("raw-provider-trace")
        raise failure_type("credential-bearing-provider-error")

    owner = SimpleNamespace(
        _run_protected_preflight=escaped_failure,
        _is_sanitized_result=q1._is_sanitized_result,
    )
    monkeypatch.setattr(q1_source, "_load_q1_owner", lambda: owner)

    report = q1_source.run_preflight()
    captured = capsys.readouterr()

    encoded = json.dumps(report, sort_keys=True)
    assert captured.out == ""
    assert captured.err == ""
    assert "raw-provider-payload" not in encoded
    assert "raw-provider-trace" not in encoded
    assert "credential-bearing-provider-error" not in encoded
    assert calls == ["started"]
    assert report["source_admission"]["status"] == "PASS"
    assert report["dispatch"] == {
        "status": "FAILED",
        "provider_call_counts": None,
        "reason_codes": ["QUALIFICATION_DISPATCH_FAILED"],
    }


def test_q1_runner_loads_only_this_worktrees_production_module():
    owner = q1_source._load_q1_owner()
    root = Path(runner.__file__).resolve().parents[1]
    source_root = (root / "src").resolve(strict=True)

    assert source_root in Path(owner.__file__).resolve(strict=True).parents
    assert owner._run_protected_preflight.__name__ == "_run_protected_preflight"
