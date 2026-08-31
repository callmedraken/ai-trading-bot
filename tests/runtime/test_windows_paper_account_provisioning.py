"""Fake Win32 source gates. No native production objects or effects are used."""

import ctypes
from contextlib import contextmanager
from dataclasses import replace
from pathlib import PureWindowsPath
from types import SimpleNamespace
from uuid import UUID

import pytest
from tests.runtime.test_manual_paper_account_provisioning import (
    MACHINE,
    SID,
    make_bundle,
)

import trading_bot.runtime.windows_paper_account_provisioning as p
from trading_bot.runtime.manual_paper_account_provisioning import (
    verify_manual_paper_account_provisioning_bundle,
)
from trading_bot.runtime.windows_authority_security import (
    CREATE_NEW,
    DELETE,
    FILE_FLAG_OPEN_REPARSE_POINT,
    FILE_SHARE_DELETE,
    FILE_SHARE_READ,
    FILE_WRITE_DATA,
    OPEN_EXISTING,
    SecurityInspection,
    authority_parent_security_policy,
)
from trading_bot.runtime.windows_paper_account_security import (
    WindowsPaperAccountReadSession,
    paper_account_security_policy,
)


class Function:
    def __init__(self, call):
        self.call = call

    def __call__(self, *args):
        return self.call(*args)


