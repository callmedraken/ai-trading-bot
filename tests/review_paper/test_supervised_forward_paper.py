"""131-Q source certification: fake acquisition/pipeline, no provider or writes."""

import ast
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

import trading_bot.review_paper.supervised_forward_paper as module
from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce, TradeProposal
from trading_bot.execution.models import ExecutionInstruction
from trading_bot.review_paper.forward_preview import ReviewPaperForwardPreview
from trading_bot.review_paper.intent_bridge import build_review_paper_intent
from trading_bot.review_paper.risk_prices import (
    ReviewPaperRiskPriceMark,
    ReviewPaperRiskPriceSnapshot,
)
from trading_bot.review_paper.session_admission import (
    ReviewPaperSessionSchedule,
    ReviewPaperSessionStatus,
    admit_review_paper_session,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.supervised_forward_paper import (
    ReviewPaperSupervisedPreparationStatus as Status,
)
from trading_bot.review_paper.supervised_forward_paper import (
    execute_review_paper_supervised_cycle as execute,
)
from trading_bot.review_paper.supervised_forward_paper import (
    prepare_review_paper_supervised_cycle as prepare,
)
from trading_bot.risk.manager import RiskManager
from trading_bot.risk.models import RiskContext, RiskLimits, RiskOutcome
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.robinhood_paper_operator import RobinhoodPaperOperatorEvidence
from trading_bot.robinhood_paper_pipeline import (
    RobinhoodDeterministicPaperPipelineResult,
)

AT = datetime(2026, 10, 2, 16, tzinfo=UTC)
AGE = timedelta(minutes=1)
SPY = Symbol("SPY")
SCHEDULE = ReviewPaperSessionSchedule(
    AT.date(),
    AT.replace(hour=13, minute=30),
    AT.replace(hour=20),
)
BUFFER = timedelta(minutes=5)
BLOCKED = [
    (ReviewPaperSessionStatus.NON_SESSION_DATE, AT + timedelta(days=1)),
    (ReviewPaperSessionStatus.BEFORE_REGULAR_WINDOW, AT.replace(hour=13)),
    (ReviewPaperSessionStatus.OPENING_BUFFER, SCHEDULE.opens_at),
    (ReviewPaperSessionStatus.CLOSING_BUFFER, SCHEDULE.closes_at - BUFFER),
    (ReviewPaperSessionStatus.AFTER_REGULAR_WINDOW, SCHEDULE.closes_at),
]


def _preview(inputs, snapshot):
    context = RiskContext(
        cash=Decimal("10000"),
        equity=Decimal("10000"),
        positions={},
        current_price=Decimal("100"),
        total_market_exposure=Decimal("0"),
        new_trading_enabled=inputs["new_trading_enabled"],
        as_of=snapshot.observed_at,
    )
    return ReviewPaperForwardPreview(
        inputs["proposal"],
        snapshot,
        inputs["risk_limits"],
        context,
        RiskManager(inputs["risk_limits"]).evaluate(inputs["proposal"], context),
    )


def _pipeline(preparation, instruction, status="PASS"):
    decision = preparation.preview.risk_decision
    evidence = RobinhoodPaperOperatorEvidence(
        source_head="a" * 40,
        source_tree="b" * 40,
        status=status,
        phase="complete",
        symbol="SPY",
        side="buy",
        quantity="1",
        order_type="market",
        get_accounts_calls=1,
        get_equity_orders_calls=2,
        review_equity_order_calls=1,
        get_equity_quotes_calls=0,
        baseline_order_pages=1,
        post_review_order_pages=1,
        paper_record_count=1,
        replay=False,
        review_echo_validated=True,
        quote_fill_validated=True,
        disclosure_present=True,
        interactive_reauth_count=0,
    )
    return RobinhoodDeterministicPaperPipelineResult(
        decision,
        build_review_paper_intent(decision, instruction, order_id=UUID(int=2)),
        evidence,
    )


@pytest.fixture
def harness(monkeypatch, tmp_path):
    events = []
    # Exact domain boundary objects without constructing a database or transport.
    store = object.__new__(ReviewPaperStore)
    adapter = object.__new__(RobinhoodReviewReadAdapter)
    inputs = dict(
        store=store,
        proposal=TradeProposal(
            UUID(int=1), SPY, OrderSide.BUY, Decimal("1"), AT, "test"
        ),
        schedule=SCHEDULE,
        opening_buffer=BUFFER,
        closing_buffer=BUFFER,
        adapter=adapter,
        max_quote_age=AGE,
        risk_limits=RiskLimits(),
        new_trading_enabled=True,
    )
    snapshot = ReviewPaperRiskPriceSnapshot(
        AT,
        (ReviewPaperRiskPriceMark(SPY, Decimal("100"), AT),),
    )
    h = SimpleNamespace(
        inputs=inputs,
        snapshot=snapshot,
        at=AT,
        events=events,
        history=(),
        admissions=[],
        previews=[],
    )

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "provider or durable mutation invoked during certification"
        )

    for name in (
        "record_market_review",
        "_initialize",
        "_connect",
        "reconstruct_ledger",
        "create_account_snapshot",
    ):
        monkeypatch.setattr(ReviewPaperStore, name, forbidden)
    for name in ("equity_quotes", "review_equity_order", "get_equity_orders"):
        if hasattr(RobinhoodReviewReadAdapter, name):
            monkeypatch.setattr(RobinhoodReviewReadAdapter, name, forbidden)

    def now(zone):
        assert zone is UTC
        events.append("clock")
        return h.at

    h.clock = Mock(side_effect=now)
    monkeypatch.setattr(module, "datetime", SimpleNamespace(now=h.clock))

    def admission(**kwargs):
        events.append("admission")
        result = admit_review_paper_session(**kwargs)
        h.admissions.append(result)
        return result

    def history():
        events.append("history")
        return h.history

    def acquire(**kwargs):
        events.append("P")
        return h.snapshot

    def preview(**kwargs):
        events.append("O")
        result = _preview(h.inputs, h.snapshot)
        h.previews.append(result)
        return result

    h.admit = Mock(side_effect=admission)
    h.read_history = Mock(side_effect=history)
    h.acquire = Mock(side_effect=acquire)
    h.preview = Mock(side_effect=preview)
    h.pipeline = Mock(side_effect=forbidden)
    monkeypatch.setattr(module, "admit_review_paper_session", h.admit)
    monkeypatch.setattr(ReviewPaperStore, "history", h.read_history)
    monkeypatch.setattr(module, "acquire_review_paper_risk_price_snapshot", h.acquire)
    monkeypatch.setattr(module, "build_review_paper_forward_preview", h.preview)
    monkeypatch.setattr(module, "run_robinhood_forward_paper_cycle", h.pipeline)
    h.config = dict(
        instruction=ExecutionInstruction(OrderType.MARKET, TimeInForce.DAY, AT),
        order_id=UUID(int=2),
        expected_branch="feature/robinhood-review-paper-side-foundation",
        expected_head="a" * 40,
        expected_tree="b" * 40,
        evidence_path=tmp_path / "evidence.json",
        redirect_uri="http://127.0.0.1:8765/callback",
        slippage_basis_points=Decimal("1.25"),
        commission=Decimal("0.1"),
    )
    return h


