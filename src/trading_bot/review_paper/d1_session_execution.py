"""Mandatory D1R7-bound D1R8 successor; every effect belongs to this controller."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from trading_bot.domain import OrderType, Symbol, TimeInForce
from trading_bot.execution.models import ExecutionInstruction
from trading_bot.market_data import create_alpaca_daily_snapshot_provider
from trading_bot.review_paper import d1_session_authorization as prerequisite
from trading_bot.review_paper.alpaca_strategy_history import (
    acquire_current_production_strategy_history_from_alpaca,
    production_history_calendar,
)
from trading_bot.review_paper.alpaca_windows_credentials import (
    API_KEY_TARGET,
    API_SECRET_TARGET,
    validate_alpaca_credential_bytes,
)
from trading_bot.review_paper.armed_session_store import ArmedSessionStore
from trading_bot.review_paper.d1_session_execution_store import (
    BRANCH,
    MAX_BYTES,
    PRODUCER_HEAD,
    PRODUCER_TREE,
    Journal,
    digest,
    parse_journal,
    reservation_name,
    validate_facts,
)
from trading_bot.review_paper.forward_preview import build_review_paper_forward_preview
from trading_bot.review_paper.intent_bridge import build_review_paper_intent
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.review_paper.production_strategy_decision import (
    CurrentStrategyDecisionPolicy,
    build_current_production_strategy_decision,
)
from trading_bot.review_paper.risk_prices import build_review_paper_risk_price_snapshot
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.risk import RiskLimits, RiskOutcome
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.strategies.production import ProductionStrategyContract
from trading_bot.strategies.production_decision import ProductionStrategyDecisionStatus

INTERLOCK = "AUTHORIZE_ARCH134_D1R8_ONE_D1R7_BOUND_SYNTHETIC_PAPER_SESSION"
TOKEN_TARGET = "AITradingBot/Brokerage/Robinhood/MCP/OAuthTokens/v1"
CLIENT_TARGET = "AITradingBot/Brokerage/Robinhood/MCP/OAuthClientInfo/v1"


@dataclass(frozen=True, slots=True)
class ReviewedProof:
    """Reviewed assertions only; construction never grants source acceptance."""

    source: prerequisite.Source
    d1r7_bytes: int
    d1r7_sha256: str
    publication_confirmed: bool

    def __post_init__(self) -> None:
        if (
            type(self.source) is not prerequisite.Source
            or self.source.branch != BRANCH
            or type(self.d1r7_bytes) is not int
            or not 0 < self.d1r7_bytes <= prerequisite.MAX_BYTES
            or type(self.d1r7_sha256) is not str
            or len(self.d1r7_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.d1r7_sha256)
            or self.publication_confirmed is not True
        ):
            raise ValueError("reviewed source and completed publication proof required")


class Runtime(Protocol):
    """Host-owned seams, replaced only with disposable fakes during certification."""

    parent: Path
    paper_path: Path
    session_path: Path

    def clock(self) -> datetime: ...
    def admit_source(self, source: prerequisite.Source) -> tuple[Path, ...]: ...
    def admit_runtime(self) -> None: ...
    def write_readiness(self) -> None: ...
    def read_credential(self, target: str) -> bytearray: ...
    def alpaca_transport(self) -> object: ...
    def robinhood(
        self, records: tuple[bytearray, ...]
    ) -> tuple[RobinhoodReviewReadAdapter, object]: ...


class SessionExpired(ValueError):
    """Closed session/clock classification, without native diagnostics."""


def compatibility_evidence(contract: ProductionStrategyContract) -> dict:
    """Nonrecoverable existing-store fence, deliberately never HISTORY_STARTED."""
    return dict(
        schema="armed-paper-session/v1",
        source_head=contract.source_head,
        source_tree=contract.source_tree,
        contract_id=str(contract.contract_id),
        target_session=contract.target_session_date.isoformat(),
        historical_provider="alpaca",
        historical_sessions=[],
        snapshot_sha256=[],
        history_seed_sha256=None,
        operation_id=str(
            uuid5(
                NAMESPACE_URL,
                "arch134-d1r8-compatibility-fence/v1:SPY:"
                + contract.target_session_date.isoformat(),
            )
        ),
        order_id=None,
        fill_id=None,
        strategy_outcome=None,
        proposal_id=None,
        wait_started_at=None,
        admitted_at=None,
        admission_opens_at=None,
        admission_closes_at=None,
        prepare_result=None,
        execute_result=None,
        alpaca_reads=0,
        strategy_evaluations=0,
        prepare_attempts=0,
        execute_attempts=0,
        robinhood_get_equity_quotes=0,
        robinhood_get_accounts=0,
        robinhood_get_equity_orders=0,
        robinhood_review_equity_order=0,
        paper_mutations=0,
        broker_placement_count=0,
        effect_counts_complete=True,
        status="EXECUTE_STARTED",
    )


def run_session(runtime: Runtime, proof: ReviewedProof, interlock: str) -> str:
    """One current-session attempt; no sleeper, continuation, recovery or retry."""
    if (
        type(proof) is not ReviewedProof
        or type(interlock) is not str
        or interlock != INTERLOCK
    ):
        raise ValueError("D1R8 proof and interlock required")
    producer = prerequisite.Source(prerequisite.BRANCH, PRODUCER_HEAD, PRODUCER_TREE)
    roots = runtime.admit_source(proof.source)
    now = prerequisite.utc(runtime.clock())
    plan = prerequisite.Plan(producer, proof.source, now)
    prerequisite.checked_path(runtime.parent)
    predecessor_path = runtime.parent / plan.name
    original_stat = predecessor_path.lstat()
    predecessor_identity = original_stat.st_dev, original_stat.st_ino
    payload = prerequisite.read_evidence(
        predecessor_path, prerequisite.MAX_BYTES, predecessor_identity
    )
    records = prerequisite.parse_authorization(payload)
    # Parsing alone is insufficient: exact reviewed bytes, producer, successor,
    # publication completion assertion and current session are independently bound.
    facts = dict(
        prerequisite=records[0]["facts"],
        d1r7_bytes=proof.d1r7_bytes,
        d1r7_sha256=proof.d1r7_sha256,
        publication_confirmed=proof.publication_confirmed,
    )
    plan = validate_facts(facts)
    if (
        plan.intended_d1 != proof.source
        or len(payload) != proof.d1r7_bytes
        or hashlib.sha256(payload).hexdigest() != proof.d1r7_sha256
        or predecessor_path.name != plan.name
    ):
        raise ValueError("prerequisite/source binding rejected")
    contract = ProductionStrategyContract.from_json(
        prerequisite.canonical(plan.facts["strategy_contract"]).decode()
    )
    schedule = NYSEPublishedRegularSessionAuthority().schedule_for(plan.target)
    last_time = prerequisite.utc(plan.observed_at)
    published_at = last_time
    expires_at = plan.expires_at
    storage_ids = None
    durable_history = None
    prepared = None
    journal = None
    paper_reader = None

    def observe() -> datetime:
        nonlocal last_time
        at = prerequisite.utc(runtime.clock())
        if at < last_time:
            raise SessionExpired("clock regression")
        last_time = at
        if (
            at < published_at
            or at >= expires_at
            or at.astimezone(ZoneInfo("America/New_York")).date() != plan.target
            or at < prerequisite.utc(schedule.opens_at) + timedelta(seconds=300)
        ):
            raise SessionExpired("session not admitted")
        return at

    def paths() -> tuple:
        for path in (runtime.parent, runtime.paper_path, runtime.session_path):
            prerequisite.checked_path(path)
        if (
            not runtime.parent.is_dir()
            or runtime.paper_path.parent != runtime.session_path.parent
            or runtime.parent.resolve() == runtime.paper_path.parent.resolve()
            or any(
                p.resolve().is_relative_to(root.resolve())
                for root in roots
                for p in (runtime.parent, runtime.paper_path, runtime.session_path)
            )
        ):
            raise ValueError("external separated paths required")
        if {p.name for p in runtime.paper_path.parent.iterdir()} != {
            "paper.sqlite",
            "armed-sessions.sqlite",
        }:
            raise ValueError("runtime sidecar or unexpected path")
        if (
            runtime.paper_path.name != "paper.sqlite"
            or runtime.session_path.name != "armed-sessions.sqlite"
        ):
            raise ValueError("fixed store basenames required")
        identities = []
        for path in (runtime.paper_path, runtime.session_path):
            # The public stable reader validates regularity, links and open/path
            # identity. Runtime schemas and ledger are admitted separately.
            info = path.lstat()
            if not 100 <= info.st_size <= 64 * 1024 * 1024:
                raise ValueError("runtime database size rejected")
            database = prerequisite.read_evidence(
                path, info.st_size, (info.st_dev, info.st_ino)
            )
            if (
                database[:16] != b"SQLite format 3\x00"
                or database[18:20] != b"\x01\x01"
            ):
                raise ValueError("existing rollback-journal SQLite required")
            identities.append((info.st_dev, info.st_ino))
        if identities[0] == identities[1]:
            raise ValueError("store identities overlap")
        return tuple(identities)

    def read_store() -> ReviewPaperStore:
        nonlocal paper_reader
        if paper_reader is None:
            paper_reader = ReviewPaperStore(
                runtime.paper_path, starting_cash=Decimal("10000"), read_only=True
            )
        return paper_reader

    def guard() -> datetime:
        if runtime.admit_source(proof.source) != roots:
            raise ValueError("source registry changed")
        if (
            prerequisite.read_evidence(
                predecessor_path, prerequisite.MAX_BYTES, predecessor_identity
            )
            != payload
        ):
            raise ValueError("D1R7 changed")
        # The initial canonical parse is bound to these exact immutable bytes.
        # Identical stable rereads preserve that proof without reparsing it.
        if (
            journal is not None
            and prerequisite.read_evidence(
                journal.path, len(journal.expected), journal.identity
            )
            != journal.expected
        ):
            raise ValueError("D1R8 journal changed")
        if storage_ids is not None and paths() != storage_ids:
            raise ValueError("runtime identity changed")
        runtime.admit_runtime()
        if durable_history is not None and read_store().history() != durable_history:
            raise ValueError("paper state changed")
        at = observe()  # after potentially slow admission, never before it only
        if prepared is not None:
            snapshot, preview = prepared
            if any(
                at > mark.source_at + timedelta(seconds=60) for mark in snapshot.marks
            ):
                raise ValueError("prepared quote expired")
            if journal is None or journal.effects["paper_fill_mutations"] == 0:
                current = build_review_paper_forward_preview(
                    store=read_store(),
                    proposal=preview.proposal,
                    price_snapshot=snapshot,
                    risk_limits=RiskLimits(),
                    new_trading_enabled=True,
                )
                if current != preview:
                    raise ValueError("prepared risk/strategy state changed")
            observe()
        return at

    # All read-only admissions precede exclusive reservation or rollback writes.
    storage_ids = paths()
    runtime.admit_runtime()
    session_store = ArmedSessionStore(runtime.session_path)
    session_store.qualify()
    key = f"armed-paper-session/v1:SPY:{plan.target}"
    with closing(
        sqlite3.connect(runtime.session_path.resolve().as_uri() + "?mode=ro", uri=True)
    ) as connection:
        if connection.execute(
            "SELECT 1 FROM armed_session_v1 WHERE session_key=?", (key,)
        ).fetchone():
            raise ValueError("legacy session already consumed")
    durable_history = read_store().history()
    if any(
        r.intent.symbol == Symbol("SPY")
        and r.filled_at.astimezone(ZoneInfo("America/New_York")).date() == plan.target
        for r in durable_history
    ):
        raise ValueError("prior target paper fill")
    output = runtime.parent / reservation_name(plan.target.isoformat())
    if output.exists() or output.is_symlink():
        raise ValueError("D1R8 session consumed")
    guard()
    journal = Journal(runtime.parent, facts)
    blobs = []

    def state(name: str, result: object = None) -> None:
        journal.append(
            name,
            observe(),
            result_sha256=digest(result) if result is not None else None,
        )

    def effect(counter: str, operation: Callable[[], object]):
        guard()
        journal.append(journal.state, observe(), action="INTENT", counter=counter)
        guard()  # Intent durability/admission can be slow; recheck before entry.
        result = operation()
        journal.append(journal.state, observe(), action="ACK", counter=counter)
        return result

    def credentials(targets: tuple[str, ...], family: str) -> tuple[bytearray, ...]:
        selected = []
        for target in targets:

            def read_one(target=target):
                blob = runtime.read_credential(target)
                if type(blob) is bytearray:
                    blobs.append(blob)  # Own cleanup before ACK I/O can fail.
                return blob

            blob = effect(
                family + "_credential_reads",
                read_one,
            )
            if type(blob) is not bytearray or not 0 < len(blob) <= 2560:
                raise ValueError("credential rejected")
            selected.append(blob)
        return tuple(selected)

    def finish(result: str) -> str:
        guard()
        journal.append("FINAL", observe(), classification=result)
        journal.close()
        parse_journal(
            prerequisite.read_evidence(journal.path, MAX_BYTES, journal.identity)
        )
        guard()
        return result

    try:
        state("SESSION_RESERVED")
        state("SOURCE_AND_D1R7_BOUND")
        guard()
        state("WRITE_READINESS_STARTED")
        effect("write_readiness_attempts", runtime.write_readiness)
        state("WRITE_READINESS_CONFIRMED")
        guard()
        if (
            effect(
                "compatibility_reservations",
                lambda: session_store.reserve(key, compatibility_evidence(contract)),
            )
            is not None
        ):
            raise ValueError("legacy collision")
        state("LEGACY_SESSION_FENCE_CLAIMED")
        state("CREDENTIAL_READ_INTENT")
        alpaca_records = credentials((API_KEY_TARGET, API_SECRET_TARGET), "alpaca")
        for blob in alpaca_records:
            validate_alpaca_credential_bytes(blob)
        state("CREDENTIAL_READ_CONFIRMED")

        class HistoryTransport:
            def execute(self, request, **secrets):
                state("HISTORY_READ_INTENT")
                result = effect(
                    "alpaca_history_requests",
                    lambda: raw_transport.execute(request, **secrets),
                )
                state("HISTORY_READ_CONFIRMED")
                return result

        raw_transport = runtime.alpaca_transport()
        provider = create_alpaca_daily_snapshot_provider(
            transport=HistoryTransport(),
            clock=observe,
            environment={
                "APCA_API_KEY_ID": alpaca_records[0].decode(),
                "APCA_API_SECRET_KEY": alpaca_records[1].decode(),
            },
        )
        history = acquire_current_production_strategy_history_from_alpaca(
            contract, provider, requested_at=observe(), before_read=guard
        )
        state(
            "HISTORY_READY",
            {
                "snapshot_sha256": [
                    hashlib.sha256(p).hexdigest() for p in history.snapshot_bytes
                ],
                "history_seed_sha256": history.history_seed.artifact_sha256,
            },
        )
        state("STRATEGY_STARTED")
        decision = effect(
            "strategy_evaluations",
            lambda: build_current_production_strategy_decision(
                contract,
                read_store(),
                snapshot_verification=history.snapshot_verification,
                history_seed=history.history_seed,
                strategy_config=contract.strategy_config,
                calendar=production_history_calendar(),
                planning_at=observe(),
                caller_idempotency_key=f"arch134-d1r8/v1:SPY:{plan.target}",
                policy=CurrentStrategyDecisionPolicy(timedelta(seconds=600)),
            ),
        )
        state(
            "STRATEGY_DECIDED",
            {
                "contract_id": str(contract.contract_id),
                "status": decision.status.value,
                "proposal_id": str(decision.proposal.proposal_id)
                if decision.proposal
                else None,
            },
        )
        if decision.status is ProductionStrategyDecisionStatus.NO_SIGNAL:
            return finish("NO_SIGNAL")
        if decision.status is not ProductionStrategyDecisionStatus.TRADE_PROPOSAL:
            raise ValueError("strategy decision rejected")
        state("PREPARE_STARTED")
        effect("prepare_attempts", lambda: None)
        robinhood_records = credentials((TOKEN_TARGET, CLIENT_TARGET), "robinhood")
        adapter, resolver = runtime.robinhood(robinhood_records)
        if type(adapter) is not RobinhoodReviewReadAdapter:
            raise ValueError("typed read/review adapter required")
        state("QUOTE_INTENT")
        symbols = tuple(
            sorted(
                set(read_store().reconstruct_ledger().positions) | {contract.symbol},
                key=str,
            )
        )
        quotes = effect("quote_requests", lambda: adapter.equity_quotes(symbols))
        snapshot = build_review_paper_risk_price_snapshot(
            response=quotes,
            required_symbols=symbols,
            observed_at=observe(),
            max_quote_age=timedelta(seconds=60),
        )
        state("QUOTE_CONFIRMED")
        preview = build_review_paper_forward_preview(
            store=read_store(),
            proposal=decision.proposal,
            price_snapshot=snapshot,
            risk_limits=RiskLimits(),
            new_trading_enabled=True,
        )
        prepared = snapshot, preview
        state(
            "PREPARED",
            {
                "marks": [
                    [str(m.symbol), str(m.price), m.source_at.isoformat()]
                    for m in snapshot.marks
                ],
                "risk_outcome": preview.risk_decision.outcome.value,
                "approved_quantity": str(preview.risk_decision.approved_quantity),
            },
        )
        if preview.risk_decision.outcome is RiskOutcome.REJECTED:
            return finish("RISK_REJECTED")
        guard()
        state("EXECUTE_STARTED")
        effect("execute_attempts", lambda: None)
        intent = build_review_paper_intent(
            preview.risk_decision,
            ExecutionInstruction(OrderType.MARKET, TimeInForce.DAY, observe()),
            order_id=uuid5(NAMESPACE_URL, f"arch134-d1r8-order/v1:SPY:{plan.target}"),
        )
        state("ACCOUNT_READ")
        account = effect("account_resolutions", resolver.resolve)

        def order_window() -> None:
            cursor = None
            seen = set()
            for _ in range(100):
                page = effect(
                    "order_history_attempts",
                    lambda cursor=cursor: adapter.agentic_equity_orders(
                        account_number=account,
                        created_at_gte=intent.proposed_at,
                        cursor=cursor,
                        symbol=intent.symbol,
                    ),
                )
                if any(order is not None for order in page.orders):
                    raise ValueError("real-order window nonempty")
                if not page.next_cursor:
                    return
                if page.next_cursor in seen:
                    raise ValueError("order cursor cycle")
                cursor = page.next_cursor
                seen.add(cursor)
            raise ValueError("order pagination ceiling")

        state("BASELINE_ORDER_READS")
        order_window()
        state("REVIEW_INTENT")
        review = effect(
            "order_reviews",
            lambda: adapter.review_market_order(
                account_number=account, intent=intent, received_at=observe()
            ),
        )
        state("REVIEW_CONFIRMED")
        state("POST_REVIEW_ORDER_READS")
        order_window()
        # Review echo is enforced by the typed adapter; freshness and current
        # preparation are independently rechecked before the sole local mutation.
        at = guard()
        if (
            review.reviewed_at > at
            or review.reviewed_at < intent.proposed_at
            or any(
                not timedelta(0) <= at - stamp <= timedelta(seconds=60)
                for stamp in (
                    review.quote.venue_ask_time,
                    review.quote.venue_bid_time,
                    review.quote.venue_last_trade_time,
                )
            )
        ):
            raise ValueError("review quote freshness rejected")
        state("PAPER_WRITE_INTENT")

        def paper_write():
            # Writable construction occurs only behind the journal intent.
            store = ReviewPaperStore(runtime.paper_path, starting_cash=Decimal("10000"))
            return store.record_market_review(
                intent,
                review,
                slippage_basis_points=Decimal("0"),
                commission=Decimal("0"),
            )

        fill = effect("paper_fill_mutations", paper_write)
        after = read_store().history()
        if (
            len(after) != len(durable_history) + 1
            or after[:-1] != durable_history
            or after[-1] != fill
            or fill.intent != intent
        ):
            raise ValueError("paper acknowledgement rejected")
        durable_history = after
        state(
            "PAPER_WRITE_ACKNOWLEDGED",
            {
                "order_id": str(intent.order_id),
                "fill_id": str(fill.fill_id),
                "paper_trade_id": str(fill.paper_trade_id),
            },
        )
        return finish("PAPER_EXECUTED")
    except BaseException as error:
        result = (
            "INDETERMINATE"
            if (
                journal.pending is not None
                or journal.broken
                or journal.effects["paper_fill_mutations"] > 0
            )
            else ("SESSION_EXPIRED" if isinstance(error, SessionExpired) else "BLOCKED")
        )
        # No compensating write follows journal ambiguity. An unclosed/prefix or
        # terminal-looking file is consumed and cannot qualify execution.
        try:
            if not journal.broken and journal.stream is not None:
                journal.append("FINAL", last_time, classification=result)
            journal.close()
        except BaseException:
            result = "INDETERMINATE"
        return result
    finally:
        for blob in blobs:
            blob[:] = b"\x00" * len(blob)
