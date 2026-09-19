"""Focused Architecture-94 P1 deterministic strategy-plan coverage."""

import json
import os
from dataclasses import fields, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_DOWN, Context, Decimal, localcontext
from hashlib import sha256
from uuid import UUID

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
from tests.runtime.test_verified_snapshot_preparation import _policies

from trading_bot.domain import Bar, OrderSide
from trading_bot.execution import PaperFillPolicy
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    DailySnapshotBar,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.portfolio import MetadataEntry, PortfolioConstraints
from trading_bot.rebalancing import (
    RebalanceAssumptions,
    RebalanceProposalPolicy,
    RebalanceStatus,
)
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime import (
    ARCHITECTURE94_STRATEGY_PLAN_BYTE_LENGTH_METADATA_KEY,
    ARCHITECTURE94_STRATEGY_PLAN_ID_METADATA_KEY,
    ARCHITECTURE94_STRATEGY_PLAN_SHA256_METADATA_KEY,
    CallerAssertedNextSessionOpenReference,
    CheckpointedVerifiedSnapshotPaperCycleRequest,
    ManualPaperSelectedC3Assertion,
    ManualPaperStrategyDecisionRequest,
    ManualPaperStrategyPlanRequest,
    ManualPaperStrategyPlanSerializationError,
    ManualPaperStrategyPlanValidationError,
    ManualPaperStrategyPlanVerificationError,
    ManualPaperStrategySignalStatus,
    PaperAccountCheckpointPosition,
    PaperAccountGenesisRequest,
    PaperPortfolioRuntime,
    PreparedManualPaperStrategyDecision,
    SelectedC3SnapshotAuditEvidence,
    SelectedC3SnapshotPermit,
    SelectedC3SnapshotReadError,
    SelectedC3SnapshotReadResult,
    StrategyHistorySeedSourceDescriptor,
    build_c3_verified_daily_bar_open_binding,
    build_manual_paper_strategy_decision,
    build_manual_paper_strategy_plan,
    complete_manual_paper_strategy_plan,
    create_genesis_paper_account_checkpoint,
    create_strategy_history_seed,
    parse_manual_paper_strategy_plan,
    serialize_paper_account_checkpoint,
    serialize_strategy_history_seed,
    verified_prior_from_genesis,
    verify_genesis_paper_account_checkpoint,
    verify_manual_paper_strategy_plan,
    verify_strategy_history_seed,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

_TARGET_SESSION = TradingSession(date(2025, 1, 6))
_NEXT_SESSION = TradingSession(date(2025, 1, 7))
_SEED_SESSIONS = (date(2024, 12, 31), date(2025, 1, 2), date(2025, 1, 3))
_SOURCE = StrategyHistorySeedSourceDescriptor("manual-plan-focused-test")
_DEFAULT_CONFIG = MovingAverageCrossoverConfig(2, 3, Decimal("2"))
_SELECTION_ID = UUID("10000000-0000-0000-0000-000000000001")
_SESSION_ID = UUID("20000000-0000-0000-0000-000000000002")
_TERMINAL_ID = UUID("30000000-0000-0000-0000-000000000003")


def _snapshot(close: str = "12"):
    price = Decimal(close)
    accepted = accepted_result(
        request=capture_request(symbols=(SPY,)),
        candidates=(
            candidate(
                SPY,
                0,
                open_price=price,
                high=price + Decimal("1"),
                low=price - Decimal("1"),
                close=price,
            ),
        ),
    )
    assert accepted.snapshot is not None
    payload = serialize_daily_snapshot(accepted.snapshot)
    return verify_daily_snapshot(payload, calendar())


def _seed_bar(session_date: date, close: str) -> DailySnapshotBar:
    price = Decimal(close)
    return DailySnapshotBar(
        TradingSession(session_date),
        Bar(
            SPY,
            datetime.combine(session_date, time(), tzinfo=UTC) + timedelta(hours=5),
            price,
            price + Decimal("1"),
            price - Decimal("1"),
            price,
            100,
        ),
    )


def _c3_assertion(snapshot_verification) -> ManualPaperSelectedC3Assertion:
    assert snapshot_verification.snapshot is not None
    return ManualPaperSelectedC3Assertion(
        _SELECTION_ID,
        _SESSION_ID,
        _TERMINAL_ID,
        snapshot_verification.snapshot.snapshot_id,
        snapshot_verification.sha256,
        snapshot_verification.byte_length,
    )


def _verified_seed(
    config: MovingAverageCrossoverConfig,
    closes: tuple[str, str, str],
):
    seed = create_strategy_history_seed(
        symbol=SPY,
        source=_SOURCE,
        bars=tuple(
            _seed_bar(day, close)
            for day, close in zip(_SEED_SESSIONS, closes, strict=True)
        ),
    )
    return verify_strategy_history_seed(
        serialize_strategy_history_seed(seed),
        expected_symbol=SPY,
        target_session=_TARGET_SESSION,
        strategy_config=config,
        calendar=calendar(),
    )


def _prior(*, cash: str = "100", quantity: str = "0", basis: str = "0"):
    positions = ()
    if Decimal(quantity) > 0:
        positions = (
            PaperAccountCheckpointPosition.from_exact_basis(
                SPY, Decimal(quantity), Decimal(basis)
            ),
        )
    checkpoint = create_genesis_paper_account_checkpoint(
        PaperAccountGenesisRequest(
            datetime(2025, 1, 1, tzinfo=UTC),
            Decimal(cash),
            positions,
            Decimal("0"),
        )
    )
    payload = serialize_paper_account_checkpoint(checkpoint)
    return verified_prior_from_genesis(verify_genesis_paper_account_checkpoint(payload))


def _request(
    *,
    closes: tuple[str, str, str] = ("10", "10", "9"),
    selected_close: str = "12",
    config: MovingAverageCrossoverConfig = _DEFAULT_CONFIG,
    history_seed=None,
    prior=None,
    paper_account_id: str = "paper.account-1",
    selected_c3_assertion: ManualPaperSelectedC3Assertion | None = None,
    caller_key: str = "manual-cycle-1",
    open_price: str = "12",
    policies=None,
    planning_at: datetime = CAPTURED_AT + timedelta(minutes=1),
    submitted_at: datetime = CAPTURED_AT + timedelta(minutes=2),
    filled_at: datetime = datetime(2025, 1, 7, 20, tzinfo=UTC),
    metadata: tuple[MetadataEntry, ...] = (MetadataEntry("source", "test"),),
) -> ManualPaperStrategyPlanRequest:
    snapshot_verification = _snapshot(selected_close)
    return ManualPaperStrategyPlanRequest(
        snapshot_verification,
        paper_account_id,
        selected_c3_assertion or _c3_assertion(snapshot_verification),
        prior or _prior(),
        history_seed or _verified_seed(config, closes),
        config,
        caller_key,
        CallerAssertedNextSessionOpenReference(SPY, _NEXT_SESSION, Decimal(open_price)),
        policies or _policies(),
        planning_at,
        submitted_at,
        filled_at,
        metadata,
    )


def _binding(**kwargs):
    return build_manual_paper_strategy_plan(_request(**kwargs), calendar())


def _decision_request(
    request: ManualPaperStrategyPlanRequest,
) -> ManualPaperStrategyDecisionRequest:
    return ManualPaperStrategyDecisionRequest(
        request.snapshot_verification,
        request.paper_account_id,
        request.selected_c3_assertion,
        request.prior_checkpoint,
        request.history_seed,
        request.strategy_config,
        request.caller_idempotency_key,
        request.policies,
        request.planning_at,
        request.submitted_at,
        request.filled_at,
        request.metadata,
    )


def _execution_snapshot(open_price: str, *, symbol=SPY):
    requested_at = datetime(2025, 1, 8, 18, tzinfo=UTC)
    price = Decimal(open_price)
    accepted = accepted_result(
        request=capture_request(
            request_id=UUID("98dbdaca-e14b-5f10-8ca9-3650e18aa1d9"),
            requested_at=requested_at,
            symbols=(symbol,),
        ),
        candidates=(
            candidate(
                symbol,
                0,
                session=_NEXT_SESSION,
                timestamp=datetime(2025, 1, 7, 20, tzinfo=UTC),
                open_price=price,
                high=price + Decimal("1"),
                low=price - Decimal("1"),
                close=price,
            ),
        ),
        captured_at=requested_at + timedelta(seconds=1),
    )
    assert accepted.snapshot is not None
    payload = serialize_daily_snapshot(accepted.snapshot)
    return verify_daily_snapshot(payload, calendar())


def _selected_result(snapshot_verification) -> SelectedC3SnapshotReadResult:
    assert snapshot_verification.snapshot is not None
    payload = serialize_daily_snapshot(snapshot_verification.snapshot)
    audit = SelectedC3SnapshotAuditEvidence(
        UUID("81000000-0000-4000-8000-000000000001"),
        UUID("82000000-0000-4000-8000-000000000002"),
        UUID("83000000-0000-4000-8000-000000000003"),
        UUID("84000000-0000-4000-8000-000000000004"),
        snapshot_verification.snapshot.snapshot_id,
        snapshot_verification.sha256,
        snapshot_verification.byte_length,
        "8" * 64,
        "SUCCEEDED",
        "CONFIRMED",
        r"F:\AITradingBot\Authority\capture-output\selected.json",
    )
    return SelectedC3SnapshotReadResult(
        audit,
        object.__new__(SelectedC3SnapshotPermit),
        payload,
        snapshot_verification,
    )


def _verified_open_binding(
    monkeypatch: pytest.MonkeyPatch,
    open_price: str,
    *,
    symbol=SPY,
):
    import trading_bot.runtime.verified_c3_daily_bar_open as open_module

    authority = object()
    monkeypatch.setattr(
        open_module, "require_validated_production_authority", lambda value: value
    )
    monkeypatch.setattr(
        open_module,
        "require_selected_c3_snapshot_matches_authority",
        lambda permit, audit, current: None,
    )
    return build_c3_verified_daily_bar_open_binding(
        _selected_result(_execution_snapshot(open_price, symbol=symbol)),
        authority,  # type: ignore[arg-type]
    )


def test_pre_open_request_and_prepared_decision_contain_no_open_input() -> None:
    request = _decision_request(_request())
    prepared = build_manual_paper_strategy_decision(request, calendar())

    assert all("open" not in item.name for item in fields(type(request)))
    assert all("open" not in item.name for item in fields(type(prepared)))
    assert isinstance(prepared, PreparedManualPaperStrategyDecision)
    assert prepared.intended_execution_session == _NEXT_SESSION


def test_prepared_decision_uses_public_xnys_timing_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_bot.runtime import manual_paper_strategy_plan as module

    authority_session = TradingSession(date(2025, 1, 8))
    calls: list[TradingSession] = []

    def use_public_authority(selected_session: TradingSession) -> TradingSession:
        calls.append(selected_session)
        return authority_session

    monkeypatch.setattr(module, "next_xnys_execution_session", use_public_authority)
    request = _decision_request(
        _request(filled_at=datetime(2025, 1, 8, 20, tzinfo=UTC))
    )

    prepared = build_manual_paper_strategy_decision(request, calendar())

    assert calls == [_TARGET_SESSION]
    assert prepared.intended_execution_session == authority_session


def test_phase_one_evaluates_once_and_completion_never_reevaluates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_bot.runtime import manual_paper_strategy_plan as module

    original = module.MovingAverageCrossoverStrategy.evaluate
    calls = 0

    def counted(self, context):
        nonlocal calls
        calls += 1
        return original(self, context)

    monkeypatch.setattr(module.MovingAverageCrossoverStrategy, "evaluate", counted)
    prepared = build_manual_paper_strategy_decision(
        _decision_request(_request()), calendar()
    )
    assert calls == 1

    def forbidden(self, context):
        del self, context
        raise AssertionError("completion must not reevaluate the strategy")

    monkeypatch.setattr(module.MovingAverageCrossoverStrategy, "evaluate", forbidden)
    completed = complete_manual_paper_strategy_plan(
        prepared, _verified_open_binding(monkeypatch, "12"), calendar()
    )
    assert completed.plan.strategy_proposal == prepared.strategy_proposal


def test_later_c3_open_changes_only_final_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _decision_request(_request())
    first_prepared = build_manual_paper_strategy_decision(request, calendar())
    second_prepared = build_manual_paper_strategy_decision(request, calendar())
    first = complete_manual_paper_strategy_plan(
        first_prepared, _verified_open_binding(monkeypatch, "12"), calendar()
    )
    second = complete_manual_paper_strategy_plan(
        second_prepared, _verified_open_binding(monkeypatch, "13"), calendar()
    )

    assert first_prepared == second_prepared
    assert first.plan.target == second.plan.target == first_prepared.target
    assert first.plan.plan_id != second.plan.plan_id
    assert first.artifact_bytes != second.artifact_bytes


def test_completion_rejects_wrong_execution_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.verified_c3_daily_bar_open as open_module

    monkeypatch.setattr(
        open_module, "require_validated_production_authority", lambda value: value
    )
    monkeypatch.setattr(
        open_module,
        "require_selected_c3_snapshot_matches_authority",
        lambda permit, audit, current: None,
    )
    wrong_session = build_c3_verified_daily_bar_open_binding(
        _selected_result(_snapshot()),
        object(),  # type: ignore[arg-type]
    )
    prepared = build_manual_paper_strategy_decision(
        _decision_request(_request()), calendar()
    )

    with pytest.raises(ManualPaperStrategyPlanValidationError, match="session"):
        complete_manual_paper_strategy_plan(prepared, wrong_session, calendar())


def test_completion_rejects_wrong_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = build_manual_paper_strategy_decision(
        _decision_request(_request()), calendar()
    )
    wrong_symbol = _verified_open_binding(monkeypatch, "12", symbol=QQQ)

    with pytest.raises(ManualPaperStrategyPlanValidationError, match="symbol"):
        complete_manual_paper_strategy_plan(prepared, wrong_symbol, calendar())


def test_forged_replacement_open_cannot_override_selected_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = build_manual_paper_strategy_decision(
        _decision_request(_request()), calendar()
    )
    binding = _verified_open_binding(monkeypatch, "12")
    object.__setattr__(binding, "_open_price", Decimal("999"))

    with pytest.raises(ManualPaperStrategyPlanValidationError, match="provenance"):
        complete_manual_paper_strategy_plan(prepared, binding, calendar())


def test_wrong_current_c1_p2_provenance_rejects_open_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.verified_c3_daily_bar_open as open_module

    monkeypatch.setattr(
        open_module, "require_validated_production_authority", lambda value: value
    )

    def reject(permit, audit, authority):
        del permit, audit, authority
        raise SelectedC3SnapshotReadError("P2 read does not match C1 authority")

    monkeypatch.setattr(
        open_module, "require_selected_c3_snapshot_matches_authority", reject
    )
    with pytest.raises(ValueError, match="current C1"):
        build_c3_verified_daily_bar_open_binding(
            _selected_result(_execution_snapshot("12")),
            object(),  # type: ignore[arg-type]
        )


def test_completion_revalidates_current_c1_p2_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.verified_c3_daily_bar_open as open_module

    prepared = build_manual_paper_strategy_decision(
        _decision_request(_request()), calendar()
    )
    binding = _verified_open_binding(monkeypatch, "12")

    def reject(permit, audit, authority):
        del permit, audit, authority
        raise SelectedC3SnapshotReadError("P2 read does not match current C1")

    monkeypatch.setattr(
        open_module, "require_selected_c3_snapshot_matches_authority", reject
    )
    with pytest.raises(ManualPaperStrategyPlanValidationError, match="provenance"):
        complete_manual_paper_strategy_plan(prepared, binding, calendar())


@pytest.mark.parametrize(
    ("kwargs", "expected_plan_id", "expected_sha256", "expected_length", "request_id"),
    (
        (
            {},
            "51752429-00b3-577a-9008-6f9845918975",
            "f94d3dbd2d3372c261617ee5180c0b46227a269dc2c73672f773fbc3fbb3a2af",
            5946,
            "20af4bbb-15e2-59da-a0d0-fe2e09ea1355",
        ),
        (
            {
                "closes": ("9", "12", "12"),
                "selected_close": "10",
                "config": MovingAverageCrossoverConfig(2, 3, Decimal("99")),
                "prior": _prior(cash="10", quantity="2.5", basis="25"),
                "open_price": "10",
            },
            "8d6da27e-4282-54fd-b681-1d1776323b57",
            "fc8d4be1b37b34a9bc8e674a45b77404a9820f8e8aec8df347c6a4804caccb55",
            6026,
            "20c1300b-26ac-5cec-b42a-797397e69d4a",
        ),
        (
            {"closes": ("10", "11", "12"), "selected_close": "13"},
            "cbc85bd1-7f53-57fe-9837-56a1a46e11f9",
            "96ac573fbf8c2f998130322643249cec378824de5e2345db9497e682e91fafff",
            5452,
            "ffb2e701-ac8c-556c-892f-dd9233d87169",
        ),
    ),
    ids=("bullish", "bearish", "no-signal"),
)
def test_two_phase_completion_is_exactly_legacy_compatible(
    monkeypatch: pytest.MonkeyPatch,
    kwargs: dict[str, object],
    expected_plan_id: str,
    expected_sha256: str,
    expected_length: int,
    request_id: str,
) -> None:
    request = _request(**kwargs)
    legacy = build_manual_paper_strategy_plan(request, calendar())
    prepared = build_manual_paper_strategy_decision(
        _decision_request(request), calendar()
    )
    completed = complete_manual_paper_strategy_plan(
        prepared,
        _verified_open_binding(
            monkeypatch,
            str(request.open_reference.caller_asserted_open_reference_price),
        ),
        calendar(),
    )

    assert completed == legacy
    assert completed.plan == legacy.plan
    assert completed.artifact_bytes == legacy.artifact_bytes
    assert completed.plan.plan_id == legacy.plan.plan_id
    assert completed.artifact_sha256 == legacy.artifact_sha256
    assert completed.artifact_byte_length == legacy.artifact_byte_length
    assert completed.checkpointed_request == legacy.checkpointed_request
    assert completed.checkpointed_request.request_id == (
        legacy.checkpointed_request.request_id
    )
    assert completed.plan.target == legacy.plan.target
    assert completed.plan.strategy_run_id == legacy.plan.strategy_run_id
    assert completed.plan.strategy_step_index == legacy.plan.strategy_step_index
    assert completed.plan.planner_plan_id == legacy.plan.planner_plan_id
    assert completed.plan.planner_result_id == legacy.plan.planner_result_id
    assert completed.plan.strategy_proposal == legacy.plan.strategy_proposal
    assert completed.plan.planner_proposal == legacy.plan.planner_proposal
    assert str(completed.plan.plan_id) == expected_plan_id
    assert completed.artifact_sha256 == expected_sha256
    assert completed.artifact_byte_length == expected_length
    assert str(completed.checkpointed_request.request_id) == request_id


def test_bullish_crossover_flat_produces_exact_buy_and_target() -> None:
    bound = _binding()
    plan = bound.plan

    assert plan.signal_status is ManualPaperStrategySignalStatus.TRADE_PROPOSAL
    assert plan.strategy_proposal is not None
    assert plan.strategy_proposal.side is OrderSide.BUY
    assert plan.strategy_proposal.desired_quantity == Decimal("2")
    assert plan.planner_proposal is not None
    assert plan.planner_proposal.symbol == plan.strategy_proposal.symbol == SPY
    assert plan.planner_proposal.side is plan.strategy_proposal.side
    assert (
        plan.planner_proposal.desired_quantity
        == plan.strategy_proposal.desired_quantity
    )
    assert plan.target.quantities[0].quantity == Decimal("2")
    assert plan.target.target_cash == Decimal("76")
    assert plan.target.target_cash + Decimal("2") * Decimal("12") == Decimal("100")


def test_bearish_crossover_invested_produces_exact_full_sell() -> None:
    config = MovingAverageCrossoverConfig(2, 3, Decimal("99"))
    bound = _binding(
        closes=("9", "12", "12"),
        selected_close="10",
        config=config,
        prior=_prior(cash="10", quantity="2.5", basis="25"),
        open_price="10",
    )
    proposal = bound.plan.strategy_proposal

    assert proposal is not None and proposal.side is OrderSide.SELL
    assert proposal.desired_quantity == Decimal("2.5")
    assert bound.plan.planner_proposal is not None
    assert bound.plan.planner_proposal.desired_quantity == Decimal("2.5")
    assert bound.plan.target.quantities[0].quantity == Decimal("0")
    assert bound.plan.target.target_cash == Decimal("35")


def test_no_crossover_is_explicit_no_signal_and_no_planner_proposal() -> None:
    bound = _binding(closes=("10", "11", "12"), selected_close="13")

    assert bound.plan.signal_status is ManualPaperStrategySignalStatus.NO_SIGNAL
    assert bound.plan.strategy_proposal is None
    assert bound.plan.planner_proposal is None
    assert bound.plan.target.quantities[0].quantity == Decimal("0")
    assert bound.plan.target.target_cash == Decimal("100")


def test_existing_nonactionable_crossover_retains_marked_account() -> None:
    bound = _binding(prior=_prior(cash="16", quantity="2", basis="20"))

    assert bound.plan.signal_status is ManualPaperStrategySignalStatus.NO_SIGNAL
    assert bound.plan.strategy_proposal is None
    assert bound.plan.planner_proposal is None
    assert bound.plan.target.quantities[0].quantity == Decimal("2")
    assert bound.plan.target.target_cash == Decimal("16")
    assert bound.plan.target.target_cash + Decimal("2") * Decimal("12") == Decimal("40")


@pytest.mark.parametrize(
    "config",
    (
        MovingAverageCrossoverConfig(2, 3, Decimal("1.2345")),
        MovingAverageCrossoverConfig(2, 3, Decimal("100")),
    ),
)
def test_unrepresentable_or_unfunded_target_fails_closed(
    config: MovingAverageCrossoverConfig,
) -> None:
    with pytest.raises(ManualPaperStrategyPlanValidationError):
        _binding(config=config)


def test_deterministic_replay_and_nonsemantic_environment_independence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _binding()
    monkeypatch.setenv("ARCH94_IRRELEVANT_PATH", r"Z:\different\artifact.json")
    monkeypatch.setenv("ARCH94_IRRELEVANT_MODE", "different")
    second = _binding()
    replayed = verify_manual_paper_strategy_plan(
        first.artifact_bytes,
        calendar(),
        expected_sha256=first.artifact_sha256,
        expected_byte_length=first.artifact_byte_length,
        expected_checkpointed_request=first.checkpointed_request,
    )

    assert first.plan.plan_id == second.plan.plan_id == replayed.plan.plan_id
    assert first.artifact_bytes == second.artifact_bytes
    assert os.environ["ARCH94_IRRELEVANT_MODE"] == "different"


def test_artifact_semantics_are_independent_of_ambient_decimal_context() -> None:
    request = _request()
    market_calendar = calendar()

    with localcontext(Context(prec=28)):
        historical = build_manual_paper_strategy_plan(request, market_calendar)
    with localcontext(Context(prec=6, rounding=ROUND_DOWN)):
        hostile = build_manual_paper_strategy_plan(request, market_calendar)

    assert hostile.plan == historical.plan
    assert hostile.plan.strategy_proposal == historical.plan.strategy_proposal
    assert hostile.artifact_bytes == historical.artifact_bytes
    assert hostile.artifact_sha256 == historical.artifact_sha256
    assert hostile.artifact_byte_length == historical.artifact_byte_length
    assert hostile.checkpointed_request == historical.checkpointed_request


def test_retains_canonical_paper_account_and_selected_c3_provenance() -> None:
    bound = _binding()
    parsed = parse_manual_paper_strategy_plan(bound.artifact_bytes)

    assert parsed.paper_account_id == "paper.account-1"
    assert parsed.selected_c3_assertion == _c3_assertion(_snapshot())
    assert parsed == bound.plan
    assert (
        verify_manual_paper_strategy_plan(bound.artifact_bytes, calendar()).plan
        == bound.plan
    )


@pytest.mark.parametrize(
    "field", ("snapshot_id", "artifact_sha256", "artifact_byte_length")
)
def test_rejects_selected_c3_snapshot_evidence_mismatch(field: str) -> None:
    request = _request()
    mismatched = {
        "snapshot_id": UUID("40000000-0000-0000-0000-000000000004"),
        "artifact_sha256": "f" * 64,
        "artifact_byte_length": request.selected_c3_assertion.artifact_byte_length + 1,
    }
    assertion = replace(request.selected_c3_assertion, **{field: mismatched[field]})

    with pytest.raises(ManualPaperStrategyPlanValidationError, match="C3 assertion"):
        build_manual_paper_strategy_plan(
            replace(request, selected_c3_assertion=assertion), calendar()
        )


def test_provenance_changes_plan_and_request_identity_but_not_economic_result() -> None:
    baseline_request = _request()
    baseline = build_manual_paper_strategy_plan(baseline_request, calendar())
    assertion = baseline_request.selected_c3_assertion
    variants = (
        replace(baseline_request, paper_account_id="paper.account-2"),
        replace(
            baseline_request,
            selected_c3_assertion=replace(
                assertion,
                selection_id=UUID("50000000-0000-0000-0000-000000000005"),
            ),
        ),
        replace(
            baseline_request,
            selected_c3_assertion=replace(
                assertion,
                session_id=UUID("60000000-0000-0000-0000-000000000006"),
            ),
        ),
        replace(
            baseline_request,
            selected_c3_assertion=replace(
                assertion,
                terminal_id=UUID("70000000-0000-0000-0000-000000000007"),
            ),
        ),
    )

    for request in variants:
        changed = build_manual_paper_strategy_plan(request, calendar())
        assert changed.plan.plan_id != baseline.plan.plan_id
        assert (
            changed.checkpointed_request.request_id
            != baseline.checkpointed_request.request_id
        )
        assert changed.plan.strategy_run_id == baseline.plan.strategy_run_id
        assert changed.plan.signal_status is baseline.plan.signal_status
        assert changed.plan.strategy_proposal == baseline.plan.strategy_proposal
        assert changed.plan.target == baseline.plan.target


def test_semantic_input_changes_change_plan_identity() -> None:
    baseline = _binding().plan.plan_id
    changed_policy = replace(_policies(), proposal_confidence=Decimal("0.5"))
    shifted = timedelta(seconds=1)
    variants = (
        _binding(closes=("10", "10", "8")).plan.plan_id,
        _binding(selected_close="12.5", open_price="12.5").plan.plan_id,
        _binding(prior=_prior(cash="125")).plan.plan_id,
        _binding(config=MovingAverageCrossoverConfig(2, 3, Decimal("3"))).plan.plan_id,
        _binding(policies=changed_policy).plan.plan_id,
        _binding(open_price="13").plan.plan_id,
        _binding(caller_key="manual-cycle-2").plan.plan_id,
        _binding(
            planning_at=CAPTURED_AT + timedelta(minutes=1) + shifted,
            submitted_at=CAPTURED_AT + timedelta(minutes=2) + shifted,
        ).plan.plan_id,
        _binding(metadata=(MetadataEntry("source", "changed"),)).plan.plan_id,
    )

    assert all(value != baseline for value in variants)
    assert len(set(variants)) == len(variants)


def test_detached_binding_injects_exact_three_metadata_entries_in_order() -> None:
    bound = _binding(metadata=(MetadataEntry("a", "1"), MetadataEntry("b", "2")))
    metadata = bound.checkpointed_request.metadata

    assert tuple(item.key for item in metadata) == (
        "a",
        "b",
        ARCHITECTURE94_STRATEGY_PLAN_ID_METADATA_KEY,
        ARCHITECTURE94_STRATEGY_PLAN_SHA256_METADATA_KEY,
        ARCHITECTURE94_STRATEGY_PLAN_BYTE_LENGTH_METADATA_KEY,
    )
    assert metadata[-3].value == str(bound.plan.plan_id)
    assert metadata[-2].value == bound.artifact_sha256
    assert metadata[-1].value == str(bound.artifact_byte_length)
    assert bound.plan.request_core.metadata == metadata[:-3]
    assert b"architecture94.strategy_plan_sha256" not in bound.artifact_bytes
    assert b"architecture94.strategy_plan_byte_length" not in bound.artifact_bytes


@pytest.mark.parametrize(
    "key",
    (
        "architecture94.strategy_plan_id",
        "architecture94.caller_value",
    ),
)
def test_rejects_caller_architecture94_metadata(key: str) -> None:
    with pytest.raises(ManualPaperStrategyPlanValidationError, match="reserved"):
        _request(metadata=(MetadataEntry(key, "x"),))


def test_exact_reconstructed_existing_request_round_trips_unchanged_schema() -> None:
    from trading_bot.runtime import (
        parse_checkpointed_verified_snapshot_paper_cycle_request,
        serialize_checkpointed_verified_snapshot_paper_cycle_request,
    )

    bound = _binding()
    payload = serialize_checkpointed_verified_snapshot_paper_cycle_request(
        bound.checkpointed_request
    )
    assert (
        parse_checkpointed_verified_snapshot_paper_cycle_request(payload)
        == bound.checkpointed_request
    )


@pytest.mark.parametrize(
    ("turnover", "minimum_position", "expected_turnover", "expected_minimum"),
    (
        (Decimal("0.25"), None, "0.25", None),
        (None, Decimal("0.05"), None, "0.05"),
        (None, None, None, None),
        (Decimal("0.25"), Decimal("0.05"), "0.25", "0.05"),
    ),
)
def test_checkpointed_request_optional_portfolio_constraints_round_trip(
    turnover: Decimal | None,
    minimum_position: Decimal | None,
    expected_turnover: str | None,
    expected_minimum: str | None,
) -> None:
    from trading_bot.runtime import (
        parse_checkpointed_verified_snapshot_paper_cycle_request,
        serialize_checkpointed_verified_snapshot_paper_cycle_request,
    )

    constraints = PortfolioConstraints(
        minimum_cash_weight=Decimal("0.1"),
        maximum_cash_weight=Decimal("0.9"),
        maximum_position_weight=Decimal("0.8"),
        maximum_one_way_rebalance_turnover=turnover,
        minimum_position_weight=minimum_position,
    )
    bound = _binding(policies=replace(_policies(), portfolio_constraints=constraints))
    payload = serialize_checkpointed_verified_snapshot_paper_cycle_request(
        bound.checkpointed_request
    )
    tree = json.loads(payload)
    serialized = tree["policies"]["portfolio_constraints"]
    parsed = parse_checkpointed_verified_snapshot_paper_cycle_request(payload)
    parsed_constraints = parsed.policies.portfolio_constraints

    assert serialized["maximum_one_way_rebalance_turnover"] == expected_turnover
    assert serialized["minimum_position_weight"] == expected_minimum
    assert parsed == bound.checkpointed_request
    assert parsed_constraints == constraints
    assert parsed_constraints is not None
    assert parsed_constraints.maximum_one_way_rebalance_turnover == turnover
    assert parsed_constraints.minimum_position_weight == minimum_position
    if turnover is None:
        assert parsed_constraints.maximum_one_way_rebalance_turnover is None
    if minimum_position is None:
        assert parsed_constraints.minimum_position_weight is None

    if turnover is not None and minimum_position is not None:
        assert len(payload) == 1924
        assert sha256(payload).hexdigest() == (
            "b13a88eb454fbb782524388ffcf78226ec4d254bd2ed6a8457d6f0ed4a361142"
        )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    (
        ("maximum_one_way_rebalance_turnover", "not-a-decimal"),
        ("minimum_position_weight", 0),
    ),
)
def test_checkpointed_request_invalid_non_null_optional_constraint_fails_closed(
    field: str,
    invalid_value: object,
) -> None:
    from trading_bot.runtime import (
        CheckpointedPaperCycleReportSchemaError,
        parse_checkpointed_verified_snapshot_paper_cycle_request,
        serialize_checkpointed_verified_snapshot_paper_cycle_request,
    )

    constraints = PortfolioConstraints(
        maximum_one_way_rebalance_turnover=Decimal("0.25"),
        minimum_position_weight=Decimal("0.05"),
    )
    bound = _binding(policies=replace(_policies(), portfolio_constraints=constraints))
    tree = json.loads(
        serialize_checkpointed_verified_snapshot_paper_cycle_request(
            bound.checkpointed_request
        )
    )
    tree["policies"]["portfolio_constraints"][field] = invalid_value
    payload = (json.dumps(tree, sort_keys=True, separators=(",", ":")) + "\n").encode()

    with pytest.raises(CheckpointedPaperCycleReportSchemaError):
        parse_checkpointed_verified_snapshot_paper_cycle_request(payload)


