"""Source-owned, non-interactive transport composition for published PREPARE."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from trading_bot.domain import TradeProposal
from trading_bot.review_paper.published_session_prepare import (
    run_review_paper_published_session_prepare_qualification,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.supervised_forward_paper import (
    ReviewPaperSupervisedPreparation,
)
from trading_bot.risk.models import RiskLimits
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.robinhood_mcp.sdk_transport import RobinhoodMcpStreamableHttpTransport
from trading_bot.robinhood_mcp.windows_oauth import (
    LoopbackOAuthError,
    create_windows_robinhood_oauth_factory,
)


def _block_interactive_authorization(url: str) -> object:
    """Reject interactive authorization without exposing the redirect material."""
    raise LoopbackOAuthError("Interactive OAuth authorization is forbidden")


def run_robinhood_published_session_prepare_qualification(
    *,
    session_date: date,
    store: ReviewPaperStore,
    proposal: TradeProposal,
    opening_buffer: timedelta,
    closing_buffer: timedelta,
    max_quote_age: timedelta,
    risk_limits: RiskLimits,
    new_trading_enabled: bool,
    expected_source_head: str,
    expected_source_tree: str,
    evidence_path: Path,
    redirect_uri: str,
) -> ReviewPaperSupervisedPreparation:
    """Compose inert boundaries once and return the exact accepted PREPARE result."""
    oauth_factory = create_windows_robinhood_oauth_factory(
        redirect_uri=redirect_uri,
        browser_opener=_block_interactive_authorization,
    )
    transport = RobinhoodMcpStreamableHttpTransport(oauth_factory)
    adapter = RobinhoodReviewReadAdapter(transport)
    return run_review_paper_published_session_prepare_qualification(
        session_date=session_date,
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
