from __future__ import annotations

import json
import logging
import os
import sys
import warnings
from dataclasses import asdict, replace
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot import robinhood_paper_operator as operator
from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce
from trading_bot.review_paper import ReviewPaperIntent, ReviewPaperStore
from trading_bot.risk import RiskOutcome
from trading_bot.robinhood_mcp import (
    RobinhoodMcpStreamableHttpTransport,
    RobinhoodReviewReadTransport,
)

HEAD = "a" * 40
TREE = "b" * 40
_ADMIT_SOURCE = operator._admit_source
ACCOUNT = "private-canonical-account"
RAW = "private-raw-material"


def _intent() -> ReviewPaperIntent:
    return ReviewPaperIntent(
        proposal_id=UUID("11111111-1111-1111-1111-111111111111"),
        order_id=UUID("22222222-2222-2222-2222-222222222222"),
        symbol=Symbol("SPY"),
        side=OrderSide.BUY,
        desired_quantity=Decimal("10"),
        approved_quantity=Decimal("5"),
        risk_outcome=RiskOutcome.RESIZED,
        risk_reason_codes=("MAX_POSITION_PERCENT",),
        proposal_reason=RAW,
        proposal_confidence=Decimal("0.72"),
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        proposed_at=datetime(2026, 10, 2, 15, 0, tzinfo=UTC),
    )


def _quote() -> dict[str, object]:
    return {
        "adjusted_previous_close": "495.00",
        "ask_price": "500.10",
        "bid_price": "500.00",
        "has_traded": True,
        "last_non_reg_trade_price": None,
        "last_trade_price": "500.05",
        "previous_close": "495.00",
        "previous_close_date": "2026-10-01",
        "state": "active",
        "symbol": "SPY",
        "venue_ask_time": "2026-10-02T15:00:01+00:00",
        "venue_bid_time": "2026-10-02T15:00:01+00:00",
        "venue_last_non_reg_trade_time": None,
        "venue_last_trade_time": "2026-10-02T15:00:00+00:00",
    }


def _review() -> dict[str, object]:
    return {
        "data": {
            "market_data_disclosure": RAW,
            "order_checks": {"private": RAW},
            "quantity": "5",
            "quote_data": _quote(),
            "side": "buy",
            "symbol": "SPY",
            "type": "market",
            "account_number": ACCOUNT,
        },
        "guide": RAW,
    }


def _page(cursor: str = "", orders: list | None = None) -> dict:
    return {"data": {"next": cursor, "orders": orders or []}, "guide": RAW}


def _order() -> dict:
    return {
        "id": "real-order-1",
        "symbol": "SPY",
        "side": "buy",
        "state": "filled",
        "placed_agent": "agentic",
        "created_at": "2026-10-02T15:00:01+00:00",
        "last_transaction_at": "2026-10-02T15:00:02+00:00",
        "market_hours": "regular_hours",
        "time_in_force": "gfd",
        "type": "market",
        "trigger": "immediate",
        "quantity": "5",
        "cumulative_quantity": "5",
        "average_price": "500",
        "price": None,
        "stop_price": None,
        "fees": "0",
        "ref_id": None,
        "reject_reason": None,
        "instrument_id": "instrument-1",
        "dollar_based_amount": None,
        "executions": [],
    }


