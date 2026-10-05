"""One caller-owned deterministic risk cycle delegated to the paper operator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from trading_bot.domain import TradeProposal
from trading_bot.execution.models import ExecutionInstruction
from trading_bot.review_paper import ReviewPaperIntent, build_review_paper_intent
from trading_bot.risk import (
    RiskContext,
    RiskDecision,
    RiskLimits,
    RiskManager,
    RiskOutcome,
)
from trading_bot.robinhood_paper_operator import (
    RobinhoodPaperOperatorEvidence,
    run_robinhood_paper_operator,
)


@dataclass(frozen=True, slots=True)
class RobinhoodDeterministicPaperPipelineResult:
    """Preserved risk decision, bridged intent, and sanitized operator evidence."""

    risk_decision: RiskDecision
    intent: ReviewPaperIntent | None
    operator_evidence: RobinhoodPaperOperatorEvidence | None

    def __post_init__(self) -> None:
        if type(self.risk_decision) is not RiskDecision:
            raise TypeError("risk_decision must be exactly a RiskDecision")
        if self.risk_decision.outcome is RiskOutcome.REJECTED:
            if self.intent is not None or self.operator_evidence is not None:
                raise ValueError(
                    "rejected risk must have no intent or operator evidence"
                )
        else:
            if type(self.intent) is not ReviewPaperIntent:
                raise TypeError("accepted risk must have exactly a ReviewPaperIntent")
            if type(self.operator_evidence) is not RobinhoodPaperOperatorEvidence:
                raise TypeError("accepted risk must have exactly operator evidence")


def run_robinhood_deterministic_paper_pipeline(
    *,
    proposal: TradeProposal,
    risk_context: RiskContext,
    risk_limits: RiskLimits,
    instruction: ExecutionInstruction,
    order_id: UUID,
    review_received_at: datetime,
    expected_branch: str,
    expected_head: str,
    expected_tree: str,
    paper_store_path: Path,
    evidence_path: Path,
    redirect_uri: str,
    starting_cash: Decimal,
    slippage_basis_points: Decimal,
    commission: Decimal,
) -> RobinhoodDeterministicPaperPipelineResult:
    """Evaluate once; reject locally or bridge and invoke the operator once.

    The supplied context alone owns paper-risk authority. No identities or
    configuration are discovered here. Accepted calls may perform read/review
    and local paper effects through the existing operator; failures are neither
    caught nor retried. Operator PASS/FAIL evidence is returned unchanged.
    """
    if type(instruction) is not ExecutionInstruction:
        raise TypeError("instruction must be exactly an ExecutionInstruction")
    if type(order_id) is not UUID:
        raise TypeError("order_id must be exactly a UUID")
    decision = RiskManager(risk_limits).evaluate(proposal, risk_context)
    if decision.outcome is RiskOutcome.REJECTED:
        return RobinhoodDeterministicPaperPipelineResult(decision, None, None)
    intent = build_review_paper_intent(decision, instruction, order_id=order_id)
    evidence = run_robinhood_paper_operator(
        intent=intent,
        review_received_at=review_received_at,
        expected_branch=expected_branch,
        expected_head=expected_head,
        expected_tree=expected_tree,
        paper_store_path=paper_store_path,
        evidence_path=evidence_path,
        redirect_uri=redirect_uri,
        starting_cash=starting_cash,
        slippage_basis_points=slippage_basis_points,
        commission=commission,
    )
    return RobinhoodDeterministicPaperPipelineResult(decision, intent, evidence)
