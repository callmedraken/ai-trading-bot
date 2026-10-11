"""Provider-free production decision materialization from explicit current evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from hashlib import sha256
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailySnapshotVerificationResult,
    DailySnapshotVerificationStatus,
    canonical_bar_material,
    canonical_decimal,
    replay_verified_daily_snapshot,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.strategy_prior import build_review_paper_strategy_prior
from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.strategies.daily_decision import (
    PreparedCurrentStrategyDecision,
    evaluate_daily_strategy_decision,
)
from trading_bot.strategies.history_seed import (
    VerifiedStrategyHistorySeed,
    serialize_strategy_history_seed,
    verify_strategy_history_seed,
)
from trading_bot.strategies.production import ProductionStrategyContract
from trading_bot.strategies.production_decision import (
    ProductionStrategyDecision,
    ProductionStrategyDecisionStatus,
)

_CONTEXT_NAMESPACE = UUID("fa24a924-9a39-548d-8184-456783f7be2d")


@dataclass(frozen=True, slots=True)
class CurrentStrategyDecisionPolicy:
    """Explicit bounded freshness policy, with no inferred history acquisition."""

    max_snapshot_age: timedelta

    def __post_init__(self) -> None:
        if type(
            self.max_snapshot_age
        ) is not timedelta or self.max_snapshot_age <= timedelta(0):
            raise ValueError("max_snapshot_age must be an explicit positive timedelta")


def build_current_production_strategy_decision(
    contract: ProductionStrategyContract,
    store: ReviewPaperStore,
    *,
    snapshot_verification: DailySnapshotVerificationResult,
    history_seed: VerifiedStrategyHistorySeed,
    strategy_config: MovingAverageCrossoverConfig,
    calendar: BoundMarketCalendar,
    planning_at: datetime,
    caller_idempotency_key: str,
    policy: CurrentStrategyDecisionPolicy,
) -> ProductionStrategyDecision:
    """Validate current evidence, reconstruct paper state, and evaluate once."""
    if type(contract) is not ProductionStrategyContract:
        raise TypeError("contract must be exactly ProductionStrategyContract")
    if type(store) is not ReviewPaperStore:
        raise TypeError("store must be exactly ReviewPaperStore")
    if type(snapshot_verification) is not DailySnapshotVerificationResult:
        raise TypeError("snapshot_verification must be exact")
    if type(history_seed) is not VerifiedStrategyHistorySeed:
        raise TypeError("history_seed must be exact verified evidence")
    if type(strategy_config) is not MovingAverageCrossoverConfig:
        raise TypeError("strategy_config must be exact")
    if type(policy) is not CurrentStrategyDecisionPolicy:
        raise TypeError("policy must be exact")
    if (
        type(calendar) is not BoundMarketCalendar
        or type(calendar.calendar) is not NYSEMarketCalendar
        or calendar.descriptor != XNYS_CALENDAR_DESCRIPTOR
    ):
        raise ValueError("calendar must be an exact bound XNYS calendar")
    if (
        type(planning_at) is not datetime
        or planning_at.tzinfo is None
        or planning_at.utcoffset() is None
    ):
        raise ValueError("planning_at must be an explicit aware datetime")
    planning_at = planning_at.astimezone(UTC)
    if (
        type(caller_idempotency_key) is not str
        or not caller_idempotency_key.strip()
        or caller_idempotency_key != caller_idempotency_key.strip()
        or len(caller_idempotency_key) > 256
    ):
        raise ValueError("caller_idempotency_key must be bounded explicit text")
    if (
        strategy_config != contract.strategy_config
        or history_seed.strategy_config != contract.strategy_config
        or history_seed.seed.symbol != contract.symbol
    ):
        raise ValueError("strategy/history config or symbol does not match contract")
    verification = snapshot_verification
    if (
        verification.status is not DailySnapshotVerificationStatus.PASS
        or verification.snapshot is None
        or verification.diagnostics
    ):
        raise ValueError("one complete PASS snapshot verification is required")
    payload = serialize_daily_snapshot(verification.snapshot)
    if (
        sha256(payload).hexdigest() != verification.sha256
        or len(payload) != verification.byte_length
    ):
        raise ValueError("snapshot verification does not match canonical evidence")
    verified = verify_daily_snapshot(
        payload,
        calendar,
        expected_sha256=verification.sha256,
        expected_byte_length=verification.byte_length,
    )
    if verified.status is not DailySnapshotVerificationStatus.PASS:
        raise ValueError("snapshot fails calendar replay")
    replay = replay_verified_daily_snapshot(verified)
    if replay.symbols != (contract.symbol,) or len(replay.bars) != 1:
        raise ValueError(
            "snapshot must contain exactly the contract symbol/current bar"
        )
    current = replay.bars[0]
    if (
        current.bar.symbol != contract.symbol
        or current.session != replay.target_session
    ):
        raise ValueError("current bar/session does not reconcile")
    zone = ZoneInfo(calendar.descriptor.exchange_timezone)
    anchor = datetime.combine(replay.target_session.session_date, time(12), zone)
    execution_session = calendar.next_session(anchor)
    if (
        execution_session.session_date != contract.target_session_date
        or planning_at.astimezone(zone).date() != contract.target_session_date
        or calendar.previous_session(planning_at) != replay.target_session
        or history_seed.target_session != replay.target_session
    ):
        raise ValueError("snapshot/history/planning session does not match contract")
    captured_at = verified.snapshot.audit.captured_at
    if not timedelta(0) <= planning_at - captured_at <= policy.max_snapshot_age:
        raise ValueError("snapshot is stale or captured after planning")
    seed_payload = serialize_strategy_history_seed(history_seed.seed)
    if (
        sha256(seed_payload).hexdigest() != history_seed.artifact_sha256
        or len(seed_payload) != history_seed.artifact_byte_length
    ):
        raise ValueError("history artifact evidence disagrees")
    seed = verify_strategy_history_seed(
        seed_payload,
        expected_symbol=contract.symbol,
        target_session=replay.target_session,
        strategy_config=contract.strategy_config,
        calendar=calendar,
    )
    if seed != history_seed:
        raise ValueError("history evidence does not replay exactly")
    prior = build_review_paper_strategy_prior(
        store, symbol=contract.symbol, as_of=planning_at
    )
    # Versioned semantic values; no paths, artifact hashes or legacy IDs.
    parts = (
        "current-production-strategy-context/v1",
        str(contract.contract_id),
        str(verified.snapshot.snapshot_id),
        str(seed.seed.seed_id),
        canonical_bar_material(seed.seed.bars + replay.bars),
        str(prior.compact_state.compact_state_id),
        str(prior.sequence),
        *(str(item) for item in prior.fill_ids),
        caller_idempotency_key,
        canonical_timestamp(planning_at),
        str(policy.max_snapshot_age.days),
        str(policy.max_snapshot_age.seconds),
        str(policy.max_snapshot_age.microseconds),
        canonical_decimal(contract.strategy_config.desired_quantity),
    )
    material = "".join(f"{len(item.encode('utf-8'))}:{item}" for item in parts)
    run_id = uuid5(_CONTEXT_NAMESPACE, material)
    proposal = evaluate_daily_strategy_decision(
        run_id=run_id,
        step_index=prior.sequence,
        current_bar=current.bar,
        target_session=replay.target_session,
        seed_bars=seed.seed.bars,
        compact=prior.compact_state,
        strategy_config=contract.strategy_config,
        account_positions=prior.positions,
    )
    prepared = PreparedCurrentStrategyDecision(
        verified,
        seed,
        prior.compact_state,
        prior.fill_ids,
        contract.strategy_config,
        contract.symbol,
        replay.target_session,
        execution_session,
        run_id,
        prior.sequence,
        proposal,
        prior.positions,
        planning_at,
        caller_idempotency_key,
        policy.max_snapshot_age,
    )
    return ProductionStrategyDecision(
        contract,
        prepared,
        ProductionStrategyDecisionStatus.NO_SIGNAL
        if proposal is None
        else ProductionStrategyDecisionStatus.TRADE_PROPOSAL,
        proposal,
    )
