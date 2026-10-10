"""133-AE immutable runtime-host admission; fake observations only."""

import ast
import ctypes
import hashlib
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_supervised_release_installation import FAKE_PYTHON, FakeNative, accepted

from scripts import checkpoint_runner as runner
from scripts import run_test_certification as certification
from trading_bot.arch133_acl.read_only import (
    ADMINISTRATORS_SID,
    SYSTEM_SID,
    TRADING_SID,
)
from trading_bot.supervised_release import observer
from trading_bot.supervised_release import runtime_admission as subject
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.installation_contract import PYTHON_SHA256
from trading_bot.supervised_release.model import (
    LAUNCHER_RELATIVE_PATH,
    PRODUCTION_PYTHON,
    project_scheduler_action,
    release_root,
)

ROOT = Path(__file__).resolve().parents[2]
NAME = "arch133-robinhood-supervised-runtime-host-admission"


class FakeRuntime:
    def __init__(self, process, substrate):
        self.process = process
        self.substrate = substrate
        self.process_reads = 0
        self.substrate_reads = 0
        self.process_hook = None
        self.substrate_hook = None

    def observe_process(self):
        self.process_reads += 1
        if self.process_hook:
            self.process_hook(self)
        return self.process

    def observe_substrate(self):
        self.substrate_reads += 1
        if self.substrate_hook:
            self.substrate_hook(self)
        return self.substrate


def _row(path, kind, index, *, owner=SYSTEM_SID):
    return subject.RuntimeObjectObservation(
        path=path,
        final_path=path,
        kind=kind,
        owner_sid=owner,
        filesystem="NTFS",
        local=True,
        reparse=False,
        identity=(7, index),
        links=1,
        trading_mutation_granted=0,
        rename_replace_denied=True,
    )


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: pytest.fail("native"))
    release = accepted()
    native = FakeNative(release)
    native.seed(release)
    monkeypatch.setattr(
        observer,
        "hashlib",
        SimpleNamespace(
            sha256=lambda data: (
                SimpleNamespace(hexdigest=lambda: PYTHON_SHA256)
                if data == FAKE_PYTHON
                else hashlib.sha256(data)
            )
        ),
    )
    binding = RuntimeBinding(release)
    installed = observer.observe_installed_release(release, binding, native=native)
    native.events.clear()
    native.read_scopes = 0

    root = release_root(release.manifest.release_id)
    source = root + r"\src"
    launcher = root + "\\" + LAUNCHER_RELATIVE_PATH.replace("/", "\\")
    dependency = subject.SITE_PACKAGES + r"\tzdata\__init__.py"
    objects = (
        _row(
            subject.RUNTIME_PARENT,
            subject.RuntimeObjectKind.DIRECTORY,
            10,
            owner=ADMINISTRATORS_SID,
        ),
        _row(subject.RUNTIME_ROOT, subject.RuntimeObjectKind.DIRECTORY, 11),
        _row(PRODUCTION_PYTHON, subject.RuntimeObjectKind.FILE, 12),
        _row(subject.LIB_ROOT, subject.RuntimeObjectKind.DIRECTORY, 13),
        _row(subject.SITE_PACKAGES, subject.RuntimeObjectKind.DIRECTORY, 14),
        _row(
            subject.SITE_PACKAGES + r"\tzdata",
            subject.RuntimeObjectKind.DIRECTORY,
            15,
        ),
        _row(dependency, subject.RuntimeObjectKind.FILE, 16),
    )
    substrate = subject.RuntimeSubstrateObservation(
        runtime_parent=subject.RUNTIME_PARENT,
        runtime_root=subject.RUNTIME_ROOT,
        site_packages=subject.SITE_PACKAGES,
        trading_sid=TRADING_SID,
        trading_non_admin=True,
        trading_elevated=False,
        objects=objects,
        inventory_complete=True,
        native_no_follow=True,
        pinned_and_rechecked=True,
        configuration_absent=subject.CONFIGURATION_PATHS,
        configuration_scan_complete=True,
        runtime_search_roots=(subject.LIB_ROOT, subject.RUNTIME_ROOT),
        absent_search_roots=(subject.DLLS_ROOT, subject.ZIP_PATH),
        dependencies=(
            subject.DependencyObservation("sys", "builtin", "builtin", None),
            subject.DependencyObservation("tzdata", "runtime", dependency, dependency),
        ),
        dependencies_complete=True,
        before_fingerprint="a" * 64,
        after_fingerprint="a" * 64,
    )
    process = subject.ProcessObservation(
        platform="win32",
        executable=PRODUCTION_PYTHON,
        python_version="3.14.3",
        isolated=True,
        no_site=True,
        dont_write_bytecode=True,
        argv=(launcher,),
        working_directory=root,
        pycache_prefix=subject.NO_PYCACHE,
        pycache_absent=True,
        sys_path=(source, subject.SITE_PACKAGES, *substrate.runtime_search_roots),
        project_module_origins=(
            subject.ProjectModuleOrigin(
                "trading_bot", source + r"\trading_bot\__init__.py"
            ),
            subject.ProjectModuleOrigin(
                "trading_bot.nested.model",
                source + r"\trading_bot\nested\model.py",
            ),
        ),
        project_modules_complete=True,
        site_main_called=False,
        pth_processed=False,
        sitecustomize_loaded=False,
        usercustomize_loaded=False,
    )
    return SimpleNamespace(
        release=release,
        binding=binding,
        installed=installed,
        native=native,
        runtime=FakeRuntime(process, substrate),
        root=root,
        source=source,
        launcher=launcher,
    )


