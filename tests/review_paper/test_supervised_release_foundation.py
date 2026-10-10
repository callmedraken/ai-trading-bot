"""Fake release material only; never open production or scratch namespaces."""

import ast
import builtins
import json
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner
from scripts import run_test_certification as certification
from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.supervised_release import (
    DURABLE_DATA_ROOT,
    LAUNCHER_RELATIVE_PATH,
    PRODUCTION_PYTHON,
    STRATEGY_ID,
    STRATEGY_VERSION,
    ReleaseInventoryEntry,
    ReleaseManifest,
    canonical_strategy_config,
    project_scheduler_action,
    release_root,
    strategy_config_sha256,
    validate_release_root,
)

NAME = "arch133-robinhood-supervised-release-foundation"
ROOT = Path(__file__).resolve().parents[2]


def manifest(**changes):
    material = dict(
        source_head="a" * 40,
        source_tree="b" * 40,
        production_python_version="3.14.3",
        production_python_sha256="c" * 64,
        launcher_relative_path=LAUNCHER_RELATIVE_PATH,
        launcher_sha256="d" * 64,
        source_inventory=(
            ReleaseInventoryEntry(LAUNCHER_RELATIVE_PATH, "d" * 64),
            ReleaseInventoryEntry(
                "src/trading_bot/strategies/moving_average.py", "e" * 64
            ),
            ReleaseInventoryEntry("pyproject.toml", "f" * 64),
        ),
        strategy_id=STRATEGY_ID,
        strategy_version=STRATEGY_VERSION,
        strategy_config=MovingAverageCrossoverConfig(5, 20, Decimal("1.00")),
        risk_policy_id="long-only-reviewed-policy",
        risk_policy_version="1.0.0",
        risk_policy_sha256="1" * 64,
    )
    return ReleaseManifest(**(material | changes))


def test_canonical_round_trip_and_logical_material_identity():
    original = manifest()
    assert original.release_id == "release-ed0cca1bbc6152f4beeeaee4fe5e2b3a"
    assert original.source_inventory_sha256 == (
        "ed7069757a141cb02ee9d4678611800a1ba4f9b73e8cfcc46cdc6b6a7bd32511"
    )
    assert original.strategy_config_sha256 == (
        "f20af916c822820459636b43bcd475e7e458aa94ca01209d53dd618a7024ddfe"
    )
    assert ReleaseManifest.from_json(original.to_json()) == original
    pretty = json.dumps(json.loads(original.to_json()), indent=3)
    assert ReleaseManifest.from_json(pretty).release_id == original.release_id
    assert ReleaseManifest.from_json(pretty).to_json() == original.to_json()
    assert manifest().release_id == original.release_id
    assert (
        manifest(
            strategy_config=MovingAverageCrossoverConfig(5, 20, Decimal("1"))
        ).release_id
        == original.release_id
    )
    assert "F:" not in original.to_json()
    assert "release_id" not in original._material()
    with pytest.raises(FrozenInstanceError):
        original.source_head = "c" * 40


@pytest.mark.parametrize(
    "change",
    [
        {"source_head": "2" * 40},
        {"source_tree": "3" * 40},
        {"strategy_version": "1.0.1"},
        {"strategy_config": MovingAverageCrossoverConfig(6, 20, Decimal("1"))},
        {"strategy_config": MovingAverageCrossoverConfig(5, 21, Decimal("1"))},
        {"strategy_config": MovingAverageCrossoverConfig(5, 20, Decimal("2"))},
        {"production_python_version": "3.14.4"},
        {"production_python_sha256": "4" * 64},
        {"risk_policy_id": "other-reviewed-policy"},
        {"risk_policy_version": "1.1.0"},
        {"risk_policy_sha256": "5" * 64},
    ],
)
def test_changed_bound_material_changes_release_identity(change):
    assert manifest(**change).release_id != manifest().release_id


def test_inventory_binding_is_ordered_exact_and_launcher_consistent():
    original = manifest()
    updated = original.source_inventory[:-1] + (
        ReleaseInventoryEntry("pyproject.toml", "0" * 64),
    )
    assert replace(original, source_inventory=updated).release_id != original.release_id
    assert (
        replace(original, source_inventory=original.source_inventory[::-1]).release_id
        != original.release_id
    )
    with pytest.raises(ValueError):
        replace(
            original,
            source_inventory=original.source_inventory
            + (original.source_inventory[0],),
        )
    with pytest.raises(ValueError):
        replace(
            original,
            source_inventory=original.source_inventory
            + (ReleaseInventoryEntry(LAUNCHER_RELATIVE_PATH.upper(), "d" * 64),),
        )
    with pytest.raises(ValueError):
        replace(original, source_inventory=original.source_inventory[1:])
    with pytest.raises(ValueError):
        replace(original, launcher_sha256="0" * 64)


