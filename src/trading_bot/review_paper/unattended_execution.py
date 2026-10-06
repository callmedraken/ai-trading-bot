"""133-D concrete bindings; 133-C alone owns wake transitions and ordering.

No host discovery or launch surface. Persisted OAuth is read once at the quote
edge and reused without refresh, challenge response, or credential writes.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable, Generator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from trading_bot.domain import OrderType, Symbol, TimeInForce
from trading_bot.execution.models import ExecutionInstruction
from trading_bot.review_paper.forward_preview import ReviewPaperForwardPreview
from trading_bot.review_paper.intent_bridge import build_review_paper_intent
from trading_bot.review_paper.models import ReviewPaperRecord
from trading_bot.review_paper.risk_prices import (
    ReviewPaperRiskPriceSnapshot,
    build_review_paper_risk_price_snapshot,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.unattended_activation import (
    ReviewPaperActivation,
    ReviewPaperWakeState,
)
from trading_bot.review_paper.unattended_one_wake import (
    OneWakeInstants,
    OneWakeResult,
    OneWakeSyntheticEffectResult,
    compose_one_review_paper_wake,
)
from trading_bot.review_paper.unattended_state_schema import PersistedReviewPaperWake
from trading_bot.review_paper.unattended_state_store import UnattendedStateStore
from trading_bot.review_paper.unattended_state_verifier import verify_unattended_state
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.robinhood_mcp.sdk_transport import RobinhoodMcpStreamableHttpTransport
from trading_bot.robinhood_mcp.windows_oauth import WindowsOAuthStorage
from trading_bot.robinhood_paper_operator import (
    RobinhoodPaperOperatorEvidence,
    admit_robinhood_paper_source,
    run_robinhood_paper_operator,
)

if TYPE_CHECKING:
    import httpx2


class UnattendedExecutionError(RuntimeError):
    """Fixed sanitized failure; never carries upstream credential/provider text."""


@dataclass(frozen=True, slots=True)
class UnattendedExecutionBinding:
    """Explicit admitted source/runtime and output material, supplied by caller.

    deployment_identity is the activation's admitted runtime identity. Host
    attestation/discovery is deliberately outside this source composition.
    oauth_valid_until is an explicit bound, never an inferred token renewal.
    quote_observed_clock is source-owned and called once only after the single
    quote response returns so provider latency cannot inherit a pre-request time.
    """

    source_branch: str
    source_head: str
    source_tree: str
    deployment_identity: str
    evidence_path: Path
    redirect_uri: str
    oauth_valid_until: datetime
    quote_observed_clock: Callable[[], datetime]

    def __post_init__(self) -> None:
        if (
            type(self.source_branch) is not str
            or not self.source_branch
            or self.source_branch != self.source_branch.strip()
        ):
            raise ValueError("explicit source branch required")
        if (
            not isinstance(self.evidence_path, Path)
            or not self.evidence_path.is_absolute()
        ):
            raise ValueError("explicit absolute evidence path required")
        if not callable(self.quote_observed_clock):
            raise ValueError("explicit post-quote clock required")
        at = self.oauth_valid_until
        if type(at) is not datetime or at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("explicit aware OAuth expiry required")


@dataclass(frozen=True, slots=True)
class UnattendedExecutionResult:
    """Closed sanitized acknowledgement; no raw record, credentials, or paths."""

    wake: OneWakeResult
    operator_evidence: RobinhoodPaperOperatorEvidence | None
    operator_evidence_sha256: str | None
    paper_trade_id: UUID | None
    fill_id: UUID | None


def _persisted_auth_factory(
    storage: WindowsOAuthStorage,
) -> Callable[[], object]:
    # The accepted getter validates both persisted token and client registration.
    # Read once, before the quote; never construct OAuthClientProvider (which can
    # refresh, discover/register, or reauthorize following an HTTP challenge).
    tokens = asyncio.run(storage.get_tokens())
    if (
        tokens is None
        or tokens.token_type.lower() != "bearer"
        or not tokens.access_token
        or (tokens.expires_in is not None and tokens.expires_in <= 0)
    ):
        raise UnattendedExecutionError("persisted OAuth unavailable")
    import httpx2

    class PersistedAuth(httpx2.Auth):
        def __repr__(self) -> str:
            return "PersistedAuth(<redacted>)"

        __str__ = __repr__

        def auth_flow(
            self, request: httpx2.Request
        ) -> Generator[httpx2.Request, httpx2.Response, None]:
            request.headers["Authorization"] = "Bearer " + tokens.access_token
            response = yield request
            if response.status_code in (401, 403):
                raise UnattendedExecutionError("persisted OAuth rejected")

    return PersistedAuth


class _ExecutionEdges:
    """Private per-invocation budget, never a second wake authority."""

    def __init__(self, activation, state_store, paper_store, binding, oauth_storage):
        self.activation = activation
        self.state_store = state_store
        self.paper_store = paper_store
        self.binding = binding
        self.oauth_storage = oauth_storage
        self.auth_factory = None
        self.snapshot = None
        self.history = None
        self.quote_used = False
        self.operator_used = False
        self.evidence = None
        self.digest = None
        self.record = None

    def prepare_quote(
        self,
        *,
        activation: ReviewPaperActivation,
        required_symbols: tuple[Symbol, ...],
        as_of: datetime,
    ) -> ReviewPaperRiskPriceSnapshot:
        if self.quote_used:
            raise UnattendedExecutionError("quote budget consumed")
        self.quote_used = True
        b = self.binding
        if (
            activation is not self.activation
            or (b.source_head, b.source_tree, b.deployment_identity)
            != (
                activation.source_head,
                activation.source_tree,
                activation.deployment_identity,
            )
            or as_of >= b.oauth_valid_until
        ):
            raise UnattendedExecutionError("source/runtime/OAuth binding mismatch")
        paths = {self.paper_store.path.resolve(), self.state_store.path.resolve()}
        reserved = {
            Path(str(path) + suffix)
            for path in paths
            for suffix in ("", "-wal", "-shm", "-journal")
        }
        if b.evidence_path.resolve() in reserved or b.evidence_path.exists():
            raise UnattendedExecutionError("evidence destination unavailable")
        self.history = self.paper_store.history()
        # 131-P symbol discovery/bounds, delegated mark/freshness policy to 131-N.
        symbols = tuple(
            sorted(
                set(self.paper_store.reconstruct_ledger().positions)
                | {activation.proposal.symbol},
                key=str,
            )
        )
        if required_symbols != symbols or not 1 <= len(symbols) <= 20:
            raise UnattendedExecutionError("required quote symbols mismatch")
        # Reuse 131-H's source admission before the first provider edge.
        roots = admit_robinhood_paper_source(
            expected_branch=b.source_branch,
            expected_head=b.source_head,
            expected_tree=b.source_tree,
        )
        if any(
            path == root or path.is_relative_to(root)
            for root in roots
            for path in (*paths, b.evidence_path.resolve())
        ):
            raise UnattendedExecutionError("outputs overlap admitted source")
        self.auth_factory = _persisted_auth_factory(self.oauth_storage)
        adapter = RobinhoodReviewReadAdapter(
            RobinhoodMcpStreamableHttpTransport(self.auth_factory)
        )
        response = adapter.equity_quotes(symbols)
        observed_at = b.quote_observed_clock()
        if (
            type(observed_at) is not datetime
            or observed_at.tzinfo is None
            or observed_at.utcoffset() is None
        ):
            raise UnattendedExecutionError("post-quote observation invalid")
        observed_at = observed_at.astimezone(UTC)
        if observed_at < as_of or observed_at >= b.oauth_valid_until:
            raise UnattendedExecutionError("post-quote observation outside authority")
        self.snapshot = build_review_paper_risk_price_snapshot(
            response=response,
            required_symbols=symbols,
            observed_at=observed_at,
            max_quote_age=activation.max_quote_age,
        )
        return self.snapshot

    def simulate_review_paper(
        self,
        *,
        activation: ReviewPaperActivation,
        persisted: PersistedReviewPaperWake,
        preview: ReviewPaperForwardPreview,
        as_of: datetime,
    ) -> OneWakeSyntheticEffectResult:
        if self.operator_used:
            raise UnattendedExecutionError("operator budget consumed")
        # Independent read-only reopen, including exact activation bytes/revision.
        verified = verify_unattended_state(
            self.state_store.path,
            expected_activation=activation,
            expected_wake_id=persisted.wake.wake_id,
            expected_wake=persisted.wake,
            expected_revision=persisted.revision,
        )
        if (
            activation is not self.activation
            or verified.state is not ReviewPaperWakeState.REVIEW_STARTED
            or preview.proposal is not activation.proposal
            or preview.risk_decision.proposal is not activation.proposal
            or preview.risk_limits is not activation.risk_limits
            or preview.price_snapshot is not self.snapshot
            or preview.risk_context.new_trading_enabled
            is not activation.new_trading_enabled
            or self.paper_store.history() != self.history
            or str(self.paper_store.path) != activation.store_path
            or self.paper_store.starting_cash != activation.starting_cash
            or as_of >= self.binding.oauth_valid_until
            or self.auth_factory is None
        ):
            raise UnattendedExecutionError("revalidated execution material mismatch")
        intent = build_review_paper_intent(
            preview.risk_decision,
            ExecutionInstruction(OrderType.MARKET, TimeInForce.DAY, as_of),
            order_id=activation.local_order_id,
        )
        self.operator_used = True
        b = self.binding
        evidence = run_robinhood_paper_operator(
            intent=intent,
            review_received_at=as_of,
            expected_branch=b.source_branch,
            expected_head=activation.source_head,
            expected_tree=activation.source_tree,
            paper_store_path=Path(activation.store_path),
            evidence_path=b.evidence_path,
            redirect_uri=b.redirect_uri,
            starting_cash=activation.starting_cash,
            slippage_basis_points=activation.slippage_basis_points,
            commission=activation.commission,
            oauth_factory=self.auth_factory,
        )
        if type(evidence) is not RobinhoodPaperOperatorEvidence:
            raise UnattendedExecutionError("operator evidence malformed")
        raw = b.evidence_path.read_bytes()
        expected_bytes = (json.dumps(asdict(evidence), sort_keys=True) + "\n").encode(
            "utf-8"
        )
        record = self.paper_store.get_by_order_id(activation.local_order_id)
        history = self.paper_store.history()
        replay = record in self.history
        if (
            raw != expected_bytes
            or evidence.status != "PASS"
            or evidence.phase != "complete"
            or evidence.source_head != activation.source_head
            or evidence.source_tree != activation.source_tree
            or (evidence.symbol, evidence.side, evidence.quantity, evidence.order_type)
            != (
                str(intent.symbol),
                intent.side.value,
                format(intent.approved_quantity, "f"),
                "MARKET",
            )
            or any(
                type(value) is not int or value != 0
                for value in (
                    evidence.get_equity_quotes_calls,
                    evidence.interactive_reauth_count,
                    evidence.placement_calls,
                    evidence.cancellation_calls,
                    evidence.options_mutation_calls,
                    evidence.crypto_mutation_calls,
                )
            )
            or any(
                value is not True
                for value in (
                    evidence.review_echo_validated,
                    evidence.quote_fill_validated,
                )
            )
            or evidence.replay is not replay
            or type(evidence.paper_record_count) is not int
            or evidence.paper_record_count != len(history)
            or type(record) is not ReviewPaperRecord
            or type(evidence.disclosure_present) is not bool
            or evidence.disclosure_present
            != (
                isinstance(record.review.market_data_disclosure, str)
                and bool(record.review.market_data_disclosure.strip())
            )
            or record.intent != intent
            or record.slippage_basis_points != activation.slippage_basis_points
            or record.commission != activation.commission
            or (
                record.review.symbol,
                record.review.side,
                record.review.quantity,
                record.review.order_type,
            )
            != (intent.symbol, intent.side, intent.approved_quantity, intent.order_type)
            or history != (self.history if replay else (*self.history, record))
        ):
            raise UnattendedExecutionError("operator/paper acknowledgement mismatch")
        counts = (
            evidence.get_accounts_calls,
            evidence.get_equity_orders_calls,
            evidence.review_equity_order_calls,
            evidence.baseline_order_pages,
            evidence.post_review_order_pages,
        )
        if any(type(value) is not int for value in counts) or (
            counts != (0, 0, 0, 0, 0)
            if replay
            else (
                counts[0] != 1
                or counts[2] != 1
                or not 1 <= counts[3] <= 100
                or not 1 <= counts[4] <= 100
                or counts[1] != counts[3] + counts[4]
            )
        ):
            raise UnattendedExecutionError("operator call budget mismatch")
        self.evidence = evidence
        self.digest = hashlib.sha256(raw).hexdigest()
        self.record = record
        return OneWakeSyntheticEffectResult(
            activation.activation_id,
            persisted.wake.wake_id,
            activation.local_order_id,
            True,
        )


def execute_one_unattended_review_paper_wake(
    *,
    activation: ReviewPaperActivation,
    expected: PersistedReviewPaperWake,
    state_store: UnattendedStateStore,
    paper_store: ReviewPaperStore,
    instants: OneWakeInstants,
    binding: UnattendedExecutionBinding,
    oauth_storage: WindowsOAuthStorage,
) -> UnattendedExecutionResult:
    """Bind one admitted 133-C wake; real access requires separate authorization.

    Source tests replace the actual transport/credential effect. Terminal and
    reconciliation-only replays never read OAuth, quote, or invoke the operator.
    """
    if (
        type(binding) is not UnattendedExecutionBinding
        or type(oauth_storage) is not WindowsOAuthStorage
    ):
        raise TypeError("exact explicit execution/OAuth bindings required")
    edges = _ExecutionEdges(
        activation, state_store, paper_store, binding, oauth_storage
    )
    wake = compose_one_review_paper_wake(
        activation=activation,
        expected=expected,
        state_store=state_store,
        paper_store=paper_store,
        instants=instants,
        quote_seam=edges,
        effect_seam=edges,
    )
    return UnattendedExecutionResult(
        wake,
        edges.evidence,
        edges.digest,
        None if edges.record is None else edges.record.paper_trade_id,
        None if edges.record is None else edges.record.fill_id,
    )
