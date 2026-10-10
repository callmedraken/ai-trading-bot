"""133-AF fake deployment evidence only; never observe a production surface."""

import ast
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from test_supervised_release_installation import FakeNative
from test_supervised_runtime_host_admission import setup as runtime_setup  # noqa: F401

from scripts import checkpoint_runner as runner
from scripts import run_test_certification as certification
from trading_bot.supervised_release import qualification as subject
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import (
    ReleaseBundle,
    ReleaseFile,
    verify_release_bundle,
)
from trading_bot.supervised_release.installation_contract import ANCESTORS
from trading_bot.supervised_release.maintenance import (
    TASK_PATH,
    MaintenanceTask,
    ModeEvidence,
    OperatingMode,
    SchedulerObservation,
)
from trading_bot.supervised_release.model import DURABLE_DATA_ROOT, PRODUCTION_PYTHON
from trading_bot.supervised_release.observer import observe_installed_release
from trading_bot.supervised_release.runtime_admission import admit_runtime_host

ROOT = Path(__file__).resolve().parents[2]
NAME = "arch133-robinhood-supervised-deployment-qualification"
C = subject.QualificationClass
QUIESCENT = ModeEvidence(
    OperatingMode.SUPERVISED_MAINTENANCE, False, False, False, False, False
)


class FakeReads:
    def __init__(self, release):
        identifier = release.manifest.release_id
        self.selection = subject.SelectionObservation(
            (identifier,), (identifier,), (TASK_PATH,)
        )
        self.task = SchedulerObservation(xml=MaintenanceTask(release).xml)
        self.mode = QUIESCENT
        self.reads = {"selection": 0, "task": 0, "mode": 0}
        self.hook = None

    def read(self, name):
        self.reads[name] += 1
        if self.hook:
            self.hook(self, name, self.reads[name])
        return getattr(self, name)

    def observe_selection(self):
        return self.read("selection")

    def observe_fixed_task(self):
        return self.read("task")

    def observe_mode(self):
        return self.read("mode")


@pytest.fixture
def setup(request):
    f = request.getfixturevalue("runtime_setup")
    f.runtime.substrate = replace(
        f.runtime.substrate,
        objects=tuple(
            replace(row, identity=f.installed.python_identity)
            if row.path == PRODUCTION_PYTHON
            else replace(row, identity=(7, row.identity[1] + 100))
            for row in f.runtime.substrate.objects
        ),
    )
    f.admission = admit_runtime_host(
        f.release,
        f.binding,
        f.installed,
        image_observer=f.native,
        runtime_observer=f.runtime,
    )
    assert f.admission.evidence is not None
    f.native.events.clear()
    f.native.read_scopes = 0
    f.runtime.process_reads = f.runtime.substrate_reads = 0
    f.reads = FakeReads(f.release)
    return f


def qualify(f, **overrides):
    args = dict(
        release=f.release,
        binding=f.binding,
        installed=f.installed,
        runtime_admission=f.admission,
        image_observer=f.native,
        scheduler_observer=f.reads,
        mode_observer=f.reads,
        runtime_observer=f.runtime,
        selection_observer=f.reads,
    )
    args.update(overrides)
    return subject.qualify_deployment(**args)


def rollback_candidate(f):
    manifest = replace(f.release.manifest, risk_policy_version="2.0.0")
    bundle = ReleaseBundle(
        tuple(
            ReleaseFile(item.relative_path, manifest.to_json().encode())
            if item.relative_path == "manifest.json"
            else item
            for item in f.release.bundle.files
        )
    )
    import hashlib

    release = verify_release_bundle(
        bundle,
        expected_manifest_sha256=hashlib.sha256(
            manifest.to_json().encode()
        ).hexdigest(),
        expected_source_head=f.release.expected_source_head,
        expected_source_tree=f.release.expected_source_tree,
        expected_source_paths=f.release.expected_source_paths,
    )
    binding = RuntimeBinding(release)
    native = FakeNative(release)
    native.seed(release)
    for path, row in tuple(native.nodes.items()):
        if path not in (*ANCESTORS, PRODUCTION_PYTHON, r"F:\AITradingBot\runtime"):
            native.nodes[path] = replace(row, identity=(7, row.identity[1] + 1000))
    installed = observe_installed_release(release, binding, native=native)
    native.events.clear()
    native.read_scopes = 0
    f.reads.selection = replace(
        f.reads.selection, rollback_release_ids=(manifest.release_id,)
    )
    return subject.RollbackCandidate(release, binding, installed), native


