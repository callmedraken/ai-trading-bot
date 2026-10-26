"""R5 source-only failure injection; never observes or mutates production."""

import ast
import builtins
import hashlib
import inspect
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.runtime.checkpoint_runner.test_ci import (
    _use_historical_predecessor_authority,
)

from scripts import checkpoint_runner as runner
from trading_bot.arch133_acl.read_only import ADMINISTRATORS_SID
from trading_bot.supervised_release import successor_publication_recovery as r
from trading_bot.supervised_release.installation_contract import (
    IMAGE_ACES,
    ObjectFacts,
    ReleasePaths,
)

ROOT = Path(__file__).resolve().parents[2]


def fact(path):
    return ObjectFacts(
        path, "directory", r.STAGING_IDENTITY, ADMINISTRATORS_SID, True, IMAGE_ACES
    )


def namespace(*, final=False, staging=True, names=None):
    return r.Namespace(
        replace(fact(r.RELEASES_BASE), identity=r.PARENT_IDENTITY),
        names
        if names is not None
        else tuple(
            sorted(
                ([r.RELEASE_ID] if final else [])
                + ([r.RELEASE_ID + ".installing"] if staging else [])
            )
        ),
        fact(r.FINAL_PATH) if final else None,
        fact(r.STAGING_PATH) if staging else None,
    )


@pytest.fixture
def seams(monkeypatch, tmp_path):
    events = []
    state = SimpleNamespace(final=False, staging=True)
    attempt = tmp_path / "r5" / "attempt.json"
    monkeypatch.setattr(r, "ATTEMPT_PATH", attempt)
    monkeypatch.setattr(r, "admit_source", lambda: events.append("source"))
    monkeypatch.setattr(
        r, "admit_predecessor_source", lambda: events.append("predecessor")
    )
    monkeypatch.setattr(r, "admit_incident", lambda: events.append("incident"))
    monkeypatch.setattr(
        r, "require_administrator", lambda: events.append("administrator")
    )
    monkeypatch.setattr(
        r,
        "reconstruct_release",
        lambda: ("release", "binding", ReleasePaths(r.RELEASE_ID)),
    )
    monkeypatch.setattr(
        r,
        "observe_namespace",
        lambda paths: namespace(final=state.final, staging=state.staging),
    )

    def replay(release, binding, *, final):
        events.append("final_replay" if final else "staging_replay")
        return r.expected_image()

    monkeypatch.setattr(r, "replay_image", replay)
    monkeypatch.delenv(r.AUTH_ENV, raising=False)
    return state, events, attempt


def authorize(monkeypatch, seams, *, outcome=True):
    state, events, attempt = seams
    monkeypatch.setenv(r.AUTH_ENV, r.AUTH_VALUE)

    def publish(evidence):
        assert attempt.read_bytes() == r.ATTEMPT_BYTES
        events.append("publish")
        r.validate_image(evidence)
        if isinstance(outcome, BaseException):
            raise outcome
        if outcome:
            state.final, state.staging = True, False
        return outcome

    module = SimpleNamespace(publish_preserved_image=publish)
    monkeypatch.setitem(
        sys.modules,
        "trading_bot.supervised_release.successor_native_publication",
        module,
    )


def assert_no_retry(result):
    assert result["status"] == "INDETERMINATE"
    assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"
    assert result["automatic_retry"] == "NOT_AUTHORIZED"
    assert result["primary"]["disposition"] == "PRESERVE_PUBLICATION_EVIDENCE_NO_RETRY"


