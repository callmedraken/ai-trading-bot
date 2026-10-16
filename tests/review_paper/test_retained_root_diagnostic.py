"""133-J fake-native coverage only; never inspect a real retained host object."""

import ast
import ctypes
import inspect
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.arch133_acl import read_only as native
from trading_bot.arch133_acl import retained_diagnostic as diagnostic
from trading_bot.arch133_acl import retained_reads as reads

HEAD, TREE = "a" * 40, "b" * 40


def observation(aces=native.ADMIN_ACES):
    return native.DirectoryObservation(native.ADMINISTRATORS_SID, True, aces, (7, 99))


@pytest.fixture
def fake(monkeypatch):
    calls = []
    monkeypatch.setattr(
        diagnostic,
        "_source",
        lambda *args: {
            "source_head": HEAD,
            "source_tree": TREE,
        },
    )
    monkeypatch.setattr(
        native,
        "open_directory",
        lambda path, **kw: (
            calls.append(("open", path, kw))
            or (99 if path == diagnostic.TARGET_PATH else path)
        ),
    )
    monkeypatch.setattr(
        native, "close_handle", lambda handle: calls.append(("close", handle))
    )
    monkeypatch.setattr(
        native,
        "inspect_directory_security",
        lambda *args: calls.append(("inspect", *args)) or (observation(), "c" * 64),
    )
    monkeypatch.setattr(native, "inspect_directory", lambda *args: observation())
    names = tuple((name, i) for i, name in enumerate(reads.FINAL_NAMES))
    monkeypatch.setattr(reads, "namespace", lambda handle: names)
    monkeypatch.setattr(
        reads,
        "open_retained_file",
        lambda name: calls.append(("file_open", name)) or name,
    )
    monkeypatch.setattr(
        reads,
        "file_snapshot",
        lambda handle, name: (
            (7, dict(names)[name]),
            "d" * 64,
        ),
    )
    return calls


def test_fixed_target_and_no_api_or_environment_path_override(monkeypatch, fake):
    for variable in (
        "AI_TRADING_BOT_ROOT",
        "AI_TRADING_BOT_SCRATCH_ROOT",
        "TEMP",
        "TMP",
    ):
        monkeypatch.setenv(variable, r"C:\wrong")
    assert diagnostic.TARGET_PATH == reads.TARGET_PATH == r"F:\AITradingBot\Arch133"
    assert tuple(inspect.signature(diagnostic.diagnose_retained_root).parameters) == (
        "expected_head",
        "expected_tree",
    )
    result = diagnostic.diagnose_retained_root(HEAD, TREE)
    assert result["status"] == "PASS"
    assert fake[0] == ("open", r"F:\AITradingBot\Arch133", {"mutable": True})
    assert result["policy_classification"] == "ADMIN_SYSTEM_ONLY"
    assert result["open_requested_access"] == 0xC00E0081
    assert result["open_share_mode"] == result["open_disposition"] == 3
    assert result["open_flags"] == 0x02200000
    assert result["final_path"] == r"\\?\F:\AITradingBot\Arch133"
    assert result["identity"] == (7, 99)
    assert result["root_security_unchanged"] and result["file_hashes_unchanged"]
    assert result["namespace_exactness"] and result["stable_reobservation"]
    assert len(result["file_hashes_before"]) == 4
    assert all(result[key] == 0 for key in diagnostic.ZERO_EFFECTS)
    assert [call for call in fake if call == ("close", 99)] == [("close", 99)]
    assert fake[-1] == ("close", 99)
    assert [call for call in fake if call[0] == "inspect"] == [
        ("inspect", 99, diagnostic.TARGET_PATH),
        ("inspect", 99, diagnostic.TARGET_PATH),
    ]


@pytest.mark.parametrize("code", [0, 5, 32, 87, 1314, 0xFFFFFFFF])
def test_exact_native_open_numeric_status_no_fallback(monkeypatch, code):
    calls = []

    def bind(library, name, arguments, result):
        assert name == "CreateFileW"
        assert arguments == [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        assert result is ctypes.c_void_p

        def invoke(*values):
            calls.append(values)
            return ctypes.c_void_p(-1).value

        return invoke

    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: object())
    monkeypatch.setattr(native, "_bind", bind)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: code)
    with pytest.raises(native.RootOpenError) as failure:
        native.open_directory(diagnostic.TARGET_PATH, mutable=True)
    assert failure.value.win32_error == code
    assert calls == [(diagnostic.TARGET_PATH, 0xC00E0081, 3, None, 3, 0x02200000, None)]


