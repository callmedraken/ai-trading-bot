"""Read-only memory object tests; no production directory is ever created."""

import ctypes
import inspect
from dataclasses import dataclass, replace
from uuid import UUID

import pytest

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.windows_authority import (
    AuthorityObjectError,
    AuthorityPathError,
    AuthoritySecurityError,
    require_fixed_authority_tree_path,
)
from trading_bot.runtime.windows_authority_security import (
    FILE_ALL_ACCESS,
    AuthorityObjectKind,
    SecurityAce,
    SecurityInspection,
    WindowsHandle,
    authority_security_policy,
)

from .test_personal_desktop_paper_account_publication import (
    prohibit_production_effects as prohibit_production_effects,
)


@pytest.fixture(autouse=True)
def block_real_native(monkeypatch, prohibit_production_effects):
    def forbidden(*args, **kwargs):
        pytest.fail("read tests must never load a native DLL")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)


SID = "S-1-5-21-1-2-3-1009"
IDENTITY = "11111111-1111-5111-8111-111111111111"
ROOT = security.PERSONAL_DESKTOP_PAPER_V2_ROOT
ANCHOR = security.PERSONAL_DESKTOP_PAPER_V2_ANCHOR
RUNTIME = security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
OPERATIONS = security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
UNATTENDED = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS
GENESIS = ROOT + f"\\paper-account-genesis-{IDENTITY}"
CHECKPOINT = GENESIS + f"\\paper-account-checkpoint-{IDENTITY}.json"
TRANSITION = RUNTIME + f"\\paper-account-transition-{IDENTITY}"
REPORT = TRANSITION + f"\\checkpointed-paper-cycle-report-{IDENTITY}.json"


def inspection(path):
    spec = security.paper_object_spec(path)
    if spec.role in {security.PaperObjectRole.PARENT, security.PaperObjectRole.VOLUME}:
        owner = security.ADMINISTRATORS_SID
        aces = (
            SecurityAce(owner, FILE_ALL_ACCESS),
            SecurityAce(security.SYSTEM_SID, FILE_ALL_ACCESS),
        )
    elif spec.role in {
        security.PaperObjectRole.C1_ROOT,
        security.PaperObjectRole.CAPTURE_OUTPUT,
    }:
        role = (
            "root"
            if spec.role is security.PaperObjectRole.C1_ROOT
            else "capture-output"
        )
        policy = authority_security_policy(role, SID)
        owner, aces = policy.owner_sid, policy.aces
    elif spec.role is security.PaperObjectRole.HISTORICAL_SNAPSHOT:
        owner, aces = SID, ()
    else:
        owner = (
            SID
            if spec.role
            in {
                security.PaperObjectRole.OUTPUT_FILE,
                security.PaperObjectRole.OUTPUT_DIRECTORY,
                security.PaperObjectRole.UNATTENDED_INVOCATION_FILE,
                security.PaperObjectRole.UNATTENDED_INVOCATION_DIRECTORY,
            }
            else security.ADMINISTRATORS_SID
        )
        policy = security.paper_security_policy(spec.role, SID, owner_sid=owner)
        aces = policy.aces
    return SecurityInspection(
        path, path, spec.kind, owner, True, aces, False, "F:\\", "NTFS"
    )


@dataclass
class Node:
    observation: security.PaperObjectObservation
    payload: bytes | None


class MemoryReadApi:
    """Only memory maps use production-name strings; no filesystem operations."""

    def __init__(self):
        self.nodes = {}
        self.handles = {}
        self.calls = []
        self.overrides = {}
        self.inspections = {}
        self.on_inspect = lambda *args: None
        self.on_read = lambda *args: None
        self.next_handle = 1
        self.trading_runtime = False
        self.staging_present = False
        self.on_staging_probe = lambda: self.staging_present

    def fixed_staging_present(self):
        self.calls.append(("fixed_staging_present",))
        return self.on_staging_probe()

    def require_parent_access(self, path):
        if self.trading_runtime and path == security.PERSONAL_DESKTOP_PAPER_PARENT:
            raise AuthorityObjectError("Trading cannot read/list protected parent")

    def put(self, path, payload=None):
        if path != "F:\\":
            parent = path.rsplit("\\", 1)[0]
            if parent == "F:":
                parent += "\\"
            if parent not in self.nodes:
                self.put(parent)
        self.nodes[path] = Node(
            security.PaperObjectObservation(
                inspection(path),
                (7, len(self.nodes) + 10),
                len(payload) if payload is not None else 0,
                1,
            ),
            payload,
        )

    def open(self, path, kind):
        self.calls.append(("open", path, kind))
        self.require_parent_access(path)
        if path not in self.nodes:
            raise AuthorityObjectError("memory object absent")
        handle = self.next_handle
        self.next_handle += 1
        self.handles[handle] = self.nodes[path]
        return handle

    def close(self, handle):
        self.calls.append(("close", handle))
        del self.handles[handle]

    def inspect(self, handle, path, kind):
        count = self.inspections.get(path, 0) + 1
        self.inspections[path] = count
        self.on_inspect(path, count, self.handles[handle])
        return self.handles[handle].observation

    def read(self, handle, maximum):
        self.calls.append(("read", maximum))
        self.on_read(self.handles[handle])
        payload = self.handles[handle].payload
        assert type(payload) is bytes
        if len(payload) > maximum:
            raise AuthorityObjectError("memory artifact bound exceeded")
        return payload

    def names(self, handle, path, maximum):
        self.calls.append(("names", path, maximum))
        self.require_parent_access(path)
        if path in self.overrides:
            return self.overrides[path]
        prefix = path if path.endswith("\\") else path + "\\"
        return tuple(
            p[len(prefix) :]
            for p in self.nodes
            if p.startswith(prefix) and p != path and "\\" not in p[len(prefix) :]
        )