def test_frozen_incident_and_separate_authority():
    assert r.ACCEPTED_HEAD == "ad4c3d3334048054df6d8f046040349619c277f2"
    assert r.ACCEPTED_TREE == "b4cbf3039171673d3fba44e4999b172e658a4f91"
    assert (
        r.INSTALL_ATTEMPT_SHA256
        == "6677dd0d690fc611d6d4ba643179d78f0f168dfc2183c4310aae26e6d84c5f67"
    )
    assert (
        r.EXECUTE_REPORT_SHA256
        == "2b62f5718c1d9ed70b9cbf5232129c76734fdb1b77ae690137e6c7a5234fd84d"
    )
    assert (
        r.BLOCKED_REPORT_SHA256
        == "cd14c43cb9e2c9d500941c0cd026e7e14617d2a9a1c0a377e5d6b06c75debeec"
    )
    assert r.RELEASE_ID == "release-cb94451fc3295a97afffe9fac5d09ff3"
    assert r.MANIFEST_SHA256 == (
        "e36ca8cdd163a3a93137e50972913acfe468745639ec773ba21e842d8d814875"
    )
    assert r.BINDING_SHA256 == (
        "5ee1ea4218114b78d24b82ab7369972eafcaf332fa0b8e5ae59e5da08b953329"
    )
    assert r.INVENTORY_SHA256 == (
        "cd1b9ad5ec963916b6de6d5b81ebbad75d79ebcd5c4fc86fc991bfd0e1225d21"
    )
    assert r.PYTHON_VERSION == "3.14.3"
    assert r.PYTHON_SHA256 == (
        "cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b"
    )
    assert r.STAGING_IDENTITY == (1855336320, 281474982917732)
    assert r.PARENT_IDENTITY == (1855336320, 281474980511321)
    assert r.PYTHON_IDENTITY == (1855336320, 281474977875353)
    assert r.ATTEMPT_PATH != r.INSTALL_ATTEMPT_PATH
    assert r.ATTEMPT_BYTES == (
        b'{"automatic_retry":"NOT_AUTHORIZED","schema":"arch134-f1r1-d1s3-r5-publication-recovery-attempt/v1","status":"CONSUMED"}\n'
    )
    assert r.AUTH_ENV == "AI_TRADING_BOT_ARCH134_F1R1_D1S3_R5_PUBLICATION_AUTHORIZATION"
    assert r.AUTH_VALUE == (
        "ARCH134_F1R1_D1S3_R5_ONE_PRESERVED_RELEASE_PUBLICATION_AUTHORIZED"
    )
    assert str(r.ATTEMPT_PATH) == (
        r"F:\AI\temp\arch134-f1r1-d1s3-r5-publication-recovery-attempt\attempt.json"
    )
    assert r.WORKTREE == Path(
        r"F:\AI\worktrees\ai-trading-bot-production-paper-134f1r1-"
        r"d1s3-r5-publication-recovery-current"
    )


def reports():
    source = {
        phase: {"head": r.ACCEPTED_HEAD, "tree": r.ACCEPTED_TREE, "porcelain": ""}
        for phase in ("before", "after")
    }
    source["identity_stable"] = True
    common = {
        "schema": "ai-trading-bot-checkpoint-runner/v1",
        "checkpoint": r.INSTALL_CHECKPOINT,
        "source": source,
    }
    execute = {
        **common,
        "protected_execution": "ATTEMPTED",
        "status": "STOPPED",
        "result": {
            "status": "INDETERMINATE",
            "effect_disposition": "MAY_HAVE_OCCURRED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": {
                "status": "INDETERMINATE",
                "disposition": "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY",
                "reason": "PUBLICATION",
            },
            "attempt": {
                "state": "CONSUMED",
                "path": str(r.INSTALL_ATTEMPT_PATH),
                "payload_sha256": r.INSTALL_ATTEMPT_SHA256,
            },
        },
    }
    blocked = {
        **common,
        "protected_execution": "NOT_AUTHORIZED",
        "result": {
            "status": "BLOCKED",
            "effect_disposition": "NOT_STARTED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": {
                "reason": "INSTALLATION_BLOCKED",
                "installation_classification": "BLOCKED",
                "attempt_state": "CONSUMED",
            },
        },
    }
    return execute, blocked


@pytest.mark.parametrize("execute", [True, False])
def test_report_semantics_accept_only_expected(execute):
    report = reports()[0 if execute else 1]
    r._report_semantics(report, execute=execute)
    report["result"]["primary"]["reason"] = "INSTALL_REQUIRED"
    with pytest.raises(ValueError):
        r._report_semantics(report, execute=execute)