@pytest.mark.parametrize("code", [5, 32, 87, 0xFFFFFFFF])
def test_failed_open_reaches_no_inspection_other_open_or_file(monkeypatch, fake, code):
    calls = []

    def fail(path, **kw):
        calls.append((path, kw))
        raise native.RootOpenError(code)

    monkeypatch.setattr(native, "open_directory", fail)
    result = diagnostic.diagnose_retained_root(HEAD, TREE)
    assert result["status"] == "FAILED_CLOSED"
    assert result["open_win32_error"] == code and result["open_success"] is False
    assert result["identity"] is None and result["file_hashes_before"] is None
    assert calls == [(diagnostic.TARGET_PATH, {"mutable": True})] and not fake


def test_scratch_policy_classification_is_shared_but_scratch_never_opened(fake):
    assert observation(native.ROOT_ACES).classification() == "EXACT_INTENDED_ROOT"
    assert diagnostic.diagnose_retained_root(HEAD, TREE)["status"] == "PASS"
    assert "Arch133IQualification" not in repr(fake)


@pytest.mark.parametrize(
    "change",
    [
        "identity",
        "owner",
        "protected",
        "aces",
        "security",
        "namespace",
        "file_hash",
        "file_identity",
        "parent",
        "source",
    ],
)
def test_independent_reobservation_drift_fails_closed(monkeypatch, fake, change):
    before = observation()
    altered = {
        "identity": replace(before, identity=(7, 100)),
        "owner": replace(before, owner_sid=native.SYSTEM_SID),
        "protected": replace(before, protected=False),
        "aces": replace(before, aces=native.ROOT_ACES),
    }.get(change, before)
    observations = iter(
        [(before, "c" * 64), (altered, "e" * 64 if change == "security" else "c" * 64)]
    )
    monkeypatch.setattr(
        native, "inspect_directory_security", lambda *a: next(observations)
    )
    if change == "namespace":
        snapshots = iter([tuple((n, i) for i, n in enumerate(reads.FINAL_NAMES)), ()])
        monkeypatch.setattr(reads, "namespace", lambda *a: next(snapshots))
    if change in {"file_hash", "file_identity"}:
        snapshots = iter(
            [((7, i), "d" * 64) for i in range(4)]
            + [
                ((7, i + (1 if change == "file_identity" else 0)), "e" * 64)
                for i in range(4)
            ]
        )
        monkeypatch.setattr(reads, "file_snapshot", lambda *a: next(snapshots))
    if change == "parent":
        snapshots = iter([before, before, altered, replace(before, identity=(7, 100))])
        monkeypatch.setattr(native, "inspect_directory", lambda *a: next(snapshots))
    if change == "source":
        snapshots = iter(
            [
                {"source_head": HEAD, "source_tree": TREE},
                {"source_head": TREE, "source_tree": TREE},
            ]
        )
        monkeypatch.setattr(diagnostic, "_source", lambda *a: next(snapshots))
    assert diagnostic.diagnose_retained_root(HEAD, TREE)["status"] == "FAILED_CLOSED"
    assert fake.count(("close", 99)) == 1


@pytest.mark.parametrize(
    "edge", ["inspect_directory_security", "namespace", "file_snapshot", "close_handle"]
)
def test_native_failures_close_once_and_sanitize(monkeypatch, fake, edge, capsys):
    module = native if edge in {"inspect_directory_security", "close_handle"} else reads
    original = getattr(module, edge)

    def fail(*args):
        if edge == "close_handle":
            original(*args)
        raise OSError("TOKEN=private native filesystem payload")

    monkeypatch.setattr(module, edge, fail)
    assert (
        diagnostic.main(["diagnose", "--source-head", HEAD, "--source-tree", TREE]) == 3
    )
    output = capsys.readouterr()
    assert "private" not in output.out + output.err
    assert fake.count(("close", 99)) == 1


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["diagnose"],
        ["repair"],
        ["execute-once"],
        ["diagnose", "--root", r"F:\AITradingBot\Arch133"],
        [
            "diagnose",
            "--source-head",
            HEAD,
            "--source-tree",
            TREE,
            "--root",
            r"C:\wrong",
        ],
        ["diagnose", "--source-head", "secret", "--source-tree", TREE],
    ],
)
def test_cli_rejects_path_or_execution_grammar_without_echo(monkeypatch, capsys, args):
    monkeypatch.setattr(
        diagnostic,
        "diagnose_retained_root",
        lambda *a: pytest.fail("diagnostic reached"),
    )
    assert diagnostic.main(args) == 3
    output = capsys.readouterr()
    assert not output.out
    assert json.loads(output.err)["reason"] == "RETAINED_DIAGNOSTIC_FAILED_CLOSED"


