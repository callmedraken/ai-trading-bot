"""One-cycle Robinhood review-paper operator; no scheduling or order placement.

Callers supply a deterministic, already risk-approved ReviewPaperIntent and an
explicit capture timestamp. Source admission and local output admission precede
OAuth composition. Call counts describe attempted reviewed boundary invocations,
including calls that fail before an MCP request is sent. The returned value and
JSON evidence deliberately exclude the durable record and all upstream errors.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import warnings
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from pathlib import Path

from trading_bot.domain import OrderType, Symbol
from trading_bot.review_paper import (
    ReviewPaperIntent,
    ReviewPaperStore,
    RobinhoodEquityOrderReview,
)
from trading_bot.robinhood_mcp import (
    RobinhoodAgenticAccountResolver,
    RobinhoodEquityOrdersPage,
    RobinhoodMcpStreamableHttpTransport,
    RobinhoodReviewReadAdapter,
    create_robinhood_agentic_account_resolver,
)
from trading_bot.robinhood_mcp.windows_oauth import (
    create_windows_robinhood_oauth_factory,
)
from trading_bot.robinhood_paper_cycle import RobinhoodReviewPaperCycle


class RobinhoodPaperOperatorError(RuntimeError):
    """Source/output admission or local evidence publication failed."""


@dataclass(frozen=True, slots=True)
class RobinhoodPaperOperatorEvidence:
    """Closed machine-readable evidence schema containing no upstream material."""

    source_head: str
    source_tree: str
    status: str
    phase: str
    symbol: str
    side: str
    quantity: str
    order_type: str
    get_accounts_calls: int
    get_equity_orders_calls: int
    review_equity_order_calls: int
    get_equity_quotes_calls: int
    baseline_order_pages: int
    post_review_order_pages: int
    paper_record_count: int | None
    replay: bool
    review_echo_validated: bool
    quote_fill_validated: bool
    disclosure_present: bool
    interactive_reauth_count: int
    placement_calls: int = 0
    cancellation_calls: int = 0
    options_mutation_calls: int = 0
    crypto_mutation_calls: int = 0


@dataclass(slots=True)
class _Observation:
    phase: str = "composition"
    get_accounts_calls: int = 0
    get_equity_orders_calls: int = 0
    review_equity_order_calls: int = 0
    baseline_order_pages: int = 0
    post_review_order_pages: int = 0
    review_echo_validated: bool = False
    disclosure_present: bool = False
    interactive_reauth_count: int = 0

    def forbid_browser(self, _authorization_url: str) -> object:
        self.interactive_reauth_count += 1
        raise RobinhoodPaperOperatorError("interactive OAuth is forbidden")


class _ObservedResolver:
    def __init__(
        self, resolver: RobinhoodAgenticAccountResolver, observation: _Observation
    ) -> None:
        self._resolver = resolver
        self._observation = observation

    def resolve(self) -> str:
        self._observation.phase = "account_resolution"
        self._observation.get_accounts_calls += 1
        return self._resolver.resolve()


class _ObservedAdapter(RobinhoodReviewReadAdapter):
    def __init__(
        self, transport: RobinhoodMcpStreamableHttpTransport, observation: _Observation
    ) -> None:
        super().__init__(transport)
        self._observation = observation

    def review_market_order(
        self, *, account_number: str, intent: ReviewPaperIntent, received_at: datetime
    ) -> RobinhoodEquityOrderReview:
        self._observation.phase = "review"
        self._observation.review_equity_order_calls += 1
        review = super().review_market_order(
            account_number=account_number, intent=intent, received_at=received_at
        )
        self._observation.review_echo_validated = True
        self._observation.disclosure_present = _disclosure_present(
            review.market_data_disclosure
        )
        return review

    def agentic_equity_orders(
        self,
        *,
        account_number: str,
        created_at_gte: datetime | None = None,
        cursor: str | None = None,
        symbol: Symbol | None = None,
        state: str | None = None,
    ) -> RobinhoodEquityOrdersPage:
        after = self._observation.review_equity_order_calls > 0
        self._observation.phase = "post_review" if after else "baseline"
        self._observation.get_equity_orders_calls += 1
        page = super().agentic_equity_orders(
            account_number=account_number,
            created_at_gte=created_at_gte,
            cursor=cursor,
            symbol=symbol,
            state=state,
        )
        if after:
            self._observation.post_review_order_pages += 1
        else:
            self._observation.baseline_order_pages += 1
        return page


def _discard_log(_logger: logging.Logger, _record: logging.LogRecord) -> None:
    pass


def _discard_warning(*_args: object, **_kwargs: object) -> None:
    pass


@contextmanager
def _suppress_downstream_output() -> Iterator[None]:
    """Discard output for one synchronous cycle, restoring process state on exit.

    The null device retains no content. Redirect both Python streams and standard
    descriptors, and block logger dispatch including preconfigured handlers that
    hold their own streams. No in-memory or on-disk capture buffer is created.
    """
    original_streams = (sys.stdout, sys.stderr)
    for stream in original_streams:
        stream.flush()
    previous_disable = logging.root.manager.disable
    previous_handle = logging.Logger.handle
    with (
        open(os.devnull, "w", encoding="utf-8") as sink,
        redirect_stdout(sink),
        redirect_stderr(sink),
        warnings.catch_warnings(),
        ExitStack() as descriptors,
    ):
        for descriptor in (1, 2):
            saved = os.dup(descriptor)
            descriptors.callback(os.close, saved)
            descriptors.callback(os.dup2, saved, descriptor)
            os.dup2(sink.fileno(), descriptor)
        try:
            logging.disable(sys.maxsize)
            logging.Logger.handle = _discard_log
            warnings.simplefilter("ignore")
            warnings.showwarning = _discard_warning
            yield
        finally:
            try:
                # Drain any downstream writes through retained original streams
                # while their descriptors still point to the null device.
                for stream in original_streams:
                    stream.flush()
            finally:
                logging.Logger.handle = previous_handle
                logging.disable(previous_disable)


def _disclosure_present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _git(root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        raise RobinhoodPaperOperatorError("source identity unavailable") from None


def _admit_source(
    expected_branch: str, expected_head: str, expected_tree: str
) -> tuple[Path, ...]:
    root = Path(__file__).resolve().parents[2]
    if (
        not isinstance(expected_branch, str)
        or not expected_branch
        or not isinstance(expected_head, str)
        or re.fullmatch(r"[0-9a-f]{40}", expected_head) is None
        or not isinstance(expected_tree, str)
        or re.fullmatch(r"[0-9a-f]{40}", expected_tree) is None
        or Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root
        or _git(root, "branch", "--show-current") != expected_branch
        or _git(root, "rev-parse", "HEAD") != expected_head
        or _git(root, "rev-parse", "HEAD^{tree}") != expected_tree
        or _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    ):
        raise RobinhoodPaperOperatorError("source identity mismatch")
    roots = tuple(
        Path(line.removeprefix("worktree ")).resolve()
        for line in _git(root, "worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    )
    if root not in roots:
        raise RobinhoodPaperOperatorError("repository boundaries unavailable")
    return roots


def admit_robinhood_paper_source(
    *, expected_branch: str, expected_head: str, expected_tree: str
) -> tuple[Path, ...]:
    """Expose the accepted read-only source admission before a 133-D quote."""
    return _admit_source(expected_branch, expected_head, expected_tree)


def _admit_output(path: Path, roots: tuple[Path, ...]) -> Path:
    try:
        if not isinstance(path, Path) or not path.is_absolute():
            raise ValueError
        resolved = path.resolve()
        if any(resolved == root or resolved.is_relative_to(root) for root in roots):
            raise ValueError
        return resolved
    except Exception:
        raise RobinhoodPaperOperatorError(
            "output paths must be absolute and outside repository worktrees"
        ) from None


def _decimal_context() -> Context:
    return Context(
        prec=28,
        rounding=ROUND_HALF_EVEN,
        Emin=-999999,
        Emax=999999,
        capitals=1,
        clamp=0,
        flags=[],
        traps=[InvalidOperation, DivisionByZero, Overflow],
    )


def run_robinhood_paper_operator(
    *,
    intent: ReviewPaperIntent,
    review_received_at: datetime,
    expected_branch: str,
    expected_head: str,
    expected_tree: str,
    paper_store_path: Path,
    evidence_path: Path,
    redirect_uri: str,
    starting_cash: Decimal,
    slippage_basis_points: Decimal = Decimal("0"),
    commission: Decimal = Decimal("0"),
    oauth_factory: Callable[[], object] | None = None,
) -> RobinhoodPaperOperatorEvidence:
    """Run exactly one accepted paper cycle, returning PASS or sanitized FAIL.

    This function performs real read/review requests when called in production;
    source certification uses fakes only. It never evaluates risk or generates
    an intent. An explicit auth factory allows the 133-D persisted-only binding
    to reuse this same operator without the supervised OAuth provider.
    Existing evidence files are never overwritten. Source/input/path
    admission failures raise a fixed local error before Robinhood calls.
    """
    if oauth_factory is not None and not callable(oauth_factory):
        raise RobinhoodPaperOperatorError("invalid explicit OAuth factory")
    roots = _admit_source(expected_branch, expected_head, expected_tree)
    paper_path = _admit_output(paper_store_path, roots)
    output_path = _admit_output(evidence_path, roots)
    if output_path in {
        paper_path,
        Path(str(paper_path) + "-wal"),
        Path(str(paper_path) + "-shm"),
        Path(str(paper_path) + "-journal"),
    }:
        raise RobinhoodPaperOperatorError("paper store and evidence paths overlap")
    if (
        not isinstance(intent, ReviewPaperIntent)
        or intent.order_type is not OrderType.MARKET
        or not isinstance(review_received_at, datetime)
        or review_received_at.tzinfo is None
        or review_received_at.utcoffset() is None
        or review_received_at < intent.proposed_at
        or any(
            not isinstance(value, Decimal) or not value.is_finite()
            for value in (starting_cash, slippage_basis_points, commission)
        )
        or starting_cash <= 0
        or not Decimal("0") <= slippage_basis_points <= Decimal("9999")
        or commission < 0
    ):
        raise RobinhoodPaperOperatorError("invalid paper operator inputs")

    observation = _Observation()
    status = "FAIL"
    replay = False
    quote_fill_validated = False
    paper_record_count = None
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Reserve the evidence destination before any brokerage request.
        with output_path.open("x", encoding="utf-8", newline="\n") as output:
            with localcontext(_decimal_context()), _suppress_downstream_output():
                store = None
                try:
                    observation.phase = "paper_store"
                    store = ReviewPaperStore(paper_path, starting_cash=starting_cash)
                    observation.phase = "composition"
                    active_oauth_factory = (
                        create_windows_robinhood_oauth_factory(
                            redirect_uri=redirect_uri,
                            browser_opener=observation.forbid_browser,
                        )
                        if oauth_factory is None
                        else oauth_factory
                    )
                    transport = RobinhoodMcpStreamableHttpTransport(
                        active_oauth_factory
                    )
                    resolver = _ObservedResolver(
                        create_robinhood_agentic_account_resolver(transport),
                        observation,
                    )
                    cycle = RobinhoodReviewPaperCycle(
                        _ObservedAdapter(transport, observation),
                        store,
                        account_resolver=resolver,
                        slippage_basis_points=slippage_basis_points,
                        commission=commission,
                    )
                    observation.phase = "durable_check"
                    result = cycle.run(
                        intent=intent, review_received_at=review_received_at
                    )
                    replay = result.reused_durable_record
                    observation.review_echo_validated = True
                    observation.disclosure_present = _disclosure_present(
                        result.record.review.market_data_disclosure
                    )
                    quote_fill_validated = True
                    observation.phase = "complete"
                    status = "PASS"
                except Exception:
                    # Never serialize upstream exceptions or their chained context.
                    if observation.interactive_reauth_count:
                        observation.phase = "interactive_reauth_blocked"
                if store is not None:
                    try:
                        paper_record_count = len(store.history())
                    except Exception:
                        status = "FAIL"
                        observation.phase = "paper_history"
                evidence = RobinhoodPaperOperatorEvidence(
                    source_head=expected_head,
                    source_tree=expected_tree,
                    status=status,
                    phase=observation.phase,
                    symbol=str(intent.symbol),
                    side=intent.side.value,
                    quantity=format(intent.approved_quantity, "f"),
                    order_type=intent.order_type.value,
                    get_accounts_calls=observation.get_accounts_calls,
                    get_equity_orders_calls=observation.get_equity_orders_calls,
                    review_equity_order_calls=observation.review_equity_order_calls,
                    get_equity_quotes_calls=0,
                    baseline_order_pages=observation.baseline_order_pages,
                    post_review_order_pages=observation.post_review_order_pages,
                    paper_record_count=paper_record_count,
                    replay=replay,
                    review_echo_validated=observation.review_echo_validated,
                    quote_fill_validated=quote_fill_validated,
                    disclosure_present=observation.disclosure_present,
                    interactive_reauth_count=observation.interactive_reauth_count,
                )
            output.write(json.dumps(asdict(evidence), sort_keys=True) + "\n")
            output.flush()
        return evidence
    except Exception:
        raise RobinhoodPaperOperatorError("local evidence publication failed") from None
