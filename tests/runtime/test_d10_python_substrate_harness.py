"""Pure/mock P124-1 harness tests; no production path is opened."""

from __future__ import annotations

import ntpath
from dataclasses import replace

import pytest

from scripts import d10_python_substrate_harness as h
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


def _fixture() -> tuple[
    h.NativeSnapshot,
    h.TradingObservation,
    h.Diagnostic,
    h.SystemDllObservation,
    h.SignedA123Identity,
]:
    objects = (
        _node(q.VOLUME, q.Kind.DIRECTORY, ("AITradingBot",)),
        _node(q.ROOT, q.Kind.DIRECTORY, ("runtime",)),
        _node(q.RUNTIME, q.Kind.DIRECTORY, ("Lib", "python.exe")),
        _node(q.LIB, q.Kind.DIRECTORY, ("site-packages",)),
        _node(q.SITE_PACKAGES, q.Kind.DIRECTORY),
        _node(q.PYTHON, q.Kind.FILE),
    )
    by_path = {item.path: item for item in objects}
    snapshot = h.NativeSnapshot(
        tuple(
            h.NativeObject(
                item,
                0x10 if item.kind is q.Kind.DIRECTORY else 0x80,
                len(item.aces),
                None
                if item.path == q.VOLUME
                else by_path[ntpath.dirname(item.path)].file_index,
            )
            for item in objects
        ),
        q.CONFIG_NAMES,
        (q.DLLS, q.ZIP),
        True,
        True,
        True,
    )
    token = h.TokenObservation(
        q.TRADING, True, False, (q.TRADING,), ("SeChangeNotifyPrivilege",), True, True
    )
    trading = h.TradingObservation(
        token,
        tuple(
            h.NativeAccess(
                q.TradingAccessEvidence(item.path, q.MUTATION_MASK, 0, True),
                True,
                False,
                False,
                False,
                True,
                True,
                True,
            )
            for item in objects
        ),
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
    deps = tuple(
        h.Dependency(name, "builtin", None, "builtin") for name in h.GUARD_IMPORTS
    )
    diagnostic = h.Diagnostic(
        imports, (q.PYTHON, *q.FLAGS, "-c"), deps, h.GUARD_IMPORTS, True, True
    )
    dlls = h.SystemDllObservation(
        q.ObjectEvidence(
            q.SYSTEM32,
            q.SYSTEM32,
            q.Kind.DIRECTORY,
            q.SYSTEM,
            True,
            (q.Ace(q.SYSTEM, q.ALL_ACCESS),),
            False,
            3,
            "C:\\",
            "NTFS",
            77,
            99,
            1,
        ),
        q.TradingAccessEvidence(q.SYSTEM32, q.MUTATION_MASK, 0, True),
        (
            h.SystemDll(
                imports.loaded_system_dlls[0],
                imports.loaded_system_dlls[0],
                q.SYSTEM,
                True,
                (q.Ace(q.SYSTEM, q.ALL_ACCESS),),
                0,
                True,
                True,
                True,
            ),
        ),
        True,
        True,
        True,
    )
    signed = h.SignedA123Identity(q.PYTHON, q.VERSION, "a" * 64, True, True)
    return snapshot, trading, diagnostic, dlls, signed


class MockCollector:
    def __init__(self) -> None:
        (
            self.before,
            self.trading_value,
            self.diagnostic_value,
            self.dlls,
            self.signed,
        ) = _fixture()
        self.after = self.before
        self.calls: list[str] = []

    def inventory(self) -> h.NativeSnapshot:
        self.calls.append("inventory")
        return self.before if self.calls.count("inventory") == 1 else self.after

    def trading(self, paths: tuple[str, ...]) -> h.TradingObservation:
        self.calls.append("trading")
        assert set(paths) == {row.evidence.path for row in self.before.objects}
        return self.trading_value

    def diagnostic(self) -> h.Diagnostic:
        self.calls.append("diagnostic")
        return self.diagnostic_value

    def system_dlls(self, paths: tuple[str, ...]) -> h.SystemDllObservation:
        self.calls.append("system_dlls")
        assert paths == self.diagnostic_value.imports.loaded_system_dlls
        return self.dlls

    def signed_a123_identity(self) -> h.SignedA123Identity:
        self.calls.append("signed")
        return self.signed


def test_complete_evidence_and_deterministic_transcript() -> None:
    collector = MockCollector()
    first = h.collect(collector)
    assert b'"status":"PASS"' in first
    assert first == h.collect(MockCollector())
    assert collector.calls == [
        "inventory",
        "trading",
        "diagnostic",
        "system_dlls",
        "inventory",
        "signed",
    ]
    assert b"handle" not in first and b"credential" not in first


@pytest.mark.parametrize(
    ("section", "change"),
    [
        ("before", {"inventory_complete": False}),
        ("before", {"no_follow": False}),
        ("before", {"absent_search_roots": ()}),
        (
            "trading_value",
            {
                "token": h.TokenObservation(
                    q.TRADING, False, True, (q.ADMIN,), (), True, True
                )
            },
        ),
        ("diagnostic_value", {"guard_imports_covered": ()}),
        ("diagnostic_value", {"runtime_files_complete": False}),
        ("dlls", {"known_dlls_complete": False}),
        ("signed", {"signature_verified": False}),
    ],
)
def test_missing_proof_blocks(section: str, change: dict[str, object]) -> None:
    collector = MockCollector()
    setattr(collector, section, replace(getattr(collector, section), **change))
    with pytest.raises(h.CollectionBlocked):
        h.collect(collector)


def test_reobservation_drift_blocks() -> None:
    collector = MockCollector()
    collector.after = replace(collector.before, absent_configuration=())
    with pytest.raises(h.CollectionBlocked, match="drift"):
        h.collect(collector)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("granted_mask", 1),
        ("tested_mask", 1),
        ("rename_replace_denied", False),
    ],
)
def test_effective_mutation_denial_required(field: str, value: object) -> None:
    collector = MockCollector()
    first = collector.trading_value.access[0]
    changed = replace(first, evidence=replace(first.evidence, **{field: value}))
    collector.trading_value = replace(
        collector.trading_value,
        access=(changed, *collector.trading_value.access[1:]),
    )
    with pytest.raises(h.CollectionBlocked):
        h.collect(collector)


