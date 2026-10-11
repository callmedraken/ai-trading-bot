from __future__ import annotations

import ast
import ctypes
import hashlib
import json
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import checkpoint_runner as runner
from trading_bot.supervised_release import native_publication as native
from trading_bot.supervised_release import publication_recovery as subject
from trading_bot.supervised_release.installation_contract import ReleasePaths

NAME = "arch133-robinhood-supervised-release-publication-recovery"


def fail():
    raise RuntimeError("private native details")


def setup_image(monkeypatch):
    calls = []
    paths = ReleasePaths(subject.incident.EXPECTED_RELEASE_ID)
    release = SimpleNamespace(
        expected_source_head=subject.incident.FAILED_AG_HEAD,
        expected_source_tree=subject.incident.FAILED_AG_TREE,
    )
    binding = object()
    evidence = subject.expected_image()
    parent = SimpleNamespace(identity=evidence.parent_identity)
    image = SimpleNamespace(identity=evidence.image_identity)
    state = {
        "final": False,
        "staging": True,
        "names": (paths.release_id + ".installing",),
    }

    def namespace(p):
        assert p == paths
        calls.append("namespace")
        return (
            parent,
            state["names"],
            image if state["final"] else None,
            image if state["staging"] else None,
        )

    def observe(r, b, *, native):
        assert r is release and b is binding
        calls.append("observe-final" if state["final"] else "observe-staging")
        return evidence

    def publish(e):
        assert e == evidence
        calls.append("publish")
        state.update(final=True, staging=False, names=(paths.release_id,))
        return True

    def consume(mark):
        calls.append("latch")
        mark()

    monkeypatch.setattr(subject, "_records", lambda: calls.append("records"))
    monkeypatch.setattr(
        subject.incident,
        "read_incident_record",
        lambda path, limit: subject.ATTEMPT_BYTES,
    )
    monkeypatch.setattr(
        subject.incident, "require_administrator_host", lambda: calls.append("host")
    )
    monkeypatch.setattr(
        subject.incident,
        "reconstruct_failed_release",
        lambda: (release, binding, paths),
    )
    monkeypatch.setattr(subject, "latch_consumed", lambda: False)
    monkeypatch.setattr(subject, "_namespace", namespace)
    monkeypatch.setattr(subject, "observe_staging_release", observe)
    monkeypatch.setattr(subject, "observe_installed_release", observe)
    monkeypatch.setattr(subject, "_consume", consume)
    monkeypatch.setattr(native, "publish_preserved_image", publish)
    monkeypatch.setenv(subject.AUTH_ENV, subject.AUTH_VALUE)
    return calls, state, evidence, release, paths


def test_exact_staging_preflight_has_zero_effect(monkeypatch):
    calls, _, evidence, _, _ = setup_image(monkeypatch)
    result = subject.preflight(lambda: calls.append("source"))
    assert result["status"] == "PASS"
    assert result["primary"]["status"] == "READY"
    assert result["primary"]["reason"] == "EXACT_STAGING_ONLY"
    assert result["primary"]["image_identity"] == evidence.image_identity
    assert result["effect_disposition"] == "NOT_STARTED"
    assert calls.count("observe-staging") == 2
    assert calls.count("source") == 2
    assert "latch" not in calls and "publish" not in calls


def test_success_is_one_publication_after_latch_and_independent_final_replays(
    monkeypatch,
):
    calls, _, evidence, _, _ = setup_image(monkeypatch)
    result = subject.execute_once(lambda: calls.append("source"))
    assert result["status"] == "PASS"
    assert result["primary"] == {
        "status": "FINAL_PUBLISHED_VERIFIED",
        "reason": "EXACT_FINAL_ONLY",
        "disposition": "VERIFIED",
        **asdict(evidence),
    }
    assert result["effect_disposition"] == "CONFIRMED"
    assert result["automatic_retry"] == "NOT_AUTHORIZED"
    assert calls.count("publish") == 1 and calls.count("latch") == 1
    assert calls.index("latch") < calls.index("publish") < calls.index("observe-final")
    assert calls.count("observe-final") == 2
    assert calls.count("source") == 4


