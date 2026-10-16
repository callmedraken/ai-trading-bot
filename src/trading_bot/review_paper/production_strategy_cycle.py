"""Human-started production-strategy live-paper composition.

This module does not implement strategy, quote, risk, paper accounting, or
broker logic. It only composes an accepted production strategy decision with
the existing Architecture-131 supervised review-paper PREPARE/EXECUTE boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from trading_bot.execution.models import ExecutionInstruction
from trading_bot.review_paper.session_admission import ReviewPaperSessionSchedule
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.supervised_forward_paper import (
    ReviewPaperSupervisedExecutionResult,
    ReviewPaperSupervisedPreparation,
    ReviewPaperSupervisedPreparationStatus,
    execute_review_paper_supervised_cycle,
    prepare_review_paper_supervised_cycle,
)
from trading_bot.risk.models import RiskLimits
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.strategies.production_decision import (
    ProductionStrategyDecision,
    ProductionStrategyDecisionStatus,
)


class ProductionStrategyPaperPreparationStatus(StrEnum):
    """Closed outcomes for one human-started production PREPARE."""

    NO_SIGNAL = "NO_SIGNAL"
    SESSION_NOT_ADMITTED = "SESSION_NOT_ADMITTED"
    SESSION_EXPIRED_DURING_ACQUISITION = "SESSION_EXPIRED_DURING_ACQUISITION"
    RISK_REJECTED = "RISK_REJECTED"
    READY_TO_PROCEED = "READY_TO_PROCEED"


_SUPERVISED_STATUS_MAP = {
    ReviewPaperSupervisedPreparationStatus.SESSION_NOT_ADMITTED: (
        ProductionStrategyPaperPreparationStatus.SESSION_NOT_ADMITTED
    ),
    ReviewPaperSupervisedPreparationStatus.SESSION_EXPIRED_DURING_ACQUISITION: (
        ProductionStrategyPaperPreparationStatus.SESSION_EXPIRED_DURING_ACQUISITION
    ),
    ReviewPaperSupervisedPreparationStatus.RISK_REJECTED: (
        ProductionStrategyPaperPreparationStatus.RISK_REJECTED
    ),
    ReviewPaperSupervisedPreparationStatus.READY_TO_PROCEED: (
        ProductionStrategyPaperPreparationStatus.READY_TO_PROCEED
    ),
}


@dataclass(frozen=True, slots=True)
class ProductionStrategyPaperPreparation:
    """Retain one production decision and its exact supervised PREPARE result."""

    decision: ProductionStrategyDecision
    status: ProductionStrategyPaperPreparationStatus
    supervised: ReviewPaperSupervisedPreparation | None

    def __post_init__(self) -> None:
        if type(self.decision) is not ProductionStrategyDecision:
            raise TypeError("decision must be exactly ProductionStrategyDecision")
        if type(self.status) is not ProductionStrategyPaperPreparationStatus:
            raise TypeError(
                "status must be exactly ProductionStrategyPaperPreparationStatus"
            )

        if self.status is ProductionStrategyPaperPreparationStatus.NO_SIGNAL:
            if (
                self.decision.status is not ProductionStrategyDecisionStatus.NO_SIGNAL
                or self.decision.proposal is not None
                or self.supervised is not None
            ):
                raise ValueError("NO_SIGNAL preparation carries effect material")
            return

        if (
            self.decision.status is not ProductionStrategyDecisionStatus.TRADE_PROPOSAL
            or self.decision.proposal is None
            or type(self.supervised) is not ReviewPaperSupervisedPreparation
            or self.supervised.proposal is not self.decision.proposal
            or self.supervised.schedule.session_date
            != self.decision.contract.target_session_date
            or _SUPERVISED_STATUS_MAP.get(self.supervised.status) is not self.status
        ):
            raise ValueError("supervised PREPARE is outside production decision")


@dataclass(frozen=True, slots=True)
class ProductionStrategyPaperExecutionResult:
    """Retain the exact accepted Architecture-131 execution result."""

    preparation: ProductionStrategyPaperPreparation
    execution: ReviewPaperSupervisedExecutionResult

    def __post_init__(self) -> None:
        if type(self.preparation) is not ProductionStrategyPaperPreparation:
            raise TypeError(
                "preparation must be exactly ProductionStrategyPaperPreparation"
            )
        if (
            self.preparation.status
            is not ProductionStrategyPaperPreparationStatus.READY_TO_PROCEED
            or type(self.preparation.supervised) is not ReviewPaperSupervisedPreparation
        ):
            raise ValueError("execution result requires READY_TO_PROCEED preparation")
        if type(self.execution) is not ReviewPaperSupervisedExecutionResult:
            raise TypeError(
                "execution must be exactly ReviewPaperSupervisedExecutionResult"
            )
        if self.execution.preparation is not self.preparation.supervised:
            raise ValueError("execution does not retain exact supervised preparation")


def prepare_production_strategy_paper_cycle(
    *,
    decision: ProductionStrategyDecision,
    store: ReviewPaperStore,
    schedule: ReviewPaperSessionSchedule,
    opening_buffer: timedelta,
    closing_buffer: timedelta,
    adapter: RobinhoodReviewReadAdapter,
    max_quote_age: timedelta,
    risk_limits: RiskLimits,
    new_trading_enabled: bool,
) -> ProductionStrategyPaperPreparation:
    """Create a shadow/live-data PREPARE without granting paper execution."""
    if type(decision) is not ProductionStrategyDecision:
        raise TypeError("decision must be exactly ProductionStrategyDecision")

    if decision.status is ProductionStrategyDecisionStatus.NO_SIGNAL:
        if decision.proposal is not None:
            raise ValueError("NO_SIGNAL decision carries a proposal")
        return ProductionStrategyPaperPreparation(
            decision,
            ProductionStrategyPaperPreparationStatus.NO_SIGNAL,
            None,
        )

    if (
        decision.status is not ProductionStrategyDecisionStatus.TRADE_PROPOSAL
        or decision.proposal is None
    ):
        raise ValueError("production decision has inconsistent proposal material")
    if type(schedule) is not ReviewPaperSessionSchedule:
        raise TypeError("schedule must be exactly ReviewPaperSessionSchedule")
    if schedule.session_date != decision.contract.target_session_date:
        raise ValueError("schedule does not match production contract target session")

    supervised = prepare_review_paper_supervised_cycle(
        store=store,
        proposal=decision.proposal,
        schedule=schedule,
        opening_buffer=opening_buffer,
        closing_buffer=closing_buffer,
        adapter=adapter,
        max_quote_age=max_quote_age,
        risk_limits=risk_limits,
        new_trading_enabled=new_trading_enabled,
    )
    if type(supervised) is not ReviewPaperSupervisedPreparation:
        raise ValueError("supervised PREPARE returned invalid material")
    status = _SUPERVISED_STATUS_MAP.get(supervised.status)
    if status is None:
        raise ValueError("supervised PREPARE returned unknown status")
    return ProductionStrategyPaperPreparation(decision, status, supervised)


def execute_production_strategy_paper_cycle(
    *,
    preparation: ProductionStrategyPaperPreparation,
    instruction: ExecutionInstruction,
    order_id: UUID,
    expected_branch: str,
    expected_head: str,
    expected_tree: str,
    evidence_path: Path,
    redirect_uri: str,
    slippage_basis_points: Decimal,
    commission: Decimal,
) -> ProductionStrategyPaperExecutionResult:
    """Delegate one explicit paper EXECUTE; never retry or reacquire."""
    if type(preparation) is not ProductionStrategyPaperPreparation:
        raise TypeError(
            "preparation must be exactly ProductionStrategyPaperPreparation"
        )
    if (
        preparation.status
        is not ProductionStrategyPaperPreparationStatus.READY_TO_PROCEED
        or type(preparation.supervised) is not ReviewPaperSupervisedPreparation
    ):
        raise ValueError("paper EXECUTE requires READY_TO_PROCEED preparation")
    if type(expected_head) is not str or type(expected_tree) is not str:
        raise TypeError("expected source identities must be strings")
    if (
        expected_head != preparation.decision.contract.source_head
        or expected_tree != preparation.decision.contract.source_tree
    ):
        raise ValueError("execution source does not match production contract")

    execution = execute_review_paper_supervised_cycle(
        preparation=preparation.supervised,
        instruction=instruction,
        order_id=order_id,
        expected_branch=expected_branch,
        expected_head=expected_head,
        expected_tree=expected_tree,
        evidence_path=evidence_path,
        redirect_uri=redirect_uri,
        slippage_basis_points=slippage_basis_points,
        commission=commission,
    )
    if type(execution) is not ReviewPaperSupervisedExecutionResult:
        raise ValueError("supervised EXECUTE returned invalid material")
    return ProductionStrategyPaperExecutionResult(preparation, execution)


__all__ = [
    "ProductionStrategyPaperExecutionResult",
    "ProductionStrategyPaperPreparation",
    "ProductionStrategyPaperPreparationStatus",
    "execute_production_strategy_paper_cycle",
    "prepare_production_strategy_paper_cycle",
]
