"""Account-scoped Windows mutex and supervised paper-cycle admission.

The composition order encoded by this scope is: genuine registered C1/Trading
paper authority establishes the immutable account ID; acquire its mutex; while
held, reread/revalidate mutable authoritative lineage and tip; perform future
strategy/plan/risk/simulated execution; commit the future Architecture-67
transition; commit its receipt or complete zero-runtime recovery/reconciliation;
then release only after that terminal durable outcome.  The immutable pre-lock
read is never the mutable state snapshot used by a future writer.

PD2A deliberately stops immediately after mutex admission and performs none of
the mutable reread, execution, transition, receipt, or recovery effects.
"""

from __future__ import annotations

import ctypes
import os
import re
import threading
from ctypes import wintypes
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Protocol, Self

from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    ValidatedPersonalDesktopPaperAccount,
    require_validated_personal_desktop_paper_account,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_qualification import (
    PaperReceiptRecoveryQualificationResult,
    require_validated_paper_receipt_recovery_qualification,
)
from trading_bot.runtime.windows_authority import require_windows_platform
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

PAPER_ACCOUNT_MUTEX_LABEL = "personal-desktop-paper-account-mutex/v1"
PAPER_ACCOUNT_MUTEX_PREFIX = "Global\\AITradingBot-PaperAccount-v1-"
PAPER_ACCOUNT_MUTEX_WAIT_MILLISECONDS = 30_000

WAIT_OBJECT_0 = 0
WAIT_ABANDONED_0 = 0x80
WAIT_TIMEOUT = 0x102
WAIT_FAILED = 0xFFFFFFFF
INFINITE = 0xFFFFFFFF

ADMINISTRATORS_SID = "S-1-5-32-544"
SYSTEM_SID = "S-1-5-18"
_CANONICAL_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


class PaperAccountMutexError(RuntimeError):
    """Base failure for paper-account mutex admission."""


class PaperAccountMutexSecurityError(PaperAccountMutexError):
    """The creator or kernel-object security policy is not exact."""


class PaperAccountMutexBusyError(PaperAccountMutexError):
    """The source-bounded wait expired without acquiring ownership."""


class PaperAccountMutexWaitError(PaperAccountMutexError):
    """The native wait failed or returned an unknown state."""


class PaperAccountMutexReentrantError(PaperAccountMutexError):
    """This process already has an active admission for the account."""


class PaperAccountMutexReleaseError(PaperAccountMutexError):
    """An owned mutex could not be released cleanly."""


class PaperAccountMutexPoisonedError(PaperAccountMutexError):
    """The account is blocked after uncertain mutex release ownership."""


def _canonical_paper_account_id(paper_account_id: str) -> str:
    if (
        type(paper_account_id) is not str
        or _CANONICAL_UUID.fullmatch(paper_account_id) is None
    ):
        raise PaperAccountMutexError(
            "paper_account_id must be exact canonical lowercase UUID text"
        )
    return paper_account_id


def canonical_paper_account_mutex_material(paper_account_id: str) -> bytes:
    """Return length-framed label/account identity bytes and nothing else."""

    account_id = _canonical_paper_account_id(paper_account_id)
    parts = (PAPER_ACCOUNT_MUTEX_LABEL, account_id)
    return "".join(f"{len(part.encode('utf-8'))}:{part}" for part in parts).encode(
        "utf-8"
    )


def paper_account_mutex_digest(paper_account_id: str) -> str:
    """Return the lowercase SHA-256 suffix for one canonical account ID."""

    return sha256(canonical_paper_account_mutex_material(paper_account_id)).hexdigest()


def paper_account_mutex_name(paper_account_id: str) -> str:
    """Return the source-owned Global mutex name for one account."""

    return PAPER_ACCOUNT_MUTEX_PREFIX + paper_account_mutex_digest(paper_account_id)