def test_qualification_rejection_blocks() -> None:
    collector = MockCollector()
    collector.signed = replace(collector.signed, version="0.0.0")
    with pytest.raises(h.CollectionBlocked):
        h.collect(collector)


def test_unknown_native_capability_cannot_serialize() -> None:
    with pytest.raises(h.CollectionBlocked):
        h.canonical_transcript({"handle": object()})


@pytest.mark.parametrize(
    ("path", "changes"),
    [
        (q.PYTHON, {"final_path": q.RUNTIME + r"\else.exe"}),
        (q.PYTHON, {"reparse": True}),
        (q.PYTHON, {"links": 2}),
        (q.PYTHON, {"owner_sid": q.TRADING}),
        (q.PYTHON, {"dacl_protected": False}),
        (q.PYTHON, {"aces": (q.Ace(q.TRADING, q.ALL_ACCESS),)}),
        (q.RUNTIME, {"children": ("Lib", "lib", "python.exe")}),
        (q.RUNTIME, {"children": ("Lib",)}),
    ],
)
def test_native_object_security_and_inventory_fail_closed(
    path: str, changes: dict[str, object]
) -> None:
    collector = MockCollector()
    rows = tuple(
        replace(row, evidence=replace(row.evidence, **changes))
        if row.evidence.path == path
        else row
        for row in collector.before.objects
    )
    collector.before = replace(collector.before, objects=rows)
    collector.after = collector.before
    with pytest.raises(h.CollectionBlocked):
        h.collect(collector)


@pytest.mark.parametrize(
    "changes",
    [
        {"flags": ("-I", "-S")},
        {"version": "3.14.2"},
        {"executable": q.RUNTIME + r"\other.exe"},
        {"site_main_called": True},
        {"pth_processed": True},
        {"sys_path": (q.LIB, q.SITE_PACKAGES)},
        {"sys_path": (q.LIB, r"C:\Unreviewed")},
        {"loaded_runtime_files": ()},
        {"loaded_system_dlls": ()},
    ],
)
def test_interpreter_runtime_dependency_failure(changes: dict[str, object]) -> None:
    collector = MockCollector()
    collector.diagnostic_value = replace(
        collector.diagnostic_value,
        imports=replace(collector.diagnostic_value.imports, **changes),
    )
    with pytest.raises(h.CollectionBlocked):
        h.collect(collector)


@pytest.mark.parametrize(
    "changes",
    [
        {"absent_configuration": ()},
        {"absent_search_roots": ()},
    ],
)
def test_absence_proof_required(changes: dict[str, object]) -> None:
    collector = MockCollector()
    collector.before = replace(collector.before, **changes)
    collector.after = collector.before
    with pytest.raises(h.CollectionBlocked):
        h.collect(collector)


def test_optional_root_present_and_absent_is_contradictory() -> None:
    collector = MockCollector()
    zip_node = _node(q.ZIP, q.Kind.FILE)
    runtime_rows = tuple(
        replace(
            row,
            evidence=replace(
                row.evidence,
                children=(*row.evidence.children, "python314.zip"),
            ),
        )
        if row.evidence.path == q.RUNTIME
        else row
        for row in collector.before.objects
    )
    collector.before = replace(
        collector.before,
        objects=(
            *runtime_rows,
            h.NativeObject(
                zip_node,
                0x80,
                len(zip_node.aces),
                len(q.RUNTIME),
            ),
        ),
    )
    collector.after = collector.before
    collector.trading_value = replace(
        collector.trading_value,
        access=(
            *collector.trading_value.access,
            h.NativeAccess(
                q.TradingAccessEvidence(q.ZIP, q.MUTATION_MASK, 0, True),
                True,
                False,
                False,
                False,
                True,
                True,
                True,
            ),
        ),
    )
    with pytest.raises(h.CollectionBlocked, match="optional search root"):
        h.collect(collector)