def admit(f):
    return subject.admit_runtime_host(
        f.release,
        f.binding,
        f.installed,
        image_observer=f.native,
        runtime_observer=f.runtime,
    )


def test_exact_immutable_runtime_admission_and_unproven_dependency_closure(setup):
    result = admit(setup)
    assert result.status is subject.RuntimeStatus.VERIFIED
    assert result.reason is subject.RuntimeReason.VERIFIED
    assert result.evidence.release_id == setup.release.manifest.release_id
    assert result.evidence.release_root == setup.root
    assert result.evidence.source_root == setup.source
    assert result.evidence.launcher == setup.launcher
    assert result.evidence.site_packages == subject.SITE_PACKAGES
    assert result.evidence.dependency_closure == "UNPROVEN"
    assert setup.native.read_scopes == 2
    assert setup.runtime.process_reads == setup.runtime.substrate_reads == 2
    assert not any(
        event[0] in {"write", "publish", "create_directory"}
        for event in setup.native.events
    )


def test_future_scheduler_projection_uses_no_site_and_new_supervised_launcher(setup):
    action = project_scheduler_action(setup.release.manifest)
    assert action.executable == PRODUCTION_PYTHON
    assert action.working_directory == setup.root
    assert action.arguments == ("-I", "-S", "-B", setup.launcher)
    assert setup.release.manifest.launcher_relative_path == (
        "scripts/run_arch133_supervised_release_review_paper.py"
    )


def test_new_launcher_bootstraps_only_release_source_and_fixed_site_packages():
    path = ROOT / "scripts/run_arch133_supervised_release_review_paper.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imports == {"sys"}
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "pathlib"
        and [alias.name for alias in node.names] == ["Path"]
        for node in tree.body
    )
    assert "site.main" not in source and "import site" not in source
    assert "sitecustomize" in source and "usercustomize" in source
    assert r"F:\AITradingBot\runtime\Lib\site-packages" in source
    assert "sys.path[:0] = [_source, _site]" in source
    assert "sys.flags.no_site" in source and "sys.flags.isolated" in source


@pytest.mark.parametrize(
    "field,value",
    [
        ("platform", "linux"),
        ("executable", r"C:\Python\python.exe"),
        ("python_version", "3.14.2"),
        ("isolated", False),
        ("no_site", False),
        ("dont_write_bytecode", False),
        ("argv", ("wrong.py",)),
        ("working_directory", r"F:\AI\worktrees\wrong"),
        ("pycache_prefix", r"F:\wrong"),
        ("pycache_absent", False),
        ("project_modules_complete", False),
        ("site_main_called", True),
        ("pth_processed", True),
        ("sitecustomize_loaded", True),
        ("usercustomize_loaded", True),
    ],
)
def test_process_fact_drift_blocks(setup, field, value):
    setup.runtime.process = replace(setup.runtime.process, **{field: value})
    result = admit(setup)
    assert result.status is subject.RuntimeStatus.BLOCKED
    assert result.reason is subject.RuntimeReason.PROCESS


@pytest.mark.parametrize(
    "path",
    [
        r"F:\AI\worktrees\ai-trading-bot\src\trading_bot\__init__.py",
        r"C:\Users\John\site-packages\trading_bot\__init__.py",
        r"F:\AITradingBot\releases\release-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        r"\src\trading_bot\__init__.py",
    ],
)
def test_project_module_origin_outside_exact_release_blocks(setup, path):
    origins = (
        subject.ProjectModuleOrigin("trading_bot", path),
        *setup.runtime.process.project_module_origins[1:],
    )
    setup.runtime.process = replace(
        setup.runtime.process, project_module_origins=origins
    )
    assert admit(setup).status is subject.RuntimeStatus.BLOCKED


