"""Read-only Paper-v2 qualification for a missing terminal receipt.

The production boundary accepts only genuine C1 provenance and the fixed
Trading-readable Paper-v2 namespace.  A qualified result is point-in-time
evidence only: it carries no path, handle, output capability, operation ID, or
filesystem mutation authority.
"""

from __future__ import annotations

import threading
import weakref
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    IdentifiedMarketCalendar,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    PersonalDesktopPaperAccountRecoveryReadEvidence,
    verify_personal_desktop_paper_account_recovery_read,
)
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PaperReadNativeApi,
    WindowsPaperReadNativeApi,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObserver,
    WindowsTradingTokenObserver,
    require_trading_token,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)


class PaperReceiptRecoveryQualificationStatus(StrEnum):
    """Read-only classification of the complete installed Paper-v2 account."""

    NO_RECOVERY_REQUIRED = "NO_RECOVERY_REQUIRED"
    RECEIPT_RECOVERY_REQUIRED = "RECEIPT_RECOVERY_REQUIRED"
    BLOCKED = "BLOCKED"


class PaperReceiptRecoveryQualificationDiagnostic(StrEnum):
    """Sanitized explanation for one qualification classification."""

    VERIFIED_COMPLETE_ACCOUNT = "VERIFIED_COMPLETE_ACCOUNT"
    VERIFIED_TERMINAL_RECEIPT_MISSING = "VERIFIED_TERMINAL_RECEIPT_MISSING"
    VERIFICATION_BLOCKED = "VERIFICATION_BLOCKED"


@dataclass(frozen=True, slots=True, eq=False, weakref_slot=True)
class PaperReceiptRecoveryQualificationResult:
    """Immutable non-authorizing result; production provenance is opaque."""

    status: PaperReceiptRecoveryQualificationStatus
    diagnostic: PaperReceiptRecoveryQualificationDiagnostic
    paper_account_id: str | None
    terminal_checkpoint_id: UUID | None
    missing_application_id: UUID | None
    predecessor_checkpoint_id: UUID | None

    def __post_init__(self) -> None:
        blocked = self.status is PaperReceiptRecoveryQualificationStatus.BLOCKED
        recovery = (
            self.status
            is PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
        )
        expected_diagnostic = {
            PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED: (
                PaperReceiptRecoveryQualificationDiagnostic.VERIFIED_COMPLETE_ACCOUNT
            ),
            PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED: (
                PaperReceiptRecoveryQualificationDiagnostic.VERIFIED_TERMINAL_RECEIPT_MISSING
            ),
            PaperReceiptRecoveryQualificationStatus.BLOCKED: (
                PaperReceiptRecoveryQualificationDiagnostic.VERIFICATION_BLOCKED
            ),
        }.get(self.status)
        if (
            type(self.status) is not PaperReceiptRecoveryQualificationStatus
            or type(self.diagnostic) is not PaperReceiptRecoveryQualificationDiagnostic
            or self.diagnostic is not expected_diagnostic
            or (blocked != (self.paper_account_id is None))
            or (blocked != (self.terminal_checkpoint_id is None))
            or (recovery != (self.missing_application_id is not None))
            or (recovery != (self.predecessor_checkpoint_id is not None))
            or (
                self.paper_account_id is not None
                and (
                    type(self.paper_account_id) is not str or not self.paper_account_id
                )
            )
            or (
                self.terminal_checkpoint_id is not None
                and type(self.terminal_checkpoint_id) is not UUID
            )
            or (
                self.missing_application_id is not None
                and type(self.missing_application_id) is not UUID
            )
            or (
                self.predecessor_checkpoint_id is not None
                and type(self.predecessor_checkpoint_id) is not UUID
            )
        ):
            raise ValueError("Paper-v2 receipt-recovery qualification is invalid")


_REGISTRY: weakref.WeakKeyDictionary[
    PaperReceiptRecoveryQualificationResult,
    PersonalDesktopPaperAccountRecoveryReadEvidence,
] = weakref.WeakKeyDictionary()
_REGISTRY_LOCK = threading.Lock()


def require_validated_paper_receipt_recovery_qualification(
    qualification: PaperReceiptRecoveryQualificationResult,
) -> PersonalDesktopPaperAccountRecoveryReadEvidence:
    """Require genuine production issuance for a recoverable terminal edge."""

    with _REGISTRY_LOCK:
        if (
            type(qualification) is not PaperReceiptRecoveryQualificationResult
            or qualification.status
            is not PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
            or qualification not in _REGISTRY
        ):
            raise PersonalDesktopPaperAccountError(
                "receipt recovery lacks validated production qualification"
            )
        return _REGISTRY[qualification]


