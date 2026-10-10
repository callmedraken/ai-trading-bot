"""133-AD fake image/task/mode observations; no Task Scheduler/production reads."""

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
from trading_bot.arch133_scheduler_installation.operator import TASK_XML
from trading_bot.supervised_release import maintenance as subject
from trading_bot.supervised_release import observer
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.installation_contract import PYTHON_SHA256
from trading_bot.supervised_release.model import PRODUCTION_PYTHON

ROOT = Path(__file__).resolve().parents[2]
NAME = "arch133-robinhood-supervised-maintenance-rebind"
QUIESCENT = subject.ModeEvidence(
    subject.OperatingMode.SUPERVISED_MAINTENANCE, False, False, False, False, False
)
PREDECESSOR = TASK_XML.format(
    start="2026-10-07T13:35:00.000000Z", end="2026-10-07T19:55:00.000000Z"
)


class FakeReads:
    def __init__(self, observation=None):
        self.observation = observation or subject.SchedulerObservation()
        self.mode = QUIESCENT
        self.task_reads = 0
        self.mode_reads = 0
        self.task_hook = None
        self.mode_hook = None

    def observe_fixed_task(self):
        self.task_reads += 1
        if self.task_hook:
            self.task_hook(self)
        return self.observation

    def observe_mode(self):
        self.mode_reads += 1
        if self.mode_hook:
            self.mode_hook(self)
        return self.mode

    def credential(self):
        pytest.fail("credential access during source plan")


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
    return SimpleNamespace(
        release=release,
        binding=binding,
        installed=installed,
        native=native,
        reads=FakeReads(),
    )


def plan(f):
    return subject.plan_maintenance_rebind(
        f.release,
        f.binding,
        f.installed,
        image_observer=f.native,
        scheduler_observer=f.reads,
        mode_observer=f.reads,
    )


def test_fixed_immutable_action_and_absence(setup):
    f = setup
    result = plan(f)
    assert result.status is subject.Status.PLANNED
    assert result.classification is subject.Classification.ABSENT
    assert result.installed == f.installed
    task = result.task
    root = "F:\\AITradingBot\\releases\\" + f.release.manifest.release_id
    assert task.task_path == subject.TASK_PATH
    assert task.working_directory == root
    assert task.executable == PRODUCTION_PYTHON
    assert task.arguments == (
        "-I",
        "-S",
        "-B",
        root + r"\scripts\run_arch133_supervised_release_review_paper.py",
    )
    assert task.principal_sid == "S-1-5-21-1397534616-3988210162-180023805-1009"
    assert task.run_level == "LeastPrivilege"
    assert task.enabled is task.allow_demand_start is False
    assert task.semantic_arguments == task.scheduler_owned_environment == ()
    assert task.triggers == ()
    assert "<Triggers></Triggers>" in task.xml
    assert f.native.read_scopes == f.reads.task_reads == 2
    assert f.reads.mode_reads == 3
    assert not any(
        event[0] in {"write", "publish", "create_directory"}
        for event in f.native.events
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("mode", subject.OperatingMode.UNATTENDED_RUNTIME),
        ("mode", "SUPERVISED_MAINTENANCE"),
        *(
            (field, value)
            for field in (
                "active_bot_process",
                "active_bot_cycle",
                "runtime_authority",
                "trading_authority",
                "provider_authority",
            )
            for value in (True, 0, None)
        ),
    ],
)
def test_mode_exclusion_before_image_and_scheduler(setup, field, value):
    setup.reads.mode = replace(QUIESCENT, **{field: value})
    result = plan(setup)
    assert result.status is subject.Status.BLOCKED
    assert result.reason is subject.Reason.MODE
    assert setup.native.events == [] and setup.reads.task_reads == 0


