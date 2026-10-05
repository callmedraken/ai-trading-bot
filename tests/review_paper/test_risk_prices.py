"""Architecture 131-N canonical, transport-free quote risk-price contract."""

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from types import MappingProxyType

import pytest

import trading_bot.review_paper.risk_prices as module
from trading_bot.domain import Symbol
from trading_bot.review_paper.risk_prices import (
    ReviewPaperRiskPriceMark,
    ReviewPaperRiskPriceSnapshot,
    build_review_paper_risk_price_snapshot,
)
from trading_bot.robinhood_mcp.models import (
    RobinhoodEquityQuoteResult,
    RobinhoodEquityQuotesResponse,
    RobinhoodOfficialClose,
    RobinhoodQuoteData,
)

AT = datetime(2026, 10, 2, 18, tzinfo=UTC)
AGE = timedelta(minutes=1)
AAPL = Symbol("AAPL")
SPY = Symbol("SPY")
PRICE = Decimal("123.4500")


class TupleSubclass(tuple):
    pass


class TimedeltaSubclass(timedelta):
    pass


class ResponseSubclass(RobinhoodEquityQuotesResponse):
    pass


def _quote(symbol=SPY, **changes):
    return RobinhoodQuoteData(
        **{
            "symbol": symbol,
            "adjusted_previous_close": Decimal("10"),
            "ask_price": Decimal("200"),
            "bid_price": Decimal("100"),
            "has_traded": True,
            "last_non_reg_trade_price": None,
            "last_trade_price": PRICE,
            "previous_close": Decimal("20"),
            "previous_close_date": "2026-10-01",
            "state": "active",
            "venue_ask_time": AT,
            "venue_bid_time": AT,
            "venue_last_non_reg_trade_time": None,
            "venue_last_trade_time": AT - timedelta(seconds=10),
            **changes,
        }
    )


def _response(*quotes):
    return RobinhoodEquityQuotesResponse(
        tuple(RobinhoodEquityQuoteResult(quote, None) for quote in quotes)
    )


def _build(**changes):
    return build_review_paper_risk_price_snapshot(
        **{
            "response": _response(_quote()),
            "required_symbols": (SPY,),
            "observed_at": AT,
            "max_quote_age": AGE,
            **changes,
        }
    )


def test_exact_single_regular_trade_and_read_only_mapping():
    result = _build()
    assert type(result) is ReviewPaperRiskPriceSnapshot
    assert result == ReviewPaperRiskPriceSnapshot(
        AT, (ReviewPaperRiskPriceMark(SPY, PRICE, AT - timedelta(seconds=10)),)
    )
    assert type(result.prices) is MappingProxyType
    assert dict(result.prices) == {SPY: PRICE}
    assert next(iter(result.prices)) is SPY
    assert result.prices[SPY] is result.marks[0].price
    assert result.prices[SPY].as_tuple() == PRICE.as_tuple()
    with pytest.raises(TypeError):
        result.prices[SPY] = Decimal("1")
    assert result.prices is not result.prices
    assert _build() == result


def test_multiple_symbols_follow_required_order_not_response_order():
    result = _build(
        response=_response(_quote(), _quote(AAPL, last_trade_price=Decimal("42"))),
        required_symbols=(AAPL, SPY),
    )
    assert tuple(mark.symbol for mark in result.marks) == (AAPL, SPY)
    assert tuple(result.prices.items()) == ((AAPL, Decimal("42")), (SPY, PRICE))


@pytest.mark.parametrize(
    "nonregular_price,nonregular_at,expected_price,expected_at",
    [
        (None, None, PRICE, AT - timedelta(seconds=10)),
        (Decimal("99"), None, PRICE, AT - timedelta(seconds=10)),
        (None, AT, PRICE, AT - timedelta(seconds=10)),
        (Decimal("99"), AT, Decimal("99"), AT),
        (Decimal("99"), AT - timedelta(seconds=10), PRICE, AT - timedelta(seconds=10)),
        (Decimal("99"), AT - timedelta(seconds=11), PRICE, AT - timedelta(seconds=10)),
    ],
)
def test_current_trade_selection(
    nonregular_price, nonregular_at, expected_price, expected_at
):
    result = _build(
        response=_response(
            _quote(
                last_non_reg_trade_price=nonregular_price,
                venue_last_non_reg_trade_time=nonregular_at,
            )
        )
    )
    assert result.marks == (ReviewPaperRiskPriceMark(SPY, expected_price, expected_at),)


