"""133-K fake native edges only. Never open production or retained scratch objects."""

import ast
import ctypes
import hashlib
import inspect
import io
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.arch133_acl import (
    administrator,
    primitive,
    read_only,
    recovery,
    root_policy_apply,
)
from trading_bot.arch133_acl import retained_reads as reads

SECRET = "private-native-diagnostic-must-not-escape"
HEAD, TREE = "a" * 40, "b" * 40


@pytest.fixture(autouse=True)
def no_real_native(monkeypatch):
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: pytest.fail("native reached"))
    monkeypatch.setattr(recovery, "_attempt_consumed", False)


@pytest.fixture
def fake(monkeypatch):
    state = SimpleNamespace(
        calls=[],
        applied=False,
        status=0,
        root_reads=0,
        fail=None,
        drift=None,
        source_reads=0,
    )
    root = read_only.DirectoryObservation(
        read_only.ADMINISTRATORS_SID, True, read_only.ADMIN_ACES, recovery.ROOT_IDENTITY
    )
    parent = replace(root, identity=(recovery.ROOT_IDENTITY[0], 3))
    names = tuple((name, i + 10) for i, name in enumerate(reads.FINAL_NAMES))
    state.names = names
    state.root = root

    def source():
        state.source_reads += 1
        return {
            "source_head": HEAD if state.drift != "source" else TREE,
            "source_tree": TREE,
        }

    def open_directory(path, **kw):
        state.calls.append(("open", path, kw))
        if state.fail == "open" and path == recovery.TARGET_PATH:
            raise read_only.RootOpenError(5)
        return path

    def close(handle):
        state.calls.append(("close", handle))
        if state.fail == "close" and handle == recovery.TARGET_PATH:
            raise RuntimeError(SECRET)

    def security(handle, path):
        state.calls.append(("security", path))
        if path != recovery.TARGET_PATH:
            if state.drift == "parent":
                return replace(parent, identity=(1, 2)), "e" * 64
            return parent, "c" * 64
        state.root_reads += 1
        if state.applied:
            if state.fail == "readback":
                raise RuntimeError(SECRET)
            after = replace(root, aces=read_only.ROOT_ACES)
            changes = {
                "post_policy": {"aces": read_only.ROOT_ACES[:-1]},
                "identity": {"identity": (1, 2)},
                "reparse": {"reparse": True},
                "filesystem": {"filesystem": "FAT32"},
                "owner": {"owner_sid": read_only.SYSTEM_SID},
                "protected": {"protected": False},
            }
            return replace(after, **changes.get(state.fail, {})), "d" * 64
        changed = root
        if state.root_reads > 1:
            changed = replace(root, identity=(1, 2)) if state.drift == "root" else root
        return changed, (
            "f" * 64 if state.drift == "security" else recovery.PRE_SECURITY_SHA256
        )

    def namespace(handle):
        state.calls.append(("namespace", handle))
        if (state.applied and state.fail == "namespace") or state.drift == "namespace":
            return tuple((name, i + 100) for i, (name, _) in enumerate(names))
        return names

    def snapshot(handle, name):
        digest = recovery.FILE_HASHES[name]
        if (state.applied and state.fail == "file_hash") or state.drift == "file_hash":
            digest = "e" * 64
        file_id = dict(namespace(recovery.TARGET_PATH))[name]
        if state.fail == "file_identity" and state.applied:
            file_id += 1
        return (recovery.ROOT_IDENTITY[0], file_id), digest

    def apply(handle):
        if state.fail == "prepare":
            raise RuntimeError(SECRET)
        state.calls.append(("set", handle))
        state.applied = True
        if state.fail == "apply":
            raise RuntimeError(SECRET)
        return state.status

    monkeypatch.setattr(recovery, "_source", source)
    monkeypatch.setattr(administrator, "administrator_sid", lambda: "S-1-5-21-1-2-3-4")
    monkeypatch.setattr(read_only, "open_directory", open_directory)
    monkeypatch.setattr(read_only, "close_handle", close)
    monkeypatch.setattr(read_only, "inspect_directory_security", security)
    monkeypatch.setattr(reads, "namespace", namespace)
    monkeypatch.setattr(reads, "open_retained_file", lambda name: name)
    monkeypatch.setattr(reads, "file_snapshot", snapshot)
    monkeypatch.setattr(recovery, "apply_root_policy_status", apply)
    monkeypatch.setattr(
        root_policy_apply, "native_application_attempts", lambda: int(state.applied)
    )
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: True))
    return state


