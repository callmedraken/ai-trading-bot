"""Mock Windows seams for P124-1; no fixed production path is opened."""

from __future__ import annotations

import ctypes
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

from scripts import d10_python_substrate_windows as w
from trading_bot.runtime import personal_desktop_d10_python_substrate as q


def _node(path: str, kind: q.Kind) -> q.ObjectEvidence:
    mask = q.DIRECTORY_READ if kind is q.Kind.DIRECTORY else q.FILE_READ_EXECUTE
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
            q.Ace(q.TRADING, mask),
        ),
        False,
        3,
        q.VOLUME,
        "NTFS",
        42,
        len(path),
        1,
    )


def test_complete_native_inventory_uses_fixed_paths_and_rechecks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nodes = {
        q.VOLUME: _node(q.VOLUME, q.Kind.DIRECTORY),
        q.ROOT: _node(q.ROOT, q.Kind.DIRECTORY),
        q.RUNTIME: _node(q.RUNTIME, q.Kind.DIRECTORY),
        q.LIB: _node(q.LIB, q.Kind.DIRECTORY),
        q.SITE_PACKAGES: _node(q.SITE_PACKAGES, q.Kind.DIRECTORY),
        q.PYTHON: _node(q.PYTHON, q.Kind.FILE),
    }
    children = {
        q.VOLUME: ("AITradingBot",),
        q.ROOT: ("runtime",),
        q.RUNTIME: ("Lib", "python.exe"),
        q.LIB: ("site-packages",),
        q.SITE_PACKAGES: (),
    }
    opened: list[str] = []
    absent: list[str] = []

    def open_path(path: str) -> str:
        opened.append(path)
        return path

    monkeypatch.setattr(w, "_open", open_path)
    monkeypatch.setattr(w, "_close", lambda handle: None)
    monkeypatch.setattr(w, "_inspect", lambda path, handle: (nodes[path], 0x10))
    monkeypatch.setattr(w, "_children", lambda path: children[path])
    monkeypatch.setattr(w, "_absent", absent.append)
    snapshot = w.collect_inventory()
    assert {row.evidence.path for row in snapshot.objects} == set(nodes)
    assert len(opened) == len(nodes)
    assert snapshot.pinned_and_rechecked
    assert set(absent) == {*q.CONFIG_NAMES, q.DLLS, q.ZIP}


def test_pinned_native_identity_drift_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def inspect(path: str, handle: str) -> tuple[q.ObjectEvidence, int]:
        nonlocal calls
        calls += 1
        node = _node(path, q.Kind.DIRECTORY)
        if calls > 3:
            node = replace(node, file_index=node.file_index + 1)
        return node, 0x10

    monkeypatch.setattr(w, "_open", lambda path: path)
    monkeypatch.setattr(w, "_close", lambda handle: None)
    monkeypatch.setattr(w, "_inspect", inspect)
    monkeypatch.setattr(w, "_children", lambda path: ())
    monkeypatch.setattr(w, "_absent", lambda path: None)
    with pytest.raises(w.NativeFailure):
        w.collect_inventory()


@pytest.mark.parametrize(
    "path",
    [
        r"F:\AITradingBot\other",
        r"F:\AITradingBot\runtime\..\D10",
        r"C:\Windows\SysWOW64\kernel32.dll",
        r"C:\Windows\System32\sub\kernel32.dll",
        r"C:\Windows\System32\kernel32:stream.dll",
    ],
)
def test_unreviewed_native_path_rejected(path: str) -> None:
    with pytest.raises(w.NativeFailure):
        w._fixed(path)


def test_fixed_system32_direct_dll_admitted() -> None:
    w._fixed(q.SYSTEM32)
    w._fixed(q.SYSTEM32 + r"\kernel32.dll")


def test_fixed_inspect_still_rejects_case_only_final_path_difference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        w, "_native_final_path", lambda handle: q.RUNTIME + r"\python.EXE"
    )
    monkeypatch.setattr(
        w,
        "_inspect_final",
        lambda *args: pytest.fail("fixed inspection must stop before identity read"),
    )
    with pytest.raises(w.NativeFailure, match="final native path differs"):
        w._inspect(q.PYTHON, 1)


@pytest.mark.parametrize(
    "path",
    [
        q.RUNTIME + r"\..\D10\module.pyd",
        q.RUNTIME + r"\module.pyd:stream",
        q.RUNTIME + r"\module.pyd.",
        q.RUNTIME + "\\module.pyd ",
        r"\\server\share\module.pyd",
        r"F:\Other\module.pyd",
        q.SYSTEM32 + r"\sub\kernel32.dll",
        q.SYSTEM32 + r"\kernel32.dll:stream",
    ],
)
def test_dynamic_reported_path_syntax_fails_closed(path: str) -> None:
    with pytest.raises(w.NativeFailure):
        w._runtime_reported_path(path)


def test_runtime_report_path_opens_exact_spelling_and_retains_native_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reported = q.RUNTIME + r"\VCRUNTIME140.dll"
    final_path = q.RUNTIME + r"\vcruntime140.dll"
    opened: list[str] = []

    monkeypatch.setattr(
        w, "_open_runtime_reported", lambda path: opened.append(path) or 5
    )
    monkeypatch.setattr(
        w,
        "_inspect_runtime_reported",
        lambda path, handle: (
            replace(_node(path, q.Kind.FILE), final_path=final_path),
            0x80,
        ),
    )
    monkeypatch.setattr(w, "_close", lambda handle: None)

    assert w._diagnostic_path(reported) == final_path
    assert opened == [reported]


