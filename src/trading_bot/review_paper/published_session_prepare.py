"""Explicit-date published-session bindings for supervised PREPARE only."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from trading_bot.domain import TradeProposal
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.review_paper.prepare_qualification import (
    run_review_paper_prepare_qualification,
)
from trading_bot.review_paper.session_admission import ReviewPaperSessionSchedule
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.supervised_forward_paper import (
    ReviewPaperSupervisedPreparation,
    prepare_review_paper_supervised_cycle,
)
from trading_bot.risk.models import RiskLimits
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter


class ReviewPaperPublishedNonSessionDateError(ValueError):
    """The explicit date is a published non-session date."""


def resolve_review_paper_published_session_schedule(
    session_date: date,
) -> ReviewPaperSessionSchedule:
    """Resolve exactly one date through the accepted published authority."""
    schedule = NYSEPublishedRegularSessionAuthority().schedule_for(session_date)
    if schedule is None:
        raise ReviewPaperPublishedNonSessionDateError(
            f"not a published NYSE session date: {session_date}"
        )
    return schedule


def prepare_review_paper_supervised_published_session(
    *,
    session_date: date,
    store: ReviewPaperStore,
    proposal: TradeProposal,
    opening_buffer: timedelta,
    closing_buffer: timedelta,
    adapter: RobinhoodReviewReadAdapter,
    max_quote_age: timedelta,
    risk_limits: RiskLimits,
    new_trading_enabled: bool,
) -> ReviewPaperSupervisedPreparation:
    """Resolve once, then preserve the accepted delegate result unchanged."""
    schedule = resolve_review_paper_published_session_schedule(session_date)
    return prepare_review_paper_supervised_cycle(
        schedule=schedule,
        store=store,
        proposal=proposal,
        opening_buffer=opening_buffer,
        closing_buffer=closing_buffer,
        adapter=adapter,
        max_quote_age=max_quote_age,
        risk_limits=risk_limits,
        new_trading_enabled=new_trading_enabled,
    )


def run_review_paper_published_session_prepare_qualification(
    *,
    session_date: date,
    store: ReviewPaperStore,
    proposal: TradeProposal,
    opening_buffer: timedelta,
    closing_buffer: timedelta,
    adapter: RobinhoodReviewReadAdapter,
    max_quote_age: timedelta,
    risk_limits: RiskLimits,
    new_trading_enabled: bool,
    expected_source_head: str,
    expected_source_tree: str,
    evidence_path: Path,
) -> ReviewPaperSupervisedPreparation:
    """Resolve once, then preserve the accepted delegate result unchanged."""
    schedule = resolve_review_paper_published_session_schedule(session_date)
    return run_review_paper_prepare_qualification(
        schedule=schedule,
        store=store,
        proposal=proposal,
        opening_buffer=opening_buffer,
        closing_buffer=closing_buffer,
        adapter=adapter,
        max_quote_age=max_quote_age,
        risk_limits=risk_limits,
        new_trading_enabled=new_trading_enabled,
        expected_source_head=expected_source_head,
        expected_source_tree=expected_source_tree,
        evidence_path=evidence_path,
    )