@pytest.mark.parametrize("final,staging", [(True, True), (True, False), (False, False)])
def test_final_conflicts_and_missing_staging_block_before_latch(
    monkeypatch, final, staging
):
    calls, state, _, _, _ = setup_image(monkeypatch)
    state.update(final=final, staging=staging)
    result = subject.execute_once(lambda: None)
    assert result["status"] == "BLOCKED"
    assert result["effect_disposition"] == "NOT_STARTED"
    assert "latch" not in calls and "publish" not in calls


@pytest.mark.parametrize("phase", ["records", "host", "source", "staging", "latch"])
def test_before_latch_failures_are_zero_publication(monkeypatch, phase):
    calls, _, _, _, _ = setup_image(monkeypatch)

    def admit():
        pass

    if phase == "records":
        monkeypatch.setattr(subject, "_records", fail)
    elif phase == "host":
        monkeypatch.setattr(subject.incident, "require_administrator_host", fail)
    elif phase == "source":
        admit = fail
    elif phase == "staging":
        monkeypatch.setattr(subject, "observe_staging_release", lambda *a, **k: fail())
    else:
        monkeypatch.setattr(subject, "_consume", lambda mark: fail())
    result = subject.execute_once(admit)
    assert result["status"] == "BLOCKED"
    assert result["primary"]["disposition"] == "NO_PUBLICATION_EFFECT"
    assert "publish" not in calls
    assert "private" not in str(result)


@pytest.mark.parametrize(
    "phase",
    [
        "flush",
        "close",
        "rename",
        "false",
        "final",
        "staging-present",
        "namespace",
        "records",
        "source",
        "interrupt",
        "exit",
    ],
)
def test_every_post_fence_ambiguity_preserves_without_retry(monkeypatch, phase):
    calls, state, _, _, paths = setup_image(monkeypatch)
    admit_count = 0

    def admit():
        nonlocal admit_count
        admit_count += 1
        if phase == "source" and admit_count == 4:
            fail()

    original_publish = native.publish_preserved_image
    if phase == "flush":

        def consume(mark):
            calls.append("latch")
            mark()
            fail()

        monkeypatch.setattr(subject, "_consume", consume)
    else:

        def publish(e):
            if phase in {"rename", "interrupt", "exit"}:
                calls.append("publish")
                raise {
                    "rename": RuntimeError,
                    "interrupt": KeyboardInterrupt,
                    "exit": SystemExit,
                }[phase]()
            result = original_publish(e)
            if phase == "close":
                fail()
            if phase == "false":
                return False
            if phase == "staging-present":
                state["staging"] = True
            if phase == "namespace":
                state["names"] = (paths.release_id, "release-" + "1" * 32)
            return result

        monkeypatch.setattr(native, "publish_preserved_image", publish)
    if phase == "final":
        monkeypatch.setattr(
            subject, "observe_installed_release", lambda *a, **k: fail()
        )
    if phase == "records":

        def records():
            if "latch" in calls:
                fail()

        monkeypatch.setattr(subject, "_records", records)
    result = subject.execute_once(admit)
    assert result["status"] == "INDETERMINATE"
    assert result["primary"]["disposition"] == "PRESERVE_PUBLICATION_EVIDENCE_NO_RETRY"
    assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"
    assert result["automatic_retry"] == "NOT_AUTHORIZED"
    assert calls.count("publish") <= 1
    assert "private" not in str(result)


def test_native_true_without_final_never_succeeds(monkeypatch):
    calls, _, _, _, _ = setup_image(monkeypatch)
    monkeypatch.setattr(
        native, "publish_preserved_image", lambda e: calls.append("publish") or True
    )
    assert subject.execute_once(lambda: None)["status"] == "INDETERMINATE"
    assert calls.count("publish") == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("image_identity", (1855336320, 1)),
        ("parent_identity", (1855336320, 1)),
        ("python_identity", (1855336320, 1)),
        ("python_version", "3.14.4"),
        ("python_sha256", "0" * 64),
        ("manifest_sha256", "0" * 64),
        ("binding_sha256", "0" * 64),
        ("release_id", "release-" + "1" * 32),
    ],
)
def test_image_evidence_drift_blocks(monkeypatch, field, value):
    calls, _, evidence, _, _ = setup_image(monkeypatch)
    monkeypatch.setattr(
        subject,
        "observe_staging_release",
        lambda *a, **k: replace(evidence, **{field: value}),
    )
    assert subject.preflight(lambda: None)["status"] == "BLOCKED"
    assert "latch" not in calls


