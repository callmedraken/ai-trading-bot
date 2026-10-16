"""134-B2 pure current-product materialization and legacy compatibility."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Context, Decimal, localcontext
from pathlib import Path
from uuid import UUID

import pytest
from tests.market_data.daily_snapshot_test_support import (
    CAPTURED_AT,
    QQQ,
    SPY,
    calendar,
)
from tests.review_paper.test_store import _intent, _review
from tests.runtime.test_manual_paper_strategy_plan import (
    _DEFAULT_CONFIG,
    _NEXT_SESSION,
    _decision_request,
    _request,
    _seed_bar,
    _snapshot,
    _verified_seed,
)

from scripts import checkpoint_runner
from trading_bot.domain import OrderSide
from trading_bot.review_paper import production_strategy_decision as subject
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.strategy_prior import (
    ReviewPaperStrategyPrior,
    build_review_paper_strategy_prior,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperStrategyPlanValidationError,
    build_manual_paper_strategy_decision,
)
from trading_bot.strategies import (
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
    daily_decision,
    history_seed,
)
from trading_bot.strategies.production import ProductionStrategyContract
from trading_bot.strategies.production_decision import ProductionStrategyDecisionStatus

PLANNING = CAPTURED_AT + timedelta(minutes=1)


def contract(**kwargs):
    return ProductionStrategyContract(
        kwargs.get("target", _NEXT_SESSION.session_date),
        "a" * 40,
        "b" * 40,
        kwargs.get("symbol", SPY),
        kwargs.get("config", _DEFAULT_CONFIG),
    )


@pytest.fixture
def store(tmp_path):
    return ReviewPaperStore(tmp_path / "paper.sqlite", starting_cash=Decimal("1000"))


def build(store, **kwargs):
    values = dict(
        snapshot_verification=_snapshot(),
        history_seed=_verified_seed(_DEFAULT_CONFIG, ("10", "10", "9")),
        strategy_config=_DEFAULT_CONFIG,
        calendar=calendar(),
        planning_at=PLANNING,
        caller_idempotency_key="current-cycle-1",
        policy=subject.CurrentStrategyDecisionPolicy(timedelta(minutes=10)),
    )
    selected_contract = kwargs.pop("contract", contract())
    values.update(kwargs)
    return subject.build_current_production_strategy_decision(
        selected_contract, store, **values
    )


def fill(store, *, side=OrderSide.BUY, quantity="2", price="10", identity=1):
    at = datetime(2025, 1, 3, 16, identity, tzinfo=UTC)
    intent = _intent(
        order_id=UUID(int=identity),
        side=side,
        desired=Decimal(quantity),
        approved=Decimal(quantity),
        proposed_at=at,
    )
    review = _review(
        side=side,
        quantity=Decimal(quantity),
        bid=Decimal(price),
        ask=Decimal(price),
        quote_time=at + timedelta(seconds=1),
    )
    return store.record_market_review(intent, review)


def test_empty_prior_preserves_starting_cash_and_bytes(store):
    before, history = store.path.read_bytes(), store.history()
    prior = build_review_paper_strategy_prior(store, symbol=SPY, as_of=PLANNING)
    assert prior.sequence == 0 and prior.fill_ids == ()
    assert prior.compact_state.cash == store.starting_cash
    assert prior.compact_state.positions == ()
    assert prior.compact_state.realized_profit_loss == Decimal("0")
    assert prior.compact_state.as_of == PLANNING
    assert store.path.read_bytes() == before and store.history() == history


def test_fills_reconstruct_cash_positions_basis_realized_without_writes(
    store, monkeypatch
):
    buy = fill(store, quantity="5", price="10", identity=1)
    sell = fill(store, side=OrderSide.SELL, quantity="2", price="15", identity=2)
    before, history = store.path.read_bytes(), store.history()

    def forbidden(*args, **kwargs):
        raise AssertionError("durable writes forbidden")

    monkeypatch.setattr(ReviewPaperStore, "record_market_review", forbidden)
    monkeypatch.setattr(ReviewPaperStore, "_initialize", forbidden)
    prior = build_review_paper_strategy_prior(store, symbol=SPY, as_of=PLANNING)
    assert prior.sequence == 2 and prior.fill_ids == (buy.fill_id, sell.fill_id)
    assert prior.compact_state.cash == Decimal("980")
    assert prior.compact_state.realized_profit_loss == Decimal("10")
    (position,) = prior.compact_state.positions
    assert (
        position.symbol,
        position.quantity,
        position.average_cost,
        position.total_cost_basis,
    ) == (
        SPY,
        Decimal("3"),
        Decimal("10"),
        Decimal("30"),
    )
    build(store)
    assert store.path.read_bytes() == before and store.history() == history


def test_prior_arithmetic_is_independent_of_ambient_decimal(store):
    fill(store, quantity="2", price="10.12345", identity=1)
    expected = build_review_paper_strategy_prior(store, symbol=SPY, as_of=PLANNING)
    with localcontext(Context(prec=3)):
        assert (
            build_review_paper_strategy_prior(store, symbol=SPY, as_of=PLANNING)
            == expected
        )


def test_prior_requires_exact_store_and_cannot_be_invented(store):
    class DerivedStore(ReviewPaperStore):
        pass

    derived = DerivedStore(store.path, starting_cash=store.starting_cash)
    for invalid in (object(), store.path, derived):
        with pytest.raises(TypeError):
            build_review_paper_strategy_prior(invalid, symbol=SPY, as_of=PLANNING)
    valid = build_review_paper_strategy_prior(store, symbol=SPY, as_of=PLANNING)
    with pytest.raises(ValueError, match="must come from"):
        ReviewPaperStrategyPrior(SPY, valid.compact_state, (), (), object())


def test_future_or_wrong_symbol_history_fails(store):
    fill(store)
    with pytest.raises(ValueError, match="unsupported symbol or future fill"):
        build_review_paper_strategy_prior(store, symbol=QQQ, as_of=PLANNING)
    with pytest.raises(ValueError, match="unsupported symbol or future fill"):
        build_review_paper_strategy_prior(
            store, symbol=SPY, as_of=datetime(2025, 1, 1, tzinfo=UTC)
        )


def test_inconsistent_reconstruction_fails(store, monkeypatch):
    fill(store)
    original = ReviewPaperStore.reconstruct_ledger

    def inconsistent(self):
        ledger = original(self)
        ledger._fills.clear()
        return ledger

    monkeypatch.setattr(ReviewPaperStore, "reconstruct_ledger", inconsistent)
    with pytest.raises(ValueError, match="reconstruction disagrees"):
        build_review_paper_strategy_prior(store, symbol=SPY, as_of=PLANNING)


def test_history_change_during_reconstruction_fails(store, monkeypatch):
    record = fill(store)
    original = ReviewPaperStore.history
    calls = 0

    def changing(self):
        nonlocal calls
        calls += 1
        return () if calls == 3 else original(self)

    monkeypatch.setattr(ReviewPaperStore, "history", changing)
    with pytest.raises(ValueError, match="history changed"):
        build_review_paper_strategy_prior(store, symbol=SPY, as_of=PLANNING)
    assert record in original(store)


@pytest.mark.parametrize("no_signal", [False, True])
def test_evaluate_once_closed_outcome_and_proposal_identity(
    store, monkeypatch, no_signal
):
    proposals, contexts = [], []
    original = MovingAverageCrossoverStrategy.evaluate

    def once(self, context):
        contexts.append(context)
        proposal = original(self, context)
        proposals.append(proposal)
        return proposal

    monkeypatch.setattr(MovingAverageCrossoverStrategy, "evaluate", once)
    values = (
        {}
        if not no_signal
        else {
            "history_seed": _verified_seed(_DEFAULT_CONFIG, ("10", "11", "12")),
            "snapshot_verification": _snapshot("13"),
        }
    )
    before = store.path.read_bytes()
    result = build(store, **values)
    assert len(proposals) == len(contexts) == 1
    assert result.proposal is proposals[0] is result.prepared.strategy_proposal
    assert result.status is (
        ProductionStrategyDecisionStatus.NO_SIGNAL
        if no_signal
        else ProductionStrategyDecisionStatus.TRADE_PROPOSAL
    )
    assert (result.proposal is None) == no_signal
    assert contexts[0].step_index == 0
    assert store.path.read_bytes() == before


def test_durable_sequence_and_determinism(store):
    fill(store)
    first = build(store)
    second = build(store)
    assert first == second
    assert first.prepared.strategy_step_index == 1
    assert first.prepared.prior_state.cash == Decimal("980")
    assert len(first.prepared.durable_fill_ids) == 1
    assert (
        first.prepared.strategy_run_id
        != build(store, caller_idempotency_key="other").prepared.strategy_run_id
    )


@pytest.mark.parametrize(
    "mutation",
    [
        {"contract": object()},
        {"contract": contract(symbol=QQQ)},
        {"contract": contract(target=date(2025, 1, 8))},
        {"strategy_config": MovingAverageCrossoverConfig(2, 4, Decimal("2"))},
        {"history_seed": None},
        {"snapshot_verification": None},
        {"planning_at": PLANNING + timedelta(days=1)},
        {"planning_at": PLANNING + timedelta(hours=1)},
        {"planning_at": CAPTURED_AT - timedelta(seconds=1)},
        {"planning_at": PLANNING.replace(tzinfo=None)},
        {"caller_idempotency_key": ""},
        {"policy": object()},
        {"calendar": object()},
    ],
)
def test_invalid_current_evidence_fails_before_evaluation(store, monkeypatch, mutation):
    def forbidden(*args, **kwargs):
        raise AssertionError("evaluation must not run")

    monkeypatch.setattr(MovingAverageCrossoverStrategy, "evaluate", forbidden)
    with pytest.raises((TypeError, ValueError)):
        build(store, **mutation)


def test_history_hash_config_and_session_drift_fail_before_evaluation(
    store, monkeypatch
):
    valid = _verified_seed(_DEFAULT_CONFIG, ("10", "10", "9"))

    def forbidden(*args, **kwargs):
        raise AssertionError("evaluation must not run")

    monkeypatch.setattr(MovingAverageCrossoverStrategy, "evaluate", forbidden)
    for field, value in (
        ("artifact_sha256", "a" * 64),
        ("strategy_config", MovingAverageCrossoverConfig(1, 2, Decimal("2"))),
        ("target_session", _NEXT_SESSION),
    ):
        # Existing construction-protected evidence can be corrupted without minting it.
        original = getattr(valid, field)
        object.__setattr__(valid, field, value)
        with pytest.raises(ValueError):
            build(store, history_seed=valid)
        object.__setattr__(valid, field, original)


@pytest.mark.parametrize(
    "bars",
    [
        (_seed_bar(date(2025, 1, 3), "9"),),
        tuple(
            _seed_bar(day, close)
            for day, close in zip(
                (date(2024, 12, 30), date(2024, 12, 31), date(2025, 1, 2)),
                ("10", "10", "9"),
                strict=True,
            )
        ),
    ],
)
def test_insufficient_or_stale_seed_fails_before_evaluation(store, monkeypatch, bars):
    valid = _verified_seed(_DEFAULT_CONFIG, ("10", "10", "9"))
    seed = history_seed.create_strategy_history_seed(
        symbol=SPY, source=valid.seed.source, bars=bars
    )
    payload = history_seed.serialize_strategy_history_seed(seed)
    from hashlib import sha256

    object.__setattr__(valid, "seed", seed)
    object.__setattr__(valid, "artifact_sha256", sha256(payload).hexdigest())
    object.__setattr__(valid, "artifact_byte_length", len(payload))

    def forbidden(*args, **kwargs):
        raise AssertionError("evaluation must not run")

    monkeypatch.setattr(MovingAverageCrossoverStrategy, "evaluate", forbidden)
    with pytest.raises(ValueError):
        build(store, history_seed=valid)


def test_legacy_and_current_enter_same_core(store, monkeypatch):
    from trading_bot.runtime import manual_paper_strategy_plan as legacy

    calls = []
    original = daily_decision.evaluate_daily_strategy_decision

    def shared(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(legacy, "evaluate_daily_strategy_decision", shared)
    monkeypatch.setattr(subject, "evaluate_daily_strategy_decision", shared)
    request = _decision_request(_request())
    expected = build_manual_paper_strategy_decision(request, calendar())
    current = build(store)
    assert len(calls) == 2
    assert calls[0]["strategy_config"] == calls[1]["strategy_config"]
    assert calls[0]["current_bar"] == calls[1]["current_bar"]
    assert expected.strategy_proposal is not None and current.proposal is not None
    assert expected.strategy_proposal.reason == current.proposal.reason
    prior = build_review_paper_strategy_prior(store, symbol=SPY, as_of=PLANNING)
    with pytest.raises(ManualPaperStrategyPlanValidationError):
        replace(request, prior_checkpoint=prior)
    object.__setattr__(request, "prior_checkpoint", prior)
    with pytest.raises(ManualPaperStrategyPlanValidationError):
        build_manual_paper_strategy_decision(request, calendar())


def test_current_import_does_not_load_historical_runtime_or_provider_operator(tmp_path):
    script = tmp_path / "import_current.py"
    script.write_text(
        "import sys\n"
        "import trading_bot.review_paper.production_strategy_decision\n"
        "assert not any(name.startswith('trading_bot.runtime') "
        "for name in sys.modules)\n"
        "assert not any('robinhood_mcp' in name or "
        "'production_strategy_prepare_operator' in name "
        "for name in sys.modules)\n",
        encoding="utf-8",
    )
    root = Path(subject.__file__).resolve().parents[2]
    environment = dict(os.environ, PYTHONPATH=str(root))
    result = subprocess.run(
        [sys.executable, "-B", str(script)],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_current_ast_closure_has_no_authority_forgery_or_effects():
    from trading_bot.review_paper import strategy_prior

    modules = (subject, strategy_prior, daily_decision, history_seed)
    forbidden_imports = (
        "personal_desktop",
        "verified_c3",
        "checkpointed_verified",
        "d10",
        "robinhood_mcp",
        "oauth",
        "scheduler",
        "subprocess",
        "socket",
        "urllib",
        "httpx",
        "requests",
        "supervised_forward_paper",
        "production_strategy_cycle",
        "production_strategy_prepare_operator",
        "experiments",
        "optimization",
        "windows",
        "acl_repair",
        "scratch_root_acl",
    )
    forbidden_calls = {
        "VerifiedPriorCheckpoint",
        "record_market_review",
        "_initialize",
        "ReviewPaperStore",
        "review_equity_order",
        "place_order",
        "execute",
        "connect",
        "sleep",
        "now",
        "utcnow",
        "eval",
        "exec",
        "__import__",
        "run",
        "Popen",
        "chmod",
        "write_text",
        "write_bytes",
    }
    for module in modules:
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "_VERIFIED_PRIOR_AUTHORITY" not in source
        assert "Paper-v2" not in source
        tree = ast.parse(source)
        imports = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        ]
        imports += [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ]
        assert not any(
            part in name.lower() for name in imports for part in forbidden_imports
        )
        calls = {
            getattr(node.func, "attr", getattr(node.func, "id", ""))
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        assert not calls & forbidden_calls
    assert (
        sum(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "evaluate"
            for node in ast.walk(
                ast.parse(Path(daily_decision.__file__).read_text(encoding="utf-8"))
            )
        )
        == 1
    )


def test_unique_active_route_current_ownership_and_authority():
    root = Path(checkpoint_runner.__file__).resolve().parents[1]
    name = "arch134-production-strategy-live-paper"
    matches = [
        key
        for key, spec in checkpoint_runner._checkpoint_specs().items()
        if spec.remote_branch == "feature/robinhood-production-strategy-live-paper"
        and key in checkpoint_runner.ACTIVE_CI_CHECKPOINTS
    ]
    assert matches == [name]
    assert checkpoint_runner._checkpoint_specs()[name].preflight is None
    assert checkpoint_runner._checkpoint_specs()[name].execute is None
    assert (
        checkpoint_runner._arch134_production_strategy_live_paper_authority_check(root)
        == ()
    )


def test_multiple_symbol_history_is_rejected_even_with_one_symbol_contract(store):
    fill(store)
    at = datetime(2025, 1, 3, 16, 2, tzinfo=UTC)
    intent = replace(
        _intent(
            order_id=UUID(int=2),
            desired=Decimal("1"),
            approved=Decimal("1"),
            proposed_at=at,
        ),
        symbol=QQQ,
    )
    review = _review(
        quantity=Decimal("1"), bid=Decimal("10"), ask=Decimal("10"), quote_time=at
    )
    review = replace(review, symbol=QQQ, quote=replace(review.quote, symbol=QQQ))
    store.record_market_review(intent, review)
    before = store.path.read_bytes()
    with pytest.raises(ValueError, match="unsupported symbol"):
        build(store)
    assert store.path.read_bytes() == before


def test_exact_ledger_average_cost_reaches_shared_core(store, monkeypatch):
    fill(store, quantity="2", price="10", identity=1)
    fill(store, quantity="1", price="11", identity=2)
    ledger = store.reconstruct_ledger()
    prior = build_review_paper_strategy_prior(store, symbol=SPY, as_of=PLANNING)
    assert prior.positions == tuple(ledger.positions.values())
    assert prior.positions[0].average_cost == Decimal("31") / Decimal("3")
    original = MovingAverageCrossoverStrategy.evaluate

    def inspect_context(self, context):
        assert context.positions == ledger.positions
        assert context.account_snapshot.cash == ledger.cash
        assert (
            context.account_snapshot.realized_profit_loss == ledger.realized_profit_loss
        )
        return original(self, context)

    monkeypatch.setattr(MovingAverageCrossoverStrategy, "evaluate", inspect_context)
    build(store)


def test_missing_store_is_rejected_without_recreating_database(store):
    store._path = store.path.parent / "missing.sqlite"
    with pytest.raises(ValueError, match="store is missing"):
        build_review_paper_strategy_prior(store, symbol=SPY, as_of=PLANNING)
    assert not store.path.exists()


def test_malformed_and_wrong_symbol_snapshot_fail_before_evaluation(store, monkeypatch):
    from tests.market_data.daily_snapshot_test_support import (
        accepted_result,
        candidate,
        capture_request,
    )

    from trading_bot.market_data import (
        serialize_daily_snapshot,
        verify_daily_snapshot,
    )

    valid = _snapshot()
    other = accepted_result(
        request=capture_request(symbols=(QQQ,)), candidates=(candidate(QQQ, 0),)
    )
    wrong_symbol = verify_daily_snapshot(
        serialize_daily_snapshot(other.snapshot), calendar()
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("evaluation must not run")

    monkeypatch.setattr(MovingAverageCrossoverStrategy, "evaluate", forbidden)
    for snapshot in (
        replace(valid, sha256="a" * 64),
        verify_daily_snapshot(b"{}", calendar()),
        wrong_symbol,
    ):
        with pytest.raises(ValueError):
            build(store, snapshot_verification=snapshot)


def test_current_result_preserves_exact_types_and_closed_status(store):
    from trading_bot.strategies.production_decision import ProductionStrategyDecision

    result = build(store)
    with pytest.raises(ValueError):
        replace(result, status=ProductionStrategyDecisionStatus.NO_SIGNAL)
    with pytest.raises(ValueError):
        replace(result, proposal=replace(result.proposal, reason="substitution"))

    class DerivedPrepared(daily_decision.PreparedCurrentStrategyDecision):
        pass

    from dataclasses import fields

    derived = DerivedPrepared(
        **{
            field.name: getattr(result.prepared, field.name)
            for field in fields(result.prepared)
        }
    )
    with pytest.raises(TypeError):
        ProductionStrategyDecision(
            result.contract, derived, result.status, result.proposal
        )


def test_relocated_history_primitives_are_the_exact_legacy_exports():
    from trading_bot.runtime import strategy_history_seed as legacy

    assert (
        legacy.VerifiedStrategyHistorySeed is history_seed.VerifiedStrategyHistorySeed
    )
    assert (
        legacy.verify_strategy_history_seed is history_seed.verify_strategy_history_seed
    )
    assert (
        legacy.serialize_strategy_history_seed
        is history_seed.serialize_strategy_history_seed
    )
