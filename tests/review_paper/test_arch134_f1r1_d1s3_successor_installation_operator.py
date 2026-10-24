"""D1S3 successor installation operator source-only tests."""

import ast
import inspect
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_supervised_runtime_host_admission as production_fixtures
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
    IMAGE_ACES,
    InstallDisposition,
    InstalledEvidence,
    InstallReason,
    InstallResult,
    InstallStatus,
)

production_setup = production_fixtures.setup

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


def test_d1s2_semantic_refinement_is_exact_and_d1s1_modules_remain_frozen():
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
        if relative.endswith("/successor_readiness.py"):
            assert current == runner.ARCH134_D1S3_SHARED_SUCCESSOR_PINS[relative]
        else:
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
    assert result.reason is subject.OperatorReason.SUCCESSOR_ROOT_PROVISIONING_REVIEW
    assert (
        result.to_dict()["readiness_status"]
        == "READY_FOR_D1_SUCCESSOR_ROOT_PROVISIONING_REVIEW"
    )
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
            names=(PARENT_NAME, SESSION_NAMES[0]),
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
        assert subject.observe_attempt(attempt).state is subject.AttemptState.CONSUMED
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


@pytest.mark.parametrize("rejected", ["source", "administrator", "boundary", None])
def test_execute_prerequisite_order(monkeypatch, tmp_path, rejected):
    boundary, events = make_boundary(), []
    attempt = tmp_path / "attempt.json"
    observe = subject.observe_attempt
    monkeypatch.setattr(subject, "observe_attempt", lambda: observe(attempt))

    def call(step, value, *args, **kwargs):
        events.append(step)
        if step == rejected:
            raise RuntimeError("pre-entry rejection")
        if args:
            assert args == (
                (boundary.declaration,) if step == "boundary" else (boundary,)
            )
        if step == "execute":
            assert kwargs == {"authorization": None}
        return value

    monkeypatch.delenv(subject.AUTH_ENV, raising=False)
    for name, step, value in (
        ("derive_successor_declaration", "source", boundary.declaration),
        ("_administrator_host", "administrator", None),
        ("_protected_boundary", "boundary", boundary),
        ("execute_installation", "execute", {"status": "dispatch"}),
    ):
        monkeypatch.setattr(
            subject, name, lambda *a, s=step, v=value, **kw: call(s, v, *a, **kw)
        )
    for name in ("consume_attempt", "install_release"):
        monkeypatch.setattr(subject, name, lambda *_: pytest.fail("unexpected effect"))
    result = runner._arch134_d1s3_execute()
    order = ["source", "administrator", "boundary", "execute"]
    assert events == (order if rejected is None else order[: order.index(rejected) + 1])
    if rejected is None:
        assert result == {"status": "dispatch"}
    else:
        assert result["status"] == "BLOCKED"
        assert result["effect_disposition"] == "NOT_STARTED"
    assert not attempt.exists()


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


def test_arch145a_source_removal_restores_predecessor_failure(monkeypatch):
    monkeypatch.setattr(runner, "ARCH145A_SOURCE_PIN_OVERRIDES", {})
    assert runner._arch144c_authority_check(ROOT)


@pytest.mark.parametrize(
    ("attribute", "path"),
    [
        (
            "ARCH144C_PREDECESSOR_SOURCE_PINS",
            "scripts/run_test_certification.py",
        ),
        (
            "ARCH144C_PREDECESSOR_TEST_PINS",
            "tests/runtime/checkpoint_runner/test_core.py",
        ),
        (
            "ARCH134_F1R1_C1_PREDECESSOR_SOURCE_PINS",
            "scripts/run_test_certification.py",
        ),
        (
            "ARCH134_F1R1_C1_PREDECESSOR_TEST_PINS",
            "tests/runtime/checkpoint_runner/test_core.py",
        ),
        (
            "ARCH134_F1R1_B_PREDECESSOR_SOURCE_PINS",
            "scripts/run_test_certification.py",
        ),
        (
            "ARCH134_F1R1_B_PREDECESSOR_TEST_PINS",
            "tests/runtime/checkpoint_runner/test_core.py",
        ),
        (
            "ARCH134_D1S2_PREDECESSOR_PINS",
            "tests/runtime/checkpoint_runner/test_core.py",
        ),
        (
            "ARCH134_D1S2_SOURCE_PREDECESSOR_PINS",
            "tests/review_paper/test_arch134_f1r1_d1s1_successor_soak.py",
        ),
    ],
)
def test_d1s3_authority_requires_each_predecessor_overlay(
    monkeypatch: pytest.MonkeyPatch, attribute: str, path: str
) -> None:
    pins = dict(getattr(runner, attribute))
    pins[path] = "a" * 40
    monkeypatch.setattr(runner, attribute, pins)
    assert runner._arch134_d1s3_authority_check(ROOT)