@pytest.mark.parametrize(
    "execute,section,key,value",
    [
        (True, "result", "status", "PASS"),
        (True, "primary", "reason", "STAGING_VERIFICATION"),
        (True, "attempt", "state", "AVAILABLE"),
        (True, "attempt", "payload_sha256", "0" * 64),
        (True, "report", "protected_execution", "NOT_AUTHORIZED"),
        (False, "primary", "attempt_state", "AVAILABLE"),
        (False, "primary", "installation_classification", "INSTALL_REQUIRED"),
        (False, "result", "effect_disposition", "MAY_HAVE_OCCURRED"),
        (False, "report", "protected_execution", "ATTEMPTED"),
    ],
)
def test_report_semantic_drift_rejected(execute, section, key, value):
    report = reports()[0 if execute else 1]
    target = (
        report
        if section == "report"
        else report["result"]
        if section == "result"
        else report["result"][section]
    )
    target[key] = value
    with pytest.raises(ValueError):
        r._report_semantics(report, execute=execute)


@pytest.mark.parametrize(
    "target", [r.INSTALL_ATTEMPT_PATH, r.EXECUTE_REPORT_PATH, r.BLOCKED_REPORT_PATH]
)
def test_incident_digest_drift_rejected(monkeypatch, target):
    values, calls, _ = inject_incident(monkeypatch)
    values[target] = b"wrong"
    with pytest.raises(ValueError, match="DIGEST"):
        r.admit_incident()
    assert target in calls


def inject_incident(monkeypatch):
    execute, blocked = reports()
    latch = {
        "schema": "arch134-f1r1-d1s3-installation-attempt/v1",
        "automatic_retry": "NOT_AUTHORIZED",
        "status": "CONSUMED",
    }
    values = {
        r.INSTALL_ATTEMPT_PATH: json.dumps(latch).encode(),
        r.EXECUTE_REPORT_PATH: json.dumps(execute).encode(),
        r.BLOCKED_REPORT_PATH: json.dumps(blocked).encode(),
    }
    for key, path in (
        ("INSTALL_ATTEMPT_SHA256", r.INSTALL_ATTEMPT_PATH),
        ("EXECUTE_REPORT_SHA256", r.EXECUTE_REPORT_PATH),
        ("BLOCKED_REPORT_SHA256", r.BLOCKED_REPORT_PATH),
    ):
        monkeypatch.setattr(r, key, hashlib.sha256(values[path]).hexdigest())
    # Recompose report after the injected latch digest.
    execute["result"]["attempt"]["payload_sha256"] = r.INSTALL_ATTEMPT_SHA256
    values[r.EXECUTE_REPORT_PATH] = json.dumps(execute).encode()
    monkeypatch.setattr(
        r,
        "EXECUTE_REPORT_SHA256",
        hashlib.sha256(values[r.EXECUTE_REPORT_PATH]).hexdigest(),
    )
    calls = []
    monkeypatch.setattr(
        r, "read_record", lambda path: (calls.append(path), values[path])[1]
    )
    return values, calls, latch


def test_incident_semantics_and_repeated_bytes(monkeypatch):
    values, calls, latch = inject_incident(monkeypatch)
    r.admit_incident()
    assert all(calls.count(path) == 2 for path in values)
    latch["status"] = "AVAILABLE"
    values[r.INSTALL_ATTEMPT_PATH] = json.dumps(latch).encode()
    monkeypatch.setattr(
        r,
        "INSTALL_ATTEMPT_SHA256",
        hashlib.sha256(values[r.INSTALL_ATTEMPT_PATH]).hexdigest(),
    )
    with pytest.raises(ValueError, match="ORIGINAL_LATCH"):
        r.admit_incident()


@pytest.mark.parametrize("kind", ["file", "directory", "malformed"])
def test_any_existing_object_consumes_r5(seams, kind):
    _, _, path = seams
    assert not r.latch_consumed()
    path.parent.mkdir()
    if kind == "directory":
        path.mkdir()
    else:
        path.write_bytes(r.ATTEMPT_BYTES if kind == "file" else b"bad")
    assert r.latch_consumed()
    with pytest.raises(FileExistsError):
        r.consume_attempt(lambda: pytest.fail("second reservation"))


