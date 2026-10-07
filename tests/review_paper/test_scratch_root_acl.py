"""133-I tests: only fake native edges; never qualify a real scratch object."""

import ast
import ctypes
import inspect
import io
import json
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from trading_bot.arch133_acl import primitive as native
from trading_bot.arch133_acl import qualification as q

SECRET = "secret-native-exception-never-evidence"


@pytest.fixture(autouse=True)
def no_real_native(monkeypatch):
    monkeypatch.setattr(
        ctypes, "WinDLL", lambda *a, **k: pytest.fail("real Win32 reached")
    )


class FakeScratch:
    def __init__(self, *, status=0, failure=None):
        self.status = status
        self.failure = failure
        self.calls = []
        self.attempted = False
        self.applied = False
        self.reads = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.failure == "close":
            raise RuntimeError(SECRET)

    @contextmanager
    def guard(self):
        yield

    def snapshot(self):
        self.calls.append("snapshot")
        if self.attempted:
            raise q.QualificationError("occupied")
        return {
            "source_head": "a" * 40,
            "source_tree": "b" * 40,
            "administrator_sid": "S-1-5-21-1-2-3-4",
            "parents_sha256": "c" * 64,
        }

    def arm_once(self, reviewed, authorization):
        self.calls.append("arm")
        assert authorization == "AUTHORIZE Q133-I SCRATCH " + reviewed

    def create_root_once(self):
        if self.attempted:
            raise q.QualificationError("already attempted")
        self.attempted = True
        self.calls.append("create")
        if self.failure == "create":
            raise RuntimeError(SECRET)

    def inspect(self):
        self.reads += 1
        self.calls.append("readback")
        if self.failure == "readback" and self.reads == 2:
            raise RuntimeError(SECRET)
        result = native.DirectoryObservation(
            native.ADMINISTRATORS_SID,
            True,
            native.ADMIN_ACES if self.reads == 1 or self.status else native.ROOT_ACES,
            (1, 2),
        )
        if self.reads == 1 and self.failure == "pre_policy":
            result = replace(result, protected=False)
        if self.reads == 2:
            changes = {
                "post_policy": {"aces": native.ROOT_ACES[:-1]},
                "identity": {"identity": (1, 3)},
                "reparse": {"reparse": True},
                "filesystem": {"filesystem": "FAT32"},
            }
            result = replace(result, **changes.get(self.failure, {}))
        return result

    def apply_once(self):
        assert not self.applied
        self.applied = True
        self.calls.append("set")
        if self.failure == "apply":
            raise RuntimeError(SECRET)
        return self.status

    def finish(self):
        self.calls.append("finish")
        if self.failure == "finish":
            raise RuntimeError(SECRET)


def execute(backend):
    digest = q._plan(backend)["plan_sha256"]
    return q._execute_once(backend, digest, "AUTHORIZE Q133-I SCRATCH " + digest)


def test_policy_exactly_matches_publication_and_admin_policy():
    from trading_bot.review_paper import unattended_publication_windows as publication

    policy = publication.publication_policy("root")
    assert policy.owner_sid == native.ADMINISTRATORS_SID
    assert policy.dacl_protected is True
    assert (
        tuple(
            (ace.principal_sid, ace.access_mask, ace.ace_type, ace.ace_flags)
            for ace in policy.aces
        )
        == native.ROOT_ACES
    )
    assert (
        tuple(
            (ace.principal_sid, ace.access_mask, ace.ace_type, ace.ace_flags)
            for ace in publication.ADMIN_POLICY.aces
        )
        == native.ADMIN_ACES
    )
    assert publication.identity.TRADING_SID == native.TRADING_SID