@pytest.mark.parametrize(
    ("final_path", "message"),
    [
        (q.RUNTIME + r"\other.dll", "beyond case"),
        (r"F:\Other\VCRUNTIME140.dll", "fixed native namespace"),
        (q.RUNTIME + r"\Lib\vcruntime140.dll", "beyond case"),
    ],
)
def test_runtime_reported_path_rejects_non_case_final_difference(
    monkeypatch: pytest.MonkeyPatch, final_path: str, message: str
) -> None:
    reported = q.RUNTIME + r"\VCRUNTIME140.dll"
    monkeypatch.setattr(w, "_native_final_path", lambda handle: final_path)
    monkeypatch.setattr(
        w,
        "_inspect_final",
        lambda *args: pytest.fail("mismatched final path must be rejected"),
    )
    with pytest.raises(w.NativeFailure, match=message):
        w._inspect_runtime_reported(reported, 1)


def test_runtime_reported_path_accepts_only_case_difference_and_retains_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reported = q.RUNTIME + r"\VCRUNTIME140.dll"
    final_path = q.RUNTIME + r"\vcruntime140.dll"
    evidence = replace(_node(reported, q.Kind.FILE), final_path=final_path)
    monkeypatch.setattr(w, "_native_final_path", lambda handle: final_path)
    monkeypatch.setattr(
        w, "_inspect_final", lambda path, final, handle: (evidence, 0x80)
    )

    item, attributes = w._inspect_runtime_reported(reported, 1)
    assert item.path == reported
    assert item.final_path == final_path
    assert attributes == 0x80


def test_system32_reported_case_difference_is_direct_child_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reported = q.SYSTEM32 + r"\KERNEL32.DLL"
    final_path = q.SYSTEM32 + r"\kernel32.dll"
    evidence = replace(_node(reported, q.Kind.FILE), final_path=final_path)
    monkeypatch.setattr(w, "_native_final_path", lambda handle: final_path)
    monkeypatch.setattr(
        w, "_inspect_final", lambda path, final, handle: (evidence, 0x80)
    )

    item, _ = w._inspect_system32_reported(reported, 1)
    assert item.path == reported
    assert item.final_path == final_path
    for invalid in (
        q.SYSTEM32 + r"\sub\kernel32.dll",
        q.SYSTEM32 + r"\kernel32.dll:stream",
        q.SYSTEM32 + r"\kernel32.exe",
        r"C:\Windows\SysWOW64\kernel32.dll",
        q.SYSTEM32 + r"\kernel32.dll",
    ):
        if invalid == q.SYSTEM32 + r"\kernel32.dll":
            native_final = q.SYSTEM32 + r"\user32.dll"
            monkeypatch.setattr(
                w, "_native_final_path", lambda handle, final=native_final: final
            )
        with pytest.raises(w.NativeFailure):
            w._inspect_system32_reported(invalid, 1)


def _system32_collection_seams(
    monkeypatch: pytest.MonkeyPatch,
    dll: q.ObjectEvidence,
    inspections: tuple[q.ObjectEvidence, ...] | None = None,
) -> list[str]:
    from scripts import d10_python_substrate_harness as h

    facts = h.TokenObservation(
        q.TRADING, True, False, (q.TRADING,), ("SeChangeNotifyPrivilege",), True, True
    )
    parent = replace(
        _node(q.SYSTEM32, q.Kind.DIRECTORY),
        owner_sid=q.SYSTEM,
        volume_root="C:\\",
    )
    opened: list[str] = []
    inspection_index = 0

    def inspect_dll(path: str, handle: int) -> tuple[q.ObjectEvidence, int]:
        nonlocal inspection_index
        item = dll
        if inspections is not None:
            item = inspections[min(inspection_index, len(inspections) - 1)]
        inspection_index += 1
        return item, 0x80

    def access_check(descriptor: int, token: int, desired: int) -> tuple[int, bool]:
        return 0, False

    monkeypatch.setattr(w, "_trading_token", lambda pid: (103, facts))
    monkeypatch.setattr(w, "_open", lambda path: path)
    monkeypatch.setattr(
        w, "_open_system32_reported", lambda path: opened.append(path) or path
    )
    monkeypatch.setattr(w, "_inspect", lambda path, handle: (parent, 0x10))
    monkeypatch.setattr(w, "_inspect_system32_reported", inspect_dll)
    monkeypatch.setattr(w, "_descriptor", lambda handle: 19)
    monkeypatch.setattr(w, "_access_check", access_check)
    monkeypatch.setattr(w, "_bind", lambda *args: lambda pointer: None)
    monkeypatch.setattr(w, "_close", lambda handle: None)
    return opened


def test_native_system32_collection_preserves_reported_and_final_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reported = q.SYSTEM32 + r"\KERNEL32.DLL"
    final_path = q.SYSTEM32 + r"\kernel32.dll"
    dll = replace(_node(reported, q.Kind.FILE), final_path=final_path)
    opened = _system32_collection_seams(monkeypatch, dll)

    observation = w.collect_system_dlls((reported,), 123)
    assert opened == [reported]
    assert observation.parent.path == q.SYSTEM32
    assert observation.parent.final_path == q.SYSTEM32
    assert observation.dlls[0].path == reported
    assert observation.dlls[0].final_path == final_path
    assert observation.dlls[0].link_count == 1


@pytest.mark.parametrize("link_count", [1, 2])
def test_native_system32_collection_admits_positive_link_counts(
    monkeypatch: pytest.MonkeyPatch, link_count: int
) -> None:
    path = q.SYSTEM32 + r"\kernel32.dll"
    dll = replace(_node(path, q.Kind.FILE), links=link_count)
    _system32_collection_seams(monkeypatch, dll)

    observation = w.collect_system_dlls((path,), 123)
    assert observation.dlls[0].link_count == link_count


@pytest.mark.parametrize("link_count", [0, -1, True, None, "2", 2.0])
def test_native_system32_collection_rejects_invalid_link_counts(
    monkeypatch: pytest.MonkeyPatch, link_count: object
) -> None:
    path = q.SYSTEM32 + r"\kernel32.dll"
    dll = replace(_node(path, q.Kind.FILE), links=link_count)
    _system32_collection_seams(monkeypatch, dll)

    with pytest.raises(w.NativeFailure, match="System32 DLL object differs"):
        w.collect_system_dlls((path,), 123)


