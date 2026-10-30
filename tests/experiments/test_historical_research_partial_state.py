"""Fake Win32 only: no test observes the real custody or OPEN namespace."""

import ast
import ctypes
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import arch146_source_authority as authority
from scripts import checkpoint_runner as runner
from trading_bot.experiments import historical_research_b2_preflight as b2
from trading_bot.experiments import historical_research_native as credentials
from trading_bot.experiments import historical_research_native_custody as disk
from trading_bot.experiments import historical_research_partial_state as observer
from trading_bot.runtime.windows_authority_security import (
    AuthorityObjectKind,
    SecurityAce,
    SecurityInspection,
)

ROOT = Path(__file__).resolve().parents[2]
PROBES = (
    disk.ATTEMPT_CLAIM_PATH,
    disk.CUSTODY_ROOT,
    disk.OPEN_PARENT,
    disk.OPEN_ROOT,
)
PARENT = SecurityInspection(
    disk.CUSTODY_PARENT,
    disk.CUSTODY_PARENT,
    AuthorityObjectKind.DIRECTORY,
    disk.ADMIN,
    True,
    (SecurityAce(disk.ADMIN, 0x1F01FF, 0, 3), SecurityAce(disk.SYSTEM, 0x1F01FF, 0, 3)),
    False,
    "F:\\",
    "NTFS",
)