@pytest.mark.parametrize("status", [0, 5, 87, 1307, 0xFFFFFFFF])
def test_exact_status_retained_and_nonzero_fails_closed(status):
    backend = FakeScratch(status=status)
    result = execute(backend)
    assert result["native_set_security_info_status"] == status
    assert result["status"] == ("PASS" if status == 0 else "FAILED_CLOSED")
    assert result["pre_application_policy"] == "ADMIN_SYSTEM_ONLY"
    assert result["post_application_policy"] == (
        "EXACT_INTENDED_ROOT" if status == 0 else "ADMIN_SYSTEM_ONLY"
    )
    assert result["exact_intended_policy_match"] is (status == 0)
    assert result["filesystem"] == "NTFS" and result["reparse"] is False
    assert result["scratch_path"] == q.SCRATCH_PATH
    assert all(result[key] == 0 for key in q.ZERO_EFFECTS)
    assert backend.calls.count("set") == 1 and backend.reads == 2
    assert (
        len(q.canonical(result)) < 2048 and SECRET not in q.canonical(result).decode()
    )
    before = backend.calls.copy()
    with pytest.raises(q.QualificationError):
        execute(backend)
    assert backend.calls.count("set") == 1 and backend.calls.count("create") == 1
    assert backend.calls[: len(before)] == before


@pytest.mark.parametrize("status", [-1, True, 2**32, "5", {"error": SECRET}])
def test_malformed_native_status_cannot_escape(status):
    result = execute(FakeScratch(status=status))
    assert result["status"] == "FAILED_CLOSED"
    assert result["native_set_security_info_status"] is None
    assert SECRET not in q.canonical(result).decode()


@pytest.mark.parametrize(
    "failure",
    [
        "create",
        "pre_policy",
        "apply",
        "readback",
        "post_policy",
        "identity",
        "reparse",
        "filesystem",
        "finish",
    ],
)
def test_one_attempt_and_independent_readback_failures(failure):
    backend = FakeScratch(failure=failure)
    result = execute(backend)
    assert result["status"] == "FAILED_CLOSED"
    assert backend.calls.count("set") <= 1 and backend.calls.count("create") == 1
    assert SECRET not in q.canonical(result).decode()
    if failure in {
        "readback",
        "post_policy",
        "identity",
        "reparse",
        "filesystem",
        "finish",
    }:
        assert result["native_set_security_info_status"] == 0
    if failure in {"create", "pre_policy"}:
        assert "set" not in backend.calls


@pytest.mark.parametrize(
    "reviewed,auth",
    [
        (None, ""),
        ("a" * 64, "bad"),
        ("g" * 64, "AUTHORIZE Q133-I SCRATCH " + "g" * 64),
        (True, ""),
        ("a" * 64, "AUTHORIZE Q133-2 " + "a" * 64),
        ("a" * 64, SECRET),
    ],
)
def test_malformed_authority_before_backend_construction(monkeypatch, reviewed, auth):
    monkeypatch.setattr(q, "ScratchNative", lambda: pytest.fail("backend reached"))
    with pytest.raises(q.QualificationError):
        q.execute_scratch_once(reviewed, auth)
    fake = FakeScratch()
    with pytest.raises(q.QualificationError):
        q._execute_once(fake, reviewed, auth)
    assert not fake.calls


def test_valid_but_changed_plan_stops_before_creation():
    fake = FakeScratch()
    with pytest.raises(q.QualificationError):
        q._execute_once(fake, "d" * 64, "AUTHORIZE Q133-I SCRATCH " + "d" * 64)
    assert not fake.attempted


def test_close_failure_retains_native_status(monkeypatch):
    fake = FakeScratch(failure="close")
    monkeypatch.setattr(q, "ScratchNative", lambda: fake)
    digest = q._plan(fake)["plan_sha256"]
    result = q.execute_scratch_once(digest, "AUTHORIZE Q133-I SCRATCH " + digest)
    assert result["status"] == "FAILED_CLOSED"
    assert result["native_set_security_info_status"] == 0


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["repair"],
        ["plan", r"F:\AITradingBot\Arch133"],
        ["plan", "--root", r"F:\AITradingBot\Arch133"],
        ["execute-once"],
        ["execute-once", "--reviewed-plan-sha256", "a" * 64],
    ],
)
def test_cli_rejects_paths_and_redirected_authority_before_observation(
    monkeypatch, capsys, args
):
    monkeypatch.setattr(
        sys, "stdin", io.StringIO("AUTHORIZE Q133-I SCRATCH " + "a" * 64)
    )
    monkeypatch.setattr(q, "plan_scratch", lambda: pytest.fail("plan reached"))
    assert q.main(args) == 3
    assert "SCRATCH_QUALIFICATION_FAILED_CLOSED" in capsys.readouterr().err


