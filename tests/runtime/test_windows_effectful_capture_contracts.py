from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

import pytest

from trading_bot.domain import Symbol
from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR, ProviderDescriptor
from trading_bot.runtime.windows_effectful_capture import (
    ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
    ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
    C3_CHILD_OPERATION_VERSION,
    C3_CREDENTIAL_POLICY_VERSION,
    C3_OUTPUT_POLICY_VERSION,
    BoundProductionCapturePlan,
    ProductionCapturePlan,
    ProductionCaptureRequest,
    ProductionProviderLaunchPlan,
    WindowsEffectfulCapturePlanError,
    bind_production_capture_plan,
    build_production_provider_launch_plan,
    derive_daily_snapshot_request_id,
    prepare_production_capture_plan,
)
from trading_bot.runtime.windows_transactional_authority import (
    snapshot_capture_request_for_test,
)

_RESERVATION = "11111111-1111-4111-8111-111111111111"
_OTHER_RESERVATION = "22222222-2222-4222-8222-222222222222"
_REQUEST_JSON = (
    b'{"bar_interval":"1d","child_operation_version":"child/v1",'
    b'"ordered_universe":["AAPL","MSFT"],"output_policy_version":"output/v1",'
    b'"permitted_provider_operation":"historical-stock-bars-v2-raw-usd-no-asof",'
    b'"provider_id":"alpaca-market-data","request_limit":2,'
    b'"request_window_end_date":"2026-08-14",'
    b'"request_window_start_date":"2026-08-13",'
    b'"target_session_date":"2026-08-17"}'
)
_REQUEST_DIGEST = "24a16ab9924dd76b36db8304af128741bd539e9e7238b114981db116eef73394"
_REQUEST_ID = "2db7da0e-e78b-5928-abb1-a8659705f414"


def _request(
    *,
    symbols: tuple[str, ...] = ("AAPL", "MSFT"),
    start: date = date(2026, 8, 13),
    end: date = date(2026, 8, 14),
    target: date = date(2026, 8, 17),
) -> ProductionCaptureRequest:
    return ProductionCaptureRequest(
        ordered_universe=tuple(Symbol(symbol) for symbol in symbols),
        request_window_start_date=start,
        request_window_end_date=end,
        target_session_date=target,
    )


def _requested_at(hour: int = 14) -> datetime:
    return datetime(2026, 8, 17, hour, tzinfo=UTC)


def _plan(*, requested_at: datetime | None = None) -> ProductionCapturePlan:
    return prepare_production_capture_plan(
        _request(),
        _requested_at() if requested_at is None else requested_at,
    )


def test_c3_request_builds_exact_c2_capture_request_bytes_and_digest() -> None:
    request = _request()

    assert request.canonical_c2_request_json() == _REQUEST_JSON
    assert hashlib.sha256(_REQUEST_JSON).hexdigest() == _REQUEST_DIGEST

    validated = snapshot_capture_request_for_test(request.to_c2_request_dict())
    assert validated.canonical_json() == _REQUEST_JSON


def test_c3_request_returns_fresh_c2_mapping_without_caller_alias() -> None:
    request = _request()
    first = request.to_c2_request_dict()
    first_universe = first["ordered_universe"]
    assert type(first_universe) is list
    first_universe.append("SPY")

    second = request.to_c2_request_dict()
    assert second["ordered_universe"] == ["AAPL", "MSFT"]
    assert second["request_limit"] == 2


def test_c3_request_rejects_duplicate_or_empty_universe() -> None:
    with pytest.raises(WindowsEffectfulCapturePlanError, match="duplicate-free"):
        ProductionCaptureRequest(
            ordered_universe=(Symbol("AAPL"), Symbol("AAPL")),
            request_window_start_date=date(2026, 8, 13),
            request_window_end_date=date(2026, 8, 14),
            target_session_date=date(2026, 8, 17),
        )

    with pytest.raises(WindowsEffectfulCapturePlanError, match="empty"):
        ProductionCaptureRequest(
            ordered_universe=(),
            request_window_start_date=date(2026, 8, 13),
            request_window_end_date=date(2026, 8, 14),
            target_session_date=date(2026, 8, 17),
        )


def test_c3_request_rejects_invalid_date_order() -> None:
    with pytest.raises(WindowsEffectfulCapturePlanError, match="start"):
        _request(start=date(2026, 8, 15), end=date(2026, 8, 14))

    with pytest.raises(WindowsEffectfulCapturePlanError, match="must precede"):
        _request(end=date(2026, 8, 17), target=date(2026, 8, 17))


def test_plan_selects_latest_xnys_session_inside_authorized_window() -> None:
    plan = _plan()

    assert plan.authorized_snapshot_session.session_date == date(2026, 8, 14)
    assert plan.requested_at_utc == _requested_at()
    assert plan.c2_request_json == _REQUEST_JSON
    assert plan.c2_request_digest == _REQUEST_DIGEST


def test_plan_accepts_weekend_invocation_for_friday_prior_session() -> None:
    plan = prepare_production_capture_plan(
        _request(),
        datetime(2026, 8, 15, 18, tzinfo=UTC),
    )

    assert plan.authorized_snapshot_session.session_date == date(2026, 8, 14)