def test_frozen_p1_profile_builds_and_detached_replay_is_no_action() -> None:
    config = MovingAverageCrossoverConfig(3, 5, Decimal("1"))
    seed_sessions = (
        date(2024, 12, 27),
        date(2024, 12, 30),
        date(2024, 12, 31),
        date(2025, 1, 2),
        date(2025, 1, 3),
    )
    seed = create_strategy_history_seed(
        symbol=SPY,
        source=_SOURCE,
        bars=tuple(
            _seed_bar(session, close)
            for session, close in zip(
                seed_sessions, ("10", "11", "12", "13", "14"), strict=True
            )
        ),
    )
    verified_seed = verify_strategy_history_seed(
        serialize_strategy_history_seed(seed),
        expected_symbol=SPY,
        target_session=_TARGET_SESSION,
        strategy_config=config,
        calendar=calendar(),
    )
    policies = replace(
        _policies(),
        rebalance_assumptions=RebalanceAssumptions(
            fixed_commission=Decimal("0"),
            allow_fractional_quantities=False,
            quantity_increment=Decimal("1"),
            minimum_trade_notional=Decimal("0"),
            minimum_trade_quantity=Decimal("1"),
            target_weight_tolerance=Decimal("0"),
            additional_execution_cash_buffer=Decimal("0"),
            use_planned_sell_proceeds=False,
        ),
        portfolio_constraints=PortfolioConstraints(
            minimum_cash_weight=Decimal("0.90"),
            maximum_cash_weight=Decimal("1"),
            maximum_position_weight=Decimal("0.10"),
            maximum_one_way_rebalance_turnover=Decimal("0.10"),
            minimum_position_weight=None,
            long_only=True,
            allow_leverage=False,
        ),
        proposal_policy=RebalanceProposalPolicy(allow_partial_plans=False),
        risk_limits=RiskLimits(
            max_position_percent=Decimal("0.10"),
            max_total_exposure_percent=Decimal("0.10"),
            max_order_notional=Decimal("2500"),
            max_new_position_percent=Decimal("0.10"),
            minimum_cash_reserve_percent=Decimal("0.90"),
            allow_fractional_shares=False,
            fractional_increment=Decimal("1"),
            allow_buying=True,
            allow_selling=True,
            estimated_commission=Decimal("0"),
        ),
        risk_policy=PortfolioRiskPolicy(allow_sell_proceeds_for_later_buys=False),
        fill_policy=PaperFillPolicy(
            slippage_basis_points=Decimal("0"),
            fixed_commission=Decimal("0"),
        ),
        trading_enabled=True,
    )
    built = build_manual_paper_strategy_plan(
        _request(
            selected_close="15",
            config=config,
            history_seed=verified_seed,
            policies=policies,
            open_price="15",
            metadata=(),
        ),
        calendar(),
    )
    replayed = verify_manual_paper_strategy_plan(
        built.artifact_bytes,
        calendar(),
        expected_sha256=built.artifact_sha256,
        expected_byte_length=built.artifact_byte_length,
        expected_checkpointed_request=built.checkpointed_request,
    )

    assert replayed == built
    assert replayed.plan.signal_status is ManualPaperStrategySignalStatus.NO_SIGNAL
    assert replayed.plan.planner_status is RebalanceStatus.NO_ACTION
    assert replayed.checkpointed_request.policies.portfolio_constraints == (
        policies.portfolio_constraints
    )


