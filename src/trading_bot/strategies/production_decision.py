"""Pure production-strategy decision bridge.

This module binds one session-scoped production strategy contract to the already
verified Architecture-94 daily strategy-decision path. It adds no provider,
paper-store, risk, scheduler, clock, research, or execution capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from trading_bot.domain import TradeProposal
from trading_bot.market_data import IdentifiedMarketCalendar
from trading_bot.strategies.daily_decision import PreparedCurrentStrategyDecision
from trading_bot.strategies.history_seed import VerifiedStrategyHistorySeed
from trading_bot.strategies.production import ProductionStrategyContract

if TYPE_CHECKING:
    from trading_bot.runtime.manual_paper_strategy_plan import (
        ManualPaperStrategyDecisionRequest,
        PreparedManualPaperStrategyDecision,
    )


def build_manual_paper_strategy_decision(
    request: ManualPaperStrategyDecisionRequest,
    calendar: IdentifiedMarketCalendar,
) -> PreparedManualPaperStrategyDecision:
    """Retain the legacy builder seam, loading historical code only for legacy use."""
    from trading_bot.runtime.manual_paper_strategy_plan import (
        build_manual_paper_strategy_decision as legacy_builder,
    )

    return legacy_builder(request, calendar)


def _legacy_prepared_type():
    from trading_bot.runtime.manual_paper_strategy_plan import (
        PreparedManualPaperStrategyDecision,
    )

    return PreparedManualPaperStrategyDecision


def _legacy_signal_matches(prepared, proposal_present: bool) -> bool:
    from trading_bot.runtime.manual_paper_strategy_plan import (
        ManualPaperStrategySignalStatus,
    )

    expected = (
        ManualPaperStrategySignalStatus.TRADE_PROPOSAL
        if proposal_present
        else ManualPaperStrategySignalStatus.NO_SIGNAL
    )
    return prepared.signal_status is expected


class ProductionStrategyDecisionStatus(StrEnum):
    """Closed production decision outcomes before provider/risk/execution."""

    NO_SIGNAL = "NO_SIGNAL"
    TRADE_PROPOSAL = "TRADE_PROPOSAL"


@dataclass(frozen=True, slots=True)
class ProductionStrategyDecision:
    """Exact retained production contract plus one verified strategy decision."""

    contract: ProductionStrategyContract
    prepared: PreparedManualPaperStrategyDecision | PreparedCurrentStrategyDecision
    status: ProductionStrategyDecisionStatus
    proposal: TradeProposal | None

    def __post_init__(self) -> None:
        if type(self.contract) is not ProductionStrategyContract:
            raise TypeError("contract must be exactly ProductionStrategyContract")
        current = type(self.prepared) is PreparedCurrentStrategyDecision
        if not current and type(self.prepared) is not _legacy_prepared_type():
            raise TypeError(
                "prepared must be exactly PreparedManualPaperStrategyDecision"
            )
        if type(self.status) is not ProductionStrategyDecisionStatus:
            raise TypeError("status must be exactly ProductionStrategyDecisionStatus")
        if (
            self.prepared.strategy_config != self.contract.strategy_config
            or self.prepared.symbol != self.contract.symbol
            or self.prepared.intended_execution_session.session_date
            != self.contract.target_session_date
        ):
            raise ValueError("prepared decision does not match production contract")

        if self.status is ProductionStrategyDecisionStatus.NO_SIGNAL:
            if (
                (not current and not _legacy_signal_matches(self.prepared, False))
                or self.prepared.strategy_proposal is not None
                or self.proposal is not None
            ):
                raise ValueError("NO_SIGNAL decision carries proposal material")
            return

        if (
            (not current and not _legacy_signal_matches(self.prepared, True))
            or type(self.prepared.strategy_proposal) is not TradeProposal
            or self.proposal is not self.prepared.strategy_proposal
            or self.proposal.symbol != self.contract.symbol
        ):
            raise ValueError("TRADE_PROPOSAL decision does not retain exact proposal")


def build_production_strategy_decision(
    contract: ProductionStrategyContract,
    request: ManualPaperStrategyDecisionRequest,
    calendar: IdentifiedMarketCalendar,
) -> ProductionStrategyDecision:
    """Evaluate the existing verified daily strategy path exactly once."""
    from trading_bot.runtime.manual_paper_strategy_plan import (
        ManualPaperStrategyDecisionRequest,
        ManualPaperStrategySignalStatus,
        PreparedManualPaperStrategyDecision,
    )

    if type(contract) is not ProductionStrategyContract:
        raise TypeError("contract must be exactly ProductionStrategyContract")
    if type(request) is not ManualPaperStrategyDecisionRequest:
        raise TypeError("request must be exactly ManualPaperStrategyDecisionRequest")

    seed = request.history_seed
    if (
        type(seed) is not VerifiedStrategyHistorySeed
        or request.strategy_config != contract.strategy_config
        or seed.strategy_config != contract.strategy_config
        or seed.seed.symbol != contract.symbol
    ):
        raise ValueError("strategy request does not match production contract")

    prepared = build_manual_paper_strategy_decision(request, calendar)
    if type(prepared) is not PreparedManualPaperStrategyDecision:
        raise ValueError("strategy decision builder returned invalid material")
    if (
        prepared.strategy_config != contract.strategy_config
        or prepared.symbol != contract.symbol
        or prepared.intended_execution_session.session_date
        != contract.target_session_date
    ):
        raise ValueError("prepared strategy decision is outside production contract")

    if prepared.signal_status is ManualPaperStrategySignalStatus.NO_SIGNAL:
        if prepared.strategy_proposal is not None:
            raise ValueError("NO_SIGNAL prepared decision contains a proposal")
        return ProductionStrategyDecision(
            contract,
            prepared,
            ProductionStrategyDecisionStatus.NO_SIGNAL,
            None,
        )
    if (
        prepared.signal_status is ManualPaperStrategySignalStatus.TRADE_PROPOSAL
        and type(prepared.strategy_proposal) is TradeProposal
        and prepared.strategy_proposal.symbol == contract.symbol
    ):
        return ProductionStrategyDecision(
            contract,
            prepared,
            ProductionStrategyDecisionStatus.TRADE_PROPOSAL,
            prepared.strategy_proposal,
        )
    raise ValueError("prepared strategy decision has inconsistent signal material")


__all__ = [
    "ProductionStrategyDecision",
    "ProductionStrategyDecisionStatus",
    "build_production_strategy_decision",
]
