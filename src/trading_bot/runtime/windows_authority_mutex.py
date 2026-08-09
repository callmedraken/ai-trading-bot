"""Machine-wide Global named mutex for lifecycle arbitration."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from ctypes import wintypes
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from trading_bot.runtime.windows_authority import (
    LifecycleMutexError,
    LifecycleMutexSecurityError,
    LifecycleMutexWaitError,
    require_windows_platform,
)
from trading_bot.runtime.windows_authority_security import (
    MUTEX_MODIFY_STATE,
    READ_CONTROL,
    SYNCHRONIZE,
    SecurityObjectType,
    SecurityPolicy,
    authority_security_policy,
    build_security_attributes,
    inspect_handle_security,
    is_current_token_administrator,
    is_current_token_elevated,
    resolve_current_token_sid,
    resolve_local_trading_sid,
)

LIFECYCLE_MUTEX_LABEL = "lifecycle-arbiter/v1"
LIFECYCLE_MUTEX_PREFIX = "Global\\AITradingBot-Lifecycle-v1-"
WAIT_OBJECT_0 = 0
WAIT_ABANDONED_0 = 0x80
WAIT_FAILED = 0xFFFFFFFF
INFINITE = 0xFFFFFFFF
ERROR_ALREADY_EXISTS = 183
ADMINISTRATORS_SID = "S-1-5-32-544"
SYSTEM_SID = "S-1-5-18"


def canonical_lifecycle_mutex_material(
    machine_authority_id: str,
    authority_epoch_id: str,
    launch_reservation_id: str,
) -> bytes:
    """Return the exact sorted-key UTF-8 identity material from architecture 77."""

    if any(
        type(value) is not str
        for value in (machine_authority_id, authority_epoch_id, launch_reservation_id)
    ):
        raise LifecycleMutexError("lifecycle identity fields must be text")
    return json.dumps(
        {
            "authority_epoch_id": authority_epoch_id,
            "label": LIFECYCLE_MUTEX_LABEL,
            "launch_reservation_id": launch_reservation_id,
            "machine_authority_id": machine_authority_id,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def lifecycle_mutex_digest(
    machine_authority_id: str,
    authority_epoch_id: str,
    launch_reservation_id: str,
) -> str:
    """Derive the lowercase hexadecimal SHA-256 mutex suffix."""

    return hashlib.sha256(
        canonical_lifecycle_mutex_material(
            machine_authority_id, authority_epoch_id, launch_reservation_id
        )
    ).hexdigest()


def lifecycle_mutex_name(
    machine_authority_id: str,
    authority_epoch_id: str,
    launch_reservation_id: str,
) -> str:
    """Return the one fixed machine-wide named-mutex object name."""

    return LIFECYCLE_MUTEX_PREFIX + lifecycle_mutex_digest(
        machine_authority_id, authority_epoch_id, launch_reservation_id
    )


derive_lifecycle_mutex_digest = lifecycle_mutex_digest
build_lifecycle_mutex_name = lifecycle_mutex_name


def reviewed_lifecycle_mutex_security_policy(
    trading_sid: str,
    *,
    owner_sid: str,
) -> SecurityPolicy:
    """Return the exact mutex policy for one approved creator-compatible owner."""

    if owner_sid not in {ADMINISTRATORS_SID, SYSTEM_SID, trading_sid}:
        raise LifecycleMutexSecurityError("lifecycle mutex owner is not approved")
    base = authority_security_policy("lifecycle-mutex", trading_sid)
    return SecurityPolicy(owner_sid, base.aces)


def select_lifecycle_mutex_owner_sid(
    trading_sid: str,
    current_token_sid: str,
    *,
    token_is_elevated: bool,
    token_is_administrator: bool,
) -> str:
    """Select an owner the current approved token can assign, from exact SID facts."""

    if current_token_sid == trading_sid:
        return trading_sid
    if current_token_sid == SYSTEM_SID:
        return SYSTEM_SID
    if token_is_elevated and token_is_administrator:
        return ADMINISTRATORS_SID
    raise LifecycleMutexSecurityError(
        "current token cannot create an approved lifecycle mutex owner"
    )


def resolve_current_lifecycle_mutex_owner_sid(trading_sid: str) -> str:
    """Resolve the approved owner compatible with the current Windows token."""

    current_sid = resolve_current_token_sid()
    if current_sid in {trading_sid, SYSTEM_SID}:
        return current_sid
    return select_lifecycle_mutex_owner_sid(
        trading_sid,
        current_sid,
        token_is_elevated=is_current_token_elevated(),
        token_is_administrator=is_current_token_administrator(),
    )


def validate_lifecycle_mutex_security_descriptor(trading_sid: str) -> None:
    """Preflight construction of the reviewed binary mutex descriptor."""

    require_windows_platform()
    owner_sid = resolve_current_lifecycle_mutex_owner_sid(trading_sid)
    with build_security_attributes(
        reviewed_lifecycle_mutex_security_policy(trading_sid, owner_sid=owner_sid)
    ):
        pass


class LifecycleMutexState(StrEnum):
    OWNED = "OWNED"
    ABANDONED_OWNER = "ABANDONED_OWNER"


@dataclass(frozen=True, slots=True)
class LifecycleMutexAcquisition:
    """Typed result retaining conservative WAIT_ABANDONED information."""

    name: str
    digest: str
    state: LifecycleMutexState

    @property
    def was_abandoned(self) -> bool:
        return self.state is LifecycleMutexState.ABANDONED_OWNER


def _validate_mutex_policy(
    handle: int,
    trading_sid: str,
) -> SecurityPolicy:
    base = authority_security_policy("lifecycle-mutex", trading_sid)
    owner, protected, aces = inspect_handle_security(handle, SecurityObjectType.KERNEL)
    if owner not in {ADMINISTRATORS_SID, SYSTEM_SID, trading_sid}:
        raise LifecycleMutexSecurityError(
            "existing lifecycle mutex owner is unexpected"
        )
    if not protected or aces != base.aces:
        raise LifecycleMutexSecurityError(
            "existing lifecycle mutex security is unexpected"
        )
    return SecurityPolicy(owner, base.aces)


class GlobalLifecycleMutex:
    """One non-stealable machine-wide mutex scope."""

    def __init__(
        self,
        machine_authority_id: str,
        authority_epoch_id: str,
        launch_reservation_id: str,
        *,
        trading_sid: str | None = None,
    ) -> None:
        self.digest = lifecycle_mutex_digest(
            machine_authority_id, authority_epoch_id, launch_reservation_id
        )
        self.name = LIFECYCLE_MUTEX_PREFIX + self.digest
        self._trading_sid = trading_sid
        self._handle: int | None = None
        self._owned = False
        self.acquisition: LifecycleMutexAcquisition | None = None

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()

    def acquire(self) -> LifecycleMutexAcquisition:
        """Create/open, validate, and wait forever; never take over by timeout."""

        require_windows_platform()
        if self._handle is not None:
            raise LifecycleMutexError("lifecycle mutex scope is already active")
        trading_sid = self._trading_sid or resolve_local_trading_sid()
        owner_sid = resolve_current_lifecycle_mutex_owner_sid(trading_sid)
        policy = reviewed_lifecycle_mutex_security_policy(
            trading_sid, owner_sid=owner_sid
        )
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel32.CreateMutexExW
        create.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        create.restype = ctypes.c_void_p
        with build_security_attributes(policy) as attributes:
            handle = create(
                ctypes.byref(attributes.attributes),
                self.name,
                0,
                MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE,
            )
        if not handle:
            raise LifecycleMutexSecurityError(
                "lifecycle mutex could not be created/opened"
            )
        self._handle = int(getattr(handle, "value", handle))
        try:
            if not _validate_mutex_policy(self._handle, trading_sid):
                raise LifecycleMutexSecurityError("lifecycle mutex policy mismatch")
            wait = kernel32.WaitForSingleObject
            wait.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            wait.restype = ctypes.c_ulong
            result = int(wait(self._handle, INFINITE))
            if result == WAIT_FAILED:
                raise LifecycleMutexWaitError("lifecycle mutex wait failed")
            if result not in (WAIT_OBJECT_0, WAIT_ABANDONED_0):
                raise LifecycleMutexWaitError(
                    "lifecycle mutex returned an unexpected wait state"
                )
            self._owned = True
            state = (
                LifecycleMutexState.ABANDONED_OWNER
                if result == WAIT_ABANDONED_0
                else LifecycleMutexState.OWNED
            )
            self.acquisition = LifecycleMutexAcquisition(self.name, self.digest, state)
            return self.acquisition
        except BaseException:
            self.close()
            raise

    def release(self) -> None:
        """Release only a mutex owned by this scope, then close its handle."""

        if self._handle is None:
            return
        try:
            if self._owned:
                release = ctypes.WinDLL("kernel32", use_last_error=True).ReleaseMutex
                release.argtypes = [ctypes.c_void_p]
                release.restype = wintypes.BOOL
                if not release(self._handle):
                    raise LifecycleMutexError(
                        "owned lifecycle mutex could not be released"
                    )
                self._owned = False
        finally:
            self.close()

    def close(self) -> None:
        """Close the native handle without releasing an unowned mutex."""

        if self._handle is not None:
            if os.name == "nt":
                close = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
                close.argtypes = [ctypes.c_void_p]
                close.restype = wintypes.BOOL
                close(self._handle)
            self._handle = None


ProductionLifecycleMutex = GlobalLifecycleMutex