def authority(plan):
    digest = plan["plan_sha256"]
    return digest, "AUTHORIZE Q133-K ROOT-ACL " + digest


def test_fixed_pins_canonical_plan_and_zero_mutations(fake, monkeypatch):
    for name in ("AI_TRADING_BOT_ROOT", "TEMP", "TMP", "AI_TRADING_BOT_RECOVERY_ROOT"):
        monkeypatch.setenv(name, r"C:\wrong")
    assert recovery.TARGET_PATH == r"F:\AITradingBot\Arch133"
    assert recovery.ROOT_IDENTITY == (1855336320, 1407374886183770)
    assert recovery.PRE_SECURITY_SHA256 == (
        "b8fc336502437d1599a257da32a20bb62966663bb20fa44694d614c0f59361a3"
    )
    assert tuple(inspect.signature(recovery.plan_recovery).parameters) == ()
    assert tuple(inspect.signature(recovery.execute_recovery_once).parameters) == (
        "reviewed",
        "authorization",
    )
    plan = recovery.plan_recovery()
    assert recovery.plan_recovery() == plan
    digest = plan.pop("plan_sha256")
    assert digest == hashlib.sha256(recovery.canonical(plan)).hexdigest()
    assert plan["file_hashes"] == {
        "activation.json": (
            "37873b490c3f2ccced53431c599e40ca54fdc008e09e9bfdb38eb61d10f3cab2"
        ),
        "host-binding.json": (
            "c1106d1937dab615da0f12eb9170c020add2ffdece3d3b88a10d2edf26eb47ab"
        ),
        "paper.sqlite": (
            "384828dd21e9abc82afabec955184eed22cf57839e72bcd43c74d162534663b9"
        ),
        "wake.sqlite": (
            "210812b956aba6d59dcf3cfbf398ebd628c972cfffbb6dd39bd96ef308a6887f"
        ),
    }
    assert plan["pre_application_policy"] == "ADMIN_SYSTEM_ONLY"
    assert plan["open_requested_access"] == 0xC00E0081
    assert plan["open_share_mode"] == plan["open_disposition"] == 3
    assert plan["open_flags"] == 0x02200000
    assert plan["intended_owner_sid"] == read_only.ADMINISTRATORS_SID
    assert plan["intended_dacl_protected"] is True
    assert plan["intended_aces"] == read_only.ROOT_ACES
    assert len(plan["intended_aces"]) == 6
    assert all(plan[key] == 0 for key in recovery.ZERO_EFFECTS)
    assert plan["acl_mutation_attempts"] == 0
    assert not any(call[0] == "set" for call in fake.calls)
    assert "Arch133IQualification" not in repr(fake.calls)


@pytest.mark.parametrize(
    "drift", ["root", "security", "namespace", "file_hash", "source", "parent"]
)
def test_plan_independent_drift_rejects(fake, monkeypatch, drift):
    original = read_only.inspect_directory_security

    def observe(handle, path):
        value = original(handle, path)
        if path == recovery.TARGET_PATH:
            fake.drift = drift
        return value

    monkeypatch.setattr(read_only, "inspect_directory_security", observe)
    with pytest.raises(recovery.RecoveryError):
        recovery.plan_recovery()
    assert not fake.applied


