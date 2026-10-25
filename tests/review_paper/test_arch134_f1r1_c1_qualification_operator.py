"""C1 tests use disposable roots/processes only; never the fixed external exercise."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import stat
import subprocess
import tarfile
import time
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import arch134_f1r1_qualification as q
from scripts import arch134_f1r1_qualification_process as process

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def prepared(tmp_path):
    paths = q.QualificationPaths._for_tests(tmp_path / "qualification")
    result = q.prepare(paths)
    assert result["QUALIFICATION_STATUS"] == q.QualificationStatus.READY
    return paths


def start(paths):
    # Only this explicitly disposable helper enters copied source; no CLI root override.
    code = (
        "import sys; from pathlib import Path; "
        f"sys.path.insert(0, {str(paths.fixture)!r}); "
        "import arch134_f1r1_qualification as q; "
        "raise SystemExit(q.main(['run'], _test_paths="
        f"q.QualificationPaths._for_tests(Path({str(paths.root)!r}))))"
    )
    child = subprocess.Popen(
        [
            q.require_fixture(paths).manifest.interpreter.executable,
            "-I",
            "-S",
            "-B",
            "-",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    child.stdin.write(code)
    child.stdin.close()
    child.stdin = None
    return child


def await_running(paths, child):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if child.poll() is not None:
            stdout, stderr = child.communicate()
            pytest.fail(f"disposable host exited: {stdout} {stderr}")
        try:
            if q.status(paths)["QUALIFICATION_STATUS"] == q.QualificationStatus.RUNNING:
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.02)
    pytest.fail("disposable host did not become safely waiting")


@pytest.fixture
def running(prepared):
    child = start(prepared)
    try:
        await_running(prepared, child)
        yield prepared, child
    finally:
        if child.poll() is None:
            child.kill()  # Only the subprocess created by this disposable test.
        child.communicate(timeout=8)


def test_cli_is_closed_and_rejects_paths_pids_and_effect_commands():
    assert q.COMMANDS == ("prepare", "run", "status", "stop", "verify")
    for argv in (
        ["run", "--root", "F:\\AITradingBot"],
        ["stop", "--pid", "1"],
        ["stop", "--path", "anything"],
        ["install"],
        ["resume"],
        ["retry"],
        ["authorize"],
        ["schedule"],
        ["live"],
    ):
        with pytest.raises(SystemExit):
            q.parser().parse_args(argv)


@pytest.mark.parametrize("suffix", ["", "\\data", "\\runtime", "\\releases\\child"])
def test_production_namespaces_rejected_before_io(suffix):
    with pytest.raises(q.QualificationError, match="production"):
        q.safe_namespace(Path("F:\\AITradingBot" + suffix))


def test_ordinary_paths_are_fixed_test_override_is_python_only(tmp_path):
    with pytest.raises(q.QualificationError, match="fixed"):
        q.QualificationPaths(tmp_path)
    assert q.QualificationPaths._for_tests(tmp_path).root == tmp_path
    assert str(q.ROOT) == r"F:\AI\temp\qualification\arch134-f1r1-host-isolation"
    with pytest.raises(q.QualificationError):
        q.QualificationPaths._for_tests(tmp_path).state("arbitrary.json")


def test_manifest_identity_and_prepare_are_deterministic_and_idempotent(prepared):
    before = q.require_fixture(prepared)
    assert before.manifest.runtime_id.startswith("qualification-")
    assert not before.manifest.runtime_id.startswith("runtime-")
    snapshots = snapshot(prepared)
    assert q.prepare(prepared)["RUNTIME_ID"] == before.manifest.runtime_id
    assert snapshot(prepared) == snapshots
    assert q.admit_fixture(prepared).reason is q.QualificationReason.EXACT_FIXTURE
    assert q.verify(prepared)["HOST_LEASE_AUTHORITIES"] == 0


def snapshot(paths):
    return {
        str(p.relative_to(paths.root)): (
            p.read_bytes(),
            p.stat().st_mtime_ns,
            p.stat().st_ino,
        )
        for p in paths.root.rglob("*")
        if p.is_file()
    }


def test_status_and_verify_are_read_only(prepared):
    before = snapshot(prepared)
    q.status(prepared)
    q.verify(prepared)
    assert snapshot(prepared) == before
    assert not prepared.state("process.json").exists()


def test_stale_file_alone_cannot_claim_life_and_is_not_deleted(prepared):
    lock = prepared.state("lease.lock")
    before = lock.stat().st_ino
    assert q.lease_state(prepared) == "FREE"
    result = q.status(prepared)
    assert result["PROCESS_STATE"] == "NOT_STARTED"
    assert result["LEASE_STATE"] == "FREE"
    assert lock.stat().st_ino == before


def test_one_exclusive_holder_only_and_no_reacquisition(prepared):
    runtime_id = q.require_fixture(prepared).manifest.runtime_id
    first, second = (
        q.QualificationHostLease(prepared),
        q.QualificationHostLease(prepared),
    )
    assert first.acquire(runtime_id) is True
    try:
        assert q.lease_state(prepared) == "HELD"
        assert second.acquire(runtime_id) is False
        with pytest.raises(q.QualificationError):
            second.acquire(runtime_id)
    finally:
        first.release()
    assert q.lease_state(prepared) == "FREE"
    with pytest.raises(q.QualificationError):
        first.acquire(runtime_id)


def test_process_creation_identity_observed():
    current = process.current_process()
    assert current == process.observe_process(os.getpid())
    assert current.birth
    assert Path(current.executable) == Path(q.interpreter().executable)


def test_controlled_stop_persists_terminal_before_release(running):
    paths, child = running
    before = q.verify(paths)
    assert before["HOST_LEASE_AUTHORITIES"] == 1
    assert before["PROCESS_STATE"] == "ALIVE_EXACT"
    q.request_stop(paths)
    q.request_stop(paths)
    stdout, stderr = child.communicate(timeout=8)
    assert child.returncode == 0, (stdout, stderr)
    result = q.verify(paths)
    assert result["QUALIFICATION_STATUS"] == q.QualificationStatus.COMPLETED
    assert result["LAST_LIFECYCLE_EVENT"] == "NORMAL_RETURN"
    assert result["LEASE_STATE"] == "FREE"
    assert result["PROCESS_STATE"] == "GONE"
    assert result["LIFECYCLE_RECORD_COUNT"] == 5
    assert result["RUNTIME_ID"] == before["RUNTIME_ID"]
    terminal = q.decode(q.read(paths.state("result.json")))
    assert terminal["lease_released_after_terminal"] is True
    assert result["PROTECTED_EFFECT_COUNTERS"] == q.zeros()
    # Ordering is also source-checked: append -> release -> result, no other release.
    source = (ROOT / "scripts/arch134_f1r1_qualification.py").read_text(
        encoding="utf-8-sig"
    )
    assert source.index("append(paths, runtime_id, terminal)") < source.index(
        "lease.release()"
    )


def test_process_death_releases_lease_preserves_abrupt_evidence_no_restart(running):
    paths, child = running
    child.kill()
    child.communicate(timeout=8)
    before = snapshot(paths)
    assert q.lease_state(paths) == "FREE"
    result = q.status(paths)
    assert result["QUALIFICATION_STATUS"] == q.QualificationStatus.ABRUPT
    with pytest.raises(q.QualificationError, match="ABRUPT"):
        q.verify(paths)
    assert snapshot(paths) == before
    retry = start(paths)
    retry.communicate(timeout=8)
    assert retry.returncode == 2
    assert not paths.state("result.json").exists()
    assert q.lease_state(paths) == "FREE"


def test_duplicate_host_rejected_and_preserved_as_failure(running):
    paths, child = running
    second = start(paths)
    second.communicate(timeout=8)
    assert second.returncode == 2
    assert child.poll() is None
    assert len(q.journal(paths, q.require_fixture(paths).manifest.runtime_id)) == 4
    # Rejected duplicate is preserved independently; no second lock/loop evidence.
    assert paths.state("duplicate.json").exists()
    with pytest.raises(q.QualificationError, match="duplicate"):
        q.verify(paths)


def test_copied_host_independent_of_cwd_git_and_development_files(
    running, tmp_path, monkeypatch
):
    paths, child = running
    before = q.verify(paths)
    unrelated = tmp_path / "development"
    unrelated.mkdir()
    (unrelated / "edit.py").write_text("# unrelated edit\n")
    subprocess.run(["git", "init", str(unrelated)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(unrelated), "status", "--short"],
        check=True,
        capture_output=True,
    )
    monkeypatch.chdir(unrelated)
    after = q.verify(paths)
    assert after["RUNTIME_ID"] == before["RUNTIME_ID"]
    assert after["PROCESS_IDENTITY"] == before["PROCESS_IDENTITY"]
    assert child.poll() is None
    value = q.decode(q.read(paths.state("process.json")))
    assert Path(value["source_origin"]).parent == paths.fixture
    assert str(ROOT) not in value["source_origin"]


@pytest.mark.parametrize("mutation", ["pid_reuse", "unknown", "gone"])
def test_status_does_not_trust_pid_or_infer_unknown_liveness(
    running, monkeypatch, mutation
):
    paths, _ = running
    original = q.decode(q.read(paths.state("process.json")))["process"]
    if mutation == "pid_reuse":
        monkeypatch.setattr(
            q,
            "observe_process",
            lambda pid: q.QualificationProcessEvidence(
                pid, "different-birth", original["executable"]
            ),
        )
        with pytest.raises(q.QualificationError, match="PID reuse"):
            q.status(paths)
    elif mutation == "unknown":

        def unavailable(pid):
            raise OSError("unavailable")

        monkeypatch.setattr(q, "observe_process", unavailable)
        assert q.status(paths)["QUALIFICATION_STATUS"] == q.QualificationStatus.UNPROVEN
        with pytest.raises(q.QualificationError):
            q.verify(paths)
    else:
        monkeypatch.setattr(q, "observe_process", lambda pid: None)
        assert q.status(paths)["QUALIFICATION_STATUS"] == q.QualificationStatus.ABRUPT


@pytest.mark.parametrize("payload", [b"{", b"{}", b"{}\n", b"\n", b'{"x":1,"x":1}\n'])
def test_malformed_partial_or_noncanonical_journal_rejected_without_repair(
    prepared, payload
):
    path = prepared.state("lifecycle.jsonl")
    path.write_bytes(payload)
    with pytest.raises((ValueError, KeyError)):
        q.verify(prepared)
    assert path.read_bytes() == payload


@pytest.mark.parametrize("counter", q.PROTECTED_COUNTERS)
def test_nonzero_protected_effect_counter_rejected(prepared, counter):
    runtime_id = q.require_fixture(prepared).manifest.runtime_id
    q.append(prepared, runtime_id, "HOST_ENTERED")
    path = prepared.state("lifecycle.jsonl")
    row = q.journal(prepared, runtime_id)[0]
    row["protected_effects"][counter] = 1
    path.write_bytes(q.canonical(row) + b"\n")
    with pytest.raises(q.QualificationError):
        q.verify(prepared)


@pytest.mark.parametrize("name", q.SOURCE_NAMES)
def test_fixture_byte_drift_rejected(prepared, name):
    path = prepared.fixture / name
    path.chmod(stat.S_IREAD | stat.S_IWRITE)
    path.write_bytes(path.read_bytes() + b" ")
    assert q.admit_fixture(prepared).status is None
    with pytest.raises(q.QualificationError):
        q.verify(prepared)


def test_interpreter_observation_drift_and_production_interpreter_rejected(
    prepared, monkeypatch
):
    actual = q.interpreter()
    monkeypatch.setattr(q, "interpreter", lambda: replace(actual, sha256="0" * 64))
    assert q.admit_fixture(prepared).status is None
    with pytest.raises(q.QualificationError, match="production"):
        q.safe_namespace(Path(r"F:\AITradingBot\runtime\python.exe"))


def test_partial_prepare_preserved_and_not_repaired(tmp_path):
    paths = q.QualificationPaths._for_tests(tmp_path / "partial")
    paths.root.mkdir()
    marker = paths.root / "preserve.txt"
    marker.write_text("preserve")
    with pytest.raises(q.QualificationError):
        q.prepare(paths)
    assert marker.read_text() == "preserve"
    assert not paths.fixture.exists()


def test_stop_requires_only_fixed_waiting_qualification(prepared):
    with pytest.raises(q.QualificationError):
        q.request_stop(prepared)
    assert not prepared.state("stop.json").exists()


def test_qualification_types_cannot_substitute_for_production_evidence(prepared):
    from trading_bot.supervised_release.installation_contract import (
        InstalledEvidence,
        ReleasePaths,
    )
    from trading_bot.supervised_release.runtime_admission import (
        RuntimeAdmissionEvidence,
        RuntimeAdmissionResult,
    )
    from trading_bot.supervised_release.runtime_host_composition import (
        Architecture133HostBinding,
        HostBindingError,
        assess_host_qualification_readiness,
        bind_architecture133_host,
    )

    evidence = q.require_fixture(prepared)
    result = q.admit_fixture(prepared)
    for own in (
        evidence,
        result,
        evidence.manifest,
        q.interpreter(),
        process.current_process(),
    ):
        assert not isinstance(
            own,
            (
                InstalledEvidence,
                RuntimeAdmissionEvidence,
                RuntimeAdmissionResult,
                Architecture133HostBinding,
            ),
        )
        with pytest.raises(HostBindingError):
            bind_architecture133_host(own, own, own, own)
        with pytest.raises(HostBindingError):
            assess_host_qualification_readiness(own)
    with pytest.raises(ValueError, match="fixed release"):
        ReleasePaths(
            q.reference(prepared.fixture / q.SOURCE_NAMES[2])["release_id"]
        ).admit(str(q.ROOT))


def test_logical_predecessor_reference_replays_exact_accepted_git_bytes():
    from scripts import checkpoint_runner as runner
    from trading_bot.supervised_release.binding import RuntimeBinding
    from trading_bot.supervised_release.bundle import (
        ReleaseBundle,
        ReleaseFile,
        verify_release_bundle,
    )

    reference = q.reference(ROOT / "scripts" / q.SOURCE_NAMES[2])
    archive = subprocess.run(
        ["git", "archive", reference["source_head"]],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    manifest = reference["manifest"]
    names = tuple(row["relative_path"] for row in manifest["source_inventory"])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        source = {name: tar.extractfile(name).read() for name in names}
    source["manifest.json"] = q.canonical(manifest)
    release = verify_release_bundle(
        ReleaseBundle(tuple(ReleaseFile(n, b) for n, b in sorted(source.items()))),
        expected_manifest_sha256=reference["manifest_sha256"],
        expected_source_head=reference["source_head"],
        expected_source_tree=reference["source_tree"],
        expected_source_paths=names,
    )
    binding = RuntimeBinding(release)
    assert release.manifest.release_id == reference["release_id"]
    assert (
        release.manifest.source_inventory_sha256 == reference["source_inventory_sha256"]
    )
    assert binding.sha256 == reference["binding_sha256"]
    assert json.loads(binding.to_json()) == reference["binding"]
    for name, expected in reference["frozen_predecessors"].items():
        assert getattr(runner, name) == expected
    assert (
        reference["reference_kind"] == "PURE_RELEASE_REPLAY_NOT_INSTALLED_HOST_EVIDENCE"
    )


def test_cli_import_closure_has_no_production_or_effect_modules():
    allowed = {
        "__future__",
        "argparse",
        "ast",
        "errno",
        "hashlib",
        "json",
        "os",
        "stat",
        "sys",
        "time",
        "collections",
        "dataclasses",
        "enum",
        "pathlib",
        "ctypes",
        "fcntl",
        "msvcrt",
        "arch134_f1r1_qualification",
        "arch134_f1r1_qualification_process",
    }
    for name in q.SOURCE_NAMES:
        if not name.endswith(".py"):
            continue
        tree = ast.parse((ROOT / "scripts" / name).read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] in allowed for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.module.split(".")[0] in allowed
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not names & {
            "kill",
            "terminate",
            "connect",
            "system",
            "environ",
            "getenv",
            "Popen",
        }


def test_production_runtime_contracts_and_a_b_blobs_unchanged():
    base = "3f2e75f3daee40dfcf094b6057ae1a91f8de8928"
    for relative in (
        "src/trading_bot/supervised_release/runtime_admission.py",
        "src/trading_bot/supervised_release/runtime_host_composition.py",
        "src/trading_bot/supervised_release/runtime_isolation.py",
        "src/trading_bot/supervised_release/model.py",
        "src/trading_bot/supervised_release/installation_contract.py",
        "src/trading_bot/supervised_release/lifecycle_store.py",
    ):
        expected = subprocess.run(
            ["git", "show", base + ":" + relative],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        actual = (ROOT / relative).read_text(encoding="utf-8").encode()
        assert actual == expected


def test_c1_registration_overlays_and_frozen_dictionaries(monkeypatch):
    from scripts import checkpoint_runner as runner

    name = runner.ARCH134_F1R1_C1_NAME
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert runner.resolve_ci_certification_profile(name) == "robinhood"
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), spec.remote_branch, "push"
        )
        == name
    )
    assert runner._arch134_f1r1_c1_authority_check(ROOT) == ()
    assert runner._arch134_f1r1_b_authority_check(ROOT) == ()
    assert runner._arch134_f1r1_a_authority_check(ROOT) == ()
    base = subprocess.run(
        [
            "git",
            "show",
            "3f2e75f3daee40dfcf094b6057ae1a91f8de8928:scripts/checkpoint_runner.py",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode()
    current = Path(runner.__file__).read_text()
    before = {
        n.target.id: n.value
        for n in ast.parse(base).body
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
    }
    after = {
        n.target.id: n.value
        for n in ast.parse(current).body
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
    }
    for constant, value in before.items():
        if constant not in {
            "ACTIVE_CI_CHECKPOINTS",
            "REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256",
            "CI_CERTIFICATION_PROFILES",
        }:
            assert ast.dump(value) == ast.dump(after[constant]), constant
    for kind in ("SOURCE", "TEST"):
        prior = getattr(runner, f"ARCH134_F1R1_C1_PREDECESSOR_{kind}_PINS")
        after_name = (
            "ARCH134_F1R1_C1_SOURCE_PIN_OVERRIDES"
            if kind == "SOURCE"
            else "ARCH134_F1R1_C1_TEST_PIN_OVERRIDES"
        )
        resolver = (
            runner._arch134_f1r1_c1_current_source_pin
            if kind == "SOURCE"
            else runner._arch134_f1r1_c1_current_inventory_test_pin
        )
        successor = getattr(runner, after_name)
        path = next(iter(prior))
        assert resolver(path, prior[path]) == successor[path]
        assert resolver("unrelated", "a" * 40) == "a" * 40
        with pytest.raises(ValueError):
            resolver(path, "a" * 40)
        for mutation in ("missing", "extra", "blob", "remove"):
            changed = dict(successor)
            if mutation == "missing":
                changed.pop(path)
            elif mutation == "extra":
                changed["unreviewed"] = "a" * 40
            elif mutation == "blob":
                changed[path] = "a" * 40
            else:
                changed.clear()
            with monkeypatch.context() as patch:
                patch.setattr(runner, after_name, changed)
                with pytest.raises(ValueError):
                    resolver(path, prior[path])
    frozen_functions = {
        n.name: n for n in ast.parse(base).body if isinstance(n, ast.FunctionDef)
    }
    current_functions = {
        n.name: n for n in ast.parse(current).body if isinstance(n, ast.FunctionDef)
    }
    permitted = set(runner.ARCH134_F1R1_C1_RUNNER_AST_PINS)
    permitted.update(runner.ARCH134_D1S3_RUNNER_AST_PINS)
    permitted.update(runner.ARCH132_R3M_C3_AST_PINS)
    permitted.update(runner.ARCH132_R3M_C3_NEW_AST_PINS)
    workflow_key = "_batch_workflow_is_reviewed"
    assert (
        hashlib.sha256(
            ast.dump(current_functions[workflow_key], include_attributes=False).encode()
        ).hexdigest()
        == runner.ARCH132_R3M_AST_PINS[workflow_key]
    )
    permitted.add(workflow_key)
    for name, function in frozen_functions.items():
        if name not in permitted:
            assert ast.dump(function) == ast.dump(current_functions[name]), name


def test_durable_normal_return_precedes_concrete_release_in_disposable_child(prepared):
    code = f"""
