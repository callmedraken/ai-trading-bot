"""D1Q-R2 source tests never open production targets or grant production rights."""

import ctypes
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from trading_bot.review_paper import production_paper_runtime_acl as acl
from trading_bot.runtime import windows_authority_security as security

SID = "S-1-5-21-100-200-300-1001"
OTHER = "S-1-5-21-100-200-300-1002"
LOGON = "S-1-5-5-111-222"


class FakeNative:
    def __init__(self):
        self.objects = {}
        self.events = []
        self.handles = {}
        self.fault = None
        self.inventory = ("armed-sessions.sqlite", "paper.sqlite")
        for i, path in enumerate(acl.ARCH134_RUNTIME_TARGETS):
            s = security.SecurityInspection(
                path,
                path,
                acl._kind(path),
                acl.ADMINISTRATORS,
                False,
                (
                    security.SecurityAce(acl.ADMINISTRATORS, security.FILE_ALL_ACCESS),
                    security.SecurityAce(acl.SYSTEM, security.FILE_ALL_ACCESS),
                    security.SecurityAce(LOGON, acl.DIAGNOSED_RX),
                ),
                False,
                "F:\\",
                "NTFS",
            )
            self.objects[path] = acl.Observation(s, (123, i + 1, 1))

    def open(self, path, *, update):
        assert path in acl.ARCH134_RUNTIME_TARGETS
        self.events.append(("open", path, update))
        handle = object()
        self.handles[handle] = path
        return handle

    def inspect(self, handle, path):
        assert self.handles[handle] == path
        self.events.append(("inspect", path))
        if self.fault == "postcheck" and any(e[0] == "apply" for e in self.events):
            raise ValueError("PRIVATE NATIVE USER ACL SID PATH")
        return self.objects[path]

    def names(self):
        return self.inventory

    def apply(self, handle, policy):
        path = self.handles[handle]
        self.events.append(("apply", path))
        if self.fault == path:
            raise ValueError("PRIVATE NATIVE USER ACL SID PATH")
        before = self.objects[path]
        self.objects[path] = replace(
            before,
            security=replace(
                before.security,
                owner_sid=policy.owner_sid,
                aces=policy.aces,
                dacl_protected=True,
            ),
        )
        if self.fault == "identity":
            self.objects[path] = replace(self.objects[path], identity=(123, 999, 1))

    def close(self, handle):
        path = self.handles.pop(handle)
        self.events.append(("close", path))
        if self.fault == "close" and any(e[0] == "apply" for e in self.events):
            raise ValueError("PRIVATE CLOSE")


@pytest.fixture
def native(monkeypatch):
    fake = FakeNative()
    monkeypatch.setattr(acl, "NativeRuntimeAcl", lambda: fake)
    monkeypatch.setattr(acl, "resolve_current_token_sid", lambda: SID)
    monkeypatch.setattr(acl, "require_administrator_token", lambda: None)
    return fake


def execute():
    return acl.inspect_or_provision(expected_runtime_sid=SID, execute=True)


def exact(fake, path):
    policy = acl.runtime_policy(
        SID, directory=acl._kind(path) is security.AuthorityObjectKind.DIRECTORY
    )
    s = fake.objects[path].security
    fake.objects[path] = replace(
        fake.objects[path],
        security=replace(
            s, owner_sid=policy.owner_sid, aces=policy.aces, dacl_protected=True
        ),
    )


def test_exact_masks_and_inheritance_flags():
    assert (
        security.OBJECT_INHERIT_ACE,
        security.CONTAINER_INHERIT_ACE,
        security.INHERIT_ONLY_ACE,
        security.INHERITED_ACE,
    ) == (1, 2, 8, 16)
    db = acl.runtime_policy(SID, directory=False)
    root = acl.runtime_policy(SID, directory=True)
    assert db.owner_sid == root.owner_sid == acl.ADMINISTRATORS
    assert db.dacl_protected is root.dacl_protected is True
    assert db.aces == (
        security.SecurityAce(acl.ADMINISTRATORS, 0x1F01FF),
        security.SecurityAce(acl.SYSTEM, 0x1F01FF),
        security.SecurityAce(SID, security.sqlite_trading_file_rights()),
    )
    assert db.aces[-1].access_mask == 0x12019F
    assert not db.aces[-1].access_mask & (
        security.DELETE | security.WRITE_DAC | security.WRITE_OWNER
    )
    assert all(a.ace_flags == 0 for a in db.aces)
    assert root.aces[2] == security.SecurityAce(SID, 0x1200AB)
    assert not root.aces[2].access_mask & (
        security.FILE_DELETE_CHILD
        | security.FILE_ADD_SUBDIRECTORY
        | security.DELETE
        | security.WRITE_DAC
        | security.WRITE_OWNER
    )
    assert root.aces[3] == security.SecurityAce(SID, 0x13019F, ace_flags=9)
    assert root.aces[3].ace_flags & security.INHERIT_ONLY_ACE
    assert not root.aces[3].ace_flags & security.CONTAINER_INHERIT_ACE
    assert acl.DIAGNOSED_RX == 0x1200A9