@pytest.mark.parametrize(
    "change",
    ["policy", "identity", "filesystem", "reparse", "owner", "protected", "hash"],
)
def test_exact_baseline_required(fake, monkeypatch, change):
    values = {
        "policy": {"aces": read_only.ROOT_ACES},
        "identity": {"identity": (1, 2)},
        "filesystem": {"filesystem": "FAT32"},
        "reparse": {"reparse": True},
        "owner": {"owner_sid": read_only.SYSTEM_SID},
        "protected": {"protected": False},
    }
    original = read_only.inspect_directory_security
    monkeypatch.setattr(
        read_only,
        "inspect_directory_security",
        lambda h, p: (
            (
                replace(fake.root, **values.get(change, {})),
                "f" * 64 if change == "hash" else recovery.PRE_SECURITY_SHA256,
            )
            if p == recovery.TARGET_PATH
            else original(h, p)
        ),
    )
    with pytest.raises(recovery.RecoveryError):
        recovery.plan_recovery()


@pytest.mark.parametrize(
    "reviewed", [None, 1, "", "a" * 63, "a" * 65, "A" * 64, "z" * 64, "a" * 64 + "\n"]
)
def test_malformed_hash_rejected_before_observation(fake, reviewed):
    with pytest.raises(recovery.RecoveryError):
        recovery.execute_recovery_once(reviewed, "bad")
    assert fake.calls == [] and fake.source_reads == 0


@pytest.mark.parametrize(
    "text",
    [
        "",
        "AUTHORIZE Q133-2",
        "AUTHORIZE Q133-I SCRATCH ",
        "AUTHORIZE Q133-K ROOT-ACL ",
        None,
    ],
)
def test_wrong_authorization_rejected_before_observation(fake, text):
    with pytest.raises(recovery.RecoveryError):
        recovery.execute_recovery_once("a" * 64, text)
    assert fake.calls == []


def test_non_tty_rejected_at_api_and_cli(fake, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("authorization"))
    with pytest.raises(recovery.RecoveryError):
        recovery.execute_recovery_once(
            "a" * 64, "AUTHORIZE Q133-K ROOT-ACL " + "a" * 64
        )
    assert recovery.main(["execute-once", "--reviewed-plan-sha256", "a" * 64]) == 3
    assert fake.calls == [] and "Type AUTHORIZE" not in capsys.readouterr().err


def test_changed_reviewed_plan_rejected_before_prompt(fake, monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "stdin",
        SimpleNamespace(
            isatty=lambda: True, readline=lambda *a: pytest.fail("prompt reached")
        ),
    )
    assert recovery.main(["execute-once", "--reviewed-plan-sha256", "f" * 64]) == 3
    assert not fake.applied and "Type AUTHORIZE" not in capsys.readouterr().err


def test_changed_plan_api_rejects_before_mutation(fake):
    result = recovery.execute_recovery_once(
        "f" * 64, "AUTHORIZE Q133-K ROOT-ACL " + "f" * 64
    )
    assert result["status"] == "FAILED_CLOSED" and result["acl_mutation_attempts"] == 0
    assert not fake.applied