def test_fixed_path_only_no_environment_selection(monkeypatch):
    monkeypatch.setenv("AI_TRADING_BOT_SCRATCH_ROOT", r"F:\AITradingBot\Arch133")
    monkeypatch.setenv("TEMP", r"F:\AITradingBot\Arch133")
    assert q.SCRATCH_PATH == r"F:\AI\temp\arch133i-root-acl-qualification-v1"
    assert q.SOURCE_ROOT == Path(
        r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133i"
    )
    assert list(inspect.signature(q.execute_scratch_once).parameters) == [
        "reviewed",
        "authorization",
    ]
    assert list(inspect.signature(q.ScratchNative).parameters) == []
    assert list(inspect.signature(q.plan_scratch).parameters) == []
    assert execute(FakeScratch())["scratch_path"] == q.SCRATCH_PATH


def test_native_occupied_scratch_stops_without_mutation(monkeypatch):
    calls = []
    fake = q.ScratchNative()
    fake._guarded = True
    fake._armed = True
    fake._absent = lambda: (_ for _ in ()).throw(q.QualificationError("occupied"))
    monkeypatch.setattr(
        native, "create_admin_directory", lambda *a: calls.append("create")
    )
    with pytest.raises(q.QualificationError):
        fake.create_root_once()
    assert fake._attempted and not calls
    with pytest.raises(q.QualificationError):
        fake.create_root_once()
    assert not calls


def test_native_mutation_fixed_arguments_once(monkeypatch):
    calls = []
    fake = q.ScratchNative()
    fake._guarded = True
    fake._armed = True
    fake._absent = lambda: None
    monkeypatch.setattr(
        native, "create_admin_directory", lambda path: calls.append(("create", path))
    )
    monkeypatch.setattr(
        native,
        "open_directory",
        lambda path, **kw: calls.append(("open", path, kw)) or 77,
    )
    monkeypatch.setattr(native, "close_handle", lambda h: calls.append(("close", h)))
    monkeypatch.setattr(
        native, "apply_root_policy_status", lambda h: calls.append(("set", h)) or 5
    )
    with fake:
        fake.create_root_once()
        assert fake.apply_once() == 5
        with pytest.raises(q.QualificationError):
            fake.apply_once()
        with pytest.raises(q.QualificationError):
            fake.create_root_once()
    assert calls == [
        ("create", q.SCRATCH_PATH),
        ("open", q.SCRATCH_PATH, {"mutable": True}),
        ("set", 77),
        ("close", 77),
    ]


@pytest.mark.parametrize("status", [0, 5, 87, 1307, 0xFFFFFFFF])
def test_real_shared_set_security_info_abi_and_status(monkeypatch, status):
    calls = []

    def bind(library, name, arguments, result):
        def invoke(*values):
            calls.append((name, values))
            if name == "ConvertStringSecurityDescriptorToSecurityDescriptorW":
                values[2]._obj.value = 101
            elif name == "GetSecurityDescriptorOwner":
                values[1]._obj.value = 102
            elif name == "GetSecurityDescriptorDacl":
                values[1]._obj.value = 1
                values[2]._obj.value = 103
            elif name == "SetSecurityInfo":
                assert arguments == [
                    ctypes.c_void_p,
                    ctypes.c_uint32,
                    ctypes.c_uint32,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                ]
                assert result is ctypes.c_uint32
                assert values[0:3] == (77, 1, 0x80000005)
                assert values[3].value == 102 and values[4] is None
                assert values[5].value == 103 and values[6] is None
                return status
            return 1

        return invoke

    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: object())
    monkeypatch.setattr(native, "_bind", bind)
    assert native.apply_root_policy_status(77) == status
    assert [name for name, _ in calls].count("SetSecurityInfo") == 1
    assert calls[-1][0] == "LocalFree"
    assert calls[0][1][1] == 1