@pytest.mark.parametrize(
    ("field", "value"), [("kind", q.Kind.DIRECTORY), ("reparse", True)]
)
def test_native_system32_collection_requires_non_reparse_file(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    path = q.SYSTEM32 + r"\kernel32.dll"
    dll = replace(_node(path, q.Kind.FILE), **{field: value})
    _system32_collection_seams(monkeypatch, dll)

    with pytest.raises(w.NativeFailure, match="System32 DLL object differs"):
        w.collect_system_dlls((path,), 123)


def test_system32_native_handle_inspection_rejects_reparse_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def get_info(handle: int, info_pointer: object) -> int:
        info = ctypes.cast(info_pointer, ctypes.POINTER(w.ByHandleInfo)).contents
        info.attributes = w.FILE_ATTRIBUTE_REPARSE_POINT
        return 1

    monkeypatch.setattr(w, "_dll", lambda name: object())
    monkeypatch.setattr(w, "_bind", lambda *args: get_info)

    with pytest.raises(w.NativeFailure, match="reparse object"):
        w._inspect_final(
            q.SYSTEM32 + r"\kernel32.dll",
            q.SYSTEM32 + r"\kernel32.dll",
            17,
        )


def test_system32_parent_native_final_path_remains_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(w, "_native_final_path", lambda handle: q.SYSTEM32.lower())
    monkeypatch.setattr(
        w,
        "_inspect_final",
        lambda *args: pytest.fail("fixed System32 parent path must remain exact"),
    )

    with pytest.raises(w.NativeFailure, match="final native path differs"):
        w._inspect(q.SYSTEM32, 17)


@pytest.mark.parametrize("failing_check", range(1, 8))
def test_native_system32_trading_mutation_and_delete_denials_are_required(
    monkeypatch: pytest.MonkeyPatch, failing_check: int
) -> None:
    path = q.SYSTEM32 + r"\kernel32.dll"
    dll = replace(_node(path, q.Kind.FILE), links=2)
    _system32_collection_seams(monkeypatch, dll)
    checks = 0

    def access_check(descriptor: int, token: int, desired: int) -> tuple[int, bool]:
        nonlocal checks
        checks += 1
        if checks != failing_check:
            return 0, False
        if desired == 0x02000000:
            return q.MUTATION_MASK, False
        return 0, True

    monkeypatch.setattr(w, "_access_check", access_check)

    with pytest.raises(w.NativeFailure):
        w.collect_system_dlls((path,), 123)
    assert checks == (4 if failing_check <= 4 else 7)


def test_native_system32_link_count_drift_during_reobservation_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = q.SYSTEM32 + r"\kernel32.dll"
    initial = replace(_node(path, q.Kind.FILE), links=2)
    changed = replace(initial, links=3)
    _system32_collection_seams(monkeypatch, initial, (initial, changed))

    with pytest.raises(w.NativeFailure, match="System32 DLL identity/security drift"):
        w.collect_system_dlls((path,), 123)


def test_fixed_signed_input_final_path_remains_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = w._D10_ATTESTATION
    case_variant = path.replace("\\D10\\", "\\d10\\")

    def create_file(requested: str, *args: object) -> int:
        assert requested == path
        return 17

    def final_path(handle: int, buffer: object, size: int, flags: int) -> int:
        buffer.value = "\\\\?\\" + case_variant
        return len(buffer.value)

    def bind(dll: object, name: str, args: list[object], result: object) -> object:
        if name == "CreateFileW":
            return create_file
        if name == "GetFinalPathNameByHandleW":
            return final_path
        raise AssertionError(name)

    monkeypatch.setattr(w, "_dll", lambda name: object())
    monkeypatch.setattr(w, "_bind", bind)
    monkeypatch.setattr(w, "_close", lambda handle: None)
    with pytest.raises(w.NativeFailure, match="fixed signed input final path differs"):
        w._read_fixed_signed_input(path, 1024)


def test_signed_input_reobservation_ignores_only_last_access_time() -> None:
    before = w.ByHandleInfo()
    before.attributes = 32
    before.creation_low = 11
    before.creation_high = 12
    before.access_low = 13
    before.access_high = 14
    before.write_low = 15
    before.write_high = 16
    before.volume_serial = 17
    before.size_high = 18
    before.size_low = 19
    before.links = 1
    before.file_index_high = 20
    before.file_index_low = 21

    after = w.ByHandleInfo()
    ctypes.memmove(ctypes.byref(after), ctypes.byref(before), ctypes.sizeof(before))
    after.access_low = 999
    after.access_high = 1000

    assert bytes(before) != bytes(after)
    assert w._signed_input_reobservation(before) == w._signed_input_reobservation(after)


@pytest.mark.parametrize(
    "field",
    [
        "attributes",
        "creation_low",
        "creation_high",
        "write_low",
        "write_high",
        "volume_serial",
        "size_high",
        "size_low",
        "links",
        "file_index_high",
        "file_index_low",
    ],
)
def test_signed_input_reobservation_blocks_stable_fact_drift(field: str) -> None:
    before = w.ByHandleInfo()
    before.attributes = 32
    before.creation_low = 11
    before.creation_high = 12
    before.access_low = 13
    before.access_high = 14
    before.write_low = 15
    before.write_high = 16
    before.volume_serial = 17
    before.size_high = 18
    before.size_low = 19
    before.links = 1
    before.file_index_high = 20
    before.file_index_low = 21

    after = w.ByHandleInfo()
    ctypes.memmove(ctypes.byref(after), ctypes.byref(before), ctypes.sizeof(before))
    setattr(after, field, int(getattr(after, field)) + 1)

    assert w._signed_input_reobservation(before) != w._signed_input_reobservation(after)


def test_wrong_signed_input_name_blocks() -> None:
    with pytest.raises(w.NativeFailure):
        w._read_fixed_signed_input(q.ROOT + r"\D10\other.json", 1024)


def test_operator_output_must_not_be_production_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(SystemExit):
        w.main(["--trading-pid", "1", "--output", q.ROOT + r"\proof.json"])


def test_native_volume_observation_retains_unrelated_grants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import d10_python_substrate_harness as h

    paths = (q.VOLUME, q.ROOT, q.RUNTIME)
    facts = h.TokenObservation(
        q.TRADING, True, False, (q.TRADING,), ("SeChangeNotifyPrivilege",), True, True
    )
    closed: list[object] = []
    monkeypatch.setattr(w, "_trading_token", lambda pid: (103, facts))
    monkeypatch.setattr(w, "_fixed", lambda path: None)
    monkeypatch.setattr(w, "_open", lambda path: path)
    monkeypatch.setattr(w, "_close", closed.append)
    monkeypatch.setattr(
        w,
        "_inspect",
        lambda path, handle: (_node(path, q.Kind.DIRECTORY), 0x10),
    )
    monkeypatch.setattr(w, "_descriptor", lambda handle: handle)
    monkeypatch.setattr(
        w, "_security", lambda handle: (q.ADMIN, True, (q.Ace(q.ADMIN, q.ALL_ACCESS),))
    )
    monkeypatch.setattr(w, "_dll", lambda name: object())
    monkeypatch.setattr(w, "_bind", lambda dll, name, args, result: lambda ptr: None)

    def access_check(descriptor: str, token: int, desired: int) -> tuple[int, bool]:
        assert token == 103
        if desired == 0x02000000:
            return (0x00010116 if descriptor == q.VOLUME else 0, True)
        if desired == q.MUTATION_MASK:
            return (0, False)
        if desired == 0x00010000:
            return (0x00010000, descriptor == q.VOLUME)
        if desired == 0x40:
            return (0, False)
        raise AssertionError(desired)

    monkeypatch.setattr(w, "_access_check", access_check)
    result = w.collect_trading_access(paths, 123)
    volume = result.access[0]
    assert volume.evidence.policy is q.AccessPolicy.VOLUME_NAMESPACE
    assert volume.evidence.granted_mask == 0x00010116
    assert volume.evidence.rename_replace_denied
    assert volume.rename_access_status
    assert not volume.replace_access_status
    assert volume.token_groups_accounted and volume.token_privileges_accounted
    assert volume.acl_agrees
    assert all(
        row.evidence.policy is q.AccessPolicy.PROTECTED_OBJECT
        for row in result.access[1:]
    )
    assert closed[-1] == 103


def _diagnostic_json() -> dict[str, object]:
    from scripts import d10_python_substrate_harness as h

    return {
        "executable": q.PYTHON,
        "prefix": q.RUNTIME,
        "base_prefix": q.RUNTIME,
        "version": q.VERSION,
        "isolated": True,
        "no_site": True,
        "dont_write_bytecode": True,
        "pycache_prefix": q.ROOT + r"\D10\no-pycache",
        "sys_path": [q.ZIP, q.DLLS, q.LIB],
        "purelib": q.SITE_PACKAGES,
        "platlib": q.SITE_PACKAGES,
        "site_main_called": False,
        "pth_processed": False,
        "dependencies": [[name, "built-in"] for name in h.GUARD_IMPORTS],
        "loaded_modules": [
            q.PYTHON,
            r"C:\Windows\System32\kernel32.dll",
        ],
    }


def test_fixed_diagnostic_command_and_complete_mock_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    import subprocess

    from scripts import d10_python_substrate_harness as h

    calls: list[tuple[str, ...]] = []

    def run(argv: list[str], **kwargs: object) -> object:
        calls.append(tuple(argv[: len(q.FLAGS) + 2]))
        assert argv[: len(q.FLAGS) + 2] == [q.PYTHON, *q.FLAGS, "-c"]
        assert kwargs["cwd"] == q.RUNTIME
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(_diagnostic_json()).encode("utf-8"),
            stderr=b"",
        )

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(w, "_diagnostic_path", lambda path: path)
    diagnostic = w.collect_diagnostic()
    assert calls == [(q.PYTHON, *q.FLAGS, "-c")]
    assert diagnostic.guard_imports_covered == h.GUARD_IMPORTS
    assert diagnostic.imports.loaded_system_dlls == (
        r"C:\Windows\System32\kernel32.dll",
    )