def test_exact_constants_and_existing_c1_path_guard_is_unchanged():
    assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False
    assert ROOT == r"F:\AITradingBot\Paper-v2"
    assert (
        security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT
        == r"F:\AITradingBot\.Paper-v2.provisioning"
    )
    assert RUNTIME == r"F:\AITradingBot\Paper-v2\runtime"
    assert OPERATIONS == r"F:\AITradingBot\Paper-v2\runtime\paper-operations"
    assert UNATTENDED == (r"F:\AITradingBot\Paper-v2\runtime\unattended-invocations")
    with pytest.raises(AuthorityPathError):
        require_fixed_authority_tree_path(ROOT)


@pytest.mark.parametrize(
    "path",
    [
        ROOT.lower(),
        ROOT + "\\",
        ROOT + "\\..\\Paper-v2",
        ROOT.replace("\\", "/"),
        "\\\\?\\" + ROOT,
        "\\\\.\\" + ROOT,
        r"\\server\share\Paper-v2",
        r"\\?\GLOBALROOT\Device\HarddiskVolume1\AITradingBot\Paper-v2",
        r"\\?\Volume{11111111-1111-1111-1111-111111111111}\Paper-v2",
        r"F:\AITradingBot\Paper",
        r"F:\AITradingBot\.Paper.provisioning-v1",
        security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT,
        ROOT + ":stream",
        ANCHOR + ".",
        ROOT.replace("Paper-v2", "Paper-v20"),
        r"G:\AITradingBot\Paper-v2",
        r"F:\test\Paper-v2",
        CHECKPOINT.replace("checkpoint-1111", "checkpoint-2111"),
    ],
)
def test_alias_traversal_and_alternate_roots_rejected_before_open(path):
    api = MemoryReadApi()
    with security.PinnedPaperReadSession(api, SID) as session:
        with pytest.raises(AuthorityPathError):
            session.pin(path)
    assert api.calls == []


UNATTENDED_FINAL = UNATTENDED + f"\\unattended-paper-invocation-{IDENTITY}"
UNATTENDED_STAGING = UNATTENDED + f"\\.unattended-paper-invocation-{IDENTITY}.staging"
UNATTENDED_FILE = (
    UNATTENDED_FINAL + f"\\personal-desktop-unattended-paper-invocation-{IDENTITY}.json"
)
UNATTENDED_STAGING_FILE = (
    UNATTENDED_STAGING
    + f"\\personal-desktop-unattended-paper-invocation-{IDENTITY}.json"
)

V2_ROLES = [
    ROOT,
    ANCHOR,
    GENESIS,
    CHECKPOINT,
    RUNTIME,
    OPERATIONS,
    TRANSITION,
    REPORT,
    UNATTENDED,
    UNATTENDED_FINAL,
    UNATTENDED_STAGING,
    UNATTENDED_FILE,
    UNATTENDED_STAGING_FILE,
]


@pytest.mark.parametrize("path", V2_ROLES)
def test_role_policy_exact_rights_protected_owner_and_admin_system(path):
    spec = security.paper_object_spec(path)
    observed = inspection(path)
    security.require_paper_object_security(path, spec, observed, SID)
    trading = next(ace for ace in observed.aces if ace.principal_sid == SID)
    assert not trading.access_mask & 0xC0000  # WRITE_DAC / WRITE_OWNER
    if path in {ROOT, ANCHOR, GENESIS, CHECKPOINT}:
        assert not trading.access_mask & (0x10000 | 0x2 | 0x4 | 0x10 | 0x40 | 0x100)
        assert observed.owner_sid == security.ADMINISTRATORS_SID
    elif path in {RUNTIME, OPERATIONS, UNATTENDED}:
        assert observed.owner_sid == security.ADMINISTRATORS_SID
        assert trading.access_mask & 0x6 == 0x6
        assert not trading.access_mask & 0x10000
    else:
        assert observed.owner_sid == SID
    # All accepted entries are explicit allows without inheritance flags.
    assert all(ace.ace_type == 0 and ace.ace_flags == 0 for ace in observed.aces)
    security.require_paper_object_security(
        path, spec, replace(observed, aces=tuple(reversed(observed.aces))), SID
    )