def blocked(result, classification):
    assert result == subject.QualificationResult((classification,))


def test_selected_identity_propagation_and_only_read_scopes(setup):
    result = qualify(setup)
    assert result.classifications == (
        C.SELECTED_READY_DISABLED,
        C.SELECTED_RUNTIME_ADMITTED,
    )
    assert result.evidence.selected == setup.installed
    assert result.evidence.runtime == setup.admission.evidence
    assert result.evidence.scheduler == setup.reads.task
    assert result.evidence.runtime.release_root == setup.root
    assert result.evidence.runtime.source_root == setup.source
    assert result.evidence.runtime.launcher == setup.launcher
    assert result.evidence.durable_data_root == DURABLE_DATA_ROOT
    assert result.evidence.rollback is None
    assert result.evidence.runtime.dependency_closure == "UNPROVEN"
    assert setup.native.read_scopes == 4
    assert setup.runtime.process_reads == setup.runtime.substrate_reads == 4
    assert set(name for name, _ in setup.native.events) <= {
        "read_open",
        "read_close",
        "object",
        "names",
        "read",
        "python_version",
    }
    assert setup.reads.reads == {"selection": 2, "task": 2, "mode": 2}


def test_distinct_rollback_replayed_twice_and_never_bound(setup):
    candidate, native = rollback_candidate(setup)
    result = qualify(setup, rollback=candidate, rollback_image_observer=native)
    assert result.classifications == (
        C.SELECTED_READY_DISABLED,
        C.SELECTED_RUNTIME_ADMITTED,
        C.ROLLBACK_CANDIDATE_VERIFIED,
    )
    assert result.evidence.rollback == candidate.installed
    assert candidate.release.manifest.release_id != setup.release.manifest.release_id
    assert native.read_scopes == 2
    assert candidate.release.manifest.release_id not in result.evidence.scheduler.xml
    assert result.evidence.scheduler == setup.reads.task
    assert not any(
        name.startswith(("install", "publish", "write", "create"))
        for name, _ in native.events
    )


def test_selected_equals_rollback_rejected_before_rollback_reads(setup):
    candidate = subject.RollbackCandidate(setup.release, setup.binding, setup.installed)
    blocked(
        qualify(setup, rollback=candidate, rollback_image_observer=setup.native),
        C.BLOCKED_ROLLBACK_STATE,
    )
    assert setup.native.read_scopes == 1


@pytest.mark.parametrize(
    "field",
    [
        "release_id",
        "manifest_sha256",
        "binding_sha256",
        "parent_identity",
        "image_identity",
        "python_identity",
        "python_version",
        "python_sha256",
        "dependency_closure",
    ],
)
def test_selected_installed_identity_must_replay(setup, field):
    old = getattr(setup.installed, field)
    value = (99, 99) if type(old) is tuple else "drift"
    blocked(
        qualify(setup, installed=replace(setup.installed, **{field: value})),
        C.BLOCKED_IDENTITY_DRIFT,
    )


@pytest.mark.parametrize(
    "field",
    [
        "release_id",
        "manifest_sha256",
        "binding_sha256",
        "image_identity",
        "python_identity",
        "release_root",
        "source_root",
        "launcher",
        "site_packages",
        "dependency_closure",
    ],
)
def test_ae_runtime_evidence_exact_agreement(setup, field):
    old = getattr(setup.admission.evidence, field)
    value = (99, 99) if type(old) is tuple else "drift"
    admission = replace(
        setup.admission, evidence=replace(setup.admission.evidence, **{field: value})
    )
    blocked(qualify(setup, runtime_admission=admission), C.BLOCKED_RUNTIME_STATE)


