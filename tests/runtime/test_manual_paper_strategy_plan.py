"""Focused Architecture-94 P1 deterministic strategy-plan coverage."""

import json
import os
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest
from tests.market_data.daily_snapshot_test_support import (
    CAPTURED_AT,
    SPY,
    accepted_result,
    calendar,
    candidate,
    capture_request,
)
from tests.runtime.test_verified_snapshot_preparation import _policies

from trading_bot.domain import Bar, OrderSide
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    DailySnapshotBar,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime import (
    ARCHITECTURE94_STRATEGY_PLAN_BYTE_LENGTH_METADATA_KEY,
    ARCHITECTURE94_STRATEGY_PLAN_ID_METADATA_KEY,
    ARCHITECTURE94_STRATEGY_PLAN_SHA256_METADATA_KEY,
    CallerAssertedNextSessionOpenReference,
    CheckpointedVerifiedSnapshotPaperCycleRequest,
    ManualPaperStrategyPlanRequest,
    ManualPaperStrategyPlanSerializationError,
    ManualPaperStrategyPlanValidationError,
    ManualPaperStrategyPlanVerificationError,
    ManualPaperStrategySignalStatus,
    PaperAccountCheckpointPosition,
    PaperAccountGenesisRequest,
    PaperPortfolioRuntime,
    StrategyHistorySeedSourceDescriptor,
    build_manual_paper_strategy_plan,
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
    prior=None,
    caller_key: str = "manual-cycle-1",
    open_price: str = "12",
    policies=None,
    planning_at: datetime = CAPTURED_AT + timedelta(minutes=1),
    submitted_at: datetime = CAPTURED_AT + timedelta(minutes=2),
    filled_at: datetime = datetime(2025, 1, 7, 20, tzinfo=UTC),
    metadata: tuple[MetadataEntry, ...] = (MetadataEntry("source", "test"),),
) -> ManualPaperStrategyPlanRequest:
    return ManualPaperStrategyPlanRequest(
        _snapshot(selected_close),
        prior or _prior(),
        _verified_seed(config, closes),
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
