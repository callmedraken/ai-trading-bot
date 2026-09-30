"""R7C source/mock certification. No production native/helper invocation."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts.d10_protected_deployment import (
    ADMINISTRATORS_SID,
    FILE_ALL_ACCESS,
    SYSTEM_SID,
    TRADING_FILE_READ,
    Ace,
    CheckedDirectory,
    CheckedFile,
    DeploymentBlocked,
    NativeObject,
    expected_policy,
)

from scripts import checkpoint_runner as runner
from scripts import d10_arch128_r3_preflight as r3
from scripts import d10_arch128_r4_orchestration as r4c
from scripts import d10_arch128_r4_replacement as r4
from scripts import d10_arch128_r6_reactivation as r6
from scripts import d10_arch128_r7_observation as o
from scripts import d10_arch128_r7_windows as w
from scripts import run_personal_desktop_d10_launch_guard as guard

PLAN = r6.derive_reactivation_plan(datetime(2026, 10, 1, 12, tzinfo=UTC))
ROOT = Path(__file__).resolve().parents[2]


def native(path, *, directory=False, evidence=False):
    owner, protected, aces = expected_policy(directory)
    if evidence:
        aces = (
            Ace(ADMINISTRATORS_SID, FILE_ALL_ACCESS),
            Ace(SYSTEM_SID, FILE_ALL_ACCESS),
            Ace(guard.TRADING_SID, guard.TRADING_EVIDENCE_FILE_ACCESS),
        )
    return NativeObject(
        path,
        path,
        directory,
        owner,
        protected,
        aces,
        False,
        3,
        "F:" + chr(92),
        "NTFS",
        9,
        11,
        1,
        0,
    )


def empty():
    return CheckedFile(native(PLAN.evidence_path, evidence=True), b"", True)


def projection(spec=None):
    return {
        **o.scheduler_semantics(spec),
        "xml_byte_length": 4096,
        "xml_sha256": o.PREDECESSOR_XML_SHA256 if spec is None else "a" * 64,
    }


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "0",
        "-1",
        "+1",
        "1.0",
        " 1",
        "1 ",
        "1\n",
        "ÃƒÆ’Ã¢â€žÂ¢Ãƒâ€šÃ‚Â¡",
        "ÃƒÆ’Ã‚Â¯Ãƒâ€šÃ‚Â¼ÃƒÂ¢Ã¢â€šÂ¬Ã‹Å“",
        "1_0",
        "4294967296",
    ],
)
def test_pid_rejects_non_ascii_or_nonpositive(value):
    with pytest.raises(DeploymentBlocked):
        w.parse_trading_pid(value)


def test_pid_exact_environment_factory_is_inert(monkeypatch):
    constructed = []
    monkeypatch.setenv(w.TRADING_PID_ENV, "00123")
    monkeypatch.setattr(
        w,
        "WindowsR7Boundaries",
        lambda pid: (
            constructed.append(pid) or SimpleNamespace(activation_clock=object())
        ),
    )
    boundaries, clock = w.host_factory()
    assert constructed == [123]
    assert clock is boundaries.activation_clock
    monkeypatch.delenv(w.TRADING_PID_ENV)
    with pytest.raises(DeploymentBlocked):
        w.host_factory()
    assert constructed == [123]


def test_disabled_scheduler_matches_existing_r3_model():
    assert o.scheduler_semantics(None) == r3._expected_scheduler()
    o.require_scheduler(projection(), None)


@pytest.mark.parametrize("key", tuple(o.scheduler_semantics(PLAN.scheduler)))
def test_every_dynamic_scheduler_field_is_independently_required(key):
    item = projection(PLAN.scheduler)
    value = item[key]
    item[key] = (
        not value
        if type(value) is bool
        else value + 1
        if type(value) is int
        else value + "drift"
    )
    with pytest.raises(DeploymentBlocked):
        o.require_scheduler(item, PLAN.scheduler)


def test_dynamic_scheduler_uses_semantics_and_bounded_xml_not_old_digest():
    o.require_scheduler(projection(PLAN.scheduler), PLAN.scheduler)
    item = projection()
    item["xml_sha256"] = "a" * 64
    with pytest.raises(DeploymentBlocked):
        o.require_scheduler(item, None)
    item = projection(PLAN.scheduler)
    item["extra"] = True
    with pytest.raises(DeploymentBlocked):
        o.require_scheduler(item, PLAN.scheduler)


@pytest.mark.parametrize(
    "change",
    [
        {"size": 1},
        {"final_path": PLAN.evidence_path.upper()},
        {"path": PLAN.evidence_path + ":x"},
        {"directory": True},
        {"reparse": True},
        {"links": 2},
        {"drive_type": 4},
        {"filesystem": "FAT32"},
        {"volume_root": "C:" + chr(92)},
        {"owner_sid": guard.TRADING_SID},
        {"dacl_protected": False},
        {"aces": (Ace(guard.TRADING_SID, guard.TRADING_EVIDENCE_FILE_ACCESS | 2),)},
    ],
)
def test_exact_empty_evidence_native_policy(change):
    checked = empty()
    with pytest.raises(DeploymentBlocked):
        o.require_empty_evidence(
            replace(checked, identity=replace(checked.identity, **change)),
            PLAN.evidence_path,
        )


@pytest.mark.parametrize(
    "change", [{"data": b"x"}, {"stable": False}, {"data": bytearray()}]
)
def test_evidence_requires_exact_zero_bytes_and_stability(change):
    with pytest.raises(DeploymentBlocked):
        o.require_empty_evidence(replace(empty(), **change), PLAN.evidence_path)


@pytest.mark.parametrize(
    "path",
    [
        PLAN.evidence_path.upper(),
        PLAN.evidence_path + ":stream",
        PLAN.evidence_path + ".",
        PLAN.evidence_path + " ",
        PLAN.evidence_path.replace("evidence", "evidence\\..\\evidence"),
        PLAN.evidence_path.replace("wake-", "other-"),
        PLAN.evidence_path.replace("F:", "C:"),
    ],
)
def test_evidence_namespace_rejects_noncanonical(path):
    with pytest.raises(DeploymentBlocked):
        o.require_evidence_path(path)


def evidence_backend(monkeypatch):
    backend = object.__new__(w.WindowsR7EvidenceBackend)
    backend._plan = PLAN
    backend._kernel = object()
    backend._advapi = object()
    monkeypatch.setattr(backend, "require_administrator", lambda: None)
    return backend


def test_evidence_initial_acl_is_append_only_and_protected(monkeypatch):
    backend = evidence_backend(monkeypatch)
    captured = []

    def convert(sddl, revision, descriptor, ignored):
        captured.append(sddl)
        descriptor._obj.value = 123
        return True

    monkeypatch.setattr(backend, "_bind", lambda *args: convert)
    backend._build_security_descriptor(False)
    assert captured == [
        "O:BA D:P(A;;FA;;;BA)(A;;FA;;;SY)"
        + f"(A;;0x{guard.TRADING_EVIDENCE_FILE_ACCESS:08X};;;{guard.TRADING_SID})"
    ]
    assert guard.TRADING_EVIDENCE_FILE_ACCESS == TRADING_FILE_READ | 4
    assert guard.TRADING_EVIDENCE_FILE_ACCESS & (2 | 0x10000 | 0x40000 | 0x80000) == 0


def test_evidence_creation_is_create_new_empty_and_independently_verified(monkeypatch):
    backend = evidence_backend(monkeypatch)
    events = []
    monkeypatch.setattr(
        backend, "_security_attributes", lambda **kw: (123, w.ctypes.c_int(1))
    )
    monkeypatch.setattr(
        backend, "_free_security_descriptor", lambda value: events.append("free")
    )
    monkeypatch.setattr(
        backend, "_close_handle", lambda value: events.append(("close", value))
    )

    def create(*args):
        events.append(("create", args))
        return 17

    monkeypatch.setattr(
        backend,
        "_bind",
        lambda lib, name, *args: create if name == "CreateFileW" else pytest.fail(name),
    )
    monkeypatch.setattr(
        backend, "observe_empty", lambda path: events.append(("verify", path))
    )
    backend.create_file(PLAN.evidence_path, b"")
    args = events[0][1]
    assert args[0] == PLAN.evidence_path
    assert args[1] == 2 | 0x20000 | 0x40000 | 0x80000
    assert args[2] == 0 and args[4] == 1
    assert args[5] == guard.FILE_FLAG_OPEN_REPARSE_POINT | guard.FILE_FLAG_WRITE_THROUGH
    assert events[1:] == ["free", ("close", 17), ("verify", PLAN.evidence_path)]
    for path, data in (
        (PLAN.evidence_path, b"x"),
        (PLAN.evidence_path.replace("wake-", "wake-a"), b""),
        (
            r6.derive_reactivation_plan(
                datetime(2026, 10, 2, tzinfo=UTC)
            ).evidence_path,
            b"",
        ),
    ):
        with pytest.raises(DeploymentBlocked):
            backend.create_file(path, data)
    assert len(events) == 4


def test_evidence_verification_reopens_and_rechecks_identity(monkeypatch):
    backend = evidence_backend(monkeypatch)
    closed = []
    item = empty().identity
    monkeypatch.setattr(backend, "_open_existing", lambda *args, **kwargs: 17)
    monkeypatch.setattr(backend, "_inspect", lambda handle: item)
    monkeypatch.setattr(backend, "_native_facts", lambda path, facts: facts)
    monkeypatch.setattr(backend, "_close_handle", closed.append)
    assert backend.observe_empty(PLAN.evidence_path) == empty()
    assert closed == [17, 17]
    values = iter((item, replace(item, file_index=12)))
    monkeypatch.setattr(backend, "_inspect", lambda handle: next(values))
    with pytest.raises(DeploymentBlocked):
        backend.observe_empty(PLAN.evidence_path)
    assert closed == [17, 17, 17]


class StageReader:
    def __init__(self, stage):
        self.stage = stage
        self.extra_children = ()
        self.evidence_extra = ()
        self.lease_bytes = PLAN.lease.canonical_bytes()
        self.lease_override = None
        self.namespace_present = None

    def require_administrator(self):
        pass

    def list_directory(self, path):
        if path.endswith("evidence"):
            names = (
                ()
                if self.stage == "INITIAL"
                else (PLAN.evidence_path.rsplit(chr(92), 1)[1],)
            ) + self.evidence_extra
        else:
            names = (
                "source",
                "launch-guard.py",
                "deployment.attestation.json",
                "deployment.attestation.sig",
                "executable-manifest.json",
                "evidence",
            ) + self.extra_children
            if self.stage == "FINAL":
                names += ("activation.lease.json",)
        return CheckedDirectory(native(path, directory=True), names, True)

    def absent(self, path):
        if path == self.namespace_present:
            return False
        if "activation.lease" in path:
            if self.lease_override is not None:
                return self.lease_override
            return not (
                self.stage == "FINAL" and path.endswith("activation.lease.json")
            )
        return True

    def read_file(self, path, limit):
        if path == PLAN.evidence_path:
            assert limit == 0
            return empty()
        return CheckedFile(
            replace(native(path), size=len(self.lease_bytes)), self.lease_bytes, True
        )


@pytest.fixture
def stage_trust(monkeypatch):
    # Isolate stage policy while retaining the existing verifier's exact root
    # inventory validation. Hash/signature checks stay in unchanged R4 helpers.
    monkeypatch.setattr(
        r4c, "_parent_native", lambda *args: native(r4.PARENT_PATH, directory=True)
    )
    monkeypatch.setattr(
        r4c,
        "_verify_old_root",
        lambda *args: r4c.RootProof(native(r4.RETIRED_PATH, directory=True), None),
    )

    def signed(reader, verifier, root, identity, extras):
        checked = reader.list_directory(root)
        r4c.require_directory(
            checked,
            root,
            {
                "source",
                "launch-guard.py",
                "deployment.attestation.json",
                "deployment.attestation.sig",
                "executable-manifest.json",
                *extras,
            },
        )
        return r4c.RootProof(checked.identity, None)

    monkeypatch.setattr(r4c, "_verify_signed_root", signed)


@pytest.mark.parametrize(
    "stage", ("INITIAL", "AFTER_CREDENTIAL", "BEFORE_LEASE", "FINAL")
)
def test_staged_complete_has_exact_r6_facts(stage, stage_trust):
    reader = StageReader(stage)
    plan = None if stage == "INITIAL" else PLAN
    activated = stage in ("BEFORE_LEASE", "FINAL")
    result = r4c.observe_r7_complete(
        reader,
        object(),
        lambda: projection(PLAN.scheduler if activated else None),
        stage,
        plan,
    )
    assert result.evidence_paths == (() if plan is None else (PLAN.evidence_path,))
    assert result.lease_final_installing_tmp_present == (stage == "FINAL", False, False)
    assert result.scheduler_disabled_nonrunning_exact is not activated
    assert result.scheduler == (PLAN.scheduler if activated else None)


@pytest.mark.parametrize("stage", ("", "READY", "COMPLETE", "initial", None))
def test_other_stages_rejected_before_host_read(stage):
    with pytest.raises(DeploymentBlocked):
        r4c.observe_r7_complete(
            object(), object(), lambda: pytest.fail("read"), stage, PLAN
        )


@pytest.mark.parametrize(
    "stage", ("INITIAL", "AFTER_CREDENTIAL", "BEFORE_LEASE", "FINAL")
)
@pytest.mark.parametrize(
    "drift", ("child", "evidence", "scheduler", "lease", "staging", "historical")
)
def test_stage_mismatches_fail_closed(stage, drift, stage_trust):
    reader = StageReader(stage)
    plan = None if stage == "INITIAL" else PLAN
    spec = PLAN.scheduler if stage in ("BEFORE_LEASE", "FINAL") else None
    item = projection(spec)
    if drift == "child":
        reader.extra_children = ("no-pycache",)
    if drift == "evidence":
        reader.evidence_extra = ("wake-foreign.jsonl",)
    if drift == "scheduler":
        item["enabled"] = not item["enabled"]
    if drift == "lease":
        reader.lease_override = False
    if drift == "staging":
        reader.namespace_present = r4.STAGING_PATH
    if drift == "historical":
        reader.namespace_present = r4.HISTORICAL_S5R8_RETIRED_PATH
    with pytest.raises(DeploymentBlocked):
        r4c.observe_r7_complete(reader, object(), lambda: item, stage, plan)


def test_final_lease_bytes_must_equal_plan(stage_trust):
    reader = StageReader("FINAL")
    reader.lease_bytes += b" "
    with pytest.raises(DeploymentBlocked):
        r4c.observe_r7_complete(
            reader, object(), lambda: projection(PLAN.scheduler), "FINAL", PLAN
        )


def test_old_r4_complete_still_rejects_runtime_evidence(stage_trust):
    reader = StageReader("AFTER_CREDENTIAL")
    with pytest.raises(DeploymentBlocked):
        r4c._verify_new_root(reader, object(), r4.CANONICAL_PATH)
    with pytest.raises(DeploymentBlocked):
        r4c.observe_post(
            reader, object(), lambda: projection(), r4.NamespaceState.COMPLETE
        )


def bound(monkeypatch):
    monkeypatch.setattr(
        w,
        "WindowsR7Reader",
        lambda: SimpleNamespace(bind_evidence=lambda evidence: None),
    )
    monkeypatch.setattr(w, "WindowsCngVerifier", lambda: object())
    monkeypatch.setattr(w, "WindowsActivationLeaseBackend", lambda: object())
    host = w.WindowsR7Boundaries(123)
    host._plan = PLAN
    monkeypatch.setattr(host, "_require_active_window", lambda: None)
    return host


@pytest.mark.parametrize(
    "phase",
    ("NEW", "ADMITTED", "PLANNED", "CREATED", "PROBE_ATTEMPTED", "SCHEDULER_VERIFIED"),
)
def test_credential_cannot_be_acquired_before_successful_probe(phase, monkeypatch):
    host = bound(monkeypatch)
    host._phase = phase
    monkeypatch.setattr(
        w, "_interactive_credential", lambda: pytest.fail("credential acquired")
    )
    with pytest.raises(DeploymentBlocked):
        host.acquire_scheduler_credential()


def test_failed_probe_latches_before_credential(monkeypatch):
    host = bound(monkeypatch)
    host._phase = "CREATED"
    host._evidence_verified = True
    monkeypatch.setattr(
        w.substrate, "probe_trading_evidence_append_open", lambda *args: None
    )
    with pytest.raises(DeploymentBlocked):
        host.probe_trading_append_open(PLAN.evidence_path)
    with pytest.raises(DeploymentBlocked):
        host.acquire_scheduler_credential()


def test_scheduler_update_exact_plan_consumes_credential_and_readback_required(
    monkeypatch,
):
    host = bound(monkeypatch)
    host._phase = "FRESH"
    host._evidence_verified = True
    credential = w.SchedulerCredential("test-only")
    host._credential = w.weakref.ref(credential)
    payloads = []

    def transport(helper, payload):
        assert helper == w.UPDATE_HELPER
        payloads.append(json.loads(payload))
        assert credential.password == ""
        return (
            0,
            b'{"schema":"arch128-r7-scheduler-update/v1","disposition":"CALL_RETURNED"}',
            b"",
        )

    monkeypatch.setattr(w, "_transport", transport)
    assert (
        host.update_scheduler(PLAN, credential) is r6.MutationDisposition.CALL_RETURNED
    )
    assert credential.password == "" and host._credential is None
    assert set(payloads[0]) == {"activation_utc", "password"}
    with pytest.raises(DeploymentBlocked):
        host.publish_lease(PLAN.lease)
    monkeypatch.setattr(w, "_read_scheduler_projection", lambda: projection())
    with pytest.raises(DeploymentBlocked):
        host.read_scheduler()
    assert host._phase == "SCHEDULER_RETURNED"
    monkeypatch.setattr(
        w, "_read_scheduler_projection", lambda: projection(PLAN.scheduler)
    )
    assert host.read_scheduler() == PLAN.scheduler
    assert host._phase == "SCHEDULER_VERIFIED"


@pytest.mark.parametrize(
    "output",
    (
        (2, b"", b""),
        (0, b"{}", b""),
        (
            0,
            b'{"schema":"arch128-r7-scheduler-update/v1","disposition":"CALL_RETURNED"}',
            b"error",
        ),
    ),
)
def test_update_ambiguity_releases_secret(output, monkeypatch):
    credential = w.SchedulerCredential("test-only")
    monkeypatch.setattr(w, "_transport", lambda *args: output)
    assert w._scheduler_update(PLAN, credential) is r6.MutationDisposition.INDETERMINATE
    assert credential.password == ""


def test_interactive_credential_rejects_redirected_input(monkeypatch):
    monkeypatch.setattr(w.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(w.getpass, "getpass", lambda *args: pytest.fail("fallback"))
    with pytest.raises(DeploymentBlocked):
        w._interactive_credential()


def test_transport_rejects_arbitrary_commands_before_launch():
    with pytest.raises(DeploymentBlocked):
        w._transport(Path("evil.ps1"))
    with pytest.raises(DeploymentBlocked):
        w._transport(w.OBSERVE_HELPER, b"secret")


def test_com_projection_duplicate_and_two_read_drift_rejected(monkeypatch):
    item = projection(PLAN.scheduler)
    for value in (
        {
            "schema": "arch128-r3-scheduler-observation/v1",
            "status": "OBSERVED",
            "first": item,
            "second": {},
        },
    ):
        monkeypatch.setattr(
            w,
            "_transport",
            lambda *args, value=value: (0, json.dumps(value).encode(), b""),
        )
        with pytest.raises(DeploymentBlocked):
            w._read_scheduler_projection()


class LeaseFake:
    def __init__(self, fail=None):
        self.files = {}
        self.events = []
        self.fail = fail

    def require_administrator(self):
        self.events.append("admin")

    def absent(self, path):
        return path not in self.files

    def create_file(self, path, data):
        assert path == w.PUBLICATION.temporary_path and path not in self.files
        assert data == PLAN.lease.canonical_bytes()
        self.events.append("tmp")
        self.files[path] = CheckedFile(
            replace(native(path), size=len(data)), data, True
        )

    def publish_create_only(self, source, dest):
        self.events.append((source, dest))
        if self.fail == dest:
            raise RuntimeError("native ambiguity")
        assert dest not in self.files
        item = self.files.pop(source)
        self.files[dest] = replace(
            item, identity=replace(item.identity, path=dest, final_path=dest)
        )

    def read_file(self, path, limit):
        return self.files[path]


def test_exact_three_stage_publication_and_no_retry(monkeypatch):
    host = bound(monkeypatch)
    host._phase = "BEFORE_LEASE"
    host._evidence_verified = True
    fake = LeaseFake()
    host._reader = host._lease = fake
    monkeypatch.setattr(
        w, "_read_scheduler_projection", lambda: projection(PLAN.scheduler)
    )
    result = host.publish_lease(PLAN.lease)
    assert result.steps == r6.LEASE_PUBLICATION_STEPS
    assert result.disposition is r6.MutationDisposition.PUBLISHED_VERIFIED
    assert list(fake.files) == [w.PUBLICATION.final_path]
    assert fake.events == [
        "admin",
        "tmp",
        (w.PUBLICATION.temporary_path, w.PUBLICATION.installing_path),
        (w.PUBLICATION.installing_path, w.PUBLICATION.final_path),
    ]
    with pytest.raises(DeploymentBlocked):
        host.publish_lease(PLAN.lease)


@pytest.mark.parametrize(
    "destination", (w.PUBLICATION.installing_path, w.PUBLICATION.final_path)
)
def test_publication_ambiguity_latches_no_cleanup_or_retry(destination, monkeypatch):
    host = bound(monkeypatch)
    host._phase = "BEFORE_LEASE"
    host._evidence_verified = True
    fake = LeaseFake(destination)
    host._reader = host._lease = fake
    monkeypatch.setattr(
        w, "_read_scheduler_projection", lambda: projection(PLAN.scheduler)
    )
    with pytest.raises(RuntimeError):
        host.publish_lease(PLAN.lease)
    assert fake.files
    with pytest.raises(DeploymentBlocked):
        host.publish_lease(PLAN.lease)


def test_historical_updater_bytes_and_semantics_unchanged():
    # Normalize checkout newline style so Windows CI and Linux agree.
    source = (ROOT / "scripts/d10_p1245_scheduler_update.ps1").read_text()
    assert hashlib.sha256(source.encode()).hexdigest() == (
        "a43c95c2c418f79022c4e7253aaebfe2011f4093aedadd3607ce56fb0ab7b96c"
    )
    assert "run_personal_desktop_unattended_capture_warmup.py" in source
    assert "$action.WorkingDirectory =" in source


def test_r7_helper_checks_exact_disabled_predecessor_and_only_three_mutations():
    source = w.UPDATE_HELPER.read_text()
    mutations = re.findall(
        r"(?m)^\s*(\$(?:definition|trigger|action)[.][\w.]+)\s*=", source
    )
    assert mutations == [
        "$trigger.StartBoundary",
        "$trigger.EndBoundary",
        "$definition.Settings.Enabled",
    ]
    expected_block = source.split("$expected = [ordered]@{", 1)[1].split("\n    }", 1)[
        0
    ]
    parsed = {}
    for key, raw in re.findall(
        r"(\w+)\s*=\s*('[^']*'|\$true|\$false|[0-9]+)", expected_block
    ):
        parsed[key] = (
            raw[1:-1]
            if raw.startswith("'")
            else raw == "$true"
            if raw.startswith("$")
            else int(raw)
        )
    expected = projection()
    expected.pop("task_state")
    expected.pop("xml_byte_length")
    assert parsed == expected
    assert source.count("State -ne 1") == 2
    assert "$first[$key].GetType() -ne $expected[$key].GetType()" in source
    assert "$definition, 4," in source
    assert source.count("RegisterTaskDefinition(") == 1
    for forbidden in (
        ".Run(",
        "Start-ScheduledTask",
        "Enable-ScheduledTask",
        "NewTask",
        "Remove-Item",
        "Write-Error",
    ):
        assert forbidden not in source
    assert "$activation.AddDays(7)" in source
    assert "$callAttempted = $true" in source


@pytest.mark.skipif(
    shutil.which("powershell.exe") is None,
    reason="Windows PowerShell parser gate runs in Windows CI",
)
def test_r7_powershell_syntax_only():
    # ParseFile cannot execute the helper or instantiate Schedule.Service.
    helper = str(w.UPDATE_HELPER).replace("'", "''")
    command = (
        "$tokens=$null; $errors=$null; "
        "[void][System.Management.Automation.Language.Parser]::ParseFile('"
        + helper
        + "', [ref]$tokens, [ref]$errors); if ($errors.Count) { exit 1 }"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")


def test_runner_registers_reviewed_wrapper_and_r7c_gate_passes():
    assert runner._checkpoint_specs()["arch128-r7"].execute is runner._r7_execute
    assert runner._r7_authority_check(ROOT) == ()
    host = Path(w.__file__).read_text()
    tree = ast.parse(host)
    for node in tree.body:
        assert not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call)
    assert "def main(" not in host


@pytest.mark.parametrize(
    "file,addition",
    (
        ("d10_arch128_r7_windows.py", "\nfrom scripts import provider_adapter\n"),
        ("d10_arch128_r7_windows.py", "\nsubprocess.run(['evil'])\n"),
        (
            "d10_arch128_r7_scheduler_update.ps1",
            "\n$definition.Principal.RunLevel = 1\n",
        ),
        ("d10_arch128_r7_scheduler_update.ps1", "\n$task.Run ()\n"),
        ("d10_arch128_r7_scheduler_update.ps1", "\n& 'evil.exe'\n"),
    ),
)
def test_r7c_authority_gate_rejects_unreviewed_effects(file, addition, tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in (
        "d10_arch128_r7_windows.py",
        "d10_arch128_r7_observation.py",
        "d10_arch128_r7_scheduler_update.ps1",
        "d10_python_substrate_windows.py",
    ):
        source = (ROOT / "scripts" / name).read_text()
        (scripts / name).write_text(
            source + (addition if name == file else ""), encoding="utf-8"
        )
    assert runner._r7c_authority_check(tmp_path)


def test_probe_authority_rejects_broadened_access(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in (
        "d10_arch128_r7_windows.py",
        "d10_arch128_r7_observation.py",
        "d10_arch128_r7_scheduler_update.ps1",
        "d10_python_substrate_windows.py",
    ):
        source = (ROOT / "scripts" / name).read_text()
        if name == "d10_python_substrate_windows.py":
            source = source.replace(
                "r6.guard.TRADING_EVIDENCE_FILE_ACCESS,",
                "r6.guard.TRADING_EVIDENCE_FILE_ACCESS | 2,",
            )
        (scripts / name).write_text(source, encoding="utf-8")
    assert runner._r7c_authority_check(tmp_path)


def test_scheduler_rejects_other_valid_activation_plan_before_transport(monkeypatch):
    host = bound(monkeypatch)
    host._phase = "FRESH"
    host._evidence_verified = True
    credential = w.SchedulerCredential("test-only")
    host._credential = w.weakref.ref(credential)
    monkeypatch.setattr(w, "_transport", lambda *args: pytest.fail("mutated"))
    other = r6.derive_reactivation_plan(datetime(2026, 10, 2, tzinfo=UTC))
    with pytest.raises(DeploymentBlocked):
        host.update_scheduler(other, credential)


@pytest.mark.parametrize("drift", ("bytes", "identity", "collision", "com"))
def test_lease_publication_readback_failure_preserves_partial_state(monkeypatch, drift):
    host = bound(monkeypatch)
    host._phase = "BEFORE_LEASE"
    host._evidence_verified = True
    fake = LeaseFake()
    host._reader = host._lease = fake
    original_read = fake.read_file

    def read(path, limit):
        item = original_read(path, limit)
        if drift == "bytes":
            return replace(item, data=item.data + b" ")
        if drift == "identity" and path == w.PUBLICATION.installing_path:
            return replace(item, identity=replace(item.identity, file_index=99))
        return item

    fake.read_file = read
    if drift == "collision":
        fake.files[w.PUBLICATION.final_path] = empty()
    monkeypatch.setattr(
        w,
        "_read_scheduler_projection",
        lambda: projection() if drift == "com" else projection(PLAN.scheduler),
    )
    with pytest.raises(DeploymentBlocked):
        host.publish_lease(PLAN.lease)
    with pytest.raises(DeploymentBlocked):
        host.publish_lease(PLAN.lease)
    assert fake.files


@pytest.mark.parametrize("failure", (None, "probe", "scheduler", "lease"))
def test_concrete_bindings_compose_with_unchanged_r6_order_and_ambiguity(
    monkeypatch, failure
):
    events = []
    fake = LeaseFake(w.PUBLICATION.final_path if failure == "lease" else None)
    fake.bind_evidence = lambda evidence: None
    monkeypatch.setattr(w, "WindowsR7Reader", lambda: fake)
    monkeypatch.setattr(w, "WindowsActivationLeaseBackend", lambda: fake)
    monkeypatch.setattr(w, "WindowsCngVerifier", lambda: object())
    monkeypatch.setattr(
        w,
        "datetime",
        SimpleNamespace(now=lambda tz: PLAN.lease.accepted_activation_utc),
    )

    class Evidence:
        def __init__(self, plan):
            assert plan == PLAN

        def create_file(self, path, data):
            assert path == PLAN.evidence_path and data == b""
            events.append("create")

        def observe_empty(self, path):
            events.append("evidence_read")
            return empty()

    monkeypatch.setattr(w, "WindowsR7EvidenceBackend", Evidence)

    def probe(pid, lease):
        events.append("probe")
        assert pid == 123 and lease == PLAN.lease
        if failure == "probe":
            raise RuntimeError("probe failure")
        return r6.TradingOpenObservation(
            guard.TRADING_SID,
            guard.TRADING_EVIDENCE_FILE_ACCESS,
            1,
            3,
            guard.FILE_FLAG_OPEN_REPARSE_POINT | guard.FILE_FLAG_WRITE_THROUGH,
            True,
            0,
        )

    monkeypatch.setattr(w.substrate, "probe_trading_evidence_append_open", probe)
    secrets = []

    def credential():
        events.append("credential")
        value = w.SchedulerCredential("test-only")
        secrets.append(value)
        return value

    monkeypatch.setattr(w, "_interactive_credential", credential)
    activated = False

    def transport(helper, payload=None):
        nonlocal activated
        assert helper == w.UPDATE_HELPER
        events.append("update")
        activated = True
        return (
            0,
            b'{"schema":"arch128-r7-scheduler-update/v1","disposition":"CALL_RETURNED"}',
            b"",
        )

    monkeypatch.setattr(w, "_transport", transport)

    def scheduler_read():
        events.append("com_read")
        return projection(
            PLAN.scheduler if activated and failure != "scheduler" else None
        )

    monkeypatch.setattr(w, "_read_scheduler_projection", scheduler_read)

    def admission(reader, verifier, scheduler, stage, plan):
        events.append("admit:" + stage)
        identity = r4.NEW_IDENTITY
        return r6.AdmissionObservation(
            identity.deployment_id,
            identity.unsigned_attestation_sha256,
            identity.certified_source_head,
            identity.certified_source_tree,
            (stage == "FINAL", False, False),
            () if plan is None else (plan.evidence_path,),
            stage not in ("BEFORE_LEASE", "FINAL"),
            plan.scheduler if stage in ("BEFORE_LEASE", "FINAL") else None,
        )

    monkeypatch.setattr(r4c, "observe_r7_complete", admission)
    host = w.WindowsR7Boundaries(123)
    result = r6.ReactivationOperator(host, host.activation_clock).run(execute_r7=True)
    assert events[:4] == ["admit:INITIAL", "create", "evidence_read", "probe"]
    if failure == "probe":
        assert "credential" not in events
    else:
        assert events[4:8] == [
            "credential",
            "admit:AFTER_CREDENTIAL",
            "evidence_read",
            "update",
        ]
        assert secrets[0].password == "" and host._credential is None
    if failure is None:
        assert result["status"] == "PASS"
        assert result["lease_publication"] is r6.MutationDisposition.PUBLISHED_VERIFIED
    else:
        assert result["status"] in ("STOPPED", "INDETERMINATE")
        assert result["reconciliation_required"] is True
        if failure == "scheduler":
            assert not fake.files
    assert (
        result["automatic_retry"] is False
        and result["automatic_rollback"] is False
        and result["automatic_cleanup"] is False
    )
    for effect in (
        "manual_task_start",
        "source_launch",
        "provider",
        "Paper-v2",
        "broker",
        "live",
    ):
        assert result[effect] == "NOT_RUN"


def test_secret_is_not_retained_by_host_after_pause_failure(monkeypatch):
    host = bound(monkeypatch)
    host._phase = "PROBED"
    monkeypatch.setattr(
        w, "_interactive_credential", lambda: w.SchedulerCredential("test-only")
    )
    credential = host.acquire_scheduler_credential()
    reference = host._credential
    assert reference() is credential
    del credential
    assert reference() is None


def test_frozen_r4_and_r5_primitive_asts_are_unchanged():
    pins = {
        "scripts/d10_python_substrate_windows.py": {
            "_reported_path": (
                "4452406c2fdc8ebee0e5816cf8a65971c7738a43f05ee7c88ea66c5a12830563"
            ),
            "_duplicate_token": (
                "2ff80347e088c334876e399098bf859e41f987a7ec8c04673563996c7823cf55"
            ),
            "_trading_token": (
                "e34a673bd17f33d92395c364b69dab38844ecc4dcab00b373c964c637fa99f49"
            ),
            "collect_trading_access": (
                "90ca647ef2199ff8fe5d5010256655d7c532250baa7f11d7f8bfc7f77092fde3"
            ),
        },
        "scripts/d10_arch128_r4_orchestration.py": {
            "_verify_new_root": (
                "b3cc30b3dad15882490bff008bebad9e0fbb3a2865763139c6a4be2bcf51c90d"
            ),
            "_post_once": (
                "ccd558b84993cd8c2a865f25249b4fb2eadfc3b67ec0d8ab96b2bc63f49f6d1f"
            ),
            "observe_post": (
                "6a1c0cb3bf50b66cc5a40e02bc38f9bd23fde9fa1f6a5339a6186f14ee5b509b"
            ),
        },
    }
    for filename, functions in pins.items():
        tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
        current = {
            node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
        }
        for name, digest in functions.items():
            assert (
                hashlib.sha256(
                    ast.dump(current[name], include_attributes=False).encode()
                ).hexdigest()
                == digest
            )


@pytest.mark.parametrize("failure", (None, "input", "output", "invalid_handle"))
def test_real_console_handles_required_before_no_echo_credential(monkeypatch, failure):
    events = []

    class NativeCall:
        def __init__(self, implementation):
            self.implementation = implementation

        def __call__(self, *args):
            return self.implementation(*args)

    def handle(identifier):
        events.append(identifier)
        return 0 if failure == "invalid_handle" else identifier

    def mode(handle, pointer):
        return not (
            (failure == "input" and handle == 0xFFFFFFF6)
            or (failure == "output" and handle == 0xFFFFFFF4)
        )

    kernel = SimpleNamespace(
        GetStdHandle=NativeCall(handle), GetConsoleMode=NativeCall(mode)
    )

    def library(path, **kwargs):
        assert path == r"C:\Windows\System32\kernel32.dll"
        return kernel

    monkeypatch.setattr(w.ctypes, "WinDLL", library, raising=False)
    if failure is None:
        w._require_interactive_console()
        assert events == [0xFFFFFFF6, 0xFFFFFFF4]
    else:
        with pytest.raises(DeploymentBlocked):
            w._require_interactive_console()


@pytest.mark.parametrize(
    "filename,addition",
    (
        ("d10_arch128_r7_readonly.py", "\ncreate_file = None\n"),
        ("d10_arch128_r7_protected.py", "\nimport ctypes\n"),
        ("d10_arch128_r7_windows.py", "\nfrom scripts import provider_adapter\n"),
    ),
)
def test_complete_r7_gate_preserves_r7a_r7b_and_runs_r7c(filename, addition, tmp_path):
    directory = tmp_path / "scripts"
    directory.mkdir()
    for name in (
        "d10_arch128_r7_readonly.py",
        "d10_arch128_r7_protected.py",
        "d10_arch128_r7_windows.py",
        "d10_arch128_r7_observation.py",
        "d10_arch128_r7_scheduler_update.ps1",
        "d10_python_substrate_windows.py",
    ):
        source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        (directory / name).write_text(
            source + (addition if name == filename else ""), encoding="utf-8"
        )
    assert runner._r7_authority_check(tmp_path)
