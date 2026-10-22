"""D1S3 successor installation operator source-only tests."""

import ast
import inspect
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_supervised_release_installation import accepted

from scripts import checkpoint_runner as runner
from trading_bot.review_paper import successor_readiness
from trading_bot.review_paper.successor_readiness import (
    InstallationObservation,
    InstallationReadiness,
    InstallationReason,
    ReadinessStatus,
    SuccessorReleaseDeclaration,
    SuccessorRootObservation,
    SuccessorSourcePolicy,
    SuccessorStoreClassification,
)
from trading_bot.review_paper.successor_soak_contract import (
    PARENT_NAME,
    SESSION_NAMES,
    STORE_IDENTITY,
)
from trading_bot.supervised_release import successor_installation_operator as subject
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.installation_contract import (
    InstallDisposition,
    InstalledEvidence,
    InstallReason,
    InstallResult,
    InstallStatus,
)

ROOT = Path(__file__).resolve().parents[2]
BASE_HEAD = "2b697b79e6bdbc964d2b0414ced057628e6c2da7"
BASE_TREE = "e510210070874ade43a240457645939650e457d8"


class InstallationFake:
    def __init__(self, declaration, classifications):
        self.declaration = declaration
        self.classifications = list(classifications)
        self.calls = 0

    def observe(self, paths):
        self.calls += 1
        classification = self.classifications[
            min(self.calls - 1, len(self.classifications) - 1)
        ]
        if classification is InstallationReadiness.INSTALL_REQUIRED:
            return InstallationObservation(
                classification,
                InstallationReason.FINAL_AND_STAGING_ABSENT,
                paths.final,
                paths.staging,
            )
        if classification is InstallationReadiness.ALREADY_INSTALLED_EXACT:
            evidence = InstalledEvidence(
                self.declaration.release_id,
                self.declaration.manifest_sha256,
                self.declaration.binding.sha256,
                (7, 800),
                (7, 801),
                (7, 802),
            )
            return InstallationObservation(
                classification,
                InstallationReason.EXACT_FINAL,
                paths.final,
                paths.staging,
                final_identity=evidence.image_identity,
                installed_evidence=evidence,
            )
        return InstallationObservation(
            classification,
            InstallationReason.STAGING_CONFLICT,
            paths.final,
            paths.staging,
        )


class RootFake:
    def __init__(self, root):
        self.root = root
        self.calls = 0

    def observe_root(self):
        self.calls += 1
        return self.root


def make_boundary(*, installation=None, root=None):
    release = accepted()
    binding = RuntimeBinding(release)
    policy = SuccessorSourcePolicy(
        subject.SOURCE_REMOTE,
        subject.SOURCE_REF,
        release.expected_source_head,
        release.expected_source_tree,
        release.expected_source_paths,
    )
    declaration = SuccessorReleaseDeclaration(policy, release, binding)
    installation = installation or InstallationFake(
        declaration, [InstallationReadiness.INSTALL_REQUIRED]
    )
    root = root or RootFake(
        SuccessorRootObservation(SuccessorStoreClassification.ABSENT_ELIGIBLE)
    )
    return subject.D1S3Boundary(
        declaration,
        installation,
        object(),
        object(),
        root,
    )


def test_exact_predecessor_identity_and_fixed_effect_boundary():
    assert subject.BASE_HEAD == BASE_HEAD
    assert subject.SOURCE_REMOTE == "https://github.com/callmedraken/ai-trading-bot.git"
    assert subject.SOURCE_REF == "refs/heads/" + subject.BRANCH
    assert subject.ATTEMPT_PATH == Path(
        r"F:\AI\temp\arch134-f1r1-d1s3-installation-attempt\attempt.json"
    )
    assert all(value == 0 for _, value in subject.ZERO_PROTECTED_EFFECTS)


def test_d1s2_modules_are_not_modified_by_successor_operator():
    paths = (
        "src/trading_bot/review_paper/successor_readiness.py",
        "src/trading_bot/review_paper/successor_soak_contract.py",
        "src/trading_bot/review_paper/successor_soak_store.py",
        "src/trading_bot/review_paper/successor_soak_admission.py",
    )
    for relative in paths:
        base = (
            subprocess.run(
                ["git", "-C", str(ROOT), "rev-parse", f"{BASE_HEAD}:{relative}"],
                check=True,
                capture_output=True,
            )
            .stdout.decode()
            .strip()
        )
        current = runner._git_blob_sha1(ROOT / relative)
        assert current == base