@pytest.mark.parametrize("status", [0, 5, 32, 87, 1314, 0x80000000, 0xFFFFFFFF])
def test_dword_preserved_and_independent_readback_always_once(fake, status):
    plan = recovery.plan_recovery()
    fake.calls.clear()
    fake.status = status
    result = recovery.execute_recovery_once(*authority(plan))
    assert result["native_set_security_info_status"] == status
    assert result["status"] == ("PASS" if status == 0 else "FAILED_CLOSED")
    assert result["acl_mutation_attempts"] == 1
    assert (
        result["root_identity_before"]
        == result["root_identity_after"]
        == recovery.ROOT_IDENTITY
    )
    assert result["post_application_policy"] == "EXACT_INTENDED_ROOT"
    assert result["namespace_unchanged"] and result["file_hashes_unchanged"]
    assert result["file_hashes_after"] == recovery.FILE_HASHES
    assert all(result[key] == 0 for key in recovery.ZERO_EFFECTS)
    assert [call for call in fake.calls if call[0] == "set"] == [
        ("set", recovery.TARGET_PATH)
    ]
    after = fake.calls[fake.calls.index(("set", recovery.TARGET_PATH)) + 1 :]
    assert [c for c in after if c == ("security", recovery.TARGET_PATH)] == [
        ("security", recovery.TARGET_PATH)
    ]
    assert [c for c in fake.calls if c[0] == "open"] == [
        ("open", p, {}) for p in recovery.PARENTS
    ] + [("open", recovery.TARGET_PATH, {"mutable": True})]
    for handle in (*recovery.PARENTS, recovery.TARGET_PATH, *reads.FINAL_NAMES):
        assert fake.calls.count(("close", handle)) == 1
    with pytest.raises(recovery.RecoveryError):
        recovery.execute_recovery_once(*authority(plan))


@pytest.mark.parametrize(
    "failure",
    [
        "post_policy",
        "identity",
        "reparse",
        "filesystem",
        "owner",
        "protected",
        "namespace",
        "file_hash",
        "file_identity",
        "readback",
        "apply",
        "close",
    ],
)
def test_mutation_failure_retains_consumed_authority_and_sanitizes(fake, failure):
    plan = recovery.plan_recovery()
    fake.calls.clear()
    fake.fail = failure
    result = recovery.execute_recovery_once(*authority(plan))
    assert result["status"] == "FAILED_CLOSED"
    assert result["acl_mutation_attempts"] == 1
    assert SECRET not in recovery.canonical(result).decode()
    assert fake.calls.count(("set", recovery.TARGET_PATH)) == 1
    assert fake.calls.count(("close", recovery.TARGET_PATH)) == 1
    if failure == "apply":
        assert result["native_set_security_info_status"] is None
        assert result["post_application_policy"] == "EXACT_INTENDED_ROOT"
    with pytest.raises(recovery.RecoveryError):
        recovery.execute_recovery_once(*authority(plan))
    assert fake.calls.count(("set", recovery.TARGET_PATH)) == 1


@pytest.mark.parametrize(
    "drift", ["root", "security", "namespace", "file_hash", "source", "parent"]
)
def test_immediate_pre_mutation_drift_stops(fake, monkeypatch, drift):
    plan = recovery.plan_recovery()
    original = recovery._RetainedRoot.snapshot
    count = 0

    def snapshot(self):
        nonlocal count
        count += 1
        if count == 3:
            fake.drift = drift
        return original(self)

    monkeypatch.setattr(recovery._RetainedRoot, "snapshot", snapshot)
    result = recovery.execute_recovery_once(*authority(plan))
    assert result["status"] == "FAILED_CLOSED" and result["acl_mutation_attempts"] == 0
    assert not fake.applied


@pytest.mark.parametrize("drift", ["parent", "source"])
def test_post_mutation_parent_source_drift_fails(fake, monkeypatch, drift):
    plan = recovery.plan_recovery()
    original = recovery.apply_root_policy_status

    def apply(handle):
        result = original(handle)
        fake.drift = drift
        return result

    monkeypatch.setattr(recovery, "apply_root_policy_status", apply)
    result = recovery.execute_recovery_once(*authority(plan))
    assert result["status"] == "FAILED_CLOSED" and result["acl_mutation_attempts"] == 1


def test_no_fallback_root_open_and_partial_handles_close(fake):
    fake.fail = "open"
    with pytest.raises(recovery.RecoveryError):
        recovery.plan_recovery()
    assert [call for call in fake.calls if call[0] == "open"] == [
        ("open", p, {}) for p in recovery.PARENTS
    ] + [("open", recovery.TARGET_PATH, {"mutable": True})]
    assert all(fake.calls.count(("close", p)) == 1 for p in recovery.PARENTS)


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["plan", "--target", r"C:\wrong"],
        ["execute-once"],
        ["plan", "--source-head", HEAD],
    ],
)
def test_no_cli_target_or_source_override(fake, args, capsys):
    assert recovery.main(args) == 3
    assert fake.calls == []
    assert "FAILED_CLOSED" in capsys.readouterr().err