@pytest.fixture(autouse=True)
def forbid_other_boundaries(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("forbidden boundary reached")

    for name in (
        "run_real_b2_readonly_preflight",
        "WindowsB2ReadOnlyObserver",
    ):
        monkeypatch.setattr(b2, name, forbidden)
    for name in (
        "observe_research_operator_token",
        "interactive_research_credentials",
        "credential_binding_is_current",
        "EphemeralHistoricalResearchCredentialSource",
        "HttpsHistoricalResearchTransport",
    ):
        monkeypatch.setattr(credentials, name, forbidden)
    for name in (
        "observe_fresh",
        "create_directory",
        "create_file",
        "flush_namespace",
        "inspect_created",
        "_parents",
        "_hold",
        "_open",
        "_absent",
    ):
        monkeypatch.setattr(disk.WindowsCustodyNative, name, forbidden)


class FakeWin32:
    def __init__(self, monkeypatch, parent=PARENT):
        self.parent = parent
        self.present = set()
        self.errors = {}
        self.close_failures = set()
        self.drive = 3
        self.opened = []
        self.closed = []
        self.inspected = []
        self.handles = {}
        self.last_error = 2
        self.inspect_failure = None
        monkeypatch.setattr(disk.WindowsCustodyNative, "_api", self.api)
        monkeypatch.setattr(disk, "inspect_open_authority_object", self.inspect)
        monkeypatch.setattr(ctypes, "get_last_error", lambda: self.last_error)

    def api(self, *args):
        # Descriptor binding passes the native instance as the first argument.
        library, name, arguments, result = args[-4:]
        assert library == "kernel32"
        assert name in {"GetDriveTypeW", "CreateFileW", "CloseHandle"}
        return {
            "GetDriveTypeW": self.get_drive,
            "CreateFileW": self.open,
            "CloseHandle": self.close,
        }[name]

    def get_drive(self, path):
        assert path == "F:\\"
        return self.drive

    def open(self, path, access, share, attributes, disposition, flags, template):
        assert access in (0x80, 0x20080)  # No read/write data or list-directory.
        assert (share, attributes, disposition, flags, template) == (
            3,
            None,
            3,
            0x02200000,
            None,
        )
        self.opened.append((path, access))
        assert path in ("F:\\", r"F:\AI", disk.CUSTODY_PARENT, *PROBES)
        if path in self.errors:
            self.last_error = self.errors[path]
            return ctypes.c_void_p(-1).value
        if path in PROBES and path not in self.present:
            self.last_error = 2
            return ctypes.c_void_p(-1).value
        handle = len(self.handles) + 100
        self.handles[handle] = path
        return handle

    def close(self, handle):
        self.closed.append(handle)
        return self.handles[handle] not in self.close_failures

    def inspect(self, handle, path, kind):
        assert self.handles[handle] == path
        self.inspected.append(path)
        if self.inspect_failure:
            raise self.inspect_failure
        return (
            self.parent
            if path == disk.CUSTODY_PARENT
            else replace(PARENT, expected_path=path, final_path=path)
        )


@pytest.mark.parametrize("reverse", [False, True])
def test_exact_parent_passes_and_never_grants_effects(monkeypatch, reverse):
    parent = replace(PARENT, aces=PARENT.aces[::-1]) if reverse else PARENT
    fake = FakeWin32(monkeypatch, parent)
    result = runner._arch146_partial_state_preflight()
    assert result["status"] == "PASS"
    assert result["classification"] == "PARTIAL_STATE_OBSERVED_EXACT"
    assert result["stable_repetitions"] == 2
    assert result["parent_path"] == disk.CUSTODY_PARENT
    assert result["parent_kind"] == "DIRECTORY"
    assert result["filesystem"] == "NTFS" and result["volume_root"] == "F:\\"
    assert result["non_reparse"] is result["dacl_protected"] is True
    assert result["owner_sid"] == disk.ADMIN
    assert result["ace_multiset"] == [
        [ace.principal_sid, ace.access_mask, ace.ace_type, ace.ace_flags]
        for ace in sorted(PARENT.aces, key=lambda ace: ace.principal_sid)
    ]
    assert all(
        result[name] is True
        for name in (
            "claim_absent",
            "protected_root_absent",
            "open_parent_absent",
            "open_root_absent",
        )
    )
    assert all(
        type(result[key]) is int and result[key] == 0
        for key in observer.EFFECT_COUNTERS
    )
    assert result["acquisition_authorized"] is False
    assert result["open_parent_creation_authorized"] is False
    assert result["protected_execution"] == "NOT_AUTHORIZED"
    assert (
        fake.opened
        == [
            ("F:\\", 0x20080),
            (r"F:\AI", 0x20080),
            (disk.CUSTODY_PARENT, 0x20080),
            *((path, 0x80) for path in PROBES),
        ]
        * 2
    )
    assert fake.inspected == ["F:\\", r"F:\AI", disk.CUSTODY_PARENT] * 2
    assert fake.closed == [102, 101, 100, 105, 104, 103]


@pytest.mark.parametrize(
    "aces",
    [
        PARENT.aces[:1],
        (*PARENT.aces, SecurityAce(disk.USERS, 0x1200A9, 0, 3)),
        (*PARENT.aces, PARENT.aces[0]),
        (PARENT.aces[0], PARENT.aces[0]),
        (replace(PARENT.aces[0], principal_sid=disk.USERS), PARENT.aces[1]),
        (replace(PARENT.aces[0], access_mask=0x1200A9), PARENT.aces[1]),
        (replace(PARENT.aces[0], ace_type=1), PARENT.aces[1]),
        (replace(PARENT.aces[0], ace_type=2), PARENT.aces[1]),
        (replace(PARENT.aces[0], ace_flags=0), PARENT.aces[1]),
        (replace(PARENT.aces[0], ace_flags=0x13), PARENT.aces[1]),
        (replace(PARENT.aces[0], ace_flags=0x0B), PARENT.aces[1]),
    ],
)
def test_exact_ace_multiset_rejects_every_field_drift(monkeypatch, aces):
    FakeWin32(monkeypatch, replace(PARENT, aces=aces))
    assert (
        observer.partial_state_readonly_preflight()["classification"]
        == "HOST_PARENT_POLICY"
    )


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"owner_sid": disk.SYSTEM}, "HOST_PARENT_POLICY"),
        ({"dacl_protected": False}, "HOST_PARENT_POLICY"),
        ({"kind": AuthorityObjectKind.FILE}, "HOST_PARENT_POLICY"),
        ({"filesystem": "FAT32"}, "HOST_VOLUME_POLICY"),
        ({"volume_root": "C:\\"}, "HOST_VOLUME_POLICY"),
        ({"is_reparse_point": True}, "HOST_REPARSE_OR_ALIAS"),
        ({"final_path": r"F:\alias"}, "HOST_REPARSE_OR_ALIAS"),
        ({"expected_path": r"F:\alias"}, "HOST_REPARSE_OR_ALIAS"),
    ],
)
def test_parent_drift_blocks(monkeypatch, changes, code):
    FakeWin32(monkeypatch, replace(PARENT, **changes))
    assert observer.partial_state_readonly_preflight()["classification"] == code


@pytest.mark.parametrize(
    "index,code",
    list(
        enumerate(
            (
                "HOST_CLAIM_PRESENT",
                "HOST_PROTECTED_ROOT_PRESENT",
                "HOST_OPEN_PARENT_PRESENT",
                "HOST_OPEN_ROOT_PRESENT",
            )
        )
    ),
)
def test_any_existing_probe_object_blocks_and_closes(monkeypatch, index, code):
    fake = FakeWin32(monkeypatch)
    fake.present.add(PROBES[index])
    assert observer.partial_state_readonly_preflight()["classification"] == code
    assert len(fake.closed) == 8