def test_original_latch_cannot_be_recovery_latch(monkeypatch):
    monkeypatch.setattr(r, "ATTEMPT_PATH", r.INSTALL_ATTEMPT_PATH)
    with pytest.raises(ValueError, match="ORIGINAL_INSTALLATION_LATCH_FORBIDDEN"):
        r.latch_consumed()


def test_exclusive_latch_flush_fsync_readback(seams, monkeypatch):
    _, events, path = seams
    monkeypatch.setattr(r.os, "fsync", lambda fd: events.append("fsync"))
    r.consume_attempt(lambda: events.append("reserved"))
    assert events == ["reserved", "fsync"]
    assert path.read_bytes() == r.ATTEMPT_BYTES
    with pytest.raises(FileExistsError):
        r.consume_attempt(lambda: events.append("again"))


def test_preflight_staging_only_read_only_repeated_replay(seams):
    _, events, path = seams
    result = r.preflight()
    assert result["status"] == "PASS"
    assert (
        result["primary"]["status"] == "READY_FOR_EXACT_PRESERVED_RELEASE_PUBLICATION"
    )
    assert result["primary"]["execute_eligible"] is True
    assert events.count("staging_replay") >= 2
    assert not path.parent.exists()
    assert result["effect_disposition"] == "NOT_STARTED"


@pytest.mark.parametrize(
    "final,staging,consumed,status,reason",
    [
        (True, False, True, "PASS", "FINAL_PUBLISHED_VERIFIED"),
        (False, True, True, "BLOCKED", "CONSUMED_RECOVERY_ATTEMPT"),
        (True, False, False, "BLOCKED", "FINAL_PRESENT_BEFORE_RECOVERY"),
        (True, True, False, "BLOCKED", "NAMESPACE_CONFLICT"),
        (False, False, False, "BLOCKED", "PRESERVED_IMAGE_MISSING"),
    ],
)
def test_closed_reconciliation_cases(seams, final, staging, consumed, status, reason):
    state, events, path = seams
    state.final, state.staging = final, staging
    if consumed:
        path.parent.mkdir()
        path.write_bytes(b"any existing latch consumes")
    before = path.read_bytes() if consumed else None
    result = r.preflight()
    assert (result["status"], result["primary"]["reason"]) == (status, reason)
    assert result["primary"]["execute_eligible"] is False
    if consumed:
        assert path.read_bytes() == before
    if status == "PASS":
        assert events.count("final_replay") >= 2
        assert result["primary"]["namespace"]["staging_present"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("release_id", "wrong"),
        ("manifest_sha256", "0" * 64),
        ("binding_sha256", "0" * 64),
        ("parent_identity", (1, 2)),
        ("image_identity", (1, 2)),
        ("python_identity", (1, 2)),
        ("python_version", "3.14.2"),
        ("python_sha256", "0" * 64),
        ("dependency_closure", "PROVEN"),
    ],
)
def test_image_field_rejected(field, value):
    with pytest.raises(ValueError):
        r.validate_image(replace(r.expected_image(), **{field: value}))


@pytest.mark.parametrize(
    "seam",
    ["admit_source", "admit_incident", "require_administrator", "reconstruct_release"],
)
def test_prefence_rejection_does_not_consume_or_import(seams, monkeypatch, seam):
    _, _, path = seams
    authorize(monkeypatch, seams)

    def reject():
        raise ValueError("rejected")

    monkeypatch.setattr(r, seam, reject)
    assert r.execute_once()["effect_disposition"] == "NOT_STARTED"
    assert not path.exists()


def test_missing_auth_stops_before_admission(seams):
    _, events, path = seams
    assert r.execute_once()["primary"]["reason"] == "AUTHORIZATION_REJECTED"
    assert not events and not path.exists()


def test_fence_acknowledgement_is_required_before_writer(seams, monkeypatch):
    _, events, path = seams
    authorize(monkeypatch, seams)
    monkeypatch.setattr(r, "consume_attempt", lambda mark: None)
    assert_no_retry(r.execute_once())
    assert "publish" not in events and not path.exists()


