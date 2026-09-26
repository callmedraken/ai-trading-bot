"""A124-4 pure acceptance tests; no production path is opened."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from trading_bot.runtime import personal_desktop_d10_python_substrate as q


def _node(path: str, kind: q.Kind, children: tuple[str, ...] = ()) -> q.ObjectEvidence:
    read = q.DIRECTORY_READ if kind is q.Kind.DIRECTORY else q.FILE_READ_EXECUTE
    return q.ObjectEvidence(
        path,
        path,
        kind,
        q.ADMIN,
        True,
        (
            q.Ace(q.ADMIN, q.ALL_ACCESS),
            q.Ace(q.SYSTEM, q.ALL_ACCESS),
        )
        if path == q.ROOT
        else (
            q.Ace(q.ADMIN, q.ALL_ACCESS),
            q.Ace(q.SYSTEM, q.ALL_ACCESS),
            q.Ace(q.TRADING, read),
        ),
        False,
        3,
        q.VOLUME,
        "NTFS",
        42,
        len(path),
        1,
        children,
    )


def evidence() -> q.QualificationEvidence:
    objects = (
        _node(q.VOLUME, q.Kind.DIRECTORY, ("AITradingBot",)),
        _node(q.ROOT, q.Kind.DIRECTORY, ("runtime",)),
        _node(q.RUNTIME, q.Kind.DIRECTORY, ("python.exe", "Lib")),
        _node(q.PYTHON, q.Kind.FILE),
        _node(q.LIB, q.Kind.DIRECTORY, ("site-packages",)),
        _node(q.SITE_PACKAGES, q.Kind.DIRECTORY),
    )
    imports = q.ImportEvidence(
        q.PYTHON,
        q.RUNTIME,
        q.RUNTIME,
        q.VERSION,
        q.FLAGS,
        True,
        True,
        True,
        q.ROOT + r"\D10\no-pycache",
        (q.ZIP, q.DLLS, q.LIB),
        (q.PYTHON,),
        (r"C:\Windows\System32\kernel32.dll",),
        q.SITE_PACKAGES,
        q.SITE_PACKAGES,
        False,
        False,
    )
    return q.QualificationEvidence(
        objects,
        imports,
        q.CONFIG_NAMES,
        (q.ZIP, q.DLLS),
        q.PYTHON,
        q.VERSION,
        q.TRADING,
        True,
        False,
        (q.TRADING,),
        ("SeChangeNotifyPrivilege",),
        True,
        True,
        tuple(
            q.TradingAccessEvidence(
                item.path, q.MUTATION_MASK, 0, True, q.access_policy_for_path(item.path)
            )
            for item in objects
        ),
        True,
        True,
        True,
    )


def _change_node(
    ev: q.QualificationEvidence, path: str, **changes: object
) -> q.QualificationEvidence:
    return replace(
        ev,
        objects=tuple(
            replace(item, **changes) if item.path == path else item
            for item in ev.objects
        ),
    )


def _add_runtime_file(
    ev: q.QualificationEvidence, path: str, *, loaded_final: str | None = None
) -> q.QualificationEvidence:
    runtime = next(item for item in ev.objects if item.path == q.RUNTIME)
    updated = _change_node(
        ev,
        q.RUNTIME,
        children=(*runtime.children, path.rsplit("\\", 1)[-1]),
    )
    item = _node(path, q.Kind.FILE)
    access = q.TradingAccessEvidence(
        path, q.MUTATION_MASK, 0, True, q.AccessPolicy.PROTECTED_OBJECT
    )
    runtime_files = {*ev.imports.loaded_runtime_files}
    runtime_files.add(loaded_final or path)
    return replace(
        updated,
        objects=(*updated.objects, item),
        imports=replace(
            updated.imports, loaded_runtime_files=tuple(sorted(runtime_files))
        ),
        trading_access=(*updated.trading_access, access),
    )


def test_fixed_paths_and_sanitized_result() -> None:
    result = q.qualify_python_substrate(evidence())
    assert result == q.QualificationResult(
        q.PYTHON,
        q.VERSION,
        q.RUNTIME,
        q.SITE_PACKAGES,
        (q.ZIP, q.DLLS, q.LIB),
        6,
    )
    assert not hasattr(result, "handle")
    assert not hasattr(result, "authority")


def test_dynamic_runtime_final_maps_to_one_protected_file_case_insensitively() -> None:
    inventory_path = q.RUNTIME + r"\VCRUNTIME140.dll"
    native_final = q.RUNTIME + r"\vcruntime140.dll"
    ev = _add_runtime_file(evidence(), inventory_path, loaded_final=native_final)

    result = q.qualify_python_substrate(ev)
    assert result.protected_object_count == 7


def test_case_colliding_runtime_inventory_remains_blocked() -> None:
    ev = _add_runtime_file(evidence(), q.RUNTIME + r"\VCRUNTIME140.dll")
    ev = _add_runtime_file(ev, q.RUNTIME + r"\vcruntime140.dll")

    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(ev)


@pytest.mark.parametrize(
    ("path", "changes"),
    [
        (q.PYTHON, {"final_path": r"F:\Other\python.exe"}),
        (q.PYTHON, {"final_path": r"\\server\share\python.exe"}),
        (q.PYTHON, {"final_path": r"\\?\F:\AITradingBot\runtime\python.exe"}),
        (q.PYTHON, {"owner_sid": q.TRADING}),
        (q.PYTHON, {"dacl_protected": False}),
        (q.PYTHON, {"reparse": True}),
        (q.PYTHON, {"links": 2}),
        (q.ROOT, {"owner_sid": q.TRADING}),
        (q.RUNTIME, {"children": ("python.exe",)}),
        (q.RUNTIME, {"aces": (q.Ace(q.TRADING, q.ALL_ACCESS),)}),
        (q.SITE_PACKAGES, {"owner_sid": q.TRADING}),
    ],
)
def test_object_and_writable_parent_fail_closed(
    path: str, changes: dict[str, object]
) -> None:
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(_change_node(evidence(), path, **changes))


@pytest.mark.parametrize(
    "mask",
    [
        0x00000002,
        0x00000004,
        0x00000010,
        0x00000040,
        0x00010000,
        0x00040000,
        0x00080000,
        0x001F01FF,
    ],
)
def test_trading_mutation_ace_fails_closed(mask: int) -> None:
    item = next(item for item in evidence().objects if item.path == q.RUNTIME)
    aces = item.aces[:-1] + (q.Ace(q.TRADING, mask),)
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(_change_node(evidence(), q.RUNTIME, aces=aces))


def test_root_parent_requires_two_exact_aces_and_admin_owner() -> None:
    ev = evidence()
    parent = next(item for item in ev.objects if item.path == q.ROOT)
    assert len(parent.aces) == 2
    q.qualify_python_substrate(ev)
    for aces in (
        (*parent.aces, q.Ace(q.TRADING, q.DIRECTORY_READ)),
        parent.aces[:1],
        parent.aces[1:],
    ):
        with pytest.raises(q.SubstrateBlocked, match="protected deployment parent"):
            q.qualify_python_substrate(_change_node(ev, q.ROOT, aces=aces))
    with pytest.raises(q.SubstrateBlocked, match="protected deployment parent"):
        q.qualify_python_substrate(_change_node(ev, q.ROOT, owner_sid=q.SYSTEM))


def test_missing_bypass_traverse_privilege_blocks_pure_qualification() -> None:
    with pytest.raises(q.SubstrateBlocked, match="bypass-traverse"):
        q.qualify_python_substrate(replace(evidence(), trading_enabled_privileges=()))


def test_missing_trading_effective_denial_fails_closed() -> None:
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(
            replace(
                evidence(),
                trading_access=(
                    q.TradingAccessEvidence(
                        q.PYTHON,
                        q.MUTATION_MASK,
                        0,
                        True,
                        q.AccessPolicy.PROTECTED_OBJECT,
                    ),
                ),
            )
        )


@pytest.mark.parametrize(
    "change",
    [
        {"signed_a123_python": r"F:\Other\python.exe"},
        {"signed_a123_version": "3.14.4"},
        {"native_no_follow": False},
        {"native_pinned_and_rechecked": False},
        {"trading_token_non_admin": False},
        {"absent_configuration": ()},
        {"absent_search_roots": ()},
    ],
)
def test_unproven_startup_or_identity_fails_closed(change: dict[str, object]) -> None:
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(replace(evidence(), **change))


@pytest.mark.parametrize(
    "change",
    [
        {"sys_path": (q.LIB, q.SITE_PACKAGES)},
        {"sys_path": (q.LIB, r"F:\Other")},
        {"sys_path": (q.LIB, r"\\server\share")},
        {"sys_path": (q.LIB, r"\\?\F:\AITradingBot\runtime\Lib")},
        {"flags": ("-I", "-B")},
        {"isolated": False},
        {"no_site": False},
        {"dont_write_bytecode": False},
        {"site_main_called": True},
        {"pth_processed": True},
        {"loaded_runtime_files": (r"F:\Other\evil.pyd",)},
        {"loaded_system_dlls": (r"C:\Other\evil.dll",)},
    ],
)
def test_unreviewed_import_or_startup_behavior_fails_closed(
    change: dict[str, object],
) -> None:
    ev = evidence()
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(replace(ev, imports=replace(ev.imports, **change)))


def test_unexpected_pth_or_venv_configuration_fails_closed() -> None:
    ev = evidence()
    extra = _node(q.RUNTIME + r"\python3.14._pth", q.Kind.FILE)
    modified = _change_node(
        ev, q.RUNTIME, children=("python.exe", "Lib", "python3.14._pth")
    )
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(
            replace(modified, objects=modified.objects + (extra,))
        )


def test_accepted_source_does_not_provision_or_change_arch77() -> None:
    source = Path(q.__file__).read_text(encoding="utf-8")
    forbidden = (
        "CreateFileW",
        "SetSecurityInfo",
        "subprocess.run",
        "TaskScheduler",
        "site.main(",
        "trading_bot.runtime.windows_authority",
    )
    assert all(item not in source for item in forbidden)
    assert q.ROOT == r"F:\AITradingBot"
    assert q.RUNTIME == r"F:\AITradingBot\runtime"
    assert q.PYTHON == r"F:\AITradingBot\runtime\python.exe"
    assert q.SITE_PACKAGES == r"F:\AITradingBot\runtime\Lib\site-packages"


def test_a123_interpreter_contract_is_the_same() -> None:
    from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
        D10_PRODUCTION_PYTHON,
    )

    assert q.PYTHON == D10_PRODUCTION_PYTHON


def test_reviewed_system_dll_location_is_fixed() -> None:
    ev = evidence()
    imports = replace(
        ev.imports,
        loaded_system_dlls=(r"C:\Other\evil.dll",),
    )
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(
            replace(ev, imports=imports, system_dlls_reviewed=True)
        )


def test_system_owned_runtime_file_is_privileged() -> None:
    ev = _change_node(evidence(), q.PYTHON, owner_sid=q.SYSTEM)
    assert q.qualify_python_substrate(ev).python == q.PYTHON


@pytest.mark.parametrize(
    "field,value",
    [
        ("granted_mask", 0x00010000),
        ("granted_mask", 0x00040000),
        ("granted_mask", 0x00080000),
        ("tested_mask", 0x00010000),
    ],
)
def test_trading_effective_mutation_access_fails_closed(field: str, value: int) -> None:
    ev = evidence()
    access = tuple(
        replace(entry, **{field: value}) if entry.path == q.RUNTIME else entry
        for entry in ev.trading_access
    )
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(replace(ev, trading_access=access))


def test_python_execute_is_required_by_explicit_policy() -> None:
    ev = evidence()
    item = next(item for item in ev.objects if item.path == q.PYTHON)
    no_execute = item.aces[:-1] + (q.Ace(q.TRADING, q.FILE_READ),)
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(_change_node(ev, q.PYTHON, aces=no_execute))


def test_reviewed_file_read_execute_has_no_mutation_authority() -> None:
    ev = evidence()
    item = next(item for item in ev.objects if item.path == q.PYTHON)
    assert item.aces[-1] == q.Ace(q.TRADING, q.FILE_READ_EXECUTE)
    assert q.FILE_READ_EXECUTE & 0x20
    assert q.FILE_READ_EXECUTE & q.MUTATION_MASK == 0
    assert q.qualify_python_substrate(ev).python == q.PYTHON


@pytest.mark.parametrize("mask", [0x2, 0x4, 0x40, 0x10000, 0x40000, 0x80000])
def test_python_trading_mutation_right_blocks(mask: int) -> None:
    ev = evidence()
    item = next(item for item in ev.objects if item.path == q.PYTHON)
    aces = item.aces[:-1] + (q.Ace(q.TRADING, q.FILE_READ_EXECUTE | mask),)
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(_change_node(ev, q.PYTHON, aces=aces))


@pytest.mark.parametrize(
    "change",
    [
        {"final_path": r"F:\Other"},
        {"drive_type": 4},
        {"volume_root": "G:\\"},
    ],
)
def test_volume_parent_identity_must_be_exact(change: dict[str, object]) -> None:
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(_change_node(evidence(), q.VOLUME, **change))


def test_volume_parent_allows_unrelated_root_rights() -> None:
    ev = evidence()
    volume = next(item for item in ev.objects if item.path == q.VOLUME)
    ev = _change_node(
        ev,
        q.VOLUME,
        dacl_protected=False,
        aces=volume.aces + (q.Ace(q.TRADING, 0x00010116),),
    )
    access = tuple(
        replace(entry, granted_mask=0x00010116) if entry.path == q.VOLUME else entry
        for entry in ev.trading_access
    )
    assert (
        q.qualify_python_substrate(replace(ev, trading_access=access)).python
        == q.PYTHON
    )


@pytest.mark.parametrize("mask", [0x40, 0x40000, 0x80000])
def test_volume_namespace_right_blocks(mask: int) -> None:
    ev = evidence()
    access = tuple(
        replace(entry, granted_mask=mask) if entry.path == q.VOLUME else entry
        for entry in ev.trading_access
    )
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(replace(ev, trading_access=access))


def test_volume_policy_label_mismatch_blocks() -> None:
    ev = evidence()
    access = tuple(
        replace(entry, policy=q.AccessPolicy.PROTECTED_OBJECT)
        if entry.path == q.VOLUME
        else entry
        for entry in ev.trading_access
    )
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(replace(ev, trading_access=access))


def test_broad_volume_acl_with_effective_denial_is_accepted() -> None:
    ev = evidence()
    broad = (
        q.Ace(q.ADMIN, q.ALL_ACCESS),
        q.Ace(q.SYSTEM, q.ALL_ACCESS),
        q.Ace("S-1-5-32-545", q.DIRECTORY_READ),
        q.Ace(q.TRADING, q.DIRECTORY_READ),
    )
    modified = _change_node(ev, q.VOLUME, dacl_protected=False, aces=broad)
    assert q.qualify_python_substrate(modified).python == q.PYTHON


@pytest.mark.parametrize("path", [q.ROOT, q.RUNTIME, q.PYTHON])
@pytest.mark.parametrize(
    "change",
    [
        {"granted_mask": 0x2},
        {"granted_mask": 0x40},
        {"granted_mask": 0x10000},
        {"granted_mask": 0x40000},
        {"granted_mask": 0x80000},
        {"rename_replace_denied": False},
    ],
)
def test_protected_object_mutation_or_replacement_blocks(
    path: str, change: dict[str, object]
) -> None:
    ev = evidence()
    access = tuple(
        replace(entry, **change) if entry.path == path else entry
        for entry in ev.trading_access
    )
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(replace(ev, trading_access=access))


def test_volume_parent_child_replace_denial_required() -> None:
    ev = evidence()
    access = tuple(
        replace(entry, rename_replace_denied=False) if entry.path == q.VOLUME else entry
        for entry in ev.trading_access
    )
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(replace(ev, trading_access=access))


def _present_optional(
    ev: q.QualificationEvidence, path: str
) -> q.QualificationEvidence:
    kind = q.Kind.DIRECTORY if path == q.DLLS else q.Kind.FILE
    runtime = next(item for item in ev.objects if item.path == q.RUNTIME)
    updated = _change_node(
        ev, q.RUNTIME, children=runtime.children + (path.rsplit("\\", 1)[-1],)
    )
    return replace(updated, objects=updated.objects + (_node(path, kind),))


@pytest.mark.parametrize("path", [q.DLLS, q.ZIP])
def test_optional_root_present_and_absent_is_contradictory(path: str) -> None:
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(_present_optional(evidence(), path))


@pytest.mark.parametrize("path", [q.DLLS, q.ZIP])
def test_optional_root_state_must_be_proven(path: str) -> None:
    ev = evidence()
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(
            replace(
                ev,
                absent_search_roots=tuple(
                    item for item in ev.absent_search_roots if item != path
                ),
            )
        )


@pytest.mark.parametrize("path", [q.DLLS, q.ZIP])
def test_protected_present_optional_root_is_accepted(path: str) -> None:
    ev = _present_optional(evidence(), path)
    access = ev.trading_access + (
        q.TradingAccessEvidence(
            path, q.MUTATION_MASK, 0, True, q.AccessPolicy.PROTECTED_OBJECT
        ),
    )
    ev = replace(
        ev,
        absent_search_roots=tuple(
            item for item in ev.absent_search_roots if item != path
        ),
        trading_access=access,
    )
    assert q.qualify_python_substrate(ev).python == q.PYTHON


@pytest.mark.parametrize(
    "changes",
    [
        {"system_dlls_reviewed": False},
        {"system_dll_transcript_complete": False},
        {"runtime_dependency_transcript_complete": False},
    ],
)
def test_missing_transcript_completeness_blocks(changes: dict[str, object]) -> None:
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(replace(evidence(), **changes))


def test_empty_system_dll_transcript_blocks() -> None:
    ev = evidence()
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(
            replace(ev, imports=replace(ev.imports, loaded_system_dlls=()))
        )


def test_empty_runtime_dependency_transcript_blocks() -> None:
    ev = evidence()
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(
            replace(ev, imports=replace(ev.imports, loaded_runtime_files=()))
        )