def test_unattended_paths_have_distinct_exact_roles_and_artifact_bound():
    assert security.paper_object_spec(UNATTENDED).role is (
        security.PaperObjectRole.UNATTENDED_INVOCATIONS
    )
    assert security.paper_object_spec(UNATTENDED_FINAL).role is (
        security.PaperObjectRole.UNATTENDED_INVOCATION_DIRECTORY
    )
    assert security.paper_object_spec(UNATTENDED_STAGING).role is (
        security.PaperObjectRole.UNATTENDED_INVOCATION_DIRECTORY
    )
    artifact = security.paper_object_spec(UNATTENDED_FILE)
    assert artifact.role is security.PaperObjectRole.UNATTENDED_INVOCATION_FILE
    assert security.paper_object_spec(UNATTENDED_STAGING_FILE).role is (
        security.PaperObjectRole.UNATTENDED_INVOCATION_FILE
    )
    assert artifact.maximum_bytes == (
        security.MAX_PERSONAL_DESKTOP_UNATTENDED_PAPER_INVOCATION_BYTES
    )
    assert security.paper_security_policy(artifact.role, SID).owner_sid == SID


@pytest.mark.parametrize(
    "path",
    (
        UNATTENDED.lower(),
        UNATTENDED + "\\",
        UNATTENDED.replace("Paper-v2", "Paper-v20"),
        UNATTENDED
        + "\\unattended-paper-invocation-AAAAAAAA-AAAA-5AAA-8AAA-AAAAAAAAAAAA",
        UNATTENDED_FINAL.replace(IDENTITY, "21111111-1111-5111-8111-111111111111")
        + f"\\personal-desktop-unattended-paper-invocation-{IDENTITY}.json",
        UNATTENDED_FINAL
        + f"\\personal-desktop-unattended-paper-invocation-{IDENTITY}.JSON",
        UNATTENDED_FINAL + "\\extra.json",
    ),
)
def test_unattended_alias_case_parent_and_identity_mismatch_rejected_before_open(path):
    api = MemoryReadApi()
    with security.PinnedTradingPaperReadSession(api, SID) as session:
        with pytest.raises(AuthorityPathError):
            session.pin(path)
    assert api.calls == []


@pytest.mark.parametrize("path", V2_ROLES)
@pytest.mark.parametrize(
    "change",
    [
        "owner",
        "unprotected",
        "outsider",
        "missing-system",
        "missing-admin",
        "duplicate",
        "inherited",
        "inherit-only",
        "deny",
        "object-ace",
        "write-dac",
        "write-owner",
    ],
)
def test_role_policy_rejects_acl_mutations(path, change):
    observed = inspection(path)
    aces = observed.aces
    if change == "owner":
        observed = replace(observed, owner_sid="S-1-5-21-4-5-6-1009")
    elif change == "unprotected":
        observed = replace(observed, dacl_protected=False)
    elif change == "outsider":
        aces += (SecurityAce("S-1-1-0", security.TRADING_FILE_READ),)
    elif change == "missing-system":
        aces = tuple(a for a in aces if a.principal_sid != security.SYSTEM_SID)
    elif change == "missing-admin":
        aces = tuple(a for a in aces if a.principal_sid != security.ADMINISTRATORS_SID)
    elif change == "duplicate":
        aces += (aces[-1],)
    else:
        changes = {
            "inherited": {"ace_flags": 0x10},
            "inherit-only": {"ace_flags": 8},
            "deny": {"ace_type": 1},
            "object-ace": {"ace_type": 5},
            "write-dac": {"access_mask": aces[-1].access_mask | 0x40000},
            "write-owner": {"access_mask": aces[-1].access_mask | 0x80000},
        }
        aces = (*aces[:-1], replace(aces[-1], **changes[change]))
    with pytest.raises(AuthoritySecurityError):
        security.require_paper_object_security(
            path, security.paper_object_spec(path), replace(observed, aces=aces), SID
        )


@pytest.mark.parametrize(
    "path", [ROOT, ANCHOR, GENESIS, CHECKPOINT, RUNTIME, OPERATIONS, UNATTENDED]
)
def test_trading_cannot_own_immutable_or_runtime_containers(path):
    with pytest.raises(AuthoritySecurityError):
        security.paper_security_policy(
            security.paper_object_spec(path).role, SID, owner_sid=SID
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"final_path": ROOT.lower()},
        {"final_path": "\\\\?\\" + ROOT},
        {"final_path": r"\\?\GLOBALROOT\Device\HarddiskVolume1"},
        {"is_reparse_point": True},
        {"kind": AuthorityObjectKind.FILE},
        {"filesystem": "FAT32"},
        {"volume_root": "G:\\"},
    ],
)
@pytest.mark.parametrize(
    "session_type",
    [security.PinnedPaperReadSession, security.PinnedTradingPaperReadSession],
)
def test_unsafe_handle_facts_fail_before_artifact_read(changes, session_type):
    api = MemoryReadApi()
    api.put(ROOT)
    node = api.nodes[ROOT]
    node.observation = replace(
        node.observation, security=replace(node.observation.security, **changes)
    )
    with pytest.raises((AuthorityObjectError, AuthoritySecurityError)):
        with session_type(api, SID) as session:
            session.pin(ROOT)
    assert not api.handles
    assert not any(call[0] == "read" for call in api.calls)