def test_exclusive_creation_race_has_no_publication(seams, monkeypatch):
    _, events, path = seams
    authorize(monkeypatch, seams)

    def race(mark):
        path.parent.mkdir()
        path.write_bytes(b"another reservation")
        raise FileExistsError("reservation race")

    monkeypatch.setattr(r, "consume_attempt", race)
    assert_no_retry(r.execute_once())
    assert path.read_bytes() == b"another reservation" and "publish" not in events


def test_parent_namespace_delta_must_be_exact(seams, monkeypatch):
    state, events, _ = seams
    authorize(monkeypatch, seams)
    monkeypatch.setattr(
        r,
        "observe_namespace",
        lambda paths: namespace(
            final=state.final,
            staging=state.staging,
            names=(r.RELEASE_ID, "unrelated-change") if state.final else None,
        ),
    )
    assert_no_retry(r.execute_once())
    assert events.count("publish") == 1


def test_namespace_drift_is_indeterminate(seams, monkeypatch):
    calls = []

    def observe(paths):
        calls.append(1)
        return namespace(names=("drift",) if len(calls) > 1 else None)

    monkeypatch.setattr(r, "observe_namespace", observe)
    assert r.preflight()["status"] == "INDETERMINATE"


def test_replay_drift_is_indeterminate(seams, monkeypatch):
    calls = []

    def replay(*args, **kwargs):
        calls.append(1)
        return (
            replace(r.expected_image(), python_version="3.14.2")
            if len(calls) > 1
            else r.expected_image()
        )

    monkeypatch.setattr(r, "replay_image", replay)
    assert r.preflight()["status"] == "INDETERMINATE"


def test_success_one_call_lazy_import_after_durable_readback(seams, monkeypatch):
    _, events, path = seams
    authorize(monkeypatch, seams)
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.endswith("successor_native_publication"):
            assert path.read_bytes() == r.ATTEMPT_BYTES
            events.append("native_import")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    result = r.execute_once()
    assert result["status"] == "PASS" and result["effect_disposition"] == "CONFIRMED"
    assert result["primary"]["namespace"]["classification"] == "EXACT_FINAL_ONLY"
    assert result["primary"]["image"] == asdict(r.expected_image())
    assert events.count("publish") == 1 and events.count("final_replay") >= 2
    assert events.index("native_import") < events.index("publish")
    assert r.execute_once()["status"] == "BLOCKED"
    assert events.count("publish") == 1


@pytest.mark.parametrize(
    "failure", [False, OSError("rename"), KeyboardInterrupt(), SystemExit()]
)
def test_publication_failures_preserve_consumed_ambiguity(seams, monkeypatch, failure):
    _, events, path = seams
    authorize(monkeypatch, seams, outcome=failure)
    assert_no_retry(r.execute_once())
    assert path.read_bytes() == r.ATTEMPT_BYTES and events.count("publish") == 1
    assert r.preflight()["primary"]["reason"] == "CONSUMED_RECOVERY_ATTEMPT"


@pytest.mark.parametrize("phase", ["flush", "fsync", "readback", "write"])
def test_latch_failure_is_terminal_before_native_import(seams, monkeypatch, phase):
    _, events, path = seams
    authorize(monkeypatch, seams)
    original = Path.open

    class Broken:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.handle.close()

        def write(self, data):
            if phase == "write":
                return self.handle.write(data[:1])
            return self.handle.write(data)

        def flush(self):
            if phase == "flush":
                raise OSError("flush")
            self.handle.flush()

        def fileno(self):
            return self.handle.fileno()

    if phase in {"flush", "write"}:
        monkeypatch.setattr(
            Path,
            "open",
            lambda self, mode="r", *a, **k: (
                Broken(original(self, mode, *a, **k))
                if self == path and mode == "xb"
                else original(self, mode, *a, **k)
            ),
        )
    elif phase == "fsync":
        monkeypatch.setattr(
            r.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("fsync"))
        )
    else:
        monkeypatch.setattr(r, "read_record", lambda p: b"wrong")
    assert_no_retry(r.execute_once())
    assert path.exists() and "publish" not in events