def test_removing_d1s3_overlay_restores_d1s2_fail_closed_behavior(monkeypatch):
    monkeypatch.setattr(runner, "ARCH134_D1S3_ACTIVE_CI_CHECKPOINTS_SHA256", "")
    monkeypatch.setattr(runner, "ARCH134_D1S3_MUTABLE_CURRENT_DOCS", ())
    monkeypatch.setattr(runner, "ARCH134_D1S3_SHARED_SUCCESSOR_PINS", {})
    monkeypatch.setattr(runner, "ARCH134_D1S3_SOURCE_PINS", {})
    monkeypatch.setattr(runner, "ARCH134_D1S3_RUNNER_AST_PINS", {})
    assert runner._arch134_d1s2_authority_check(ROOT)


class RootReadFake:
    """Only logical fixed-path read facts; disposable D1 bytes are copied in."""

    def __init__(self, harness, *, absent=False):
        from trading_bot.arch133_acl.read_only import ADMIN_ACES
        from trading_bot.supervised_release.installation_contract import ObjectFacts
        from trading_bot.supervised_release.model import DURABLE_DATA_ROOT

        self.h = harness
        self.nodes = dict(harness.source.native.nodes)
        self.nodes[DURABLE_DATA_ROOT] = ObjectFacts(
            DURABLE_DATA_ROOT,
            "directory",
            (7, 800),
            IMAGE_ACES[0][0],
            True,
            ADMIN_ACES,
        )
        if not absent:
            self.nodes[subject.PRODUCTION_ROOT] = ObjectFacts(
                subject.PRODUCTION_ROOT,
                "directory",
                (7, 900),
                IMAGE_ACES[0][0],
                True,
                IMAGE_ACES,
            )
        self.payloads = {}
        self.events = []
        self.extra_names = ()
        self.sync()

    def sync(self):
        from dataclasses import replace

        root = self.nodes.get(subject.PRODUCTION_ROOT)
        if root is None:
            return
        for index, name in enumerate((PARENT_NAME, *SESSION_NAMES), 1):
            data = self.h.storage.read(name)
            if data is not None:
                path = subject.PRODUCTION_ROOT + "\\" + name
                self.payloads[path] = data
                self.nodes[path] = replace(
                    root,
                    path=path,
                    kind="file",
                    identity=(7, 900 + index),
                    size=len(data),
                )

    def read_session(self):
        from contextlib import nullcontext

        return nullcontext(self)

    def object(self, path, *, directory):
        self.events.append(("object", path))
        return self.nodes.get(path)

    def names(self, path):
        self.events.append(("names", path))
        assert path == subject.PRODUCTION_ROOT
        return (
            tuple(
                name
                for name in (PARENT_NAME, *SESSION_NAMES)
                if path + "\\" + name in self.payloads
            )
            + self.extra_names
        )

    def read(self, path, limit):
        self.events.append(("read", path))
        data = self.payloads[path]
        assert len(data) <= limit
        return data


class ManualRuntimeFake:
    def __init__(self, harness, ownership=None):
        from trading_bot.supervised_release.successor_native_read import Ownership

        self.h = harness
        self.ownership = ownership or Ownership.CURRENT_EXACT
        self.owners = []

    def observe_process(self):
        return self.h.source.runtime.observe_process()

    def observe_substrate(self):
        return self.h.source.runtime.observe_substrate()

    def observe_manual_process(self):
        return self.h.observations.process

    def observe_owner(self, process):
        from trading_bot.supervised_release.successor_native_read import Ownership

        self.owners.append(process)
        return (
            self.ownership
            if process == self.h.observations.process
            else Ownership.GONE_OR_MISMATCHED
        )


