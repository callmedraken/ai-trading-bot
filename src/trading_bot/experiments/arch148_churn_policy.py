"""Fixed research-only Architecture 148 churn policy variants.

The cooldown concept references Freqtrade at
``a025e7fb3b3acf0e90fd86a9f597aea5b528e1b7`` (GPL-3.0), whose
``CooldownPeriod`` blocks entry for a fixed duration after a trade closes.
Only that behavioral idea is adapted here: the local policy is regime-exit-only,
single-strategy, and reset at the official session boundary. No Freqtrade code
is copied and no dependency is added. QuantConnect/Lean at
``53236fa4a23433a96c7f57cbe7850dba9be840ac`` (Apache-2.0) remains the pinned
fill/fill-forward behavior reference; it does not change this repository's
real-observation-only sparse execution and valuation rules. No source is copied
and no dependency is added from Lean.
"""

from __future__ import annotations

from datetime import timedelta
from enum import Enum

from trading_bot.live_runtime.models import (
    MarketQuality,
    MarketRegime,
    SignalAnalysis,
    TargetPosition,
)
from trading_bot.live_runtime.strategy import confirmed_regime_exit


class ChurnPolicy(Enum):
    """The four predeclared sparse-replay policy variants."""

    CONTROL = "CONTROL"
    OPPOSITE_CONFIRMATION_EXIT = "OPPOSITE_CONFIRMATION_EXIT"
    OPPOSITE_EXIT_COOLDOWN_15M = "OPPOSITE_EXIT_COOLDOWN_15M"
    OPPOSITE_EXIT_COOLDOWN_30M = "OPPOSITE_EXIT_COOLDOWN_30M"

    @property
    def cooldown_duration(self) -> timedelta:
        if self is ChurnPolicy.OPPOSITE_EXIT_COOLDOWN_15M:
            return timedelta(minutes=15)
        if self is ChurnPolicy.OPPOSITE_EXIT_COOLDOWN_30M:
            return timedelta(minutes=30)
        return timedelta()

    def should_exit_regime(self, signal: SignalAnalysis, held: TargetPosition) -> bool:
        """Apply the selected normal regime-exit rule to completed signals."""

        if self is ChurnPolicy.CONTROL:
            return confirmed_regime_exit(signal, held)
        if (
            signal.quality is not MarketQuality.READY
            or signal.latest is None
            or signal.previous is None
            or held not in (TargetPosition.TQQQ, TargetPosition.SQQQ)
            or signal.latest.bar_end - signal.previous.bar_end != timedelta(minutes=5)
        ):
            return False
        opposite = (
            MarketRegime.BEARISH
            if held is TargetPosition.TQQQ
            else MarketRegime.BULLISH
        )
        return (
            signal.latest.candidate is opposite
            and signal.previous.candidate is opposite
        )

    def reversal_source(self, signal: SignalAnalysis) -> MarketRegime | None:
        """Return the confirmed directional source retained for trade audit."""

        if self is ChurnPolicy.CONTROL:
            confirmation = signal.entry_confirmation
            return (
                confirmation
                if confirmation in (MarketRegime.BULLISH, MarketRegime.BEARISH)
                else None
            )
        if (
            signal.quality is MarketQuality.READY
            and signal.latest is not None
            and signal.previous is not None
            and signal.latest.bar_end - signal.previous.bar_end == timedelta(minutes=5)
            and signal.latest.candidate is signal.previous.candidate
            and signal.latest.candidate in (MarketRegime.BULLISH, MarketRegime.BEARISH)
        ):
            return signal.latest.candidate
        return None


CONTROL = ChurnPolicy.CONTROL
OPPOSITE_CONFIRMATION_EXIT = ChurnPolicy.OPPOSITE_CONFIRMATION_EXIT
OPPOSITE_EXIT_COOLDOWN_15M = ChurnPolicy.OPPOSITE_EXIT_COOLDOWN_15M
OPPOSITE_EXIT_COOLDOWN_30M = ChurnPolicy.OPPOSITE_EXIT_COOLDOWN_30M
CHURN_POLICIES = (
    CONTROL,
    OPPOSITE_CONFIRMATION_EXIT,
    OPPOSITE_EXIT_COOLDOWN_15M,
    OPPOSITE_EXIT_COOLDOWN_30M,
)

__all__ = [
    "CHURN_POLICIES",
    "CONTROL",
    "OPPOSITE_CONFIRMATION_EXIT",
    "OPPOSITE_EXIT_COOLDOWN_15M",
    "OPPOSITE_EXIT_COOLDOWN_30M",
    "ChurnPolicy",
]
