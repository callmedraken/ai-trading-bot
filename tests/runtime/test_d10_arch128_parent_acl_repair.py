from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from scripts import d10_arch128_parent_acl_repair as repair
from scripts.d10_protected_deployment import (
    ADMINISTRATORS_SID,
    D10_PARENT,
    FILE_ALL_ACCESS,
    SYSTEM_SID,
    Ace,
    DeploymentBlocked,
    NativeObject,
)


def _native(aces: tuple[Ace, ...]) -> NativeObject:
    return NativeObject(
        path=D10_PARENT,
        final_path=D10_PARENT,
        directory=True,
        owner_sid=ADMINISTRATORS_SID,
        dacl_protected=True,
        aces=aces,
        reparse=False,
        drive_type=3,
        volume_root="F:\\",
        filesystem="NTFS",
        volume_serial=123,
        file_index=456,
        links=1,
        size=4096,
    )


def _drift() -> NativeObject:
    return _native(repair._expected_drift_aces())


def _target() -> NativeObject:
    return _native(
        (
            Ace(ADMINISTRATORS_SID, FILE_ALL_ACCESS),
            Ace(SYSTEM_SID, FILE_ALL_ACCESS),
        )
    )


def test_exact_drift_is_fixed_three_ace_state() -> None:
    assert repair._expected_drift_aces() == (
        Ace(ADMINISTRATORS_SID, FILE_ALL_ACCESS),
        Ace(SYSTEM_SID, FILE_ALL_ACCESS),
        Ace(repair.DRIFT_SID, FILE_ALL_ACCESS, flags=repair.DRIFT_FLAGS),
    )


def test_target_policy_is_frozen_two_ace_parent() -> None:
    policy = repair._target_policy()
    assert policy.owner_sid == ADMINISTRATORS_SID
    assert policy.dacl_protected is True
    assert len(policy.aces) == 2
    assert policy.aces[0].principal_sid == ADMINISTRATORS_SID
    assert policy.aces[1].principal_sid == SYSTEM_SID


def test_shape_rejects_any_other_extra_ace() -> None:
    wrong = _native(
        (
            Ace(ADMINISTRATORS_SID, FILE_ALL_ACCESS),
            Ace(SYSTEM_SID, FILE_ALL_ACCESS),
            Ace("S-1-5-21-1-2-3-4", FILE_ALL_ACCESS, flags=3),
        )
    )
    with pytest.raises(DeploymentBlocked):
        repair._require_parent_shape(wrong, repair._expected_drift_aces())


def test_interlock_blocks_before_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        repair,
        "_repair_once",
        lambda: (_ for _ in ()).throw(AssertionError("repair called")),
    )
    result = repair._dispatch((repair.EXECUTE_FLAG,), {})
    assert result["status"] == "BLOCKED"
    assert result["acl_mutation"] == "NOT_RUN"


def test_unknown_arguments_are_non_mutating() -> None:
    result = repair._dispatch(("--wrong",), {})
    assert result["status"] == "BLOCKED"
    assert result["acl_mutation"] == "NOT_RUN"


class _FakeReader:
    def __init__(self) -> None:
        self.current = _drift()
        self.closed = False
        self.fail_close = False

    def require_administrator(self) -> None:
        return None

    def _open(self, path: str, *, directory: bool):
        assert path == D10_PARENT
        assert directory is True
        return 11

    def _inspect(self, handle: int, path: str) -> NativeObject:
        assert handle in (11, 22)
        assert path == D10_PARENT
        return self.current

    def _close(self, handle: int) -> None:
        assert handle in (11, 22)
        if self.fail_close:
            raise RuntimeError("close ambiguity")
        self.closed = True


def test_repair_rewrites_only_exact_parent_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = _FakeReader()
    monkeypatch.setattr(
        repair.r4w,
        "WindowsArch128ReadOnlyReader",
        lambda: reader,
    )
    monkeypatch.setattr(repair, "_open_parent_for_acl", lambda reader: 22)

    def apply(handle, policy):
        assert handle == 22
        assert len(policy.aces) == 2
        reader.current = _target()

    monkeypatch.setattr(repair, "apply_security_policy", apply)

    result = repair._repair_once()
    assert result["status"] == "PASS"
    assert result["before_ace_count"] == 3
    assert result["after_ace_count"] == 2
    assert result["recursive_acl_mutation"] == "NOT_RUN"
    assert result["d10_child_mutation"] == "NOT_RUN"


def test_post_apply_mismatch_stops_without_second_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = _FakeReader()
    calls = 0
    monkeypatch.setattr(
        repair.r4w,
        "WindowsArch128ReadOnlyReader",
        lambda: reader,
    )
    monkeypatch.setattr(repair, "_open_parent_for_acl", lambda reader: 22)

    def apply(handle, policy):
        nonlocal calls
        calls += 1
        reader.current = replace(_target(), file_index=999)

    monkeypatch.setattr(repair, "apply_security_policy", apply)

    result = repair._repair_once()
    assert result["status"] == "STOPPED_AFTER_APPLY"
    assert calls == 1


def test_operator_has_no_recursive_scheduler_or_trading_authority() -> None:
    source = Path(repair.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "SetNamedSecurityInfo",
        "icacls",
        "takeown",
        "Get-ChildItem",
        "os.walk",
        "rglob",
        "RegisterTask",
        "Start-ScheduledTask",
        "Enable-ScheduledTask",
        "publish_activation",
        "provider.",
        "paper_v2",
        "broker.",
        "live_order",
    ):
        assert forbidden not in source

    assert "apply_security_policy(handle, _target_policy())" in source
    assert repair.D10_PARENT == r"F:\AITradingBot"


def test_post_apply_close_ambiguity_is_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = _FakeReader()
    monkeypatch.setattr(
        repair.r4w,
        "WindowsArch128ReadOnlyReader",
        lambda: reader,
    )
    monkeypatch.setattr(repair, "_open_parent_for_acl", lambda reader: 22)

    def apply(handle, policy):
        reader.current = _target()
        reader.fail_close = True

    monkeypatch.setattr(repair, "apply_security_policy", apply)

    result = repair._repair_once()
    assert result["status"] == "STOPPED_AFTER_APPLY"
    assert result["reason"] == "handle_close_ambiguous"
