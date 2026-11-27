"""Research-only adapter for typed Architecture 149 monthly targets.

This module preserves Arch149's frozen replay as the sole ranking authority. It
does not expose the replay's returns, holdings, or fills to the Portfolio
Manager, and its signals remain unadmitted research inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.experiments.arch149_monthly_defensive_rotation import (
    STRATEGY_ID,
    MonthlyTarget,
    RotationReplay,
    TargetResolution,
    monthly_rotation_identity,
    verify_rotation_replay_identity,
)
from trading_bot.experiments.filtered_trend_data import UNIVERSE
from trading_bot.portfolio_manager.decision import MarketSignal


class Arch149EvidenceStatus(StrEnum):
    """Evidence state exposed by this source-only adapter."""

    UNADMITTED = "UNADMITTED"


class Arch149AuthorityStatus(StrEnum):
    """Authority ceiling for adapted Arch149 signal facts."""

    RESEARCH_SIGNAL_ONLY_NO_ORDER_AUTHORITY = "RESEARCH_SIGNAL_ONLY_NO_ORDER_AUTHORITY"


@dataclass(frozen=True, slots=True)
class Arch149SignalBatch:
    """Identity-bound target facts without strategy-performance authority."""

    strategy_id: str
    source_replay_id: str
    target_sequence_identity: str
    targets: tuple[MonthlyTarget, ...]
    evidence_status: Arch149EvidenceStatus = Arch149EvidenceStatus.UNADMITTED

    def __post_init__(self) -> None:
        if self.strategy_id != STRATEGY_ID:
            raise ValueError("Arch149 signal batch must name the frozen strategy")
        for name in ("source_replay_id", "target_sequence_identity"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonblank")
        if type(self.targets) is not tuple or any(
            type(target) is not MonthlyTarget for target in self.targets
        ):
            raise TypeError(
                "targets must be an immutable tuple of MonthlyTarget values"
            )
        dates = tuple(target.signal_date for target in self.targets)
        if not dates or dates != tuple(sorted(set(dates))):
            raise ValueError(
                "Arch149 targets must be nonempty and chronologically unique"
            )
        if self.evidence_status is not Arch149EvidenceStatus.UNADMITTED:
            raise ValueError("PM1 cannot admit Architecture 149 evidence")

    @property
    def authority_status(self) -> Arch149AuthorityStatus:
        return Arch149AuthorityStatus.RESEARCH_SIGNAL_ONLY_NO_ORDER_AUTHORITY

    @property
    def performance_evidence_available(self) -> bool:
        return False

    @property
    def order_authority(self) -> bool:
        return False

    @property
    def identity(self) -> UUID:
        return UUID(
            monthly_rotation_identity(
                "portfolio-manager-arch149-signal-batch/v1",
                (
                    self.strategy_id,
                    self.source_replay_id,
                    self.target_sequence_identity,
                    tuple(target.identity for target in self.targets),
                ),
            )
        )

    def target_for(self, signal_date: date) -> MonthlyTarget | None:
        """Return the frozen target fact for one exact signal date."""
        if type(signal_date) is not date:
            raise TypeError("signal_date must be a date")
        return next(
            (target for target in self.targets if target.signal_date == signal_date),
            None,
        )

    def market_signals_for(self, signal_date: date) -> tuple[MarketSignal, ...]:
        """Translate one target into non-authoritative PM research diagnostics."""
        target = self.target_for(signal_date)
        if target is None:
            raise KeyError("no Arch149 target exists for the requested signal date")
        scores = dict(target.ranked_scores)
        target_text = target.target if target.target is not None else "UNAVAILABLE"
        next_session = (
            target.next_session.isoformat()
            if target.next_session is not None
            else "NONE"
        )
        rationale = (
            f"Arch149 {self.strategy_id} target={target_text}; "
            f"resolution={target.resolution.value}; next_session={next_session}; "
            "evidence is unadmitted and cannot authorize an order."
        )
        return tuple(
            MarketSignal(
                symbol=Symbol(symbol),
                score=scores.get(symbol),
                rationale=rationale,
                evidence_available=False,
            )
            for symbol in UNIVERSE
        )


def adapt_arch149_replay(replay: RotationReplay) -> Arch149SignalBatch:
    """Expose only verified typed target facts from the immutable Arch149 replay."""
    if type(replay) is not RotationReplay:
        raise TypeError("replay must be an exact RotationReplay value")
    if (
        replay.strategy_id != STRATEGY_ID
        or not verify_rotation_replay_identity(replay)
        or any(
            type(target.resolution) is not TargetResolution for target in replay.targets
        )
    ):
        raise ValueError("Arch149 replay identity or target contract is invalid")
    return Arch149SignalBatch(
        strategy_id=replay.strategy_id,
        source_replay_id=replay.identity,
        target_sequence_identity=replay.target_sequence_identity,
        targets=replay.targets,
    )
