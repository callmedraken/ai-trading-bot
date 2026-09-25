"""Mock Windows seams for P124-1; no fixed production path is opened."""

from __future__ import annotations

from dataclasses import replace

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


def test_wrong_signed_input_name_blocks() -> None:
    with pytest.raises(w.NativeFailure):
        w._read_fixed_signed_input(q.ROOT + r"\D10\other.json", 1024)


def test_operator_output_must_not_be_production_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(SystemExit):
        w.main(["--trading-pid", "1", "--output", q.ROOT + r"\proof.json"])


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
    from types import SimpleNamespace

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
    diagnostic = w.collect_diagnostic()
    assert calls == [(q.PYTHON, *q.FLAGS, "-c")]
    assert diagnostic.guard_imports_covered == h.GUARD_IMPORTS
    assert diagnostic.imports.loaded_system_dlls == (
        r"C:\Windows\System32\kernel32.dll",
    )


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
    from types import SimpleNamespace

    raw = _diagnostic_json() | changed
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
    from types import SimpleNamespace

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
    from types import SimpleNamespace

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


def test_actual_trading_token_facts_are_read_from_accesscheck_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    from types import SimpleNamespace

    class Handle:
        closed = False

        def Close(self) -> None:
            self.closed = True

    process = Handle()
    primary = Handle()
    duplicate = Handle()
    token_user = 1
    token_groups = 2
    token_privileges = 3
    token_elevation = 4

    def information(token: object, kind: int) -> object:
        assert token is duplicate
        if kind == token_user:
            return ("trading", 0)
        if kind == token_groups:
            return [("trading", 4)]
        if kind == token_privileges:
            return [("notify", 2)]
        return 0

    security = SimpleNamespace(
        TOKEN_QUERY=8,
        TOKEN_DUPLICATE=2,
        SecurityImpersonation=2,
        TokenUser=token_user,
        TokenGroups=token_groups,
        TokenPrivileges=token_privileges,
        TokenElevation=token_elevation,
        OpenProcessToken=lambda handle, rights: primary,
        DuplicateToken=lambda token, level: duplicate,
        GetTokenInformation=information,
        ConvertSidToStringSid=lambda value: q.TRADING,
        LookupPrivilegeName=lambda system, luid: "SeChangeNotifyPrivilege",
    )
    api = SimpleNamespace(OpenProcess=lambda rights, inherit, pid: process)
    monkeypatch.setitem(sys.modules, "win32api", api)
    monkeypatch.setitem(sys.modules, "win32security", security)
    pinned, facts = w._trading_token(123)
    assert pinned is duplicate
    assert facts.sid == q.TRADING
    assert facts.enabled_groups == (q.TRADING,)
    assert facts.enabled_privileges == ("SeChangeNotifyPrivilege",)
    assert process.closed and primary.closed
    assert not duplicate.closed


def test_windows_api_failure_blocks_without_native_fallback() -> None:
    with pytest.raises(w.NativeFailure, match="MockRead failed"):
        w._check(False, "MockRead")
