"""133-D uses actual 133-C/131-H/I/store with only credential/provider fakes."""

import ast
import hashlib
import json
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

import trading_bot.review_paper.unattended_execution as module
import trading_bot.review_paper.unattended_one_wake as coordinator
import trading_bot.robinhood_paper_operator as operator
from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce, TradeProposal
from trading_bot.execution.models import ExecutionInstruction
from trading_bot.review_paper.intent_bridge import build_review_paper_intent
from trading_bot.review_paper.models import (
    ReviewPaperIntent,
    review_paper_fill_id,
    review_paper_trade_id,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.unattended_activation import ReviewPaperActivation
from trading_bot.review_paper.unattended_activation import ReviewPaperWakeState as State
from trading_bot.review_paper.unattended_one_wake import (
    OneWakeInstants,
    OneWakeStateError,
)
from trading_bot.review_paper.unattended_state_store import UnattendedStateStore
from trading_bot.risk import RiskLimits, RiskOutcome
from trading_bot.robinhood_mcp.parsing import parse_review_equity_order_response
from trading_bot.robinhood_mcp.sdk_transport import RobinhoodMcpStreamableHttpTransport
from trading_bot.robinhood_mcp.windows_oauth import WindowsOAuthStorage

AT = datetime(2026, 10, 5, 16, tzinfo=UTC)
SPY = Symbol("SPY")
SECRET = "fake-secret-never-evidence"


def quote(at=AT):
    return dict(
        symbol="SPY",
        adjusted_previous_close="100",
        ask_price="101",
        bid_price="99",
        has_traded=True,
        last_non_reg_trade_price=None,
        last_trade_price="100",
        previous_close="100",
        previous_close_date=None,
        state="active",
        venue_ask_time=at.isoformat(),
        venue_bid_time=at.isoformat(),
        venue_last_non_reg_trade_time=None,
        venue_last_trade_time=at.isoformat(),
    )


def review(side, quantity, at=AT):
    return {
        "data": dict(
            symbol="SPY",
            side=side,
            quantity=quantity,
            type="market",
            quote_data=quote(at),
            market_data_disclosure=SECRET,
            order_checks={"fake": SECRET},
        )
    }


@pytest.fixture
def harness(tmp_path, monkeypatch):
    h = SimpleNamespace(
        calls=[],
        oauth_reads=0,
        failure=None,
        operator_calls=0,
        fault=None,
        previews=[],
        review_received_at=None,
        quote_clock_calls=0,
        quote_observed_at=AT,
        quote_source_at=AT,
    )
    h.paper_store = ReviewPaperStore(
        tmp_path / "paper.sqlite", starting_cash=Decimal("10000")
    )
    h.state_store = UnattendedStateStore(tmp_path / "wake.sqlite")
    h.activation = ReviewPaperActivation(
        source_head="a" * 40,
        source_tree="b" * 40,
        deployment_identity="c" * 64,
        target_session_date=AT.date(),
        proposal=TradeProposal(
            UUID(int=1), SPY, OrderSide.BUY, Decimal("1"), AT, "frozen"
        ),
        risk_limits=RiskLimits(),
        new_trading_enabled=True,
        store_identity=UUID(int=2),
        store_path=str(h.paper_store.path),
        starting_cash=Decimal("10000"),
        opening_buffer=timedelta(minutes=5),
        closing_buffer=timedelta(minutes=5),
        max_quote_age=timedelta(minutes=1),
        slippage_basis_points=Decimal("5"),
        commission=Decimal("0.1"),
        local_order_id=UUID(int=3),
        created_at=AT,
    )
    h.instants = OneWakeInstants(
        AT, AT + timedelta(seconds=10), AT + timedelta(seconds=11)
    )

    def quote_clock():
        h.quote_clock_calls += 1
        assert h.calls and h.calls[-1][0] == "get_equity_quotes"
        return h.quote_observed_at

    h.binding = module.UnattendedExecutionBinding(
        "feature/robinhood-unattended-review-paper-133d",
        "a" * 40,
        "b" * 40,
        "c" * 64,
        tmp_path / "evidence.json",
        "http://127.0.0.1:8765/oauth/callback",
        AT + timedelta(minutes=5),
        quote_clock,
    )
    h.oauth_storage = object.__new__(WindowsOAuthStorage)
    original_preview = coordinator.build_review_paper_forward_preview

    def observed_preview(**kwargs):
        value = original_preview(**kwargs)
        h.previews.append(value)
        return value

    monkeypatch.setattr(
        coordinator, "build_review_paper_forward_preview", observed_preview
    )

    async def get_tokens(self):
        h.oauth_reads += 1
        if h.failure == "oauth":
            raise RuntimeError(SECRET)
        if h.failure == "missing_oauth":
            return None
        return SimpleNamespace(token_type="Bearer", access_token=SECRET, expires_in=300)

    monkeypatch.setattr(WindowsOAuthStorage, "get_tokens", get_tokens)
    # No optional HTTP/SDK dependency or real credential access in source gates.
    monkeypatch.setitem(
        sys.modules, "httpx2", SimpleNamespace(Auth=type("Auth", (), {}))
    )

    async def caller(name, arguments):
        current = h.state_store.snapshot().current(h.activation)
        assert current.wake.state is (
            State.PREPARE_STARTED
            if name == "get_equity_quotes"
            else State.REVIEW_STARTED
        )
        h.calls.append((name, arguments))
        if h.failure == name:
            raise RuntimeError(SECRET)
        if name == "get_equity_quotes":
            assert arguments == {"symbols": ["SPY"]}
            return {
                "data": {
                    "results": [{"quote": quote(h.quote_source_at), "close": None}]
                }
            }
        if name == "get_accounts":
            return {
                "data": {
                    "accounts": [{"account_number": SECRET, "agentic_allowed": True}]
                }
            }
        if name == "get_equity_orders":
            return {"data": {"next": "", "orders": []}}
        if name == "review_equity_order":
            return review(arguments["side"], arguments["quantity"])
        pytest.fail("forbidden provider call")

    class TestTransport(RobinhoodMcpStreamableHttpTransport):
        def __new__(cls, factory):
            assert factory.__name__ == "PersistedAuth"
            assert SECRET not in repr(factory())
            return RobinhoodMcpStreamableHttpTransport.for_test(caller)

    monkeypatch.setattr(module, "RobinhoodMcpStreamableHttpTransport", TestTransport)
    monkeypatch.setattr(operator, "RobinhoodMcpStreamableHttpTransport", TestTransport)
    monkeypatch.setattr(
        operator, "_admit_source", lambda *args: (tmp_path / "repository",)
    )
    monkeypatch.setattr(
        operator,
        "create_windows_robinhood_oauth_factory",
        lambda **kw: pytest.fail("interactive/refresh OAuth composition"),
    )
    real_operator = module.run_robinhood_paper_operator

    def observed_operator(**kwargs):
        h.operator_calls += 1
        h.review_received_at = kwargs["review_received_at"]
        assert (
            h.state_store.snapshot().current(h.activation).wake.state
            is State.REVIEW_STARTED
        )
        assert kwargs["paper_store_path"] == h.paper_store.path
        assert kwargs["starting_cash"] == h.activation.starting_cash
        assert kwargs["slippage_basis_points"] == h.activation.slippage_basis_points
        assert kwargs["commission"] == h.activation.commission
        intent = kwargs["intent"]
        h.intent = intent
        assert intent == build_review_paper_intent(
            h.previews[-1].risk_decision,
            ExecutionInstruction(
                OrderType.MARKET,
                TimeInForce.DAY,
                max(h.instants.pre_effect_at, h.quote_observed_at),
            ),
            order_id=h.activation.local_order_id,
        )
        assert intent.order_id == h.activation.local_order_id
        assert intent.proposal_id == h.activation.proposal.proposal_id
        if h.fault == "exception":
            raise RuntimeError(SECRET)
        if h.fault == "process":
            raise SystemExit(SECRET)
        if h.fault == "alternate_order":
            kwargs["intent"] = replace(intent, order_id=UUID(int=300))
        if h.fault == "alternate_quantity":
            kwargs["intent"] = replace(intent, approved_quantity=Decimal("2"))
        if h.fault == "alternate_commission":
            kwargs["commission"] = Decimal("1")
        if h.fault == "alternate_slippage":
            kwargs["slippage_basis_points"] = Decimal("10")
        evidence = real_operator(**kwargs)
        if h.fault == "post_commit_exception":
            raise RuntimeError(SECRET)
        if h.fault == "missing_evidence":
            kwargs["evidence_path"].unlink()
        if h.fault == "malformed":
            return None
        if isinstance(h.fault, dict):
            evidence = replace(evidence, **h.fault)
            kwargs["evidence_path"].write_text(
                json.dumps(asdict(evidence), sort_keys=True) + "\n"
            )
        return evidence

    monkeypatch.setattr(module, "run_robinhood_paper_operator", observed_operator)
    return h


def run(h):
    expected = h.state_store.snapshot().current(h.activation)
    return module.execute_one_unattended_review_paper_wake(
        activation=h.activation,
        expected=expected,
        state_store=h.state_store,
        paper_store=h.paper_store,
        instants=h.instants,
        binding=h.binding,
        oauth_storage=h.oauth_storage,
    )


def admit(h):
    h.state_store.admit(h.activation)


def replay_is_inert(h):
    before = (
        h.state_store.path.read_bytes(),
        h.paper_store.path.read_bytes(),
        list(h.calls),
        h.oauth_reads,
        h.operator_calls,
    )
    result = run(h)
    assert result.wake.quote_attempts == result.wake.effect_attempts == 0
    assert result.operator_evidence is None
    assert before == (
        h.state_store.path.read_bytes(),
        h.paper_store.path.read_bytes(),
        h.calls,
        h.oauth_reads,
        h.operator_calls,
    )


def test_post_quote_clock_advances_pre_effect_time(harness):
    h = harness
    h.quote_observed_at = AT + timedelta(seconds=20)
    h.quote_source_at = h.quote_observed_at
    admit(h)
    result = run(h)
    assert result.wake.final_state is State.COMPLETED
    assert result.wake.admissions[-1].as_of == h.quote_observed_at
    assert h.review_received_at == h.quote_observed_at
    assert h.quote_clock_calls == 1
    assert h.operator_calls == 1


def test_quote_return_after_closing_buffer_stops_before_review(harness):
    h = harness
    late = datetime(2026, 10, 5, 19, 55, 1, tzinfo=UTC)
    h.quote_observed_at = late
    h.quote_source_at = late
    h.binding = replace(
        h.binding, oauth_valid_until=late + timedelta(minutes=5)
    )
    admit(h)
    result = run(h)
    assert result.wake.final_state is State.STOPPED
    assert result.wake.classification.value == "SESSION_NOT_ADMITTED"
    assert result.wake.admissions[-1].as_of == late
    assert h.quote_clock_calls == 1
    assert h.operator_calls == 0


def test_quote_return_after_freshness_deadline_stops_before_review(harness):
    h = harness
    h.quote_observed_at = AT + timedelta(seconds=61)
    h.quote_source_at = AT
    admit(h)
    result = run(h)
    assert result.wake.final_state is State.STOPPED
    assert h.quote_clock_calls == 1
    assert h.operator_calls == 0


@pytest.mark.parametrize("side", list(OrderSide))
@pytest.mark.parametrize("outcome", list(RiskOutcome))
def test_exact_risk_intent_and_synthetic_result(harness, side, outcome):
    h = harness
    if side is OrderSide.SELL:
        prior_at = AT - timedelta(minutes=2)
        seed = ReviewPaperIntent(
            UUID(int=90),
            UUID(int=91),
            SPY,
            OrderSide.BUY,
            Decimal("5"),
            Decimal("5"),
            RiskOutcome.APPROVED,
            (),
            "seed",
            None,
            OrderType.MARKET,
            TimeInForce.DAY,
            prior_at,
        )
        h.paper_store.record_market_review(
            seed,
            parse_review_equity_order_response(
                review("buy", "5", prior_at), received_at=prior_at
            ),
        )
    quantity = Decimal("50") if outcome is RiskOutcome.RESIZED else Decimal("1")
    h.activation = replace(
        h.activation,
        proposal=replace(h.activation.proposal, side=side, desired_quantity=quantity),
        new_trading_enabled=outcome is not RiskOutcome.REJECTED,
        risk_limits=RiskLimits(allow_selling=outcome is not RiskOutcome.REJECTED),
    )
    admit(h)
    result = run(h)
    assert result.wake.risk_outcome is outcome
    assert result.wake.quote_attempts == 1
    assert h.oauth_reads == 1
    if outcome is RiskOutcome.REJECTED:
        assert result.wake.final_state is State.STOPPED
        assert h.operator_calls == result.wake.effect_attempts == 0
        assert [c[0] for c in h.calls] == ["get_equity_quotes"]
    else:
        assert result.wake.final_state is State.COMPLETED
        assert result.wake.transitions == (
            State.READY,
            State.PREPARE_STARTED,
            State.PREPARED,
            State.REVIEW_STARTED,
            State.COMPLETED,
        )
        assert h.operator_calls == result.wake.effect_attempts == 1
        assert [c[0] for c in h.calls] == [
            "get_equity_quotes",
            "get_accounts",
            "get_equity_orders",
            "review_equity_order",
            "get_equity_orders",
        ]
        evidence = result.operator_evidence
        assert evidence.status == "PASS"
        assert (
            evidence.placement_calls,
            evidence.cancellation_calls,
            evidence.options_mutation_calls,
            evidence.crypto_mutation_calls,
        ) == (0, 0, 0, 0)
        assert (
            result.operator_evidence_sha256
            == hashlib.sha256(h.binding.evidence_path.read_bytes()).hexdigest()
        )
        assert SECRET not in repr(result)
        assert result.paper_trade_id == review_paper_trade_id(
            h.activation.local_order_id
        )
        assert result.fill_id == review_paper_fill_id(h.activation.local_order_id)
        record = h.paper_store.get_by_order_id(h.activation.local_order_id)
        assert record.intent == h.intent
        before = h.paper_store.path.read_bytes()
        assert (
            h.paper_store.record_market_review(
                record.intent,
                record.review,
                slippage_basis_points=h.activation.slippage_basis_points,
                commission=h.activation.commission,
            )
            == record
        )
        assert h.paper_store.path.read_bytes() == before
    replay_is_inert(h)


@pytest.mark.parametrize("failure", ["oauth", "missing_oauth", "get_equity_quotes"])
def test_provider_failure_before_operator_stops(harness, failure):
    h = harness
    h.failure = failure
    admit(h)
    result = run(h)
    assert result.wake.final_state is State.STOPPED
    assert result.wake.effect_attempts == h.operator_calls == 0
    assert sum(c[0] == "get_equity_quotes" for c in h.calls) <= 1
    assert not h.paper_store.history()
    replay_is_inert(h)


@pytest.mark.parametrize(
    "fault",
    [
        "exception",
        "process",
        "post_commit_exception",
        "missing_evidence",
        "malformed",
        "alternate_order",
        "alternate_quantity",
        "alternate_commission",
        "alternate_slippage",
        {"status": "FAIL"},
        {"source_head": "d" * 40},
        {"quantity": "2"},
        {"replay": True},
        {"review_equity_order_calls": 2},
        {"get_equity_quotes_calls": 1},
        {"interactive_reauth_count": 1},
        {"placement_calls": 1},
        {"cancellation_calls": 1},
        {"options_mutation_calls": 1},
        {"crypto_mutation_calls": 1},
        {"placement_calls": False},
        {"paper_record_count": 2},
        {"review_echo_validated": False},
        {"disclosure_present": False},
        {"get_accounts_calls": True},
    ],
)
def test_post_invocation_ambiguity_never_acknowledges(harness, fault):
    h = harness
    h.fault = fault
    admit(h)
    result = run(h)
    assert result.wake.final_state is State.INDETERMINATE
    assert result.wake.effect_attempts == h.operator_calls == 1
    assert result.operator_evidence is result.paper_trade_id is result.fill_id is None
    assert sum(c[0] == "review_equity_order" for c in h.calls) <= 1
    assert SECRET not in repr(result)
    replay_is_inert(h)


@pytest.mark.parametrize(
    "failure", ["get_accounts", "get_equity_orders", "review_equity_order"]
)
def test_operator_fail_is_indeterminate(harness, failure):
    h = harness
    h.failure = failure
    admit(h)
    result = run(h)
    assert result.wake.final_state is State.INDETERMINATE
    assert h.operator_calls == 1
    assert not h.paper_store.history()
    replay_is_inert(h)


@pytest.mark.parametrize(
    "state", [State.PREPARE_STARTED, State.PREPARED, State.REVIEW_STARTED]
)
def test_restart_has_zero_edges(harness, state):
    h = harness
    admit(h)
    current = h.state_store.snapshot().current(h.activation)
    for next_state in (State.PREPARE_STARTED, State.PREPARED, State.REVIEW_STARTED):
        current = h.state_store.transition(current, state=next_state, at=AT)
        if next_state is state:
            break
    replay_is_inert(h)
    assert not h.calls and h.oauth_reads == h.operator_calls == 0


@pytest.mark.parametrize(
    "change",
    [
        {"source_head": "d" * 40},
        {"source_tree": "d" * 40},
        {"deployment_identity": "d" * 64},
        {"oauth_valid_until": AT},
    ],
)
def test_explicit_binding_failure_is_pre_effect(harness, change):
    h = harness
    h.binding = replace(h.binding, **change)
    admit(h)
    assert run(h).wake.final_state is State.STOPPED
    assert not h.calls and h.oauth_reads == h.operator_calls == 0


def test_source_admission_failure_precedes_oauth_quote(harness, monkeypatch):
    h = harness

    def fail(*args):
        raise operator.RobinhoodPaperOperatorError("source identity mismatch")

    monkeypatch.setattr(operator, "_admit_source", fail)
    admit(h)
    assert run(h).wake.final_state is State.STOPPED
    assert not h.calls and h.oauth_reads == h.operator_calls == 0


@pytest.mark.parametrize(
    "at", [AT - timedelta(hours=6), AT + timedelta(hours=6), AT + timedelta(days=1)]
)
def test_no_catchup_or_outside_session_acquisition(harness, at):
    h = harness
    h.instants = OneWakeInstants(at, at, at)
    h.activation = replace(
        h.activation,
        created_at=AT - timedelta(days=1),
        proposal=replace(h.activation.proposal, created_at=AT - timedelta(days=1)),
    )
    admit(h)
    assert run(h).wake.final_state is State.STOPPED
    assert not h.calls and h.oauth_reads == h.operator_calls == 0


@pytest.mark.parametrize("status", [200, 401, 403])
def test_persisted_auth_single_http_attempt_no_refresh(harness, status):
    factory = module._persisted_auth_factory(harness.oauth_storage)
    auth = factory()
    request = SimpleNamespace(headers={})
    flow = auth.auth_flow(request)
    assert next(flow) is request
    assert request.headers["Authorization"] == "Bearer " + SECRET
    with pytest.raises(
        StopIteration if status == 200 else module.UnattendedExecutionError
    ):
        flow.send(SimpleNamespace(status_code=status))
    assert harness.oauth_reads == 1
    assert SECRET not in repr(auth)


def test_source_has_single_coordinator_operator_quote_and_no_host_surface():
    tree = ast.parse(Path(module.__file__).read_text())
    names = [
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    ]
    assert names.count("compose_one_review_paper_wake") == 1
    assert names.count("run_robinhood_paper_operator") == 1
    assert names.count("build_review_paper_intent") == 1
    assert not any(isinstance(n, (ast.While, ast.AsyncFor)) for n in ast.walk(tree))
    assert not any(
        isinstance(n, ast.Attribute)
        and n.attr in {"sleep", "now", "transition", "getenv", "refresh_token"}
        for n in ast.walk(tree)
    )


@pytest.mark.parametrize("symbols", [(), (SPY, SPY), (Symbol("QQQ"),)])
def test_required_symbols_fail_before_oauth_or_provider(harness, symbols):
    h = harness
    edges = module._ExecutionEdges(
        h.activation, h.state_store, h.paper_store, h.binding, h.oauth_storage
    )
    with pytest.raises(module.UnattendedExecutionError):
        edges.prepare_quote(activation=h.activation, required_symbols=symbols, as_of=AT)
    assert not h.calls and h.oauth_reads == h.operator_calls == 0


def test_quote_budget_never_reacquires(harness):
    h = harness
    admit(h)
    current = h.state_store.snapshot().current(h.activation)
    h.state_store.transition(current, state=State.PREPARE_STARTED, at=AT)
    edges = module._ExecutionEdges(
        h.activation, h.state_store, h.paper_store, h.binding, h.oauth_storage
    )
    edges.prepare_quote(activation=h.activation, required_symbols=(SPY,), as_of=AT)
    with pytest.raises(module.UnattendedExecutionError, match="budget consumed"):
        edges.prepare_quote(activation=h.activation, required_symbols=(SPY,), as_of=AT)
    assert h.oauth_reads == len(h.calls) == 1


@pytest.mark.parametrize("failed_state", [State.REVIEW_STARTED, State.COMPLETED])
def test_failed_durable_fence_never_grants_retry(harness, monkeypatch, failed_state):
    h = harness
    admit(h)
    original = UnattendedStateStore.transition

    def fail(self, expected, *, state, at):
        if state is failed_state:
            raise RuntimeError(SECRET)
        return original(self, expected, state=state, at=at)

    monkeypatch.setattr(UnattendedStateStore, "transition", fail)
    with pytest.raises(OneWakeStateError, match="reconciliation required"):
        run(h)
    assert h.operator_calls == (0 if failed_state is State.REVIEW_STARTED else 1)
    assert h.state_store.snapshot().current(h.activation).wake.state is (
        State.PREPARED if failed_state is State.REVIEW_STARTED else State.REVIEW_STARTED
    )
    replay_is_inert(h)