class FakeWin32:
    """Exercise the real native session using an entirely in-memory kernel."""

    def __init__(self):
        self.nodes = {}
        self.handles = {}
        self.next_id = 1
        self.next_handle = 100
        self.events = []
        self.opens = []
        self.creations = []
        self.fault = None
        self.fault_used = False
        self.corruption = None
        self.active_policy = None
        self.last_error = 2
        for path in (PureWindowsPath("F:/"), p._PARENT):
            self.node(path, True, authority_parent_security_policy())

    def node(self, path, directory, policy):
        result = dict(
            path=path,
            directory=directory,
            policy=policy,
            data=b"",
            identity=self.next_id,
            links=1,
        )
        self.next_id += 1
        self.nodes[path] = result
        return result

    def label(self, node):
        path = node["path"]
        if path in (PureWindowsPath("F:/"), p._PARENT):
            return "parent"
        stage = (
            "staging"
            if path.is_relative_to(p.PRODUCTION_PAPER_STAGING_ROOT)
            else "final"
        )
        role = (
            "anchor"
            if path.name == "manual-paper-account-authority.json"
            else "genesis-file"
            if path.suffix == ".json"
            else "genesis-directory"
            if path.name.startswith("paper-account-genesis-")
            else "root"
        )
        return f"{role}:{stage}"

    def event(self, name, when):
        self.events.append((name, when))
        if self.fault == (name, when) and not self.fault_used:
            self.fault_used = True
            raise OSError("raw native error with private diagnostic")

    def __getattr__(self, name):
        return Function(getattr(self, "api_" + name))

    def api_CreateDirectoryW(self, path, security):
        path = PureWindowsPath(path)
        role = (
            "root" if path == p.PRODUCTION_PAPER_STAGING_ROOT else "genesis-directory"
        )
        label = f"create:{role}"
        self.event(label, "before")
        assert security is not None and self.active_policy is not None
        if path in self.nodes:
            return 0
        self.node(path, True, self.active_policy)
        self.creations.append((path, self.active_policy))
        self.event(label, "after")
        return 1

    def api_CreateFileW(
        self, path, access, share, security, disposition, flags, template
    ):
        path = PureWindowsPath(path)
        assert flags & FILE_FLAG_OPEN_REPARSE_POINT
        assert template is None
        self.opens.append((path, access, share, disposition, flags))
        if disposition == CREATE_NEW:
            assert security is not None and self.active_policy is not None
            role = (
                "anchor"
                if path.name == "manual-paper-account-authority.json"
                else "genesis-file"
            )
            self.event("create:" + role, "before")
            if path in self.nodes:
                return -1
            self.node(path, False, self.active_policy)
            self.creations.append((path, self.active_policy))
            self.event("create:" + role, "after")
        else:
            assert disposition == OPEN_EXISTING
            if path not in self.nodes:
                return -1
        handle = self.next_handle
        self.next_handle += 1
        self.handles[handle] = self.nodes[path]
        return handle

    def api_GetFileType(self, handle):
        return 1

    def api_GetFileInformationByHandleEx(self, handle, info_class, pointer, size):
        node = self.handles[handle]
        if info_class == 18:
            target = ctypes.cast(pointer, ctypes.POINTER(p._FileIdInfo)).contents
            target.volume = 12
            target.identifier[:] = node["identity"].to_bytes(16, "little")
        else:
            assert info_class == 1
            target = ctypes.cast(pointer, ctypes.POINTER(p._FileStandardInfo)).contents
            target.size = len(node["data"])
            target.links = node["links"]
            target.directory = node["directory"]
            target.delete_pending = False
        return 1

    def api_GetFileAttributesW(self, path):
        node = self.nodes.get(PureWindowsPath(path))
        return (0x10 if node["directory"] else 0x80) if node else 0xFFFFFFFF

    def api_WriteFile(self, handle, buffer, length, count, overlapped):
        node = self.handles[handle]
        name = "write:" + self.label(node)
        self.event(name, "before")
        node["data"] = ctypes.string_at(buffer, length)
        actual = length
        if self.corruption == "partial-write" and "genesis-file" in name:
            node["data"] = node["data"][:3]
            actual = 3
        ctypes.cast(count, ctypes.POINTER(p.wintypes.DWORD)).contents.value = actual
        self.event(name, "after")
        return 1

    def api_FlushFileBuffers(self, handle):
        name = "flush:" + self.label(self.handles[handle])
        self.event(name, "before")
        self.event(name, "after")
        return 1

    def api_SetFilePointerEx(self, handle, offset, pointer, method):
        assert offset == 0 and method == 0
        return 1

    def api_ReadFile(self, handle, buffer, length, count, overlapped):
        node = self.handles[handle]
        label = self.label(node)
        name = "read:" + label
        self.event(name, "before")
        payload = node["data"]
        if self.corruption == label:
            payload = b"x" + payload[1:]
        ctypes.memmove(buffer, payload, len(payload))
        ctypes.cast(count, ctypes.POINTER(p.wintypes.DWORD)).contents.value = len(
            payload
        )
        self.event(name, "after")
        return 1

    def api_SetFileInformationByHandle(self, handle, info_class, buffer, size):
        assert info_class == 3
        info = p._PaperRootRenameInfo.from_buffer(buffer)
        assert info.flags == 0 and not info.root_directory
        name = ctypes.string_at(
            ctypes.addressof(buffer) + p._PaperRootRenameInfo.name.offset,
            info.name_length,
        ).decode("utf-16-le")
        assert name == str(p.PRODUCTION_PAPER_ROOT)
        assert self.handles[handle]["path"] == p.PRODUCTION_PAPER_STAGING_ROOT
        self.event("rename", "before")
        if self.corruption == "final-race":
            self.node(p.PRODUCTION_PAPER_ROOT, True, authority_parent_security_policy())
        if p.PRODUCTION_PAPER_ROOT in self.nodes:
            return 0
        changed = {}
        for path, node in self.nodes.items():
            new = (
                p.PRODUCTION_PAPER_ROOT
                / path.relative_to(p.PRODUCTION_PAPER_STAGING_ROOT)
                if path.is_relative_to(p.PRODUCTION_PAPER_STAGING_ROOT)
                else path
            )
            node["path"] = new
            changed[new] = node
        self.nodes = changed
        self.event("rename", "after")
        return 1

    def inspect(self, handle, path, kind):
        node = self.handles[handle]
        label = self.label(node)
        self.event("inspect:" + label, "before")
        assert path == node["path"]
        policy = node["policy"]
        if self.corruption == "security:" + label:
            policy = replace(policy, dacl_protected=False)
        if self.corruption == "identity:" + label:
            node["identity"] += 1
        inspection = SecurityInspection(
            str(path),
            str(path),
            kind,
            policy.owner_sid,
            policy.dacl_protected,
            policy.aces,
            False,
            "F:\\",
            "NTFS",
        )
        self.event("inspect:" + label, "after")
        return inspection

    def inventory(self, path, limit):
        root = PureWindowsPath(path)
        label = "inventory:" + self.label(self.nodes[root])
        self.event(label, "before")
        names = tuple(
            path.name for path in self.nodes if path.parent == root and path != root
        )
        if self.corruption == label:
            names += ("unexpected",)
        self.event(label, "after")
        return names