def test_repeated_observations_must_agree(monkeypatch):
    _, _, evidence, _, _ = setup_image(monkeypatch)
    sequence = iter((evidence, replace(evidence, image_identity=(1, 2))))
    monkeypatch.setattr(
        subject, "observe_staging_release", lambda *a, **k: next(sequence)
    )
    assert subject.preflight(lambda: None)["status"] == "BLOCKED"


def test_namespace_drift_blocks(monkeypatch):
    _, _, _, _, _ = setup_image(monkeypatch)
    original = subject._namespace
    count = 0

    def namespace(paths):
        nonlocal count
        count += 1
        value = original(paths)
        return value if count == 1 else (value[0], (), value[2], value[3])

    monkeypatch.setattr(subject, "_namespace", namespace)
    assert subject.preflight(lambda: None)["status"] == "BLOCKED"


def test_ag_source_drift_blocks(monkeypatch):
    calls, _, _, release, paths = setup_image(monkeypatch)
    release.expected_source_tree = "0" * 40
    assert subject.execute_once(lambda: None)["status"] == "BLOCKED"
    assert "latch" not in calls
    release.expected_source_tree = subject.incident.FAILED_AG_TREE
    sequence = iter(((release, object(), paths), (object(), object(), paths)))
    monkeypatch.setattr(
        subject.incident, "reconstruct_failed_release", lambda: next(sequence)
    )
    monkeypatch.setattr(subject, "_image", lambda *a, **k: subject.expected_image())
    assert subject.preflight(lambda: None)["status"] == "BLOCKED"


def test_consumed_aj_latch_never_retries_even_after_success(monkeypatch):
    calls, _, _, _, _ = setup_image(monkeypatch)
    monkeypatch.setattr(subject, "latch_consumed", lambda: True)
    assert subject.execute_once(lambda: None)["status"] == "INDETERMINATE"
    assert subject.preflight(lambda: None)["status"] == "INDETERMINATE"
    assert not calls


def test_missing_authorization_blocks_before_any_effect(monkeypatch):
    calls, _, _, _, _ = setup_image(monkeypatch)
    monkeypatch.delenv(subject.AUTH_ENV)
    assert subject.execute_once(lambda: None)["status"] == "BLOCKED"
    assert not calls


def test_durable_latch_is_exclusive_and_not_ag_latch(tmp_path, monkeypatch):
    attempt = tmp_path / "aj.json"
    ag = tmp_path / "ag.json"
    ag.write_bytes(subject.incident.ATTEMPT_BYTES)
    monkeypatch.setattr(subject, "ATTEMPT_PATH", attempt)
    marks = []
    subject._consume(lambda: marks.append("consumed"))
    assert attempt.read_bytes() == subject.ATTEMPT_BYTES
    assert marks == ["consumed"]
    assert ag.read_bytes() == subject.incident.ATTEMPT_BYTES
    with pytest.raises(FileExistsError):
        subject._consume(lambda: pytest.fail("second fence forbidden"))
    assert attempt.read_bytes() == subject.ATTEMPT_BYTES


def test_flush_failure_preserves_consumed_latch(tmp_path, monkeypatch):
    attempt = tmp_path / "aj.json"
    monkeypatch.setattr(subject, "ATTEMPT_PATH", attempt)
    monkeypatch.setattr(subject.os, "fsync", lambda fd: fail())
    marks = []
    with pytest.raises(RuntimeError):
        subject._consume(lambda: marks.append("consumed"))
    assert marks == ["consumed"] and attempt.exists()
    assert subject.latch_consumed()


