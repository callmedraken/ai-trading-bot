"""Architecture-144 pure paper-eligibility artifact coverage."""

import ast
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid5

import pytest

import trading_bot.experiments as exports
import trading_bot.experiments.research_strategy_paper_candidate_eligibility as subject
import trading_bot.experiments.research_strategy_walk_forward as walk_forward
from trading_bot.domain import Bar, Symbol
from trading_bot.experiments import (
    research_strategy_paper_evidence_verification as evidence_subject,
)
from trading_bot.experiments.research_strategy_definition import (
    ResearchStrategyDefinition,
    ResearchStrategyEvaluationPolicy,
)
from trading_bot.experiments.research_strategy_paper_candidate_eligibility import (
    OBSERVATION_TERMINAL_CLASSIFICATIONS,
    PAPER_TERMINAL_CLASSIFICATIONS,
    QUALIFYING_TERMINAL_CLASSIFICATIONS,
    REQUIRE_CONSECUTIVE_PUBLISHED_REGULAR_SESSIONS,
    REQUIRED_PAPER_EXECUTED_COUNT,
    REQUIRED_SESSION_COUNT,
    RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_IDENTITY_VERSION,
    RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_NAMESPACE,
    RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_SCHEMA,
    RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_IDENTITY_VERSION,
    RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_NAMESPACE,
    RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_SCHEMA,
    RESEARCH_STRATEGY_PAPER_SOAK_POLICY_IDENTITY_VERSION,
    RESEARCH_STRATEGY_PAPER_SOAK_POLICY_NAMESPACE,
    RESEARCH_STRATEGY_PAPER_SOAK_POLICY_SCHEMA,
    ResearchStrategyPaperCandidateEligibility,
    ResearchStrategyPaperSessionObservation,
    ResearchStrategyPaperSoakPolicy,
    canonical_decimal,
    validate_research_strategy_paper_eligibility_window,
)
from trading_bot.experiments.research_strategy_paper_candidate_eligibility import (
    ResearchStrategyPaperCandidateEligibilityError as Error,
)
from trading_bot.experiments.research_strategy_paper_evidence_verification import (
    D1R8_BRANCH,
    D1R8_SOURCE_HEAD,
    D1R8_SOURCE_TREE,
    D1R9_BRANCH,
    D1R9_SOURCE_HEAD,
    D1R9_SOURCE_TREE,
    ResearchStrategyPaperEvidenceVerificationError,
    build_verified_research_strategy_paper_candidate_eligibility,
    build_verified_research_strategy_paper_session_observation,
    verify_research_strategy_paper_candidate_eligibility,
    verify_research_strategy_paper_session_observation,
)
from trading_bot.experiments.research_strategy_production_compatibility import (
    ProductionStrategySemanticTarget,
    build_research_strategy_production_compatibility_proof,
)
from trading_bot.market_data.models import HistoricalDataRequest, HistoricalDataResult
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig as Config
from trading_bot.strategies.production import (
    MOVING_AVERAGE_STRATEGY_ID,
    MOVING_AVERAGE_STRATEGY_VERSION,
    PRODUCTION_STRATEGY_SCHEMA,
)

HEAD, TREE, PRODUCTION_HEAD, PRODUCTION_TREE = (char * 40 for char in "abcd")
JOURNAL_A = "1" * 64
JOURNAL_B = "2" * 64
_DATES = (
    date(2024, 1, 2),
    date(2024, 1, 3),
    date(2024, 1, 4),
    date(2024, 1, 5),
    date(2024, 1, 8),
)


