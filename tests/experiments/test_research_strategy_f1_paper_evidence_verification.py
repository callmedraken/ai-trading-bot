"""Synthetic supplied-byte F1 admission; no operational adapters or evidence."""

import ast
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid5

import pytest

import trading_bot.experiments.research_strategy_walk_forward as walk_forward
from trading_bot.domain import Bar, Symbol
from trading_bot.experiments import (
    research_strategy_f1_paper_evidence_verification as subject,
)
from trading_bot.experiments.research_strategy_definition import (
    ResearchStrategyDefinition,
    ResearchStrategyEvaluationPolicy,
)
from trading_bot.experiments.research_strategy_paper_candidate_eligibility_v2 import (
    ResearchStrategyPaperCandidateEligibilityV2,
    ResearchStrategyPaperSessionObservationV2,
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
DATES = tuple(date(2026, 10, day) for day in (20, 21, 22, 23, 26))
PINS = dict(
    qualification_source_head=PRODUCTION_HEAD,
    qualification_source_tree=PRODUCTION_TREE,
    proof_source_head=PRODUCTION_HEAD,
    proof_source_tree=PRODUCTION_TREE,
)


@pytest.fixture(scope="module")
def evidence_chain():
    symbol = Symbol("SPY")
    definition = ResearchStrategyDefinition(
        subject.D1R8_SOURCE_HEAD,
        subject.D1R8_SOURCE_TREE,
        symbol,
        Config(2, 3, Decimal("1")),
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
        subject.D1R8_SOURCE_HEAD,
        subject.D1R8_SOURCE_TREE,
        symbol,
        definition.strategy_config,
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
                subject._D1R5["sha256"],
                subject._D1R6["sha256"],
            ]
        )
    ).hexdigest()
    return {
        "checkpoint": "arch134-d1r7-d1-session-authorization",
        "source": {
            "origin": "https://github.com/callmedraken/ai-trading-bot.git",
            "branch": subject.D1R7_BRANCH,
            "head": subject.D1R7_SOURCE_HEAD,
            "tree": subject.D1R7_SOURCE_TREE,
        },
        "intended_d1": {
            "origin": "https://github.com/callmedraken/ai-trading-bot.git",
            "branch": subject.D1R8_BRANCH,
            "head": subject.D1R8_SOURCE_HEAD,
            "tree": subject.D1R8_SOURCE_TREE,
        },
        "qualification_session": "2026-10-16",
        "target_session": session_date.isoformat(),
        "observed_at": f"{session_date.isoformat()}T13:00:00+00:00",
        "authorization_expires_at": f"{session_date.isoformat()}T19:55:00+00:00",
        "reservation_basename": (
            f"arch134-d1r7-{session_date.isoformat()}-{reservation_digest}.jsonl"
        ),
        "d1r5": subject._D1R5,
        "d1r6": subject._D1R6,
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
        "d1_policy": subject._D1R7_POLICY,
    }