class EqualityAlias:
    def __eq__(self, other):
        return True


@pytest.mark.parametrize("which", ["installed", "runtime", "selection"])
def test_untyped_equality_alias_cannot_forge_evidence(setup, which):
    if which == "installed":
        blocked(
            qualify(
                setup, installed=replace(setup.installed, release_id=EqualityAlias())
            ),
            C.BLOCKED_IDENTITY_DRIFT,
        )
    elif which == "runtime":
        evidence = replace(setup.admission.evidence, launcher=EqualityAlias())
        blocked(
            qualify(
                setup, runtime_admission=replace(setup.admission, evidence=evidence)
            ),
            C.BLOCKED_RUNTIME_STATE,
        )
    else:
        setup.reads.selection = replace(
            setup.reads.selection, selected_release_ids=(EqualityAlias(),)
        )
        blocked(qualify(setup), C.BLOCKED_IDENTITY_DRIFT)


def test_scheduler_bound_to_rollback_is_not_selected_authority(setup):
    candidate, native = rollback_candidate(setup)
    setup.reads.task = SchedulerObservation(xml=MaintenanceTask(candidate.release).xml)
    blocked(
        qualify(setup, rollback=candidate, rollback_image_observer=native),
        C.BLOCKED_SCHEDULER_STATE,
    )


@pytest.mark.parametrize(
    "changes", [{"status": "VERIFIED"}, {"reason": "VERIFIED"}, {"evidence": None}]
)
def test_ae_typed_accepted_result_required(setup, changes):
    blocked(
        qualify(setup, runtime_admission=replace(setup.admission, **changes)),
        C.BLOCKED_RUNTIME_STATE,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"xml": None},
        {"task_path": r"\Other"},
        {"enabled": True},
        {"running": True},
        {"active_instances": 1},
        {"active_instances": -1},
        {"enabled": 0},
        {"running": 0},
        {"active_instances": False},
    ],
)
def test_exact_disabled_scheduler_state(setup, changes):
    setup.reads.task = replace(setup.reads.task, **changes)
    blocked(qualify(setup), C.BLOCKED_SCHEDULER_STATE)


@pytest.mark.parametrize(
    "old,new",
    [
        ("-I -S -B", "-I -B"),
        ("-I -S -B", "-I -S -B --caller"),
        ("<Enabled>false", "<Enabled>true"),
        ("IgnoreNew", "Parallel"),
        ("<Triggers></Triggers>", "<Triggers><TimeTrigger /></Triggers>"),
        ("<AllowStartOnDemand>false", "<AllowStartOnDemand>true"),
        ("<WakeToRun>false", "<WakeToRun>true"),
        ("LeastPrivilege", "HighestAvailable"),
        ("<WorkingDirectory>", "<WorkingDirectory>C:\\caller"),
        ("<Exec>", "<Exec><Environment>caller</Environment>"),
        ("</Settings>", "<RestartOnFailure /></Settings>"),
        ("python.exe", "other.exe"),
    ],
)
def test_scheduler_projection_and_definition_exact(setup, old, new):
    assert old in setup.reads.task.xml
    setup.reads.task = replace(
        setup.reads.task, xml=setup.reads.task.xml.replace(old, new)
    )
    blocked(qualify(setup), C.BLOCKED_SCHEDULER_STATE)


@pytest.mark.parametrize(
    "field",
    [
        "active_bot_process",
        "active_bot_cycle",
        "runtime_authority",
        "trading_authority",
        "provider_authority",
    ],
)
def test_runtime_quiescence_no_effect_authority(setup, field):
    setup.reads.mode = replace(QUIESCENT, **{field: True})
    blocked(qualify(setup), C.BLOCKED_RUNTIME_STATE)


def test_runtime_python_file_identity_agrees_with_ac(setup):
    setup.runtime.substrate = replace(
        setup.runtime.substrate,
        objects=tuple(
            replace(row, identity=(7, 987)) if row.path == PRODUCTION_PYTHON else row
            for row in setup.runtime.substrate.objects
        ),
    )
    blocked(qualify(setup), C.BLOCKED_RUNTIME_STATE)


