"""D1S2 source-only installed-release/manual-start readiness bridge."""

import ast
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
import test_supervised_runtime_host_admission as production_fixtures

from scripts import checkpoint_runner as runner
from trading_bot.review_paper import successor_readiness as subject
from trading_bot.review_paper.successor_soak_contract import (
    PARENT_NAME,
    SESSION_NAMES,
    SESSIONS,
    STORE_IDENTITY,
)
from trading_bot.supervised_release.runtime_isolation import RuntimeAdmissionStatus

ROOT = Path(__file__).resolve().parents[2]
BASE = "88d6a4ba11a77ca4a7b04b102b914e9e4ea9bd96"


class InstallationFake:
    def __init__(self, release, installed, *, classification):
        self.release = release
        self.installed = installed
        self.classification = classification
        self.paths = None
        self.calls = 0

    def observe(self, paths):
        self.calls += 1
        self.paths = paths
        if self.classification is subject.InstallationReadiness.INSTALL_REQUIRED:
            return subject.InstallationObservation(
                subject.InstallationReadiness.INSTALL_REQUIRED,
                subject.InstallationReason.FINAL_AND_STAGING_ABSENT,
                paths.final,
                paths.staging,
            )
        if self.classification is subject.InstallationReadiness.ALREADY_INSTALLED_EXACT:
            return subject.InstallationObservation(
                subject.InstallationReadiness.ALREADY_INSTALLED_EXACT,
                subject.InstallationReason.EXACT_FINAL,
                paths.final,
                paths.staging,
                self.installed.image_identity,
                None,
                self.installed,
            )
        return subject.InstallationObservation(
            self.classification,
            subject.InstallationReason.STAGING_CONFLICT,
            paths.final,
            paths.staging,
        )


class SuccessorFake:
    def __init__(self, *, root=None, process=None):
        self.root = root or subject.SuccessorRootObservation(
            subject.SuccessorStoreClassification.EMPTY_FRESH_ADMITTED,
            identity=(7, 900),
            parent_identity=(7, 800),
        )
        self.process = process
        self.root_reads = 0
        self.process_reads = 0
        self.mutate_after = None

    def observe_root(self):
        self.root_reads += 1
        if self.mutate_after is not None and self.root_reads == 2:
            return self.mutate_after
        return self.root

    def observe_manual_process(self):
        self.process_reads += 1
        return self.process


@pytest.fixture
def setup(monkeypatch):
    source = production_fixtures.setup.__wrapped__(monkeypatch)
    policy = subject.SuccessorSourcePolicy(
        subject.SOURCE_REMOTE,
        "refs/heads/feature/robinhood-production-paper-134f1r1-successor-readiness-current",
        source.release.expected_source_head,
        source.release.expected_source_tree,
        source.release.expected_source_paths,
    )
    installation = InstallationFake(
        source.release,
        source.installed,
        classification=subject.InstallationReadiness.ALREADY_INSTALLED_EXACT,
    )
    successor = SuccessorFake(
        process=subject.ManualProcessObservation(
            100, "windows-filetime:1000", SESSIONS[0]
        )
    )
    boundary = subject.SuccessorReadinessBoundary(
        policy,
        source.release,
        source.binding,
        installation,
        source.native,
        source.runtime,
        successor,
    )
    return boundary, source, installation, successor


