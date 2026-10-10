"""133-AH one-shot provisioning for the fixed immutable-release parent.

The only production mutation is one CreateDirectoryW for RELEASES_BASE using
the already-reviewed immutable-image security descriptor. No release image,
scheduler, credential, provider, durable paper or trading authority is present.
"""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from trading_bot.arch133_acl.administrator import administrator_sid
from trading_bot.arch133_acl.read_only import (
    ADMINISTRATORS_SID,
    SYSTEM_SID,
    TRADING_SID,
)
from trading_bot.supervised_release.installation_contract import (
    IMAGE_ACES,
    ReleasePaths,
)
from trading_bot.supervised_release.model import RELEASES_BASE
from trading_bot.supervised_release.native_read import (
    WindowsReadSession,
    bind,
    windows_libraries,
)
from trading_bot.supervised_release.native_write import image_security_attributes
from trading_bot.supervised_release.observer import check_object

WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-supervised-release-parent-provisioning"
)
BRANCH = "feature/robinhood-supervised-release-parent-provisioning"
BASE_HEAD = "e462a4f666ae2b28dd0d9c0459f4efce154c3470"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
AUTH_ENV = "AI_TRADING_BOT_ARCH133_AH_PARENT_AUTHORIZATION"
AUTH_VALUE = "ARCH133_AH_ONE_RELEASE_PARENT_PROVISION_AUTHORIZED"
# Valid UUID5-shaped lexical probe only. It is never created or selected.
PROBE_RELEASE_ID = "release-00000000000050008000000000000000"
CONTAINER_ACES = (
    (ADMINISTRATORS_SID, 0x1F01FF, 0, 0),
    (SYSTEM_SID, 0x1F01FF, 0, 0),
)


@dataclass(frozen=True, slots=True)
class ParentReadiness:
    exists: bool
    container_identity: tuple[int, int]
    parent_identity: tuple[int, int] | None


def _administrator_host() -> None:
    windows_libraries()
    administrator_sid()


def _observe_once(session: WindowsReadSession) -> ParentReadiness:
    volume = check_object(
        session.object("F:\\", directory=True),
        "F:\\",
        directory=True,
        image_policy=False,
    )
    if (
        type(volume.owner) is not str
        or not volume.owner
        or volume.owner == TRADING_SID
        or any(
            type(sid) is not str
            or not sid
            or type(mask) is not int
            or type(kind) is not int
            or type(flags) is not int
            or kind not in {0, 1}
            or flags & ~0x1F
            or (
                kind == 0
                and not flags & 0x08
                and sid not in {ADMINISTRATORS_SID, SYSTEM_SID}
                and mask & (0x000C0040 | 0x10000000)
            )
            for sid, mask, kind, flags in volume.aces
        )
    ):
        raise ValueError("volume namespace authority rejected")

    container_path = r"F:\AITradingBot"
    container = check_object(
        session.object(container_path, directory=True),
        container_path,
        directory=True,
        volume=volume.identity[0],
        image_policy=False,
    )
    if (
        container.owner != ADMINISTRATORS_SID
        or container.protected is not True
        or container.aces != CONTAINER_ACES
    ):
        raise ValueError("release container security rejected")

    observed = session.object(RELEASES_BASE, directory=True)
    if observed is None:
        return ParentReadiness(False, container.identity, None)
    parent = check_object(
        observed,
        RELEASES_BASE,
        directory=True,
        volume=container.identity[0],
    )
    return ParentReadiness(True, container.identity, parent.identity)


def _readiness() -> ParentReadiness:
    session = WindowsReadSession(ReleasePaths(PROBE_RELEASE_ID))
    try:
        first = _observe_once(session)
        second = _observe_once(session)
        if second != first:
            raise ValueError("release parent observation drift")
        return first
    finally:
        session.close()


def _primary(
    status: str,
    readiness: ParentReadiness | None = None,
    *,
    disposition: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": status,
        "release_parent": RELEASES_BASE,
    }
    if disposition is not None:
        result["disposition"] = disposition
    if readiness is not None:
        result["target_state"] = (
            "EXACT_PARENT_PRESENT" if readiness.exists else "ABSENT"
        )
        result["container_identity"] = readiness.container_identity
        if readiness.parent_identity is not None:
            result["parent_identity"] = readiness.parent_identity
        result["expected_aces"] = IMAGE_ACES
    return result


def _preflight() -> dict[str, object]:
    try:
        _administrator_host()
        readiness = _readiness()
        return {
            "status": "PASS",
            "effect_disposition": "NOT_STARTED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": _primary(
                "ALREADY_PROVISIONED_VERIFIED"
                if readiness.exists
                else "READY_TO_PROVISION",
                readiness,
            ),
        }
    except (Exception, KeyboardInterrupt):
        return {
            "status": "BLOCKED",
            "effect_disposition": "NOT_STARTED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": _primary(
                "BLOCKED", disposition="NO_PARENT_PROVISIONING_EFFECT"
            ),
        }


def _create_parent() -> bool:
    kernel, _ = windows_libraries()
    create = bind(
        kernel,
        "CreateDirectoryW",
        [ctypes.c_wchar_p, ctypes.c_void_p],
        ctypes.c_int32,
    )
    with image_security_attributes() as attributes:
        return bool(create(RELEASES_BASE, ctypes.byref(attributes)))


def _execute_once(consume_attempt: Callable[[], None]) -> dict[str, object]:
    try:
        _administrator_host()
        before = _readiness()
    except (Exception, KeyboardInterrupt):
        return {
            "status": "BLOCKED",
            "effect_disposition": "NOT_STARTED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": _primary(
                "BLOCKED", disposition="NO_PARENT_PROVISIONING_EFFECT"
            ),
        }

    if before.exists:
        return {
            "status": "PASS",
            "effect_disposition": "NOT_STARTED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": _primary("ALREADY_PROVISIONED_VERIFIED", before),
        }

    try:
        consume_attempt()
    except (Exception, KeyboardInterrupt):
        return {
            "status": "BLOCKED",
            "effect_disposition": "NOT_STARTED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": _primary(
                "BLOCKED",
                before,
                disposition="NO_PARENT_PROVISIONING_EFFECT",
            ),
        }

    try:
        created = _create_parent()
        after = _readiness()
        if created is not True or not after.exists:
            raise ValueError("release parent creation acknowledgement rejected")
        return {
            "status": "PASS",
            "effect_disposition": "CONFIRMED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": _primary("PROVISIONED_VERIFIED", after),
        }
    except (Exception, KeyboardInterrupt):
        return {
            "status": "INDETERMINATE",
            "effect_disposition": "MAY_HAVE_OCCURRED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": {
                **_primary("INDETERMINATE"),
                "disposition": "PRESERVE_PARENT_PROVISIONING_EVIDENCE_NO_RETRY",
            },
        }
