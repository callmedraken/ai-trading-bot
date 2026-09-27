"""Fake-boundary tests for the read-only P125-R1B native admission adapter."""

from __future__ import annotations

import ast
import hashlib
import inspect
import io
import json
import subprocess
from dataclasses import fields, replace
from pathlib import Path

import pytest

from scripts import d10_protected_deployment as d
from scripts import d10_protected_replacement as r
from scripts import d10_protected_replacement_windows as w
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    D10_LAUNCHER_RELATIVE_PATH,
    D10_SIGNING_KEY_ID,
    EXECUTABLE_MANIFEST_SCHEMA,
    ExecutableManifest,
    ExecutableManifestEntry,
    build_deployment_attestation,
)


def _scheduler_read(**changed: object) -> dict[str, object]:
    value = {
        **w._EXPECTED_SCHEDULER,
        "xml_byte_length": 83,
        "xml_sha256": "a" * 64,
    }
    value.update(changed)
    return value


def _record(
    first: dict[str, object] | None = None, second: dict[str, object] | None = None
) -> bytes:
    return json.dumps(
        {
            "schema": w.SCHEDULER_SCHEMA,
            "status": "OBSERVED",
            "first": first if first is not None else _scheduler_read(),
            "second": second if second is not None else _scheduler_read(),
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _runner(data: bytes, *, exit_code: int = 0, stderr: bytes = b""):
    def run(command, **kwargs):
        assert command == (
            w.POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(w.SCHEDULER_HELPER),
        )
        assert kwargs == {"capture_output": True, "check": False, "timeout": 30}
        return subprocess.CompletedProcess(command, exit_code, data, stderr)

    return run


def test_exact_fixed_scheduler_transport_and_diagnostic_xml_hash() -> None:
    assert not inspect.signature(w.observe_d5_scheduler).parameters
    assert not inspect.signature(w.observe_admission).parameters
    assert w.SCHEDULER_HELPER == Path(w.__file__).with_name(
        "d10_p125_d5_scheduler_observe.ps1"
    )
    observed = w._observe_d5_scheduler(_runner(_record()))
    assert observed.xml_byte_length == 83
    assert observed.xml_sha256 == "a" * 64
    assert observed.xml_sha256 != w.LEGACY_D5_XML_SHA256
    assert dict(observed.semantics) == w._EXPECTED_SCHEDULER


@pytest.mark.parametrize("field", sorted(w._EXPECTED_SCHEDULER))
def test_every_scheduler_semantic_field_independently_blocks(field: str) -> None:
    original = w._EXPECTED_SCHEDULER[field]
    wrong = (
        not original
        if type(original) is bool
        else original + 1
        if type(original) is int
        else str(original) + " "
    )
    with pytest.raises(w.AdmissionBlocked, match="scheduler_semantic_drift"):
        w._observe_d5_scheduler(
            run=_runner(_record(first=_scheduler_read(**{field: wrong})))
        )


@pytest.mark.parametrize(
    "data,exit_code,stderr",
    [
        (b"", 0, b""),
        (b"{}", 1, b""),
        (_record(), 0, b"diagnostic"),
        (b"x" * (w.MAX_SCHEDULER_STDOUT + 1), 0, b""),
        (b"{not json}", 0, b""),
        (_record() + _record(), 0, b""),
        (_record().replace(b'"OBSERVED"', b'"PASS"'), 0, b""),
    ],
)
def test_scheduler_transport_fails_closed(
    data: bytes, exit_code: int, stderr: bytes
) -> None:
    with pytest.raises(w.AdmissionBlocked):
        w._observe_d5_scheduler(_runner(data, exit_code=exit_code, stderr=stderr))


@pytest.mark.parametrize(
    "changed",
    [
        {"xml_byte_length": 84},
        {"xml_sha256": "b" * 64},
        {"action_count": 2},
        {"trigger_count": 0},
    ],
)
def test_two_read_semantic_or_xml_drift_blocks(changed: dict[str, object]) -> None:
    with pytest.raises(w.AdmissionBlocked):
        w._observe_d5_scheduler(_runner(_record(second=_scheduler_read(**changed))))


def test_scheduler_record_rejects_missing_extra_duplicate_and_wrong_types() -> None:
    candidates = [
        _record(
            first={
                key: value
                for key, value in _scheduler_read().items()
                if key != "principal_sid"
            }
        ),
        _record(first={**_scheduler_read(), "LastRunTime": "ignored?"}),
        _record(first=_scheduler_read(enabled=1)),
        _record(first=_scheduler_read(xml_byte_length=True)),
        _record().replace(
            b'"status":"OBSERVED"', b'"status":"OBSERVED","status":"OBSERVED"'
        ),
    ]
    for data in candidates:
        with pytest.raises(w.AdmissionBlocked):
            w._observe_d5_scheduler(_runner(data))


def test_helper_source_is_fixed_com_read_only_and_excludes_diagnostics() -> None:
    helper = w.SCHEDULER_HELPER.read_text(encoding="utf-8")
    assert "Schedule.Service" in helper
    assert ".GetFolder('\\')" in helper
    assert ".GetTask('AITradingBot-PD4-UnattendedPaper-v1')" in helper
    assert "$args.Count -ne 0" in helper
    assert ".Translate([System.Security.Principal.SecurityIdentifier])" in helper
    for forbidden in (
        "RegisterTask",
        "Set-ScheduledTask",
        "Get-ScheduledTask",
        "schtasks",
        "LastRunTime",
        "LastTaskResult",
        "NextRunTime",
        "TaskState",
        "Register-ScheduledTask",
        "C:\\Windows\\System32\\Tasks",
        "Get-Content",
    ):
        assert forbidden not in helper
    assert "Xml" in helper and "ComputeHash" in helper
    adapter = Path(w.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "MoveFileW",
        "CreateDirectoryW",
        "WriteFile",
        "SetSecurityInfo",
        "RegisterTask",
        "Set-ScheduledTask",
        "Get-ScheduledTask",
    ):
        assert forbidden not in adapter


def test_sid_form_principal_requires_windows_round_trip() -> None:
    helper = w.SCHEDULER_HELPER.read_text(encoding="utf-8")
    sid_branch = helper.split("if ($userId -match '^S-1-') {", 1)[1].split(
        "} else {", 1
    )[0]
    assert "SecurityIdentifier]::new($userId)" in sid_branch
    assert "$sid.Translate([System.Security.Principal.NTAccount])" in sid_branch
    assert (
        "$account.Translate([System.Security.Principal.SecurityIdentifier])"
        in sid_branch
    )
    assert sid_branch.index("$sid.Translate(") < sid_branch.index("$account.Translate(")
    assert "$resolvedSid = $sid.Value" in helper
    frozen_sid = "S-1-5-21-1397534616-3988210162-180023805-1009"
    assert f"if ($resolvedSid -ne '{frozen_sid}')" in helper


def test_frozen_prior_p1245_lineage_and_explicit_admission_fields() -> None:
    assert w._FROZEN_PRIOR_P1245_LINEAGE == (
        "2fd79986-fb50-5fe4-800a-2d4aa5e7307c",
        "9f3d111b-25bb-5ee4-9abf-f5215a32b826",
        "NOT_RUN_NO_D10_ACTIVATION_OR_SCHEDULER_MUTATION",
    )
    source = ast.parse(Path(w.__file__).read_text(encoding="utf-8"))
    constructions = [
        node
        for node in ast.walk(source)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "AdmissionFacts"
    ]
    assert len(constructions) == 1
    assert constructions[0].args == []
    assert {keyword.arg for keyword in constructions[0].keywords} == {
        field.name for field in fields(r.AdmissionFacts)
    }


def test_scheduler_process_capture_is_bounded_without_real_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProcess:
        stdout = io.BytesIO(b"x" * (w.MAX_SCHEDULER_STDOUT + 500))
        stderr = io.BytesIO(b"y" * (w.MAX_SCHEDULER_STDERR + 500))

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def wait(self, *, timeout: int | None = None) -> int:
            assert timeout == 30
            return 0

    def fake_popen(command, **kwargs):
        assert command == (
            w.POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(w.SCHEDULER_HELPER),
        )
        assert kwargs == {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
        }
        return FakeProcess()

    monkeypatch.setattr(w.subprocess, "Popen", fake_popen)
    result = w._run_scheduler_bounded(
        (
            w.POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(w.SCHEDULER_HELPER),
        ),
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert len(result.stdout) == w.MAX_SCHEDULER_STDOUT + 1
    assert len(result.stderr) == w.MAX_SCHEDULER_STDERR + 1


def _native(
    path: str, *, directory: bool, serial: int = 17, bad: str = "", size: int = 0
) -> d.NativeObject:
    owner, protected, aces = (
        d.expected_parent_policy()
        if path == r.PARENT_PATH
        else d.expected_policy(directory)
    )
    result = d.NativeObject(
        path,
        path,
        directory,
        owner,
        protected,
        aces,
        False,
        3,
        "F:\\",
        "NTFS",
        serial,
        1000 + len(path),
        1,
        size,
    )
    if bad == "acl":
        return replace(result, aces=())
    if bad == "reparse":
        return replace(result, reparse=True)
    if bad == "link":
        return replace(result, links=2)
    if bad == "final":
        return replace(result, final_path=r"F:\Other")
    return result


class FakeNative:
    def __init__(self) -> None:
        self.directories: dict[str, tuple[str, ...]] = {}
        self.files: dict[str, bytes] = {}
        self.bad: dict[str, str] = {}
        self.serial = 17
        self.serial_overrides: dict[str, int] = {}
        self.calls: list[tuple[str, str]] = []
        self.parent_index = 1000 + len(r.PARENT_PATH)

    def require_administrator(self) -> None:
        self.calls.append(("administrator", ""))

    def list_directory(self, path: str) -> d.CheckedDirectory:
        self.calls.append(("directory", path))
        if path not in self.directories:
            raise w.AdmissionBlocked("missing directory")
        item = _native(
            path,
            directory=True,
            serial=self.serial_overrides.get(path, self.serial),
            bad=self.bad.get(path, ""),
        )
        if path == r.PARENT_PATH:
            item = replace(item, file_index=self.parent_index)
        return d.CheckedDirectory(item, self.directories[path], True)

    def read_file(self, path: str, limit: int) -> d.CheckedFile:
        self.calls.append(("file", path))
        if path not in self.files:
            raise w.AdmissionBlocked("missing file")
        data = self.files[path]
        return d.CheckedFile(
            _native(
                path,
                directory=False,
                serial=self.serial_overrides.get(path, self.serial),
                bad=self.bad.get(path, ""),
                size=len(data),
            ),
            data,
            True,
        )

    def absent(self, path: str) -> bool:
        self.calls.append(("absent", path))
        return path not in self.files and path not in self.directories


def test_native_path_allowlist_rejects_caller_selected_or_traversal() -> None:
    allowed = w._WindowsReplacementReader._allowed
    assert allowed(r.PARENT_PATH, directory=True)
    assert allowed(r.CANONICAL_PATH, directory=True)
    assert allowed(r.STAGING_PATH, directory=True)
    assert allowed(r.RETIRED_PATH, directory=None)
    for path in (
        r"F:\Other\D10",
        r.CANONICAL_PATH + r"\..\other",
        r.CANONICAL_PATH + r"\secret.txt",
    ):
        assert not allowed(path, directory=False)
        assert not allowed(path, directory=True)
        assert not allowed(path, directory=None)


def test_source_snapshot_requires_exact_inventory_acl_and_bytes() -> None:
    root = r.STAGING_PATH
    source = root + r"\source"
    launcher = D10_LAUNCHER_RELATIVE_PATH
    entries = (
        ExecutableManifestEntry(
            launcher,
            4,
            "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a",
        ),
        ExecutableManifestEntry(
            "src/trading_bot/__init__.py",
            4,
            "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a",
        ),
    )
    manifest = ExecutableManifest(EXECUTABLE_MANIFEST_SCHEMA, entries)
    native = FakeNative()
    native.directories = {
        source: ("scripts", "src"),
        source + r"\scripts": (launcher.split("/")[-1],),
        source + r"\src": ("trading_bot",),
        source + r"\src\trading_bot": ("__init__.py",),
    }
    native.files = {
        source + "\\" + launcher.replace("/", "\\"): bytes((1, 2, 3, 4)),
        source + r"\src\trading_bot\__init__.py": bytes((1, 2, 3, 4)),
    }
    assert w._snapshot(native, root, manifest) == 17
    native.bad[next(iter(native.files))] = "reparse"
    with pytest.raises(d.DeploymentBlocked):
        w._snapshot(native, root, manifest)
    native.bad.clear()
    native.directories[source + r"\scripts"] = (launcher.split("/")[-1], "UNEXPECTED")
    with pytest.raises(d.DeploymentBlocked):
        w._snapshot(native, root, manifest)


def test_admission_two_fresh_passes_and_scheduler_are_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FakeNative()
    native.directories[r.PARENT_PATH] = (
        r.CANONICAL_PATH.rsplit("\\", 1)[-1],
        r.STAGING_PATH.rsplit("\\", 1)[-1],
    )
    monkeypatch.setattr(w, "_verify_old", lambda backend, verifier: (object(), 17))
    monkeypatch.setattr(w, "_verify_new", lambda backend, manifest: 17)
    result = w._observe_admission(native, object(), _runner(_record()))
    assert r.classify_namespace(result.namespace) is r.NamespaceState.OLD_CANONICAL
    assert result.facts.all_exact()
    assert [item for item in native.calls if item[0] == "administrator"] == [
        ("administrator", ""),
        ("administrator", ""),
    ]


def test_admission_blocks_native_identity_drift_between_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DriftingNative(FakeNative):
        def list_directory(self, path: str) -> d.CheckedDirectory:
            if path == r.PARENT_PATH and any(
                call == ("directory", r.PARENT_PATH) for call in self.calls
            ):
                self.parent_index += 1
            return super().list_directory(path)

    native = DriftingNative()
    native.directories[r.PARENT_PATH] = (
        r.CANONICAL_PATH.rsplit("\\", 1)[-1],
        r.STAGING_PATH.rsplit("\\", 1)[-1],
    )
    monkeypatch.setattr(w, "_verify_old", lambda backend, verifier: (object(), 17))
    monkeypatch.setattr(w, "_verify_new", lambda backend, manifest: 17)
    with pytest.raises(w.AdmissionBlocked, match="admission_revalidation_drift"):
        w._observe_admission(native, object(), _runner(_record()))


class FakeVerifier:
    key_id = D10_SIGNING_KEY_ID

    def verify(self, message: bytes, signature: bytes) -> bool:
        return bool(message and signature)


def _full_native(monkeypatch: pytest.MonkeyPatch) -> FakeNative:
    native = FakeNative()
    source_files = {
        D10_LAUNCHER_RELATIVE_PATH: b"launcher",
        "src/trading_bot/__init__.py": b"package",
    }
    entries = tuple(
        ExecutableManifestEntry(path, len(data), hashlib.sha256(data).hexdigest())
        for path, data in sorted(source_files.items())
    )
    manifest = ExecutableManifest(EXECUTABLE_MANIFEST_SCHEMA, entries)
    old_guard, new_guard = b"old guard", b"new guard"
    head = r.NEW_IDENTITY.certified_source_head
    tree = r.NEW_IDENTITY.certified_source_tree
    old_att = build_deployment_attestation(
        certified_source_head=head,
        certified_source_tree=tree,
        production_python_version="3.14.3",
        launch_guard_byte_length=len(old_guard),
        launch_guard_sha256=hashlib.sha256(old_guard).hexdigest(),
        executable_manifest_sha256=manifest.digest,
        executable_file_count=len(entries),
    )
    new_att = build_deployment_attestation(
        certified_source_head=head,
        certified_source_tree=tree,
        production_python_version="3.14.3",
        launch_guard_byte_length=len(new_guard),
        launch_guard_sha256=hashlib.sha256(new_guard).hexdigest(),
        executable_manifest_sha256=manifest.digest,
        executable_file_count=len(entries),
    )
    signature = (1).to_bytes(32, "big") * 2
    monkeypatch.setattr(
        r,
        "OLD_IDENTITY",
        r.DeploymentIdentity(
            old_att.deployment_id,
            manifest.digest,
            len(entries),
            sum(len(data) for data in source_files.values()),
            len(old_guard),
            hashlib.sha256(old_guard).hexdigest(),
            hashlib.sha256(old_att.canonical_bytes()).hexdigest(),
            hashlib.sha256(signature).hexdigest(),
        ),
    )
    monkeypatch.setattr(
        r,
        "NEW_IDENTITY",
        r.DeploymentIdentity(
            new_att.deployment_id,
            manifest.digest,
            len(entries),
            sum(len(data) for data in source_files.values()),
            len(new_guard),
            hashlib.sha256(new_guard).hexdigest(),
            hashlib.sha256(new_att.canonical_bytes()).hexdigest(),
            certified_source_head=head,
            certified_source_tree=tree,
        ),
    )
    native.directories[r.PARENT_PATH] = (
        r.CANONICAL_PATH.rsplit("\\", 1)[-1],
        r.STAGING_PATH.rsplit("\\", 1)[-1],
    )
    for root, guard in (
        (r.CANONICAL_PATH, old_guard),
        (r.STAGING_PATH, new_guard),
    ):
        native.directories[root] = (
            (
                "source",
                "launch-guard.py",
                "deployment.attestation.json",
                "deployment.attestation.sig",
                "executable-manifest.json",
            )
            if root == r.CANONICAL_PATH
            else ("source", "launch-guard.py")
        )
        source = root + r"\source"
        native.directories[source] = ("scripts", "src")
        native.directories[source + r"\scripts"] = (
            D10_LAUNCHER_RELATIVE_PATH.split("/")[-1],
        )
        native.directories[source + r"\src"] = ("trading_bot",)
        native.directories[source + r"\src\trading_bot"] = ("__init__.py",)
        for path, data in source_files.items():
            native.files[source + "\\" + path.replace("/", "\\")] = data
        native.files[root + r"\launch-guard.py"] = guard
    native.files[r.CANONICAL_PATH + r"\deployment.attestation.json"] = (
        old_att.canonical_bytes()
    )
    native.files[r.CANONICAL_PATH + r"\deployment.attestation.sig"] = signature
    native.files[r.CANONICAL_PATH + r"\executable-manifest.json"] = (
        manifest.canonical_bytes()
    )
    return native


def test_complete_fake_native_admission_and_closed_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = _full_native(monkeypatch)
    result = w._observe_admission(native, FakeVerifier(), _runner(_record()))
    assert result.facts.all_exact()
    assert r.classify_namespace(result.namespace) is r.NamespaceState.OLD_CANONICAL
    assert all(
        operation in {"administrator", "directory", "file", "absent"}
        for operation, _ in native.calls
    )


def test_invalid_frozen_prior_p1245_status_cannot_admit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = _full_native(monkeypatch)
    monkeypatch.setattr(
        w,
        "_FROZEN_PRIOR_P1245_LINEAGE",
        (*w._FROZEN_PRIOR_P1245_LINEAGE[:2], "P1245_COMPLETED"),
    )
    original_facts = r.AdmissionFacts
    constructed: list[dict[str, object]] = []

    def record_facts(**values: object) -> r.AdmissionFacts:
        constructed.append(values)
        return original_facts(**values)

    monkeypatch.setattr(r, "AdmissionFacts", record_facts)
    with pytest.raises(w.AdmissionBlocked, match="admission_facts_incomplete"):
        w._observe_admission(native, FakeVerifier(), _runner(_record()))
    assert len(constructed) == 1
    assert constructed[0]["no_prior_d10_activation_or_scheduler_mutation"] is False


@pytest.mark.parametrize(
    "drift",
    [
        "old_guard",
        "new_guard",
        "old_signature",
        "source",
        "acl",
        "reparse",
        "lease",
        "volume",
    ],
)
def test_full_fake_native_drift_blocks(
    monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    native = _full_native(monkeypatch)
    if drift == "old_guard":
        native.files[r.CANONICAL_PATH + r"\launch-guard.py"] = b"wrong"
    elif drift == "new_guard":
        native.files[r.STAGING_PATH + r"\launch-guard.py"] = b"wrong"
    elif drift == "old_signature":
        native.files[r.CANONICAL_PATH + r"\deployment.attestation.sig"] = b"wrong"
    elif drift == "source":
        native.files[r.STAGING_PATH + r"\source\src\trading_bot\__init__.py"] = b"wrong"
    elif drift == "acl":
        native.bad[r.CANONICAL_PATH] = "acl"
    elif drift == "reparse":
        native.bad[r.STAGING_PATH + r"\source"] = "reparse"
    elif drift == "lease":
        native.files[r.CANONICAL_PATH + r"\activation.lease.json"] = b"bad"
    elif drift == "volume":
        native.serial_overrides[r.STAGING_PATH] = 18
    with pytest.raises(w.AdmissionBlocked):
        w._observe_admission(native, FakeVerifier(), _runner(_record()))


def test_admission_rejects_parent_case_collision_and_absence_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FakeNative()
    native.directories[r.PARENT_PATH] = (
        r.CANONICAL_PATH.rsplit("\\", 1)[-1],
        r.STAGING_PATH.rsplit("\\", 1)[-1],
        "d10",
    )
    monkeypatch.setattr(w, "_verify_old", lambda backend, verifier: (object(), 17))
    monkeypatch.setattr(w, "_verify_new", lambda backend, manifest: 17)
    with pytest.raises(w.AdmissionBlocked):
        w._observe_admission(native, object(), _runner(_record()))
    native.directories[r.PARENT_PATH] = native.directories[r.PARENT_PATH][:2]
    native.directories[r.RETIRED_PATH] = ()
    with pytest.raises(w.AdmissionBlocked):
        w._observe_admission(native, object(), _runner(_record()))