@pytest.mark.parametrize("native_error", [2, 3, 5, 32, 87, 123])
def test_only_exact_native_not_found_is_absent(monkeypatch, native_error):
    fake = FakeWin32(monkeypatch)
    fake.errors[PROBES[2]] = native_error
    result = observer.partial_state_readonly_preflight()
    assert result["classification"] == (
        "PARTIAL_STATE_OBSERVED_EXACT" if native_error in (2, 3) else "HOST_UNKNOWN"
    )
    assert len(fake.closed) == 6


@pytest.mark.parametrize("path", ["F:\\", r"F:\AI", disk.CUSTODY_PARENT])
def test_missing_parent_chain_is_unavailable(monkeypatch, path):
    fake = FakeWin32(monkeypatch)
    fake.errors[path] = 3
    assert (
        observer.partial_state_readonly_preflight()["classification"]
        == "HOST_PARENT_UNAVAILABLE"
    )
    assert len(fake.closed) == len(fake.handles)


def test_nonfixed_volume_blocks_without_opens(monkeypatch):
    fake = FakeWin32(monkeypatch)
    fake.drive = 4
    assert (
        observer.partial_state_readonly_preflight()["classification"]
        == "HOST_VOLUME_POLICY"
    )
    assert not fake.opened and not fake.closed


@pytest.mark.parametrize("path", [disk.CUSTODY_PARENT, PROBES[0]])
def test_close_failure_takes_priority_and_other_handles_close(monkeypatch, path):
    fake = FakeWin32(monkeypatch)
    fake.close_failures.add(path)
    fake.present.add(PROBES[0])
    result = observer.partial_state_readonly_preflight()
    assert result["status"] == "BLOCKED"
    assert result["classification"] == "HOST_CLOSE_AMBIGUITY"
    assert len(fake.closed) == len(fake.handles) == 8
    assert len(set(fake.closed)) == 8  # Never retry an ambiguous close.


def test_repetition_drift_blocks(monkeypatch):
    fake = FakeWin32(monkeypatch)
    observe = disk.WindowsCustodyNative().observe_partial_state_readonly
    calls = []

    def drifting():
        calls.append(1)
        if len(calls) == 2:
            fake.present.add(PROBES[1])
        return observe()

    result = observer.partial_state_readonly_preflight(observe=drifting)
    assert result["classification"] == "HOST_STATE_DRIFT"
    assert result["stable_repetitions"] == 0 and len(calls) == 2


def test_equivalent_ace_reordering_between_repetitions_is_stable(monkeypatch):
    fake = FakeWin32(monkeypatch)
    observe = disk.WindowsCustodyNative().observe_partial_state_readonly

    def reordered():
        fake.parent = replace(fake.parent, aces=fake.parent.aces[::-1])
        return observe()

    assert (
        observer.partial_state_readonly_preflight(observe=reordered)["status"] == "PASS"
    )


def test_arbitrary_native_and_observer_exceptions_are_sanitized(monkeypatch):
    secret = "arbitrary-secret-username-environment-native-error"
    fake = FakeWin32(monkeypatch)
    fake.inspect_failure = RuntimeError(secret)
    result = observer.partial_state_readonly_preflight()
    assert result["classification"] == "HOST_UNKNOWN"
    assert len(fake.closed) == 2
    assert secret not in json.dumps(result)

    def raising():
        raise RuntimeError(secret)

    result = observer.partial_state_readonly_preflight(observe=raising)
    assert result["classification"] == "HOST_UNKNOWN"
    assert secret not in json.dumps(result)
    result = observer.partial_state_readonly_preflight(
        observe=lambda: disk.CustodyPartialState(secret)
    )
    assert result["classification"] == "HOST_UNKNOWN"
    assert secret not in json.dumps(result)


def test_registration_and_current_readonly_authority():
    specs = runner._checkpoint_specs()
    spec = specs[runner.ARCH146_PARTIAL_STATE_NAME]
    assert sum(value.name == spec.name for value in specs.values()) == 1
    assert (
        spec.remote_branch
        == "feature/research-arch146-b-partial-state-observer-current"
    )
    assert spec.preflight is runner._arch146_partial_state_preflight
    assert spec.execute is None
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] == "full"
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(spec.name) == 1
    assert runner.resolve_ci_checkpoint(specs, spec.remote_branch, "push") == spec.name
    assert runner._arch146_partial_state_authority_check(ROOT) == ()
    assert authority.partial_state_observer_is_readonly(ROOT)
    predecessor = specs[runner.ARCH146_PRE_B2_NAME]
    assert predecessor.preflight is predecessor.execute is None
    assert predecessor.remote_branch == runner.ARCH146_PRE_B2_BRANCH


