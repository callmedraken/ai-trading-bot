"""Fake-boundary tests for P125 native admission and fixed mutations."""

from __future__ import annotations

import ast
import ctypes
import hashlib
import inspect
import io
import json
import subprocess
from dataclasses import fields, replace
from pathlib import Path

import pytest
from scripts.d10_protected_deployment_windows import WindowsReplacementStagingBackend

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
    parse_executable_manifest,
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


def test_staging_writer_is_fixed_and_excludes_trust_and_lease() -> None:
    writer = object.__new__(WindowsReplacementStagingBackend)
    writer._source_files = frozenset()
    writer._source_directories = frozenset()
    writer.bind_source_inventory(
        tuple(sorted((D10_LAUNCHER_RELATIVE_PATH, "src/trading_bot/__init__.py")))
    )
    assert writer._allowed_directory_create(r.STAGING_PATH)
    assert writer._allowed_directory_create(r.STAGING_PATH + r"\source.installing")
    assert writer._allowed_file_create(r.STAGING_PATH + r"\launch-guard.py.installing")
    assert writer._allowed_file_create(
        r.STAGING_PATH + r"\source.installing\src\trading_bot\__init__.py"
    )
    for rejected in (
        r.CANONICAL_PATH,
        r.STAGING_PATH + r"\activation.lease.json",
        r.STAGING_PATH + r"\deployment.attestation.json.installing",
        r.STAGING_PATH + r"\source.installing\..\escape.py",
    ):
        assert not writer._allowed_directory_create(rejected)
        assert not writer._allowed_file_create(rejected)
    assert not writer._allowed_file_create(d.TRUST_INSTALLING_PATHS[0])
    assert w._WindowsReplacementReader._allowed(r.STAGING_PATH, directory=None)
    assert not w._WindowsReplacementReader._allowed(
        r.STAGING_PATH + r"\..\elsewhere", directory=None
    )


def test_rename_source_open_requests_delete_and_no_follow() -> None:
    reader = object.__new__(w._WindowsReplacementReader)
    reader._kernel = object()
    seen: list[tuple[object, ...]] = []

    def create(*args):
        seen.append(args)
        return 41

    reader._bind = lambda _lib, name, _args, _result: (
        create if name == "CreateFileW" else None
    )
    assert reader._open_rename_source(r.CANONICAL_PATH) == 41
    path, access, share, _, disposition, flags, _ = seen[0]
    assert path == r.CANONICAL_PATH
    assert access & 0x00010000  # DELETE
    assert share == 1
    assert disposition == 3
    assert flags & 0x00200000  # no follow
    assert flags & 0x02000000  # directory backup semantics
    assert reader._open_rename_parent() == 41
    parent_path, parent_access, parent_share, _, parent_disposition, parent_flags, _ = (
        seen[1]
    )
    assert parent_path == r.PARENT_PATH
    assert parent_access & 0x0004  # FILE_ADD_SUBDIRECTORY
    assert parent_access & 0x0020  # FILE_TRAVERSE
    assert parent_share == 1
    assert parent_disposition == 3
    assert parent_flags & 0x00200000
    assert parent_flags & 0x02000000
    with pytest.raises(w.AdmissionBlocked, match="rename_source_path_unreviewed"):
        reader._open_rename_source(r.RETIRED_PATH)