@pytest.fixture
def native(monkeypatch):
    fake = FakeWin32()
    monkeypatch.setattr(p, "require_windows_platform", lambda: None)
    monkeypatch.setattr(p.ctypes, "WinDLL", lambda *a, **k: fake, raising=False)
    monkeypatch.setattr(
        p.ctypes, "get_last_error", lambda: fake.last_error, raising=False
    )
    monkeypatch.setattr(p, "inspect_open_authority_object", fake.inspect)
    monkeypatch.setattr(p, "enumerate_paper_directory", fake.inventory)

    @contextmanager
    def security(policy):
        assert fake.active_policy is None
        fake.active_policy = policy
        try:
            yield SimpleNamespace(attributes=p.wintypes.DWORD(1))
        finally:
            fake.active_policy = None

    class Handle:
        def __init__(self, value, *, close=True):
            self.value = value
            self.owned = close

        def __enter__(self):
            return self.value

        def __exit__(self, *args):
            self.close()

        def close(self):
            if self.owned and self.value:
                fake.handles.pop(self.value)
                self.value = 0

    monkeypatch.setattr(p, "WindowsHandle", Handle)
    monkeypatch.setattr(p, "build_security_attributes", security)
    return fake


def publish(native, bundle=None, expected=None):
    bundle = bundle or make_bundle()
    expected = expected or verify_manual_paper_account_provisioning_bundle(bundle)
    return p._publish(bundle, expected, p._WindowsPublicationSession)


def test_exact_native_publication_sequence_and_security(native):
    bundle = make_bundle()
    result = publish(native, bundle)
    manifest = result.bundle.manifest
    assert result.state is p.PaperAccountPublicationState.PUBLISHED_VALIDATED
    assert p.PRODUCTION_PAPER_STAGING_ROOT not in native.nodes
    assert not native.handles
    expected = p._layout(p.PRODUCTION_PAPER_ROOT, manifest.genesis_checkpoint_id)
    assert set(native.nodes) == set(expected) | {PureWindowsPath("F:/"), p._PARENT}
    assert [policy for path, policy in native.creations] == [
        paper_account_security_policy(role, SID) for role in expected.values()
    ]
    for path, policy in native.creations:
        assert path.is_relative_to(p.PRODUCTION_PAPER_STAGING_ROOT)
        assert policy.owner_sid == "S-1-5-32-544"
        assert policy.dacl_protected
        assert policy.aces[-1].access_mask & 0x000C0000 == 0
        assert all(ace.ace_flags == 0 for ace in policy.aces)
    for path, access, share, disposition, _flags in native.opens:
        if path.is_relative_to(p.PRODUCTION_PAPER_ROOT):
            assert disposition == OPEN_EXISTING and not access & FILE_WRITE_DATA
        if path == p.PRODUCTION_PAPER_STAGING_ROOT:
            assert access & DELETE and not share & FILE_SHARE_DELETE
        if disposition == CREATE_NEW:
            assert share == FILE_SHARE_READ | FILE_SHARE_DELETE
    phases = [
        event
        for event, when in native.events
        if when == "before"
        and event.split(":")[0] in {"create", "write", "flush", "read", "rename"}
    ]
    assert phases == [
        "create:root",
        "create:genesis-directory",
        "create:genesis-file",
        "write:genesis-file:staging",
        "flush:genesis-file:staging",
        "read:genesis-file:staging",
        "create:anchor",
        "write:anchor:staging",
        "flush:anchor:staging",
        "read:anchor:staging",
        "rename",
        "read:genesis-file:final",
        "read:anchor:final",
    ]


