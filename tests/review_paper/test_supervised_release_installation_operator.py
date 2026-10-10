"""133-AG source tests: disposable Git, fake host and native installation only.

Never invoke registered host preflight/execute callbacks or inspect production.
"""

import ast
import hashlib
import inspect
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_supervised_release_installation import (
    FAKE_PYTHON,
    FakeNative,
    accepted,
    effect_events,
)

from scripts import checkpoint_runner as runner
from scripts import run_test_certification as certification
from trading_bot.supervised_release import installation_operator as subject
from trading_bot.supervised_release import installer, observer
from trading_bot.supervised_release import release_parent_provisioning as parent_subject
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.installation_contract import (
    IMAGE_ACES,
    PYTHON_SHA256,
    PYTHON_VERSION,
    InstallDisposition,
    InstallReason,
    InstallResult,
    InstallStatus,
)
from trading_bot.supervised_release.model import (
    LAUNCHER_RELATIVE_PATH,
    PRODUCTION_PYTHON,
    RELEASES_BASE,
)

ROOT = Path(__file__).resolve().parents[2]
NAME = "arch133-robinhood-supervised-release-installation-operator"


def git(root, *arguments):
    return (
        subprocess.run(
            ["git", "-C", str(root), *arguments], check=True, capture_output=True
        )
        .stdout.decode()
        .strip()
    )


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    material = {
        "pyproject.toml": b"[project]\nname='inert'\n",
        LAUNCHER_RELATIVE_PATH: b"# inert launcher\n",
        "src/trading_bot/__init__.py": b"# inert source\n",
    }
    for name, data in material.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    git(tmp_path, "init")
    git(tmp_path, "config", "core.autocrlf", "false")
    git(tmp_path, "config", "user.name", "Source Test")
    git(tmp_path, "config", "user.email", "source-test@example.invalid")
    git(tmp_path, "remote", "add", "origin", subject.ORIGIN)
    git(tmp_path, "checkout", "-b", subject.BRANCH)
    git(tmp_path, "add", "--", *material)
    git(tmp_path, "commit", "-m", "inert source")
    monkeypatch.setattr(subject, "WORKTREE", tmp_path)
    monkeypatch.setattr(subject, "BASE_HEAD", git(tmp_path, "rev-parse", "HEAD"))
    return tmp_path, material


def test_complete_production_declaration_and_replay(checkout, monkeypatch):
    root, material = checkout
    calls = []
    collect = subject.collect_release_bundle
    replay = subject.replay_inputs

    def recording(checkout, *, declaration):
        calls.append(declaration)
        return collect(checkout, declaration=declaration)

    monkeypatch.setattr(subject, "collect_release_bundle", recording)
    monkeypatch.setattr(
        subject,
        "replay_inputs",
        lambda *args: (calls.append("replay"), replay(*args))[1],
    )
    release, binding = subject._derive_release()
    declaration = calls[0]
    assert release.manifest == declaration
    assert declaration.source_head == git(root, "rev-parse", "HEAD")
    assert declaration.source_tree == git(root, "rev-parse", "HEAD^{tree}")
    assert declaration.production_python_version == "3.14.3"
    assert declaration.production_python_sha256 == PYTHON_SHA256
    assert (
        declaration.launcher_sha256
        == hashlib.sha256(material[LAUNCHER_RELATIVE_PATH]).hexdigest()
    )
    assert declaration.strategy_id == "MovingAverageCrossoverStrategy"
    assert declaration.strategy_version == "1.0.0"
    assert (
        declaration.strategy_config.short_window,
        declaration.strategy_config.long_window,
        str(declaration.strategy_config.desired_quantity),
    ) == (5, 20, "1")
    assert declaration.risk_policy_id == "arch133-long-only-review-paper"
    assert declaration.risk_policy_version == "1.0.0"
    assert (
        declaration.risk_policy_sha256
        == hashlib.sha256(subject.RISK_POLICY_MATERIAL).hexdigest()
    )
    assert tuple(
        entry.relative_path for entry in declaration.source_inventory
    ) == tuple(sorted(material))
    assert binding.verified_release == release and calls[1] == "replay"
    assert (
        RuntimeBinding.from_json(binding.to_json(), verified_release=release) == binding
    )
    assert git(root, "status", "--porcelain") == ""