def _synthetic_paper_evidence(
    session_date: date,
    *,
    classification: str = "NO_SIGNAL",
    production_source_head: str = subject.D1R8_SOURCE_HEAD,
    production_source_tree: str = subject.D1R8_SOURCE_TREE,
    observed_at: str | None = None,
    authorization_expires_at: str | None = None,
    terminal_at: str | None = None,
) -> tuple[bytes, bytes]:
    observed_at = observed_at or f"{session_date.isoformat()}T13:00:00+00:00"
    authorization_expires_at = (
        authorization_expires_at or f"{session_date.isoformat()}T19:55:00+00:00"
    )
    terminal_at = terminal_at or observed_at
    d1r7 = _synthetic_d1r7_facts(
        session_date, production_source_head, production_source_tree
    )
    d1r7["observed_at"] = observed_at
    d1r7["authorization_expires_at"] = authorization_expires_at
    d1r7_payload = b"".join(
        _canonical(
            {
                "schema": "arch134-d1r7-d1-session-authorization/v1",
                "event": event,
                "classification": subject._D1R7_READY if event == "FINAL" else None,
                "reason_code": "PREREQUISITES_BOUND" if event == "FINAL" else None,
                "facts": d1r7,
                "budgets": dict.fromkeys(subject._D1R7_COUNTERS, 0),
                "effects": dict.fromkeys(subject._D1R7_COUNTERS, 0),
                "authority": dict.fromkeys(subject._D1R7_AUTHORITY, False),
            }
        )
        + b"\n"
        for event in subject._D1R7_EVENTS
    )
    d1r8_facts = {
        "prerequisite": d1r7,
        "d1r7_bytes": len(d1r7_payload),
        "d1r7_sha256": sha256(d1r7_payload).hexdigest(),
        "publication_confirmed": True,
    }
    budgets = dict(subject.D1R8_BUDGETS)
    effects = dict.fromkeys(budgets, 0)
    binding = sha256(_canonical(d1r8_facts)).hexdigest()
    rows: list[dict[str, object]] = []

    def state(event: str, *, facts: object = None, result_hash: str | None = None):
        rows.append(
            {
                "schema": subject.D1R8_SCHEMA,
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
                "schema": subject.D1R8_SCHEMA,
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
    if classification in {"RISK_REJECTED", "PAPER_EXECUTED"}:
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
    if classification == "PAPER_EXECUTED":
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
    elif classification not in {"NO_SIGNAL", "RISK_REJECTED"}:
        raise AssertionError("unsupported synthetic classification")
    rows.append(
        {
            "schema": subject.D1R8_SCHEMA,
            "event": "FINAL",
            "action": None,
            "counter": None,
            "facts": None,
            "binding_sha256": binding,
            "budgets": budgets,
            "effects": dict(effects),
            "classification": classification,
            "observed_at": terminal_at,
            "result_sha256": None,
        }
    )
    d1r8_payload = b"".join(_canonical(row) + b"\n" for row in rows)

    return d1r7_payload, d1r8_payload


def packed(rows):
    return b"".join(_canonical(row) + b"\n" for row in rows)


def rows(payload):
    return [json.loads(line) for line in payload.splitlines()]


def proof(payload):
    return {"bytes": len(payload), "sha256": sha256(payload).hexdigest()}


def journal_row(
    facts, event, effects, at, *, first=False, classification=None, evidence=None
):
    child = facts["kind"] == "child"
    return dict(
        schema=subject._f1_child_schema if child else subject._f1_schema,
        event=event,
        classification=classification,
        facts=facts if first else None,
        binding=subject._f1_digest(facts),
        identity=subject._f1_domain_id(facts),
        effects=dict(effects),
        budgets=subject._f1_child_budgets if child else subject._f1_budgets,
        observed_at=at,
        proof=evidence,
    )


def synthetic_window(
    classifications=(
        "PAPER_EXECUTED",
        "NO_SIGNAL",
        "NO_SIGNAL",
        "NO_SIGNAL",
        "NO_SIGNAL",
    ),
):
    # Test data only. No runtime Journal, controller, Plan, host or store is used.
    facts = dict(
        source=dict(
            branch=subject._f1_branch,
            head=subject.PAPER_AUTHORITY_SOURCE_HEAD,
            tree=subject.PAPER_AUTHORITY_SOURCE_TREE,
        ),
        d1r7=subject._f1_d1r7,
        d1r8=subject._f1_d1r8,
        semantic_predecessor=subject._f1_d1r9_predecessor,
        symbol="SPY",
        targets=[d.isoformat() for d in DATES],
        contracts=[subject._f1_contract(d.isoformat()) for d in DATES],
        policy=subject._f1_policy,
        scheduler=subject._f1_scheduler,
        ceilings=subject._f1_ceilings,
        runtime={
            name: dict(device=1, inode=i, bytes=1, sha256="a" * 64)
            for i, name in enumerate(("paper", "sessions", "python"), 1)
        },
        authorized_at="2026-10-20T12:00:00+00:00",
        kind="parent",
    )
    parent = []
    effects = dict.fromkeys(subject._f1_budgets, 0)
    at = facts["authorized_at"]
    for event in (
        "SOAK_RESERVED",
        "SOURCES_ADMITTED",
        "WINDOW_BOUND",
        "SCHEDULER_CREATE_INTENT",
        "SCHEDULER_CREATE_ACK",
        "SOAK_READY",
        "SCHEDULER_RUN_INTENT",
        "SCHEDULER_RUN_ACK",
    ):
        if event == "SCHEDULER_CREATE_INTENT":
            effects["scheduler_creates"] += 1
        if event == "SCHEDULER_RUN_INTENT":
            effects["scheduler_runs"] += 1
        parent.append(journal_row(facts, event, effects, at, first=not parent))
    evidence = []
    summaries = []
    for ordinal, (day, status) in enumerate(
        zip(DATES, classifications, strict=True), 1
    ):
        at = day.isoformat() + "T13:00:00+00:00"
        effects["child_grants"] += 1
        parent.append(
            journal_row(facts, f"SESSION_{ordinal}_GRANT_INTENT", effects, at)
        )
        prefix = proof(packed(parent))
        cf = dict(
            facts,
            kind="child",
            parent_id=parent[0]["identity"],
            parent_prefix=prefix,
            ordinal=ordinal,
            target_session=day.isoformat(),
        )
        p7, p8 = _synthetic_paper_evidence(day, classification=status)
        child = []
        ce = dict.fromkeys(subject._f1_child_budgets, 0)
        for event in (
            "CHILD_RESERVED",
            "SOURCES_ADMITTED",
            "TARGET_BOUND",
            "CHILD_READY",
            "D1R7_DELEGATION_INTENT",
            "D1R7_READY",
            "D1R8_DELEGATION_INTENT",
            "FINAL",
        ):
            if event == "D1R7_DELEGATION_INTENT":
                ce["d1r7_attempts"] += 1
            if event == "D1R8_DELEGATION_INTENT":
                ce["d1r8_attempts"] += 1
            child.append(
                journal_row(
                    cf,
                    event,
                    ce,
                    at,
                    first=not child,
                    classification=status if event == "FINAL" else None,
                    evidence=proof(p7)
                    if event == "D1R7_READY"
                    else proof(p8)
                    if event == "FINAL"
                    else None,
                )
            )
        cb = packed(child)
        summary = dict(
            ordinal=ordinal,
            target_session=day.isoformat(),
            child_id=child[0]["identity"],
            child_journal=proof(cb),
            grant_prefix=prefix,
            classification=status,
            d1r7=proof(p7),
            d1r8=proof(p8),
            effects=ce,
            d1r8_effects=rows(p8)[-1]["effects"],
            contract=facts["contracts"][ordinal - 1],
        )
        parent.append(
            journal_row(
                facts,
                f"SESSION_{ordinal}_FINAL",
                effects,
                at,
                classification=status,
                evidence=summary,
            )
        )
        summaries.append(summary)
        evidence.append((day, cb, p7, p8))
    parent.append(
        journal_row(
            facts,
            "FINAL",
            effects,
            at,
            classification="COMPLETED",
            evidence=dict(
                children=summaries,
                scheduler="MATCH",
                parent_prefix=proof(packed(parent)),
            ),
        )
    )
    return packed(parent), tuple(evidence)


def observation(chain, parent, session):
    day, child, p7, p8 = session
    return subject.build_verified_research_strategy_paper_session_observation_v2(
        day, parent, child, p7, p8, *chain, **PINS
    )


def eligibility(chain, parent, sessions):
    return subject.build_verified_research_strategy_paper_candidate_eligibility_v2(
        parent,
        sessions,
        *chain,
        **PINS,
        eligibility_source_head=HEAD,
        eligibility_source_tree=TREE,
    )


@pytest.fixture(scope="module")
def window():
    return synthetic_window()


def test_complete_five_session_replay_and_verifiers(evidence_chain, window):
    parent, sessions = window
    for ordinal, session in enumerate(sessions, 1):
        result = observation(evidence_chain, parent, session)
        assert result.authority_child_ordinal == ordinal
        assert result.authority_parent_journal_sha256 == sha256(parent).hexdigest()
        assert (
            ResearchStrategyPaperSessionObservationV2.from_json(result.to_json())
            == result
        )
        subject.verify_research_strategy_paper_session_observation_v2(
            result, parent, *session[1:], *evidence_chain, **PINS
        )
    result = eligibility(evidence_chain, parent, sessions)
    assert result.paper_executed_count == 1
    assert (
        ResearchStrategyPaperCandidateEligibilityV2.from_json(result.to_json())
        == result
    )
    subject.verify_research_strategy_paper_candidate_eligibility_v2(
        result,
        parent,
        sessions,
        *evidence_chain,
        **PINS,
        eligibility_source_head=HEAD,
        eligibility_source_tree=TREE,
    )


@pytest.mark.parametrize("status", ["NO_SIGNAL", "RISK_REJECTED", "PAPER_EXECUTED"])
def test_terminal_matrix(evidence_chain, status):
    parent, sessions = synthetic_window((status,) * 5)
    assert (
        observation(evidence_chain, parent, sessions[0]).terminal_classification
        == status
    )
    if status == "PAPER_EXECUTED":
        assert eligibility(evidence_chain, parent, sessions).paper_executed_count == 5
    else:
        with pytest.raises(ValueError):
            eligibility(evidence_chain, parent, sessions)


@pytest.mark.parametrize("surface", ["parent", "child", "d1r7", "d1r8"])
@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "prefix",
        "truncate",
        "trailing",
        "utf8",
        "duplicate",
        "whitespace",
        "oversize",
        "nonbytes",
    ],
)
def test_malformed_supplied_bytes_fail(evidence_chain, window, surface, mutation):
    parent, sessions = window
    day, child, p7, p8 = sessions[0]
    blobs = [parent, child, p7, p8]
    idx = ["parent", "child", "d1r7", "d1r8"].index(surface)
    original = blobs[idx]
    changed = {
        "empty": b"",
        "prefix": original[: original.index(b"\n") + 1],
        "truncate": original[:-1],
        "trailing": original + b"\n",
        "utf8": b"\xff",
        "duplicate": original.replace(b"{", b'{"schema":"duplicate",', 1),
        "whitespace": b" " + original,
        "oversize": b"x" * 2097153,
        "nonbytes": "text",
    }[mutation]
    blobs[idx] = changed
    with pytest.raises(ValueError):
        observation(evidence_chain, blobs[0], (day, *blobs[1:]))