class FakeRenameNative:
    def __init__(self, step: r.RenameStep) -> None:
        self.source_path, self.destination_path = w._fixed_rename_paths(step)
        self.parent = _native(r.PARENT_PATH, directory=True)
        self.source = _native(self.source_path, directory=True)
        self.old_source = self.source
        self.events: list[tuple[object, ...]] = []
        self.renamed = False
        self.collision = False
        self.native_false = False
        self.native_exception = False
        self.pre_drift = False
        self.post_drift = False
        self.parent_pre_drift = False
        self.parent_post_drift = False
        self.close_failure = False
        self.source_inspections = 0
        self.parent_inspections = 0
        self._kernel = object()

    def require_administrator(self) -> None:
        self.events.append(("administrator",))

    def list_directory(self, path: str) -> d.CheckedDirectory:
        if path == r.RETIRED_PATH:
            return d.CheckedDirectory(
                replace(self.old_source, path=path, final_path=path), (), True
            )
        assert path == r.PARENT_PATH
        return d.CheckedDirectory(
            self.parent,
            (
                r.RETIRED_PATH.rsplit("\\", 1)[-1],
                r.STAGING_PATH.rsplit("\\", 1)[-1],
            ),
            True,
        )

    def _open_rename_parent(self) -> int:
        self.events.append(("open_parent", r.PARENT_PATH))
        return 11

    def _open_rename_source(self, path: str) -> int:
        self.events.append(("open_source", path))
        assert path == self.source_path
        return 22

    def _inspect(self, handle: int, path: str) -> d.NativeObject:
        self.events.append(("inspect", handle, path))
        if handle == 11:
            self.parent_inspections += 1
            if self.parent_pre_drift and self.parent_inspections == 2:
                return replace(self.parent, file_index=self.parent.file_index + 1)
            if self.parent_post_drift and self.parent_inspections == 3:
                return replace(self.parent, file_index=self.parent.file_index + 1)
            return self.parent
        assert handle == 22 and path == self.source_path
        self.source_inspections += 1
        if self.pre_drift and self.source_inspections == 2:
            return replace(self.source, file_index=self.source.file_index + 1)
        if self.renamed:
            result = replace(self.source, final_path=self.destination_path)
            if self.post_drift:
                result = replace(result, aces=())
            return result
        return self.source

    def absent(self, path: str) -> bool:
        self.events.append(("absent", path))
        assert path == self.destination_path
        return not self.collision

    def _bind(self, _library, name, _args, _result):
        assert name == "SetFileInformationByHandle"

        def rename(handle, info_class, pointer, size):
            info = ctypes.cast(pointer, ctypes.POINTER(w._FileRenameInfo)).contents
            name_bytes = ctypes.string_at(
                ctypes.addressof(info) + w._FileRenameInfo.file_name.offset,
                info.file_name_length,
            )
            leaf = name_bytes.decode("utf-16-le")
            self.events.append(
                (
                    "rename",
                    handle,
                    info_class,
                    info.replace_if_exists,
                    info.root_directory,
                    leaf,
                    size,
                )
            )
            if self.native_exception:
                raise OSError("ambiguous native call")
            if self.native_false:
                return False
            self.renamed = True
            return True

        return rename

    def _close(self, handle: int) -> None:
        self.events.append(("close", handle))
        if self.close_failure:
            raise OSError("close uncertain")


@pytest.mark.parametrize(
    "step",
    [r.RenameStep.OLD_TO_RETIRED, r.RenameStep.STAGING_TO_CANONICAL],
)
def test_handle_pinned_fixed_rename_success(step: r.RenameStep) -> None:
    native = FakeRenameNative(step)
    outcome = w._rename_fixed_step(native, step, native.source, native.parent)
    assert outcome is r.MutationOutcome.SUCCESS
    rename = next(event for event in native.events if event[0] == "rename")
    assert rename[1:6] == (
        22,
        3,
        0,
        11,
        native.destination_path.rsplit("\\", 1)[-1],
    )
    assert all(
        event[0] != "close" for event in native.events[: native.events.index(rename)]
    )
    assert native.events.index(rename) > next(
        index
        for index, event in enumerate(native.events)
        if event == ("inspect", 22, native.source_path)
    )
    assert ("inspect", 22, native.source_path) in native.events[
        native.events.index(rename) + 1 :
    ]
    assert native.events[-2:] == [("close", 22), ("close", 11)]


@pytest.mark.parametrize(
    "failure",
    [
        "collision",
        "native_false",
        "native_exception",
        "pre_drift",
        "post_drift",
        "parent_pre_drift",
        "parent_post_drift",
        "close_failure",
        "volume",
    ],
)
def test_rename_uncertainty_is_indeterminate_without_retry(failure: str) -> None:
    native = FakeRenameNative(r.RenameStep.OLD_TO_RETIRED)
    if failure == "volume":
        native.source = replace(native.source, volume_serial=18)
    else:
        setattr(native, failure, True)
    assert (
        w._rename_fixed_step(
            native, r.RenameStep.OLD_TO_RETIRED, native.source, native.parent
        )
        is r.MutationOutcome.INDETERMINATE
    )
    assert len([event for event in native.events if event[0] == "rename"]) <= 1
    assert native.events[-2:] == [("close", 22), ("close", 11)]


def test_fixed_rename_rejects_unknown_step_and_wrong_admitted_identity() -> None:
    with pytest.raises(w.AdmissionBlocked, match="rename_step_unreviewed"):
        w._fixed_rename_paths("F:\\arbitrary")
    native = FakeRenameNative(r.RenameStep.OLD_TO_RETIRED)
    assert (
        w._rename_fixed_step(
            native,
            r.RenameStep.OLD_TO_RETIRED,
            replace(native.source, file_index=999),
            native.parent,
        )
        is r.MutationOutcome.INDETERMINATE
    )
    assert not any(event[0] == "rename" for event in native.events)