def test_positive_readiness_composes_exact_chain_and_zero_effects(setup):
    boundary, source, installation, successor = setup
    result = subject.assess_successor_readiness(boundary)
    assert (
        result.status
        is subject.ReadinessStatus.READY_FOR_D1_SUCCESSOR_INSTALLED_RELEASE_PREFLIGHT
    )
    assert result.reason is subject.ReadinessReason.VERIFIED
    assert result.ready
    assert (
        result.installation.classification
        is subject.InstallationReadiness.ALREADY_INSTALLED_EXACT
    )
    assert result.host.runtime_id == result.lineage.material.runtime_id
    assert result.f1r1_a.status is RuntimeAdmissionStatus.ADMITTED
    assert result.f1r1_b.value == "READY_FOR_F1R1_HOST_QUALIFICATION"
    assert (
        result.store.classification
        is subject.SuccessorStoreClassification.EMPTY_FRESH_ADMITTED
    )
    assert result.store.store_identity is None
    assert result.process.observed_date == SESSIONS[0]
    assert result.manual_start_state == ("RUNNING", "STOPPED", "RUNNING")
    assert result.launcher_runtime_status == subject.LAUNCHER_RUNTIME_STATUS
    assert result.launcher_effect_status == subject.LAUNCHER_EFFECT_STATUS
    assert all(value == 0 for _, value in result.protected_effects)
    assert installation.calls == 1
    assert successor.root_reads == successor.process_reads == 2
    assert not source.native.events or not any(
        event[0] in {"create_directory", "file_create", "write", "publish"}
        for event in source.native.events
    )


def test_install_required_is_read_only_and_does_not_observe_or_create(setup):
    boundary, _, _, successor = setup
    installation = InstallationFake(
        boundary.release,
        None,
        classification=subject.InstallationReadiness.INSTALL_REQUIRED,
    )
    boundary = replace(boundary, installation_observer=installation)
    result = subject.assess_successor_readiness(boundary)
    assert result.status is subject.ReadinessStatus.INSTALL_REQUIRED
    assert result.reason is subject.ReadinessReason.INSTALL_REQUIRED
    assert (
        result.installation.reason
        is subject.InstallationReason.FINAL_AND_STAGING_ABSENT
    )
    assert installation.calls == 1
    assert successor.root_reads == successor.process_reads == 0


@pytest.mark.parametrize(
    "classification",
    [
        subject.InstallationReadiness.BLOCKED,
        subject.InstallationReadiness.INDETERMINATE,
    ],
)
def test_installation_conflicts_fail_closed_without_retry(setup, classification):
    boundary, _, _, successor = setup
    installation = InstallationFake(
        boundary.release, None, classification=classification
    )
    boundary = replace(boundary, installation_observer=installation)
    result = subject.assess_successor_readiness(boundary)
    expected = (
        subject.ReadinessStatus.BLOCKED
        if classification is subject.InstallationReadiness.BLOCKED
        else subject.ReadinessStatus.INDETERMINATE
    )
    assert result.status is expected
    assert result.installation.classification is classification
    assert installation.calls == 1
    assert successor.root_reads == successor.process_reads == 0


@pytest.mark.parametrize(
    "classification",
    [
        subject.SuccessorStoreClassification.ABSENT_ELIGIBLE,
        subject.SuccessorStoreClassification.CONFLICTING_FOREIGN,
        subject.SuccessorStoreClassification.ALIAS_OR_REPARSE,
        subject.SuccessorStoreClassification.WRONG_PARENT_OR_POLICY,
        subject.SuccessorStoreClassification.REPLACED_OBJECT,
        subject.SuccessorStoreClassification.CONSUMED,
        subject.SuccessorStoreClassification.MALFORMED,
    ],
)
def test_successor_root_states_never_satisfy_d1_readiness(setup, classification):
    boundary, _, _, successor = setup
    successor.root = subject.SuccessorRootObservation(classification)
    result = subject.assess_successor_readiness(boundary)
    assert result.status is subject.ReadinessStatus.BLOCKED
    assert result.reason is subject.ReadinessReason.SUCCESSOR_STORE_NOT_READY
    assert result.store.classification is classification


def test_successor_root_indeterminate_is_not_promoted(setup):
    boundary, _, _, successor = setup
    successor.root = subject.SuccessorRootObservation(
        subject.SuccessorStoreClassification.INDETERMINATE
    )
    result = subject.assess_successor_readiness(boundary)
    assert result.status is subject.ReadinessStatus.INDETERMINATE
    assert result.reason is subject.ReadinessReason.SUCCESSOR_STORE_UNPROVEN