@pytest.mark.parametrize(
    "kind", ["bound", "predecessor", "unexpected", "enabled", "running", "instances"]
)
def test_closed_classifications(setup, kind):
    f = setup
    xml = subject.MaintenanceTask(f.release).xml
    if kind == "predecessor":
        xml = PREDECESSOR
    if kind == "unexpected":
        xml = xml.replace("<Priority>7", "<Priority>8")
    f.reads.observation = subject.SchedulerObservation(
        xml=xml,
        enabled=kind == "enabled",
        running=kind == "running",
        active_instances=int(kind == "instances"),
    )
    result = plan(f)
    expected = {
        "bound": subject.Classification.ALREADY_BOUND_DISABLED,
        "predecessor": subject.Classification.EXACT_REVIEWED_133P_PREDECESSOR_DISABLED,
        "unexpected": subject.Classification.UNEXPECTED_EXISTING,
    }.get(kind, subject.Classification.RUNNING_OR_ENABLED)
    assert result.classification is expected
    assert result.status is (
        subject.Status.PLANNED
        if kind in {"bound", "predecessor"}
        else subject.Status.BLOCKED
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("task_path", r"\other"),
        ("enabled", 0),
        ("running", None),
        ("active_instances", True),
        ("active_instances", -1),
        ("xml", ""),
        ("xml", "<!DOCTYPE Task><Task/>"),
        ("xml", "<Task>"),
        pytest.param("xml", " " * 65537, id="oversized-xml"),
    ],
)
def test_bad_observation_fails_closed(setup, field, value):
    setup.reads.observation = replace(subject.SchedulerObservation(), **{field: value})
    assert plan(setup).status is subject.Status.BLOCKED


@pytest.mark.parametrize("historical", [False, True])
@pytest.mark.parametrize(
    "old,new",
    [
        ("<Priority>7", "<Priority>8"),
        ("LeastPrivilege", "HighestAvailable"),
        ("-I ", "-X "),
        ("python.exe", "other.exe"),
        ("-1009", "-1010"),
        ("<AllowStartOnDemand>false", "<AllowStartOnDemand>true"),
        ("<StartWhenAvailable>false", "<StartWhenAvailable>true"),
        ("<Actions Context=", "<Unexpected/><Actions Context="),
        ("</Exec>", "<Environment><Variable>x</Variable></Environment></Exec>"),
        ("</Actions>", "<Exec><Command>other</Command></Exec></Actions>"),
        ("<MultipleInstancesPolicy>IgnoreNew", "<MultipleInstancesPolicy>Parallel"),
    ],
)
def test_complete_definition_drift_is_not_normalized(setup, historical, old, new):
    xml = PREDECESSOR if historical else subject.MaintenanceTask(setup.release).xml
    assert old in xml
    setup.reads.observation = subject.SchedulerObservation(xml=xml.replace(old, new))
    result = plan(setup)
    assert result.status is subject.Status.BLOCKED
    assert result.classification is subject.Classification.UNEXPECTED_EXISTING


@pytest.mark.parametrize(
    "xml",
    [
        PREDECESSOR.replace("<Enabled>true", "<Enabled>false"),
        PREDECESSOR.replace("TimeTrigger", "BootTrigger"),
        PREDECESSOR.replace(
            "2026-10-07T19:55:00.000000Z", "2026-10-07T12:00:00.000000Z"
        ),
        PREDECESSOR.replace(
            "2026-10-07T13:35:00.000000Z", "2026-99-07T13:35:00.000000Z"
        ),
        PREDECESSOR.replace(".000000Z", "+00:00"),
    ],
)
def test_predecessor_requires_complete_reviewed_time_definition(setup, xml):
    setup.reads.observation = subject.SchedulerObservation(xml=xml)
    assert plan(setup).classification is subject.Classification.UNEXPECTED_EXISTING


@pytest.mark.parametrize("source", ["task", "mode", "image"])
def test_repeated_observation_drift(setup, source):
    f = setup
    if source == "task":

        def hook(reads):
            if reads.task_reads == 2:
                reads.observation = subject.SchedulerObservation(xml=PREDECESSOR)

        f.reads.task_hook = hook
    elif source == "mode":

        def hook(reads):
            if reads.mode_reads == 2:
                reads.mode = replace(QUIESCENT, active_bot_process=True)

        f.reads.mode_hook = hook
    else:

        def hook(native, count):
            if count == 2:
                path = native.paths.final
                native.nodes[path] = replace(native.nodes[path], identity=(7, 9999))

        f.native.hook = hook
    result = plan(f)
    assert result.status is subject.Status.BLOCKED
    assert result.reason is subject.Reason.DRIFT


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
def test_cached_evidence_cannot_establish_admission(setup, field):
    value = getattr(setup.installed, field)
    setup.installed = replace(
        setup.installed, **{field: (7, 9999) if isinstance(value, tuple) else "wrong"}
    )
    assert plan(setup).status is subject.Status.BLOCKED
    assert setup.reads.task_reads == 0