def rebind(payload, mutate):
    data = rows(payload)
    mutate(data)
    return packed(data)


@pytest.mark.parametrize(
    "mutation",
    [
        "schema",
        "branch",
        "head",
        "tree",
        "identity",
        "binding",
        "timestamp",
        "backward",
        "skip",
        "counter",
        "scheduler",
        "prefix_bytes",
        "prefix_hash",
        "child_count",
        "child_order",
        "child_target",
        "child_contract",
        "child_digest",
        "child_effects",
        "child_ordinal",
        "child_id",
        "grant",
    ],
)
def test_parent_replay_rejects_mutations(evidence_chain, window, mutation):
    parent, sessions = window

    def change(r):
        summary = r[-1]["proof"]["children"][0]
        if mutation in ("branch", "head", "tree"):
            r[0]["facts"]["source"][mutation] = "0" * 40
        elif mutation == "schema":
            r[0]["schema"] = "wrong"
        elif mutation in ("identity", "binding"):
            r[-1][mutation] = "0" * 64
        elif mutation == "timestamp":
            r[1]["observed_at"] = "2026-10-20T12:00:00Z"
        elif mutation == "backward":
            r[1]["observed_at"] = "2026-10-19T12:00:00+00:00"
        elif mutation == "skip":
            del r[2]
        elif mutation == "counter":
            r[-1]["effects"]["child_grants"] = 6
        elif mutation == "scheduler":
            r[-1]["proof"]["scheduler"] = "DRIFT"
        elif mutation == "prefix_bytes":
            r[-1]["proof"]["parent_prefix"]["bytes"] += 1
        elif mutation == "prefix_hash":
            r[-1]["proof"]["parent_prefix"]["sha256"] = "0" * 64
        elif mutation == "child_count":
            r[-1]["proof"]["children"].pop()
        elif mutation == "child_order":
            r[-1]["proof"]["children"].reverse()
        elif mutation == "child_target":
            summary["target_session"] = "2026-10-27"
        elif mutation == "child_contract":
            summary["contract"]["strategy_config"]["short_window"] = 3
        elif mutation == "child_digest":
            summary["child_journal"]["sha256"] = "0" * 64
        elif mutation == "child_effects":
            summary["d1r8_effects"]["paper_fill_mutations"] = 0
        elif mutation == "child_ordinal":
            summary["ordinal"] = 2
        elif mutation == "child_id":
            summary["child_id"] = str(uuid5(UUID(int=0), "wrong"))
        elif mutation == "grant":
            summary["grant_prefix"]["sha256"] = "0" * 64

    bad = rebind(parent, change)
    with pytest.raises(ValueError):
        observation(evidence_chain, bad, sessions[0])