@pytest.mark.parametrize(
    "phase",
    ["branch", "origin", "dirty", "head_drift", "tree_drift", "launcher_dirty", "link"],
)
def test_changed_source_fails_closed(checkout, monkeypatch, phase):
    root, material = checkout
    if phase == "branch":
        git(root, "checkout", "-b", "feature/wrong")
    elif phase == "origin":
        git(root, "remote", "set-url", "origin", "https://example.invalid/wrong.git")
    elif phase in {"dirty", "launcher_dirty"}:
        (
            root / (LAUNCHER_RELATIVE_PATH if phase == "launcher_dirty" else "extra.py")
        ).write_text("# changed")
    elif phase == "link":
        # Fake Windows reparse facts; never create a real link or traverse one.
        original = Path.lstat

        def lstat(path):
            facts = original(path)
            if path == root / LAUNCHER_RELATIVE_PATH:
                return SimpleNamespace(
                    st_mode=facts.st_mode,
                    st_file_attributes=0x400,
                    st_size=facts.st_size,
                )
            return facts

        monkeypatch.setattr(Path, "lstat", lstat)
    else:
        original = subject._git
        count = 0

        def drift(*args):
            nonlocal count
            value = original(*args)
            target = ("rev-parse", "HEAD" if phase == "head_drift" else "HEAD^{tree}")
            if args == target:
                count += 1
                if count > 1:
                    return "f" * 40
            return value

        monkeypatch.setattr(subject, "_git", drift)
    with pytest.raises(ValueError):
        subject._derive_release()


@pytest.mark.parametrize(
    "field",
    ["expected_source_head", "expected_source_tree", "expected_manifest_sha256"],
)
def test_collected_release_tamper_rejected(checkout, monkeypatch, field):
    collect = subject.collect_release_bundle

    def tamper(*args, **kwargs):
        release = collect(*args, **kwargs)
        return replace(
            release, **{field: "f" * (64 if field.endswith("sha256") else 40)}
        )

    monkeypatch.setattr(subject, "collect_release_bundle", tamper)
    with pytest.raises(ValueError):
        subject._derive_release()


@pytest.fixture
def fake(monkeypatch):
    release = accepted()
    binding = RuntimeBinding(release)
    native = FakeNative(release)
    hashes = SimpleNamespace(
        sha256=lambda data: (
            SimpleNamespace(hexdigest=lambda: PYTHON_SHA256)
            if data == FAKE_PYTHON
            else hashlib.sha256(data)
        )
    )
    monkeypatch.setattr(subject, "hashlib", hashes)
    monkeypatch.setattr(observer, "hashlib", hashes)
    monkeypatch.setattr(subject, "_derive_release", lambda: (release, binding))
    monkeypatch.setattr(
        subject, "_administrator_host", native.require_administrator_host
    )
    monkeypatch.setattr(subject, "WindowsObserver", lambda: native)
    monkeypatch.setattr(
        installer,
        "install_release",
        lambda release, binding: installer_engine(release, binding, native=native),
    )
    return release, binding, native


installer_engine = installer.install_release


def test_readonly_preflight_ready_and_no_mutation(fake):
    release, binding, native = fake
    before = (dict(native.nodes), dict(native.data))
    result = subject._preflight()
    assert result["status"] == "PASS" and result["primary"]["status"] == "READY"
    assert result["primary"]["release_id"] == release.manifest.release_id
    assert result["primary"]["binding_sha256"] == binding.sha256
    assert result["primary"]["final"] == native.paths.final
    assert result["primary"]["staging"] == native.paths.staging
    assert result["primary"]["python_version"] == PYTHON_VERSION
    assert not effect_events(native) and (native.nodes, native.data) == before
    assert "install_open" not in {phase for phase, _ in native.events}


@pytest.mark.parametrize(
    "state",
    [
        "final",
        "conflict",
        "staging",
        "both",
        "alias",
        "orphan",
        "parent_acl",
        "python_hash",
        "python_version",
        "runtime_acl",
        "host",
    ],
)
def test_preflight_existing_namespace_and_host_admission(fake, state):
    release, binding, native = fake
    if state in {"final", "conflict", "both"}:
        native.seed(release)
    if state == "conflict":
        native.data[native.paths.child(native.paths.final, LAUNCHER_RELATIVE_PATH)] = (
            b"changed"
        )
    if state in {"staging", "both"}:
        native.add(native.paths.staging, directory=True)
    if state == "alias":
        native.add(
            RELEASES_BASE + "\\" + native.paths.release_id.upper(), directory=True
        )
    if state == "orphan":
        native.add(
            RELEASES_BASE + "\\release-" + "f" * 32 + ".installing", directory=True
        )
    if state == "parent_acl":
        native.nodes[RELEASES_BASE] = replace(native.nodes[RELEASES_BASE], aces=())
    if state == "runtime_acl":
        native.nodes[PRODUCTION_PYTHON] = replace(
            native.nodes[PRODUCTION_PYTHON],
            aces=(*IMAGE_ACES, ("caller", 0x1F01FF, 0, 0)),
        )
    if state == "python_hash":
        native.data[PRODUCTION_PYTHON] = b"wrong executable"
    if state == "python_version":
        native.version = "3.14.4"
    if state == "host":
        native.fail = "host"
    result = subject._preflight()
    assert result["status"] == ("PASS" if state == "final" else "BLOCKED")
    if state == "final":
        assert result["primary"]["status"] == "ALREADY_INSTALLED_VERIFIED"
    else:
        assert result["primary"]["disposition"] == "NO_INSTALLATION_EFFECT"
    assert not effect_events(native)
    assert "private unrelated" not in json.dumps(result)


