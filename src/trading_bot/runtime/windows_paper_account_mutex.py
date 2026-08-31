"""Architecture-94 account mutex; no C2 lifecycle identity or authority."""

from __future__ import annotations

import ctypes
import hashlib
import json
from ctypes import wintypes
from dataclasses import dataclass
from enum import StrEnum
from typing import Self
from uuid import UUID

from trading_bot.runtime.windows_authority import (
    WindowsAuthorityError,
    require_windows_platform,
)
from trading_bot.runtime.windows_authority_security import (
    MUTEX_ALL_ACCESS,
    MUTEX_MODIFY_STATE,
    READ_CONTROL,
    SYNCHRONIZE,
    SecurityAce,
    SecurityObjectType,
    SecurityPolicy,
    build_security_attributes,
    inspect_handle_security,
    is_current_token_administrator,
    is_current_token_elevated,
    resolve_current_token_sid,
)

PAPER_ACCOUNT_MUTEX_LABEL = "manual-paper-account/v1"
PAPER_ACCOUNT_MUTEX_PREFIX = "Global\\AITradingBot-Paper-v1-"
_ADMINISTRATORS = "S-1-5-32-544"
_SYSTEM = "S-1-5-18"
_WAIT_OBJECT = 0
_WAIT_ABANDONED = 0x80
_INFINITE = 0xFFFFFFFF


class PaperAccountMutexError(WindowsAuthorityError):
    """Bounded nonsecret mutex failure, without native error details."""