@pytest.mark.parametrize("surface", ["child", "d1r7", "d1r8"])
@pytest.mark.parametrize(
    "mutation",
    [
        "schema",
        "source",
        "target",
        "contract",
        "effects",
        "terminal",
        "ordering",
        "proof",
    ],
)
def test_underlying_proofs_reject_mutations(evidence_chain, window, surface, mutation):
    parent, sessions = window
    session = list(sessions[0])
    idx = {"child": 1, "d1r7": 2, "d1r8": 3}[surface]

    def change(r):
        f = r[0]["facts"]
        if mutation == "schema":
            r[0]["schema"] = "wrong"
        elif mutation == "effects":
            r[-1]["effects"][next(iter(r[-1]["effects"]))] = 99
        elif mutation == "terminal":
            r[-1]["classification"] = "INDETERMINATE"
        elif mutation == "ordering":
            del r[2]
        elif mutation == "proof":
            r[-1]["proof"] = {"bytes": 1, "sha256": "0" * 64}
        else:
            if surface == "d1r8":
                f = f["prerequisite"]
            if mutation == "source":
                f["source"]["head"] = "0" * 40
            elif mutation == "target":
                f["target_session"] = "2026-10-27"
            elif mutation == "contract":
                if surface == "child":
                    f["contracts"][0]["symbol"] = "QQQ"
                else:
                    f["strategy_contract"]["symbol"] = "QQQ"

    session[idx] = rebind(session[idx], change)
    with pytest.raises(ValueError):
        observation(evidence_chain, parent, tuple(session))