def qualify_personal_desktop_paper_receipt_recovery(
    authority: ValidatedProductionAuthority,
    *,
    historical_cycle_configuration_payloads: tuple[bytes, ...] = (),
) -> PaperReceiptRecoveryQualificationResult:
    """Qualify the fixed installed account without opening any write boundary."""

    try:
        c1 = require_validated_production_authority(authority)
        observer = WindowsTradingTokenObserver()
        recovery_read = _perform_recovery_read(
            c1.machine_authority_id,
            c1.approved_account_sid,
            api=None,
            observer=observer,
            calendar=BoundMarketCalendar(
                XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()
            ),
            configurations=historical_cycle_configuration_payloads,
        )
        require_validated_production_authority(c1)
    except Exception:
        return _blocked_result()
    result = _result_from_verified_read(recovery_read)
    if (
        result.status
        is PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
    ):
        with _REGISTRY_LOCK:
            _REGISTRY[result] = recovery_read
    return result


def _qualify_personal_desktop_paper_receipt_recovery_for_test(
    machine_authority_id: str,
    trading_sid: str,
    *,
    api: PaperReadNativeApi,
    observer: TradingTokenObserver,
    calendar: IdentifiedMarketCalendar,
    configurations: tuple[bytes, ...] = (),
) -> PaperReceiptRecoveryQualificationResult:
    """Exercise disposable read seams without minting production provenance."""

    try:
        recovery_read = _perform_recovery_read(
            machine_authority_id,
            trading_sid,
            api=api,
            observer=observer,
            calendar=calendar,
            configurations=configurations,
        )
    except Exception:
        return _blocked_result()
    return _result_from_verified_read(recovery_read)


def _perform_recovery_read(
    machine_authority_id: str,
    trading_sid: str,
    *,
    api: PaperReadNativeApi | None,
    observer: TradingTokenObserver,
    calendar: IdentifiedMarketCalendar,
    configurations: tuple[bytes, ...],
) -> PersonalDesktopPaperAccountRecoveryReadEvidence:
    """Hold exact token observations around the complete pinned read interval."""

    initial_token = observer.observe()
    require_trading_token(trading_sid, initial_token)
    try:
        read_api = WindowsPaperReadNativeApi() if api is None else api
        return verify_personal_desktop_paper_account_recovery_read(
            machine_authority_id,
            trading_sid,
            api=read_api,
            observer=observer,
            calendar=calendar,
            configurations=configurations,
        )
    finally:
        final_token = observer.observe()
        require_trading_token(trading_sid, final_token)
        if final_token != initial_token:
            raise PersonalDesktopPaperAccountError(
                "Trading token changed during recovery qualification"
            )


def _result_from_verified_read(
    recovery_read: PersonalDesktopPaperAccountRecoveryReadEvidence,
) -> PaperReceiptRecoveryQualificationResult:
    account = recovery_read.account
    diagnostics = PaperReceiptRecoveryQualificationDiagnostic
    if recovery_read.missing_application_id is None:
        status = PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED
        diagnostic = diagnostics.VERIFIED_COMPLETE_ACCOUNT
    else:
        status = PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
        diagnostic = diagnostics.VERIFIED_TERMINAL_RECEIPT_MISSING
    return PaperReceiptRecoveryQualificationResult(
        status=status,
        diagnostic=diagnostic,
        paper_account_id=account.anchor.paper_account_id,
        terminal_checkpoint_id=account.lineage.terminal_checkpoint_id,
        missing_application_id=recovery_read.missing_application_id,
        predecessor_checkpoint_id=recovery_read.missing_predecessor_checkpoint_id,
    )


def _blocked_result() -> PaperReceiptRecoveryQualificationResult:
    return PaperReceiptRecoveryQualificationResult(
        status=PaperReceiptRecoveryQualificationStatus.BLOCKED,
        diagnostic=PaperReceiptRecoveryQualificationDiagnostic.VERIFICATION_BLOCKED,
        paper_account_id=None,
        terminal_checkpoint_id=None,
        missing_application_id=None,
        predecessor_checkpoint_id=None,
    )