@pytest.mark.parametrize(
    "change", ["identity", "replacement", "acl", "content", "inventory"]
)
@pytest.mark.parametrize(
    "session_type",
    [security.PinnedPaperReadSession, security.PinnedTradingPaperReadSession],
)
def test_pinned_interval_rechecks_identity_security_bytes_and_inventory(
    change, session_type
):
    api = MemoryReadApi()
    api.put(ANCHOR, b"anchor")
    with pytest.raises((AuthorityObjectError, AuthoritySecurityError)):
        with session_type(api, SID) as session:
            session.read(ANCHOR)
            session.names(ROOT)
            node = api.nodes[ANCHOR]
            if change == "identity":
                node.observation = replace(node.observation, identity=(7, 900))
            elif change == "replacement":
                api.nodes[ANCHOR] = replace(
                    node, observation=replace(node.observation, identity=(7, 900))
                )
            elif change == "acl":
                node.observation = replace(
                    node.observation,
                    security=replace(node.observation.security, dacl_protected=False),
                )
            elif change == "content":
                node.payload = b"ANCHOR"
            else:
                api.overrides[ROOT] = (
                    "personal-desktop-paper-account-authority.json",
                    "unexpected",
                )
    assert not api.handles


@pytest.mark.parametrize(
    "path,maximum",
    [
        (ANCHOR, security.MAX_INSTALLED_PAPER_ANCHOR_BYTES),
        (CHECKPOINT, security.MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES),
    ],
)
def test_artifact_size_limit_is_checked_before_native_read(path, maximum):
    api = MemoryReadApi()
    api.put(path, b"x")
    api.nodes[path].observation = replace(
        api.nodes[path].observation, byte_length=maximum + 1
    )
    with pytest.raises(AuthorityObjectError, match="length"):
        with security.PinnedPaperReadSession(api, SID) as session:
            session.read(path)
    assert not any(call[0] == "read" for call in api.calls)
    assert not api.handles


@pytest.mark.parametrize(
    "names",
    [
        ("runtime", "RUNTIME"),
        ("..",),
        ("x:y",),
        ("x\\y",),
        tuple(str(i) for i in range(security.MAX_PAPER_V2_DIRECTORY_ENTRIES + 1)),
    ],
)
def test_inventory_names_and_bounds_fail_closed(names):
    api = MemoryReadApi()
    api.put(ROOT)
    api.overrides[ROOT] = names
    with pytest.raises(AuthorityObjectError):
        with security.PinnedPaperReadSession(api, SID) as session:
            session.names(ROOT)


def test_native_open_is_read_only_open_existing_no_follow_and_no_delete_sharing():
    calls = []

    class CreateFile:
        def __call__(self, *args):
            calls.append(args)
            return 9

    class Kernel:
        CreateFileW = CreateFile()

    api = object.__new__(security.WindowsPaperReadNativeApi)
    api._kernel = Kernel()
    for path in (ROOT, ANCHOR):
        handle = api.open(path, security.paper_object_spec(path).kind)
        # Fake handles are not passed to real CloseHandle.
        assert isinstance(handle, WindowsHandle)
        handle._close = False
    assert [call[2] for call in calls] == [3, 1]
    assert all(
        call[1] == 0x20081 and call[4] == 3 and call[5] == 0x02200000 for call in calls
    )
    assert all(call[3] is None and call[6] is None for call in calls)
    with pytest.raises(AuthorityPathError):
        api.open(r"F:\test\Paper-v2", AuthorityObjectKind.DIRECTORY)
    assert len(calls) == 2


@pytest.fixture
def staging_kernel(monkeypatch):
    class Function:
        def __init__(self, action):
            self.action = action

        def __call__(self, *args):
            return self.action(*args)

    class Kernel:
        def __init__(self):
            self.calls = []
            self.handle = 9
            self.error = 0
            self.close_result = 1
            self.CreateFileW = Function(self.create)
            self.CloseHandle = Function(self.close)

        def create(self, *args):
            self.calls.append(("create", args))
            return self.handle

        def close(self, handle):
            self.calls.append(("close", handle))
            return self.close_result

    kernel = Kernel()
    monkeypatch.setattr(ctypes, "get_last_error", lambda: kernel.error, raising=False)
    api = object.__new__(security.WindowsPaperReadNativeApi)
    api._kernel = kernel
    return api, kernel