def test_diagnostic_keeps_reported_and_native_dynamic_spellings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    import subprocess

    runtime_rows = (
        (
            q.RUNTIME + r"\VCRUNTIME140.dll",
            q.RUNTIME + r"\vcruntime140.dll",
            "vcruntime",
        ),
        (
            q.RUNTIME + r"\python3.DLL",
            q.RUNTIME + r"\python3.dll",
            "python3",
        ),
    )
    system_reported = q.SYSTEM32 + r"\KERNEL32.DLL"
    raw = _diagnostic_json()
    raw["dependencies"] = [
        *raw["dependencies"],
        *[[name, reported] for reported, _, name in runtime_rows],
    ]
    raw["loaded_modules"] = [
        q.PYTHON,
        *(reported for reported, _, _ in runtime_rows),
        system_reported,
    ]
    final_by_report = {q.PYTHON: q.PYTHON}
    final_by_report.update({reported: final for reported, final, _ in runtime_rows})
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(raw).encode("utf-8"),
            stderr=b"",
        ),
    )
    monkeypatch.setattr(w, "_diagnostic_path", lambda path: final_by_report[path])

    diagnostic = w.collect_diagnostic()
    for reported, final_path, name in runtime_rows:
        dependency = next(row for row in diagnostic.dependencies if row.name == name)
        assert dependency.origin == reported
        assert dependency.final_path == final_path
        mapping = next(
            row for row in diagnostic.runtime_mappings if row.reported_path == reported
        )
        assert mapping.final_path == final_path
        assert final_path in diagnostic.imports.loaded_runtime_files
    assert diagnostic.imports.loaded_system_dlls == (system_reported,)