def _ready(h):
    preparation = prepare(**h.inputs)
    h.events.clear()
    for mock in (h.clock, h.admit, h.read_history, h.acquire, h.preview, h.pipeline):
        mock.reset_mock()
    pipeline = _pipeline(preparation, h.config["instruction"])

    def effect(**kwargs):
        h.events.append("L")
        return pipeline

    h.pipeline.side_effect = effect
    return preparation, pipeline


def test_prepare_order_exact_calls_and_preserved_objects(harness):
    h = harness
    result = prepare(**h.inputs)
    assert h.events == [
        "clock",
        "admission",
        "history",
        "P",
        "admission",
        "O",
        "history",
    ]
    h.clock.assert_called_once_with(UTC)
    assert h.read_history.call_count == 2
    assert all(call.args == () for call in h.read_history.call_args_list)
    h.acquire.assert_called_once_with(
        **{
            key: h.inputs[key]
            for key in ("store", "proposal", "adapter", "max_quote_age")
        }
    )
    h.preview.assert_called_once_with(
        store=h.inputs["store"],
        proposal=h.inputs["proposal"],
        price_snapshot=h.snapshot,
        risk_limits=h.inputs["risk_limits"],
        new_trading_enabled=True,
    )
    assert h.admit.call_count == 2
    for call, instant in zip(
        h.admit.call_args_list, (AT, h.snapshot.observed_at), strict=True
    ):
        assert call.kwargs == dict(
            schedule=SCHEDULE,
            as_of=instant,
            opening_buffer=BUFFER,
            closing_buffer=BUFFER,
        )
    for name in (
        "store",
        "proposal",
        "schedule",
        "opening_buffer",
        "closing_buffer",
        "max_quote_age",
        "risk_limits",
        "new_trading_enabled",
    ):
        assert getattr(result, name) is h.inputs[name]
    assert result.price_snapshot is h.snapshot
    assert result.initial_admission is h.admissions[0]
    assert result.quote_admission is h.admissions[1]
    assert result.preview is h.previews[0]
    assert result.durable_history is h.history
    assert result.initial_admission is not result.quote_admission
    assert result.status is Status.READY_TO_PROCEED
    assert result.quote_valid_until == AT + AGE
    h.pipeline.assert_not_called()