def _rename_admission(native: FakeRenameNative) -> w.AdmissionObservation:
    facts = r.AdmissionFacts(*([True] * len(fields(r.AdmissionFacts))))
    scheduler = w._observe_d5_scheduler(_runner(_record()))
    return w.AdmissionObservation(
        r.NamespaceObservation(
            r.RootObservation(r.CANONICAL_PATH, True, r.OLD_IDENTITY),
            r.RootObservation(r.STAGING_PATH, True, r.NEW_IDENTITY),
            r.RootObservation(r.RETIRED_PATH, False),
        ),
        facts,
        scheduler,
        native.parent,
        native.source,
        _native(r.STAGING_PATH, directory=True),
    )


def test_fixed_session_requires_first_step_then_allows_second_in_same_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FakeRenameNative(r.RenameStep.OLD_TO_RETIRED)
    admission = _rename_admission(native)
    monkeypatch.setattr(w, "_observe_admission", lambda *_args: admission)
    session = w._FixedRenameSession(native, admission, object(), object())
    with pytest.raises(w.AdmissionBlocked, match="rename_step_not_ready"):
        session.publish_staged_root()
    assert session.retire_old_root() is r.MutationOutcome.SUCCESS
    assert session.result.phase is r.Phase.READY_TO_PUBLISH_NEW
    assert len([event for event in native.events if event[0] == "rename"]) == 1
    native.source_path, native.destination_path = w._fixed_rename_paths(
        r.RenameStep.STAGING_TO_CANONICAL
    )
    native.source = admission.new_native
    native.renamed = False
    native.source_inspections = 0
    monkeypatch.setattr(w, "_verify_old", lambda *_args: (object(), 17))
    monkeypatch.setattr(w, "_verify_new", lambda *_args: 17)
    monkeypatch.setattr(w, "_observe_d5_scheduler", lambda *_args: admission.scheduler)
    assert session.publish_staged_root() is r.MutationOutcome.SUCCESS
    assert session.result.phase is r.Phase.VERIFY_PUBLICATION
    assert len([event for event in native.events if event[0] == "rename"]) == 2


def test_indeterminate_first_step_blocks_second_and_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FakeRenameNative(r.RenameStep.OLD_TO_RETIRED)
    native.native_false = True
    admission = _rename_admission(native)
    monkeypatch.setattr(w, "_observe_admission", lambda *_args: admission)
    session = w._FixedRenameSession(native, admission, object(), object())
    assert session.retire_old_root() is r.MutationOutcome.INDETERMINATE
    assert session.result.phase is r.Phase.BLOCKED
    with pytest.raises(w.AdmissionBlocked, match="rename_step_not_ready"):
        session.retire_old_root()
    with pytest.raises(w.AdmissionBlocked, match="rename_step_not_ready"):
        session.publish_staged_root()
    assert len([event for event in native.events if event[0] == "rename"]) == 1


def test_rename_session_cannot_start_without_verified_staging() -> None:
    native = FakeRenameNative(r.RenameStep.OLD_TO_RETIRED)
    admission = _rename_admission(native)
    with pytest.raises(w.AdmissionBlocked, match="rename_session_admission_incomplete"):
        w._FixedRenameSession(
            native, replace(admission, new_native=None), object(), object()
        )
    assert native.events == []


class FakeStagingWriter:
    def __init__(self, native: FakeNative) -> None:
        self.native = native
        self.events: list[tuple[object, ...]] = []
        self.corrupt_guard = False

    def bind_source_inventory(self, paths: tuple[str, ...]) -> None:
        self.events.append(("bind", paths))

    def _child(self, path: str, *, add: bool) -> None:
        parent, leaf = path.rsplit("\\", 1)
        children = set(self.native.directories[parent])
        if add:
            children.add(leaf)
        else:
            children.remove(leaf)
        self.native.directories[parent] = tuple(sorted(children))

    def create_directory(self, path: str) -> None:
        self.events.append(("directory", path))
        assert path not in self.native.directories
        self.native.directories[path] = ()
        self._child(path, add=True)

    def create_file(self, path: str, data: bytes) -> None:
        self.events.append(("file", path, data))
        assert path not in self.native.files
        self.native.files[path] = (
            b"wrong"
            if self.corrupt_guard and path.endswith("launch-guard.py.installing")
            else data
        )
        self._child(path, add=True)

    def publish_create_only(self, installing: str, final: str) -> None:
        self.events.append(("publish", installing, final))
        assert final not in self.native.files and final not in self.native.directories
        if installing in self.native.files:
            self.native.files[final] = self.native.files.pop(installing)
        else:
            for mapping in (self.native.directories, self.native.files):
                moved = {
                    final + key[len(installing) :]: value
                    for key, value in mapping.items()
                    if key == installing or key.startswith(installing + "\\")
                }
                for key in tuple(mapping):
                    if key == installing or key.startswith(installing + "\\"):
                        del mapping[key]
                mapping.update(moved)
        self._child(installing, add=False)
        self._child(final, add=True)