PHASES = [
    "create:root",
    "create:genesis-directory",
    "create:genesis-file",
    "write:genesis-file:staging",
    "flush:genesis-file:staging",
    "read:genesis-file:staging",
    "create:anchor",
    "write:anchor:staging",
    "flush:anchor:staging",
    "read:anchor:staging",
    "inventory:root:staging",
    "inventory:genesis-directory:staging",
    "inspect:root:staging",
    "inspect:genesis-file:staging",
    "inspect:anchor:staging",
    "rename",
    "inspect:root:final",
    "read:genesis-file:final",
    "read:anchor:final",
    "inventory:root:final",
    "inventory:genesis-directory:final",
]


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize("when", ["before", "after"])
def test_faults_preserve_state_and_block_second_attempt(native, phase, when):
    native.fault = (phase, when)
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        publish(native)
    assert native.fault_used
    assert "raw native" not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__
    final = p.PRODUCTION_PAPER_ROOT in native.nodes
    staging = p.PRODUCTION_PAPER_STAGING_ROOT in native.nodes
    assert final != staging or (phase == "create:root" and when == "before")
    assert not native.handles
    if final:
        assert caught.value.state in {
            p.PaperAccountPublicationState.PUBLISHED_CANDIDATE,
            p.PaperAccountPublicationState.PUBLICATION_OUTCOME_UNCERTAIN,
        }
    if final or staging:
        before = [
            (path, node["data"], node["identity"], node["policy"])
            for path, node in native.nodes.items()
        ]
        creates = len(native.creations)
        with pytest.raises(p.WindowsPaperAccountProvisioningError):
            publish(native)
        assert len(native.creations) == creates
        assert before == [
            (path, node["data"], node["identity"], node["policy"])
            for path, node in native.nodes.items()
        ]


@pytest.mark.parametrize(
    "final,staging,state",
    [
        (True, False, p.PaperAccountPublicationState.EXISTING_FINAL),
        (False, True, p.PaperAccountPublicationState.STAGING_REQUIRES_MANUAL_RECOVERY),
        (True, True, p.PaperAccountPublicationState.EXISTING_FINAL_AND_STAGING),
    ],
)
def test_existing_state_never_mutated(native, final, staging, state):
    for present, path in (
        (final, p.PRODUCTION_PAPER_ROOT),
        (staging, p.PRODUCTION_PAPER_STAGING_ROOT),
    ):
        if present:
            native.node(path, False, authority_parent_security_policy())
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        publish(native)
    assert caught.value.state == state
    assert not native.creations


@pytest.mark.parametrize(
    "corruption",
    [
        "partial-write",
        "genesis-file:staging",
        "anchor:staging",
        "genesis-file:final",
        "anchor:final",
        "security:root:staging",
        "security:genesis-directory:staging",
        "security:genesis-file:staging",
        "security:anchor:staging",
        "security:root:final",
        "security:genesis-file:final",
        "security:anchor:final",
        "identity:root:staging",
        "identity:genesis-file:staging",
        "identity:root:final",
        "inventory:root:staging",
        "inventory:genesis-directory:staging",
        "inventory:root:final",
        "final-race",
    ],
)
def test_native_corruption_blocks_without_cleanup(native, corruption):
    native.corruption = corruption
    with pytest.raises(p.WindowsPaperAccountProvisioningError):
        publish(native)
    assert (
        p.PRODUCTION_PAPER_STAGING_ROOT in native.nodes
        or p.PRODUCTION_PAPER_ROOT in native.nodes
    )
    assert not native.handles