@pytest.mark.parametrize(
    "wrong",
    [
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
        "remote",
    ],
)
def test_source_admission_drift_before_native(monkeypatch, tmp_path, wrong):
    monkeypatch.setattr(
        diagnostic, "SOURCE_ROOT", Path(diagnostic.__file__).resolve().parents[3]
    )
    monkeypatch.setattr(sys, "platform", "other" if wrong == "platform" else "win32")
    monkeypatch.setattr(sys, "flags", SimpleNamespace(isolated=wrong != "isolated"))
    monkeypatch.setattr(sys, "dont_write_bytecode", wrong != "bytecode")
    if wrong == "location":
        monkeypatch.setattr(diagnostic, "__file__", str(tmp_path / "elsewhere"))
    values = {
        ("rev-parse", "--show-toplevel"): str(
            tmp_path if wrong == "git_root" else diagnostic.SOURCE_ROOT
        ),
        ("branch", "--show-current"): "wrong"
        if wrong == "branch"
        else diagnostic.SOURCE_BRANCH,
        ("remote", "get-url", "origin"): "wrong"
        if wrong == "origin"
        else diagnostic.ORIGIN,
        ("status", "--porcelain=v1", "--untracked-files=all"): "dirty"
        if wrong == "dirty"
        else "",
        ("rev-parse", "HEAD"): TREE if wrong == "head" else HEAD,
        ("rev-parse", "HEAD^{tree}"): HEAD if wrong == "tree" else TREE,
        ("rev-parse", "refs/remotes/origin/" + diagnostic.SOURCE_BRANCH): TREE
        if wrong == "remote"
        else HEAD,
    }
    monkeypatch.setattr(
        diagnostic.subprocess,
        "run",
        lambda argv, **kw: SimpleNamespace(stdout=values[tuple(argv[4:])]),
    )
    monkeypatch.setattr(
        native, "open_directory", lambda *a, **kw: pytest.fail("native reached")
    )
    result = diagnostic.diagnose_retained_root(HEAD, TREE)
    assert result["status"] == "FAILED_CLOSED" and result["source_head"] is None


def test_isolated_import_closure_native_binding_allowlist(tmp_path):
    root = Path(__file__).resolve().parents[2]
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import sys, ctypes, json\n"
        "def forbidden(*a, **kw): raise AssertionError('import native effect')\n"
        "ctypes.WinDLL = forbidden\n"
        f"sys.path.insert(0, {str(root / 'src')!r})\n"
        "from trading_bot.arch133_acl import retained_diagnostic\n"
        "names = sorted(n for n in sys.modules if n.startswith('trading_bot'))\n"
        "print(json.dumps(names))\n",
        encoding="utf-8",
    )
    process = subprocess.run(
        [sys.executable, "-I", "-B", str(probe)],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    assert set(json.loads(process.stdout)) == {
        "trading_bot",
        "trading_bot.config",
        "trading_bot.arch133_acl",
        "trading_bot.arch133_acl.read_only",
        "trading_bot.arch133_acl.retained_reads",
        "trading_bot.arch133_acl.retained_diagnostic",
    }
    bindings = set()
    for module in (native, reads, diagnostic):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_bind"
            ):
                bindings.add(ast.literal_eval(node.args[1]))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert (
            not names & {"eval", "exec", "__import__", "getattr"}
            if module is diagnostic
            else True
        )
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
    }
    assert not hasattr(native, "apply_root_policy_status")
    assert not hasattr(native, "create_admin_directory")


@pytest.mark.parametrize(
    "name", ["other", "..", "paper.sqlite-wal", r"C:\wrong", "activation.json/child"]
)
def test_retained_file_name_allowlist(name):
    with pytest.raises(native.RootAclError):
        reads.open_retained_file(name)