def test_plan_uses_latest_session_when_window_ends_on_holiday() -> None:
    request = _request(
        start=date(2026, 7, 2),
        end=date(2026, 7, 3),
        target=date(2026, 7, 6),
    )
    plan = prepare_production_capture_plan(
        request,
        datetime(2026, 7, 4, 16, tzinfo=UTC),
    )

    assert plan.authorized_snapshot_session.session_date == date(2026, 7, 2)


def test_plan_rejects_window_without_modeled_session() -> None:
    request = _request(
        start=date(2026, 8, 15),
        end=date(2026, 8, 16),
        target=date(2026, 8, 17),
    )

    with pytest.raises(WindowsEffectfulCapturePlanError, match="contains no"):
        prepare_production_capture_plan(request, _requested_at())


def test_plan_rejects_naive_clock_and_late_backfill() -> None:
    with pytest.raises(WindowsEffectfulCapturePlanError, match="timezone-aware"):
        prepare_production_capture_plan(
            _request(),
            datetime(2026, 8, 17, 14),
        )

    with pytest.raises(WindowsEffectfulCapturePlanError, match="does not reconcile"):
        prepare_production_capture_plan(
            _request(),
            datetime(2026, 8, 18, 14, tzinfo=UTC),
        )


def test_plan_rejects_inconsistent_direct_construction() -> None:
    plan = _plan()

    with pytest.raises(WindowsEffectfulCapturePlanError, match="bytes"):
        ProductionCapturePlan(
            request=plan.request,
            requested_at_utc=plan.requested_at_utc,
            authorized_snapshot_session=plan.authorized_snapshot_session,
            c2_request_json=b"{}",
            c2_request_digest=plan.c2_request_digest,
        )

    with pytest.raises(WindowsEffectfulCapturePlanError, match="digest"):
        ProductionCapturePlan(
            request=plan.request,
            requested_at_utc=plan.requested_at_utc,
            authorized_snapshot_session=plan.authorized_snapshot_session,
            c2_request_json=plan.c2_request_json,
            c2_request_digest="00" * 32,
        )


def test_reservation_binding_produces_exact_provider_request_and_golden_uuid() -> None:
    plan = _plan()
    bound = bind_production_capture_plan(plan, _RESERVATION)

    assert type(bound) is BoundProductionCapturePlan
    assert str(bound.daily_snapshot_request.request_id) == _REQUEST_ID
    assert bound.daily_snapshot_request.symbols == (Symbol("AAPL"), Symbol("MSFT"))
    assert bound.daily_snapshot_request.requested_at == _requested_at()
    assert bound.provider_request.target_session == plan.authorized_snapshot_session
    assert bound.provider_request.provider == ALPACA_DAILY_SNAPSHOT_DESCRIPTOR


def test_daily_snapshot_request_identity_excludes_clock_but_binds_reservation() -> None:
    early = _plan(requested_at=datetime(2026, 8, 17, 14, tzinfo=UTC))
    later = _plan(requested_at=datetime(2026, 8, 17, 20, tzinfo=UTC))

    assert derive_daily_snapshot_request_id(early, _RESERVATION) == (
        derive_daily_snapshot_request_id(later, _RESERVATION)
    )
    assert derive_daily_snapshot_request_id(early, _RESERVATION) != (
        derive_daily_snapshot_request_id(early, _OTHER_RESERVATION)
    )


def test_reservation_binding_rejects_noncanonical_uuid_text() -> None:
    plan = _plan()

    with pytest.raises(WindowsEffectfulCapturePlanError, match="canonical UUID"):
        bind_production_capture_plan(plan, "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA")

    with pytest.raises(WindowsEffectfulCapturePlanError, match="canonical UUID"):
        bind_production_capture_plan(plan, "not-a-uuid")


def test_provider_launch_plan_is_secret_free_and_fixed() -> None:
    bound = bind_production_capture_plan(_plan(), _RESERVATION)
    launch = build_production_provider_launch_plan(bound)

    assert launch.reservation_id == _RESERVATION
    assert launch.c2_request_digest == _REQUEST_DIGEST
    assert launch.authorized_snapshot_session.session_date == date(2026, 8, 14)
    assert launch.provider_request == bound.provider_request
    assert launch.provider == ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
    assert launch.child_operation_version == C3_CHILD_OPERATION_VERSION
    assert launch.credential_policy_version == C3_CREDENTIAL_POLICY_VERSION
    assert launch.output_policy_version == C3_OUTPUT_POLICY_VERSION
    assert launch.api_key_id_credential_target == ALPACA_API_KEY_ID_CREDENTIAL_TARGET
    assert (
        launch.api_secret_key_credential_target
        == ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET
    )
    assert not hasattr(launch, "api_key_id")
    assert not hasattr(launch, "api_secret_key")


def test_provider_launch_plan_rejects_caller_override() -> None:
    bound = bind_production_capture_plan(_plan(), _RESERVATION)

    with pytest.raises(WindowsEffectfulCapturePlanError, match="provider"):
        ProductionProviderLaunchPlan(
            bound_capture=bound,
            provider=ProviderDescriptor(
                provider_id="alternate-provider",
                adapter_version=1,
                operation="alternate-operation",
                feed="sip",
            ),
        )

    with pytest.raises(WindowsEffectfulCapturePlanError, match="not fixed"):
        ProductionProviderLaunchPlan(
            bound_capture=bound,
            credential_policy_version="alternate/v1",
        )