def test_results_iterated_once_and_candidate_called_once_per_symbol(monkeypatch):
    iterations = []
    calls = []

    class Results(tuple):
        def __iter__(self):
            iterations.append(True)
            return super().__iter__()

    original = RobinhoodQuoteData.current_trade_candidate

    def candidate(self):
        calls.append(self.symbol)
        return original(self)

    def forbidden(*args):
        raise AssertionError("fill policy must not be called")

    monkeypatch.setattr(RobinhoodQuoteData, "current_trade_candidate", candidate)
    monkeypatch.setattr(RobinhoodQuoteData, "require_paper_fill_reference", forbidden)
    response = RobinhoodEquityQuotesResponse(
        Results(
            (
                RobinhoodEquityQuoteResult(_quote(), None),
                RobinhoodEquityQuoteResult(_quote(AAPL), None),
            )
        )
    )
    _build(response=response, required_symbols=(AAPL, SPY))
    assert iterations == [True]
    assert calls == [AAPL, SPY]


def test_official_close_and_closes_error_are_not_authority():
    close = RobinhoodOfficialClose(SPY, "2026-10-02", False, Decimal("999"), "official")
    response = RobinhoodEquityQuotesResponse(
        (
            RobinhoodEquityQuoteResult(_quote(), close),
            None,
            RobinhoodEquityQuoteResult(
                None, RobinhoodOfficialClose(AAPL, None, None, None, None)
            ),
        ),
        closes_error="close unavailable",
    )
    assert _build(response=response) == _build()
    with pytest.raises(ValueError, match="exactly match"):
        _build(
            response=RobinhoodEquityQuotesResponse(
                (RobinhoodEquityQuoteResult(None, close),)
            )
        )


def test_timezone_normalization():
    offset = timezone(timedelta(hours=-7))
    source_at = (AT - timedelta(seconds=10)).astimezone(offset)
    result = _build(
        observed_at=AT.astimezone(offset),
        response=_response(_quote(venue_last_trade_time=source_at)),
    )
    mark = ReviewPaperRiskPriceMark(SPY, PRICE, source_at)
    direct = ReviewPaperRiskPriceSnapshot(AT.astimezone(offset), (mark,))
    assert result == direct == _build()
    assert result.observed_at.tzinfo is UTC
    assert mark.source_at.tzinfo is UTC


@pytest.mark.parametrize("response", [None, (), {}, ResponseSubclass(())])
def test_response_requires_exact_type(response):
    with pytest.raises(TypeError, match="response"):
        _build(response=response)


@pytest.mark.parametrize(
    "symbols,error,match",
    [
        ([SPY], TypeError, "exactly tuple"),
        (TupleSubclass((SPY,)), TypeError, "exactly tuple"),
        (None, TypeError, "exactly tuple"),
        ((), ValueError, "nonempty"),
        (("SPY",), TypeError, "Symbol"),
        ((SPY, SPY), ValueError, "unique"),
        ((SPY, AAPL), ValueError, "canonical"),
    ],
)
def test_required_symbols_contract(symbols, error, match):
    with pytest.raises(error, match=match):
        _build(required_symbols=symbols)


@pytest.mark.parametrize(
    "response,match",
    [
        (_response(_quote(), _quote()), "duplicate"),
        (_response(), "exactly match"),
        (_response(_quote(AAPL)), "exactly match"),
        (_response(_quote(), _quote(AAPL)), "exactly match"),
        (RobinhoodEquityQuotesResponse((None,)), "exactly match"),
        (
            RobinhoodEquityQuotesResponse((RobinhoodEquityQuoteResult(None, None),)),
            "exactly match",
        ),
    ],
)
def test_quote_coverage(response, match):
    with pytest.raises(ValueError, match=match):
        _build(response=response)


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"has_traded": False}, "never traded"),
        ({"state": "inactive"}, "not active"),
        ({"state": "Active"}, "not active"),
        ({"last_trade_price": Decimal("0")}, "positive"),
        ({"venue_last_trade_time": AT + timedelta(microseconds=1)}, "future"),
        ({"venue_last_trade_time": AT - AGE - timedelta(microseconds=1)}, "stale"),
    ],
)
def test_invalid_selected_quote(changes, match):
    with pytest.raises(ValueError, match=match):
        _build(response=_response(_quote(**changes)))


