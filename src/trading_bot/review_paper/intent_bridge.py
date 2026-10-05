"""Pure conversion of an existing risk approval into local paper intent."""

from __future__ import annotations

from uuid import UUID

from trading_bot.execution.models import ExecutionInstruction
from trading_bot.review_paper.models import ReviewPaperIntent
from trading_bot.risk.models import RiskDecision, RiskOutcome


def build_review_paper_intent(
    decision: RiskDecision,
    instruction: ExecutionInstruction,
    *,
    order_id: UUID,
) -> ReviewPaperIntent:
    """Preserve approved inputs exactly, using the caller's local order identity."""

    if type(decision) is not RiskDecision:
        raise TypeError("decision must be exactly a RiskDecision")
    if type(instruction) is not ExecutionInstruction:
        raise TypeError("instruction must be exactly an ExecutionInstruction")
    if type(order_id) is not UUID:
        raise TypeError("order_id must be exactly a UUID")
    if decision.outcome is RiskOutcome.REJECTED:
        raise ValueError("rejected risk decisions cannot create paper intent")
    if decision.evaluated_at < decision.proposal.created_at:
        raise ValueError("decision evaluated_at must not precede proposal created_at")
    if instruction.created_at < decision.evaluated_at:
        raise ValueError(
            "instruction created_at must not precede decision evaluated_at"
        )

    return ReviewPaperIntent(
        proposal_id=decision.proposal.proposal_id,
        order_id=order_id,
        symbol=decision.proposal.symbol,
        side=decision.proposal.side,
        desired_quantity=decision.proposal.desired_quantity,
        approved_quantity=decision.approved_quantity,
        risk_outcome=decision.outcome,
        risk_reason_codes=tuple(reason.code.value for reason in decision.reasons),
        proposal_reason=decision.proposal.reason,
        proposal_confidence=decision.proposal.confidence,
        order_type=instruction.order_type,
        time_in_force=instruction.time_in_force,
        proposed_at=decision.proposal.created_at,
        limit_price=instruction.limit_price,
    )