def test_readonly_exact_diagnosed_state(native, monkeypatch):
    monkeypatch.setattr(
        acl, "require_administrator_token", lambda: pytest.fail("diagnostic elevation")
    )
    result = acl.inspect_or_provision()
    assert result["status"] == "NEEDS_PROVISIONING" and result["result"] == "PASS"
    assert not any(e[0] == "apply" or (e[0] == "open" and e[2]) for e in native.events)
    assert not native.handles
    text = json.dumps(result)
    assert all(v not in text for v in (SID, LOGON, "John", "PRIVATE", "F:"))
    assert len(result["runtime_sid_digest"]) == 64


@pytest.mark.parametrize("sid", [OTHER, "John", "S-1-5-18", "", None])
def test_expected_sid_mismatch_before_open_or_apply(native, sid):
    result = acl.inspect_or_provision(expected_runtime_sid=sid, execute=True)
    assert result["status"] == "BLOCKED" and not native.events


def test_non_elevated_blocks_before_sid_or_open(native, monkeypatch):
    def denied():
        raise ValueError("PRIVATE ADMIN")

    monkeypatch.setattr(acl, "require_administrator_token", denied)
    monkeypatch.setattr(
        acl, "resolve_current_token_sid", lambda: pytest.fail("token after rejection")
    )
    assert execute()["status"] == "BLOCKED"
    assert not native.events


@pytest.mark.parametrize("target", range(3))
@pytest.mark.parametrize(
    "fault",
    [
        "owner",
        "reparse",
        "path",
        "expected_path",
        "volume",
        "fs",
        "kind",
        "extra",
        "third",
        "inherited",
        "protected",
        "mask",
        "deny",
    ],
)
def test_unexpected_before_state_blocks(native, target, fault):
    path = acl.ARCH134_RUNTIME_TARGETS[target]
    s = native.objects[path].security
    changes = {
        "owner": {"owner_sid": SID},
        "reparse": {"is_reparse_point": True},
        "path": {"final_path": r"F:\AITradingBot"},
        "expected_path": {"expected_path": r"F:\AITradingBot"},
        "volume": {"volume_root": "C:\\"},
        "fs": {"filesystem": "ReFS"},
        "kind": {
            "kind": security.AuthorityObjectKind.FILE
            if target == 0
            else security.AuthorityObjectKind.DIRECTORY
        },
        "extra": {"aces": (*s.aces, security.SecurityAce(SID, 1))},
        "third": {"aces": (*s.aces[:2], security.SecurityAce(SID, acl.DIAGNOSED_RX))},
        "inherited": {"aces": (*s.aces[:2], replace(s.aces[2], ace_flags=16))},
        "protected": {"dacl_protected": True},
        "mask": {"aces": (*s.aces[:2], replace(s.aces[2], access_mask=1))},
        "deny": {"aces": (*s.aces[:2], replace(s.aces[2], ace_type=1))},
    }
    native.objects[path] = replace(
        native.objects[path], security=replace(s, **changes[fault])
    )
    assert execute()["status"] == "BLOCKED"
    assert not any(e[0] == "apply" for e in native.events)
    assert not native.handles


@pytest.mark.parametrize("target", [1, 2])
@pytest.mark.parametrize("links", [0, 2])
def test_link_drift_blocks(native, target, links):
    path = acl.ARCH134_RUNTIME_TARGETS[target]
    native.objects[path] = replace(
        native.objects[path], identity=(123, target + 1, links)
    )
    assert execute()["status"] == "BLOCKED"
    assert not any(e[0] == "apply" for e in native.events)


