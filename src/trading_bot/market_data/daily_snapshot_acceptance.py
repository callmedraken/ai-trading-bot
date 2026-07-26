"""Deterministic acceptance of one provider-neutral daily response."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from trading_bot.domain import Bar, Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data.daily_snapshot_identity import (
    canonical_bars_evidence,
    daily_snapshot_audit_hash,
    daily_snapshot_id,
)
from trading_bot.market_data.daily_snapshot_models import (
    DailyBarCandidate,
    DailyMarketDataSnapshot,
    DailyProviderRequest,
    DailyProviderResponse,
    DailySnapshotAcceptanceResult,
    DailySnapshotAcceptanceStatus,
    DailySnapshotBar,
    DailySnapshotDiagnostic,
    DailySnapshotDiagnosticCode,
    DailySnapshotFreshness,
    DailySnapshotRejectionClassification,
    SnapshotAuditEvidence,
)
from trading_bot.market_data.daily_snapshot_provider import (
    IdentifiedMarketCalendar,
    derive_completed_session,
    require_matching_calendar,
)
from trading_bot.market_data.exceptions import (
    InvalidDailySnapshotCalendarError,
    InvalidDailySnapshotResponseError,
)

_DIAGNOSTIC_ORDER = {
    code: position
    for position, code in enumerate(
        (
            DailySnapshotDiagnosticCode.REQUEST_RESPONSE_MISMATCH,
            DailySnapshotDiagnosticCode.PAGINATION_INCOMPLETE,
            DailySnapshotDiagnosticCode.INVALID_RESPONSE_ORDINAL,
            DailySnapshotDiagnosticCode.MALFORMED_CANDIDATE,
            DailySnapshotDiagnosticCode.SESSION_TIMESTAMP_MISMATCH,
            DailySnapshotDiagnosticCode.UNEXPECTED_SYMBOL,
            DailySnapshotDiagnosticCode.DUPLICATE_SYMBOL,
            DailySnapshotDiagnosticCode.MISSING_SYMBOL,
            DailySnapshotDiagnosticCode.NON_SESSION,
            DailySnapshotDiagnosticCode.MIXED_SESSION,
            DailySnapshotDiagnosticCode.FUTURE_SESSION,
            DailySnapshotDiagnosticCode.STALE_SESSION,
        )
    )
}

_CLASSIFICATION_PRECEDENCE = (
    (
        DailySnapshotRejectionClassification.REQUEST_RESPONSE_MISMATCH,
        frozenset({DailySnapshotDiagnosticCode.REQUEST_RESPONSE_MISMATCH}),
    ),
    (
        DailySnapshotRejectionClassification.INCOMPLETE_RESPONSE,
        frozenset({DailySnapshotDiagnosticCode.PAGINATION_INCOMPLETE}),
    ),
    (
        DailySnapshotRejectionClassification.MALFORMED_CANDIDATE,
        frozenset(
            {
                DailySnapshotDiagnosticCode.INVALID_RESPONSE_ORDINAL,
                DailySnapshotDiagnosticCode.MALFORMED_CANDIDATE,
                DailySnapshotDiagnosticCode.SESSION_TIMESTAMP_MISMATCH,
            }
        ),
    ),
    (
        DailySnapshotRejectionClassification.UNEXPECTED_SYMBOL,
        frozenset({DailySnapshotDiagnosticCode.UNEXPECTED_SYMBOL}),
    ),
    (
        DailySnapshotRejectionClassification.DUPLICATE_SYMBOL,
        frozenset({DailySnapshotDiagnosticCode.DUPLICATE_SYMBOL}),
    ),
    (
        DailySnapshotRejectionClassification.MISSING_SYMBOL,
        frozenset({DailySnapshotDiagnosticCode.MISSING_SYMBOL}),
    ),
    (
        DailySnapshotRejectionClassification.NON_SESSION,
        frozenset({DailySnapshotDiagnosticCode.NON_SESSION}),
    ),
    (
        DailySnapshotRejectionClassification.MIXED_SESSION,
        frozenset({DailySnapshotDiagnosticCode.MIXED_SESSION}),
    ),
    (
        DailySnapshotRejectionClassification.FUTURE,
        frozenset({DailySnapshotDiagnosticCode.FUTURE_SESSION}),
    ),
    (
        DailySnapshotRejectionClassification.STALE,
        frozenset({DailySnapshotDiagnosticCode.STALE_SESSION}),
    ),
)

REJECTION_CLASSIFICATION_PRECEDENCE = tuple(
    classification for classification, _ in _CLASSIFICATION_PRECEDENCE
)


def accept_daily_provider_response(
    request: DailyProviderRequest,
    response: DailyProviderResponse,
    calendar: IdentifiedMarketCalendar,
) -> DailySnapshotAcceptanceResult:
    """Accept one complete exact-session response or retain every rejection."""
    if type(request) is not DailyProviderRequest:
        raise InvalidDailySnapshotResponseError(
            "request must be a DailyProviderRequest"
        )
    if type(response) is not DailyProviderResponse:
        raise InvalidDailySnapshotResponseError(
            "response must be a DailyProviderResponse"
        )
    require_matching_calendar(request.capture_request, calendar)

    diagnostics: list[DailySnapshotDiagnostic] = []
    derived_target = derive_completed_session(request.capture_request, calendar)
    if request.target_session != derived_target or response.request != request:
        diagnostics.append(
            DailySnapshotDiagnostic(
                DailySnapshotDiagnosticCode.REQUEST_RESPONSE_MISMATCH,
                detail="provider request or frozen target does not reconcile",
            )
        )
    if not response.pagination_complete:
        diagnostics.append(
            DailySnapshotDiagnostic(
                DailySnapshotDiagnosticCode.PAGINATION_INCOMPLETE,
                detail="provider response is not complete",
            )
        )
    if (
        response.provider_as_of is not None
        and response.provider_as_of.astimezone(
            ZoneInfo(request.capture_request.calendar.exchange_timezone)
        ).date()
        < request.target_session.session_date
    ):
        diagnostics.append(
            DailySnapshotDiagnostic(
                DailySnapshotDiagnosticCode.STALE_SESSION,
                detail="provider_as_of precedes the frozen target session",
            )
        )

    valid_by_symbol: dict[Symbol, DailySnapshotBar] = {}
    seen_symbols: list[Symbol] = []
    candidate_sessions: set[TradingSession] = set()
    candidates_by_symbol: Counter[Symbol] = Counter()
    timezone = ZoneInfo(request.capture_request.calendar.exchange_timezone)

    for position, candidate in enumerate(response.candidates):
        if type(candidate) is not DailyBarCandidate:
            diagnostics.append(
                DailySnapshotDiagnostic(
                    DailySnapshotDiagnosticCode.MALFORMED_CANDIDATE,
                    response_ordinal=position,
                    detail="candidate must be DailyBarCandidate",
                )
            )
            continue

        ordinal_valid = (
            type(candidate.response_ordinal) is int
            and candidate.response_ordinal == position
        )
        if not ordinal_valid:
            diagnostics.append(
                DailySnapshotDiagnostic(
                    DailySnapshotDiagnosticCode.INVALID_RESPONSE_ORDINAL,
                    symbol=(
                        candidate.symbol if type(candidate.symbol) is Symbol else None
                    ),
                    response_ordinal=position,
                    detail="response ordinal must equal tuple position",
                )
            )

        if type(candidate.symbol) is Symbol:
            seen_symbols.append(candidate.symbol)
            candidates_by_symbol[candidate.symbol] += 1
            if candidate.symbol not in request.capture_request.symbols:
                diagnostics.append(
                    DailySnapshotDiagnostic(
                        DailySnapshotDiagnosticCode.UNEXPECTED_SYMBOL,
                        symbol=candidate.symbol,
                        response_ordinal=position,
                        detail="candidate symbol was not requested",
                    )
                )

        snapshot_bar = _validated_snapshot_bar(candidate)
        if snapshot_bar is None:
            diagnostics.append(
                DailySnapshotDiagnostic(
                    DailySnapshotDiagnosticCode.MALFORMED_CANDIDATE,
                    symbol=(
                        candidate.symbol if type(candidate.symbol) is Symbol else None
                    ),
                    response_ordinal=position,
                    detail="candidate scalar or OHLCV value is invalid",
                )
            )
            continue

        candidate_sessions.add(snapshot_bar.session)
        local_date = snapshot_bar.bar.timestamp.astimezone(timezone).date()
        if local_date != snapshot_bar.session.session_date:
            diagnostics.append(
                DailySnapshotDiagnostic(
                    DailySnapshotDiagnosticCode.SESSION_TIMESTAMP_MISMATCH,
                    symbol=snapshot_bar.bar.symbol,
                    response_ordinal=position,
                    detail="timestamp exchange date does not match session",
                )
            )
            continue

        is_session = _is_modeled_session(snapshot_bar.session, calendar, timezone)
        if not is_session:
            diagnostics.append(
                DailySnapshotDiagnostic(
                    DailySnapshotDiagnosticCode.NON_SESSION,
                    symbol=snapshot_bar.bar.symbol,
                    response_ordinal=position,
                    detail="candidate date is not a modeled XNYS session",
                )
            )
            continue
        if snapshot_bar.session.session_date > request.target_session.session_date:
            diagnostics.append(
                DailySnapshotDiagnostic(
                    DailySnapshotDiagnosticCode.FUTURE_SESSION,
                    symbol=snapshot_bar.bar.symbol,
                    response_ordinal=position,
                    detail="candidate session follows the frozen target",
                )
            )
            continue
        if snapshot_bar.session.session_date < request.target_session.session_date:
            diagnostics.append(
                DailySnapshotDiagnostic(
                    DailySnapshotDiagnosticCode.STALE_SESSION,
                    symbol=snapshot_bar.bar.symbol,
                    response_ordinal=position,
                    detail="candidate session precedes the frozen target",
                )
            )
            continue
        if (
            ordinal_valid
            and snapshot_bar.bar.symbol in request.capture_request.symbols
            and candidates_by_symbol[snapshot_bar.bar.symbol] == 1
        ):
            valid_by_symbol[snapshot_bar.bar.symbol] = snapshot_bar

    for symbol, count in candidates_by_symbol.items():
        if count > 1:
            diagnostics.append(
                DailySnapshotDiagnostic(
                    DailySnapshotDiagnosticCode.DUPLICATE_SYMBOL,
                    symbol=symbol,
                    detail="response contains more than one candidate for symbol",
                )
            )
            valid_by_symbol.pop(symbol, None)

    for symbol in request.capture_request.symbols:
        if candidates_by_symbol[symbol] == 0:
            diagnostics.append(
                DailySnapshotDiagnostic(
                    DailySnapshotDiagnosticCode.MISSING_SYMBOL,
                    symbol=symbol,
                    detail="provider response contains no candidate for symbol",
                )
            )

    if len(candidate_sessions) > 1:
        diagnostics.append(
            DailySnapshotDiagnostic(
                DailySnapshotDiagnosticCode.MIXED_SESSION,
                detail="provider candidates contain multiple session dates",
            )
        )

    if diagnostics:
        ordered = _ordered_diagnostics(diagnostics, request.capture_request.symbols)
        classification = _classification(ordered)
        return DailySnapshotAcceptanceResult(
            status=DailySnapshotAcceptanceStatus.REJECTED,
            freshness=_freshness(classification),
            snapshot=None,
            classification=classification,
            diagnostics=ordered,
        )

    bars = tuple(valid_by_symbol[symbol] for symbol in request.capture_request.symbols)
    identity = daily_snapshot_id(
        request.capture_request,
        request.target_session,
        request.provider,
        bars,
    )
    response_symbols = tuple(seen_symbols)
    audit_hash = daily_snapshot_audit_hash(
        snapshot_id=identity,
        requested_at=request.capture_request.requested_at,
        captured_at=response.captured_at,
        provider_as_of=response.provider_as_of,
        provider_request_id=response.provider_request_id,
        provider_response_symbols=response_symbols,
        source_payload=response.source_payload,
    )
    snapshot = DailyMarketDataSnapshot(
        snapshot_id=identity,
        request=request.capture_request,
        target_session=request.target_session,
        provider=request.provider,
        bars=bars,
        canonical_bars=canonical_bars_evidence(bars),
        audit=SnapshotAuditEvidence(
            captured_at=response.captured_at,
            provider_as_of=response.provider_as_of,
            provider_request_id=response.provider_request_id,
            provider_response_symbols=response_symbols,
            source_payload=response.source_payload,
            audit_sha256=audit_hash,
        ),
    )
    return DailySnapshotAcceptanceResult(
        status=DailySnapshotAcceptanceStatus.ACCEPTED,
        freshness=DailySnapshotFreshness.CURRENT,
        snapshot=snapshot,
        classification=None,
        diagnostics=(),
    )


def _validated_snapshot_bar(
    candidate: DailyBarCandidate,
) -> DailySnapshotBar | None:
    if (
        type(candidate.symbol) is not Symbol
        or type(candidate.session) is not TradingSession
        or type(candidate.timestamp) is not datetime
        or candidate.timestamp.tzinfo is None
        or candidate.timestamp.utcoffset() is None
        or any(
            type(value) is not Decimal or not value.is_finite() or value <= 0
            for value in (
                candidate.open,
                candidate.high,
                candidate.low,
                candidate.close,
            )
        )
        or type(candidate.volume) is not int
        or candidate.volume < 0
    ):
        return None
    try:
        return DailySnapshotBar(
            candidate.session,
            Bar(
                symbol=candidate.symbol,
                timestamp=candidate.timestamp,
                open=candidate.open,
                high=candidate.high,
                low=candidate.low,
                close=candidate.close,
                volume=candidate.volume,
            ),
        )
    except (TypeError, ValueError):
        return None


def _is_modeled_session(
    session: TradingSession,
    calendar: IdentifiedMarketCalendar,
    timezone: ZoneInfo,
) -> bool:
    local_noon = datetime.combine(session.session_date, time(12), tzinfo=timezone)
    result = calendar.is_trading_session(local_noon)
    if type(result) is not bool:
        raise InvalidDailySnapshotCalendarError(
            "calendar is_trading_session must return bool"
        )
    return result


def _ordered_diagnostics(
    diagnostics: list[DailySnapshotDiagnostic],
    symbols: tuple[Symbol, ...],
) -> tuple[DailySnapshotDiagnostic, ...]:
    symbol_positions = {symbol: position for position, symbol in enumerate(symbols)}
    fallback = len(symbols)
    return tuple(
        sorted(
            diagnostics,
            key=lambda item: (
                _DIAGNOSTIC_ORDER[item.code],
                (
                    symbol_positions[item.symbol]
                    if item.symbol in symbol_positions
                    else fallback
                ),
                "" if item.symbol is None else str(item.symbol),
                (item.response_ordinal if item.response_ordinal is not None else 2**31),
                item.detail,
            ),
        )
    )


def _classification(
    diagnostics: tuple[DailySnapshotDiagnostic, ...],
) -> DailySnapshotRejectionClassification:
    codes = frozenset(item.code for item in diagnostics)
    for classification, matching_codes in _CLASSIFICATION_PRECEDENCE:
        if codes & matching_codes:
            return classification
    raise InvalidDailySnapshotResponseError(
        "rejected response has no classified diagnostic"
    )


def _freshness(
    classification: DailySnapshotRejectionClassification,
) -> DailySnapshotFreshness:
    return {
        DailySnapshotRejectionClassification.REQUEST_RESPONSE_MISMATCH: (
            DailySnapshotFreshness.INVALID
        ),
        DailySnapshotRejectionClassification.INCOMPLETE_RESPONSE: (
            DailySnapshotFreshness.INCOMPLETE
        ),
        DailySnapshotRejectionClassification.MALFORMED_CANDIDATE: (
            DailySnapshotFreshness.INVALID
        ),
        DailySnapshotRejectionClassification.UNEXPECTED_SYMBOL: (
            DailySnapshotFreshness.INVALID
        ),
        DailySnapshotRejectionClassification.DUPLICATE_SYMBOL: (
            DailySnapshotFreshness.INVALID
        ),
        DailySnapshotRejectionClassification.MISSING_SYMBOL: (
            DailySnapshotFreshness.MISSING
        ),
        DailySnapshotRejectionClassification.NON_SESSION: (
            DailySnapshotFreshness.NON_SESSION
        ),
        DailySnapshotRejectionClassification.MIXED_SESSION: (
            DailySnapshotFreshness.INCONSISTENT
        ),
        DailySnapshotRejectionClassification.FUTURE: (DailySnapshotFreshness.FUTURE),
        DailySnapshotRejectionClassification.STALE: DailySnapshotFreshness.STALE,
    }[classification]