@pytest.mark.parametrize(
    "price",
    [
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        Decimal("-1"),
    ],
)
def test_nonfinite_or_negative_candidate_rejected(monkeypatch, price):
    # Typed quote construction rejects these; inject only the selected candidate.
    monkeypatch.setattr(
        RobinhoodQuoteData, "current_trade_candidate", lambda self: (price, AT)
    )
    with pytest.raises(ValueError, match="finite and positive"):
        _build()


def test_exact_max_age_accepted_and_decimal_context_independent():
    response = _response(_quote(venue_last_trade_time=AT - AGE))
    expected = _build(response=response)
    with localcontext() as context:
        context.prec = 1
        assert _build(response=response) == expected
    assert expected.marks[0].source_at == AT - AGE


@pytest.mark.parametrize(
    "age,error",
    [
        (60, TypeError),
        (None, TypeError),
        (TimedeltaSubclass(seconds=1), TypeError),
        (timedelta(0), ValueError),
        (timedelta(seconds=-1), ValueError),
    ],
)
def test_max_quote_age_contract(age, error):
    with pytest.raises(error, match="max_quote_age"):
        _build(max_quote_age=age)


@pytest.mark.parametrize(
    "observed,error", [(AT.replace(tzinfo=None), ValueError), (None, TypeError)]
)
def test_observed_at_contract(observed, error):
    with pytest.raises(error, match="observed_at"):
        _build(observed_at=observed)


@pytest.mark.parametrize(
    "changes,error",
    [
        ({"symbol": "SPY"}, TypeError),
        ({"price": 123.45}, TypeError),
        ({"price": Decimal("0")}, ValueError),
        ({"price": Decimal("-1")}, ValueError),
        ({"price": Decimal("NaN")}, ValueError),
        ({"price": Decimal("sNaN")}, ValueError),
        ({"price": Decimal("Infinity")}, ValueError),
        ({"source_at": AT.replace(tzinfo=None)}, ValueError),
        ({"source_at": None}, TypeError),
    ],
)
def test_direct_mark_validation(changes, error):
    with pytest.raises(error):
        replace(_build().marks[0], **changes)


@pytest.mark.parametrize(
    "changes,error",
    [
        ({"marks": []}, TypeError),
        ({"marks": TupleSubclass(())}, TypeError),
        ({"marks": ()}, ValueError),
        ({"marks": (None,)}, TypeError),
        ({"marks": (ReviewPaperRiskPriceMark(SPY, PRICE, AT),) * 2}, ValueError),
        (
            {
                "marks": (
                    ReviewPaperRiskPriceMark(SPY, PRICE, AT),
                    ReviewPaperRiskPriceMark(AAPL, PRICE, AT),
                )
            },
            ValueError,
        ),
        (
            {
                "marks": (
                    ReviewPaperRiskPriceMark(
                        SPY, PRICE, AT + timedelta(microseconds=1)
                    ),
                )
            },
            ValueError,
        ),
        ({"observed_at": AT.replace(tzinfo=None)}, ValueError),
        ({"observed_at": None}, TypeError),
    ],
)
def test_direct_snapshot_consistency(changes, error):
    with pytest.raises(error):
        replace(_build(), **changes)


@pytest.mark.parametrize(
    "value,field,new",
    [(_build(), "observed_at", AT), (_build().marks[0], "price", Decimal("1"))],
)
def test_frozen_and_slotted(value, field, new):
    assert not hasattr(value, "__dict__")
    with pytest.raises(FrozenInstanceError):
        setattr(value, field, new)