def test_base_metadata_97_becomes_exact_final_100_and_round_trips() -> None:
    from trading_bot.runtime import (
        parse_checkpointed_verified_snapshot_paper_cycle_request,
        serialize_checkpointed_verified_snapshot_paper_cycle_request,
    )

    base_metadata = tuple(MetadataEntry(f"key-{index}", "v") for index in range(97))
    bound = _binding(metadata=base_metadata)
    payload = serialize_checkpointed_verified_snapshot_paper_cycle_request(
        bound.checkpointed_request
    )

    assert len(bound.plan.request_core.metadata) == 97
    assert len(bound.checkpointed_request.metadata) == 100
    assert bound.checkpointed_request.metadata[:97] == base_metadata
    assert (
        parse_checkpointed_verified_snapshot_paper_cycle_request(payload)
        == bound.checkpointed_request
    )


def test_rejects_98_base_metadata_entries() -> None:
    metadata = tuple(MetadataEntry(f"key-{index}", "v") for index in range(98))
    with pytest.raises(ManualPaperStrategyPlanValidationError, match="base bounds"):
        _request(metadata=metadata)


@pytest.mark.parametrize(
    "metadata",
    (
        (MetadataEntry("k" * 129, "v"),),
        (MetadataEntry("key", "v" * 4097),),
    ),
)
def test_rejects_oversized_base_metadata_key_or_value(
    metadata: tuple[MetadataEntry, ...],
) -> None:
    with pytest.raises(ManualPaperStrategyPlanValidationError, match="base bounds"):
        _request(metadata=metadata)