@pytest.mark.parametrize(
    "phase",
    [
        None,
        "create_directory",
        "write",
        "publish",
        "published",
        "final_observer",
        "escaped",
        "bad_ack",
    ],
)
def test_execute_once_consumes_before_engine_and_preserves_ambiguity(
    fake, monkeypatch, phase
):
    release, binding, native = fake
    events = []
    calls = []
    if phase == "final_observer":
        native.hook = lambda host, scope: (
            (_ for _ in ()).throw(RuntimeError("private observer"))
            if scope == 3
            else None
        )
    elif phase not in {None, "escaped", "bad_ack"}:
        native.fail = phase

    def install(release, binding):
        assert events == ["consumed"] and not effect_events(native)
        calls.append((release, binding))
        if phase == "escaped":
            raise RuntimeError("private native capability")
        if phase == "bad_ack":
            return InstallResult(
                InstallStatus.INSTALLED_VERIFIED,
                InstallDisposition.VERIFIED,
                InstallReason.VERIFIED,
            )
        return installer_engine(release, binding, native=native)

    monkeypatch.setattr(installer, "install_release", install)
    result = subject._execute_once(lambda: events.append("consumed"))
    assert len(calls) == 1 and events == ["consumed"]
    assert result["status"] == ("PASS" if phase is None else "INDETERMINATE")
    if phase is not None:
        assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"
        assert (
            result["primary"]["disposition"]
            == "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY"
        )
    assert "private" not in json.dumps(result)
    assert not any(
        event[0] in {"cleanup", "retry", "rollback", "remove"}
        for event in native.events
    )


def test_exact_existing_final_zero_mutation(fake):
    release, binding, native = fake
    native.seed(release)
    result = subject._execute_once(lambda: None)
    assert result["primary"]["status"] == "ALREADY_INSTALLED_VERIFIED"
    assert result["primary"]["manifest_sha256"] == release.expected_manifest_sha256
    assert result["primary"]["binding_sha256"] == binding.sha256
    assert not effect_events(native)
    assert set(result["primary"]) == {
        "status",
        "disposition",
        "reason",
        "release_id",
        "manifest_sha256",
        "binding_sha256",
        "parent_identity",
        "image_identity",
        "python_identity",
        "python_version",
        "python_sha256",
        "dependency_closure",
    }


def test_staging_blocks_before_latch_and_installer(fake):
    release, binding, native = fake
    native.add(native.paths.staging, directory=True)
    result = subject._execute_once(lambda: pytest.fail("attempt consumed"))
    assert result["status"] == "BLOCKED"
    assert result["primary"]["disposition"] == "NO_INSTALLATION_EFFECT"
    assert result["primary"]["reason"] == "STAGING_EXISTS"
    assert not effect_events(native)


def test_fixed_latch_survives_new_invocation_and_authorization(tmp_path, monkeypatch):
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": subject.BRANCH,
        "porcelain": "",
    }
    latch = tmp_path / "latch" / "attempt.json"
    monkeypatch.setattr(runner, "SUPERVISED_INSTALLATION_ATTEMPT", latch)
    monkeypatch.setattr(runner, "_installation_execution_admitted", True)
    monkeypatch.setattr(
        runner, "_installation_execution_source", (state["head"], state["tree"])
    )
    monkeypatch.setattr(runner, "_git_state", lambda root: state)
    monkeypatch.setattr(
        runner, "_supervised_installation_admission", lambda *args: None
    )
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *args: state["head"])
    runner._consume_supervised_installation_attempt()
    original = latch.read_bytes()
    monkeypatch.setenv(subject.AUTH_ENV, subject.AUTH_VALUE)
    monkeypatch.setenv(
        "AI_TRADING_BOT_CHECKPOINT_EVIDENCE_ROOT", str(tmp_path / "different")
    )
    with pytest.raises(FileExistsError):
        runner._consume_supervised_installation_attempt()
    assert latch.read_bytes() == original