def test_bound_successor_namespace_requires_exact_store_identity(setup):
    boundary, _, _, successor = setup
    successor.root = subject.SuccessorRootObservation(
        subject.SuccessorStoreClassification.ALREADY_BOUND_EXACT,
        identity=(7, 901),
        parent_identity=(7, 800),
        names=(PARENT_NAME, *SESSION_NAMES),
        store_identity=STORE_IDENTITY,
        evidence_complete=True,
    )
    result = subject.assess_successor_readiness(boundary)
    assert result.ready

    successor.root = replace(
        successor.root, store_identity=replace(STORE_IDENTITY, sha256="f" * 64)
    )
    result = subject.assess_successor_readiness(boundary)
    assert result.status is subject.ReadinessStatus.BLOCKED


def test_replaced_root_is_detected_between_read_only_observations(setup):
    boundary, _, _, successor = setup
    successor.mutate_after = replace(
        successor.root, identity=(7, 901), parent_identity=(7, 800)
    )
    result = subject.assess_successor_readiness(boundary)
    assert result.status is subject.ReadinessStatus.BLOCKED
    assert result.reason is subject.ReadinessReason.SUCCESSOR_STORE_DRIFT


def test_source_policy_and_complete_bundle_are_not_inferred_from_image(setup):
    boundary, source, _, _ = setup
    with pytest.raises(ValueError):
        subject.SuccessorReleaseDeclaration(
            replace(boundary.source_policy, accepted_head="c" * 40),
            boundary.release,
            boundary.binding,
        )
    incomplete = replace(
        boundary.source_policy,
        source_paths=boundary.source_policy.source_paths[:-1],
    )
    result = subject.assess_successor_readiness(
        replace(boundary, source_policy=incomplete)
    )
    assert result.status is subject.ReadinessStatus.BLOCKED
    assert source.release.manifest.source_inventory


def test_exact_production_paths_and_runtime_substrate_are_required(setup):
    boundary, _, installation, _ = setup
    original = installation.observe

    def wrong_paths(paths):
        value = original(paths)
        return replace(value, final_path=paths.final + "\\foreign")

    installation.observe = wrong_paths
    result = subject.assess_successor_readiness(boundary)
    assert result.status is subject.ReadinessStatus.BLOCKED
    assert result.reason is subject.ReadinessReason.INSTALLATION_BLOCKED
    installation.observe = original

    boundary.runtime_observer.process = replace(
        boundary.runtime_observer.process, working_directory=r"F:\AI\ai-trading-bot"
    )
    result = subject.assess_successor_readiness(boundary)
    assert result.status is subject.ReadinessStatus.BLOCKED


def test_c2_and_old_f1_namespaces_cannot_substitute(setup):
    boundary, _, _, successor = setup
    for path in (
        r"F:\AI\temp\qualification\arch134-f1r1-host-isolation",
        r"F:\AI\temp\qualification",
        r"F:\AI\worktrees\ai-trading-bot-production-paper-134f-five-session-soak",
    ):
        successor.root = replace(
            successor.root,
            classification=subject.SuccessorStoreClassification.CONFLICTING_FOREIGN,
            path=path,
        )
        result = subject.assess_successor_readiness(boundary)
        assert result.status is subject.ReadinessStatus.BLOCKED


def test_launcher_remains_no_argument_inert_and_effect_closed():
    launcher = (
        ROOT / "scripts/run_arch133_supervised_release_review_paper.py"
    ).read_text()
    assert "if sys.argv[1:]" in launcher
    assert "HOST_FAILED_CLOSED" in launcher
    assert "requests" not in launcher and "socket" not in launcher
    tree = ast.parse(launcher)
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"resume", "retry", "repair", "main"}
        for node in ast.walk(tree)
    )