@pytest.fixture
def evidence_chain():
    symbol = Symbol("SPY")
    definition = ResearchStrategyDefinition(
        HEAD, TREE, symbol, Config(2, 3, Decimal("1"))
    )
    policy = ResearchStrategyEvaluationPolicy(
        starting_cash=Decimal("10000"),
        fixed_commission=Decimal("0"),
        slippage_basis_points=Decimal("0"),
        trading_enabled=True,
        allow_missing_sessions=False,
        max_position_percent=Decimal("0.2"),
        max_total_exposure_percent=Decimal("0.8"),
        max_order_notional=None,
        max_new_position_percent=None,
        minimum_cash_reserve_percent=Decimal("0.1"),
        allow_fractional_shares=True,
        fractional_increment=Decimal("0.001"),
        allow_buying=True,
        allow_selling=True,
        estimated_commission=Decimal("0"),
    )
    timestamps = tuple(
        datetime(2024, 1, day, 20, tzinfo=UTC)
        for day in (2, 3, 4, 5, 8, 9, 10, 11, 12, 16, 17)
    )
    bars = tuple(
        Bar(
            symbol,
            timestamp,
            Decimal(close),
            Decimal(close),
            Decimal(close),
            Decimal(close),
            1000,
        )
        for timestamp, close in zip(
            timestamps,
            (100, 101, 99, 102, 103, 101, 104, 105, 103, 106, 107),
            strict=True,
        )
    )
    data = HistoricalDataResult(
        HistoricalDataRequest(
            symbol, datetime(2024, 1, 2, tzinfo=UTC), datetime(2024, 1, 19, tzinfo=UTC)
        ),
        bars,
        "test-memory",
    )
    folds = tuple(
        walk_forward.ResearchStrategyWalkForwardFold(
            datetime(2024, 1, start, 5, tzinfo=UTC),
            datetime(2024, 1, middle, 5, tzinfo=UTC),
            datetime(2024, 1, middle, 5, tzinfo=UTC),
            datetime(2024, 1, end, 5, tzinfo=UTC),
        )
        for start, middle, end in ((2, 5, 9), (9, 12, 17))
    )
    completed = walk_forward.run_research_strategy_walk_forward(
        definition,
        policy,
        data,
        folds,
        evaluation_source_head=PRODUCTION_HEAD,
        evaluation_source_tree=PRODUCTION_TREE,
    )
    qualification_policy = walk_forward.ResearchStrategyWalkForwardQualificationPolicy(
        minimum_fold_count=2,
        minimum_fold_return=Decimal("-1"),
        minimum_median_return=Decimal("-1"),
        maximum_fold_drawdown_percentage=Decimal("100"),
        require_equal_test_window_bar_count=True,
    )
    qualification = walk_forward.qualify_research_strategy_walk_forward(
        completed,
        qualification_policy,
        qualification_source_head=PRODUCTION_HEAD,
        qualification_source_tree=PRODUCTION_TREE,
    )
    passed = walk_forward.build_walk_forward_passed_research_strategy(
        qualification,
        completed,
        qualification_policy,
        qualification_source_head=PRODUCTION_HEAD,
        qualification_source_tree=PRODUCTION_TREE,
    )
    target = ProductionStrategySemanticTarget(
        HEAD, TREE, symbol, definition.strategy_config
    )
    proof = build_research_strategy_production_compatibility_proof(
        completed,
        qualification,
        qualification_policy,
        passed,
        target,
        qualification_source_head=PRODUCTION_HEAD,
        qualification_source_tree=PRODUCTION_TREE,
        proof_source_head=PRODUCTION_HEAD,
        proof_source_tree=PRODUCTION_TREE,
    )
    return proof, completed, qualification, qualification_policy, passed, target


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _synthetic_d1r7_facts(
    session_date: date, production_source_head: str, production_source_tree: str
) -> dict[str, object]:
    contract_material = (
        "production-strategy-contract-identity/v1",
        session_date.isoformat(),
        production_source_head,
        production_source_tree,
        MOVING_AVERAGE_STRATEGY_ID,
        MOVING_AVERAGE_STRATEGY_VERSION,
        "SPY",
        "2",
        "3",
        "1",
    )
    contract_id = uuid5(
        UUID("c0867c3b-548e-5512-a135-3c4f1225e6fc"),
        "".join(f"{len(item.encode()):}:{item}" for item in contract_material),
    )
    reservation_digest = sha256(
        _canonical(
            [
                "arch134-d1r7-d1-session-authorization/v1",
                session_date.isoformat(),
                evidence_subject._D1R5["sha256"],
                evidence_subject._D1R6["sha256"],
            ]
        )
    ).hexdigest()
    return {
        "checkpoint": "arch134-d1r7-d1-session-authorization/v1",
        "source": {
            "origin": "https://github.com/callmedraken/ai-trading-bot.git",
            "branch": evidence_subject.D1R7_BRANCH,
            "head": evidence_subject.D1R7_SOURCE_HEAD,
            "tree": evidence_subject.D1R7_SOURCE_TREE,
        },
        "intended_d1": {
            "origin": "https://github.com/callmedraken/ai-trading-bot.git",
            "branch": D1R8_BRANCH,
            "head": D1R8_SOURCE_HEAD,
            "tree": D1R8_SOURCE_TREE,
        },
        "qualification_session": "2026-10-16",
        "target_session": session_date.isoformat(),
        "observed_at": f"{session_date.isoformat()}T00:00:00+00:00",
        "authorization_expires_at": f"{session_date.isoformat()}T00:05:00+00:00",
        "reservation_basename": (
            f"arch134-d1r7-{session_date.isoformat()}-{reservation_digest}.jsonl"
        ),
        "d1r5": evidence_subject._D1R5,
        "d1r6": evidence_subject._D1R6,
        "strategy_contract": {
            "schema": PRODUCTION_STRATEGY_SCHEMA,
            "contract_id": str(contract_id),
            "target_session_date": session_date.isoformat(),
            "source_head": production_source_head,
            "source_tree": production_source_tree,
            "strategy_id": MOVING_AVERAGE_STRATEGY_ID,
            "strategy_version": MOVING_AVERAGE_STRATEGY_VERSION,
            "symbol": "SPY",
            "strategy_config": {
                "short_window": 2,
                "long_window": 3,
                "desired_quantity": "1",
            },
        },
        "d1_policy": evidence_subject._D1R7_POLICY,
    }