def test_project_module_must_be_in_verified_release_inventory(setup):
    path = setup.source + r"\trading_bot\not-in-release.py"
    setup.runtime.process = replace(
        setup.runtime.process,
        project_module_origins=(
            subject.ProjectModuleOrigin("trading_bot.not_in_release", path),
        ),
    )
    assert admit(setup).status is subject.RuntimeStatus.BLOCKED


def test_current_directory_or_duplicate_search_authority_blocks(setup):
    setup.runtime.process = replace(
        setup.runtime.process,
        sys_path=(
            setup.source,
            subject.SITE_PACKAGES,
            "",
            *setup.runtime.substrate.runtime_search_roots,
        ),
    )
    assert admit(setup).status is subject.RuntimeStatus.BLOCKED
    setup.runtime.process = replace(
        setup.runtime.process,
        sys_path=(
            setup.source,
            subject.SITE_PACKAGES,
            subject.LIB_ROOT,
            subject.LIB_ROOT.lower(),
        ),
    )
    assert admit(setup).status is subject.RuntimeStatus.BLOCKED


@pytest.mark.parametrize(
    "field,value",
    [
        ("runtime_root", r"F:\other"),
        ("site_packages", r"F:\other\site-packages"),
        ("trading_sid", "S-1-5-21-wrong"),
        ("trading_non_admin", False),
        ("trading_elevated", True),
        ("inventory_complete", False),
        ("native_no_follow", False),
        ("pinned_and_rechecked", False),
        ("configuration_scan_complete", False),
        ("dependencies_complete", False),
        ("after_fingerprint", "b" * 64),
    ],
)
def test_substrate_fact_drift_blocks(setup, field, value):
    setup.runtime.substrate = replace(setup.runtime.substrate, **{field: value})
    result = admit(setup)
    assert result.status is subject.RuntimeStatus.BLOCKED
    assert result.reason is subject.RuntimeReason.SUBSTRATE


@pytest.mark.parametrize(
    "change", ["owner", "reparse", "mutation", "bool_mutation", "rename", "alias", "kind"]
)
def test_substrate_object_security_and_identity_blocks(setup, change):
    rows = list(setup.runtime.substrate.objects)
    row = rows[1]
    if change == "owner":
        row = replace(row, owner_sid=TRADING_SID)
    elif change == "reparse":
        row = replace(row, reparse=True)
    elif change == "mutation":
        row = replace(row, trading_mutation_granted=1)
    elif change == "bool_mutation":
        row = replace(row, trading_mutation_granted=False)
    elif change == "rename":
        row = replace(row, rename_replace_denied=False)
    elif change == "kind":
        row = replace(row, kind="directory")
    else:
        row = replace(row, identity=rows[0].identity)
    rows[1] = row
    setup.runtime.substrate = replace(setup.runtime.substrate, objects=tuple(rows))
    assert admit(setup).status is subject.RuntimeStatus.BLOCKED


def test_absent_search_root_cannot_also_be_present(setup):
    rows = (
        *setup.runtime.substrate.objects,
        _row(subject.DLLS_ROOT, subject.RuntimeObjectKind.DIRECTORY, 99),
    )
    setup.runtime.substrate = replace(setup.runtime.substrate, objects=rows)
    assert admit(setup).status is subject.RuntimeStatus.BLOCKED


@pytest.mark.parametrize("kind", ["escape", "missing_final", "duplicate", "incomplete"])
def test_dependency_origin_coverage_blocks(setup, kind):
    deps = list(setup.runtime.substrate.dependencies)
    dep = deps[1]
    if kind == "escape":
        dep = replace(
            dep,
            origin=r"C:\Users\John\site-packages\tzdata\__init__.py",
            final_path=r"C:\Users\John\site-packages\tzdata\__init__.py",
        )
    elif kind == "missing_final":
        dep = replace(dep, final_path=subject.RUNTIME_ROOT + r"\missing.py")
    elif kind == "duplicate":
        dep = replace(dep, name="sys")
    else:
        setup.runtime.substrate = replace(
            setup.runtime.substrate, dependencies_complete=False
        )
        assert admit(setup).status is subject.RuntimeStatus.BLOCKED
        return
    deps[1] = dep
    setup.runtime.substrate = replace(setup.runtime.substrate, dependencies=tuple(deps))
    assert admit(setup).status is subject.RuntimeStatus.BLOCKED


@pytest.mark.parametrize("source", ["process", "substrate", "image"])
def test_repeated_observation_drift_blocks(setup, source):
    if source == "process":

        def hook(runtime):
            if runtime.process_reads == 2:
                runtime.process = replace(runtime.process, pycache_absent=False)

        setup.runtime.process_hook = hook
    elif source == "substrate":

        def hook(runtime):
            if runtime.substrate_reads == 2:
                runtime.substrate = replace(
                    runtime.substrate, after_fingerprint="b" * 64
                )

        setup.runtime.substrate_hook = hook
    else:

        def hook(native, count):
            if count == 2:
                path = native.paths.final
                native.nodes[path] = replace(native.nodes[path], identity=(7, 9999))

        setup.native.hook = hook
    result = admit(setup)
    assert result.status is subject.RuntimeStatus.BLOCKED
    assert result.reason is subject.RuntimeReason.DRIFT