@pytest.mark.parametrize("drift", ["bytes", "missing", "extra", "reparse", "python"])
@pytest.mark.parametrize("which", ["selected", "rollback"])
def test_selected_and_rollback_image_independent_replay(setup, drift, which):
    candidate, rollback_native = rollback_candidate(setup)
    native = setup.native if which == "selected" else rollback_native
    path = native.paths.final + r"\src\trading_bot\__init__.py"
    if drift == "bytes":
        native.data[path] = b"tampered"
    elif drift == "missing":
        native.nodes.pop(path)
    elif drift == "extra":
        native.add(native.paths.final + r"\unreviewed.txt", directory=False)
    elif drift == "reparse":
        native.nodes[path] = replace(native.nodes[path], reparse=True)
    else:
        native.version = "3.14.4"
    blocked(
        qualify(setup, rollback=candidate, rollback_image_observer=rollback_native),
        C.BLOCKED_IDENTITY_DRIFT if which == "selected" else C.BLOCKED_ROLLBACK_STATE,
    )


@pytest.mark.parametrize(
    "changes,classification",
    [
        ({"selected_release_ids": ()}, C.BLOCKED_IDENTITY_DRIFT),
        ({"selected_release_ids": ("alternate",)}, C.BLOCKED_IDENTITY_DRIFT),
        ({"runtime_release_ids": ()}, C.BLOCKED_RUNTIME_STATE),
        ({"task_paths": (TASK_PATH, TASK_PATH)}, C.BLOCKED_SCHEDULER_STATE),
        ({"complete": False}, C.BLOCKED_IDENTITY_DRIFT),
        ({"rollback_release_ids": ("alternate",)}, C.BLOCKED_ROLLBACK_STATE),
        ({"rollback_bound_or_active": True}, C.BLOCKED_ROLLBACK_STATE),
    ],
)
def test_selection_inventory_ambiguity(setup, changes, classification):
    setup.reads.selection = replace(setup.reads.selection, **changes)
    blocked(qualify(setup), classification)


@pytest.mark.parametrize("which", ["none", "duplicate", "selected", "list", "multiple"])
def test_rollback_inventory_ambiguity(setup, which):
    candidate, native = rollback_candidate(setup)
    identifier = candidate.release.manifest.release_id
    values = {
        "none": (),
        "duplicate": (identifier, identifier),
        "selected": (setup.release.manifest.release_id,),
        "list": [identifier],
        "multiple": (identifier, "alternate"),
    }
    setup.reads.selection = replace(
        setup.reads.selection, rollback_release_ids=values[which]
    )
    blocked(
        qualify(setup, rollback=candidate, rollback_image_observer=native),
        C.BLOCKED_ROLLBACK_STATE,
    )


@pytest.mark.parametrize(
    "which", ["binding", "installed", "python", "parent", "image_alias"]
)
def test_rollback_binding_and_host_identity_drift(setup, which):
    candidate, native = rollback_candidate(setup)
    if which == "binding":
        candidate = replace(candidate, binding=setup.binding)
    elif which == "installed":
        candidate = replace(candidate, installed=setup.installed)
    else:
        path = {
            "python": PRODUCTION_PYTHON,
            "parent": ANCESTORS[-1],
            "image_alias": native.paths.final,
        }[which]
        identity = (
            setup.installed.image_identity if which == "image_alias" else (7, 999)
        )
        native.nodes[path] = replace(native.nodes[path], identity=identity)
        candidate = replace(
            candidate,
            installed=observe_installed_release(
                candidate.release, candidate.binding, native=native
            ),
        )
    blocked(
        qualify(setup, rollback=candidate, rollback_image_observer=native),
        C.BLOCKED_ROLLBACK_STATE,
    )