@pytest.mark.parametrize(
    "changed",
    [
        {"dependencies": []},
        {"loaded_modules": []},
        {"loaded_modules": [r"C:\Windows\SysWOW64\kernel32.dll"]},
        {"site_main_called": True},
    ],
)
def test_diagnostic_missing_or_unreviewed_observation_blocks(
    monkeypatch: pytest.MonkeyPatch, changed: dict[str, object]
) -> None:
    import json
    import subprocess

    raw = _diagnostic_json() | changed
    monkeypatch.setattr(w, "_diagnostic_path", lambda path: path)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(raw).encode("utf-8"),
            stderr=b"",
        ),
    )
    if changed == {"site_main_called": True}:
        # The native collector records the fact; frozen A124-4 rejects it.
        assert w.collect_diagnostic().imports.site_main_called
    else:
        with pytest.raises(w.NativeFailure):
            w.collect_diagnostic()


def test_malformed_signature_rejected_before_native_api() -> None:
    with pytest.raises(w.NativeFailure, match="envelope"):
        w._verify_signed_a123(b"attestation", b"short")


def test_signed_a123_input_comes_from_fixed_paths_and_verified_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hashlib

    from trading_bot.runtime import personal_desktop_d10_deployment_identity as a

    reads: list[tuple[str, int]] = []

    def read(path: str, limit: int) -> bytes:
        reads.append((path, limit))
        return b"attestation" if path == w._D10_ATTESTATION else b"s" * 64

    def verify(attestation: bytes, signature: bytes) -> None:
        assert attestation == b"attestation"
        assert signature == b"s" * 64

    monkeypatch.setattr(w, "_read_fixed_signed_input", read)
    monkeypatch.setattr(w, "_verify_signed_a123", verify)
    monkeypatch.setattr(
        a,
        "parse_deployment_attestation",
        lambda data: SimpleNamespace(
            signing_key_id=a.D10_SIGNING_KEY_ID,
            production_python=q.PYTHON,
            production_python_version=q.VERSION,
        ),
    )
    assert a.D10_SIGNING_KEY_ID == "AITradingBot/D10/DeploymentAttestation/v3"
    result = w.collect_signed_a123_identity()
    assert reads == [(w._D10_ATTESTATION, 64 * 1024), (w._D10_SIGNATURE, 64)]
    assert result.attestation_sha256 == hashlib.sha256(b"attestation").hexdigest()
    assert result.signature_verified and result.signing_key_id_verified


@pytest.mark.parametrize(
    "wrong_key_id", ["wrong", "AITradingBot/D10/DeploymentAttestation/v2"]
)
def test_wrong_signed_key_id_blocks(
    monkeypatch: pytest.MonkeyPatch, wrong_key_id: str
) -> None:

    from trading_bot.runtime import personal_desktop_d10_deployment_identity as a

    monkeypatch.setattr(w, "_read_fixed_signed_input", lambda path, limit: b"x")
    monkeypatch.setattr(w, "_verify_signed_a123", lambda data, signature: None)
    monkeypatch.setattr(
        a,
        "parse_deployment_attestation",
        lambda data: SimpleNamespace(signing_key_id=wrong_key_id),
    )
    with pytest.raises(w.NativeFailure, match="key identity"):
        w.collect_signed_a123_identity()


def test_qualification_failure_produces_nonzero_operator_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import d10_python_substrate_harness as h

    monkeypatch.setattr(w.os.path, "realpath", lambda path: path)
    monkeypatch.setattr(w, "WindowsCollector", lambda pid: object())
    monkeypatch.setattr(
        h,
        "collect",
        lambda collector: (_ for _ in ()).throw(
            h.CollectionBlocked("qualification rejected")
        ),
    )
    assert w.main(["--trading-pid", "123", "--output", r"C:\evidence.json"]) == 2


def _native_token_seams(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sid: str = q.TRADING,
    groups: tuple[tuple[str, int], ...] = ((q.TRADING, 4),),
    privileges: tuple[tuple[str, int], ...] = (("SeChangeNotifyPrivilege", 2),),
    elevated: bool = False,
) -> list[int]:
    closed: list[int] = []
    monkeypatch.setattr(w, "_open_process", lambda pid: 101)
    monkeypatch.setattr(w, "_open_process_token", lambda process: 102)
    monkeypatch.setattr(w, "_duplicate_token", lambda primary: 103)
    monkeypatch.setattr(w, "_close", closed.append)
    monkeypatch.setattr(w, "_token_user", lambda token: sid)
    monkeypatch.setattr(w, "_token_groups", lambda token: groups)
    monkeypatch.setattr(w, "_token_privileges", lambda token: privileges)
    monkeypatch.setattr(w, "_token_elevated", lambda token: elevated)
    monkeypatch.setitem(sys.modules, "win32api", None)
    monkeypatch.setitem(sys.modules, "win32security", None)
    return closed