def canonical_paper_account_mutex_material(paper_account_id: UUID) -> bytes:
    """Return precisely the frozen v1 sorted-key compact UTF-8 material."""
    if type(paper_account_id) is not UUID:
        raise PaperAccountMutexError("paper account ID must be an exact UUID")
    return json.dumps(
        {"label": PAPER_ACCOUNT_MUTEX_LABEL, "paper_account_id": str(paper_account_id)},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def paper_account_mutex_name(paper_account_id: UUID) -> str:
    """Derive one machine-wide name without paths, epochs, or process state."""
    return (
        PAPER_ACCOUNT_MUTEX_PREFIX
        + hashlib.sha256(
            canonical_paper_account_mutex_material(paper_account_id)
        ).hexdigest()
    )


def paper_account_mutex_security_policy(
    trading_sid: str, *, owner_sid: str
) -> SecurityPolicy:
    """Exact protected, noninheriting reviewed kernel-object ACE policy."""
    if trading_sid in {_ADMINISTRATORS, _SYSTEM}:
        raise PaperAccountMutexError("paper mutex Trading principal is invalid")
    if owner_sid not in {_ADMINISTRATORS, _SYSTEM, trading_sid}:
        raise PaperAccountMutexError("paper mutex owner is not approved")
    return SecurityPolicy(
        owner_sid,
        (
            SecurityAce(_ADMINISTRATORS, MUTEX_ALL_ACCESS),
            SecurityAce(_SYSTEM, MUTEX_ALL_ACCESS),
            SecurityAce(trading_sid, MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE),
        ),
    )


def select_paper_account_mutex_owner(
    trading_sid: str,
    current_token_sid: str,
    *,
    token_is_elevated: bool,
    token_is_administrator: bool,
) -> str:
    """Select only an owner assignable by the frozen approved token policy."""
    if current_token_sid in {trading_sid, _SYSTEM}:
        return current_token_sid
    if token_is_elevated and token_is_administrator:
        return _ADMINISTRATORS
    raise PaperAccountMutexError("paper mutex token cannot assign an approved owner")


class PaperAccountMutexState(StrEnum):
    OWNED = "OWNED"
    ABANDONED_OWNER = "ABANDONED_OWNER"


@dataclass(frozen=True, slots=True)
class PaperAccountMutexAcquisition:
    name: str
    state: PaperAccountMutexState

    @property
    def was_abandoned(self) -> bool:
        return self.state is PaperAccountMutexState.ABANDONED_OWNER


class GlobalPaperAccountMutex:
    """Create/open, inspect exact security, wait, release, and close once.

    Acquisition, including WAIT_ABANDONED, is only serialization evidence.
    The caller must completely revalidate the account inside every scope.
    """

    __slots__ = ("_name", "_trading_sid", "_handle", "_owned", "_acquisition")

    def __init__(self, paper_account_id: UUID, *, trading_sid: str) -> None:
        self._name = paper_account_mutex_name(paper_account_id)
        self._trading_sid = trading_sid
        self._handle: int | None = None
        self._owned = False
        self._acquisition: PaperAccountMutexAcquisition | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def acquisition(self) -> PaperAccountMutexAcquisition | None:
        return self._acquisition

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("paper mutex scopes cannot be subclassed")

    def __copy__(self) -> object:
        raise TypeError("paper mutex scopes cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        raise TypeError("paper mutex scopes cannot be copied")

    def __reduce_ex__(self, protocol: int) -> object:
        raise TypeError("paper mutex scopes cannot be serialized")

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        self.release()

    def acquire(self) -> PaperAccountMutexAcquisition:
        """Never steal or bypass a contended mutex; wait without a timeout."""
        if self._handle is not None:
            raise PaperAccountMutexError("paper mutex scope is already active")
        try:
            require_windows_platform()
            token_sid = resolve_current_token_sid()
            owner = select_paper_account_mutex_owner(
                self._trading_sid,
                token_sid,
                token_is_elevated=(
                    False
                    if token_sid in {self._trading_sid, _SYSTEM}
                    else is_current_token_elevated()
                ),
                token_is_administrator=(
                    False
                    if token_sid in {self._trading_sid, _SYSTEM}
                    else is_current_token_administrator()
                ),
            )
            policy = paper_account_mutex_security_policy(
                self._trading_sid, owner_sid=owner
            )
            native = ctypes.WinDLL("kernel32", use_last_error=True)
            create = native.CreateMutexExW
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
                raise PaperAccountMutexError("paper mutex open failed")
            self._handle = int(getattr(handle, "value", handle))
            observed_owner, protected, aces = inspect_handle_security(
                self._handle, SecurityObjectType.KERNEL
            )
            expected = paper_account_mutex_security_policy(
                self._trading_sid, owner_sid=observed_owner
            )
            if protected is not True or aces != expected.aces:
                raise PaperAccountMutexError("paper mutex security mismatch")
            wait = native.WaitForSingleObject
            wait.argtypes = [ctypes.c_void_p, wintypes.DWORD]
            wait.restype = wintypes.DWORD
            result = int(wait(self._handle, _INFINITE))
            if result not in {_WAIT_OBJECT, _WAIT_ABANDONED}:
                raise PaperAccountMutexError("paper mutex wait failed")
            self._owned = True
            self._acquisition = PaperAccountMutexAcquisition(
                self.name,
                PaperAccountMutexState.ABANDONED_OWNER
                if result == _WAIT_ABANDONED
                else PaperAccountMutexState.OWNED,
            )
            return self._acquisition
        except BaseException as error:
            self.release()
            if not isinstance(error, Exception):
                raise
            raise PaperAccountMutexError("paper mutex acquisition failed") from None

    def release(self) -> None:
        """Release ownership and close the handle even if native release fails."""
        handle, owned = self._handle, self._owned
        self._handle = None
        self._owned = False
        self._acquisition = None
        if handle is None:
            return
        failed = False
        try:
            native = ctypes.WinDLL("kernel32", use_last_error=True)
            try:
                if owned:
                    release = native.ReleaseMutex
                    release.argtypes = [ctypes.c_void_p]
                    release.restype = wintypes.BOOL
                    failed = not release(handle)
            finally:
                close = native.CloseHandle
                close.argtypes = [ctypes.c_void_p]
                close.restype = wintypes.BOOL
                failed = not close(handle) or failed
        except Exception:
            failed = True
        if failed:
            raise PaperAccountMutexError(
                "paper mutex release or close failed"
            ) from None