@pytest.mark.parametrize("status,at", BLOCKED)
def test_prepare_each_initial_blocked_status(harness, status, at):
    h = harness
    h.at = at
    result = prepare(**h.inputs)
    assert result.status is Status.SESSION_NOT_ADMITTED
    assert result.initial_admission.status is status
    assert h.events == ["clock", "admission"]
    h.acquire.assert_not_called()
    h.preview.assert_not_called()
    h.pipeline.assert_not_called()
    h.read_history.assert_not_called()
    assert all(
        getattr(result, name) is None
        for name in (
            "price_snapshot",
            "quote_admission",
            "preview",
            "durable_history",
            "quote_valid_until",
        )
    )


@pytest.mark.parametrize("status,at", BLOCKED)
def test_prepare_quote_time_blocked(harness, status, at):
    h = harness
    h.snapshot = ReviewPaperRiskPriceSnapshot(
        at, (ReviewPaperRiskPriceMark(SPY, Decimal("100"), at),)
    )
    result = prepare(**h.inputs)
    assert result.status is Status.SESSION_EXPIRED_DURING_ACQUISITION
    assert result.price_snapshot is h.snapshot
    assert result.quote_admission.status is status
    assert result.quote_admission.as_of == at
    assert result.preview is result.durable_history is result.quote_valid_until is None
    assert h.events == ["clock", "admission", "history", "P", "admission"]
    h.preview.assert_not_called()
    h.pipeline.assert_not_called()
    assert h.read_history.call_count == 1


@pytest.mark.parametrize(
    "name",
    [
        "store",
        "proposal",
        "schedule",
        "opening_buffer",
        "closing_buffer",
        "adapter",
        "max_quote_age",
        "risk_limits",
        "new_trading_enabled",
    ],
)
@pytest.mark.parametrize("subclass", [False, True])
def test_prepare_exact_type_admission(harness, name, subclass):
    h = harness
    value = h.inputs[name]
    bad = object()
    if subclass and type(value) is not bool:
        child = type("Child", (type(value),), {})
        if type(value) is timedelta:
            bad = child(seconds=value.total_seconds())
        elif hasattr(value, "__dataclass_fields__"):
            bad = child(
                **{field.name: getattr(value, field.name) for field in fields(value)}
            )
        else:
            bad = object.__new__(child)
    with pytest.raises(TypeError, match=name):
        prepare(**{**h.inputs, name: bad})
    assert h.events == []
    h.acquire.assert_not_called()
    h.pipeline.assert_not_called()


@pytest.mark.parametrize(
    "name,value",
    [
        ("max_quote_age", timedelta(0)),
        ("max_quote_age", -AGE),
        ("opening_buffer", -BUFFER),
        ("closing_buffer", -BUFFER),
        ("opening_buffer", timedelta(days=1)),
        ("closing_buffer", timedelta(days=1)),
    ],
)
def test_prepare_invalid_durations_before_access(harness, name, value):
    with pytest.raises(ValueError):
        prepare(**{**harness.inputs, name: value})
    assert harness.events == []


@pytest.mark.parametrize(
    "quantity,enabled,outcome,status",
    [
        ("1", True, RiskOutcome.APPROVED, Status.READY_TO_PROCEED),
        ("30", True, RiskOutcome.RESIZED, Status.READY_TO_PROCEED),
        ("1", False, RiskOutcome.REJECTED, Status.RISK_REJECTED),
    ],
)
def test_prepare_risk_outcomes(harness, quantity, enabled, outcome, status):
    h = harness
    h.inputs["proposal"] = replace(
        h.inputs["proposal"], desired_quantity=Decimal(quantity)
    )
    h.inputs["new_trading_enabled"] = enabled
    result = prepare(**h.inputs)
    assert result.status is status
    assert result.preview.risk_decision.outcome is outcome
    assert result.durable_history is h.history
    assert result.quote_valid_until == AT + AGE
    h.pipeline.assert_not_called()


def test_prepare_history_drift_no_retry(harness):
    h = harness
    h.read_history.side_effect = [(), (object(),)]
    with pytest.raises(RuntimeError, match="history changed"):
        prepare(**h.inputs)
    assert h.read_history.call_count == 2
    assert h.acquire.call_count == h.preview.call_count == 1
    h.pipeline.assert_not_called()


@pytest.mark.parametrize(
    "age", [timedelta(seconds=59), AGE, AGE + timedelta(microseconds=1)]
)
def test_prepare_earliest_deadline_and_freshness(harness, age):
    h = harness
    qqq = Symbol("QQQ")
    h.snapshot = ReviewPaperRiskPriceSnapshot(
        AT,
        (
            ReviewPaperRiskPriceMark(qqq, Decimal("100"), AT - age),
            ReviewPaperRiskPriceMark(SPY, Decimal("100"), AT),
        ),
    )
    context = RiskContext(
        Decimal("10000"), Decimal("10000"), {}, Decimal("100"), Decimal("0"), True, AT
    )
    # A second required symbol must be in the preview context.
    from trading_bot.domain import Position

    context = replace(
        context, positions={qqq: Position(qqq, Decimal("1"), Decimal("100"))}
    )
    preview = ReviewPaperForwardPreview(
        h.inputs["proposal"],
        h.snapshot,
        h.inputs["risk_limits"],
        context,
        RiskManager(h.inputs["risk_limits"]).evaluate(h.inputs["proposal"], context),
    )
    h.preview.side_effect = None
    h.preview.return_value = preview
    if age > AGE:
        with pytest.raises(ValueError, match="deadline"):
            prepare(**h.inputs)
    else:
        assert prepare(**h.inputs).quote_valid_until == AT - age + AGE
    h.pipeline.assert_not_called()