def _synthetic_paper_evidence(
    session_date: date,
    *,
    classification: str = "NO_SIGNAL",
    production_source_head: str = HEAD,
    production_source_tree: str = TREE,
) -> tuple[bytes, bytes]:
    d1r7 = _synthetic_d1r7_facts(
        session_date, production_source_head, production_source_tree
    )
    d1r8_facts = {
        "prerequisite": d1r7,
        "d1r7_bytes": 1,
        "d1r7_sha256": "a" * 64,
        "publication_confirmed": True,
    }
    budgets = dict(evidence_subject.D1R8_BUDGETS)
    effects = dict.fromkeys(budgets, 0)
    binding = sha256(_canonical(d1r8_facts)).hexdigest()
    observed_at = f"{session_date.isoformat()}T00:00:00+00:00"
    rows: list[dict[str, object]] = []

    def state(event: str, *, facts: object = None, result_hash: str | None = None):
        rows.append(
            {
                "schema": evidence_subject.D1R8_SCHEMA,
                "event": event,
                "action": None,
                "counter": None,
                "facts": facts,
                "binding_sha256": binding,
                "budgets": budgets,
                "effects": dict(effects),
                "classification": None,
                "observed_at": observed_at,
                "result_sha256": result_hash,
            }
        )

    def action(event: str, action_name: str, counter: str):
        if action_name == "INTENT":
            effects[counter] += 1
            if counter.endswith("credential_reads"):
                effects["credential_reads"] += 1
        rows.append(
            {
                "schema": evidence_subject.D1R8_SCHEMA,
                "event": event,
                "action": action_name,
                "counter": counter,
                "facts": None,
                "binding_sha256": binding,
                "budgets": budgets,
                "effects": dict(effects),
                "classification": None,
                "observed_at": observed_at,
                "result_sha256": None,
            }
        )

    state("SESSION_RESERVED", facts=d1r8_facts)
    state("SOURCE_AND_D1R7_BOUND")
    state("WRITE_READINESS_STARTED")
    action("WRITE_READINESS_STARTED", "INTENT", "write_readiness_attempts")
    action("WRITE_READINESS_STARTED", "ACK", "write_readiness_attempts")
    state("WRITE_READINESS_CONFIRMED")
    action("WRITE_READINESS_CONFIRMED", "INTENT", "compatibility_reservations")
    action("WRITE_READINESS_CONFIRMED", "ACK", "compatibility_reservations")
    state("LEGACY_SESSION_FENCE_CLAIMED")
    state("CREDENTIAL_READ_INTENT")
    for _ in range(2):
        action("CREDENTIAL_READ_INTENT", "INTENT", "alpaca_credential_reads")
        action("CREDENTIAL_READ_INTENT", "ACK", "alpaca_credential_reads")
    state("CREDENTIAL_READ_CONFIRMED")
    for _ in range(4):
        state("HISTORY_READ_INTENT")
        action("HISTORY_READ_INTENT", "INTENT", "alpaca_history_requests")
        action("HISTORY_READ_INTENT", "ACK", "alpaca_history_requests")
        state("HISTORY_READ_CONFIRMED")
    state("HISTORY_READY", result_hash="b" * 64)
    state("STRATEGY_STARTED")
    action("STRATEGY_STARTED", "INTENT", "strategy_evaluations")
    action("STRATEGY_STARTED", "ACK", "strategy_evaluations")
    state("STRATEGY_DECIDED", result_hash="c" * 64)
    if classification == "PAPER_EXECUTED":
        state("PREPARE_STARTED")
        action("PREPARE_STARTED", "INTENT", "prepare_attempts")
        action("PREPARE_STARTED", "ACK", "prepare_attempts")
        for _ in range(2):
            action("PREPARE_STARTED", "INTENT", "robinhood_credential_reads")
            action("PREPARE_STARTED", "ACK", "robinhood_credential_reads")
        state("QUOTE_INTENT")
        action("QUOTE_INTENT", "INTENT", "quote_requests")
        action("QUOTE_INTENT", "ACK", "quote_requests")
        state("QUOTE_CONFIRMED")
        state("PREPARED", result_hash="d" * 64)
        state("EXECUTE_STARTED")
        action("EXECUTE_STARTED", "INTENT", "execute_attempts")
        action("EXECUTE_STARTED", "ACK", "execute_attempts")
        state("ACCOUNT_READ")
        action("ACCOUNT_READ", "INTENT", "account_resolutions")
        action("ACCOUNT_READ", "ACK", "account_resolutions")
        state("BASELINE_ORDER_READS")
        for _ in range(2):
            action("BASELINE_ORDER_READS", "INTENT", "order_history_attempts")
            action("BASELINE_ORDER_READS", "ACK", "order_history_attempts")
        state("REVIEW_INTENT")
        action("REVIEW_INTENT", "INTENT", "order_reviews")
        action("REVIEW_INTENT", "ACK", "order_reviews")
        state("REVIEW_CONFIRMED")
        state("POST_REVIEW_ORDER_READS")
        for _ in range(2):
            action("POST_REVIEW_ORDER_READS", "INTENT", "order_history_attempts")
            action("POST_REVIEW_ORDER_READS", "ACK", "order_history_attempts")
        state("PAPER_WRITE_INTENT")
        action("PAPER_WRITE_INTENT", "INTENT", "paper_fill_mutations")
        action("PAPER_WRITE_INTENT", "ACK", "paper_fill_mutations")
        state("PAPER_WRITE_ACKNOWLEDGED", result_hash="e" * 64)
    elif classification != "NO_SIGNAL":
        raise AssertionError("unsupported synthetic classification")
    rows.append(
        {
            "schema": evidence_subject.D1R8_SCHEMA,
            "event": "FINAL",
            "action": None,
            "counter": None,
            "facts": None,
            "binding_sha256": binding,
            "budgets": budgets,
            "effects": dict(effects),
            "classification": classification,
            "observed_at": observed_at,
            "result_sha256": None,
        }
    )
    d1r8_payload = b"".join(_canonical(row) + b"\n" for row in rows)

    d1r9_facts = {
        "source": {
            "branch": D1R9_BRANCH,
            "head": D1R9_SOURCE_HEAD,
            "tree": D1R9_SOURCE_TREE,
        },
        "d1r7": {
            "branch": evidence_subject.D1R7_BRANCH,
            "head": evidence_subject.D1R7_SOURCE_HEAD,
            "tree": evidence_subject.D1R7_SOURCE_TREE,
        },
        "d1r8": {
            "branch": D1R8_BRANCH,
            "head": D1R8_SOURCE_HEAD,
            "tree": D1R8_SOURCE_TREE,
        },
        "target_session": session_date.isoformat(),
        "authorized_at": observed_at,
        "symbol": "SPY",
        "runtime": {
            name: {"device": 1, "inode": index, "bytes": 1, "sha256": "d" * 64}
            for index, name in enumerate(("paper", "sessions", "python"), start=1)
        },
    }
    d1r9_binding = sha256(_canonical(d1r9_facts)).hexdigest()
    d1r9_budgets = dict(evidence_subject.D1R9_BUDGETS)
    d1r9_effects = dict.fromkeys(d1r9_budgets, 0)
    d1r9_rows: list[dict[str, object]] = []

    def supervisor_row(
        event: str,
        *,
        facts: object = None,
        proof: object = None,
        final: bool = False,
    ):
        if event == "SCHEDULER_RUN_INTENT":
            d1r9_effects["scheduler_runs"] += 1
        elif event == "D1R7_DELEGATION_INTENT":
            d1r9_effects["d1r7_attempts"] += 1
        elif event == "D1R8_DELEGATION_INTENT":
            d1r9_effects["d1r8_attempts"] += 1
        d1r9_rows.append(
            {
                "schema": evidence_subject.D1R9_SCHEMA,
                "event": event,
                "classification": classification if final else None,
                "facts": facts,
                "binding": d1r9_binding,
                "effects": dict(d1r9_effects),
                "budgets": d1r9_budgets,
                "observed_at": observed_at,
                "proof": proof,
            }
        )

    supervisor_row("AUTHORIZATION_RESERVED", facts=d1r9_facts)
    supervisor_row("SOURCES_ADMITTED")
    supervisor_row("TARGET_BOUND")
    supervisor_row("SUPERVISOR_READY")
    supervisor_row("SCHEDULER_RUN_INTENT")
    supervisor_row("SCHEDULER_RUN_ACK")
    supervisor_row("D1R7_DELEGATION_INTENT")
    supervisor_row("D1R7_READY", proof={"bytes": 1, "sha256": "e" * 64})
    supervisor_row("D1R8_DELEGATION_INTENT")
    supervisor_row(
        "FINAL",
        proof={
            "bytes": len(d1r8_payload),
            "sha256": sha256(d1r8_payload).hexdigest(),
        },
        final=True,
    )
    d1r9_payload = b"".join(_canonical(row) + b"\n" for row in d1r9_rows)
    return d1r9_payload, d1r8_payload


