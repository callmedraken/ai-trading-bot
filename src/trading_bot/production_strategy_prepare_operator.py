"""Separately authorized, one-shot production SHADOW PREPARE; never EXECUTE.

Consumes an existing exact production decision. It creates no strategy authority.
Evidence is fresh and external; failures expose only a fixed local message and
leave no successful evidence. No CLI reconstructs a decision from operator args.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import warnings
from collections.abc import Iterator, Mapping
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from datetime import timedelta
from pathlib import Path

from trading_bot.review_paper.production_strategy_cycle import (
    ProductionStrategyPaperPreparation,
    prepare_production_strategy_paper_cycle,
)
from trading_bot.review_paper.published_session_prepare import (
    resolve_review_paper_published_session_schedule,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.risk.models import RiskLimits
from trading_bot.robinhood_execute_qualification_verifier import (
    qualification_fingerprint,
    read_qualification_store,
)
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.robinhood_mcp.sdk_transport import RobinhoodMcpStreamableHttpTransport
from trading_bot.robinhood_mcp.windows_oauth import (
    LoopbackOAuthError,
    create_windows_robinhood_oauth_factory,
)
from trading_bot.robinhood_paper_operator import admit_robinhood_paper_source
from trading_bot.strategies.production_decision import (
    ProductionStrategyDecision,
    ProductionStrategyDecisionStatus,
)


class ProductionStrategyPrepareOperatorError(RuntimeError):
    """Sanitized terminal failure; never grants retry or execution authority."""


def _block_interactive_authorization(url: str) -> object:
    raise LoopbackOAuthError("Interactive OAuth authorization is forbidden")


class _QuoteOnlyTransport:
    """Count attempts before delegation and fail closed on any second operation."""

    def __init__(self, transport: RobinhoodMcpStreamableHttpTransport) -> None:
        self.transport = transport
        self.quote_calls = 0

    def get_equity_quotes(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        if self.quote_calls != 0:
            raise ProductionStrategyPrepareOperatorError("Quote budget exhausted")
        self.quote_calls += 1
        return self.transport.get_equity_quotes(arguments)

    def review_equity_order(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        raise ProductionStrategyPrepareOperatorError("Only one quote read is allowed")

    def get_equity_orders(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        raise ProductionStrategyPrepareOperatorError("Only one quote read is allowed")


def _discard_log(*args: object, **kwargs: object) -> None:
    pass


@contextmanager
def _quiet_provider() -> Iterator[None]:
    # Discard, never capture, upstream prints/logs/warnings and native FD output.
    streams = sys.stdout, sys.stderr
    for stream in streams:
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
            yield
        finally:
            for stream in streams:
                stream.flush()
            logging.Logger.handle = previous_handle
            logging.disable(previous_disable)


def run_production_strategy_shadow_prepare(
    *,
    decision: ProductionStrategyDecision,
    store: ReviewPaperStore,
    opening_buffer: timedelta,
    closing_buffer: timedelta,
    max_quote_age: timedelta,
    risk_limits: RiskLimits,
    new_trading_enabled: bool,
    expected_branch: str,
    expected_source_head: str,
    expected_source_tree: str,
    evidence_path: Path,
    redirect_uri: str,
) -> ProductionStrategyPaperPreparation:
    """Return the exact 134-C result after one bounded, sanitized qualification.

    Call only after independent human authorization of this exact decision and
    source. NO_SIGNAL does not inspect store/config/OAuth/provider inputs. Its
    null durable observations mean the store was untouched, not observed empty.
    A failed invocation is terminal; an empty reserved evidence file is not PASS.
    """
    if type(decision) is not ProductionStrategyDecision:
        raise TypeError("decision must be exactly ProductionStrategyDecision")
    if (
        expected_source_head != decision.contract.source_head
        or expected_source_tree != decision.contract.source_tree
    ):
        raise ProductionStrategyPrepareOperatorError("Source differs from contract")
    try:
        roots = admit_robinhood_paper_source(
            expected_branch=expected_branch,
            expected_head=expected_source_head,
            expected_tree=expected_source_tree,
        )
        source_root = Path(__file__).resolve().parents[2]
        if source_root not in roots:
            raise ValueError
        # Reject mixed executable imports, even when the checkout itself is clean.
        for name, module in tuple(sys.modules.items()):
            if name == "trading_bot" or name.startswith("trading_bot."):
                filename = getattr(module, "__file__", None)
                if not filename or not Path(filename).resolve().is_relative_to(
                    source_root / "src"
                ):
                    raise ValueError
        if not isinstance(evidence_path, Path) or not evidence_path.is_absolute():
            raise ValueError
        output_path = evidence_path.resolve()
        if (
            evidence_path.is_symlink()
            or evidence_path.exists()
            or any(output_path.is_relative_to(root) for root in roots)
            or not output_path.parent.is_dir()
        ):
            raise ValueError

        schedule = adapter = None
        bounded = None
        before = after = None
        if decision.status is ProductionStrategyDecisionStatus.TRADE_PROPOSAL:
            schedule = resolve_review_paper_published_session_schedule(
                decision.contract.target_session_date
            )
            if type(store) is not ReviewPaperStore:
                raise TypeError
            store_path = store.path.resolve()
            if output_path in {
                store_path,
                *(
                    Path(str(store_path) + suffix)
                    for suffix in ("-wal", "-shm", "-journal")
                ),
            }:
                raise ValueError
            before = qualification_fingerprint(*read_qualification_store(store_path))

        # Exclusive reservation precedes OAuth/provider construction. A collision
        # cannot consume a provider call or overwrite prior evidence.
        with output_path.open("x", encoding="utf-8", newline="\n") as output:
            with _quiet_provider():
                if decision.status is ProductionStrategyDecisionStatus.TRADE_PROPOSAL:
                    oauth = create_windows_robinhood_oauth_factory(
                        redirect_uri=redirect_uri,
                        browser_opener=_block_interactive_authorization,
                    )
                    bounded = _QuoteOnlyTransport(
                        RobinhoodMcpStreamableHttpTransport(oauth)
                    )
                    adapter = RobinhoodReviewReadAdapter(bounded)
                result = prepare_production_strategy_paper_cycle(
                    decision=decision,
                    store=store,
                    schedule=schedule,
                    opening_buffer=opening_buffer,
                    closing_buffer=closing_buffer,
                    adapter=adapter,
                    max_quote_age=max_quote_age,
                    risk_limits=risk_limits,
                    new_trading_enabled=new_trading_enabled,
                )
            if (
                type(result) is not ProductionStrategyPaperPreparation
                or result.decision is not decision
            ):
                raise ValueError
            supervised = result.supervised
            calls = 0 if bounded is None else bounded.quote_calls
            expected_calls = int(
                supervised is not None and supervised.price_snapshot is not None
            )
            if calls != expected_calls:
                raise ValueError
            if before is not None:
                after = qualification_fingerprint(*read_qualification_store(store_path))
                if before != after:
                    raise ValueError
            # Re-admit the executable tree after acquisition; never repair drift.
            admit_robinhood_paper_source(
                expected_branch=expected_branch,
                expected_head=expected_source_head,
                expected_tree=expected_source_tree,
            )
            proposal = decision.proposal
            payload = {
                "schema": "production-strategy-shadow-prepare/v1",
                "source_head": expected_source_head,
                "source_tree": expected_source_tree,
                "contract_id": str(decision.contract.contract_id),
                "target_session_date": (
                    decision.contract.target_session_date.isoformat()
                ),
                "decision_status": decision.status.value,
                "prepare_status": result.status.value,
                "proposal": None
                if proposal is None
                else {
                    "proposal_id": str(proposal.proposal_id),
                    "symbol": str(proposal.symbol),
                    "side": proposal.side.value,
                    "desired_quantity": str(proposal.desired_quantity),
                },
                "initial_admission_status": None
                if supervised is None
                else supervised.initial_admission.status.value,
                "quote_admission_status": None
                if supervised is None or supervised.quote_admission is None
                else supervised.quote_admission.status.value,
                "quote_observed_at": None
                if supervised is None or supervised.price_snapshot is None
                else supervised.price_snapshot.observed_at.isoformat(),
                "quote_valid_until": None
                if supervised is None or supervised.quote_valid_until is None
                else supervised.quote_valid_until.isoformat(),
                "risk_outcome": None
                if supervised is None or supervised.preview is None
                else supervised.preview.risk_decision.outcome.value,
                "approved_quantity": None
                if supervised is None or supervised.preview is None
                else str(supervised.preview.risk_decision.approved_quantity),
                "durable_observed": before is not None,
                "durable_before": before,
                "durable_after": after,
                "get_equity_quotes_calls": calls,
                "get_accounts_calls": 0,
                "get_equity_orders_calls": 0,
                "review_equity_order_calls": 0,
                "placement_calls": 0,
                "cancellation_calls": 0,
                "options_mutation_calls": 0,
                "crypto_mutation_calls": 0,
                "execute_invoked": False,
                "pipeline_result_present": False,
            }
            output.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return result
    except Exception:
        raise ProductionStrategyPrepareOperatorError("Shadow PREPARE stopped") from None
