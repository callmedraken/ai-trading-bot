"""One human-started cycle bound to the sole durable virtual paper account."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from trading_bot.domain import Symbol, TradeProposal
from trading_bot.execution.models import ExecutionInstruction
from trading_bot.review_paper.risk_context import build_review_paper_risk_context
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.risk import RiskLimits
from trading_bot.robinhood_paper_pipeline import (
    RobinhoodDeterministicPaperPipelineResult,
    run_robinhood_deterministic_paper_pipeline,
)


def run_robinhood_forward_paper_cycle(
    *,
    store: ReviewPaperStore,
    proposal: TradeProposal,
    prices: Mapping[Symbol, Decimal],
    as_of: datetime,
    new_trading_enabled: bool,
    risk_limits: RiskLimits,
    instruction: ExecutionInstruction,
    order_id: UUID,
    review_received_at: datetime,
    expected_branch: str,
    expected_head: str,
    expected_tree: str,
    evidence_path: Path,
    redirect_uri: str,
    slippage_basis_points: Decimal,
    commission: Decimal,
) -> RobinhoodDeterministicPaperPipelineResult:
    """Build durable risk context once and return the exact 131-J result.

    The accepted builder validates the explicit snapshot and reconstructs the
    account. The same store owns the pipeline's path and starting cash. Accepted
    pipeline calls may perform review and local paper effects through 131-H;
    failures propagate without retries. Source certification uses test doubles
    at that effect boundary.
    """
    risk_context = build_review_paper_risk_context(
        store,
        proposal,
        prices,
        as_of=as_of,
        new_trading_enabled=new_trading_enabled,
    )
    return run_robinhood_deterministic_paper_pipeline(
        proposal=proposal,
        risk_context=risk_context,
        risk_limits=risk_limits,
        instruction=instruction,
        order_id=order_id,
        review_received_at=review_received_at,
        expected_branch=expected_branch,
        expected_head=expected_head,
        expected_tree=expected_tree,
        paper_store_path=store.path,
        evidence_path=evidence_path,
        redirect_uri=redirect_uri,
        starting_cash=store.starting_cash,
        slippage_basis_points=slippage_basis_points,
        commission=commission,
    )