@pytest.mark.parametrize("field", list(json.loads(manifest().to_json())))
@pytest.mark.parametrize("operation", ["missing", "unknown"])
def test_exact_top_level_fields(field, operation):
    raw = json.loads(manifest().to_json())
    if operation == "missing":
        raw.pop(field)
    else:
        raw[field + "_unknown"] = raw[field]
    with pytest.raises(ValueError):
        ReleaseManifest.from_json(json.dumps(raw))


@pytest.mark.parametrize("text", ["null", "[]", "{", "1", "true", "{}", 1, None])
def test_malformed_json(text):
    with pytest.raises(ValueError):
        ReleaseManifest.from_json(text)


@pytest.mark.parametrize(
    "field",
    ["schema", "release_id", "source_inventory_sha256", "strategy_config_sha256"],
)
def test_derived_identity_and_schema_tampering(field):
    raw = json.loads(manifest().to_json())
    raw[field] = "wrong"
    with pytest.raises(ValueError):
        ReleaseManifest.from_json(json.dumps(raw))


@pytest.mark.parametrize("nested", ["strategy_config", "source_inventory"])
def test_nested_unknown_missing_and_duplicate_json_fields(nested):
    raw = json.loads(manifest().to_json())
    target = raw[nested] if nested == "strategy_config" else raw[nested][0]
    target["unknown"] = True
    with pytest.raises(ValueError):
        ReleaseManifest.from_json(json.dumps(raw))
    target.pop("unknown")
    target.pop(next(iter(target)))
    with pytest.raises(ValueError):
        ReleaseManifest.from_json(json.dumps(raw))
    text = manifest().to_json()
    with pytest.raises(ValueError, match="duplicate"):
        ReleaseManifest.from_json(text[:-1] + ',"source_head":"' + "a" * 40 + '"}')
    with pytest.raises(ValueError, match="duplicate"):
        ReleaseManifest.from_json(
            text.replace('"short_window":5', '"short_window":5,"short_window":5')
        )


@pytest.mark.parametrize(
    "field",
    [
        "source_head",
        "source_tree",
        "production_python_sha256",
        "launcher_sha256",
        "risk_policy_sha256",
    ],
)
@pytest.mark.parametrize(
    "bad", [None, True, 123, "", "A" * 64, "g" * 64, "a" * 39, "a" * 65, " a" * 32]
)
def test_invalid_digests(field, bad):
    with pytest.raises(ValueError):
        manifest(**{field: bad})


@pytest.mark.parametrize(
    "field", ["production_python_version", "strategy_version", "risk_policy_version"]
)
@pytest.mark.parametrize(
    "bad", [None, True, 3, "", "1", "1.0", "01.0.0", "1.0.0rc1", "1.0.-1", "1.0.0 "]
)
def test_invalid_versions(field, bad):
    with pytest.raises(ValueError):
        manifest(**{field: bad})


@pytest.mark.parametrize("bad", ["2.7.18", "3.11.9", "4.0.0"])
def test_python_floor(bad):
    with pytest.raises(ValueError):
        manifest(production_python_version=bad)


@pytest.mark.parametrize(
    "path",
    [
        "../escape.py",
        "scripts/../escape.py",
        "scripts/./escape.py",
        "/scripts/escape.py",
        "scripts//escape.py",
        r"scripts\escape.py",
        r"F:\AITradingBot\Arch133\wake.sqlite",
        "F:/AITradingBot/Arch133/paper.sqlite",
        "Arch133/activation.json",
        "scripts/Arch133/activation.json",
        "src/Arch133/wake.json",
        "runtime/python.exe",
        "releases/other/launcher.py",
        "scripts/escape.py:stream",
        "scripts/NUL.py",
        "scripts/COM1.py",
        "scripts/file.py.",
        "scripts/space name.py",
        "scripts/a\n.py",
        "scripts/paper.sqlite",
        "scripts/../Arch133/paper.json",
        None,
        1,
    ],
)
def test_unsafe_or_durable_inventory_names_rejected(path):
    with pytest.raises(ValueError):
        ReleaseInventoryEntry(path, "a" * 64)
    with pytest.raises(ValueError):
        manifest(launcher_relative_path=path)