def test_prepare_deadline_overflow(harness):
    h = harness
    h.inputs["max_quote_age"] = timedelta.max
    with pytest.raises(OverflowError):
        prepare(**h.inputs)
    assert h.acquire.call_count == h.preview.call_count == 1
    h.pipeline.assert_not_called()


@pytest.mark.parametrize("boundary", ["admit", "read_history", "acquire", "preview"])
def test_prepare_failure_identity_and_no_retry(harness, boundary):
    h = harness
    error = RuntimeError("boundary failure")
    getattr(h, boundary).side_effect = error
    with pytest.raises(RuntimeError) as caught:
        prepare(**h.inputs)
    assert caught.value is error
    assert getattr(h, boundary).call_count == 1
    h.pipeline.assert_not_called()


@pytest.mark.parametrize("operator_status", ["PASS", "FAIL"])
def test_execute_order_exact_forwarding_and_result(harness, operator_status):
    h = harness
    preparation, _ = _ready(h)
    h.at = AT + timedelta(seconds=10)
    pipeline = _pipeline(preparation, h.config["instruction"], operator_status)
    h.pipeline.side_effect = lambda **kwargs: h.events.append("L") or pipeline
    result = execute(preparation=preparation, **h.config)
    assert h.events == ["clock", "admission", "O", "history", "L"]
    h.clock.assert_called_once_with(UTC)
    h.admit.assert_called_once_with(
        schedule=SCHEDULE, as_of=h.at, opening_buffer=BUFFER, closing_buffer=BUFFER
    )
    h.read_history.assert_called_once_with()
    h.preview.assert_called_once_with(
        store=preparation.store,
        proposal=preparation.proposal,
        price_snapshot=preparation.price_snapshot,
        risk_limits=preparation.risk_limits,
        new_trading_enabled=preparation.new_trading_enabled,
    )
    h.pipeline.assert_called_once_with(
        store=preparation.store,
        proposal=preparation.proposal,
        prices=preparation.price_snapshot.prices,
        as_of=preparation.price_snapshot.observed_at,
        new_trading_enabled=preparation.new_trading_enabled,
        risk_limits=preparation.risk_limits,
        review_received_at=h.at,
        **h.config,
    )
    args = h.pipeline.call_args.kwargs
    for name in ("store", "proposal", "risk_limits", "new_trading_enabled"):
        assert args[name] is getattr(preparation, name)
    for name, value in h.config.items():
        assert args[name] is value
    assert args["as_of"] is preparation.price_snapshot.observed_at
    assert args["review_received_at"] is h.at
    assert result.preparation is preparation
    assert result.pipeline_result is pipeline
    assert result.pipeline_result.operator_evidence is pipeline.operator_evidence
    assert result.execute_admission is h.admissions[-1]
    assert result.revalidated_preview is h.previews[-1]
    assert result.revalidated_preview == preparation.preview
    h.acquire.assert_not_called()
    assert not h.config["evidence_path"].exists()


@pytest.mark.parametrize(
    "status",
    [
        Status.SESSION_NOT_ADMITTED,
        Status.SESSION_EXPIRED_DURING_ACQUISITION,
        Status.RISK_REJECTED,
    ],
)
def test_execute_nonready_before_any_access(harness, status):
    h = harness
    if status is Status.SESSION_NOT_ADMITTED:
        h.at = BLOCKED[0][1]
    elif status is Status.SESSION_EXPIRED_DURING_ACQUISITION:
        h.snapshot = replace(h.snapshot, observed_at=SCHEDULE.closes_at)
    else:
        h.inputs["new_trading_enabled"] = False
    preparation = prepare(**h.inputs)
    assert preparation.status is status
    h.events.clear()
    with pytest.raises(ValueError, match="READY"):
        execute(preparation=preparation, **h.config)
    assert h.events == []
    h.pipeline.assert_not_called()


@pytest.mark.parametrize("name", ["preparation", "instruction", "order_id"])
@pytest.mark.parametrize("subclass", [False, True])
def test_execute_exact_types(harness, name, subclass):
    h = harness
    preparation, _ = _ready(h)
    inputs = dict(preparation=preparation, **h.config)
    value = inputs[name]
    bad = object()
    if subclass:
        child = type("Child", (type(value),), {})
        bad = (
            child(int=value.int)
            if name == "order_id"
            else child(**{f.name: getattr(value, f.name) for f in fields(value)})
        )
    with pytest.raises(TypeError, match=name):
        execute(**{**inputs, name: bad})
    assert h.events == []
    h.pipeline.assert_not_called()


