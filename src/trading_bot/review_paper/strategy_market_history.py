"""134-B3 current Robinhood history acquisition and verified byte materialization."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailyBarCandidate,
    DailyProviderResponse,
    DailySnapshotCaptureRequest,
    DailySnapshotVerificationResult,
    ProviderDescriptor,
    SourcePayloadEvidence,
    accept_daily_provider_response,
    build_daily_provider_request,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.review_paper.production_strategy_decision import (
    CurrentStrategyDecisionPolicy,
    build_current_production_strategy_decision,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.robinhood_mcp.historical import (
    RobinhoodDailyHistory,
    RobinhoodDailyHistoryRequest,
    parse_equity_historicals_response,
)
from trading_bot.strategies.history_seed import (
    StrategyHistorySeedSourceDescriptor,
    VerifiedStrategyHistorySeed,
    create_strategy_history_seed,
    serialize_strategy_history_seed,
    verify_strategy_history_seed,
)
from trading_bot.strategies.production import ProductionStrategyContract
from trading_bot.strategies.production_decision import ProductionStrategyDecision

_PROVIDER = ProviderDescriptor("robinhood", 1, "get_equity_historicals", "regular")
_REQUEST_NAMESPACE = UUID("63169697-e9f7-58de-94d0-bcce34588901")


@dataclass(frozen=True, slots=True)
class ProductionStrategyHistoryEvidence:
    """Canonical bytes and verified inner evidence; no persistence/execution permit."""

    history: RobinhoodDailyHistory
    captured_at: datetime
    source_evidence_bytes: bytes
    snapshot_bytes: bytes
    history_seed_bytes: bytes
    snapshot_verification: DailySnapshotVerificationResult
    history_seed: VerifiedStrategyHistorySeed


def materialize_production_strategy_history(
    contract: ProductionStrategyContract,
    history: RobinhoodDailyHistory,
    *,
    captured_at: datetime,
) -> ProductionStrategyHistoryEvidence:
    """Replay the strict response, then use unchanged snapshot and seed verifiers."""
    if type(contract) is not ProductionStrategyContract:
        raise TypeError("contract must be exact ProductionStrategyContract")
    if type(history) is not RobinhoodDailyHistory:
        raise TypeError("history must be exact parsed RobinhoodDailyHistory")
    request = history.request
    _require_contract_request(contract, request)
    if (
        type(captured_at) is not datetime
        or captured_at.tzinfo is None
        or captured_at.utcoffset() is None
    ):
        raise ValueError("captured_at must be explicit aware datetime")
    captured_at = captured_at.astimezone(UTC)
    if (
        captured_at < request.requested_at
        or captured_at.astimezone(ZoneInfo("America/New_York")).date()
        != contract.target_session_date
    ):
        raise ValueError("capture must follow request within the target session date")
    # Parsed dataclasses are data, not provider authority: replay retained bytes.
    if (
        type(history.response_bytes) is not bytes
        or not 0 < len(history.response_bytes) <= 4 * 1024 * 1024
    ):
        raise ValueError("history response bytes must be bounded exact bytes")
    replay = parse_equity_historicals_response(
        json.loads(history.response_bytes), request
    )
    if replay != history:
        raise ValueError("history values and retained response bytes disagree")
    source_bytes = (
        json.dumps(
            {
                "schema": "robinhood-strategy-history-evidence/v1",
                "provider": "robinhood",
                "tool": "get_equity_historicals",
                "arguments": request.arguments(),
                "requested_at": canonical_timestamp(request.requested_at),
                "captured_at": canonical_timestamp(captured_at),
                "calendar": XNYS_CALENDAR_DESCRIPTOR.version,
                "sessions": [
                    item.session.session_date.isoformat() for item in history.bars
                ],
                "response": json.loads(history.response_bytes),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    parts = (
        "robinhood-daily-history-capture-request/v1",
        str(request.symbol),
        canonical_timestamp(request.requested_at),
        str(request.long_window),
        *(item.session.session_date.isoformat() for item in history.bars),
    )
    request_id = uuid5(
        _REQUEST_NAMESPACE,
        "".join(f"{len(item.encode('utf-8'))}:{item}" for item in parts),
    )
    capture = DailySnapshotCaptureRequest(
        request_id, (request.symbol,), request.requested_at, XNYS_CALENDAR_DESCRIPTOR
    )
    provider_request = build_daily_provider_request(
        capture, _PROVIDER, request.calendar
    )
    current = history.bars[-1]
    bar = current.bar
    candidate = DailyBarCandidate(
        0,
        bar.symbol,
        current.session,
        bar.timestamp,
        bar.open,
        bar.high,
        bar.low,
        bar.close,
        bar.volume,
    )
    response = DailyProviderResponse(
        provider_request,
        (candidate,),
        captured_at,
        None,
        None,
        SourcePayloadEvidence(
            sha256(history.response_bytes).hexdigest(),
            len(history.response_bytes),
            "application/json",
        ),
        True,
    )
    accepted = accept_daily_provider_response(
        provider_request, response, request.calendar
    )
    if accepted.snapshot is None:
        raise ValueError("Robinhood current daily snapshot acceptance failed")
    snapshot_bytes = serialize_daily_snapshot(accepted.snapshot)
    verification = verify_daily_snapshot(snapshot_bytes, request.calendar)
    if not verification.passed:
        raise ValueError("Robinhood current daily snapshot verification failed")
    seed = create_strategy_history_seed(
        symbol=request.symbol,
        # Schema v1 remains OFFLINE_SEED/non-authoritative. Provider provenance
        # belongs exclusively to the outer evidence, not an inner authority flag.
        source=StrategyHistorySeedSourceDescriptor("current-strategy-history.v1"),
        bars=history.bars[:-1],
    )
    seed_bytes = serialize_strategy_history_seed(seed)
    verified_seed = verify_strategy_history_seed(
        seed_bytes,
        expected_symbol=contract.symbol,
        target_session=current.session,
        strategy_config=contract.strategy_config,
        calendar=request.calendar,
    )
    return ProductionStrategyHistoryEvidence(
        history,
        captured_at,
        source_bytes,
        snapshot_bytes,
        seed_bytes,
        verification,
        verified_seed,
    )


def acquire_production_strategy_history(
    contract: ProductionStrategyContract,
    adapter: RobinhoodReviewReadAdapter,
    *,
    calendar: BoundMarketCalendar,
    requested_at: datetime,
    capture_time: Callable[[], datetime],
) -> ProductionStrategyHistoryEvidence:
    """One separately authorized historical read, no quote/review/account/fallback."""
    if type(contract) is not ProductionStrategyContract:
        raise TypeError("contract must be exact ProductionStrategyContract")
    if type(adapter) is not RobinhoodReviewReadAdapter:
        raise TypeError("adapter must be exact RobinhoodReviewReadAdapter")
    if not callable(capture_time):
        raise TypeError("capture_time must be callable")
    request = RobinhoodDailyHistoryRequest(
        contract.symbol, requested_at, contract.strategy_config.long_window, calendar
    )
    _require_contract_request(contract, request)
    history = adapter.equity_daily_history(request)
    return materialize_production_strategy_history(
        contract, history, captured_at=capture_time()
    )


def build_production_strategy_decision_from_history(
    contract: ProductionStrategyContract,
    store: ReviewPaperStore,
    *,
    evidence: ProductionStrategyHistoryEvidence,
    planning_at: datetime,
    caller_idempotency_key: str,
    policy: CurrentStrategyDecisionPolicy,
) -> ProductionStrategyDecision:
    """Replay materialization and delegate once to the accepted 134-B2 boundary."""
    if type(evidence) is not ProductionStrategyHistoryEvidence:
        raise TypeError("evidence must be exact ProductionStrategyHistoryEvidence")
    replay = materialize_production_strategy_history(
        contract, evidence.history, captured_at=evidence.captured_at
    )
    if replay != evidence:
        raise ValueError("history evidence does not replay exactly")
    return build_current_production_strategy_decision(
        contract,
        store,
        snapshot_verification=evidence.snapshot_verification,
        history_seed=evidence.history_seed,
        strategy_config=contract.strategy_config,
        calendar=evidence.history.request.calendar,
        planning_at=planning_at,
        caller_idempotency_key=caller_idempotency_key,
        policy=policy,
    )


def _require_contract_request(
    contract: ProductionStrategyContract, request: RobinhoodDailyHistoryRequest
) -> None:
    if type(request) is not RobinhoodDailyHistoryRequest:
        raise TypeError("request must be exact RobinhoodDailyHistoryRequest")
    if (
        request.symbol != contract.symbol
        or request.long_window != contract.strategy_config.long_window
        or request.requested_at.astimezone(ZoneInfo("America/New_York")).date()
        != contract.target_session_date
        or not request.calendar.is_trading_session(request.requested_at)
    ):
        raise ValueError(
            "history request symbol/config/session does not match contract"
        )