@pytest.mark.parametrize(
    "mode",
    ["other_expected", "none_expected", "bad_genesis", "bad_anchor", "bad_manifest"],
)
def test_all_bundle_validation_precedes_native_creation(native, mode):
    bundle = make_bundle()
    expected = verify_manual_paper_account_provisioning_bundle(bundle)
    if mode == "other_expected":
        from decimal import Decimal

        expected = verify_manual_paper_account_provisioning_bundle(
            make_bundle(starting_cash=Decimal("2"))
        )
    elif mode == "none_expected":
        expected = None
    else:
        field = mode.removeprefix("bad_") + "_bytes"
        bundle = replace(bundle, **{field: b"bad"})
    with pytest.raises(p.WindowsPaperAccountProvisioningError):
        p._publish(bundle, expected, p._WindowsPublicationSession)
    assert not native.creations and not native.opens


@pytest.mark.parametrize(
    "path",
    [
        r"F:\AITradingBot\PaperOther",
        r"F:\AITradingBot\Paper\..\Paper",
        r"F:\AITradingBot\paper",
        r"F:\AITradingBot\Paper.",
        r"F:\AITradingBot\Paper ",
        r"F:\AITradingBot\Paper:stream",
        r"F:\AITradingBot\Paper\CON",
        r"\\?\F:\AITradingBot\Paper",
        r"\\.\F:\AITradingBot\Paper",
        r"\\?\GLOBALROOT\Device\HarddiskVolume1\Paper",
        r"\\server\share\Paper",
        r"G:\AITradingBot\Paper",
        r"F:\AITradingBot\.Paper.provisioning-v2",
        r"F:\AITradingBot\Paper\paper-operations",
        r"F:\AITradingBot\Paper\provisioning-manifest.json",
    ],
)
def test_fixed_path_rejects_aliases_and_other_inventory(path):
    with pytest.raises(ValueError):
        p.require_fixed_paper_provisioning_path(path, UUID(int=1))


def test_c1_paths_still_reject_paper_and_reader_remains_read_only():
    from trading_bot.runtime.windows_authority_security import (
        validate_fixed_parent_chain,
    )

    for path in (p.PRODUCTION_PAPER_ROOT, p.PRODUCTION_PAPER_STAGING_ROOT):
        with pytest.raises(Exception, match="outside the fixed authority"):
            validate_fixed_parent_chain(path)
    for name in (
        "create_directory",
        "create_file",
        "rename_root",
        "publish",
        "repair",
        "delete",
    ):
        assert not hasattr(WindowsPaperAccountReadSession, name)


def test_published_bytes_pass_existing_p3_genesis_only_preflight(native, tmp_path):
    from trading_bot.runtime.manual_paper_account_authority import (
        DisposableManualPaperAccountAuthorityForTest,
    )

    published = publish(native)
    root = tmp_path / "paper"
    capture = tmp_path / "capture"
    capture.mkdir()
    for path, node in native.nodes.items():
        if path.is_relative_to(p.PRODUCTION_PAPER_ROOT):
            target = root.joinpath(*path.relative_to(p.PRODUCTION_PAPER_ROOT).parts)
            if node["directory"]:
                target.mkdir()
            else:
                target.write_bytes(node["data"])
    authority = DisposableManualPaperAccountAuthorityForTest(
        paper_root=root,
        capture_root=capture,
        machine_authority_id=MACHINE,
        approved_trading_sid=SID,
        mutex_factory=lambda _: pytest.fail("no lock needed"),
    )
    preflight = authority.preflight()
    assert preflight.paper_account_id == published.bundle.manifest.paper_account_id
    assert (
        preflight.terminal_checkpoint_id
        == published.bundle.manifest.genesis_checkpoint_id
    )
    assert preflight.terminal_sequence == preflight.finalized_transition_count == 0
    assert preflight.historical_snapshot_dependencies == ()