@pytest.mark.parametrize(
    "name,classification",
    [
        ("selection", C.BLOCKED_IDENTITY_DRIFT),
        ("task", C.BLOCKED_SCHEDULER_STATE),
        ("mode", C.BLOCKED_RUNTIME_STATE),
    ],
)
def test_repeated_observation_drift(setup, name, classification):
    def drift(reads, key, count):
        if key == name and count == 2:
            if key == "selection":
                reads.selection = replace(reads.selection, complete=False)
            elif key == "task":
                reads.task = replace(reads.task, running=True)
            else:
                reads.mode = replace(reads.mode, active_bot_cycle=True)

    setup.reads.hook = drift
    blocked(qualify(setup), classification)


@pytest.mark.parametrize("which", ["process", "substrate"])
@pytest.mark.parametrize("count", [2, 4])
def test_runtime_drift_across_ae_and_final_observation(setup, which, count):
    def drift(runtime):
        if getattr(runtime, which + "_reads") == count:
            if which == "process":
                runtime.process = replace(
                    runtime.process, working_directory="C:\\alternate"
                )
            else:
                runtime.substrate = replace(
                    runtime.substrate,
                    before_fingerprint="b" * 64,
                    after_fingerprint="b" * 64,
                )

    setattr(setup.runtime, which + "_hook", drift)
    blocked(qualify(setup), C.BLOCKED_RUNTIME_STATE)


@pytest.mark.parametrize("which", ["selected", "rollback"])
def test_final_image_drift_no_retry_or_partial_success(setup, which):
    candidate, native = rollback_candidate(setup)
    image = setup.native if which == "selected" else native

    def drift(backend, scope):
        if scope == (4 if which == "selected" else 2):
            root = backend.paths.final
            backend.nodes[root] = replace(backend.nodes[root], identity=(7, 9090))

    image.hook = drift
    result = qualify(setup, rollback=candidate, rollback_image_observer=native)
    blocked(
        result,
        C.BLOCKED_IDENTITY_DRIFT if which == "selected" else C.BLOCKED_ROLLBACK_STATE,
    )
    assert image.read_scopes == (4 if which == "selected" else 2)


@pytest.mark.parametrize(
    "field",
    [
        "root",
        "release_root",
        "rollback_root",
        "source_root",
        "launcher",
        "python",
        "durable_data_root",
        "task_path",
        "branch",
        "worktree",
        "environment",
        "cwd",
    ],
)
def test_no_caller_selected_paths(setup, field):
    with pytest.raises(TypeError):
        qualify(setup, **{field: "C:\\caller"})
    assert setup.native.read_scopes == 0


@pytest.mark.parametrize(
    "field,classification",
    [
        ("image_observer", C.BLOCKED_IDENTITY_DRIFT),
        ("scheduler_observer", C.BLOCKED_SCHEDULER_STATE),
        ("mode_observer", C.BLOCKED_RUNTIME_STATE),
        ("runtime_observer", C.BLOCKED_RUNTIME_STATE),
        ("selection_observer", C.BLOCKED_IDENTITY_DRIFT),
    ],
)
def test_missing_read_seam_never_selects_native_default(setup, field, classification):
    blocked(qualify(setup, **{field: None}), classification)


def test_rollback_observer_pair_and_single_typed_candidate(setup):
    candidate, native = rollback_candidate(setup)
    blocked(qualify(setup, rollback=candidate), C.BLOCKED_ROLLBACK_STATE)
    blocked(qualify(setup, rollback_image_observer=native), C.BLOCKED_ROLLBACK_STATE)
    blocked(
        qualify(setup, rollback=(candidate,), rollback_image_observer=native),
        C.BLOCKED_ROLLBACK_STATE,
    )


def test_observer_exception_sanitized_and_no_retry(setup):
    def fail(*args):
        raise RuntimeError("private diagnostics or credentials must never escape")

    setup.reads.hook = fail
    result = qualify(setup)
    blocked(result, C.BLOCKED_RUNTIME_STATE)
    assert setup.reads.reads["mode"] == 1
    assert "private" not in repr(result)


def test_release_and_binding_replay_before_observations(setup):
    object.__setattr__(setup.release, "expected_source_tree", "c" * 40)
    blocked(
        qualify(setup),
        C.BLOCKED_IDENTITY_DRIFT,
    )
    assert not setup.native.events