def test_actual_trading_token_facts_and_handle_lifetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = _native_token_seams(monkeypatch)
    pinned, facts = w._trading_token(123)
    assert pinned == 103
    assert facts.sid == q.TRADING
    assert facts.enabled_groups == (q.TRADING,)
    assert facts.enabled_privileges == ("SeChangeNotifyPrivilege",)
    assert facts.groups_complete and facts.privileges_complete
    assert closed == [102, 101]
    w._close(pinned)
    assert closed == [102, 101, 103]


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"sid": q.ADMIN}, "not exact non-admin Trading"),
        ({"elevated": True}, "not exact non-admin Trading"),
        ({"groups": ((q.TRADING, 4), (q.ADMIN, 4))}, "not exact non-admin Trading"),
        ({"groups": ((q.TRADING, 4), (q.ADMIN, 0))}, "not exact non-admin Trading"),
        ({"privileges": ()}, "bypass-traverse privilege missing"),
        *[
            (
                {
                    "privileges": (
                        ("SeChangeNotifyPrivilege", 2),
                        (dangerous, 2),
                    )
                },
                "enabled bypass privilege",
            )
            for dangerous in (
                "SeBackupPrivilege",
                "SeRestorePrivilege",
                "SeTakeOwnershipPrivilege",
                "SeSecurityPrivilege",
                "SeDebugPrivilege",
            )
        ],
    ],
)
def test_trading_token_policy_blocks_and_closes(
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, object],
    reason: str,
) -> None:
    closed = _native_token_seams(monkeypatch, **changes)
    with pytest.raises(
        w.NativeFailure, match="Trading token acquisition failed"
    ) as error:
        w._trading_token(123)
    assert reason in str(error.value.__cause__)
    assert closed == [102, 101, 103]


@pytest.mark.parametrize(
    "failed_seam",
    [
        "_open_process",
        "_open_process_token",
        "_duplicate_token",
        "_token_user",
        "_token_groups",
        "_token_privileges",
        "_token_elevated",
    ],
)
def test_trading_native_failure_closes_every_acquired_handle(
    monkeypatch: pytest.MonkeyPatch, failed_seam: str
) -> None:
    closed = _native_token_seams(monkeypatch)

    def fail(*args: object) -> None:
        raise w.NativeFailure("native failure")

    monkeypatch.setattr(w, failed_seam, fail)
    with pytest.raises(w.NativeFailure, match="Trading token acquisition failed"):
        w._trading_token(123)
    expected = {
        "_open_process": [],
        "_open_process_token": [101],
        "_duplicate_token": [102, 101],
    }.get(failed_seam, [102, 101, 103])
    assert closed == expected


def test_native_open_and_duplicate_use_only_reviewed_rights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(w, "_dll", lambda name: object())
    calls: list[tuple[object, ...]] = []

    def bind(_dll: object, name: str, _args: object, _result: object) -> object:
        if name == "OpenProcess":

            def open_process(rights: int, inherit: bool, pid: int) -> int:
                calls.append((name, rights, inherit, pid))
                return 101

            return open_process
        if name in ("OpenProcessToken", "DuplicateToken"):

            def token_call(handle: int, rights: int, output: object) -> int:
                calls.append((name, handle, rights))
                ctypes.cast(
                    output, ctypes.POINTER(w.wintypes.HANDLE)
                ).contents.value = 102 if name == "OpenProcessToken" else 103
                return 1

            return token_call
        raise AssertionError(name)

    monkeypatch.setattr(w, "_bind", bind)
    assert w._open_process(123) == 101
    assert w._open_process_token(101) == 102
    assert w._duplicate_token(102) == 103
    assert calls == [
        ("OpenProcess", w.PROCESS_QUERY_LIMITED_INFORMATION, False, 123),
        ("OpenProcessToken", 101, w.TOKEN_QUERY | w.TOKEN_DUPLICATE),
        ("DuplicateToken", 102, 2),
    ]


def test_native_privilege_name_lookup_uses_allocated_buffer_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(w, "_dll", lambda name: object())
    monkeypatch.setattr(w.ctypes, "get_last_error", lambda: w.ERROR_INSUFFICIENT_BUFFER)

    def lookup(_system: object, luid: object, name: object, length: object) -> int:
        count = ctypes.cast(length, ctypes.POINTER(w.wintypes.DWORD))
        assert ctypes.cast(luid, ctypes.POINTER(w.Luid)).contents.low == 7
        if name is None:
            count.contents.value = 24
            return 0
        assert count.contents.value == 25
        name.value = "SeChangeNotifyPrivilege"
        count.contents.value = len(name.value)
        return 1

    monkeypatch.setattr(w, "_bind", lambda dll, name, args, result: lookup)
    assert w._lookup_privilege_name(w.Luid(7, 0)) == "SeChangeNotifyPrivilege"


def test_token_information_native_probe_and_read_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def bind(_dll: object, name: str, _args: object, _result: object) -> object:
        assert name == "GetTokenInformation"

        def get(
            _token: object,
            _kind: object,
            buffer: object,
            _size: object,
            returned: object,
        ) -> int:
            if buffer is None:
                ctypes.cast(
                    returned, ctypes.POINTER(w.wintypes.DWORD)
                ).contents.value = 4
                return 0
            return 0

        return get

    monkeypatch.setattr(w, "_dll", lambda name: object())
    monkeypatch.setattr(w, "_bind", bind)
    monkeypatch.setattr(w.ctypes, "get_last_error", lambda: w.ERROR_INSUFFICIENT_BUFFER)
    with pytest.raises(w.NativeFailure, match="GetTokenInformation failed"):
        w._token_information(103, w.TOKEN_USER)


@pytest.mark.parametrize("kind", [w.TOKEN_USER, w.TOKEN_GROUPS, w.TOKEN_PRIVILEGES])
def test_incomplete_token_class_blocks(
    monkeypatch: pytest.MonkeyPatch, kind: int
) -> None:
    monkeypatch.setattr(
        w, "_token_information", lambda token, info: (ctypes.create_string_buffer(1), 1)
    )
    with pytest.raises(w.NativeFailure, match="incomplete"):
        {
            w.TOKEN_USER: w._token_user,
            w.TOKEN_GROUPS: w._token_groups,
            w.TOKEN_PRIVILEGES: w._token_privileges,
        }[kind](103)