def _uuid(name: str) -> UUID:
    return uuid5(UUID(int=0), name)


def _observation(
    session_date: date,
    *,
    classification: str = "NO_SIGNAL",
    ordinal: int = 0,
    quantity: Decimal = Decimal("1.00"),
) -> ResearchStrategyPaperSessionObservation:
    return ResearchStrategyPaperSessionObservation(
        compatibility_proof_id=_uuid("compatibility-proof"),
        production_target_id=_uuid("production-target"),
        target_session_date=session_date,
        production_contract_id=_uuid(f"production-contract-{session_date}"),
        d1r9_source_head=HEAD,
        d1r9_source_tree=TREE,
        d1r8_source_head=PRODUCTION_HEAD,
        d1r8_source_tree=PRODUCTION_TREE,
        d1r9_journal_sha256=f"{ordinal + 1:064x}",
        d1r8_journal_sha256=f"{ordinal + 11:064x}",
        terminal_classification=classification,
        symbol=Symbol("SPY"),
        strategy_config=Config(2, 3, quantity),
        production_source_head=HEAD,
        production_source_tree=TREE,
    )


def _window(
    *, executed: bool = True
) -> tuple[ResearchStrategyPaperSessionObservation, ...]:
    return tuple(
        _observation(
            session_date,
            classification=(
                "PAPER_EXECUTED"
                if executed and ordinal == len(_DATES) - 1
                else "NO_SIGNAL"
            ),
            ordinal=ordinal,
        )
        for ordinal, session_date in enumerate(_DATES)
    )