@pytest.mark.parametrize(
    "seam", ["admit_source", "admit_incident", "observe_namespace", "replay_image"]
)
def test_post_publication_drift_is_terminal(seams, monkeypatch, seam):
    state, events, path = seams
    authorize(monkeypatch, seams)
    original = getattr(r, seam)

    def observe(*args, **kwargs):
        if state.final:
            raise r.ObservationDrift("post-publication drift")
        return original(*args, **kwargs)

    monkeypatch.setattr(r, seam, observe)
    assert_no_retry(r.execute_once())
    assert path.exists() and events.count("publish") == 1


def test_native_writer_exact_no_replace_record(monkeypatch):
    # Import the real module only in this isolated source-only test.
    import ctypes

    from trading_bot.supervised_release import successor_native_publication as native

    session = object.__new__(native.PublicationSession)
    session.paths = ReleasePaths(r.RELEASE_ID)
    session.publication_requested = False
    session.handles = {r.STAGING_PATH: 12, r.RELEASES_BASE: 34}
    session.kernel = object()
    monkeypatch.setattr(
        native,
        "observe_parent",
        lambda s: replace(fact(r.RELEASES_BASE), identity=r.PARENT_IDENTITY),
    )
    monkeypatch.setattr(
        session, "object", lambda p, **kw: fact(p) if p == r.STAGING_PATH else None
    )
    calls = []

    def bind(kernel, name, args, result):
        assert name == "SetFileInformationByHandle"

        def request(handle, kind, buffer, size):
            class Rename(ctypes.Structure):
                _fields_ = [
                    ("replace", ctypes.c_ubyte),
                    ("root", ctypes.c_void_p),
                    ("length", ctypes.c_uint32),
                    ("name", ctypes.c_uint16 * 1),
                ]

            record = ctypes.cast(buffer, ctypes.POINTER(Rename)).contents
            assert record.replace == 0 and record.root == 34
            assert (
                ctypes.string_at(
                    ctypes.addressof(buffer) + Rename.name.offset, record.length
                ).decode("utf-16-le")
                == r.RELEASE_ID
            )
            calls.append((handle, kind))
            return 1

        return request

    monkeypatch.setattr(native, "bind", bind)
    monkeypatch.setattr(
        native, "close_native_handle", lambda kernel, handle: calls.append("closed")
    )
    assert session.publish() is True
    assert calls == [(12, 3), "closed"]
    with pytest.raises(native.NativeObservationError):
        session.publish()
    forbidden = {
        "create_directory",
        "write_file",
        "seal_staging",
        "unlink",
        "remove",
        "rmdir",
        "replace",
        "MoveFileExW",
    }
    assert not (forbidden - {"replace"}) & set(dir(session))
    tree = ast.parse(inspect.getsource(native))
    assert not {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} & (
        forbidden - {"replace"}
    )


def test_runner_registration_and_historical_boundary(monkeypatch):
    _use_historical_predecessor_authority(monkeypatch, ROOT)
    spec = runner._checkpoint_specs()[r.CHECKPOINT]
    assert spec.preflight is runner._arch134_r5_preflight
    assert spec.execute is runner._arch134_r5_execute
    assert spec.remote_branch == r.BRANCH and spec.remote_head_env == r.REMOTE_HEAD_ENV
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] == "robinhood"
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), r.BRANCH, "push")
        == r.CHECKPOINT
    )
    assert (
        runner.SUPERVISED_PUBLICATION_RECOVERY_NAME not in runner.ACTIVE_CI_CHECKPOINTS
    )
    assert (
        runner._checkpoint_specs()[runner.SUPERVISED_PUBLICATION_RECOVERY_NAME].execute
        is not spec.execute
    )
    assert runner._arch134_r5_authority_check(ROOT) == ()


def test_source_gate_never_invokes_protected_dispatch(tmp_path):
    spec = runner._checkpoint_specs()[r.CHECKPOINT]
    steps = runner.build_verification_steps(
        spec, python_executable="python", basetemp=tmp_path / "pytest"
    )
    assert {step.name for step in steps} == {
        "git_diff_check",
        "ruff_check",
        "ruff_format",
        "pytest",
    }
    assert not any(
        token in {"execute", "preflight"} for step in steps for token in step.argv
    )