def test_complete_142_143_verification_and_target_pin_checks(evidence_chain, window):
    parent, sessions = window
    for idx, _item in enumerate(evidence_chain):
        altered = list(evidence_chain)
        altered[idx] = None
        with pytest.raises(ValueError):
            observation(tuple(altered), parent, sessions[0])
    for name in PINS:
        pins = dict(PINS, **{name: "e" * 40})
        with pytest.raises(ValueError):
            subject.build_verified_research_strategy_paper_session_observation_v2(
                sessions[0][0], parent, *sessions[0][1:], *evidence_chain, **pins
            )


def test_exact_external_reconciliation_and_v1_rejection(evidence_chain, window):
    from trading_bot.experiments.research_strategy_paper_evidence_verification import (
        build_verified_research_strategy_paper_session_observation,
    )

    parent, sessions = window
    day, child, p7, p8 = sessions[0]
    with pytest.raises(ValueError):
        build_verified_research_strategy_paper_session_observation(
            day, child, p8, *evidence_chain, **PINS
        )
    result = observation(evidence_chain, parent, sessions[0])
    forged = replace(result, authority_child_journal_sha256="0" * 64)
    with pytest.raises(ValueError):
        subject.verify_research_strategy_paper_session_observation_v2(
            forged, parent, child, p7, p8, *evidence_chain, **PINS
        )
    good = eligibility(evidence_chain, parent, sessions)
    with pytest.raises(ValueError):
        subject.verify_research_strategy_paper_candidate_eligibility_v2(
            replace(good, eligibility_source_head="e" * 40),
            parent,
            sessions,
            *evidence_chain,
            **PINS,
            eligibility_source_head=HEAD,
            eligibility_source_tree=TREE,
        )
    for bad in (
        sessions[:4],
        sessions[::-1],
        sessions + (sessions[0],),
        tuple([sessions[0]] * 5),
    ):
        with pytest.raises(ValueError):
            eligibility(evidence_chain, parent, bad)