def _staging_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[FakeNative, d.CertifiedMaterial, FakeStagingWriter]:
    native = _full_native(monkeypatch)
    for mapping in (native.directories, native.files):
        for path in tuple(mapping):
            if path == r.STAGING_PATH or path.startswith(r.STAGING_PATH + "\\"):
                del mapping[path]
    native.directories[r.PARENT_PATH] = ("D10",)
    manifest = parse_executable_manifest(
        native.files[r.CANONICAL_PATH + r"\executable-manifest.json"]
    )
    guard = b"new guard"
    attestation = build_deployment_attestation(
        certified_source_head=r.NEW_IDENTITY.certified_source_head,
        certified_source_tree=r.NEW_IDENTITY.certified_source_tree,
        production_python_version="3.14.3",
        launch_guard_byte_length=len(guard),
        launch_guard_sha256=hashlib.sha256(guard).hexdigest(),
        executable_manifest_sha256=manifest.digest,
        executable_file_count=len(manifest.entries),
    )
    files = tuple(
        d.SourceFile(
            entry.relative_path,
            native.files[
                r.CANONICAL_PATH + "\\source\\" + entry.relative_path.replace("/", "\\")
            ],
            entry.sha256,
        )
        for entry in manifest.entries
    )
    material = d.CertifiedMaterial(object(), manifest, attestation, files, guard)
    return native, material, FakeStagingWriter(native)


def test_staging_constructs_exact_guard_source_only_and_reverifies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native, material, writer = _staging_fixture(monkeypatch)
    w._construct_fixed_staging(
        material, writer, native, FakeVerifier(), _runner(_record())
    )
    assert native.directories[r.STAGING_PATH] == ("launch-guard.py", "source")
    assert native.files[r.STAGING_PATH + r"\launch-guard.py"] == material.guard_bytes
    assert not any(
        name in path
        for path in (*native.files, *native.directories)
        if path.startswith(r.STAGING_PATH + "\\")
        for name in ("deployment.attestation", "activation.lease", "no-pycache")
    )
    assert (
        "publish",
        r.STAGING_PATH + r"\source.installing",
        r.STAGING_PATH + r"\source",
    ) in writer.events
    assert writer.events[-1] == (
        "publish",
        r.STAGING_PATH + r"\launch-guard.py.installing",
        r.STAGING_PATH + r"\launch-guard.py",
    )
    assert any(
        call == ("file", r.STAGING_PATH + r"\launch-guard.py") for call in native.calls
    )
    assert r.CANONICAL_PATH in native.directories


def test_staging_existing_or_wrong_material_blocks_without_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native, material, writer = _staging_fixture(monkeypatch)
    native.directories[r.STAGING_PATH] = ()
    with pytest.raises(w.AdmissionBlocked):
        w._construct_fixed_staging(
            material, writer, native, FakeVerifier(), _runner(_record())
        )
    assert writer.events == []
    native.directories.pop(r.STAGING_PATH)
    with pytest.raises(w.AdmissionBlocked, match="staging_material_identity"):
        w._construct_fixed_staging(
            replace(material, guard_bytes=b"wrong"),
            writer,
            native,
            FakeVerifier(),
            _runner(_record()),
        )
    assert writer.events == []


def test_unexpected_replacement_sibling_blocks_staging_before_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native, material, writer = _staging_fixture(monkeypatch)
    native.directories[r.PARENT_PATH] = ("D10", "D10.replacement-unreviewed")
    with pytest.raises(
        w.AdmissionBlocked, match="replacement_reserved_sibling_conflict"
    ):
        w._construct_fixed_staging(
            material, writer, native, FakeVerifier(), _runner(_record())
        )
    assert writer.events == []


def test_staging_reverification_failure_leaves_partial_state_for_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native, material, writer = _staging_fixture(monkeypatch)
    writer.corrupt_guard = True
    with pytest.raises(w.AdmissionBlocked, match="new_guard_identity"):
        w._construct_fixed_staging(
            material, writer, native, FakeVerifier(), _runner(_record())
        )
    assert r.STAGING_PATH in native.directories
    assert r.CANONICAL_PATH in native.directories
    assert not any(
        event[0] in ("delete", "rollback", "rename_root") for event in writer.events
    )