@pytest.mark.parametrize(
    "changes",
    [
        {"complete": False},
        {"reviewed": False},
        {"known_dlls_complete": False},
        {"dlls": ()},
    ],
)
def test_system32_transcript_must_be_complete(changes: dict[str, object]) -> None:
    collector = MockCollector()
    collector.dlls = replace(collector.dlls, **changes)
    with pytest.raises(h.CollectionBlocked):
        h.collect(collector)


def test_non_system32_dll_blocks() -> None:
    collector = MockCollector()
    row = collector.dlls.dlls[0]
    bad = replace(
        row,
        path=r"C:\Windows\SysWOW64\kernel32.dll",
        final_path=r"C:\Windows\SysWOW64\kernel32.dll",
    )
    collector.dlls = replace(collector.dlls, dlls=(bad,))
    with pytest.raises(h.CollectionBlocked):
        h.collect(collector)


def test_missing_bypass_traverse_privilege_blocks_harness() -> None:
    collector = MockCollector()
    collector.trading_value = replace(
        collector.trading_value,
        token=replace(collector.trading_value.token, enabled_privileges=()),
    )
    with pytest.raises(h.CollectionBlocked, match="bypass-traverse"):
        h.collect(collector)


def test_access_check_indeterminate_blocks() -> None:
    collector = MockCollector()
    first = collector.trading_value.access[0]
    collector.trading_value = replace(
        collector.trading_value,
        access=(
            replace(first, access_check_succeeded=False),
            *collector.trading_value.access[1:],
        ),
    )
    with pytest.raises(h.CollectionBlocked):
        h.collect(collector)


@pytest.mark.parametrize(
    "change",
    [
        {"rename_access_status": True},
        {"replace_access_status": True},
        {"token_groups_accounted": False},
        {"token_privileges_accounted": False},
        {"acl_agrees": False},
    ],
)
def test_trading_access_indeterminacy_blocks(change: dict[str, object]) -> None:
    collector = MockCollector()
    first = collector.trading_value.access[0]
    collector.trading_value = replace(
        collector.trading_value,
        access=(replace(first, **change), *collector.trading_value.access[1:]),
    )
    with pytest.raises(h.CollectionBlocked):
        h.collect(collector)


@pytest.mark.parametrize(
    "change",
    [
        {"owner_sid": q.SYSTEM},
        {"dacl_protected": False},
        {"aces": (q.Ace(q.TRADING, q.ALL_ACCESS),)},
        {"file_index": 999},
    ],
)
def test_before_after_native_security_identity_drift_blocks(
    change: dict[str, object],
) -> None:
    collector = MockCollector()
    rows = tuple(
        replace(
            row,
            evidence=replace(row.evidence, **change),
            ace_count=len(change.get("aces", row.evidence.aces)),
        )
        if row.evidence.path == q.PYTHON
        else row
        for row in collector.after.objects
    )
    collector.after = replace(collector.after, objects=rows)
    with pytest.raises(h.CollectionBlocked, match="drift"):
        h.collect(collector)


def test_system32_parent_security_must_be_reviewable() -> None:
    collector = MockCollector()
    collector.dlls = replace(
        collector.dlls,
        parent_access=replace(collector.dlls.parent_access, granted_mask=1),
    )
    with pytest.raises(h.CollectionBlocked):
        h.collect(collector)


def test_transcript_order_independent_of_native_set_enumeration() -> None:
    baseline = h.collect(MockCollector())
    collector = MockCollector()
    shuffled_rows = tuple(
        replace(
            row,
            evidence=replace(
                row.evidence, children=tuple(reversed(row.evidence.children))
            ),
        )
        for row in reversed(collector.before.objects)
    )
    collector.before = replace(
        collector.before,
        objects=shuffled_rows,
        absent_configuration=tuple(reversed(collector.before.absent_configuration)),
        absent_search_roots=tuple(reversed(collector.before.absent_search_roots)),
    )
    collector.after = collector.before
    collector.trading_value = replace(
        collector.trading_value,
        access=tuple(reversed(collector.trading_value.access)),
    )
    collector.diagnostic_value = replace(
        collector.diagnostic_value,
        dependencies=tuple(reversed(collector.diagnostic_value.dependencies)),
        imports=replace(
            collector.diagnostic_value.imports,
            sys_path=collector.diagnostic_value.imports.sys_path,
            loaded_runtime_files=tuple(
                reversed(collector.diagnostic_value.imports.loaded_runtime_files)
            ),
        ),
    )
    assert h.collect(collector) == baseline