import sys
from pathlib import Path
sys.path.insert(0, {str(prepared.fixture)!r})
import arch134_f1r1_qualification as q
paths = q.QualificationPaths._for_tests(Path({str(prepared.root)!r}))
original = q.QualificationHostLease.release
def checked_release(self):
    runtime_id = q.require_fixture(paths).manifest.runtime_id
    assert q.journal(paths, runtime_id)[-1]['event'] == 'NORMAL_RETURN'
    assert q.lease_state(paths) == 'HELD'
    original(self)
q.QualificationHostLease.release = checked_release
result = q.QualificationHost(paths).run(wait_once=lambda: q.request_stop(paths))
assert result['QUALIFICATION_STATUS'] == 'HOST_QUALIFICATION_COMPLETED'
"""
    result = subprocess.run(
        [
            q.require_fixture(prepared).manifest.interpreter.executable,
            "-I",
            "-S",
            "-B",
            "-",
        ],
        input=code,
        text=True,
        capture_output=True,
        timeout=8,
    )
    assert result.returncode == 0, result.stderr
    assert q.verify(prepared)["QUALIFICATION_STATUS"] == q.QualificationStatus.COMPLETED


def test_caught_internal_failure_is_terminal_but_not_positive(running):
    paths, child = running
    paths.state("stop.json").write_bytes(b"{}")
    child.communicate(timeout=8)
    assert child.returncode == 2
    result = q.status(paths)
    assert result["QUALIFICATION_STATUS"] == q.QualificationStatus.FAILED
    assert result["LAST_LIFECYCLE_EVENT"] == "CAUGHT_INTERNAL_FAILURE"
    assert result["LEASE_STATE"] == "FREE"
    with pytest.raises(q.QualificationError):
        q.verify(paths)


def test_duplicate_authority_event_rejected(prepared):
    runtime_id = q.require_fixture(prepared).manifest.runtime_id
    for event in q.EVENTS:
        q.append(prepared, runtime_id, event)
    rows = list(q.journal(prepared, runtime_id))
    rows[-1]["event"] = "SUPERVISOR_LOCK_ACQUIRED"
    prepared.state("lifecycle.jsonl").write_bytes(
        b"".join(q.canonical(r) + b"\n" for r in rows)
    )
    with pytest.raises(q.QualificationError):
        q.verify(prepared)


def test_terminal_unknown_process_observation_is_conservative(running, monkeypatch):
    paths, child = running
    q.request_stop(paths)
    child.communicate(timeout=8)

    def unavailable(pid):
        raise OSError("unavailable")

    monkeypatch.setattr(q, "observe_process", unavailable)
    assert q.status(paths)["QUALIFICATION_STATUS"] == q.QualificationStatus.UNPROVEN
    with pytest.raises(q.QualificationError):
        q.verify(paths)


def test_crash_after_reservation_before_lease_cannot_reacquire(prepared):
    code = f"""