@pytest.mark.parametrize("status,at", BLOCKED)
def test_execute_session_expired(harness, status, at):
    h = harness
    preparation, _ = _ready(h)
    h.at = at
    with pytest.raises(RuntimeError, match="session"):
        execute(preparation=preparation, **h.config)
    assert h.events == ["clock", "admission"]
    h.pipeline.assert_not_called()
    h.acquire.assert_not_called()


@pytest.mark.parametrize(
    "offset,valid", [(timedelta(0), True), (timedelta(microseconds=1), False)]
)
def test_execute_exact_quote_deadline(harness, offset, valid):
    h = harness
    preparation, _ = _ready(h)
    h.at = preparation.quote_valid_until + offset
    if valid:
        execute(preparation=preparation, **h.config)
        assert h.pipeline.call_count == 1
    else:
        with pytest.raises(RuntimeError, match="quote expired"):
            execute(preparation=preparation, **h.config)
        assert h.events == ["clock", "admission"]
        h.pipeline.assert_not_called()
    h.acquire.assert_not_called()


@pytest.mark.parametrize("drift", ["context", "decision", "history", "instruction"])
def test_execute_pre_effect_drift_stops(harness, drift):
    h = harness
    preparation, _ = _ready(h)
    if drift in {"context", "decision"}:
        preview = preparation.preview
        if drift == "context":
            preview = replace(
                preview,
                risk_context=replace(preview.risk_context, cash=Decimal("9999")),
            )
        else:
            preview = replace(
                preview,
                risk_decision=replace(
                    preview.risk_decision,
                    outcome=RiskOutcome.REJECTED,
                    approved_quantity=Decimal("0"),
                    reasons=RiskManager(RiskLimits(allow_buying=False))
                    .evaluate(preview.proposal, preview.risk_context)
                    .reasons,
                ),
            )
        h.preview.side_effect = None
        h.preview.return_value = preview
    elif drift == "history":
        h.history = (object(),)
    else:
        h.config["instruction"] = replace(
            h.config["instruction"], created_at=AT - timedelta(microseconds=1)
        )
    with pytest.raises((RuntimeError, ValueError)):
        execute(preparation=preparation, **h.config)
    assert h.preview.call_count == 1
    assert h.read_history.call_count == (0 if drift in {"context", "decision"} else 1)
    h.pipeline.assert_not_called()
    h.acquire.assert_not_called()


def test_execute_pipeline_mismatch_surfaces_without_retry(harness):
    h = harness
    preparation, _ = _ready(h)
    decision = RiskManager(RiskLimits(allow_buying=False)).evaluate(
        preparation.proposal, preparation.preview.risk_context
    )
    h.pipeline.side_effect = None
    h.pipeline.return_value = RobinhoodDeterministicPaperPipelineResult(
        decision, None, None
    )
    with pytest.raises(ValueError, match="pipeline risk decision"):
        execute(preparation=preparation, **h.config)
    assert h.pipeline.call_count == 1
    h.acquire.assert_not_called()


@pytest.mark.parametrize("boundary", ["admit", "preview", "read_history", "pipeline"])
def test_execute_exception_identity_and_no_retry(harness, boundary):
    h = harness
    preparation, _ = _ready(h)
    error = RuntimeError("explicit failure")
    getattr(h, boundary).side_effect = error
    with pytest.raises(RuntimeError) as caught:
        execute(preparation=preparation, **h.config)
    assert caught.value is error
    assert getattr(h, boundary).call_count == 1
    assert h.pipeline.call_count == (1 if boundary == "pipeline" else 0)
    h.acquire.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "READY_TO_PROCEED"),
        ("initial_admission", None),
        ("price_snapshot", None),
        ("quote_admission", None),
        ("preview", None),
        ("durable_history", None),
        ("durable_history", []),
        ("durable_history", (object(),)),
        ("quote_valid_until", None),
        ("quote_valid_until", AT.replace(tzinfo=None)),
        ("quote_valid_until", AT - timedelta(microseconds=1)),
        ("quote_valid_until", AT + AGE + timedelta(microseconds=1)),
        ("status", Status.RISK_REJECTED),
        ("status", Status.SESSION_NOT_ADMITTED),
        ("status", Status.SESSION_EXPIRED_DURING_ACQUISITION),
    ],
)
def test_preparation_direct_construction_invariants(harness, field, value):
    preparation, _ = _ready(harness)
    with pytest.raises((TypeError, ValueError)):
        replace(preparation, **{field: value})


