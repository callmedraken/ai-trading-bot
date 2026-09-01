"""Architecture-95 fake-native gates; never open a production path."""

import ctypes
import inspect
import socket
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import PureWindowsPath
from types import SimpleNamespace

import pytest
from tests.runtime.test_manual_paper_account_provisioning import make_bundle
from tests.runtime.test_windows_paper_account_provisioning import (
    native as native_fixture,
)
from tests.runtime.test_windows_paper_account_provisioning import (
    publish,
)

import trading_bot.runtime.windows_p3_r1_recovery_authorization as a
import trading_bot.runtime.windows_paper_account_provisioning as p
from trading_bot.runtime.manual_paper_account_authority import (
    ManualPaperAccountAnchor,
    serialize_manual_paper_account_anchor,
)
from trading_bot.runtime.manual_paper_account_provisioning import (
    ManualPaperAccountProvisioningBundle,
    serialize_manual_paper_account_provisioning_manifest,
    verify_manual_paper_account_provisioning_bundle,
)
from trading_bot.runtime.paper_account_checkpoint import (
    PaperAccountGenesisRequest,
    create_genesis_paper_account_checkpoint,
    serialize_paper_account_checkpoint,
)

native = native_fixture


@pytest.fixture
def frozen_bundle():
    # In-memory test vector only. No production freeze files are read or written.
    genesis = serialize_paper_account_checkpoint(
        create_genesis_paper_account_checkpoint(
            PaperAccountGenesisRequest(
                as_of=datetime.fromisoformat("2026-08-29T09:46:43.769105+00:00"),
                cash=Decimal("100000"),
                positions=(),
                realized_profit_loss=Decimal("0"),
                metadata=(),
                open_orders=(),
            )
        )
    )
    manifest = p._P3_R1_BUNDLE.manifest
    anchor = serialize_manual_paper_account_anchor(
        ManualPaperAccountAnchor(
            manifest.paper_account_id,
            manifest.machine_authority_id,
            manifest.approved_trading_sid,
            manifest.genesis_checkpoint_id,
            manifest.genesis_sha256,
            manifest.genesis_byte_length,
        )
    )
    result = ManualPaperAccountProvisioningBundle(
        genesis, anchor, serialize_manual_paper_account_provisioning_manifest(manifest)
    )
    assert verify_manual_paper_account_provisioning_bundle(result) == p._P3_R1_BUNDLE
    return result


@pytest.fixture
def recovery(native, monkeypatch, frozen_bundle):
    manifest = p._P3_R1_BUNDLE.manifest
    layout = p._layout(p.PRODUCTION_PAPER_STAGING_ROOT, manifest.genesis_checkpoint_id)
    for path, role in layout.items():
        node = native.node(
            path,
            role in {"root", "genesis-directory"},
            p.paper_account_security_policy(role, manifest.approved_trading_sid),
        )
        if role == "genesis-file":
            node["data"] = frozen_bundle.genesis_bytes
        elif role == "anchor":
            node["data"] = frozen_bundle.anchor_bytes
    # Fake exact database bytes; the production constant is independently pinned
    # below. This substitute exists only inside the in-memory Win32 model.
    database = b"fake unchanged database"
    monkeypatch.setattr(
        p, "_P3_R1_DATABASE", (sha256(database).hexdigest(), len(database))
    )
    for path, role, directory in (
        (p.PRODUCTION_AUTHORITY_PATHS.root, "authority", True),
        (p.PRODUCTION_AUTHORITY_PATHS.database, "database", False),
    ):
        node = native.node(
            path,
            directory,
            p.authority_security_policy(role, manifest.approved_trading_sid),
        )
        if not directory:
            node["data"] = database
    authorization = a.P3R1RecoveryAuthorization(
        schema=a.RECOVERY_AUTHORIZATION_SCHEMA,
        signing_key_id=a.RECOVERY_SIGNING_KEY_ID,
        machine_authority_id=manifest.machine_authority_id,
        approved_trading_sid=manifest.approved_trading_sid,
        administrator_operator_sid="S-1-5-21-1-2-3-1001",
        paper_account_id=str(manifest.paper_account_id),
        genesis_checkpoint_id=str(manifest.genesis_checkpoint_id),
        bootstrap_sha256=p._P3_R1_BOOTSTRAP,
        authority_database_sha256=a._AUTHORITY_DATABASE_SHA256,
        authority_database_bytes=a._AUTHORITY_DATABASE_BYTES,
        source_commit="1" * 40,
        source_tree="2" * 40,
        wheel_sha256="3" * 64,
        wheel_bytes=1000,
        installed_record_sha256="4" * 64,
        installed_record_bytes=100,
        staging_root=str(p.PRODUCTION_PAPER_STAGING_ROOT),
        final_root=str(p.PRODUCTION_PAPER_ROOT),
    )
    permit = a.issue_disposable_p3_r1_recovery_permit_for_test(authorization)

    def check(phase):
        native.event(phase, "before")
        native.event(phase, "after")

    def authorize(authorization_bytes, signature):
        assert authorization_bytes == authorization.canonical_bytes()
        assert signature == b"test-signature"
        check("authorization")
        return permit

    monkeypatch.setattr(p, "authorize_p3_r1_recovery", authorize)
    monkeypatch.setattr(
        p,
        "consume_p3_r1_recovery_permit",
        a.consume_disposable_p3_r1_recovery_permit_for_test,
    )
    monkeypatch.setattr(
        p._WindowsPublicationSession,
        "require_quiescent_runtime",
        lambda _: check("quiescent"),
    )

    def run():
        return p.recover_p3_r1_retained_staging(
            bundle=frozen_bundle,
            authorization_bytes=authorization.canonical_bytes(),
            signature=b"test-signature",
        )

    return SimpleNamespace(
        run=run,
        authorization=authorization,
        bundle=frozen_bundle,
        layout=layout,
    )