@pytest.mark.parametrize("failure", ["flush", "source", "remote", "context"])
def test_latch_failure_never_grants_installation_authority(
    tmp_path, monkeypatch, failure
):
    state = {"head": "a" * 40, "tree": "b" * 40}
    latch = tmp_path / "attempt.json"
    monkeypatch.setattr(runner, "SUPERVISED_INSTALLATION_ATTEMPT", latch)
    monkeypatch.setattr(
        runner, "_installation_execution_admitted", failure != "context"
    )
    monkeypatch.setattr(
        runner,
        "_installation_execution_source",
        ("f" * 40 if failure == "source" else state["head"], state["tree"]),
    )
    monkeypatch.setattr(runner, "_git_state", lambda *args: state)
    monkeypatch.setattr(
        runner, "_supervised_installation_admission", lambda *args: None
    )
    monkeypatch.setattr(
        runner,
        "_remote_branch_head",
        lambda *args: "f" * 40 if failure == "remote" else state["head"],
    )
    if failure == "flush":
        monkeypatch.setattr(
            runner.os,
            "fsync",
            lambda *args: (_ for _ in ()).throw(OSError("fake flush failure")),
        )
    with pytest.raises((RuntimeError, OSError)):
        runner._consume_supervised_installation_attempt()
    assert latch.exists() is (failure == "flush")


@pytest.mark.parametrize("gate", ["dirty", "remote", "authorization", "consumed"])
def test_runner_interlocks_never_reach_registered_native_callback(
    tmp_path, monkeypatch, gate
):
    spec = runner._checkpoint_specs()[NAME]
    # Substitute the callback; no real registered host function is invoked.
    spec = replace(spec, execute=lambda: pytest.fail("callback reached"))
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: {NAME: spec})
    monkeypatch.setattr(
        runner, "_supervised_installation_admission", lambda *args: None
    )
    monkeypatch.setattr(
        runner,
        "_git_state",
        lambda *args: {
            "head": "a" * 40,
            "tree": "b" * 40,
            "branch": subject.BRANCH,
            "porcelain": "dirty" if gate == "dirty" else "",
        },
    )
    monkeypatch.setattr(
        runner,
        "_remote_branch_head",
        lambda *args: "b" * 40 if gate == "remote" else "a" * 40,
    )
    monkeypatch.setattr(
        runner, "SUPERVISED_INSTALLATION_ATTEMPT", tmp_path / "latch.json"
    )
    monkeypatch.setenv(
        subject.AUTH_ENV, "wrong" if gate == "authorization" else subject.AUTH_VALUE
    )
    if gate == "consumed":
        (tmp_path / "latch.json").write_text("incomplete consumed evidence")
    with pytest.raises(RuntimeError):
        runner.execute_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )
    assert not (tmp_path / "evidence").exists()


def test_latch_parent_alias_is_rejected(tmp_path, monkeypatch):
    latch = tmp_path / "attempt.json"
    monkeypatch.setattr(runner, "SUPERVISED_INSTALLATION_ATTEMPT", latch)
    original = Path.lstat

    def aliased(path):
        facts = original(path)
        if path == tmp_path:
            return SimpleNamespace(st_mode=facts.st_mode, st_file_attributes=0x400)
        return facts

    monkeypatch.setattr(Path, "lstat", aliased)
    with pytest.raises(RuntimeError, match="namespace rejected"):
        runner._supervised_installation_latch_consumed()
    assert not latch.exists()


def test_source_registration_pins_chaining_topology():
    spec = runner._checkpoint_specs()[NAME]
    assert spec.preflight is runner._supervised_installation_preflight
    assert spec.execute is runner._supervised_installation_execute
    assert spec.remote_branch == subject.BRANCH and spec.remote_head_env is None
    assert spec.authority_check(ROOT) == ()
    assert (
        runner.ACTIVE_CI_CHECKPOINTS[0] == NAME
        and len(runner.ACTIVE_CI_CHECKPOINTS) == 57
    )
    assert runner._batch_workflow_is_reviewed(
        (ROOT / ".github/workflows/checkpoint-source-gates.yml").read_text()
    )
    inventory = certification.discover_inventory(ROOT)
    assert {
        name: len(certification.select_inventory(inventory, name))
        for name in certification.PROFILES
    } == {"full": 156, "robinhood": 83, "legacy": 205, "exhaustive": 361}


@pytest.mark.parametrize(
    "gate", ["path", "branch", "origin", "ancestor", "dirty", "pins"]
)
def test_exact_runner_source_admission(tmp_path, monkeypatch, gate):
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": subject.BRANCH,
        "porcelain": "",
    }
    monkeypatch.setattr(subject, "WORKTREE", tmp_path)
    monkeypatch.setattr(runner, "_REPOSITORY_ROOT", tmp_path)

    def output(root, *args):
        if args == ("remote", "get-url", "origin"):
            return "wrong" if gate == "origin" else subject.ORIGIN
        return "f" * 40 if gate == "ancestor" else subject.BASE_HEAD

    monkeypatch.setattr(runner, "_git_output", output)
    monkeypatch.setattr(
        runner,
        "_supervised_installation_operator_authority_check",
        lambda *args: ("drift",) if gate == "pins" else (),
    )
    if gate == "branch":
        state["branch"] = "feature/caller"
    if gate == "dirty":
        state["porcelain"] = "changed index"
    with pytest.raises(RuntimeError, match="source authority rejected"):
        runner._supervised_installation_admission(
            tmp_path / "wrong" if gate == "path" else tmp_path, state
        )


