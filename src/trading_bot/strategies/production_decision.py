"""Pure production-strategy decision bridge.

This module binds one session-scoped production strategy contract to the already
verified Architecture-94 daily strategy-decision path. It adds no provider,
paper-store, risk, scheduler, clock, research, or execution capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from trading_bot.domain import TradeProposal
from trading_bot.market_data import IdentifiedMarketCalendar
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperStrategyDecisionRequest,
    ManualPaperStrategySignalStatus,
    PreparedManualPaperStrategyDecision,
    build_manual_paper_strategy_decision,
)
from trading_bot.runtime.strategy_history_seed import VerifiedStrategyHistorySeed
from trading_bot.strategies.production import ProductionStrategyContract


class ProductionStrategyDecisionStatus(StrEnum):
    """Closed production decision outcomes before provider/risk/execution."""

    NO_SIGNAL = "NO_SIGNAL"
    TRADE_PROPOSAL = "TRADE_PROPOSAL"


@dataclass(frozen=True, slots=True)
class ProductionStrategyDecision:
    """Exact retained production contract plus one verified strategy decision."""

    contract: ProductionStrategyContract
    prepared: PreparedManualPaperStrategyDecision
    status: ProductionStrategyDecisionStatus
    proposal: TradeProposal | None

    def __post_init__(self) -> None:
        if type(self.contract) is not ProductionStrategyContract:
            raise TypeError("contract must be exactly ProductionStrategyContract")
        if type(self.prepared) is not PreparedManualPaperStrategyDecision:
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
                self.prepared.signal_status
                is not ManualPaperStrategySignalStatus.NO_SIGNAL
                or self.prepared.strategy_proposal is not None
                or self.proposal is not None
            ):
                raise ValueError("NO_SIGNAL decision carries proposal material")
            return

        if (
            self.prepared.signal_status
            is not ManualPaperStrategySignalStatus.TRADE_PROPOSAL
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
