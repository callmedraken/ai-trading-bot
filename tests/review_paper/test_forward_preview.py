"""Architecture 131-O immutable risk-only preview and closed composition."""

import ast
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, Inexact, Rounded, localcontext
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest

import trading_bot.review_paper.forward_preview as module
from trading_bot.domain import (
    OrderSide,
    OrderType,
    Position,
    Symbol,
    TimeInForce,
    TradeProposal,
)
from trading_bot.review_paper.forward_preview import (
    ReviewPaperForwardPreview,
    build_review_paper_forward_preview,
)
from trading_bot.review_paper.models import (
    ReviewPaperIntent,
    RobinhoodEquityOrderReview,
    RobinhoodReviewQuote,
)
from trading_bot.review_paper.risk_prices import (
    ReviewPaperRiskPriceMark,
    ReviewPaperRiskPriceSnapshot,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.risk.models import RiskContext, RiskDecision, RiskLimits, RiskOutcome

AT = datetime(2026, 10, 3, 16, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def _proposal(side=OrderSide.BUY, quantity="1", symbol=SPY):
    return TradeProposal(UUID(int=1), symbol, side, Decimal(quantity), AT, "preview")


def _snapshot(prices=None, observed_at=AT):
    prices = {SPY: Decimal("100")} if prices is None else prices
    return ReviewPaperRiskPriceSnapshot(
        observed_at,
        tuple(
            ReviewPaperRiskPriceMark(symbol, prices[symbol], observed_at)
            for symbol in sorted(prices, key=str)
        ),
    )


@pytest.fixture
def store(tmp_path):
    return ReviewPaperStore(tmp_path / "paper.sqlite", starting_cash=Decimal("10000"))


def _seed(store, symbol=SPY):
    """Create durable fixture history before invoking the effect-free preview."""
    at = AT - timedelta(minutes=1)
    quantity = Decimal("5")
    price = Decimal("100")
    intent = ReviewPaperIntent(
        proposal_id=UUID(int=2),
        order_id=UUID(int=3),
        symbol=symbol,
        side=OrderSide.BUY,
        desired_quantity=quantity,
        approved_quantity=quantity,
        risk_outcome=RiskOutcome.APPROVED,
        risk_reason_codes=(),
        proposal_reason="fixture buy",
        proposal_confidence=None,
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        proposed_at=at,
    )
    quote = RobinhoodReviewQuote(
        symbol=symbol,
        adjusted_previous_close=price,
        ask_price=price,
        bid_price=price,
        has_traded=True,
        last_non_reg_trade_price=None,
        last_trade_price=price,
        previous_close=price,
        previous_close_date=None,
        state="active",
        venue_ask_time=at,
        venue_bid_time=at,
        venue_last_non_reg_trade_time=None,
        venue_last_trade_time=at,
    )
    review = RobinhoodEquityOrderReview(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=quantity,
        quote=quote,
        order_checks_json="{}",
        reviewed_at=at,
        market_data_disclosure="fixture",
    )
    store.record_market_review(intent, review)


def _build(store, **changes):
    return build_review_paper_forward_preview(
        **{
            "store": store,
            "proposal": _proposal(),
            "price_snapshot": _snapshot(),
            "risk_limits": RiskLimits(),
            "new_trading_enabled": True,
            **changes,
        }
    )


@pytest.mark.parametrize(
    "owned,side,desired,limits,enabled,outcome,approved,projected",
    [
        (False, OrderSide.BUY, "1", RiskLimits(), True, RiskOutcome.APPROVED, "1", "1"),
        (True, OrderSide.BUY, "2", RiskLimits(), True, RiskOutcome.APPROVED, "2", "7"),
        (
            True,
            OrderSide.BUY,
            "30",
            RiskLimits(),
            True,
            RiskOutcome.RESIZED,
            "15",
            "20",
        ),
        (
            False,
            OrderSide.BUY,
            "1",
            RiskLimits(allow_buying=False),
            True,
            RiskOutcome.REJECTED,
            "0",
            "0",
        ),
        (
            True,
            OrderSide.BUY,
            "1",
            RiskLimits(allow_buying=False),
            True,
            RiskOutcome.REJECTED,
            "0",
            "5",
        ),
        (True, OrderSide.SELL, "2", RiskLimits(), True, RiskOutcome.APPROVED, "2", "3"),
        (True, OrderSide.SELL, "5", RiskLimits(), True, RiskOutcome.APPROVED, "5", "0"),
        (True, OrderSide.SELL, "8", RiskLimits(), True, RiskOutcome.RESIZED, "5", "0"),
        (
            False,
            OrderSide.SELL,
            "1",
            RiskLimits(),
            True,
            RiskOutcome.REJECTED,
            "0",
            "0",
        ),
        (
            True,
            OrderSide.SELL,
            "2",
            RiskLimits(allow_selling=False),
            True,
            RiskOutcome.REJECTED,
            "0",
            "5",
        ),
        (True, OrderSide.BUY, "1", RiskLimits(), False, RiskOutcome.REJECTED, "0", "5"),
    ],
)
def test_durable_buy_sell_and_rejected_projections(
    store,
    monkeypatch,
    owned,
    side,
    desired,
    limits,
    enabled,
    outcome,
    approved,
    projected,
):
    if owned:
        _seed(store)
    before = store.path.read_bytes()
    history = store.history()

    def forbidden(*args, **kwargs):
        raise AssertionError("preview attempted a durable write")

    monkeypatch.setattr(ReviewPaperStore, "record_market_review", forbidden)
    preview = _build(
        store,
        proposal=_proposal(side, desired),
        risk_limits=limits,
        new_trading_enabled=enabled,
    )
    current = Decimal("5") if owned else Decimal("0")
    assert preview.risk_decision.outcome is outcome
    assert preview.risk_decision.approved_quantity == Decimal(approved)
    assert preview.current_position_quantity == current
    assert preview.current_position_market_value == current * Decimal("100")
    assert preview.projected_position_quantity == Decimal(projected)
    assert preview.projected_position_market_value == Decimal(projected) * Decimal(
        "100"
    )
    assert preview.projected_total_market_exposure == Decimal(projected) * Decimal(
        "100"
    )
    assert store.history() == history
    assert store.path.read_bytes() == before
    assert (
        _build(
            store,
            proposal=preview.proposal,
            price_snapshot=preview.price_snapshot,
            risk_limits=limits,
            new_trading_enabled=enabled,
        )
        == preview
    )


def test_other_position_exposure_is_preserved(store):
    _seed(store, QQQ)
    result = _build(
        store, price_snapshot=_snapshot({QQQ: Decimal("200"), SPY: Decimal("100")})
    )
    assert result.current_position_quantity == Decimal("0")
    assert result.projected_total_market_exposure == Decimal("1100")


def test_exact_single_authority_calls_and_identity(store, monkeypatch):
    proposal = _proposal()
    snapshot = _snapshot()
    limits = RiskLimits()
    context = module.build_review_paper_risk_context(
        store,
        proposal,
        snapshot.prices,
        as_of=snapshot.observed_at,
        new_trading_enabled=True,
    )
    decision = module.RiskManager(limits).evaluate(proposal, context)
    prices = snapshot.prices
    monkeypatch.setattr(
        ReviewPaperRiskPriceSnapshot, "prices", property(lambda self: prices)
    )
    context_builder = Mock(return_value=context)
    evaluator = Mock(return_value=decision)
    manager = Mock(return_value=Mock(evaluate=evaluator))
    monkeypatch.setattr(module, "build_review_paper_risk_context", context_builder)
    monkeypatch.setattr(module, "RiskManager", manager)

    def forbidden(*args, **kwargs):
        raise AssertionError("direct ledger/account access")

    monkeypatch.setattr(ReviewPaperStore, "reconstruct_ledger", forbidden)
    monkeypatch.setattr(ReviewPaperStore, "create_account_snapshot", forbidden)
    result = _build(
        store, proposal=proposal, price_snapshot=snapshot, risk_limits=limits
    )
    context_builder.assert_called_once_with(
        store, proposal, prices, as_of=snapshot.observed_at, new_trading_enabled=True
    )
    assert context_builder.call_args.args[0] is store
    assert context_builder.call_args.args[1] is proposal
    assert context_builder.call_args.args[2] is prices
    assert context_builder.call_args.kwargs["as_of"] is snapshot.observed_at
    manager.assert_called_once_with(limits)
    assert manager.call_args.args[0] is limits
    evaluator.assert_called_once_with(proposal, context)
    assert evaluator.call_args.args[0] is proposal
    assert evaluator.call_args.args[1] is context
    for name, value in (
        ("proposal", proposal),
        ("price_snapshot", snapshot),
        ("risk_limits", limits),
        ("risk_context", context),
        ("risk_decision", decision),
    ):
        assert getattr(result, name) is value


@pytest.mark.parametrize("boundary", ["context", "manager", "evaluate"])
def test_authority_failures_propagate_without_retry(store, monkeypatch, boundary):
    error = ValueError("authority failed")
    context = module.build_review_paper_risk_context(
        store, _proposal(), _snapshot().prices, as_of=AT, new_trading_enabled=True
    )
    builder = Mock(return_value=context)
    evaluator = Mock(side_effect=error if boundary == "evaluate" else None)
    manager = Mock(return_value=Mock(evaluate=evaluator))
    if boundary == "context":
        builder.side_effect = error
    elif boundary == "manager":
        manager.side_effect = error
    monkeypatch.setattr(module, "build_review_paper_risk_context", builder)
    monkeypatch.setattr(module, "RiskManager", manager)
    with pytest.raises(ValueError) as raised:
        _build(store)
    assert raised.value is error
    assert builder.call_count == 1
    assert manager.call_count == (0 if boundary == "context" else 1)
    assert evaluator.call_count == (1 if boundary == "evaluate" else 0)


@pytest.mark.parametrize(
    "field,expected",
    [
        ("store", ReviewPaperStore),
        ("proposal", TradeProposal),
        ("price_snapshot", ReviewPaperRiskPriceSnapshot),
        ("risk_limits", RiskLimits),
    ],
)
@pytest.mark.parametrize("subclass", [False, True])
def test_builder_exact_types_fail_before_authority(
    store, monkeypatch, field, expected, subclass
):
    value = object.__new__(type("Subclass", (expected,), {})) if subclass else object()
    builder = Mock()
    monkeypatch.setattr(module, "build_review_paper_risk_context", builder)
    with pytest.raises(TypeError, match=field):
        _build(store, **{field: value})
    builder.assert_not_called()


@pytest.mark.parametrize("enabled", [0, 1, None, "true", Decimal("1")])
def test_non_bool_trading_flag(store, monkeypatch, enabled):
    builder = Mock()
    monkeypatch.setattr(module, "build_review_paper_risk_context", builder)
    with pytest.raises(TypeError, match="new_trading_enabled"):
        _build(store, new_trading_enabled=enabled)
    builder.assert_not_called()


@pytest.mark.parametrize("case", ["missing", "extra", "old"])
def test_snapshot_admission_fails_through_131k(store, monkeypatch, case):
    _seed(store, QQQ)
    prices = {SPY: Decimal("100"), QQQ: Decimal("200")}
    observed_at = AT
    if case == "missing":
        del prices[QQQ]
    elif case == "extra":
        prices[Symbol("DIA")] = Decimal("300")
    else:
        observed_at -= timedelta(seconds=1)
    builder = Mock(wraps=module.build_review_paper_risk_context)
    manager = Mock()
    monkeypatch.setattr(module, "build_review_paper_risk_context", builder)
    monkeypatch.setattr(module, "RiskManager", manager)
    with pytest.raises(ValueError, match="precede" if case == "old" else "exactly"):
        _build(store, price_snapshot=_snapshot(prices, observed_at))
    assert builder.call_count == 1
    manager.assert_not_called()


@pytest.mark.parametrize(
    "field",
    ["proposal", "price_snapshot", "risk_limits", "risk_context", "risk_decision"],
)
@pytest.mark.parametrize("subclass", [False, True])
def test_direct_preview_exact_types(store, field, subclass):
    preview = _build(store)
    expected = type(getattr(preview, field))
    value = object.__new__(type("Subclass", (expected,), {})) if subclass else object()
    with pytest.raises(TypeError, match=field):
        replace(preview, **{field: value})


def test_direct_preview_rejects_equal_but_distinct_proposal(store):
    preview = _build(store)
    with pytest.raises(ValueError, match="exact proposal"):
        replace(preview, proposal=replace(preview.proposal))
    with pytest.raises(ValueError, match="exact proposal"):
        replace(
            preview,
            risk_decision=replace(
                preview.risk_decision, proposal=replace(preview.proposal)
            ),
        )


@pytest.mark.parametrize(
    "case", ["decision_time", "snapshot_time", "proposal_time", "price", "symbols"]
)
def test_direct_preview_rejects_cross_object_contradictions(store, case):
    preview = _build(store)
    changes = {}
    if case == "decision_time":
        changes["risk_decision"] = replace(
            preview.risk_decision, evaluated_at=AT + timedelta(seconds=1)
        )
    elif case == "snapshot_time":
        changes["price_snapshot"] = _snapshot(observed_at=AT + timedelta(seconds=1))
    elif case == "proposal_time":
        proposal = replace(preview.proposal, created_at=AT + timedelta(seconds=1))
        changes = {
            "proposal": proposal,
            "risk_decision": replace(preview.risk_decision, proposal=proposal),
        }
    elif case == "price":
        changes["risk_context"] = replace(
            preview.risk_context, current_price=Decimal("101")
        )
    else:
        changes["price_snapshot"] = _snapshot(
            {SPY: Decimal("100"), QQQ: Decimal("200")}
        )
    with pytest.raises(ValueError):
        replace(preview, **changes)


@pytest.mark.parametrize("case", ["position", "exposure"])
def test_direct_preview_rejects_negative_projection(store, case):
    _seed(store)
    preview = _build(store, proposal=_proposal(OrderSide.SELL, "5"))
    context = (
        replace(
            preview.risk_context,
            positions={SPY: Position(SPY, Decimal("1"), Decimal("100"))},
        )
        if case == "position"
        else replace(preview.risk_context, total_market_exposure=Decimal("1"))
    )
    with pytest.raises(ValueError, match="nonnegative"):
        replace(preview, risk_context=context)


@pytest.mark.parametrize("side", [OrderSide.BUY, OrderSide.SELL])
def test_decimal_projections_ignore_ambient_precision_and_traps(side):
    quantity = Decimal("1.2345678901234567890123456789012345678900")
    approved = Decimal("0.0000000000000000000000000000000000000001")
    price = Decimal("123.45678901234567890123456789012345678900")
    proposal = _proposal(side, str(approved))
    snapshot = _snapshot({SPY: price})
    context = RiskContext(
        Decimal("10000"),
        Decimal("20000"),
        {SPY: Position(SPY, quantity, Decimal("100"))},
        price,
        Decimal("1000.0000000000000000000000000000000000000000"),
        True,
        AT,
    )
    decision = RiskDecision(proposal, RiskOutcome.APPROVED, approved, (), AT)
    preview = ReviewPaperForwardPreview(
        proposal, snapshot, RiskLimits(), context, decision
    )
    with localcontext() as arithmetic:
        arithmetic.prec = 200
        current_value = quantity * price
        projected = (
            quantity + approved if side is OrderSide.BUY else quantity - approved
        )
        projected_value = projected * price
        exposure = (
            context.total_market_exposure + approved * price
            if side is OrderSide.BUY
            else context.total_market_exposure - approved * price
        )
    with localcontext() as arithmetic:
        arithmetic.prec = 2
        arithmetic.traps[Inexact] = True
        arithmetic.traps[Rounded] = True
        result = replace(preview)
        assert result.current_position_quantity is quantity
        assert (
            result.current_position_market_value.as_tuple() == current_value.as_tuple()
        )
        assert result.projected_position_quantity.as_tuple() == projected.as_tuple()
        assert (
            result.projected_position_market_value.as_tuple()
            == projected_value.as_tuple()
        )
        assert result.projected_total_market_exposure.as_tuple() == exposure.as_tuple()
        assert result.price_snapshot.marks[0].price is price


def test_preview_frozen_slotted_and_only_risk_public_surface(store):
    preview = _build(store)
    assert not hasattr(preview, "__dict__")
    assert tuple(field.name for field in fields(preview)) == (
        "proposal",
        "price_snapshot",
        "risk_limits",
        "risk_context",
        "risk_decision",
    )
    with pytest.raises(FrozenInstanceError):
        preview.proposal = _proposal()
    assert {
        name
        for name, value in vars(ReviewPaperForwardPreview).items()
        if isinstance(value, property)
    } == {
        "current_position_quantity",
        "current_position_market_value",
        "projected_position_quantity",
        "projected_position_market_value",
        "projected_total_market_exposure",
    }


def test_source_closed_import_and_call_surface_and_exact_composition():
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    expected_imports = {
        "__future__": {"annotations"},
        "dataclasses": {"dataclass"},
        "decimal": {
            "MAX_EMAX",
            "MIN_EMIN",
            "ROUND_HALF_EVEN",
            "Context",
            "Decimal",
            "Inexact",
            "InvalidOperation",
            "Overflow",
        },
        "trading_bot.domain": {"OrderSide", "TradeProposal"},
        "trading_bot.review_paper.risk_context": {"build_review_paper_risk_context"},
        "trading_bot.review_paper.risk_prices": {"ReviewPaperRiskPriceSnapshot"},
        "trading_bot.review_paper.store": {"ReviewPaperStore"},
        "trading_bot.risk.manager": {"RiskManager"},
        "trading_bot.risk.models": {
            "RiskContext",
            "RiskDecision",
            "RiskLimits",
            "RiskOutcome",
        },
    }
    imports = {}
    calls = []
    for node in ast.walk(tree):
        assert not isinstance(
            node, (ast.Import, ast.Try, ast.While, ast.With, ast.AsyncFunctionDef)
        )
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0 and all(alias.asname is None for alias in node.names)
            imports[node.module] = {alias.name for alias in node.names}
        if isinstance(node, ast.Call):
            call = ast.unparse(node.func)
            calls.append(call)
            assert call in {
                "Context",
                "max",
                "min",
                "_context",
                "len",
                "left.adjusted",
                "right.adjusted",
                "left.as_tuple",
                "right.as_tuple",
                "_context(len(left.as_tuple().digits) + "
                "len(right.as_tuple().digits)).multiply",
                "dataclass",
                "type",
                "getattr",
                "TypeError",
                "ValueError",
                "set",
                "Decimal",
                "self.risk_context.positions.get",
                "_multiply",
                "_sum_context",
                "context.add",
                "context.subtract",
                "build_review_paper_risk_context",
                "RiskManager",
                "RiskManager(risk_limits).evaluate",
                "ReviewPaperForwardPreview",
            }
    assert imports == expected_imports
    assert calls.count("build_review_paper_risk_context") == 1
    assert calls.count("RiskManager") == 1
    assert calls.count("RiskManager(risk_limits).evaluate") == 1
    builder = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "build_review_paper_forward_preview"
    )
    assert not builder.args.args and not builder.args.vararg and not builder.args.kwarg
    assert [arg.arg for arg in builder.args.kwonlyargs] == [
        "store",
        "proposal",
        "price_snapshot",
        "risk_limits",
        "new_trading_enabled",
    ]
    actual = ast.Module(body=builder.body[-3:], type_ignores=[])
    expected = ast.parse("""risk_context = build_review_paper_risk_context(
    store, proposal, price_snapshot.prices,
    as_of=price_snapshot.observed_at, new_trading_enabled=new_trading_enabled,
)
decision = RiskManager(risk_limits).evaluate(proposal, risk_context)
return ReviewPaperForwardPreview(
    proposal=proposal, price_snapshot=price_snapshot, risk_limits=risk_limits,
    risk_context=risk_context, risk_decision=decision,
)
""")
    assert ast.dump(actual) == ast.dump(expected)


@pytest.mark.parametrize(
    "outcome,approved,reasons",
    [
        (RiskOutcome.REJECTED, "1", ()),
        (RiskOutcome.APPROVED, "0.5", ()),
        (RiskOutcome.RESIZED, "0", ()),
        (RiskOutcome.RESIZED, "1", ()),
        (RiskOutcome.RESIZED, "0.5", ()),
    ],
)
def test_existing_risk_decision_invariants_remain_authoritative(
    store, outcome, approved, reasons
):
    preview = _build(store)
    with pytest.raises(ValueError):
        replace(
            preview.risk_decision,
            outcome=outcome,
            approved_quantity=Decimal(approved),
            reasons=reasons,
        )
