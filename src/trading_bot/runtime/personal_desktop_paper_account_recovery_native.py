"""Source-disabled, fixed-name, single-attempt recovery rename only."""

from __future__ import annotations

import ctypes

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
)
from trading_bot.runtime.windows_authority import (
    AuthorityObjectError,
    require_windows_platform,
)


def _require_gates() -> None:
    if security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is not True:
        raise PersonalDesktopPaperAccountError("recovery effects are disabled")
    if security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is not False:
        raise PersonalDesktopPaperAccountError("original publisher must be disarmed")


class WindowsPaperRecoveryFinalizeApi:
    """No path arguments or other effects. A failed move consumes this instance.

    Admission, pinned-parent trust and complete verification belong to the
    production finalizer. This wrapper never provides a retry/recovery permit.
    """

    def __init__(self) -> None:
        _require_gates()
        require_windows_platform()
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._attempted = False

    def rename_no_clobber(self) -> None:
        _require_gates()
        if self._attempted:
            raise AuthorityObjectError("recovery rename attempt already consumed")
        self._attempted = True  # Before binding/invocation, including response loss.
        move = self._kernel.MoveFileExW
        move.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        move.restype = ctypes.c_int32
        # Same parent/volume, WRITE_THROUGH only: no replace, copy or delayed move.
        if not move(
            security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT,
            security.PERSONAL_DESKTOP_PAPER_V2_ROOT,
            0x8,
        ):
            raise AuthorityObjectError("recovery same-parent no-clobber rename failed")
