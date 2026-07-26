from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from tests.market_data.daily_snapshot_test_support import (
    CAPTURED_AT,
    PROVIDER,
    QQQ,
    SOURCE_PAYLOAD,
    SPY,
    accepted_result,
    calendar,
    candidate,
    capture_request,
)

from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    DailyBarCandidate,
    DailyProviderResponse,
    DailySnapshotAcceptanceStatus,
    DailySnapshotDiagnosticCode,
    DailySnapshotFreshness,
    DailySnapshotRejectionClassification,
    accept_daily_provider_response,
    build_daily_provider_request,
)


def test_acceptance_normalizes_valid_bars_to_caller_order() -> None:
    result = accepted_result()

    assert result.status is DailySnapshotAcceptanceStatus.ACCEPTED
    assert result.freshness is DailySnapshotFreshness.CURRENT
    assert result.diagnostics == ()
    assert result.snapshot is not None
    assert tuple(item.bar.symbol for item in result.snapshot.bars) == (SPY, QQQ)
    assert result.snapshot.audit.provider_response_symbols == (QQQ, SPY)


def test_rejection_retains_all_diagnostics_in_fixed_precedence() -> None:
    request = capture_request()
    bound_calendar = calendar()
    provider_request = build_daily_provider_request(request, PROVIDER, bound_calendar)
    stale = TradingSession(date(2025, 1, 3))
    future = TradingSession(date(2025, 1, 7))
    holiday = TradingSession(date(2025, 1, 1))
    extra = Symbol("DIA")
    candidates = (
        candidate(SPY, 7),
        candidate(SPY, 1),
        candidate(
            QQQ,
            2,
            session=stale,
            timestamp=datetime(2025, 1, 3, 5, tzinfo=UTC),
        ),
        candidate(
            extra,
            3,
            session=future,
            timestamp=datetime(2025, 1, 7, 5, tzinfo=UTC),
        ),
        candidate(
            extra,
            4,
            session=holiday,
            timestamp=datetime(2025, 1, 1, 5, tzinfo=UTC),
        ),
    )
    response = DailyProviderResponse(
        provider_request,
        candidates,
        CAPTURED_AT,
        None,
        None,
        SOURCE_PAYLOAD,
        False,
    )

    result = accept_daily_provider_response(provider_request, response, bound_calendar)

    assert result.status is DailySnapshotAcceptanceStatus.REJECTED
    assert result.snapshot is None
    assert (
        result.classification
        is DailySnapshotRejectionClassification.INCOMPLETE_RESPONSE
    )
    codes = tuple(item.code for item in result.diagnostics)
    assert codes == tuple(
        sorted(
            codes,
            key=lambda code: (
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
            ).index(code),
        )
    )
    assert {
        DailySnapshotDiagnosticCode.PAGINATION_INCOMPLETE,
        DailySnapshotDiagnosticCode.INVALID_RESPONSE_ORDINAL,
        DailySnapshotDiagnosticCode.UNEXPECTED_SYMBOL,
        DailySnapshotDiagnosticCode.DUPLICATE_SYMBOL,
        DailySnapshotDiagnosticCode.NON_SESSION,
        DailySnapshotDiagnosticCode.MIXED_SESSION,
        DailySnapshotDiagnosticCode.FUTURE_SESSION,
        DailySnapshotDiagnosticCode.STALE_SESSION,
    } <= set(codes)