def test_install_required_preflight_is_closed_and_read_only(tmp_path):
    boundary = make_boundary()
    attempt = tmp_path / "attempt.json"
    before = subject.observe_attempt(attempt)
    result = subject.assess_d1s3_preflight(boundary, attempt=before)
    assert result.status is subject.OperatorStatus.PASS
    assert result.reason is subject.OperatorReason.INSTALL_REQUIRED
    assert result.execute_eligible
    assert result.attempt.state is subject.AttemptState.AVAILABLE
    assert not attempt.exists()
    assert boundary.installation_observer.calls == 1
    assert boundary.successor_observer.calls == 1


def test_already_installed_exact_never_becomes_execute_eligible(tmp_path):
    release = accepted()
    binding = RuntimeBinding(release)
    policy = SuccessorSourcePolicy(
        subject.SOURCE_REMOTE,
        subject.SOURCE_REF,
        release.expected_source_head,
        release.expected_source_tree,
        release.expected_source_paths,
    )
    declaration = SuccessorReleaseDeclaration(policy, release, binding)
    installation = InstallationFake(
        declaration, [InstallationReadiness.ALREADY_INSTALLED_EXACT]
    )
    boundary = make_boundary(installation=installation)
    result = subject.assess_d1s3_preflight(boundary)
    assert result.status is subject.OperatorStatus.PASS
    assert result.reason is subject.OperatorReason.ALREADY_INSTALLED_EXACT
    assert not result.execute_eligible

    calls = []
    outcome = subject.execute_installation(
        boundary,
        authorization=subject.AUTH_VALUE,
        attempt_path=tmp_path / "attempt.json",
        installer=lambda *_: calls.append(True),
    )
    assert outcome["effect_disposition"] == "NOT_STARTED"
    assert calls == []


def test_exact_existing_successor_root_routes_only_through_d1s2_readiness(
    monkeypatch,
):
    declaration = make_boundary().declaration
    installation = InstallationFake(
        declaration, [InstallationReadiness.ALREADY_INSTALLED_EXACT]
    )
    root = RootFake(
        SuccessorRootObservation(
            SuccessorStoreClassification.ALREADY_BOUND_EXACT,
            identity=(7, 901),
            parent_identity=(7, 800),
            names=(PARENT_NAME, *SESSION_NAMES),
            store_identity=STORE_IDENTITY,
            evidence_complete=True,
        )
    )
    boundary = make_boundary(installation=installation, root=root)
    calls = []

    def readiness(readiness_boundary):
        calls.append(readiness_boundary)
        return SimpleNamespace(
            status=ReadinessStatus.READY_FOR_D1_SUCCESSOR_INSTALLED_RELEASE_PREFLIGHT,
        )

    monkeypatch.setattr(subject, "assess_successor_readiness", readiness)
    result = subject.assess_d1s3_preflight(boundary)
    assert result.status is subject.OperatorStatus.PASS
    assert result.reason is subject.OperatorReason.ALREADY_INSTALLED_EXACT
    assert not result.execute_eligible
    assert len(calls) == 1


@pytest.mark.parametrize(
    "classification",
    [
        InstallationReadiness.BLOCKED,
        InstallationReadiness.INDETERMINATE,
    ],
)
def test_installation_conflicts_fail_closed(classification):
    boundary = make_boundary(
        installation=InstallationFake(
            make_boundary().declaration,
            [classification],
        )
    )
    result = subject.assess_d1s3_preflight(boundary)
    assert result.status is (
        subject.OperatorStatus.BLOCKED
        if classification is InstallationReadiness.BLOCKED
        else subject.OperatorStatus.INDETERMINATE
    )
    assert not result.execute_eligible