@pytest.mark.parametrize(
    "status", [Status.SESSION_NOT_ADMITTED, Status.SESSION_EXPIRED_DURING_ACQUISITION]
)
@pytest.mark.parametrize("field", ["preview", "durable_history", "quote_valid_until"])
def test_blocked_results_cannot_carry_execution_state(harness, status, field):
    h = harness
    ready, _ = _ready(h)
    if status is Status.SESSION_NOT_ADMITTED:
        h.at = BLOCKED[0][1]
    else:
        h.snapshot = replace(h.snapshot, observed_at=SCHEDULE.closes_at)
    blocked = prepare(**h.inputs)
    with pytest.raises(ValueError):
        replace(blocked, **{field: getattr(ready, field)})


def test_direct_construction_preserves_preview_inputs_and_admissions(harness):
    preparation, _ = _ready(harness)
    for name in ("proposal", "risk_limits", "price_snapshot"):
        equal_copy = replace(getattr(preparation, name))
        with pytest.raises(ValueError, match="exact prepared"):
            replace(preparation, **{name: equal_copy})
    with pytest.raises(ValueError, match="exact prepared"):
        replace(preparation, new_trading_enabled=False)
    other_schedule = replace(
        SCHEDULE, opens_at=SCHEDULE.opens_at - timedelta(minutes=1)
    )
    with pytest.raises(ValueError, match="schedule"):
        replace(preparation, schedule=other_schedule)
    other_admission = admit_review_paper_session(
        schedule=SCHEDULE,
        as_of=AT + timedelta(seconds=1),
        opening_buffer=BUFFER,
        closing_buffer=BUFFER,
    )
    with pytest.raises(ValueError, match="observation"):
        replace(preparation, quote_admission=other_admission)
    offset_deadline = preparation.quote_valid_until.astimezone(
        timezone(timedelta(hours=2))
    )
    assert (
        replace(preparation, quote_valid_until=offset_deadline).quote_valid_until.tzinfo
        is UTC
    )


@pytest.mark.parametrize(
    "field",
    ["preparation", "execute_admission", "revalidated_preview", "pipeline_result"],
)
def test_execution_result_exact_types(harness, field):
    preparation, _ = _ready(harness)
    result = execute(preparation=preparation, **harness.config)
    with pytest.raises(TypeError):
        replace(result, **{field: object()})
    value = getattr(result, field)
    child = type("Child", (type(value),), {})
    subclass = child(**{f.name: getattr(value, f.name) for f in fields(value)})
    with pytest.raises(TypeError):
        replace(result, **{field: subclass})


def test_execution_result_direct_invariants(harness):
    h = harness
    preparation, _ = _ready(h)
    result = execute(preparation=preparation, **h.config)
    admission = admit_review_paper_session(
        schedule=SCHEDULE,
        as_of=SCHEDULE.closes_at,
        opening_buffer=BUFFER,
        closing_buffer=BUFFER,
    )
    with pytest.raises(ValueError, match="current session"):
        replace(result, execute_admission=admission)
    preview = replace(
        result.revalidated_preview,
        risk_context=replace(
            result.revalidated_preview.risk_context, cash=Decimal("9999")
        ),
    )
    with pytest.raises(ValueError, match="risk context/decision"):
        replace(result, revalidated_preview=preview)
    with pytest.raises(ValueError, match="exact prepared"):
        replace(
            result,
            revalidated_preview=replace(
                result.revalidated_preview, risk_limits=replace(preparation.risk_limits)
            ),
        )
    h.inputs["new_trading_enabled"] = False
    rejected = prepare(**h.inputs)
    with pytest.raises(ValueError, match="READY"):
        replace(result, preparation=rejected)


def test_results_frozen_slotted_and_status_enum(harness):
    h = harness
    preparation, _ = _ready(h)
    result = execute(preparation=preparation, **h.config)
    assert [member.value for member in Status] == [
        "SESSION_NOT_ADMITTED",
        "SESSION_EXPIRED_DURING_ACQUISITION",
        "RISK_REJECTED",
        "READY_TO_PROCEED",
    ]
    for value in (preparation, result):
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)