def _eligibility(
    observations: tuple[ResearchStrategyPaperSessionObservation, ...],
    *,
    paper_executed_count: int = 1,
) -> ResearchStrategyPaperCandidateEligibility:
    return ResearchStrategyPaperCandidateEligibility(
        compatibility_proof_id=observations[0].compatibility_proof_id,
        production_target_id=observations[0].production_target_id,
        policy_id=ResearchStrategyPaperSoakPolicy().policy_id,
        observation_ids=tuple(item.observation_id for item in observations),
        first_session_date=observations[0].target_session_date,
        last_session_date=observations[-1].target_session_date,
        paper_executed_count=paper_executed_count,
        symbol=observations[0].symbol,
        strategy_config=observations[0].strategy_config,
        research_strategy_source_head=HEAD,
        research_strategy_source_tree=TREE,
        production_source_head=PRODUCTION_HEAD,
        production_source_tree=PRODUCTION_TREE,
        eligibility_source_head="e" * 40,
        eligibility_source_tree="f" * 40,
    )


def test_exact_fields_fixed_values_and_package_exports() -> None:
    assert tuple(
        item.name for item in fields(ResearchStrategyPaperSessionObservation)
    ) == (
        "schema",
        "observation_id",
        "compatibility_proof_id",
        "production_target_id",
        "target_session_date",
        "production_contract_id",
        "d1r9_source_head",
        "d1r9_source_tree",
        "d1r8_source_head",
        "d1r8_source_tree",
        "d1r9_journal_sha256",
        "d1r8_journal_sha256",
        "terminal_classification",
        "production_strategy_schema",
        "strategy_id",
        "strategy_version",
        "symbol",
        "strategy_config",
        "production_source_head",
        "production_source_tree",
    )
    assert tuple(item.name for item in fields(ResearchStrategyPaperSoakPolicy)) == (
        "schema",
        "policy_id",
        "required_session_count",
        "required_paper_executed_count",
        "require_consecutive_published_regular_sessions",
        "qualifying_terminal_classifications",
    )
    assert tuple(
        item.name for item in fields(ResearchStrategyPaperCandidateEligibility)
    ) == (
        "schema",
        "eligibility_id",
        "compatibility_proof_id",
        "production_target_id",
        "policy_id",
        "observation_ids",
        "first_session_date",
        "last_session_date",
        "paper_executed_count",
        "production_strategy_schema",
        "strategy_id",
        "strategy_version",
        "symbol",
        "strategy_config",
        "research_strategy_source_head",
        "research_strategy_source_tree",
        "production_source_head",
        "production_source_tree",
        "eligibility_source_head",
        "eligibility_source_tree",
    )
    policy = ResearchStrategyPaperSoakPolicy()
    assert (
        policy.required_session_count,
        policy.required_paper_executed_count,
        policy.require_consecutive_published_regular_sessions,
        policy.qualifying_terminal_classifications,
    ) == (5, 1, True, ("NO_SIGNAL", "PAPER_EXECUTED"))
    for name in subject.__all__:
        assert getattr(exports, name) is getattr(subject, name)


def test_identity_material_is_exact_and_semantic_fields_are_significant() -> None:
    observation = _observation(_DATES[0])
    material = (
        RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_IDENTITY_VERSION,
        observation.schema,
        str(observation.compatibility_proof_id),
        str(observation.production_target_id),
        observation.target_session_date.isoformat(),
        str(observation.production_contract_id),
        observation.d1r9_source_head,
        observation.d1r9_source_tree,
        observation.d1r8_source_head,
        observation.d1r8_source_tree,
        observation.d1r9_journal_sha256,
        observation.d1r8_journal_sha256,
        observation.terminal_classification,
        observation.production_strategy_schema,
        observation.strategy_id,
        observation.strategy_version,
        str(observation.symbol),
        str(observation.strategy_config.short_window),
        str(observation.strategy_config.long_window),
        "1",
        observation.production_source_head,
        observation.production_source_tree,
    )
    expected = uuid5(
        RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_NAMESPACE,
        "".join(f"{len(item.encode('utf-8'))}:{item}" for item in material),
    )
    assert observation.observation_id == expected
    assert (
        replace(observation, terminal_classification="PAPER_EXECUTED").observation_id
        != observation.observation_id
    )
    assert (
        replace(observation, strategy_config=Config(3, 4, Decimal("1"))).observation_id
        != observation.observation_id
    )
    assert (
        replace(observation, production_source_head="e" * 40).observation_id
        != observation.observation_id
    )


def test_uuid5_framing_uses_utf8_byte_lengths() -> None:
    expected = uuid5(UUID(int=0), "2:é3:abc")
    assert subject._identity(UUID(int=0), "é", ("abc",)) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (Decimal("0"), "0"),
        (Decimal("-0"), "0"),
        (Decimal("1.2300"), "1.23"),
        (Decimal("1000.000"), "1000"),
    ],
)
def test_canonical_decimal(value: Decimal, expected: str) -> None:
    assert canonical_decimal(value) == expected