def paper_account_mutex_security_policy(
    trading_sid: str, *, owner_sid: str
) -> SecurityPolicy:
    """Build the exact protected kernel-object owner/DACL policy."""

    aces = (
        SecurityAce(ADMINISTRATORS_SID, MUTEX_ALL_ACCESS),
        SecurityAce(SYSTEM_SID, MUTEX_ALL_ACCESS),
        SecurityAce(trading_sid, MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE),
    )
    if owner_sid not in {trading_sid, SYSTEM_SID, ADMINISTRATORS_SID}:
        raise PaperAccountMutexSecurityError("paper mutex owner is not approved")
    return SecurityPolicy(owner_sid, aces)


class _PaperAccountMutexNativeApi(Protocol):
    """Small injectable Win32 kernel boundary used by the mutex scope."""

    def creator_owner_sid(
        self, trading_sid: str, *, allow_elevated_administrator: bool
    ) -> str: ...

    def create_mutex(self, name: str, policy: SecurityPolicy) -> int: ...

    def inspect_mutex(
        self, handle: int
    ) -> tuple[str, bool, tuple[SecurityAce, ...]]: ...

    def wait(self, handle: int, milliseconds: int) -> int: ...

    def release(self, handle: int) -> bool: ...

    def close(self, handle: int) -> None: ...


class _WindowsPaperAccountMutexNativeApi:
    """Production ctypes implementation; it accepts no caller native handle."""

    def creator_owner_sid(
        self, trading_sid: str, *, allow_elevated_administrator: bool
    ) -> str:
        require_windows_platform()
        current_sid = resolve_current_token_sid()
        if current_sid == trading_sid:
            return trading_sid
        if current_sid == SYSTEM_SID:
            return SYSTEM_SID
        if (
            allow_elevated_administrator
            and is_current_token_elevated()
            and is_current_token_administrator()
        ):
            return ADMINISTRATORS_SID
        raise PaperAccountMutexSecurityError(
            "current token cannot create the paper-account mutex"
        )

    def create_mutex(self, name: str, policy: SecurityPolicy) -> int:
        require_windows_platform()
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
                name,
                0,
                MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE,
            )
        value = int(getattr(handle, "value", handle) or 0)
        if not value:
            raise PaperAccountMutexSecurityError(
                "paper-account mutex could not be created or opened"
            )
        return value

    def inspect_mutex(self, handle: int) -> tuple[str, bool, tuple[SecurityAce, ...]]:
        return inspect_handle_security(handle, SecurityObjectType.KERNEL)

    def wait(self, handle: int, milliseconds: int) -> int:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        wait = kernel32.WaitForSingleObject
        wait.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        wait.restype = wintypes.DWORD
        return int(wait(handle, milliseconds))

    def release(self, handle: int) -> bool:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        release = kernel32.ReleaseMutex
        release.argtypes = [ctypes.c_void_p]
        release.restype = wintypes.BOOL
        return bool(release(handle))

    def close(self, handle: int) -> None:
        if os.name != "nt":  # pragma: no cover - production class is Windows-only
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        close = kernel32.CloseHandle
        close.argtypes = [ctypes.c_void_p]
        close.restype = wintypes.BOOL
        close(handle)


class PaperAccountMutexState(StrEnum):
    OWNED = "OWNED"
    ABANDONED_OWNER = "ABANDONED_OWNER"


@dataclass(frozen=True, slots=True)
class PaperAccountMutexAcquisition:
    """Immutable acquisition evidence preserving abandoned ownership."""

    paper_account_id: str
    name: str
    digest: str
    state: PaperAccountMutexState

    @property
    def was_abandoned(self) -> bool:
        return self.state is PaperAccountMutexState.ABANDONED_OWNER


_ACTIVE_ACCOUNT_MUTEXES: set[str] = set()
_POISONED_ACCOUNT_MUTEXES: set[str] = set()
_ACTIVE_ACCOUNT_MUTEXES_LOCK = threading.Lock()