@pytest.mark.parametrize("logon", ["S-1-5-5-0-1", "S-1-5-5-4294967295-99"])
def test_structural_logon_sid_admitted_without_machine_binding(native, logon):
    for path, o in native.objects.items():
        native.objects[path] = replace(
            o,
            security=replace(
                o.security,
                aces=(
                    *o.security.aces[:2],
                    security.SecurityAce(logon, acl.DIAGNOSED_RX),
                ),
            ),
        )
    assert acl.inspect_or_provision()["status"] == "NEEDS_PROVISIONING"


@pytest.mark.parametrize("target", range(3))
def test_partial_state_blocks_without_repair(native, target):
    exact(native, acl.ARCH134_RUNTIME_TARGETS[target])
    assert execute()["status"] == "BLOCKED"
    assert not any(e[0] == "apply" for e in native.events)


@pytest.mark.parametrize(
    "inventory",
    [
        (),
        ("paper.sqlite",),
        ("armed-sessions.sqlite", "paper.sqlite", "paper.sqlite-journal"),
        ("armed-sessions.sqlite-wal", "paper.sqlite"),
    ],
)
def test_inventory_sidecar_ambiguity(native, inventory):
    native.inventory = inventory
    assert execute()["status"] == "BLOCKED"
    assert not any(e[0] == "apply" for e in native.events)


def test_mutation_order_same_pinned_postchecks_and_independent_reopen(native):
    result = execute()
    root, paper, session = acl.ARCH134_RUNTIME_TARGETS
    assert result["status"] == "PROVISIONED" and result["result"] == "PASS"
    assert [e[1] for e in native.events if e[0] == "apply"] == [paper, session, root]
    assert result["acl_applies_verified"] == result["acl_apply_attempts"] == 3
    assert [e[1] for e in native.events if e[0] == "open"] == [root, paper, session] * 2
    for i, event in enumerate(native.events):
        if event[0] == "apply":
            assert native.events[i + 1] == ("inspect", event[1])
    assert not native.handles
    assert all(
        value == 0
        for key, value in result.items()
        if key.endswith("mutations") or key == "provider_calls"
    )
    assert all(e[1] in acl.ARCH134_RUNTIME_TARGETS for e in native.events)


@pytest.mark.parametrize(
    "fault", ["postcheck", "identity", "close", *acl.ARCH134_RUNTIME_TARGETS]
)
def test_apply_failure_terminal_no_retry_or_rollback(native, fault):
    native.fault = fault
    result = execute()
    assert result["status"] == "STOPPED_AFTER_APPLY" and result["result"] == "FAIL"
    applies = [e[1] for e in native.events if e[0] == "apply"]
    assert len(applies) == len(set(applies)) and len(applies) <= 3
    assert not native.handles
    assert "PRIVATE" not in json.dumps(result)


@pytest.mark.parametrize("execute_mode", [False, True])
def test_already_exact_idempotent(native, execute_mode):
    for path in acl.ARCH134_RUNTIME_TARGETS:
        exact(native, path)
    result = execute() if execute_mode else acl.inspect_or_provision()
    assert result["status"] == "ALREADY_PROVISIONED" and result["result"] == "PASS"
    assert result["acl_apply_attempts"] == 0
    assert not any(e[0] == "apply" for e in native.events)


@pytest.mark.parametrize("phase", ["before", "fresh", "open"])
def test_reobservation_and_reopen_drift_block_without_retry(native, phase):
    original = native.inspect
    calls = 0

    def inspect(handle, path):
        nonlocal calls
        calls += 1
        observed = original(handle, path)
        if phase == "before" and calls == 4:
            return replace(observed, identity=(123, 999, 1))
        if phase == "fresh" and len([e for e in native.events if e[0] == "open"]) > 3:
            return replace(observed, identity=(123, 999, 1))
        return observed

    native.inspect = inspect
    if phase == "open":
        original_open = native.open

        def open_target(path, *, update):
            if len([e for e in native.events if e[0] == "open"]) == 3:
                raise ValueError("PRIVATE REOPEN")
            return original_open(path, update=update)

        native.open = open_target
    result = execute()
    assert result["status"] == (
        "BLOCKED" if phase == "before" else "STOPPED_AFTER_APPLY"
    )
    applies = [e[1] for e in native.events if e[0] == "apply"]
    assert len(applies) == len(set(applies))
    assert not native.handles