@pytest.mark.parametrize(
    "kind", ["binding", "source", "python", "bytes", "missing", "extra"]
)
def test_exact_binding_and_installed_image_replay(setup, kind):
    f = setup
    if kind == "binding":
        other = accepted()
        object.__setattr__(other, "expected_source_head", "c" * 40)
        f.binding = RuntimeBinding(other)
    elif kind == "source":
        object.__setattr__(f.release, "expected_source_tree", "c" * 40)
    elif kind == "python":
        f.native.data[PRODUCTION_PYTHON] = b"drift"
    elif kind == "bytes":
        f.native.data[f.native.paths.child(f.native.paths.final, "pyproject.toml")] += (
            b"x"
        )
    elif kind == "missing":
        f.native.nodes.pop(f.native.paths.child(f.native.paths.final, "pyproject.toml"))
    else:
        f.native.add(
            f.native.paths.child(f.native.paths.final, "extra"), directory=True
        )
    assert plan(f).status is subject.Status.BLOCKED
    assert f.reads.task_reads == 0


def test_plan_has_no_credential_capability_and_sanitizes_failure(setup):
    def fail(_):
        raise RuntimeError("secret native details")

    setup.reads.task_hook = fail
    result = plan(setup)
    assert result.status is subject.Status.BLOCKED
    assert "secret" not in repr(result)


@pytest.mark.parametrize(
    "kind,attempts,intent",
    [
        ("absent", 1, subject.Disposition.ONE_CREATE),
        ("bound", 0, subject.Disposition.READ_ONLY_SUCCESS),
        ("predecessor", 1, subject.Disposition.ONE_REBIND),
        ("unexpected", 0, subject.Disposition.NO_SCHEDULER_EFFECT),
    ],
)
@pytest.mark.parametrize("acknowledgement", [True, False, None, "ambiguous", 1])
def test_inert_future_one_attempt_accounting(
    setup, kind, attempts, intent, acknowledgement
):
    f = setup
    if kind != "absent":
        f.reads.observation = subject.SchedulerObservation(
            xml=(
                PREDECESSOR
                if kind == "predecessor"
                else subject.MaintenanceTask(f.release).xml
                if kind == "bound"
                else "<Task/>"
            )
        )
    budget = subject.MutationAccounting()
    pending = budget.begin(plan(f))
    assert pending.attempts == attempts and pending.disposition is intent
    with pytest.raises(ValueError):
        budget.begin(plan(f))
    if attempts:
        done = budget.finish(independently_verified=acknowledgement)
        assert done.status is (
            subject.Status.VERIFIED
            if acknowledgement is True
            else subject.Status.INDETERMINATE
        )
        assert done.attempts == 1
        assert done.disposition is (
            intent
            if acknowledgement is True
            else subject.Disposition.PRESERVE_SCHEDULER_EVIDENCE_NO_RETRY
        )
        with pytest.raises(ValueError):
            budget.begin(plan(f))
        with pytest.raises(ValueError):
            budget.finish(independently_verified=True)