@pytest.fixture
def native_harness(production_setup, tmp_path, monkeypatch):
    import test_arch134_f1r1_d1s1_successor_soak as d1

    from trading_bot.supervised_release import observer
    from trading_bot.supervised_release import successor_native_read as native

    h = d1.harness.__wrapped__(production_setup, tmp_path, monkeypatch)
    monkeypatch.setattr(native, "hashlib", observer.hashlib)
    declaration = SuccessorReleaseDeclaration(
        SuccessorSourcePolicy(
            subject.SOURCE_REMOTE,
            subject.SOURCE_REF,
            h.source.release.expected_source_head,
            h.source.release.expected_source_tree,
            h.source.release.expected_source_paths,
        ),
        h.source.release,
        h.source.binding,
    )
    return h, declaration, d1, native


def root_adapter(native_harness, *, ownership=None, absent=False):
    h, declaration, _, native = native_harness
    reader = RootReadFake(h, absent=absent)
    runtime = ManualRuntimeFake(h, ownership)
    observer = native.NativeSuccessorRootObserver(
        declaration,
        runtime,
        reader=reader,
        image_observer=h.source.native,
    )
    return observer, reader, runtime


def test_native_factory_is_inert_and_supplies_all_real_observers(
    native_harness, monkeypatch
):
    _, declaration, _, native = native_harness
    monkeypatch.setattr(
        native,
        "windows_libraries",
        lambda: pytest.fail("native read during construction"),
    )
    boundary = subject._protected_boundary(declaration)
    assert boundary.declaration is declaration
    assert isinstance(
        boundary.installation_observer, subject.InstallationNativeObserver
    )
    assert isinstance(boundary.runtime_observer, native.NativeRuntimeObserver)
    assert isinstance(boundary.successor_observer, native.NativeSuccessorRootObserver)
    assert boundary.installation_observer._native is boundary.image_observer


def test_native_empty_and_absent_root_are_read_only(native_harness):
    _, _, _, native = native_harness
    for absent, classification in (
        (False, SuccessorStoreClassification.EMPTY_FRESH_ADMITTED),
        (True, SuccessorStoreClassification.ABSENT_ELIGIBLE),
    ):
        observer, reader, runtime = root_adapter(native_harness, absent=absent)
        before = dict(reader.nodes), dict(reader.payloads)
        first = observer.observe_root()
        assert first.classification is classification
        assert observer.observe_root() == first
        assert before == (reader.nodes, reader.payloads)
        assert runtime.owners == []
        assert not hasattr(reader, "reserve") and not hasattr(reader, "write")
        assert isinstance(observer._reader, RootReadFake)
    assert native.D1S3ReadSession.__bases__[0].__name__ == "WindowsReadSession"


def test_native_absent_root_requires_exact_admin_system_only_parent(native_harness):
    observer, reader, _ = root_adapter(native_harness, absent=True)
    value = observer.observe_root()
    assert value.classification is SuccessorStoreClassification.ABSENT_ELIGIBLE
    assert value.parent_identity == reader.nodes[subject.DURABLE_DATA_ROOT].identity