def test_cli_roundtrip_authorization(fake, monkeypatch, capsys):
    plan = recovery.plan_recovery()
    reviewed, authorization = authority(plan)
    monkeypatch.setattr(
        sys,
        "stdin",
        SimpleNamespace(isatty=lambda: True, readline=lambda n: authorization + "\n"),
    )
    assert recovery.main(["execute-once", "--reviewed-plan-sha256", reviewed]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "PASS"
    assert "AUTHORIZE Q133-K ROOT-ACL" in captured.err


@pytest.mark.parametrize(
    "wrong",
    [
        None,
        "platform",
        "isolated",
        "bytecode",
        "location",
        "git_root",
        "branch",
        "origin",
        "dirty",
        "head",
        "tree",
        "tracking_head",
        "tracking_tree",
    ],
)
def test_exact_source_admission(monkeypatch, tmp_path, wrong):
    monkeypatch.setattr(
        recovery, "SOURCE_ROOT", Path(recovery.__file__).resolve().parents[3]
    )
    monkeypatch.setattr(sys, "platform", "other" if wrong == "platform" else "win32")
    monkeypatch.setattr(sys, "flags", SimpleNamespace(isolated=wrong != "isolated"))
    monkeypatch.setattr(sys, "dont_write_bytecode", wrong != "bytecode")
    if wrong == "location":
        monkeypatch.setattr(recovery, "__file__", str(tmp_path / "wrong"))
    tracking = "refs/remotes/origin/" + recovery.SOURCE_BRANCH
    values = {
        ("rev-parse", "--show-toplevel"): str(
            tmp_path if wrong == "git_root" else recovery.SOURCE_ROOT
        ),
        ("branch", "--show-current"): "wrong"
        if wrong == "branch"
        else recovery.SOURCE_BRANCH,
        ("remote", "get-url", "origin"): "wrong"
        if wrong == "origin"
        else recovery.ORIGIN,
        ("status", "--porcelain=v1", "--untracked-files=all"): "dirty"
        if wrong == "dirty"
        else "",
        ("rev-parse", "HEAD"): "bad" if wrong == "head" else HEAD,
        ("rev-parse", "HEAD^{tree}"): "bad" if wrong == "tree" else TREE,
        ("rev-parse", tracking): TREE if wrong == "tracking_head" else HEAD,
        ("rev-parse", tracking + "^{tree}"): HEAD if wrong == "tracking_tree" else TREE,
    }
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kw: SimpleNamespace(stdout=values[tuple(argv[4:])]),
    )
    if wrong:
        with pytest.raises((recovery.RecoveryError, IndexError)):
            recovery._source()
    else:
        assert recovery._source() == {"source_head": HEAD, "source_tree": TREE}


@pytest.mark.parametrize("role", ["VOLUME", "PARENT"])
@pytest.mark.parametrize(
    "change",
    [
        None,
        "owner",
        "missing_admin",
        "missing_system",
        "delete_child",
        "write_dac",
        "write_owner",
        "deny",
        "flags",
        "reparse",
        "filesystem",
    ],
)
def test_parent_concrete_rights_admission(role, change):
    observation = read_only.DirectoryObservation(
        read_only.ADMINISTRATORS_SID, True, read_only.ADMIN_ACES, (1, 2)
    )
    extras = {
        "delete_child": ("other", 0x40, 0, 0),
        "write_dac": ("other", 0x40000, 0, 0),
        "write_owner": ("other", 0x80000, 0, 0),
        "deny": ("other", 1, 1, 0),
        "flags": ("other", 1, 0, 4),
    }
    if change in extras:
        observation = replace(observation, aces=observation.aces + (extras[change],))
    elif change == "owner":
        observation = replace(observation, owner_sid=read_only.TRADING_SID)
    elif change == "missing_admin":
        observation = replace(observation, aces=read_only.ADMIN_ACES[1:])
    elif change == "missing_system":
        observation = replace(observation, aces=read_only.ADMIN_ACES[:1])
    elif change == "reparse":
        observation = replace(observation, reparse=True)
    elif change == "filesystem":
        observation = replace(observation, filesystem="FAT32")
    if change:
        with pytest.raises(recovery.RecoveryError):
            recovery._require_parent(observation, role)
    else:
        recovery._require_parent(observation, role)