def test_successful_install_consumes_durable_latch_and_reobserves(tmp_path):
    declaration = make_boundary().declaration
    installation = InstallationFake(
        declaration,
        [
            InstallationReadiness.INSTALL_REQUIRED,
            InstallationReadiness.ALREADY_INSTALLED_EXACT,
        ],
    )
    root = RootFake(
        SuccessorRootObservation(SuccessorStoreClassification.ABSENT_ELIGIBLE)
    )
    boundary = subject.D1S3Boundary(declaration, installation, object(), object(), root)
    evidence = InstalledEvidence(
        declaration.release_id,
        declaration.manifest_sha256,
        declaration.binding.sha256,
        (7, 800),
        (7, 801),
        (7, 802),
    )
    calls = []

    def installer(release, binding):
        calls.append((release, binding))
        return InstallResult(
            InstallStatus.INSTALLED_VERIFIED,
            InstallDisposition.VERIFIED,
            InstallReason.VERIFIED,
            evidence,
        )

    attempt = tmp_path / "attempt.json"
    outcome = subject.execute_installation(
        boundary,
        authorization=subject.AUTH_VALUE,
        attempt_path=attempt,
        installer=installer,
    )
    assert outcome["status"] == "READY_FOR_D1_SUCCESSOR_ROOT_PROVISIONING_REVIEW"
    assert outcome["effect_disposition"] == "CONFIRMED"
    assert len(calls) == 1
    assert subject.observe_attempt(attempt).state is subject.AttemptState.CONSUMED
    assert root.calls == 2


def test_post_entry_exception_is_consumed_indeterminate_and_not_retryable(tmp_path):
    declaration = make_boundary().declaration
    boundary = make_boundary(
        installation=InstallationFake(
            declaration,
            [InstallationReadiness.INSTALL_REQUIRED],
        )
    )
    attempt = tmp_path / "attempt.json"
    calls = []

    def installer(*_):
        calls.append(True)
        raise RuntimeError("injected post-entry failure")

    first = subject.execute_installation(
        boundary,
        authorization=subject.AUTH_VALUE,
        attempt_path=attempt,
        installer=installer,
    )
    second = subject.execute_installation(
        boundary,
        authorization=subject.AUTH_VALUE,
        attempt_path=attempt,
        installer=installer,
    )
    assert first["status"] == "INDETERMINATE"
    assert first["effect_disposition"] == "MAY_HAVE_OCCURRED"
    assert second["effect_disposition"] == "NOT_STARTED"
    assert len(calls) == 1


def test_authorization_rejection_is_pre_entry_and_does_not_create_latch(tmp_path):
    calls = []
    attempt = tmp_path / "attempt.json"
    result = subject.execute_installation(
        make_boundary(),
        authorization="wrong",
        attempt_path=attempt,
        installer=lambda *_: calls.append(True),
    )
    assert result["status"] == "BLOCKED"
    assert result["effect_disposition"] == "NOT_STARTED"
    assert not attempt.exists()
    assert calls == []


def test_ack_identity_mismatch_is_indeterminate_and_preserves_attempt(tmp_path):
    declaration = make_boundary().declaration
    boundary = make_boundary(
        installation=InstallationFake(
            declaration,
            [
                InstallationReadiness.INSTALL_REQUIRED,
            ],
        )
    )
    bad = InstalledEvidence(
        "f" * 32,
        declaration.manifest_sha256,
        declaration.binding.sha256,
        (7, 800),
        (7, 801),
        (7, 802),
    )
    result = subject.execute_installation(
        boundary,
        authorization=subject.AUTH_VALUE,
        attempt_path=tmp_path / "attempt.json",
        installer=lambda *_: InstallResult(
            InstallStatus.INSTALLED_VERIFIED,
            InstallDisposition.VERIFIED,
            InstallReason.VERIFIED,
            bad,
        ),
    )
    assert result["status"] == "INDETERMINATE"
    assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"


def test_source_admission_and_capability_boundaries_are_explicit():
    source = inspect.getsource(subject)
    tree = ast.parse(source)
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    forbidden = (
        "trading_bot.robinhood_mcp",
        "trading_bot.credentials",
        "trading_bot.broker",
        "trading_bot.scheduler",
        "trading_bot.live",
        "trading_bot.review_paper.successor_soak_store",
    )
    assert not any(name in imports for name in forbidden)
    assert (
        "from trading_bot.supervised_release import installation_operator" not in source
    )
    assert "run_arch133_supervised_release_review_paper" not in source
    assert not any(
        module in imports
        for module in (
            "trading_bot.robinhood_mcp",
            "trading_bot.scheduler",
            "trading_bot.provider",
            "trading_bot.broker",
            "trading_bot.credentials",
            "trading_bot.live",
            "trading_bot.review_paper.successor_soak_store",
        )
    )