def test_exact_incident_records_and_evidence_bytes_are_required(tmp_path, monkeypatch):
    ag = tmp_path / "ag.json"
    ai = tmp_path / "ai.json"
    ag.write_bytes(b"original AG failure")
    primary = {
        "status": "STAGING_VERIFIED_PRESERVED",
        "reason": "EXACT_STAGING_ONLY",
        "disposition": "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY",
        **asdict(subject.expected_image()),
    }
    ai.write_bytes(json.dumps({"result": {"primary": primary}}).encode())
    monkeypatch.setattr(subject.incident, "REPORT_PATH", ag)
    monkeypatch.setattr(subject, "AI_REPORT_PATH", ai)
    monkeypatch.setattr(
        subject, "AG_REPORT_SHA256", hashlib.sha256(ag.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(
        subject, "AI_REPORT_SHA256", hashlib.sha256(ai.read_bytes()).hexdigest()
    )
    calls = []
    monkeypatch.setattr(
        subject.incident, "admit_failed_installation", lambda: calls.append("AG")
    )
    subject._records()
    assert calls == ["AG"]
    ai.write_bytes(ai.read_bytes() + b" ")
    with pytest.raises(ValueError):
        subject._records()
    monkeypatch.setattr(
        subject, "AI_REPORT_SHA256", hashlib.sha256(ai.read_bytes()).hexdigest()
    )
    ag.write_bytes(b"other AG failure")
    with pytest.raises(ValueError):
        subject._records()


def test_fixed_real_incident_pins():
    assert subject.STAGING_IDENTITY == (1855336320, 281474980566367)
    assert (
        subject.AI_REPORT_SHA256
        == "f620f13a9d9cac6caeda36205b47b68f849fe1c4ac7c337df18fc795d56d6e45"
    )
    assert (
        subject.AG_REPORT_SHA256
        == "ac1c51bc7dc30dde655efe64570f1ed301586e742dfe0bd0e47f2bc12c1d8560"
    )
    assert subject.ATTEMPT_PATH != subject.incident.ATTEMPT_PATH
    assert subject.ATTEMPT_PATH == Path(
        r"F:\AI\temp\arch133-aj-publication-recovery-attempt.json"
    )


@pytest.mark.parametrize(
    "names",
    [
        (),
        ("other.installing",),
        ("bogus",),
        ("release-" + "1" * 32, "RELEASE-" + "1" * 32),
    ],
)
def test_namespace_aliases_or_missing_staging_name_rejected(monkeypatch, names):
    paths = ReleasePaths(subject.incident.EXPECTED_RELEASE_ID)
    parent = SimpleNamespace(identity=subject.incident.EXPECTED_PARENT_IDENTITY)

    class Session:
        def names(self, path):
            return names

        def object(self, path, *, directory):
            return (
                None
                if path == paths.final
                else SimpleNamespace(identity=subject.STAGING_IDENTITY)
            )

    class Observer:
        @contextmanager
        def read_session(self, p):
            yield Session()

    monkeypatch.setattr(subject, "WindowsObserver", Observer)
    monkeypatch.setattr(subject, "observe_parent", lambda session: parent)
    with pytest.raises(ValueError):
        subject._namespace(paths)


def test_publication_native_has_no_materialization_and_exact_paths(monkeypatch):
    monkeypatch.setattr(
        native.WindowsReadSession,
        "__init__",
        lambda self, paths: setattr(self, "paths", paths),
    )
    session = native.PublicationSession()
    assert session.paths == ReleasePaths(subject.incident.EXPECTED_RELEASE_ID)
    for name in (
        "create_directory",
        "write_file",
        "seal_staging",
        "install_session",
        "unlink",
        "replace",
    ):
        assert not hasattr(session, name)
    with pytest.raises(TypeError):
        native.PublicationSession(ReleasePaths(subject.incident.EXPECTED_RELEASE_ID))


def test_native_rename_is_one_no_replace_handle_relative_request(monkeypatch):
    paths = ReleasePaths(subject.incident.EXPECTED_RELEASE_ID)
    session = object.__new__(native.PublicationSession)
    session.paths = paths
    session.publication_requested = False
    session.kernel = object()
    session.handles = {paths.staging: 41, str(Path(paths.final).parent): 42}
    from trading_bot.supervised_release.model import RELEASES_BASE

    session.handles[RELEASES_BASE] = 42
    image = SimpleNamespace(identity=subject.STAGING_IDENTITY)
    parent = SimpleNamespace(identity=subject.incident.EXPECTED_PARENT_IDENTITY)
    monkeypatch.setattr(native, "observe_parent", lambda s: parent)
    monkeypatch.setattr(native, "check_object", lambda obj, *a, **k: obj)
    monkeypatch.setattr(
        session, "object", lambda path, **k: image if path == paths.staging else None
    )
    calls = []

    def bind(kernel, name, args, result):
        assert name == "SetFileInformationByHandle"

        def rename(handle, kind, buffer, size):
            class Rename(ctypes.Structure):
                _fields_ = [
                    ("replace", ctypes.c_ubyte),
                    ("root", ctypes.c_void_p),
                    ("length", ctypes.c_uint32),
                    ("name", ctypes.c_uint16 * 1),
                ]

            record = ctypes.cast(buffer, ctypes.POINTER(Rename)).contents
            assert record.replace == 0 and record.root == 42
            assert (
                ctypes.string_at(
                    ctypes.addressof(buffer) + Rename.name.offset, record.length
                ).decode("utf-16-le")
                == paths.release_id
            )
            assert handle == 41 and kind == 3
            calls.append("rename")
            return 1

        return rename

    monkeypatch.setattr(native, "bind", bind)
    monkeypatch.setattr(
        native, "close_native_handle", lambda kernel, handle: calls.append("close")
    )
    assert session.publish() is True
    assert calls == ["rename", "close"]
    with pytest.raises(native.NativeObservationError):
        session.publish()
    assert calls == ["rename", "close"]


def test_native_scope_close_ambiguity_escapes_to_operator(monkeypatch):
    monkeypatch.setattr(native.incident, "require_administrator_host", lambda: None)

    class Session:
        def publish(self):
            return True

        def close(self):
            fail()

    monkeypatch.setattr(native, "PublicationSession", Session)
    with pytest.raises(RuntimeError):
        native.publish_preserved_image(subject.expected_image())


def test_aj_routes_single_active_checkpoint_and_retains_split_workflow():
    spec = runner._checkpoint_specs()[NAME]
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), subject.BRANCH, "push")
        == NAME
    )
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), subject.BRANCH, "pull_request"
        )
        is None
    )
    assert spec.preflight is runner._supervised_publication_preflight
    assert spec.execute is runner._supervised_publication_execute
    assert spec.remote_head_env is None
    root = Path(runner.__file__).resolve().parents[1]
    assert runner._batch_workflow_is_reviewed(
        (root / ".github/workflows/checkpoint-source-gates.yml").read_text()
    )
    # AJ pins the complete historical registry. Later checkpoint additions must
    # keep that protected recovery gate closed without changing any other pin.
    functions = {
        node.name: node
        for node in ast.parse(
            (root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        ).body
        if isinstance(node, ast.FunctionDef)
    }
    drifted = {
        name
        for name, pin in runner.SUPERVISED_PUBLICATION_RUNNER_PINS.items()
        if hashlib.sha256(
            ast.dump(functions[name], include_attributes=False).encode()
        ).hexdigest()
        != pin
    }
    assert drifted == {"_checkpoint_specs"}
    assert runner._supervised_publication_recovery_authority_check(root) == (
        "publication recovery runner authority drift",
    )


def test_direct_runner_execute_requires_admitted_context(monkeypatch):
    monkeypatch.setattr(runner, "_publication_execution_source", None)
    monkeypatch.setenv(subject.AUTH_ENV, subject.AUTH_VALUE)
    with pytest.raises(RuntimeError):
        runner._supervised_publication_execute()


@pytest.mark.parametrize(
    "mutation",
    [
        "import trading_bot.supervised_release.native_write\n",
        "from trading_bot.supervised_release import installation_operator\n",
        "from trading_bot.supervised_release.installer import install_release\n",
        "def forbidden():\n    path.unlink()\n",
        "def forbidden():\n    path.mkdir()\n",
    ],
)
def test_authority_rejects_forbidden_capabilities_even_when_rehashed(
    tmp_path, monkeypatch, mutation
):
    root = Path(runner.__file__).resolve().parents[1]
    real_read = Path.read_text
    relative = "src/trading_bot/supervised_release/publication_recovery.py"
    changed = real_read(root / relative) + mutation
    data = changed.encode()
    pin = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    monkeypatch.setattr(
        runner,
        "SUPERVISED_PUBLICATION_RECOVERY_PINS",
        {**runner.SUPERVISED_PUBLICATION_RECOVERY_PINS, relative: pin},
    )

    def read(path, *args, **kwargs):
        return changed if path == root / relative else real_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    failures = runner._supervised_publication_recovery_authority_check(root)
    assert any(
        "import drift" in value or "forbidden capability" in value for value in failures
    )


def test_recovery_imports_do_not_depend_on_other_modules_private_helpers():
    tree = ast.parse(Path(subject.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not any(alias.name.startswith("_") for alias in node.names)
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "incident"
        ):
            assert not node.attr.startswith("_")


@pytest.mark.parametrize(
    "phase", ["path", "branch", "dirty", "origin", "ancestor", "pins"]
)
def test_runner_exact_source_admission(tmp_path, monkeypatch, phase):
    state = {
        "branch": subject.BRANCH,
        "head": "a" * 40,
        "tree": "b" * 40,
        "porcelain": "",
    }
    monkeypatch.setattr(subject, "WORKTREE", tmp_path)
    monkeypatch.setattr(runner, "_REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(
        runner, "_supervised_publication_recovery_authority_check", lambda root: ()
    )

    def git(root, *args):
        return subject.ORIGIN if args[0] == "remote" else subject.BASE_HEAD

    monkeypatch.setattr(runner, "_git_output", git)
    runner._supervised_publication_admission(tmp_path, state)
    if phase == "path":
        monkeypatch.setattr(subject, "WORKTREE", tmp_path / "other")
    elif phase == "branch":
        state["branch"] = "feature/other"
    elif phase == "dirty":
        state["porcelain"] = "M source.py"
    elif phase == "origin":
        monkeypatch.setattr(
            runner, "_git_output", lambda *a: "https://example.com/other.git"
        )
    elif phase == "ancestor":
        monkeypatch.setattr(
            runner,
            "_git_output",
            lambda root, *args: subject.ORIGIN if args[0] == "remote" else "0" * 40,
        )
    else:
        monkeypatch.setattr(
            runner,
            "_supervised_publication_recovery_authority_check",
            lambda root: ("drift",),
        )
    with pytest.raises(RuntimeError):
        runner._supervised_publication_admission(tmp_path, state)


def test_runner_live_source_rejects_remote_drift(monkeypatch):
    state = {
        "branch": subject.BRANCH,
        "head": "a" * 40,
        "tree": "b" * 40,
        "porcelain": "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda root: state)
    monkeypatch.setattr(runner, "_supervised_publication_admission", lambda *a: None)
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *a: "a" * 40)
    assert runner._supervised_publication_live_source() == ("a" * 40, "b" * 40)
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *a: "0" * 40)
    with pytest.raises(RuntimeError):
        runner._supervised_publication_live_source()


def test_runner_preflight_rechecks_exact_source(monkeypatch):
    states = iter((("a" * 40, "b" * 40), ("c" * 40, "b" * 40)))
    monkeypatch.setattr(
        runner, "_supervised_publication_live_source", lambda: next(states)
    )

    def preflight(admit_source):
        with pytest.raises(RuntimeError):
            admit_source()
        return {"status": "BLOCKED"}

    monkeypatch.setattr(subject, "preflight", preflight)
    assert runner._supervised_publication_preflight()["status"] == "BLOCKED"


def test_runner_aj_preflight_emits_stdout_only(tmp_path, monkeypatch):
    state = {
        "branch": subject.BRANCH,
        "head": "a" * 40,
        "tree": "b" * 40,
        "porcelain": "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda root: state)
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *a: "a" * 40)
    monkeypatch.setattr(runner, "_supervised_publication_admission", lambda *a: None)
    monkeypatch.setattr(
        runner,
        "_supervised_publication_preflight",
        lambda: {
            "status": "PASS",
            "effect_disposition": "NOT_STARTED",
            "primary": {"status": "READY"},
        },
    )
    spec = runner._checkpoint_specs()[NAME]
    passed, report_path = runner.preflight_checkpoint(
        spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
    )
    assert passed and report_path is None
    assert not (tmp_path / "evidence").exists()
    tampered = replace(spec, preflight=lambda: pytest.fail("tampered callback"))
    with pytest.raises(RuntimeError):
        runner.preflight_checkpoint(
            tampered, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )


def test_runner_clears_context_and_reclassifies_late_source_drift(
    tmp_path, monkeypatch
):
    before = {
        "branch": subject.BRANCH,
        "head": "a" * 40,
        "tree": "b" * 40,
        "porcelain": "",
    }
    after = {**before, "tree": "c" * 40}
    states = iter((before, after))
    monkeypatch.setattr(runner, "_git_state", lambda root: next(states))
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *a: before["head"])
    monkeypatch.setattr(runner, "_supervised_publication_admission", lambda *a: None)

    def execute():
        assert runner._publication_execution_source == (before["head"], before["tree"])
        return {
            "status": "PASS",
            "effect_disposition": "CONFIRMED",
            "primary": {"status": "FINAL_PUBLISHED_VERIFIED"},
        }

    monkeypatch.setattr(runner, "_supervised_publication_execute", execute)
    passed, path = runner.execute_checkpoint(
        runner._checkpoint_specs()[NAME],
        repo_root=tmp_path,
        evidence_root=tmp_path / "evidence",
    )
    assert not passed and runner._publication_execution_source is None
    report = json.loads(path.read_text())
    assert report["result"]["primary"]["status"] == "INDETERMINATE"
    assert (
        report["result"]["primary"]["disposition"]
        == "PRESERVE_PUBLICATION_EVIDENCE_NO_RETRY"
    )