def test_fixed_staging_probe_is_zero_access_no_follow_and_closes(staging_kernel):
    api, kernel = staging_kernel
    # Only CreateFileW and CloseHandle exist on this kernel. No type/content/ACL
    # query or mutation can occur; any successful object open blocks admission.
    assert api.fixed_staging_present() is True
    assert kernel.calls == [
        (
            "create",
            (
                security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT,
                0,
                1 | 2 | 4,
                None,
                3,
                0x02000000 | 0x00200000,
                None,
            ),
        ),
        ("close", 9),
    ]
    assert kernel.CreateFileW.argtypes == [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    assert kernel.CreateFileW.restype is ctypes.c_void_p
    assert kernel.CloseHandle.argtypes == [ctypes.c_void_p]
    assert kernel.CloseHandle.restype is ctypes.c_int32


@pytest.mark.parametrize("handle", [-1, ctypes.c_void_p(-1).value])
@pytest.mark.parametrize("error", [2, 3, 0, 5, 32, 123, 303, 1920])
def test_fixed_staging_probe_only_exact_not_found_is_absent(
    staging_kernel, handle, error
):
    api, kernel = staging_kernel
    kernel.handle, kernel.error = handle, error
    if error in (2, 3):
        assert api.fixed_staging_present() is False
    else:
        with pytest.raises(AuthorityObjectError, match="staging presence"):
            api.fixed_staging_present()
    assert [call[0] for call in kernel.calls] == ["create"]


@pytest.mark.parametrize("handle", [None, 0])
def test_fixed_staging_probe_null_handle_is_not_trustworthy_absence(
    staging_kernel, handle
):
    api, kernel = staging_kernel
    kernel.handle, kernel.error = handle, 2
    with pytest.raises(AuthorityObjectError, match="invalid"):
        api.fixed_staging_present()
    assert [call[0] for call in kernel.calls] == ["create"]


def test_fixed_staging_probe_close_failure_blocks(staging_kernel):
    api, kernel = staging_kernel
    kernel.close_result = 0
    with pytest.raises(AuthorityObjectError, match="close"):
        api.fixed_staging_present()
    assert kernel.calls[-1] == ("close", 9)


def test_fixed_staging_probe_has_no_caller_inputs(staging_kernel):
    api, kernel = staging_kernel
    assert not inspect.signature(api.fixed_staging_present).parameters
    assert tuple(
        inspect.signature(security.PaperReadNativeApi.fixed_staging_present).parameters
    ) == ("self",)
    for value in (ROOT, security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT, False, api):
        with pytest.raises(TypeError):
            api.fixed_staging_present(value)
    with pytest.raises(TypeError):
        api.fixed_staging_present(path=ROOT)
    assert kernel.calls == []


@pytest.mark.parametrize(
    "path",
    [
        "F:\\",
        security.PERSONAL_DESKTOP_PAPER_PARENT,
        security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT,
    ],
)
def test_trading_session_cannot_admit_parent_or_staging(path):
    api = MemoryReadApi()
    with security.PinnedTradingPaperReadSession(api, SID) as session:
        with pytest.raises(AuthorityPathError):
            session.pin(path)
    assert api.calls == []


def test_snapshot_dependencies_cannot_supply_a_path():
    expected = (
        r"F:\AITradingBot\Authority\capture-output\daily-market-data-snapshot-"
        + IDENTITY
        + ".json"
    )
    assert security.historical_snapshot_path(UUID(IDENTITY)) == expected
    for value in (expected, ROOT, "..", "\\\\server\\share"):
        with pytest.raises(AuthorityPathError):
            security.historical_snapshot_path(value)


def test_hardlinks_and_aggregate_size_bounds(monkeypatch):
    api = MemoryReadApi()
    api.put(ANCHOR, b"anchor")
    api.nodes[ANCHOR].observation = replace(api.nodes[ANCHOR].observation, links=2)
    with pytest.raises(AuthorityObjectError, match="hard-link"):
        with security.PinnedPaperReadSession(api, SID) as session:
            session.read(ANCHOR)
    api.nodes[ANCHOR].observation = replace(api.nodes[ANCHOR].observation, links=1)
    monkeypatch.setattr(security, "MAX_PAPER_V2_READ_BYTES", 5)
    with pytest.raises(AuthorityObjectError, match="aggregate"):
        with security.PinnedPaperReadSession(api, SID) as session:
            session.read(ANCHOR)
    assert not any(call[0] == "read" for call in api.calls)


def test_native_read_checks_size_before_allocating(monkeypatch):
    class GetSize:
        def __call__(self, handle, pointer):
            ctypes.cast(pointer, ctypes.POINTER(ctypes.c_int64))[0] = 4097
            return 1

    class Kernel:
        GetFileSizeEx = GetSize()

    api = object.__new__(security.WindowsPaperReadNativeApi)
    api._kernel = Kernel()
    with pytest.raises(AuthorityObjectError, match="bound"):
        api.read(WindowsHandle(9, close=False), 4096)


@pytest.mark.parametrize("failure", [None, "seek", "short", "growth"])
def test_native_bounded_read_uses_pinned_handle_and_checks_completion(failure):
    from .test_personal_desktop_paper_account_token import Function

    calls = []
    sizes = []

    def get_size(handle, pointer):
        assert handle == 9
        sizes.append(handle)
        value = 7 if failure == "growth" and len(sizes) > 1 else 6
        ctypes.cast(pointer, ctypes.POINTER(ctypes.c_int64))[0] = value
        return 1

    def seek(handle, offset, unused, origin):
        assert handle == 9 and offset == 0 and origin == 0
        calls.append("seek")
        return failure != "seek"

    def read(handle, buffer, maximum, count, overlapped):
        assert handle == 9 and maximum == 6 and overlapped is None
        calls.append("read")
        ctypes.memmove(buffer, b"anchor", 6)
        ctypes.cast(count, ctypes.POINTER(ctypes.c_uint32))[0] = (
            0 if failure == "short" else 6
        )
        return 1

    class Kernel:
        GetFileSizeEx = Function(get_size)
        SetFilePointerEx = Function(seek)
        ReadFile = Function(read)

    api = object.__new__(security.WindowsPaperReadNativeApi)
    api._kernel = Kernel()
    if failure:
        with pytest.raises(AuthorityObjectError):
            api.read(WindowsHandle(9, close=False), 4096)
    else:
        assert api.read(WindowsHandle(9, close=False), 4096) == b"anchor"
        assert calls == ["seek", "read"]
    if failure == "seek":
        assert calls == ["seek"]


@pytest.mark.parametrize("drive,flags", [(3, 8), (4, 8), (3, 0)])
def test_native_identity_and_fixed_persistent_acl_volume_checks(
    monkeypatch, drive, flags
):
    from .test_personal_desktop_paper_account_token import Function

    monkeypatch.setattr(
        security, "inspect_open_authority_object", lambda *args: inspection(ANCHOR)
    )

    def volume(root, label, label_size, serial, component, returned_flags, fs, fs_size):
        assert root == "F:\\"
        ctypes.cast(returned_flags, ctypes.POINTER(ctypes.c_uint32))[0] = flags
        return 1

    def info(handle, pointer):
        assert handle == 9
        fields = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))
        fields[7], fields[9], fields[10], fields[11], fields[12] = 7, 6, 1, 1, 9
        return 1

    class Kernel:
        GetDriveTypeW = Function(lambda path: drive)
        GetVolumeInformationW = Function(volume)
        GetFileInformationByHandle = Function(info)

    api = object.__new__(security.WindowsPaperReadNativeApi)
    api._kernel = Kernel()
    if drive != 3 or flags != 8:
        with pytest.raises(AuthorityObjectError, match="persistent-ACL"):
            api.inspect(WindowsHandle(9, close=False), ANCHOR, AuthorityObjectKind.FILE)
    else:
        result = api.inspect(
            WindowsHandle(9, close=False), ANCHOR, AuthorityObjectKind.FILE
        )
        assert result.identity == (7, (1 << 32) | 9)
        assert result.byte_length == 6 and result.links == 1