def test_native_exact_admin_system_only_parent_reaches_install_required_assessment(
    native_harness,
):
    h, declaration, _, _ = native_harness
    root, _, runtime = root_adapter(native_harness, absent=True)
    installation = InstallationFake(
        declaration, [InstallationReadiness.INSTALL_REQUIRED]
    )
    boundary = subject.D1S3Boundary(
        declaration,
        installation,
        h.source.native,
        runtime,
        root,
    )
    result = subject.assess_d1s3_preflight(
        boundary,
        attempt=subject.AttemptObservation(subject.AttemptState.AVAILABLE, "inert"),
    )
    assert result.status is subject.OperatorStatus.PASS
    assert result.reason is subject.OperatorReason.INSTALL_REQUIRED
    assert result.execute_eligible
    assert result.attempt.state is subject.AttemptState.AVAILABLE


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("owner", "foreign"),
        ("protected", False),
        ("aces", ()),
        ("aces", IMAGE_ACES),
        ("reparse", True),
        ("links", 2),
        ("local", False),
        ("filesystem", "ReFS"),
        ("persistent_acls", False),
        ("identity", (8, 800)),
        ("identity", (7, 0)),
    ],
)
def test_native_durable_parent_policy_is_closed(native_harness, field, value):
    observer, reader, _ = root_adapter(native_harness, absent=True)
    reader.nodes[subject.DURABLE_DATA_ROOT] = replace(
        reader.nodes[subject.DURABLE_DATA_ROOT], **{field: value}
    )
    result = observer.observe_root()
    assert result.classification is SuccessorStoreClassification.WRONG_PARENT_OR_POLICY
    assert not result.stable


def test_native_successor_root_retains_immutable_image_policy(native_harness):
    from trading_bot.arch133_acl.read_only import ADMIN_ACES

    observer, reader, _ = root_adapter(native_harness)
    reader.nodes[subject.PRODUCTION_ROOT] = replace(
        reader.nodes[subject.PRODUCTION_ROOT], aces=ADMIN_ACES
    )
    result = observer.observe_root()
    assert result.classification is SuccessorStoreClassification.WRONG_PARENT_OR_POLICY


@pytest.mark.parametrize(
    "disposition", ["NO_SIGNAL", "RISK_REJECTED", "PAPER_REQUIRED"]
)
def test_native_progression_requires_actual_parent_child_replay(
    native_harness, disposition
):
    h, _, d1, _ = native_harness
    d1.start(h, d1.contract.QuoteDisposition(disposition))
    observer, reader, runtime = root_adapter(native_harness)
    root = observer.observe_root()
    assert root.classification is SuccessorStoreClassification.ALREADY_BOUND_EXACT
    assert root.names == (PARENT_NAME, SESSION_NAMES[0])
    assert root.store_identity == STORE_IDENTITY and root.evidence_complete
    assert not root.consumed and not root.malformed
    assert runtime.owners == []
    assert any(event[0] == "read" for event in reader.events)


@pytest.mark.parametrize("ordinal", [1, 2])
@pytest.mark.parametrize(
    "ownership", ["CURRENT_EXACT", "GONE_OR_MISMATCHED", "UNPROVEN"]
)
def test_native_active_reservation_binds_ordinal_process_and_grant_prefix(
    native_harness, ordinal, ownership
):
    h, _, d1, native = native_harness
    if ordinal == 2:
        d1.start(h)
        d1.second_process(h)
    observations = []

    def quote():
        observer, _, runtime = root_adapter(
            native_harness, ownership=native.Ownership(ownership)
        )
        result = observer.observe_root()
        observations.append(result)
        assert runtime.owners == [h.observations.process]
        return d1.contract.QuoteDisposition.NO_SIGNAL

    d1.start(h, quote=quote)
    result = observations[0]
    assert (
        result.classification
        is {
            "CURRENT_EXACT": SuccessorStoreClassification.ACTIVE_CURRENT_EXACT,
            "GONE_OR_MISMATCHED": SuccessorStoreClassification.CONSUMED,
            "UNPROVEN": SuccessorStoreClassification.INDETERMINATE,
        }[ownership]
    )
    assert result.names == (
        (PARENT_NAME, SESSION_NAMES[0])
        if ordinal == 1
        else (PARENT_NAME, *SESSION_NAMES)
    )
    assert result.consumed is (ownership == "GONE_OR_MISMATCHED")


@pytest.mark.parametrize("halted", [False, True])
def test_native_terminal_replay_is_consumed_not_malformed(native_harness, halted):
    h, _, d1, _ = native_harness
    if halted:
        d1.start(h, guard=lambda: False)
    else:
        d1.start(h)
        d1.second_process(h)
        d1.start(h)
    observer, _, runtime = root_adapter(native_harness)
    root = observer.observe_root()
    assert root.classification is SuccessorStoreClassification.CONSUMED
    assert root.consumed and root.evidence_complete and not root.malformed
    assert runtime.owners == []