def test_runner_late_source_drift_is_preserved_ambiguity(monkeypatch, tmp_path):
    before = {"head": "a" * 40, "tree": "b" * 40, "branch": r.BRANCH, "porcelain": ""}
    states = iter((before, {**before, "tree": "c" * 40}))
    monkeypatch.setattr(runner, "_git_state", lambda root: next(states))
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *a: before["head"])
    monkeypatch.setattr(
        runner,
        "_arch134_r5_execute",
        lambda: {
            "status": "PASS",
            "effect_disposition": "CONFIRMED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": {"status": "FINAL_PUBLISHED_VERIFIED"},
        },
    )
    passed, path = runner.execute_checkpoint(
        runner._checkpoint_specs()[r.CHECKPOINT],
        repo_root=tmp_path,
        evidence_root=tmp_path / "evidence",
    )
    assert not passed
    report = json.loads(path.read_text())
    assert report["source"]["identity_stable"] is False
    assert_no_retry(report["result"])


def test_historical_dispatch_cannot_substitute_for_r5(monkeypatch):
    specs = runner._checkpoint_specs()
    specs[r.CHECKPOINT] = replace(
        specs[r.CHECKPOINT],
        execute=specs[runner.SUPERVISED_PUBLICATION_RECOVERY_NAME].execute,
    )
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "R5 registration drift" in runner._arch134_r5_authority_check(ROOT)


@pytest.mark.parametrize(
    "mapping",
    [
        "ARCH134_R5_BLOB_PREDECESSORS",
        "ARCH134_R5_BLOB_PINS",
        "ARCH134_R5_AST_PREDECESSORS",
        "ARCH134_R5_AST_PINS",
    ],
)
def test_r5_overlay_maps_cannot_drift(monkeypatch, mapping):
    monkeypatch.setattr(runner, mapping, {})
    assert runner._arch134_r5_authority_check(ROOT)


def test_historical_incident_modules_byte_unchanged():
    import subprocess

    for name in (
        "installation_reconciliation.py",
        "publication_recovery.py",
        "native_publication.py",
    ):
        relative = "src/trading_bot/supervised_release/" + name
        accepted = (
            subprocess.run(
                ["git", "-C", str(ROOT), "rev-parse", r.ACCEPTED_HEAD + ":" + relative],
                capture_output=True,
                check=True,
            )
            .stdout.decode()
            .strip()
        )
        assert runner._git_blob_sha1(ROOT / relative) == accepted


def test_preflight_import_closure_has_no_writer_or_historical_operator():
    tree = ast.parse(inspect.getsource(r))
    imports = [n.module or "" for n in tree.body if isinstance(n, ast.ImportFrom)]
    assert not any(
        any(
            part in name
            for part in (
                "installer",
                "native_publication",
                "installation_operator",
                "installation_reconciliation",
                "publication_recovery",
            )
        )
        for name in imports
    )


def test_recovery_import_is_inert_and_does_not_load_mutation_modules():
    import subprocess

    code = (
        "import sys, ctypes\n"
        "def reject(*args, **kwargs):\n"
        "    raise AssertionError('native call during import')\n"
        "ctypes.WinDLL = reject\n"
        f"sys.path.insert(0, {str(ROOT / 'src')!r})\n"
        "import trading_bot.supervised_release.successor_publication_recovery\n"
        "for name in (\n"
        "    'installer', 'native_write', 'successor_native_publication',\n"
        "    'installation_reconciliation', 'publication_recovery',\n"
        "    'native_publication',\n"
        "):\n"
        "    assert 'trading_bot.supervised_release.' + name not in sys.modules, name\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-"],
        input=code,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "field,value",
    [
        ("identity", (1, 2)),
        ("owner", "wrong"),
        ("protected", False),
        ("aces", ()),
        ("filesystem", "FAT32"),
        ("local", False),
        ("persistent_acls", False),
        ("reparse", True),
        ("links", 2),
    ],
)
def test_native_namespace_rejects_security_or_identity_drift(monkeypatch, field, value):
    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def names(self, path):
            return (r.RELEASE_ID + ".installing",)

        def object(self, path, **kwargs):
            return (
                replace(fact(path), **{field: value})
                if path == r.STAGING_PATH
                else None
            )

    monkeypatch.setattr(
        r,
        "WindowsObserver",
        lambda: SimpleNamespace(read_session=lambda paths: Session()),
    )
    monkeypatch.setattr(r, "observe_parent", lambda session: namespace().parent)
    with pytest.raises(ValueError):
        r.observe_namespace(ReleasePaths(r.RELEASE_ID))