def test_tampered_plan_id_semantic_field_and_noncanonical_bytes_fail() -> None:
    bound = _binding()
    tree = json.loads(bound.artifact_bytes)
    tree["plan_id"] = "00000000-0000-0000-0000-000000000001"
    bad_id = (json.dumps(tree, sort_keys=True, separators=(",", ":")) + "\n").encode()
    tree = json.loads(bound.artifact_bytes)
    tree["caller_idempotency_key"] = "tampered"
    bad_semantic = (
        json.dumps(tree, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    noncanonical = (
        json.dumps(json.loads(bound.artifact_bytes), indent=2).encode() + b"\n"
    )

    for payload in (bad_id, bad_semantic, noncanonical):
        with pytest.raises(
            (
                ManualPaperStrategyPlanValidationError,
                ManualPaperStrategyPlanSerializationError,
            )
        ):
            parse_manual_paper_strategy_plan(payload)


def test_strict_plan_parser_rejects_extra_duplicate_and_over_bound() -> None:
    from trading_bot.runtime import MAX_MANUAL_PAPER_STRATEGY_PLAN_BYTES

    bound = _binding()
    tree = json.loads(bound.artifact_bytes)
    tree["extra"] = True
    extra = (json.dumps(tree, sort_keys=True, separators=(",", ":")) + "\n").encode()
    duplicate = bound.artifact_bytes.replace(
        b'"schema":"manual-paper-strategy-plan/v1"',
        b'"schema":"manual-paper-strategy-plan/v1",'
        b'"schema":"manual-paper-strategy-plan/v1"',
    )

    over_bound = b"x" * (MAX_MANUAL_PAPER_STRATEGY_PLAN_BYTES + 1)
    for payload in (extra, duplicate, over_bound):
        with pytest.raises(ManualPaperStrategyPlanSerializationError):
            parse_manual_paper_strategy_plan(payload)


def test_tampered_detached_sha_length_and_injected_metadata_fail() -> None:
    bound = _binding()
    with pytest.raises(ManualPaperStrategyPlanVerificationError, match="SHA-256"):
        verify_manual_paper_strategy_plan(
            bound.artifact_bytes, calendar(), expected_sha256="0" * 64
        )
    with pytest.raises(ManualPaperStrategyPlanVerificationError, match="byte length"):
        verify_manual_paper_strategy_plan(
            bound.artifact_bytes,
            calendar(),
            expected_byte_length=bound.artifact_byte_length + 1,
        )

    final = bound.checkpointed_request
    tampered_metadata = final.metadata[:-3] + (
        final.metadata[-2],
        final.metadata[-3],
        final.metadata[-1],
    )
    tampered_request = CheckpointedVerifiedSnapshotPaperCycleRequest(
        final.request_id,
        final.snapshot_reference,
        final.target,
        final.open_references,
        final.policies,
        final.planning_at,
        final.submitted_at,
        final.filled_at,
        tampered_metadata,
    )
    with pytest.raises(
        ManualPaperStrategyPlanVerificationError, match="metadata order"
    ):
        verify_manual_paper_strategy_plan(
            bound.artifact_bytes,
            calendar(),
            expected_checkpointed_request=tampered_request,
        )

    tampered_value = final.metadata[:-2] + (
        MetadataEntry(ARCHITECTURE94_STRATEGY_PLAN_SHA256_METADATA_KEY, "0" * 64),
        final.metadata[-1],
    )
    wrong_value_request = replace(final, metadata=tampered_value)
    with pytest.raises(ManualPaperStrategyPlanVerificationError, match="injected"):
        verify_manual_paper_strategy_plan(
            bound.artifact_bytes,
            calendar(),
            expected_checkpointed_request=wrong_value_request,
        )


def test_strategy_is_called_exactly_once_for_one_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_bot.runtime import manual_paper_strategy_plan as module

    original = module.MovingAverageCrossoverStrategy.evaluate
    calls = 0

    def counted(self, context):
        nonlocal calls
        calls += 1
        return original(self, context)

    monkeypatch.setattr(module.MovingAverageCrossoverStrategy, "evaluate", counted)
    _binding()
    assert calls == 1


def test_plan_build_and_verification_never_run_paper_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("paper runtime must not run during P1")

    monkeypatch.setattr(PaperPortfolioRuntime, "run_cycle", forbidden)
    bound = _binding()
    verified = verify_manual_paper_strategy_plan(bound.artifact_bytes, calendar())
    assert verified.plan == bound.plan