@pytest.mark.parametrize(
    "mutation", ["partial", "foreign", "fake_names", "grant_prefix", "runtime_identity"]
)
def test_native_noncanonical_or_false_evidence_never_promotes_filenames(
    native_harness, mutation
):
    import json

    h, _, d1, _ = native_harness
    d1.start(h)
    observer, reader, _ = root_adapter(native_harness)
    parent = subject.PRODUCTION_ROOT + "\\" + PARENT_NAME
    child = subject.PRODUCTION_ROOT + "\\" + SESSION_NAMES[0]
    if mutation == "partial":
        reader.payloads[parent] = reader.payloads[parent][:-1]
    elif mutation == "fake_names":
        reader.payloads[parent] = b"{}\n{}\n"
        reader.payloads[child] = b"{}\n{}\n"
    elif mutation == "grant_prefix":
        rows = [json.loads(line) for line in reader.payloads[child].splitlines()]
        rows[0]["grant_prefix"] = "f" * 64
        reader.payloads[child] = b"".join(
            d1.contract.canonical(row) + b"\n" for row in rows
        )
    elif mutation == "runtime_identity":
        reader.payloads[parent] = reader.payloads[parent].replace(
            b'"store_identity":[7,900]', b'"store_identity":[7,999]'
        )
    else:
        reader.payloads[parent] = reader.payloads[parent].replace(
            b'"kind":"PARENT"', b'"kind":"FOREIGN"'
        )
    root = observer.observe_root()
    assert root.classification is SuccessorStoreClassification.MALFORMED
    assert root.malformed


def test_native_alias_policy_foreign_names_and_replacement_reject(native_harness):
    from dataclasses import replace

    h, _, d1, _ = native_harness
    d1.start(h)
    observer, reader, _ = root_adapter(native_harness)
    baseline = observer.observe_root()
    assert baseline.classification is SuccessorStoreClassification.ALREADY_BOUND_EXACT
    reader.nodes[subject.PRODUCTION_ROOT] = replace(
        reader.nodes[subject.PRODUCTION_ROOT], identity=(7, 999)
    )
    assert (
        observer.observe_root().classification
        is SuccessorStoreClassification.REPLACED_OBJECT
    )
    for field, value, classification in (
        ("reparse", True, SuccessorStoreClassification.ALIAS_OR_REPARSE),
        ("links", 2, SuccessorStoreClassification.ALIAS_OR_REPARSE),
        ("owner", "foreign", SuccessorStoreClassification.WRONG_PARENT_OR_POLICY),
    ):
        observer, reader, _ = root_adapter(native_harness)
        reader.nodes[subject.PRODUCTION_ROOT] = replace(
            reader.nodes[subject.PRODUCTION_ROOT], **{field: value}
        )
        assert observer.observe_root().classification is classification
    observer, reader, _ = root_adapter(native_harness)
    reader.extra_names = ("old-f1.jsonl",)
    assert (
        observer.observe_root().classification
        is SuccessorStoreClassification.CONFLICTING_FOREIGN
    )


@pytest.mark.parametrize(
    "path",
    [
        r"F:\AI\temp\qualification\arch134-f1r1-host-isolation",
        r"F:\AITradingBot\Arch133\old-f1",
        subject.PRODUCTION_ROOT + r"\..\foreign",
        subject.PRODUCTION_ROOT.lower(),
        subject.PRODUCTION_ROOT + r"\successor-parent-v1.jsonl:alias",
    ],
)
def test_native_paths_exclude_historical_and_aliased_roots(native_harness, path):
    _, _, _, native = native_harness
    with pytest.raises(ValueError):
        native.D1S3ReadPaths().admit(path)