def test_shared_creation_and_open_flags(monkeypatch):
    calls = []

    @contextmanager
    def attributes():
        yield ctypes.c_uint32(42)

    def bind(library, name, arguments, result):
        def invoke(*values):
            calls.append((name, values))
            return 77 if name == "CreateFileW" else 1

        return invoke

    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: object())
    monkeypatch.setattr(native, "_bind", bind)
    monkeypatch.setattr(native, "admin_security_attributes", attributes)
    native.create_admin_directory(q.SCRATCH_PATH)
    assert native.open_directory(q.SCRATCH_PATH, mutable=True) == 77
    assert calls[0][0] == "CreateDirectoryW"
    assert calls[0][1][0] == q.SCRATCH_PATH
    assert calls[1] == (
        "CreateFileW",
        (q.SCRATCH_PATH, 0xC00E0081, 3, None, 3, 0x02200000, None),
    )


def test_isolated_import_graph_has_no_effect_capabilities(tmp_path):
    """Fresh interpreter checks transitive imports, including package initializers."""
    root = Path(__file__).resolve().parents[2]
    probe = tmp_path / "import_probe.py"
    probe.write_text(
        "import sys, ctypes, json\n"
        "def forbidden(*a, **k): raise AssertionError('native import effect')\n"
        "ctypes.WinDLL = forbidden\n"
        f"sys.path.insert(0, {str(root / 'src')!r})\n"
        "from trading_bot.arch133_acl import qualification\n"
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
        "trading_bot.arch133_acl.primitive",
        "trading_bot.arch133_acl.qualification",
    }
    for module in (q, native):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "HOST_ROOT" not in source and r"F:\AITradingBot" not in source
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not any(
                    word in node.module
                    for word in (
                        "runtime",
                        "robinhood",
                        "oauth",
                        "scheduler",
                        "publication",
                    )
                )
        assert not any(
            word in source
            for word in (
                "rmtree",
                "unlink(",
                "RemoveDirectory",
                "DeleteFile",
                "environ",
                "getenv",
            )
        )


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "path",
        "reparse",
        "kind",
        "drive",
        "volume",
        "filesystem",
        "persistent_acl",
        "security",
        "control",
        "acl",
        "count",
        "get_ace",
        "ace_type",
        "protected",
        "owner",
        "mask",
        "ace_flags",
    ],
)
def test_independent_binary_readback_and_native_failures(monkeypatch, failure):
    path = q.SCRATCH_PATH
    buffers = []
    sid_map = {301: native.ADMINISTRATORS_SID}
    for sid, mask, kind, flags in native.ROOT_ACES:
        buffer = ctypes.create_string_buffer(20)
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))[0] = (
            7 if failure == "ace_type" else kind
        )
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))[1] = (
            3 if failure == "ace_flags" else flags
        )
        ctypes.cast(ctypes.addressof(buffer) + 4, ctypes.POINTER(ctypes.c_uint32))[
            0
        ] = 1 if failure == "mask" else mask
        sid_map[ctypes.addressof(buffer) + 8] = sid
        buffers.append(buffer)
    calls = []

    def bind(library, name, args, result):
        def invoke(*values):
            calls.append(name)
            if name == "GetFinalPathNameByHandleW":
                values[1].value = "wrong" if failure == "path" else "\\\\?\\" + path
                return len(values[1].value)
            if name == "GetFileInformationByHandle":
                info = values[1]._obj
                info.attributes = (
                    0x400 if failure == "reparse" else 0 if failure == "kind" else 0x10
                )
                info.volume, info.index_low = 1, 2
            elif name == "GetDriveTypeW":
                assert values == ("F:\\",)
                return 4 if failure == "drive" else 3
            elif name == "GetVolumeInformationW":
                assert values[0] == "F:\\"
                values[5]._obj.value = 0 if failure == "persistent_acl" else 8
                values[6].value = "FAT32" if failure == "filesystem" else "NTFS"
                return failure != "volume"
            elif name == "GetSecurityInfo":
                assert values[:3] == (77, 1, 5)
                values[3]._obj.value, values[5]._obj.value = 301, 302
                values[7]._obj.value = 300
                return 5 if failure == "security" else 0
            elif name == "GetSecurityDescriptorControl":
                values[1]._obj.value = 0 if failure == "protected" else 0x1000
                return failure != "control"
            elif name == "GetAclInformation":
                values[1]._obj.count = 65 if failure == "count" else 6
                return failure != "acl"
            elif name == "GetAce":
                values[2]._obj.value = ctypes.addressof(buffers[values[1]])
                return failure != "get_ace"
            return 1

        return invoke

    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: object())
    monkeypatch.setattr(native, "_bind", bind)
    monkeypatch.setattr(
        native,
        "_sid_text",
        lambda a, k, sid: (
            native.TRADING_SID
            if failure == "owner" and sid.value == 301
            else sid_map[sid.value]
        ),
    )
    if failure in {None, "protected", "owner", "mask", "ace_flags"}:
        observed = native.inspect_directory(77, path)
        assert observed.identity == (1, 2)
        assert observed.filesystem == "NTFS" and observed.reparse is False
        assert observed.classification() == (
            "EXACT_INTENDED_ROOT" if failure is None else "OTHER_POLICY"
        )
    else:
        with pytest.raises(native.RootAclError):
            native.inspect_directory(77, path)
    assert "SetSecurityInfo" not in calls
    if "GetSecurityInfo" in calls:
        assert calls[-1] == "LocalFree"


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "ConvertStringSidToSidW",
        "InitializeAcl",
        "AddAccessAllowedAceEx",
        "InitializeSecurityDescriptor",
        "SetSecurityDescriptorControl",
        "SetSecurityDescriptorOwner",
        "SetSecurityDescriptorDacl",
    ],
)
def test_shared_binary_admin_creation_descriptor(monkeypatch, failure):
    calls = []
    sids = []

    def bind(library, name, args, result):
        def invoke(*values):
            calls.append((name, values))
            if name == failure:
                return 0
            if name == "ConvertStringSidToSidW":
                sids.append(values[0])
                values[1]._obj.value = len(sids) + 100
            elif name == "GetLengthSid":
                return 12
            return 1

        return invoke

    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: object())
    monkeypatch.setattr(native, "_bind", bind)
    if failure:
        with pytest.raises(native.RootAclError):
            with native.admin_security_attributes():
                pytest.fail("invalid descriptor admitted")
    else:
        with native.admin_security_attributes() as attributes:
            assert attributes.inherit_handle == 0 and attributes.descriptor
            assert attributes.length == ctypes.sizeof(type(attributes))
        assert sids == [
            native.ADMINISTRATORS_SID,
            native.ADMINISTRATORS_SID,
            native.SYSTEM_SID,
        ]
        adds = [values for name, values in calls if name == "AddAccessAllowedAceEx"]
        assert len(adds) == 2 and all(
            values[1:4] == (2, 0, 0x1F01FF) for values in adds
        )
        control = next(
            values for name, values in calls if name == "SetSecurityDescriptorControl"
        )
        assert control[1:] == (0x1000, 0x1000)
    assert sum(name == "LocalFree" for name, _ in calls) == len(sids)


