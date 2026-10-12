"""134-D1: current-product raw Alpaca history, without legacy host authority."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.market_calendar import NYSEMarketCalendar, TradingSession
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    XNYS_CALENDAR_DESCRIPTOR,
    AlpacaDailySnapshotProvider,
    BoundMarketCalendar,
    DailySnapshotCaptureRequest,
    DailySnapshotVerificationResult,
    accept_daily_provider_response,
    build_daily_provider_request,
    replay_verified_daily_snapshot,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.strategies.history_seed import (
    StrategyHistorySeedSourceDescriptor,
    VerifiedStrategyHistorySeed,
    create_strategy_history_seed,
    serialize_strategy_history_seed,
    verify_strategy_history_seed,
)
from trading_bot.strategies.production import ProductionStrategyContract

_NAMESPACE = UUID("cbdd7687-1c6e-503e-ab32-d06ca9f8749d")


def production_history_calendar() -> BoundMarketCalendar:
    return BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())


def required_alpaca_history_sessions(
    contract: ProductionStrategyContract,
) -> tuple[TradingSession, ...]:
    """Derive exactly long_window + 1 published consecutive completed sessions."""
    if type(contract) is not ProductionStrategyContract:
        raise TypeError("exact production contract required")
    if not 1 <= contract.strategy_config.long_window <= 252:
        raise ValueError("MVP history window exceeds bounded authority")
    authority = NYSEPublishedRegularSessionAuthority()
    if authority.schedule_for(contract.target_session_date) is None:
        raise ValueError("target is not a published session")
    calendar = production_history_calendar()
    zone = ZoneInfo("America/New_York")
    anchor = datetime.combine(contract.target_session_date, time.min, zone)
    sessions = []
    for _ in range(contract.strategy_config.long_window + 1):
        session = calendar.previous_session(anchor)
        if authority.schedule_for(session.session_date) is None:
            raise ValueError("completed history is outside published authority")
        sessions.append(session)
        anchor = datetime.combine(session.session_date, time.min, zone)
    return tuple(reversed(sessions))


@dataclass(frozen=True, slots=True)
class AlpacaProductionHistory:
    sessions: tuple[TradingSession, ...]
    snapshot_bytes: tuple[bytes, ...]
    snapshot_verification: DailySnapshotVerificationResult
    history_seed_bytes: bytes
    history_seed: VerifiedStrategyHistorySeed


def acquire_current_production_strategy_history_from_alpaca(
    contract: ProductionStrategyContract,
    provider: AlpacaDailySnapshotProvider,
    *,
    requested_at: datetime,
    before_read: Callable[[], None],
) -> AlpacaProductionHistory:
    """One fixed raw daily read per session; reject before advancing on any gap."""
    sessions = required_alpaca_history_sessions(contract)
    if type(provider) is not AlpacaDailySnapshotProvider:
        raise TypeError("exact existing Alpaca provider required")
    if type(requested_at) is not datetime or requested_at.tzinfo is None:
        raise ValueError("aware acquisition observation required")
    zone = ZoneInfo("America/New_York")
    if requested_at.astimezone(zone).date() != contract.target_session_date:
        raise ValueError("acquisition must occur on target session date")
    calendar = production_history_calendar()
    payloads = []
    bars = []
    verification = None
    last_capture = requested_at.astimezone(UTC)
    for session in sessions:
        # Older request timestamps are calendar selectors, not fabricated clock
        # observations. Actual provider captured_at remains unchanged in audit.
        selector = (
            requested_at
            if session == sessions[-1]
            else datetime.combine(
                session.session_date + timedelta(days=1), time.min, zone
            )
        )
        material = (
            "alpaca-production-history-request/v1",
            str(contract.contract_id),
            session.session_date.isoformat(),
        )
        request = DailySnapshotCaptureRequest(
            uuid5(_NAMESPACE, "".join(f"{len(x)}:{x}" for x in material)),
            (contract.symbol,),
            selector,
            XNYS_CALENDAR_DESCRIPTOR,
        )
        frozen = build_daily_provider_request(
            request, ALPACA_DAILY_SNAPSHOT_DESCRIPTOR, calendar
        )
        if frozen.target_session != session:
            raise ValueError("calendar selector disagrees with required session")
        before_read()
        response = provider.fetch(frozen)
        captured = response.captured_at
        if (
            captured < last_capture
            or captured.astimezone(zone).date() != contract.target_session_date
        ):
            raise ValueError("capture crossed target date or regressed")
        last_capture = captured
        accepted = accept_daily_provider_response(frozen, response, calendar)
        if accepted.snapshot is None or accepted.diagnostics:
            raise ValueError("Alpaca daily snapshot rejected")
        payload = serialize_daily_snapshot(accepted.snapshot)
        verification = verify_daily_snapshot(payload, calendar)
        if not verification.passed:
            raise ValueError("Alpaca snapshot canonical verification failed")
        replay = replay_verified_daily_snapshot(verification)
        if (
            replay.target_session != session
            or replay.symbols != (contract.symbol,)
            or len(replay.bars) != 1
        ):
            raise ValueError("verified history is outside exact contract")
        payloads.append(payload)
        bars.extend(replay.bars)
    seed_bytes = serialize_strategy_history_seed(
        create_strategy_history_seed(
            symbol=contract.symbol,
            source=StrategyHistorySeedSourceDescriptor("alpaca-production-history.v1"),
            bars=tuple(bars[:-1]),
        )
    )
    seed = verify_strategy_history_seed(
        seed_bytes,
        expected_symbol=contract.symbol,
        target_session=sessions[-1],
        strategy_config=contract.strategy_config,
        calendar=calendar,
    )
    return AlpacaProductionHistory(
        sessions, tuple(payloads), verification, seed_bytes, seed
    )
