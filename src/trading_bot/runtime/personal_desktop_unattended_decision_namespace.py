"""Trading-principal read-only qualification of the fixed decision namespace."""

from __future__ import annotations

from enum import StrEnum

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObservation,
    TradingTokenObserver,
    WindowsTradingTokenObserver,
    require_trading_token,
)


class TradingDecisionNamespaceClassification(StrEnum):
    """Diagnostic evidence only; no filesystem or provisioning authority."""

    MISSING = "MISSING"
    PRESENT_VALID = "PRESENT_VALID"
    BLOCKED = "BLOCKED"


def qualify_trading_unattended_decision_namespace() -> (
    TradingDecisionNamespaceClassification
):
    """Inventory and pin the source-owned namespace without mutation."""
    try:
        observer = WindowsTradingTokenObserver()
        initial = observer.observe()
        require_trading_token(
            PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
            initial,
        )
        return _qualify(observer, security.WindowsPaperReadNativeApi(), initial=initial)
    except Exception:
        return TradingDecisionNamespaceClassification.BLOCKED


def qualify_trading_unattended_decision_namespace_for_test(
    token_observer: TradingTokenObserver, native_api: security.PaperReadNativeApi
) -> TradingDecisionNamespaceClassification:
    """Disposable native seams; never needed by the production entry point."""
    return _qualify(token_observer, native_api)


def _qualify(
    observer: TradingTokenObserver,
    api: security.PaperReadNativeApi,
    *,
    initial: TradingTokenObservation | None = None,
) -> TradingDecisionNamespaceClassification:
    sid = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid
    try:
        if initial is None:
            initial = observer.observe()
        require_trading_token(sid, initial)
        with security.PinnedTradingPaperReadSession(api, sid) as session:
            names = session.names(security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME)
            if any(name != name.rstrip(" .") for name in names):
                raise ValueError("runtime inventory contains ambiguous Win32 names")
            matches = tuple(n for n in names if n.casefold() == "unattended-decisions")
            if not matches:
                classification = TradingDecisionNamespaceClassification.MISSING
            elif matches == ("unattended-decisions",):
                pinned = session.pin(
                    security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS
                )
                if (
                    pinned.spec.role
                    is not security.PaperObjectRole.UNATTENDED_DECISIONS
                ):
                    raise ValueError("decision namespace role is invalid")
                classification = TradingDecisionNamespaceClassification.PRESENT_VALID
            else:
                raise ValueError("decision namespace spelling is ambiguous")
            # Context exit independently reopens every pinned object and checks
            # parent inventory, security, identity and reparse drift.
        final = observer.observe()
        require_trading_token(sid, final)
        if final != initial:
            raise ValueError("Trading token changed during namespace qualification")
        return classification
    except Exception:
        return TradingDecisionNamespaceClassification.BLOCKED