def test_ag_runner_preflight_creates_no_files(tmp_path, monkeypatch, capsys):
    spec = runner._checkpoint_specs()[NAME]
    # Test runner transport with an inert callback, never a registered native call.
    spec = replace(
        spec, preflight=lambda: {"status": "PASS", "primary": {"status": "READY"}}
    )
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: {NAME: spec})
    monkeypatch.setattr(
        runner, "_supervised_installation_admission", lambda *args: None
    )
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": subject.BRANCH,
        "porcelain": "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda *args: state)
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *args: state["head"])
    before = tuple(tmp_path.iterdir())
    assert runner.preflight_checkpoint(
        spec, repo_root=tmp_path, evidence_root=tmp_path / "unused"
    ) == (True, None)
    assert tuple(tmp_path.iterdir()) == before
    assert "EVIDENCE=STDOUT" in capsys.readouterr().out


@pytest.mark.parametrize(
    "field,value",
    [
        ("preflight", None),
        ("execute", None),
        ("remote_branch", "feature/caller"),
        ("remote_head_env", "CALLER"),
        ("tests", ()),
        ("ruff_paths", ()),
    ],
)
def test_ag_registration_drift_fails_closed(monkeypatch, field, value):
    specs = runner._checkpoint_specs()
    specs[NAME] = replace(specs[NAME], **{field: value})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert (
        "installation operator registration drift"
        in runner._supervised_installation_operator_authority_check(ROOT)
    )