import sys, os
from pathlib import Path
sys.path.insert(0, {str(prepared.fixture)!r})
import arch134_f1r1_qualification as q
q.QualificationHostLease.acquire = lambda self, runtime_id: os._exit(37)
paths = q.QualificationPaths._for_tests(Path({str(prepared.root)!r}))
raise SystemExit(q.main(['run'], _test_paths=paths))
"""
    command = [
        q.require_fixture(prepared).manifest.interpreter.executable,
        "-I",
        "-S",
        "-B",
        "-",
    ]
    first = subprocess.run(
        command, input=code, text=True, capture_output=True, timeout=8
    )
    assert first.returncode == 37
    assert prepared.state("process.json").exists()
    assert not prepared.state("lifecycle.jsonl").exists()
    assert q.status(prepared)["QUALIFICATION_STATUS"] == q.QualificationStatus.ABRUPT
    again = subprocess.run(
        command, input=code, text=True, capture_output=True, timeout=8
    )
    assert again.returncode == 2
    assert q.lease_state(prepared) == "FREE"


def test_prepare_rejects_unreviewed_executable_source_before_materialization(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name in (*q.SOURCE_NAMES, "checkpoint_runner.py"):
        (source / name).write_bytes((ROOT / "scripts" / name).read_bytes())
    modified = source / q.SOURCE_NAMES[0]
    modified.write_bytes(modified.read_bytes() + b"# byte drift\n")
    paths = q.QualificationPaths._for_tests(tmp_path / "never-created")
    with pytest.raises(q.QualificationError, match="reviewed C1 pins"):
        q.prepare(paths, source=source)
    assert not paths.root.exists()


@pytest.mark.parametrize(
    "name",
    [
        r"\\?\F:\AITradingBot\data",
        r"\\server\share\qualification",
        r"F:\AITradingBot.\data",
        r"F:\AITradingBot \data",
        r"F:\AI\temp\qualification:stream",
    ],
)
def test_qualification_aliases_rejected_before_access(name):
    with pytest.raises(q.QualificationError):
        q.safe_namespace(Path(name))