def snapshot(native):
    return {str(path): dict(node) for path, node in native.nodes.items()}


def test_recovery_exact_state_and_ordering(native, recovery, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unexpected effect")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(p._WindowsPublicationSession, "create_file", forbidden)
    monkeypatch.setattr(p._WindowsPublicationSession, "create_directory", forbidden)
    # Unknown native calls (including credential, broker or transition effects)
    # fail through FakeWin32.__getattr__; only the root rename may mutate nodes.
    before = snapshot(native)
    result = recovery.run()
    assert (
        result.publication.state is p.PaperAccountPublicationState.PUBLISHED_VALIDATED
    )
    assert result.publication.bundle == p._P3_R1_BUNDLE
    assert result.first_production_mutation == "P3_R1_ROOT_RENAME"
    assert not native.handles and not native.creations
    assert p.PRODUCTION_PAPER_STAGING_ROOT not in native.nodes
    assert len(result.native_identities) == 4
    rename = native.events.index(("rename", "before"))
    proof = native.events.index(("final-path", "before"))
    assert native.events[rename + 1] == ("rename", "after")
    assert proof == rename + 2
    assert native.events.count(("rename", "before")) == 1
    for path, role in recovery.layout.items():
        final = p.PRODUCTION_PAPER_ROOT / path.relative_to(
            p.PRODUCTION_PAPER_STAGING_ROOT
        )
        prior = before[str(path)]
        after = native.nodes[final]
        assert {k: v for k, v in prior.items() if k != "path"} == {
            k: v for k, v in after.items() if k != "path"
        }
        if role != "root":
            assert native.events.index(("close:" + role + ":staging", "after")) < rename
            assert native.events.index(("inspect:" + role + ":final", "before")) > proof
    assert all(
        path == p.PRODUCTION_PAPER_STAGING_ROOT
        or not path.is_relative_to(p.PRODUCTION_PAPER_STAGING_ROOT)
        for path in native.rename_handle_paths[0]
    )
    for path, access, share, disposition, _ in native.opens:
        assert disposition == p.OPEN_EXISTING
        assert not access & p.FILE_WRITE_DATA
        if path == p.PRODUCTION_PAPER_STAGING_ROOT:
            assert access & p.DELETE and not share & p.FILE_SHARE_DELETE
        elif path.is_relative_to(p.PRODUCTION_PAPER_ROOT):
            assert not access & p.DELETE
    assert (
        before[str(p.PRODUCTION_AUTHORITY_PATHS.database)]
        == native.nodes[p.PRODUCTION_AUTHORITY_PATHS.database]
    )


@pytest.mark.parametrize(
    "final,staging,state",
    [
        (False, False, p.PaperAccountPublicationState.NOT_PUBLISHED),
        (True, False, p.PaperAccountPublicationState.EXISTING_FINAL),
        (True, True, p.PaperAccountPublicationState.EXISTING_FINAL_AND_STAGING),
    ],
)
def test_recovery_requires_exact_namespace(native, recovery, final, staging, state):
    if not staging:
        for path in recovery.layout:
            del native.nodes[path]
    if final:
        native.node(p.PRODUCTION_PAPER_ROOT, True, p.authority_parent_security_policy())
    before = snapshot(native)
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        recovery.run()
    assert caught.value.state is state
    assert snapshot(native) == before and not native.creations and not native.handles
    assert ("rename", "before") not in native.events


@pytest.mark.parametrize(
    "role", ["root", "genesis-directory", "genesis-file", "anchor"]
)
@pytest.mark.parametrize(
    "drift",
    [
        "owner",
        "protected",
        "ace-order",
        "ace-mask",
        "ace-flags",
        "reparse",
        "type",
        "identity",
        "volume",
        "delete-pending",
        "alias",
    ],
)
def test_recovery_rejects_unsafe_or_changing_objects(
    native, recovery, monkeypatch, role, drift
):
    path = next(
        path for path, item_role in recovery.layout.items() if item_role == role
    )
    original = native.inspect

    def inspect_object(handle, expected_path, kind):
        result = original(handle, expected_path, kind)
        if expected_path != path:
            return result
        node = native.handles[handle]
        if drift in {"identity", "volume"}:
            node[drift] += 1
        elif drift == "delete-pending":
            node["delete_pending"] = True
        elif drift == "type":
            node["directory"] = not node["directory"]
        elif drift == "alias":
            raise ValueError("native final path is an alias")
        elif drift == "owner":
            result = replace(
                result, owner_sid=p._P3_R1_BUNDLE.manifest.approved_trading_sid
            )
        elif drift == "protected":
            result = replace(result, dacl_protected=False)
        elif drift == "reparse":
            result = replace(result, is_reparse_point=True)
        else:
            aces = result.aces
            if drift == "ace-order":
                aces = tuple(reversed(aces))
            elif drift == "ace-mask":
                aces = (replace(aces[0], access_mask=1),) + aces[1:]
            else:
                aces = (replace(aces[0], ace_flags=0x10),) + aces[1:]
            result = replace(result, aces=aces)
        return result

    monkeypatch.setattr(p, "inspect_open_authority_object", inspect_object)
    with pytest.raises(p.WindowsPaperAccountProvisioningError):
        recovery.run()
    assert ("rename", "before") not in native.events
    assert p.PRODUCTION_PAPER_ROOT not in native.nodes and not native.handles


@pytest.mark.parametrize(
    "drift",
    [
        "genesis",
        "anchor",
        "extra",
        "missing",
        "casefold",
        "overflow",
        "hardlink",
        "database",
    ],
)
def test_recovery_rejects_retained_bytes_and_inventory(native, recovery, drift):
    paths = {role: path for path, role in recovery.layout.items()}
    if drift in {"genesis", "anchor", "database"}:
        path = (
            p.PRODUCTION_AUTHORITY_PATHS.database
            if drift == "database"
            else paths["genesis-file" if drift == "genesis" else "anchor"]
        )
        native.nodes[path]["data"] = b"x" + native.nodes[path]["data"][1:]
    elif drift == "missing":
        del native.nodes[paths["genesis-file"]]
    elif drift == "hardlink":
        native.nodes[paths["genesis-file"]]["links"] = 2
    elif drift == "casefold":
        original = native.nodes.pop(paths["anchor"])
        path = paths["anchor"].with_name(paths["anchor"].name.upper())
        original["path"] = path
        native.nodes[path] = original
    else:
        for number in range(5 if drift == "overflow" else 1):
            native.node(
                p.PRODUCTION_PAPER_STAGING_ROOT / f"unexpected-{number}",
                True,
                p.authority_parent_security_policy(),
            )
    before = snapshot(native)
    with pytest.raises(p.WindowsPaperAccountProvisioningError):
        recovery.run()
    assert snapshot(native) == before and not native.handles
    assert ("rename", "before") not in native.events


@pytest.mark.parametrize("mode", ["ordinary", "recovery"])
@pytest.mark.parametrize("role", ["genesis-directory", "genesis-file", "anchor"])
@pytest.mark.parametrize("when", ["before", "after"])
def test_descendant_close_failure_blocks_without_retry(
    native, recovery, mode, role, when
):
    if mode == "ordinary":
        for path in recovery.layout:
            del native.nodes[path]
    native.fault = (f"close:{role}:staging", when)
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        recovery.run() if mode == "recovery" else publish(native)
    assert (
        caught.value.state
        is p.PaperAccountPublicationState.STAGING_REQUIRES_MANUAL_RECOVERY
    )
    assert ("rename", "before") not in native.events
    assert native.events.count((f"close:{role}:staging", "before")) == 1
    assert p.PRODUCTION_PAPER_ROOT not in native.nodes
    assert p.PRODUCTION_PAPER_STAGING_ROOT in native.nodes
    # A failed native close is ambiguous. Do not retry it (or publish).
    assert len(native.handles) == (1 if when == "before" else 0)


@pytest.mark.parametrize("mode", ["ordinary", "recovery"])
@pytest.mark.parametrize(
    "role", ["root", "genesis-directory", "genesis-file", "anchor"]
)
@pytest.mark.parametrize("field", ["identity", "volume"])
def test_exact_pre_post_identity_continuity(
    native, recovery, monkeypatch, mode, role, field
):
    if mode == "ordinary":
        for path in recovery.layout:
            del native.nodes[path]
    original = native.api_SetFileInformationByHandle

    def rename(*args):
        result = original(*args)
        for node in native.nodes.values():
            if native.label(node) == role + ":final":
                node[field] += 1
        return result

    monkeypatch.setattr(native, "api_SetFileInformationByHandle", rename)
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        recovery.run() if mode == "recovery" else publish(native)
    assert caught.value.state is p.PaperAccountPublicationState.PUBLISHED_CANDIDATE
    assert native.events.count(("rename", "before")) == 1
    assert p.PRODUCTION_PAPER_ROOT in native.nodes and not native.handles


@pytest.mark.parametrize(
    "mode,accepted",
    [
        ("exact", True),
        ("outside-count-garbage", True),
        ("included-trailing-character", False),
        ("included-trailing-characters", False),
        ("short", False),
        ("wrong-same-length", False),
        ("zero", False),
        ("required-buffer-size", False),
        ("oversized", False),
    ],
)
def test_retained_root_uses_exact_counted_native_final_path(
    native, recovery, monkeypatch, mode, accepted
):
    expected = "\\\\?\\" + str(p.PRODUCTION_PAPER_ROOT)

    def final_path(handle, buffer, size, flags):
        assert handle in native.handles and flags == 0
        observed = expected
        count = len(expected)
        if mode == "outside-count-garbage":
            observed += "nondeterministic-garbage"
        elif mode == "included-trailing-character":
            observed += "X"
            count += 1
        elif mode == "included-trailing-characters":
            observed += "sis"
            count += 3
        elif mode == "short":
            count -= 1
        elif mode == "wrong-same-length":
            observed = expected[:-1] + "X"
        elif mode == "zero":
            return 0
        elif mode == "required-buffer-size":
            return size
        elif mode == "oversized":
            return size + 1
        encoded = observed.encode("utf-16-le")
        ctypes.memmove(ctypes.addressof(buffer), encoded, len(encoded))
        return count

    monkeypatch.setattr(native, "api_GetFinalPathNameByHandleW", final_path)
    if accepted:
        result = recovery.run()
        assert (
            result.publication.state
            is p.PaperAccountPublicationState.PUBLISHED_VALIDATED
        )
    else:
        with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
            recovery.run()
        assert caught.value.state is p.PaperAccountPublicationState.PUBLISHED_CANDIDATE
        assert not any(
            path.is_relative_to(p.PRODUCTION_PAPER_ROOT) for path, *_ in native.opens
        )
    assert not native.handles


def test_rename_info_is_fixed_no_replace_and_explicitly_terminated(
    native, recovery, monkeypatch
):
    original = p._WindowsPublicationSession._call
    observed = []
    writable_pointer_declarations = []

    def call(session, name, result, types, *args):
        if name == "SetFileInformationByHandle":
            handle, info_class, buffer, size = args
            info = p._PaperRootRenameInfo.from_buffer(buffer)
            name_offset = p._PaperRootRenameInfo.name.offset
            destination = ctypes.string_at(
                ctypes.addressof(buffer) + name_offset, info.name_length
            )
            terminator = ctypes.string_at(
                ctypes.addressof(buffer) + name_offset + info.name_length,
                len("\0".encode("utf-16-le")),
            )
            observed.append(
                (
                    handle,
                    info_class,
                    info.flags,
                    info.root_directory,
                    info.name_length,
                    destination,
                    terminator,
                    size,
                )
            )
        elif name == "GetFinalPathNameByHandleW":
            writable_pointer_declarations.append(types[1])
        return original(session, name, result, types, *args)

    monkeypatch.setattr(p._WindowsPublicationSession, "_call", call)
    recovery.run()
    assert len(observed) == 1
    (
        handle,
        info_class,
        flags,
        root_directory,
        name_length,
        destination,
        terminator,
        size,
    ) = observed[0]
    expected_destination = str(p.PRODUCTION_PAPER_ROOT).encode("utf-16-le")
    assert handle and info_class == 3
    assert flags == 0 and not root_directory
    assert name_length == len(expected_destination)
    assert destination == expected_destination
    assert terminator == b"\0\0"
    assert size >= p._PaperRootRenameInfo.name.offset + name_length + len(terminator)
    assert writable_pointer_declarations == [
        ctypes.POINTER(p.wintypes.WCHAR),
        ctypes.POINTER(p.wintypes.WCHAR),
    ]


@pytest.mark.parametrize(
    "phase",
    [
        "authorization",
        "quiescent",
        "inspect:root:staging",
        "inspect:genesis-directory:staging",
        "read:genesis-file:staging",
        "read:anchor:staging",
        "inventory:root:staging",
        "inventory:genesis-directory:staging",
        "rename",
        "final-path",
        "inspect:root:final",
        "inspect:genesis-directory:final",
        "read:genesis-file:final",
        "read:anchor:final",
        "inventory:root:final",
        "inventory:genesis-directory:final",
    ],
)
@pytest.mark.parametrize("when", ["before", "after"])
def test_recovery_crash_states_never_retry_or_cleanup(native, recovery, phase, when):
    native.fault = (phase, when)
    before = snapshot(native)
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        recovery.run()
    assert native.fault_used and not native.creations and not native.handles
    assert "private" not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__
    assert native.events.count(("rename", "before")) <= 1
    if p.PRODUCTION_PAPER_ROOT in native.nodes:
        assert caught.value.state in {
            p.PaperAccountPublicationState.PUBLISHED_CANDIDATE,
            p.PaperAccountPublicationState.PUBLICATION_OUTCOME_UNCERTAIN,
        }
    else:
        assert snapshot(native) == before
    assert (p.PRODUCTION_PAPER_ROOT in native.nodes) != (
        p.PRODUCTION_PAPER_STAGING_ROOT in native.nodes
    )


@pytest.mark.parametrize("mode", ["ordinary", "recovery"])
def test_late_final_appearance_blocks_before_native_rename(
    native, recovery, monkeypatch, mode
):
    if mode == "ordinary":
        for path in recovery.layout:
            del native.nodes[path]
    original = p.WindowsHandle.close

    def close(handle):
        if (
            handle.value
            and native.label(native.handles[handle.value])
            == "genesis-directory:staging"
        ):
            native.node(
                p.PRODUCTION_PAPER_ROOT, True, p.authority_parent_security_policy()
            )
        original(handle)

    monkeypatch.setattr(p.WindowsHandle, "close", close)
    with pytest.raises(p.WindowsPaperAccountProvisioningError):
        recovery.run() if mode == "recovery" else publish(native)
    assert ("rename", "before") not in native.events
    assert (
        p.PRODUCTION_PAPER_ROOT in native.nodes
        and p.PRODUCTION_PAPER_STAGING_ROOT in native.nodes
    )


@pytest.mark.parametrize(
    "mode",
    ["rename-false", "rename-error-after", "both", "missing-final", "database-after"],
)
def test_recovery_rename_ambiguity_and_postconditions(
    native, recovery, monkeypatch, mode
):
    original = native.api_SetFileInformationByHandle

    def rename(*args):
        if mode == "rename-false":
            native.event("rename", "before")
            return 0
        result = original(*args)
        if mode == "rename-error-after":
            raise OSError("ambiguous result")
        if mode == "both":
            native.node(
                p.PRODUCTION_PAPER_STAGING_ROOT,
                True,
                p.authority_parent_security_policy(),
            )
        if mode == "missing-final":
            native.nodes.pop(p.PRODUCTION_PAPER_ROOT)
        if mode == "database-after":
            native.nodes[p.PRODUCTION_AUTHORITY_PATHS.database]["data"] = b"changed"
        return result

    monkeypatch.setattr(native, "api_SetFileInformationByHandle", rename)
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        recovery.run()
    assert caught.value.state is (
        p.PaperAccountPublicationState.PUBLICATION_OUTCOME_UNCERTAIN
        if mode in {"rename-false", "rename-error-after"}
        else p.PaperAccountPublicationState.PUBLISHED_CANDIDATE
    )
    assert native.events.count(("rename", "before")) == 1
    assert not native.creations and not native.handles


@pytest.mark.parametrize(
    "mode",
    [
        "alternate-bundle",
        "authorization",
        "quiescence",
    ],
)
def test_recovery_preconditions_block_before_paper_opens(
    native, recovery, monkeypatch, mode
):
    def fail(*args):
        raise ValueError("precondition failed")

    if mode == "alternate-bundle":
        recovery.bundle = make_bundle()
    else:
        owner, name = {
            "authorization": (p, "authorize_p3_r1_recovery"),
            "quiescence": (p._WindowsPublicationSession, "require_quiescent_runtime"),
        }[mode]
        monkeypatch.setattr(owner, name, fail)
    before = snapshot(native)
    with pytest.raises(p.WindowsPaperAccountProvisioningError):
        p.recover_p3_r1_retained_staging(
            bundle=recovery.bundle,
            authorization_bytes=recovery.authorization.canonical_bytes(),
            signature=b"test-signature",
        )
    assert snapshot(native) == before and not native.opens


def test_api_has_no_generic_recovery_options_and_ordinary_never_recovers(
    native, recovery, monkeypatch
):
    assert set(inspect.signature(p.recover_p3_r1_retained_staging).parameters) == {
        "bundle",
        "authorization_bytes",
        "signature",
    }
    monkeypatch.setattr(
        p,
        "recover_p3_r1_retained_staging",
        lambda **kw: pytest.fail("implicit recovery"),
    )
    before = snapshot(native)
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        publish(native, recovery.bundle)
    assert (
        caught.value.state
        is p.PaperAccountPublicationState.STAGING_REQUIRES_MANUAL_RECOVERY
    )
    assert before == snapshot(native)
    assert not native.creations and ("rename", "before") not in native.events


@pytest.mark.parametrize("role", ["genesis-directory", "genesis-file", "anchor"])
@pytest.mark.parametrize("root_delete_share", [False, True])
def test_fake_kernel_rejects_old_retained_descendant_topology(
    native, recovery, role, root_delete_share
):
    with p._WindowsPublicationSession(p._P3_R1_BUNDLE) as session:
        session.validate_parent()
        session.open_staging()
        for path, item_role in recovery.layout.items():
            if item_role not in {"root", role}:
                session.handles.pop(path).handle.close()
        root = session.handles[p.PRODUCTION_PAPER_STAGING_ROOT]
        if root_delete_share:
            root.handle.close()
            root.handle = session._open(
                p.PRODUCTION_PAPER_STAGING_ROOT,
                True,
                access=p.DELETE | p.READ_CONTROL | p.FILE_READ_DATA,
                share=p.FILE_SHARE_READ | p.FILE_SHARE_DELETE,
            )
        name = str(p.PRODUCTION_PAPER_ROOT).encode("utf-16-le")
        terminator_size = len("\0".encode("utf-16-le"))
        terminator_offset = p._PaperRootRenameInfo.name.offset + len(name)
        size = max(
            ctypes.sizeof(p._PaperRootRenameInfo),
            terminator_offset + terminator_size,
        )
        buffer = ctypes.create_string_buffer(size)
        info = p._PaperRootRenameInfo.from_buffer(buffer)
        info.name_length = len(name)
        ctypes.memmove(
            ctypes.addressof(buffer) + p._PaperRootRenameInfo.name.offset,
            name,
            len(name),
        )
        ctypes.memset(ctypes.addressof(buffer) + terminator_offset, 0, terminator_size)
        assert (
            native.api_SetFileInformationByHandle(root.handle.value, 3, buffer, size)
            == 0
        )
        assert native.last_error == 5
        assert p.PRODUCTION_PAPER_ROOT not in native.nodes


def test_database_incident_pin_is_exact():
    assert p._P3_R1_DATABASE == (
        "6a8fb988d1cb223fbb66b09e8dab1e0de4b6aafd148dfdf01df08029203f4b76",
        331776,
    )


@pytest.mark.parametrize(
    "mode",
    [
        "quiescent",
        "production-python",
        "production-pythonw",
        "snapshot-failure",
        "enumeration-failure",
        "open-failure",
        "query-failure",
        "close-failure",
    ],
)
def test_native_quiescence_snapshot_fails_closed(native, monkeypatch, mode):
    queried = []
    closed = []
    records = iter(
        [
            (p.os.getpid(), "python.exe"),
            (1234, "unrelated.exe"),
            (5678, "pythonw.exe" if mode == "production-pythonw" else "python.exe"),
        ]
    )

    class Handle:
        def __init__(self, value):
            self.value = value

        def __enter__(self):
            return self.value

        def __exit__(self, *args):
            closed.append(self.value)
            if mode == "close-failure":
                raise ValueError("native close failure")

    def call(self, name, result, types, *args):
        if name == "CreateToolhelp32Snapshot":
            assert args == (2, 0)
            return -1 if mode == "snapshot-failure" else 111
        if name in {"Process32FirstW", "Process32NextW"}:
            entry = ctypes.cast(args[1], ctypes.POINTER(p._ProcessEntry)).contents
            try:
                entry.pid, entry.executable = next(records)
            except StopIteration:
                native.last_error = 5 if mode == "enumeration-failure" else 18
                return 0
            return 1
        if name == "OpenProcess":
            assert args == (0x1000, False, 5678)
            queried.append(5678)
            return 0 if mode == "open-failure" else 222
        if name == "QueryFullProcessImageNameW":
            if mode == "query-failure":
                return 0
            args[2].value = (
                str(p._RUNTIME / "python.exe")
                if mode.startswith("production-")
                else r"C:\unrelated\python.exe"
            )
            return 1
        pytest.fail("unexpected process operation: " + name)

    monkeypatch.setattr(p, "WindowsHandle", Handle)
    monkeypatch.setattr(p._WindowsPublicationSession, "_call", call)
    session = p._WindowsPublicationSession(p._P3_R1_BUNDLE)
    if mode == "quiescent":
        session.require_quiescent_runtime()
        assert queried == [5678] and closed == [222, 111]
    else:
        with pytest.raises(ValueError):
            session.require_quiescent_runtime()
        if mode != "snapshot-failure":
            assert 111 in closed


@pytest.mark.parametrize(
    "change",
    [
        "database-identity",
        "database-volume",
        "database-security",
        "database-length",
        "database-after-close",
        "parent-identity",
        "parent-security",
        "root-after-close",
    ],
)
def test_late_recovery_pre_mutation_drift(native, recovery, monkeypatch, change):
    original = p._WindowsPublicationSession.prepare_rename

    def prepare(session, bundle):
        original(session, bundle)
        path = (
            p.PRODUCTION_AUTHORITY_PATHS.database
            if change.startswith("database")
            else p._PARENT
            if change.startswith("parent")
            else p.PRODUCTION_PAPER_STAGING_ROOT
        )
        node = native.nodes[path]
        if change.endswith("security"):
            node["policy"] = replace(node["policy"], dacl_protected=False)
        elif change.endswith("volume"):
            node["volume"] += 1
        elif change in {"database-length", "database-after-close"}:
            node["data"] = b"changed"
        else:
            node["identity"] += 1

    monkeypatch.setattr(p._WindowsPublicationSession, "prepare_rename", prepare)
    with pytest.raises(p.WindowsPaperAccountProvisioningError):
        recovery.run()
    assert ("rename", "before") not in native.events
    assert not native.handles


@pytest.mark.parametrize("stage", ["before", "after"])
def test_mutation_marker_is_at_native_rename_only(native, recovery, monkeypatch, stage):
    original = p._WindowsPublicationSession._call
    seen = []

    def call(session, name, result, types, *args):
        if name == "SetFileInformationByHandle":
            seen.append(session.rename_attempted)
            assert session.rename_attempted
            if stage == "before":
                raise OSError("native call outcome unavailable")
        result = original(session, name, result, types, *args)
        if name == "SetFileInformationByHandle" and stage == "after":
            raise OSError("rename completed, result lost")
        return result

    monkeypatch.setattr(p._WindowsPublicationSession, "_call", call)
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        recovery.run()
    assert seen == [True]
    assert (
        caught.value.state
        is p.PaperAccountPublicationState.PUBLICATION_OUTCOME_UNCERTAIN
    )
    assert (p.PRODUCTION_PAPER_ROOT in native.nodes) == (stage == "after")


@pytest.mark.parametrize(
    "corruption",
    [
        "genesis-file:final",
        "anchor:final",
        "security:root:final",
        "security:genesis-directory:final",
        "security:genesis-file:final",
        "security:anchor:final",
        "inventory:root:final",
        "inventory:genesis-directory:final",
    ],
)
def test_recovery_complete_final_validation_failure_preserves_candidate(
    native, recovery, corruption
):
    native.corruption = corruption
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        recovery.run()
    assert caught.value.state is p.PaperAccountPublicationState.PUBLISHED_CANDIDATE
    assert p.PRODUCTION_PAPER_ROOT in native.nodes
    assert p.PRODUCTION_PAPER_STAGING_ROOT not in native.nodes
    assert not native.handles and not native.creations
    assert native.events.count(("rename", "before")) == 1


def test_second_quiescence_failure_does_not_cross_mutation_boundary(
    native, recovery, monkeypatch
):
    checks = 0

    def quiescent(session):
        nonlocal checks
        checks += 1
        if checks == 2:
            assert not session.rename_attempted
            assert set(session.handles) == {
                PureWindowsPath("F:/"),
                p._PARENT,
                p.PRODUCTION_PAPER_STAGING_ROOT,
            }
            raise ValueError("runtime appeared")

    monkeypatch.setattr(
        p._WindowsPublicationSession, "require_quiescent_runtime", quiescent
    )
    before = snapshot(native)
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        recovery.run()
    assert (
        caught.value.state
        is p.PaperAccountPublicationState.STAGING_REQUIRES_MANUAL_RECOVERY
    )
    assert before == snapshot(native) and not native.handles
    assert ("rename", "before") not in native.events


@pytest.mark.parametrize("role", ["genesis-directory", "genesis-file", "anchor"])
def test_final_descendant_open_failure_retains_candidate(
    native, recovery, monkeypatch, role
):
    original = native.api_CreateFileW

    def open_file(path, *args):
        path = PureWindowsPath(path)
        if path in native.nodes and native.label(native.nodes[path]) == role + ":final":
            return -1
        return original(str(path), *args)

    monkeypatch.setattr(native, "api_CreateFileW", open_file)
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        recovery.run()
    assert caught.value.state is p.PaperAccountPublicationState.PUBLISHED_CANDIDATE
    assert native.events.count(("rename", "before")) == 1
    assert not native.handles and not native.creations


@pytest.mark.parametrize("role", ["root:final", "database"])
def test_final_close_failure_never_reports_recovered_success(native, recovery, role):
    native.fault = ("close:" + role, "after")
    with pytest.raises(p.WindowsPaperAccountProvisioningError) as caught:
        recovery.run()
    assert caught.value.state is p.PaperAccountPublicationState.PUBLISHED_CANDIDATE
    assert native.events.count(("close:" + role, "before")) == 1
    assert native.events.count(("rename", "before")) == 1
    assert not native.handles and not native.creations