@pytest.mark.parametrize(
    "wrong",
    ["branch", "origin", "head", "tree", "dirty", "platform", "isolation", "bytecode"],
)
def test_source_admission_rejects_drift_before_mutation(monkeypatch, wrong):
    from types import SimpleNamespace

    monkeypatch.setattr(sys, "platform", "linux" if wrong == "platform" else "win32")
    monkeypatch.setattr(sys, "flags", SimpleNamespace(isolated=wrong != "isolation"))
    monkeypatch.setattr(sys, "dont_write_bytecode", wrong != "bytecode")
    if wrong in {"branch", "origin", "head", "tree", "dirty"}:
        monkeypatch.setattr(q, "SOURCE_ROOT", Path(q.__file__).resolve().parents[3])
    reached = []

    def run(argv, **kwargs):
        reached.append(tuple(argv[4:]))
        assert argv[:4] == ["git", "--no-optional-locks", "-C", str(q.SOURCE_ROOT)]
        values = {
            ("rev-parse", "--show-toplevel"): str(q.SOURCE_ROOT),
            ("branch", "--show-current"): "wrong"
            if wrong == "branch"
            else q.SOURCE_BRANCH,
            ("remote", "get-url", "origin"): "wrong" if wrong == "origin" else q.ORIGIN,
            ("status", "--porcelain=v1", "--untracked-files=all"): "dirty"
            if wrong == "dirty"
            else "",
            ("rev-parse", "HEAD"): "bad" if wrong == "head" else "a" * 40,
            ("rev-parse", "HEAD^{tree}"): "bad" if wrong == "tree" else "b" * 40,
        }
        return SimpleNamespace(stdout=values[tuple(argv[4:])])

    monkeypatch.setattr(q.subprocess, "run", run)
    with pytest.raises(q.QualificationError, match="scratch source rejected"):
        q._source()
    expected_last = {
        "branch": ("branch", "--show-current"),
        "origin": ("remote", "get-url", "origin"),
        "head": ("rev-parse", "HEAD^{tree}"),
        "tree": ("rev-parse", "HEAD^{tree}"),
        "dirty": ("status", "--porcelain=v1", "--untracked-files=all"),
    }
    if wrong in expected_last:
        assert reached[-1] == expected_last[wrong]
    else:
        assert not reached  # Platform/interpreter rejection precedes Git/path IO.