@pytest.mark.parametrize(
    "field",
    [
        "release_id",
        "manifest_sha256",
        "binding_sha256",
        "parent_identity",
        "image_identity",
        "python_identity",
        "python_sha256",
        "python_version",
        "dependency_closure",
    ],
)
def test_cached_installed_evidence_cannot_establish_runtime_authority(setup, field):
    value = getattr(setup.installed, field)
    setup.installed = replace(
        setup.installed,
        **{field: (7, 9999) if isinstance(value, tuple) else "wrong"},
    )
    result = admit(setup)
    assert result.status is subject.RuntimeStatus.BLOCKED
    assert result.reason is subject.RuntimeReason.INPUT_OR_IMAGE
    assert setup.runtime.process_reads == setup.runtime.substrate_reads == 0


def test_binding_mismatch_blocks_before_runtime_observation(setup):
    other = accepted()
    object.__setattr__(other, "expected_source_head", "c" * 40)
    setup.binding = RuntimeBinding(other)
    result = admit(setup)
    assert result.status is subject.RuntimeStatus.BLOCKED
    assert setup.runtime.process_reads == setup.runtime.substrate_reads == 0


def test_no_implicit_runtime_or_native_observer(setup):
    assert (
        subject.admit_runtime_host(
            setup.release,
            setup.binding,
            setup.installed,
            image_observer=None,
            runtime_observer=setup.runtime,
        ).status
        is subject.RuntimeStatus.BLOCKED
    )
    assert (
        subject.admit_runtime_host(
            setup.release,
            setup.binding,
            setup.installed,
            image_observer=setup.native,
            runtime_observer=None,
        ).status
        is subject.RuntimeStatus.BLOCKED
    )


@pytest.mark.parametrize(
    "field",
    [
        "release_root",
        "source_root",
        "launcher",
        "runtime_root",
        "site_packages",
        "branch",
        "worktree",
        "environment",
        "cwd",
    ],
)
def test_no_caller_selected_runtime_authority(setup, field):
    with pytest.raises(TypeError):
        subject.admit_runtime_host(
            setup.release,
            setup.binding,
            setup.installed,
            image_observer=setup.native,
            runtime_observer=setup.runtime,
            **{field: "caller-choice"},
        )


def test_source_registration_profiles_and_authority():
    spec = runner._checkpoint_specs()[NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-supervised-runtime-host-admission"
    assert runner.ACTIVE_CI_CHECKPOINTS[0] == NAME
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 54
    assert spec.authority_check(ROOT) == ()
    inventory = certification.discover_inventory(ROOT)
    profiles = {
        name: certification.select_inventory(inventory, name)
        for name in ("full", "robinhood", "legacy", "exhaustive")
    }
    assert {name: len(modules) for name, modules in profiles.items()} == {
        "full": 154,
        "robinhood": 81,
        "legacy": 205,
        "exhaustive": 359,
    }


def test_runtime_admission_import_closure_is_inert():
    code = """
import ctypes, sys
def forbidden(*args, **kwargs):
    raise AssertionError('native access')
ctypes.WinDLL = forbidden
import trading_bot.supervised_release.runtime_admission
assert 'trading_bot.supervised_release.native_read' not in sys.modules
assert 'trading_bot.supervised_release.native_write' not in sys.modules
assert 'trading_bot.supervised_release.installer' not in sys.modules
assert not any('arch133_scheduler_installation' in name for name in sys.modules)
assert not any('robinhood_mcp' in name for name in sys.modules)
assert not any(name.endswith('unattended_execution') for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-B", "-"],
        input=code,
        text=True,
        capture_output=True,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert result.returncode == 0, result.stderr


def test_runtime_read_seam_has_no_effect_capabilities():
    assert {
        name for name in subject.RuntimeObserver.__dict__ if not name.startswith("_")
    } == {"observe_process", "observe_substrate"}
    tree = ast.parse(Path(subject.__file__).read_text(encoding="utf-8-sig"))
    forbidden = {
        "run",
        "Popen",
        "WinDLL",
        "open",
        "unlink",
        "delete",
        "enable",
        "start",
        "credential",
        "provider",
        "publish",
        "install_release",
        "sleep",
    }
    calls = {
        getattr(node.func, "attr", getattr(node.func, "id", ""))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert not calls & forbidden