def test_operator_and_runner_authority_tamper_rejected(tmp_path):
    paths = {
        *runner.SUPERVISED_RELEASE_SOURCES,
        *runner.SUPERVISED_RELEASE_BUNDLE_SOURCES,
        *runner.SUPERVISED_RELEASE_INSTALLATION_SOURCES,
        *runner.SUPERVISED_RELEASE_NATIVE_PRIMITIVE_PINS,
        *runner.SUPERVISED_MAINTENANCE_SOURCES,
        *runner.SUPERVISED_RUNTIME_ADMISSION_SOURCES,
        runner.SUPERVISED_DEPLOYMENT_QUALIFICATION_SOURCE,
        runner.SUPERVISED_INSTALLATION_OPERATOR_SOURCE,
        ".github/workflows/checkpoint-source-gates.yml",
        "scripts/checkpoint_runner.py",
    }
    for name in paths:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (ROOT / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._supervised_installation_operator_authority_check(tmp_path) == ()
    path = tmp_path / runner.SUPERVISED_INSTALLATION_OPERATOR_SOURCE
    path.write_text(path.read_text() + "\nimport trading_bot.robinhood_mcp\n")
    failures = runner._supervised_installation_operator_authority_check(tmp_path)
    assert "installation operator reviewed source drift" in failures
    assert "installation operator import boundary drift" in failures
    path.write_text((ROOT / runner.SUPERVISED_INSTALLATION_OPERATOR_SOURCE).read_text())
    path = tmp_path / "scripts/checkpoint_runner.py"
    original = path.read_text()
    path.write_text(
        original.replace("arch133-ag-installation-attempt", "caller-attempt")
    )
    assert (
        "installation attempt namespace source drift"
        in runner._supervised_installation_operator_authority_check(tmp_path)
    )
    path.write_text(original)
    path.write_text(
        path.read_text().replace("handle.flush()", "handle.flush(); bypass = True")
    )
    assert (
        "installation runner authority drift"
        in runner._supervised_installation_operator_authority_check(tmp_path)
    )


def test_no_caller_policy_or_alternate_cli_and_import_closure():
    assert not inspect.signature(subject._derive_release).parameters
    assert not inspect.signature(subject._preflight).parameters
    assert tuple(inspect.signature(subject._execute_once).parameters) == (
        "consume_attempt",
    )
    tree = ast.parse(Path(subject.__file__).read_text())
    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))
    calls = [
        getattr(node.func, "attr", getattr(node.func, "id", ""))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    ]
    assert calls.count("install_release") == 1
    assert not {
        "rmtree",
        "unlink",
        "remove",
        "rename",
        "write_bytes",
        "write_text",
        "exec",
        "eval",
        "input",
        "retry",
        "cleanup",
        "rollback",
    } & set(calls)
    code = """
import ctypes, sys
def denied(*args, **kwargs):
    raise AssertionError('native access at import')
ctypes.WinDLL = denied
import trading_bot.supervised_release.installation_operator
for name in sys.modules:
    assert not any(part in name for part in (
        'supervised_release.native_write', 'supervised_release.installer',
        'scheduler', 'oauth', 'credentials', 'robinhood_mcp',
        'unattended_execution', 'unattended_host', 'paper_v2', 'broker',
    )), name
"""
    result = subprocess.run(
        [sys.executable, "-B", "-"],
        input=code,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert result.returncode == 0, result.stderr


def test_ah_preflight_ready_or_existing(monkeypatch):
    monkeypatch.setattr(parent_subject, "_administrator_host", lambda: None)
    for exists, expected, target_state in (
        (False, "READY_TO_CREATE", "ABSENT"),
        (True, "ALREADY_PROVISIONED", "EXACT_PARENT_PRESENT"),
    ):
        readiness = parent_subject.ParentReadiness(
            exists,
            (7, 11),
            (7, 12) if exists else None,
        )
        monkeypatch.setattr(parent_subject, "_readiness", lambda value=readiness: value)
        result = parent_subject._preflight()
        assert result["status"] == "PASS"
        assert result["primary"]["status"] == expected
        assert result["primary"]["target_state"] == target_state
        assert result["effect_disposition"] == "NOT_STARTED"


def test_ah_precreate_failure_has_exact_no_effect_disposition(monkeypatch):
    monkeypatch.setattr(parent_subject, "_administrator_host", lambda: None)
    monkeypatch.setattr(
        parent_subject,
        "_readiness",
        lambda: parent_subject.ParentReadiness(False, (7, 11), None),
    )

    def reject():
        raise RuntimeError("private detail")

    result = parent_subject._execute_once(reject)

    assert result["status"] == "BLOCKED"
    assert result["effect_disposition"] == "NOT_STARTED"
    assert result["primary"]["disposition"] == "NO_PARENT_PROVISIONING_EFFECT"
    assert result["primary"]["target_state"] == "ABSENT"
    assert "private" not in repr(result)


def test_ah_execute_consumes_once_before_single_create(monkeypatch):
    events = []
    states = iter(
        (
            parent_subject.ParentReadiness(False, (7, 11), None),
            parent_subject.ParentReadiness(True, (7, 11), (7, 12)),
        )
    )
    monkeypatch.setattr(parent_subject, "_administrator_host", lambda: None)
    monkeypatch.setattr(parent_subject, "_readiness", lambda: next(states))
    monkeypatch.setattr(
        parent_subject,
        "_create_parent",
        lambda: events.append("create") or True,
    )

    result = parent_subject._execute_once(lambda: events.append("consume"))

    assert result["status"] == "PASS"
    assert result["primary"]["status"] == "PROVISIONED_VERIFIED"
    assert result["effect_disposition"] == "CONFIRMED"
    assert events == ["consume", "create"]


def test_ah_existing_parent_is_zero_effect(monkeypatch):
    monkeypatch.setattr(parent_subject, "_administrator_host", lambda: None)
    monkeypatch.setattr(
        parent_subject,
        "_readiness",
        lambda: parent_subject.ParentReadiness(True, (7, 11), (7, 12)),
    )
    monkeypatch.setattr(
        parent_subject,
        "_create_parent",
        lambda: pytest.fail("create must not run"),
    )

    result = parent_subject._execute_once(
        lambda: pytest.fail("latch must not be consumed")
    )

    assert result["status"] == "PASS"
    assert result["primary"]["status"] == "ALREADY_PROVISIONED_VERIFIED"
    assert result["effect_disposition"] == "NOT_STARTED"


@pytest.mark.parametrize("mode", ["create_false", "post_observation"])
def test_ah_possible_effect_is_indeterminate_without_retry(monkeypatch, mode):
    events = []
    first = parent_subject.ParentReadiness(False, (7, 11), None)
    calls = 0

    def readiness():
        nonlocal calls
        calls += 1
        if calls == 1:
            return first
        if mode == "post_observation":
            raise RuntimeError("private detail")
        return parent_subject.ParentReadiness(True, (7, 11), (7, 12))

    monkeypatch.setattr(parent_subject, "_administrator_host", lambda: None)
    monkeypatch.setattr(parent_subject, "_readiness", readiness)
    monkeypatch.setattr(
        parent_subject,
        "_create_parent",
        lambda: events.append("create") or False,
    )

    result = parent_subject._execute_once(lambda: events.append("consume"))

    assert result["status"] == "INDETERMINATE"
    assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"
    assert (
        result["primary"]["disposition"]
        == "PRESERVE_PARENT_PROVISIONING_EVIDENCE_NO_RETRY"
    )
    assert events == ["consume", "create"]
    assert "private" not in repr(result)


def test_ah_registration_and_capability_surface():
    name = "arch133-robinhood-supervised-release-parent-provisioning"
    spec = runner._checkpoint_specs()[name]
    assert runner.ACTIVE_CI_CHECKPOINTS[0] == NAME
    assert runner.ACTIVE_CI_CHECKPOINTS[1] == name
    assert runner.ACTIVE_CI_CHECKPOINTS[2] == (
        "arch133-robinhood-supervised-deployment-qualification"
    )
    assert spec.preflight is runner._supervised_release_parent_preflight
    assert spec.execute is runner._supervised_release_parent_execute
    assert spec.remote_branch == parent_subject.BRANCH
    assert spec.remote_head_env is None
    assert spec.tests == runner.SUPERVISED_RELEASE_PARENT_TESTS
    assert spec.ruff_paths == runner.SUPERVISED_RELEASE_PARENT_RUFF_PATHS
    source = inspect.getsource(parent_subject)
    assert source.count('"CreateDirectoryW"') == 1
    for forbidden in (
        "install_release(",
        ".unlink(",
        ".remove(",
        "rmtree(",
        "RegisterTask",
    ):
        assert forbidden not in source


def test_ah_runner_preflight_creates_no_files(tmp_path, monkeypatch, capsys):
    name = "arch133-robinhood-supervised-release-parent-provisioning"
    spec = runner._checkpoint_specs()[name]
    spec = replace(
        spec,
        preflight=lambda: {
            "status": "PASS",
            "effect_disposition": "NOT_STARTED",
            "primary": {"status": "READY_TO_CREATE", "target_state": "ABSENT"},
        },
    )
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": parent_subject.BRANCH,
        "porcelain": "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda *args: state)
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *args: state["head"])
    before = tuple(tmp_path.iterdir())

    assert runner.preflight_checkpoint(
        spec,
        repo_root=tmp_path,
        evidence_root=tmp_path / "unused",
    ) == (True, None)
    assert tuple(tmp_path.iterdir()) == before
    assert "EVIDENCE=STDOUT" in capsys.readouterr().out