@pytest.mark.parametrize("installed", [False, True])
def test_registered_preflight_reaches_native_installation_only_boundary(
    native_harness, monkeypatch, installed
):
    from trading_bot.supervised_release import native_read

    h, declaration, _, native = native_harness
    if not installed:
        final = declaration.binding.to_dict()["release_root"]
        h.source.native.nodes = {
            path: row
            for path, row in h.source.native.nodes.items()
            if path != final and not path.startswith(final + "\\")
        }
    reader = RootReadFake(h, absent=True)
    before = dict(h.source.native.nodes), dict(reader.nodes), dict(reader.payloads)
    monkeypatch.setattr(subject, "_administrator_host", lambda: None)
    monkeypatch.setattr(subject, "derive_successor_declaration", lambda: declaration)
    monkeypatch.setattr(
        subject,
        "observe_attempt",
        lambda: subject.AttemptObservation(
            subject.AttemptState.AVAILABLE, str(subject.ATTEMPT_PATH)
        ),
    )
    monkeypatch.setattr(native_read, "WindowsObserver", lambda: h.source.native)
    monkeypatch.setattr(native, "D1S3NativeReader", lambda declaration: reader)
    monkeypatch.setattr(
        native.NativeRuntimeObserver,
        "observe_substrate",
        lambda *_: pytest.fail("fabricated runtime"),
    )
    monkeypatch.setattr(
        subject.subprocess, "run", lambda *a, **kw: pytest.fail("process start")
    )
    result = runner._arch134_d1s3_preflight()
    assert result["status"] == "PASS"
    assert result["effect_disposition"] == "NOT_STARTED"
    assert result["primary"]["execute_eligible"] is (not installed)
    assert result["primary"]["installation_classification"] == (
        "ALREADY_INSTALLED_EXACT" if installed else "INSTALL_REQUIRED"
    )
    if installed:
        assert (
            result["primary"]["readiness_status"]
            == "READY_FOR_D1_SUCCESSOR_ROOT_PROVISIONING_REVIEW"
        )
    assert before == (h.source.native.nodes, reader.nodes, reader.payloads)
    assert all(count == 0 for _, count in result["primary"]["protected_effects"])


@pytest.mark.parametrize("progressed", [False, True])
def test_full_native_root_composition_requires_real_applicable_runtime_facts(
    native_harness, progressed
):
    h, declaration, d1, _ = native_harness
    if progressed:
        d1.start(h)
        d1.second_process(h)
    root, _, runtime = root_adapter(native_harness)
    boundary = subject.D1S3Boundary(
        declaration,
        subject.InstallationNativeObserver(
            declaration.release, declaration.binding, h.source.native
        ),
        h.source.native,
        runtime,
        root,
    )
    result = subject.assess_d1s3_preflight(
        boundary,
        attempt=subject.AttemptObservation(subject.AttemptState.AVAILABLE, "inert"),
    )
    assert result.readiness.ready
    assert (
        result.readiness.process.observed_date
        == d1.contract.SESSIONS[1 if progressed else 0]
    )
    assert not result.execute_eligible
    h.source.runtime.process = replace(
        h.source.runtime.process,
        executable=r"F:\AI\ai-trading-bot\.venv\Scripts\python.exe",
    )
    result = subject.assess_d1s3_preflight(
        boundary,
        attempt=subject.AttemptObservation(subject.AttemptState.AVAILABLE, "inert"),
    )
    assert result.status is subject.OperatorStatus.BLOCKED
    assert not result.readiness.ready and result.readiness.manual_start_state is None


def test_native_runtime_never_selects_mutable_or_arbitrary_python(
    native_harness, monkeypatch
):
    _, declaration, _, native = native_harness
    runtime = native.NativeRuntimeObserver(declaration)
    monkeypatch.setattr(
        native,
        "windows_libraries",
        lambda: pytest.fail("native access before mutable rejection"),
    )
    for observe in (
        runtime.observe_process,
        runtime.observe_substrate,
        runtime.observe_manual_process,
    ):
        with pytest.raises(ValueError, match="current process"):
            observe()