def test_cli_plan_has_zero_execute_calls(monkeypatch, capsys):
    monkeypatch.setattr(q, "plan_scratch", lambda: {"plan_sha256": "a" * 64})
    monkeypatch.setattr(
        q, "execute_scratch_once", lambda *a: pytest.fail("execute reached")
    )
    assert q.main(["plan"]) == 0
    assert json.loads(capsys.readouterr().out) == {"plan_sha256": "a" * 64}


def test_native_unarmed_backend_cannot_mutate(monkeypatch):
    backend = q.ScratchNative()
    backend._guarded = True
    monkeypatch.setattr(
        native, "create_admin_directory", lambda *a: pytest.fail("unarmed mutation")
    )
    with pytest.raises(q.QualificationError):
        backend.create_root_once()
    assert not backend._attempted
    with pytest.raises(q.QualificationError):
        backend.arm_once("a" * 64, "malformed")
    assert not backend._armed


def test_native_arm_is_bound_to_plan_and_cannot_repeat(monkeypatch):
    backend = q.ScratchNative()
    backend._guarded = True
    monkeypatch.setattr(q, "_plan", lambda b: {"plan_sha256": "a" * 64})
    with pytest.raises(q.QualificationError):
        backend.arm_once("b" * 64, "AUTHORIZE Q133-I SCRATCH " + "b" * 64)
    assert not backend._armed
    backend.arm_once("a" * 64, "AUTHORIZE Q133-I SCRATCH " + "a" * 64)
    assert backend._armed
    with pytest.raises(q.QualificationError):
        backend.arm_once("a" * 64, "AUTHORIZE Q133-I SCRATCH " + "a" * 64)


@pytest.mark.parametrize("wrong", ["source_root", "module_location", "git_root"])
def test_source_admission_rejects_real_wrong_location(monkeypatch, tmp_path, wrong):
    from types import SimpleNamespace

    actual_root = Path(q.__file__).resolve().parents[3]
    wrong_module = tmp_path / "src" / "trading_bot" / "arch133_acl" / "qualification.py"
    wrong_module.parent.mkdir(parents=True)
    wrong_module.write_text(
        "# Real existing unrelated module location.\n", encoding="utf-8"
    )
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "flags", SimpleNamespace(isolated=True))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.setattr(
        q, "SOURCE_ROOT", tmp_path if wrong == "source_root" else actual_root
    )
    if wrong == "module_location":
        monkeypatch.setattr(q, "__file__", str(wrong_module))
    calls = []

    def run(argv, **kwargs):
        calls.append(tuple(argv[4:]))
        assert calls == [("rev-parse", "--show-toplevel")]
        return SimpleNamespace(stdout=str(tmp_path))

    monkeypatch.setattr(q.subprocess, "run", run)
    with pytest.raises(q.QualificationError, match="scratch source rejected"):
        q._source()
    assert calls == ([("rev-parse", "--show-toplevel")] if wrong == "git_root" else [])