@pytest.mark.parametrize("target", ["genesis", "anchor"])
def test_staging_semantic_verification_failure_prevents_rename(
    native, monkeypatch, target
):
    # Fail the post-write semantic gate, after pure immutable bundle validation.
    if target == "genesis":
        original = p.verify_genesis_paper_account_checkpoint
        monkeypatch.setattr(
            p, "verify_genesis_paper_account_checkpoint", lambda data: original(b"{}")
        )
    else:

        def reject(data):
            raise ValueError("anchor parse failed")

        monkeypatch.setattr(p, "parse_manual_paper_account_anchor", reject)
    with pytest.raises(p.WindowsPaperAccountProvisioningError):
        publish(native)
    assert p.PRODUCTION_PAPER_ROOT not in native.nodes
    assert p.PRODUCTION_PAPER_STAGING_ROOT in native.nodes
    assert ("rename", "before") not in native.events


@pytest.mark.parametrize(
    "drift",
    [
        "owner",
        "protected",
        "ace-order",
        "ace-mask",
        "ace-flags",
        "extra-ace",
        "reparse",
    ],
)
def test_exact_security_inspection_drifts_block_before_children(
    native, monkeypatch, drift
):
    original = native.inspect

    def inspect(handle, path, kind):
        result = original(handle, path, kind)
        if path != p.PRODUCTION_PAPER_STAGING_ROOT:
            return result
        if drift == "owner":
            return replace(result, owner_sid=SID)
        if drift == "protected":
            return replace(result, dacl_protected=False)
        if drift == "reparse":
            return replace(result, is_reparse_point=True)
        aces = result.aces
        if drift == "ace-order":
            aces = tuple(reversed(aces))
        elif drift == "ace-mask":
            aces = aces[:-1] + (
                replace(aces[-1], access_mask=aces[-1].access_mask | 0x40000),
            )
        elif drift == "ace-flags":
            aces = (replace(aces[0], ace_flags=0x10),) + aces[1:]
        else:
            aces += (aces[0],)
        return replace(result, aces=aces)

    monkeypatch.setattr(p, "inspect_open_authority_object", inspect)
    with pytest.raises(p.WindowsPaperAccountProvisioningError):
        publish(native)
    assert len(native.creations) == 1
    assert not native.handles


@pytest.mark.parametrize("change", ["identity", "security", "inventory", "final"])
def test_late_staging_change_cannot_publish_unvalidated_tree(
    native, monkeypatch, change
):
    original = p._WindowsPublicationSession.revalidate

    def revalidate(session):
        if p.PRODUCTION_PAPER_STAGING_ROOT in native.nodes:
            root = native.nodes[p.PRODUCTION_PAPER_STAGING_ROOT]
            if change == "identity":
                root["identity"] += 1
            elif change == "security":
                root["policy"] = replace(root["policy"], dacl_protected=False)
            elif change == "inventory":
                native.node(
                    p.PRODUCTION_PAPER_STAGING_ROOT / "extra", True, root["policy"]
                )
            else:
                native.node(p.PRODUCTION_PAPER_ROOT, True, root["policy"])
        return original(session)

    monkeypatch.setattr(p._WindowsPublicationSession, "revalidate", revalidate)
    with pytest.raises(p.WindowsPaperAccountProvisioningError):
        publish(native)
    assert p.PRODUCTION_PAPER_STAGING_ROOT in native.nodes
    assert ("rename", "before") not in native.events


def test_absence_probe_error_and_unsafe_parent_cannot_create(native, monkeypatch):
    native.last_error = 5
    with pytest.raises(p.WindowsPaperAccountProvisioningError):
        publish(native)
    assert not native.creations
    native.last_error = 2
    native.nodes[p._PARENT]["policy"] = replace(
        authority_parent_security_policy(), owner_sid=SID
    )
    with pytest.raises(p.WindowsPaperAccountProvisioningError):
        publish(native)
    assert not native.creations


def test_close_failure_after_rename_is_published_candidate(native, monkeypatch):
    original = p.WindowsHandle.close
    used = False

    def close(handle):
        nonlocal used
        original(handle)
        if not used and p.PRODUCTION_PAPER_ROOT in native.nodes:
            used = True
            raise OSError("private close failure")

    monkeypatch.setattr(p.WindowsHandle, "close", close)
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        publish(native)
    assert caught.value.state is p.PaperAccountPublicationState.PUBLISHED_CANDIDATE
    assert p.PRODUCTION_PAPER_ROOT in native.nodes
    assert not native.handles