@pytest.mark.parametrize(
    "value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")]
)
def test_nonfinite_decimal_is_rejected(value: Decimal) -> None:
    with pytest.raises(Error):
        canonical_decimal(value)


def test_policy_identity_order_and_immutability() -> None:
    policy = ResearchStrategyPaperSoakPolicy()
    material = (
        RESEARCH_STRATEGY_PAPER_SOAK_POLICY_IDENTITY_VERSION,
        policy.schema,
        "5",
        "1",
        "true",
        "2",
        "NO_SIGNAL",
        "PAPER_EXECUTED",
    )
    expected = uuid5(
        RESEARCH_STRATEGY_PAPER_SOAK_POLICY_NAMESPACE,
        "".join(f"{len(item.encode('utf-8'))}:{item}" for item in material),
    )
    assert policy.policy_id == expected
    assert (
        policy.qualifying_terminal_classifications
        == QUALIFYING_TERMINAL_CLASSIFICATIONS
    )
    assert ResearchStrategyPaperSoakPolicy.from_json(policy.to_json()) == policy
    with pytest.raises(FrozenInstanceError):
        policy.required_session_count = 6  # type: ignore[misc]
    object.__setattr__(policy, "required_session_count", 6)
    with pytest.raises(Error):
        policy.to_json()


def test_canonical_json_roundtrip_and_no_eligibility_boolean() -> None:
    observations = _window()
    observation = observations[0]
    eligibility = _eligibility(observations)
    assert (
        ResearchStrategyPaperSessionObservation.from_json(observation.to_json())
        == observation
    )
    assert ResearchStrategyPaperSoakPolicy.from_json(
        ResearchStrategyPaperSoakPolicy().to_json()
    )
    assert (
        ResearchStrategyPaperCandidateEligibility.from_json(eligibility.to_json())
        == eligibility
    )
    assert "eligibility" not in {item.name for item in fields(eligibility)}
    assert not hasattr(observation, "externally_verified")


@pytest.mark.parametrize("artifact", ["observation", "eligibility", "policy"])
@pytest.mark.parametrize("mutation", ["missing", "unknown", "duplicate", "whitespace"])
def test_strict_json_field_and_byte_rejection(artifact: str, mutation: str) -> None:
    observations = _window()
    value = {
        "observation": observations[0].to_json(),
        "eligibility": _eligibility(observations).to_json(),
        "policy": ResearchStrategyPaperSoakPolicy().to_json(),
    }[artifact]
    parser = {
        "observation": ResearchStrategyPaperSessionObservation.from_json,
        "eligibility": ResearchStrategyPaperCandidateEligibility.from_json,
        "policy": ResearchStrategyPaperSoakPolicy.from_json,
    }[artifact]
    raw = json.loads(value)
    if mutation == "missing":
        raw.pop(next(iter(raw)))
        mutated = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    elif mutation == "unknown":
        raw["unknown"] = 1
        mutated = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    elif mutation == "whitespace":
        mutated = " " + value
    else:
        if artifact == "observation":
            mutated = value.replace(
                '"strategy_config":{"desired_quantity":"1","long_window":3,"short_window":2}',
                '"strategy_config":{"short_window":2,"short_window":2,"long_window":3,"desired_quantity":"1"}',
            )
        elif artifact == "policy":
            mutated = value.replace(
                '"schema":"research-strategy-paper-soak-policy/v1"',
                '"schema":"research-strategy-paper-soak-policy/v1","schema":"research-strategy-paper-soak-policy/v1"',
            )
        else:
            mutated = value.replace('"symbol":"SPY"', '"symbol":"SPY","symbol":"SPY"')
    with pytest.raises(Error):
        parser(mutated)


@pytest.mark.parametrize(
    "path,value",
    [
        (("strategy_config", "desired_quantity"), 1.0),
        (("strategy_config", "short_window"), True),
        (("target_session_date",), "20240102"),
        (("observation_id",), str(_uuid("wrong"))),
    ],
)
def test_noncanonical_scalar_rejection(path: tuple[str, ...], value: object) -> None:
    raw = json.loads(_observation(_DATES[0]).to_json())
    cursor = raw
    for name in path[:-1]:
        cursor = cursor[name]
    cursor[path[-1]] = value
    with pytest.raises(Error):
        ResearchStrategyPaperSessionObservation.from_json(
            json.dumps(raw, sort_keys=True, separators=(",", ":"))
        )


