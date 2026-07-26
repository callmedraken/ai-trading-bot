"""Focused tests for pure verified-snapshot paper-cycle preparation."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_DOWN, ROUND_UP, Decimal, localcontext
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from tests.market_data.daily_snapshot_test_support import (
    CAPTURED_AT,
    QQQ,
    SPY,
    accepted_result,
    calendar,
    candidate,
    capture_request,
)

from trading_bot.domain import Symbol
from trading_bot.execution import PaperFillPolicy
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailySnapshotVerificationStatus,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.rebalancing import (
    RebalanceAssumptions,
    RebalanceProposalPolicy,
)
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime import (
    CallerAssertedNextSessionOpenReference,
    ExplicitQuantityTarget,
    ExplicitQuantityTargetPortfolio,
    InvalidVerifiedSnapshotPaperCyclePreparationRequestError,
    PaperPortfolioRuntime,
    VerifiedDailySnapshotReference,
    VerifiedSnapshotAccountPosition,
    VerifiedSnapshotAccountState,
    VerifiedSnapshotPaperCyclePolicies,
    VerifiedSnapshotPaperCyclePolicyError,
    VerifiedSnapshotPaperCyclePreparationDiagnosticCode,
    VerifiedSnapshotPaperCyclePreparationRequest,
    VerifiedSnapshotPaperCycleSnapshotError,
    VerifiedSnapshotPaperCycleTargetError,
    VerifiedSnapshotPaperCycleTemporalError,
    VerifiedSnapshotPaperCycleUniverseError,
    prepare_verified_snapshot_paper_cycle,
)

_ACCOUNT_STATE_ID = UUID("7b93f860-fef6-5bc0-a60b-746bb1f35c5e")
_TARGET_ID = UUID("bf8999ae-f854-553d-9fd8-4c49e3424442")
_REQUEST_ID = UUID("0cf415b3-bdf4-55e5-9f0e-b0f680769e65")
_NEXT_SESSION = TradingSession(date(2025, 1, 7))


def _verification():
    snapshot = accepted_result().snapshot
    assert snapshot is not None
    payload = serialize_daily_snapshot(snapshot)
    return verify_daily_snapshot(payload, calendar())


def _policies(
    *,
    assumptions: RebalanceAssumptions | None = None,
    risk_limits: RiskLimits | None = None,
    risk_policy: PortfolioRiskPolicy | None = None,
    fill_policy: PaperFillPolicy | None = None,
    trading_enabled: bool = True,
) -> VerifiedSnapshotPaperCyclePolicies:
    return VerifiedSnapshotPaperCyclePolicies(
        assumptions or RebalanceAssumptions(),
        None,
        RebalanceProposalPolicy(allow_partial_plans=True),
        None,
        risk_limits
        or RiskLimits(
            max_position_percent=Decimal("0.80"),
            max_total_exposure_percent=Decimal("0.90"),
            minimum_cash_reserve_percent=Decimal("0.10"),
        ),
        risk_policy or PortfolioRiskPolicy(True),
        fill_policy or PaperFillPolicy(),
        trading_enabled,
    )


def _request(
    *,
    verification=None,
    reference: VerifiedDailySnapshotReference | None = None,
    account_state: VerifiedSnapshotAccountState | None = None,
    target: ExplicitQuantityTargetPortfolio | None = None,
    open_references: tuple[CallerAssertedNextSessionOpenReference, ...] | None = None,
    policies: VerifiedSnapshotPaperCyclePolicies | None = None,
    planning_at: datetime | None = None,
    submitted_at: datetime | None = None,
    filled_at: datetime | None = None,
) -> VerifiedSnapshotPaperCyclePreparationRequest:
    verification = verification or _verification()
    snapshot = verification.snapshot
    assert snapshot is not None
    planning_at = planning_at or CAPTURED_AT + timedelta(minutes=1)
    submitted_at = submitted_at or planning_at + timedelta(minutes=1)
    filled_at = filled_at or datetime(2025, 1, 7, 20, 0, tzinfo=UTC)
    return VerifiedSnapshotPaperCyclePreparationRequest(
        _REQUEST_ID,
        reference
        or VerifiedDailySnapshotReference(
            snapshot.snapshot_id,
            verification.sha256,
            verification.byte_length,
        ),
        account_state
        or VerifiedSnapshotAccountState(
            _ACCOUNT_STATE_ID,
            CAPTURED_AT - timedelta(minutes=1),
            Decimal("972.50"),
            (
                VerifiedSnapshotAccountPosition(
                    SPY,
                    Decimal("10"),
                    Decimal("100"),
                ),
            ),
        ),
        target
        or ExplicitQuantityTargetPortfolio(
            _TARGET_ID,
            (
                ExplicitQuantityTarget(SPY, Decimal("0")),
                ExplicitQuantityTarget(QQQ, Decimal("5")),
            ),
            Decimal("985"),
        ),
        open_references
        or (
            CallerAssertedNextSessionOpenReference(
                SPY,
                _NEXT_SESSION,
                Decimal("103"),
            ),
            CallerAssertedNextSessionOpenReference(
                QQQ,
                _NEXT_SESSION,
                Decimal("204"),
            ),
        ),
        policies or _policies(),
        planning_at,
        submitted_at,
        filled_at,
    )


def _prepare(**request_overrides):
    verification = request_overrides.pop("verification", None) or _verification()
    return prepare_verified_snapshot_paper_cycle(
        _request(verification=verification, **request_overrides),
        verification,
        calendar(),
    )


def _assert_code(error, code) -> None:
    assert error.value.diagnostic.code is code


def test_prepares_normalized_account_explicit_zero_and_exact_planner_inputs() -> None:
    prepared = _prepare()

    assert tuple(item.symbol for item in prepared.account_state.positions) == (
        SPY,
        QQQ,
    )
    assert prepared.account_state.positions[1].quantity == Decimal("0")
    assert prepared.account_state.positions[1].average_cost == Decimal("0")
    assert prepared.portfolio_state.equity == Decimal("2000.00")
    assert tuple(item.planning_close for item in prepared.close_marks) == (
        Decimal("102.750"),
        Decimal("203.00"),
    )
    assert prepared.target.quantities[0].quantity == Decimal("0")
    assert prepared.target_portfolio.allocations[0].weight == Decimal("0")
    plan = (
        __import__(
            "trading_bot.rebalancing",
            fromlist=["RebalancePlanner"],
        )
        .RebalancePlanner()
        .plan(prepared.planner_request)
    )
    assert tuple(item.target_quantity for item in plan.deviations) == (
        Decimal("0"),
        Decimal("5"),
    )
    assert prepared.next_session == _NEXT_SESSION
    assert not hasattr(prepared, "verification")
    with pytest.raises(FrozenInstanceError):
        prepared.request_id = UUID(int=0)  # type: ignore[misc]


@pytest.mark.parametrize("field", ("snapshot_id", "sha256", "byte_length"))
def test_rejects_snapshot_reference_mismatch(field: str) -> None:
    verification = _verification()
    snapshot = verification.snapshot
    assert snapshot is not None
    values = {
        "snapshot_id": snapshot.snapshot_id,
        "sha256": verification.sha256,
        "byte_length": verification.byte_length,
    }
    values[field] = (
        UUID("aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa")
        if field == "snapshot_id"
        else "0" * 64
        if field == "sha256"
        else verification.byte_length + 1
    )
    reference = VerifiedDailySnapshotReference(
        values["snapshot_id"],
        values["sha256"],
        values["byte_length"],
    )

    with pytest.raises(VerifiedSnapshotPaperCycleSnapshotError) as error:
        _prepare(verification=verification, reference=reference)

    _assert_code(
        error,
        VerifiedSnapshotPaperCyclePreparationDiagnosticCode.SNAPSHOT_REFERENCE_MISMATCH,
    )


def test_rejects_non_pass_verification() -> None:
    failed = verify_daily_snapshot(b"{}", calendar())
    assert failed.status is DailySnapshotVerificationStatus.FAIL

    with pytest.raises(VerifiedSnapshotPaperCycleSnapshotError) as error:
        prepare_verified_snapshot_paper_cycle(_request(), failed, calendar())

    _assert_code(
        error,
        VerifiedSnapshotPaperCyclePreparationDiagnosticCode.SNAPSHOT_VERIFICATION_REQUIRED,
    )


def test_rejects_account_symbol_absent_from_snapshot() -> None:
    account = VerifiedSnapshotAccountState(
        _ACCOUNT_STATE_ID,
        CAPTURED_AT - timedelta(minutes=1),
        Decimal("972.50"),
        (
            VerifiedSnapshotAccountPosition(
                Symbol("IWM"),
                Decimal("1"),
                Decimal("100"),
            ),
        ),
    )

    with pytest.raises(VerifiedSnapshotPaperCycleUniverseError) as error:
        _prepare(account_state=account)

    _assert_code(
        error,
        VerifiedSnapshotPaperCyclePreparationDiagnosticCode.ACCOUNT_UNIVERSE_MISMATCH,
    )


@pytest.mark.parametrize(
    "target",
    (
        ExplicitQuantityTargetPortfolio(
            _TARGET_ID,
            (ExplicitQuantityTarget(SPY, Decimal("0")),),
            Decimal("2000"),
        ),
        ExplicitQuantityTargetPortfolio(
            _TARGET_ID,
            (
                ExplicitQuantityTarget(QQQ, Decimal("5")),
                ExplicitQuantityTarget(SPY, Decimal("0")),
            ),
            Decimal("985"),
        ),
    ),
)
def test_rejects_target_omission_or_wrong_order(
    target: ExplicitQuantityTargetPortfolio,
) -> None:
    with pytest.raises(VerifiedSnapshotPaperCycleUniverseError) as error:
        _prepare(target=target)

    _assert_code(
        error,
        VerifiedSnapshotPaperCyclePreparationDiagnosticCode.TARGET_UNIVERSE_MISMATCH,
    )


def test_rejects_open_reference_universe_mismatch() -> None:
    references = (
        CallerAssertedNextSessionOpenReference(
            QQQ,
            _NEXT_SESSION,
            Decimal("204"),
        ),
        CallerAssertedNextSessionOpenReference(
            SPY,
            _NEXT_SESSION,
            Decimal("103"),
        ),
    )

    with pytest.raises(VerifiedSnapshotPaperCycleUniverseError) as error:
        _prepare(open_references=references)

    _assert_code(
        error,
        VerifiedSnapshotPaperCyclePreparationDiagnosticCode.OPEN_REFERENCE_UNIVERSE_MISMATCH,
    )


def test_rejects_target_cash_mismatch() -> None:
    target = ExplicitQuantityTargetPortfolio(
        _TARGET_ID,
        (
            ExplicitQuantityTarget(SPY, Decimal("0")),
            ExplicitQuantityTarget(QQQ, Decimal("5")),
        ),
        Decimal("984.99"),
    )

    with pytest.raises(VerifiedSnapshotPaperCycleTargetError) as error:
        _prepare(target=target)

    _assert_code(
        error,
        VerifiedSnapshotPaperCyclePreparationDiagnosticCode.TARGET_CASH_MISMATCH,
    )


def test_rejects_nonrepresentable_quantity_target() -> None:
    account = VerifiedSnapshotAccountState(
        _ACCOUNT_STATE_ID,
        CAPTURED_AT - timedelta(minutes=1),
        Decimal("12.33"),
    )
    target = ExplicitQuantityTargetPortfolio(
        _TARGET_ID,
        (
            ExplicitQuantityTarget(SPY, Decimal("0.04")),
            ExplicitQuantityTarget(QQQ, Decimal("0")),
        ),
        Decimal("8.22"),
    )

    with pytest.raises(VerifiedSnapshotPaperCycleTargetError) as error:
        _prepare(account_state=account, target=target)

    _assert_code(
        error,
        VerifiedSnapshotPaperCyclePreparationDiagnosticCode.QUANTITY_TARGET_NOT_EXACTLY_REPRESENTABLE,
    )


@pytest.mark.parametrize(
    "value",
    (
        1.0,
        True,
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("0.0000000000000000001"),
        Decimal("1E+19"),
    ),
)
def test_rejects_unsupported_quantity_scalars(value: object) -> None:
    with pytest.raises(
        InvalidVerifiedSnapshotPaperCyclePreparationRequestError
    ) as error:
        ExplicitQuantityTarget(SPY, value)  # type: ignore[arg-type]

    _assert_code(
        error,
        VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_DECIMAL,
    )


def test_isolates_all_arithmetic_from_ambient_decimal_context() -> None:
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_DOWN
        low = _prepare()
        assert context.prec == 6
        assert context.rounding is ROUND_DOWN
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_UP
        high = _prepare()
        assert context.prec == 50
        assert context.rounding is ROUND_UP

    assert low == high
    assert low.preparation_id == high.preparation_id


@pytest.mark.parametrize(
    ("target_date", "requested_date", "expected_next"),
    (
        (date(2025, 1, 10), date(2025, 1, 13), date(2025, 1, 13)),
        (date(2025, 7, 3), date(2025, 7, 7), date(2025, 7, 7)),
    ),
)
def test_derives_next_session_across_weekend_and_holiday_in_est_or_edt(
    target_date: date,
    requested_date: date,
    expected_next: date,
) -> None:
    verification, captured_at = _dated_verification(target_date, requested_date)
    next_session = TradingSession(expected_next)
    planning_at = captured_at + timedelta(minutes=1)
    request = _request(
        verification=verification,
        account_state=VerifiedSnapshotAccountState(
            _ACCOUNT_STATE_ID,
            captured_at - timedelta(minutes=1),
            Decimal("972.50"),
            (
                VerifiedSnapshotAccountPosition(
                    SPY,
                    Decimal("10"),
                    Decimal("100"),
                ),
            ),
        ),
        open_references=(
            CallerAssertedNextSessionOpenReference(
                SPY,
                next_session,
                Decimal("103"),
            ),
            CallerAssertedNextSessionOpenReference(
                QQQ,
                next_session,
                Decimal("204"),
            ),
        ),
        planning_at=planning_at,
        submitted_at=planning_at + timedelta(minutes=1),
        filled_at=captured_at + timedelta(hours=2),
    )

    prepared = prepare_verified_snapshot_paper_cycle(
        request,
        verification,
        calendar(),
    )

    assert prepared.target_session.session_date == target_date
    assert prepared.next_session == next_session
    assert prepared.filled_at.astimezone(ZoneInfo("America/New_York")).date() == (
        expected_next
    )


def _dated_verification(
    target_date: date,
    requested_date: date,
):
    exchange = ZoneInfo("America/New_York")
    requested_at = datetime.combine(
        requested_date,
        datetime.min.time(),
        exchange,
    ).astimezone(UTC) + timedelta(hours=9)
    captured_at = requested_at + timedelta(minutes=1)
    target_session = TradingSession(target_date)
    timestamp = datetime.combine(
        target_date,
        datetime.min.time(),
        exchange,
    ).astimezone(UTC)
    request = capture_request(requested_at=requested_at)
    result = accepted_result(
        request=request,
        candidates=(
            candidate(
                QQQ,
                0,
                session=target_session,
                timestamp=timestamp,
                open_price=Decimal("200"),
                high=Decimal("205"),
                low=Decimal("198"),
                close=Decimal("203"),
            ),
            candidate(
                SPY,
                1,
                session=target_session,
                timestamp=timestamp,
            ),
        ),
        captured_at=captured_at,
    )
    assert result.snapshot is not None
    payload = serialize_daily_snapshot(result.snapshot)
    return verify_daily_snapshot(payload, calendar()), captured_at


def test_rejects_invalid_chronology() -> None:
    with pytest.raises(VerifiedSnapshotPaperCycleTemporalError) as error:
        _prepare(planning_at=CAPTURED_AT - timedelta(seconds=1))

    _assert_code(
        error,
        VerifiedSnapshotPaperCyclePreparationDiagnosticCode.INVALID_CHRONOLOGY,
    )


@pytest.mark.parametrize(
    "wrong_session",
    (
        TradingSession(date(2025, 1, 6)),
        TradingSession(date(2025, 1, 8)),
    ),
)
def test_rejects_snapshot_or_skipped_open_reference_session(
    wrong_session: TradingSession,
) -> None:
    references = (
        CallerAssertedNextSessionOpenReference(SPY, wrong_session, Decimal("103")),
        CallerAssertedNextSessionOpenReference(QQQ, wrong_session, Decimal("204")),
    )

    with pytest.raises(VerifiedSnapshotPaperCycleTemporalError) as error:
        _prepare(open_references=references)

    _assert_code(
        error,
        VerifiedSnapshotPaperCyclePreparationDiagnosticCode.OPEN_REFERENCE_SESSION_MISMATCH,
    )


def test_rejects_wrong_new_york_fill_session() -> None:
    with pytest.raises(VerifiedSnapshotPaperCycleTemporalError) as error:
        _prepare(filled_at=datetime(2025, 1, 8, 15, 0, tzinfo=UTC))

    _assert_code(
        error,
        VerifiedSnapshotPaperCyclePreparationDiagnosticCode.FILL_SESSION_MISMATCH,
    )


@pytest.mark.parametrize(
    "policies",
    (
        lambda: _policies(fill_policy=PaperFillPolicy(fixed_commission=Decimal("1"))),
        lambda: _policies(
            assumptions=RebalanceAssumptions(
                allow_fractional_quantities=False,
                quantity_increment=Decimal("1"),
            )
        ),
        lambda: _policies(risk_policy=PortfolioRiskPolicy(False)),
    ),
)
def test_rejects_cross_policy_mismatch(policies) -> None:
    with pytest.raises(VerifiedSnapshotPaperCyclePolicyError) as error:
        policies()

    _assert_code(
        error,
        VerifiedSnapshotPaperCyclePreparationDiagnosticCode.POLICY_MISMATCH,
    )


def test_preparation_identity_is_deterministic_and_input_sensitive() -> None:
    first = _prepare()
    second = _prepare()
    request = _request()
    changed_references = (
        replace(
            request.open_references[0],
            caller_asserted_open_reference_price=Decimal("103.01"),
        ),
        request.open_references[1],
    )
    changed = _prepare(open_references=changed_references)

    assert first == second
    assert (
        first.preparation_id
        == second.preparation_id
        == UUID("e27ef863-e551-5eaa-974d-8cd69d8f9f62")
    )
    assert first.planner_request.request_id == UUID(
        "69feecda-7556-5458-8248-aa3af052681c"
    )
    assert changed.preparation_id != first.preparation_id


def test_does_not_invoke_provider_or_runtime(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("external or runtime operation invoked")

    monkeypatch.setattr(PaperPortfolioRuntime, "run_cycle", fail)
    monkeypatch.setattr(
        "trading_bot.market_data.AlpacaDailySnapshotProvider.fetch",
        fail,
    )

    prepared = _prepare()

    assert prepared.preparation_id


def test_rejects_calendar_descriptor_mismatch() -> None:
    mismatched_descriptor = replace(
        XNYS_CALENDAR_DESCRIPTOR,
        version="different-version",
    )
    mismatched = BoundMarketCalendar(mismatched_descriptor, calendar().calendar)
    verification = _verification()

    with pytest.raises(VerifiedSnapshotPaperCycleSnapshotError) as error:
        prepare_verified_snapshot_paper_cycle(
            _request(verification=verification),
            verification,
            mismatched,
        )

    _assert_code(
        error,
        VerifiedSnapshotPaperCyclePreparationDiagnosticCode.CALENDAR_MISMATCH,
    )