def test_native_adapter_capability_surface_is_read_only(native_harness):
    _, _, _, native = native_harness
    text = inspect.getsource(native)
    tree = ast.parse(text)
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    function_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    forbidden = {
        "mkdir",
        "unlink",
        "rename",
        "write_bytes",
        "write_text",
        "reserve",
        "Popen",
        "run",
        "start",
        "CreateProcessW",
        "WriteFile",
        "CreateDirectoryW",
        "SetSecurityInfo",
        "CreateServiceW",
    }
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls & forbidden
    assert '"OpenProcess"' in text and '"GetProcessTimes"' in text
    assert '"CreateProcess' not in text
    assert "installation_operator" not in text
    assert "ROOT_ACES" not in text
    assert "arch133_reprovision_recovery" not in text
    assert not function_names & {
        "create_directory",
        "write_file",
        "repair",
        "provision",
    }
    assert "trading_bot.arch133_reprovision_recovery" not in imports
    assert "trading_bot.arch133_acl.root_policy_apply" not in imports


@pytest.mark.parametrize(
    "case,expected",
    [
        ("current", "CURRENT_EXACT"),
        ("pid_reuse", "GONE_OR_MISMATCHED"),
        ("exited", "GONE_OR_MISMATCHED"),
        ("mutable_image", "GONE_OR_MISMATCHED"),
        ("other_live", "UNPROVEN"),
        ("denied", "UNPROVEN"),
        ("gone", "GONE_OR_MISMATCHED"),
        ("oversized_pid", "UNPROVEN"),
    ],
)
def test_native_owner_probe_queries_only_exact_replayed_pid(
    native_harness, monkeypatch, case, expected
):
    _, _, d1, native = native_harness
    calls = []
    process = d1.admission.ManualProcessObservation(
        2**40 if case == "oversized_pid" else 100,
        "windows-filetime:1000",
        d1.contract.SESSIONS[0],
    )

    def opened(access, inherit, pid):
        calls.append((access, inherit, pid))
        assert access == 0x1000 and not inherit and pid == process.pid
        return None if case in {"denied", "gone"} else 42

    def times(handle, creation, *rest):
        creation._obj.value = 1001 if case == "pid_reuse" else 1000
        return 1

    def exit_code(handle, code):
        code._obj.value = 0 if case == "exited" else 259
        return 1

    def image(handle, flags, text, size):
        text.value = (
            r"F:\AI\mutable\python.exe"
            if case == "mutable_image"
            else native.PRODUCTION_PYTHON
        )
        return 1

    functions = {
        "OpenProcess": opened,
        "GetProcessTimes": times,
        "GetExitCodeProcess": exit_code,
        "QueryFullProcessImageNameW": image,
        "CloseHandle": lambda h: calls.append(("close", h)) or 1,
    }
    monkeypatch.setattr(native, "windows_libraries", lambda: (object(), object()))
    monkeypatch.setattr(native, "bind", lambda lib, name, args, result: functions[name])
    monkeypatch.setattr(
        native,
        "close_native_handle",
        lambda kernel, handle: functions["CloseHandle"](handle),
    )
    monkeypatch.setattr(
        native.ctypes, "get_last_error", lambda: 87 if case == "gone" else 5
    )
    monkeypatch.setattr(
        native.os, "getpid", lambda: 101 if case == "other_live" else 100
    )
    assert native.observe_exact_owner(process) is native.Ownership(expected)
    if case == "oversized_pid":
        assert calls == []
    elif case not in {"gone", "denied"}:
        assert calls[-1] == ("close", 42)