def test_pin_bound_includes_recursively_opened_ancestors(monkeypatch):
    api = MemoryReadApi()
    api.put(ANCHOR, b"anchor")
    monkeypatch.setattr(security, "MAX_PAPER_V2_PINNED_OBJECTS", 2)
    with pytest.raises(AuthorityObjectError, match="pinned-object bound"):
        with security.PinnedPaperReadSession(api, SID) as session:
            session.read(ANCHOR)
    assert sum(call[0] == "open" for call in api.calls) == 2
    assert not api.handles


@pytest.mark.parametrize("mask", [0x2, 0x4, 0x40, 0x10000, 0x40000, 0x80000])
def test_parent_chain_rejects_unrelated_replacement_authority(mask):
    api = MemoryReadApi()
    api.put(ANCHOR, b"anchor")
    node = api.nodes[security.PERSONAL_DESKTOP_PAPER_PARENT]
    changed = replace(
        node.observation.security,
        aces=(*node.observation.security.aces, SecurityAce("S-1-1-0", mask)),
    )
    node.observation = replace(node.observation, security=changed)
    with pytest.raises(AuthoritySecurityError, match="replacement"):
        with security.PinnedPaperReadSession(api, SID) as session:
            session.read(ANCHOR)
    assert not any(call[0] == "open" and call[1] == ROOT for call in api.calls)


@pytest.mark.parametrize("mask", [0x1301BF, 0x1200A9, 0x2, 0x4, 0x10, 0x100, 0x10000])
def test_volume_accepts_ordinary_data_and_self_delete_rights(mask):
    path = "F:\\"
    observed = inspection(path)
    observed = replace(observed, aces=(*observed.aces, SecurityAce("S-1-5-11", mask)))
    security.require_paper_object_security(
        path, security.paper_object_spec(path), observed, SID
    )


@pytest.mark.parametrize(
    "mask",
    [0x40, 0x40000, 0x80000, 0x10000000, 0x20000000, 0x40000000, 0x80000000, 0x200],
)
def test_volume_rejects_child_delete_security_control_and_unknown_rights(mask):
    path = "F:\\"
    observed = inspection(path)
    observed = replace(
        observed, aces=(*observed.aces, SecurityAce("S-1-5-11", 0x1301BF | mask))
    )
    with pytest.raises(AuthoritySecurityError, match="replacement"):
        security.require_paper_object_security(
            path, security.paper_object_spec(path), observed, SID
        )


@pytest.mark.parametrize("path", ["F:\\", security.PERSONAL_DESKTOP_PAPER_PARENT])
@pytest.mark.parametrize(
    "change",
    ["owner", "missing-system", "missing-admin", "partial-admin", "deny", "flags"],
)
def test_parent_roles_retain_owner_full_control_and_ace_validation(path, change):
    observed = inspection(path)
    if change == "owner":
        observed = replace(observed, owner_sid=SID)
    elif change == "missing-system":
        observed = replace(observed, aces=observed.aces[:1])
    elif change == "missing-admin":
        observed = replace(observed, aces=observed.aces[1:])
    else:
        changes = {
            "partial-admin": {"access_mask": 0x1200A9},
            "deny": {"ace_type": 1},
            "flags": {"ace_flags": 8},  # inherit-only is not effective control
        }
        observed = replace(
            observed,
            aces=(replace(observed.aces[0], **changes[change]), observed.aces[1]),
        )
    with pytest.raises(AuthoritySecurityError):
        security.require_paper_object_security(
            path, security.paper_object_spec(path), observed, SID
        )