def test_sources_have_no_operational_capabilities():
    forbidden = {
        "os",
        "pathlib",
        "sqlite3",
        "subprocess",
        "socket",
        "requests",
        "http",
        "random",
        "time",
        "ctypes",
        "win32com",
        "importlib",
    }
    allowed = {
        "trading_bot.domain",
        "trading_bot.experiments.research_strategy_paper_candidate_eligibility",
        "trading_bot.experiments.research_strategy_paper_candidate_eligibility_v2",
        "trading_bot.experiments.research_strategy_production_compatibility",
        "trading_bot.experiments.research_strategy_walk_forward",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.strategies.moving_average",
        "trading_bot.strategies.production",
        "trading_bot.market_calendar",
    }
    for name in (
        "research_strategy_paper_candidate_eligibility_v2.py",
        "research_strategy_f1_paper_evidence_verification.py",
    ):
        source = Path(subject.__file__).with_name(name).read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(x.name.split(".")[0] not in forbidden for x in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module.split(".")[0] not in forbidden
                if node.module.startswith("trading_bot."):
                    assert node.module in allowed
                assert all(not x.name.startswith("_") for x in node.names)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in {"open", "eval", "exec", "__import__"}
                if isinstance(node.func, ast.Attribute):
                    assert node.func.attr not in {
                        "now",
                        "today",
                        "uuid4",
                        "read_bytes",
                        "read_text",
                        "write_bytes",
                        "write_text",
                        "connect",
                        "Popen",
                    }


@pytest.mark.parametrize(
    "mutation",
    [
        "saved_effects",
        "r7_digest",
        "r8_digest",
        "classification",
        "grant_prefix",
        "before_grant",
        "child_ordinal",
        "child_identity",
        "d1r8_binding",
        "d1r7_policy",
        "unacknowledged",
        "partial_terminal",
    ],
)
def test_reconciled_outer_hashes_cannot_hide_underlying_drift(
    evidence_chain, window, mutation
):
    # Alter the last child, then rebuild its outer saved digest and the complete
    # parent FINAL prefix proof. A matching outer hash is never verification.
    parent, sessions = window
    parents = rows(parent)
    day, child, p7, p8 = sessions[-1]
    children, r7, r8 = rows(child), rows(p7), rows(p8)
    summary = parents[-2]["proof"]
    if mutation == "saved_effects":
        summary["d1r8_effects"]["credential_reads"] = 1
    elif mutation == "r7_digest":
        summary["d1r7"]["sha256"] = "0" * 64
    elif mutation == "r8_digest":
        summary["d1r8"]["sha256"] = "0" * 64
    elif mutation == "classification":
        summary["classification"] = "RISK_REJECTED"
        parents[-2]["classification"] = "RISK_REJECTED"
    elif mutation == "grant_prefix":
        children[0]["facts"]["parent_prefix"]["sha256"] = "0" * 64
    elif mutation == "before_grant":
        children[0]["observed_at"] = day.isoformat() + "T12:00:00+00:00"
    elif mutation == "child_ordinal":
        children[0]["facts"]["ordinal"] = 4
    elif mutation == "child_identity":
        for row in children:
            row["identity"] = str(uuid5(UUID(int=0), "wrong"))
    elif mutation == "d1r8_binding":
        r8[0]["facts"]["d1r7_sha256"] = "0" * 64
    elif mutation == "d1r7_policy":
        for row in r7:
            row["facts"]["d1_policy"]["opening_buffer_seconds"] = 0
    elif mutation == "unacknowledged":
        index = next(i for i, row in enumerate(r8) if row["action"] == "ACK")
        del r8[index]
    elif mutation == "partial_terminal":
        del r8[2:-1]
    child, p7, p8 = packed(children), packed(r7), packed(r8)
    summary["child_journal"] = proof(child)
    parents[-1]["proof"]["children"][-1] = summary
    parents[-1]["proof"]["parent_prefix"] = proof(packed(parents[:-1]))
    with pytest.raises(ValueError):
        observation(evidence_chain, packed(parents), (day, child, p7, p8))


@pytest.mark.parametrize(
    "mutation",
    ["parent", "child", "contract", "ordinal", "target", "proof", "effects", "clock"],
)
def test_frozen_final_and_positive_boundaries(evidence_chain, window, mutation):
    parent, sessions = window
    day, child, p7, p8 = sessions[0]
    if mutation == "parent":
        parent = rebind(
            parent, lambda r: r[-1].update(classification="BLOCKED", proof=None)
        )
    elif mutation == "child":
        child = rebind(
            child, lambda r: r[-1].update(classification="INDETERMINATE", proof=None)
        )
    elif mutation == "contract":
        day = DATES[1]
    elif mutation == "ordinal":
        child = rebind(child, lambda r: r[0]["facts"].update(ordinal=True))
    elif mutation == "target":
        child = sessions[1][1]
    elif mutation == "proof":
        p7, p8 = sessions[1][2:]
    elif mutation == "effects":
        p8 = rebind(p8, lambda r: r[-1]["effects"].update(credential_reads=True))
    elif mutation == "clock":
        p8 = rebind(p8, lambda r: r[-1].update(observed_at="2026-10-20T19:55:00+00:00"))
    with pytest.raises(ValueError):
        observation(evidence_chain, parent, (day, child, p7, p8))