def test_final_second_readback_drift_is_indeterminate(monkeypatch):
    calls, _, evidence, _, _ = setup_image(monkeypatch)
    observations = iter((evidence, replace(evidence, image_identity=(1, 2))))
    monkeypatch.setattr(
        subject, "observe_installed_release", lambda *a, **k: next(observations)
    )
    assert subject.execute_once(lambda: None)["status"] == "INDETERMINATE"
    assert calls.count("publish") == 1


def test_durable_fence_acknowledgement_is_required(monkeypatch):
    calls, _, _, _, _ = setup_image(monkeypatch)
    monkeypatch.setattr(subject, "_consume", lambda mark: None)
    assert subject.execute_once(lambda: None)["status"] == "BLOCKED"
    assert "publish" not in calls


def test_public_incident_boundary_requires_original_ag_latch(tmp_path, monkeypatch):
    attempt = tmp_path / "ag.json"
    attempt.write_bytes(subject.incident.ATTEMPT_BYTES)
    monkeypatch.setattr(subject.incident, "ATTEMPT_PATH", attempt)
    monkeypatch.setattr(subject.incident, "_attempt_context", lambda: None)
    subject.incident.admit_failed_installation()
    attempt.write_bytes(b"reset")
    with pytest.raises(ValueError):
        subject.incident.admit_failed_installation()


def test_latch_creation_race_is_indeterminate_and_never_publishes(monkeypatch):
    calls, _, _, _, _ = setup_image(monkeypatch)

    def consume(mark):
        monkeypatch.setattr(subject, "latch_consumed", lambda: True)
        raise FileExistsError("another attempt consumed the AJ latch")

    monkeypatch.setattr(subject, "_consume", consume)
    assert subject.execute_once(lambda: None)["status"] == "INDETERMINATE"
    assert "publish" not in calls
    assert subject.execute_once(lambda: None)["status"] == "INDETERMINATE"


def test_latch_readback_drift_is_after_fence_and_never_publishes(monkeypatch):
    calls, _, _, _, _ = setup_image(monkeypatch)
    monkeypatch.setattr(
        subject.incident, "read_incident_record", lambda path, limit: b"changed"
    )
    assert subject.execute_once(lambda: None)["status"] == "INDETERMINATE"
    assert "latch" in calls and "publish" not in calls