def _assert_pure_surface(source):
    tree = ast.parse(source)
    imports = {}
    for node in ast.walk(tree):
        assert not isinstance(
            node,
            (
                ast.Import,
                ast.While,
                ast.AsyncFor,
                ast.With,
                ast.AsyncWith,
                ast.Try,
                ast.Await,
                ast.AsyncFunctionDef,
                ast.Lambda,
                ast.Global,
                ast.Nonlocal,
                ast.Delete,
                ast.Yield,
                ast.YieldFrom,
            ),
        )
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert all(alias.asname is None for alias in node.names)
            imports[node.module] = {alias.name for alias in node.names}
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id in {
                    "dataclass",
                    "isinstance",
                    "type",
                    "TypeError",
                    "ValueError",
                    "_normalize_utc",
                    "_require_symbols",
                    "all",
                    "any",
                    "len",
                    "set",
                    "tuple",
                    "sorted",
                    "Decimal",
                    "timedelta",
                    "MappingProxyType",
                    "ReviewPaperRiskPriceMark",
                    "ReviewPaperRiskPriceSnapshot",
                }
            else:
                assert isinstance(node.func, ast.Attribute)
                assert node.func.attr in {
                    "utcoffset",
                    "astimezone",
                    "is_finite",
                    "__setattr__",
                    "current_trade_candidate",
                    "append",
                }
                if node.func.attr == "__setattr__":
                    assert ast.unparse(node.func) == "object.__setattr__"
                    assert ast.unparse(node.args[0]) == "self"
                    assert isinstance(node.args[1], ast.Constant)
                    assert node.args[1].value in {"source_at", "observed_at"}
                if node.func.attr == "append":
                    assert ast.unparse(node.func) == "marks.append"
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                assert not isinstance(target, ast.Attribute)
                if isinstance(target, ast.Subscript):
                    assert ast.unparse(target) == "quotes[quote.symbol]"
        if isinstance(node, ast.For):
            assert ast.unparse(node.iter) in {"response.results", "required_symbols"}
    assert imports == {
        "__future__": {"annotations"},
        "collections.abc": {"Mapping"},
        "dataclasses": {"dataclass"},
        "datetime": {"UTC", "datetime", "timedelta"},
        "decimal": {"Decimal"},
        "types": {"MappingProxyType"},
        "trading_bot.domain": {"Symbol"},
        "trading_bot.robinhood_mcp.models": {
            "RobinhoodEquityQuotesResponse",
            "RobinhoodQuoteData",
        },
    }


def test_source_has_only_pure_bounded_snapshot_capabilities():
    _assert_pure_surface(Path(module.__file__).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "addition",
    [
        "from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter",
        (
            "from trading_bot.robinhood_mcp.sdk_transport "
            "import RobinhoodMcpStreamableHttpTransport"
        ),
        "from trading_bot.robinhood_mcp.windows_oauth import load_token",
        "from trading_bot.review_paper.store import ReviewPaperStore",
        "from trading_bot.review_paper.performance import ReviewPaperPerformanceStore",
        "from trading_bot.risk import RiskManager",
        "from trading_bot.robinhood_paper_pipeline import run_robinhood_paper_pipeline",
        (
            "from trading_bot.robinhood_forward_paper_cycle "
            "import run_robinhood_forward_paper_cycle"
        ),
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "import os",
        "import socket",
        "import subprocess",
        "import uuid",
        "import time",
        "open('paper.sqlite', 'w')",
        "Path('paper.sqlite').write_text('x')",
        "os.getenv('TOKEN')",
        "datetime.now()",
        "datetime.today()",
        "datetime.utcnow()",
        "time.time()",
        "uuid.uuid4()",
        "sleep(1)",
        "retry()",
        "poll()",
        "schedule()",
        "while True: pass",
        "for item in range(10): pass",
        "quote.get_equity_quotes()",
        "quote.review_equity_order()",
        "quote.get_equity_orders()",
        "quote.require_paper_fill_reference()",
        "store.reconstruct_ledger()",
        "build_review_paper_risk_context()",
        "manager.evaluate()",
        "store.record_quotes()",
        "quote.price = Decimal('1')",
    ],
)
def test_structural_guard_rejects_forbidden_capabilities(addition):
    with pytest.raises(AssertionError):
        _assert_pure_surface(
            Path(module.__file__).read_text(encoding="utf-8") + "\n" + addition
        )
