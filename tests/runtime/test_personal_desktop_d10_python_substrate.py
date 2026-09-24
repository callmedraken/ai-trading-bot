"""A124-4 pure acceptance tests; no production path is opened."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from trading_bot.runtime import personal_desktop_d10_python_substrate as q


def _node(path: str, kind: q.Kind, children: tuple[str, ...] = ()) -> q.ObjectEvidence:
    read = q.DIRECTORY_READ if kind is q.Kind.DIRECTORY else q.FILE_READ
    return q.ObjectEvidence(
        path,
        path,
        kind,
        q.ADMIN,
        True,
        (
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
        (),
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
        True,
        True,
        tuple(
            q.TradingAccessEvidence(item.path, q.MUTATION_MASK, 0) for item in objects
        ),
        False,
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
        (q.VOLUME, {"dacl_protected": False}),
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


def test_missing_trading_effective_denial_fails_closed() -> None:
    with pytest.raises(q.SubstrateBlocked):
        q.qualify_python_substrate(
            replace(
                evidence(),
                trading_access=(q.TradingAccessEvidence(q.PYTHON, q.MUTATION_MASK, 0),),
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