def test_eligibility_identity_preserves_observation_order_and_policy_binding() -> None:
    observations = _window()
    eligibility = _eligibility(observations)
    config = eligibility.strategy_config
    material = (
        RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_IDENTITY_VERSION,
        eligibility.schema,
        str(eligibility.compatibility_proof_id),
        str(eligibility.production_target_id),
        str(eligibility.policy_id),
        str(REQUIRED_SESSION_COUNT),
        *(str(item) for item in eligibility.observation_ids),
        eligibility.first_session_date.isoformat(),
        eligibility.last_session_date.isoformat(),
        str(eligibility.paper_executed_count),
        eligibility.production_strategy_schema,
        eligibility.strategy_id,
        eligibility.strategy_version,
        str(eligibility.symbol),
        str(config.short_window),
        str(config.long_window),
        "1",
        eligibility.research_strategy_source_head,
        eligibility.research_strategy_source_tree,
        eligibility.production_source_head,
        eligibility.production_source_tree,
        eligibility.eligibility_source_head,
        eligibility.eligibility_source_tree,
    )
    expected = uuid5(
        RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_NAMESPACE,
        "".join(f"{len(item.encode('utf-8'))}:{item}" for item in material),
    )
    assert eligibility.eligibility_id == expected
    reordered = replace(
        eligibility,
        observation_ids=(
            observations[1].observation_id,
            observations[0].observation_id,
            *(item.observation_id for item in observations[2:]),
        ),
    )
    assert reordered.eligibility_id != eligibility.eligibility_id
    assert eligibility.paper_executed_count == REQUIRED_PAPER_EXECUTED_COUNT
    with pytest.raises(Error):
        _eligibility(observations, paper_executed_count=0)
    object.__setattr__(eligibility, "policy_id", _uuid("different-policy"))
    with pytest.raises(Error):
        eligibility.to_json()


def test_intrinsic_window_validation_accepts_exact_policy_semantics() -> None:
    observations = _window()
    assert validate_research_strategy_paper_eligibility_window(observations) == 1
    assert OBSERVATION_TERMINAL_CLASSIFICATIONS == (
        "NO_SIGNAL",
        "RISK_REJECTED",
        "PAPER_EXECUTED",
    )
    assert PAPER_TERMINAL_CLASSIFICATIONS == OBSERVATION_TERMINAL_CLASSIFICATIONS
    assert REQUIRE_CONSECUTIVE_PUBLISHED_REGULAR_SESSIONS is True


@pytest.mark.parametrize(
    "mutator",
    [
        lambda values: (
            tuple(
                replace(values[0], terminal_classification="RISK_REJECTED") for _ in [0]
            )
            + values[1:]
        ),
        lambda values: (
            tuple(replace(values[-1], terminal_classification="NO_SIGNAL") for _ in [0])
            + values[1:-1]
        ),
        lambda values: (values[0], values[1], values[2], values[4], values[3]),
        lambda values: tuple(
            replace(item, strategy_config=Config(3, 4, Decimal("1")))
            if item is values[-1]
            else item
            for item in values
        ),
    ],
)
def test_intrinsic_window_validation_rejects_nonqualifying_or_inconsistent_windows(
    mutator,
) -> None:
    with pytest.raises(Error):
        validate_research_strategy_paper_eligibility_window(mutator(_window()))
    with pytest.raises(Error):
        validate_research_strategy_paper_eligibility_window(_window(executed=False))


@pytest.mark.parametrize(
    "classification", ["SESSION_MISSED", "BLOCKED", "INDETERMINATE"]
)
def test_incomplete_terminal_classifications_cannot_form_observations(
    classification: str,
) -> None:
    with pytest.raises(Error):
        _observation(_DATES[0], classification=classification)