AUTHENTICATED_USERS = "S-1-5-11"
USERS = "S-1-5-32-545"


def parent_observation(aces=native.ADMIN_ACES, owner=native.ADMINISTRATORS_SID):
    return native.DirectoryObservation(owner, False, aces, (1, 2))


def test_parent_volume_admits_known_qualified_acl_shape():
    aces = native.ADMIN_ACES + (
        (AUTHENTICATED_USERS, 0x1301BF, 0, 0),
        (USERS, 0x1200A9, 0, 0),
        (AUTHENTICATED_USERS, 0x10000000, 0, 0x0B),
    )
    q._require_parent_security(parent_observation(aces), "VOLUME")


@pytest.mark.parametrize("role", ["VOLUME", "PARENT"])
@pytest.mark.parametrize("flags", [0, 1, 2, 3, 0x10, 0x13])
def test_parent_roles_admit_users_concrete_read_rights(role, flags):
    q._require_parent_security(
        parent_observation(native.ADMIN_ACES + ((USERS, 0x1200A9, 0, flags),)), role
    )


@pytest.mark.parametrize("flags", [0x09, 0x0A, 0x0B, 0x1B])
def test_parent_volume_templates_are_ineffective(flags):
    q._require_parent_security(
        parent_observation(native.ADMIN_ACES + ((USERS, 0x10000000, 0, flags),)),
        "VOLUME",
    )


@pytest.mark.parametrize("role", ["VOLUME", "PARENT"])
@pytest.mark.parametrize(
    "mask", [0x40, 0x40000, 0x80000, 0x10000000, 0x200000, 0xFFFFFFFF]
)
def test_parent_roles_reject_effective_replacement_security_or_unknown_rights(
    role, mask
):
    with pytest.raises(q.QualificationError, match="replacement rejected"):
        q._require_parent_security(
            parent_observation(
                native.ADMIN_ACES + ((AUTHENTICATED_USERS, mask, 0, 0),)
            ),
            role,
        )


@pytest.mark.parametrize("mask", [0x1301BF, 0x10000, 0x02, 0x04, 0x10, 0x100])
def test_parent_component_does_not_inherit_permissive_volume_rule(mask):
    observed = parent_observation(
        native.ADMIN_ACES + ((AUTHENTICATED_USERS, mask, 0, 0),)
    )
    q._require_parent_security(observed, "VOLUME")
    with pytest.raises(q.QualificationError, match="replacement rejected"):
        q._require_parent_security(observed, "PARENT")


@pytest.mark.parametrize("role", ["VOLUME", "PARENT"])
@pytest.mark.parametrize("kind", [1, 2, 7, 255])
@pytest.mark.parametrize("flags", [0, 0x0B])
def test_parent_roles_reject_deny_and_unknown_aces_including_templates(
    role, kind, flags
):
    with pytest.raises(q.QualificationError, match="ACE rejected"):
        q._require_parent_security(
            parent_observation(native.ADMIN_ACES + ((USERS, 0x1200A9, kind, flags),)),
            role,
        )


@pytest.mark.parametrize(
    "role, flags",
    [("VOLUME", value) for value in (0x04, 0x07, 0x08, 0x18, 0x20, 0x40, 0x80)]
    + [("PARENT", value) for value in (0x04, 0x07, 0x08, 0x09, 0x0B, 0x20, 0x40, 0x80)],
)
def test_parent_roles_reject_malformed_or_unsupported_inheritance(role, flags):
    with pytest.raises(q.QualificationError):
        q._require_parent_security(
            parent_observation(native.ADMIN_ACES + ((USERS, 0x1200A9, 0, flags),)), role
        )