def test_only_reviewed_launcher_and_public_strategy():
    with pytest.raises(ValueError):
        manifest(launcher_relative_path="scripts/other.py")
    with pytest.raises(ValueError):
        manifest(strategy_id="arbitrary.plugin")
    with pytest.raises(TypeError):
        canonical_strategy_config({})
    with pytest.raises(ValueError):
        manifest(risk_policy_id="../policy")
    assert DURABLE_DATA_ROOT == r"F:\AITradingBot\Arch133"
    assert STRATEGY_ID == "MovingAverageCrossoverStrategy"
    assert STRATEGY_VERSION == "1.0.0"


def test_strategy_config_exact_decimal_and_context_independence():
    config = MovingAverageCrossoverConfig(
        5, 20, Decimal("123456789012345678901234567890.00")
    )
    expected = {
        "schema": "moving-average-crossover-config/v1",
        "short_window": 5,
        "long_window": 20,
        "desired_quantity": "12345678901234567890123456789e1",
    }
    digest = strategy_config_sha256(config)
    with localcontext() as context:
        context.prec = 2
        context.capitals = 0
        assert canonical_strategy_config(config) == expected
        assert strategy_config_sha256(config) == digest
        assert (
            ReleaseManifest.from_json(
                manifest(strategy_config=config).to_json()
            ).strategy_config
            == config
        )
    assert strategy_config_sha256(
        MovingAverageCrossoverConfig(5, 20, Decimal("1.00"))
    ) == strategy_config_sha256(MovingAverageCrossoverConfig(5, 20, Decimal("1")))


@pytest.mark.parametrize("quantity", ["1.00", "0", "NaN", "Infinity", "-1e0", 1, True])
def test_noncanonical_or_invalid_config_quantity(quantity):
    raw = json.loads(manifest().to_json())
    raw["strategy_config"]["desired_quantity"] = quantity
    with pytest.raises(ValueError):
        ReleaseManifest.from_json(json.dumps(raw))


def test_scheduler_projection_exact_action_without_access(monkeypatch):
    original = manifest()

    def deny(*args, **kwargs):
        pytest.fail("filesystem or native access attempted")

    monkeypatch.setattr(builtins, "open", deny)
    for method in (
        "open",
        "read_bytes",
        "read_text",
        "write_bytes",
        "write_text",
        "mkdir",
        "exists",
        "resolve",
    ):
        monkeypatch.setattr(Path, method, deny)
    action = project_scheduler_action(ReleaseManifest.from_json(original.to_json()))
    expected = r"F:\AITradingBot\releases" + "\\" + original.release_id
    assert (
        action.executable == PRODUCTION_PYTHON == r"F:\AITradingBot\runtime\python.exe"
    )
    assert action.working_directory == expected
    assert action.arguments == (
        "-I",
        "-S",
        "-B",
        expected + r"\scripts\run_arch133_supervised_release_review_paper.py",
    )
    assert project_scheduler_action(original, root=expected) == action
    assert validate_release_root(expected, original.release_id) == expected
    assert DURABLE_DATA_ROOT not in action.working_directory
    assert not any(
        hasattr(action, name)
        for name in (
            "execute",
            "install",
            "rebind",
            "update",
            "hot_reload",
            "task_path",
        )
    )


@pytest.mark.parametrize(
    "root",
    [
        r"F:\AITradingBot\Arch133",
        r"C:\releases",
        r"F:\AITradingBot\releases",
        r"F:\AITradingBot\releases\..\Arch133",
        r"\\?\F:\AITradingBot\releases",
        "",
        1,
    ],
)
def test_arbitrary_roots_rejected(root):
    with pytest.raises(ValueError):
        project_scheduler_action(manifest(), root=root)


def test_root_aliases_and_wrong_release_rejected():
    original = manifest()
    root = release_root(original.release_id)
    for bad in (
        root.lower(),
        root.replace("\\", "/"),
        root + "\\",
        root + "\\..",
        root + ".",
        release_root(manifest(source_head="f" * 40).release_id),
    ):
        with pytest.raises(ValueError):
            project_scheduler_action(original, root=bad)
    for bad in (
        "../escape",
        "release-" + "a" * 32,
        original.release_id.upper(),
        original.release_id + "/escape",
        None,
    ):
        with pytest.raises(ValueError):
            release_root(bad)