class _PaperAccountMutex:
    """Low-level source-named mutex with process-wide account non-reentrancy."""

    def __init__(
        self,
        paper_account_id: str,
        trading_sid: str,
        *,
        _api: _PaperAccountMutexNativeApi | None = None,
        _allow_elevated_administrative_creator: bool = False,
    ) -> None:
        self.paper_account_id = _canonical_paper_account_id(paper_account_id)
        self.digest = paper_account_mutex_digest(self.paper_account_id)
        self.name = PAPER_ACCOUNT_MUTEX_PREFIX + self.digest
        self._trading_sid = trading_sid
        self._api = _api or _WindowsPaperAccountMutexNativeApi()
        self._allow_admin = _allow_elevated_administrative_creator
        self._handle: int | None = None
        self._owns_mutex = False
        self._reserved = False
        self.acquisition: PaperAccountMutexAcquisition | None = None

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()

    def acquire(self) -> PaperAccountMutexAcquisition:
        if self._handle is not None or self._reserved:
            raise PaperAccountMutexReentrantError(
                "paper-account mutex scope is already active"
            )
        with _ACTIVE_ACCOUNT_MUTEXES_LOCK:
            if self.digest in _POISONED_ACCOUNT_MUTEXES:
                raise PaperAccountMutexPoisonedError(
                    "paper account mutex ownership is uncertain after release failure"
                )
            if self.digest in _ACTIVE_ACCOUNT_MUTEXES:
                raise PaperAccountMutexReentrantError(
                    "paper account already has an active in-process mutex scope"
                )
            _ACTIVE_ACCOUNT_MUTEXES.add(self.digest)
            self._reserved = True
        try:
            owner_sid = self._api.creator_owner_sid(
                self._trading_sid,
                allow_elevated_administrator=self._allow_admin,
            )
            if owner_sid == ADMINISTRATORS_SID and not self._allow_admin:
                raise PaperAccountMutexSecurityError(
                    "administrative paper mutex creation was not explicitly allowed"
                )
            policy = paper_account_mutex_security_policy(
                self._trading_sid, owner_sid=owner_sid
            )
            self._handle = self._api.create_mutex(self.name, policy)
            owner, protected, aces = self._api.inspect_mutex(self._handle)
            allowed_owners = {self._trading_sid, SYSTEM_SID}
            if self._allow_admin:
                allowed_owners.add(ADMINISTRATORS_SID)
            expected_aces = paper_account_mutex_security_policy(
                self._trading_sid, owner_sid=owner
            ).aces
            if owner not in allowed_owners or not protected or aces != expected_aces:
                raise PaperAccountMutexSecurityError(
                    "paper-account mutex kernel security is unexpected"
                )
            result = self._api.wait(self._handle, PAPER_ACCOUNT_MUTEX_WAIT_MILLISECONDS)
            if result == WAIT_TIMEOUT:
                raise PaperAccountMutexBusyError(
                    "paper-account mutex remained busy for the fixed wait bound"
                )
            if result == WAIT_FAILED:
                raise PaperAccountMutexWaitError("paper-account mutex wait failed")
            if result not in {WAIT_OBJECT_0, WAIT_ABANDONED_0}:
                raise PaperAccountMutexWaitError(
                    "paper-account mutex returned an unexpected wait state"
                )
            self._owns_mutex = True
            state = (
                PaperAccountMutexState.ABANDONED_OWNER
                if result == WAIT_ABANDONED_0
                else PaperAccountMutexState.OWNED
            )
            self.acquisition = PaperAccountMutexAcquisition(
                self.paper_account_id, self.name, self.digest, state
            )
            return self.acquisition
        except BaseException:
            self._close_and_unreserve()
            raise

    def release(self) -> None:
        if self._handle is None:
            self._unreserve()
            return
        if self._owns_mutex and not self._api.release(self._handle):
            self._close_and_poison()
            raise PaperAccountMutexReleaseError(
                "owned paper-account mutex could not be released"
            )
        if self._owns_mutex:
            self._owns_mutex = False
        self._close_and_unreserve()

    def _close_and_poison(self) -> None:
        handle, self._handle = self._handle, None
        with _ACTIVE_ACCOUNT_MUTEXES_LOCK:
            _POISONED_ACCOUNT_MUTEXES.add(self.digest)
            _ACTIVE_ACCOUNT_MUTEXES.discard(self.digest)
            self._reserved = False
        try:
            if handle is not None:
                self._api.close(handle)
        finally:
            self._owns_mutex = False

    def _close_and_unreserve(self) -> None:
        handle, self._handle = self._handle, None
        try:
            if handle is not None:
                self._api.close(handle)
        finally:
            self._owns_mutex = False
            self._unreserve()

    def _unreserve(self) -> None:
        if not self._reserved:
            return
        with _ACTIVE_ACCOUNT_MUTEXES_LOCK:
            _ACTIVE_ACCOUNT_MUTEXES.discard(self.digest)
            self._reserved = False