def test_durable_progress_precedes_each_native_apply(native):
    published = []
    original = native.apply

    def apply(handle, policy):
        assert published[-1]["status"] == "STOPPED_AFTER_APPLY"
        assert (
            published[-1]["acl_apply_attempts"]
            == len([e for e in native.events if e[0] == "apply"]) + 1
        )
        original(handle, policy)

    native.apply = apply
    result = acl.inspect_or_provision(
        expected_runtime_sid=SID,
        execute=True,
        publish=lambda state: published.append(dict(state)),
    )
    assert result["status"] == "PROVISIONED"
    assert [s["acl_apply_attempts"] for s in published] == [1, 2, 3]


@pytest.mark.parametrize(
    "replacement",
    [
        ("expected_runtime_sid != sid", "False"),
        ("require_administrator_token()", "pass"),
        ("path not in ARCH134_RUNTIME_TARGETS", "False"),
        ("FILE_TRAVERSE | FILE_LIST_DIRECTORY | FILE_ADD_FILE", "FILE_ALL_ACCESS"),
    ],
)
def test_structural_security_expansion_rejected_with_refreshed_blob_pin(
    tmp_path, monkeypatch, replacement
):
    from scripts import checkpoint_runner as runner

    root = Path(runner.__file__).resolve().parents[1]
    relative = "src/trading_bot/review_paper/production_paper_runtime_acl.py"
    for file in runner.ARCH134_RUNTIME_ACL_SOURCE_PINS:
        target = tmp_path / file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / file).read_bytes())
    target = tmp_path / relative
    old, new = replacement
    source = target.read_text()
    # Formatting can split this expression over separate lines.
    if old == "FILE_TRAVERSE | FILE_LIST_DIRECTORY | FILE_ADD_FILE":
        old = "FILE_TRAVERSE\n    | FILE_LIST_DIRECTORY\n    | FILE_ADD_FILE"
    assert old in source
    target.write_text(source.replace(old, new, 1), encoding="utf-8")
    pins = dict(runner.ARCH134_RUNTIME_ACL_SOURCE_PINS)
    pins[relative] = runner._git_blob_sha1(target)
    monkeypatch.setattr(runner, "ARCH134_RUNTIME_ACL_SOURCE_PINS", pins)
    assert any(
        "structural" in f for f in runner._arch134_runtime_acl_authority_check(tmp_path)
    )


def test_checked_close_ambiguity_is_not_retried(monkeypatch):
    class Close:
        calls = 0

        def __call__(self, value):
            self.calls += 1
            return False

    close = Close()
    monkeypatch.setattr(security, "require_windows_platform", lambda: None)
    from types import SimpleNamespace

    monkeypatch.setattr(
        security, "_kernel32", lambda: SimpleNamespace(CloseHandle=close)
    )
    handle = security.WindowsHandle(123)
    with pytest.raises(Exception, match="ambiguous"):
        security.close_security_object_checked(handle)
    assert close.calls == 1 and handle.value == 0


@pytest.mark.parametrize("directory", [False, True])
@pytest.mark.parametrize("update", [False, True])
def test_fixed_native_open_uses_no_follow_and_deny_delete_sharing(
    monkeypatch, directory, update
):
    from types import SimpleNamespace

    calls = []

    class Create:
        def __call__(self, *args):
            calls.append(args)
            return 123

    monkeypatch.setattr(security, "require_windows_platform", lambda: None)
    monkeypatch.setattr(
        security, "_kernel32", lambda: SimpleNamespace(CreateFileW=Create())
    )
    path = acl.ARCH134_RUNTIME_TARGETS[0 if directory else 1]
    kind = (
        security.AuthorityObjectKind.DIRECTORY
        if directory
        else security.AuthorityObjectKind.FILE
    )
    handle = security.open_arch134_runtime_object(path, kind, for_update=update)
    assert handle.value == 123
    call = calls[0]
    assert call[0] == path and call[4] == security.OPEN_EXISTING
    assert call[5] & security.FILE_FLAG_OPEN_REPARSE_POINT
    assert bool(call[5] & security.FILE_FLAG_BACKUP_SEMANTICS) == directory
    assert call[2] == (3 if directory else 1)
    assert not call[2] & security.FILE_SHARE_DELETE
    assert bool(call[1] & security.WRITE_DAC) == update
    assert bool(call[1] & security.WRITE_OWNER) == update