def test_shared_application_is_one_frozen_implementation():
    assert (
        primitive.apply_root_policy_status is root_policy_apply.apply_root_policy_status
    )
    assert primitive.administrator_sid is administrator.administrator_sid
    tree = ast.parse(inspect.getsource(root_policy_apply.apply_root_policy_status))
    # Exact original function AST, including SDDL, ABI, DWORD handling and cleanup.
    assert (
        hashlib.sha256(
            ast.dump(tree.body[0], include_attributes=False).encode()
        ).hexdigest()
        == "0b88b3a8c676473833cd80a7c7feceb451f15df9e1dd636da7402f4463aa88a9"
    )


def test_isolated_recovery_import_closure_and_native_allowlist(tmp_path):
    root = Path(__file__).resolve().parents[2]
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import sys, ctypes, json\n"
        "def forbidden(*a, **k): raise AssertionError('import effect')\n"
        "ctypes.WinDLL = forbidden\n"
        f"sys.path.insert(0, {str(root / 'src')!r})\n"
        "from trading_bot.arch133_acl import recovery\n"
        "names = sorted(n for n in sys.modules if n.startswith('trading_bot'))\n"
        "print(json.dumps(names))\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(probe)],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    assert set(json.loads(result.stdout)) == {
        "trading_bot",
        "trading_bot.config",
        "trading_bot.arch133_acl",
        "trading_bot.arch133_acl.recovery",
        "trading_bot.arch133_acl.read_only",
        "trading_bot.arch133_acl.retained_reads",
        "trading_bot.arch133_acl.administrator",
        "trading_bot.arch133_acl.root_policy_apply",
    }
    bindings = set()
    for module in (recovery, read_only, reads, administrator, root_policy_apply):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert not any(
            word in source
            for word in (
                "CreateDirectoryW",
                "MoveFileExW",
                "WriteFile",
                "DeleteFileW",
                "RemoveDirectoryW",
                "SetNamedSecurityInfo",
                "SetFileSecurity",
                "Arch133IQualification",
                "environ",
                "getenv",
                "unlink(",
                "rename(",
            )
        )
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_bind"
            ):
                bindings.add(ast.literal_eval(node.args[1]))
    assert bindings == {
        "CreateFileW",
        "CloseHandle",
        "LocalFree",
        "ConvertSidToStringSidW",
        "GetFinalPathNameByHandleW",
        "GetFileInformationByHandle",
        "GetVolumeInformationW",
        "GetDriveTypeW",
        "GetSecurityInfo",
        "GetSecurityDescriptorControl",
        "GetAclInformation",
        "GetAce",
        "GetSecurityDescriptorLength",
        "GetFileInformationByHandleEx",
        "SetFilePointerEx",
        "ReadFile",
        "GetCurrentProcess",
        "OpenProcessToken",
        "ConvertStringSidToSidW",
        "CheckTokenMembership",
        "GetTokenInformation",
        "ConvertStringSecurityDescriptorToSecurityDescriptorW",
        "GetSecurityDescriptorOwner",
        "GetSecurityDescriptorDacl",
        "SetSecurityInfo",
    }


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "open",
        "convert",
        "membership",
        "disabled",
        "elevation_query",
        "unelevated",
        "user_query",
        "system",
        "trading",
    ],
)
def test_read_only_token_admission_requires_enabled_elevated_administrator(
    monkeypatch, failure
):
    calls = []

    def bind(library, name, arguments, result):
        def invoke(*values):
            calls.append(name)
            if name == "OpenProcessToken":
                values[2]._obj.value = 77
                return failure != "open"
            if name == "ConvertStringSidToSidW":
                values[1]._obj.value = 88
                return failure != "convert"
            if name == "CheckTokenMembership":
                values[2]._obj.value = int(failure != "disabled")
                return failure != "membership"
            if name == "GetTokenInformation":
                if values[1] == 20:
                    values[2]._obj.value = int(failure != "unelevated")
                    return failure != "elevation_query"
                return failure != "user_query"
            return 1

        return invoke

    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: object())
    monkeypatch.setattr(administrator, "_bind", bind)
    sid = {"system": read_only.SYSTEM_SID, "trading": read_only.TRADING_SID}.get(
        failure, "S-1-5-21-1-2-3-4"
    )
    monkeypatch.setattr(administrator, "_sid_text", lambda *a: sid)
    monkeypatch.setattr(
        administrator, "close_handle", lambda h: calls.append(("close", h))
    )
    if failure:
        with pytest.raises(read_only.RootAclError):
            administrator.administrator_sid()
    else:
        assert administrator.administrator_sid() == sid
    if failure != "open":
        assert calls.count(("close", 77)) == 1