def test_source_registration_inventory_and_pins():
    spec = runner._checkpoint_specs()[NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-supervised-maintenance-rebind"
    assert runner.ACTIVE_CI_CHECKPOINTS[3] == NAME
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 56
    assert spec.authority_check(ROOT) == ()
    workflow = (ROOT / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert runner._batch_workflow_is_reviewed(workflow)
    inventory = certification.discover_inventory(ROOT)
    profiles = {
        name: certification.select_inventory(inventory, name)
        for name in ("full", "robinhood", "legacy", "exhaustive")
    }
    assert {name: len(modules) for name, modules in profiles.items()} == {
        "full": 156,
        "robinhood": 83,
        "legacy": 205,
        "exhaustive": 361,
    }


def test_import_closure_inert_in_fresh_interpreter():
    code = """
import ctypes, sys
def forbidden(*args, **kwargs):
    raise AssertionError('native access')
ctypes.WinDLL = forbidden
import trading_bot.supervised_release.maintenance
assert 'trading_bot.supervised_release.native_read' not in sys.modules
assert 'trading_bot.supervised_release.native_write' not in sys.modules
assert 'trading_bot.supervised_release.installer' not in sys.modules
assert not any('arch133_scheduler_installation' in name for name in sys.modules)
assert not any('robinhood_mcp' in name for name in sys.modules)
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


def test_read_seams_have_no_forbidden_capabilities():
    assert {
        name for name in subject.SchedulerObserver.__dict__ if not name.startswith("_")
    } == {"observe_fixed_task"}
    assert {
        name for name in subject.ModeObserver.__dict__ if not name.startswith("_")
    } == {"observe_mode"}
    tree = ast.parse(Path(subject.__file__).read_text(encoding="utf-8-sig"))
    forbidden = {
        "run",
        "Popen",
        "WinDLL",
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
        getattr(n.func, "attr", getattr(n.func, "id", ""))
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
    }
    assert not calls & forbidden


@pytest.mark.parametrize(
    "field",
    [
        "task_path",
        "executable",
        "production_root",
        "release_root",
        "launcher",
        "principal",
        "environment",
        "trigger",
        "drive",
        "fallback_target",
    ],
)
def test_no_caller_selected_scheduler_target(setup, field):
    with pytest.raises(TypeError):
        subject.plan_maintenance_rebind(
            setup.release,
            setup.binding,
            setup.installed,
            image_observer=setup.native,
            scheduler_observer=setup.reads,
            mode_observer=setup.reads,
            **{field: "caller-choice"},
        )
    assert not setup.native.events and setup.reads.task_reads == 0


@pytest.mark.parametrize(
    "field",
    ["preflight", "execute", "remote_head_env", "remote_branch", "tests", "ruff_paths"],
)
def test_source_registration_drift_fails_closed(monkeypatch, field):
    specs = runner._checkpoint_specs()
    value = (
        (lambda: {})
        if field in {"preflight", "execute"}
        else ()
        if field in {"tests", "ruff_paths"}
        else "unexpected"
    )
    specs[NAME] = replace(specs[NAME], **{field: value})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert (
        "maintenance source-only registration drift"
        in runner._supervised_maintenance_authority_check(ROOT)
    )


def test_source_pin_drift_fails_closed(monkeypatch):
    monkeypatch.setattr(
        runner,
        "SUPERVISED_MAINTENANCE_PINS",
        {
            "src/trading_bot/supervised_release/maintenance.py": "0" * 40,
        },
    )
    assert (
        "maintenance reviewed source drift"
        in runner._supervised_maintenance_authority_check(ROOT)
    )


def test_scheduler_enabled_in_xml_blocks_before_second_read(setup):
    xml = subject.MaintenanceTask(setup.release).xml.replace(
        "<Enabled>false", "<Enabled>true"
    )
    setup.reads.observation = subject.SchedulerObservation(xml=xml)
    result = plan(setup)
    assert result.status is subject.Status.BLOCKED
    assert result.classification is subject.Classification.RUNNING_OR_ENABLED
    assert setup.reads.task_reads == 1


def test_installed_bytes_drift_after_scheduler_observation(setup):
    def hook(reads):
        if reads.task_reads == 2:
            path = setup.native.paths.child(setup.native.paths.final, "pyproject.toml")
            setup.native.data[path] += b"changed"

    setup.reads.task_hook = hook
    result = plan(setup)
    assert result.status is subject.Status.BLOCKED
    assert result.reason is subject.Reason.DRIFT


def test_no_implicit_native_observer_when_seam_missing(setup):
    result = subject.plan_maintenance_rebind(
        setup.release,
        setup.binding,
        setup.installed,
        image_observer=None,
        scheduler_observer=setup.reads,
        mode_observer=setup.reads,
    )
    assert result.status is subject.Status.BLOCKED
    assert not setup.native.events and setup.reads.task_reads == 0