def test_registration_is_exact_and_protected_execute_is_not_called():
    spec = runner._checkpoint_specs()[runner.ARCH134_D1S3_NAME]
    assert spec.remote_branch == subject.BRANCH
    assert spec.remote_head_env == subject.REMOTE_HEAD_ENV
    assert spec.preflight is runner._arch134_d1s3_preflight
    assert spec.execute is runner._arch134_d1s3_execute
    assert runner.CI_CERTIFICATION_PROFILES[runner.ARCH134_D1S3_NAME] == "robinhood"
    assert spec.tests[-1].endswith("d1s3_successor_installation_operator.py")
    assert spec.ruff_paths[-2].endswith("successor_installation_operator.py")


def test_successor_readiness_still_has_no_effect_capability():
    assert "install_release" not in inspect.getsource(successor_readiness)
    assert all(value == 0 for _, value in subject.ZERO_PROTECTED_EFFECTS)


def test_current_document_exception_is_exact_and_predecessor_maps_are_unchanged():
    assert runner.ARCH134_D1S3_MUTABLE_CURRENT_DOCS == (
        "docs/PROJECT_STATUS.md",
        "docs/AI_TRADING_BOT_HANDOFF.md",
    )
    assert all(
        path not in runner.ARCH134_D1S3_SHARED_SUCCESSOR_PINS
        and path not in runner.ARCH134_D1S3_SOURCE_PINS
        for path in runner.ARCH134_D1S3_MUTABLE_CURRENT_DOCS
    )
    assert not runner._arch134_d1s3_mutable_current_doc(
        "docs/architecture/134-f1r1-d1s3-successor-release-installation-operator.md"
    )

    predecessor = subprocess.run(
        ["git", "show", f"{BASE_HEAD}:scripts/checkpoint_runner.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    current = (ROOT / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    before_nodes = {
        node.target.id: node
        for node in ast.parse(predecessor).body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id.startswith("ARCH134_D1S2_")
        and ("PREDECESSOR" in node.target.id or "SHA256" in node.target.id)
    }
    current_nodes = {
        node.target.id: node
        for node in ast.parse(current).body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert before_nodes
    assert all(
        ast.dump(node, include_attributes=False)
        == ast.dump(current_nodes[name], include_attributes=False)
        for name, node in before_nodes.items()
    )


def test_current_document_wording_can_change_without_blob_authority(monkeypatch):
    original = runner._git_blob_sha1

    def changed_current_doc(path):
        if str(path).replace("/", "\\").endswith("docs\\PROJECT_STATUS.md"):
            return "0" * 40
        if str(path).replace("/", "\\").endswith("docs\\AI_TRADING_BOT_HANDOFF.md"):
            return "1" * 40
        return original(path)

    monkeypatch.setattr(runner, "_git_blob_sha1", changed_current_doc)
    assert runner._arch134_d1s3_authority_check(ROOT) == ()


def test_other_pinned_paths_and_arbitrary_docs_remain_fail_closed(monkeypatch):
    original = runner._git_blob_sha1
    target = next(iter(runner.ARCH134_D1S3_SHARED_SUCCESSOR_PINS))

    def changed_shared(path):
        if str(path).replace("/", "\\").endswith(target.replace("/", "\\")):
            return "a" * 40
        return original(path)

    monkeypatch.setattr(runner, "_git_blob_sha1", changed_shared)
    assert runner._arch134_d1s3_authority_check(ROOT)
    monkeypatch.undo()

    monkeypatch.setattr(
        runner,
        "ARCH134_D1S3_MUTABLE_CURRENT_DOCS",
        (*runner.ARCH134_D1S3_MUTABLE_CURRENT_DOCS, "docs/architecture/foreign.md"),
    )
    assert runner._arch134_d1s3_authority_check(ROOT)


def test_removing_d1s3_overlay_restores_d1s2_fail_closed_behavior(monkeypatch):
    monkeypatch.setattr(runner, "ARCH134_D1S3_ACTIVE_CI_CHECKPOINTS_SHA256", "")
    monkeypatch.setattr(runner, "ARCH134_D1S3_MUTABLE_CURRENT_DOCS", ())
    monkeypatch.setattr(runner, "ARCH134_D1S3_SHARED_SUCCESSOR_PINS", {})
    monkeypatch.setattr(runner, "ARCH134_D1S3_SOURCE_PINS", {})
    monkeypatch.setattr(runner, "ARCH134_D1S3_RUNNER_AST_PINS", {})
    assert runner._arch134_d1s2_authority_check(ROOT)