@pytest.mark.parametrize(
    "field,value",
    [
        ("execute", lambda: {}),
        ("preflight", None),
        ("remote_branch", "feature/wrong"),
    ],
)
def test_registration_authority_rejects_dispatch_drift(monkeypatch, field, value):
    specs = runner._checkpoint_specs()
    name = runner.ARCH146_PARTIAL_STATE_NAME
    specs[name] = replace(specs[name], **{field: value})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert (
        "146 partial-state read-only registration drift"
        in runner._arch146_partial_state_authority_check(ROOT)
    )


@pytest.mark.parametrize(
    "bad_call",
    [
        "observe_fresh",
        "create_directory",
        "create_file",
        "flush_namespace",
        "run_real_b2_readonly_preflight",
        "observe_research_operator_token",
        "interactive_research_credentials",
        "credential_binding_is_current",
        "HttpsHistoricalResearchTransport",
        "read_bytes",
    ],
)
def test_current_owner_rejects_forbidden_observer_calls(tmp_path, bad_call):
    relative = authority.PARTIAL_STATE_SOURCE
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text((ROOT / relative).read_text() + f"\n{bad_call}()\n")
    native = Path("src/trading_bot/experiments/historical_research_native_custody.py")
    (tmp_path / native).write_text((ROOT / native).read_text())
    assert not authority.partial_state_observer_is_readonly(tmp_path)


def test_existing_b2_and_freshness_sources_remain_exact():
    relative = "src/trading_bot/experiments/historical_research_native_custody.py"
    old = subprocess.run(
        ["git", "show", "cbc00675da352fd205d43a6fc4452f2a7fb33e22:" + relative],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode()

    def freshness(source):
        cls = next(
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.ClassDef) and node.name == "WindowsCustodyNative"
        )
        return ast.dump(
            next(
                node
                for node in cls.body
                if isinstance(node, ast.FunctionDef) and node.name == "observe_fresh"
            )
        )

    assert freshness(old) == freshness((ROOT / relative).read_text())
    for relative in (
        authority.B2_PREFLIGHT_SOURCE,
        "scripts/arch146_b2_readonly_preflight.py",
    ):
        old = subprocess.run(
            ["git", "show", "cbc00675da352fd205d43a6fc4452f2a7fb33e22:" + relative],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert (ROOT / relative).read_bytes().replace(b"\r\n", b"\n") == old


def test_runner_preflight_evidence_is_readonly(monkeypatch, tmp_path):
    FakeWin32(monkeypatch)
    spec = runner._checkpoint_specs()[runner.ARCH146_PARTIAL_STATE_NAME]
    source = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": spec.remote_branch,
        "porcelain": "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda _: source.copy())
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *args: source["head"])
    passed, path = runner.preflight_checkpoint(
        spec, repo_root=ROOT, evidence_root=tmp_path
    )
    report = json.loads(path.read_text())
    assert passed and report["kind"] == "read_only_preflight"
    assert report["protected_execution"] == "NOT_AUTHORIZED"
    assert report["result"]["classification"] == "PARTIAL_STATE_OBSERVED_EXACT"


def test_current_dispatch_admits_observer_and_preserves_old_delegation(monkeypatch):
    assert (
        runner.preflight_checkpoint
        is runner._arch146_partial_state_preflight_checkpoint
    )
    assert runner._readonly_candidate_authority_check(ROOT) == ()
    spec = runner._checkpoint_specs()[runner.ARCH146_PRE_B2_NAME]
    calls = []
    monkeypatch.setattr(
        runner,
        "_arch134_readonly_diagnostic_r3_preflight_checkpoint",
        lambda *args, **kwargs: calls.append(args[0]) or (False, None),
    )
    assert runner.preflight_checkpoint(spec, repo_root=ROOT, evidence_root=ROOT) == (
        False,
        None,
    )
    assert calls == [spec]


@pytest.mark.parametrize("dirty,remote", [(True, "a" * 40), (False, "c" * 40)])
def test_runner_source_failure_prevents_native_observation(
    monkeypatch, tmp_path, dirty, remote
):
    fake = FakeWin32(monkeypatch)
    spec = runner._checkpoint_specs()[runner.ARCH146_PARTIAL_STATE_NAME]
    source = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": spec.remote_branch,
        "porcelain": "?? unrelated" if dirty else "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda _: source.copy())
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *args: remote)
    with pytest.raises(RuntimeError):
        runner.preflight_checkpoint(spec, repo_root=ROOT, evidence_root=tmp_path)
    assert not fake.opened