_ADMISSION_KEY = object()
_RECOVERY_ADMISSION_KEY = object()


class SupervisedPaperCycleAdmission:
    """Held PD2A admission; no paper state or Architecture-67 effect occurs."""

    def __init__(self, mutex: _PaperAccountMutex, *, _key: object) -> None:
        if _key is not _ADMISSION_KEY:
            raise PaperAccountMutexError(
                "supervised admission requires registered production authority"
            )
        self._mutex = mutex

    @property
    def acquisition(self) -> PaperAccountMutexAcquisition | None:
        return self._mutex.acquisition

    def __enter__(self) -> Self:
        self._mutex.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._mutex.release()


class PaperReceiptRecoveryAdmission:
    """Held PD3 admission derived only from registered recovery evidence."""

    def __init__(self, mutex: _PaperAccountMutex, *, _key: object) -> None:
        if _key is not _RECOVERY_ADMISSION_KEY:
            raise PaperAccountMutexError(
                "receipt-recovery admission requires registered production authority"
            )
        self._mutex = mutex

    @property
    def acquisition(self) -> PaperAccountMutexAcquisition | None:
        return self._mutex.acquisition

    def __enter__(self) -> Self:
        self._mutex.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._mutex.release()


def supervised_paper_cycle_admission(
    authority: ValidatedPersonalDesktopPaperAccount,
) -> SupervisedPaperCycleAdmission:
    """Admit only a genuine registered account and derive its exact mutex.

    The validated read establishes immutable ``paper_account_id`` only.  Future
    PD2 must reread/revalidate mutable lineage and tip after ``__enter__`` and
    before any mutation, then keep this admission held through terminal durable
    receipt commitment or zero-runtime reconciliation.
    """

    return _supervised_paper_cycle_admission(
        authority, api=_WindowsPaperAccountMutexNativeApi()
    )


def _supervised_paper_cycle_admission(
    authority: ValidatedPersonalDesktopPaperAccount,
    *,
    api: _PaperAccountMutexNativeApi,
) -> SupervisedPaperCycleAdmission:
    evidence = require_validated_personal_desktop_paper_account(authority)
    mutex = _PaperAccountMutex(
        evidence.anchor.paper_account_id,
        evidence.anchor.approved_trading_sid,
        _api=api,
    )
    return SupervisedPaperCycleAdmission(mutex, _key=_ADMISSION_KEY)


def paper_receipt_recovery_admission(
    qualification: PaperReceiptRecoveryQualificationResult,
) -> PaperReceiptRecoveryAdmission:
    """Admit only genuine recoverable PD3-B evidence to the existing mutex."""

    return _paper_receipt_recovery_admission(
        qualification, api=_WindowsPaperAccountMutexNativeApi()
    )


def _paper_receipt_recovery_admission(
    qualification: PaperReceiptRecoveryQualificationResult,
    *,
    api: _PaperAccountMutexNativeApi,
) -> PaperReceiptRecoveryAdmission:
    evidence = require_validated_paper_receipt_recovery_qualification(qualification)
    mutex = _PaperAccountMutex(
        evidence.account.anchor.paper_account_id,
        evidence.account.anchor.approved_trading_sid,
        _api=api,
    )
    return PaperReceiptRecoveryAdmission(mutex, _key=_RECOVERY_ADMISSION_KEY)