def test_retained_files_open_with_read_only_rights_and_deny_write_delete(monkeypatch):
    calls = []
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: object())
    monkeypatch.setattr(
        reads, "_bind", lambda *a: lambda *values: calls.append(values) or 77
    )
    for name in reads.FINAL_NAMES:
        assert reads.open_retained_file(name) == 77
    assert calls == [
        (diagnostic.TARGET_PATH + "\\" + n, 0x80000080, 1, None, 3, 0x00200000, None)
        for n in reads.FINAL_NAMES
    ]


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "missing",
        "extra",
        "duplicate",
        "directory",
        "reparse",
        "offset",
        "length",
        "native",
    ],
)
def test_binary_held_namespace_exactness_and_bounds(monkeypatch, failure):
    assert reads.DirectoryEntry.name.offset == 104
    calls = []
    names = list(reads.FINAL_NAMES)
    if failure == "missing":
        names.pop()
    if failure == "extra":
        names.append("extra")
    if failure == "duplicate":
        names[-1] = names[0]

    def query(handle, info_class, buffer, size):
        assert handle == 99
        calls.append(info_class)
        if len(calls) > 1 or failure == "native":
            return 0
        offset = 0
        for i, name in enumerate(names):
            encoded = name.encode("utf-16-le")
            entry = reads.DirectoryEntry.from_buffer(buffer, offset)
            entry.file_id = i
            entry.name_bytes = 1 if failure == "length" else len(encoded)
            entry.attributes = (
                0x10 if failure == "directory" else 0x400 if failure == "reparse" else 0
            )
            step = (104 + len(encoded) + 7) // 8 * 8
            entry.next = (
                (1 if failure == "offset" else step) if i < len(names) - 1 else 0
            )
            ctypes.memmove(
                ctypes.addressof(buffer) + offset + 104, encoded, len(encoded)
            )
            offset += step
        return 1

    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: object())
    monkeypatch.setattr(
        ctypes, "get_last_error", lambda: 5 if failure == "native" else 18
    )
    monkeypatch.setattr(reads, "_bind", lambda *a: query)
    if failure is None:
        assert reads.namespace(99) == tuple((n, i) for i, n in enumerate(names))
        assert calls == [11, 10]
    else:
        with pytest.raises(native.RootAclError):
            reads.namespace(99)


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "path",
        "reparse",
        "directory",
        "hardlink",
        "size",
        "seek",
        "read",
        "short",
        "oversize",
    ],
)
def test_binary_read_only_file_hash_identity_and_failures(monkeypatch, failure):
    import hashlib

    name = "paper.sqlite"
    payload = b"retained database bytes"
    calls = []

    def bind(library, api, arguments, result):
        def invoke(*values):
            calls.append(api)
            if api == "GetFinalPathNameByHandleW":
                values[1].value = (
                    "wrong"
                    if failure == "path"
                    else "\\\\?\\" + reads.TARGET_PATH + "\\" + name
                )
                return len(values[1].value)
            if api == "GetFileInformationByHandle":
                info = values[1]._obj
                info.attributes = (
                    0x400
                    if failure == "reparse"
                    else 0x10
                    if failure == "directory"
                    else 0
                )
                info.links = 2 if failure == "hardlink" else 1
                info.volume, info.index_low = 7, 9
                info.size_low = (
                    reads.MAX_FILE_BYTES + 1 if failure == "size" else len(payload)
                )
            if api == "SetFilePointerEx":
                assert values == (77, 0, None, 0)
                return failure != "seek"
            if api == "ReadFile":
                if failure == "read":
                    return 0
                if calls.count("ReadFile") == 1 and failure != "short":
                    ctypes.memmove(values[1], payload, len(payload))
                    values[3]._obj.value = (
                        65537 if failure == "oversize" else len(payload)
                    )
                else:
                    values[3]._obj.value = 0
            return 1

        return invoke

    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: object())
    monkeypatch.setattr(reads, "_bind", bind)
    if failure is None:
        assert reads.file_snapshot(77, name) == (
            (7, 9),
            hashlib.sha256(payload).hexdigest(),
        )
    else:
        with pytest.raises(native.RootAclError):
            reads.file_snapshot(77, name)
    assert set(calls) <= {
        "GetFinalPathNameByHandleW",
        "GetFileInformationByHandle",
        "SetFilePointerEx",
        "ReadFile",
    }


def test_shared_exact_open_success_does_not_query_error(monkeypatch):
    calls = []
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: object())
    monkeypatch.setattr(
        native, "_bind", lambda *a: lambda *values: calls.append(values) or 77
    )
    monkeypatch.setattr(
        ctypes, "get_last_error", lambda: pytest.fail("stale status queried")
    )
    assert native.open_directory(diagnostic.TARGET_PATH, mutable=True) == 77
    assert calls == [(diagnostic.TARGET_PATH, 0xC00E0081, 3, None, 3, 0x02200000, None)]


@pytest.mark.parametrize(
    "name,expected",
    (
        (
            "apply_root_policy_status",
            "0b88b3a8c676473833cd80a7c7feceb451f15df9e1dd636da7402f4463aa88a9",
        ),
        (
            "create_admin_directory",
            "6512492167a80c5a1067efa4267f5b25b4895268131e0f4d347feb63723282f7",
        ),
        (
            "admin_security_attributes",
            "1aa8873f1d3592aa9119110b7d9cef4b70dab52ddfe1cf035e6a41b61508337d",
        ),
        (
            "administrator_sid",
            "bd2c70331a0c5c0b7bf413f6c07ebe3d70e3c8bf9106a6c1b16a1423d71779bf",
        ),
    ),
)
def test_existing_mutation_function_asts_remain_accepted(name, expected):
    import hashlib

    from trading_bot.arch133_acl import primitive

    tree = ast.parse(inspect.getsource(getattr(primitive, name)))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    assert (
        hashlib.sha256(
            ast.dump(function, include_attributes=False).encode()
        ).hexdigest()
        == expected
    )
    assert primitive.open_directory is native.open_directory
    assert primitive.inspect_directory is native.inspect_directory
    assert primitive.DirectoryObservation is native.DirectoryObservation