def test_cli_source_failure_stops_before_native(native, monkeypatch, capsys):
    def blocked(*args):
        raise ValueError("PRIVATE SOURCE PATH")

    monkeypatch.setattr(acl, "admit_source", blocked)
    assert acl.main(args("--diagnose")) == 3 and not native.events
    assert "PRIVATE" not in capsys.readouterr().out


def test_registered_source_only_authority_and_canonical_mapping(monkeypatch):
    from scripts import checkpoint_runner as runner

    root = Path(runner.__file__).resolve().parents[1]
    assert runner._arch134_runtime_acl_authority_check(root) == ()
    spec = runner._checkpoint_specs()[runner.ARCH134_RUNTIME_ACL_NAME]
    assert spec.preflight is spec.execute is None
    assert runner.ACTIVE_CI_CHECKPOINTS[-1] == spec.name
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), acl.BRANCH, "push")
        == spec.name
    )
    assert runner.resolve_ci_certification_profile(spec.name) == "robinhood"


@pytest.mark.parametrize("kind", ["repository", "existing", "link"])
def test_evidence_redirection_rejected_before_acl(native, monkeypatch, tmp_path, kind):
    output = tmp_path / "acl.json"
    roots = (tmp_path,) if kind == "repository" else ()
    if kind == "existing":
        output.write_bytes(b"preserve")
    if kind == "link":
        # Metadata no-follow rejection; no symlink privilege needed.
        monkeypatch.setattr(Path, "is_symlink", lambda self: self == output)
    monkeypatch.setattr(acl, "admit_source", lambda *_: roots)
    assert (
        acl.main(
            args(
                "--execute",
                acl.EXECUTE_INTERLOCK,
                "--expected-runtime-sid",
                SID,
                "--evidence",
                str(output),
            )
        )
        == 3
    )
    assert not native.events


def args(*more):
    return ["--expected-head", "a" * 40, "--expected-tree", "b" * 40, *more]


def test_cli_diagnostic_zero_evidence(native, monkeypatch, capsys):
    monkeypatch.setattr(acl, "admit_source", lambda *_: ())
    assert acl.main(args("--diagnose")) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "NEEDS_PROVISIONING"


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--execute", "wrong"],
        ["--execute", acl.EXECUTE_INTERLOCK],
        ["--diagnose", "--expected-runtime-sid", SID],
        ["--diagnose", "--path", r"F:\AITradingBot"],
    ],
)
def test_cli_interlock_and_arguments_before_effects(native, extra, capsys):
    assert acl.main(args(*extra)) == 3
    assert not native.events and "PRIVATE" not in capsys.readouterr().out


def test_fresh_evidence_execute_and_no_overwrite(native, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(acl, "admit_source", lambda *_: ())
    output = tmp_path / "acl.json"
    command = args(
        "--execute",
        acl.EXECUTE_INTERLOCK,
        "--expected-runtime-sid",
        SID,
        "--evidence",
        str(output),
    )
    assert acl.main(command) == 0
    evidence = output.read_bytes()
    assert json.loads(evidence)["status"] == "PROVISIONED"
    assert SID.encode() not in evidence
    count = len(native.events)
    assert acl.main(command) == 3 and output.read_bytes() == evidence
    assert len(native.events) == count
    capsys.readouterr()


@pytest.mark.parametrize(
    "path",
    [
        r"F:\AITradingBot",
        r"F:\AITradingBot\Arch134D1\paper.sqlite-journal",
        r"F:\AITradingBot\Other",
        r"C:\other",
    ],
)
def test_native_open_rejects_arbitrary_paths_before_win32(path, monkeypatch):
    monkeypatch.setattr(
        security, "_kernel32", lambda: pytest.fail("Win32 on arbitrary path")
    )
    with pytest.raises(ValueError):
        security.open_arch134_runtime_object(
            path, security.AuthorityObjectKind.FILE, for_update=True
        )


def test_import_inert_and_exact_tracked_closure():
    root = Path(__file__).resolve().parents[2]
    program = """import ctypes, sys, json
def forbidden(*args, **kwargs):
    raise AssertionError('native work on import')
ctypes.WinDLL = forbidden
from trading_bot.review_paper import production_paper_runtime_acl
files = (m.__file__ for n, m in sys.modules.items()
         if n == 'trading_bot' or n.startswith('trading_bot.'))
print(json.dumps(sorted(files)))
"""
    child = subprocess.run(
        [sys.executable, "-B", "-"],
        input=program,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(root / "src")},
    )
    from scripts import checkpoint_runner as runner

    for file in json.loads(child.stdout):
        assert (
            Path(file).resolve().relative_to(root).as_posix()
            in runner.ARCH134_RUNTIME_ACL_SOURCE_PINS
        )