def test_registration_workflow_profiles_and_authority_chain():
    spec = runner._checkpoint_specs()[NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-supervised-deployment-qualification"
    assert spec.tests == runner.SUPERVISED_DEPLOYMENT_QUALIFICATION_TESTS
    assert spec.ruff_paths == runner.SUPERVISED_DEPLOYMENT_QUALIFICATION_RUFF_PATHS
    assert (
        spec.authority_check
        is runner._supervised_deployment_qualification_authority_check
    )
    assert spec.authority_check(ROOT) == ()
    assert runner.ACTIVE_CI_CHECKPOINTS[0] == NAME
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 55
    workflow = (ROOT / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(NAME) == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    assert not runner._batch_workflow_is_reviewed(
        workflow.replace(NAME, "caller-checkpoint")
    )
    inventory = certification.discover_inventory(ROOT)
    profiles = {
        name: certification.select_inventory(inventory, name)
        for name in ("full", "robinhood", "legacy", "exhaustive")
    }
    assert {name: len(modules) for name, modules in profiles.items()} == {
        "full": 155,
        "robinhood": 82,
        "legacy": 205,
        "exhaustive": 360,
    }
    assert set(profiles["robinhood"]) <= set(profiles["full"])
    assert set(profiles["full"]).isdisjoint(profiles["legacy"])
    assert set(profiles["full"]) | set(profiles["legacy"]) == set(inventory)


@pytest.mark.parametrize(
    "relative",
    [
        "src/trading_bot/supervised_release/observer.py",
        "src/trading_bot/supervised_release/maintenance.py",
        "src/trading_bot/supervised_release/runtime_admission.py",
        "src/trading_bot/supervised_release/qualification.py",
    ],
)
def test_ac_ad_ae_af_authority_pin_drift_fails_closed(monkeypatch, relative):
    original = runner._git_blob_sha1
    monkeypatch.setattr(
        runner,
        "_git_blob_sha1",
        lambda path: "0" * 40 if path == ROOT / relative else original(path),
    )
    assert runner._supervised_deployment_qualification_authority_check(ROOT)


@pytest.mark.parametrize(
    "field,value",
    [
        ("preflight", lambda: None),
        ("execute", lambda: None),
        ("remote_head_env", "CALLER"),
        ("remote_branch", "feature/caller"),
        ("tests", ()),
        ("ruff_paths", ()),
    ],
)
def test_registration_drift_fails_closed(monkeypatch, field, value):
    specs = runner._checkpoint_specs()
    specs[NAME] = replace(specs[NAME], **{field: value})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert (
        "deployment qualification source-only registration drift"
        in runner._supervised_deployment_qualification_authority_check(ROOT)
    )


def test_no_mutation_retry_cleanup_or_path_surface():
    assert {
        key for key in subject.SelectionObserver.__dict__ if not key.startswith("_")
    } == {"observe_selection"}
    tree = ast.parse(Path(subject.__file__).read_text(encoding="utf-8"))
    forbidden = {
        "open",
        "run",
        "Popen",
        "WinDLL",
        "sleep",
        "unlink",
        "remove",
        "delete",
        "install_release",
        "publish",
        "start",
        "enable",
        "begin",
        "finish",
        "rebind",
        "activate",
        "repair",
        "cleanup",
        "retry",
    }
    calls = {
        getattr(node.func, "attr", getattr(node.func, "id", ""))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert not calls & forbidden
    assert not any(
        isinstance(node, (ast.While, ast.AsyncFunctionDef)) for node in ast.walk(tree)
    )


def test_import_closure_remains_inert():
    code = """
import ctypes, sys
def forbidden(*args, **kwargs):
    raise AssertionError('native access')
ctypes.WinDLL = forbidden
import trading_bot.supervised_release.qualification
for name in sys.modules:
    assert not any(part in name for part in (
        'supervised_release.native_', 'supervised_release.installer',
        'arch133_scheduler_installation', 'robinhood_mcp', 'credentials',
        'unattended_execution', 'unattended_host', 'paper_v2', 'broker',
    )), name
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
