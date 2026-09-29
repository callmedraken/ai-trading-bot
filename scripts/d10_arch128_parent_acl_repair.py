"""Architecture-128 exact parent-ACL reconciliation operator.

Importing this module has no host effect. The read-only mode observes only the
fixed deployment parent. The protected mode can rewrite only that parent's
owner/DACL from the exact diagnosed three-ACE drift to the frozen two-ACE
policy. It never recurses and has no scheduler, activation, source-launch, or
trading authority.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
from ctypes import wintypes
from dataclasses import asdict, replace
from typing import Final

from scripts import d10_arch128_r4_replacement as r4
from scripts import d10_arch128_r4_windows as r4w
from scripts import d10_protected_replacement_windows as legacy_windows
from scripts.d10_protected_deployment import (
    ADMINISTRATORS_SID,
    D10_PARENT,
    FILE_ALL_ACCESS,
    SYSTEM_SID,
    Ace,
    DeploymentBlocked,
    NativeObject,
    require_parent_native_object,
)
from trading_bot.runtime.windows_authority_security import (
    SecurityAce,
    SecurityPolicy,
    apply_security_policy,
)

SCHEMA: Final = "arch128-r4-parent-acl-repair/v1"
READ_ONLY_FLAG: Final = "--read-only-drift-check"
EXECUTE_FLAG: Final = "--execute-reviewed-parent-acl-repair"
AUTH_ENV: Final = "AI_TRADING_BOT_ARCH128_PARENT_ACL_REPAIR_AUTHORIZATION"
AUTH_VALUE: Final = "ARCH128_PARENT_ACL_REPAIR_AUTHORIZED"
DRIFT_SID: Final = "S-1-5-21-1397534616-3988210162-180023805-1005"
DRIFT_FLAGS: Final = 3

_WRITE_DAC = 0x00040000


def _expected_drift_aces() -> tuple[Ace, ...]:
    return (
        Ace(ADMINISTRATORS_SID, FILE_ALL_ACCESS),
        Ace(SYSTEM_SID, FILE_ALL_ACCESS),
        Ace(DRIFT_SID, FILE_ALL_ACCESS, flags=DRIFT_FLAGS),
    )


def _target_policy() -> SecurityPolicy:
    return SecurityPolicy(
        ADMINISTRATORS_SID,
        (
            SecurityAce(ADMINISTRATORS_SID, FILE_ALL_ACCESS),
            SecurityAce(SYSTEM_SID, FILE_ALL_ACCESS),
        ),
        True,
    )


def _require_parent_shape(item: NativeObject, aces: tuple[Ace, ...]) -> None:
    if (
        type(item) is not NativeObject
        or item.path != D10_PARENT
        or item.final_path != D10_PARENT
        or item.directory is not True
        or item.reparse is not False
        or item.drive_type != 3
        or item.volume_root != "F:\\"
        or item.filesystem != "NTFS"
        or item.owner_sid != ADMINISTRATORS_SID
        or item.dacl_protected is not True
        or item.aces != aces
        or item.links != 1
        or type(item.file_index) is not int
        or item.file_index <= 0
        or type(item.volume_serial) is not int
        or item.volume_serial <= 0
    ):
        raise DeploymentBlocked("arch128_parent_acl_drift_shape_mismatch")


def _observe_parent(reader: r4w.WindowsArch128ReadOnlyReader) -> NativeObject:
    reader.require_administrator()
    handle = reader._open(D10_PARENT, directory=True)
    if handle is None:
        raise DeploymentBlocked("arch128_parent_acl_target_unavailable")
    try:
        first = reader._inspect(handle, D10_PARENT)
        second = reader._inspect(handle, D10_PARENT)
    finally:
        reader._close(handle)
    if first != second:
        raise DeploymentBlocked("arch128_parent_acl_observation_drift")
    return second


def _observe_exact_drift(
    reader: r4w.WindowsArch128ReadOnlyReader,
) -> NativeObject:
    item = _observe_parent(reader)
    _require_parent_shape(item, _expected_drift_aces())
    return item


def _observe_exact_target(
    reader: r4w.WindowsArch128ReadOnlyReader,
) -> NativeObject:
    item = _observe_parent(reader)
    require_parent_native_object(item)
    return item


def _open_parent_for_acl(
    reader: r4w.WindowsArch128ReadOnlyReader,
) -> int:
    create = reader._bind(
        reader._kernel,
        "CreateFileW",
        [
            ctypes.c_wchar_p,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ],
        wintypes.HANDLE,
    )
    handle = create(
        D10_PARENT,
        legacy_windows._READ_CONTROL
        | _WRITE_DAC
        | legacy_windows._FILE_READ_ATTRIBUTES
        | legacy_windows._SYNCHRONIZE,
        legacy_windows._FILE_SHARE_READ
        | legacy_windows._FILE_SHARE_WRITE
        | legacy_windows._FILE_SHARE_DELETE,
        None,
        legacy_windows._OPEN_EXISTING,
        legacy_windows._FILE_FLAG_OPEN_REPARSE_POINT
        | legacy_windows._FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    if handle in (None, 0, ctypes.c_void_p(-1).value):
        raise DeploymentBlocked("arch128_parent_acl_write_open_unavailable")
    return int(handle)


def _base(mode: str) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "mode": mode,
        "status": "BLOCKED",
        "target": D10_PARENT,
        "acl_mutation": "NOT_RUN",
        "recursive_acl_mutation": "NOT_RUN",
        "d10_child_mutation": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "activation": "NOT_RUN",
        "source_launch": "NOT_RUN",
        "provider": "NOT_RUN",
        "Paper-v2": "NOT_RUN",
        "broker": "NOT_RUN",
        "live": "NOT_RUN",
    }


def _read_only() -> dict[str, object]:
    result = _base("READ_ONLY_DRIFT_CHECK")
    try:
        reader = r4w.WindowsArch128ReadOnlyReader()
        observed = _observe_exact_drift(reader)
    except Exception as exc:
        result["reason"] = type(exc).__name__
        result["detail"] = str(exc)
        return result

    result.update(
        {
            "status": "PASS",
            "drift_state": "EXACT_DIAGNOSED_THREE_ACE_STATE",
            "observed": asdict(observed),
        }
    )
    return result


def _repair_once() -> dict[str, object]:
    result = _base("PROTECTED_REPAIR")
    reader = r4w.WindowsArch128ReadOnlyReader()
    before = _observe_exact_drift(reader)
    handle: int | None = None
    applied = False
    close_ambiguous = False

    try:
        handle = _open_parent_for_acl(reader)
        pinned_before = reader._inspect(handle, D10_PARENT)
        if pinned_before != before:
            raise DeploymentBlocked("arch128_parent_acl_pinned_identity_drift")

        apply_security_policy(handle, _target_policy())
        applied = True

        pinned_after = reader._inspect(handle, D10_PARENT)
        expected_after = replace(
            before,
            owner_sid=ADMINISTRATORS_SID,
            dacl_protected=True,
            aces=(
                Ace(ADMINISTRATORS_SID, FILE_ALL_ACCESS),
                Ace(SYSTEM_SID, FILE_ALL_ACCESS),
            ),
        )
        if pinned_after != expected_after:
            raise DeploymentBlocked("arch128_parent_acl_post_apply_drift")
    except Exception as exc:
        result["status"] = "STOPPED_AFTER_APPLY" if applied else "BLOCKED"
        result["reason"] = type(exc).__name__
        result["detail"] = str(exc)
        return result
    finally:
        if handle is not None:
            try:
                reader._close(handle)
            except Exception:
                close_ambiguous = True

    if close_ambiguous:
        result["status"] = "STOPPED_AFTER_APPLY"
        result["reason"] = "handle_close_ambiguous"
        return result

    try:
        after = _observe_exact_target(reader)
        if (
            after.file_index != before.file_index
            or after.volume_serial != before.volume_serial
            or after.final_path != before.final_path
        ):
            raise DeploymentBlocked("arch128_parent_acl_object_identity_changed")
    except Exception as exc:
        result["status"] = "STOPPED_AFTER_APPLY"
        result["reason"] = type(exc).__name__
        result["detail"] = str(exc)
        return result

    result.update(
        {
            "status": "PASS",
            "acl_mutation": "EXACT_PARENT_POLICY_APPLIED_AND_VERIFIED",
            "before_ace_count": len(before.aces),
            "after_ace_count": len(after.aces),
            "file_index": after.file_index,
            "volume_serial": after.volume_serial,
        }
    )
    return result


def _dispatch(
    arguments: tuple[str, ...],
    environment: dict[str, str],
) -> dict[str, object]:
    if arguments == (READ_ONLY_FLAG,):
        return _read_only()

    if arguments != (EXECUTE_FLAG,):
        result = _base("INTERLOCK")
        result["reason"] = "execution_flag_not_exact"
        return result

    if environment.get(AUTH_ENV) != AUTH_VALUE:
        result = _base("PROTECTED_REPAIR")
        result["reason"] = "authorization_interlock_not_exact"
        return result

    return _repair_once()


def main() -> int:
    result = _dispatch(tuple(sys.argv[1:]), dict(os.environ))
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "PASS":
        return 1

    if result["mode"] == "READ_ONLY_DRIFT_CHECK":
        print("D10_ARCH128_PARENT_ACL_DRIFT_CHECK=PASS")
    else:
        print("D10_ARCH128_PARENT_ACL_REPAIR=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
