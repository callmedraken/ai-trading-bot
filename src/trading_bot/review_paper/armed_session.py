"""134-D1 one-session ARM controller, composing unchanged B2 and 134-C."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.domain import OrderType, TimeInForce
from trading_bot.execution.models import ExecutionInstruction
from trading_bot.market_data import AlpacaDailySnapshotProvider
from trading_bot.review_paper.alpaca_strategy_history import (
    acquire_current_production_strategy_history_from_alpaca,
    production_history_calendar,
    required_alpaca_history_sessions,
)
from trading_bot.review_paper.armed_session_store import (
    ArmedSessionStatus,
    ArmedSessionStore,
    evidence_bytes,
    write_session_evidence,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.review_paper.production_strategy_cycle import (
    ProductionStrategyPaperExecutionResult,
    ProductionStrategyPaperPreparation,
    execute_production_strategy_paper_cycle,
    prepare_production_strategy_paper_cycle,
)
from trading_bot.review_paper.production_strategy_cycle import (
    ProductionStrategyPaperPreparationStatus as PreparationStatus,
)
from trading_bot.review_paper.production_strategy_decision import (
    CurrentStrategyDecisionPolicy,
    build_current_production_strategy_decision,
)
from trading_bot.review_paper.session_admission import (
    ReviewPaperSessionStatus,
    admit_review_paper_session,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.risk.models import RiskLimits
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.strategies.production import ProductionStrategyContract
from trading_bot.strategies.production_decision import ProductionStrategyDecisionStatus

ARM_INTERLOCK = "AUTHORIZE_ARCH134_D1_ONE_SYNTHETIC_PAPER_SESSION"
_NAMESPACE = UUID("b719fe73-bc50-565d-9b77-c39da34008bd")


@dataclass(frozen=True, slots=True)
class ArmedSessionPolicy:
    risk_limits: RiskLimits
    opening_buffer: timedelta = timedelta(minutes=5)
    closing_buffer: timedelta = timedelta(minutes=5)
    max_quote_age: timedelta = timedelta(minutes=1)
    max_snapshot_age: timedelta = timedelta(minutes=10)

    def __post_init__(self) -> None:
        if type(self.risk_limits) is not RiskLimits:
            raise TypeError("exact risk configuration required")
        for value in (
            self.opening_buffer,
            self.closing_buffer,
            self.max_quote_age,
            self.max_snapshot_age,
        ):
            if type(value) is not timedelta or value <= timedelta(0):
                raise ValueError("positive explicit timing policy required")


class _SessionTerminal(Exception):
    pass


class _OneSessionArm:
    """In-memory one-shot permission; durable reservation supplies restart fence."""

    def __init__(self, contract: ProductionStrategyContract) -> None:
        self.contract = contract
        self.consumed = False

    def consume(self, contract: ProductionStrategyContract) -> None:
        if self.consumed or contract is not self.contract:
            raise ValueError("ARM already consumed or contract changed")
        self.consumed = True


def run_armed_production_paper_session(
    *,
    contract: ProductionStrategyContract,
    store: ReviewPaperStore,
    session_store: ArmedSessionStore,
    policy: ArmedSessionPolicy,
    expected_branch: str,
    evidence_path: Path,
    execute_evidence_path: Path,
    arm_interlock: str,
    clock: Callable[[], datetime],
    sleeper: Callable[[float], None],
    admit_source: Callable[[], None],
    alpaca_provider: Callable[[], AlpacaDailySnapshotProvider],
    quote_adapter: Callable[[], RobinhoodReviewReadAdapter],
) -> dict[str, object]:
    """Run one target date, one evaluation, one PREPARE and at most one EXECUTE.

    Source/secret factories are host-owned seams, never CLI-selected capabilities.
    All exceptions are sanitized. Any reserved prior attempt is non-retryable;
    only a matching durable NO_SIGNAL/PAPER_EXECUTED is reported completed.
    """
    if (
        type(contract) is not ProductionStrategyContract
        or type(store) is not ReviewPaperStore
        or type(session_store) is not ArmedSessionStore
        or type(policy) is not ArmedSessionPolicy
        or arm_interlock != ARM_INTERLOCK
    ):
        raise ValueError("session ARM admission rejected")
    key = f"armed-paper-session/v1:{contract.symbol}:{contract.target_session_date}"
    material = ("armed-paper-result/v1", str(contract.contract_id))
    operation_id = uuid5(_NAMESPACE, "".join(f"{len(x)}:{x}" for x in material))
    evidence: dict[str, object] = {
        "schema": "armed-paper-session/v1",
        "source_head": contract.source_head,
        "source_tree": contract.source_tree,
        "contract_id": str(contract.contract_id),
        "target_session": contract.target_session_date.isoformat(),
        "historical_provider": "alpaca",
        "historical_sessions": [],
        "snapshot_sha256": [],
        "history_seed_sha256": None,
        "operation_id": str(operation_id),
        "order_id": None,
        "fill_id": None,
        "strategy_outcome": None,
        "proposal_id": None,
        "wait_started_at": None,
        "admitted_at": None,
        "admission_opens_at": None,
        "admission_closes_at": None,
        "prepare_result": None,
        "execute_result": None,
        "alpaca_reads": 0,
        "strategy_evaluations": 0,
        "prepare_attempts": 0,
        "execute_attempts": 0,
        "robinhood_get_equity_quotes": 0,
        "robinhood_get_accounts": 0,
        "robinhood_get_equity_orders": 0,
        "robinhood_review_equity_order": 0,
        "paper_mutations": 0,
        "broker_placement_count": 0,
        "effect_counts_complete": True,
        "status": ArmedSessionStatus.ADMITTED.value,
    }
    admit_source()
    if evidence_path.exists():
        raise ValueError("fresh evidence destinations required")
    if (
        session_store.path.resolve()
        in {
            store.path.resolve(),
            evidence_path.resolve(),
            execute_evidence_path.resolve(),
        }
        or evidence_path.resolve() == execute_evidence_path.resolve()
    ):
        raise ValueError("session paths overlap")
    prior = session_store.reserve(key, evidence)
    if prior is not None:
        same = all(
            prior.get(k) == evidence[k]
            for k in (
                "schema",
                "source_head",
                "source_tree",
                "contract_id",
                "target_session",
                "operation_id",
            )
        )
        result = dict(prior) if same else dict(evidence)
        if same and prior.get("status") == "PAPER_EXECUTED":
            matches = [
                r
                for r in store.history()
                if str(r.intent.order_id) == prior.get("order_id")
                and str(r.fill_id) == prior.get("fill_id")
            ]
            same = len(matches) == 1
        result["status"] = (
            ArmedSessionStatus.ALREADY_COMPLETED.value
            if same
            and prior.get("status")
            in {
                ArmedSessionStatus.NO_SIGNAL.value,
                ArmedSessionStatus.PAPER_EXECUTED.value,
            }
            else ArmedSessionStatus.BLOCKED.value
        )
        write_session_evidence(evidence_path, evidence_bytes(result))
        return result
    persisted = evidence_bytes(evidence)
    arm = _OneSessionArm(contract)

    def publish(status: ArmedSessionStatus) -> None:
        nonlocal persisted
        evidence["status"] = status.value
        persisted = session_store.publish(key, persisted, evidence)

    def observe() -> datetime:
        value = clock()
        if type(value) is not datetime or value.tzinfo is None:
            raise ValueError("invalid clock")
        return value.astimezone(UTC)

    def admission(now: datetime):
        if now.astimezone(ZoneInfo("America/New_York")).date() != schedule.session_date:
            return None
        return admit_review_paper_session(
            schedule=schedule,
            as_of=now,
            opening_buffer=policy.opening_buffer,
            closing_buffer=policy.closing_buffer,
        )

    def stop(status: ArmedSessionStatus) -> None:
        publish(status)
        raise _SessionTerminal

    try:
        if execute_evidence_path.exists():
            raise ValueError("fresh execution evidence required")
        if any(
            record.intent.symbol == contract.symbol
            and record.filled_at.astimezone(ZoneInfo("America/New_York")).date()
            == contract.target_session_date
            for record in store.history()
        ):
            stop(ArmedSessionStatus.BLOCKED)
        now = observe()
        schedule = NYSEPublishedRegularSessionAuthority().schedule_for(
            contract.target_session_date
        )
        if schedule is None:
            stop(ArmedSessionStatus.SESSION_NOT_ADMITTED)
        initial = admission(now)
        if initial is None or now >= initial.admission_closes_at:
            stop(ArmedSessionStatus.SESSION_EXPIRED)
        sessions = required_alpaca_history_sessions(contract)
        evidence["historical_sessions"] = [
            item.session_date.isoformat() for item in sessions
        ]
        evidence["admission_opens_at"] = initial.admission_opens_at.isoformat()
        evidence["admission_closes_at"] = initial.admission_closes_at.isoformat()

        def before_read() -> None:
            admit_source()
            current = admission(observe())
            if current is None or current.as_of >= current.admission_closes_at:
                raise ValueError("session expired before history read")
            evidence["alpaca_reads"] += 1
            evidence["effect_counts_complete"] = False
            publish(ArmedSessionStatus.HISTORY_STARTED)

        history = acquire_current_production_strategy_history_from_alpaca(
            contract, alpaca_provider(), requested_at=now, before_read=before_read
        )
        evidence["snapshot_sha256"] = [
            sha256(p).hexdigest() for p in history.snapshot_bytes
        ]
        evidence["history_seed_sha256"] = history.history_seed.artifact_sha256
        evidence["effect_counts_complete"] = True
        publish(ArmedSessionStatus.HISTORY_READY)
        admit_source()
        planning = observe()
        current = admission(planning)
        if current is None or planning >= current.admission_closes_at:
            stop(ArmedSessionStatus.SESSION_EXPIRED)
        evidence["strategy_evaluations"] = 1
        publish(ArmedSessionStatus.HISTORY_READY)
        decision = build_current_production_strategy_decision(
            contract,
            store,
            snapshot_verification=history.snapshot_verification,
            history_seed=history.history_seed,
            strategy_config=contract.strategy_config,
            calendar=production_history_calendar(),
            planning_at=planning,
            caller_idempotency_key=str(operation_id),
            policy=CurrentStrategyDecisionPolicy(policy.max_snapshot_age),
        )
        evidence["strategy_outcome"] = decision.status.value
        if decision.status is ProductionStrategyDecisionStatus.NO_SIGNAL:
            stop(ArmedSessionStatus.NO_SIGNAL)
        evidence["proposal_id"] = str(decision.proposal.proposal_id)
        if planning < current.admission_opens_at:
            evidence["wait_started_at"] = planning.isoformat()
            publish(ArmedSessionStatus.WAITING_FOR_MARKET)
            sleeper((current.admission_opens_at - planning).total_seconds())
        admit_source()
        awake = observe()
        current = admission(awake)
        if current is None or awake >= current.admission_closes_at:
            stop(ArmedSessionStatus.SESSION_EXPIRED)
        if current.status is not ReviewPaperSessionStatus.ADMITTED:
            stop(ArmedSessionStatus.BLOCKED)
        evidence["admitted_at"] = awake.isoformat()
        evidence["prepare_attempts"] = 1
        evidence["robinhood_get_equity_quotes"] = 1
        evidence["effect_counts_complete"] = False
        publish(ArmedSessionStatus.PREPARING)
        adapter = quote_adapter()
        prepared = prepare_production_strategy_paper_cycle(
            decision=decision,
            store=store,
            schedule=schedule,
            opening_buffer=policy.opening_buffer,
            closing_buffer=policy.closing_buffer,
            adapter=adapter,
            max_quote_age=policy.max_quote_age,
            risk_limits=policy.risk_limits,
            new_trading_enabled=True,
        )
        if (
            type(prepared) is not ProductionStrategyPaperPreparation
            or prepared.decision is not decision
        ):
            raise ValueError("invalid retained preparation")
        evidence["effect_counts_complete"] = True
        evidence["robinhood_get_equity_quotes"] = int(
            prepared.supervised.price_snapshot is not None
        )
        evidence["prepare_result"] = prepared.status.value
        if prepared.status is not PreparationStatus.READY_TO_PROCEED:
            terminal = {
                "RISK_REJECTED": ArmedSessionStatus.RISK_REJECTED,
                "SESSION_NOT_ADMITTED": ArmedSessionStatus.SESSION_NOT_ADMITTED,
                "SESSION_EXPIRED_DURING_ACQUISITION": (
                    ArmedSessionStatus.SESSION_EXPIRED
                ),
            }[prepared.status.value]
            stop(terminal)
        publish(ArmedSessionStatus.READY_TO_PROCEED)
        admit_source()
        executed_at = observe()
        current = admission(executed_at)
        if current is None or current.status is not ReviewPaperSessionStatus.ADMITTED:
            stop(ArmedSessionStatus.SESSION_EXPIRED)
        arm.consume(decision.contract)
        evidence["execute_attempts"] = 1
        evidence["paper_mutations"] = None
        evidence["order_id"] = str(operation_id)
        evidence["effect_counts_complete"] = False
        publish(ArmedSessionStatus.EXECUTE_STARTED)
        result = execute_production_strategy_paper_cycle(
            preparation=prepared,
            instruction=ExecutionInstruction(
                OrderType.MARKET, TimeInForce.DAY, executed_at
            ),
            order_id=operation_id,
            expected_branch=expected_branch,
            expected_head=contract.source_head,
            expected_tree=contract.source_tree,
            evidence_path=execute_evidence_path,
            redirect_uri="http://127.0.0.1:8765/callback",
            slippage_basis_points=Decimal("0"),
            commission=Decimal("0"),
        )
        if (
            type(result) is not ProductionStrategyPaperExecutionResult
            or result.preparation is not prepared
        ):
            raise ValueError("invalid retained execution")
        operator = result.execution.pipeline_result.operator_evidence
        if operator is None:
            raise ValueError("missing execution evidence")
        for name, bound in (
            ("get_accounts", 1),
            ("get_equity_orders", 202),
            ("review_equity_order", 1),
        ):
            count = getattr(operator, name + "_calls")
            if type(count) is not int or not 0 <= count <= bound:
                raise ValueError("invalid effect count")
            evidence["robinhood_" + name] = count
        if (
            operator.status != "PASS"
            or operator.replay
            or operator.source_head != contract.source_head
            or operator.source_tree != contract.source_tree
            or operator.placement_calls != 0
            or operator.cancellation_calls != 0
            or operator.options_mutation_calls != 0
            or operator.crypto_mutation_calls != 0
            or operator.get_equity_quotes_calls != 0
            or operator.interactive_reauth_count != 0
            or not operator.review_echo_validated
            or not operator.quote_fill_validated
            or not operator.disclosure_present
        ):
            raise ValueError("execution acknowledgement failed")
        records = [r for r in store.history() if r.intent.order_id == operation_id]
        if (
            len(records) != 1
            or len(store.history()) != len(prepared.supervised.durable_history) + 1
        ):
            raise ValueError("paper fill acknowledgement failed")
        record = records[0]
        if (
            record.intent.proposal_id != decision.proposal.proposal_id
            or record.intent != result.execution.pipeline_result.intent
            or record.intent.symbol != contract.symbol
        ):
            raise ValueError("paper fill differs from retained intent")
        evidence["fill_id"] = str(record.fill_id)
        evidence["paper_mutations"] = 1
        evidence["execute_result"] = "PASS"
        evidence["effect_counts_complete"] = True
        publish(ArmedSessionStatus.PAPER_EXECUTED)
    except _SessionTerminal:
        pass
    except Exception:
        # If publication also fails, the last durable pre-effect fence survives.
        publish(ArmedSessionStatus.BLOCKED)
    write_session_evidence(evidence_path, evidence_bytes(evidence))
    return dict(evidence)