@pytest.mark.parametrize(
    "gate", ["path", "branch", "origin", "ancestor", "dirty", "pins"]
)
def test_ah_exact_runner_source_admission(tmp_path, monkeypatch, gate):
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": parent_subject.BRANCH,
        "porcelain": "",
    }
    monkeypatch.setattr(parent_subject, "WORKTREE", tmp_path)
    monkeypatch.setattr(runner, "_REPOSITORY_ROOT", tmp_path)

    def output(root, *args):
        if args == ("remote", "get-url", "origin"):
            return "wrong" if gate == "origin" else parent_subject.ORIGIN
        return "f" * 40 if gate == "ancestor" else parent_subject.BASE_HEAD

    monkeypatch.setattr(runner, "_git_output", output)
    monkeypatch.setattr(
        runner,
        "_supervised_release_parent_authority_check",
        lambda *args: ("drift",) if gate == "pins" else (),
    )
    if gate == "branch":
        state["branch"] = "feature/caller"
    if gate == "dirty":
        state["porcelain"] = "changed index"

    with pytest.raises(RuntimeError, match="source authority rejected"):
        runner._supervised_release_parent_admission(
            tmp_path / "wrong" if gate == "path" else tmp_path,
            state,
        )


def test_ah_fixed_latch_is_exclusive_and_survives_flush_failure(
    tmp_path, monkeypatch
):
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": parent_subject.BRANCH,
        "porcelain": "",
    }
    latch = tmp_path / "latch" / "attempt.json"
    monkeypatch.setattr(runner, "SUPERVISED_RELEASE_PARENT_ATTEMPT", latch)
    monkeypatch.setattr(runner, "_git_state", lambda *args: state)
    monkeypatch.setattr(
        runner, "_supervised_release_parent_admission", lambda *args: None
    )
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *args: state["head"])
    monkeypatch.setattr(
        runner.os,
        "fsync",
        lambda *args: (_ for _ in ()).throw(OSError("fake flush failure")),
    )

    with pytest.raises(OSError, match="fake flush failure"):
        runner._consume_supervised_release_parent_attempt()
    assert latch.exists()
    original = latch.read_bytes()
    with pytest.raises(FileExistsError):
        runner._consume_supervised_release_parent_attempt()
    assert latch.read_bytes() == original