@pytest.mark.parametrize("owner", [security.ADMINISTRATORS_SID, security.SYSTEM_SID])
def test_recursive_pin_crosses_representative_safe_volume_acl(owner):
    api = MemoryReadApi()
    api.put(ANCHOR, b"anchor")
    volume = api.nodes["F:\\"]
    observed = replace(
        volume.observation.security,
        owner_sid=owner,
        aces=(
            *volume.observation.security.aces,
            SecurityAce("S-1-5-11", 0x1301BF, ace_flags=3),
            SecurityAce("S-1-5-32-545", 0x1200A9, ace_flags=0x13),
        ),
    )
    volume.observation = replace(volume.observation, security=observed)
    with security.PinnedPaperReadSession(api, SID) as session:
        assert session.read(ANCHOR) == b"anchor"
    opened = [call[1] for call in api.calls if call[0] == "open"]
    assert opened[:4] == ["F:\\", security.PERSONAL_DESKTOP_PAPER_PARENT, ROOT, ANCHOR]
    assert api.inspections["F:\\"] >= 3  # initial, retained, and reopened checks
    assert not api.handles


@pytest.mark.parametrize("field", ["byte_length", "links"])
def test_publication_parent_metadata_reproduces_strict_read_failure(field):
    api = MemoryReadApi()
    path = security.PERSONAL_DESKTOP_PAPER_PARENT
    api.put(path)
    with security.PinnedPaperPublicationParent(api, SID) as parent:
        # The exact generic session/comparison used by the old publisher.
        with pytest.raises(
            AuthorityObjectError, match="pinned identity/security drift"
        ):
            with security.PinnedPaperReadSession(api, SID) as ordinary:
                ordinary.pin(path)
                node = api.nodes[path]
                node.observation = replace(
                    node.observation, **{field: getattr(node.observation, field) + 1}
                )
                parent.finish()
    assert not api.handles


@pytest.mark.parametrize("named_only", [False, True])
@pytest.mark.parametrize("path", ["F:\\", security.PERSONAL_DESKTOP_PAPER_PARENT])
@pytest.mark.parametrize(
    "change",
    [
        "identity",
        "identity-type",
        "owner",
        "acl",
        "protected",
        "expected-path",
        "final-path",
        "kind",
        "reparse",
        "volume",
        "filesystem",
    ],
)
def test_publication_parent_rejects_authority_drift(path, change, named_only):
    api = MemoryReadApi()
    api.put(security.PERSONAL_DESKTOP_PAPER_PARENT)
    with pytest.raises((AuthorityObjectError, AuthoritySecurityError)):
        with security.PinnedPaperPublicationParent(api, SID):
            node = api.nodes[path]
            observed = node.observation
            if change == "identity":
                changed = replace(observed, identity=(7, 999))
            elif change == "identity-type":
                changed = replace(
                    observed, identity=tuple(map(float, observed.identity))
                )
            else:
                fields = {
                    "owner": {"owner_sid": security.SYSTEM_SID},
                    "acl": {"aces": tuple(reversed(observed.security.aces))},
                    "protected": {"dacl_protected": False},
                    "expected-path": {"expected_path": path.lower()},
                    "final-path": {"final_path": path.lower()},
                    "kind": {"kind": AuthorityObjectKind.FILE},
                    "reparse": {"is_reparse_point": True},
                    "volume": {"volume_root": "G:\\"},
                    "filesystem": {"filesystem": "FAT32"},
                }
                changed = replace(
                    observed, security=replace(observed.security, **fields[change])
                )
            if named_only:
                api.nodes[path] = replace(node, observation=changed)
            else:
                node.observation = changed
    assert not api.handles


@pytest.mark.parametrize("field", ["byte_length", "links"])
def test_publication_guard_does_not_relax_volume_metadata(field):
    api = MemoryReadApi()
    api.put(security.PERSONAL_DESKTOP_PAPER_PARENT)
    with pytest.raises(AuthorityObjectError, match="identity/security drift"):
        with security.PinnedPaperPublicationParent(api, SID):
            node = api.nodes["F:\\"]
            node.observation = replace(node.observation, **{field: 9})
    assert not api.handles


def test_explicit_parent_inventory_remains_strict_during_publication():
    api = MemoryReadApi()
    path = security.PERSONAL_DESKTOP_PAPER_PARENT
    api.put(path)
    with security.PinnedPaperPublicationParent(api, SID) as parent:
        with pytest.raises(AuthorityObjectError, match="inventory changed"):
            with security.PinnedPaperReadSession(api, SID) as ordinary:
                assert ordinary.names(path) == ()
                api.overrides[path] = (".Paper-v2.provisioning",)
                parent.finish()
    assert not api.handles