def test_wrong_native_parent_rejected(monkeypatch):
    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def names(self, path):
            return ()

    monkeypatch.setattr(
        r,
        "WindowsObserver",
        lambda: SimpleNamespace(read_session=lambda paths: Session()),
    )
    monkeypatch.setattr(
        r,
        "observe_parent",
        lambda session: replace(namespace().parent, identity=(1, 2)),
    )
    with pytest.raises(ValueError, match="PARENT_NAMESPACE"):
        r.observe_namespace(ReleasePaths(r.RELEASE_ID))


@pytest.mark.parametrize(
    "fault", ["head", "tree", "branch", "origin", "dirty", "remote", "predecessor"]
)
def test_exact_current_source_admission_rejects_drift(monkeypatch, tmp_path, fault):
    # Exercise a relocated source fixture on every host, including the operator
    # machine. The production WORKTREE constant is independently frozen above.
    source_root = tmp_path / "ci-checkout"
    monkeypatch.setattr(r, "WORKTREE", source_root)
    monkeypatch.setattr(
        r,
        "__file__",
        str(
            source_root
            / "src/trading_bot/supervised_release/successor_publication_recovery.py"
        ),
    )
    monkeypatch.setenv(r.REMOTE_HEAD_ENV, "a" * 40)
    monkeypatch.setenv(r.SOURCE_TREE_ENV, "b" * 40)
    monkeypatch.setattr(r, "_safe_ancestors", lambda p: None)
    values = {
        ("rev-parse", "HEAD"): "a" * 40,
        ("ls-files", "-v", "-z"): "H source\0",
        ("rev-parse", "HEAD^{tree}"): "b" * 40,
        ("branch", "--show-current"): r.BRANCH,
        ("remote", "get-url", "origin"): r.ORIGIN,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
        ("diff", "--cached", "--name-only"): "",
        ("merge-base", r.ACCEPTED_HEAD, "HEAD"): r.ACCEPTED_HEAD,
        ("rev-parse", r.ACCEPTED_HEAD + "^{tree}"): r.ACCEPTED_TREE,
        ("rev-parse", "--show-toplevel"): str(r.WORKTREE),
        ("ls-remote", "origin", "refs/heads/" + r.BRANCH): "a" * 40
        + "\trefs/heads/"
        + r.BRANCH,
    }
    monkeypatch.setattr(r, "_git", lambda *args: values[args].encode())
    r.admit_source()
    key = {
        "head": ("rev-parse", "HEAD"),
        "tree": ("rev-parse", "HEAD^{tree}"),
        "branch": ("branch", "--show-current"),
        "origin": ("remote", "get-url", "origin"),
        "dirty": ("status", "--porcelain=v1", "--untracked-files=all"),
        "remote": ("ls-remote", "origin", "refs/heads/" + r.BRANCH),
        "predecessor": ("rev-parse", r.ACCEPTED_HEAD + "^{tree}"),
    }[fault]
    values[key] = "wrong"
    with pytest.raises(ValueError):
        r.admit_source()


def test_wrong_import_origin_rejected_before_git_observation(monkeypatch, tmp_path):
    monkeypatch.setenv(r.REMOTE_HEAD_ENV, "a" * 40)
    monkeypatch.setenv(r.SOURCE_TREE_ENV, "b" * 40)
    monkeypatch.setattr(r, "WORKTREE", tmp_path / "expected")
    monkeypatch.setattr(r, "__file__", str(tmp_path / "other" / "module.py"))
    monkeypatch.setattr(r, "_safe_ancestors", lambda path: None)
    monkeypatch.setattr(r, "_git", lambda *args: pytest.fail("Git before origin fence"))
    with pytest.raises(ValueError, match="R5_IMPORT_SOURCE_REJECTED"):
        r.admit_source()