@pytest.mark.parametrize(
    ("kind", "offset", "entry_size"),
    [
        (
            w.TOKEN_GROUPS,
            w.TokenGroups.groups.offset,
            ctypes.sizeof(w.SidAndAttributes),
        ),
        (
            w.TOKEN_PRIVILEGES,
            w.TokenPrivileges.privileges.offset,
            ctypes.sizeof(w.LuidAndAttributes),
        ),
    ],
)
def test_token_count_cannot_exceed_native_buffer(
    monkeypatch: pytest.MonkeyPatch, kind: int, offset: int, entry_size: int
) -> None:
    buffer = ctypes.create_string_buffer(offset + entry_size)
    ctypes.cast(buffer, ctypes.POINTER(w.wintypes.DWORD)).contents.value = 2
    monkeypatch.setattr(
        w, "_token_information", lambda token, info: (buffer, len(buffer))
    )
    with pytest.raises(w.NativeFailure, match="count incomplete"):
        (w._token_groups if kind == w.TOKEN_GROUPS else w._token_privileges)(103)


def test_token_user_sid_pointer_must_remain_inside_native_buffer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer = ctypes.create_string_buffer(ctypes.sizeof(w.SidAndAttributes))
    ctypes.cast(buffer, ctypes.POINTER(w.SidAndAttributes)).contents.sid = 1
    monkeypatch.setattr(
        w, "_token_information", lambda token, info: (buffer, len(buffer))
    )
    with pytest.raises(w.NativeFailure, match="SID pointer outside"):
        w._token_user(103)


@pytest.mark.parametrize("converted", [True, False])
def test_native_sid_conversion_allocation_is_freed(
    monkeypatch: pytest.MonkeyPatch, converted: bool
) -> None:
    text = ctypes.create_unicode_buffer(q.TRADING)
    freed: list[int] = []
    monkeypatch.setattr(w, "_dll", lambda name: object())

    def bind(_dll: object, name: str, _args: object, _result: object) -> object:
        if name == "ConvertSidToStringSidW":

            def convert(sid: object, output: object) -> int:
                ctypes.cast(
                    output, ctypes.POINTER(ctypes.c_void_p)
                ).contents.value = ctypes.addressof(text)
                return int(converted)

            return convert
        if name == "LocalFree":
            return lambda allocation: freed.append(allocation.value) or None
        raise AssertionError(name)

    monkeypatch.setattr(w, "_bind", bind)
    if converted:
        assert w._sid(123) == q.TRADING
    else:
        with pytest.raises(w.NativeFailure, match="ConvertSidToStringSidW failed"):
            w._sid(123)
    assert freed == [ctypes.addressof(text)]


def test_native_token_classes_parse_complete_enabled_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_offset = ctypes.sizeof(w.SidAndAttributes)
    user = ctypes.create_string_buffer(user_offset + 12)
    ctypes.cast(user, ctypes.POINTER(w.SidAndAttributes)).contents.sid = (
        ctypes.addressof(user) + user_offset
    )
    groups_offset = w.TokenGroups.groups.offset
    group_size = ctypes.sizeof(w.SidAndAttributes)
    groups = ctypes.create_string_buffer(groups_offset + 2 * group_size + 24)
    ctypes.cast(groups, ctypes.POINTER(w.wintypes.DWORD)).contents.value = 2
    for index, attributes in enumerate((w.SE_GROUP_ENABLED, 0)):
        entry = ctypes.cast(
            ctypes.byref(groups, groups_offset + index * group_size),
            ctypes.POINTER(w.SidAndAttributes),
        ).contents
        entry.sid = (
            ctypes.addressof(groups) + groups_offset + 2 * group_size + 12 * index
        )
        entry.attributes = attributes
    privilege_offset = w.TokenPrivileges.privileges.offset
    privilege_size = ctypes.sizeof(w.LuidAndAttributes)
    privileges = ctypes.create_string_buffer(privilege_offset + 2 * privilege_size)
    ctypes.cast(privileges, ctypes.POINTER(w.wintypes.DWORD)).contents.value = 2
    for index, attributes in enumerate((w.SE_PRIVILEGE_ENABLED, 0)):
        entry = ctypes.cast(
            ctypes.byref(privileges, privilege_offset + index * privilege_size),
            ctypes.POINTER(w.LuidAndAttributes),
        ).contents
        entry.luid.low = index + 1
        entry.attributes = attributes
    observations = {
        w.TOKEN_USER: user,
        w.TOKEN_GROUPS: groups,
        w.TOKEN_PRIVILEGES: privileges,
    }
    monkeypatch.setattr(
        w,
        "_token_information",
        lambda token, kind: (observations[kind], len(observations[kind])),
    )
    monkeypatch.setattr(
        w,
        "_sid_in_token_buffer",
        lambda buffer, length, pointer: (
            q.ADMIN
            if buffer is groups
            and pointer > ctypes.addressof(groups) + groups_offset + 2 * group_size
            else q.TRADING
        ),
    )
    seen: list[int] = []
    monkeypatch.setattr(
        w,
        "_lookup_privilege_name",
        lambda luid: seen.append(luid.low) or "SeChangeNotifyPrivilege",
    )
    assert w._token_user(103) == q.TRADING
    assert w._token_groups(103) == ((q.TRADING, w.SE_GROUP_ENABLED), (q.ADMIN, 0))
    assert w._token_privileges(103) == (("SeChangeNotifyPrivilege", 2),)
    assert seen == [1]


