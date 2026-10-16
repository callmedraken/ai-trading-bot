"""134-D1: current-product raw Alpaca history, without legacy host authority."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.market_calendar import NYSEMarketCalendar, TradingSession
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    XNYS_CALENDAR_DESCRIPTOR,
    AlpacaDailySnapshotProvider,
    AlpacaHttpStatusError,
    AlpacaResponseError,
    AlpacaResponseMetadataFailureReason,
    AlpacaTransportError,
    AlpacaTransportFailureStage,
    BoundMarketCalendar,
    DailySnapshotCaptureRequest,
    DailySnapshotVerificationResult,
    accept_daily_provider_response,
    build_daily_provider_request,
    replay_verified_daily_snapshot,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.review_paper.armed_history_failure import (
    HistoryFailureClassification,
    HistoryFailureDetails,
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


class ProductionHistoryAcquisitionFailure(RuntimeError):
    """Only closed semantic facts; no underlying error in args/repr/str."""

    def __init__(self, details: HistoryFailureDetails) -> None:
        if type(details) is not HistoryFailureDetails:
            raise ValueError("exact history failure details required")
        self.details = details
        super().__init__(details.classification.value)


def _history_stage[T](
    classification: HistoryFailureClassification,
    session: date,
    ordinal: int,
    action: Callable[[], T],
) -> T:
    try:
        return action()
    except Exception as error:
        stage = reason = status = code = None
        if classification is HistoryFailureClassification.INTERNAL_FAILED:
            if type(error) is AlpacaTransportError:
                classification = HistoryFailureClassification.TRANSPORT_FAILED
                stage = (
                    error.stage
                    if type(error.stage) is AlpacaTransportFailureStage
                    else AlpacaTransportFailureStage.UNKNOWN
                )
                if stage is AlpacaTransportFailureStage.RESPONSE_METADATA:
                    reason = (
                        error.metadata_reason
                        if type(error.metadata_reason)
                        is AlpacaResponseMetadataFailureReason
                        else AlpacaResponseMetadataFailureReason.GENERIC
                    )
            elif type(error) is AlpacaHttpStatusError:
                classification = HistoryFailureClassification.HTTP_FAILED
                status = (
                    error.status
                    if type(error.status) is int and 100 <= error.status <= 599
                    else None
                )
                code = (
                    error.provider_code
                    if type(error.provider_code) is int
                    and 0 <= error.provider_code <= (1 << 63) - 1
                    else None
                )
            elif type(error) is AlpacaResponseError:
                classification = HistoryFailureClassification.PROVIDER_RESPONSE_INVALID
        details = HistoryFailureDetails(
            session, ordinal, classification, stage, reason, status, code
        )
    # Raised outside the handler: underlying exception context is discarded.
    raise ProductionHistoryAcquisitionFailure(details) from None


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
    for ordinal, session in enumerate(sessions, 1):
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
        response = _history_stage(
            HistoryFailureClassification.INTERNAL_FAILED,
            session.session_date,
            ordinal,
            lambda frozen=frozen: provider.fetch(frozen),
        )

        def capture(response=response, last_capture=last_capture):
            captured = response.captured_at
            if (
                type(captured) is not datetime
                or captured.tzinfo is None
                or (
                    captured < last_capture
                    or captured.astimezone(zone).date() != contract.target_session_date
                )
            ):
                raise ValueError("capture observation rejected")
            return captured

        last_capture = _history_stage(
            HistoryFailureClassification.CAPTURE_OBSERVATION_REJECTED,
            session.session_date,
            ordinal,
            capture,
        )

        def accept(frozen=frozen, response=response):
            accepted = accept_daily_provider_response(frozen, response, calendar)
            if accepted.snapshot is None or accepted.diagnostics:
                raise ValueError("snapshot acceptance rejected")
            return accepted

        accepted = _history_stage(
            HistoryFailureClassification.SNAPSHOT_ACCEPTANCE_REJECTED,
            session.session_date,
            ordinal,
            accept,
        )

        def verify(accepted=accepted):
            payload = serialize_daily_snapshot(accepted.snapshot)
            verification = verify_daily_snapshot(payload, calendar)
            if not verification.passed:
                raise ValueError("snapshot verification rejected")
            return payload, verification, replay_verified_daily_snapshot(verification)

        payload, verification, replay = _history_stage(
            HistoryFailureClassification.SNAPSHOT_VERIFICATION_REJECTED,
            session.session_date,
            ordinal,
            verify,
        )

        def check_contract(replay=replay, session=session):
            if (
                replay.target_session != session
                or replay.symbols != (contract.symbol,)
                or len(replay.bars) != 1
            ):
                raise ValueError("verified history contract rejected")

        _history_stage(
            HistoryFailureClassification.VERIFIED_HISTORY_REJECTED,
            session.session_date,
            ordinal,
            check_contract,
        )
        payloads.append(payload)
        bars.extend(replay.bars)

    def build_seed():
        seed_bytes = serialize_strategy_history_seed(
            create_strategy_history_seed(
                symbol=contract.symbol,
                source=StrategyHistorySeedSourceDescriptor(
                    "alpaca-production-history.v1"
                ),
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
        return seed_bytes, seed

    seed_bytes, seed = _history_stage(
        HistoryFailureClassification.HISTORY_SEED_REJECTED,
        sessions[-1].session_date,
        len(sessions),
        build_seed,
    )
    return AlpacaProductionHistory(
        sessions, tuple(payloads), verification, seed_bytes, seed
    )
