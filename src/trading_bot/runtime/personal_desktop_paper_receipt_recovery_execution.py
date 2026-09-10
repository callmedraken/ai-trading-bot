"""Source-owned PD3 receipt-recovery effect gate.

PD3-D1 supplies only the disabled gate and error boundary needed by later
recovery composition.  It performs no qualification, reconstruction, recovery,
or Paper-v2 output effect.
"""

from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
)

PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED = False


class PersonalDesktopPaperReceiptRecoveryExecutionError(
    PersonalDesktopPaperAccountError
):
    """A personal-desktop receipt-recovery execution failed closed."""


class PersonalDesktopPaperReceiptRecoveryEffectsDisabledError(
    PersonalDesktopPaperReceiptRecoveryExecutionError
):
    """The dedicated receipt-recovery production-effect gate is disabled."""