@pytest.mark.parametrize(
    ("elevation_value", "returned_length", "api_success", "expected"),
    [
        pytest.param(0, 4, True, False, id="not-elevated"),
        pytest.param(1, 4, True, True, id="elevated"),
        pytest.param(0, 4, False, "GetTokenInformation failed", id="api-failure"),
        pytest.param(0, 0, True, "TokenElevation length invalid", id="wrong-length"),
        pytest.param(2, 4, True, "TokenElevation value invalid", id="invalid-value"),
    ],
)
def test_token_elevation_reads_fixed_dword_without_sizing_probe(
    monkeypatch: pytest.MonkeyPatch,
    elevation_value: int,
    returned_length: int,
    api_success: bool,
    expected: bool | str,
) -> None:
    def generic_info(_token: int, _kind: int) -> None:
        raise AssertionError("TokenElevation used generic sizing helper")

    monkeypatch.setattr(w, "_token_information", generic_info)
    monkeypatch.setattr(
        w, "_dll", lambda name: object() if name == "advapi32" else None
    )
    monkeypatch.setattr(w.ctypes, "get_last_error", lambda: 5)
    calls: list[tuple[int, int, int]] = []

    def bind(_dll: object, name: str, args: object, result: object) -> object:
        assert name == "GetTokenInformation"
        assert args == [
            w.wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            w.wintypes.DWORD,
            ctypes.POINTER(w.wintypes.DWORD),
        ]
        assert result is w.wintypes.BOOL

        def get(
            token: int,
            information_class: int,
            output: object,
            size: int,
            returned: object,
        ) -> int:
            calls.append((token, information_class, size))
            assert output is not None
            ctypes.cast(
                output, ctypes.POINTER(w.wintypes.DWORD)
            ).contents.value = elevation_value
            ctypes.cast(
                returned, ctypes.POINTER(w.wintypes.DWORD)
            ).contents.value = returned_length
            return int(api_success)

        return get

    monkeypatch.setattr(w, "_bind", bind)
    if isinstance(expected, str):
        with pytest.raises(w.NativeFailure, match=expected):
            w._token_elevated(103)
    else:
        assert w._token_elevated(103) is expected
    assert calls == [(103, w.TOKEN_ELEVATION, ctypes.sizeof(w.wintypes.DWORD))]


def test_trading_cleanup_failure_blocks_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _native_token_seams(monkeypatch)

    def close(handle: int) -> None:
        if handle == 102:
            raise w.NativeFailure("CloseHandle failed")

    monkeypatch.setattr(w, "_close", close)
    with pytest.raises(w.NativeFailure, match="Trading token acquisition failed"):
        w._trading_token(123)


def test_administrator_membership_api_failure_frees_sid_and_handles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[int] = []
    freed: list[int] = []
    monkeypatch.setattr(w, "_dll", lambda name: object())
    monkeypatch.setattr(w, "_open_process_token", lambda process: 201)
    monkeypatch.setattr(w, "_duplicate_token", lambda primary: 202)
    monkeypatch.setattr(w, "_token_elevated", lambda primary: True)
    monkeypatch.setattr(w, "_close", closed.append)

    def bind(_dll: object, name: str, _args: object, _result: object) -> object:
        if name == "GetCurrentProcess":
            return lambda: 999
        if name == "ConvertStringSidToSidW":

            def convert(sid: str, output: object) -> int:
                ctypes.cast(
                    output, ctypes.POINTER(ctypes.c_void_p)
                ).contents.value = 303
                return 1

            return convert
        if name == "LocalFree":
            return lambda pointer: freed.append(pointer.value) or None
        if name == "CheckTokenMembership":
            return lambda token, sid, member: 0
        raise AssertionError(name)

    monkeypatch.setattr(w, "_bind", bind)
    with pytest.raises(w.NativeFailure, match="Administrator token proof unavailable"):
        w.require_administrator()
    assert freed == [303]
    assert closed == [202, 201]


@pytest.mark.parametrize(
    ("elevated", "member", "accepted"),
    [(True, True, True), (False, True, False), (True, False, False)],
)
def test_administrator_proof_requires_both_facts_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch, elevated: bool, member: bool, accepted: bool
) -> None:
    closed: list[int] = []
    freed: list[int] = []
    monkeypatch.setattr(w, "_dll", lambda name: object())
    monkeypatch.setattr(w, "_open_process_token", lambda process: 201)
    monkeypatch.setattr(w, "_duplicate_token", lambda primary: 202)
    monkeypatch.setattr(w, "_token_elevated", lambda primary: elevated)
    monkeypatch.setattr(w, "_close", closed.append)
    monkeypatch.setitem(sys.modules, "win32api", None)
    monkeypatch.setitem(sys.modules, "win32security", None)

    def bind(_dll: object, name: str, _args: object, _result: object) -> object:
        if name == "GetCurrentProcess":
            return lambda: 999
        if name == "ConvertStringSidToSidW":

            def convert(sid: str, output: object) -> int:
                assert sid == q.ADMIN
                ctypes.cast(
                    output, ctypes.POINTER(ctypes.c_void_p)
                ).contents.value = 303
                return 1

            return convert
        if name == "CheckTokenMembership":

            def check(token: int, sid: object, output: object) -> int:
                assert token == 202
                assert sid.value == 303
                ctypes.cast(
                    output, ctypes.POINTER(w.wintypes.BOOL)
                ).contents.value = int(member)
                return 1

            return check
        if name == "LocalFree":
            return lambda pointer: freed.append(pointer.value) or None
        raise AssertionError(name)

    monkeypatch.setattr(w, "_bind", bind)
    if accepted:
        w.require_administrator()
    else:
        with pytest.raises(
            w.NativeFailure, match="Administrator token proof unavailable"
        ):
            w.require_administrator()
    assert closed == [202, 201]
    assert freed == [303]


def test_administrator_duplication_failure_closes_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[int] = []
    monkeypatch.setattr(w, "_dll", lambda name: object())
    monkeypatch.setattr(w, "_bind", lambda dll, name, args, result: lambda: 999)
    monkeypatch.setattr(w, "_open_process_token", lambda process: 201)
    monkeypatch.setattr(w, "_token_elevated", lambda primary: True)
    monkeypatch.setattr(
        w,
        "_duplicate_token",
        lambda primary: (_ for _ in ()).throw(w.NativeFailure("duplicate")),
    )
    monkeypatch.setattr(w, "_close", closed.append)
    with pytest.raises(w.NativeFailure, match="Administrator token proof unavailable"):
        w.require_administrator()
    assert closed == [201]


def test_windows_api_failure_blocks_without_native_fallback() -> None:
    with pytest.raises(w.NativeFailure, match="MockRead failed"):
        w._check(False, "MockRead")