REAL_HOST_VOLUME_ACES = (
    SecurityAce(security.ADMINISTRATORS_SID, FILE_ALL_ACCESS),
    SecurityAce(security.ADMINISTRATORS_SID, 0x10000000, ace_flags=0x0B),
    SecurityAce(security.SYSTEM_SID, FILE_ALL_ACCESS),
    SecurityAce(security.SYSTEM_SID, 0x10000000, ace_flags=0x0B),
    SecurityAce("S-1-5-11", 0x001301BF),
    SecurityAce("S-1-5-11", 0xE0010000, ace_flags=0x0B),
    SecurityAce("S-1-5-32-545", 0x001200A9),
    SecurityAce("S-1-5-32-545", 0xA0000000, ace_flags=0x0B),
)


def test_real_host_volume_acl_accepts_effective_rights_and_inherit_only_templates():
    path = "F:\\"
    security.require_paper_object_security(
        path,
        security.paper_object_spec(path),
        replace(inspection(path), aces=REAL_HOST_VOLUME_ACES),
        SID,
    )


def test_recursive_pin_crosses_real_host_volume_and_strict_protected_parent():
    api = MemoryReadApi()
    api.put(ANCHOR, b"anchor")
    volume = api.nodes["F:\\"]
    volume.observation = replace(
        volume.observation,
        security=replace(volume.observation.security, aces=REAL_HOST_VOLUME_ACES),
    )
    parent = api.nodes[security.PERSONAL_DESKTOP_PAPER_PARENT].observation.security
    assert parent.owner_sid == security.ADMINISTRATORS_SID
    assert parent.dacl_protected is True
    assert parent.aces == (
        SecurityAce(security.ADMINISTRATORS_SID, FILE_ALL_ACCESS),
        SecurityAce(security.SYSTEM_SID, FILE_ALL_ACCESS),
    )
    with security.PinnedPaperReadSession(api, SID) as session:
        assert session.read(ANCHOR) == b"anchor"
    opened = [call[1] for call in api.calls if call[0] == "open"]
    assert opened[:4] == ["F:\\", security.PERSONAL_DESKTOP_PAPER_PARENT, ROOT, ANCHOR]
    assert api.inspections["F:\\"] >= 3
    assert not api.handles


@pytest.mark.parametrize(
    "principal", [security.ADMINISTRATORS_SID, security.SYSTEM_SID]
)
@pytest.mark.parametrize("mask", [FILE_ALL_ACCESS, 0x10000000])
def test_volume_inherit_only_control_does_not_replace_effective_control(
    principal, mask
):
    path = "F:\\"
    aces = tuple(
        replace(ace, access_mask=mask, ace_flags=0x0B)
        if ace.principal_sid == principal
        else ace
        for ace in inspection(path).aces
    )
    with pytest.raises(AuthoritySecurityError, match="lacks SYSTEM/Administrators"):
        security.require_paper_object_security(
            path,
            security.paper_object_spec(path),
            replace(inspection(path), aces=aces),
            SID,
        )


@pytest.mark.parametrize("flags", [0x09, 0x0A, 0x0B, 0x19, 0x1A, 0x1B])
def test_volume_inherit_only_requires_object_or_container_inheritance(flags):
    path = "F:\\"
    observed = inspection(path)
    template = SecurityAce("S-1-5-11", 0xE0010000, ace_flags=flags)
    security.require_paper_object_security(
        path,
        security.paper_object_spec(path),
        replace(observed, aces=(*observed.aces, template)),
        SID,
    )


@pytest.mark.parametrize("flags", [0x08, 0x18, 0x04, 0x0F, 0x20, 0x2B, 0x4B, 0x8B])
def test_volume_rejects_malformed_inherit_only_and_unsupported_flags(flags):
    path = "F:\\"
    observed = inspection(path)
    template = SecurityAce("S-1-5-11", 0xE0010000, ace_flags=flags)
    with pytest.raises(AuthoritySecurityError):
        security.require_paper_object_security(
            path,
            security.paper_object_spec(path),
            replace(observed, aces=(*observed.aces, template)),
            SID,
        )


@pytest.mark.parametrize("ace_type", [1, 5])
def test_volume_inherit_only_still_requires_ordinary_allow_ace(ace_type):
    path = "F:\\"
    aces = (
        *REAL_HOST_VOLUME_ACES[:-1],
        replace(REAL_HOST_VOLUME_ACES[-1], ace_type=ace_type),
    )
    with pytest.raises(AuthoritySecurityError, match="unsupported"):
        security.require_paper_object_security(
            path,
            security.paper_object_spec(path),
            replace(inspection(path), aces=aces),
            SID,
        )


@pytest.mark.parametrize("mask", [0xE0010000, 0xA0000000, 0x1301BF])
@pytest.mark.parametrize("flags", [0, 0x03, 0x0B])
def test_parent_rejects_unrelated_effective_and_inherit_only_write_templates(
    mask, flags
):
    path = security.PERSONAL_DESKTOP_PAPER_PARENT
    observed = inspection(path)
    with pytest.raises(AuthoritySecurityError):
        security.require_paper_object_security(
            path,
            security.paper_object_spec(path),
            replace(
                observed,
                aces=(*observed.aces, SecurityAce("S-1-5-11", mask, ace_flags=flags)),
            ),
            SID,
        )