@pytest.mark.skipif(os.name != "nt", reason="test-only native NTFS inheritance")
def test_native_disposable_file_inheritance_and_protected_database(tmp_path):
    # No production operator or production path. Owner is the test's current user.
    sid = security.resolve_current_token_sid()
    directory = tmp_path / "inheritance"
    assert not str(directory).startswith(r"F:\AITradingBot")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create_dir = kernel.CreateDirectoryW
    create_dir.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p]
    create_dir.restype = ctypes.c_int32
    policy = security.SecurityPolicy(
        sid,
        (
            security.SecurityAce(sid, security.FILE_ALL_ACCESS),
            security.SecurityAce(
                sid,
                security.sqlite_trading_file_rights() | security.DELETE,
                ace_flags=9,
            ),
        ),
    )
    with security.build_security_attributes(policy) as bundle:
        assert create_dir(str(directory), ctypes.byref(bundle.attributes))
    create = kernel.CreateFileW
    create.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create.restype = ctypes.c_void_p
    journal = directory / "test-journal"
    value = create(
        str(journal),
        security.READ_CONTROL | security.FILE_WRITE_DATA | security.DELETE,
        7,
        None,
        1,
        security.FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    assert value not in (None, 0, ctypes.c_void_p(-1).value)
    handle = security.WindowsHandle(value)
    try:
        _, protected, aces = security.inspect_handle_security(
            value, security.SecurityObjectType.FILE
        )
        assert not protected
        assert (
            security.SecurityAce(
                sid,
                security.sqlite_trading_file_rights() | security.DELETE,
                ace_flags=16,
            )
            in aces
        )
        assert all(not a.ace_flags & security.INHERIT_ONLY_ACE for a in aces)
    finally:
        security.close_security_object_checked(handle)
    journal.unlink()
    database = directory / "test.sqlite"
    db_policy = security.SecurityPolicy(
        sid, (security.SecurityAce(sid, security.sqlite_trading_file_rights()),)
    )
    with security.build_security_attributes(db_policy) as bundle:
        value = create(
            str(database),
            security.READ_CONTROL,
            7,
            ctypes.byref(bundle.attributes),
            1,
            security.FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
    assert value not in (None, 0, ctypes.c_void_p(-1).value)
    try:
        _, protected, aces = security.inspect_handle_security(
            value, security.SecurityObjectType.FILE
        )
        assert protected and aces == db_policy.aces
        assert not any(a.access_mask & security.DELETE for a in aces)
    finally:
        security.close_security_object_checked(security.WindowsHandle(value))
    # Only the test parent has FILE_DELETE_CHILD.
    database.unlink()


@pytest.mark.parametrize(
    "addition",
    [
        "import socket\n",
        "import importlib\n",
        "def bad():\n    eval('1')\n",
        "def bad(x):\n    x.icacls()\n",
        "def bad(x):\n    x.takeown()\n",
        "def bad(x):\n    x.register_task()\n",
        "def bad(x):\n    x.CredWriteW()\n",
        "def bad(x):\n    x.place_equity_order()\n",
        "def bad(x):\n    x.execute('INSERT')\n",
        "def bad(x):\n    x.rglob('*')\n",
        "def bad(x):\n    x.walk()\n",
    ],
)
def test_authority_rejects_expansion_even_with_new_blob_pin(
    tmp_path, monkeypatch, addition
):
    from scripts import checkpoint_runner as runner

    root = Path(runner.__file__).resolve().parents[1]
    for relative in runner.ARCH134_RUNTIME_ACL_SOURCE_PINS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / relative).read_bytes())
    relative = "src/trading_bot/review_paper/production_paper_runtime_acl.py"
    target = tmp_path / relative
    target.write_text(target.read_text() + addition, encoding="utf-8")
    pins = dict(runner.ARCH134_RUNTIME_ACL_SOURCE_PINS)
    pins[relative] = runner._git_blob_sha1(target)
    monkeypatch.setattr(runner, "ARCH134_RUNTIME_ACL_SOURCE_PINS", pins)
    failures = runner._arch134_runtime_acl_authority_check(tmp_path)
    assert any("import" in f or "forbidden" in f or "structural" in f for f in failures)