def test_security_attribute_cleanup_failure_closes_created_file(native, monkeypatch):
    original = p.build_security_attributes
    calls = 0

    @contextmanager
    def attributes(policy):
        nonlocal calls
        calls += 1
        with original(policy) as result:
            yield result
        if calls == 3:
            raise OSError("descriptor cleanup failed")

    monkeypatch.setattr(p, "build_security_attributes", attributes)
    with pytest.raises(p.WindowsPaperAccountProvisioningError):
        publish(native)
    assert p.PRODUCTION_PAPER_STAGING_ROOT in native.nodes
    assert p.PRODUCTION_PAPER_ROOT not in native.nodes
    assert not native.handles


def test_production_entry_requires_admin_sealed_runtime_and_exact_signed_binding(
    native, monkeypatch
):
    bundle = make_bundle()
    expected = verify_manual_paper_account_provisioning_bundle(bundle)
    events = []
    monkeypatch.setattr(
        p, "require_administrator_token", lambda: events.append("admin")
    )
    monkeypatch.setattr(p.sys, "executable", r"F:\AITradingBot\runtime\python.exe")
    monkeypatch.setattr(
        p,
        "__file__",
        r"F:\AITradingBot\runtime\Lib\site-packages\trading_bot\runtime\windows_paper_account_provisioning.py",
    )
    validation = SimpleNamespace(
        bootstrap_verification=SimpleNamespace(
            bootstrap=SimpleNamespace(
                machine_authority_id=MACHINE, approved_account_sid=SID
            )
        )
    )
    monkeypatch.setattr(
        p,
        "validate_installed_authority_complete",
        lambda: events.append("installed") or validation,
    )
    monkeypatch.setattr(
        p,
        "require_initialized_supported_authority_evidence",
        lambda v: events.append("complete"),
    )
    result = p.publish_manual_paper_account(bundle=bundle, expected=expected)
    assert result.state is p.PaperAccountPublicationState.PUBLISHED_VALIDATED
    assert events == ["admin", "installed", "complete"]
    assert not hasattr(result, "bootstrap")


@pytest.mark.parametrize(
    "mode", ["admin", "runtime", "source", "installed", "incomplete", "machine", "sid"]
)
def test_production_precondition_failures_have_zero_creation(native, monkeypatch, mode):
    def fail():
        raise RuntimeError("private failure")

    monkeypatch.setattr(
        p, "require_administrator_token", fail if mode == "admin" else lambda: None
    )
    monkeypatch.setattr(
        p.sys,
        "executable",
        "elsewhere" if mode == "runtime" else r"F:\AITradingBot\runtime\python.exe",
    )
    monkeypatch.setattr(
        p,
        "__file__",
        "elsewhere"
        if mode == "source"
        else (
            r"F:\AITradingBot\runtime\Lib\site-packages\trading_bot\runtime"
            r"\windows_paper_account_provisioning.py"
        ),
    )
    validation = SimpleNamespace(
        bootstrap_verification=SimpleNamespace(
            bootstrap=SimpleNamespace(
                machine_authority_id="bad" if mode == "machine" else MACHINE,
                approved_account_sid="bad" if mode == "sid" else SID,
            )
        )
    )
    monkeypatch.setattr(
        p,
        "validate_installed_authority_complete",
        fail if mode == "installed" else lambda: validation,
    )
    monkeypatch.setattr(
        p,
        "require_initialized_supported_authority_evidence",
        lambda v: fail() if mode == "incomplete" else None,
    )
    bundle = make_bundle()
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        p.publish_manual_paper_account(
            bundle=bundle,
            expected=verify_manual_paper_account_provisioning_bundle(bundle),
        )
    assert caught.value.state == p.PaperAccountPublicationState.NOT_PUBLISHED
    assert not native.creations and not native.opens