def test_structural_closed_authority_and_separate_effect_boundary():
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    expected_imports = {
        "__future__": {"annotations"},
        "dataclasses": {"dataclass"},
        "datetime": {"UTC", "datetime", "timedelta"},
        "decimal": {"Decimal"},
        "enum": {"StrEnum"},
        "pathlib": {"Path"},
        "uuid": {"UUID"},
        "trading_bot.domain": {"TradeProposal"},
        "trading_bot.execution.models": {"ExecutionInstruction"},
        "trading_bot.review_paper.forward_preview": {
            "ReviewPaperForwardPreview",
            "build_review_paper_forward_preview",
        },
        "trading_bot.review_paper.models": {"ReviewPaperRecord"},
        "trading_bot.review_paper.risk_price_acquisition": {
            "acquire_review_paper_risk_price_snapshot"
        },
        "trading_bot.review_paper.risk_prices": {"ReviewPaperRiskPriceSnapshot"},
        "trading_bot.review_paper.session_admission": {
            "ReviewPaperSessionAdmission",
            "ReviewPaperSessionSchedule",
            "ReviewPaperSessionStatus",
            "admit_review_paper_session",
        },
        "trading_bot.review_paper.store": {"ReviewPaperStore"},
        "trading_bot.risk.models": {"RiskLimits", "RiskOutcome"},
        "trading_bot.robinhood_forward_paper_cycle": {
            "run_robinhood_forward_paper_cycle"
        },
        "trading_bot.robinhood_mcp.adapter": {"RobinhoodReviewReadAdapter"},
        "trading_bot.robinhood_paper_pipeline": {
            "RobinhoodDeterministicPaperPipelineResult"
        },
    }
    imports = {}
    allowed_calls = {
        "dataclass",
        "type",
        "getattr",
        "TypeError",
        "ValueError",
        "RuntimeError",
        "timedelta",
        "min",
        "any",
        "dict",
        "object.__setattr__",
        "deadline.astimezone",
        "self.quote_valid_until.astimezone",
        "self.quote_valid_until.utcoffset",
        "_require_inputs",
        "_require_admission",
        "_require_preview",
        "_quote_deadline",
        "datetime.now",
        "admit_review_paper_session",
        "store.history",
        "preparation.store.history",
        "acquire_review_paper_risk_price_snapshot",
        "build_review_paper_forward_preview",
        "run_robinhood_forward_paper_cycle",
        "ReviewPaperSupervisedPreparation",
        "ReviewPaperSupervisedExecutionResult",
    }
    for node in ast.walk(tree):
        assert not isinstance(
            node, (ast.Import, ast.Try, ast.While, ast.With, ast.AsyncFunctionDef)
        )
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0 and all(alias.asname is None for alias in node.names)
            imports[node.module] = {alias.name for alias in node.names}
        if isinstance(node, ast.Call):
            assert ast.unparse(node.func) in allowed_calls
    assert imports == expected_imports
    for name, effects, admissions, histories in (
        ("prepare_review_paper_supervised_cycle", 0, 2, 2),
        ("execute_review_paper_supervised_cycle", 1, 1, 1),
    ):
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        assert (
            not function.args.args
            and not function.args.vararg
            and not function.args.kwarg
        )
        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
        names = [ast.unparse(node.func) for node in calls]
        assert names.count("run_robinhood_forward_paper_cycle") == effects
        if effects == 0:
            assert not any(
                isinstance(node, ast.Name)
                and node.id == "run_robinhood_forward_paper_cycle"
                for node in ast.walk(function)
            )
            assert names.count("acquire_review_paper_risk_price_snapshot") == 1
        else:
            assert "acquire_review_paper_risk_price_snapshot" not in names
        assert names.count("datetime.now") == 1
        clock = next(node for node in calls if ast.unparse(node.func) == "datetime.now")
        assert ast.dump(clock) == ast.dump(
            ast.parse("datetime.now(UTC)", mode="eval").body
        )
        assert names.count("admit_review_paper_session") == admissions
        assert names.count("build_review_paper_forward_preview") == 1
        assert (
            names.count("store.history") + names.count("preparation.store.history")
            == histories
        )


def test_prepare_quote_admission_uses_distinct_observation(harness):
    h = harness
    observed = AT + timedelta(seconds=2)
    h.snapshot = ReviewPaperRiskPriceSnapshot(
        observed, (ReviewPaperRiskPriceMark(SPY, Decimal("100"), AT),)
    )
    result = prepare(**h.inputs)
    assert result.initial_admission.as_of == AT
    assert result.quote_admission.as_of is h.snapshot.observed_at
    assert result.quote_admission.as_of == observed
    assert result.preview.risk_decision.evaluated_at == observed
    assert result.quote_valid_until == AT + AGE
    h.clock.assert_called_once_with(UTC)


def test_execute_forwards_exact_snapshot_price_mapping(harness, monkeypatch):
    h = harness
    prices = h.snapshot.prices
    monkeypatch.setattr(
        ReviewPaperRiskPriceSnapshot, "prices", property(lambda self: prices)
    )
    preparation, _ = _ready(h)
    execute(preparation=preparation, **h.config)
    assert h.pipeline.call_args.kwargs["prices"] is prices


@pytest.mark.parametrize(
    "field", ["initial_admission", "quote_admission", "price_snapshot", "preview"]
)
def test_preparation_rejects_optional_domain_subclasses(harness, field):
    preparation, _ = _ready(harness)
    value = getattr(preparation, field)
    child = type("Child", (type(value),), {})
    subclass = child(**{f.name: getattr(value, f.name) for f in fields(value)})
    with pytest.raises(TypeError):
        replace(preparation, **{field: subclass})