@pytest.mark.parametrize(
    ("candidate_value", "expected_code"),
    [
        (
            DailyBarCandidate(
                0,
                SPY,
                TradingSession(date(2025, 1, 6)),
                datetime(2025, 1, 6, 5, tzinfo=UTC),
                Decimal("NaN"),
                Decimal("2"),
                Decimal("1"),
                Decimal("1"),
                1,
            ),
            DailySnapshotDiagnosticCode.MALFORMED_CANDIDATE,
        ),
        (
            DailyBarCandidate(
                0,
                SPY,
                TradingSession(date(2025, 1, 6)),
                datetime(2025, 1, 6, 5, tzinfo=UTC),
                Decimal("1"),
                Decimal("2"),
                Decimal("1"),
                Decimal("1"),
                True,
            ),
            DailySnapshotDiagnosticCode.MALFORMED_CANDIDATE,
        ),
    ],
)
def test_malformed_decimals_and_bool_volume_are_rejected(
    candidate_value: DailyBarCandidate,
    expected_code: DailySnapshotDiagnosticCode,
) -> None:
    result = accepted_result(
        request=capture_request(symbols=(SPY,)),
        candidates=(candidate_value,),
    )

    assert result.status is DailySnapshotAcceptanceStatus.REJECTED
    assert expected_code in {item.code for item in result.diagnostics}
    assert result.classification is (
        DailySnapshotRejectionClassification.MALFORMED_CANDIDATE
    )


@pytest.mark.parametrize(
    ("session", "timestamp", "classification", "freshness"),
    [
        (
            TradingSession(date(2025, 1, 3)),
            datetime(2025, 1, 3, 5, tzinfo=UTC),
            DailySnapshotRejectionClassification.STALE,
            DailySnapshotFreshness.STALE,
        ),
        (
            TradingSession(date(2025, 1, 7)),
            datetime(2025, 1, 7, 5, tzinfo=UTC),
            DailySnapshotRejectionClassification.FUTURE,
            DailySnapshotFreshness.FUTURE,
        ),
        (
            TradingSession(date(2025, 1, 1)),
            datetime(2025, 1, 1, 5, tzinfo=UTC),
            DailySnapshotRejectionClassification.NON_SESSION,
            DailySnapshotFreshness.NON_SESSION,
        ),
    ],
)
def test_temporal_rejections_keep_specific_top_level_classification(
    session: TradingSession,
    timestamp: datetime,
    classification: DailySnapshotRejectionClassification,
    freshness: DailySnapshotFreshness,
) -> None:
    result = accepted_result(
        request=capture_request(symbols=(SPY,)),
        candidates=(candidate(SPY, 0, session=session, timestamp=timestamp),),
    )

    assert result.classification is classification
    assert result.freshness is freshness
    assert DailySnapshotDiagnosticCode.MISSING_SYMBOL not in {
        item.code for item in result.diagnostics
    }


def test_absent_requested_symbol_is_classified_as_missing() -> None:
    result = accepted_result(candidates=(candidate(SPY, 0),))

    assert result.classification is DailySnapshotRejectionClassification.MISSING_SYMBOL
    assert result.freshness is DailySnapshotFreshness.MISSING
    assert tuple(item.symbol for item in result.diagnostics) == (QQQ,)


def test_provider_as_of_before_target_is_stale() -> None:
    result = accepted_result(provider_as_of=datetime(2025, 1, 3, 22, tzinfo=UTC))

    assert result.classification is DailySnapshotRejectionClassification.STALE
    assert result.freshness is DailySnapshotFreshness.STALE


def test_response_request_mismatch_has_highest_classification() -> None:
    request = capture_request()
    other = capture_request(
        request_id=request.request_id,
        requested_at=datetime(2025, 1, 8, 18, tzinfo=UTC),
    )
    bound_calendar = calendar()
    expected = build_daily_provider_request(request, PROVIDER, bound_calendar)
    returned = build_daily_provider_request(other, PROVIDER, bound_calendar)
    response = DailyProviderResponse(
        returned,
        (),
        datetime(2025, 1, 8, 18, 0, 1, tzinfo=UTC),
        None,
        None,
        SOURCE_PAYLOAD,
        False,
    )

    result = accept_daily_provider_response(expected, response, bound_calendar)

    assert (
        result.classification
        is DailySnapshotRejectionClassification.REQUEST_RESPONSE_MISMATCH
    )
