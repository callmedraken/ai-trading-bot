"""Read-only memory object tests; no production directory is ever created."""

import ctypes
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

SID = "S-1-5-21-1-2-3-1009"
IDENTITY = "11111111-1111-5111-8111-111111111111"
ROOT = security.PERSONAL_DESKTOP_PAPER_V2_ROOT
ANCHOR = security.PERSONAL_DESKTOP_PAPER_V2_ANCHOR
RUNTIME = security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
OPERATIONS = security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
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
        if path in self.overrides:
            return self.overrides[path]
        prefix = path if path.endswith("\\") else path + "\\"
        return tuple(
            p[len(prefix) :]
            for p in self.nodes
            if p.startswith(prefix) and p != path and "\\" not in p[len(prefix) :]
        )


def test_exact_constants_and_existing_c1_path_guard_is_unchanged():
    assert ROOT == r"F:\AITradingBot\Paper-v2"
    assert (
        security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT
        == r"F:\AITradingBot\.Paper-v2.provisioning"
    )
    assert RUNTIME == r"F:\AITradingBot\Paper-v2\runtime"
    assert OPERATIONS == r"F:\AITradingBot\Paper-v2\runtime\paper-operations"
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


V2_ROLES = [ROOT, ANCHOR, GENESIS, CHECKPOINT, RUNTIME, OPERATIONS, TRANSITION, REPORT]


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
    elif path in {RUNTIME, OPERATIONS}:
        assert observed.owner_sid == security.ADMINISTRATORS_SID
        assert trading.access_mask & 0x6 == 0x6
    else:
        assert observed.owner_sid == SID
    # All accepted entries are explicit allows without inheritance flags.
    assert all(ace.ace_type == 0 and ace.ace_flags == 0 for ace in observed.aces)
    security.require_paper_object_security(
        path, spec, replace(observed, aces=tuple(reversed(observed.aces))), SID
    )


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
    "path", [ROOT, ANCHOR, GENESIS, CHECKPOINT, RUNTIME, OPERATIONS]
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
def test_unsafe_handle_facts_fail_before_artifact_read(changes):
    api = MemoryReadApi()
    api.put(ROOT)
    node = api.nodes[ROOT]
    node.observation = replace(
        node.observation, security=replace(node.observation.security, **changes)
    )
    with pytest.raises((AuthorityObjectError, AuthoritySecurityError)):
        with security.PinnedPaperReadSession(api, SID) as session:
            session.pin(ROOT)
    assert not api.handles
    assert not any(call[0] == "read" for call in api.calls)


@pytest.mark.parametrize(
    "change", ["identity", "replacement", "acl", "content", "inventory"]
)
def test_pinned_interval_rechecks_identity_security_bytes_and_inventory(change):
    api = MemoryReadApi()
    api.put(ANCHOR, b"anchor")
    with pytest.raises((AuthorityObjectError, AuthoritySecurityError)):
        with security.PinnedPaperReadSession(api, SID) as session:
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


@pytest.mark.parametrize("mask", [0x40, 0x40000, 0x80000, 0x10000000, 0x200])
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