class _Caller:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.pages = [_page(), _page()]
        self.review = _review()
        self.failure: str | None = None
        self.browser_opener = None
        self.reauth = False
        self.noisy = False

    async def __call__(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        if self.noisy:
            _emit_downstream_material()
        if self.reauth:
            self.browser_opener("https://authorization.invalid/?code=" + RAW)
        if self.failure == name:
            raise RuntimeError(ACCOUNT + RAW)
        if name == "get_accounts":
            return {
                "data": {
                    "accounts": [
                        {"account_number": ACCOUNT, "agentic_allowed": True},
                        {
                            "account_number": "ineligible-account",
                            "agentic_allowed": False,
                        },
                    ]
                }
            }
        if name == "get_equity_orders":
            return self.pages.pop(0)
        if name == "review_equity_order":
            return self.review
        raise AssertionError("unexpected tool")


@pytest.fixture
def composition(tmp_path, monkeypatch):
    root = tmp_path / "repository"
    root.mkdir()
    monkeypatch.setattr(operator, "_admit_source", lambda *args: (root,))
    caller = _Caller()

    def oauth_factory(*, redirect_uri, browser_opener):
        assert redirect_uri == "http://127.0.0.1:8765/oauth/callback"
        caller.browser_opener = browser_opener
        return lambda: None

    # Keep the real concrete transport and internal account factory; replace only
    # production construction with the accepted async test-caller entry point.
    class TestTransport(RobinhoodMcpStreamableHttpTransport):
        def __new__(cls, oauth_factory):
            return RobinhoodMcpStreamableHttpTransport.for_test(caller)

    monkeypatch.setattr(operator, "RobinhoodMcpStreamableHttpTransport", TestTransport)
    monkeypatch.setattr(
        operator, "create_windows_robinhood_oauth_factory", oauth_factory
    )
    inputs = {
        "intent": _intent(),
        "review_received_at": datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
        "expected_branch": "feature/robinhood-review-paper-mode",
        "expected_head": HEAD,
        "expected_tree": TREE,
        "paper_store_path": tmp_path / "paper.sqlite",
        "evidence_path": tmp_path / "evidence.json",
        "redirect_uri": "http://127.0.0.1:8765/oauth/callback",
        "starting_cash": Decimal("10000"),
    }
    return caller, inputs, root


def _assert_redacted(evidence, path):
    text = path.read_text()
    assert json.loads(text) == asdict(evidence)
    for secret in (ACCOUNT, RAW, "account_number", "authorization.invalid", "code="):
        assert secret not in text
        assert secret not in repr(evidence)
    assert evidence.placement_calls == 0
    assert evidence.cancellation_calls == 0
    assert evidence.options_mutation_calls == 0
    assert evidence.crypto_mutation_calls == 0


def test_successful_composition_canonical_account_once_and_sanitized(composition):
    caller, inputs, _ = composition
    evidence = operator.run_robinhood_paper_operator(**inputs)
    assert evidence.status == "PASS"
    assert evidence.phase == "complete"
    assert [name for name, _ in caller.calls] == [
        "get_accounts",
        "get_equity_orders",
        "review_equity_order",
        "get_equity_orders",
    ]
    assert all(args["account_number"] == ACCOUNT for _, args in caller.calls[1:])
    assert caller.calls[2][1]["quantity"] == "5"
    assert evidence.get_accounts_calls == 1
    assert evidence.get_equity_orders_calls == 2
    assert evidence.review_equity_order_calls == 1
    assert evidence.get_equity_quotes_calls == 0
    assert evidence.baseline_order_pages == evidence.post_review_order_pages == 1
    assert evidence.paper_record_count == 1
    assert evidence.review_echo_validated and evidence.quote_fill_validated
    assert evidence.disclosure_present and not evidence.replay
    assert evidence.interactive_reauth_count == 0
    _assert_redacted(evidence, inputs["evidence_path"])
    store = ReviewPaperStore(inputs["paper_store_path"], starting_cash=Decimal("10000"))
    assert store.history()[0].fill_price == Decimal("500.10")
    assert ACCOUNT.encode() not in inputs["paper_store_path"].read_bytes()


@pytest.mark.parametrize("conflict", [False, True])
def test_durable_replay_and_conflict_make_zero_calls(composition, conflict):
    caller, inputs, _ = composition
    assert operator.run_robinhood_paper_operator(**inputs).status == "PASS"
    before = inputs["paper_store_path"].read_bytes()
    caller.calls.clear()
    inputs["evidence_path"] = inputs["evidence_path"].with_name("second.json")
    if conflict:
        inputs["intent"] = replace(inputs["intent"], proposal_reason="changed intent")
    result = operator.run_robinhood_paper_operator(**inputs)
    assert caller.calls == []
    assert result.get_accounts_calls == result.get_equity_orders_calls == 0
    assert result.review_equity_order_calls == result.get_equity_quotes_calls == 0
    assert result.status == ("FAIL" if conflict else "PASS")
    assert result.replay is (not conflict)
    assert result.paper_record_count == 1
    assert inputs["paper_store_path"].read_bytes() == before
    _assert_redacted(result, inputs["evidence_path"])


def test_pagination_exhausted_for_both_windows(composition):
    caller, inputs, _ = composition
    caller.pages = [_page("baseline-2"), _page(), _page("post-2"), _page()]
    result = operator.run_robinhood_paper_operator(**inputs)
    assert result.status == "PASS"
    assert result.baseline_order_pages == result.post_review_order_pages == 2
    assert result.get_equity_orders_calls == 4
    assert [
        args.get("cursor") for name, args in caller.calls if name == "get_equity_orders"
    ] == [None, "baseline-2", None, "post-2"]
    assert all(args["account_number"] == ACCOUNT for _, args in caller.calls[1:])


@pytest.mark.parametrize("after", [False, True])
def test_real_orders_block_review_or_persistence_on_later_page(composition, after):
    caller, inputs, _ = composition
    caller.pages = ([_page()] if after else []) + [
        _page("later"),
        _page(orders=[_order()]),
    ]
    result = operator.run_robinhood_paper_operator(**inputs)
    assert result.status == "FAIL"
    assert result.phase == ("post_review" if after else "baseline")
    assert result.review_equity_order_calls == int(after)
    assert result.paper_record_count == 0
    assert not result.quote_fill_validated
    assert [name for name, _ in caller.calls].count("review_equity_order") == int(after)
    _assert_redacted(result, inputs["evidence_path"])


@pytest.mark.parametrize(
    "tool", ["get_accounts", "get_equity_orders", "review_equity_order"]
)
def test_upstream_errors_are_not_evidence(composition, tool, capsys, caplog):
    caller, inputs, _ = composition
    caller.failure = tool
    result = operator.run_robinhood_paper_operator(**inputs)
    assert result.status == "FAIL"
    assert result.paper_record_count == 0
    _assert_redacted(result, inputs["evidence_path"])
    assert capsys.readouterr().out == ""
    assert ACCOUNT not in caplog.text and RAW not in caplog.text


def test_browser_reauthorization_attempt_fails_closed(composition):
    caller, inputs, _ = composition
    caller.reauth = True
    result = operator.run_robinhood_paper_operator(**inputs)
    assert result.status == "FAIL"
    assert result.phase == "interactive_reauth_blocked"
    assert result.interactive_reauth_count == 1
    assert result.review_equity_order_calls == result.get_equity_orders_calls == 0
    assert result.paper_record_count == 0
    _assert_redacted(result, inputs["evidence_path"])


@pytest.mark.parametrize("field", ["evidence_path", "paper_store_path"])
@pytest.mark.parametrize("relative", ["output", "child/../output"])
def test_paths_inside_repository_rejected_before_calls(composition, field, relative):
    caller, inputs, root = composition
    inputs[field] = root / relative
    with pytest.raises(
        operator.RobinhoodPaperOperatorError, match="outside repository"
    ):
        operator.run_robinhood_paper_operator(**inputs)
    assert caller.calls == []
    assert not inputs["paper_store_path"].exists()
    assert not inputs["evidence_path"].exists()


def test_other_registered_worktree_is_also_rejected(composition, monkeypatch, tmp_path):
    caller, inputs, root = composition
    other = tmp_path / "other-worktree"
    monkeypatch.setattr(operator, "_admit_source", lambda *args: (root, other))
    inputs["evidence_path"] = other / "evidence.json"
    with pytest.raises(operator.RobinhoodPaperOperatorError):
        operator.run_robinhood_paper_operator(**inputs)
    assert not caller.calls


@pytest.mark.parametrize("field", ["evidence_path", "paper_store_path"])
def test_relative_paths_rejected(composition, field):
    caller, inputs, _ = composition
    inputs[field] = Path("relative")
    with pytest.raises(operator.RobinhoodPaperOperatorError):
        operator.run_robinhood_paper_operator(**inputs)
    assert not caller.calls


@pytest.mark.parametrize("suffix", ["", "-wal", "-shm", "-journal"])
def test_evidence_cannot_overwrite_store_or_sidecars(composition, suffix):
    caller, inputs, _ = composition
    inputs["evidence_path"] = Path(str(inputs["paper_store_path"]) + suffix)
    with pytest.raises(operator.RobinhoodPaperOperatorError, match="overlap"):
        operator.run_robinhood_paper_operator(**inputs)
    assert not caller.calls


def test_existing_evidence_is_preserved_and_blocks_calls(composition):
    caller, inputs, _ = composition
    inputs["evidence_path"].write_text("existing evidence")
    with pytest.raises(operator.RobinhoodPaperOperatorError):
        operator.run_robinhood_paper_operator(**inputs)
    assert not caller.calls
    assert inputs["evidence_path"].read_text() == "existing evidence"


@pytest.mark.parametrize(
    "change",
    [
        {"starting_cash": Decimal("NaN")},
        {"commission": Decimal("-1")},
        {"slippage_basis_points": Decimal("10000")},
        {"review_received_at": datetime(2026, 10, 2, 15, 0, 2)},
        {"review_received_at": datetime(2026, 10, 1, tzinfo=UTC)},
    ],
)
def test_invalid_inputs_block_calls_and_output(composition, change):
    caller, inputs, _ = composition
    inputs.update(change)
    with pytest.raises(operator.RobinhoodPaperOperatorError, match="inputs"):
        operator.run_robinhood_paper_operator(**inputs)
    assert not caller.calls
    assert not inputs["evidence_path"].exists()


@pytest.mark.parametrize("bad", ["echo", "quote", "timestamp"])
def test_review_echo_and_fill_policy_fail_closed(composition, bad):
    caller, inputs, _ = composition
    if bad == "echo":
        caller.review["data"]["quantity"] = "999"
    elif bad == "quote":
        caller.review["data"]["quote_data"]["ask_price"] = "0"
    else:
        caller.review["data"]["quote_data"]["venue_ask_time"] = "2026-10-01T15:00:01Z"
    result = operator.run_robinhood_paper_operator(**inputs)
    assert result.status == "FAIL"
    assert result.paper_record_count == 0
    assert not result.quote_fill_validated
    assert result.review_echo_validated is (bad == "timestamp")
    _assert_redacted(result, inputs["evidence_path"])


def test_fill_is_independent_of_ambient_decimal_context(composition):
    _, inputs, _ = composition
    with localcontext() as context:
        context.prec = 2
        result = operator.run_robinhood_paper_operator(**inputs)
        assert context.prec == 2
    assert result.status == "PASS"
    assert ReviewPaperStore(
        inputs["paper_store_path"], starting_cash=Decimal("10000")
    ).history()[0].fill_price == Decimal("500.10")


@pytest.mark.parametrize("mismatch", ["root", "branch", "head", "tree", "dirty"])
def test_source_admission_rejects_drift_before_output(
    composition, monkeypatch, mismatch
):
    caller, inputs, _ = composition
    monkeypatch.setattr(operator, "_admit_source", _ADMIT_SOURCE)
    root = Path(operator.__file__).resolve().parents[2]
    replies = {
        ("rev-parse", "--show-toplevel"): str(root),
        ("branch", "--show-current"): inputs["expected_branch"],
        ("rev-parse", "HEAD"): HEAD,
        ("rev-parse", "HEAD^{tree}"): TREE,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
        ("worktree", "list", "--porcelain"): f"worktree {root}",
    }
    key = {
        "root": ("rev-parse", "--show-toplevel"),
        "branch": ("branch", "--show-current"),
        "head": ("rev-parse", "HEAD"),
        "tree": ("rev-parse", "HEAD^{tree}"),
        "dirty": ("status", "--porcelain=v1", "--untracked-files=all"),
    }[mismatch]
    replies[key] = str(root.parent) if mismatch == "root" else "wrong"
    monkeypatch.setattr(operator, "_git", lambda root, *args: replies[args])
    with pytest.raises(operator.RobinhoodPaperOperatorError, match="source identity"):
        operator.run_robinhood_paper_operator(**inputs)
    assert not caller.calls
    assert not inputs["evidence_path"].exists()


def test_source_admission_registers_all_worktree_roots(monkeypatch, tmp_path):
    root = Path(operator.__file__).resolve().parents[2]
    replies = {
        ("rev-parse", "--show-toplevel"): str(root),
        ("branch", "--show-current"): "expected-branch",
        ("rev-parse", "HEAD"): HEAD,
        ("rev-parse", "HEAD^{tree}"): TREE,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
        ("worktree", "list", "--porcelain"): f"worktree {root}\n\nworktree {tmp_path}",
    }
    calls = []

    def source_git(root, *args):
        calls.append(args)
        return replies[args]

    monkeypatch.setattr(operator, "_git", source_git)
    assert operator._admit_source("expected-branch", HEAD, TREE) == (
        root,
        tmp_path.resolve(),
    )

    assert ("status", "--porcelain=v1", "--untracked-files=all") in calls


def test_git_failure_suppresses_raw_stderr(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise RuntimeError(RAW + ACCOUNT)

    monkeypatch.setattr(operator.subprocess, "run", fail)
    with pytest.raises(operator.RobinhoodPaperOperatorError) as caught:
        operator._git(tmp_path, "rev-parse", "HEAD")
    assert RAW not in str(caught.value) and ACCOUNT not in str(caught.value)
    assert caught.value.__suppress_context__


def test_public_mcp_surface_exact_and_mutation_methods_absent():
    expected = {"review_equity_order", "get_equity_quotes", "get_equity_orders"}
    assert {
        name
        for name in RobinhoodReviewReadTransport.__dict__
        if not name.startswith("_")
    } == expected
    assert {
        name
        for name in RobinhoodMcpStreamableHttpTransport.__dict__
        if not name.startswith("_") and name != "for_test"
    } == expected
    for name in (
        "get_accounts",
        "call_tool",
        "place_equity_order",
        "cancel_equity_order",
        "place_option_order",
        "cancel_option_order",
        "exercise_option",
        "place_crypto_order",
        "cancel_crypto_order",
    ):
        assert not hasattr(RobinhoodMcpStreamableHttpTransport, name)


def test_real_windows_factory_redirect_denial_without_browser_or_listener(
    composition, monkeypatch
):
    from trading_bot.robinhood_mcp import sdk_transport, windows_oauth

    caller, inputs, _ = composition
    callbacks = {}
    closed = []

    class FakeServer:
        def close(self):
            closed.append(True)

        async def wait_closed(self):
            pass

    async def fake_listener(*args, **kwargs):
        return FakeServer()

    def capture_provider(**kwargs):
        callbacks.update(kwargs)
        return lambda: object()

    async def reauth_request(name, arguments):
        caller.calls.append((name, dict(arguments)))
        await callbacks["redirect_handler"](
            "https://authorization.invalid/?state=" + RAW
        )
        raise AssertionError("reauthorization must never complete")

    class TestTransport(RobinhoodMcpStreamableHttpTransport):
        def __new__(cls, oauth_factory):
            return RobinhoodMcpStreamableHttpTransport.for_test(reauth_request)

    monkeypatch.setattr(
        operator,
        "create_windows_robinhood_oauth_factory",
        windows_oauth.create_windows_robinhood_oauth_factory,
    )
    monkeypatch.setattr(
        sdk_transport, "create_robinhood_oauth_factory", capture_provider
    )
    monkeypatch.setattr(windows_oauth.asyncio, "start_server", fake_listener)
    monkeypatch.setattr(operator, "RobinhoodMcpStreamableHttpTransport", TestTransport)
    result = operator.run_robinhood_paper_operator(**inputs)
    assert result.status == "FAIL"
    assert result.phase == "interactive_reauth_blocked"
    assert result.interactive_reauth_count == 1
    assert result.paper_record_count == 0
    assert result.review_equity_order_calls == result.get_equity_orders_calls == 0
    assert closed
    _assert_redacted(result, inputs["evidence_path"])


def _emit_downstream_material() -> None:
    material = ACCOUNT + RAW
    print(material)
    sys.stderr.write(material + "\n")
    os.write(1, material.encode())
    os.write(2, material.encode())
    logging.getLogger("downstream").warning(material)
    # Even warnings configured to emit, and direct standard logger dispatch,
    # remain discarded inside the bounded operation.
    warnings.simplefilter("always")
    warnings.warn(material, RuntimeWarning, stacklevel=1)
    logging.getLogger("downstream").handle(
        logging.LogRecord("downstream", logging.ERROR, "", 0, material, (), None)
    )


@pytest.mark.parametrize("failure", [None, "review_equity_order"])
def test_downstream_output_logs_and_warnings_never_escape(
    composition, monkeypatch, capfd, caplog, failure
):
    caller, inputs, _ = composition
    caller.noisy = True
    caller.failure = failure
    factory = operator.create_windows_robinhood_oauth_factory

    def noisy_composition(**kwargs):
        _emit_downstream_material()
        return factory(**kwargs)

    monkeypatch.setattr(
        operator, "create_windows_robinhood_oauth_factory", noisy_composition
    )
    result = operator.run_robinhood_paper_operator(**inputs)
    assert result.status == ("PASS" if failure is None else "FAIL")
    assert result.paper_record_count == (1 if failure is None else 0)
    assert result.post_review_order_pages == 1
    captured = capfd.readouterr()
    assert captured.out == captured.err == ""
    assert ACCOUNT not in caplog.text and RAW not in caplog.text
    _assert_redacted(result, inputs["evidence_path"])


@pytest.mark.parametrize("failure", [None, RuntimeError, KeyboardInterrupt, SystemExit])
def test_suppression_restores_process_state_on_every_exit(failure, capfd, caplog):
    previous_disable = logging.root.manager.disable
    logging.disable(logging.ERROR)
    streams = (sys.stdout, sys.stderr)
    handle = logging.Logger.handle
    showwarning = warnings.showwarning
    filters = warnings.filters
    filter_contents = list(filters)
    descriptors = (os.fstat(1), os.fstat(2))
    try:

        def suppressed():
            with operator._suppress_downstream_output():
                _emit_downstream_material()
                if failure:
                    raise failure("terminal control")

        if failure:
            with pytest.raises(failure):
                suppressed()
        else:
            suppressed()
        assert (sys.stdout, sys.stderr) == streams
        assert logging.root.manager.disable == logging.ERROR
        assert logging.Logger.handle is handle
        assert warnings.showwarning is showwarning
        assert warnings.filters is filters and warnings.filters == filter_contents
        assert (os.fstat(1), os.fstat(2)) == descriptors
        captured = capfd.readouterr()
        assert captured.out == captured.err == ""
        assert ACCOUNT not in caplog.text and RAW not in caplog.text
        print("caller stdout restored")
        sys.stderr.write("caller stderr restored\n")
        os.write(1, b"caller fd1 restored\n")
        os.write(2, b"caller fd2 restored\n")
        logging.getLogger("caller").critical("caller logging restored")
        captured = capfd.readouterr()
        assert "caller stdout restored" in captured.out
        assert "caller fd1 restored" in captured.out
        assert "caller stderr restored" in captured.err
        assert "caller fd2 restored" in captured.err
        assert "caller logging restored" in caplog.text
    finally:
        logging.disable(previous_disable)


@pytest.mark.parametrize("disclosure", ["", " ", "\t\n", None, " disclosure "])
def test_disclosure_present_requires_nonblank_string_on_new_cycle_and_replay(
    composition, disclosure
):
    caller, inputs, _ = composition
    caller.review["data"]["market_data_disclosure"] = disclosure
    expected = isinstance(disclosure, str) and bool(disclosure.strip())
    first = operator.run_robinhood_paper_operator(**inputs)
    assert first.status == "PASS"
    assert first.disclosure_present is expected
    inputs["evidence_path"] = inputs["evidence_path"].with_name("replay.json")
    caller.calls.clear()
    replay = operator.run_robinhood_paper_operator(**inputs)
    assert replay.status == "PASS" and replay.replay
    assert replay.disclosure_present is expected
    assert caller.calls == []