def test_native_boundary_rejects_authority_without_public_wrapper(fake):
    with recovery._RetainedRoot() as backend:
        with pytest.raises(recovery.RecoveryError):
            backend.apply_once("a" * 64, "AUTHORIZE Q133-2")
        with pytest.raises(recovery.RecoveryError):
            backend.apply_once("a" * 64, "AUTHORIZE Q133-K ROOT-ACL " + "a" * 64)
    assert not fake.applied


def test_descriptor_preparation_failure_consumes_authority_without_native_attempt(fake):
    plan = recovery.plan_recovery()
    fake.fail = "prepare"
    result = recovery.execute_recovery_once(*authority(plan))
    assert result["status"] == "FAILED_CLOSED"
    assert result["acl_mutation_attempts"] == 0 and not fake.applied
    assert recovery._attempt_consumed
    assert result["post_application_policy"] == "ADMIN_SYSTEM_ONLY"
    with pytest.raises(recovery.RecoveryError):
        recovery.execute_recovery_once(*authority(plan))


def test_actual_native_binding_attempt_counter_without_real_native():
    calls = []

    class Function:
        def __call__(self, *values):
            calls.append(values)
            return 5

    library = SimpleNamespace(SetSecurityInfo=Function(), LocalFree=Function())
    previous = root_policy_apply.native_application_attempts()
    root_policy_apply._bind(library, "LocalFree", [], ctypes.c_void_p)()
    assert root_policy_apply.native_application_attempts() == previous
    bound = root_policy_apply._bind(library, "SetSecurityInfo", [], ctypes.c_uint32)
    assert root_policy_apply.native_application_attempts() == previous
    assert bound(77, 1, 0x80000005, None, None, None, None) == 5
    assert root_policy_apply.native_application_attempts() == previous + 1
    assert calls[-1][:3] == (77, 1, 0x80000005)


@pytest.mark.parametrize("status", [None, True, -1, 0x100000000, "0"])
def test_invalid_native_return_still_reads_back_and_consumes(fake, status):
    plan = recovery.plan_recovery()
    fake.status = status
    result = recovery.execute_recovery_once(*authority(plan))
    assert result["status"] == "FAILED_CLOSED" and result["acl_mutation_attempts"] == 1
    assert result["native_set_security_info_status"] is None
    assert result["post_application_policy"] == "EXACT_INTENDED_ROOT"