@pytest.mark.parametrize("entrypoint", ["preflight", "execute"])
def test_ah_runner_revalidates_live_remote_before_host_entry(
    monkeypatch, entrypoint
):
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": parent_subject.BRANCH,
        "porcelain": "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda *args: state)
    monkeypatch.setattr(
        runner, "_supervised_release_parent_admission", lambda *args: None
    )
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *args: "f" * 40)
    monkeypatch.setattr(
        parent_subject,
        "_preflight",
        lambda: pytest.fail("host preflight reached"),
    )
    monkeypatch.setattr(
        parent_subject,
        "_execute_once",
        lambda consume: pytest.fail("host execute reached"),
    )
    monkeypatch.setenv(parent_subject.AUTH_ENV, parent_subject.AUTH_VALUE)

    with pytest.raises(RuntimeError, match="live remote authority rejected"):
        (
            runner._supervised_release_parent_preflight()
            if entrypoint == "preflight"
            else runner._supervised_release_parent_execute()
        )


def test_ah_execute_checkpoint_remote_race_is_no_parent_effect(
    tmp_path, monkeypatch
):
    name = "arch133-robinhood-supervised-release-parent-provisioning"
    spec = runner._checkpoint_specs()[name]
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": parent_subject.BRANCH,
        "porcelain": "",
    }
    calls = 0

    def remote(*args):
        nonlocal calls
        calls += 1
        return state["head"] if calls == 1 else "f" * 40

    monkeypatch.setattr(runner, "_git_state", lambda *args: state)
    monkeypatch.setattr(
        runner, "_supervised_release_parent_admission", lambda *args: None
    )
    monkeypatch.setattr(runner, "_remote_branch_head", remote)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: {name: spec})
    monkeypatch.setenv(parent_subject.AUTH_ENV, parent_subject.AUTH_VALUE)

    passed, report_path = runner.execute_checkpoint(
        spec,
        repo_root=tmp_path,
        evidence_root=tmp_path / "evidence",
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert passed is False
    assert report["status"] == "STOPPED"
    assert report["effect_disposition"] == "NOT_STARTED"
    assert report["runner_error"] == {
        "type": "PARENT_PROVISIONING_STOPPED",
        "detail": "NO_PARENT_PROVISIONING_EFFECT",
    }


def test_ah_runner_consumed_latch_blocks_new_effect(monkeypatch):
    monkeypatch.setattr(
        runner,
        "_supervised_release_parent_admission",
        lambda repo_root, state: None,
    )
    monkeypatch.setattr(
        runner,
        "_git_state",
        lambda root: {
            "head": "a",
            "tree": "b",
            "branch": parent_subject.BRANCH,
            "porcelain": "",
        },
    )
    monkeypatch.setattr(runner, "_remote_branch_head", lambda root, branch: "a")
    monkeypatch.setattr(
        runner, "_supervised_release_parent_latch_consumed", lambda: True
    )
    monkeypatch.setenv(parent_subject.AUTH_ENV, parent_subject.AUTH_VALUE)
    result = runner._supervised_release_parent_execute()
    assert result["status"] == "INDETERMINATE"
    assert result["primary"]["reason"] == "CONSUMED_ATTEMPT"
    assert (
        result["primary"]["disposition"]
        == "PRESERVE_PARENT_PROVISIONING_EVIDENCE_NO_RETRY"
    )


def test_ah_observer_absent_exact_and_malformed_parent_policy():
    release = accepted()
    native = FakeNative(release)
    container_path = r"F:\AITradingBot"
    native.nodes[container_path] = replace(
        native.nodes[container_path],
        aces=parent_subject.CONTAINER_ACES,
    )
    exact_container = native.nodes[container_path]
    native.nodes.pop(RELEASES_BASE)

    absent = parent_subject._observe_once(native)
    assert absent.exists is False
    assert absent.parent_identity is None

    native.add(RELEASES_BASE, directory=True)
    exact = parent_subject._observe_once(native)
    assert exact.exists is True
    assert exact.parent_identity == native.nodes[RELEASES_BASE].identity

    for malformed_container in (
        replace(exact_container, protected=False),
        replace(
            exact_container,
            aces=tuple(reversed(parent_subject.CONTAINER_ACES)),
        ),
        replace(
            exact_container,
            aces=(*parent_subject.CONTAINER_ACES, IMAGE_ACES[2]),
        ),
    ):
        native.nodes[container_path] = malformed_container
        with pytest.raises(ValueError, match="release container security rejected"):
            parent_subject._observe_once(native)
    native.nodes[container_path] = exact_container

    native.nodes[RELEASES_BASE] = replace(
        native.nodes[RELEASES_BASE],
        protected=False,
    )
    with pytest.raises(ValueError, match="object identity/security rejected"):
        parent_subject._observe_once(native)