def test_preparation_rejects_inconsistent_initial_and_quote_admissions(harness):
    h = harness
    preparation, _ = _ready(h)
    blocked = admit_review_paper_session(
        schedule=SCHEDULE,
        as_of=SCHEDULE.closes_at,
        opening_buffer=BUFFER,
        closing_buffer=BUFFER,
    )
    with pytest.raises(ValueError, match="initial admission"):
        replace(preparation, initial_admission=blocked)
    snapshot = replace(h.snapshot, observed_at=SCHEDULE.closes_at)
    expired = replace(
        preparation,
        status=Status.SESSION_EXPIRED_DURING_ACQUISITION,
        price_snapshot=snapshot,
        quote_admission=blocked,
        preview=None,
        durable_history=None,
        quote_valid_until=None,
    )
    with pytest.raises(ValueError, match="quote-time admission"):
        replace(expired, status=Status.READY_TO_PROCEED)
    with pytest.raises(ValueError):
        replace(
            preparation,
            status=Status.SESSION_EXPIRED_DURING_ACQUISITION,
            preview=None,
            durable_history=None,
            quote_valid_until=None,
        )
    with pytest.raises(ValueError, match="no acquired state"):
        replace(
            preparation,
            status=Status.SESSION_NOT_ADMITTED,
            price_snapshot=None,
            quote_admission=None,
            preview=None,
            durable_history=None,
            quote_valid_until=None,
        )
    blocked_result = replace(
        preparation,
        status=Status.SESSION_NOT_ADMITTED,
        initial_admission=blocked,
        price_snapshot=None,
        quote_admission=None,
        preview=None,
        durable_history=None,
        quote_valid_until=None,
    )
    for field, value in (
        ("price_snapshot", h.snapshot),
        ("quote_admission", preparation.quote_admission),
    ):
        with pytest.raises(ValueError, match="no acquired state"):
            replace(blocked_result, **{field: value})


def test_direct_execution_result_detects_risk_decision_and_expiry(harness):
    h = harness
    preparation, _ = _ready(h)
    result = execute(preparation=preparation, **h.config)
    late = admit_review_paper_session(
        schedule=SCHEDULE,
        as_of=preparation.quote_valid_until + timedelta(microseconds=1),
        opening_buffer=BUFFER,
        closing_buffer=BUFFER,
    )
    with pytest.raises(ValueError, match="quote validity"):
        replace(result, execute_admission=late)
    rejected = RiskManager(RiskLimits(allow_buying=False)).evaluate(
        preparation.proposal,
        preparation.preview.risk_context,
    )
    with pytest.raises(ValueError, match="risk context/decision"):
        replace(
            result,
            revalidated_preview=replace(
                result.revalidated_preview, risk_decision=rejected
            ),
        )
    with pytest.raises(ValueError, match="pipeline risk decision"):
        replace(
            result,
            pipeline_result=RobinhoodDeterministicPaperPipelineResult(
                rejected, None, None
            ),
        )


def test_nonempty_durable_history_preserved_and_equal_reads_admitted(harness):
    from trading_bot.review_paper.models import (
        ReviewPaperRecord,
        RobinhoodEquityOrderReview,
        RobinhoodReviewQuote,
        review_paper_fill_id,
        review_paper_trade_id,
    )

    h = harness
    preview = _preview(h.inputs, h.snapshot)
    intent = build_review_paper_intent(
        preview.risk_decision,
        h.config["instruction"],
        order_id=h.config["order_id"],
    )
    price = Decimal("100")
    quote = RobinhoodReviewQuote(
        symbol=SPY,
        adjusted_previous_close=price,
        ask_price=price,
        bid_price=price,
        has_traded=True,
        last_non_reg_trade_price=None,
        last_trade_price=price,
        previous_close=price,
        previous_close_date=None,
        state="active",
        venue_ask_time=AT,
        venue_bid_time=AT,
        venue_last_non_reg_trade_time=None,
        venue_last_trade_time=AT,
    )
    review = RobinhoodEquityOrderReview(
        symbol=SPY,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=intent.approved_quantity,
        quote=quote,
        order_checks_json="{}",
        reviewed_at=AT,
        market_data_disclosure="fake review",
    )
    record = ReviewPaperRecord(
        review_paper_trade_id(intent.order_id),
        intent,
        review,
        review_paper_fill_id(intent.order_id),
        price,
        Decimal("0"),
        Decimal("0"),
        AT,
    )
    before = (record,)
    after = (replace(record),)
    assert before == after and before is not after
    h.read_history.side_effect = [before, after]
    preparation = prepare(**h.inputs)
    assert preparation.durable_history is before
    assert preparation.durable_history[0] is record
    h.read_history.side_effect = None
    h.read_history.return_value = after
    pipeline = _pipeline(preparation, h.config["instruction"])
    h.pipeline.side_effect = None
    h.pipeline.return_value = pipeline
    assert execute(preparation=preparation, **h.config).pipeline_result is pipeline
    h.read_history.return_value = (replace(record, commission=Decimal("1")),)
    h.pipeline.reset_mock()
    with pytest.raises(RuntimeError, match="history changed"):
        execute(preparation=preparation, **h.config)
    h.pipeline.assert_not_called()