def test_source_has_no_operational_or_external_evidence_capability() -> None:
    source_path = Path(subject.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden = {
        "D1R9",
        "D1R8",
        "ProductionStrategyContract",
        "build_production_strategy",
        "PAPER_CANDIDATE",
        "AWAITING_HUMAN_PROMOTION",
        "sqlite3",
        "subprocess",
        "socket",
        "requests",
        "uuid4",
        "now",
        "utcnow",
        "today",
        "open",
        "read_text",
        "write_text",
        "scheduler",
        "provider",
        "credential",
        "broker",
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    strings = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not forbidden & (names | attributes | strings)
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and any(
            alias.name.split(".")[0]
            in {"pathlib", "os", "sqlite3", "subprocess", "socket", "requests"}
            for alias in node.names
        )
        for node in ast.walk(tree)
    )


def test_schema_constants_are_exact() -> None:
    assert RESEARCH_STRATEGY_PAPER_SESSION_OBSERVATION_SCHEMA == (
        "research-strategy-paper-session-observation/v1"
    )
    assert (
        RESEARCH_STRATEGY_PAPER_SOAK_POLICY_SCHEMA
        == "research-strategy-paper-soak-policy/v1"
    )
    assert RESEARCH_STRATEGY_PAPER_CANDIDATE_ELIGIBILITY_SCHEMA == (
        "research-strategy-paper-candidate-eligibility/v1"
    )
    assert PRODUCTION_STRATEGY_SCHEMA
    assert MOVING_AVERAGE_STRATEGY_ID
    assert MOVING_AVERAGE_STRATEGY_VERSION
    assert sha256(_eligibility(_window()).to_json().encode()).hexdigest()


def test_144b_replays_synthetic_d1r8_and_d1r9_before_building_observation(
    evidence_chain,
) -> None:
    proof, completed, qualification, qualification_policy, passed, target = (
        evidence_chain
    )
    session_date = date(2026, 10, 19)
    d1r9_evidence, d1r8_evidence = _synthetic_paper_evidence(session_date)
    observation = build_verified_research_strategy_paper_session_observation(
        session_date,
        d1r9_evidence,
        d1r8_evidence,
        proof,
        completed,
        qualification,
        qualification_policy,
        passed,
        target,
        qualification_source_head=PRODUCTION_HEAD,
        qualification_source_tree=PRODUCTION_TREE,
        proof_source_head=PRODUCTION_HEAD,
        proof_source_tree=PRODUCTION_TREE,
    )
    verify_research_strategy_paper_session_observation(
        observation,
        d1r9_evidence,
        d1r8_evidence,
        proof,
        completed,
        qualification,
        qualification_policy,
        passed,
        target,
        qualification_source_head=PRODUCTION_HEAD,
        qualification_source_tree=PRODUCTION_TREE,
        proof_source_head=PRODUCTION_HEAD,
        proof_source_tree=PRODUCTION_TREE,
    )
    assert observation.terminal_classification == "NO_SIGNAL"
    assert observation.d1r9_source_head == D1R9_SOURCE_HEAD
    assert observation.d1r8_source_head == D1R8_SOURCE_HEAD


def test_144b_rejects_reconciled_artifact_mutation(evidence_chain) -> None:
    proof, completed, qualification, qualification_policy, passed, target = (
        evidence_chain
    )
    session_date = date(2026, 10, 19)
    d1r9_evidence, d1r8_evidence = _synthetic_paper_evidence(session_date)
    observation = build_verified_research_strategy_paper_session_observation(
        session_date,
        d1r9_evidence,
        d1r8_evidence,
        proof,
        completed,
        qualification,
        qualification_policy,
        passed,
        target,
        qualification_source_head=PRODUCTION_HEAD,
        qualification_source_tree=PRODUCTION_TREE,
        proof_source_head=PRODUCTION_HEAD,
        proof_source_tree=PRODUCTION_TREE,
    )
    with pytest.raises(ResearchStrategyPaperEvidenceVerificationError):
        verify_research_strategy_paper_session_observation(
            replace(observation, d1r8_journal_sha256="f" * 64),
            d1r9_evidence,
            d1r8_evidence,
            proof,
            completed,
            qualification,
            qualification_policy,
            passed,
            target,
            qualification_source_head=PRODUCTION_HEAD,
            qualification_source_tree=PRODUCTION_TREE,
            proof_source_head=PRODUCTION_HEAD,
            proof_source_tree=PRODUCTION_TREE,
        )


def test_144b_builds_and_replays_a_mixed_five_session_eligibility_window(
    evidence_chain,
) -> None:
    proof, completed, qualification, qualification_policy, passed, target = (
        evidence_chain
    )
    session_dates = tuple(date(2026, 10, day) for day in range(19, 24))
    session_evidence = tuple(
        (
            session_date,
            *(
                _synthetic_paper_evidence(
                    session_date,
                    classification=("PAPER_EXECUTED" if index == 4 else "NO_SIGNAL"),
                )
            ),
        )
        for index, session_date in enumerate(session_dates)
    )
    eligibility = build_verified_research_strategy_paper_candidate_eligibility(
        session_evidence,
        proof,
        completed,
        qualification,
        qualification_policy,
        passed,
        target,
        qualification_source_head=PRODUCTION_HEAD,
        qualification_source_tree=PRODUCTION_TREE,
        proof_source_head=PRODUCTION_HEAD,
        proof_source_tree=PRODUCTION_TREE,
        eligibility_source_head=PRODUCTION_HEAD,
        eligibility_source_tree=PRODUCTION_TREE,
    )
    verify_research_strategy_paper_candidate_eligibility(
        eligibility,
        session_evidence,
        proof,
        completed,
        qualification,
        qualification_policy,
        passed,
        target,
        qualification_source_head=PRODUCTION_HEAD,
        qualification_source_tree=PRODUCTION_TREE,
        proof_source_head=PRODUCTION_HEAD,
        proof_source_tree=PRODUCTION_TREE,
    )
    assert eligibility.paper_executed_count == 1
    assert eligibility.first_session_date == session_dates[0]
    assert eligibility.last_session_date == session_dates[-1]


def test_144b_source_is_pure_and_does_not_import_effectful_d1_modules() -> None:
    source_path = Path(evidence_subject.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_names = {
        "ProductionStrategyContract",
        "build_production_strategy",
        "sqlite3",
        "subprocess",
        "socket",
        "requests",
        "uuid4",
        "scheduler",
        "provider",
        "broker",
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert not forbidden_names & (names | attributes)
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not any(
        name.endswith(
            (
                "d1_session_execution_store",
                "d1_session_supervisor",
                "d1_session_execution",
            )
        )
        for name in imported_modules
    )


def test_144b_exports_are_reachable_from_experiments_package() -> None:
    for name in evidence_subject.__all__:
        assert getattr(exports, name) is getattr(evidence_subject, name)
