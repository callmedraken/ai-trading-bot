from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.domain import (
    OrderSide,
    OrderType,
    Position,
    Symbol,
    TimeInForce,
    TradeProposal,
)
from trading_bot.ledger import PaperLedger
from trading_bot.review_paper import (
    ReviewPaperIntent,
    ReviewPaperPerformanceStore,
    ReviewPaperStore,
    RobinhoodEquityOrderReview,
    RobinhoodReviewQuote,
    build_review_paper_risk_context,
)
from trading_bot.risk import RiskContext, RiskOutcome

NOW = datetime(2026, 10, 2, 16, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def _proposal(symbol=SPY, side=OrderSide.BUY) -> TradeProposal:
    return TradeProposal(
        proposal_id=UUID(int=1),
        symbol=symbol,
        side=side,
        desired_quantity=Decimal("1"),
        created_at=NOW,
        reason="explicit proposal",
    )


@pytest.fixture
def store(tmp_path) -> ReviewPaperStore:
    return ReviewPaperStore(tmp_path / "paper.sqlite", starting_cash=Decimal("10000"))


def _buy(store, symbol, quantity, price, identity, commission=Decimal("0")):
    at = NOW - timedelta(minutes=10 - identity)
    intent = ReviewPaperIntent(
        proposal_id=UUID(int=identity),
        order_id=UUID(int=100 + identity),
        symbol=symbol,
        side=OrderSide.BUY,
        desired_quantity=quantity,
        approved_quantity=quantity,
        risk_outcome=RiskOutcome.APPROVED,
        risk_reason_codes=(),
        proposal_reason="durable buy",
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
        market_data_disclosure="explicit test fixture",
    )
    store.record_market_review(intent, review, commission=commission)


def _build(store, proposal=None, prices=None, **kwargs):
    return build_review_paper_risk_context(
        store,
        _proposal() if proposal is None else proposal,
        {SPY: Decimal("123.4500")} if prices is None else prices,
        as_of=kwargs.pop("as_of", NOW),
        new_trading_enabled=kwargs.pop("new_trading_enabled", True),
        **kwargs,
    )


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("cash", [Decimal("10000"), Decimal("1234.5600")])
def test_empty_ledger_exact_mapping(tmp_path, cash, enabled):
    store = ReviewPaperStore(tmp_path / "empty.sqlite", starting_cash=cash)
    assert _build(store, new_trading_enabled=enabled) == RiskContext(
        cash=cash,
        equity=cash,
        positions={},
        current_price=Decimal("123.4500"),
        total_market_exposure=Decimal("0"),
        new_trading_enabled=enabled,
        as_of=NOW,
    )
    assert store.starting_cash == cash


@pytest.mark.parametrize("symbol,side", [(QQQ, OrderSide.BUY), (SPY, OrderSide.SELL)])
def test_durable_weighted_position_and_marked_account(store, symbol, side):
    _buy(store, SPY, Decimal("2"), Decimal("100"), 1, Decimal("2"))
    _buy(store, SPY, Decimal("3"), Decimal("120"), 2, Decimal("3"))
    prices = {SPY: Decimal("150")}
    if symbol == QQQ:
        prices[QQQ] = Decimal("400.2500")
    context = _build(store, _proposal(symbol, side), prices)
    assert context == RiskContext(
        cash=Decimal("9435"),
        equity=Decimal("10185"),
        positions={SPY: Position(SPY, Decimal("5"), Decimal("113"))},
        current_price=prices[symbol],
        total_market_exposure=Decimal("750"),
        new_trading_enabled=True,
        as_of=NOW,
    )
    assert context.positions == store.reconstruct_ledger().positions
    assert context.current_price.as_tuple() == prices[symbol].as_tuple()


def test_multiple_positions_all_marked_preserving_order(store):
    _buy(store, QQQ, Decimal("2"), Decimal("200"), 1)
    _buy(store, SPY, Decimal("3"), Decimal("100"), 2)
    context = _build(store, prices={SPY: Decimal("150"), QQQ: Decimal("250")})
    assert context.cash == Decimal("9300")
    assert context.total_market_exposure == Decimal("950")
    assert context.equity == Decimal("10250")
    assert context.current_price == Decimal("150")
    assert tuple(context.positions) == (QQQ, SPY)
    assert context.positions == store.reconstruct_ledger().positions


@pytest.mark.parametrize(
    "prices", [{}, {QQQ: Decimal("100")}, {SPY: Decimal("100"), QQQ: Decimal("200")}]
)
def test_empty_ledger_requires_exact_proposal_price_set(store, prices):
    with pytest.raises(ValueError, match="exactly"):
        _build(store, prices=prices)


@pytest.mark.parametrize(
    "prices",
    [
        {SPY: Decimal("100")},
        {QQQ: Decimal("200")},
        {SPY: Decimal("100"), QQQ: Decimal("200"), Symbol("DIA"): Decimal("300")},
    ],
)
def test_open_ledger_requires_exact_positions_and_new_proposal_set(store, prices):
    _buy(store, SPY, Decimal("1"), Decimal("100"), 1)
    with pytest.raises(ValueError, match="exactly"):
        _build(store, _proposal(QQQ), prices)


@pytest.mark.parametrize("price", [1, 1.0, "1", None, True])
def test_price_coercion_rejected(store, price):
    with pytest.raises(TypeError, match="Decimal"):
        _build(store, prices={SPY: price})


@pytest.mark.parametrize(
    "price",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_nonfinite_or_nonpositive_price_rejected(store, price):
    with pytest.raises(ValueError, match="finite positive"):
        _build(store, prices={SPY: price})


@pytest.mark.parametrize("key", ["SPY", 1, None])
def test_non_symbol_keys_rejected(store, key):
    with pytest.raises(TypeError, match="Symbol"):
        _build(store, prices={key: Decimal("100")})


@pytest.mark.parametrize("prices", [[], [(SPY, Decimal("100"))], None, "SPY"])
def test_non_mapping_rejected(store, prices):
    with pytest.raises(TypeError, match="Mapping"):
        build_review_paper_risk_context(
            store, _proposal(), prices, as_of=NOW, new_trading_enabled=True
        )


@pytest.mark.parametrize("enabled", [0, 1, None, "true"])
def test_enabled_must_be_exact_bool(store, enabled):
    with pytest.raises(TypeError, match="exactly bool"):
        _build(store, new_trading_enabled=enabled)


@pytest.mark.parametrize(
    "as_of,error",
    [
        (NOW.replace(tzinfo=None), ValueError),
        (NOW - timedelta(microseconds=1), ValueError),
        ("now", TypeError),
        (None, TypeError),
    ],
)
def test_invalid_as_of_rejected(store, as_of, error):
    with pytest.raises(error):
        _build(store, as_of=as_of)


def test_as_of_normalizes_to_utc(store):
    at = NOW.astimezone(timezone(timedelta(hours=-7)))
    context = _build(store, as_of=at)
    assert context.as_of == NOW and context.as_of.tzinfo is UTC


def test_exact_store_and_proposal_types_required(store):
    class DerivedStore(ReviewPaperStore):
        pass

    class DerivedProposal(TradeProposal):
        pass

    for invalid in (None, object(), DerivedStore.__new__(DerivedStore)):
        with pytest.raises(TypeError, match="exactly a ReviewPaperStore"):
            _build(invalid)
    derived = DerivedProposal(
        UUID(int=1), SPY, OrderSide.BUY, Decimal("1"), NOW, "test"
    )
    for invalid in (object(), derived):
        with pytest.raises(TypeError, match="exactly a TradeProposal"):
            _build(store, invalid)


def test_one_reconstruction_one_snapshot_and_exact_mapping(store, monkeypatch):
    ledger = store.reconstruct_ledger()
    calls = []
    prices = MappingProxyType({SPY: Decimal("123.4500")})
    snapshot = ledger.create_account_snapshot(prices, NOW)
    # This snapshot stub exposes only the reviewed context inputs.
    snapshot = SimpleNamespace(
        cash=snapshot.cash,
        equity=snapshot.equity,
        positions_market_value=snapshot.positions_market_value,
    )

    def reconstruct(self):
        assert self is store
        calls.append("reconstruct")
        return ledger

    def create(self, supplied, at):
        assert self is ledger and supplied is prices and at == NOW
        calls.append("snapshot")
        return snapshot

    monkeypatch.setattr(ReviewPaperStore, "reconstruct_ledger", reconstruct)
    monkeypatch.setattr(PaperLedger, "create_account_snapshot", create)
    context = _build(store, prices=prices)
    assert calls == ["reconstruct", "snapshot"]
    assert context.cash == snapshot.cash
    assert context.equity == snapshot.equity
    assert context.total_market_exposure == snapshot.positions_market_value


def test_deterministic_construction_preserves_durable_history_and_valuations(
    store, monkeypatch
):
    _buy(store, SPY, Decimal("2"), Decimal("100"), 1)
    performance = ReviewPaperPerformanceStore(store)
    history = store.history()
    valuations = performance.history()
    durable_bytes = store.path.read_bytes()
    prices = {SPY: Decimal("120")}
    original_prices = prices.copy()

    def forbidden(*args, **kwargs):
        pytest.fail("paper context attempted a durable write")

    monkeypatch.setattr(ReviewPaperStore, "record_market_review", forbidden)
    first = _build(store, prices=prices)
    assert _build(store, prices=MappingProxyType(prices)) == first
    assert store.history() == history
    assert performance.history() == valuations == ()
    assert store.path.read_bytes() == durable_bytes
    assert store.starting_cash == Decimal("10000")
    assert prices == original_prices


def test_source_has_closed_import_and_call_surface():
    import trading_bot.review_paper.risk_context as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imports = {
        "__future__": {"annotations"},
        "collections.abc": {"Mapping"},
        "datetime": {"datetime"},
        "decimal": {"Decimal"},
        "trading_bot.domain": {"Symbol", "TradeProposal"},
        "trading_bot.domain._validation": {"normalize_utc"},
        "trading_bot.review_paper.store": {"ReviewPaperStore"},
        "trading_bot.risk.models": {"RiskContext"},
    }
    actual = {}
    for node in ast.walk(tree):
        assert not isinstance(node, ast.Import)
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert all(alias.asname is None for alias in node.names)
            actual[node.module] = {alias.name for alias in node.names}
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id in {
                    "type",
                    "isinstance",
                    "TypeError",
                    "ValueError",
                    "normalize_utc",
                    "Decimal",
                    "set",
                    "RiskContext",
                }
            else:
                assert isinstance(node.func, ast.Attribute)
                assert ast.unparse(node.func) in {
                    "prices.items",
                    "price.is_finite",
                    "store.reconstruct_ledger",
                    "ledger.create_account_snapshot",
                }
    assert actual == imports
