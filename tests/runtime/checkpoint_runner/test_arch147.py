"""Architecture 147 checkpoint and current source-authority coverage."""

import ast
from pathlib import Path

import pytest

from scripts import arch147_source_authority as successor
from scripts import checkpoint_runner as runner
from scripts import current_source_authority as current
from scripts import source_authority as ownership

ROOT = Path(runner.__file__).resolve().parents[1]


def test_arch147_is_current_source_only_full_without_effect_dispatch():
    spec = runner._checkpoint_specs()[runner.ARCH147_NAME]
    assert spec.name == runner.ARCH147_NAME
    assert spec.remote_branch == runner.ARCH147_BRANCH
    assert spec.preflight is None
    assert spec.execute is None
    assert runner.CI_CERTIFICATION_PROFILES[runner.ARCH147_NAME] == "full"
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS[0] == runner.ARCH147_NAME
    assert (
        spec.tests.count(
            "tests/experiments/test_historical_research_desktop_acquisition.py"
        )
        == 1
    )
    assert "scripts/acquire_desktop_research.py" in spec.ruff_paths
    assert "scripts/run_desktop_research_campaign.py" in spec.ruff_paths
    assert "src/trading_bot/gui/desktop_campaign_service.py" in spec.ruff_paths
    assert "tests/experiments/test_desktop_research_campaign.py" in spec.tests
    assert "tests/experiments/test_desktop_research_campaign_gui.py" in spec.tests
    assert (
        "src/trading_bot/experiments/historical_research_desktop_acquisition.py"
        in spec.ruff_paths
    )
    assert (
        spec.tests.count("tests/experiments/test_historical_research_partial_state.py")
        == 1
    )


def test_consumed_architecture_146_observer_is_not_current_route():
    assert runner.ARCH146_PARTIAL_STATE_NAME not in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert runner.ARCH146_PRE_B2_NAME not in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert runner.ARCH146B1_NAME not in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert current.current_preflight_dispatch_failures(ROOT) == ()


def test_arch147_authority_is_static_and_does_not_dispatch_host_work(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Architecture 147 authority dispatched an effect")

    monkeypatch.setattr(runner, "preflight_checkpoint", forbidden)
    monkeypatch.setattr(runner, "execute_checkpoint", forbidden)
    assert runner._arch147_authority_check(ROOT) == ()


def test_arch147_resolves_for_feature_branch():
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), runner.ARCH147_BRANCH, "push"
        )
        == runner.ARCH147_NAME
    )


def test_export_successor_preserves_historical_pin_and_security_classification():
    path = successor.MARKET_DATA_INITIALIZER
    pin = runner.READONLY_SOURCE_PINS[path]
    assert pin == "3b5237e5f7a6bbfa34213f48db9aa8dc3f52fe66"
    assert ownership.classify_path(path) is ownership.PinClass.SECURITY_SEMANTIC
    assert ownership.current_owner(path) is None
    assert ownership.historical_blob(ROOT, pin)
    assert successor.desktop_export_authority_failures(ROOT) == ()
    assert ownership.blob_matches(ROOT, ROOT / path, pin)
    assert runner._readonly_admission_graph_check(ROOT) == ()
    assert not successor.initializer_preserves_exports(ROOT, path, "0" * 40)
    assert not successor.initializer_preserves_exports(
        ROOT, successor.EXPERIMENTS_INITIALIZER, "0" * 40
    )
    assert ownership.blob_matches(
        ROOT,
        ROOT / successor.EXPERIMENTS_INITIALIZER,
        successor.EXPERIMENTS_PREDECESSOR_BLOB,
    )
    assert runner._arch146a_authority_check(ROOT) == ()
    assert runner._checkpoint_specs()[runner.ARCH146A_NAME].authority_check(ROOT) == ()


@pytest.mark.parametrize(
    "relative",
    [
        successor.MARKET_DATA_INITIALIZER,
        successor.EXPERIMENTS_INITIALIZER,
    ],
)
@pytest.mark.parametrize(
    "mutation",
    [
        "owner",
        "missing_export",
        "resolver",
        "extra_statement",
        "extra_import",
        "public_list",
        "rebind",
        "duplicate_resolver",
        "eager_call",
    ],
)
def test_export_successor_rejects_any_semantic_drift(tmp_path, relative, mutation):
    source = (ROOT / relative).read_text(encoding="utf-8")
    tree = ast.parse(source)
    groups = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "_LAZY_EXPORT_GROUPS"
    )
    resolver = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "__getattr__"
    )
    if mutation == "owner":
        groups.value.keys[0].value = "trading_bot.unreviewed_adapter"
    elif mutation == "missing_export":
        groups.value.values[0].elts.pop()
    elif mutation == "resolver":
        resolver.body[-1] = ast.parse("return None").body[0]
    elif mutation == "extra_statement":
        tree.body.extend(ast.parse("print('unreviewed import effect')").body)
    elif mutation == "extra_import":
        tree.body.extend(ast.parse("import socket").body)
    elif mutation == "public_list":
        public = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "__all__"
        )
        public.value.elts.pop()
    elif mutation == "rebind":
        tree.body.extend(ast.parse("_LAZY_EXPORTS = {}").body)
    elif mutation == "duplicate_resolver":
        tree.body.append(resolver)
    else:
        tree.body.extend(ast.parse("__getattr__('AlpacaDailySnapshotProvider')").body)
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    destination.write_text(ast.unparse(tree), encoding="utf-8")
    pin = (
        runner.READONLY_SOURCE_PINS[relative]
        if relative == successor.MARKET_DATA_INITIALIZER
        else successor.EXPERIMENTS_PREDECESSOR_BLOB
    )
    assert not successor.initializer_preserves_exports(tmp_path, relative, pin)
    assert not ownership.blob_matches(tmp_path, destination, pin)


def test_unchanged_historical_initializer_remains_exactly_accepted(tmp_path):
    relative = successor.MARKET_DATA_INITIALIZER
    pin = runner.READONLY_SOURCE_PINS[relative]
    historical = ownership.historical_blob(ROOT, pin)
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    destination.write_bytes(historical)
    assert ownership.blob_matches(tmp_path, destination, pin)
    # P3 separately requires the offline lazy form; old source stays historical.
    assert not successor.initializer_preserves_exports(tmp_path, relative, pin)