@pytest.mark.parametrize("role", ["VOLUME", "PARENT"])
@pytest.mark.parametrize("sid", [native.ADMINISTRATORS_SID, native.SYSTEM_SID])
@pytest.mark.parametrize("change", ["missing", "read_only", "template"])
def test_parent_roles_require_both_effective_admin_full_control(role, sid, change):
    aces = tuple(ace for ace in native.ADMIN_ACES if ace[0] != sid)
    if change == "read_only":
        aces += ((sid, 0x1200A9, 0, 0),)
    elif change == "template":
        aces += ((sid, 0x1F01FF, 0, 0x0B),)
    with pytest.raises(q.QualificationError):
        q._require_parent_security(parent_observation(aces), role)


@pytest.mark.parametrize("role", ["VOLUME", "PARENT"])
@pytest.mark.parametrize(
    "owner", [AUTHENTICATED_USERS, native.TRADING_SID, "S-1-5-21-1-2-3-4"]
)
def test_parent_roles_reject_untrusted_owner_including_operator_user(role, owner):
    with pytest.raises(q.QualificationError, match="owner rejected"):
        q._require_parent_security(parent_observation(owner=owner), role)


def test_parent_roles_reject_unknown_role():
    with pytest.raises(q.QualificationError, match="role rejected"):
        q._require_parent_security(parent_observation(), "ROOT")


@pytest.mark.parametrize("changed", [None, "identity", "security"])
def test_native_guard_keeps_role_checks_held_parents_and_reobservation(
    monkeypatch, changed
):
    opened, closed, inspected = [], [], []
    observations = {path: parent_observation() for path in q.PARENTS}
    observations[q.PARENTS[0]] = parent_observation(
        native.ADMIN_ACES + ((AUTHENTICATED_USERS, 0x1301BF, 0, 0),)
    )

    def open_directory(path, mutable=False):
        assert mutable is False
        opened.append(path)
        return len(opened)

    def inspect_directory(handle, path):
        assert handle == opened.index(path) + 1
        inspected.append((handle, path))
        return observations[path]

    monkeypatch.setattr(native, "administrator_sid", lambda: "S-1-5-21-1-2-3-4")
    monkeypatch.setattr(native, "open_directory", open_directory)
    monkeypatch.setattr(native, "close_handle", closed.append)
    monkeypatch.setattr(native, "inspect_directory", inspect_directory)
    monkeypatch.setattr(q, "_source", lambda: {})
    with q.ScratchNative() as backend:
        with backend.guard():
            assert opened == list(q.PARENTS) and not closed
            assert backend._guarded and len(backend._parents) == 3
            if changed:
                path = q.PARENTS[1]
                updates = (
                    {"identity": (1, 3)} if changed == "identity" else {"aces": ()}
                )
                observations[path] = replace(observations[path], **updates)
                with pytest.raises(q.QualificationError, match="parent changed"):
                    backend.finish()
            else:
                backend.finish()
            assert not closed
        assert not backend._guarded
    assert closed == [3, 2, 1] and len(inspected) == 6


@pytest.mark.parametrize("path", q.PARENTS[1:])
def test_native_guard_never_assigns_volume_role_to_components(monkeypatch, path):
    opened, closed = [], []

    def open_directory(value):
        opened.append(value)
        return len(opened)

    def observe(handle, value):
        aces = native.ADMIN_ACES
        if value in {q.PARENTS[0], path}:
            aces += ((AUTHENTICATED_USERS, 0x1301BF, 0, 0),)
        return parent_observation(aces)

    monkeypatch.setattr(native, "administrator_sid", lambda: "S-1-5-21-1-2-3-4")
    monkeypatch.setattr(native, "open_directory", open_directory)
    monkeypatch.setattr(native, "close_handle", closed.append)
    monkeypatch.setattr(native, "inspect_directory", observe)
    with q.ScratchNative() as backend:
        with pytest.raises(q.QualificationError, match="replacement rejected"):
            with backend.guard():
                pytest.fail("unsafe component admitted")
        assert not backend._guarded and not backend._attempted
    assert opened[-1] == path and closed == list(range(len(opened), 0, -1))