def test_readiness_module_has_no_effectful_or_historical_imports():
    path = ROOT / "src/trading_bot/review_paper/successor_readiness.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imports |= {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    forbidden = {
        "ctypes",
        "requests",
        "socket",
        "sqlite3",
        "subprocess",
        "trading_bot.supervised_release.installer",
        "trading_bot.supervised_release.installation_operator",
        "trading_bot.supervised_release.native_write",
        "trading_bot.arch133_scheduler_installation",
        "trading_bot.arch133_scheduler_installation.operator",
        "trading_bot.review_paper.successor_soak",
        "trading_bot.review_paper.d1_session_execution",
    }
    assert not imports & forbidden
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name
        in {"install", "publish", "execute", "resume", "retry", "repair", "main"}
        for node in ast.walk(tree)
    )


def test_d1s1_predecessor_source_identity_remains_exact():
    for relative in (
        "src/trading_bot/supervised_release/model.py",
        "src/trading_bot/supervised_release/binding.py",
        "src/trading_bot/supervised_release/bundle.py",
        "src/trading_bot/supervised_release/installation_contract.py",
        "src/trading_bot/supervised_release/runtime_admission.py",
        "src/trading_bot/supervised_release/runtime_host_composition.py",
        "src/trading_bot/supervised_release/runtime_isolation.py",
    ):
        expected = subprocess.run(
            ["git", "rev-parse", BASE + ":" + relative],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        actual = subprocess.run(
            ["git", "hash-object", relative],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert actual == expected


def test_manual_start_policy_has_no_scheduler_or_resume_surface():
    module = (ROOT / "src/trading_bot/review_paper/successor_readiness.py").read_text()
    tree = ast.parse(module)
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any("scheduler" in item.lower() for item in imports)
    assert "--resume" not in module
    assert "Task Scheduler" not in module
    assert subject.ZERO_PROTECTED_EFFECTS[-1] == ("LIVE_EFFECTS", 0)


def test_d1s2_checkpoint_registration_and_predecessor_overlay():
    spec = runner._checkpoint_specs()[runner.ARCH134_D1S2_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == runner.ARCH134_D1S2_BRANCH
    assert runner.resolve_ci_certification_profile(spec.name) == "robinhood"
    assert runner._arch134_d1s2_active_inventory() == runner.ACTIVE_CI_CHECKPOINTS
    assert runner._arch134_d1s2_authority_check(ROOT) == ()
    assert runner.ARCH134_D1S1_PREDECESSOR_PINS_SHA256 == (
        "fe37fa5dde15617ca7814b2dc28b9d8c4b0bdb801eff860cac48c35b11d21d62"
    )
    assert runner.ARCH134_D1S1_SUCCESSOR_PINS_SHA256 == (
        "8d343d995082ed0589ed3cae52704275a15480a6f574e16ca1b9710537f47ac4"
    )


def test_removing_d1s2_overlay_restores_d1s1_resolution(monkeypatch):
    path = "docs/PROJECT_STATUS.md"
    predecessor = runner.ARCH134_D1S2_PREDECESSOR_PINS[path]
    assert (
        runner._arch134_d1s2_current_source_pin(path, predecessor)
        == (runner.ARCH134_D1S2_SUCCESSOR_PINS[path])
    )
    monkeypatch.setattr(runner, "ARCH134_D1S2_SUCCESSOR_PINS", None)
    assert runner._arch134_d1s2_current_source_pin(path, predecessor) == predecessor

    source_path = "tests/review_paper/test_arch134_f1r1_d1s1_successor_soak.py"
    source_predecessor = runner.ARCH134_D1S2_SOURCE_PREDECESSOR_PINS[source_path]
    monkeypatch.setattr(runner, "ARCH134_D1S2_SOURCE_PINS", None)
    assert runner._arch134_d1s2_source_pin(source_path, source_predecessor) == (
        source_predecessor
    )