def test_native_runtime_collects_closed_current_process_and_substrate(
    native_harness, monkeypatch
):
    from contextlib import nullcontext

    from trading_bot.arch133_verifier.token import TradingTokenObservation
    from trading_bot.supervised_release.installation_contract import (
        IMAGE_ACES,
        ObjectFacts,
        ReleasePaths,
    )
    from trading_bot.supervised_release.runtime_admission import (
        RuntimeStatus,
        admit_runtime_host,
    )

    h, declaration, _, native = native_harness
    final = ReleasePaths(declaration.release_id).final
    launcher = (
        final
        + "\\"
        + declaration.release.manifest.launcher_relative_path.replace("/", "\\")
    )
    nodes = {}
    for index, row in enumerate(h.source.runtime.substrate.objects, 1):
        nodes[row.path] = ObjectFacts(
            row.path, row.kind.value, (7, 100 + index), row.owner_sid, True, IMAGE_ACES
        )

    class RuntimeReader:
        def read_session(self):
            return nullcontext(self)

        def object(self, path, *, directory):
            return nodes.get(path)

        def names(self, path):
            prefix = path + "\\"
            return tuple(
                key[len(prefix) :]
                for key in nodes
                if key.startswith(prefix) and "\\" not in key[len(prefix) :]
            )

    state = SimpleNamespace(
        platform="win32",
        executable=native.PRODUCTION_PYTHON,
        argv=[launcher],
        orig_argv=[native.PRODUCTION_PYTHON, "-I", "-S", "-B", launcher],
        flags=SimpleNamespace(isolated=1, no_site=1),
        dont_write_bytecode=True,
        pycache_prefix=native.NO_PYCACHE,
        version_info=(3, 14, 3),
        path=[
            final + r"\src",
            native.SITE_PACKAGES,
            native.LIB_ROOT,
            native.RUNTIME_ROOT,
        ],
        modules={
            "sys": SimpleNamespace(__spec__=SimpleNamespace(origin="built-in")),
            "trading_bot": SimpleNamespace(
                __file__=final + r"\src\trading_bot\__init__.py"
            ),
        },
    )
    token = TradingTokenObservation(native.TRADING_SID, 1, False, False, ())
    monkeypatch.setattr(native, "sys", state)
    monkeypatch.setattr(native.os, "getcwd", lambda: final)
    monkeypatch.setattr(
        native,
        "WindowsTradingTokenObserver",
        lambda: SimpleNamespace(observe=lambda: token),
    )
    runtime = native.NativeRuntimeObserver(
        declaration, reader=RuntimeReader(), image_observer=h.source.native
    )
    result = admit_runtime_host(
        declaration.release,
        declaration.binding,
        h.source.installed,
        image_observer=h.source.native,
        runtime_observer=runtime,
    )
    assert result.status is RuntimeStatus.VERIFIED
    process = runtime.observe_process()
    substrate = runtime.observe_substrate()
    assert process.executable == native.PRODUCTION_PYTHON
    assert process.project_modules_complete and not process.site_main_called
    assert substrate.inventory_complete and substrate.dependencies_complete
    assert substrate.before_fingerprint == substrate.after_fingerprint
    state.orig_argv = [r"F:\AI\mutable\python.exe", launcher]
    with pytest.raises(ValueError):
        runtime.observe_process()


def test_native_empty_root_namespace_drift_is_not_admitted(native_harness):
    observer, reader, _ = root_adapter(native_harness)
    calls = 0
    original = reader.names

    def drift(path):
        nonlocal calls
        calls += 1
        return original(path) if calls == 1 else ("foreign.jsonl",)

    reader.names = drift
    assert (
        observer.observe_root().classification
        is SuccessorStoreClassification.REPLACED_OBJECT
    )


def test_native_overlay_validates_d1s2_own_source_predecessor_before_substitution(
    monkeypatch,
):
    pins = dict(runner.ARCH134_D1S2_SOURCE_PINS)
    pins["src/trading_bot/review_paper/successor_readiness.py"] = "a" * 40
    monkeypatch.setattr(runner, "ARCH134_D1S2_SOURCE_PINS", pins)
    assert runner._arch134_d1s2_authority_check(ROOT)
    assert runner._arch134_d1s3_authority_check(ROOT)


def test_native_runtime_paths_admit_canonical_timezone_data_not_ads(native_harness):
    _, _, _, native = native_harness
    path = native.SITE_PACKAGES + r"\tzdata\zoneinfo\Etc\GMT+10"
    assert native.D1S3ReadPaths().admit(path) == path
    for tail in ("file:stream", "file.", "file ", "CON .txt", "part\\..\\foreign"):
        with pytest.raises(ValueError):
            native.D1S3ReadPaths().admit(native.RUNTIME_ROOT + "\\" + tail)


def test_native_unreadable_root_remains_closed_indeterminate(native_harness):
    observer, reader, _ = root_adapter(native_harness)

    def unreadable():
        raise PermissionError("private host error must not escape")

    reader.read_session = unreadable
    value = observer.observe_root()
    assert value.classification is SuccessorStoreClassification.INDETERMINATE
    assert not value.stable and not value.evidence_complete
