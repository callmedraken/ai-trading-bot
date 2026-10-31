"""Immutable cached paper visibility; reading this model performs no I/O."""

from __future__ import annotations

from dataclasses import dataclass

from trading_bot.desktop_paper.configuration import PaperStrategyBinding
from trading_bot.desktop_paper.models import PaperCycleResult, PaperStoreSnapshot
from trading_bot.desktop_runtime import Lifecycle


@dataclass(frozen=True, slots=True)
class DesktopPaperSnapshot:
    binding: PaperStrategyBinding | None = None
    state: Lifecycle = Lifecycle.STOPPED
    activity: str = "SELECTION_REQUIRED"
    diagnostic: str = "PAPER_EVALUATION_SELECTION_REQUIRED"
    financial: PaperStoreSnapshot | None = None
    latest: PaperCycleResult | None = None
    stale: bool = True
    mode: str = "SIMULATED_PAPER"
    purpose: str = "PAPER_EVALUATION"
    source_lane: str = "OPEN_REPLAY"