def test_source_only_registration_profiles_and_preflight_execute_refusal(
    tmp_path, monkeypatch
):
    spec = runner._checkpoint_specs()[NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-supervised-release-foundation"
    assert runner.ACTIVE_CI_CHECKPOINTS.count(NAME) == 1
    assert runner._supervised_release_authority_check(ROOT) == ()
    inventory = certification.discover_inventory(ROOT)
    module = "tests/review_paper/test_supervised_release_foundation.py"
    for profile in ("full", "robinhood", "exhaustive"):
        assert module in certification.select_inventory(inventory, profile)
    assert module not in certification.select_inventory(inventory, "legacy")
    monkeypatch.setattr(runner, "_git_state", lambda *a: pytest.fail("host accessed"))
    for function in (runner.preflight_checkpoint, runner.execute_checkpoint):
        with pytest.raises(RuntimeError):
            function(spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence")


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: None},
        {"execute": lambda: None},
        {"remote_head_env": "INJECTED"},
        {"remote_branch": "wrong"},
        {"tests": ()},
        {"ruff_paths": ()},
    ],
)
def test_registration_drift_fails_closed(monkeypatch, change):
    specs = runner._checkpoint_specs()
    specs[NAME] = replace(specs[NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._supervised_release_authority_check(ROOT)


def test_pure_module_has_no_native_scheduler_write_or_reload_imports():
    source = ROOT / "src/trading_bot/supervised_release/model.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    allowed = {
        "__future__",
        "hashlib",
        "json",
        "re",
        "dataclasses",
        "decimal",
        "pathlib",
        "uuid",
        "trading_bot.strategies",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name in allowed for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module in allowed
            if node.module == "pathlib":
                assert [alias.name for alias in node.names] == ["PureWindowsPath"]
        if isinstance(node, ast.Call):
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else getattr(node.func, "attr", "")
            )
            assert name not in {
                "open",
                "exec",
                "eval",
                "compile",
                "__import__",
                "reload",
                "read_text",
                "read_bytes",
                "write_text",
                "write_bytes",
                "mkdir",
                "resolve",
                "exists",
                "run",
                "Popen",
                "system",
            }


@pytest.mark.parametrize("mutation", ["missing", "native_import", "write", "reload"])
def test_source_capability_drift_fails_closed(tmp_path, mutation):
    for relative in runner.SUPERVISED_RELEASE_SOURCES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (ROOT / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    workflow = tmp_path / ".github/workflows/checkpoint-source-gates.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        (ROOT / ".github/workflows/checkpoint-source-gates.yml").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    assert runner._supervised_release_authority_check(tmp_path) == ()
    target = tmp_path / runner.SUPERVISED_RELEASE_SOURCES[1]
    if mutation == "missing":
        target.unlink()
    else:
        payload = {
            "native_import": "import ctypes",
            "write": "open('fake', 'w')",
            "reload": "reload(fake)",
        }[mutation]
        target.write_text(
            target.read_text(encoding="utf-8") + "\n" + payload + "\n", encoding="utf-8"
        )
    assert runner._supervised_release_authority_check(tmp_path)


def test_actual_import_and_projection_no_production_scratch_native_or_write_access():
    # A fresh isolated interpreter also guards the existing strategy import closure.
    probe = """
import os
import sys
sys.path.insert(0, SOURCE)
def audit(event, args):
    if event.startswith(('ctypes.', 'socket.', 'winreg.', 'subprocess.')):
        raise AssertionError('native/provider/process access')
    if event == 'open':
        flags = args[2]
        if isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            raise AssertionError('write access')
    events = {'open', 'os.listdir', 'os.scandir', 'os.mkdir', 'os.remove', 'os.rename'}
    if event in events:
        for arg in args:
            if isinstance(arg, str):
                path = arg.replace(chr(92), '/').casefold()
                protected = path.startswith('f:/aitradingbot')
                scratch = any(x in path for x in ('unattended-133y', 'unattended-133z'))
                if protected or scratch:
                    raise AssertionError('production/scratch access')
    if event in {'os.mkdir', 'os.remove', 'os.rename'}:
        raise AssertionError('filesystem mutation')
sys.addaudithook(audit)
from decimal import Decimal
from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.supervised_release import *
manifest = ReleaseManifest(
    'a'*40, 'b'*40, '3.14.3', 'c'*64, LAUNCHER_RELATIVE_PATH, 'd'*64,
    (ReleaseInventoryEntry(LAUNCHER_RELATIVE_PATH, 'd'*64),),
    STRATEGY_ID, STRATEGY_VERSION, MovingAverageCrossoverConfig(5, 20, Decimal('1')),
    'reviewed-policy', '1.0.0', 'e'*64,
)
assert ReleaseManifest.from_json(manifest.to_json()) == manifest
assert project_scheduler_action(manifest).arguments[0:3] == ('-I', '-S', '-B')
effectful = (
    'trading_bot.review_paper', 'trading_bot.arch133_', 'trading_bot.robinhood'
)
assert not any(name.startswith(effectful) for name in sys.modules)
print('PURE_RELEASE_PASS')
"""
    probe = "SOURCE = " + repr(str(ROOT / "src")) + "\n" + probe
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-"],
        input=probe,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PURE_RELEASE_PASS"
